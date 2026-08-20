#!/usr/bin/env python3
"""3D Gaussian Splatting training with mask-based loss exclusion.

Standalone script run via subprocess. Imports Inria gaussian-splatting
modules and adds mask support to prevent floaters on dynamic objects.

Usage:
    python train_masked.py \
        --source_path /path/to/scene \
        --model_path /path/to/output \
        --mask_path /path/to/masks \
        --iterations 30000
"""

import sys
import os

# Add gaussian-splatting to path
GS_ROOT = os.environ.get(
    "GS_ROOT", "/workspace/third_party/gaussian-splatting"
)
sys.path.insert(0, GS_ROOT)

import torch
import numpy as np
from pathlib import Path
from argparse import ArgumentParser
from random import randint
from PIL import Image
from tqdm import tqdm

from gaussian_renderer import render
from scene import Scene, GaussianModel
from arguments import ModelParams, PipelineParams, OptimizationParams
from utils.loss_utils import l1_loss, ssim


# ---------------------------------------------------------------------------
# Mask loading
# ---------------------------------------------------------------------------

_mask_cache: dict[str, torch.Tensor] = {}


def load_mask(mask_dir: str, image_name: str, H: int, W: int,
              device: torch.device) -> torch.Tensor:
    """Load mask for an image. Returns (1, H, W) tensor: 1=keep, 0=exclude.

    Our pipeline convention: white (255) = dynamic → exclude from loss.
    """
    if not mask_dir:
        return torch.ones(1, H, W, device=device)

    cache_key = image_name
    if cache_key in _mask_cache:
        return _mask_cache[cache_key].to(device)

    stem = Path(image_name).stem
    for ext in (".png", ".jpg"):
        p = Path(mask_dir) / (stem + ext)
        if p.exists():
            mask = np.array(Image.open(p).convert("L")).astype(np.float32) / 255.0
            # Resize if needed
            if mask.shape[0] != H or mask.shape[1] != W:
                from torchvision.transforms.functional import resize
                t = torch.from_numpy(mask).unsqueeze(0)
                t = resize(t, [H, W])
                mask = t.squeeze(0).numpy()
            weight = 1.0 - mask  # invert: 0=dynamic→exclude, 1=static→keep
            weight_t = torch.from_numpy(weight).float().unsqueeze(0)
            _mask_cache[cache_key] = weight_t
            return weight_t.to(device)

    # No mask → keep all pixels
    fallback = torch.ones(1, H, W, device=device)
    _mask_cache[cache_key] = fallback.cpu()
    return fallback


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train(args_list: list[str]):
    parser = ArgumentParser(description="3DGS training with mask support")
    lp = ModelParams(parser)
    op = OptimizationParams(parser)
    pp = PipelineParams(parser)
    parser.add_argument("--mask_path", type=str, default="")
    parser.add_argument("--save_iterations", nargs="+", type=int,
                        default=[7_000, 30_000])
    parser.add_argument("--quiet", action="store_true")
    parsed = parser.parse_args(args_list)

    dataset = lp.extract(parsed)
    opt = op.extract(parsed)
    pipe = pp.extract(parsed)
    mask_path = parsed.mask_path
    save_iters = set(parsed.save_iterations)
    quiet = parsed.quiet

    # Initialise Gaussians and scene
    gaussians = GaussianModel(dataset.sh_degree)
    scene = Scene(dataset, gaussians)
    gaussians.training_setup(opt)

    bg_color = [1, 1, 1] if dataset.white_background else [0, 0, 0]
    background = torch.tensor(bg_color, dtype=torch.float32, device="cuda")

    viewpoints = scene.getTrainCameras().copy()
    n_views = len(viewpoints)
    iterations = opt.iterations

    print(f"[3DGS] Training: {n_views} views, {iterations} iterations, "
          f"mask={'YES' if mask_path else 'NO'}")

    progress = tqdm(range(1, iterations + 1), disable=quiet,
                    desc="Training")

    for iteration in progress:
        gaussians.update_learning_rate(iteration)

        # Random viewpoint
        viewpoint_cam = viewpoints[randint(0, n_views - 1)]

        # Render
        render_pkg = render(viewpoint_cam, gaussians, pipe, background)
        image = render_pkg["render"]          # (3, H, W)
        viewspace_points = render_pkg["viewspace_points"]
        visibility_filter = render_pkg["visibility_filter"]
        radii = render_pkg["radii"]

        gt_image = viewpoint_cam.original_image.cuda()  # (3, H, W)

        # ── Mask-weighted loss ─────────────────────────────────────────
        _, H, W = gt_image.shape
        weight = load_mask(mask_path, viewpoint_cam.image_name, H, W,
                           gt_image.device)  # (1, H, W)

        Ll1 = l1_loss(image * weight, gt_image * weight)
        loss_ssim = 1.0 - ssim(image * weight, gt_image * weight)
        loss = ((1.0 - opt.lambda_dssim) * Ll1
                + opt.lambda_dssim * loss_ssim)

        loss.backward()

        with torch.no_grad():
            if not quiet and iteration % 500 == 0:
                progress.set_postfix({"loss": f"{loss.item():.4f}",
                                      "pts": gaussians.get_xyz.shape[0]})

            # Densification
            if iteration < opt.densify_until_iter:
                gaussians.max_radii2D[visibility_filter] = torch.max(
                    gaussians.max_radii2D[visibility_filter],
                    radii[visibility_filter],
                )
                gaussians.add_densification_stats(
                    viewspace_points, visibility_filter,
                )

                if (iteration > opt.densify_from_iter
                        and iteration % opt.densification_interval == 0):
                    size_threshold = (
                        20 if iteration > opt.opacity_reset_interval else None
                    )
                    gaussians.densify_and_prune(
                        opt.densify_grad_threshold,
                        0.005,  # min_opacity
                        scene.cameras_extent,
                        size_threshold,
                        radii,
                    )

                if iteration % opt.opacity_reset_interval == 0:
                    gaussians.reset_opacity()

            # Optimizer step
            gaussians.optimizer.step()
            gaussians.optimizer.zero_grad(set_to_none=True)

            # Save checkpoint
            if iteration in save_iters:
                print(f"\n[3DGS] Saving at iteration {iteration} "
                      f"({gaussians.get_xyz.shape[0]} Gaussians)")
                scene.save(iteration)

    print(f"[3DGS] Training complete. Final: {gaussians.get_xyz.shape[0]} Gaussians")


if __name__ == "__main__":
    train(sys.argv[1:])

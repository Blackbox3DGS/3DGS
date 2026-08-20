"""Depth Anything V2 inference utilities."""

import logging
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

logger = logging.getLogger(__name__)

MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"


def load_model(device: torch.device):
    """Load Depth Anything V2 Small and its image processor."""
    logger.info("Loading model %s on %s ...", MODEL_ID, device)
    processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForDepthEstimation.from_pretrained(MODEL_ID).to(device)
    model.eval()
    return processor, model


def estimate_depth(
    image_path: Path,
    processor,
    model,
    device: torch.device,
) -> np.ndarray:
    """Run depth estimation on a single image.

    Returns:
        depth_map: np.ndarray of shape (H, W) with values in [0, 1].
    """
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    post = processor.post_process_depth_estimation(
        outputs,
        target_sizes=[(image.height, image.width)],
    )
    depth = post[0]["predicted_depth"]  # (H, W) tensor

    # Normalise to [0, 1]
    d_min = depth.min()
    d_max = depth.max()
    if d_max - d_min > 0:
        depth = (depth - d_min) / (d_max - d_min)
    else:
        depth = torch.zeros_like(depth)

    return depth.cpu().numpy().astype(np.float32)


def save_depth_vis(depth: np.ndarray, out_path: Path) -> None:
    """Save a depth map as a colorised PNG (INFERNO colormap)."""
    depth_u8 = (depth * 255).clip(0, 255).astype(np.uint8)
    colored = cv2.applyColorMap(depth_u8, cv2.COLORMAP_INFERNO)
    cv2.imwrite(str(out_path), colored)


def estimate_depth_batch(
    image_dir: Path,
    out_dir: Path,
    device: torch.device,
    vis_dir: Path | None = None,
) -> int:
    """Run depth estimation on all .jpg images in *image_dir*.

    Saves each depth map as a .npy file (float32, H x W, 0-1) in *out_dir*.
    If *vis_dir* is given, also saves colourised .png visualisations.
    Returns the number of processed frames.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if vis_dir is not None:
        vis_dir.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(image_dir.glob("*.jpg"))
    if not image_paths:
        raise FileNotFoundError(f"No .jpg images found in {image_dir}")

    processor, model = load_model(device)

    count = 0
    for idx, img_path in enumerate(image_paths):
        depth = estimate_depth(img_path, processor, model, device)
        npy_name = img_path.stem + ".npy"
        np.save(out_dir / npy_name, depth)

        if vis_dir is not None:
            save_depth_vis(depth, vis_dir / (img_path.stem + ".png"))

        count += 1
        if (idx + 1) % 50 == 0 or (idx + 1) == len(image_paths):
            logger.info("  depth %d / %d", idx + 1, len(image_paths))

    return count

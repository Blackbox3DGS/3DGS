"""Semantic segmentation for sky and far-background masking.

Uses SegFormer-B0 (ADE20K) to identify sky and other unreliable-to-reconstruct
regions (sky, mountain, distant buildings). These masks are OR-combined with
dynamic-object masks in Stage 03 to exclude them from 3DGS training loss,
preventing floaters and freeing capacity for the relevant accident scene.
"""

import logging
import os
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

logger = logging.getLogger(__name__)

# ADE20K class ids — safe defaults for accident-scene reconstruction.
# 2: sky, 16: mountain/hill, 26: house (far), 48: skyscraper, 84: tower
SKY_CLASSES_DEFAULT = {2, 16, 26, 48, 84}

# Optional extra classes — vegetation. Off by default (street trees may be wanted).
# 4: tree, 9: grass, 17: plant
SKY_EXTRA_CLASSES = {4, 9, 17}

SKY_MODEL = "nvidia/segformer-b0-finetuned-ade-512-512"


def _resolve_classes() -> set[int]:
    classes = set(SKY_CLASSES_DEFAULT)
    if os.getenv("SKY_INCLUDE_VEGETATION", "0") == "1":
        classes |= SKY_EXTRA_CLASSES
    return classes


def load_segformer(name: str = SKY_MODEL):
    """Returns (processor, model, device). Model on CUDA when available."""
    from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Loading SegFormer: %s (device=%s)", name, device)
    processor = SegformerImageProcessor.from_pretrained(name)
    model = SegformerForSemanticSegmentation.from_pretrained(name).to(device).eval()
    return processor, model, device


def run_semantic_masks(
    frame_paths: list[Path],
    out_dir: Path,
    sky_classes: set[int] | None = None,
    batch_size: int = 4,
) -> dict[str, np.ndarray]:
    """Run SegFormer over frames, build bool sky-mask per frame.

    Args:
        frame_paths: list of .jpg paths (sorted).
        out_dir: directory to write per-frame sky_mask PNGs for QA.
        sky_classes: ADE20K class ids to treat as "exclude". Defaults to SKY_CLASSES_DEFAULT
            (extended via SKY_INCLUDE_VEGETATION=1).
        batch_size: inference batch size.

    Returns:
        dict keyed by frame name (basename, matches FrameDetections.frame_name) →
        bool ndarray of shape (H, W). True means "mask out (exclude from 3DGS)".
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    classes = sky_classes if sky_classes is not None else _resolve_classes()
    classes_arr = np.array(sorted(classes), dtype=np.int64)
    logger.info("Semantic masks: %d frames, classes=%s", len(frame_paths), sorted(classes))

    processor, model, device = load_segformer()

    results: dict[str, np.ndarray] = {}

    for start in range(0, len(frame_paths), batch_size):
        batch_paths = frame_paths[start : start + batch_size]
        imgs = [Image.open(p).convert("RGB") for p in batch_paths]
        sizes = [img.size for img in imgs]  # (W, H)

        inputs = processor(images=imgs, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**inputs).logits  # (B, 150, h/4, w/4)

        for i, (p, (W, H)) in enumerate(zip(batch_paths, sizes)):
            up = F.interpolate(
                logits[i : i + 1], size=(H, W), mode="bilinear", align_corners=False
            )
            pred = up.argmax(dim=1)[0].cpu().numpy()  # (H, W) int
            sky = np.isin(pred, classes_arr)  # bool (H, W)
            results[p.name] = sky

            # Per-frame PNG for visual QA (white = sky/exclude).
            cv2.imwrite(str(out_dir / f"{p.stem}.png"), (sky.astype(np.uint8) * 255))

    logger.info(
        "Semantic masks done: %d frames, mean sky coverage=%.1f%%",
        len(results),
        100.0 * np.mean([m.mean() for m in results.values()]) if results else 0.0,
    )
    return results

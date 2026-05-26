"""Sky segmentation via SegFormer-B0 (ADE20K).

ADE20K label 2 = "sky".  Produces binary PNG masks (255 = sky, 0 = not-sky)
matching each source frame, then merges them with existing dynamic masks.
"""

import logging
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

logger = logging.getLogger(__name__)

_ADE20K_SKY_LABEL = 2
_MODEL_NAME = "nvidia/segformer-b0-finetuned-ade-512-512"


def _load_model(device: torch.device):
    logger.info("Loading SegFormer-B0 (ADE20K) from %s ...", _MODEL_NAME)
    processor = SegformerImageProcessor.from_pretrained(_MODEL_NAME)
    model = SegformerForSemanticSegmentation.from_pretrained(_MODEL_NAME)
    model.to(device).eval()
    return processor, model


def run_sky_segmentation(
    frame_paths: list[Path],
    out_dir: Path,
    device: torch.device | None = None,
) -> Path:
    """Generate per-frame sky masks from *frame_paths* and write to *out_dir*.

    Returns *out_dir* (the directory of written .png masks).
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    out_dir.mkdir(parents=True, exist_ok=True)
    processor, model = _load_model(device)

    for i, fp in enumerate(frame_paths):
        img = Image.open(fp).convert("RGB")
        orig_w, orig_h = img.size

        inputs = processor(images=img, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = model(**inputs).logits  # (1, num_classes, H/4, W/4)

        # Upsample to original resolution and take argmax
        upsampled = torch.nn.functional.interpolate(
            logits, size=(orig_h, orig_w), mode="bilinear", align_corners=False
        )
        label_map = upsampled.argmax(dim=1).squeeze(0).cpu().numpy()  # (H, W) int64

        sky_mask = (label_map == _ADE20K_SKY_LABEL).astype(np.uint8) * 255

        out_path = out_dir / (fp.stem + ".png")
        cv2.imwrite(str(out_path), sky_mask)

        if (i + 1) % 50 == 0:
            logger.info("  sky seg: %d / %d frames", i + 1, len(frame_paths))

    logger.info("Sky segmentation done: %d masks -> %s", len(frame_paths), out_dir)
    return out_dir


def merge_masks(
    dynamic_masks_dir: Path,
    sky_masks_dir: Path,
    out_dir: Path,
) -> Path:
    """Combine dynamic and sky masks with bitwise OR, write to *out_dir*.

    For frames without a sky mask (or vice-versa), the available mask is used
    as-is.  Output masks are binary PNGs (255 = exclude from COLMAP / 3DGS).
    Returns *out_dir*.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    all_stems = {p.stem for p in dynamic_masks_dir.glob("*.png")} | \
                {p.stem for p in sky_masks_dir.glob("*.png")}

    for stem in sorted(all_stems):
        dyn_path = dynamic_masks_dir / f"{stem}.png"
        sky_path = sky_masks_dir / f"{stem}.png"

        dyn = cv2.imread(str(dyn_path), cv2.IMREAD_GRAYSCALE) if dyn_path.exists() else None
        sky = cv2.imread(str(sky_path), cv2.IMREAD_GRAYSCALE) if sky_path.exists() else None

        if dyn is not None and sky is not None:
            # Ensure same shape (sky mask is already resized to original res)
            if dyn.shape != sky.shape:
                sky = cv2.resize(sky, (dyn.shape[1], dyn.shape[0]),
                                 interpolation=cv2.INTER_NEAREST)
            combined = cv2.bitwise_or(dyn, sky)
        elif dyn is not None:
            combined = dyn
        else:
            combined = sky

        cv2.imwrite(str(out_dir / f"{stem}.png"), combined)

    logger.info("Merged %d combined masks -> %s", len(all_stems), out_dir)
    return out_dir

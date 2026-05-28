"""Run LingBot-MAP streaming inference and return numpy outputs.

Wraps `GCTStream.inference_streaming` / `inference_windowed` plus the
post-processing copied from `lingbot-map/demo.py` so the rest of the stage
can reason in numpy.

Returns (after the call):
    extrinsics_c2w : (S, 3, 4) float32 — camera-to-world per processed frame
    intrinsics     : (S, 3, 3) float32 — at LingBot's processed (H_p, W_p)
    depth          : (S, H_p, W_p)    float32
    depth_conf     : (S, H_p, W_p)    float32
    world_points   : (S, H_p, W_p, 3) float32
    points_conf    : (S, H_p, W_p)    float32
    processed_hw   : (H_p, W_p) tuple
    images_proc    : (S, 3, H_p, W_p) float32 — preprocessed input tensor (CPU)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import torch

logger = logging.getLogger(__name__)


# Inference defaults — track demo.py for short driving sequences.
DEFAULT_IMAGE_SIZE = 518
DEFAULT_PATCH_SIZE = 14
DEFAULT_NUM_SCALE_FRAMES = 8
STREAMING_MAX_FRAMES = 320  # auto-keyframe threshold (matches demo.py)


def _lazy_import_lingbot():
    """Imports lingbot-map; raises with install hint on failure."""
    try:
        from lingbot_map.utils.load_fn import load_and_preprocess_images
        from lingbot_map.utils.pose_enc import pose_encoding_to_extri_intri
        from lingbot_map.utils.geometry import closed_form_inverse_se3_general
    except ImportError as e:
        raise ImportError(
            "lingbot-map is not installed. Install editable from the cloned repo, e.g. "
            "`pip install -e /workspace/lingbot-map` (torch is installed separately)."
        ) from e
    return load_and_preprocess_images, pose_encoding_to_extri_intri, closed_form_inverse_se3_general


def _flashinfer_available() -> bool:
    """True if the FlashInfer attention backend can be imported."""
    try:
        import flashinfer  # noqa: F401
        return True
    except Exception:
        return False


def _load_model(
    model_path: str,
    device: torch.device,
    *,
    mode: str,
    use_sdpa: bool,
    image_size: int,
    patch_size: int,
    num_scale_frames: int,
    kv_cache_sliding_window: int,
    camera_num_iterations: int,
    max_frame_num: int,
    enable_3d_rope: bool = True,
):
    """Build GCTStream and load a local ``.pt`` checkpoint.

    Mirrors ``demo.py:load_model`` — the released weights are a bare state dict
    (``lingbot-map-long.pt``), not a HuggingFace-format directory, so we
    construct the model explicitly and ``load_state_dict(strict=False)``.
    Windowed inference uses the windowed GCTStream subclass.
    """
    if mode == "windowed":
        from lingbot_map.models.gct_stream_window import GCTStream
    else:
        from lingbot_map.models.gct_stream import GCTStream

    logger.info("Building GCTStream (mode=%s, use_sdpa=%s)", mode, use_sdpa)
    model = GCTStream(
        img_size=image_size,
        patch_size=patch_size,
        enable_3d_rope=enable_3d_rope,
        max_frame_num=max_frame_num,
        kv_cache_sliding_window=kv_cache_sliding_window,
        kv_cache_scale_frames=num_scale_frames,
        kv_cache_cross_frame_special=True,
        kv_cache_include_scale_frames=True,
        use_sdpa=use_sdpa,
        camera_num_iterations=camera_num_iterations,
    )

    logger.info("Loading checkpoint: %s", model_path)
    ckpt = torch.load(model_path, map_location=device, weights_only=False)
    state_dict = ckpt.get("model", ckpt) if isinstance(ckpt, dict) else ckpt
    missing, unexpected = model.load_state_dict(state_dict, strict=False)
    if missing:
        logger.warning("  %d missing keys (e.g. %s)", len(missing), missing[:3])
    if unexpected:
        logger.warning("  %d unexpected keys (e.g. %s)", len(unexpected), unexpected[:3])

    return model.to(device).eval()


def run_inference(
    image_paths: list[Path],
    model_path: str,
    *,
    image_size: int = DEFAULT_IMAGE_SIZE,
    patch_size: int = DEFAULT_PATCH_SIZE,
    num_scale_frames: int = DEFAULT_NUM_SCALE_FRAMES,
    mode: str = "auto",       # "auto" | "streaming" | "windowed"
    window_size: int = 64,
    overlap_size: int = 16,
    keyframe_interval: int | None = None,
    kv_cache_sliding_window: int = 64,
    camera_num_iterations: int = 4,
    max_frame_num: int = 1024,
    use_sdpa: bool | None = None,   # None → auto (SDPA when FlashInfer absent)
) -> dict:
    """Run LingBot-MAP on a list of image paths.

    Returns a dict of numpy arrays (see module docstring).
    """
    (load_and_preprocess_images,
     pose_encoding_to_extri_intri,
     closed_form_inverse_se3_general) = _lazy_import_lingbot()

    # Allow expandable allocator on long sequences (matches demo.py).
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    str_paths = [str(p) for p in image_paths]

    # 1. Preprocess images (crop mode → width=518, height a multiple of patch_size).
    images = load_and_preprocess_images(
        str_paths, mode="crop",
        image_size=image_size, patch_size=patch_size,
    )
    images = images.to(device)
    num_frames, _, H_p, W_p = images.shape
    logger.info("LingBot input: %d frames @ %d×%d", num_frames, H_p, W_p)

    # 2. Auto-pick mode & keyframe interval.
    if mode == "auto":
        mode = "windowed" if num_frames > 500 else "streaming"
    if keyframe_interval is None:
        if mode == "streaming" and num_frames > STREAMING_MAX_FRAMES:
            keyframe_interval = (num_frames + STREAMING_MAX_FRAMES - 1) // STREAMING_MAX_FRAMES
        else:
            keyframe_interval = 1
    logger.info("Inference mode=%s, keyframe_interval=%d", mode, keyframe_interval)

    # 3. Load model. Default to SDPA when FlashInfer isn't installed (e.g. the
    # CUDA 11.8 deployment on RTX A5000 has no FlashInfer build).
    if use_sdpa is None:
        use_sdpa = not _flashinfer_available()
        logger.info("Attention backend: %s (auto)", "SDPA" if use_sdpa else "FlashInfer")
    model = _load_model(
        model_path, device,
        mode=mode, use_sdpa=use_sdpa,
        image_size=image_size, patch_size=patch_size,
        num_scale_frames=num_scale_frames,
        kv_cache_sliding_window=kv_cache_sliding_window,
        camera_num_iterations=camera_num_iterations,
        max_frame_num=max_frame_num,
    )

    # Cast trunk to bf16 on Ampere+ (matches demo.py).
    dtype = torch.float32
    if torch.cuda.is_available():
        dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
        if getattr(model, "aggregator", None) is not None and dtype != torch.float32:
            model.aggregator = model.aggregator.to(dtype=dtype)

    # 4. Run inference.
    output_device = torch.device("cpu")  # offload per-frame outputs to spare VRAM
    with torch.no_grad(), torch.amp.autocast("cuda", dtype=dtype):
        if mode == "streaming":
            predictions = model.inference_streaming(
                images,
                num_scale_frames=min(num_scale_frames, num_frames),
                keyframe_interval=keyframe_interval,
                output_device=output_device,
            )
        else:
            predictions = model.inference_windowed(
                images,
                window_size=window_size,
                overlap_size=overlap_size,
                num_scale_frames=min(num_scale_frames, num_frames),
                keyframe_interval=keyframe_interval,
                output_device=output_device,
            )

    # 5. Convert pose_enc → extrinsic (c2w 3x4) + intrinsic (3x3).
    pose_enc = predictions["pose_enc"]
    extrinsic_w2c, intrinsic = pose_encoding_to_extri_intri(pose_enc, (H_p, W_p))

    # Build 4x4 from 3x4 then invert w2c → c2w (same as demo.postprocess).
    ext_4x4 = torch.zeros((*extrinsic_w2c.shape[:-2], 4, 4),
                          device=extrinsic_w2c.device, dtype=extrinsic_w2c.dtype)
    ext_4x4[..., :3, :4] = extrinsic_w2c
    ext_4x4[..., 3, 3] = 1.0
    ext_4x4_c2w = closed_form_inverse_se3_general(ext_4x4)
    extrinsic_c2w = ext_4x4_c2w[..., :3, :4]

    # Drop batch dim (B=1) and pull to numpy.
    def _np(t: torch.Tensor) -> np.ndarray:
        return t.detach().to("cpu").float().numpy()

    def _strip_batch(arr: np.ndarray) -> np.ndarray:
        return arr[0] if arr.ndim >= 1 and arr.shape[0] == 1 else arr

    result = {
        "extrinsic_c2w": _strip_batch(_np(extrinsic_c2w)),       # (S, 3, 4)
        "intrinsic": _strip_batch(_np(intrinsic)),               # (S, 3, 3)
        "depth": _strip_batch(_np(predictions["depth"]).squeeze(-1)) if "depth" in predictions else None,
        "depth_conf": _strip_batch(_np(predictions["depth_conf"])) if "depth_conf" in predictions else None,
        "world_points": _strip_batch(_np(predictions["world_points"])) if "world_points" in predictions else None,
        "world_points_conf": _strip_batch(_np(predictions["world_points_conf"])) if "world_points_conf" in predictions else None,
        "processed_hw": (H_p, W_p),
        "images_proc": _strip_batch(_np(predictions["images"])) if "images" in predictions else _strip_batch(_np(images)),
    }

    # Free model + GPU cache.
    del model, predictions
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return result

import argparse
import copy
import importlib
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STEPS = [
    "02_ingest",
    "03_seg",
    "04_colmap",
    "05_depth",
    "06_scale",
    # 07 (background dense PC) and 09 (trajectory) both depend only on
    # Stage 06 output and run in parallel — see PARALLEL_GROUPS below.
    "07_pointcloud",
    "09_trajectory",
    "08_filtering",
    "10_3dgs",
    "11_format",
    "12_viewer",
]

# LingBot-MAP collapses Stage 04+05+06 into one feed-forward inference pass.
LINGBOT_STEPS = [
    "02_ingest",
    "03_seg",
    "04g_lingbot",
    "07_pointcloud",
    "09_trajectory",
    "08_filtering",
    "10_3dgs",
    "11_format",
    "12_viewer",
]

# dot-path relative to src/ for importlib
STAGE_MODULES = {
    "02_ingest": "02_ingest.ingest",
    "03_seg": "03_seg.seg",
    "04_colmap": "04_colmap.colmap_step",
    "04g_lingbot": "04g_lingbot.lingbot",
    "05_depth": "05_depth.depth",
    "06_scale": "06_scale.scale",
    "07_pointcloud": "07_pointcloud.pointcloud",
    "08_filtering": "08_filtering.filtering",
    "09_trajectory": "09_trajectory.trajectory",
    "10_3dgs": "10_3dgs.gs",
    "11_format": "11_format.format_step",
    "12_viewer": "12_viewer.viewer",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="3DGS pipeline runner (skeleton).")
    parser.add_argument("--input", required=True, help="Input path (video or TFRecord)")
    parser.add_argument(
        "--input_type",
        choices=["auto", "video", "waymo"],
        default="auto",
        help="Input type (default: auto)",
    )
    parser.add_argument(
        "--out_root",
        default=None,
        help="Output root directory (default: ai-pipeline/outputs/run_<timestamp>)",
    )
    parser.add_argument(
        "--steps",
        default=None,
        help="Comma-separated list of steps to run. "
             "Default: DEFAULT_STEPS (or LINGBOT_STEPS if --use-lingbot).",
    )
    parser.add_argument(
        "--use-lingbot",
        action="store_true",
        help="Swap Stage 04/05/06 (COLMAP + Depth Anything + scale align) for "
             "04g_lingbot (LingBot-MAP feed-forward inference). Requires "
             "lingbot-map installed and LINGBOT_MODEL_PATH set.",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Print plan only without executing.",
    )
    return parser.parse_args()


def _resolve_out_root(out_root):
    repo_root = Path(__file__).resolve().parents[2]
    if out_root:
        return Path(out_root).expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return repo_root / "outputs" / f"run_{timestamp}"


def _detect_input_type(input_path: Path) -> str:
    if input_path.suffix.lower() == ".tfrecord":
        return "waymo"
    return "video"


def _setup_logging(out_root: Path) -> None:
    """Configure root logger with console and file handlers."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root_logger.addHandler(console)

    log_dir = out_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "pipeline.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)


# Known artifact paths relative to out_root.  Each key maps to a list of
# candidate paths; _restore_artifacts() probes them in order so the same
# artifact key (e.g. "poses") can resolve to either the COLMAP output
# (04_colmap/poses.npy) or the LingBot output (04g_lingbot/poses.npy)
# depending on which stage produced it.
_ARTIFACT_PATHS = {
    "images_colmap":       ["02_ingest/images_colmap"],
    "ingest_vis":          ["02_ingest/sample_grid.png"],
    "segmentation_masks":  ["03_seg/masks"],
    "bbox_sequence":       ["03_seg/bbox_sequence.json"],
    "seg_overlay_sample":  ["03_seg/seg_overlay_sample.png"],
    "poses":               ["04g_lingbot/poses.npy", "04_colmap/poses.npy"],
    "intrinsics":          ["04g_lingbot/intrinsics.json", "04_colmap/intrinsics.json"],
    "sparse_ply":          ["04g_lingbot/sparse.ply", "04_colmap/sparse.ply"],
    "registered_frames":   ["04g_lingbot/registered_frames.json", "04_colmap/registered_frames.json"],
    "images_3dgs":         ["04g_lingbot/images_3dgs", "04_colmap/images_3dgs"],
    "colmap_model_dir":    ["04g_lingbot/sparse/0", "04_colmap/sparse/0"],
    "sparse_topdown":      ["04_colmap/sparse_topdown.png"],
    "depth_maps":          ["04g_lingbot/depth_maps", "05_depth/depth_maps"],
    "depth_vis":           ["05_depth/depth_vis"],
    "scaled_depth_maps":   ["04g_lingbot/scaled_depth_maps", "06_scale/scaled_depth_maps"],
    "scaled_depth_vis":    ["04g_lingbot/scaled_depth_vis", "06_scale/scaled_depth_vis"],
    "dense_pointcloud":    ["07_pointcloud/dense.ply"],
    "dense_topdown":       ["07_pointcloud/dense_topdown.png"],
    "filtered_pointcloud": ["08_filtering/filtered.ply"],
    "filtered_topdown":    ["08_filtering/filtered_topdown.png"],
    "trajectories":        ["09_trajectory/trajectories.json"],
    "trajectories_vis":    ["09_trajectory/trajectories_topdown.png"],
    "output_ply":          ["10_3dgs/model/point_cloud/iteration_30000/point_cloud.ply"],
    "gs_model_dir":        ["10_3dgs/model"],
    "output_topdown":      ["10_3dgs/output_topdown.png"],
    "output_splat":        ["11_format/output.splat"],
}


def _restore_artifacts(out_root: Path, context: dict) -> None:
    """Scan *out_root* for outputs from previous stages and populate context.

    Each artifact maps to a list of candidate paths; the first that exists wins.
    This lets the same key resolve to either the COLMAP or LingBot output.
    """
    restored = []
    for key, rel_paths in _ARTIFACT_PATHS.items():
        for rel in rel_paths:
            full = out_root / rel
            if full.exists():
                context["artifacts"][key] = str(full)
                restored.append(key)
                break
    if restored:
        logger.info("Restored %d artifact(s) from %s: %s", len(restored), out_root, restored)


def _run_parallel(step_names: list[str], context: dict) -> dict:
    """Execute multiple stages concurrently and merge their artifacts."""

    def _run_one(step_name: str):
        module_path = STAGE_MODULES[step_name]
        module = importlib.import_module(module_path)
        if not hasattr(module, "run"):
            raise NotImplementedError(f"{module_path}.run is not implemented.")
        logger.info("--- Running %s (%s) [parallel] ---", step_name, module_path)
        ctx = copy.deepcopy(context)
        ctx = module.run(ctx)
        return step_name, ctx["artifacts"]

    with ThreadPoolExecutor(max_workers=len(step_names)) as pool:
        futures = {pool.submit(_run_one, name): name for name in step_names}
        for future in as_completed(futures):
            step_name, artifacts = future.result()
            context["artifacts"].update(artifacts)
            logger.info("--- %s finished [parallel] ---", step_name)

    return context


def main() -> None:
    args = _parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    input_type = args.input_type
    if input_type == "auto":
        input_type = _detect_input_type(input_path)

    out_root = _resolve_out_root(args.out_root)
    if args.steps is not None:
        steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    else:
        steps = list(LINGBOT_STEPS if args.use_lingbot else DEFAULT_STEPS)

    os.makedirs(out_root, exist_ok=True)
    _setup_logging(out_root)

    logger.info("=== Pipeline Plan ===")
    logger.info("Input: %s", input_path)
    logger.info("Input type: %s", input_type)
    logger.info("Output root: %s", out_root)
    logger.info("Steps: %s", steps)

    if args.dry_run:
        logger.info("Dry run only. No execution.")
        return

    context = {
        "input_path": str(input_path),
        "input_type": input_type,
        "out_root": str(out_root),
        "artifacts": {},
    }

    # Restore artifacts from previous run (enables resuming from mid-pipeline)
    _restore_artifacts(out_root, context)

    # Add src/ to sys.path once for all stage imports
    src_root = str(Path(__file__).resolve().parents[2] / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    # Steps that can run in parallel (they share no input/output dependencies).
    # Each set is executed concurrently when ALL members appear consecutively
    # in the step list.  Their artifact dicts are merged after completion.
    PARALLEL_GROUPS = [
        {"04_colmap", "05_depth"},
        # Track A (background) Stage 07 vs Track B (trajectory) Stage 09.
        # Both consume only Stage 06 outputs; safe to run concurrently.
        {"07_pointcloud", "09_trajectory"},
    ]

    idx = 0
    while idx < len(steps):
        step = steps[idx]
        if step not in STAGE_MODULES:
            raise SystemExit(f"Unknown step: {step}")

        # Check if this step starts a parallel group.
        # Group members must appear contiguously starting at idx — otherwise
        # advancing idx by len(group) would skip / re-execute steps.
        parallel = None
        for group in PARALLEL_GROUPS:
            if step in group:
                chunk = steps[idx : idx + len(group)]
                if len(chunk) == len(group) and set(chunk) == group:
                    parallel = chunk
                    break

        if parallel and len(parallel) > 1:
            logger.info("--- Running parallel: %s ---", parallel)
            context = _run_parallel(parallel, context)
            idx += len(parallel)
        else:
            module_path = STAGE_MODULES[step]
            module = importlib.import_module(module_path)
            if not hasattr(module, "run"):
                raise NotImplementedError(f"{module_path}.run is not implemented.")

            logger.info("--- Running %s (%s) ---", step, module_path)
            context = module.run(context)
            idx += 1

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()

import argparse
import importlib
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STEPS = [
    "02_ingest",
    "03_seg",
    "04_colmap",
    "05_depth",
    "06_scale",
    "07_pointcloud",
    "08_filtering",
    "09_trajectory",
    "10_3dgs",
    "11_format",
    "12_viewer",
]

# dot-path relative to src/ for importlib
STAGE_MODULES = {
    "02_ingest": "02_ingest.ingest",
    "03_seg": "03_seg.seg",
    "04_colmap": "04_colmap.colmap_step",
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
        default=",".join(DEFAULT_STEPS),
        help="Comma-separated list of steps to run.",
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


def main() -> None:
    args = _parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    input_type = args.input_type
    if input_type == "auto":
        input_type = _detect_input_type(input_path)

    out_root = _resolve_out_root(args.out_root)
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]

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

    # Add src/ to sys.path once for all stage imports
    src_root = str(Path(__file__).resolve().parents[2] / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    for step in steps:
        if step not in STAGE_MODULES:
            raise SystemExit(f"Unknown step: {step}")

        module_path = STAGE_MODULES[step]
        module = importlib.import_module(module_path)
        if not hasattr(module, "run"):
            raise NotImplementedError(f"{module_path}.run is not implemented.")

        logger.info("--- Running %s (%s) ---", step, module_path)
        context = module.run(context)

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import sys
from pathlib import Path


def _add_src_to_path():
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    sys.path.insert(0, str(src_path))


def _setup_gpu():
    """Disable cuDNN for Blackwell GPUs (compute >= 12.0) where cuDNN is not yet supported."""
    try:
        import torch
        if torch.cuda.is_available():
            cap = torch.cuda.get_device_capability()
            if cap[0] >= 12:
                torch.backends.cudnn.enabled = False
                print(f"cuDNN disabled (compute {cap[0]}.{cap[1]}), using native CUDA kernels")
    except ImportError:
        pass


def main():
    _add_src_to_path()
    _setup_gpu()
    from pipeline.run_pipeline import main as run_main

    run_main()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import sys
from pathlib import Path


def _add_src_to_path():
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    sys.path.insert(0, str(src_path))


def main():
    _add_src_to_path()
    from pipeline.run_pipeline import main as run_main

    run_main()


if __name__ == "__main__":
    main()

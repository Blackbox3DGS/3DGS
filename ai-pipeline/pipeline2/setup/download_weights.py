"""LingBot-Map 체크포인트 다운로드 (HuggingFace).

실행 (lingbot-map env 권장, huggingface_hub 필요):
    python setup/download_weights.py --variant long --out_dir <repo>/third_party/lingbot-map/weights
변형:
    long   → lingbot-map-long.pt  (긴 시퀀스/대규모 장면 권장)
    base   → lingbot-map.pt       (균형)
    stage1 → lingbot-map-stage1.pt
"""
import argparse
from pathlib import Path

REPO = "robbyant/lingbot-map"
FILES = {
    "long": "lingbot-map-long.pt",
    "base": "lingbot-map.pt",
    "stage1": "lingbot-map-stage1.pt",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=list(FILES), default="long")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--filename", default=None,
                    help="HF repo 내 실제 파일명이 다르면 직접 지정")
    args = ap.parse_args()

    from huggingface_hub import hf_hub_download

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    fname = args.filename or FILES[args.variant]
    print(f"다운로드: {REPO}/{fname} → {out_dir}")
    path = hf_hub_download(repo_id=REPO, filename=fname, local_dir=str(out_dir))
    print(f"완료: {path}")
    print(f"\nconfig.yaml 의 paths.lingbot_ckpt 에 다음 경로를 지정하세요:\n  {path}")


if __name__ == "__main__":
    main()

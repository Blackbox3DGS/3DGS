#!/usr/bin/env bash
# LingBot-Map 추론용 conda env 생성 (Stage 1 전용).
# torch 2.8 + cu128 은 기존 3dgs_pipeline(torch 2.4)과 충돌하므로 별도 env.
set -euo pipefail

ENV_NAME="${1:-lingbot-map}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../third_party/lingbot-map" && pwd)"
CONDA="$(command -v conda || echo "$HOME/anaconda3/bin/conda")"

echo "[1/4] conda env '$ENV_NAME' 생성 (python 3.10)"
"$CONDA" create -n "$ENV_NAME" python=3.10 -y

echo "[2/4] torch 2.8.0 + cu128 설치"
"$CONDA" run -n "$ENV_NAME" pip install torch==2.8.0 torchvision==0.23.0 \
    --index-url https://download.pytorch.org/whl/cu128

echo "[3/4] lingbot-map 패키지 설치 (-e, repo=$REPO_DIR)"
"$CONDA" run -n "$ENV_NAME" pip install -e "$REPO_DIR"
# 추론에 필요한 보조 패키지 (vis 익스트라는 생략 — 우리는 viser 미사용)
"$CONDA" run -n "$ENV_NAME" pip install pyyaml

echo "[4/4] 검증"
"$CONDA" run -n "$ENV_NAME" python - <<'PY'
import torch
print("torch", torch.__version__, "cuda_avail", torch.cuda.is_available())
import lingbot_map  # noqa
print("lingbot_map import OK")
PY
echo "완료: conda activate $ENV_NAME"

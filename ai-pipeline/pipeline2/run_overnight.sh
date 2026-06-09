#!/usr/bin/env bash
# 퇴근용 무인 실행: env 설치 완료를 기다린 뒤 풀 파이프라인(①②③④) 실행.
# tmux 안에서 실행하면 연결이 끊겨도 계속 돈다.
#
#   tmux new -s p2
#   bash /home/doyun/3DGS/ai-pipeline/pipeline2/run_overnight.sh
#   (Ctrl+b, d 로 빠져나오면 백그라운드 유지. 다시 보려면 tmux attach -t p2)

set -uo pipefail
CONDA="$HOME/anaconda3/bin/conda"
REPO="/home/doyun/3DGS"
VIDEO="/home/doyun/3DGS/ai-pipeline/data/AI 공학관 주차장 (1).MOV"
OUT="/home/doyun/3DGS/ai-pipeline/outputs/p2_full"
RUNLOG="/home/doyun/3DGS/ai-pipeline/outputs/p2_full_run.log"

mkdir -p "$OUT"
echo "=== $(date) :: env 설치 완료 대기 ===" | tee -a "$RUNLOG"
# torch_install.log 또는 lingbot_env_build.log 에 DONE_ENV_BUILD 가 뜨면 시작
while ! grep -q DONE_ENV_BUILD /tmp/torch_install.log 2>/dev/null \
   && ! grep -q DONE_ENV_BUILD /tmp/lingbot_env_build.log 2>/dev/null; do
  sleep 20
done
echo "=== $(date) :: env 준비 완료. torch 검증 ===" | tee -a "$RUNLOG"
"$CONDA" run -n lingbot-map python -c "import torch,lingbot_map; print('torch',torch.__version__,'cuda',torch.cuda.is_available())" 2>&1 | tee -a "$RUNLOG" || {
  echo "!! lingbot env 검증 실패 — 중단" | tee -a "$RUNLOG"; exit 1; }

echo "=== $(date) :: 풀 파이프라인 시작 (①②③④) ===" | tee -a "$RUNLOG"
cd "$REPO"
CUDA_VISIBLE_DEVICES=1 "$CONDA" run --no-capture-output -n 3dgs_pipeline \
  python ai-pipeline/pipeline2/run.py \
    --video "$VIDEO" \
    --stages 1,2,3,4 \
    --out_root "$OUT" 2>&1 | tee -a "$RUNLOG"

code=${PIPESTATUS[0]}
echo "=== $(date) :: 파이프라인 종료 (exit=$code) ===" | tee -a "$RUNLOG"
if [ "$code" = 0 ]; then
  echo "✅ 완료. 결과: $OUT" | tee -a "$RUNLOG"
  echo "   웹뷰어: cd $OUT/04_viewer/viewer && python -m http.server 8000" | tee -a "$RUNLOG"
else
  echo "❌ 실패. 로그 확인: $RUNLOG 및 $OUT/logs/pipeline2.log" | tee -a "$RUNLOG"
fi

# AI Pipeline

## 개요
`ai-pipeline`은 졸업작품의 핵심인 **단안 사고 장면 3DGS 파이프라인**을 구현하는 영역입니다. 단일 영상 입력으로부터 카메라 포즈 추정, depth 복원, 3DGS 학습, 궤적 추출까지 한 번에 수행하는 것을 목표로 합니다.

## 입력/출력
- 입력: 블랙박스/스마트폰 영상 (.mp4/.avi)
- 출력: `output.splat` 및 차량 3D 궤적(.json)

## 단계 요약
1. 프레임 추출 (COLMAP용 / 3DGS용 분리)
1. YOLOv8-seg + ByteTrack 마스킹
1. COLMAP SfM (마스크 적용)
1. Depth Anything V2
1. Scale Alignment (COLMAP 스케일 + 카메라 높이 prior)
1. Dense Point Cloud 생성
1. Open3D Outlier Filtering
1. 3D 궤적 추출 (마스크 영역 depth median)
1. 3D Gaussian Splatting 학습 (마스크 loss 제외)
1. .splat 변환

## 최종 파이프라인 메모리
상세 파이프라인 정의는 `/Users/kyu216/projects/3DGS/ai-pipeline/PIPELINE_MEMORY.md`에 정리되어 있습니다.

## 폴더 구조
```text
/Users/kyu216/projects/3DGS/ai-pipeline
├── src        # 파이프라인 코어 모듈
│   ├── 02_ingest
│   │   └── ingest
│   ├── 03_seg
│   ├── 04_colmap
│   ├── 05_depth
│   ├── 06_scale
│   ├── 07_pointcloud
│   ├── 08_filtering
│   ├── 09_trajectory
│   ├── 10_3dgs
│   ├── 11_format
│   ├── 12_viewer
│   └── pipeline
├── scripts    # 실행 스크립트
├── configs    # 설정 파일
├── data       # 샘플/중간 데이터
├── outputs    # 결과물 저장
└── README.md
```

## 프레임 추출 실행 예시
Waymo TFRecord (전방 카메라, 10fps 기본)
`python3 /Users/kyu216/projects/3DGS/ai-pipeline/scripts/extract_waymo_front_frames.py --tfrecord /path/to/sample.tfrecord`

일반 영상 (COLMAP용 10fps)
`python3 /Users/kyu216/projects/3DGS/ai-pipeline/scripts/extract_video_frames.py --video /path/to/video.mp4 --fps 10`

## 시스템 의존성
`ffmpeg` (영상 프레임 추출)
`colmap` (카메라 포즈 추정)

## Docker (GPU 서버 실행)

```bash
# 빌드 (최초 1회, COLMAP CUDA 빌드 포함 ~20-30분)
docker compose build

# 파이프라인 실행
docker compose run pipeline --input /workspace/ai-pipeline/data/sample.tfrecord

# 특정 스테이지만 실행
docker compose run pipeline --input /workspace/ai-pipeline/data/sample.tfrecord --steps 02_ingest 03_seg 04_colmap

# GPU 확인
docker compose run --entrypoint python3 pipeline -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

## 현재 상태
- **Stage 02 (Ingest):** 구현 완료 — video/Waymo 프레임 추출
- **Stage 03 (Seg & Tracking):** 구현 완료 — YOLOv8-seg + ByteTrack + ego-motion 보정 + state back-propagation
- **Stage 04 (COLMAP):** 구현 완료 — COLMAP SfM (feature extraction → matching → mapping), GPU 자동 감지, 등록 프레임 서브샘플링
- Stage 05~12: 구현 예정

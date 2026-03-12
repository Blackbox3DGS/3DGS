# 단안 사고 장면 3DGS 파이프라인

## 개요
이 리포지토리는 **단안 영상(블랙박스/스마트폰)** 만으로 **교통사고 장면을 3D Gaussian Splatting(3DGS)** 으로 재구성하는 end-to-end 파이프라인을 목표로 합니다. 정적 실내가 아닌 **실외 동적 사고 장면**에 초점을 두며, 단순 품질 지표 향상보다 **사고 분석을 위한 다각도 재현, 궤적 오버레이, 사고 지점 마킹**까지 포함한 실용 목적을 지향합니다.

## 목표
"LiDAR 없는 단안 영상에서 교통사고 장면을 3DGS로 재구성하는 end-to-end 파이프라인"

## 차별점 및 기여
- **입력 단순화**: Street Gaussians 같은 기존 방법이 LiDAR + 멀티캠을 요구하는 것과 달리, 단안 영상만으로 동작.
- **사고 도메인 특화**: 다수의 동적 객체가 있는 교통사고 장면에 맞춘 파이프라인 설계.
- **동적 객체 마스킹 기반 SfM**: YOLOv8-seg + ByteTrack으로 마스크 생성 후 COLMAP에 `--ImageReader.mask_path` 적용.
- **Scale Alignment(물리적 prior 주입)**: COLMAP 스케일 정렬 + 카메라 높이 가정으로 절대 단위(m) 확보.
- **3D 궤적 추출**: 마스크 영역 depth의 중앙값(Median) 사용으로 궤적 안정화.
- **End-to-End 시스템**: 3DGS + 궤적 + 웹 뷰어 기반 사고 재현.

## 파이프라인 (Ours)
1. 입력 영상 (블랙박스/스마트폰, .mp4/.avi)
1. 프레임 추출
1. 객체 segmentation + tracking (YOLOv8-seg + ByteTrack)
1. COLMAP SfM (마스크 적용) → 카메라 포즈/희소 포인트클라우드
1. Monocular depth (Depth Anything V2)
1. Scale Alignment (COLMAP + 카메라 높이 prior)
1. Dense Point Cloud 생성 (역투영)
1. Outlier Filtering (Open3D SOR)
1. 3D 궤적 추출 (마스크 영역 depth median)
1. 3D Gaussian Splatting 학습 (마스크 loss 제외)
1. Splat 변환 (.ply → .splat)
1. Web Viewer (궤적/사고 지점 오버레이)

## Baseline (GT)
- 입력: Waymo 전방 카메라 + LiDAR
- Process: Street Gaussians
- Output: `output.splat` (고품질 기준선)

## 평가 계획
1. **nuScenes (Camera + LiDAR)**
1. Street Gaussians(LiDAR) vs Ours(LiDAR 무시) → PSNR/SSIM 비교
1. **블랙박스 영상 (LiDAR 없음)**
1. Street Gaussians는 실행 불가, Ours는 실행 가능 → 정성 평가
1. **Vanilla 3DGS 대비**
1. 단안 3DGS 대비 개선, LiDAR 기반 품질에 근접함을 제시

## 데이터
- Waymo (Baseline/Ours)
- YouTube 사고 영상 (Ours)

## 하드웨어
- 메인: NVIDIA GeForce RTX 5060 Ti (VRAM 16GB)
- 테스트: NVIDIA RTX 3060 (VRAM 6GB), Intel i7-12700H, RAM 16GB

## 리포지토리 구조
```text
/Users/kyu216/projects/3DGS
├── ai-pipeline   # 졸업작품 핵심 파이프라인
├── backend       # API/DB/작업관리
├── frontend      # 웹 뷰어 및 서비스 UI
├── inference_splatter.py
├── splatter-image
└── README.md
```

## 라이선스 메모
- YOLOv8-seg: AGPL-3.0
- ByteTrack: MIT
- COLMAP: BSD
- Depth Anything V2: Apache-2.0 (Small), CC-BY-NC-4.0 (Large)
- Open3D: MIT
- gaussian-splatting: Inria (non-commercial)
- splat-converter: MIT
- gsplat.js + React: MIT

## 상태
이 리포지토리는 이전 프로토타입에서 **사고 장면 단안 파이프라인**으로 전환 중입니다.

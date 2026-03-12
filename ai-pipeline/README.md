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

## 폴더 구조
```text
/Users/kyu216/projects/3DGS/ai-pipeline
├── src        # 파이프라인 코드
├── scripts    # 실행 스크립트
├── configs    # 설정 파일
├── data       # 샘플/중간 데이터
├── outputs    # 결과물 저장
└── README.md
```

## 메모
- 구현은 순차적으로 진행 예정이며, 각 단계별 스크립트가 추가됩니다.
- 라이선스 조건(AGPL, CC-BY-NC 등)을 고려하여 사용 범위를 관리합니다.

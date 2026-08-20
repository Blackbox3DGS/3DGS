# Pipeline Evaluation Report

**입력 데이터:** `sample3.tfrecord` (Waymo)  
**실행 출력:** `run_20260402_042652`  
**평가 일자:** 2026-04-09 (Stage 06 수정 반영)

---

## Stage 02 — Ingest (Frame Extraction)

**상태:** ✅ 정상

### 실행 결과
- Waymo TFRecord에서 프론트 카메라 프레임 추출
- 출력: `02_ingest/images_colmap/` (JPG)
- Waymo 캘리브레이션에서 intrinsics 자동 추출 (fx, fy, cx, cy)

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| every_n | 1 | 모든 프레임 추출 |
| 출력 포맷 | JPG | frame_XXXXXX_MICROSECONDS.jpg |

### 이슈 및 권장사항
| # | 심각도 | 이슈 | 권장 수정 |
|---|--------|------|-----------|
| 1 | Low | 비디오 입력 시 fps=10 하드코딩 | 향후 config로 분리 고려 |
| 2 | Low | 추출된 프레임 수 검증 없음 | 최소 프레임 수 체크 추가 고려 |

---

## Stage 03 — Segmentation & Tracking

**상태:** ✅ 정상

### 실행 결과
- YOLOv8m-seg + ByteTrack으로 차량/보행자 탐지 및 추적
- Farneback optical flow 기반 ego-motion 보상
- State back-propagation으로 동적/정적 분류
- 출력: `03_seg/masks/` (binary PNG), `bbox_sequence.json`

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| YOLOv8 모델 | yolov8m-seg.pt | Medium 모델 |
| conf_thresh | 0.3 | 탐지 신뢰도 |
| iou_thresh | 0.5 | NMS |
| motion_thresh | 3.0 px | ego-compensated 이동량 |
| frame_gap_tol | 5 | 트랙 간 최대 갭 |
| 대상 클래스 | person, bicycle, car, motorcycle, bus, truck | 6종 |

### 이슈 및 권장사항
| # | 심각도 | 이슈 | 권장 수정 |
|---|--------|------|-----------|
| 1 | Medium | motion_thresh=3.0px가 모든 해상도/속도에 동일 적용 | 해상도 비례 threshold 또는 config 분리 |
| 2 | Low | 클래스별 motion threshold 미분화 | 대형차(bus/truck)와 보행자는 다른 threshold 고려 |
| 3 | Low | 배경 픽셀 < 100일 때 full-image fallback | 극도로 혼잡한 장면에서 정확도 저하 가능 |

---

## Stage 04 — COLMAP (Camera Pose Estimation)

**상태:** ✅ 정상 (주의사항 있음)

### 실행 결과
- 199개 프레임 등록 (registration rate 확인 필요)
- 4,230개 sparse 3D points 생성
- Waymo intrinsics 고정 모드로 실행 (PINHOLE/OPENCV)
- 출력: `04_colmap/` (poses.npy, intrinsics.json, sparse.ply, images_3dgs/)

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| SIFT features | 8192 | max per image |
| sequential overlap | 20 frames | matcher 범위 |
| loop detection | disabled | 0 |
| 3DGS subsampling | every_n=2 | 등록 프레임 중 절반 |
| GPU | 자동 감지 (CPU fallback) | |

### 이슈 및 권장사항
| # | 심각도 | 이슈 | 권장 수정 |
|---|--------|------|-----------|
| 1 | Medium | loop detection 비활성화 | 긴 시퀀스에서 drift 누적 가능, 필요시 활성화 |
| 2 | Medium | reprojection error 등 품질 메트릭 미출력 | 재구성 품질 로그 추가 |
| 3 | Low | every_n=2 하드코딩 | 시퀀스 길이에 따라 조절 가능하게 |
| 4 | Low | point_filter.py 모듈 존재하나 미사용 | 통합 또는 제거 결정 필요 |

---

## Stage 05 — Depth Estimation

**상태:** ⚠️ 주의

### 실행 결과
- Depth Anything V2-Small로 전 프레임 depth 추정
- Per-frame min-max normalization → [0, 1] 범위
- 출력: `05_depth/depth_maps/` (.npy), `depth_vis/` (.png)

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| 모델 | Depth-Anything-V2-Small-hf | HuggingFace |
| 정규화 | per-frame min-max | 프레임별 독립 |
| 출력 범위 | [0, 1] float32 | relative depth |
| 시각화 | INFERNO colormap | |

### 이슈 및 권장사항
| # | 심각도 | 이슈 | 권장 수정 |
|---|--------|------|-----------|
| 1 | Medium | Per-frame 정규화로 프레임 간 depth 일관성 없음 | Global normalization 또는 Stage 06에서 보정 (현재 Pass 1이 이를 처리) |
| 2 | Medium | 동적 객체(차량 등)에도 depth 추정 수행 | 마스크 적용하여 동적 영역 제외 또는 Stage 06에서 필터링 |
| 3 | Low | Small 모델 사용 (정확도 vs 속도 trade-off) | 정확도 필요시 Large 모델로 교체 (CC-BY-NC 라이선스 주의) |

---

## Stage 06 — Scale Alignment

**상태:** ✅ 정상 (수정 완료)

### 수정 이력
1. **Camera height prior**: 1.5m 하드코딩 → input_type별 딕셔너리 (`waymo: 2.05m`, `video: 1.5m`)
2. **Ground plane fitting**: depth-map backprojection → **COLMAP sparse points 직접 사용** (triangulation으로 정확한 3D 위치 보장)
3. **RANSAC threshold**: 고정값 0.15m → **scene-extent 기반 adaptive** (`0.01 × 90th-percentile diameter`)
4. **Ground candidate 선별**: `select_ground_sparse_points()` 추가 (이미지 하단 40%에 투영되는 sparse points)
5. **Camera height threshold**: `measured < 0.01` (미터 가정) → 상대적 threshold (`1e-4 × scene_scale`)

### 실행 결과 (수정 후)
```
Pass 1: scale=0.7306 shift=0.6660 (96817/124542 inliers, 77.7%)
         depth inversion 감지 → 자동 반전 후 재fit
Pass 2: ground candidates = 117 / 4230 sparse points (bottom 40%, min 1 frame)
         scene_extent=31.95, inlier_thresh=0.3195
         ground plane normal=[-0.055,-0.998,0.029] d=0.095 (115/117 inliers)
         measured_height=0.0625 COLMAP units → target=2.05m → k=32.80
최종:   median=41.17m  range=[39.99, 41.97]m (frame median)
```

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| RANSAC iters (Pass 1) | 1000 | linear regression |
| inlier_thresh (Pass 1) | 2.0 | depth pair residual |
| RANSAC iters (Pass 2) | 1000 | ground plane |
| inlier_thresh (Pass 2) | auto (0.01 × scene extent) | scene-extent 기반 |
| CAMERA_HEIGHT_PRIOR | waymo: 2.05m, video: 1.5m | input_type별 |
| ground candidate | sparse points, bottom 40% | depth-map backprojection 대신 |
| vis colormap | TURBO, 0-50m | |

### Depth 시각화 분석
- TURBO colormap 기준: 앞 차량(초록) ≈ 10-20m, 도로(주황) ≈ 20-35m, 원거리(빨강) ≈ 40-50m+
- Depth ordering 정상 (가까운 곳 → 먼 곳 gradient 자연스러움)
- 전력선/간판 등 세부 구조물도 depth에 반영됨

### 잔여 이슈
| # | 심각도 | 이슈 | 비고 |
|---|--------|------|------|
| 1 | Low | median=41m이 다소 높을 수 있음 | 장면 특성(교외 도로, 원거리 비중 높음)에 따라 정상 범위 |
| 2 | Low | Frame median 편차 ~2m | 39.99~41.97m으로 안정적, 양호 |

---

## Stage 07 — Dense Point Cloud

**상태:** ✅ 정상 (voxel downsampling 적용)

### 실행 결과
```
199 registered frames backprojected (step=2)
Raw points: 122,265,600 (122M)
Voxel downsampling: voxel_size=0.1m
After downsampling: 7,448,738 (7.4M, 6.1% of original)
Output: 07_pointcloud/dense.ply (192MB, XYZ+RGB)
```

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| pixel step | 2 | every other pixel |
| min_depth | 0.5 m | 카메라 근접 노이즈 제거 |
| max_depth | 150.0 m | 하늘/무한 제거 |
| voxel_size | 0.1 m (10cm) | 3D 공간 균일 다운샘플링 |
| 색상 | RGB (원본 이미지에서 추출) | colored PLY |

### 설계 결정
- **Voxel downsampling 적용 이유:** Raw 122M points (3.1GB)는 Stage 08 (Open3D outlier removal)과 Stage 10 (3DGS 학습)에서 메모리/시간 초과 유발. 일반적인 3DGS 초기화는 1-5M points 권장.
- **voxel_size=0.1m:** 10cm 해상도로 도로/건물 구조 보존하면서 3DGS 학습에 적합한 3-10M 포인트 목표
- **step=2 + voxel 조합:** step으로 1차 감소 후, voxel로 3D 공간 균일성 보장

### 이슈 및 권장사항
| # | 심각도 | 이슈 | 비고 |
|---|--------|------|------|
| 1 | Low | voxel_size 튜닝 필요 가능 | 0.1m 기본, 디테일 필요시 0.05m, 더 축소 필요시 0.15m |
| 2 | Low | 동적 객체(차량 등) 포함됨 | Stage 10에서 mask loss 제외로 처리 예정 |

---

## Stage 08 — Point Cloud Filtering

**상태:** ✅ 정상

### 실행 결과
```
입력: 7,448,738 points (dense.ply, 192MB)
Statistical Outlier Removal: nb_neighbors=20, std_ratio=2.0
제거: 139,914 outliers (1.9%)
출력: 7,308,824 points (filtered.ply)
소요: ~6초
```

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| nb_neighbors | 20 | 각 점의 이웃 수 |
| std_ratio | 2.0 | 표준편차 배수 |

### 평가
- 1.9% 제거는 양호 (일반적 1-5% 범위)
- Voxel downsampling 후 극단적 아웃라이어만 소량 제거됨
- 7.3M points로 3DGS 학습 초기화에 적합

---

## 종합 요약

| Stage | 상태 | 비고 |
|-------|------|------|
| 02 Ingest | ✅ 정상 | fps config 분리 고려 |
| 03 Seg | ✅ 정상 | motion_thresh 해상도 비례화 고려 |
| 04 COLMAP | ✅ 정상 | 품질 메트릭 출력, loop detection 고려 |
| 05 Depth | ⚠️ 주의 | per-frame normalization, global 고려 |
| 06 Scale | ✅ 수정완료 | sparse point ground plane + scene-extent threshold |
| 07 Pointcloud | ✅ 정상 | voxel downsampling 0.1m, 7.4M points |
| 08 Filtering | ✅ 정상 | 1.9% outlier 제거, 7.3M points |

### 다음 단계
- **Track A (배경 복원):** Stage 10 → 11 → 12
- **Track B (궤적 추출):** Stage 09 → 12

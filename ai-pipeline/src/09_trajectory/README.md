# 09_trajectory

## Purpose
Stage 03이 검출한 동적 객체(차량/보행자)에 대해 track_id별 3D 월드 좌표 시퀀스를 생성한다. 최종 뷰어에서 배경 splat 위에 차량 궤적을 오버레이하여 사고 재구성 시각화를 완성한다.

## Inputs
- `bbox_sequence` (Stage 03): track별 frame_idx → bbox + state(dynamic/static)
- `segmentation_masks` (Stage 03): 프레임별 union dynamic mask PNG
- `target_ids` (Stage 03/3.5): 대상 track 집합 (`"all_dynamic"` 기본)
- `images_colmap` (Stage 02): frame_idx → 파일명 매핑 기준
- `scaled_depth_maps` (Stage 06): 프레임별 절대 스케일 depth `.npy` (단위 m)
- `poses` + `intrinsics` + `registered_frames` (Stage 04): camera-to-world + 핀홀 파라미터

## Outputs
- `trajectories.json`: `{metadata, tracks: {<id>: {class_name, points: [{frame_idx, frame_name, xyz, velocity_mps, depth_m, interpolated}, ...]}}}`
- `context["artifacts"]["trajectories"]` 키로 다운스트림에 노출
- `interpolated=true` 포인트는 관측이 없어 KF predict-only로 보간된 프레임. `depth_m`은 `null`
- `velocity_mps`는 KF 속도 추정(m/frame)에 `params.assumed_fps`(=Stage 02 추출 fps, 기본 10)를 곱한 값

## Notes
- **ROI**: bbox 하단 40%(뒷범퍼) ∩ dynamic mask ∩ 다른 트랙 bbox 제외
- **기준 깊이**: ROI 픽셀 depth의 [P20, P30] 분위수 부분집합의 중앙값
- **역투영**: `(u, v, d) + c2w + intrinsics` → `colmap_world` 좌표
- **시간 필터**: per-track Kalman filter (AB3DMOT의 `KF`, 10-state constant-velocity). ByteTrack이 이미 track_id를 부여하므로 data association 없이 per-track 필터링만 수행. 관측은 (x, y, z)만 사용하고 theta/l/w/h 차원에는 고정 더미값을 넣어 residual=0으로 만든다
- **Occlusion gap predict**: 관측이 없는 프레임에서 KF `predict()`로 위치를 외삽(`interpolated=true`). 연속 미관측이 `params.max_predict_gap`(기본 5)를 초과하면 KF를 폐기하고, 다음 관측이 새 KF를 초기화 — 그 사이 프레임은 출력에서 빠진다
- **미등록 프레임**: COLMAP이 빠뜨린 프레임은 관측에서 skip되지만 KF predict 보간으로 채워질 수 있음. 카운트는 `metadata.skipped`
- 좌표계는 Stage 04 c2w와 동일(`colmap_world`)

## Dependencies
- `filterpy>=1.4.5` (requirements.txt)
- `ai-pipeline/third_party/AB3DMOT/` — `KF` 클래스만 사용. **라이선스: CMU Noncommercial Research Use Only** (비영리 연구 전용). 상업적 배포 시 라이선스 재검토 필요. `AB3DMOT_ROOT` 환경변수로 경로 override 가능 (기본: repo의 `ai-pipeline/third_party/AB3DMOT`)

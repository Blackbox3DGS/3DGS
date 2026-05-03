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
- `trajectories.json`: `{metadata, tracks: {<id>: {class_name, points: [{frame_idx, frame_name, xyz, depth_m}, ...]}}}`
- `context["artifacts"]["trajectories"]` 키로 다운스트림에 노출

## Notes
- **ROI**: bbox 하단 40%(뒷범퍼) ∩ dynamic mask ∩ 다른 트랙 bbox 제외
- **기준 깊이**: ROI 픽셀 depth의 [P20, P30] 분위수 부분집합의 중앙값
- **역투영**: `(u, v, d) + c2w + intrinsics` → `colmap_world` 좌표
- **시간 스무딩**: gap-aware 3-프레임 중앙 이동평균 (occlusion gap > 2 frame이면 끊고 run 단위 처리)
- **미등록 프레임**: COLMAP이 빠뜨린 프레임은 skip 후 `metadata.skipped`에 카운트
- 좌표계는 Stage 04 c2w와 동일(`colmap_world`)

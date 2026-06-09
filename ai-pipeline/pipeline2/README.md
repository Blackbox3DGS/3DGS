# pipeline2 — MOV → LingBot-Map → 3DGS → 웹 시각화

iPhone 단안 영상 한 개로 3D 장면(3D Gaussian Splatting)을 재구성하고,
차량(카메라) 경로를 웹에서 애니메이션으로 보여주는 end-to-end 파이프라인.

기존 `src/` 12단계(COLMAP 기반)를 **대체**하는 새 4단계 구조입니다.

```
MOV ─① LingBot-Map ─→ point_cloud.ply + camera_poses.json + images/
        (streaming 3D recon)
     ─② 전처리 ──────→ 노이즈 제거(SOR/Radius/Voxel) + RANSAC 지면 Y=0 정렬
     ─③ 3DGS ────────→ COLMAP 포맷 → gaussian-splatting 학습 → output.splat
     ─④ 웹 뷰어 ──────→ Three.js + gaussian-splats-3d, splat + 차량 경로 애니메이션
```

## 디렉토리
```
pipeline2/
  config.yaml              모든 튜너블 (한 곳에서 관리)
  run.py                   오케스트레이터 (스테이지 선택 실행 + 재개)
  common/                  logio(설정·로깅·ply/poses I/O), geometry(지면정렬)
  stages/
    stage1_infer.py        LingBot-Map 추론 → ply/poses/images   (env: lingbot-map)
    stage2_preprocess.py   노이즈 제거 + 지면 정렬               (env: 3dgs_pipeline)
    stage3_train.py        COLMAP 작성 + 3DGS 학습 + splat 변환  (env: 3dgs_pipeline)
    stage4_viewer.py       웹 뷰어 자산 조립                     (env: 무관)
  web/                     뷰어 템플릿 (index.html / main.js / style.css)
  setup/                   env 설치·weights 다운로드 스크립트
  tests/                   합성 데이터 검증 (stage2 / stage3 / 통합)
```

## 사전 준비 (1회)

### 1) LingBot-Map env + 패키지  ⚠️ 외부 코드 설치 (직접 실행 필요)
```bash
bash setup/setup_lingbot_env.sh lingbot-map
```
torch 2.8+cu128 은 기존 `3dgs_pipeline`(torch 2.4)과 충돌하므로 **별도 env** 입니다.

### 2) 모델 가중치 다운로드
```bash
conda run -n lingbot-map python setup/download_weights.py \
    --variant long --out_dir ../third_party/lingbot-map/weights
```
다운로드된 `.pt` 경로를 `config.yaml` 의 `paths.lingbot_ckpt` 에 기입.

### 3) 학습 env
`3dgs_pipeline` (torch 2.4 + open3d + plyfile + diff-gaussian-rasterization + simple-knn)
— 이미 구성되어 있음.

## 실행

전체:
```bash
conda run -n 3dgs_pipeline python run.py \
    --video "/path/AI 공학관 주차장.MOV" --stages 1,2,3,4
```
- Stage 1 만 내부적으로 `lingbot-map` env 로 교차 호출됩니다.
- 출력: `ai-pipeline/outputs/p2_run_<timestamp>/`

부분 재실행 (중간 결과 자동 재사용):
```bash
# Stage1 산출물이 있으면 전처리부터
conda run -n 3dgs_pipeline python run.py --out_root <기존_run> --stages 2,3,4
# 학습 빼고 COLMAP 데이터셋만
... --stages 3 --skip_train
```

웹 뷰어:
```bash
cd <out_root>/04_viewer/viewer && python -m http.server 8000
# 브라우저: http://localhost:8000
```

## 출력물
| 스테이지 | 경로 | 내용 |
|---|---|---|
| 1 | `01_mapping/point_cloud.ply` | 월드 포인트클라우드 (XYZ+RGB) |
| 1 | `01_mapping/camera_poses.json` | c2w 4x4 + intrinsics |
| 1 | `01_mapping/images/` | 포즈에 대응하는 전처리 프레임 |
| 2 | `02_preprocess/point_cloud_clean.ply` | 노이즈 제거 + 지면정렬 |
| 2 | `02_preprocess/camera_poses_aligned.json` | 동일 변환 적용된 포즈 |
| 2 | `02_preprocess/preview_topdown.png` | top-down 미리보기 |
| 3 | `03_3dgs/colmap/` | COLMAP 데이터셋 |
| 3 | `03_3dgs/model/` | 3DGS 학습 결과 |
| 3 | `03_3dgs/output.splat` | 웹 뷰어용 splat |
| 4 | `04_viewer/viewer/` | 정적 웹 뷰어 |

## 검증 (합성 데이터, 실제 영상/가중치 불필요)
```bash
conda run -n 3dgs_pipeline python tests/test_stage2_synthetic.py     # 지면정렬
conda run -n 3dgs_pipeline python tests/test_stage3_splat.py         # 쿼터니언 + splat
conda run -n 3dgs_pipeline python tests/test_pipeline_integration.py # 2→3→4 연결
```

## 주의 / 알려진 한계
- **conf 필터**는 LingBot conf 의 백분위 기반(`stage1_mapping.conf_percentile`).
  모델 conf 스케일이 0~1 이 아니므로 절대 임계 대신 백분위 사용.
- **5438 프레임** 영상은 매우 길어 Stage 1 은 `mode: windowed` 사용.
  포인트는 `points_frame_stride`/`points_pixel_stride`/`max_points` 로 메모리 제한.
- **sky 마스킹**(`stage1_mapping.mask_sky`)은 아직 Stage 1 추론에 미연결(향후 작업).
- **splat 방향**: 데이터가 지면정렬(Y-up)이라 기본 회전 없음.
  뒤집혀 보이면 `stage4_viewer.splat_rotation`(XYZ Euler, rad) 로 보정.
- 카메라 intrinsics 는 LingBot 의 crop(518) 해상도 기준 → 학습/뷰어 일관.

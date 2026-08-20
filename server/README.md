# ReScene 업로드/분석 서버 (FastAPI)

프론트엔드가 쓰는 기존 API 계약(`/api/auth/*`, `/api/v1/reconstruction/*`)을 그대로 구현한 경량 파이썬 서버입니다. 영상을 업로드하면 백그라운드 워커가 즉시 분석합니다 — **GPU 없이** 프레임 추출 → YOLO/ByteTrack 추적 → 프레임 증거 충돌 검출(당사자/목격자 판별)까지 자동, LingBot 체크포인트가 설정돼 있으면 3D 재구성까지 수행합니다.

## 실행

```bash
pip install -r server/requirements.txt

# 기본 (2D 분석: 추적 + 충돌 검출) — http://127.0.0.1:8090
PORT=8090 python3 server/app.py

# 3D 재구성 포함 (lingbot-map 설치 + 체크포인트 필요)
LINGBOT_MODEL_PATH=/path/to/lingbot-map-long.pt PORT=8090 python3 server/app.py
```

프론트 연결: `frontend/.env.local`에 `VITE_API_BASE_URL=http://127.0.0.1:8090` (커밋 금지 — .gitignore 처리됨).

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `PORT` | 8080 | 서버 포트 (Spring 백엔드와 충돌 시 8090 권장) |
| `RESCENE_DATA` | `<repo>/server_data` | 잡/사용자 데이터 루트 |
| `RESCENE_PIPELINE_ROOT` | repo 루트 | ai-pipeline 소스 위치 (다른 워크트리에 있으면 지정) |
| `LINGBOT_MODEL_PATH` | (없음) | 설정 시 3D 재구성 수행 (CPU도 가능, 느림) |
| `CAMERA_HEIGHT_PRIOR` | 1.4 | 블랙박스 장착 높이(m) — 미터 스케일 산출용 |

## 잡 처리 흐름

```
업로드(mp4) → PENDING
  → PRE_PROCESSING  프레임 추출 (ffmpeg, 10fps)
  → PROCESSING      YOLO/ByteTrack 추적 → 충돌 검출(03c) [→ LingBot 3D]
  → COMPLETED       statusDescription에 충돌 시점·역할 요약
     (FAILED 시 사유 표기, 상세는 server_data/jobs/<id>/worker.log)
```

결과 파일은 `/files/<jobId>/…`로 서빙됩니다: `frames/%06d.jpg`(0-based), `pipeline/03_seg/bbox_sequence.json`, `pipeline/03c_collision/collision.json`, (3D 시) `scene.splat` + `scene_vehicles.json`.

## 주의

- 인증은 로컬 파일 기반 개발용입니다(`server_data/users.json`, 평문 저장·JWT 아님). 실서비스 전 반드시 교체해야 하는 지점이며, 그래서 프론트 API 계약을 Spring 버전과 동일하게 유지했습니다.
- 업로드 영상·결과는 `server_data/`에 저장되며 git에서 제외됩니다.

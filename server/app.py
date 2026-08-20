"""ReScene 업로드/분석 서비스 — FastAPI.

기존 프론트엔드(React)의 API 계약(Spring 백엔드용으로 정의된 것)을 그대로
구현하는 경량 파이썬 서버. 업로드된 영상은 백그라운드 워커가 즉시 분석한다
(프레임 추출 → YOLO/ByteTrack 추적 → 프레임 증거 충돌 검출 → [선택] LingBot 3D).

실행:
    pip install fastapi uvicorn python-multipart
    python3 server/app.py                     # http://localhost:8080

    # 3D 재구성까지 하려면 (lingbot-map 설치 + 체크포인트 필요):
    LINGBOT_MODEL_PATH=/path/to/lingbot-map-long.pt python3 server/app.py

인증은 로컬 파일 기반의 개발용 구현이다(JWT 아님) — 서비스화 시 교체 지점.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("rescene.app")

app = FastAPI(title="ReScene local service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 결과 파일 서빙 (frames/, bbox_sequence.json, scene.splat, vehicles.json …)
app.mount("/files", StaticFiles(directory=jobs.JOBS_ROOT, follow_symlink=True), name="files")

USERS_PATH = jobs.DATA_ROOT / "users.json"
_USERS_LOCK = threading.Lock()


def _load_users() -> dict:
    if USERS_PATH.exists():
        with open(USERS_PATH) as f:
            return json.load(f)
    return {}


def _save_users(users: dict) -> None:
    with _USERS_LOCK, open(USERS_PATH, "w") as f:
        json.dump(users, f, ensure_ascii=False, indent=1)


def current_user(request: Request) -> str:
    """Bearer local:<userId> — 로컬 개발용 토큰."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer local:"):
        return auth.removeprefix("Bearer local:")
    if auth.startswith("Bearer demo-token"):
        return "demo"
    raise HTTPException(status_code=401, detail="로그인이 필요합니다")


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


# ── 인증 (로컬 개발용) ────────────────────────────────────────────────────────

@app.post("/api/auth/signup")
async def signup(body: dict):
    user_id = body.get("userId", "").strip()
    if not user_id or not body.get("password"):
        raise HTTPException(400, "userId/password가 필요합니다")
    users = _load_users()
    if user_id in users:
        raise HTTPException(409, "이미 존재하는 사용자입니다")
    users[user_id] = {
        "password": body["password"],
        "name": body.get("name") or user_id,
        "email": body.get("email") or f"{user_id}@local",
        "birth": body.get("birth"),
    }
    _save_users(users)
    return {"result": "ok"}


@app.post("/api/auth/login")
async def login(body: dict):
    user_id = body.get("userId", "")
    users = _load_users()
    u = users.get(user_id)
    if not u or u["password"] != body.get("password"):
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다")
    return {
        "accessToken": f"local:{user_id}",
        "refreshToken": f"local-refresh:{user_id}",
        "name": u["name"],
    }


@app.get("/api/auth/profile")
async def profile(user: str = Depends(current_user)):
    u = _load_users().get(user)
    if user == "demo":
        return {"userId": "demo", "name": "데모 사용자", "email": "demo@example.com"}
    if not u:
        raise HTTPException(401, "unknown user")
    return {"userId": user, "name": u["name"], "email": u["email"], "birth": u.get("birth")}


@app.post("/api/auth/reissue")
async def reissue(body: dict):
    rt = (body or {}).get("refreshToken", "")
    if rt.startswith("local-refresh:"):
        uid = rt.removeprefix("local-refresh:")
        return {"accessToken": f"local:{uid}", "refreshToken": rt}
    raise HTTPException(401, "invalid refresh token")


@app.post("/api/auth/logout")
async def logout():
    return {"result": "ok"}


# ── 재구성 잡 API (프론트 Dashboard 계약) ─────────────────────────────────────

@app.post("/api/v1/reconstruction/upload")
async def upload(request: Request, file: UploadFile = File(...),
                 user: str = Depends(current_user)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "빈 파일입니다")
    meta = jobs.create_job(file.filename or "video.mp4", data, user, _base_url(request))
    logger.info("upload by %s → job %s (%.1f MB)", user, meta["jobId"], len(data) / 1e6)
    return meta


@app.get("/api/v1/reconstruction")
async def list_reconstructions(keyword: str | None = None,
                               user: str = Depends(current_user)):
    return jobs.list_jobs(owner=user, keyword=keyword)


@app.get("/api/v1/reconstruction/{job_id}")
async def get_job(job_id: str, user: str = Depends(current_user)):
    meta = jobs.read_meta(job_id)
    if not meta:
        raise HTTPException(404, "job not found")
    return meta


@app.patch("/api/v1/reconstruction/{job_id}/title")
async def rename(job_id: str, newTitle: str, user: str = Depends(current_user)):
    if not jobs.read_meta(job_id):
        raise HTTPException(404, "job not found")
    return jobs.write_meta(job_id, customTitle=newTitle)


@app.delete("/api/v1/reconstruction/{job_id}")
async def remove(job_id: str, user: str = Depends(current_user)):
    if not jobs.delete_job(job_id):
        raise HTTPException(404, "job not found")
    return {"result": "deleted"}


@app.post("/api/v1/reconstruction/{job_id}/target")
async def set_target(job_id: str, body: dict, user: str = Depends(current_user)):
    if not jobs.read_meta(job_id):
        raise HTTPException(404, "job not found")
    return jobs.write_meta(job_id, targetIds=body.get("targetIds"))


@app.on_event("startup")
async def _recover():
    n = jobs.recover_stale_jobs()
    if n:
        logger.info("recovered %d stale job(s) after restart", n)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="127.0.0.1", port=port)

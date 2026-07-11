"""Job store + analysis worker for the ReScene upload service.

Each job is a directory under server_data/jobs/<job_id>/:

    input.mp4            uploaded video
    meta.json            AnalysisRecord-shaped status (what the frontend polls)
    pipeline/            ai-pipeline outputs (02_ingest / 03_seg / 03c_collision …)
    frames/              0-based %06d.jpg symlinks for the frontend frames panel
    scene.splat          (optional) LingBot 3D background — only if LINGBOT_MODEL_PATH
    scene_vehicles.json  (optional) trajectories + collision + metric scale

The worker runs the CPU stages (frames → YOLO/ByteTrack → frame-evidence
collision detection) via the pipeline orchestrator in a subprocess, then the
optional LingBot 3D export if a checkpoint is configured. Everything the
viewer needs for accident analysis (collision moment, ego role, tracking
panel) is produced WITHOUT a GPU; the 3D scene is additive.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("rescene.jobs")

REPO_ROOT = Path(__file__).resolve().parents[1]
# ai-pipeline 소스 위치 — 브랜치/워크트리 구성이 다르면 env로 지정
# (예: 파이프라인은 feature/collision-detection 워크트리에 있을 때).
PIPELINE_ROOT = Path(os.environ.get("RESCENE_PIPELINE_ROOT", REPO_ROOT)).resolve()
PIPELINE = PIPELINE_ROOT / "ai-pipeline" / "scripts" / "run_pipeline.py"
SCENE_EXPORT = PIPELINE_ROOT / "ai-pipeline" / "scripts" / "lingbot_scene_export.py"

DATA_ROOT = Path(os.environ.get("RESCENE_DATA", REPO_ROOT / "server_data")).resolve()
JOBS_ROOT = DATA_ROOT / "jobs"
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

_LOCK = threading.Lock()

STATUS_DESC = {
    "PENDING": "대기 중",
    "PRE_PROCESSING": "프레임 추출 중",
    "PROCESSING": "차량 추적·사고 분석 중",
    "COMPLETED": "분석 완료",
    "FAILED": "분석 실패",
}


def _meta_path(job_id: str) -> Path:
    return JOBS_ROOT / job_id / "meta.json"


def read_meta(job_id: str) -> dict | None:
    p = _meta_path(job_id)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def write_meta(job_id: str, **updates) -> dict:
    with _LOCK:
        meta = read_meta(job_id) or {}
        meta.update(updates)
        if "status" in updates and "statusDescription" not in updates:
            meta["statusDescription"] = STATUS_DESC.get(updates["status"], "")
        with open(_meta_path(job_id), "w") as f:
            json.dump(meta, f, ensure_ascii=False)
    return meta


def list_jobs(owner: str | None = None, keyword: str | None = None) -> list:
    out = []
    for d in sorted(JOBS_ROOT.iterdir(), reverse=True):
        meta = read_meta(d.name)
        if not meta:
            continue
        if owner and meta.get("owner") not in (owner, None):
            continue
        if keyword and keyword.lower() not in meta.get("customTitle", "").lower():
            continue
        out.append(meta)
    return out


def delete_job(job_id: str) -> bool:
    d = JOBS_ROOT / job_id
    if not d.exists():
        return False
    shutil.rmtree(d)
    return True


def create_job(upload_name: str, file_bytes: bytes, owner: str, base_url: str) -> dict:
    job_id = uuid.uuid4().hex[:12]
    d = JOBS_ROOT / job_id
    d.mkdir(parents=True)
    video = d / "input.mp4"
    video.write_bytes(file_bytes)

    meta = {
        "jobId": job_id,
        "owner": owner,
        "customTitle": Path(upload_name).stem or "새 분석",
        "status": "PENDING",
        "statusDescription": STATUS_DESC["PENDING"],
        "progress": 0,
        "currentStep": "대기",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "incidentDate": datetime.now().date().isoformat(),
    }
    with open(_meta_path(job_id), "w") as f:
        json.dump(meta, f, ensure_ascii=False)

    t = threading.Thread(target=_worker, args=(job_id, base_url), daemon=True)
    t.start()
    return meta


# ── 분석 워커 ─────────────────────────────────────────────────────────────────

def _run(cmd: list, log_file: Path) -> int:
    with open(log_file, "a") as lf:
        lf.write(f"\n$ {' '.join(str(c) for c in cmd)}\n")
        lf.flush()
        proc = subprocess.run([str(c) for c in cmd], stdout=lf, stderr=subprocess.STDOUT)
    return proc.returncode


def _link_frames_zero_based(job_dir: Path) -> int:
    """images_colmap/frame_000001.jpg(1-based) → frames/000000.jpg(0-based 심볼릭)."""
    src = job_dir / "pipeline" / "02_ingest" / "images_colmap"
    dst = job_dir / "frames"
    dst.mkdir(exist_ok=True)
    frames = sorted(src.glob("*.jpg"))
    for i, p in enumerate(frames):
        link = dst / f"{i:06d}.jpg"
        if not link.exists():
            link.symlink_to(os.path.relpath(p, dst))
    return len(frames)


def _worker(job_id: str, base_url: str) -> None:
    d = JOBS_ROOT / job_id
    log = d / "worker.log"
    files = f"{base_url}/files/{job_id}"
    py = sys.executable
    try:
        t0 = time.time()
        write_meta(job_id, status="PRE_PROCESSING", progress=10, currentStep="프레임 추출")

        # CPU 스테이지: 프레임 → YOLO/ByteTrack → 프레임 증거 충돌 검출
        rc = _run([py, PIPELINE, "--input", d / "input.mp4",
                   "--out_root", d / "pipeline",
                   "--steps", "02_ingest,03_seg,03c_collision"], log)
        if rc != 0:
            raise RuntimeError(f"pipeline exited {rc} (see worker.log)")

        write_meta(job_id, status="PROCESSING", progress=55, currentStep="사고 분석 정리")
        n_frames = _link_frames_zero_based(d)

        collision_path = d / "pipeline" / "03c_collision" / "collision.json"
        with open(collision_path) as f:
            collision = json.load(f)

        updates = {
            "framesPattern": f"{files}/frames/%06d.jpg",
            "bboxSequenceUrl": f"{files}/pipeline/03_seg/bbox_sequence.json",
            "collisionUrl": f"{files}/pipeline/03c_collision/collision.json",
            "nFrames": n_frames,
        }

        # 선택: LingBot 3D 재구성 (체크포인트가 설정된 경우 — CPU도 가능, 느릴 뿐)
        model_path = os.environ.get("LINGBOT_MODEL_PATH")
        if model_path:
            write_meta(job_id, progress=65, currentStep="3D 재구성 (LingBot)")
            rc = _run([py, SCENE_EXPORT,
                       "--model_path", model_path,
                       "--image_folder", d / "pipeline" / "02_ingest" / "images_colmap",
                       "--dynamic_mask_dir", d / "pipeline" / "03_seg" / "masks",
                       "--bbox_sequence", d / "pipeline" / "03_seg" / "bbox_sequence.json",
                       "--collision", collision_path,
                       "--camera_height_prior", os.environ.get("CAMERA_HEIGHT_PRIOR", "1.4"),
                       # CPU(fp32)에선 신뢰도가 ~1.0에 몰려 GPU 기본값(2.0)이 전부
                       # 걸러버린다 — 실측 기준 1.0이 적정 (docs/METRICS.md 4절).
                       "--conf_threshold", os.environ.get("LINGBOT_CONF_THRESHOLD", "1.0"),
                       "--out_splat", d / "scene.splat",
                       "--out_vehicles", d / "scene_vehicles.json"], log)
            if rc == 0 and (d / "scene.splat").exists():
                updates["resultUrl"] = f"{files}/scene.splat"
                updates["trajectoryUrl"] = f"{files}/scene_vehicles.json"
            else:
                logger.warning("job %s: LingBot export failed (rc=%s) — 2D 결과로 완료", job_id, rc)

        col = collision.get("collision")
        role = {"party": "당사자", "witness": "목격자"}.get(collision.get("ego_role"), None)
        desc = "분석 완료"
        if col:
            desc = f"분석 완료 — 충돌 t={col['time_s']}s ({role or '역할 미상'})"
        elif collision.get("ego_role") == "none":
            desc = "분석 완료 — 충돌 미검출"
        if "resultUrl" not in updates:
            desc += " · 3D 재구성 대기(GPU)"

        write_meta(job_id, status="COMPLETED", progress=100,
                   currentStep="완료", statusDescription=desc,
                   elapsedSec=round(time.time() - t0, 1), **updates)
        logger.info("job %s completed in %.1fs", job_id, time.time() - t0)
    except Exception as e:  # noqa: BLE001 — 워커 실패는 상태로 보고
        logger.exception("job %s failed", job_id)
        write_meta(job_id, status="FAILED", progress=100,
                   statusDescription=f"분석 실패: {e}", currentStep="실패")

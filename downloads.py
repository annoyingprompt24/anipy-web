from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app import queue

router = APIRouter()


class QueueRequest(BaseModel):
    anime_id: str
    anime_name: str
    episodes: list[float]
    lang: str = "sub"


@router.post("/queue")
def enqueue(req: QueueRequest):
    if req.lang not in ("sub", "dub"):
        raise HTTPException(status_code=400, detail="lang must be 'sub' or 'dub'")
    job_ids = []
    for ep in req.episodes:
        jid = queue.add_job(req.anime_id, req.anime_name, ep, req.lang)
        job_ids.append(jid)
    return {"queued": job_ids}


@router.get("/jobs")
def list_jobs():
    return queue.get_jobs()


@router.get("/jobs/{job_id}")
def get_job(job_id: int):
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

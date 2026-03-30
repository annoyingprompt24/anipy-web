import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app import queue

router = APIRouter()


@router.get("/progress/{job_id}")
async def stream_progress(job_id: int):
    q = queue.subscribe(job_id)

    async def event_gen():
        try:
            # Send current state immediately
            job = queue.get_job(job_id)
            if job:
                yield f"data: {json.dumps({'status': job['status'], 'progress': job['progress']})}\n\n"

            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps(data)}\n\n"
                    if data.get("status") in ("done", "error"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            queue.unsubscribe(job_id, q)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

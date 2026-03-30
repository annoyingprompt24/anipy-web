import asyncio
import os
import sqlite3
import threading
import time
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime

DB_PATH = "/data/queue.db"
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/downloads/anime")

# SSE subscribers: job_id -> list of queues
_subscribers: dict[str, list[asyncio.Queue]] = {}
_subscribers_lock = threading.Lock()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id TEXT NOT NULL,
            anime_name TEXT NOT NULL,
            episode_num REAL NOT NULL,
            lang TEXT NOT NULL CHECK(lang IN ('sub', 'dub')),
            status TEXT NOT NULL DEFAULT 'queued',
            progress INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    # Reset any in-progress jobs from a previous crashed run
    conn.execute("""
        UPDATE jobs SET status = 'queued', progress = 0
        WHERE status = 'downloading'
    """)
    conn.commit()
    conn.close()


def add_job(anime_id: str, anime_name: str, episode_num: float, lang: str) -> int:
    conn = get_db()
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        """INSERT INTO jobs (anime_id, anime_name, episode_num, lang, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'queued', ?, ?)""",
        (anime_id, anime_name, episode_num, lang, now, now)
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def get_jobs(limit: int = 50) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job(job_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _update_job(conn, job_id: int, **kwargs):
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", values)
    conn.commit()


def _push_event(job_id: int, data: dict):
    sid = str(job_id)
    with _subscribers_lock:
        queues = _subscribers.get(sid, [])
    for q in queues:
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass


def subscribe(job_id: int) -> asyncio.Queue:
    sid = str(job_id)
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    with _subscribers_lock:
        _subscribers.setdefault(sid, []).append(q)
    return q


def unsubscribe(job_id: int, q: asyncio.Queue):
    sid = str(job_id)
    with _subscribers_lock:
        lst = _subscribers.get(sid, [])
        if q in lst:
            lst.remove(q)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _worker():
    """Single-threaded download worker. Runs forever in a daemon thread."""
    from anipy_api.anime import Anime
    from anipy_api.provider import LanguageTypeEnum

    init_db()

    while True:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        conn.close()

        if not row:
            time.sleep(2)
            continue

        job = dict(row)
        job_id = job["id"]
        conn = get_db()
        _update_job(conn, job_id, status="downloading", progress=0)
        conn.close()

        _push_event(job_id, {"status": "downloading", "progress": 0})

        try:
            lang_enum = LanguageTypeEnum.SUB if job["lang"] == "sub" else LanguageTypeEnum.DUB

            # Resolve the anime object
            results = Anime.search(job["anime_id"])
            if not results:
                raise RuntimeError(f"Could not find anime by id: {job['anime_id']}")

            anime = results[0]
            episodes = anime.get_episodes(lang_enum)
            ep_num = job["episode_num"]

            target = next((e for e in episodes if e.number == ep_num), None)
            if not target:
                raise RuntimeError(f"Episode {ep_num} not found")

            stream = anime.get_video(target, lang_enum)

            out_dir = Path(DOWNLOAD_DIR) / _safe_name(job["anime_name"])
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"E{ep_num:05.1f}_{job['lang']}.mp4"

            def progress_cb(current: int, total: int):
                pct = int(current / total * 100) if total else 0
                c2 = get_db()
                _update_job(c2, job_id, progress=pct)
                c2.close()
                _push_event(job_id, {"status": "downloading", "progress": pct})

            stream.download(out_file, progress_callback=progress_cb)

            conn = get_db()
            _update_job(conn, job_id, status="done", progress=100)
            conn.close()
            _push_event(job_id, {"status": "done", "progress": 100})

        except Exception as exc:
            conn = get_db()
            _update_job(conn, job_id, status="error", error=str(exc))
            conn.close()
            _push_event(job_id, {"status": "error", "progress": 0, "error": str(exc)})


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in " ._-" else "_" for c in name).strip()


def start_worker():
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

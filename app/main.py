import os
import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse

from app.queue import init_db, start_worker
from app.routes import search, downloads, progress

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

security = HTTPBasic()

AUTH_USER = os.environ.get("ANIPY_USER", "admin")
AUTH_PASS = os.environ.get("ANIPY_PASS", "changeme")


def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username.encode(), AUTH_USER.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), AUTH_PASS.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="anipy-web", docs_url=None, redoc_url=None)


@app.on_event("startup")
def on_startup():
    init_db()
    start_worker()


# API routes (all protected)
app.include_router(search.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(downloads.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(progress.router, prefix="/api", dependencies=[Depends(require_auth)])

# Serve static frontend
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", dependencies=[Depends(require_auth)])
def index():
    return FileResponse("app/static/index.html")

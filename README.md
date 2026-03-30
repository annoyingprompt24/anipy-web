# anipy-web

A lightweight web UI for searching and queueing anime downloads via [anipy-api](https://github.com/sdaqo/anipy-cli).
Downloads land in a shared volume alongside your qBittorrent/Jellyfin library.

```
anipy-web/
├── app/
│   ├── main.py          # FastAPI app + basic auth
│   ├── queue.py         # SQLite queue + background download worker
│   ├── routes/
│   │   ├── search.py    # /api/search, /api/episodes
│   │   ├── downloads.py # /api/queue, /api/jobs
│   │   └── progress.py  # /api/progress/:id  (SSE)
│   └── static/
│       └── index.html   # Single-page UI
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Deploy via Portainer

### 1. Push to git

```bash
git init
git remote add origin https://github.com/yourname/anipy-web.git
git add .
git commit -m "init"
git push -u origin main
```

### 2. Create a Portainer stack from git

1. In Portainer → **Stacks** → **Add stack**
2. Select **Repository**
3. Set **Repository URL** to your git remote
4. Set **Compose path** to `docker-compose.yml`
5. Under **Environment variables**, add:

| Variable       | Value                          |
|----------------|--------------------------------|
| `ANIPY_USER`   | your chosen username           |
| `ANIPY_PASS`   | your chosen password           |
| `DOWNLOAD_DIR` | `/mnt/media/downloads` *(host path shared with qBittorrent/Jellyfin)* |
| `PORT`         | `8080` *(or whatever port you want)* |

6. Click **Deploy the stack**

Portainer builds the image from the repo and starts the container.
Access the UI at `http://your-server-ip:8080`.

### 3. Updating

Push changes to git, then in Portainer:
- **Stacks** → select `anipy-web` → **Pull and redeploy**

---

## Local dev

```bash
cp .env.example .env
# edit .env with your values
docker compose up --build
```

---

## Environment variables

| Variable       | Required | Default           | Description                          |
|----------------|----------|-------------------|--------------------------------------|
| `ANIPY_USER`   | yes      | —                 | Basic auth username                  |
| `ANIPY_PASS`   | yes      | —                 | Basic auth password                  |
| `DOWNLOAD_DIR` | yes      | —                 | Host path to shared downloads folder |
| `PORT`         | no       | `8080`            | Host port for the web UI             |

---

## Volumes

| Mount point  | Purpose                                      |
|--------------|----------------------------------------------|
| `/downloads` | Shared with qBittorrent/Jellyfin. Anime goes into `/downloads/anime/<name>/` |
| `/data`      | SQLite queue DB (named volume, persists across redeploys) |

---

## Notes

- Downloads are queued serially — one episode at a time, in order
- In-progress downloads that were interrupted on container restart are re-queued automatically
- The `/data` named volume persists the queue DB across `Pull and redeploy` cycles in Portainer

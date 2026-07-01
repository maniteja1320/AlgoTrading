# Deploy on Railway (frontend + backend)

Two **Railway services** from one GitHub repo: Python API + React PWA.

```
Phone  →  Railway (frontend)
              ↓  VITE_API_URL
         Railway (backend)
              ↓
         Delta Exchange API
```

---

## 1. Push to GitHub

```powershell
cd c:\Users\dadapurammaniteja\Downloads\Algo
git init
git add .
git commit -m "Deploy to Railway"
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Do **not** commit `backend/.env` or `backend/data/api_credentials.json`.

---

## 2. Create Railway project

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your repo

---

## 3. Backend service

1. **New Service** → same repo
2. **Settings → Source → Root Directory:** `backend` ← **required**
3. **Settings → Config-as-code → Railway config file:** `/backend/railway.toml`  
   (Config path is **absolute from repo root**, not relative to Root Directory.)
4. **Settings → Build → Builder:** **Dockerfile** (if the deploy still uses Railpack, set this manually)
5. Optional env var: `RAILWAY_DOCKERFILE_PATH` = `Dockerfile` (only if Root Directory is `backend`)
6. **Settings → Networking → Generate Domain** → copy URL, e.g.  
   `https://delta-algo-api-production.up.railway.app`

### Backend environment variables

**Settings → Variables:**

| Variable | Value |
|----------|--------|
| `DELTA_API_KEY` | Your Delta API key (optional if using Settings UI) |
| `DELTA_API_SECRET` | Your Delta API secret |
| `DELTA_ENV` | `production` |
| `CORS_ORIGINS` | `https://YOUR-FRONTEND.up.railway.app,http://localhost:5173` |

Add the frontend URL to `CORS_ORIGINS` **after** step 4 (you can redeploy backend once frontend URL is known).

### Verify backend

Open `https://YOUR-BACKEND.up.railway.app/health` → `{"status":"ok"}`

---

## 4. Frontend service

1. **New Service** → same repo
2. **Root Directory:** `frontend` ← **required**
3. **Config-as-code file:** `/frontend/railway.toml`
4. **Build → Builder:** **Dockerfile**
5. **Variables** (set **before** deploy / redeploy after change):

| Variable | Value |
|----------|--------|
| `BACKEND_URL` | `https://YOUR-BACKEND.up.railway.app` (no trailing slash) — **runtime proxy, no rebuild needed** |
| `VITE_API_URL` | *(optional)* only if not using `BACKEND_URL`; requires rebuild |

`BACKEND_URL` makes nginx proxy `/api` and `/health` to your backend. The app uses same-origin requests, so Settings Save works without baking the URL into the build.

4. **Networking → Generate Domain** → e.g. `https://delta-algo-web.up.railway.app`
5. Update backend `CORS_ORIGINS` with this URL → redeploy backend

### Install on phone

Open frontend URL → **Install app** / **Add to Home Screen**

---

## 5. API keys

Either set `DELTA_API_KEY` / `DELTA_API_SECRET` on the backend, **or** open the app → **Settings** → Save keys (stored in `backend/data/` on the container).

---

## Important notes

### Always-on for algo strategies

Scheduled entries/exits need the backend **running 24/7**. Railway free trial credits run out; for live algo use a **paid Hobby plan** (~$5/mo) or keep backend on your PC (see [DEPLOY-FREE.md](DEPLOY-FREE.md)).

### Data persistence

`my_strategies.json` and saved API keys live on the container disk. **Redeploys can wipe them.** After each deploy:

- Re-save API keys in Settings, or use env vars
- Re-create / re-activate strategies if needed

For persistent disk, attach a **Railway Volume** mounted at `/app/data` (paid feature).

### Deploy order

1. Deploy **backend** → get backend URL  
2. Set `VITE_API_URL` on **frontend** → deploy frontend → get frontend URL  
3. Set `CORS_ORIGINS` on **backend** with frontend URL → redeploy backend  

### Local dev unchanged

```powershell
cd backend; .\restart.ps1
cd frontend; npm run dev
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `start.sh not found` / Railpack can't build | **Root Directory** must be `backend` or `frontend`, not repo root. Set **Builder → Dockerfile** and config file `/backend/railway.toml` |
| Frontend can't reach API | Check `VITE_API_URL`, redeploy frontend after changing it |
| CORS error | Add exact frontend URL to `CORS_ORIGINS`, redeploy backend |
| Build fails on frontend | Ensure `VITE_API_URL` is set before build |
| Strategies reset | Expected on redeploy without Volume; re-save config |

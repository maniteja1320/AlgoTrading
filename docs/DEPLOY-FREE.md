# Free hosting: PC backend + cloud frontend

Run the **algo backend on your Windows PC** (free, always-on while PC runs) and host the **mobile PWA frontend** on Netlify or Render (free).

```
Phone  →  Netlify / Render (frontend PWA)
              ↓  VITE_API_URL
         Cloudflare Tunnel (HTTPS)
              ↓
         Your PC :8002 (backend + strategies)
              ↓
         Delta Exchange API
```

---

## Part 1 — Backend on your PC

### One-time setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend\.env`:

```env
DELTA_API_KEY=...
DELTA_API_SECRET=...
DELTA_ENV=production
CORS_ORIGINS=http://localhost:5173,https://YOUR-FRONTEND.netlify.app
```

Replace `YOUR-FRONTEND.netlify.app` with your real Netlify/Render URL after Part 2.

### Install Cloudflare Tunnel

```powershell
winget install Cloudflare.cloudflared
```

Close and reopen PowerShell after install.

### Option A — Quick tunnel (easiest, URL changes each restart)

```powershell
cd backend
.\start-public.ps1
```

Copy the **`https://….trycloudflare.com`** URL from the output.

- Use it as **`VITE_API_URL`** on Netlify (Part 2).
- If you restart the script, the URL **changes** → update Netlify and redeploy.

### Option B — Named tunnel (stable URL, recommended)

Requires a domain on Cloudflare (your own domain, ~$10/yr, or any domain you already have).

```powershell
cloudflared tunnel login
cloudflared tunnel create algo-backend
```

Note the **tunnel ID** from the output.

```powershell
copy backend\cloudflared\config.example.yml backend\cloudflared\config.yml
```

Edit `config.yml`: set `tunnel`, `credentials-file`, and `hostname` (e.g. `api.yourdomain.com`).

```powershell
cloudflared tunnel route dns algo-backend api.yourdomain.com
cd backend
.\start-named-tunnel.ps1
```

Your stable API URL: **`https://api.yourdomain.com`**

### Keep PC awake

- Plug in power, disable sleep while trading: **Settings → System → Power → Sleep = Never** (on AC).
- Leave `start-public.ps1` or `start-named-tunnel.ps1` running.
- Strategies only run while the backend process is up.

---

## Part 2 — Frontend on Netlify (free)

1. Push this repo to GitHub (do not commit `.env` or `api_credentials.json`).
2. [netlify.com](https://netlify.com) → **Add site → Import from Git**.
3. Settings come from `netlify.toml` automatically.
4. **Site settings → Environment variables:**

   | Key | Value |
   |-----|--------|
   | `VITE_API_URL` | Your tunnel URL, e.g. `https://abc.trycloudflare.com` or `https://api.yourdomain.com` |

   No trailing slash.

5. **Deploy site**.
6. Add the Netlify URL to backend `CORS_ORIGINS` in `.env`, restart backend if you change it.
7. On your phone: open the Netlify URL → **Install app** / **Add to Home Screen**.

### Render Static Site (instead of Netlify)

- **Root directory:** `frontend`
- **Build:** `npm install && npm run build`
- **Publish:** `dist`
- **Env:** `VITE_API_URL` = same tunnel URL

---

## Part 3 — API keys on the hosted app

1. Open the PWA on your phone.
2. **Settings** → paste Delta API key + secret → **Save**.
3. Keys are stored in `backend/data/api_credentials.json` on **your PC**.

---

## Checklist

- [ ] Backend runs: `http://127.0.0.1:8002/health` → `{"status":"ok"}`
- [ ] Tunnel URL opens `/health` in phone browser
- [ ] `CORS_ORIGINS` includes your Netlify/Render URL
- [ ] `VITE_API_URL` set on Netlify and site redeployed
- [ ] Settings → API connected on phone
- [ ] PC stays on during market hours

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Phone app “failed to fetch” | Check tunnel is running; verify `VITE_API_URL`; redeploy frontend after URL change |
| CORS error | Add exact frontend URL to `CORS_ORIGINS`, restart backend |
| Strategy not entering | PC asleep or backend stopped; check backend window for logs |
| URL changed after restart | Use **named tunnel** (Option B) or update `VITE_API_URL` and redeploy |

---

## Local dev (unchanged)

```powershell
# Terminal 1
cd backend
.\restart.ps1

# Terminal 2
cd frontend
npm run dev
```

Open http://localhost:5173 — no tunnel needed.

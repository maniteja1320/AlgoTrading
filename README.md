# Delta BTC Options Algo Trading

Web application for algorithmic trading of **BTC options** on [Delta Exchange India](https://india.delta.exchange) (INR-settled).

## Features

- **BTC option chain** — live calls/puts with Greeks, bid/ask, OI
- **Manual order entry** — limit and market orders from the chain
- **Positions & orders** — monitor and cancel open orders
- **Algo strategies** — Short Straddle (ATM) and Iron Condor scaffold
- **Testnet first** — defaults to Delta India testnet

## Architecture

```
frontend/     React + Vite dashboard (port 5173)
backend/      FastAPI + delta-rest-client (port 8000)
```

Public market data works without API keys. Trading and strategies require Delta API credentials.

## Quick Start

### 1. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env with your Delta testnet API key/secret
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### 3. API Keys

1. Create a **testnet** account: https://testnet.delta.exchange/
2. Go to **Settings → API Management** and create a key with **Trading** permission
3. In the app, click **Settings** (gear icon) and paste key + secret
4. Or set `DELTA_API_KEY` and `DELTA_API_SECRET` in `backend/.env`

**Important:** Keep your API secret server-side only. Never commit `.env`.

## Delta India Endpoints

| Environment | Base URL |
|-------------|----------|
| Testnet | `https://cdn-ind.testnet.deltaex.org` |
| Production | `https://api.india.delta.exchange` |

Option: `BTCUSD` (perpetual), options symbols like `C-BTC-90000-310125`.

## Strategies

| ID | Description |
|----|-------------|
| `short_straddle` | Sells ATM call + put when combined mark premium ≥ `min_premium` |
| `iron_condor` | Preview/scaffold for OTM spreads |

Extend strategies in `backend/app/strategies/base.py` and register in `manager.py`.

## Deploy on Railway

Full guide: **[docs/DEPLOY-RAILWAY.md](docs/DEPLOY-RAILWAY.md)**

Two services from one repo:

| Service | Root directory | Key env vars |
|---------|----------------|--------------|
| **Backend** | `backend` | `DELTA_*`, `CORS_ORIGINS` |
| **Frontend** | `frontend` | `VITE_API_URL` = backend public URL |

## Free hosting (PC backend + mobile frontend)

**Recommended free setup:** backend on your **Windows PC**, frontend on **Netlify** or **Render**, linked with a **Cloudflare Tunnel**.

→ Full step-by-step guide: **[docs/DEPLOY-FREE.md](docs/DEPLOY-FREE.md)**

Quick start:

```powershell
# 1. Install tunnel: winget install Cloudflare.cloudflared
# 2. Start backend + public URL:
cd backend
.\start-public.ps1
# 3. Copy the https://….trycloudflare.com URL → Netlify env VITE_API_URL
# 4. Add Netlify URL to backend .env CORS_ORIGINS
```

The frontend is a **PWA** — install on your phone via **Add to Home Screen**.

## Deploy to Netlify only (frontend)

See [docs/DEPLOY-FREE.md](docs/DEPLOY-FREE.md) Part 2. The backend must still run somewhere reachable (your PC + tunnel is the free option).

## Disclaimer

This software is for educational purposes. Options trading involves significant risk. Test thoroughly on testnet before live trading. You are responsible for your own trades and compliance with local regulations.

# Deploying CalibrationCompass

The original project is a single **Streamlit** app (`dashboard.py`). Streamlit
needs a persistent, long-running server, which **Vercel does not provide**
(Vercel runs short-lived serverless functions). So for deployment the app is
split into two independently hosted pieces:

| Piece | Hosts | Lives in | Why |
|-------|-------|----------|-----|
| **Backend API** (FastAPI) | **Render** | `backend/` | Long-running server; runs Qiskit + talks to IBM Quantum |
| **Frontend** (static site) | **Vercel** | `frontend/` | Static HTML/CSS/JS; calls the backend API |

The original research scripts and `dashboard.py` remain at the repo root and are
untouched — they are the project's substance and still run locally.

> **Note on dependencies:** the live app only transpiles circuits and queries
> IBM calibration data, so the backend needs just `qiskit`,
> `qiskit-ibm-runtime`, `pandas`, `numpy` (+ FastAPI). The heavy research libs
> (`qiskit-aer`, `xgboost`, `shap`, `scikit-learn`, `matplotlib`) are **not**
> required to deploy and are intentionally excluded from `backend/requirements.txt`.

---

## 1. Deploy the backend to Render

### Option A — Blueprint (uses `render.yaml`)
1. Push this repo to GitHub (you'll do this manually).
2. In Render: **New + → Blueprint**, pick this repo. Render reads `render.yaml`
   and creates a web service named `calibrationcompass-api`.
3. When prompted, set the secret env vars (see below).

### Option B — Manual web service
1. Render: **New + → Web Service**, connect this repo.
2. Settings:
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/api/health`

### Environment variables (Render → service → Environment)
| Key | Value |
|-----|-------|
| `IBM_QUANTUM_TOKEN` | **your IBM Quantum API token** (secret) |
| `IBM_CHANNEL` | `ibm_quantum_platform` |
| `IBM_INSTANCE` | `open-instance` |
| `FRONTEND_ORIGIN` | your Vercel URL, e.g. `https://calibrationcompass.vercel.app` (use `*` while testing) |
| `PYTHON_VERSION` | `3.11.9` (already set by the Blueprint) |

After it deploys, note the URL, e.g. `https://calibrationcompass-api.onrender.com`.
Open `…/api/health` — it should return `{"status":"ok", ...}`.

> **Free plan caveat:** Render free web services sleep after inactivity, so the
> first request after idle can take ~30–60 s to wake. That's expected.

---

## 2. Deploy the frontend to Vercel

1. Vercel: **Add New → Project**, import this repo.
2. Settings:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Other (no build step; it's static).
3. Point the frontend at your backend. Either:
   - **Easiest:** edit `frontend/config.js` and set
     `apiBase: "https://calibrationcompass-api.onrender.com"`, commit, deploy; **or**
   - After the site is live, type the backend URL into the **"Backend URL"**
     field (top-right of the page). It's saved in your browser and overrides
     `config.js`. Good for testing without redeploying.
4. Once you know the Vercel URL, go back to Render and set `FRONTEND_ORIGIN`
   to it (for CORS), then redeploy the backend.

---

## 3. Local development

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then edit IBM_QUANTUM_TOKEN
uvicorn main:app --reload --port 8000
```

Frontend (any static server):
```bash
cd frontend
python -m http.server 5173
# open http://localhost:5173 — default backend URL is http://localhost:8000
```

---

## API reference

| Method | Path | Body | Returns |
|--------|------|------|---------|
| GET | `/api/health` | — | `{status, backends}` |
| GET | `/api/presets` | — | `{backends, presets}` |
| POST | `/api/analyze` | `{qasm, backends[]}` | circuit metrics, backend status, ranked candidates, recommendation, confidence |
| POST | `/api/submit` | `{qasm, backend, candidate_seed, shots}` | `{job_id}` |
| GET | `/api/result/{job_id}` | — | `{status, ready, terminal, counts?, error?}` |

---

## Security notes
- The IBM token lives **only** in Render's environment — never in the repo or
  the frontend. `.env` is git-ignored; only `.env.example` is committed.
- Set `FRONTEND_ORIGIN` to your real Vercel URL in production so the API isn't
  open to every origin.

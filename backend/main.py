"""CalibrationCompass API (FastAPI).

Serves the calibration-aware backend/mapping recommender and IBM QPU execution
to a separate frontend (e.g. a static site hosted on Vercel).

Run locally:
    uvicorn main:app --reload --port 8000

Environment variables (see .env.example):
    IBM_QUANTUM_TOKEN   IBM Quantum API token (required for live calls)
    IBM_CHANNEL         default: ibm_quantum_platform
    IBM_INSTANCE        default: open-instance
    FRONTEND_ORIGIN     comma-separated allowed origins for CORS (default: *)
"""

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core import BACKENDS, PRESETS, run_analysis
from qpu_executor import get_qpu_result, submit_to_qpu

app = FastAPI(title="CalibrationCompass API", version="1.0.0")

_origins = os.environ.get("FRONTEND_ORIGIN", "*").strip()
if _origins == "*" or not _origins:
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    qasm: str
    backends: Optional[List[str]] = None


class SubmitRequest(BaseModel):
    qasm: str
    backend: str
    candidate_seed: int
    shots: int = 512


@app.get("/")
def root():
    return {
        "name": "CalibrationCompass API",
        "status": "ok",
        "endpoints": ["/api/health", "/api/presets", "/api/analyze",
                      "/api/submit", "/api/result/{job_id}"],
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "backends": BACKENDS}


@app.get("/api/presets")
def presets():
    return {"backends": BACKENDS, "presets": PRESETS}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    backend_names = req.backends or BACKENDS
    try:
        return run_analysis(req.qasm, backend_names)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"IBM Quantum error: {exc}")


@app.post("/api/submit")
def submit(req: SubmitRequest):
    try:
        return submit_to_qpu(
            req.qasm, req.backend, req.candidate_seed, shots=req.shots
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"QPU submission failed: {exc}")


@app.get("/api/result/{job_id}")
def result(job_id: str):
    try:
        return get_qpu_result(job_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not retrieve result: {exc}"
        )

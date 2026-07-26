"""
app.py
------
FastAPI entrypoint for PhishGuard. Wires together the full pipeline
(parse -> triage -> coach -> store) behind a small set of REST endpoints
that the frontend calls.

Endpoints:
  POST /api/analyze          - upload a .eml file, runs the full pipeline
  GET  /api/analyses         - list all stored analyses
  GET  /api/analyses/{id}    - get one analysis by id
  GET  /api/analyses/{id}/report - download that analysis as a PDF
  GET  /api/dashboard        - aggregated stats for the dashboard page

Run with (from inside backend/):
  uvicorn app:app --reload
"""

import os
import shutil
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from parser.email_parser import analyze_email
from ai.llm_agent import triage_email, generate_coaching_message
from database.db import (
    init_db,
    save_analysis,
    get_all_analyses,
    get_analysis_by_id,
    get_verdict_counts,
    get_top_techniques,
    get_trend_over_time,
)
from reports.pdf_generator import generate_incident_pdf

app = FastAPI(title="PhishGuard API")

# Allow the frontend (served separately, e.g. via Live Server or a
# different port) to call this API during local development.
# For a real production deployment you'd restrict this to your actual
# frontend domain -- "*" is fine for a student project demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
def on_startup():
    """Creates the database tables (if they don't exist yet) when the server starts."""
    init_db()


@app.get("/")
def root():
    """Simple health check -- confirms the server is up."""
    return {"status": "PhishGuard API is running"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    Accepts an uploaded .eml file and runs it through the full pipeline:
    Stage 1 (parse) -> Stage 2 (triage) -> Stage 3 (coach) -> save to DB.

    Returns the complete saved analysis record as JSON.
    """
    if not file.filename.endswith(".eml"):
        raise HTTPException(status_code=400, detail="Only .eml files are supported.")

    # Save the upload to a temp path with a unique name so concurrent
    # uploads never collide with each other.
    temp_filename = f"{uuid.uuid4().hex}_{file.filename}"
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Stage 1
        parsed = analyze_email(temp_path)

        # Stage 2
        triage = triage_email(parsed)

        # Stage 3
        coaching = generate_coaching_message(triage, parsed)

        # Save everything together
        saved = save_analysis(parsed, triage, coaching)

        return saved

    except Exception as e:
        # Don't let a single bad upload crash the server -- surface a
        # clean error to the frontend instead.
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    finally:
        # Clean up the temp file regardless of success/failure
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/api/analyses")
def list_analyses():
    """Returns every stored analysis, most recent first."""
    return get_all_analyses()


@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: int):
    """Returns a single stored analysis by ID."""
    result = get_analysis_by_id(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return result


@app.get("/api/analyses/{analysis_id}/report")
def download_report(analysis_id: int):
    """Generates (or regenerates) and returns the PDF report for one analysis."""
    analysis = get_analysis_by_id(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    pdf_path = generate_incident_pdf(analysis)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"phishguard_report_{analysis_id}.pdf",
    )


@app.get("/api/dashboard")
def dashboard_stats():
    """
    Returns all aggregated stats needed for the dashboard page in one call,
    so the frontend doesn't need four separate requests.
    """
    return {
        "verdict_counts": get_verdict_counts(),
        "top_techniques": get_top_techniques(),
        "trend_over_time": get_trend_over_time(),
    }
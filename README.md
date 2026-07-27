# PhishGuard — AI Phishing Triage & Coaching Agent

An AI-powered agent that automates the triage of employee-reported phishing emails and closes the feedback loop by coaching employees on what tipped off the attack, turning a security tool into a training tool.

## Problem Statement
Most SMBs tell employees to "report suspicious emails to IT," but reported emails often go untriaged for hours/days, and employees rarely get feedback on whether their report was correct - causing reporting behavior to decline over time. PhishGuard automates triage and closes that feedback loop.

## Features
- **Stage 1 - Parsing:** Extracts headers, links, attachments from forwarded `.eml` files; checks SPF/DKIM/DMARC pass/fail
- **Stage 2 - AI Triage:** LLM-based agent classifies verdict (phishing/suspicious/legitimate), severity, and manipulation technique (spoofing, urgency, credential harvesting, BEC)
- **Stage 3 - Coaching Reply:** Generates a personalized, non-condescending explanation back to the employee on what to watch for
- **Stage 4 - Dashboard & Reporting:** Aggregated view of phishing verdict distribution, top techniques, and trend over time; exportable per-incident PDF reports

## Tech Stack
- **Backend:** Python, FastAPI
- **AI/LLM:** OpenRouter (OpenAI-compatible API), using the `openrouter/free` auto-router
- **Database:** SQLite via SQLAlchemy
- **Frontend:** HTML, CSS, vanilla JavaScript, Chart.js
- **Reporting:** PDF generation via ReportLab
- **Testing:** pytest
- **Deployment:** Render (backend Web Service + frontend Static Site, deployed separately)

## Project Structure
```
backend/
├── app.py                  # FastAPI entrypoint — all API endpoints
├── ai/
│   ├── llm_agent.py        # Stage 2 + 3: triage + coaching calls (OpenRouter)
│   ├── prompts.py          # Prompt templates
│   └── demo_cache.py        # Pre-cached fallback responses for demo reliability
├── parser/
│   ├── email_parser.py     # Stage 1: .eml parsing
│   ├── header_analysis.py  # SPF/DKIM/DMARC checks
│   └── url_extractor.py    # URL extraction + suspicious-link flagging
├── reports/
│   └── pdf_generator.py    # Per-incident PDF report generation
├── database/
│   ├── models.py            # SQLAlchemy schema
│   └── db.py                 # DB connection + save/query + aggregation functions
├── sample_emails/          # Test/demo .eml files (23 samples, real + synthetic)
├── requirements.txt
└── .env.example

frontend/
├── index.html
├── style.css
└── script.js

tests/
├── test_parser.py
└── test_agent.py

docs/
├── architecture.md
└── project_report.md
```

## Setup

**Backend:**
```bash
git clone https://github.com/<your-username>/PhishGuard.git
cd PhishGuard/backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
python -m pip install -r requirements.txt
cp .env.example .env  # add your OpenRouter API key
uvicorn app:app --reload
```

**Frontend** (in a separate terminal):
```bash
cd PhishGuard/frontend
python -m http.server 8080
```
Open `http://127.0.0.1:8080` in your browser. Make sure `API_BASE` in `script.js` points at wherever your backend is running (`http://127.0.0.1:8000` for local, or your deployed Render URL).

## Running Tests
```bash
cd backend
pytest tests/ -v
```

## Environment Variables
See `.env.example`:
```
OPENROUTER_API_KEY=your_api_key_here
```
Get a free key at [openrouter.ai](https://openrouter.ai).

## Deployment
Deployed on Render as two separate services:
- **Backend** (Web Service, root directory `backend/`): `https://phishguard-iih7.onrender.com`
- **Frontend** (Static Site, root directory `frontend/`): `https://phishguardf.onrender.com/`

Note: Render's free tier has no persistent disk, so the SQLite database resets on every redeploy or idle-timeout restart; expected behavior, not a bug.

## Project Status
Core pipeline complete and deployed - all 4 stages implemented, tested, and live.

## License
MIT
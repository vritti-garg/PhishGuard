# PhishGuard - AI Phishing Triage & Coaching Agent

An AI-powered agent that automates the triage of employee-reported phishing emails and closes the feedback loop by coaching employees on what tipped off the attack - turning a security tool into a training tool.

## Problem Statement
Most SMBs tell employees to "report suspicious emails to IT," but reported emails often go untriaged for hours/days, and employees rarely get feedback on whether their report was correct - causing reporting behavior to decline over time. PhishGuard automates triage and closes that feedback loop.

## Features
- **Stage 1 - Parsing:** Extracts headers, links, attachments from forwarded `.eml` files; checks SPF/DKIM/DMARC
- **Stage 2 - AI Triage:** LLM-based agent classifies verdict (phishing/legit), severity, and manipulation technique (spoofing, urgency, credential harvesting, BEC)
- **Stage 3 - Coaching Reply:** Generates a personalized explanation back to the employee on what to watch for
- **Stage 4 - Dashboard & Reporting:** Aggregated view of phishing trends, department-level reporting stats, exportable PDF reports

## Tech Stack
- **Backend:** Python, FastAPI
- **AI/LLM:** 
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript
- **Reporting:** PDF generation (WeasyPrint/ReportLab)


## Setup
```bash
git clone https://github.com/vritti-garg/PhishGuard.git
cd PhishGuard/backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env  # add your Anthropic API key
uvicorn app:app --reload
```

## Project Status
🚧 In development - see `docs/architecture.md` for pipeline design.

## License
MIT
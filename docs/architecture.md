# PhishGuard — Architecture

Technical reference for the system design. For the narrative writeup (problem
statement, methodology, results, evaluation), see `docs/project_report.md`.

---

## 1. High-level pipeline

```mermaid
flowchart TD
    A[".eml file uploaded"] --> B["Stage 1: Parsing<br/>(parser/)"]
    B --> C["Stage 2: AI Triage<br/>(ai/llm_agent.py via OpenRouter)"]
    C --> D["Stage 3: Coaching Reply<br/>(ai/llm_agent.py via OpenRouter)"]
    D --> E["Stage 4: Storage<br/>(database/db.py — SQLite)"]
    E --> F["Dashboard aggregation"]
    E --> G["PDF report generation<br/>(reports/pdf_generator.py)"]
```

Each stage's output is the next stage's input — Stage 1's deterministic JSON
feeds directly into the Stage 2 prompt, Stage 2's verdict feeds into the
Stage 3 coaching prompt, and the combined result of all three is what gets
persisted in Stage 4.

---

## 2. Component breakdown

```
backend/
├── app.py                  FastAPI app — wires all stages behind REST endpoints
│
├── parser/                 STAGE 1 — deterministic, no LLM involved
│   ├── email_parser.py     Parses .eml -> sender, subject, body, attachments
│   ├── header_analysis.py  Reads SPF/DKIM/DMARC results from mail headers
│   └── url_extractor.py    Extracts URLs, flags shorteners/IP/lookalikes
│
├── ai/                     STAGE 2 + 3 — LLM reasoning via OpenRouter
│   ├── prompts.py           Prompt templates (triage + coaching)
│   ├── llm_agent.py          API calls, retries, validation, fallback
│   └── demo_cache.py         Pre-verified fallback results for demo reliability
│
├── database/                STAGE 4 (storage)
│   ├── models.py             SQLAlchemy schema (EmailAnalysis table)
│   └── db.py                  Connection, save/query, dashboard aggregation
│
└── reports/                 STAGE 4 (reporting)
    └── pdf_generator.py       Per-incident PDF export (ReportLab)

frontend/
├── index.html                Upload / Results / Dashboard tabs
├── style.css                  Design tokens + layout
└── script.js                   Calls the backend API, renders results + charts
```

---

## 3. Request flow: uploading an email

```mermaid
sequenceDiagram
    participant U as User (browser)
    participant F as Frontend (script.js)
    participant A as app.py
    participant P as parser/
    participant L as ai/llm_agent.py + demo_cache.py
    participant D as database/db.py

    U->>F: Selects/drops a .eml file
    F->>A: POST /api/analyze (multipart file)
    A->>P: analyze_email(temp_path)
    P-->>A: parsed JSON (sender, body, auth_check, urls)
    A->>L: triage_email_with_cache(parsed, filename)
    L-->>A: verdict, technique, severity, confidence, reasoning
    A->>L: generate_coaching_message_with_cache(triage, parsed, filename)
    L-->>A: coaching message text
    A->>D: save_analysis(parsed, triage, coaching)
    D-->>A: saved record (with id)
    A-->>F: JSON response
    F-->>U: Renders verdict badge + reasoning + coaching note
```

If Stage 2 fails after retries (API down, rate-limited, invalid response), the
pipeline does **not** crash — it returns a result flagged
`manual_review_required: true`, and Stage 3 short-circuits to a safe fallback
message instead of attempting a second doomed API call.

---

## 4. API reference

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/api/analyze` | Upload a `.eml` file, runs the full 4-stage pipeline, returns the saved record |
| `GET` | `/api/analyses` | List all stored analyses, most recent first |
| `GET` | `/api/analyses/{id}` | Get one analysis by ID |
| `GET` | `/api/analyses/{id}/report` | Generate and download that analysis as a PDF |
| `GET` | `/api/dashboard` | Aggregated stats: verdict counts, top techniques, trend over time |

---

## 5. Database schema

Single table, `email_analysis` (see `database/models.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-increment |
| `sender` | String | From Stage 1 |
| `subject` | String | From Stage 1 |
| `department` | String (nullable) | Not currently wired to any UI input |
| `verdict` | String | `phishing` / `suspicious` / `legitimate` |
| `technique` | String | e.g. `urgency_pressure`, `business_email_compromise` |
| `severity` | String | `low` / `medium` / `high` / `critical` |
| `confidence` | Float | 0.0–1.0 |
| `reasoning` | String | Model's explanation |
| `manual_review_required` | Boolean | `True` if Stage 2 fell back |
| `coaching_message` | String | Stage 3 output |
| `analyzed_at` | DateTime (UTC) | Set automatically on insert |

Kept as one flat table rather than a normalized multi-table design — at this
project's scale, a single table is simpler to query for dashboard
aggregation than joining across tables would be.

---

## 6. Deployment architecture

```mermaid
flowchart LR
    subgraph Render
        BE["Backend Web Service<br/>(root: backend/)<br/>uvicorn app:app"]
        FE["Frontend Static Site<br/>(root: frontend/)<br/>plain HTML/CSS/JS"]
    end
    Browser -->|"GET static files"| FE
    Browser -->|"fetch() API calls"| BE
    BE -->|"SQLite (ephemeral disk)"| DB[("phishguard.db")]
    BE -->|"HTTPS"| OR["OpenRouter API<br/>(openrouter/free)"]
```

Backend and frontend are deployed as **two independent Render services**
from the same GitHub repo (different root directories), so either can
redeploy without affecting the other. The database has no persistent disk on
Render's free tier — it resets on every redeploy or idle-timeout restart,
which is expected behavior for this deployment tier (see
`docs/project_report.md`, Limitations, for the production alternative).

---

## 7. Design principle: deterministic checks vs. AI reasoning

A recurring theme across the codebase: anything with a ground-truth correct
answer is computed in Python, never left to the LLM to "decide."

| Determined by Python (never re-evaluated by the LLM) | Determined by the LLM |
|---|---|
| SPF / DKIM / DMARC pass-fail | Which social-engineering technique is being used |
| Whether a URL is shortened / IP-based / lookalike | Overall severity |
| Whether a field parses successfully | Confidence in the verdict |
| — | Plain-language reasoning and coaching text |

This split is why the Stage 2 prompt (`ai/prompts.py`) explicitly instructs
the model not to re-derive facts already provided — it only reasons on top
of them.
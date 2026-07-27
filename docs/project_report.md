# PhishGuard — AI Phishing Triage & Coaching Agent

**Project Report**

Team: Vritti Garg, Divyanka Kirola
B.Tech Computer Science & Engineering (Cyber Security), SRM University Delhi-NCR

---

## Abstract

Small and medium-sized businesses (SMBs) frequently ask employees to forward
suspicious emails to IT, but rarely have the staffing to triage those reports
quickly or to give employees feedback on what they got right or wrong. Over
time, this causes reporting behavior to decline, leaving organizations blind
to real phishing attempts already inside employee inboxes.

PhishGuard is an AI agent that automates this reporting pipeline end-to-end.
It parses a forwarded `.eml` file, performs deterministic authentication and
URL-based checks (SPF/DKIM/DMARC, shortened/IP-based/lookalike URLs), passes
the results to a large language model for reasoning-based triage (verdict,
technique, severity, confidence), generates a plain-language coaching message
for the employee who reported it, and stores everything in a database for
dashboard reporting and PDF export. The system deliberately separates
deterministic checks (handled in Python, where correctness is non-negotiable)
from judgment-based reasoning (handled by the LLM, where nuance is required)
— mirroring the two-phase design philosophy used in static code analysis
tools.

The result is a lightweight, self-hostable "SOC-in-a-box" for phishing
triage that closes the feedback loop between detection and employee
awareness, without requiring dedicated security staff or paid infrastructure.

---

## 1. Problem Statement

Most SMBs lack the resources for a 24/7 Security Operations Center (SOC),
yet phishing remains one of the most common initial access vectors in real
breaches. Even organizations that *do* ask employees to report suspicious
emails typically fail at the two hardest parts of the process:

1. **Timely triage** — reported emails often sit unread for hours or days,
   during which an active attack can succeed elsewhere in the organization.
2. **Employee feedback** — employees who report an email rarely learn
   whether it was actually malicious, or what specifically made it
   suspicious. Without this feedback loop, reporting behavior atrophies:
   employees stop bothering to report, because it feels like shouting into
   a void.

PhishGuard addresses both problems with a single pipeline: automated,
near-instant triage, and an automated coaching reply that turns every
reported email into a small security-awareness lesson.

---

## 2. System Architecture

PhishGuard is a four-stage pipeline, where each stage's output is the next
stage's input:

```
Uploaded .eml file
        |
        v
STAGE 1 -- Deterministic Parsing & Detection (Python)
  - Extracts sender, subject, body, attachments (parser/email_parser.py)
  - Checks SPF / DKIM / DMARC pass-fail from mail headers (header_analysis.py)
  - Extracts URLs and flags shorteners, IP-based links, excessive
    subdomains, and lookalike domains (url_extractor.py)
  - Output: one structured JSON object per email
        |
        v
STAGE 2 -- AI Triage Agent (LLM via OpenRouter)
  - Reasons over the Stage 1 facts (never re-derives them)
  - Classifies verdict (phishing / suspicious / legitimate)
  - Identifies the social-engineering technique used
  - Assigns severity and a confidence score
  - Output: structured JSON verdict with reasoning
        |
        v
STAGE 3 -- Coaching Reply Agent (LLM via OpenRouter)
  - Takes the Stage 2 verdict and writes a short, non-condescending,
    plain-language explanation for the employee who reported the email
        |
        v
STAGE 4 -- Storage, Dashboard & Reporting
  - Persists the full record (SQLite via SQLAlchemy)
  - Serves aggregated statistics (verdict distribution, top techniques,
    trend over time) to a dashboard
  - Generates a client-ready PDF incident report per analysis (ReportLab)
```

### Why this split?

Determinism matters for a security tool. SPF/DKIM/DMARC results and
URL red flags have an objectively correct answer — letting a language
model "decide" these would introduce unnecessary hallucination risk into
checks that should never be ambiguous. Python owns anything with a
ground-truth answer; the LLM is reserved for genuinely judgment-based
work (technique classification, severity reasoning, natural-language
coaching) that Python cannot do on its own.

---

## 3. Methodology

### 3.1 Stage 1 — Parsing and deterministic detection

Emails are parsed using Python's standard `email` library. Multipart
messages are walked to extract the plain-text body specifically (skipping
attachment parts), and attachment filenames are recorded without inspecting
their contents. Authentication results are read directly from the
`Authentication-Results` (or `Received-SPF`) headers already stamped by the
receiving mail server — PhishGuard does not perform live DNS lookups, which
keeps the tool simple, fast, and independent of network conditions.

URL extraction uses regex matching combined with a small set of heuristics:
known shortening services, IP-address-based URLs, domains with an unusually
high subdomain count, and simple lookalike-character patterns (e.g. `1`
substituted for `l`).

### 3.2 Stage 2 — AI triage

The parsed Stage 1 JSON is embedded into a structured prompt (see
`ai/prompts.py`) that explicitly instructs the model not to re-evaluate the
deterministic facts already provided, and to reason only about what those
facts imply. The model is asked to return a strict JSON object containing
`verdict`, `technique`, `severity`, `confidence`, and `reasoning`.

Because model-side JSON-schema enforcement is not uniformly available
across free-tier providers, the response is validated in code
(`_validate_triage_result()` in `ai/llm_agent.py`) against an allowed set of
verdict/technique/severity values before being trusted. A response that
fails validation is treated identically to an API failure.

### 3.3 Stage 3 — Coaching generation

A second, separate prompt takes the Stage 2 verdict and produces a short,
plain-language message aimed at a non-technical employee — explaining what
gave the email away and what to watch for next time, without jargon like
"SPF" or "DMARC."

### 3.4 Reliability engineering

Two mechanisms guard against a live LLM provider being unavailable during
critical moments (e.g. a live demo):

- **Retry + graceful fallback**: every LLM call retries once on failure,
  and if all retries are exhausted, the pipeline returns a clearly-flagged
  `manual_review_required: true` result rather than crashing.
- **Demo cache** (`ai/demo_cache.py`): a small set of known filenames map to
  previously-verified, real model output. If the live API fails for one of
  these specific files, the cached (but genuinely model-generated) result is
  served instead of the generic fallback message.

### 3.5 Storage and reporting

A single `EmailAnalysis` table (SQLAlchemy ORM) stores the Stage 1 basics,
Stage 2 verdict, and Stage 3 coaching message together as one row per
analyzed email. Dashboard aggregation (verdict distribution, top techniques,
day-level trend) is computed in Python over this table rather than with raw
SQL `GROUP BY`, which keeps the logic readable at the data volumes a
student/demo project realistically produces. PDF reports are generated
per-analysis using ReportLab's Platypus layout engine, with severity-based
color coding for quick visual triage.

### 3.6 Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| AI/LLM | OpenRouter (OpenAI-compatible API), `openrouter/free` auto-router |
| Database | SQLite via SQLAlchemy |
| PDF generation | ReportLab |
| Frontend | HTML, CSS, vanilla JavaScript, Chart.js |
| Testing | pytest |
| Deployment | Render (separate backend Web Service + frontend Static Site) |

---

## 4. Results

> **Fill in with your own final testing numbers before submission** —
> the placeholders below describe what to report and how to phrase it.

- **Sample dataset**: 23 sample `.eml` files were collected, combining
  real phishing/legitimate emails with synthetic test cases covering
  urgency-based phishing, business email compromise (BEC), credential
  harvesting, malicious attachments, HTML-only bodies, and ambiguous/subtle
  cases.
- **Parsing reliability**: all 23 samples were run through Stage 1
  (`parser/`) with zero crashes, including edge cases such as HTML-only
  bodies, missing authentication headers, and multipart attachments.
- **Triage accuracy**: [state how many of your 23 samples were manually
  reviewed and whether the verdict matched your own expert judgment — e.g.
  "X of 23 samples were manually reviewed against expected verdicts, with Y
  correct classifications."]
- **Automated test suite**: 25 unit tests across `tests/test_parser.py` and
  `tests/test_agent.py` — all passing. These specifically cover edge-case
  handling: missing files, missing API keys, simulated API timeouts,
  malformed model responses, and invalid enum values, in addition to normal
  parsing/detection correctness.
- **End-to-end deployment**: the full pipeline (upload → parse → triage →
  coach → store → dashboard/report) was verified working on a live Render
  deployment, not just locally.

---

## 5. Evaluation

- **Strengths**: the deterministic/AI split means the system's most
  security-critical checks (auth results, URL red flags) can never be
  "talked out of" a correct answer by the language model — a meaningful
  design advantage over end-to-end ML/LLM classifiers that treat every
  signal as equally uncertain.
- **Coaching quality**: [describe your own tone-check findings here — did
  the coaching messages read as respectful and non-condescending across
  the different phishing types you tested?]
- **Cost/accessibility**: using OpenRouter's free-tier models keeps the
  entire pipeline free to run, at the cost of occasional rate limits —
  mitigated in this project via the retry/fallback/demo-cache design rather
  than by upgrading to a paid tier.
- **Comparison to a pure ML/scikit-learn approach**: a trained classifier
  (e.g. the "Cyber AI SOC" style project) requires labeled training data and
  cannot explain its reasoning in natural language. PhishGuard's
  LLM-reasoning approach requires no training data and produces
  human-readable justifications and coaching text as a natural byproduct —
  though at the cost of per-request latency and dependency on an external
  API.

---

## 6. Limitations & Future Work

- **No real-time inbox monitoring** — PhishGuard currently analyzes one
  uploaded `.eml` file at a time; it does not integrate with a live mailbox
  (e.g. via Gmail/Outlook API) to ingest reports automatically.
- **No persistent storage on free-tier deployment** — Render's free web
  service tier does not provide a persistent disk, so the SQLite database
  resets on every redeploy or idle-timeout restart. A production version
  would use a managed database (e.g. PostgreSQL) instead.
- **Department-based dashboard segmentation is unwired** — the schema
  supports grouping reports by department, but no UI currently collects
  this field at upload time.
- **Single-model dependency** — triage quality depends on whichever model
  OpenRouter's free-tier auto-router currently provides; free-model
  availability and quality can change over time.
- **No attachment content scanning** — attachments are recorded by
  filename only; their contents are never inspected, so a malicious
  attachment could only be flagged indirectly (e.g. via accompanying
  urgency language), not directly.
- **Future work** could include: live mailbox integration, a management UI
  for department assignment, persistent cloud storage, and attachment
  sandboxing/scanning as a fifth pipeline stage.

---

## 7. Conclusion

PhishGuard demonstrates that combining deterministic security checks with
LLM-based reasoning — rather than relying on either approach alone —
produces a phishing-triage tool that is both reliable on ground-truth facts
and capable of nuanced, explainable judgment calls. By also automating the
employee-facing coaching step, the project addresses a part of the phishing
reporting workflow that most existing tools ignore: keeping employees
engaged in security reporting rather than letting the habit die out from
lack of feedback. The full pipeline — from raw `.eml` upload to a
downloadable PDF incident report — was implemented, tested (both manually
and via an automated pytest suite), and deployed to a live, publicly
accessible environment.
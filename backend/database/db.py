"""
db.py
-----
Handles the database connection (SQLite) and provides simple helper
functions to save and retrieve EmailAnalysis records.

Uses SQLite because it's zero-setup -- no separate database server
needed, just a local file (phishguard.db). Perfect for a student
project and for the demo-day "run locally as backup" plan.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, EmailAnalysis

# The .db file will be created in whatever directory you run the app from --
# for consistency, we anchor it to this file's own directory (backend/).
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "phishguard.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False is needed because FastAPI can use the DB across
# different threads/requests -- safe for SQLite in this project's scale.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """
    Creates the database tables if they don't already exist.
    Safe to call every time the app starts -- it won't wipe existing data.
    """
    Base.metadata.create_all(bind=engine)


def save_analysis(parsed_email: dict, triage_result: dict, coaching_message: str) -> dict:
    """
    Saves one complete analysis (Stage 1 + 2 + 3 combined) as a single
    row in the database. Returns the saved record as a dict.

    This is the function Phase 4 asks for: "store coaching text
    alongside triage result in DB."
    """
    session = SessionLocal()
    try:
        record = EmailAnalysis(
            sender=parsed_email.get("sender", "Unknown"),
            subject=parsed_email.get("subject", "(No Subject)"),
            department=parsed_email.get("department"),  # None for now, wire up later if you add it
            verdict=triage_result.get("verdict", "suspicious"),
            technique=triage_result.get("technique", "none_detected"),
            severity=triage_result.get("severity", "medium"),
            confidence=triage_result.get("confidence", 0.0),
            reasoning=triage_result.get("reasoning", ""),
            manual_review_required=triage_result.get("manual_review_required", False),
            coaching_message=coaching_message,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.to_dict()
    finally:
        session.close()


def get_all_analyses() -> list:
    """Returns every stored analysis, most recent first. Used by the Stage 4 dashboard later."""
    session = SessionLocal()
    try:
        records = session.query(EmailAnalysis).order_by(EmailAnalysis.analyzed_at.desc()).all()
        return [r.to_dict() for r in records]
    finally:
        session.close()


def get_analysis_by_id(analysis_id: int) -> dict:
    """Returns a single stored analysis by its ID, or None if not found."""
    session = SessionLocal()
    try:
        record = session.query(EmailAnalysis).filter(EmailAnalysis.id == analysis_id).first()
        return record.to_dict() if record else None
    finally:
        session.close()


# ---------------------------------------------------------------------
# Aggregation queries for the Stage 4 dashboard.
# These use Python-side counting on top of get_all_analyses() rather
# than raw SQL GROUP BY -- simpler to read and plenty fast at the data
# volume a student project will realistically hit (hundreds of rows,
# not millions).
# ---------------------------------------------------------------------

def get_verdict_counts() -> dict:
    """
    Returns how many emails fell into each verdict category.
    e.g. {"phishing": 12, "suspicious": 4, "legitimate": 30}
    Used for the dashboard's top-level summary cards.
    """
    records = get_all_analyses()
    counts = {"phishing": 0, "suspicious": 0, "legitimate": 0}
    for r in records:
        verdict = r.get("verdict", "suspicious")
        counts[verdict] = counts.get(verdict, 0) + 1
    return counts


def get_top_techniques(limit: int = 5) -> list:
    """
    Returns the most common phishing techniques detected, sorted by
    frequency. Excludes "none_detected" since that's not a real technique.

    Returns: [{"technique": "urgency_pressure", "count": 8}, ...]
    """
    records = get_all_analyses()
    counts = {}
    for r in records:
        technique = r.get("technique", "none_detected")
        if technique == "none_detected":
            continue
        counts[technique] = counts.get(technique, 0) + 1

    sorted_techniques = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"technique": t, "count": c} for t, c in sorted_techniques[:limit]]


def get_department_stats() -> list:
    """
    Returns phishing report counts grouped by department.
    Requires the "department" field to actually be populated when saving
    records (it's optional right now -- wire it up in your upload form
    if you want this to be meaningful).

    Returns: [{"department": "Sales", "total_reports": 10, "phishing_count": 4}, ...]
    """
    records = get_all_analyses()
    dept_data = {}

    for r in records:
        dept = r.get("department") or "Unassigned"
        if dept not in dept_data:
            dept_data[dept] = {"total_reports": 0, "phishing_count": 0}
        dept_data[dept]["total_reports"] += 1
        if r.get("verdict") == "phishing":
            dept_data[dept]["phishing_count"] += 1

    return [
        {"department": dept, **stats}
        for dept, stats in sorted(dept_data.items(), key=lambda x: x[1]["total_reports"], reverse=True)
    ]


def get_trend_over_time() -> list:
    """
    Returns phishing verdict counts grouped by date (day-level granularity).
    Useful for a line chart showing whether phishing volume is rising or
    falling over time.

    Returns: [{"date": "2026-07-20", "phishing": 3, "suspicious": 1, "legitimate": 5}, ...]
    """
    records = get_all_analyses()
    daily_data = {}

    for r in records:
        analyzed_at = r.get("analyzed_at", "")
        date_only = analyzed_at.split("T")[0] if analyzed_at else "unknown"

        if date_only not in daily_data:
            daily_data[date_only] = {"phishing": 0, "suspicious": 0, "legitimate": 0}

        verdict = r.get("verdict", "suspicious")
        daily_data[date_only][verdict] = daily_data[date_only].get(verdict, 0) + 1

    return [
        {"date": date, **counts}
        for date, counts in sorted(daily_data.items())
    ]


# Quick manual test: creates the DB, saves a dummy record, reads it back
if __name__ == "__main__":
    init_db()
    print("Database initialized at:", DB_PATH)

    dummy_parsed = {"sender": "test@example.com", "subject": "Test Email"}
    dummy_triage = {
        "verdict": "phishing",
        "technique": "urgency_pressure",
        "severity": "high",
        "confidence": 0.85,
        "reasoning": "Failed SPF/DKIM/DMARC and used urgent password-expiry language.",
        "manual_review_required": False,
    }
    dummy_coaching = "This email used urgency to pressure a quick click -- always verify with IT directly."

    saved = save_analysis(dummy_parsed, dummy_triage, dummy_coaching)
    print("\nSaved record:")
    print(saved)

    print("\nAll records in DB:")
    for r in get_all_analyses():
        print(r)
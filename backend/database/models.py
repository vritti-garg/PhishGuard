"""
models.py
---------
Defines the database schema for PhishGuard using SQLAlchemy.

One table: EmailAnalysis. Each row = one analyzed email, storing the
Stage 1 basics, Stage 2 triage verdict, and Stage 3 coaching message
together -- this is what Phase 4 asks for ("store coaching text
alongside triage result").

Kept as ONE table on purpose: for a minor project, a single flat table
is easier to query for the dashboard (Stage 4) than a normalized
multi-table design, and every field here belongs to "one analyzed email."
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class EmailAnalysis(Base):
    __tablename__ = "email_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # --- Stage 1: parsed email basics ---
    sender = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    department = Column(String, nullable=True)  # optional, for dashboard grouping later

    # --- Stage 2: triage result ---
    verdict = Column(String, nullable=False)          # phishing / suspicious / legitimate
    technique = Column(String, nullable=False)         # urgency_pressure / credential_harvesting / etc.
    severity = Column(String, nullable=False)          # low / medium / high / critical
    confidence = Column(Float, nullable=False)
    reasoning = Column(String, nullable=False)
    manual_review_required = Column(Boolean, default=False)

    # --- Stage 3: coaching message ---
    coaching_message = Column(String, nullable=True)

    # --- Metadata ---
    analyzed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convenience method -- makes it easy to return this as JSON from an API route later."""
        return {
            "id": self.id,
            "sender": self.sender,
            "subject": self.subject,
            "department": self.department,
            "verdict": self.verdict,
            "technique": self.technique,
            "severity": self.severity,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "manual_review_required": self.manual_review_required,
            "coaching_message": self.coaching_message,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
        }
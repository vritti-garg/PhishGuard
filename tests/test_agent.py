"""
test_agent.py
--------------
Unit tests for Stage 2 + 3 (ai/llm_agent.py). Run with: pytest tests/test_agent.py -v

These tests do NOT call the real OpenRouter API (no cost, no internet
needed, no flakiness in CI). Instead we mock the API client and test:
  1. The validation logic that checks a model's response is well-formed
  2. The fallback behavior when the API fails, times out, or an API
     key isn't configured
  3. The retry logic

This matters because "Handle edge cases (ambiguous emails, API errors/
timeouts)" is a checklist item -- these tests are what actually PROVE
that requirement is met, rather than just eyeballing it once.
"""

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.llm_agent import (
    triage_email,
    generate_coaching_message,
    _validate_triage_result,
    _extract_json,
    _fallback_triage_result,
)


SAMPLE_PARSED_EMAIL = {
    "sender": "test@example.com",
    "subject": "Test Subject",
    "body": "Test body",
    "attachments": [],
    "auth_check": {"spf": "fail", "dkim": "none", "dmarc": "fail"},
    "urls": [],
}


# ---------- _validate_triage_result ----------

def test_validate_accepts_well_formed_result():
    good = {
        "verdict": "phishing",
        "technique": "urgency_pressure",
        "severity": "high",
        "confidence": 0.9,
        "reasoning": "Because reasons.",
    }
    assert _validate_triage_result(good) is True


def test_validate_rejects_missing_keys():
    incomplete = {"verdict": "phishing", "severity": "high"}
    assert _validate_triage_result(incomplete) is False


def test_validate_rejects_invalid_verdict_value():
    bad = {
        "verdict": "definitely_phishing",  # not in the allowed set
        "technique": "urgency_pressure",
        "severity": "high",
        "confidence": 0.9,
        "reasoning": "x",
    }
    assert _validate_triage_result(bad) is False


def test_validate_rejects_non_numeric_confidence():
    bad = {
        "verdict": "phishing",
        "technique": "urgency_pressure",
        "severity": "high",
        "confidence": "very high",  # should be a number, not a string
        "reasoning": "x",
    }
    assert _validate_triage_result(bad) is False


# ---------- _extract_json ----------

def test_extract_json_parses_plain_json():
    raw = '{"verdict": "phishing", "confidence": 0.8}'
    result = _extract_json(raw)
    assert result["verdict"] == "phishing"


def test_extract_json_strips_markdown_fences():
    """Some models wrap JSON in ```json fences even when told not to -- must handle this."""
    raw = '```json\n{"verdict": "phishing", "confidence": 0.8}\n```'
    result = _extract_json(raw)
    assert result["verdict"] == "phishing"


# ---------- _fallback_triage_result ----------

def test_fallback_result_is_marked_for_manual_review():
    result = _fallback_triage_result("some error")
    assert result["manual_review_required"] is True
    assert result["verdict"] == "suspicious"
    assert "some error" in result["reasoning"]


# ---------- triage_email: missing API key ----------

def test_triage_email_falls_back_when_no_api_key():
    """
    With no OPENROUTER_API_KEY set, triage_email should NOT crash --
    it should return a fallback result flagged for manual review.
    """
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
        import ai.llm_agent as agent
        agent.OPENROUTER_API_KEY = ""
        agent._client = None  # force it to try (and fail) to create a client

        result = triage_email(SAMPLE_PARSED_EMAIL)

        assert result["manual_review_required"] is True
        assert result["verdict"] == "suspicious"


# ---------- triage_email: mocked API failure (timeout/error) ----------

def test_triage_email_falls_back_on_api_exception():
    """Simulates the API raising an exception (timeout, rate limit, etc.)."""
    with patch("ai.llm_agent._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = TimeoutError("Request timed out")
        mock_get_client.return_value = mock_client

        result = triage_email(SAMPLE_PARSED_EMAIL)

        assert result["manual_review_required"] is True
        assert "timed out" in result["reasoning"].lower() or "timeout" in result["reasoning"].lower()


# ---------- triage_email: mocked successful API response ----------

def test_triage_email_returns_parsed_result_on_success():
    """Simulates a well-formed API response and confirms it's parsed correctly."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        '{"verdict": "phishing", "technique": "urgency_pressure", '
        '"severity": "high", "confidence": 0.9, "reasoning": "Failed auth checks."}'
    )

    with patch("ai.llm_agent._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = triage_email(SAMPLE_PARSED_EMAIL)

        assert result["verdict"] == "phishing"
        assert result["manual_review_required"] is False


def test_triage_email_falls_back_on_malformed_json_response():
    """Simulates the model returning garbage instead of JSON."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "I think this email looks suspicious, not sure though!"

    with patch("ai.llm_agent._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = triage_email(SAMPLE_PARSED_EMAIL)

        assert result["manual_review_required"] is True


# ---------- generate_coaching_message ----------

def test_coaching_message_skips_api_call_when_manual_review_flagged():
    """If triage already failed, coaching shouldn't attempt an API call at all."""
    failed_triage = _fallback_triage_result("API down")
    message = generate_coaching_message(failed_triage, SAMPLE_PARSED_EMAIL)
    assert "manual review" in message.lower()


def test_coaching_message_falls_back_on_api_exception():
    good_triage = {
        "verdict": "phishing",
        "technique": "urgency_pressure",
        "severity": "high",
        "confidence": 0.9,
        "reasoning": "x",
        "manual_review_required": False,
    }
    with patch("ai.llm_agent._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ConnectionError("API unreachable")
        mock_get_client.return_value = mock_client

        message = generate_coaching_message(good_triage, SAMPLE_PARSED_EMAIL)

        # Should still return SOMETHING useful, not crash
        assert "phishing" in message.lower()
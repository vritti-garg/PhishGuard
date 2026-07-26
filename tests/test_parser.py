"""
test_parser.py
---------------
Unit tests for Stage 1 (parser/). Run with: pytest tests/test_parser.py -v

These tests use small in-memory/temp .eml content instead of relying on
the sample_emails/ folder, so they keep working even if someone edits
or removes those sample files later.
"""

import os
import sys
import tempfile
import pytest

# Make "backend/" importable when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parser.email_parser import analyze_email, parse_eml
from parser.header_analysis import check_auth_headers
from parser.url_extractor import extract_urls


# ---------- Helpers ----------

def write_temp_eml(content: str) -> str:
    """Writes a temp .eml file and returns its path. Caller should delete it after."""
    fd, path = tempfile.mkstemp(suffix=".eml")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


PHISHING_EML = """From: "IT Support" <it-support@fake-alerts.com>
Subject: Urgent: Verify your account
Date: Mon, 20 Jul 2026 09:15:00 +0000
Authentication-Results: mx.google.com; spf=fail smtp.mailfrom=fake-alerts.com; dkim=none; dmarc=fail
Content-Type: text/plain; charset="UTF-8"

Click here now: http://bit.ly/verify-now
"""

LEGIT_EML = """From: "Priya Sharma" <priya@company.com>
Subject: Standup notes
Date: Wed, 22 Jul 2026 11:00:00 +0000
Authentication-Results: mx.google.com; spf=pass smtp.mailfrom=company.com; dkim=pass; dmarc=pass
Content-Type: text/plain; charset="UTF-8"

No links here, just a normal update.
"""


# ---------- email_parser.py tests ----------

def test_parse_eml_extracts_basic_fields():
    path = write_temp_eml(PHISHING_EML)
    try:
        result = parse_eml(path)
        assert result["sender"] == 'IT Support <it-support@fake-alerts.com>'
        assert "Verify your account" in result["subject"]
        assert "Click here now" in result["body"]
        assert result["attachments"] == []
    finally:
        os.remove(path)


def test_analyze_email_returns_combined_structure():
    path = write_temp_eml(PHISHING_EML)
    try:
        result = analyze_email(path)
        # Confirms all four stage-1 pieces are present in one JSON object
        assert "sender" in result
        assert "subject" in result
        assert "body" in result
        assert "attachments" in result
        assert "auth_check" in result
        assert "urls" in result
    finally:
        os.remove(path)


def test_parser_does_not_crash_on_missing_file():
    """Feeding a nonexistent path should raise a clear error, not crash silently."""
    with pytest.raises(FileNotFoundError):
        parse_eml("this_file_does_not_exist.eml")


def test_parser_handles_empty_body_gracefully():
    empty_body_eml = """From: test@example.com
Subject: Empty
Date: Mon, 20 Jul 2026 09:15:00 +0000
Content-Type: text/plain; charset="UTF-8"

"""
    path = write_temp_eml(empty_body_eml)
    try:
        result = analyze_email(path)
        # Should not crash -- body may be empty string, but must exist as a key
        assert "body" in result
    finally:
        os.remove(path)


# ---------- header_analysis.py tests ----------

def test_header_analysis_detects_fail():
    headers = {
        "Authentication-Results": "mx.google.com; spf=fail smtp.mailfrom=x.com; dkim=none; dmarc=fail"
    }
    result = check_auth_headers(headers)
    assert result["spf"] == "fail"
    assert result["dkim"] == "none"
    assert result["dmarc"] == "fail"


def test_header_analysis_detects_pass():
    headers = {
        "Authentication-Results": "mx.google.com; spf=pass smtp.mailfrom=x.com; dkim=pass; dmarc=pass"
    }
    result = check_auth_headers(headers)
    assert result["spf"] == "pass"
    assert result["dkim"] == "pass"
    assert result["dmarc"] == "pass"


def test_header_analysis_handles_missing_header():
    """No Authentication-Results header at all -- should return 'unknown', not crash."""
    result = check_auth_headers({})
    assert result["spf"] == "unknown"
    assert result["dkim"] == "unknown"
    assert result["dmarc"] == "unknown"


# ---------- url_extractor.py tests ----------

def test_url_extractor_flags_shortened_url():
    urls = extract_urls("Click here: http://bit.ly/xyz123")
    assert len(urls) == 1
    assert urls[0]["is_shortened"] is True
    assert "shortened_url" in urls[0]["flags"]


def test_url_extractor_flags_ip_based_url():
    urls = extract_urls("Visit http://192.168.1.5/login")
    assert len(urls) == 1
    assert urls[0]["is_ip_address"] is True
    assert "ip_based_url" in urls[0]["flags"]


def test_url_extractor_does_not_flag_normal_url():
    urls = extract_urls("Visit https://github.com/settings/security")
    assert len(urls) == 1
    assert urls[0]["is_shortened"] is False
    assert urls[0]["is_ip_address"] is False


def test_url_extractor_handles_no_urls():
    """No URLs in the text -- should return an empty list, not crash."""
    urls = extract_urls("This email has no links at all.")
    assert urls == []


def test_url_extractor_handles_empty_string():
    urls = extract_urls("")
    assert urls == []
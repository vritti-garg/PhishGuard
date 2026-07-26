"""
email_parser.py
----------------
Stage 1 of PhishGuard: parses a raw .eml file and extracts the core
fields we need for downstream analysis (headers, body text, attachments).

This module also exposes `analyze_email()`, which combines this parser
with header_analysis.py and url_extractor.py to produce ONE structured
JSON object per email -- this JSON is what gets passed to the Gemini
triage agent in Stage 2.
"""

import json
from email import policy
from email.parser import BytesParser

# These are Stage 1 siblings -- deterministic checks, no LLM involved.
from parser.header_analysis import check_auth_headers
from parser.url_extractor import extract_urls


def parse_eml(file_path: str) -> dict:
    """
    Reads a .eml file from disk and pulls out the basic fields:
    sender, subject, plain-text body, and attachment filenames.

    Returns a dict -- NOT yet the final combined report.
    """
    with open(file_path, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    sender = msg.get("From", "Unknown")
    subject = msg.get("Subject", "(No Subject)")
    date = msg.get("Date", "Unknown")

    body = _get_plain_text_body(msg)
    attachments = _get_attachment_names(msg)

    return {
        "sender": sender,
        "subject": subject,
        "date": date,
        "body": body,
        "attachments": attachments,
        # Keep the raw headers too -- header_analysis.py needs these
        "headers": dict(msg.items()),
    }


def _get_plain_text_body(msg) -> str:
    """
    Emails can be multipart (plain text + HTML + attachments all in one).
    We only want the readable plain-text part for analysis.
    """
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments, only grab actual message text
            if content_type == "text/plain" and "attachment" not in disposition:
                try:
                    return part.get_content().strip()
                except Exception:
                    continue
        # Fallback: no plain text part found, try HTML stripped down later if needed
        return "(No plain text body found)"
    else:
        try:
            return msg.get_content().strip()
        except Exception:
            return "(Could not decode body)"


def _get_attachment_names(msg) -> list:
    """
    Returns a list of attachment filenames (if any).
    We don't process attachment CONTENTS in this project -- just flag
    that they exist, since malicious attachments are a common vector.
    """
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                attachments.append(filename)
    return attachments


def analyze_email(file_path: str) -> dict:
    """
    The main entry point for Stage 1.

    Combines:
      - parse_eml()            -> sender, subject, body, attachments
      - check_auth_headers()   -> SPF / DKIM / DMARC pass-fail
      - extract_urls()         -> URLs found in body + suspicious flags

    Returns ONE structured JSON-ready dict per email. This is what
    gets handed to the Gemini triage agent (Stage 2) next.
    """
    parsed = parse_eml(file_path)

    auth_results = check_auth_headers(parsed["headers"])
    url_results = extract_urls(parsed["body"])

    report = {
        "sender": parsed["sender"],
        "subject": parsed["subject"],
        "date": parsed["date"],
        "body": parsed["body"],
        "attachments": parsed["attachments"],
        "auth_check": auth_results,
        "urls": url_results,
    }
    return report


# Quick manual test: run this from inside backend/ (not from inside parser/) as:
# python -m parser.email_parser sample_emails/sample1.eml
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python email_parser.py <path_to_eml_file>")
        sys.exit(1)

    result = analyze_email(sys.argv[1])
    print(json.dumps(result, indent=2))
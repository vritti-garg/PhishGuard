"""
llm_agent.py
------------
Stage 2 + Stage 3: calls the Gemini API to (a) triage a parsed email
and (b) generate an employee-facing coaching message.

Design notes:
- We use Gemini's schema-constrained JSON output for triage, so we get
  back a predictable structure every time instead of parsing free text.
- All Gemini calls are wrapped with retry + timeout handling, since a
  live demo can't afford to hang or crash on a flaky API call.
- If Gemini fails entirely (timeout, API error, bad response), we return
  a clearly-marked fallback result instead of crashing the pipeline --
  a human can still review the email manually, but the app stays up.
"""

import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

from ai.prompts import build_triage_prompt, build_coaching_prompt

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# "openrouter/free" is OpenRouter's auto-router -- it picks among currently
# available free models automatically, so we're not locked to one model
# that might get rate-limited, deprecated, or removed. Confirmed working.
MODEL_NAME = "openrouter/free"

# How many times to retry a failed API call before giving up
MAX_RETRIES = 2
# Seconds to wait between retries
RETRY_DELAY = 2

_client = None


def _get_client():
    """
    Lazily creates the OpenRouter client (OpenAI-compatible) so importing
    this module doesn't fail just because an API key isn't set yet
    (useful for offline testing).
    """
    global _client
    if _client is None:
        if not OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Add it to your .env file."
            )
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
    return _client


# Allowed values -- used to sanity-check whatever comes back from the model,
# since OpenRouter's structured-output support varies by model and we can't
# always guarantee a strict schema is enforced server-side.
ALLOWED_VERDICTS = {"phishing", "suspicious", "legitimate"}
ALLOWED_TECHNIQUES = {
    "urgency_pressure",
    "credential_harvesting",
    "business_email_compromise",
    "malicious_attachment",
    "brand_impersonation",
    "none_detected",
}
ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}
REQUIRED_KEYS = {"verdict", "technique", "severity", "confidence", "reasoning"}


def _validate_triage_result(result: dict) -> bool:
    """
    Confirms the model actually returned everything we need, with values
    from the allowed sets. If this fails, we treat it the same as an API
    error and fall back rather than passing bad data downstream.
    """
    if not REQUIRED_KEYS.issubset(result.keys()):
        return False
    if result["verdict"] not in ALLOWED_VERDICTS:
        return False
    if result["technique"] not in ALLOWED_TECHNIQUES:
        return False
    if result["severity"] not in ALLOWED_SEVERITIES:
        return False
    if not isinstance(result["confidence"], (int, float)):
        return False
    return True


def _extract_json(raw_text: str) -> dict:
    """
    Some models wrap JSON in markdown code fences even when told not to.
    This strips those before parsing, so we don't fail on formatting alone.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _fallback_triage_result(error_message: str) -> dict:
    """
    Returned when Gemini can't be reached or fails repeatedly.
    Marked clearly as needing manual review -- never silently guess.
    """
    return {
        "verdict": "suspicious",
        "technique": "none_detected",
        "severity": "medium",
        "confidence": 0.0,
        "reasoning": f"AUTOMATED TRIAGE FAILED, MANUAL REVIEW NEEDED. Error: {error_message}",
        "manual_review_required": True,
    }


def triage_email(parsed_email: dict) -> dict:
    """
    Stage 2: sends the parsed email to Gemini and gets back a structured
    triage verdict. Retries on transient failures; falls back gracefully
    if Gemini is unavailable.
    """
    prompt = build_triage_prompt(parsed_email)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = _get_client()
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                # Lower temperature = more consistent, less "creative"
                # verdicts -- important for a security classification task.
                temperature=0.2,
                timeout=30,  # seconds -- don't let one call hang the demo
            )

            raw_text = response.choices[0].message.content
            result = _extract_json(raw_text)

            if not _validate_triage_result(result):
                last_error = f"Model returned incomplete/invalid fields: {result}"
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                continue

            result["manual_review_required"] = False
            return result

        except json.JSONDecodeError as e:
            last_error = f"Model returned invalid JSON: {e}"
        except Exception as e:
            # Covers API errors, timeouts, network issues, rate limits, etc.
            last_error = str(e)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    # All retries exhausted -- don't crash the pipeline, flag for a human instead
    return _fallback_triage_result(last_error)


def generate_coaching_message(triage_result: dict, parsed_email: dict) -> str:
    """
    Stage 3: generates the employee-facing coaching message based on the
    Stage 2 verdict. Plain text output, not JSON, since this is meant to
    be read directly by a person.
    """
    # Don't bother coaching on a failed triage -- nothing meaningful to explain yet
    if triage_result.get("manual_review_required"):
        return (
            "We couldn't fully analyze this email automatically. "
            "It's been flagged for manual review by the security team -- "
            "thanks for reporting it, better safe than sorry!"
        )

    prompt = build_coaching_prompt(triage_result, parsed_email)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = _get_client()
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                timeout=30,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                # Fallback message -- still useful even if Gemini is down
                return (
                    f"Verdict: {triage_result.get('verdict', 'unknown')} "
                    f"(severity: {triage_result.get('severity', 'unknown')}). "
                    "A detailed explanation couldn't be generated right now, "
                    "but this result has been logged for the security team."
                )


# Quick manual test -- requires a real OPENROUTER_API_KEY in .env to actually call the API
# Run this from inside backend/ as: python -m ai.llm_agent sample_emails/sample1_urgency_phishing.eml
if __name__ == "__main__":
    import sys
    from parser.email_parser import analyze_email

    if len(sys.argv) < 2:
        print("Usage: python llm_agent.py <path_to_eml_file>")
        sys.exit(1)

    parsed = analyze_email(sys.argv[1])
    print("--- Stage 1 parsed data ---")
    print(json.dumps(parsed, indent=2))

    triage = triage_email(parsed)
    print("\n--- Stage 2 triage result ---")
    print(json.dumps(triage, indent=2))

    coaching = generate_coaching_message(triage, parsed)
    print("\n--- Stage 3 coaching message ---")
    print(coaching)
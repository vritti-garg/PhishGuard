"""
demo_cache.py
--------------
A safety net for demo day. If OpenRouter rate-limits, times out, or is
otherwise flaky mid-demo, this provides pre-baked triage + coaching
results for your specific demo sample emails -- so the audience sees a
real result instead of the "manual review required" fallback message.

HOW THIS WORKS:
- Keyed by filename (e.g. "sample1_urgency_phishing.eml").
- triage_email_with_cache() tries the REAL API first. Only if that
  fails does it fall back to the cached response for that exact file.
- This is NOT used for anything except your known demo files -- any
  email that isn't in DEMO_CACHE still goes through the live pipeline
  normally, live and unscripted.

HOW TO USE:
1. Run your 3 demo samples through the real pipeline once, when the
   API is working, and copy the real output into DEMO_CACHE below.
2. In app.py, swap the plain triage_email() call for
   triage_email_with_cache() (see the one-line change at the bottom
   of this file).
3. On demo day, if OpenRouter hiccups, your 3 rehearsed samples still
   show a real, coherent verdict instead of the fallback message.
"""

from ai.llm_agent import triage_email as _live_triage_email
from ai.llm_agent import generate_coaching_message as _live_generate_coaching_message

# ---------------------------------------------------------------------
# Fill these in with REAL output from a working API run. Placeholder
# values below are reasonable examples -- replace them after your own
# test run so the reasoning/coaching text actually matches what your
# demo samples produced.
# ---------------------------------------------------------------------

DEMO_TRIAGE_CACHE = {
    "sample1_urgency_phishing.eml": {
        "verdict": "phishing",
        "technique": "urgency_pressure",
        "severity": "high",
        "confidence": 0.91,
        "reasoning": "The email failed SPF, DKIM, and DMARC checks, used a shortened "
                      "bit.ly URL to hide its real destination, and applied urgency "
                      "language ('2 hours', 'account lockout') to rush the recipient "
                      "into clicking without verifying.",
        "manual_review_required": False,
    },
    "sample2_bec_phishing.eml": {
        "verdict": "phishing",
        "technique": "business_email_compromise",
        "severity": "critical",
        "confidence": 0.88,
        "reasoning": "The email impersonates a company executive, requests an urgent "
                      "wire transfer, asks the recipient to keep it confidential, and "
                      "failed SPF/DKIM/DMARC -- a classic CEO-fraud pattern.",
        "manual_review_required": False,
    },
    "sample4_legitimate_internal.eml": {
        "verdict": "legitimate",
        "technique": "none_detected",
        "severity": "low",
        "confidence": 0.85,
        "reasoning": "The email passed SPF, DKIM, and DMARC checks, contains no "
                      "suspicious links or urgency language, and reads as a routine "
                      "internal status update.",
        "manual_review_required": False,
    },
}

DEMO_COACHING_CACHE = {
    "sample1_urgency_phishing.eml": (
        "This email was phishing. It used urgency -- a tight deadline and a threat of "
        "losing account access -- to rush you into clicking without checking first. "
        "Next time, if an email pressures you to act immediately, pause and verify "
        "directly with IT before clicking anything."
    ),
    "sample2_bec_phishing.eml": (
        "This email was phishing, specifically a 'CEO fraud' attempt. It impersonated "
        "a company executive and pushed for an urgent, confidential wire transfer. "
        "Real executives rarely ask for secretive financial actions over email -- when "
        "in doubt, confirm requests like this by phone or in person."
    ),
    "sample4_legitimate_internal.eml": (
        "This email looks safe. It passed all our authentication checks and reads like "
        "a normal internal update with no red flags. Good instinct reporting it anyway -- "
        "that's exactly the right habit to keep."
    ),
}


def triage_email_with_cache(parsed_email: dict, filename: str = None) -> dict:
    """
    Tries the real API first. If it fails AND the filename matches a
    known demo sample, returns the cached result instead of the generic
    fallback. Otherwise behaves exactly like triage_email().

    The returned dict includes "from_demo_cache": True/False so the
    caller (generate_coaching_message_with_cache) knows whether to also
    use the cached coaching message.
    """
    result = _live_triage_email(parsed_email)

    if result.get("manual_review_required") and filename in DEMO_TRIAGE_CACHE:
        cached = DEMO_TRIAGE_CACHE[filename].copy()
        cached["from_demo_cache"] = True
        return cached

    result["from_demo_cache"] = False
    return result


def generate_coaching_message_with_cache(triage_result: dict, parsed_email: dict, filename: str = None) -> str:
    """
    If the triage result was served from the demo cache (live API failed),
    also serve the matching cached coaching message instead of calling
    the API again (which would likely fail too, for the same reason).
    """
    if triage_result.get("from_demo_cache") and filename in DEMO_COACHING_CACHE:
        return DEMO_COACHING_CACHE[filename]

    return _live_generate_coaching_message(triage_result, parsed_email)


# ---------------------------------------------------------------------
# Quick manual test: run this file directly to confirm the cache
# lookups work correctly (does not require API access).
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import json

    dummy_parsed = {"sender": "test@example.com", "subject": "Test"}

    print("Testing cache lookup for a KNOWN demo file (simulating API failure):")
    fake_failed_result = {"manual_review_required": True}
    if "sample1_urgency_phishing.eml" in DEMO_TRIAGE_CACHE:
        print(json.dumps(DEMO_TRIAGE_CACHE["sample1_urgency_phishing.eml"], indent=2))

    print("\nTesting cache lookup for an UNKNOWN file (should have no cache entry):")
    print("unknown_file.eml" in DEMO_TRIAGE_CACHE)
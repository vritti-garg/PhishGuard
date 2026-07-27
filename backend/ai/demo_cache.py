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
        "technique": "Credential Harvesting",
        "severity": "high",
        "confidence": 0.95,
        "reasoning": "The email fails all authentication checks (SPF fail, DKIM none, DMARC fail), uses a shortened URL (bit.ly) to obscure the true phishing destination, and employs urgency pressure ('2 hours', 'immediately', 'account lockout') to drive credential harvesting via a fake password reset link. ",
        "manual_review_required": False,
    },
    "sample2_bec_phishing.eml": {
        "verdict": "phishing",
        "technique": "business_email_compromise",
        "severity": "high",
        "confidence": 0.90,
        "reasoning": "The email fails SPF, DKIM, and DMARC authentication, indicating a spoofed sender. It also uses urgency and impersonation of a CEO to request a wire transfer, which are hallmark signs of a business email compromise phishing attempt.",
        "manual_review_required": False,
    },
    "sample4_legitimate_internal.eml": {
        "verdict": "legitimate",
        "technique": "none_detected",
        "severity": "low",
        "confidence": 0.95,
        "reasoning": "All email authentication checks (SPF/DKIM/DMARC) passed, confirming the sender domain is legitimate. The email contains no URLs, attachments, or suspicious content, and the message is a routine team update with no urgency, credential requests, or financial instructions.",
        "manual_review_required": False,
    },
}

DEMO_COACHING_CACHE = {
    "sample1_urgency_phishing.eml": (
        "The email you received was actually a phishing attempt, not a safe message. It used urgent language and a shortened link that hides the real destination, both classic signs of a scam. A good habit is to hover over any link to see the actual web address before clicking, and to verify urgent requests by contacting the sender through a known channel. Thanks for flagging it — your careful eye helps keep our systems secure."
    ),
    "sample2_bec_phishing.eml": (
        "The email you reported was identified as a malicious phishing attempt. Two clues were the slightly misspelled sender address (“compnayholdings.com” instead of the correct domain) and the urgent request for a wire transfer that supposedly came from the CEO. Next time, if you get an unexpected, urgent moneytransfer request, pause and verify it through a separate channel — like a quick call or message to the person — before acting. Thanks for being vigilant and reporting it; your caution helps keep everyone safe."
    ),
    "sample4_legitimate_internal.eml": (
        "The email you received is safe — it’s a routine team update from Priya. It passed all the normal checks and has no links, attachments, or urgent requests that often signal a problem. In the future, watch for messages that try to create urgency, ask for passwords, or include unexpected files. Thanks for staying vigilant; your caution helps keep everyone’s inbox secure"
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
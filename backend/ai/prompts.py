"""
prompts.py
----------
Holds the prompt templates used by the Gemini agent (llm_agent.py).

Keeping prompts separate from the API-calling logic makes them easy to
iterate on without touching the request/response handling code.

IMPORTANT: All the deterministic checks (SPF/DKIM/DMARC, URL flags,
attachment names) are already done in Stage 1 (parser/). We hand those
RESULTS to Gemini as facts -- we never ask Gemini to re-derive them.
Gemini's job is reasoning and judgment on TOP of those facts: what
technique is being used, how severe is it, and how confident is the
verdict.
"""

import json


def build_triage_prompt(parsed_email: dict) -> str:
    """
    Builds the Stage 2 triage prompt.

    Input: the structured JSON dict produced by parser/email_parser.py
           (analyze_email()).
    Output (from Gemini): verdict, severity, technique, confidence, reasoning.

    We inject the Stage 1 facts directly into the prompt so Gemini reasons
    over ground-truth data instead of guessing at things Python already knows.
    """

    # Keep the injected data compact -- no need to dump raw headers etc.
    email_summary = {
        "sender": parsed_email.get("sender"),
        "subject": parsed_email.get("subject"),
        "body": parsed_email.get("body"),
        "attachments": parsed_email.get("attachments"),
        "spf": parsed_email.get("auth_check", {}).get("spf"),
        "dkim": parsed_email.get("auth_check", {}).get("dkim"),
        "dmarc": parsed_email.get("auth_check", {}).get("dmarc"),
        "urls": parsed_email.get("urls"),
    }

    prompt = f"""
You are a cybersecurity SOC analyst assistant. You are given a parsed
email along with pre-computed, DETERMINISTIC security facts (SPF/DKIM/DMARC
results and URL red-flags). These facts are already verified -- do not
re-evaluate or contradict them. Your job is to REASON on top of them.

EMAIL DATA (JSON):
{json.dumps(email_summary, indent=2)}

Analyze this email and decide:

1. verdict: one of "phishing", "suspicious", or "legitimate"
   - Use "suspicious" when signals are mixed or you are not fully confident
     either way -- do NOT force a hard phishing/legitimate call when the
     evidence is genuinely ambiguous.

2. technique: the primary social engineering or attack technique used.
   Choose the closest match from: "urgency_pressure", "credential_harvesting",
   "business_email_compromise", "malicious_attachment", "brand_impersonation",
   "none_detected". If multiple apply, pick the most dominant one.

3. severity: one of "low", "medium", "high", "critical"
   - Base this on potential impact (e.g. a BEC wire-transfer attempt or
     malicious attachment is higher severity than a generic promo email).

4. confidence: a number between 0 and 1 representing how confident you are
   in this verdict overall.

5. reasoning: a short (2-3 sentence) explanation of WHY you reached this
   verdict, referencing the specific facts that drove your decision
   (e.g. failed SPF, shortened URL, urgency language, etc.).

Respond ONLY with a JSON object matching this exact structure -- no extra
text, no markdown formatting, no code fences:

{{
  "verdict": "...",
  "technique": "...",
  "severity": "...",
  "confidence": 0.0,
  "reasoning": "..."
}}
"""
    return prompt.strip()


def build_coaching_prompt(triage_result: dict, parsed_email: dict) -> str:
    """
    Builds the Stage 3 coaching prompt.

    Input: the Stage 2 triage verdict + the original parsed email.
    Output (from Gemini): a short, friendly, non-condescending explanation
    written FOR THE EMPLOYEE who reported/received the email.

    This is what turns PhishGuard from a detection tool into a training tool.
    """

    prompt = f"""
You are writing a short, friendly message to an employee who reported or
received an email that our system just analyzed. Your goal is to help them
learn to recognize similar emails in the future -- NOT to make them feel
foolish or lectured.

ANALYSIS RESULT:
- Verdict: {triage_result.get('verdict')}
- Technique used: {triage_result.get('technique')}
- Severity: {triage_result.get('severity')}
- Reasoning: {triage_result.get('reasoning')}

ORIGINAL EMAIL SUBJECT: {parsed_email.get('subject')}
ORIGINAL SENDER: {parsed_email.get('sender')}

Write a short message (3-5 sentences) that:
1. Tells them plainly whether the email was safe, suspicious, or malicious.
2. Points out the ONE OR TWO specific things that gave it away (in plain,
   non-technical language -- avoid jargon like "SPF" or "DMARC").
3. Gives one practical tip for spotting this type of email next time.
4. Uses an encouraging, respectful tone -- assume they were being cautious
   by reporting it, even if it turns out to be legitimate.

Respond with ONLY the message text -- no JSON, no headers, no extra formatting.
"""
    return prompt.strip()
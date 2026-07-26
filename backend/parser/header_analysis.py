"""
header_analysis.py
-------------------
Checks the email's authentication headers (SPF, DKIM, DMARC) to see
whether the sending server passed or failed these checks.

Most modern mail servers (Gmail, Outlook, etc.) stamp this info into
the "Authentication-Results" header when they deliver a message.
We are NOT re-running SPF/DKIM lookups ourselves -- we're reading
the verdict the receiving mail server already computed and stamped
into the header. This is simpler, deterministic, and doesn't need
any live DNS/network calls.
"""

import re


def check_auth_headers(headers: dict) -> dict:
    """
    Takes the full header dict from the parsed email and extracts
    SPF / DKIM / DMARC results.

    Returns a dict like:
    {
        "spf": "pass" | "fail" | "none" | "unknown",
        "dkim": "pass" | "fail" | "none" | "unknown",
        "dmarc": "pass" | "fail" | "none" | "unknown",
        "raw_authentication_results": "<original header string>"
    }
    """
    auth_header = headers.get("Authentication-Results", "")

    spf_result = _extract_result(auth_header, "spf")
    dkim_result = _extract_result(auth_header, "dkim")
    dmarc_result = _extract_result(auth_header, "dmarc")

    # Some mail clients use a separate "Received-SPF" header instead
    if spf_result == "unknown":
        received_spf = headers.get("Received-SPF", "")
        spf_result = _extract_result(received_spf, "spf", fallback_from_start=True)

    return {
        "spf": spf_result,
        "dkim": dkim_result,
        "dmarc": dmarc_result,
        "raw_authentication_results": auth_header if auth_header else "Not present",
    }


def _extract_result(header_text: str, check_type: str, fallback_from_start: bool = False) -> str:
    """
    Looks for patterns like "spf=pass", "dkim=fail", "dmarc=none"
    inside a header string, case-insensitively.

    fallback_from_start: some "Received-SPF" headers start directly
    with the result (e.g. "Pass (...)") instead of "spf=pass".
    """
    if not header_text:
        return "unknown"

    pattern = rf"{check_type}=(\w+)"
    match = re.search(pattern, header_text, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    if fallback_from_start:
        first_word = header_text.strip().split()[0].lower() if header_text.strip() else ""
        if first_word in ("pass", "fail", "none", "neutral", "softfail"):
            return first_word

    return "unknown"


# Quick manual test with a fake header set
if __name__ == "__main__":
    sample_headers = {
        "Authentication-Results": "mx.google.com; spf=fail smtp.mailfrom=fake.com; "
                                   "dkim=none; dmarc=fail (p=REJECT)",
    }
    print(check_auth_headers(sample_headers))
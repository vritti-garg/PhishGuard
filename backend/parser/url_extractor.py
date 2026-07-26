"""
url_extractor.py
-----------------
Pulls all URLs out of the email body text and applies simple,
deterministic heuristics to flag suspicious ones.

These are all rule-based checks (no LLM here) -- the goal is to hand
Gemini a pre-flagged, structured list of URLs, so it can REASON about
intent rather than re-doing basic string matching itself.
"""

import re
from urllib.parse import urlparse

# Common URL-shortening services -- shortened links are a classic
# phishing tactic because they hide the real destination.
KNOWN_SHORTENERS = [
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly",
    "is.gd", "buff.ly", "rebrand.ly", "cutt.ly", "shorturl.at",
]

# A crude but effective heuristic: URLs pointing at a raw IP address
# instead of a domain name are a common red flag.
IP_ADDRESS_PATTERN = re.compile(r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")

URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')


def extract_urls(body_text: str) -> list:
    """
    Finds every URL in the given text and returns a list of dicts,
    each describing the URL and why it might (or might not) be
    suspicious.

    Returns:
    [
        {
            "url": "http://bit.ly/xyz",
            "domain": "bit.ly",
            "is_shortened": True,
            "is_ip_address": False,
            "flags": ["shortened_url"]
        },
        ...
    ]
    """
    if not body_text:
        return []

    found_urls = URL_PATTERN.findall(body_text)
    results = []

    for url in found_urls:
        domain = _get_domain(url)
        is_shortened = domain in KNOWN_SHORTENERS
        is_ip = bool(IP_ADDRESS_PATTERN.match(url))

        flags = []
        if is_shortened:
            flags.append("shortened_url")
        if is_ip:
            flags.append("ip_based_url")
        if not is_ip and _has_excessive_subdomains(domain):
            flags.append("excessive_subdomains")
        if _uses_lookalike_chars(domain):
            flags.append("suspicious_characters_in_domain")

        results.append({
            "url": url,
            "domain": domain,
            "is_shortened": is_shortened,
            "is_ip_address": is_ip,
            "flags": flags,
        })

    return results


def _get_domain(url: str) -> str:
    """Extracts just the domain (netloc) from a full URL."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return "unknown"


def _has_excessive_subdomains(domain: str, threshold: int = 3) -> bool:
    """
    Flags domains with an unusually high number of subdomains,
    e.g. "login.secure.verify.fake-bank.com" -- a common phishing
    trick to make a fake domain look more "official."
    """
    if domain == "unknown":
        return False
    return domain.count(".") >= threshold


def _uses_lookalike_chars(domain: str) -> bool:
    """
    Very basic check for common lookalike substitutions
    (e.g. "paypa1.com" instead of "paypal.com").
    This is intentionally simple -- a starting point, not exhaustive.
    """
    suspicious_patterns = ["1", "0", "-secure", "-verify", "-login"]
    return any(pattern in domain for pattern in suspicious_patterns)


# Quick manual test
if __name__ == "__main__":
    sample_text = """
    Please verify your account here: http://bit.ly/fake123
    Or visit our official site: http://192.168.1.5/login
    Also check: http://paypa1-secure.com/verify
    """
    for result in extract_urls(sample_text):
        print(result)
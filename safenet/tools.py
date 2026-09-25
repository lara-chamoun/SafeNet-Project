import re
from urllib.parse import urlparse

from .models import CyberSafetyState, SituationAnalysis

import json
import os

from langchain_openai import ChatOpenAI

URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>'\"]+", re.IGNORECASE)


def extract_domains(text: str) -> list[str]:
    """Extract domains without visiting them; suspicious URLs are never opened."""
    domains: list[str] = []
    for raw in URL_RE.findall(text):
        normalized = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
        domain = (urlparse(normalized).hostname or "").lower()
        if domain and domain not in domains:
            domains.append(domain)
    return domains


def match_scam_patterns(text: str) -> list[str]:
    patterns = {
        "urgent pressure": ["urgent", "immediately", "act now", "suspended", "expires"],
        "credential request": ["password", "verification code", "otp", "pin"],
        "payment request": ["send money", "gift card", "wire transfer", "crypto"],
        "prize lure": ["won a prize", "winner", "claim your prize"],
        "malware/scareware language": ["virus", "infected", "download", "attachment"],
    }
    lowered = text.lower()
    return [label for label, phrases in patterns.items() if any(p in lowered for p in phrases)]


def score_risk(
    analysis: SituationAnalysis, pattern_matches: list[str], parsed_domains: list[str]
) -> tuple[float, list[str]]:
    """Transparent deterministic risk tool. Score is capped at 1.0."""
    score = 0
    reasons: list[str] = []

    rules = [
        (analysis.contains_link, 10, "The message contains a link."),
        (analysis.urgency_language, 10, "It uses pressure or urgent language."),
        (analysis.clicked_link, 15, "The link was opened."),
        (analysis.downloaded_file, 25, "A file was downloaded."),
        (analysis.shared_password, 35, "A password was shared."),
        (analysis.shared_otp, 40, "A one-time verification code was shared."),
        (analysis.unknown_login, 30, "An unrecognized login was reported."),
    ]
    for condition, points, explanation in rules:
        if condition:
            score += points
            reasons.append(explanation)

    if parsed_domains:
        score += 10
        reasons.append("The message supplies an external web address.")

    if len(pattern_matches) >= 2:
        score += 10
        reasons.append("Several common scam patterns appear together.")

    return min(score / 100.0, 1.0), reasons



def recovery_playbook(analysis: SituationAnalysis) -> list[str]:
    actions = ["Disconnect from the suspicious page or message and stop interacting with it."]
    if analysis.shared_password:
        actions += [
            "Change the affected password from a trusted device and do not reuse the old password.",
            "Sign out of other sessions and enable two-factor authentication.",
        ]
    if analysis.shared_otp:
        actions.append("Contact the affected bank or service immediately through its official channel.")
    if analysis.downloaded_file:
        actions += [
            "Do not open the downloaded file; quarantine or delete it.",
            "Run the device's trusted security scan and seek professional help if behavior is unusual.",
        ]
    if analysis.unknown_login:
        actions += [
            "Review recent account activity and remove unknown devices or sessions.",
            "Check recovery email, phone number, and forwarding settings for unauthorized changes.",
        ]
    actions.append("Preserve screenshots and relevant messages in case support needs evidence.")
    return list(dict.fromkeys(actions))

import re
from typing import Any

# Phase 4 baseline only. These are risk indicators, not proof that a claim is
# misinformation or that a person/group is hateful. Later phases can replace
# this scorer with trained or externally evaluated models.
MISINFO_PATTERNS = [
    r"\b(?:breaking|urgent|shocking)\b.*\b(?:confirmed|proof|truth)\b",
    r"\b(?:100%|guaranteed|definitely|without doubt)\b",
    r"\b(?:they don't want you to know|secret cure|miracle cure)\b",
    r"\b(?:fake news|hoax|cover[- ]?up)\b",
    r"\b(?:vaccines?\s+(?:cause|give)\s+\w+)\b",
]

HATE_PATTERNS = [
    r"\b(?:kill|exterminate|wipe out|burn)\b\s+(?:all|every|those)\b",
    r"\b(?:dehuman|vermin|animals?)\b\s+(?:all|those|them)?\b",
    r"\b(?:go back to|you people)\b",
]

MISINFO_TERMS = {"false", "fabricated", "disinformation", "misinformation", "conspiracy"}
HATE_TERMS = {"hate", "racist", "tribe", "ethnic", "genocide", "threat"}


def _term_score(text: str, terms: set[str]) -> float:
    words = set(re.findall(r"[a-zA-Z']+", text.lower()))
    return min(45.0, len(words.intersection(terms)) * 12.0)


def _pattern_score(text: str, patterns: list[str]) -> float:
    return min(60.0, sum(20.0 for pattern in patterns if re.search(pattern, text, re.I)))


def analyze_post(text: str, public_metrics: dict[str, Any] | None = None) -> dict[str, float]:
    public_metrics = public_metrics or {}
    misinformation = min(100.0, _term_score(text, MISINFO_TERMS) + _pattern_score(text, MISINFO_PATTERNS))
    hate = min(100.0, _term_score(text, HATE_TERMS) + _pattern_score(text, HATE_PATTERNS))

    likes = float(public_metrics.get("like_count", 0) or 0)
    replies = float(public_metrics.get("reply_count", 0) or 0)
    reposts = float(public_metrics.get("retweet_count", 0) or 0)
    quotes = float(public_metrics.get("quote_count", 0) or 0)
    reach = likes + replies + reposts + quotes
    spread_velocity = min(100.0, (reposts * 2 + quotes * 2 + replies) ** 0.5 * 10)

    priority = min(100.0, max(misinformation, hate) * 0.65 + spread_velocity * 0.35)
    return {
        "misinformation_risk": round(misinformation, 2),
        "hate_speech_risk": round(hate, 2),
        "spread_velocity": round(spread_velocity, 2),
        "reach": round(reach, 2),
        "early_warning_priority": round(priority, 2),
    }

"""Deterministic extraction of candidate trial-design assumptions from protocol text.

The extractor is intentionally transparent and non-generative. It proposes fields for
human review; it does not infer unstated assumptions or make clinical recommendations.
"""
from __future__ import annotations

import re
from typing import Any

PATTERNS: dict[str, re.Pattern[str]] = {
    "target_enrollment": re.compile(r"(?:target\s+)?(?:enrollment|enrolment|sample\s+size)\s*(?:(?:of|:|=|is)\s*)?(\d{2,6})\s*(?:participants|patients|subjects)?", re.IGNORECASE),
    "dropout_rate_percent": re.compile(r"(?:dropout|withdrawal|attrition)\s+(?:rate\s+)?(?:(?:of|is)\s+)?(\d{1,2}(?:\.\d+)?)\s*%", re.IGNORECASE),
    "follow_up_months": re.compile(r"follow[- ]up\s+(?:of\s+)?(\d{1,3})\s*months?", re.IGNORECASE),
    "randomization_ratio": re.compile(r"randomi[sz]ed\s+(\d+)\s*:\s*(\d+)", re.IGNORECASE),
    "primary_endpoint": re.compile(r"primary\s+endpoint\s*(?:is|:)?\s*([^.;\n]{4,160})", re.IGNORECASE),
}


def extract_assumptions(protocol_text: str) -> dict[str, Any]:
    """Extract candidate parameters with exact evidence snippets and review status."""
    candidates: dict[str, Any] = {}
    for field, pattern in PATTERNS.items():
        match = pattern.search(protocol_text)
        if match:
            snippet_start = max(0, match.start() - 80)
            snippet_end = min(len(protocol_text), match.end() + 80)
            raw = match.group(0).strip()
            value: Any = raw
            groups = match.groups()
            if field == "target_enrollment":
                value = int(groups[0])
            elif field in {"dropout_rate_percent", "follow_up_months"}:
                value = float(groups[0]) if "." in groups[0] else int(groups[0])
            elif field == "randomization_ratio":
                value = f"{groups[0]}:{groups[1]}"
            elif field == "primary_endpoint":
                value = groups[0].strip()
            candidates[field] = {
                "candidate_value": value,
                "source_excerpt": protocol_text[snippet_start:snippet_end].strip(),
                "source_characters": [match.start(), match.end()],
                "review_status": "requires_human_review",
                "confidence": "not_calibrated",
            }
    return {
        "extraction_method": "deterministic_regex_v1",
        "fields": candidates,
        "notice": "Candidate fields only. Verify against the source protocol; absence is not evidence that an assumption is zero or unknown.",
    }

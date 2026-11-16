"""Human-in-the-loop orchestration for protocol extraction and simulation setup."""
from __future__ import annotations

from typing import Any

from .protocol_extract import extract_assumptions


def prepare_review_packet(protocol_text: str) -> dict[str, Any]:
    """Return extracted assumptions and explicit approval gates.

    The function does not execute simulation or turn text into approved parameters.
    A statistician must verify and approve each proposed value.
    """
    extraction = extract_assumptions(protocol_text)
    return {
        "protocol_assumptions": extraction,
        "approval_gate": {
            "required_before_simulation": True,
            "required_reviewers": ["qualified biostatistician or trial statistician"],
            "approved_parameters": {},
            "status": "awaiting_human_review",
        },
        "prohibited_automations": [
            "Do not infer unsupported values.",
            "Do not run confirmatory design calculations without approved assumptions.",
            "Do not treat AI or regex extraction as protocol interpretation.",
        ],
    }

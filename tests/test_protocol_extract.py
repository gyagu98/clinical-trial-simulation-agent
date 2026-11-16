from trial_sim.agent.protocol_extract import extract_assumptions
from trial_sim.agent.workflow import prepare_review_packet


def test_extracts_candidate_values_with_evidence():
    text = "The target enrollment is 240 participants. The dropout rate of 15% is expected. Follow-up of 18 months. Randomized 2:1. The primary endpoint is change from baseline in biomarker X."
    result = extract_assumptions(text)
    fields = result["fields"]
    assert fields["target_enrollment"]["candidate_value"] == 240
    assert fields["dropout_rate_percent"]["candidate_value"] == 15
    assert fields["follow_up_months"]["candidate_value"] == 18
    assert fields["randomization_ratio"]["candidate_value"] == "2:1"
    assert fields["primary_endpoint"]["review_status"] == "requires_human_review"
    assert fields["target_enrollment"]["source_excerpt"]


def test_no_guessing_when_text_has_no_values():
    result = extract_assumptions("This study evaluates a new treatment.")
    assert result["fields"] == {}


def test_review_packet_blocks_unreviewed_execution():
    packet = prepare_review_packet("Target enrollment 200 participants.")
    assert packet["approval_gate"]["required_before_simulation"] is True
    assert packet["approval_gate"]["status"] == "awaiting_human_review"
    assert packet["approval_gate"]["approved_parameters"] == {}

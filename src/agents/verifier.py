"""Person C — Verifier Agent.

Run on every CaseOutput before it's written to output/. Cases that fail this
are the ones that risk the hard-gate 0 (README.md #8) — don't skip this step
even under time pressure.
"""

from __future__ import annotations

from src.shared.config import (
    CASE_STATUSES,
    MAX_ACTIONS,
    MAX_EVIDENCE_IDS,
    MAX_IDS_PER_ENTITY_SET,
    MAX_RESPONSIBLE_PARTIES,
    MAX_ROOT_CAUSES,
    PRIMARY_ISSUES,
    RESOLUTION_ACTIONS,
)
from src.shared.data_loader import DataStore
from src.shared.evidence import validate_evidence_ids
from src.shared.interfaces import CaseOutput


def verify_case(output: CaseOutput, store: DataStore) -> list[str]:
    """Returns a list of problem descriptions. Empty list = passed."""
    problems: list[str] = []

    if output["assessment"]["primary_issue"] not in PRIMARY_ISSUES:
        problems.append(f"invalid primary_issue: {output['assessment']['primary_issue']!r}")

    if output["assessment"]["case_status"] not in CASE_STATUSES:
        problems.append(f"invalid case_status: {output['assessment']['case_status']!r}")

    confidence = output["assessment"]["confidence"]
    if not (0.0 <= confidence <= 1.0):
        problems.append(f"confidence out of [0,1]: {confidence}")

    for field_name in ("order_ids", "item_ids", "seller_ids", "payment_ids"):
        ids = output["affected_entities"][field_name]
        if len(ids) > MAX_IDS_PER_ENTITY_SET:
            problems.append(f"{field_name} exceeds cap of {MAX_IDS_PER_ENTITY_SET}: {len(ids)}")

    if len(output["evidence_ids"]) > MAX_EVIDENCE_IDS:
        problems.append(f"evidence_ids exceeds cap of {MAX_EVIDENCE_IDS}")

    if len(output["root_cause_analysis"]["ranked_causes"]) > MAX_ROOT_CAUSES:
        problems.append(f"ranked_causes exceeds cap of {MAX_ROOT_CAUSES}")

    if len(output["root_cause_analysis"]["responsible_parties"]) > MAX_RESPONSIBLE_PARTIES:
        problems.append(f"responsible_parties exceeds cap of {MAX_RESPONSIBLE_PARTIES}")

    if len(output["resolution_actions"]) > MAX_ACTIONS:
        problems.append(f"resolution_actions exceeds cap of {MAX_ACTIONS}")

    for action in output["resolution_actions"]:
        if action not in RESOLUTION_ACTIONS:
            problems.append(f"unknown resolution_action: {action!r}")

    invalid_evidence = validate_evidence_ids(output["evidence_ids"], store)
    if invalid_evidence:
        problems.append(f"evidence IDs not found in CSV data: {invalid_evidence}")

    # TODO(Person C): also check
    # - money rounding: every *_brl value has <= 2 decimal places
    # - if affected_entities.item_ids is empty, financial_resolution item_total_brl/
    #   freight_total_brl must be 0.0 (README.md #6)

    return problems

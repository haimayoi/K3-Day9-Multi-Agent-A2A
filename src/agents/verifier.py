"""Person C - final hard-gate verifier for every generated case output."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from src.shared.config import (
    CASE_STATUSES,
    LOGISTICS_PARTY_ID,
    MAX_ACTIONS,
    MAX_EVIDENCE_IDS,
    MAX_IDS_PER_ENTITY_SET,
    MAX_RESPONSIBLE_PARTIES,
    MAX_ROOT_CAUSES,
    PARTY_TYPES,
    PLATFORM_PARTY_ID,
    PRIMARY_ISSUES,
    RESOLUTION_ACTIONS,
    ROOT_CAUSE_CODES,
)
from src.shared.data_loader import DataStore
from src.shared.evidence import validate_evidence_ids
from src.shared.interfaces import CaseOutput
from src.shared.money import round_brl


_ISSUE_POLICY = {
    "canceled_order_paid": ("ORDER_CANCELED_AFTER_PAYMENT", "issue_full_refund"),
    "unavailable_order_paid": ("ORDER_UNAVAILABLE_AFTER_PAYMENT", "issue_full_refund"),
    "late_delivery_seller": ("SELLER_HANDOFF_AFTER_LIMIT", "refund_freight"),
    "late_delivery_logistics": ("CARRIER_DELIVERED_AFTER_ESTIMATE", "refund_freight"),
    "valid_split_payment": ("MULTIPLE_PAYMENTS_RECONCILED", "explain_valid_split_payment"),
    "unsupported_late_claim": ("DELIVERY_WITHIN_ESTIMATE", "reject_late_refund"),
}

_TOP_LEVEL_KEYS = {
    "case_id",
    "assessment",
    "affected_entities",
    "root_cause_analysis",
    "evidence_ids",
    "financial_resolution",
    "resolution_actions",
}
_SECTION_KEYS = {
    "assessment": {"primary_issue", "case_status", "confidence"},
    "affected_entities": {"order_ids", "item_ids", "seller_ids", "payment_ids"},
    "root_cause_analysis": {"ranked_causes", "responsible_parties"},
    "financial_resolution": {
        "currency",
        "item_total_brl",
        "freight_total_brl",
        "payment_total_brl",
        "recommended_refund_brl",
    },
}
_CASE_ID_PATTERN = re.compile(r"^EC_\d{3}$")


def _shape_problems(output) -> list[str]:
    problems: list[str] = []
    if not isinstance(output, dict):
        return ["output must be a JSON object"]

    actual_top_keys = set(output)
    if actual_top_keys != _TOP_LEVEL_KEYS:
        problems.append(
            f"top-level keys mismatch: missing={sorted(_TOP_LEVEL_KEYS - actual_top_keys)}, "
            f"extra={sorted(actual_top_keys - _TOP_LEVEL_KEYS)}"
        )

    for section_name, expected_keys in _SECTION_KEYS.items():
        section = output.get(section_name)
        if not isinstance(section, dict):
            problems.append(f"{section_name} must be an object")
            continue
        actual_keys = set(section)
        if actual_keys != expected_keys:
            problems.append(
                f"{section_name} keys mismatch: missing={sorted(expected_keys - actual_keys)}, "
                f"extra={sorted(actual_keys - expected_keys)}"
            )

    list_paths = (
        ("evidence_ids", output.get("evidence_ids")),
        ("resolution_actions", output.get("resolution_actions")),
    )
    for field_name, value in list_paths:
        if not isinstance(value, list):
            problems.append(f"{field_name} must be a list")
        elif any(not isinstance(item, str) for item in value):
            problems.append(f"{field_name} must contain only strings")

    affected = output.get("affected_entities")
    if isinstance(affected, dict):
        for field_name in ("order_ids", "item_ids", "seller_ids", "payment_ids"):
            if not isinstance(affected.get(field_name), list):
                problems.append(f"affected_entities.{field_name} must be a list")
            elif any(not isinstance(item, str) for item in affected[field_name]):
                problems.append(f"affected_entities.{field_name} must contain only strings")

    root = output.get("root_cause_analysis")
    if isinstance(root, dict):
        for field_name in ("ranked_causes", "responsible_parties"):
            if not isinstance(root.get(field_name), list):
                problems.append(f"root_cause_analysis.{field_name} must be a list")
            elif any(not isinstance(item, dict) for item in root[field_name]):
                problems.append(f"root_cause_analysis.{field_name} must contain only objects")

    return problems


def _as_decimal(value) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() else None


def _has_at_most_two_decimal_places(value) -> bool:
    amount = _as_decimal(value)
    if amount is None:
        return False
    try:
        return amount == amount.quantize(Decimal("0.01"))
    except InvalidOperation:
        return False


def _validate_entity_ids(output: CaseOutput, store: DataStore) -> list[str]:
    problems: list[str] = []
    entities = output["affected_entities"]
    order_ids = entities["order_ids"]
    order_id_set = set(order_ids)

    if not order_ids:
        problems.append("order_ids must contain the claimed order")

    linked_seller_ids: set[str] = set()
    for order_id in order_ids:
        if not isinstance(order_id, str) or not store.order_exists(order_id):
            problems.append(f"order_id not found in CSV data: {order_id!r}")
            continue
        linked_seller_ids.update(str(value) for value in store.get_items(order_id)["seller_id"])

    for item_id in entities["item_ids"]:
        if not isinstance(item_id, str) or item_id.count(":") != 1:
            problems.append(f"invalid item_id format: {item_id!r}")
            continue
        order_id, order_item_id = item_id.split(":", 1)
        if order_id not in order_id_set or not store.item_exists(order_id, order_item_id):
            problems.append(f"item_id not linked to affected order: {item_id!r}")

    for payment_id in entities["payment_ids"]:
        if not isinstance(payment_id, str) or payment_id.count(":") != 1:
            problems.append(f"invalid payment_id format: {payment_id!r}")
            continue
        order_id, payment_sequential = payment_id.split(":", 1)
        if order_id not in order_id_set or not store.payment_exists(order_id, payment_sequential):
            problems.append(f"payment_id not linked to affected order: {payment_id!r}")

    for seller_id in entities["seller_ids"]:
        if not isinstance(seller_id, str) or not store.seller_exists(seller_id):
            problems.append(f"seller_id not found in CSV data: {seller_id!r}")
        elif seller_id not in linked_seller_ids:
            problems.append(f"seller_id not linked to affected order: {seller_id!r}")

    for field_name in ("order_ids", "item_ids", "seller_ids", "payment_ids"):
        ids = entities[field_name]
        if len(ids) > MAX_IDS_PER_ENTITY_SET:
            problems.append(f"{field_name} exceeds cap of {MAX_IDS_PER_ENTITY_SET}: {len(ids)}")
        if len(ids) != len(set(ids)):
            problems.append(f"{field_name} contains duplicates")

    return problems


def _validate_responsible_parties(output: CaseOutput, primary_issue: str, store: DataStore) -> list[str]:
    problems: list[str] = []
    parties = output["root_cause_analysis"]["responsible_parties"]
    seller_ids = set(output["affected_entities"]["seller_ids"])

    if len(parties) > MAX_RESPONSIBLE_PARTIES:
        problems.append(f"responsible_parties exceeds cap of {MAX_RESPONSIBLE_PARTIES}")

    for party in parties:
        if not isinstance(party, dict) or set(party) != {"party_type", "party_id"}:
            problems.append(f"invalid responsible party shape: {party!r}")
            continue
        party_type = party["party_type"]
        party_id = party["party_id"]
        if party_type not in PARTY_TYPES:
            problems.append(f"unknown party_type: {party_type!r}")
        if party_type == "seller" and (
            party_id not in seller_ids or not store.seller_exists(party_id)
        ):
            problems.append(f"responsible seller is not an affected seller: {party_id!r}")

    if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
        expected = [{"party_type": "platform", "party_id": PLATFORM_PARTY_ID}]
        if parties != expected:
            problems.append(f"responsible_parties must be {expected!r}")
    elif primary_issue == "late_delivery_logistics":
        expected = [{"party_type": "logistics_provider", "party_id": LOGISTICS_PARTY_ID}]
        if parties != expected:
            problems.append(f"responsible_parties must be {expected!r}")
    elif primary_issue == "late_delivery_seller":
        if not parties or any(party.get("party_type") != "seller" for party in parties if isinstance(party, dict)):
            problems.append("late_delivery_seller requires at least one responsible seller")
    elif parties:
        problems.append(f"{primary_issue} must not have responsible parties")

    return problems


def _validate_financial_resolution(output: CaseOutput, primary_issue: str) -> list[str]:
    problems: list[str] = []
    financial = output["financial_resolution"]
    if financial["currency"] != "BRL":
        problems.append(f"currency must be 'BRL': {financial['currency']!r}")

    money_fields = (
        "item_total_brl",
        "freight_total_brl",
        "payment_total_brl",
        "recommended_refund_brl",
    )
    for field_name in money_fields:
        if not _has_at_most_two_decimal_places(financial[field_name]):
            problems.append(f"{field_name} must be a finite amount rounded to two decimal places")

    if any(_as_decimal(financial[field_name]) is None for field_name in money_fields):
        return problems

    if not output["affected_entities"]["item_ids"]:
        if financial["item_total_brl"] != 0.0:
            problems.append("item_total_brl must be 0.0 when item_ids is empty")
        if financial["freight_total_brl"] != 0.0:
            problems.append("freight_total_brl must be 0.0 when item_ids is empty")

    if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
        expected_refund = round_brl(financial["payment_total_brl"])
    elif primary_issue in ("late_delivery_seller", "late_delivery_logistics"):
        expected_refund = round_brl(financial["freight_total_brl"])
    else:
        expected_refund = 0.0
    if financial["recommended_refund_brl"] != expected_refund:
        problems.append(
            f"recommended_refund_brl must be {expected_refund} for {primary_issue!r}"
        )

    expected_status = "action_required" if expected_refund > 0 else "no_action"
    if output["assessment"]["case_status"] != expected_status:
        problems.append(f"case_status must be {expected_status!r} for refund {expected_refund}")

    return problems


def verify_case(output: CaseOutput, store: DataStore) -> list[str]:
    """Return all detected contract problems; an empty list means pass."""
    problems = _shape_problems(output)
    if problems:
        return problems

    case_id = output["case_id"]
    if not isinstance(case_id, str) or not _CASE_ID_PATTERN.fullmatch(case_id):
        problems.append(f"invalid case_id: {case_id!r}")

    assessment = output["assessment"]
    primary_issue = assessment["primary_issue"]
    if primary_issue not in PRIMARY_ISSUES:
        problems.append(f"invalid primary_issue: {primary_issue!r}")
        return problems
    if assessment["case_status"] not in CASE_STATUSES:
        problems.append(f"invalid case_status: {assessment['case_status']!r}")

    confidence = _as_decimal(assessment["confidence"])
    if confidence is None or not (Decimal("0") <= confidence <= Decimal("1")):
        problems.append(f"confidence out of [0,1]: {assessment['confidence']!r}")

    problems.extend(_validate_entity_ids(output, store))

    root = output["root_cause_analysis"]
    ranked_causes = root["ranked_causes"]
    if len(ranked_causes) > MAX_ROOT_CAUSES:
        problems.append(f"ranked_causes exceeds cap of {MAX_ROOT_CAUSES}")
    for expected_rank, cause in enumerate(ranked_causes, start=1):
        if not isinstance(cause, dict) or set(cause) != {"cause_code", "rank"}:
            problems.append(f"invalid ranked cause shape: {cause!r}")
            continue
        if cause["cause_code"] not in ROOT_CAUSE_CODES:
            problems.append(f"unknown root cause: {cause['cause_code']!r}")
        if cause["rank"] != expected_rank:
            problems.append(f"root cause rank must be {expected_rank}: {cause!r}")

    expected_cause, expected_action = _ISSUE_POLICY[primary_issue]
    actual_causes = [
        cause.get("cause_code") for cause in ranked_causes if isinstance(cause, dict)
    ]
    if actual_causes != [expected_cause]:
        problems.append(
            f"root causes for {primary_issue!r} must be [{expected_cause!r}]: {actual_causes}"
        )

    actions = output["resolution_actions"]
    if len(actions) > MAX_ACTIONS:
        problems.append(f"resolution_actions exceeds cap of {MAX_ACTIONS}")
    if any(action not in RESOLUTION_ACTIONS for action in actions):
        problems.append(f"unknown resolution action in {actions!r}")
    if actions != [expected_action]:
        problems.append(f"resolution_actions must be [{expected_action!r}]")

    problems.extend(_validate_responsible_parties(output, primary_issue, store))

    evidence_ids = output["evidence_ids"]
    if len(evidence_ids) > MAX_EVIDENCE_IDS:
        problems.append(f"evidence_ids exceeds cap of {MAX_EVIDENCE_IDS}")
    if len(evidence_ids) != len(set(evidence_ids)):
        problems.append("evidence_ids contains duplicates")
    invalid_evidence = validate_evidence_ids(evidence_ids, store)
    if invalid_evidence:
        problems.append(f"evidence IDs not found in CSV data: {invalid_evidence}")

    expected_policy_evidence = f"policy:{expected_cause}"
    policy_evidence_ids = [eid for eid in evidence_ids if eid.startswith("policy:")]
    if policy_evidence_ids != [expected_policy_evidence]:
        problems.append(
            f"policy evidence for {primary_issue!r} must be [{expected_policy_evidence!r}]"
        )

    entities = output["affected_entities"]
    allowed_data_evidence = {
        *(f"order:{value}" for value in entities["order_ids"]),
        *(f"item:{value}" for value in entities["item_ids"]),
        *(f"payment:{value}" for value in entities["payment_ids"]),
        *(f"seller:{value}" for value in entities["seller_ids"]),
    }
    unrelated_evidence = [
        eid for eid in evidence_ids if not eid.startswith("policy:") and eid not in allowed_data_evidence
    ]
    if unrelated_evidence:
        problems.append(f"evidence IDs outside affected entities: {unrelated_evidence}")

    problems.extend(_validate_financial_resolution(output, primary_issue))
    return problems

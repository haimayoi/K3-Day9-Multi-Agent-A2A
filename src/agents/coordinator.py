"""Person C — Coordinator + Policy Agent.

coordinate_case() receives one parsed input case, delegates domain analysis to
the Fulfillment and Payment agents, then hands both results to resolve_case().
resolve_case() applies EC_POLICY_V1 and returns a CaseOutput per README.md #6.

Apply the priority table top-to-bottom, EXACTLY in this order — do not
reorder or short-circuit differently (README.md #4):
  1. canceled_order_paid     (fulfillment.order_status == "canceled" and payment_total > 0)
  2. unavailable_order_paid  (fulfillment.order_status == "unavailable" and payment_total > 0)
  3. late_delivery_seller    (fulfillment.delivered_late and fulfillment.seller_late)
  4. late_delivery_logistics (fulfillment.delivered_late and not fulfillment.seller_late)
  5. valid_split_payment     (payment.is_split_payment and payment.reconciled)
  6. unsupported_late_claim  (not fulfillment.delivered_late and payment.reconciled)
"""

from __future__ import annotations

from src.agents.fulfillment_agent import analyze_fulfillment
from src.agents.payment_agent import analyze_payment
from src.shared.config import (
    LOGISTICS_PARTY_ID,
    MAX_ACTIONS,
    MAX_EVIDENCE_IDS,
    MAX_IDS_PER_ENTITY_SET,
    MAX_RESPONSIBLE_PARTIES,
    MAX_ROOT_CAUSES,
    PLATFORM_PARTY_ID,
)
from src.shared.evidence import item_evidence, order_evidence, payment_evidence, policy_evidence, seller_evidence
from src.shared.interfaces import CaseOutput, FulfillmentResult, PaymentResult
from src.shared.llm_client import call_llm
from src.shared.money import round_brl


_CONFIDENCE_SYSTEM_PROMPT = (
    "You are a policy compliance reviewer for an e-commerce dispute resolution "
    "system. You are given the primary_issue a deterministic rules engine already "
    "decided, plus the facts that led to it. Respond with ONLY a single number "
    "between 0 and 1 (e.g. 0.93) representing how strongly the given facts support "
    "that classification. No words, no explanation, just the number."
)


def _llm_confidence(
    primary_issue: str,
    fallback: float,
    fulfillment: FulfillmentResult,
    payment: PaymentResult,
) -> float:
    """Confidence score via gpt-4o-mini, with a deterministic fallback.

    The rules engine already decided primary_issue with certainty — this call
    never changes that decision, it only scores how clean the supporting facts
    are. Any failure (no API key, network, unparseable/out-of-range response)
    falls back to `fallback` so a flaky API call never breaks a graded run.
    """
    user_prompt = (
        f"primary_issue: {primary_issue}\n"
        f"order_status: {fulfillment['order_status']}\n"
        f"delivered_late: {fulfillment['delivered_late']}\n"
        f"seller_late: {fulfillment['seller_late']}\n"
        f"is_split_payment: {payment['is_split_payment']}\n"
        f"payment_reconciled: {payment['reconciled']}\n"
    )
    try:
        raw = call_llm(_CONFIDENCE_SYSTEM_PROMPT, user_prompt, temperature=0.0)
        value = float(raw.strip())
        if 0.0 <= value <= 1.0:
            return round(value, 2)
    except Exception:
        pass
    return fallback


_ISSUE_TO_CAUSE = {
    'canceled_order_paid': 'ORDER_CANCELED_AFTER_PAYMENT',
    'unavailable_order_paid': 'ORDER_UNAVAILABLE_AFTER_PAYMENT',
    'late_delivery_seller': 'SELLER_HANDOFF_AFTER_LIMIT',
    'late_delivery_logistics': 'CARRIER_DELIVERED_AFTER_ESTIMATE',
    'valid_split_payment': 'MULTIPLE_PAYMENTS_RECONCILED',
    'unsupported_late_claim': 'DELIVERY_WITHIN_ESTIMATE',
}

_ISSUE_TO_ACTION = {
    'canceled_order_paid': 'issue_full_refund',
    'unavailable_order_paid': 'issue_full_refund',
    'late_delivery_seller': 'refund_freight',
    'late_delivery_logistics': 'refund_freight',
    'valid_split_payment': 'explain_valid_split_payment',
    'unsupported_late_claim': 'reject_late_refund',
}


def _cap(values, limit: int):
    return values[:limit]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _strip_evidence_prefix(value: str, prefix: str) -> str:
    marker = f'{prefix}:'
    return value[len(marker):] if value.startswith(marker) else value


def _item_evidence_from_entity(item_id: str) -> str | None:
    parts = _strip_evidence_prefix(item_id, 'item').split(':')
    return item_evidence(parts[0], parts[1]) if len(parts) == 2 else None


def _payment_evidence_from_entity(payment_id: str) -> str | None:
    parts = _strip_evidence_prefix(payment_id, 'payment').split(':')
    return payment_evidence(parts[0], parts[1]) if len(parts) == 2 else None


def _choose_primary_issue(fulfillment: FulfillmentResult, payment: PaymentResult) -> str:
    if fulfillment['order_status'] == 'canceled' and payment['payment_total_brl'] > 0:
        return 'canceled_order_paid'
    if fulfillment['order_status'] == 'unavailable' and payment['payment_total_brl'] > 0:
        return 'unavailable_order_paid'
    if fulfillment['delivered_late'] and fulfillment['seller_late']:
        return 'late_delivery_seller'
    if fulfillment['delivered_late'] and not fulfillment['seller_late']:
        return 'late_delivery_logistics'
    if payment['is_split_payment'] and payment['reconciled']:
        return 'valid_split_payment'
    return 'unsupported_late_claim'


def _responsible_parties(primary_issue: str, fulfillment: FulfillmentResult) -> list[dict[str, str]]:
    if primary_issue in ('canceled_order_paid', 'unavailable_order_paid'):
        return [{'party_type': 'platform', 'party_id': PLATFORM_PARTY_ID}]
    if primary_issue == 'late_delivery_logistics':
        return [{'party_type': 'logistics_provider', 'party_id': LOGISTICS_PARTY_ID}]
    if primary_issue == 'late_delivery_seller':
        seller_ids = _unique(fulfillment['late_seller_ids'] or fulfillment['seller_ids'])
        return [{'party_type': 'seller', 'party_id': seller_id} for seller_id in seller_ids]
    return []


def _ranked_causes(primary_issue: str, fulfillment: FulfillmentResult, payment: PaymentResult):
    cause_codes = [_ISSUE_TO_CAUSE[primary_issue]]
    cause_codes.extend(fulfillment['candidate_root_causes'])
    if payment['is_split_payment'] and payment['reconciled']:
        cause_codes.append('MULTIPLE_PAYMENTS_RECONCILED')
    return [
        {'cause_code': cause_code, 'rank': rank}
        for rank, cause_code in enumerate(_cap(_unique(cause_codes), MAX_ROOT_CAUSES), start=1)
    ]


def _build_evidence_ids(
    order_ids: list[str],
    item_ids: list[str],
    seller_ids: list[str],
    payment_ids: list[str],
    ranked_causes,
    fulfillment: FulfillmentResult,
    primary_issue: str,
) -> list[str]:
    evidence_ids: list[str] = []
    if fulfillment['order_exists']:
        evidence_ids.extend(order_evidence(entity_order_id) for entity_order_id in order_ids)

    evidence_ids.append(policy_evidence(str(ranked_causes[0]['cause_code'])))

    for payment_id in payment_ids:
        evidence_id = _payment_evidence_from_entity(payment_id)
        if evidence_id is not None:
            evidence_ids.append(evidence_id)

    evidence_seller_ids = seller_ids
    if primary_issue == 'late_delivery_seller':
        evidence_seller_ids = _unique(fulfillment['late_seller_ids'] or seller_ids)
    for seller_id in _cap(evidence_seller_ids, MAX_IDS_PER_ENTITY_SET):
        evidence_ids.append(seller_evidence(seller_id))

    for item_id in item_ids:
        evidence_id = _item_evidence_from_entity(item_id)
        if evidence_id is not None:
            evidence_ids.append(evidence_id)

    for ranked_cause in ranked_causes[1:]:
        evidence_ids.append(policy_evidence(str(ranked_cause['cause_code'])))

    return _cap(_unique(evidence_ids), MAX_EVIDENCE_IDS)


def _recommended_refund(primary_issue: str, payment: PaymentResult) -> float:
    if primary_issue in ('canceled_order_paid', 'unavailable_order_paid'):
        return round_brl(payment['payment_total_brl'])
    if primary_issue in ('late_delivery_seller', 'late_delivery_logistics'):
        return round_brl(payment['freight_total_brl'])
    return 0.0


def _affected_entity_sets(order_id: str, fulfillment: FulfillmentResult, payment: PaymentResult):
    order_ids = _cap(_unique(fulfillment['order_ids'] or [order_id]), MAX_IDS_PER_ENTITY_SET)
    item_ids = _cap(_unique(fulfillment['item_ids']), MAX_IDS_PER_ENTITY_SET)
    seller_ids = _cap(_unique(fulfillment['seller_ids']), MAX_IDS_PER_ENTITY_SET)
    payment_ids = _cap(
        _unique([_strip_evidence_prefix(payment_id, 'payment') for payment_id in payment['payment_ids']]),
        MAX_IDS_PER_ENTITY_SET,
    )
    return order_ids, item_ids, seller_ids, payment_ids


def _build_case_output(
    case: dict,
    fulfillment: FulfillmentResult,
    payment: PaymentResult,
    order_id: str,
) -> CaseOutput:
    primary_issue = _choose_primary_issue(fulfillment, payment)
    refund_brl = _recommended_refund(primary_issue, payment)
    order_ids, item_ids, seller_ids, payment_ids = _affected_entity_sets(order_id, fulfillment, payment)
    ranked_causes = _ranked_causes(primary_issue, fulfillment, payment)
    responsible_parties = _cap(_responsible_parties(primary_issue, fulfillment), MAX_RESPONSIBLE_PARTIES)
    evidence_ids = _build_evidence_ids(
        order_ids, item_ids, seller_ids, payment_ids, ranked_causes, fulfillment, primary_issue
    )
    fallback_confidence = 0.95 if refund_brl > 0 else 0.9
    confidence = _llm_confidence(primary_issue, fallback_confidence, fulfillment, payment)

    return {
        'case_id': case['case_id'],
        'assessment': {
            'primary_issue': primary_issue,
            'case_status': 'action_required' if refund_brl > 0 else 'no_action',
            'confidence': confidence,
        },
        'affected_entities': {
            'order_ids': order_ids,
            'item_ids': item_ids,
            'seller_ids': seller_ids,
            'payment_ids': payment_ids,
        },
        'root_cause_analysis': {
            'ranked_causes': ranked_causes,
            'responsible_parties': responsible_parties,
        },
        'evidence_ids': evidence_ids,
        'financial_resolution': {
            'currency': 'BRL',
            'item_total_brl': round_brl(payment['item_total_brl']),
            'freight_total_brl': round_brl(payment['freight_total_brl']),
            'payment_total_brl': round_brl(payment['payment_total_brl']),
            'recommended_refund_brl': refund_brl,
        },
        'resolution_actions': _cap([_ISSUE_TO_ACTION[primary_issue]], MAX_ACTIONS),
    }


def resolve_case(
    case: dict,
    fulfillment: FulfillmentResult,
    payment: PaymentResult,
) -> CaseOutput:
    order_id = case["customer_request"]["claimed_order_id"]

    return _build_case_output(case, fulfillment, payment, order_id)


def coordinate_case(
    case: dict,
) -> tuple[CaseOutput, FulfillmentResult, PaymentResult]:
    """Delegate a case to domain agents and return every handoff for tracing."""
    order_id = case["customer_request"]["claimed_order_id"]
    fulfillment = analyze_fulfillment(order_id)
    payment = analyze_payment(order_id)
    output = resolve_case(case, fulfillment, payment)
    return output, fulfillment, payment

"""Person C — Coordinator + Policy Agent.

resolve_case() takes one input case dict (already parsed from input/EC_*.json)
and the two upstream results, and returns a CaseOutput per README.md #6.

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

from src.shared.config import (
    LOGISTICS_PARTY_ID,
    PLATFORM_PARTY_ID,
)
from src.shared.evidence import order_evidence, policy_evidence
from src.shared.interfaces import CaseOutput, FulfillmentResult, PaymentResult


def resolve_case(
    case: dict,
    fulfillment: FulfillmentResult,
    payment: PaymentResult,
) -> CaseOutput:
    order_id = case["customer_request"]["claimed_order_id"]

    # TODO(Person C):
    # 1. Walk the priority table above, pick the first matching primary_issue.
    # 2. Map to root_cause_code (src/shared/config.ROOT_CAUSE_CODES) and
    #    responsible party (platform/PLATFORM_PARTY_ID, seller/<seller_id>,
    #    logistics_provider/LOGISTICS_PARTY_ID, or none).
    # 3. recommended_refund_brl: full payment_total for canceled/unavailable,
    #    freight_total for late_delivery_*, else 0.
    # 4. case_status: "action_required" if refund > 0 else "no_action".
    # 5. resolution_actions: map 1-1 from src/shared/config.RESOLUTION_ACTIONS.
    # 6. Build evidence_ids using src/shared/evidence.py helpers only — never
    #    hand-format a string. Cap at MAX_EVIDENCE_IDS (10).
    # 7. Cap every ID list at MAX_IDS_PER_ENTITY_SET (5), ranked_causes at
    #    MAX_ROOT_CAUSES (3), responsible_parties at MAX_RESPONSIBLE_PARTIES (3),
    #    resolution_actions at MAX_ACTIONS (5).
    # 8. confidence: your own call (LLM or heuristic) but keep in [0, 1].

    raise NotImplementedError("Person C: implement resolve_case()")

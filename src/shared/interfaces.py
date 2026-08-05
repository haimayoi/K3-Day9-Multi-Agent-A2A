"""Contracts between agents (agreed at kickoff, 2026-08-05).

Person A implements analyze_fulfillment() in agents/fulfillment_agent.py
Person B implements analyze_payment() in agents/payment_agent.py
Person C (coordinator/policy) only ever imports these two functions + the
TypedDicts below — never reaches into A's or B's internals directly.

Do not change these shapes without telling the other two people; the
coordinator is built against exactly this contract.
"""

from __future__ import annotations

from typing import List, Optional, TypedDict


class FulfillmentResult(TypedDict):
    order_exists: bool
    order_status: str  # raw order_status from orders.csv, e.g. "delivered", "canceled", "unavailable"

    order_ids: List[str]
    item_ids: List[str]  # formatted "<order_id>:<order_item_id>"
    seller_ids: List[str]

    estimated_date: Optional[str]  # order_estimated_delivery_date
    actual_carrier_date: Optional[str]  # order_delivered_carrier_date
    actual_customer_date: Optional[str]  # order_delivered_customer_date

    delivered_late: bool  # actual_customer_date > estimated_date
    seller_late: bool  # any item's order_delivered_carrier_date > that item's shipping_limit_date
    late_seller_ids: List[str]  # sellers whose handoff missed shipping_limit_date

    # Root cause codes this agent found evidence for, already ranked by the
    # README.md #4 priority order (canceled/unavailable > seller-late >
    # logistics-late > delivery-within-estimate). Coordinator does NOT
    # re-derive these, only picks the first one relevant to the case.
    candidate_root_causes: List[str]


class PaymentResult(TypedDict):
    payment_ids: List[str]  # formatted "<order_id>:<payment_sequential>"
    payment_row_count: int

    item_total_brl: float
    freight_total_brl: float
    payment_total_brl: float

    is_split_payment: bool  # payment_row_count >= 2
    reconciled: bool  # |payment_total - (item_total+freight_total)| <= 0.10 BRL


class ResponsibleParty(TypedDict):
    party_type: str  # one of config.PARTY_TYPES
    party_id: str


class RankedCause(TypedDict):
    cause_code: str
    rank: int


class AffectedEntities(TypedDict):
    order_ids: List[str]
    item_ids: List[str]
    seller_ids: List[str]
    payment_ids: List[str]


class FinancialResolution(TypedDict):
    currency: str  # always "BRL"
    item_total_brl: float
    freight_total_brl: float
    payment_total_brl: float
    recommended_refund_brl: float


class Assessment(TypedDict):
    primary_issue: str  # one of config.PRIMARY_ISSUES
    case_status: str  # one of config.CASE_STATUSES
    confidence: float  # in [0, 1]


class RootCauseAnalysis(TypedDict):
    ranked_causes: List[RankedCause]
    responsible_parties: List[ResponsibleParty]


class CaseOutput(TypedDict):
    """Exact shape of each output/EC_*.json file (README.md #6)."""

    case_id: str
    assessment: Assessment
    affected_entities: AffectedEntities
    root_cause_analysis: RootCauseAnalysis
    evidence_ids: List[str]
    financial_resolution: FinancialResolution
    resolution_actions: List[str]


# --- Stubs — replace the NotImplementedError body, keep the signature -----


def analyze_fulfillment(order_id: str) -> FulfillmentResult:
    """Person A: order status, seller handoff timing, delivery timing."""
    raise NotImplementedError("Person A: implement in agents/fulfillment_agent.py")


def analyze_payment(order_id: str) -> PaymentResult:
    """Person B: payment vs item+freight reconciliation."""
    raise NotImplementedError("Person B: implement in agents/payment_agent.py")

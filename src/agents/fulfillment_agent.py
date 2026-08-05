"""Person A — Order & Seller Agent + Delivery Agent.

Fill in analyze_fulfillment() below. Signature and return shape (FulfillmentResult)
are fixed by src/shared/interfaces.py — don't change them without telling B and C.

Rules to implement, in priority order (README.md #4):
  1. canceled_order_paid:    order_status == "canceled"   and total payment > 0
  2. unavailable_order_paid: order_status == "unavailable" and total payment > 0
  3. late_delivery_seller:    delivered after estimated_date AND that seller's
                               item(s) had order_delivered_carrier_date > shipping_limit_date
  4. late_delivery_logistics: delivered after estimated_date AND carrier was NOT late
                               against shipping_limit_date
  5. (feeds unsupported_late_claim): delivered no later than estimated_date

Note: total payment > 0 needs PaymentResult — either call analyze_payment()
yourself here, or leave that check to the Coordinator (Person C). Agree with
B which one of you owns it so it isn't computed twice inconsistently.
"""

from __future__ import annotations

from src.shared.data_loader import get_data_store
from src.shared.evidence import item_evidence, order_evidence, seller_evidence
from src.shared.interfaces import FulfillmentResult


def analyze_fulfillment(order_id: str) -> FulfillmentResult:
    store = get_data_store()

    order = store.get_order(order_id)
    if order is None:
        return FulfillmentResult(
            order_exists=False,
            order_status="",
            order_ids=[],
            item_ids=[],
            seller_ids=[],
            estimated_date=None,
            actual_carrier_date=None,
            actual_customer_date=None,
            delivered_late=False,
            seller_late=False,
            late_seller_ids=[],
            candidate_root_causes=[],
        )

    items = store.get_items(order_id)

    # TODO(Person A): implement the actual date/status comparisons.
    # - order["order_status"], order["order_estimated_delivery_date"],
    #   order["order_delivered_carrier_date"], order["order_delivered_customer_date"]
    # - items["shipping_limit_date"], items["order_delivered_carrier_date"] via order,
    #   items["seller_id"], items["order_item_id"]
    # - Build item_ids with item_evidence()/seller_ids via seller_evidence() as needed
    #   for the final evidence_ids list (Coordinator will also call these directly).

    raise NotImplementedError("Person A: implement analyze_fulfillment()")

"""Person A — Order & Seller Agent + Delivery Agent.

Signature and return shape (FulfillmentResult) are fixed by
src/shared/interfaces.py — don't change them without telling B and C.

Rules implemented, in priority order (README.md #4):
  1. canceled_order_paid:     order_status == "canceled"    (payment>0 check done by Coordinator)
  2. unavailable_order_paid:  order_status == "unavailable" (payment>0 check done by Coordinator)
  3. late_delivery_seller:    delivered after estimated_date AND that seller's
                               item(s) had order_delivered_carrier_date > shipping_limit_date
  4. late_delivery_logistics: delivered after estimated_date AND carrier was NOT late
                               against shipping_limit_date
  5. (feeds unsupported_late_claim): delivered no later than estimated_date

Note: canceled/unavailable candidates are only confirmed as the actual
primary_issue once the Coordinator checks payment_total > 0 (PaymentResult,
owned by Person B) — this agent reports the order-status fact, not the final
verdict.

Dates are compared as raw ISO strings straight from the CSV (README.md #2:
"không cần chuyển múi giờ"), which works because they're all formatted
"YYYY-MM-DD HH:MM:SS" — lexicographic string comparison equals chronological
comparison for that format.
"""

from __future__ import annotations

from src.shared.data_loader import get_data_store
from src.shared.interfaces import FulfillmentResult


def _clean_date(value) -> str | None:
    """CSV gives NaN (float) for missing dates; normalize to None, else str."""
    if isinstance(value, str):
        return value
    return None


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

    order_status = str(order["order_status"])
    estimated_date = _clean_date(order["order_estimated_delivery_date"])
    actual_carrier_date = _clean_date(order["order_delivered_carrier_date"])
    actual_customer_date = _clean_date(order["order_delivered_customer_date"])

    # affected_entities format (README.md #6) — bare IDs, no "kind:" prefix.
    # Evidence IDs with the "kind:" prefix are built later by the Coordinator
    # using src/shared/evidence.py, from these same raw order_id/item_id/seller_id.
    order_ids = [order_id]
    if len(items):
        item_ids = [f"{order_id}:{item_id}" for item_id in items["order_item_id"]]
        seller_ids = sorted(set(items["seller_id"]))
    else:
        item_ids = []
        seller_ids = []

    # --- delivery timing -------------------------------------------------
    delivered_late = (
        actual_customer_date is not None
        and estimated_date is not None
        and actual_customer_date > estimated_date
    )

    # --- seller handoff timing (per item, per README.md #4 multi-item rule) ---
    late_seller_ids: list[str] = []
    if len(items) and actual_carrier_date is not None:
        for _, item in items.iterrows():
            shipping_limit = _clean_date(item["shipping_limit_date"])
            if shipping_limit is not None and actual_carrier_date > shipping_limit:
                seller_id = item["seller_id"]
                if seller_id not in late_seller_ids:
                    late_seller_ids.append(seller_id)

    seller_late = len(late_seller_ids) > 0

    # --- candidate root causes, ranked by README.md #4 priority order -----
    candidate_root_causes: list[str] = []
    if order_status == "canceled":
        candidate_root_causes.append("ORDER_CANCELED_AFTER_PAYMENT")
    elif order_status == "unavailable":
        candidate_root_causes.append("ORDER_UNAVAILABLE_AFTER_PAYMENT")
    elif delivered_late and seller_late:
        candidate_root_causes.append("SELLER_HANDOFF_AFTER_LIMIT")
    elif delivered_late and not seller_late:
        candidate_root_causes.append("CARRIER_DELIVERED_AFTER_ESTIMATE")
    elif actual_customer_date is not None and not delivered_late:
        candidate_root_causes.append("DELIVERY_WITHIN_ESTIMATE")

    return FulfillmentResult(
        order_exists=True,
        order_status=order_status,
        order_ids=order_ids,
        item_ids=item_ids,
        seller_ids=seller_ids,
        estimated_date=estimated_date,
        actual_carrier_date=actual_carrier_date,
        actual_customer_date=actual_customer_date,
        delivered_late=delivered_late,
        seller_late=seller_late,
        late_seller_ids=late_seller_ids,
        candidate_root_causes=candidate_root_causes,
    )

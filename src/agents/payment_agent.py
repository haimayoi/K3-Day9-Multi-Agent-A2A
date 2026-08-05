"""Person B — Payment Agent.

Fill in analyze_payment() below. Signature and return shape (PaymentResult)
are fixed by src/shared/interfaces.py — don't change them without telling A and C.

Rule to implement (README.md #4):
  valid_split_payment: >= 2 payment rows AND
    |sum(payment_value) - (sum(item price) + sum(item freight_value))| <= 0.10 BRL

Reminder from README.md #2: payment_value is the amount of EACH payment row,
not per-installment — do not divide by payment_installments.

If order has no item rows: item_total_brl = 0.0, freight_total_brl = 0.0
(README.md #6). Don't truncate payment_ids to the output's 5-ID cap here —
that's the Coordinator/Verifier's job, this agent reports everything it found.
"""

from __future__ import annotations

from src.shared.data_loader import get_data_store
from src.shared.evidence import payment_evidence
from src.shared.interfaces import PaymentResult
from src.shared.money import round_brl, sum_brl, within_tolerance
from src.shared.config import MONEY_RECONCILIATION_TOLERANCE_BRL


def analyze_payment(order_id: str) -> PaymentResult:
    store = get_data_store()

    payments = store.get_payments(order_id)
    items = store.get_items(order_id)

    # TODO(Person B):
    # - item_total_brl = sum_brl(items["price"]) if any items, else 0.0
    # - freight_total_brl = sum_brl(items["freight_value"]) if any items, else 0.0
    # - payment_total_brl = sum_brl(payments["payment_value"])
    # - payment_ids: [payment_evidence(order_id, seq) for seq in payments["payment_sequential"]]
    # - reconciled: within_tolerance(payment_total_brl, item_total_brl + freight_total_brl,
    #                                 MONEY_RECONCILIATION_TOLERANCE_BRL)
    # - is_split_payment: len(payments) >= 2
    # Round every total with round_brl() before returning, per README.md #4 ("làm tròn 2 chữ số").

    raise NotImplementedError("Person B: implement analyze_payment()")

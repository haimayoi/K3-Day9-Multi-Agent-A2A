"""Evidence ID builders + validators (README.md #5).

Everyone must build evidence IDs through these functions — an evidence ID
built by hand-formatting a string is exactly how you end up with a false
positive (typo, wrong field order, ID that doesn't exist in the CSVs).
"""

from __future__ import annotations

from .config import ROOT_CAUSE_CODES
from .data_loader import DataStore


def order_evidence(order_id: str) -> str:
    return f"order:{order_id}"


def item_evidence(order_id: str, order_item_id) -> str:
    return f"item:{order_id}:{order_item_id}"


def payment_evidence(order_id: str, payment_sequential) -> str:
    return f"payment:{order_id}:{payment_sequential}"


def seller_evidence(seller_id: str) -> str:
    return f"seller:{seller_id}"


def policy_evidence(root_cause_code: str) -> str:
    if root_cause_code not in ROOT_CAUSE_CODES:
        raise ValueError(f"Unknown root cause code: {root_cause_code!r}")
    return f"policy:{root_cause_code}"


def validate_evidence_ids(evidence_ids: list[str], store: DataStore) -> list[str]:
    """Return the subset of evidence_ids that do NOT resolve against the CSV data.

    Verifier Agent should call this on every case and reject/flag any non-empty
    result before writing output — those are false positives per README.md #5.
    """
    invalid: list[str] = []
    for eid in evidence_ids:
        parts = eid.split(":")
        kind = parts[0] if parts else ""

        if kind == "order" and len(parts) == 2:
            if not store.order_exists(parts[1]):
                invalid.append(eid)
        elif kind == "item" and len(parts) == 3:
            if not store.item_exists(parts[1], parts[2]):
                invalid.append(eid)
        elif kind == "payment" and len(parts) == 3:
            if not store.payment_exists(parts[1], parts[2]):
                invalid.append(eid)
        elif kind == "seller" and len(parts) == 2:
            if not store.seller_exists(parts[1]):
                invalid.append(eid)
        elif kind == "policy" and len(parts) == 2:
            if parts[1] not in ROOT_CAUSE_CODES:
                invalid.append(eid)
        else:
            invalid.append(eid)  # wrong format entirely

    return invalid

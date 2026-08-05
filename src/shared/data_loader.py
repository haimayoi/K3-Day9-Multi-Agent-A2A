"""Single cached loader for the Olist CSVs (README.md #2).

Load once, reuse across all 50 cases and all three agents — do NOT
pd.read_csv() inside a per-case loop, the CSVs are large (100k+ rows each).
Everyone should get data through get_data_store(), never read a CSV directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class DataStore:
    def __init__(
        self,
        orders: pd.DataFrame,
        order_items: pd.DataFrame,
        order_payments: pd.DataFrame,
        sellers: pd.DataFrame,
    ):
        self.orders = orders.set_index("order_id", drop=False)
        self.order_items = order_items
        self.order_payments = order_payments
        self.sellers = sellers

        self._seller_ids = set(sellers["seller_id"])
        self._items_by_order = {oid: df for oid, df in order_items.groupby("order_id")}
        self._payments_by_order = {oid: df for oid, df in order_payments.groupby("order_id")}

    # --- orders --------------------------------------------------------
    def order_exists(self, order_id: str) -> bool:
        return order_id in self.orders.index

    def get_order(self, order_id: str):
        """Returns a pandas Series for the order, or None if not found."""
        if order_id not in self.orders.index:
            return None
        return self.orders.loc[order_id]

    # --- items -----------------------------------------------------------
    def get_items(self, order_id: str) -> pd.DataFrame:
        """All order_items rows for this order. Empty DataFrame if none."""
        return self._items_by_order.get(order_id, self.order_items.iloc[0:0])

    def item_exists(self, order_id: str, order_item_id) -> bool:
        items = self.get_items(order_id)
        return str(order_item_id) in items["order_item_id"].astype(str).values

    # --- payments --------------------------------------------------------
    def get_payments(self, order_id: str) -> pd.DataFrame:
        """All order_payments rows for this order. Empty DataFrame if none."""
        return self._payments_by_order.get(order_id, self.order_payments.iloc[0:0])

    def payment_exists(self, order_id: str, payment_sequential) -> bool:
        payments = self.get_payments(order_id)
        return str(payment_sequential) in payments["payment_sequential"].astype(str).values

    # --- sellers -----------------------------------------------------------
    def seller_exists(self, seller_id: str) -> bool:
        return seller_id in self._seller_ids


@lru_cache(maxsize=1)
def get_data_store() -> DataStore:
    orders = pd.read_csv(DATA_DIR / "olist_orders_dataset.csv")
    order_items = pd.read_csv(DATA_DIR / "olist_order_items_dataset.csv")
    order_payments = pd.read_csv(DATA_DIR / "olist_order_payments_dataset.csv")
    sellers = pd.read_csv(DATA_DIR / "olist_sellers_dataset.csv")

    return DataStore(
        orders=orders,
        order_items=order_items,
        order_payments=order_payments,
        sellers=sellers,
    )

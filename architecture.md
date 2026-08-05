## Payment Agent

The Payment Agent is deterministic and does not call an LLM.

- **Role:** reconcile payment records against item prices and freight charges.
- **Inputs:** claimed `order_id`, plus payments and items retrieved with the shared `get_data_store()` datastore.
- **Outputs (`PaymentResult`):** `payment_ids`, `payment_row_count`, `item_total_brl`, `freight_total_brl`, `payment_total_brl`, `is_split_payment`, and `reconciled`.
- **Data access:** read-only access to `data/olist_order_payments_dataset.csv` and `data/olist_order_items_dataset.csv` through the shared loader; it never reads CSV files directly.
- **Handoff:** returns `PaymentResult` to the Coordinator/Policy Agent. A valid split payment has at least two payment rows and reconciles payment total against item price plus freight within `0.10 BRL`.

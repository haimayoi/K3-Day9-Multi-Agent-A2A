## Order & Seller Agent + Delivery Agent

Implemented as a single function, `analyze_fulfillment()`, rather than two
separate agents. Both responsibilities need the same `orders` +
`order_items` rows for a given `order_id`, so splitting them into two calls
would mean loading/joining the same rows twice for no benefit at this data
volume. Deterministic — does not call an LLM.

- **Role:** determine order status (`canceled`/`unavailable`), whether the
  seller handed the order to the carrier after that item's
  `shipping_limit_date` (Order & Seller responsibility), and whether the
  carrier delivered after `order_estimated_delivery_date` (Delivery
  responsibility).
- **Inputs:** claimed `order_id`, plus orders and order items retrieved with
  the shared `get_data_store()` datastore.
- **Outputs (`FulfillmentResult`):** `order_exists`, `order_status`,
  `order_ids`, `item_ids`, `seller_ids`, `estimated_date`,
  `actual_carrier_date`, `actual_customer_date`, `delivered_late`,
  `seller_late`, `late_seller_ids`, `candidate_root_causes`.
- **Data access:** read-only access to `data/olist_orders_dataset.csv` and
  `data/olist_order_items_dataset.csv` through the shared loader; never
  reads a CSV directly.
- **Handoff:** returns `FulfillmentResult` to the Coordinator/Policy Agent.
  `candidate_root_causes` is pre-ranked by the README §4 priority order
  (`canceled`/`unavailable` > seller-late > logistics-late >
  within-estimate), but this agent does **not** confirm the "payment > 0"
  condition for the canceled/unavailable rules — the Coordinator must
  combine this with `PaymentResult.payment_total_brl` before finalizing
  `primary_issue`.
- **Verification:** ran against all 50 real cases in `input/` — every case
  resolves to exactly one candidate root cause (18 within-estimate, 8 each
  of seller-late, canceled, unavailable, logistics-late), no unresolved or
  ambiguous cases. Orders with `unavailable` status confirmed to have zero
  item rows in the real data, correctly producing empty `item_ids`/`seller_ids`.

## Payment Agent

The Payment Agent is deterministic and does not call an LLM.

- **Role:** reconcile payment records against item prices and freight charges.
- **Inputs:** claimed `order_id`, plus payments and items retrieved with the shared `get_data_store()` datastore.
- **Outputs (`PaymentResult`):** `payment_ids`, `payment_row_count`, `item_total_brl`, `freight_total_brl`, `payment_total_brl`, `is_split_payment`, and `reconciled`.
- **Data access:** read-only access to `data/olist_order_payments_dataset.csv` and `data/olist_order_items_dataset.csv` through the shared loader; it never reads CSV files directly.
- **Handoff:** returns `PaymentResult` to the Coordinator/Policy Agent. A valid split payment has at least two payment rows and reconciles payment total against item price plus freight within `0.10 BRL`.

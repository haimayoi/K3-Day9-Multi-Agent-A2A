# Multi-Agent Architecture — E-commerce Dispute Resolution

## Overview

Each case flows through `main.py` → `coordinate_case()` in one direction, with
each agent handing off a structured result to the next — no agent re-reads
another agent's raw CSV rows, only its typed result object.

```text
input/EC_*.json
      |
      v
+-----------------------+     +----------------------+
| Fulfillment Agent     |     | Payment Agent        |
| (Order & Seller +     |     | (payment_agent.py)   |
|  Delivery)            |     |                      |
| analyze_fulfillment() |     | analyze_payment()    |
+-----------+-----------+     +----------+-----------+
            |  FulfillmentResult          |  PaymentResult
            v                             v
        +-------------------------------------+
        |     Coordinator / Policy Agent       |
        |     (coordinator.py)                 |
        |     resolve_case() applies           |
        |     EC_POLICY_V1 priority table      |
        +-------------------+-------------------+
                            |  CaseOutput
                            v
                  +--------------------+
                  |  Verifier Agent    |
                  |  (verifier.py)     |
                  |  verify_case()     |
                  +---------+----------+
                            |  pass -> write file / fail -> reject case
                            v
                  output/output/EC_*.json
                  + output/output.zip
```

Both domain agents (Fulfillment, Payment) run independently against the same
`order_id` and never call each other — they only read from the shared,
cached `DataStore` (`src/shared/data_loader.py`). The Coordinator is the only
agent that combines their outputs, and the Verifier is the only agent
allowed to block a case from being written.

## Agent roles & data access

| Agent | File | Reads | Writes / hands off |
| --- | --- | --- | --- |
| Fulfillment (Order & Seller + Delivery) | `src/agents/fulfillment_agent.py` | `orders.csv`, `order_items.csv` (via `DataStore`) | `FulfillmentResult` → Coordinator |
| Payment | `src/agents/payment_agent.py` | `order_payments.csv`, `order_items.csv` (via `DataStore`) | `PaymentResult` → Coordinator |
| Coordinator / Policy | `src/agents/coordinator.py` | `FulfillmentResult` + `PaymentResult` only (no direct CSV access) | `CaseOutput` → Verifier |
| Verifier | `src/agents/verifier.py` | `CaseOutput` + `DataStore` (to confirm evidence IDs are real) | pass/fail list of problems → `main.py` |
| I/O harness | `main.py` | `input/EC_*.json` | `output/output/EC_*.json`, submission zip, metadata and trace |

Every field is derived deterministically from `EC_POLICY_V1`'s fixed rule
table (README §4), which requires exact reproducibility across 50 graded
cases rather than generative judgment. A case receives confidence `1.0`
only after its CSV facts satisfy one complete policy rule; the Verifier still
checks that confidence is in `[0, 1]` before the case can be written. This
removes API variability from the graded artifact and keeps repeated runs
identical.

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

## Coordinator / Policy Agent

Deterministic — does not call an LLM. Owns `EC_POLICY_V1`: the only agent
that decides `primary_issue` and builds the final `CaseOutput`.

- **Role:** `coordinate_case()` calls Fulfillment then Payment for a given
  case, then `resolve_case()` walks the priority table top-to-bottom
  (canceled/unavailable-with-payment → seller-late → logistics-late →
  valid split payment → unsupported late claim) to pick exactly one
  `primary_issue`, in the order fixed by README §4.
- **Inputs:** `FulfillmentResult`, `PaymentResult` — never touches a CSV
  directly, only the two upstream agents' typed results.
- **Outputs (`CaseOutput`):** `assessment` (primary_issue/case_status/
  confidence), `affected_entities` (order/item/seller/payment IDs, each
  capped at 5), `root_cause_analysis` (ranked causes capped at 3,
  responsible parties capped at 3), `evidence_ids` (built via
  `src/shared/evidence.py` helpers, capped at 10), `financial_resolution`
  (item/freight/payment totals plus `recommended_refund_brl`), and
  `resolution_actions` (mapped 1-1 from `primary_issue`).
- **Handoff:** returns `CaseOutput` to the Verifier Agent before anything is
  written to `output/`.
- **No-rule handling:** `unsupported_late_claim` is selected only when actual
  delivery and estimated timestamps both exist, delivery is not late, and
  payment reconciles. Missing or contradictory facts raise an integration
  error instead of being silently mislabeled as a supported policy outcome.

## Verifier Agent

Deterministic — does not call an LLM. Last checkpoint before a case is
written to disk; a case that fails here is rejected rather than written
with bad data.

- **Role:** `verify_case()` checks exact schema and value types, policy/cause/
  action/refund consistency, confidence, rounding, list caps, responsible
  parties, no-item behavior, entity-to-order relationships and — via
  `validate_evidence_ids()` — that every evidence ID actually resolves
  against the CSV data and belongs to an affected entity.
- **Inputs:** one `CaseOutput` plus the shared `DataStore` (read-only, to
  confirm evidence IDs).
- **Outputs:** a list of problem strings; empty means the case passes.
  `main.py` refuses to replace the submission if any case has a non-empty
  list, logs the run, and only after all 50 pass writes JSON plus a zip with
  exactly `output/EC_001.json` through `output/EC_050.json`.
- **Result:** all 50 real cases pass with zero problems.

"""Model/framework config shared by all agents.

Model name must live here (in source), NOT in .env — grading requirement (README.md #9.4).
"""

# --- Model ---------------------------------------------------------------
# Used by every agent that needs an LLM call (Coordinator explanation/confidence,
# Policy tie-break reasoning, etc.). Keep every agent on this single model so
# metadata.json only needs one declaration.
MODEL_NAME = "gpt-4o-mini"
MODEL_PROVIDER = "openai"

# OpenAI has never published gpt-4o-mini's exact parameter count. This is the
# commonly cited community estimate, not an official figure. Declared as-is
# per team decision on 2026-08-05; if a grader disputes it, this is the value
# that was knowingly accepted.
MODEL_PARAM_SIZE = "~8B (unofficial estimate — OpenAI has not published the exact size)"

# --- Framework -------------------------------------------------------------
# TODO(team): fill in once picked at kickoff (e.g. "custom-python", "langgraph", "crewai").
FRAMEWORK = "TODO_FRAMEWORK"
RUNTIME = "python 3.11"

# --- Business constants (README.md #4-#6) ----------------------------------
POLICY_VERSION = "EC_POLICY_V1"

PRIMARY_ISSUES = (
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
)

ROOT_CAUSE_CODES = (
    "SELLER_HANDOFF_AFTER_LIMIT",
    "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "ORDER_CANCELED_AFTER_PAYMENT",
    "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "MULTIPLE_PAYMENTS_RECONCILED",
    "DELIVERY_WITHIN_ESTIMATE",
)

RESOLUTION_ACTIONS = (
    "issue_full_refund",
    "refund_freight",
    "explain_valid_split_payment",
    "reject_late_refund",
)

PARTY_TYPES = ("platform", "seller", "logistics_provider")

PLATFORM_PARTY_ID = "OLIST_PLATFORM"
LOGISTICS_PARTY_ID = "LOGISTICS_PROVIDER"

CASE_STATUSES = ("action_required", "no_action")

# Output limits (README.md #6)
MAX_IDS_PER_ENTITY_SET = 5
MAX_EVIDENCE_IDS = 10
MAX_ROOT_CAUSES = 3
MAX_RESPONSIBLE_PARTIES = 3
MAX_ACTIONS = 5

MONEY_RECONCILIATION_TOLERANCE_BRL = 0.10

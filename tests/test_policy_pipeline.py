from __future__ import annotations

import copy
import unittest

import pandas as pd

from src.agents.coordinator import resolve_case
from src.agents.verifier import verify_case
from src.shared.data_loader import DataStore
from src.shared.money import within_tolerance


ORDER_ID = "order-1"
SELLER_ID = "seller-1"


def fulfillment_result(**overrides):
    result = {
        "order_exists": True,
        "order_status": "delivered",
        "order_ids": [ORDER_ID],
        "item_ids": [f"{ORDER_ID}:1"],
        "seller_ids": [SELLER_ID],
        "estimated_date": "2018-01-10 00:00:00",
        "actual_carrier_date": "2018-01-05 00:00:00",
        "actual_customer_date": "2018-01-09 00:00:00",
        "delivered_late": False,
        "seller_late": False,
        "late_seller_ids": [],
        "candidate_root_causes": ["DELIVERY_WITHIN_ESTIMATE"],
    }
    result.update(overrides)
    return result


def payment_result(**overrides):
    result = {
        "payment_ids": [f"{ORDER_ID}:1"],
        "payment_row_count": 1,
        "item_total_brl": 100.0,
        "freight_total_brl": 10.0,
        "payment_total_brl": 110.0,
        "is_split_payment": False,
        "reconciled": True,
    }
    result.update(overrides)
    return result


def case_input():
    return {
        "case_id": "EC_001",
        "customer_request": {"claimed_order_id": ORDER_ID},
        "policy_version": "EC_POLICY_V1",
    }


def data_store() -> DataStore:
    return DataStore(
        orders=pd.DataFrame([{"order_id": ORDER_ID}, {"order_id": "order-2"}]),
        order_items=pd.DataFrame(
            [
                {"order_id": ORDER_ID, "order_item_id": 1, "seller_id": SELLER_ID},
                {"order_id": "order-2", "order_item_id": 1, "seller_id": "seller-2"},
            ]
        ),
        order_payments=pd.DataFrame(
            [
                {"order_id": ORDER_ID, "payment_sequential": 1},
                {"order_id": "order-2", "payment_sequential": 1},
            ]
        ),
        sellers=pd.DataFrame([{"seller_id": SELLER_ID}, {"seller_id": "seller-2"}]),
    )


class CoordinatorPolicyTests(unittest.TestCase):
    def test_all_policy_outcomes(self):
        scenarios = (
            (
                "canceled_order_paid",
                fulfillment_result(order_status="canceled"),
                payment_result(),
                110.0,
                "issue_full_refund",
            ),
            (
                "unavailable_order_paid",
                fulfillment_result(order_status="unavailable", item_ids=[], seller_ids=[]),
                payment_result(item_total_brl=0.0, freight_total_brl=0.0),
                110.0,
                "issue_full_refund",
            ),
            (
                "late_delivery_seller",
                fulfillment_result(
                    delivered_late=True,
                    seller_late=True,
                    late_seller_ids=[SELLER_ID],
                    actual_customer_date="2018-01-11 00:00:00",
                ),
                payment_result(),
                10.0,
                "refund_freight",
            ),
            (
                "late_delivery_logistics",
                fulfillment_result(
                    delivered_late=True,
                    actual_customer_date="2018-01-11 00:00:00",
                ),
                payment_result(),
                10.0,
                "refund_freight",
            ),
            (
                "valid_split_payment",
                fulfillment_result(),
                payment_result(
                    payment_ids=[f"{ORDER_ID}:1", f"{ORDER_ID}:2"],
                    payment_row_count=2,
                    is_split_payment=True,
                ),
                0.0,
                "explain_valid_split_payment",
            ),
            (
                "unsupported_late_claim",
                fulfillment_result(),
                payment_result(),
                0.0,
                "reject_late_refund",
            ),
        )

        for issue, fulfillment, payment, refund, action in scenarios:
            with self.subTest(issue=issue):
                output = resolve_case(case_input(), fulfillment, payment)
                self.assertEqual(issue, output["assessment"]["primary_issue"])
                self.assertEqual(1.0, output["assessment"]["confidence"])
                self.assertEqual(refund, output["financial_resolution"]["recommended_refund_brl"])
                self.assertEqual([action], output["resolution_actions"])
                self.assertEqual(1, len(output["root_cause_analysis"]["ranked_causes"]))

    def test_priority_prefers_canceled_over_delivery_and_split(self):
        fulfillment = fulfillment_result(
            order_status="canceled",
            delivered_late=True,
            seller_late=True,
            late_seller_ids=[SELLER_ID],
            actual_customer_date="2018-01-11 00:00:00",
        )
        payment = payment_result(
            payment_ids=[f"{ORDER_ID}:1", f"{ORDER_ID}:2"],
            payment_row_count=2,
            is_split_payment=True,
        )
        output = resolve_case(case_input(), fulfillment, payment)
        self.assertEqual("canceled_order_paid", output["assessment"]["primary_issue"])

    def test_missing_facts_do_not_become_unsupported_claim(self):
        fulfillment = fulfillment_result(actual_customer_date=None)
        with self.assertRaisesRegex(ValueError, "do not satisfy"):
            resolve_case(case_input(), fulfillment, payment_result())

    def test_unreconciled_payment_does_not_become_unsupported_claim(self):
        with self.assertRaisesRegex(ValueError, "do not satisfy"):
            resolve_case(case_input(), fulfillment_result(), payment_result(reconciled=False))


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.store = data_store()
        self.output = resolve_case(case_input(), fulfillment_result(), payment_result())

    def test_valid_output_passes(self):
        self.assertEqual([], verify_case(self.output, self.store))

    def test_wrong_refund_and_status_are_rejected(self):
        output = copy.deepcopy(self.output)
        output["financial_resolution"]["recommended_refund_brl"] = 1.0
        output["assessment"]["case_status"] = "action_required"
        problems = verify_case(output, self.store)
        self.assertTrue(any("recommended_refund_brl" in problem for problem in problems))
        self.assertTrue(any("case_status" in problem for problem in problems))

    def test_malformed_money_is_reported_without_crashing(self):
        output = copy.deepcopy(self.output)
        output["financial_resolution"]["payment_total_brl"] = "not-money"
        problems = verify_case(output, self.store)
        self.assertTrue(any("payment_total_brl" in problem for problem in problems))

    def test_evidence_from_another_order_is_rejected(self):
        output = copy.deepcopy(self.output)
        output["evidence_ids"].insert(0, "payment:order-2:1")
        problems = verify_case(output, self.store)
        self.assertTrue(any("outside affected entities" in problem for problem in problems))


class MoneyTests(unittest.TestCase):
    def test_reconciliation_tolerance_boundary_is_decimal_exact(self):
        self.assertTrue(within_tolerance(10.0, 10.10, 0.10))
        self.assertFalse(within_tolerance(10.0, 10.1000001, 0.10))


if __name__ == "__main__":
    unittest.main()

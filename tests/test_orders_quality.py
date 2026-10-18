import unittest

from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType

from src.pipelines.orders_quality import (
    ALLOWED_ORDER_STATUSES,
    OrderDataQualityError,
    QUALITY_RULES,
    reconcile_source_to_target,
    validate_orders,
)


ORDER_SCHEMA = StructType(
    [
        StructField("order_id", StringType(), True),
        StructField("customer_id", StringType(), True),
        StructField("order_date", StringType(), True),
        StructField("order_status", StringType(), True),
        StructField("total_amount", StringType(), True),
    ]
)


class OrdersQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (
            SparkSession.builder
            .appName("orders-quality-tests")
            .master("local[1]")
            .getOrCreate()
        )
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def create_orders(self, rows):
        return self.spark.createDataFrame(rows, ORDER_SCHEMA)

    def assert_quality_failure(self, rows, expected_reasons):
        with self.assertRaises(OrderDataQualityError) as context:
            validate_orders(self.create_orders(rows))
        report = context.exception.report
        self.assertEqual(report["input_count"], len(rows))
        self.assertEqual(report["rejected_count"], len(rows))
        self.assertEqual(report["accepted_count"], 0)
        for reason in QUALITY_RULES:
            self.assertEqual(
                report["reason_counts"][reason],
                expected_reasons.get(reason, 0),
            )
        return report

    def test_valid_orders_are_accepted_and_reported(self):
        rows = [
            (f"O{index}", f"C{index}", "2026-10-17", status, "0")
            for index, status in enumerate(ALLOWED_ORDER_STATUSES, start=1)
        ]

        report = validate_orders(self.create_orders(rows))

        self.assertEqual(report["input_count"], len(ALLOWED_ORDER_STATUSES))
        self.assertEqual(report["accepted_count"], len(ALLOWED_ORDER_STATUSES))
        self.assertEqual(report["rejected_count"], 0)
        self.assertTrue(all(value == 0 for value in report["reason_counts"].values()))

    def test_null_and_blank_required_fields_are_rejected(self):
        rows = [
            (None, "C1", "2026-10-17", "PLACED", "10"),
            ("O2", "  ", "2026-10-17", "PLACED", "10"),
        ]

        self.assert_quality_failure(rows, {"missing_required_fields": 2})

    def test_malformed_timestamp_is_rejected(self):
        rows = [("O1", "C1", "not-a-date", "PLACED", "10")]

        self.assert_quality_failure(rows, {"malformed_order_date": 1})

    def test_unknown_status_is_rejected(self):
        rows = [("O1", "C1", "2026-10-17", "PENDING", "10")]

        self.assert_quality_failure(rows, {"invalid_order_status": 1})

    def test_status_matching_is_exact_and_case_sensitive(self):
        rows = [
            ("O1", "C1", "2026-10-17", " placed ", "10"),
            ("O2", "C2", "2026-10-17", "placed", "10"),
        ]

        self.assert_quality_failure(rows, {"invalid_order_status": 2})

    def test_negative_non_numeric_and_non_finite_amounts_are_rejected(self):
        rows = [
            ("O1", "C1", "2026-10-17", "PLACED", "-1"),
            ("O2", "C2", "2026-10-17", "PLACED", "not-a-number"),
            ("O3", "C3", "2026-10-17", "PLACED", "NaN"),
            ("O4", "C4", "2026-10-17", "PLACED", "Infinity"),
        ]

        self.assert_quality_failure(rows, {"invalid_total_amount": 4})

    def test_all_duplicate_keys_are_rejected_after_trimming(self):
        rows = [
            ("O1", "C1", "2026-10-17", "PLACED", "10"),
            (" O1 ", "C2", "2026-10-17", "SHIPPED", "12"),
        ]

        self.assert_quality_failure(rows, {"duplicate_order_id": 2})

    def test_reason_counts_overlap_but_rejected_count_counts_rows_once(self):
        rows = [("O1", None, "bad-date", "UNKNOWN", "-1")]

        report = self.assert_quality_failure(
            rows,
            {
                "missing_required_fields": 1,
                "malformed_order_date": 1,
                "invalid_order_status": 1,
                "invalid_total_amount": 1,
            },
        )

        self.assertTrue(report["reason_counts_may_overlap"])

    def test_accepted_and_rejected_counts_reconcile_for_mixed_rows(self):
        orders = self.create_orders(
            [
                ("O1", "C1", "2026-10-17", "PLACED", "10"),
                ("O2", "C2", "bad-date", "PLACED", "10"),
            ]
        )

        with self.assertRaises(OrderDataQualityError) as context:
            validate_orders(orders)

        report = context.exception.report
        self.assertEqual(report["input_count"], 2)
        self.assertEqual(report["accepted_count"], 1)
        self.assertEqual(report["rejected_count"], 1)

    def test_missing_schema_column_is_reported_before_row_validation(self):
        orders = self.spark.createDataFrame([("O1",)], ["order_id"])

        with self.assertRaisesRegex(ValueError, "customer_id"):
            validate_orders(orders)

    def test_empty_batch_is_valid_and_reconciles_to_zero(self):
        report = validate_orders(self.create_orders([]))

        self.assertEqual(report["input_count"], 0)
        self.assertEqual(report["accepted_count"], 0)
        self.assertEqual(report["rejected_count"], 0)

    def test_source_to_target_reconciliation_matches_for_valid_runs(self):
        report = {"accepted_count": 2}

        result = reconcile_source_to_target(2, 2, report)

        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["target_count"], 2)
        self.assertEqual(result["accepted_count"], 2)

    def test_source_to_target_reconciliation_rejects_mismatches(self):
        report = {"accepted_count": 2}

        with self.assertRaisesRegex(ValueError, "source.*target"):
            reconcile_source_to_target(2, 3, report)


if __name__ == "__main__":
    unittest.main()
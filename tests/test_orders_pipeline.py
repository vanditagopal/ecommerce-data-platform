import unittest

from src.pipelines.orders_pipeline import (
    ORDERS_INPUT_PATH,
    ORDERS_OUTPUT_PATH,
    PROJECT_ROOT,
    REQUIRED_COLUMNS,
    validate_required_columns,
)


class OrdersPipelineTests(unittest.TestCase):
    def test_pipeline_paths_are_anchored_to_project_root(self):
        self.assertTrue(ORDERS_INPUT_PATH.is_absolute())
        self.assertTrue(ORDERS_OUTPUT_PATH.is_absolute())
        self.assertEqual(
            ORDERS_INPUT_PATH,
            PROJECT_ROOT / "data" / "raw" / "orders.csv",
        )
        self.assertEqual(
            ORDERS_OUTPUT_PATH,
            PROJECT_ROOT / "data" / "bronze" / "orders",
        )

    def test_required_columns_accept_complete_schema(self):
        validate_required_columns(REQUIRED_COLUMNS)

    def test_required_columns_report_missing_names(self):
        with self.assertRaisesRegex(ValueError, "customer_id"):
            validate_required_columns(["order_id"])


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyspark.sql import SparkSession

import src.pipelines.orders_pipeline as orders_pipeline
from src.pipelines.orders_quality import OrderDataQualityError


class OrdersPipelineQualityGateTests(unittest.TestCase):
    def test_invalid_batch_reports_failure_without_replacing_bronze(self):
        with tempfile.TemporaryDirectory(prefix="orders_quality_gate_") as temp_dir:
            root = Path(temp_dir)
            input_path = root / "orders.csv"
            output_path = root / "bronze" / "orders"
            report_path = root / "quality" / "orders_latest.json"

            with (
                patch.object(orders_pipeline, "ORDERS_INPUT_PATH", input_path),
                patch.object(orders_pipeline, "ORDERS_OUTPUT_PATH", output_path),
                patch.object(
                    orders_pipeline,
                    "ORDERS_QUALITY_REPORT_PATH",
                    report_path,
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                input_path.write_text(
                    "order_id,customer_id,order_date,order_status,total_amount\n"
                    "O1,C1,2026-10-17,PLACED,10.50\n",
                    encoding="utf-8",
                )
                orders_pipeline.main()

                spark = (
                    SparkSession.builder
                    .appName("verify-preserved-bronze")
                    .master("local[1]")
                    .getOrCreate()
                )
                try:
                    original_bronze = spark.read.parquet(str(output_path))
                    self.assertEqual(original_bronze.count(), 1)
                    original_order_id = original_bronze.first()["order_id"]
                finally:
                    spark.stop()

                input_path.write_text(
                    "order_id,customer_id,order_date,order_status,total_amount\n"
                    "O2,C2,bad-date,UNKNOWN,-1\n",
                    encoding="utf-8",
                )
                with self.assertRaises(OrderDataQualityError):
                    orders_pipeline.main()

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["input_count"], 1)
            self.assertEqual(report["rejected_count"], 1)
            self.assertEqual(report["accepted_count"], 0)
            self.assertEqual(report["reason_counts"]["malformed_order_date"], 1)
            self.assertEqual(report["reason_counts"]["invalid_order_status"], 1)
            self.assertEqual(report["reason_counts"]["invalid_total_amount"], 1)

            spark = (
                SparkSession.builder
                .appName("check-preserved-bronze")
                .master("local[1]")
                .getOrCreate()
            )
            try:
                preserved_bronze = spark.read.parquet(str(output_path))
                self.assertEqual(preserved_bronze.count(), 1)
                self.assertEqual(
                    preserved_bronze.first()["order_id"],
                    original_order_id,
                )
            finally:
                spark.stop()


if __name__ == "__main__":
    unittest.main()
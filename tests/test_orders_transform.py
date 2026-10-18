import unittest

from pyspark.sql import SparkSession

from src.pipelines.orders_transform import transform_orders


class OrdersTransformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (
            SparkSession.builder
            .appName("orders-transform-tests")
            .master("local[1]")
            .getOrCreate()
        )
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_transform_orders_standardizes_values(self):
        rows = [
            (" ORD00001 ", " CUST0001 ", "2026-10-17T08:15:00Z", " placed ", "12.50"),
        ]

        transformed = transform_orders(
            self.spark.createDataFrame(
                rows,
                ["order_id", "customer_id", "order_date", "order_status", "total_amount"],
            )
        )

        row = transformed.collect()[0]
        self.assertEqual(row["order_id"], "ORD00001")
        self.assertEqual(row["customer_id"], "CUST0001")
        self.assertEqual(str(row["order_status"]), "PLACED")
        self.assertEqual(float(row["total_amount"]), 12.5)
        self.assertIsNotNone(row["order_date"])

    def test_transform_orders_preserves_row_count(self):
        rows = [
            ("ORD00001", "CUST0001", "2026-10-17T08:15:00Z", "SHIPPED", "12.50"),
            ("ORD00002", "CUST0002", "2026-10-18T08:15:00Z", "DELIVERED", "99.99"),
        ]

        transformed = transform_orders(
            self.spark.createDataFrame(
                rows,
                ["order_id", "customer_id", "order_date", "order_status", "total_amount"],
            )
        )

        self.assertEqual(transformed.count(), 2)
        self.assertEqual(len(transformed.columns), 5)


if __name__ == "__main__":
    unittest.main()

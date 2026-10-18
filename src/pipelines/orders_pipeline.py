import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.sql import SparkSession
from src.pipelines.orders_quality import (
    OrderDataQualityError,
    reconcile_source_to_target,
    validate_orders,
)
from src.pipelines.orders_transform import read_orders, transform_orders

ORDERS_INPUT_PATH = PROJECT_ROOT / "data" / "raw" / "orders.csv"
ORDERS_OUTPUT_PATH = PROJECT_ROOT / "data" / "bronze" / "orders"
ORDERS_SILVER_OUTPUT_PATH = PROJECT_ROOT / "data" / "silver" / "orders"
ORDERS_QUALITY_REPORT_PATH = PROJECT_ROOT / "data" / "quality" / "orders_latest.json"
REQUIRED_COLUMNS = (
    "order_id",
    "customer_id",
    "order_date",
    "order_status",
    "total_amount",
)


def validate_required_columns(columns):
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")


def main():
    spark = (
        SparkSession.builder
        .appName("OrdersBronzePipeline")
        .master("local[*]")
        .config("spark.hadoop.io.native.lib.available", "false")
        .getOrCreate()
    )

    try:
        orders = read_orders(spark, ORDERS_INPUT_PATH)

        print("=== RAW ORDERS ===")
        orders.printSchema()

        validate_required_columns(orders.columns)
        try:
            quality_report = validate_orders(orders)
        except OrderDataQualityError as error:
            quality_report = error.report
            ORDERS_QUALITY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            ORDERS_QUALITY_REPORT_PATH.write_text(
                json.dumps(quality_report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            raise

        ORDERS_QUALITY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ORDERS_QUALITY_REPORT_PATH.write_text(
            json.dumps(quality_report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("Quality report:", json.dumps(quality_report, sort_keys=True))

        source_count = orders.count()
        orders.write.mode("overwrite").parquet(str(ORDERS_OUTPUT_PATH))

        bronze_orders = spark.read.parquet(str(ORDERS_OUTPUT_PATH))
        reconcile_source_to_target(source_count, bronze_orders.count(), quality_report)
        print("=== BRONZE ORDERS CREATED ===")

        silver_orders = transform_orders(orders)
        silver_orders.write.mode("overwrite").parquet(str(ORDERS_SILVER_OUTPUT_PATH))
        print("=== SILVER ORDERS CREATED ===")
    finally:
        spark.stop()



if __name__ == "__main__":
    main()

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def read_orders(spark, input_path) -> DataFrame:
    return (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv(str(input_path))
    )


def transform_orders(orders: DataFrame) -> DataFrame:
    return (
        orders
        .withColumn("order_id", F.trim(F.col("order_id").cast("string")))
        .withColumn("customer_id", F.trim(F.col("customer_id").cast("string")))
        .withColumn("order_date", F.to_timestamp(F.col("order_date")))
        .withColumn("order_status", F.upper(F.trim(F.col("order_status").cast("string"))))
        .withColumn("total_amount", F.col("total_amount").cast("double"))
        .select(
            "order_id",
            "customer_id",
            "order_date",
            "order_status",
            "total_amount",
        )
    )

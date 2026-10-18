import json
from functools import reduce
from operator import or_

from pyspark.sql import DataFrame
from pyspark.sql import Window
from pyspark.sql.functions import (
    col,
    count,
    expr,
    isnan,
    lit,
    sum as spark_sum,
    trim,
    when,
)


ALLOWED_ORDER_STATUSES = (
    "PLACED",
    "CONFIRMED",
    "SHIPPED",
    "DELIVERED",
    "CANCELLED",
    "RETURNED",
)

REQUIRED_ORDER_FIELDS = (
    "order_id",
    "customer_id",
    "order_date",
    "order_status",
    "total_amount",
)

QUALITY_RULES = (
    "missing_required_fields",
    "malformed_order_date",
    "invalid_order_status",
    "invalid_total_amount",
    "duplicate_order_id",
)


class OrderDataQualityError(ValueError):
    def __init__(self, report: dict[str, object]):
        self.report = report
        super().__init__(f"Order data quality validation failed: {json.dumps(report, sort_keys=True)}")


def reconcile_source_to_target(
    source_count: int,
    target_count: int,
    quality_report: dict[str, object],
) -> dict[str, object]:
    accepted_count = int(quality_report.get("accepted_count", source_count) or 0)

    if accepted_count != source_count:
        raise ValueError(
            "Source record count does not match accepted record count: "
            f"source={source_count}, accepted={accepted_count}"
        )

    if source_count != target_count:
        raise ValueError(
            "Source record count does not match target record count: "
            f"source={source_count}, target={target_count}"
        )

    return {
        "source_count": source_count,
        "target_count": target_count,
        "accepted_count": accepted_count,
    }


def validate_orders(orders: DataFrame) -> dict[str, object]:
    missing_columns = [
        field for field in REQUIRED_ORDER_FIELDS if field not in orders.columns
    ]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    missing_required = reduce(
        or_,
        [
            col(field).isNull()
            | (trim(col(field).cast("string")) == "")
            for field in REQUIRED_ORDER_FIELDS
        ],
    )
    raw_order_date = trim(col("order_date").cast("string"))
    parsed_order_date = expr("try_cast(order_date AS TIMESTAMP)")
    invalid_order_date = (
        raw_order_date.isNotNull()
        & (raw_order_date != "")
        & parsed_order_date.isNull()
    )

    order_status = col("order_status").cast("string")
    invalid_order_status = (
        col("order_status").isNotNull()
        & ~order_status.isin(*ALLOWED_ORDER_STATUSES)
    )

    parsed_amount = expr("try_cast(total_amount AS DOUBLE)")
    invalid_amount = (
        parsed_amount.isNull()
        | (parsed_amount < 0)
        | (parsed_amount == float("inf"))
        | (parsed_amount == float("-inf"))
        | isnan(parsed_amount)
    )

    order_id = trim(col("order_id").cast("string"))
    duplicate_order_id = (
        (order_id != "")
        & (count(lit(1)).over(Window.partitionBy(order_id)) > 1)
    )

    flags = {
        "missing_required_fields": missing_required,
        "malformed_order_date": invalid_order_date,
        "invalid_order_status": invalid_order_status,
        "invalid_total_amount": invalid_amount,
        "duplicate_order_id": duplicate_order_id,
    }
    any_failure = reduce(or_, [flags[name] for name in QUALITY_RULES])
    flagged_orders = orders.select(
        *[
            when(condition, lit(1)).otherwise(lit(0)).alias(name)
            for name, condition in flags.items()
        ],
        when(any_failure, lit(1)).otherwise(lit(0)).alias("rejected"),
    )
    metrics = flagged_orders.agg(
        count(lit(1)).alias("input_count"),
        *[
            spark_sum(col(name)).alias(name)
            for name in QUALITY_RULES
        ],
        spark_sum(col("rejected")).alias("rejected_count"),
    ).first().asDict()

    input_count = metrics["input_count"] or 0
    rejected_count = metrics["rejected_count"] or 0
    report: dict[str, object] = {
        "input_count": input_count,
        "accepted_count": input_count - rejected_count,
        "rejected_count": rejected_count,
        "reason_counts": {
            name: metrics[name] or 0 for name in QUALITY_RULES
        },
        "reason_counts_may_overlap": True,
    }

    if rejected_count:
        raise OrderDataQualityError(report)
    return report
import json
from pathlib import Path

from pydantic import ValidationError
from pyspark.sql import SparkSession

from src.api.schemas import (
    MetricsSummaryResponse,
    OrderResponse,
    OrdersPageResponse,
    QualityReportResponse,
)


class DataUnavailableError(Exception):
    """Raised when a required local pipeline output cannot be read."""


class OrdersDataService:
    def __init__(self, bronze_path: Path, quality_path: Path):
        self.bronze_path = bronze_path
        self.quality_path = quality_path

    def latest_quality_report(self) -> QualityReportResponse:
        try:
            with self.quality_path.open("r", encoding="utf-8") as report_file:
                report = json.load(report_file)
            return QualityReportResponse.model_validate(report)
        except (OSError, json.JSONDecodeError, ValidationError) as error:
            raise DataUnavailableError(
                "Latest data-quality report is unavailable or invalid."
            ) from error

    def summary_metrics(self) -> MetricsSummaryResponse:
        report = self.latest_quality_report()
        bronze_row_count = self._bronze_row_count()
        return MetricsSummaryResponse(
            input_count=report.input_count,
            accepted_count=report.accepted_count,
            rejected_count=report.rejected_count,
            reason_counts=report.reason_counts,
            bronze_row_count=bronze_row_count,
        )

    def list_orders(self, page: int, limit: int) -> OrdersPageResponse:
        if not self.bronze_path.exists():
            raise DataUnavailableError("Bronze orders dataset is unavailable.")

        spark = self._spark_session()
        try:
            dataframe = spark.read.parquet(str(self.bronze_path))
            total = int(dataframe.count())
            start = (page - 1) * limit
            rows = (
                dataframe.orderBy("order_id")
                .offset(start)
                .limit(limit)
                .collect()
            )
            items = [OrderResponse.model_validate(row.asDict(recursive=True)) for row in rows]
        except Exception as error:
            raise DataUnavailableError(
                "Bronze orders dataset is unavailable or invalid."
            ) from error
        finally:
            spark.stop()

        return OrdersPageResponse(
            items=items,
            count=len(items),
            page=page,
            limit=limit,
            total=total,
        )

    def _bronze_row_count(self) -> int:
        if not self.bronze_path.exists():
            raise DataUnavailableError("Bronze orders dataset is unavailable.")

        spark = self._spark_session()
        try:
            return int(spark.read.parquet(str(self.bronze_path)).count())
        except Exception as error:
            raise DataUnavailableError(
                "Bronze orders dataset is unavailable or invalid."
            ) from error
        finally:
            spark.stop()

    @staticmethod
    def _spark_session() -> SparkSession:
        return (
            SparkSession.builder
            .appName("OrdersApi")
            .master("local[1]")
            .config("spark.hadoop.io.native.lib.available", "false")
            .getOrCreate()
        )
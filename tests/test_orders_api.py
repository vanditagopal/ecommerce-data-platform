import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.schemas import (
    MetricsSummaryResponse,
    OrderResponse,
    OrdersPageResponse,
    QualityReportResponse,
)
from src.api.service import OrdersDataService


class OrdersApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.service = unittest.mock.Mock()
        reason_counts = {
            "duplicate_order_id": 0,
            "invalid_order_status": 0,
            "invalid_total_amount": 0,
            "malformed_order_date": 0,
            "missing_required_fields": 0,
        }
        self.service.summary_metrics.return_value = MetricsSummaryResponse(
            input_count=1,
            accepted_count=1,
            rejected_count=0,
            reason_counts=reason_counts,
            bronze_row_count=1,
        )
        self.service.latest_quality_report.return_value = QualityReportResponse(
            input_count=1,
            accepted_count=1,
            rejected_count=0,
            reason_counts=reason_counts,
            reason_counts_may_overlap=True,
        )
        self.service.list_orders.return_value = OrdersPageResponse(
            items=[
                OrderResponse(
                    order_id="ORD0000001",
                    customer_id="CUST000001",
                    order_date=datetime(2026, 1, 1),
                    order_status="PLACED",
                    total_amount=10.0,
                )
            ],
            count=1,
            page=1,
            limit=20,
            total=1,
        )
        service_patch = patch("src.api.app.orders_service", self.service)
        service_patch.start()
        self.addCleanup(service_patch.stop)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_summary_endpoint_returns_pipeline_metrics(self):
        response = self.client.get("/api/v1/metrics/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("input_count", payload)
        self.assertIn("accepted_count", payload)
        self.assertIn("rejected_count", payload)
        self.assertIn("bronze_row_count", payload)

    def test_latest_data_quality_returns_pipeline_report(self):
        response = self.client.get("/api/v1/data-quality/latest")
        self.assertEqual(response.status_code, 200)
        self.assertIn("input_count", response.json())

    def test_orders_endpoint_returns_paginated_rows(self):
        response = self.client.get("/api/v1/orders?page=1&limit=5")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("items", payload)
        self.assertIn("count", payload)
        self.assertLessEqual(len(payload["items"]), 5)
        self.assertEqual(payload["count"], len(payload["items"]))
        self.assertIn("total", payload)

    def test_orders_endpoint_rejects_out_of_range_pagination(self):
        response = self.client.get("/api/v1/orders?page=0&limit=101")
        self.assertEqual(response.status_code, 422)

    def test_quality_endpoint_returns_service_unavailable_when_report_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_report = Path(directory) / "missing.json"
            service = OrdersDataService(Path(directory) / "orders", missing_report)
            with patch("src.api.app.orders_service", service):
                response = self.client.get("/api/v1/data-quality/latest")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Latest data-quality report is unavailable or invalid."},
        )

    def test_quality_endpoint_returns_service_unavailable_for_invalid_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "quality.json"
            report_path.write_text(json.dumps({"input_count": "bad"}), encoding="utf-8")
            service = OrdersDataService(Path(directory) / "orders", report_path)
            with patch("src.api.app.orders_service", service):
                response = self.client.get("/api/v1/data-quality/latest")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Latest data-quality report is unavailable or invalid."},
        )

    def test_orders_endpoint_returns_service_unavailable_when_bronze_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            service = OrdersDataService(
                Path(directory) / "missing_orders",
                Path(directory) / "missing_quality.json",
            )
            with patch("src.api.app.orders_service", service):
                response = self.client.get("/api/v1/orders")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Bronze orders dataset is unavailable."},
        )


if __name__ == "__main__":
    unittest.main()

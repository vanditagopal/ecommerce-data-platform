from contextlib import contextmanager
from datetime import datetime, timedelta
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

import src.api.app as app_module
from src.api.schemas import (
    MetricsSummaryResponse,
    OrderResponse,
    OrdersPageResponse,
    QualityReportResponse,
)
from src.api.service import DataUnavailableError


class FixtureOrdersService:
    def __init__(self, quality_available=True):
        statuses = [
            "PLACED",
            "CONFIRMED",
            "SHIPPED",
            "DELIVERED",
            "CANCELLED",
            "RETURNED",
            "PLACED",
            "DELIVERED",
            "SHIPPED",
            "CONFIRMED",
            "DELIVERED",
            "PLACED",
        ]
        self.orders = [
            OrderResponse(
                order_id=f"ORD{index:07d}",
                customer_id=f"CUST{index:06d}",
                order_date=datetime(2026, 1, 1) + timedelta(days=index),
                order_status=status,
                total_amount=10.0 + index,
            )
            for index, status in enumerate(statuses, start=1)
        ]
        self.quality_available = quality_available

    def summary_metrics(self):
        return MetricsSummaryResponse(
            input_count=12,
            accepted_count=11,
            rejected_count=1,
            reason_counts={
                "duplicate_order_id": 0,
                "invalid_order_status": 1,
                "invalid_total_amount": 0,
                "malformed_order_date": 0,
                "missing_required_fields": 0,
            },
            bronze_row_count=12,
        )

    def latest_quality_report(self):
        if not self.quality_available:
            raise DataUnavailableError(
                "Latest data-quality report is unavailable or invalid."
            )
        return QualityReportResponse(
            input_count=12,
            accepted_count=11,
            rejected_count=1,
            reason_counts={
                "duplicate_order_id": 0,
                "invalid_order_status": 1,
                "invalid_total_amount": 0,
                "malformed_order_date": 0,
                "missing_required_fields": 0,
            },
            reason_counts_may_overlap=True,
        )

    def list_orders(self, page, limit):
        start = (page - 1) * limit
        items = self.orders[start : start + limit]
        return OrdersPageResponse(
            items=items,
            count=len(items),
            page=page,
            limit=limit,
            total=len(self.orders),
        )


@pytest.fixture
def run_dashboard(monkeypatch):
    @contextmanager
    def start(service):
        monkeypatch.setattr(app_module, "orders_service", service)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                app_module.app,
                log_level="critical",
                access_log=False,
                lifespan="off",
            )
        )
        thread = threading.Thread(
            target=server.run,
            kwargs={"sockets": [listener]},
            daemon=True,
        )
        thread.start()
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not thread.is_alive():
                listener.close()
                raise RuntimeError("Dashboard server stopped during startup.")
            try:
                if httpx.get(f"{base_url}/health", timeout=0.5).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.05)
        else:
            server.should_exit = True
            thread.join(timeout=5)
            listener.close()
            raise RuntimeError("Dashboard server did not become ready.")

        try:
            yield base_url
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            listener.close()

    return start


@pytest.mark.e2e
def test_dashboard_metrics_filtering_and_pagination(run_dashboard):
    with (
        run_dashboard(FixtureOrdersService()) as base_url,
        sync_playwright() as playwright,
    ):
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)

        expect(page.locator("#overall-state-label")).to_have_text("OPERATIONAL")
        expect(page.locator("#input-count")).to_have_text("12")
        expect(page.locator("#accepted-count")).to_have_text("11")

        page.locator("#status-filter").select_option("DELIVERED")
        expect(page.locator("#orders-body tr")).to_have_count(3)
        page.locator("#order-search").fill("CUST000008")
        expect(page.locator("#orders-body tr")).to_have_count(1)
        expect(page.locator("#orders-body")).to_contain_text("ORD0000008")

        page.locator("#order-search").fill("")
        page.locator("#status-filter").select_option("")
        page.locator("#page-size").select_option("10")
        expect(page.locator("#orders-body tr")).to_have_count(10)
        page.get_by_role("button", name="Next page").click()
        expect(page.locator("#pagination-info")).to_have_text(
            "Page 2 · 2 shown on this page"
        )
        expect(page.locator("#orders-body")).to_contain_text("ORD0000011")
        expect(page.locator("#orders-body")).to_contain_text("ORD0000012")
        browser.close()


@pytest.mark.e2e
def test_dashboard_shows_partial_data_when_quality_report_fails(run_dashboard):
    with (
        run_dashboard(FixtureOrdersService(quality_available=False)) as base_url,
        sync_playwright() as playwright,
    ):
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)

        expect(page.locator("#overall-state-label")).to_have_text("PARTIAL DATA")
        expect(page.locator("#notice")).to_contain_text(
            "Quality report could not be loaded."
        )
        expect(page.locator("#input-count")).to_have_text("12")
        expect(page.locator("#orders-body tr")).to_have_count(12)
        expect(page.locator("#quality-score")).to_have_text("--")
        browser.close()

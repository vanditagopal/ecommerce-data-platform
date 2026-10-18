import sys
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.schemas import (
    ApiErrorResponse,
    HealthResponse,
    MetricsSummaryResponse,
    OrdersPageResponse,
    QualityReportResponse,
)
from src.api.service import DataUnavailableError, OrdersDataService

BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "orders"
QUALITY_PATH = PROJECT_ROOT / "data" / "quality" / "orders_latest.json"

app = FastAPI(title="E-commerce Data Platform", version="0.1.0")
orders_service = OrdersDataService(BRONZE_PATH, QUALITY_PATH)


@app.exception_handler(DataUnavailableError)
def handle_data_unavailable(
    request: Request,
    error: DataUnavailableError,
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=503,
        content=ApiErrorResponse(detail=str(error)).model_dump(),
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="ecommerce-data-platform")


@app.get(
    "/api/v1/metrics/summary",
    response_model=MetricsSummaryResponse,
    responses={503: {"model": ApiErrorResponse}},
)
def metrics_summary() -> MetricsSummaryResponse:
    return orders_service.summary_metrics()


@app.get(
    "/api/v1/data-quality/latest",
    response_model=QualityReportResponse,
    responses={503: {"model": ApiErrorResponse}},
)
def latest_data_quality() -> QualityReportResponse:
    return orders_service.latest_quality_report()


@app.get(
    "/api/v1/orders",
    response_model=OrdersPageResponse,
    responses={503: {"model": ApiErrorResponse}},
)
def list_orders(
    page: int = Query(1, ge=1, le=10000),
    limit: int = Query(20, ge=1, le=100),
) -> OrdersPageResponse:
    return orders_service.list_orders(page, limit)


FRONTEND_PATH = PROJECT_ROOT / "frontend"
app.mount("/assets", StaticFiles(directory=FRONTEND_PATH / "assets"), name="assets")
app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)

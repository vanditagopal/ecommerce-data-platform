from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    service: str


class ApiErrorResponse(BaseModel):
    detail: str


class QualityReportResponse(BaseModel):
    input_count: int
    accepted_count: int
    rejected_count: int
    reason_counts: dict[str, int]
    reason_counts_may_overlap: bool


class MetricsSummaryResponse(BaseModel):
    input_count: int
    accepted_count: int
    rejected_count: int
    reason_counts: dict[str, int]
    bronze_row_count: int


class OrderResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    order_id: str
    customer_id: str
    order_date: datetime
    order_status: str
    total_amount: float


class OrdersPageResponse(BaseModel):
    items: list[OrderResponse]
    count: int
    page: int
    limit: int
    total: int
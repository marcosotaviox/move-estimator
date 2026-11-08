from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.analysis import PhotoAnalysis

BoxesMode = Literal["guide", "customer", "none"]


class AccessDetails(BaseModel):
    property_type: Literal["house", "apartment", "townhouse", "storage_unit"] | None = None
    floor: int | None = Field(default=None, ge=0, le=100)
    has_lift: bool | None = None
    stairs_flights: int = Field(default=0, ge=0, le=20)
    parking_distance_m: int | None = Field(default=None, ge=0, le=500)
    notes: str | None = None


class QuoteBase(BaseModel):
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    pickup_address: str | None = None
    dropoff_address: str | None = None
    move_date: date | None = None
    bedrooms: int | None = Field(default=None, ge=0, le=10)
    boxes_estimate: int | None = Field(default=None, ge=0, le=500)
    pickup_access: AccessDetails | None = None
    dropoff_access: AccessDetails | None = None


class QuoteCreate(QuoteBase):
    boxes_mode: BoxesMode = "guide"

    @model_validator(mode="after")
    def check_boxes(self):
        if self.boxes_mode == "customer" and self.boxes_estimate is None:
            raise ValueError("boxes_estimate is required when boxes_mode is 'customer'")
        return self


class QuoteUpdate(QuoteBase):
    boxes_mode: BoxesMode | None = None


class QuoteSummary(BaseModel):
    furniture_volume_m3: float
    boxes_mode: BoxesMode
    boxes_min: int
    boxes_max: int
    boxes_volume_min_m3: float
    boxes_volume_max_m3: float
    packing_allowance: float
    estimated_min_m3: float
    estimated_max_m3: float
    estimated_volume_m3: float
    suggested_truck: str
    items_needing_customer_input: int
    is_complete: bool


class QuoteItemOut(BaseModel):
    id: UUID
    photo_id: UUID | None = None
    room: str
    name: str
    brand_model: str | None = None
    quantity: int
    shape: str | None = None
    heavy: bool = False
    will_dismantle: bool = False
    volume_m3: float | None = None
    raw_volume_m3: float | None = None
    effective_volume_m3: float | None = None
    measure_source: str | None = None
    source_url: str | None = None
    confidence: float | None = None
    needs_customer_input: bool = False
    notes: str | None = None


class QuoteOut(BaseModel):
    id: UUID
    company_id: UUID
    status: str
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    pickup_address: str | None = None
    dropoff_address: str | None = None
    move_date: date | None = None
    bedrooms: int | None = None
    boxes_mode: BoxesMode
    boxes_estimate: int | None = None
    boxes_actual: int | None = None
    pickup_access: dict = {}
    dropoff_access: dict = {}
    created_at: datetime
    items: list[QuoteItemOut]
    summary: QuoteSummary


class PhotoUploadResult(BaseModel):
    photo_id: UUID
    analysis: PhotoAnalysis
    summary: QuoteSummary
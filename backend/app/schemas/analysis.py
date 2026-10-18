from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Dimensions(BaseModel):
    width_cm: float
    depth_cm: float
    height_cm: float


class VisionItem(BaseModel):
    """Raw item as returned by the AI."""

    name: str
    catalog_name: str | None = None
    brand_model: str | None = None
    quantity: int = Field(default=1, ge=1)
    confidence: float = Field(ge=0, le=1)
    estimated_dimensions: Dimensions | None = None
    notes: str | None = None


class AnalysedItem(BaseModel):
    """Item after matching against the catalog and web lookup."""

    name: str
    room: str
    quantity: int
    brand_model: str | None = None
    confidence: float
    catalog_item_id: UUID | None = None
    catalog_name: str | None = None
    unit_volume_m3: float | None = None
    total_volume_m3: float | None = None
    dismantlable: bool = False
    heavy: bool = False
    measure_source: Literal["table", "web"] | None = None
    dimensions: Dimensions | None = None
    matched_product: str | None = None
    match_type: Literal["exact", "similar"] | None = None
    source_url: str | None = None
    needs_lookup: bool = False
    needs_customer_input: bool = False
    estimated_dimensions: Dimensions | None = None
    notes: str | None = None


class PhotoAnalysis(BaseModel):
    room: str
    items: list[AnalysedItem]
    matched_volume_m3: float
    items_needing_lookup: int
    items_needing_customer_input: int
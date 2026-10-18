from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Shape = Literal["solid", "irregular", "stackable"]


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
    shape: Shape = "solid"
    heavy: bool = False
    dismantlable: bool = False
    confidence: float = Field(ge=0, le=1)
    estimated_dimensions: Dimensions | None = None
    notes: str | None = None


class AnalysedItem(BaseModel):
    """Item after catalog matching, web lookup and volume calculation."""

    name: str
    room: str
    quantity: int
    brand_model: str | None = None
    confidence: float
    shape: Shape = "solid"
    heavy: bool = False
    dismantlable: bool = False
    will_dismantle: bool = False

    catalog_item_id: UUID | None = None
    catalog_name: str | None = None
    measure_source: Literal["table", "web"] | None = None

    unit_volume_m3: float | None = None
    dismantled_unit_volume_m3: float | None = None
    raw_volume_m3: float | None = None
    effective_volume_m3: float | None = None

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
    raw_volume_m3: float
    effective_volume_m3: float
    items_needing_lookup: int
    items_needing_customer_input: int
from typing import Literal

from pydantic import BaseModel, Field


class LookupResult(BaseModel):
    found: bool
    match_type: Literal["exact", "similar"] | None = None
    product_name: str | None = None
    width_cm: float | None = None
    depth_cm: float | None = None
    height_cm: float | None = None
    source_url: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
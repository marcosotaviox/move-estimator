from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class CatalogItem(BaseModel):
    id: UUID
    name: str
    category: str
    aliases: list[str] = []
    volume_m3: float
    dismantlable: bool = False
    dismantled_volume_m3: float | None = None
    heavy: bool = False
    width_cm: float | None = None
    depth_cm: float | None = None
    height_cm: float | None = None
    source: str
    source_url: str | None = None
    verified: bool = True


class CatalogMatch(BaseModel):
    item: CatalogItem
    score: float
    matched_on: Literal["name", "alias", "fuzzy"]
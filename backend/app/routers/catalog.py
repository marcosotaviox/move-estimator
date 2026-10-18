from fastapi import APIRouter, HTTPException, Query

from app.schemas.catalog import CatalogItem, CatalogMatch
from app.services.catalog_service import list_items, match_item

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=list[CatalogItem])
def get_catalog(category: str | None = None):
    return list_items(category)


@router.get("/match", response_model=CatalogMatch)
def get_match(q: str = Query(..., min_length=2)):
    result = match_item(q)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No catalog match for '{q}'")
    return result
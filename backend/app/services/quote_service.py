import logging
import math
import uuid
from uuid import UUID

from app.core import estimation as est
from app.core.supabase import get_supabase
from app.schemas.analysis import AnalysedItem
from app.schemas.quotes import (
    PhotoUploadResult,
    QuoteCreate,
    QuoteItemOut,
    QuoteOut,
    QuoteSummary,
    QuoteUpdate,
)
from app.services.analysis_service import analyse_photo
from app.services.image_service import to_jpeg

logger = logging.getLogger(__name__)

PHOTO_BUCKET = "quote-photos"


class CompanyNotFoundError(LookupError):
    pass


class QuoteNotFoundError(LookupError):
    pass


class InvalidQuoteError(ValueError):
    pass


# --- Database helpers ---

def _get_company_id(slug: str) -> str:
    response = get_supabase().table("companies").select("id").eq("slug", slug).limit(1).execute()
    if not response.data:
        raise CompanyNotFoundError(slug)
    return response.data[0]["id"]


def _get_quote_row(quote_id: UUID | str) -> dict:
    response = get_supabase().table("quotes").select("*").eq("id", str(quote_id)).limit(1).execute()
    if not response.data:
        raise QuoteNotFoundError(str(quote_id))
    return response.data[0]


def _get_item_rows(quote_id: UUID | str) -> list[dict]:
    response = (
        get_supabase()
        .table("quote_items")
        .select("*")
        .eq("quote_id", str(quote_id))
        .order("created_at")
        .execute()
    )
    return response.data


def _item_row(item: AnalysedItem, quote_id: UUID | str, photo_id: UUID) -> dict:
    dims = item.dimensions
    return {
        "quote_id": str(quote_id),
        "photo_id": str(photo_id),
        "catalog_item_id": str(item.catalog_item_id) if item.catalog_item_id else None,
        "room": item.room,
        "name": item.name,
        "brand_model": item.brand_model,
        "quantity": item.quantity,
        "volume_m3": item.unit_volume_m3,
        "dismantled_unit_volume_m3": item.dismantled_unit_volume_m3,
        "width_cm": dims.width_cm if dims else None,
        "depth_cm": dims.depth_cm if dims else None,
        "height_cm": dims.height_cm if dims else None,
        "will_dismantle": item.will_dismantle,
        "heavy": item.heavy,
        "shape": item.shape,
        "raw_volume_m3": item.raw_volume_m3,
        "effective_volume_m3": item.effective_volume_m3,
        "measure_source": item.measure_source,
        "source_url": item.source_url,
        "confidence": item.confidence,
        "needs_customer_input": item.needs_customer_input,
        "notes": item.notes,
    }


# --- Estimate ---

def _boxes_range(quote: dict) -> tuple[int, int]:
    mode = quote.get("boxes_mode") or "guide"

    if mode == "none":
        return 0, 0

    if mode == "customer":
        count = quote.get("boxes_estimate") or 0
        margin = est.CUSTOMER_BOXES_MARGIN
        return math.floor(count * (1 - margin)), math.ceil(count * (1 + margin))

    bedrooms = quote.get("bedrooms")
    if bedrooms is None:
        return 0, 0
    return est.box_guide(bedrooms)


def compute_summary(quote: dict, items: list[dict]) -> QuoteSummary:
    furniture = sum(float(item.get("effective_volume_m3") or 0) for item in items)

    boxes_min, boxes_max = _boxes_range(quote)
    boxes_volume_min = boxes_min * est.BOX_VOLUME_M3
    boxes_volume_max = boxes_max * est.BOX_VOLUME_M3

    allowance = float(quote.get("packing_allowance") or est.DEFAULT_PACKING_ALLOWANCE)
    margin = est.FURNITURE_RANGE_MARGIN

    low = (furniture * (1 - margin) + boxes_volume_min) * (1 + allowance)
    high = (furniture * (1 + margin) + boxes_volume_max) * (1 + allowance)

    missing_inputs = sum(1 for item in items if item.get("needs_customer_input"))
    mode = quote.get("boxes_mode") or "guide"
    missing_bedrooms = mode == "guide" and quote.get("bedrooms") is None

    return QuoteSummary(
        furniture_volume_m3=round(furniture, 2),
        boxes_mode=mode,
        boxes_min=boxes_min,
        boxes_max=boxes_max,
        boxes_volume_min_m3=round(boxes_volume_min, 2),
        boxes_volume_max_m3=round(boxes_volume_max, 2),
        packing_allowance=allowance,
        estimated_min_m3=round(low, 1),
        estimated_max_m3=round(high, 1),
        estimated_volume_m3=round((low + high) / 2, 1),
        suggested_truck=est.suggest_truck(high),
        items_needing_customer_input=missing_inputs,
        is_complete=bool(items) and missing_inputs == 0 and not missing_bedrooms,
    )


def refresh_estimate(quote_id: UUID | str) -> QuoteSummary:
    """Recalculate the totals and store them on the quote."""
    quote = _get_quote_row(quote_id)
    summary = compute_summary(quote, _get_item_rows(quote_id))

    get_supabase().table("quotes").update(
        {
            "furniture_volume_m3": summary.furniture_volume_m3,
            "estimated_min_m3": summary.estimated_min_m3,
            "estimated_max_m3": summary.estimated_max_m3,
            "estimated_volume_m3": summary.estimated_volume_m3,
            "suggested_truck": summary.suggested_truck,
        }
    ).eq("id", str(quote_id)).execute()

    return summary


# --- Public operations ---

def get_quote(quote_id: UUID | str) -> QuoteOut:
    quote = _get_quote_row(quote_id)
    items = _get_item_rows(quote_id)
    return QuoteOut(
        **quote,
        items=[QuoteItemOut(**item) for item in items],
        summary=compute_summary(quote, items),
    )


def create_quote(company_slug: str, data: QuoteCreate) -> QuoteOut:
    row = data.model_dump(mode="json", exclude_none=True)
    row["company_id"] = _get_company_id(company_slug)

    response = get_supabase().table("quotes").insert(row).execute()
    quote_id = response.data[0]["id"]

    refresh_estimate(quote_id)
    return get_quote(quote_id)


def update_quote(quote_id: UUID, data: QuoteUpdate) -> QuoteOut:
    current = _get_quote_row(quote_id)
    changes = data.model_dump(mode="json", exclude_unset=True)

    mode = changes.get("boxes_mode", current.get("boxes_mode"))
    estimate = changes.get("boxes_estimate", current.get("boxes_estimate"))
    if mode == "customer" and estimate is None:
        raise InvalidQuoteError("boxes_estimate is required when boxes_mode is 'customer'")

    if changes:
        get_supabase().table("quotes").update(changes).eq("id", str(quote_id)).execute()

    refresh_estimate(quote_id)
    return get_quote(quote_id)


def add_photo(quote_id: UUID, data: bytes, room: str) -> PhotoUploadResult:
    _get_quote_row(quote_id)  # make sure the quote exists before doing any work

    client = get_supabase()
    jpeg = to_jpeg(data)
    photo_id = uuid.uuid4()
    path = f"{quote_id}/{photo_id}.jpg"

    # 1. Store the photo first, so it is never lost even if the AI fails
    client.storage.from_(PHOTO_BUCKET).upload(path, jpeg, {"content-type": "image/jpeg"})
    client.table("quote_photos").insert(
        {"id": str(photo_id), "quote_id": str(quote_id), "room": room, "storage_path": path}
    ).execute()

    # 2. Analyse and save the items
    analysis = analyse_photo(jpeg, room)
    rows = [_item_row(item, quote_id, photo_id) for item in analysis.items]
    if rows:
        client.table("quote_items").insert(rows).execute()

    client.table("quote_photos").update({"analysed": True}).eq("id", str(photo_id)).execute()

    # 3. Recalculate totals
    summary = refresh_estimate(quote_id)
    return PhotoUploadResult(photo_id=photo_id, analysis=analysis, summary=summary)
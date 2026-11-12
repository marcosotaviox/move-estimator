import logging
import math
import uuid
from datetime import datetime, timezone
from uuid import UUID

from app.core import estimation as est
from app.core.supabase import get_supabase
from app.schemas.analysis import AnalysedItem, Dimensions
from app.schemas.catalog import CatalogItem
from app.schemas.quotes import (
    PhotoUploadResult,
    QuoteCreate,
    QuoteItemCreate,
    QuoteItemOut,
    QuoteItemUpdate,
    QuoteOut,
    QuoteSummary,
    QuoteUpdate,
)
from app.services.analysis_service import analyse_photo
from app.services.catalog_service import add_web_item, get_item, match_item
from app.services.image_service import to_jpeg
from app.services.lookup_service import lookup_dimensions

logger = logging.getLogger(__name__)

PHOTO_BUCKET = "quote-photos"


# --- Errors (mapped to HTTP status codes in main.py) ---

class CompanyNotFoundError(LookupError):
    pass


class QuoteNotFoundError(LookupError):
    pass


class ItemNotFoundError(LookupError):
    pass


class QuoteLockedError(RuntimeError):
    pass


class InvalidQuoteError(ValueError):
    pass


class SubmissionError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("Quote is not ready to submit")
        self.problems = problems


# --- Database helpers ---

def _get_company_id(slug: str) -> str:
    response = get_supabase().table("companies").select("id").eq("slug", slug).limit(1).execute()
    if not response.data:
        raise CompanyNotFoundError(f"Company '{slug}' not found")
    return response.data[0]["id"]


def _get_quote_row(quote_id: UUID | str) -> dict:
    response = get_supabase().table("quotes").select("*").eq("id", str(quote_id)).limit(1).execute()
    if not response.data:
        raise QuoteNotFoundError("Quote not found")
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


def _get_item_row(quote_id: UUID | str, item_id: UUID | str) -> dict:
    response = (
        get_supabase()
        .table("quote_items")
        .select("*")
        .eq("id", str(item_id))
        .eq("quote_id", str(quote_id))
        .limit(1)
        .execute()
    )
    if not response.data:
        raise ItemNotFoundError("Item not found")
    return response.data[0]


def _ensure_editable(quote: dict) -> None:
    if quote.get("status") != "draft":
        raise QuoteLockedError("This quote has already been submitted and can no longer be changed")


# --- Item field builders ---

def _catalog_fields(catalog_item: CatalogItem) -> dict:
    return {
        "catalog_item_id": str(catalog_item.id),
        "volume_m3": catalog_item.volume_m3,
        "dismantled_unit_volume_m3": catalog_item.dismantled_volume_m3,
        "width_cm": catalog_item.width_cm,
        "depth_cm": catalog_item.depth_cm,
        "height_cm": catalog_item.height_cm,
        "heavy": catalog_item.heavy,
        "measure_source": "table",
        "source_url": catalog_item.source_url,
        "needs_customer_input": False,
    }


def _dimension_fields(dims: Dimensions, source: str = "customer", source_url: str | None = None) -> dict:
    return {
        "catalog_item_id": None,
        "volume_m3": round(dims.width_cm * dims.depth_cm * dims.height_cm / 1_000_000, 3),
        "dismantled_unit_volume_m3": None,
        "width_cm": dims.width_cm,
        "depth_cm": dims.depth_cm,
        "height_cm": dims.height_cm,
        "measure_source": source,
        "source_url": source_url,
        "needs_customer_input": False,
    }


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
        "confirmed": False,
        "needs_customer_input": item.needs_customer_input,
        "notes": item.notes,
    }


def _needs_confirmation(item: dict) -> bool:
    confidence = item.get("confidence")
    return (
        confidence is not None
        and float(confidence) < est.CONFIRMATION_THRESHOLD
        and not item.get("confirmed")
    )


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
    missing_confirmations = sum(1 for item in items if _needs_confirmation(item))
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
        items_needing_confirmation=missing_confirmations,
        is_complete=bool(items) and missing_inputs == 0 and missing_confirmations == 0 and not missing_bedrooms,
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


# --- Quotes ---

def get_quote(quote_id: UUID | str) -> QuoteOut:
    quote = _get_quote_row(quote_id)
    items = _get_item_rows(quote_id)
    return QuoteOut(
        **quote,
        items=[QuoteItemOut(**item, needs_confirmation=_needs_confirmation(item)) for item in items],
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
    _ensure_editable(current)
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
    _ensure_editable(_get_quote_row(quote_id))

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


# --- Item review ---

def add_item(quote_id: UUID, data: QuoteItemCreate) -> QuoteOut:
    """Manual item. Same three levels as photos: table, web, then customer measurements."""
    _ensure_editable(_get_quote_row(quote_id))

    row: dict = {
        "quote_id": str(quote_id),
        "room": data.room,
        "quantity": data.quantity,
        "shape": data.shape,
        "confidence": 1.0,
        "confirmed": True,
        "heavy": False,
        "needs_customer_input": False,
    }
    default_dismantle = False

    if data.catalog_item_id:
        catalog_item = get_item(data.catalog_item_id)
        if catalog_item is None:
            raise InvalidQuoteError("Catalog item not found")
        row.update(_catalog_fields(catalog_item))
        row["name"] = data.name or catalog_item.name
        default_dismantle = catalog_item.dismantlable

    elif data.dimensions:
        row.update(_dimension_fields(data.dimensions))
        row["name"] = data.name

    else:
        row["name"] = data.name
        match = match_item(data.name)
        if match:
            row.update(_catalog_fields(match.item))
            default_dismantle = match.item.dismantlable
        else:
            result = lookup_dimensions(data.name)
            if result.found:
                dims = Dimensions(width_cm=result.width_cm, depth_cm=result.depth_cm, height_cm=result.height_cm)
                row.update(_dimension_fields(dims, source="web", source_url=result.source_url))
                saved = add_web_item(
                    name=result.product_name or data.name,
                    alias=data.name,
                    volume_m3=row["volume_m3"],
                    dimensions=dims,
                    source_url=result.source_url,
                )
                if saved:
                    row["catalog_item_id"] = str(saved.id)
            else:
                row["needs_customer_input"] = True

    will_dismantle = data.will_dismantle if data.will_dismantle is not None else default_dismantle
    row["will_dismantle"] = will_dismantle

    raw, effective = est.item_volumes(
        row.get("volume_m3"), row.get("dismantled_unit_volume_m3"), data.shape, will_dismantle, data.quantity
    )
    row["raw_volume_m3"] = raw
    row["effective_volume_m3"] = effective

    get_supabase().table("quote_items").insert(row).execute()
    refresh_estimate(quote_id)
    return get_quote(quote_id)


def update_item(quote_id: UUID, item_id: UUID, data: QuoteItemUpdate) -> QuoteOut:
    _ensure_editable(_get_quote_row(quote_id))
    item = _get_item_row(quote_id, item_id)
    changes = data.model_dump(exclude_none=True)

    update = {key: changes[key] for key in ("name", "room", "quantity", "shape", "will_dismantle") if key in changes}

    if data.catalog_item_id:
        catalog_item = get_item(data.catalog_item_id)
        if catalog_item is None:
            raise InvalidQuoteError("Catalog item not found")
        update.update(_catalog_fields(catalog_item))
        update["heavy"] = bool(item.get("heavy")) or catalog_item.heavy
        if data.will_dismantle is None:
            update["will_dismantle"] = catalog_item.dismantlable

    if data.dimensions:
        update.update(_dimension_fields(data.dimensions))

    # Any edit means the customer has looked at the item
    update["confirmed"] = data.confirmed if data.confirmed is not None else True

    merged = {**item, **update}
    raw, effective = est.item_volumes(
        merged.get("volume_m3"),
        merged.get("dismantled_unit_volume_m3"),
        merged.get("shape") or "solid",
        bool(merged.get("will_dismantle")),
        int(merged["quantity"]),
    )
    update["raw_volume_m3"] = raw
    update["effective_volume_m3"] = effective

    get_supabase().table("quote_items").update(update).eq("id", str(item_id)).execute()
    refresh_estimate(quote_id)
    return get_quote(quote_id)


def delete_item(quote_id: UUID, item_id: UUID) -> QuoteOut:
    _ensure_editable(_get_quote_row(quote_id))

    response = (
        get_supabase()
        .table("quote_items")
        .delete()
        .eq("id", str(item_id))
        .eq("quote_id", str(quote_id))
        .execute()
    )
    if not response.data:
        raise ItemNotFoundError("Item not found")

    refresh_estimate(quote_id)
    return get_quote(quote_id)


def submit_quote(quote_id: UUID) -> QuoteOut:
    quote = _get_quote_row(quote_id)
    _ensure_editable(quote)
    items = _get_item_rows(quote_id)
    summary = compute_summary(quote, items)

    problems: list[str] = []
    if not items:
        problems.append("Add at least one photo or item")
    if summary.items_needing_customer_input:
        problems.append(f"{summary.items_needing_customer_input} item(s) need measurements")
    if summary.items_needing_confirmation:
        problems.append(f"{summary.items_needing_confirmation} item(s) need to be confirmed")
    if summary.boxes_mode == "guide" and quote.get("bedrooms") is None:
        problems.append("Tell us how many bedrooms the property has")
    if not quote.get("customer_name"):
        problems.append("Add your name")
    if not (quote.get("customer_email") or quote.get("customer_phone")):
        problems.append("Add an email or phone number")
    if not quote.get("pickup_address"):
        problems.append("Add the pickup address")
    if not quote.get("dropoff_address"):
        problems.append("Add the drop-off address")

    if problems:
        raise SubmissionError(problems)

    get_supabase().table("quotes").update(
        {"status": "submitted", "submitted_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", str(quote_id)).execute()

    return get_quote(quote_id)
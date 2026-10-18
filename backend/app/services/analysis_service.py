from concurrent.futures import ThreadPoolExecutor

from app.core.estimation import DISMANTLED_FALLBACK_FACTOR, SHAPE_FACTORS
from app.schemas.analysis import AnalysedItem, Dimensions, PhotoAnalysis, VisionItem
from app.schemas.catalog import CatalogItem
from app.services.catalog_service import add_web_item, list_items
from app.services.image_service import prepare_image
from app.services.lookup_service import lookup_dimensions
from app.services.vision_service import identify_items

MAX_LOOKUP_WORKERS = 4


def _to_analysed(item: VisionItem, room: str, catalog_by_name: dict[str, CatalogItem]) -> AnalysedItem:
    match = catalog_by_name.get(item.catalog_name.strip().lower()) if item.catalog_name else None

    # Only dismantle when the photo agrees it comes apart.
    # If matched to the table, both the table and the AI must agree.
    dismantlable = item.dismantlable and (match.dismantlable if match else True)

    base = {
        "name": item.name,
        "room": room,
        "quantity": item.quantity,
        "brand_model": item.brand_model,
        "confidence": item.confidence,
        "shape": item.shape,
        "heavy": item.heavy or (match.heavy if match else False),
        "dismantlable": dismantlable,
        "will_dismantle": dismantlable,  # rule: if it comes apart, it gets dismantled
        "estimated_dimensions": item.estimated_dimensions,
        "notes": item.notes,
    }

    if match is None:
        return AnalysedItem(**base, needs_lookup=True)

    return AnalysedItem(
        **base,
        catalog_item_id=match.id,
        catalog_name=match.name,
        unit_volume_m3=match.volume_m3,
        dismantled_unit_volume_m3=match.dismantled_volume_m3,
        measure_source="table",
    )


def _apply_lookup(item: AnalysedItem) -> AnalysedItem:
    """Level 2: search the web. Falls back to level 3 (customer input) if nothing reliable is found."""
    result = lookup_dimensions(item.name, item.brand_model, item.estimated_dimensions)

    if not result.found:
        return item.model_copy(update={"needs_lookup": False, "needs_customer_input": True})

    dimensions = Dimensions(
        width_cm=result.width_cm,
        depth_cm=result.depth_cm,
        height_cm=result.height_cm,
    )
    unit_volume = round(dimensions.width_cm * dimensions.depth_cm * dimensions.height_cm / 1_000_000, 3)
    product_name = result.product_name or item.name

    saved = add_web_item(
        name=product_name,
        alias=item.name,
        volume_m3=unit_volume,
        dimensions=dimensions,
        source_url=result.source_url,
    )

    return item.model_copy(
        update={
            "catalog_item_id": saved.id if saved else None,
            "catalog_name": saved.name if saved else None,
            "unit_volume_m3": unit_volume,
            "measure_source": "web",
            "dimensions": dimensions,
            "matched_product": product_name,
            "match_type": result.match_type,
            "source_url": result.source_url,
            "needs_lookup": False,
        }
    )


def _with_volumes(item: AnalysedItem) -> AnalysedItem:
    """Raw volume = assembled size. Effective volume = real truck space after dismantling or filling gaps."""
    if item.unit_volume_m3 is None:
        return item

    if item.will_dismantle:
        effective_unit = item.dismantled_unit_volume_m3 or item.unit_volume_m3 * DISMANTLED_FALLBACK_FACTOR
    else:
        effective_unit = item.unit_volume_m3 * SHAPE_FACTORS[item.shape]

    return item.model_copy(
        update={
            "raw_volume_m3": round(item.unit_volume_m3 * item.quantity, 3),
            "effective_volume_m3": round(effective_unit * item.quantity, 3),
        }
    )


def analyse_photo(data: bytes, room: str) -> PhotoAnalysis:
    image_b64 = prepare_image(data)

    catalog = list_items()
    catalog_by_name = {entry.name.lower(): entry for entry in catalog}

    vision_items = identify_items(image_b64, room, [entry.name for entry in catalog])
    analysed = [_to_analysed(item, room, catalog_by_name) for item in vision_items]

    # Level 2: web lookups, run in parallel
    pending = [index for index, item in enumerate(analysed) if item.needs_lookup]
    if pending:
        with ThreadPoolExecutor(max_workers=MAX_LOOKUP_WORKERS) as pool:
            results = list(pool.map(_apply_lookup, [analysed[index] for index in pending]))
        for index, result in zip(pending, results):
            analysed[index] = result

    analysed = [_with_volumes(item) for item in analysed]

    return PhotoAnalysis(
        room=room,
        items=analysed,
        raw_volume_m3=round(sum(item.raw_volume_m3 or 0 for item in analysed), 2),
        effective_volume_m3=round(sum(item.effective_volume_m3 or 0 for item in analysed), 2),
        items_needing_lookup=sum(1 for item in analysed if item.needs_lookup),
        items_needing_customer_input=sum(1 for item in analysed if item.needs_customer_input),
    )
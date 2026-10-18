import logging

import anthropic
from pydantic import ValidationError

from app.core.anthropic_client import get_anthropic
from app.core.config import get_settings
from app.schemas.analysis import Dimensions
from app.schemas.lookup import LookupResult

logger = logging.getLogger(__name__)

MIN_CM = 1
MAX_CM = 600

SYSTEM_PROMPT = """You find real product dimensions for a furniture removal company in Australia.

Use web_search to find the item's dimensions:
- If a brand or model is given, find that exact product (match_type "exact").
- Otherwise find a very similar product commonly sold in Australia, e.g. IKEA, Freedom, Fantastic Furniture, Amart, Harvey Norman, The Good Guys, Temple & Webster (match_type "similar").
- Prefer retailer or manufacturer product pages. Use the size closest to the rough size given, if any.
- Convert everything to centimetres. width = longest horizontal side, depth = the other horizontal side, height = vertical.

When done, call report_dimensions exactly once. Never reply with plain text.
If you cannot find reliable dimensions, call report_dimensions with found = false."""

REPORT_TOOL = {
    "name": "report_dimensions",
    "description": "Report the dimensions found for the item. Must always be called once.",
    "input_schema": {
        "type": "object",
        "properties": {
            "found": {"type": "boolean"},
            "match_type": {"type": ["string", "null"], "enum": ["exact", "similar", None]},
            "product_name": {"type": ["string", "null"]},
            "width_cm": {"type": ["number", "null"]},
            "depth_cm": {"type": ["number", "null"]},
            "height_cm": {"type": ["number", "null"]},
            "source_url": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["found", "confidence"],
    },
}

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}


def _describe(name: str, brand_model: str | None, estimated: Dimensions | None) -> str:
    lines = [f"Item: {name}"]
    if brand_model:
        lines.append(f"Brand/model seen in photo: {brand_model}")
    if estimated:
        lines.append(
            f"Rough size from photo (W x D x H): "
            f"{estimated.width_cm} x {estimated.depth_cm} x {estimated.height_cm} cm"
        )
    lines.append("\nFind its real dimensions and call report_dimensions.")
    return "\n".join(lines)


def _has_sane_dimensions(result: LookupResult) -> bool:
    sides = [result.width_cm, result.depth_cm, result.height_cm]
    return all(side is not None and MIN_CM <= side <= MAX_CM for side in sides)


def lookup_dimensions(
    name: str,
    brand_model: str | None = None,
    estimated: Dimensions | None = None,
) -> LookupResult:
    """Search the web for an item's dimensions. Never raises: returns found=False on any failure."""
    not_found = LookupResult(found=False)

    try:
        response = get_anthropic().messages.create(
            model=get_settings().anthropic_model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=[WEB_SEARCH_TOOL, REPORT_TOOL],
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": _describe(name, brand_model, estimated)}],
        )
    except anthropic.APIError:
        logger.exception("Web lookup failed for '%s'", name)
        return not_found

    for block in response.content:
        if block.type == "tool_use" and block.name == "report_dimensions":
            try:
                result = LookupResult.model_validate(block.input)
            except ValidationError:
                logger.warning("Invalid lookup result for '%s': %s", name, block.input)
                return not_found

            if result.found and _has_sane_dimensions(result):
                return result

            logger.info("No reliable dimensions for '%s'", name)
            return not_found

    logger.info("Lookup for '%s' ended without a report (stop_reason=%s)", name, response.stop_reason)
    return not_found
import logging

from pydantic import ValidationError

from app.core.anthropic_client import get_anthropic
from app.core.config import get_settings
from app.schemas.analysis import VisionItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an experienced furniture removalist in Australia estimating moves from customer photos.

Always answer by calling the report_items tool exactly once. Never reply with plain text.

What to report (only items that go on the truck loose, not inside a box):
- Furniture: sofas, beds, mattresses, tables, chairs, wardrobes, drawers, shelving, desks, cabinets.
- Appliances: fridges, freezers, washing machines, dryers, dishwashers, TVs.
- Large loose items: exercise equipment, BBQs, bikes, mowers, outdoor furniture, large pot plants, floor lamps, large mirrors and artwork, rugs.

Do NOT report:
- Small loose items that get packed into boxes: books, ornaments, table lamps, kitchenware, clothes, shoes, toys, small electronics,
  computer monitors, small plants, anything sitting on top of or inside furniture.
- Packing boxes, bags or suitcases. Boxes are estimated separately.
- Anything built in or fixed: kitchen cabinets, built-in wardrobes, ceiling fans, fixed lights, curtains, blinds, toilets, sinks.

Counting:
- Group identical items into one entry with a quantity (e.g. 6 matching dining chairs = quantity 6).
- Never count the same item twice. Include partially visible items only if you can tell what they are.
- If the photo has no reportable items, call report_items with an empty list.

Beds:
- Tell apart a bed frame (headboard, side rails, legs, timber or metal) from an ensemble base (fabric-covered box base).
- Always report the mattress as a separate item.

Fields:
- catalog_name: copy the exact name from the catalog list when the item fits it. Use null if nothing fits well.
- brand_model: only if a label, logo or very distinctive design is clearly visible. Never guess.
- shape:
  - "solid": box-like, nothing fits around or inside it (fridge, wardrobe, washing machine, chest of drawers, ensemble base, mattress).
  - "irregular": legs, gaps or odd shapes where small items can fill the space (exercise bike, tables, armchairs, BBQ, office chair).
  - "stackable": stacks or nests with identical items (dining chairs, stools, plastic outdoor chairs).
- dismantlable: true if this item comes apart for moving (bed frames, bunk beds, most wardrobes, large dining tables, desks, bookcases, cots).
  False for ensemble bases, mattresses and one-piece items that clearly do not come apart.
- heavy: true if it needs two or more people or special care because of weight (fridges, washing machines, pianos, safes, treadmills,
  flywheel exercise bikes, solid timber or marble furniture).
- estimated_dimensions: only when catalog_name is null. Your best estimate in centimetres, assembled.
- confidence: 0 to 1, how sure you are about what the item is.
- notes: anything a removalist should know (glass top, fragile, very heavy, tight fit)."""

REPORT_TOOL = {
    "name": "report_items",
    "description": "Report every furniture item, appliance and large loose item in the photo. Must always be called.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Short plain description, e.g. 'grey fabric 3 seater sofa'",
                        },
                        "catalog_name": {"type": ["string", "null"]},
                        "brand_model": {"type": ["string", "null"]},
                        "quantity": {"type": "integer", "minimum": 1},
                        "shape": {"type": "string", "enum": ["solid", "irregular", "stackable"]},
                        "heavy": {"type": "boolean"},
                        "dismantlable": {"type": "boolean"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "estimated_dimensions": {
                            "type": ["object", "null"],
                            "properties": {
                                "width_cm": {"type": "number"},
                                "depth_cm": {"type": "number"},
                                "height_cm": {"type": "number"},
                            },
                            "required": ["width_cm", "depth_cm", "height_cm"],
                        },
                        "notes": {"type": ["string", "null"]},
                    },
                    "required": [
                        "name",
                        "catalog_name",
                        "quantity",
                        "shape",
                        "heavy",
                        "dismantlable",
                        "confidence",
                    ],
                },
            }
        },
        "required": ["items"],
    },
}


class VisionError(RuntimeError):
    pass


def identify_items(image_b64: str, room: str, catalog_names: list[str]) -> list[VisionItem]:
    settings = get_settings()
    catalog_text = "\n".join(f"- {name}" for name in catalog_names)

    response = get_anthropic().messages.create(
        model=settings.anthropic_model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[REPORT_TOOL],
        tool_choice={"type": "auto"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Room: {room}\n\n"
                            f"Catalog items:\n{catalog_text}\n\n"
                            "Identify every furniture item, appliance and large loose item, "
                            "and report them by calling report_items."
                        ),
                    },
                ],
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "report_items":
            items: list[VisionItem] = []
            for raw in block.input.get("items", []):
                try:
                    items.append(VisionItem.model_validate(raw))
                except ValidationError:
                    logger.warning("Skipping invalid item from model: %s", raw)
            return items

    logger.warning("Model replied without calling report_items: %s", response.content)
    raise VisionError("Model did not return an item list")
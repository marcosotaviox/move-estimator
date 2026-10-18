import logging
from difflib import SequenceMatcher

from app.core.supabase import get_supabase
from app.schemas.analysis import Dimensions
from app.schemas.catalog import CatalogItem, CatalogMatch

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 0.8


def _normalize(text: str) -> str:
    """Lowercase, swap separators for spaces and collapse whitespace."""
    cleaned = text.lower().replace("/", " ").replace("-", " ")
    return " ".join(cleaned.split())


def list_items(category: str | None = None) -> list[CatalogItem]:
    query = get_supabase().table("item_catalog").select("*")
    if category:
        query = query.eq("category", category)
    response = query.order("category").order("name").execute()
    return [CatalogItem(**row) for row in response.data]


def match_item(name: str) -> CatalogMatch | None:
    """Find the best catalog item for a given item name.

    Order: exact name > exact alias > fuzzy match above threshold.
    Returns None when nothing is close enough.
    """
    query = _normalize(name)
    if not query:
        return None

    items = list_items()

    # 1. Exact name
    for item in items:
        if _normalize(item.name) == query:
            return CatalogMatch(item=item, score=1.0, matched_on="name")

    # 2. Exact alias
    for item in items:
        if query in (_normalize(alias) for alias in item.aliases):
            return CatalogMatch(item=item, score=0.95, matched_on="alias")

    # 3. Fuzzy match against names and aliases
    best: CatalogMatch | None = None
    for item in items:
        for candidate in [item.name, *item.aliases]:
            score = SequenceMatcher(None, query, _normalize(candidate)).ratio()
            if best is None or score > best.score:
                best = CatalogMatch(item=item, score=round(score, 2), matched_on="fuzzy")

    if best and best.score >= FUZZY_THRESHOLD:
        return best
    return None


def add_web_item(
    name: str,
    alias: str,
    volume_m3: float,
    dimensions: Dimensions,
    source_url: str | None,
) -> CatalogItem | None:
    """Save an item found online so future photos match it straight from the table.

    Never overwrites an existing entry. Returns None if saving fails,
    because a failed save must not break the photo analysis.
    """
    client = get_supabase()

    try:
        existing = client.table("item_catalog").select("*").eq("name", name).limit(1).execute()
        if existing.data:
            return CatalogItem(**existing.data[0])

        row = {
            "name": name,
            "category": "other",
            "aliases": [alias] if alias.lower() != name.lower() else [],
            "volume_m3": volume_m3,
            "width_cm": dimensions.width_cm,
            "depth_cm": dimensions.depth_cm,
            "height_cm": dimensions.height_cm,
            "source": "web",
            "source_url": source_url,
            "verified": False,
        }
        inserted = client.table("item_catalog").insert(row).execute()
        return CatalogItem(**inserted.data[0])
    except Exception:
        logger.exception("Could not save web item '%s' to catalog", name)
        return None
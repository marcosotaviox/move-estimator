from difflib import SequenceMatcher

from app.core.supabase import get_supabase
from app.schemas.catalog import CatalogItem, CatalogMatch

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
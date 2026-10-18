from functools import lru_cache

import anthropic

from app.core.config import get_settings


@lru_cache
def get_anthropic() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase() -> Client:
    """Single Supabase client for the whole app, using the service role key.

    Service role bypasses RLS, so this client must only ever run on the backend.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
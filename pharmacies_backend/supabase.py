from django.conf import settings
from supabase import Client, create_client


def get_supabase_client(use_service_role: bool = False) -> Client:
    """Create a Supabase client using anon or service-role credentials."""
    key = settings.SUPABASE_SERVICE_ROLE_KEY if use_service_role else settings.SUPABASE_ANON_KEY
    if not settings.SUPABASE_URL or not key:
        raise ValueError('Supabase URL/key not configured in environment variables.')
    return create_client(settings.SUPABASE_URL, key)

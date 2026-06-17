import httpx
from app.config import settings


def _headers() -> dict:
    return {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {settings.supabase_anon_key}",
        "Content-Type": "application/json",
    }


async def init_db() -> None:
    """Verify Supabase connection is reachable on startup."""
    if not settings.supabase_url or not settings.supabase_anon_key:
        print("[DB] WARNING: SUPABASE_URL or SUPABASE_ANON_KEY not set — call history will not be saved.")
        return
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/clients?limit=1",
                headers=_headers(),
            )
        if resp.is_success:
            print("[DB] Supabase connection OK.")
        else:
            print(f"[DB] Supabase check failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[DB] Supabase unreachable: {e}")

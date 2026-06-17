import httpx
from datetime import datetime, timedelta, timezone

CAL_API_BASE    = "https://api.cal.com/v2"
CAL_API_VERSION = "2024-08-13"

_BASE_HEADERS = {"cal-api-version": CAL_API_VERSION}


async def fetch_slots(event_type_id: int, api_key: str, tz: str) -> list[str]:
    """Return up to 20 available slot start-times over the next 14 days."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=14)
    params = {
        "eventTypeId": str(event_type_id),
        "startTime":   now.isoformat(),
        "endTime":     end.isoformat(),
        "timeZone":    tz,
    }
    headers = {**_BASE_HEADERS, "Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{CAL_API_BASE}/slots/available",
            params=params,
            headers=headers,
        )

    print(f"[Cal] slots status={resp.status_code}")
    print(f"[Cal] slots body={resp.text[:500]}")

    if not resp.is_success:
        return []

    return _parse_slots(resp.json())


async def debug_slots(event_type_id: int, api_key: str, tz: str) -> dict:
    """Return the raw Cal.com response — used by the /debug/cal endpoint."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=14)
    params = {
        "eventTypeId": str(event_type_id),
        "startTime":   now.isoformat(),
        "endTime":     end.isoformat(),
        "timeZone":    tz,
    }
    headers = {**_BASE_HEADERS, "Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{CAL_API_BASE}/slots/available",
            params=params,
            headers=headers,
        )

    parsed = []
    if resp.is_success:
        parsed = _parse_slots(resp.json())

    return {
        "status_code": resp.status_code,
        "raw":         resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
        "parsed_slots": parsed,
        "params_sent":  params,
    }


def _parse_slots(data: dict) -> list[str]:
    """
    Cal.com returns slots in one of two shapes depending on API version:

    Shape A  (/slots/available, cal-api-version 2024-08-13):
      { "data": { "slots": { "2026-06-17": [{"time": "..."}, ...] } } }

    Shape B  (/slots, cal-api-version 2024-09-04):
      { "data": { "2026-06-17": [{"start": "..."}, ...] } }

    We handle both by trying Shape A first, falling back to Shape B.
    """
    inner = data.get("data", {})

    # Shape A — nested under "slots"
    slots_obj = inner.get("slots") if isinstance(inner, dict) else None

    # Shape B — dates sit directly on "data"
    if not slots_obj:
        slots_obj = inner

    if not isinstance(slots_obj, dict):
        print(f"[Cal] unexpected slots structure: {data}")
        return []

    flat = []
    for day_slots in slots_obj.values():
        if not isinstance(day_slots, list):
            continue
        for s in day_slots:
            t = s.get("time") or s.get("start")
            if t:
                flat.append(t)

    return flat[:20]


async def create_booking(
    event_type_id: int,
    api_key: str,
    slot_time: str,
    attendee_name: str,
    attendee_email: str,
    timezone_str: str,
) -> dict:
    headers = {
        **_BASE_HEADERS,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "eventTypeId": event_type_id,
        "start": slot_time,
        "attendee": {
            "name":     attendee_name,
            "email":    attendee_email,
            "timeZone": timezone_str,
            "language": "en",
        },
        "metadata": {"source": "voicedesk"},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{CAL_API_BASE}/bookings",
            json=body,
            headers=headers,
        )

    print(f"[Cal] booking status={resp.status_code} body={resp.text[:300]}")

    if not resp.is_success:
        return {"ok": False}

    result  = resp.json()
    booking = result.get("data", result)
    return {
        "ok":           True,
        "booking_id":   str(booking.get("uid") or booking.get("id", "")),
        "booking_time": str(booking.get("start") or booking.get("startTime", slot_time)),
    }

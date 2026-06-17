import re
import httpx
from app.config import settings
from app.services import llm


def _headers(prefer: str = "") -> dict:
    h = {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {settings.supabase_anon_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def _base() -> str:
    return f"{settings.supabase_url}/rest/v1"


async def lookup_client(utterance: str) -> dict | None:
    if not settings.supabase_url:
        return None

    email_match = re.search(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", utterance
    )

    async with httpx.AsyncClient() as client:
        if email_match:
            resp = await client.get(
                f"{_base()}/clients",
                headers=_headers(),
                params={"email": f"eq.{email_match.group(0)}", "select": "*", "limit": "1"},
            )
        else:
            words = " ".join(utterance.strip().split()[:3])
            resp = await client.get(
                f"{_base()}/clients",
                headers=_headers(),
                params={"name": f"ilike.*{words}*", "select": "*", "limit": "1"},
            )

    if not resp.is_success or not resp.json():
        return None

    row = resp.json()[0]

    async with httpx.AsyncClient() as client:
        calls_resp = await client.get(
            f"{_base()}/calls",
            headers=_headers(),
            params={
                "client_id": f"eq.{row['id']}",
                "select": "summary,created_at",
                "order": "created_at.desc",
                "limit": "3",
            },
        )

    recent = []
    if calls_resp.is_success:
        for c in calls_resp.json():
            if c.get("summary"):
                recent.append(f"Call on {c['created_at']}: {c['summary']}")

    row["recent_calls"] = recent
    return row


async def save_call(session) -> None:
    if not session.transcript_lines or not settings.supabase_url:
        return

    full_transcript = "\n".join(session.transcript_lines)
    summary = await llm.summarize_transcript(full_transcript)

    cal = session.cal_booking
    client_name  = cal.get("name")  or (session.client or {}).get("name")
    client_email = cal.get("email") or (session.client or {}).get("email")

    client_id = (session.client or {}).get("id")

    async with httpx.AsyncClient() as client:
        if not client_id and (client_name or client_email):
            payload = {}
            if client_name:  payload["name"]  = client_name
            if client_email: payload["email"] = client_email

            ins = await client.post(
                f"{_base()}/clients",
                headers=_headers("return=representation"),
                json=payload,
            )
            if ins.is_success and ins.json():
                client_id = ins.json()[0]["id"]
            elif client_email:
                fetch = await client.get(
                    f"{_base()}/clients",
                    headers=_headers(),
                    params={"email": f"eq.{client_email}", "select": "id", "limit": "1"},
                )
                if fetch.is_success and fetch.json():
                    client_id = fetch.json()[0]["id"]

        await client.post(
            f"{_base()}/calls",
            headers=_headers(),
            json={
                "client_id": client_id,
                "transcript": full_transcript,
                "summary": summary,
            },
        )

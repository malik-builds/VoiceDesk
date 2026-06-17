from openai import AsyncOpenAI
from app.config import settings

_client = AsyncOpenAI(api_key=settings.openai_api_key)

MODEL = "gpt-5.4-mini"


async def chat(messages: list, system: str) -> str:
    full_messages = [{"role": "system", "content": system}] + messages
    resp = await _client.chat.completions.create(
        model=MODEL,
        messages=full_messages,
        max_completion_tokens=200,
    )
    return resp.choices[0].message.content


async def detect_intent(messages: list) -> str:
    resp = await _client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Reply with only 'book' if the user wants to make an appointment "
                    "or booking, or 'query' for anything else. One word only."
                ),
            },
            *messages[-2:],
        ],
        max_completion_tokens=5,
    )
    result = resp.choices[0].message.content.strip().lower()
    return "book" if "book" in result else "query"


async def extract_value(utterance: str, field_name: str) -> str:
    resp = await _client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Extract the {field_name} from this text. "
                    f"Reply with only the value, nothing else: '{utterance}'"
                ),
            }
        ],
        max_completion_tokens=50,
    )
    return resp.choices[0].message.content.strip()


async def parse_slot_selection(utterance: str, slots: list, timezone: str) -> str | None:
    slot_list = "\n".join([f"{i + 1}. {s}" for i, s in enumerate(slots)])
    resp = await _client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Available slots (timezone: {timezone}):\n{slot_list}\n\n"
                    f"User said: '{utterance}'\n\n"
                    "Reply with the exact ISO datetime string of the chosen slot, "
                    "or 'none' if unclear or declined."
                ),
            }
        ],
        max_completion_tokens=60,
    )
    result = resp.choices[0].message.content.strip()
    if result.lower() == "none":
        return None
    for slot in slots:
        if slot in result or result in slot:
            return slot
    return slots[0] if slots else None


async def summarize_transcript(transcript: str) -> str:
    resp = await _client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    "Summarize this receptionist call in 1-2 sentences "
                    "for the receptionist's notes:\n\n" + transcript
                ),
            }
        ],
        max_completion_tokens=150,
    )
    return resp.choices[0].message.content.strip()


async def slots_to_natural_language(slots: list, timezone: str) -> str:
    slot_list = "\n".join(slots[:3])
    resp = await _client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Convert these appointment slots (timezone: {timezone}) into a "
                    "natural, spoken sentence a receptionist would say. Be concise:\n"
                    + slot_list
                ),
            }
        ],
        max_completion_tokens=100,
    )
    return resp.choices[0].message.content.strip()

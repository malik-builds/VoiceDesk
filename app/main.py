import asyncio
import json
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.memory import lookup_client, save_call
from app.prompt import build_system_prompt
from app.session import Session
from app.services import tts, llm
from app.services import stt as stt_service
from fastapi.responses import JSONResponse
from app.services.cal import fetch_slots, create_booking, debug_slots


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="VoiceDesk", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/debug/cal")
async def debug_cal():
    """Hit this in a browser to see exactly what Cal.com is returning."""
    result = await debug_slots(
        settings.cal_com_event_type_id,
        settings.cal_com_api_key,
        settings.cal_com_timezone,
    )
    return JSONResponse(result)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = Session(session_id=str(uuid.uuid4()), ws=websocket)

    session.stt_ws = await stt_service.connect(
        on_partial=lambda text: asyncio.create_task(_on_partial(session, text)),
        on_final=lambda text: asyncio.create_task(_on_final(session, text)),
    )

    await websocket.send_json({"type": "session.started", "session_id": session.session_id})
    await websocket.send_json({"type": "stt.ready"})

    greeting = (
        f"Thank you for calling {settings.company_name}, "
        f"I'm {settings.receptionist_name}, how can I help you today?"
    )
    session.transcript_lines.append(f"Agent: {greeting}")
    await websocket.send_json({"type": "agent.turn", "text": greeting})
    await tts.speak(session, greeting)

    try:
        async for data in websocket.iter_text():
            if session.closed:
                break
            try:
                msg = json.loads(data)
            except Exception:
                continue

            if msg.get("type") == "audio.chunk":
                await stt_service.send_chunk(session.stt_ws, msg.get("audio", ""))

            elif msg.get("type") == "audio.commit":
                await stt_service.commit(session.stt_ws)

            elif msg.get("type") == "hangup":
                break

    except WebSocketDisconnect:
        pass
    finally:
        session.closed = True
        await stt_service.close(session.stt_ws)
        await save_call(session)


async def _on_partial(session: Session, text: str):
    """Send live partial transcript to browser for display."""
    if session.closed:
        return
    try:
        await session.ws.send_json({"type": "transcript.partial", "text": text})
    except Exception:
        pass


async def _on_final(session: Session, text: str):
    """VAD-committed transcript — run a full turn if gates are clear."""
    if session.closed or session.is_speaking or session.is_processing:
        print(f"[GATE] dropped: {text}")
        return

    try:
        await session.ws.send_json({"type": "transcript.committed", "text": text})
    except Exception:
        return

    session.is_processing = True
    try:
        await handle_turn(session, text)
    finally:
        session.is_processing = False


async def handle_turn(session: Session, user_text: str) -> None:
    session.transcript_lines.append(f"User: {user_text}")

    if not session.messages and session.client is None:
        session.client = await lookup_client(user_text)

    system = build_system_prompt(session.client)
    session.messages.append({"role": "user", "content": user_text})

    intent = await llm.detect_intent(session.messages)
    booking_active = session.cal_booking.get("phase") not in (None, "confirmed", "need_phone")

    if intent == "book" or booking_active:
        response = await handle_booking_turn(session, user_text)
    else:
        response = await llm.chat(session.messages, system)

    session.messages.append({"role": "assistant", "content": response})
    session.transcript_lines.append(f"Agent: {response}")
    await session.ws.send_json({"type": "agent.turn", "text": response})
    await tts.speak(session, response)


async def handle_booking_turn(session: Session, utterance: str) -> str:
    cal = session.cal_booking
    phase = cal.get("phase")

    if not phase:
        cal["phase"] = "need_email"
        return "I'd be happy to book an appointment. Could I get your email address?"

    if phase == "need_email":
        email_match = re.search(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", utterance
        )
        if not email_match:
            cal["email_fails"] = cal.get("email_fails", 0) + 1
            if cal["email_fails"] >= 2:
                cal["phase"] = "need_phone"
                return "No worries — could I take your phone number instead and we'll be in touch?"
            return "Sorry, I didn't catch that. Could you spell out your email address?"
        cal["email"] = email_match.group(0)
        cal["phase"] = "need_name"
        return "And your full name?"

    if phase == "need_name":
        name = await llm.extract_value(utterance, "full name")
        if not name or len(name.strip()) < 2:
            return "Sorry, I didn't catch your name. Could you repeat it?"
        cal["name"] = name.strip()
        slots = await fetch_slots(
            settings.cal_com_event_type_id,
            settings.cal_com_api_key,
            settings.cal_com_timezone,
        )
        if not slots:
            return (
                "It looks like there are no available slots in the next two weeks. "
                "Could I take your phone number and one of our team will call you back to arrange a time?"
            )
        session.calendar_slots = slots[:3]
        cal["phase"] = "need_slot"
        return await llm.slots_to_natural_language(slots[:3], settings.cal_com_timezone)

    if phase == "need_slot":
        slot = await llm.parse_slot_selection(
            utterance, session.calendar_slots, settings.cal_com_timezone
        )
        if not slot:
            return "Sorry, I didn't catch which time works for you. Could you repeat that?"
        booking = await create_booking(
            event_type_id=settings.cal_com_event_type_id,
            api_key=settings.cal_com_api_key,
            slot_time=slot,
            attendee_name=cal.get("name", "Caller"),
            attendee_email=cal.get("email", ""),
            timezone_str=settings.cal_com_timezone,
        )
        if booking["ok"]:
            cal["phase"] = "confirmed"
            await session.ws.send_json({
                "type": "booking.confirmed",
                "booking_id": booking["booking_id"],
                "booking_time": booking["booking_time"],
            })
            return (
                f"Your booking is confirmed for {booking['booking_time']}. "
                "You'll receive a confirmation email shortly. "
                "Is there anything else I can help you with?"
            )
        return "Sorry, I wasn't able to complete that booking. Would you like to try a different time?"

    if phase == "need_phone":
        return "Thank you — we'll be in touch to arrange your appointment. Is there anything else I can help you with?"

    # Booking is done or in an unexpected state — hand off to general chat
    # (never let the LLM invent a booking confirmation)
    return await llm.chat(session.messages, build_system_prompt(session.client))

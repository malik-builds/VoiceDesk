import base64
import json
import re
import websockets
from app.config import settings

_SENTENCE_RE = re.compile(r"[.!?]\s$")
_CHUNK_SIZE  = 90


async def speak(session, text: str) -> None:
    session.is_speaking = True
    await _send(session.ws, {"type": "tts.start"})
    try:
        if settings.tts_provider == "valsea":
            await _speak_valsea(session, text)
        else:
            await _speak_elevenlabs(session, text)
    finally:
        session.is_speaking = False
        await _send(session.ws, {"type": "tts.end"})


def _el_tts_url() -> str:
    return (
        f"wss://api.elevenlabs.io/v1/text-to-speech"
        f"/{settings.elevenlabs_voice_id}"
        f"/stream-input?model_id=eleven_flash_v2_5"
    )


async def _speak_elevenlabs(session, text: str) -> None:
    try:
        async with websockets.connect(
            _el_tts_url(),
            additional_headers={"xi-api-key": settings.elevenlabs_api_key},
        ) as ws:
            await ws.send(json.dumps({
                "text": " ",
                "voice_settings": {
                    "stability":        0.4,
                    "similarity_boost": 0.8,
                    "use_speaker_boost": True,
                },
                "generation_config": {
                    "chunk_length_schedule": [80, 120, 180, 240],
                },
            }))

            buf = ""
            for char in text:
                buf += char
                if len(buf) >= _CHUNK_SIZE or _SENTENCE_RE.search(buf):
                    await ws.send(json.dumps({"text": buf}))
                    buf = ""
            await ws.send(json.dumps({"text": buf or " ", "flush": True}))
            await ws.send(json.dumps({"text": ""}))

            async for raw in ws:
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                if data.get("audio"):
                    await _send(session.ws, {"type": "audio.chunk", "audio": data["audio"]})
                if data.get("isFinal"):
                    break
    except Exception as e:
        print(f"[TTS] error: {e}")


_VALSEA_TTS_URL = "wss://api.valsea.ai/v1/tts"


async def _speak_valsea(session, text: str) -> None:
    try:
        async with websockets.connect(
            _VALSEA_TTS_URL,
            additional_headers={"Authorization": f"Bearer {settings.valsea_api_key}"},
        ) as ws:
            await ws.send(json.dumps({
                "type": "tts.request",
                "text": text,
            }))

            async for msg in ws:
                if isinstance(msg, bytes):
                    encoded = base64.b64encode(msg).decode()
                    await _send(session.ws, {"type": "audio.chunk", "audio": encoded})
                else:
                    try:
                        event = json.loads(msg)
                    except Exception:
                        continue
                    if event.get("type", "") in ("tts.end", "tts.done", "tts.complete"):
                        break
    except Exception as e:
        print(f"[TTS] error: {e}")


async def _send(ws, data: dict) -> None:
    try:
        await ws.send_json(data)
    except Exception:
        pass

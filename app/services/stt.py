import asyncio
import json
import os
import websockets
from app.config import settings

_EL_STT_URL = (
    "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
    "?model_id=scribe_v2_realtime"
    "&audio_format=pcm_24000"
    "&commit_strategy=vad"
    "&vad_silence_duration_ms=1000"
)

_VALSEA_RTT_URL = "wss://api.valsea.ai/v1/realtime"

# Valsea's VAD fires aggressively mid-sentence. This holdback waits for genuine
# silence before committing, accumulating any consecutive finals into one turn.
_VALSEA_HOLDBACK_S = float(os.environ.get("VALSEA_HOLDBACK_MS", "1200")) / 1000


async def connect(on_partial, on_final):
    if settings.stt_provider == "valsea":
        return await _connect_valsea(on_partial, on_final)
    return await _connect_elevenlabs(on_partial, on_final)


async def send_chunk(ws, audio_base64: str):
    if ws is None:
        return
    if settings.stt_provider == "valsea":
        await _send_valsea(ws, audio_base64)
    else:
        await _send_elevenlabs(ws, audio_base64)


async def commit(ws):
    if ws is None or settings.stt_provider != "valsea":
        return
    try:
        await ws.send(json.dumps({"type": "audio.commit"}))
    except Exception:
        pass


async def close(ws):
    if ws is None:
        return
    if settings.stt_provider == "valsea":
        try:
            await ws.send(json.dumps({"type": "session.stop"}))
        except Exception:
            pass
    try:
        await ws.close()
    except Exception:
        pass


async def _connect_elevenlabs(on_partial, on_final):
    ws = await websockets.connect(
        _EL_STT_URL,
        additional_headers={"xi-api-key": settings.elevenlabs_api_key},
    )
    asyncio.create_task(_listen_elevenlabs(ws, on_partial, on_final))
    return ws


async def _send_elevenlabs(ws, audio_base64: str):
    try:
        await ws.send(json.dumps({
            "message_type": "input_audio_chunk",
            "audio_base_64": audio_base64,
        }))
    except Exception:
        pass


async def _listen_elevenlabs(ws, on_partial, on_final):
    try:
        async for raw in ws:
            try:
                event = json.loads(raw)
            except Exception:
                continue
            t = event.get("message_type", "")
            if t == "partial_transcript":
                text = event.get("text", "")
                if text:
                    await on_partial(text)
            elif t == "committed_transcript":
                text = str(event.get("text", "")).strip()
                if text:
                    await on_final(text)
    except Exception as e:
        print(f"[STT] closed: {e}")


async def _connect_valsea(on_partial, on_final):
    ws = await websockets.connect(
        _VALSEA_RTT_URL,
        additional_headers={"Authorization": f"Bearer {settings.valsea_api_key}"},
    )
    await ws.send(json.dumps({
        "type":              "session.start",
        "model":             "valsea-rtt",
        "language":          "english",
        "enable_correction": True,
    }))
    asyncio.create_task(_listen_valsea(ws, on_partial, on_final))
    return ws


async def _send_valsea(ws, audio_base64: str):
    try:
        await ws.send(json.dumps({
            "type":  "audio.append",
            "audio": audio_base64,
        }))
    except Exception:
        pass


async def _listen_valsea(ws, on_partial, on_final):
    accumulated = ""
    holdback: asyncio.Task | None = None

    async def _fire_after_holdback(text: str):
        await asyncio.sleep(_VALSEA_HOLDBACK_S)
        await on_final(text)

    def _reset_holdback(text: str):
        nonlocal holdback, accumulated
        accumulated = text
        if holdback and not holdback.done():
            holdback.cancel()
        holdback = asyncio.create_task(_fire_after_holdback(text))

    try:
        async for raw in ws:
            try:
                event = json.loads(raw)
            except Exception:
                continue

            t = event.get("type", "")

            if t == "transcript.partial":
                text = event.get("text", "")
                if not text:
                    continue
                if holdback and not holdback.done():
                    holdback.cancel()
                    holdback = None
                await on_partial(text)

            elif t == "transcript.final":
                text = str(event.get("text", "")).strip()
                if not text:
                    continue
                combined = (accumulated + " " + text).strip() if accumulated else text
                _reset_holdback(combined)

    except Exception as e:
        print(f"[STT] closed: {e}")
    finally:
        if holdback and not holdback.done():
            holdback.cancel()

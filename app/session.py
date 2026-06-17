from dataclasses import dataclass, field
from fastapi import WebSocket
from typing import Any


@dataclass
class Session:
    session_id: str
    ws: WebSocket
    stt_ws: Any = None

    is_speaking: bool = False
    is_processing: bool = False
    closed: bool = False

    messages: list = field(default_factory=list)
    client: dict | None = None

    cal_booking: dict = field(default_factory=dict)
    calendar_slots: list = field(default_factory=list)

    transcript_lines: list = field(default_factory=list)

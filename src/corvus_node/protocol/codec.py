"""NDJSON codec for Envelope.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from corvus_node.protocol.models import Envelope


class CodecError(ValueError):
    """Raised when a message cannot be encoded or decoded."""


def encode_message(message: Envelope) -> str:
    data = message.model_dump(mode="json")
    return json.dumps(data, separators=(",", ":"))


def decode_line(line: str) -> Envelope:
    line = line.strip()
    if not line:
        raise CodecError("Empty line")
    try:
        data: dict[str, Any] = json.loads(line)
        return Envelope.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise CodecError(str(exc)) from exc

"""Append-only in-memory audit log.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    correlation_id: str
    origin_correlation_id: str | None
    source_engine: str
    message_type: str
    decision: str | None
    details: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class AuditStore:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def log_hop(
        self,
        *,
        message_type: str,
        source_engine: str,
        correlation_id: UUID | str,
        origin_correlation_id: UUID | str | None = None,
        decision: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        origin = str(origin_correlation_id) if origin_correlation_id else None
        self.append(
            AuditEvent(
                event_type="message_hop",
                correlation_id=str(correlation_id),
                origin_correlation_id=origin,
                source_engine=source_engine,
                message_type=message_type,
                decision=decision,
                details=details or {},
            )
        )

    def log_flag(
        self,
        *,
        code: str,
        message_type: str,
        source_engine: str,
        correlation_id: UUID | str,
        origin_correlation_id: UUID | str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        extra = dict(details or {})
        extra["code"] = code
        self.append(
            AuditEvent(
                event_type="flag",
                correlation_id=str(correlation_id),
                origin_correlation_id=str(origin_correlation_id) if origin_correlation_id else None,
                source_engine=source_engine,
                message_type=message_type,
                decision="flag",
                details=extra,
            )
        )

    def log_elevate(
        self,
        *,
        message_type: str,
        source_engine: str,
        correlation_id: UUID | str,
        origin_correlation_id: UUID | str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.append(
            AuditEvent(
                event_type="elevate",
                correlation_id=str(correlation_id),
                origin_correlation_id=str(origin_correlation_id) if origin_correlation_id else None,
                source_engine=source_engine,
                message_type=message_type,
                decision="elevate",
                details=details or {},
            )
        )

    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    def types(self) -> list[str]:
        return [e.message_type for e in self._events]


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items() if key != "session_key"}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, str) and "session_key" in value:
        return "[redacted]"
    return value


def verify_chain(path: Path) -> None:
    prev = "0" * 64
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        record = json.loads(raw)
        chain = record.pop("chain", None)
        blob = json.dumps(record, sort_keys=True, separators=(",", ":"))
        expect = hashlib.sha256((prev + blob).encode("utf-8")).hexdigest()
        if chain != expect:
            raise ValueError("audit chain broken")
        prev = expect


class JsonlAuditStore(AuditStore):
    """Host-durable hash-chained JSONL. Lives outside the jail instance dir."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._prev = "0" * 64
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AuditEvent) -> None:
        super().append(event)
        record = {
            "event_type": event.event_type,
            "correlation_id": event.correlation_id,
            "origin_correlation_id": event.origin_correlation_id,
            "source_engine": event.source_engine,
            "message_type": event.message_type,
            "decision": event.decision,
            "details": _scrub(event.details),
            "timestamp": event.timestamp.isoformat(),
        }
        blob = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
        chain = hashlib.sha256((self._prev + blob).encode("utf-8")).hexdigest()
        record["chain"] = chain
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        self._prev = chain

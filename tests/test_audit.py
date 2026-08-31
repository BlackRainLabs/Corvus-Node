"""Hash-chained host audit.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from pathlib import Path
from uuid import uuid4

import pytest

from corvus_node.audit.store import JsonlAuditStore, verify_chain


def test_jsonl_chain_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "turn.jsonl"
    store = JsonlAuditStore(path)
    cid = uuid4()
    store.log_hop(
        message_type="handshake",
        source_engine="loop",
        correlation_id=cid,
    )
    store.log_flag(
        code="mac_fail",
        message_type="mac",
        source_engine="node",
        correlation_id=cid,
        details={"session_key": "should-not-persist"},
    )
    verify_chain(path)
    text = path.read_text(encoding="utf-8")
    assert "session_key" not in text
    assert "mac_fail" in text


def test_jsonl_tamper_detected(tmp_path: Path) -> None:
    path = tmp_path / "turn.jsonl"
    store = JsonlAuditStore(path)
    store.log_hop(message_type="handshake", source_engine="loop", correlation_id="a")
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace("handshake", "tampered"), encoding="utf-8")
    with pytest.raises(ValueError, match="audit chain broken"):
        verify_chain(path)

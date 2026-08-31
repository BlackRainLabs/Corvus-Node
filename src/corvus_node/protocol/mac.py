"""HMAC hop integrity for Envelope v1.1.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

from corvus_node.protocol.models import Envelope

BOOTSTRAP_TYPES = frozenset({"session_init"})


def new_session_key() -> str:
    return secrets.token_hex(32)


def payload_sha256(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def compute_mac(
    key: bytes,
    message: Envelope,
    *,
    vm_instance_id: str = "",
    guest_cid: int = 0,
) -> str:
    origin = str(message.origin_correlation_id) if message.origin_correlation_id else ""
    material = "|".join(
        (
            str(message.id),
            message.type,
            str(message.source_engine),
            str(message.destination),
            str(message.seq),
            str(message.correlation_id),
            origin,
            message.payload_sha256,
            vm_instance_id,
            str(guest_cid),
        )
    )
    return hmac.new(key, material.encode("utf-8"), hashlib.sha256).hexdigest()


class MacError(ValueError):
    """Inbound hop failed HMAC or sequence checks."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class HopMac:
    """Per-direction seq + HMAC. session_init is unsigned; the host mints the key."""

    def __init__(
        self,
        key_hex: str | None = None,
        *,
        vm_instance_id: str = "",
        guest_cid: int = 0,
    ) -> None:
        self._key = bytes.fromhex(key_hex) if key_hex else None
        self.vm_instance_id = vm_instance_id
        self.guest_cid = guest_cid
        self.out_seq = 0
        self.in_seq = -1

    @property
    def key_hex(self) -> str | None:
        return self._key.hex() if self._key else None

    def set_key(self, key_hex: str) -> None:
        self._key = bytes.fromhex(key_hex)

    def set_bind(self, *, vm_instance_id: str, guest_cid: int) -> None:
        self.vm_instance_id = vm_instance_id
        self.guest_cid = guest_cid

    def sign(self, message: Envelope) -> Envelope:
        digest = payload_sha256(message.payload)
        signed = message.model_copy(
            update={"seq": self.out_seq, "payload_sha256": digest, "mac": ""}
        )
        self.out_seq += 1
        if self._key is not None and message.type not in BOOTSTRAP_TYPES:
            signed = signed.model_copy(
                update={
                    "mac": compute_mac(
                        self._key,
                        signed,
                        vm_instance_id=self.vm_instance_id,
                        guest_cid=self.guest_cid,
                    )
                }
            )
        return signed

    def verify(self, message: Envelope) -> None:
        expected_seq = self.in_seq + 1
        if message.seq < expected_seq:
            raise MacError("replay", f"seq {message.seq} replayed")
        if message.seq != expected_seq:
            raise MacError("seq_gap", f"expected seq {expected_seq}, got {message.seq}")
        digest = payload_sha256(message.payload)
        if digest != message.payload_sha256:
            raise MacError("mac_fail", "payload hash mismatch")
        bootstrap = message.type in BOOTSTRAP_TYPES
        if bootstrap:
            self.in_seq = message.seq
            return
        if self._key is None:
            raise MacError("mac_fail", "session key not installed")
        expected = compute_mac(
            self._key,
            message,
            vm_instance_id=self.vm_instance_id,
            guest_cid=self.guest_cid,
        )
        if not message.mac or not hmac.compare_digest(expected, message.mac):
            raise MacError("mac_fail", "hmac mismatch")
        self.in_seq = message.seq

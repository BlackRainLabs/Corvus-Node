"""Pinned SHA-256 for kernel, Firecracker, and jailer. Re-check on every launch.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import hashlib
from pathlib import Path

KERNEL_SHA256: dict[str, str] = {
    "x86_64": "b36a4a1b10f33b9cfdcde3d1a787d9c090556a3edb211cd06d1f3f9a6c7e8724",
    "aarch64": "69aa3308219ec1a070bc9a8e7f80c3b34056fed8ae05efb44e55f73b31adde44",
}

FIRECRACKER_TGZ_SHA256: dict[str, str] = {
    "x86_64": "382a02a869e4d6d5cb14c40577f9545e8458021ea8b0b2d3fc10ec14d9c242e6",
    "aarch64": "8d0e69f6d6f9a1724551f607f18504052c16c1828ee3d4d7b6e6c73380871e0e",
}

FIRECRACKER_BIN_SHA256: dict[str, str] = {
    "x86_64": "2fd0171309af7e24cf8dafc8a6f921c1434c49b5f9349bb996b7ed0a4deb8aa7",
    "aarch64": "71ca0733576579a75cef268a8fd0ae0629b761b9844559c611f144132ac6038a",
}

JAILER_BIN_SHA256: dict[str, str] = {
    "x86_64": "1f3a0c1fe86212d0001819bfe0819071c01208b3ccc9398c3b3bc1b84cf21edd",
    "aarch64": "7db39d34991ccdd8d12aacab384b1dcbe35e79c27823e4e4d33725d4b504edd7",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path, expected: str, *, name: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"{name} sha256 mismatch (got {actual}, want {expected})")

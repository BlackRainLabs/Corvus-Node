"""GitHub version check (no network; mocked).

Organization: Black Rain Labs
Division: Research & Development Division
"""

import json
from urllib.error import URLError

import pytest

from corvus_node.node.update import (
    check_version,
    fetch_github_version,
    github_install_ref,
    local_unreleased,
    parse_version,
)


def test_parse_version() -> None:
    assert parse_version("v0.1.4") == (0, 1, 4)
    assert parse_version("0.1.6") == (0, 1, 6)
    assert parse_version("0.1.6") > parse_version("0.1.5")


def test_github_install_ref() -> None:
    assert github_install_ref("0.1.5").endswith("@v0.1.5")
    assert "BlackRainLabs/Corvus-Node" in github_install_ref("v0.1.5")


def test_fetch_skipped_when_env_set() -> None:
    assert fetch_github_version() is None


def test_local_unreleased_when_newer_than_github() -> None:
    assert local_unreleased("0.1.4") is True


def test_check_version_unreleased_does_not_offer_update() -> None:
    status = check_version()
    assert status.update_available is False
    assert (
        "GitHub" in status.reason
        or "unreleased" in status.reason
        or "not on GitHub" in status.reason
    )


def test_fetch_github_picks_latest_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORVUS_NODE_SKIP_UPDATE_CHECK", raising=False)
    payload = json.dumps([{"name": "v0.1.4"}, {"name": "v0.1.3"}]).encode()

    class _Resp:
        def read(self) -> bytes:
            return payload

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr("corvus_node.node.update.urllib.request.urlopen", lambda *a, **k: _Resp())
    assert fetch_github_version() == "0.1.4"


def test_fetch_github_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORVUS_NODE_SKIP_UPDATE_CHECK", raising=False)

    def _boom(*_a: object, **_k: object) -> None:
        raise URLError("offline")

    monkeypatch.setattr("corvus_node.node.update.urllib.request.urlopen", _boom)
    assert fetch_github_version() is None


def test_check_version_newer_github_on_release_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORVUS_NODE_SKIP_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("corvus_node.node.update.fetch_github_version", lambda **_: "9.9.9")
    monkeypatch.setattr("corvus_node.node.update.local_unreleased", lambda _g: False)
    monkeypatch.setattr("corvus_node.node.update.is_source_checkout", lambda: False)
    status = check_version()
    assert status.update_available is True
    assert status.github == "9.9.9"

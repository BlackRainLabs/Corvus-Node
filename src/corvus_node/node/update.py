"""GitHub version check for the installed CLI/GUI. Not a repo git pull.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from corvus_node import __version__

GITHUB_REPO = "BlackRainLabs/Corvus-Node"
DEFAULT_TAGS_URL = f"https://api.github.com/repos/{GITHUB_REPO}/tags"
INSTALL_REF = f"git+https://github.com/{GITHUB_REPO}.git"


@dataclass(frozen=True)
class VersionStatus:
    local: str
    github: str | None
    channel: str
    update_available: bool
    reason: str


def parse_version(raw: str) -> tuple[int, int, int]:
    text = raw.strip().lstrip("vV")
    parts: list[int] = []
    for chunk in text.split(".")[:3]:
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def source_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() and (parent / "src" / "corvus_node").is_dir():
            return parent
    return None


def is_source_checkout() -> bool:
    return source_root() is not None


def _git_output(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def local_unreleased(github: str | None) -> bool:
    """True when this tree should not be replaced by GitHub (dev before merge)."""
    if github is not None and parse_version(__version__) > parse_version(github):
        return True
    root = source_root()
    if root is None:
        return False
    if _git_output(root, "status", "--porcelain"):
        return True
    ahead = _git_output(root, "rev-list", "--count", "origin/main..HEAD")
    if ahead.isdigit() and int(ahead) > 0:
        return True
    return False


def fetch_github_lookup(*, timeout: float = 3.0) -> tuple[str | None, str]:
    """Latest tag and a reason when there is none (skip, no tags, or unreachable)."""
    if os.environ.get("CORVUS_NODE_SKIP_UPDATE_CHECK", "").strip() == "1":
        return None, "version check skipped"
    url = os.environ.get("CORVUS_NODE_VERSION_URL", "").strip() or DEFAULT_TAGS_URL
    req = urllib.request.Request(url, headers={"User-Agent": "corvus"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None, "GitHub unreachable"
    names: list[str] = []
    if isinstance(data, dict) and data.get("tag_name"):
        names.append(str(data["tag_name"]))
    elif isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and entry.get("name"):
                names.append(str(entry["name"]))
    if not names:
        return None, "no GitHub tags yet"
    return max(names, key=parse_version).lstrip("vV"), ""


def fetch_github_version(*, timeout: float = 3.0) -> str | None:
    version, _reason = fetch_github_lookup(timeout=timeout)
    return version


def check_version() -> VersionStatus:
    local = __version__
    github, lookup_reason = fetch_github_lookup()
    unreleased = local_unreleased(github)
    if github is None:
        channel = "unreleased" if unreleased or is_source_checkout() else "unknown"
        reason = "this build is not on GitHub yet" if unreleased else lookup_reason
        return VersionStatus(local, None, channel, False, reason)
    if unreleased:
        return VersionStatus(
            local,
            github,
            "unreleased",
            False,
            "this build is not on GitHub yet (local unreleased; wait for merge)",
        )
    if parse_version(local) < parse_version(github):
        if is_source_checkout():
            return VersionStatus(
                local,
                github,
                "source",
                False,
                "GitHub is newer; pull/merge the repo — corvus update is for the installed app",
            )
        return VersionStatus(
            local,
            github,
            "release",
            True,
            f"GitHub {github} is newer; corvus update",
        )
    return VersionStatus(local, github, "release", False, "up to date with GitHub")


def format_version_status(status: VersionStatus) -> str:
    github = status.github or "(none)"
    lines = [
        f"Version: {status.local} ({status.channel})",
        f"GitHub: {github}",
        f"Update: {status.reason}",
    ]
    return "\n".join(lines) + "\n"


def github_install_ref(tag: str) -> str:
    return f"{INSTALL_REF}@v{tag.lstrip('vV')}"

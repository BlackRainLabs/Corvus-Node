#!/bin/bash
# Guided Corvus-Node installer. Run as your user; sudo only when needed.
# Organization: Black Rain Labs — https://www.BlackRainLabs.com
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GROUP="${CORVUS_NODE_GROUP:-corvus}"
YES=0
DRY=0
FORCE_RELEASE=0
FORCE_LOCAL=0
if [[ "${CORVUS_NODE_INSTALL_YES:-}" == "1" ]]; then
  YES=1
fi
if [[ "${CORVUS_NODE_INSTALL_DRY:-}" == "1" ]]; then
  DRY=1
fi

for arg in "$@"; do
  case "$arg" in
    --yes | -y) YES=1 ;;
    --release) FORCE_RELEASE=1 ;;
    --local) FORCE_LOCAL=1 ;;
    --help | -h)
      # printed below via usage
      YES=1
      SHOW_HELP=1
      ;;
    *)
      echo "corvus: unknown option $arg (try --help)" >&2
      exit 2
      ;;
  esac
done

SHOW_HELP="${SHOW_HELP:-0}"

if [[ "$FORCE_RELEASE" -eq 1 && "$FORCE_LOCAL" -eq 1 ]]; then
  echo "corvus: use --release or --local, not both" >&2
  exit 2
fi

USE_COLOR=0
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  USE_COLOR=1
fi
if [[ "$USE_COLOR" -eq 1 ]]; then
  C_OK="$(printf '\033[32m')"
  C_DO="$(printf '\033[33m')"
  C_NEED="$(printf '\033[31m')"
  C_DIM="$(printf '\033[2m')"
  C_BOLD="$(printf '\033[1m')"
  C_RST="$(printf '\033[0m')"
else
  C_OK="" C_DO="" C_NEED="" C_DIM="" C_BOLD="" C_RST=""
fi

ok() { printf '  %sok   %s%s\n' "$C_OK" "$1" "$C_RST"; }
doing() { printf '  %sdo   %s%s\n' "$C_DO" "$1" "$C_RST"; }
need() { printf '  %sneed %s%s\n' "$C_NEED" "$1" "$C_RST"; }
skip() { printf '  %sok   %s (already up to date)%s\n' "$C_OK" "$1" "$C_RST"; }

usage() {
  cat <<'EOF'
Corvus-Node installer — Black Rain Labs
https://www.BlackRainLabs.com

  ./install.sh          install (your user; password only when needed)
  ./install.sh --yes    no “press Enter”; also confirm stop/upgrade if asked
  ./install.sh --local  this directory (default when it is a git checkout)
  ./install.sh --release
                        GitHub release wheel (default with no git tree)
  ./install.sh --help   this text

Users: unpack corvus-node-install.tar.gz from the GitHub Release, then
./install.sh here. You do not clone the project. A git clone installs
this checkout. --release always fetches the latest GitHub wheel.
If Corvus-Node is already installed, you can upgrade or keep the current
version. Your password is only for setting up isolation. Chat is not root.
The installer also installs the GUI runtime (PySide/Qt). After install, corvus just
works in this terminal — you do not type extra group commands.
EOF
}

banner() {
  cat <<EOF
${C_BOLD}
        .--.  Corvus-Node
       /v  v\\  a private AI agent for your Linux PC
      /(    )\\
       ^^  ^^
${C_RST}${C_DIM}  Black Rain Labs  ·  https://www.BlackRainLabs.com${C_RST}

EOF
}

sudo_story() {
  cat <<EOF
${C_BOLD}Why this script asks for your password${C_RST}

  Corvus-Node runs the agent in a locked-down virtual machine. Setting that
  up is a system job, so Linux asks for your password. ${C_BOLD}Chat does not.${C_RST}
  The agent never gets your admin account, and it cannot call tools
  unless you allow them.

  Files land under ${C_BOLD}\$HOME/Corvus-Node${C_RST}. This run may install missing
  packages (including GUI libraries for ${C_BOLD}corvus gui${C_RST}), build the agent
  environment, start Corvus-Node in the background, and make the ${C_BOLD}corvus${C_RST}
  command work in this terminal.

EOF
}

pause() {
  if [[ "$YES" -eq 1 || "$DRY" -eq 1 ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    return 0
  fi
  printf '%sPress Enter to continue, or Ctrl-C to stop.%s ' "$C_DIM" "$C_RST"
  read -r _
}

run_sudo() {
  if [[ "$DRY" -eq 1 ]]; then
    printf '  %sdry  sudo %s%s\n' "$C_DIM" "$*" "$C_RST"
    return 0
  fi
  sudo "$@"
}

with_spin() {
  local msg="$1"
  shift
  if [[ "$DRY" -eq 1 ]]; then
    printf '  %sdry  %s%s\n' "$C_DIM" "$*" "$C_RST"
    return 0
  fi
  if [[ ! -t 1 ]]; then
    doing "$msg"
    "$@"
    return
  fi
  doing "$msg"
  "$@" &
  local pid=$!
  local chars='|/-\'
  local i=0
  while kill -0 "$pid" 2>/dev/null; do
    printf '\r  %sdo   %s %s%s' "$C_DO" "$msg" "${chars:i++%4:1}" "$C_RST"
    sleep 0.12
  done
  local rc=0
  wait "$pid" || rc=$?
  printf '\r'
  return "$rc"
}

detect_os() {
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "${ID:-}"
    return
  fi
  echo "unknown"
}

pkg_kind() {
  local id
  id="$(detect_os)"
  case "$id" in
    debian | ubuntu) echo apt ;;
    fedora | rhel | centos | rocky | almalinux) echo dnf ;;
    *) echo none ;;
  esac
}

pkg_names() {
  local kind
  kind="$(pkg_kind)"
  case "$kind" in
    apt) echo python3 python3-venv python3-pip make curl e2fsprogs mmdebstrap qemu-kvm ;;
    dnf) echo python3 python3-pip make curl e2fsprogs mmdebstrap qemu-kvm ;;
    *) echo "" ;;
  esac
}

# Host .so names PySide6 wheels need on Linux. Values are apt / dnf package names.
qt_host_specs() {
  local kind
  kind="$(pkg_kind)"
  case "$kind" in
    apt)
      cat <<'EOF'
libGL.so.1 libgl1
libEGL.so.1 libegl1
libxkbcommon.so.0 libxkbcommon0
libxkbcommon-x11.so.0 libxkbcommon-x11-0
libxcb-cursor.so.0 libxcb-cursor0
libxcb-icccm.so.4 libxcb-icccm4
libxcb-keysyms.so.1 libxcb-keysyms1
libfontconfig.so.1 libfontconfig1
libglib-2.0.so.0 libglib2.0-0
libdbus-1.so.3 libdbus-1-3
EOF
      ;;
    dnf)
      cat <<'EOF'
libGL.so.1 mesa-libGL
libEGL.so.1 mesa-libEGL
libxkbcommon.so.0 libxkbcommon
libxkbcommon-x11.so.0 libxkbcommon-x11
libxcb-cursor.so.0 xcb-util-cursor
libxcb-icccm.so.4 xcb-util-wm
libxcb-keysyms.so.1 xcb-util-keysyms
libfontconfig.so.1 fontconfig
libglib-2.0.so.0 glib2
libdbus-1.so.3 dbus-libs
EOF
      ;;
  esac
}

so_present() {
  local so="$1"
  if command -v ldconfig >/dev/null 2>&1; then
    ldconfig -p 2>/dev/null | grep -F -q "$so"
    return $?
  fi
  return 1
}

host_pkg_present() {
  local pkg="$1"
  case "$(pkg_kind)" in
    apt)
      dpkg-query -W -f '${Status}\n' "$pkg" 2>/dev/null | grep -q "install ok installed"
      ;;
    dnf)
      rpm -q "$pkg" >/dev/null 2>&1
      ;;
    *)
      return 1
      ;;
  esac
}

bin_for_pkg() {
  case "$1" in
    python3 | python3-venv | python3-pip) echo python3 ;;
    make) echo make ;;
    curl) echo curl ;;
    e2fsprogs) echo mkfs.ext4 ;;
    mmdebstrap) echo mmdebstrap ;;
    qemu-kvm) echo true ;;
    *) echo true ;;
  esac
}

missing_pkgs() {
  local pkg bin
  for pkg in $(pkg_names); do
    bin="$(bin_for_pkg "$pkg")"
    if [[ "$pkg" == "qemu-kvm" ]]; then
      if [[ -c /dev/kvm ]]; then
        continue
      fi
      echo "$pkg"
      continue
    fi
    if [[ "$pkg" == "python3-venv" ]]; then
      if python3 -c 'import venv' 2>/dev/null; then
        continue
      fi
      echo "$pkg"
      continue
    fi
    if [[ "$pkg" == "python3-pip" ]]; then
      if python3 -m pip --version >/dev/null 2>&1; then
        continue
      fi
      echo "$pkg"
      continue
    fi
    if [[ "$pkg" == "mmdebstrap" ]]; then
      if command -v mmdebstrap >/dev/null || command -v debootstrap >/dev/null || command -v docker >/dev/null; then
        continue
      fi
      echo "$pkg"
      continue
    fi
    if command -v "$bin" >/dev/null; then
      continue
    fi
    echo "$pkg"
  done
  local so pkg
  while read -r so pkg; do
    [[ -z "${so:-}" || -z "${pkg:-}" ]] && continue
    if so_present "$so" || host_pkg_present "$pkg"; then
      continue
    fi
    echo "$pkg"
  done < <(qt_host_specs)
}

prefix_path() {
  echo "${CORVUS_NODE_PREFIX:-$HOME/Corvus-Node}"
}

assets_current() {
  local cache="${CORVUS_NODE_CACHE:-$ROOT/.cache/corvus-node}"
  python3 - "$ROOT/src/corvus_node/vm/checksums.py" "$cache" <<'PY'
import importlib.util
import platform
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("csum", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)
cache = Path(sys.argv[2])
arch = platform.machine()
if arch not in mod.KERNEL_SHA256:
    sys.exit(1)

def ok(path: Path, digest: str | None) -> bool:
    if not path.is_file():
        return False
    if digest is None:
        side = path.with_name(path.name + ".sha256")
        if not side.is_file():
            return False
        want = side.read_text().split()[0].strip()
        return mod.sha256_file(path) == want
    return mod.sha256_file(path) == digest

rootfs = cache / "rootfs.ext4"
if not ok(rootfs, None):
    sys.exit(1)
for path, digest in (
    (cache / "vmlinux", mod.KERNEL_SHA256[arch]),
    (cache / "firecracker", mod.FIRECRACKER_BIN_SHA256[arch]),
    (cache / "jailer", mod.JAILER_BIN_SHA256[arch]),
):
    if not ok(path, digest):
        sys.exit(1)
sys.exit(0)
PY
}

installed_version() {
  local prefix venv
  prefix="$(prefix_path)"
  venv="$prefix/venv/bin/python"
  if [[ ! -x "$venv" ]]; then
    return 1
  fi
  "$venv" -c 'from corvus_node import __version__; print(__version__)' 2>/dev/null
}

tree_version() {
  grep -m1 '^version =' "$ROOT/pyproject.toml" | cut -d'"' -f2
}

is_git_checkout() {
  [[ -e "$ROOT/.git" ]]
}

has_local_tree() {
  [[ -f "$ROOT/pyproject.toml" && -d "$ROOT/src/corvus_node" ]]
}

install_source() {
  if [[ "$FORCE_RELEASE" -eq 1 ]]; then
    echo release
  elif [[ "$FORCE_LOCAL" -eq 1 ]]; then
    echo local
  elif is_git_checkout; then
    echo local
  elif has_local_tree; then
    echo local
  else
    echo release
  fi
}

github_release_lookup() {
  python3 - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

url = os.environ.get("CORVUS_NODE_VERSION_URL", "").strip() or (
    "https://api.github.com/repos/BlackRainLabs/Corvus-Node/releases/latest"
)
req = urllib.request.Request(url, headers={"User-Agent": "corvus"})
try:
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
except Exception:
    sys.exit(1)
tag = ""
wheel = ""
if isinstance(data, dict):
    tag = str(data.get("tag_name") or "").lstrip("vV")
    for asset in data.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        if name.endswith(".whl") and "corvus_node" in name:
            wheel = str(asset.get("browser_download_url") or "")
            break
if not tag:
    sys.exit(1)
if not wheel:
    wheel = (
        "https://github.com/BlackRainLabs/Corvus-Node/releases/download/"
        f"v{tag}/corvus_node-{tag}-py3-none-any.whl"
    )
print(tag)
print(wheel)
PY
}

source_newer_than_install() {
  local prefix pkg
  prefix="$(prefix_path)"
  if [[ ! -d "$ROOT/src/corvus_node" ]]; then
    return 1
  fi
  pkg="$(find "$prefix/venv/lib" -path '*/site-packages/corvus_node/__init__.py' 2>/dev/null | head -1 || true)"
  if [[ -z "$pkg" || ! -f "$pkg" ]]; then
    return 0
  fi
  find "$ROOT/src/corvus_node" -type f -newer "$pkg" -print -quit 2>/dev/null | grep -q .
}

wait_corvus_up() {
  local sock i
  sock="$(control_sock)"
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    if [[ -S "$sock" ]]; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

in_group_session() {
  id -nG 2>/dev/null | tr ' ' '\n' | grep -qx "$GROUP"
}

in_group_file() {
  getent group "$GROUP" >/dev/null 2>&1 || return 1
  local user
  user="$(id -un)"
  getent group "$GROUP" | awk -F: '{print $4}' | tr ',' '\n' | grep -qx "$user"
}

confirm_yes() {
  local prompt="$1" ans lower
  if [[ "$YES" -eq 1 ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    echo "corvus: not a TTY; pass --yes to confirm" >&2
    return 1
  fi
  printf '%s [y/N] ' "$prompt"
  read -r ans || return 1
  lower="$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')"
  [[ "$lower" == "y" || "$lower" == "yes" ]]
}

unit_active() {
  command -v systemctl >/dev/null || return 1
  [[ -d /run/systemd/system ]] || return 1
  systemctl is-active --quiet corvus-node.service 2>/dev/null
}

control_sock() {
  echo "$(prefix_path)/run/control.sock"
}

node_live() {
  if [[ "${CORVUS_NODE_INSTALL_FAKE_LIVE:-}" == "1" ]]; then
    return 0
  fi
  if unit_active; then
    return 0
  fi
  [[ -S "$(control_sock)" ]]
}

control_rpc() {
  local sock type_
  sock="$1"
  type_="$2"
  python3 - "$sock" "$type_" <<'PY' || true
import json
import socket
import sys

path, typ = sys.argv[1], sys.argv[2]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    s.settimeout(8)
    s.connect(path)
    s.sendall((json.dumps({"type": typ, "payload": {}}) + "\n").encode())
    s.recv(4096)
except OSError:
    sys.exit(1)
PY
}

stop_running_node() {
  local sock
  sock="$(control_sock)"
  if [[ -S "$sock" ]]; then
    control_rpc "$sock" stop
    run_sudo python3 - "$sock" <<'PY' || true
import json
import socket
import sys

path = sys.argv[1]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    s.settimeout(8)
    s.connect(path)
    s.sendall(b'{"type":"stop","payload":{}}\n')
    s.recv(4096)
except OSError:
    sys.exit(0)
PY
  fi
  if unit_active || [[ "${CORVUS_NODE_INSTALL_FAKE_LIVE:-}" == "1" ]]; then
    run_sudo systemctl stop corvus-node.service
  fi
}

if [[ "$SHOW_HELP" -eq 1 ]]; then
  usage
  exit 0
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  need "Linux (this is $(uname -s))"
  exit 1
fi

banner
sudo_story
pause

FAILED=0

echo "${C_BOLD}Host${C_RST}"
arch="$(uname -m)"
case "$arch" in
  x86_64 | aarch64) ok "Linux $arch" ;;
  *)
    need "this CPU isn't supported yet (need 64-bit Intel/AMD or ARM)"
    FAILED=1
    ;;
esac

if [[ "${CORVUS_NODE_INSTALL_FAKE_UID:-}" == "0" ]]; then
  need "run as your user, not root (so group $GROUP is your account). ./install.sh then sudo when asked."
  exit 1
fi
if [[ "$DRY" -eq 0 && "$(id -u)" -eq 0 ]]; then
  need "run as your user, not root (so group $GROUP is your account). ./install.sh then sudo when asked."
  exit 1
fi
ok "running as $(id -un)"

if ! command -v python3 >/dev/null; then
  need "python3 (3.12 or newer)"
  FAILED=1
else
  pyver="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
  if python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
    skip "python3 $pyver"
  else
    need "python3 $pyver (need 3.12+; no third-party PPAs — use Ubuntu 24.04 or similar)"
    FAILED=1
  fi
fi

if [[ "$FAILED" -ne 0 ]]; then
  echo
  need "fix the red lines, then ./install.sh again"
  exit 1
fi

echo
echo "${C_BOLD}Packages${C_RST}"
kind="$(pkg_kind)"
if [[ "$kind" == "none" ]]; then
  need "Debian/Ubuntu or Fedora/RHEL. Install Python 3, make, curl, and virtualization support."
  exit 1
fi

mapfile -t MISSING < <(missing_pkgs | awk 'NF')
if [[ ${#MISSING[@]} -eq 0 ]]; then
  skip "host packages ($kind)"
else
  doing "install ${MISSING[*]} ($kind — only what is missing)"
  pause
  if [[ "$kind" == "apt" ]]; then
    with_spin "apt-get update" run_sudo apt-get update -qq
    with_spin "apt-get install" run_sudo apt-get install -y "${MISSING[@]}"
  else
    with_spin "dnf install" run_sudo dnf install -y "${MISSING[@]}"
  fi
  ok "host packages"
fi

echo
echo "${C_BOLD}Virtualization${C_RST}"
if [[ -c /dev/kvm ]]; then
  skip "hardware isolation ready"
else
  doing "virtualization not ready — installing support, then re-check"
  if [[ "$kind" == "apt" ]]; then
    with_spin "qemu-kvm" run_sudo apt-get install -y qemu-kvm
  else
    with_spin "qemu-kvm" run_sudo dnf install -y qemu-kvm
  fi
  if [[ "$DRY" -eq 1 ]]; then
    need "virtualization (dry-run cannot turn it on)"
    echo
    need "turn virtualization on in firmware if this is a real install"
    exit 1
  fi
  if [[ ! -c /dev/kvm ]]; then
    need "virtualization still off (enable it in firmware). Not building the agent environment."
    exit 1
  fi
  ok "/dev/kvm"
fi

echo
echo "${C_BOLD}Agent environment${C_RST}"
if assets_current; then
  skip "agent disk"
else
  doing "build the agent disk (a few minutes the first time; no password)"
  pause
  if [[ "$DRY" -eq 1 ]]; then
    printf '  %sdry  bash guest/bake.sh%s\n' "$C_DIM" "$C_RST"
  else
    with_spin "building agent disk" bash "$ROOT/guest/bake.sh"
    if ! assets_current; then
      need "agent disk still incomplete after build"
      exit 1
    fi
    ok "guest assets"
  fi
fi

echo
echo "${C_BOLD}Corvus-Node ($(prefix_path))${C_RST}"
SOURCE="$(install_source)"
PIP_SRC="$ROOT"
WANT_VER=""
if [[ "$SOURCE" == "local" ]]; then
  if ! has_local_tree; then
    need "this directory has no Corvus-Node source (need pyproject.toml and src/corvus_node)"
    exit 1
  fi
  WANT_VER="$(tree_version)"
  if is_git_checkout; then
    ok "install from this git checkout ($WANT_VER)"
  else
    ok "install from this directory ($WANT_VER)"
  fi
else
  if [[ "$DRY" -eq 1 ]]; then
    WANT_VER="$(tree_version 2>/dev/null || echo release)"
    doing "would install from GitHub release"
  else
    doing "look up GitHub release"
    mapfile -t REL < <(github_release_lookup || true)
    WANT_VER="${REL[0]:-}"
    WHEEL_URL="${REL[1]:-}"
    if [[ -z "$WANT_VER" || -z "$WHEEL_URL" ]]; then
      need "no GitHub release yet. From a git clone, ./install.sh uses this checkout."
      exit 1
    fi
    CACHE="${CORVUS_NODE_CACHE:-$ROOT/.cache/corvus-node}"
    mkdir -p "$CACHE"
    PIP_SRC="$CACHE/corvus_node-${WANT_VER}.whl"
    doing "download GitHub release $WANT_VER"
    if ! curl -fsSL --retry 3 --retry-delay 2 -o "$PIP_SRC" "$WHEEL_URL"; then
      need "could not download $WHEEL_URL"
      exit 1
    fi
    ok "install from GitHub release $WANT_VER"
  fi
fi

HAVE_VER="$(installed_version || true)"
UNIT="/etc/systemd/system/corvus-node.service"
NEED_NODE=0
if [[ "$HAVE_VER" != "$WANT_VER" ]]; then
  NEED_NODE=1
fi
if [[ ! -f "$UNIT" ]]; then
  NEED_NODE=1
fi
if [[ ! -f "$(prefix_path)/env" ]]; then
  NEED_NODE=1
fi
if [[ "$SOURCE" == "local" ]] && source_newer_than_install; then
  NEED_NODE=1
fi

if [[ -n "$HAVE_VER" && -f "$UNIT" && -f "$(prefix_path)/env" && "$NEED_NODE" -eq 1 ]]; then
  cat <<EOF
${C_BOLD}Upgrade or keep${C_RST}

  Installed:  ${HAVE_VER}
  This run:   ${WANT_VER} ($SOURCE)

  Upgrade replaces the install. No keeps ${HAVE_VER}.

EOF
  if [[ "$DRY" -eq 1 ]]; then
    doing "would ask upgrade or keep"
  elif confirm_yes "Upgrade the install? No keeps ${HAVE_VER}."; then
    :
  else
    skip "keeping Corvus-Node $HAVE_VER"
    NEED_NODE=0
  fi
fi

STOPPED_LIVE=0
if [[ "$NEED_NODE" -eq 1 ]] && node_live; then
  cat <<EOF
${C_BOLD}Corvus-Node is already running${C_RST}

  Corvus-Node is up right now. We need to stop it before replacing the install
  (otherwise you would mix old and new files).

  If you say yes, we will:
    1. End the agent session if one is running
    2. Stop Corvus-Node in the background (password may be asked)
    3. Finish this install, then start Corvus-Node again

  To only end the chat session and leave Corvus-Node ready, cancel and run:
    corvus vm stop

EOF
  if [[ "$DRY" -eq 1 ]]; then
    doing "would stop Corvus-Node (dry-run)"
  elif confirm_yes "Stop Corvus-Node, then continue install?"; then
    doing "stop Corvus-Node"
    stop_running_node
    STOPPED_LIVE=1
    ok "Corvus-Node stopped"
  else
    need "install cancelled; Corvus-Node is still running"
    exit 2
  fi
elif node_live; then
  skip "Corvus-Node is running (keeping current version)"
else
  skip "Corvus-Node is not running"
fi

if [[ "$NEED_NODE" -eq 0 ]]; then
  skip "Corvus-Node $WANT_VER at $(prefix_path)"
else
  doing "install Corvus-Node into $(prefix_path)"
  pause
  export CORVUS_NODE_PREFIX="${CORVUS_NODE_PREFIX:-$(prefix_path)}"
  with_spin "install Node" run_sudo env \
    CORVUS_NODE_PREFIX="$CORVUS_NODE_PREFIX" \
    CORVUS_NODE_PIP_SRC="$PIP_SRC" \
    bash "$ROOT/packaging/install.sh"
  ok "Corvus-Node $WANT_VER"
  if [[ "$DRY" -eq 0 ]] && ! wait_corvus_up; then
    need "Corvus-Node did not come up after install; sudo systemctl status corvus-node"
  fi
fi

if [[ "$STOPPED_LIVE" -eq 1 && "$NEED_NODE" -eq 0 && "$DRY" -eq 0 ]]; then
  doing "start Corvus-Node (it was running before this install)"
  run_sudo systemctl start corvus-node.service
  if wait_corvus_up; then
    ok "Corvus-Node started"
  else
    need "Corvus-Node did not come up; ./install.sh again"
  fi
fi

LOCAL_BIN="${HOME}/.local/bin"
if [[ "$DRY" -eq 1 ]]; then
  skip "PATH wrapper (dry-run)"
else
  mkdir -p "$LOCAL_BIN"
  if [[ -x /usr/local/bin/corvus ]]; then
    ln -sfn /usr/local/bin/corvus "$LOCAL_BIN/corvus"
    ln -sfn /usr/local/bin/corvus "$LOCAL_BIN/corvus-node"
    skip "PATH /usr/local/bin/corvus"
  elif [[ -r "$(prefix_path)/bin/corvus" ]]; then
    install -m 0755 "$(prefix_path)/bin/corvus" "$LOCAL_BIN/corvus"
    ln -sfn "$LOCAL_BIN/corvus" "$LOCAL_BIN/corvus-node"
    ok "PATH $LOCAL_BIN/corvus"
  else
    doing "wait for /usr/local/bin/corvus after privileged install"
  fi
fi

echo
echo "${C_BOLD}Group $GROUP${C_RST}"
if in_group_session; then
  skip "group $GROUP (this session)"
elif in_group_file; then
  skip "group $GROUP (corvus uses it automatically)"
elif [[ "$DRY" -eq 1 ]]; then
  skip "group $GROUP (dry-run)"
else
  need "user $(id -un) is not in $GROUP after install"
  exit 1
fi

status_cmd() {
  local bin="" line out=""
  if [[ -x /usr/local/bin/corvus ]]; then
    bin=/usr/local/bin/corvus
  elif [[ -x "${HOME}/.local/bin/corvus" ]]; then
    bin="${HOME}/.local/bin/corvus"
  elif command -v corvus >/dev/null; then
    bin="$(command -v corvus)"
  fi
  if [[ -z "$bin" ]]; then
    need "corvus command not found"
    return 0
  fi
  if ! out="$("$bin" status --brief 2>/dev/null)"; then
    out="$("$bin" status 2>/dev/null || true)"
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      Node:\ up*)
        printf '  %s%s%s\n' "$C_OK" "$line" "$C_RST"
        ;;
      Node:\ down*|Hint:*)
        printf '  %s%s%s\n' "$C_NEED" "$line" "$C_RST"
        ;;
      VM:*)
        printf '  %s\n' "$line"
        ;;
    esac
  done <<< "$out"
}

if [[ "$DRY" -eq 0 ]]; then
  echo
  echo "${C_BOLD}Status${C_RST}"
  echo
  status_cmd
fi

echo
echo "${C_BOLD}You're set${C_RST}"
cat <<EOF
  ${C_BOLD}corvus status${C_RST}     ${C_DIM}# is Corvus-Node up?${C_RST}
  ${C_BOLD}corvus start${C_RST}      ${C_DIM}# bring Corvus-Node up; asks before the VM (Enter skips)${C_RST}
  ${C_BOLD}corvus vm start${C_RST}   ${C_DIM}# start the isolated agent${C_RST}
  ${C_BOLD}corvus chat${C_RST}       ${C_DIM}# talk to it; type /exit when done${C_RST}
  ${C_BOLD}corvus gui${C_RST}        ${C_DIM}# splash (this preview)${C_RST}
  ${C_BOLD}corvus vm stop${C_RST}    ${C_DIM}# end the session; Corvus-Node stays ready${C_RST}
  ${C_BOLD}corvus stop${C_RST}       ${C_DIM}# shut everything down (asks first)${C_RST}

  ${C_DIM}Black Rain Labs  ·  https://www.BlackRainLabs.com${C_RST}

EOF
exit 0

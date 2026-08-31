#!/bin/bash
# Guided Corvus-Node installer. Run as your user; sudo only when needed.
# Organization: Black Rain Labs — https://www.BlackRainLabs.com
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GROUP="${CORVUS_NODE_GROUP:-corvus}"
YES=0
DRY=0
if [[ "${CORVUS_NODE_INSTALL_YES:-}" == "1" ]]; then
  YES=1
fi
if [[ "${CORVUS_NODE_INSTALL_DRY:-}" == "1" ]]; then
  DRY=1
fi

for arg in "$@"; do
  case "$arg" in
    --yes | -y) YES=1 ;;
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

  ./install.sh          guided install (your user; sudo when needed)
  ./install.sh --yes    no "press Enter" pauses
  ./install.sh --help   this text

Sudo is for the Node service (Firecracker jailer, /dev/kvm) and root-owned
files under $HOME/Corvus-Node. Chat is not root. The model never gets a
root shell. Group corvus is for the control socket; this installer adds
you to that group and enters it in this terminal (you do not run newgrp).

The guest jail stays under /var/lib/corvus-node so vsock Unix paths fit.
EOF
}

banner() {
  cat <<EOF
${C_BOLD}
        .--.  Corvus-Node
       /v  v\\  security-first AI agent harness
      /(    )\\
       ^^  ^^
${C_RST}${C_DIM}  Black Rain Labs  ·  https://www.BlackRainLabs.com${C_RST}

EOF
}

sudo_story() {
  cat <<EOF
${C_BOLD}Why this script asks for your password${C_RST}

  Node (the host daemon) must run as root to launch Firecracker ${C_BOLD}jailer${C_RST}
  and open /dev/kvm. Isolation is a privileged VMM, not a user namespace.

  You do ${C_BOLD}not${C_RST} sudo to chat. After install, corvus vm start / chat / stop
  are your uid. The agent stays in the guest. Engine 3 cannot call tools.

  Under ${C_BOLD}\$HOME/Corvus-Node${C_RST}, venv/assets/run are root:${GROUP} so root
  does not execute code you can edit. The jail dir stays /var/lib/corvus-node
  (short path; vsock sockets have a 107-byte limit).

  This run may: install missing packages; bake a guest disk (no sudo);
  install Node + systemd; add you to group ${GROUP} and ${C_BOLD}enter that group
  in this terminal${C_RST} so you do not run newgrp yourself.

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

in_group_session() {
  id -nG 2>/dev/null | tr ' ' '\n' | grep -qx "$GROUP"
}

in_group_file() {
  getent group "$GROUP" >/dev/null 2>&1 || return 1
  local user
  user="$(id -un)"
  getent group "$GROUP" | awk -F: '{print $4}' | tr ',' '\n' | grep -qx "$user"
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
    need "CPU $arch is not x86_64 or aarch64"
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
  need "Debian/Ubuntu (apt) or Fedora/RHEL (dnf). Install: python3 make curl e2fsprogs mmdebstrap qemu-kvm"
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
echo "${C_BOLD}KVM${C_RST}"
if [[ -c /dev/kvm ]]; then
  skip "/dev/kvm"
else
  doing "no /dev/kvm — trying qemu-kvm, then re-check"
  if [[ "$kind" == "apt" ]]; then
    with_spin "qemu-kvm" run_sudo apt-get install -y qemu-kvm
  else
    with_spin "qemu-kvm" run_sudo dnf install -y qemu-kvm
  fi
  if [[ "$DRY" -eq 1 ]]; then
    need "/dev/kvm (dry-run cannot create the device)"
    echo
    need "enable virtualization in firmware if this is a real install"
    exit 1
  fi
  if [[ ! -c /dev/kvm ]]; then
    need "/dev/kvm still missing (enable virtualization in firmware / nested virt). Not baking."
    exit 1
  fi
  ok "/dev/kvm"
fi

echo
echo "${C_BOLD}Guest disk${C_RST}"
if assets_current; then
  skip "guest assets (hashed kernel, Firecracker, jailer, rootfs)"
else
  doing "bake guest assets (several minutes the first time; no sudo)"
  pause
  if [[ "$DRY" -eq 1 ]]; then
    printf '  %sdry  bash guest/bake.sh%s\n' "$C_DIM" "$C_RST"
  else
    with_spin "baking" bash "$ROOT/guest/bake.sh"
    if ! assets_current; then
      need "guest assets still incomplete after bake"
      exit 1
    fi
    ok "guest assets"
  fi
fi

echo
echo "${C_BOLD}Node ($HOME/Corvus-Node)${C_RST}"
WANT_VER="$(tree_version)"
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
if [[ "$NEED_NODE" -eq 0 ]]; then
  skip "Node $WANT_VER at $(prefix_path)"
else
  doing "privileged install → $(prefix_path) (root-owned venv; jail /var/lib/corvus-node)"
  pause
  export CORVUS_NODE_PREFIX="${CORVUS_NODE_PREFIX:-$(prefix_path)}"
  with_spin "install Node" run_sudo env CORVUS_NODE_PREFIX="$CORVUS_NODE_PREFIX" bash "$ROOT/packaging/install.sh"
  ok "Node $WANT_VER"
fi

LOCAL_BIN="${HOME}/.local/bin"
if [[ "$DRY" -eq 1 ]]; then
  skip "PATH symlink (dry-run)"
else
  mkdir -p "$LOCAL_BIN"
  if [[ -e "$(prefix_path)/bin/corvus" ]]; then
    ln -sfn "$(prefix_path)/bin/corvus" "$LOCAL_BIN/corvus"
    ln -sfn "$(prefix_path)/bin/corvus" "$LOCAL_BIN/corvus-node"
    if [[ ":$PATH:" == *":$LOCAL_BIN:"* ]]; then
      skip "PATH $LOCAL_BIN/corvus"
    else
      ok "linked $LOCAL_BIN/corvus (add $LOCAL_BIN to PATH if corvus is not found)"
    fi
  fi
fi

echo
echo "${C_BOLD}Group $GROUP${C_RST}"
if in_group_session; then
  skip "group $GROUP (this session)"
elif in_group_file || [[ "$DRY" -eq 1 ]]; then
  if [[ "$DRY" -eq 1 ]]; then
    printf '  %sdry  exec newgrp %s%s\n' "$C_DIM" "$GROUP" "$C_RST"
  else
    doing "this terminal is not in $GROUP yet — entering it for you (no newgrp to type)"
  fi
else
  doing "add $(id -un) to $GROUP"
  run_sudo true
  if in_group_file; then
    skip "group $GROUP (passwd)"
  else
    need "could not add $(id -un) to $GROUP"
    exit 1
  fi
fi

echo
echo "${C_BOLD}Ready${C_RST}"
cat <<EOF
  ${C_BOLD}corvus status${C_RST}
  ${C_BOLD}corvus vm start${C_RST}
  ${C_BOLD}corvus chat${C_RST}     ${C_DIM}# /exit leaves; VM stays up${C_RST}
  ${C_BOLD}corvus stop${C_RST}     ${C_DIM}# guest VM down; Node stays up${C_RST}

  ${C_DIM}Black Rain Labs  ·  https://www.BlackRainLabs.com${C_RST}

EOF

if [[ "$DRY" -eq 1 ]]; then
  exit 0
fi

status_cmd() {
  local bin
  bin="$(prefix_path)/bin/corvus"
  if [[ ! -x "$bin" ]]; then
    bin="corvus"
  fi
  if in_group_session; then
    "$bin" status || true
  elif command -v sg >/dev/null; then
    sg "$GROUP" -c "$bin status" || true
  else
    "$bin" status || true
  fi
}

if [[ -t 0 ]] && ! in_group_session && in_group_file && command -v newgrp >/dev/null; then
  echo "${C_DIM}This shell will continue in group $GROUP so corvus can open the control socket.${C_RST}"
  exec newgrp "$GROUP"
fi

status_cmd
exit 0

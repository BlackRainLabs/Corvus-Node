#!/bin/bash
# Report whether this host can bake guest assets and run Corvus-Node.
# Exit 0 if the machine can install and run a guest. Exit 1 lists what is missing.
# Organization: Black Rain Labs — Research & Development Division
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="${CORVUS_NODE_CACHE:-$ROOT/.cache/corvus-node}"
need=0

ok() { printf '  ok    %s\n' "$1"; }
need_line() { printf '  need  %s\n' "$1"; need=1; }
warn() { printf '  warn  %s\n' "$1"; }

echo "Corvus-Node host check"
echo

if [[ "$(uname -s)" != "Linux" ]]; then
  need_line "Linux (this is $(uname -s))"
else
  arch="$(uname -m)"
  case "$arch" in
    x86_64 | aarch64) ok "Linux $arch" ;;
    *) need_line "CPU $arch is not x86_64 or aarch64" ;;
  esac
fi

if ! command -v python3 >/dev/null; then
  need_line "python3 (3.12 or newer)"
else
  pyver="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
  if python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
    ok "python3 $pyver"
  else
    need_line "python3 $pyver (need 3.12 or newer)"
  fi
fi

for bin in make curl; do
  if command -v "$bin" >/dev/null; then
    ok "$bin"
  else
    need_line "$bin"
  fi
done

if command -v mkfs.ext4 >/dev/null; then
  ok "mkfs.ext4"
else
  need_line "mkfs.ext4 (package e2fsprogs)"
fi

baker=""
for c in mmdebstrap debootstrap docker; do
  if command -v "$c" >/dev/null; then
    baker="$c"
    break
  fi
done
if [[ -f "$CACHE/rootfs.ext4" ]]; then
  ok "guest disk already baked ($CACHE/rootfs.ext4)"
elif [[ -n "$baker" ]]; then
  ok "rootfs baker: $baker"
else
  need_line "mmdebstrap, debootstrap, or docker (to bake the guest disk)"
fi

if [[ -c /dev/kvm ]]; then
  ok "/dev/kvm"
else
  need_line "/dev/kvm (enable virtualization in firmware; install qemu-kvm or similar)"
fi

if command -v sudo >/dev/null; then
  ok "sudo"
else
  warn "sudo not in PATH (install needs root)"
fi

if getent group corvus >/dev/null 2>&1; then
  if id -nG 2>/dev/null | tr ' ' '\n' | grep -qx corvus; then
    ok "group corvus (this user)"
  else
    warn "group corvus exists; this user is not in it (./install.sh enters the group)"
  fi
else
  warn "group corvus not created yet (./install.sh adds it)"
fi

assets=0
for f in vmlinux rootfs.ext4 firecracker jailer; do
  if [[ -e "$CACHE/$f" ]]; then
    assets=$((assets + 1))
  fi
done
if [[ "$assets" -eq 4 ]]; then
  ok "guest assets in $CACHE"
else
  warn "guest assets not complete in $CACHE — next: ./install.sh (or make guest-assets)"
fi

if command -v systemctl >/dev/null && systemctl is-active --quiet corvus-node.service 2>/dev/null; then
  ok "Node service running"
elif command -v corvus >/dev/null; then
  warn "corvus is on PATH but the Node service is not active"
fi

echo
if [[ "$need" -ne 0 ]]; then
  echo "Not ready to run a guest. Fix the 'need' lines, then run: make check"
  echo "Unit tests without a VM still work after: python3 -m venv .venv && . .venv/bin/activate && pip install -e \".[dev]\" && make test"
  exit 1
fi
echo "Ready for:"
echo "  ./install.sh          # guided install into \$HOME/Corvus-Node"
echo "  or: make guest-assets && sudo make install"
echo "  corvus status && corvus start && corvus vm start && corvus chat"
exit 0

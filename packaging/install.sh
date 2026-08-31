#!/bin/bash
# Privileged install: venv, PATH wrapper, group, systemd. Runtime CLI does not need sudo.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_SYS="${PYTHON:-$(command -v python3)}"
PREFIX="${CORVUS_NODE_PREFIX:-/opt/corvus-node}"
VENV="$PREFIX/venv"
GROUP="${CORVUS_NODE_GROUP:-corvus}"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"
ENV_FILE="${ENV_FILE:-/etc/corvus-node/env}"
RUNTIME_DIR="${CORVUS_NODE_RUNTIME_DIR:-/var/lib/corvus-node}"
BIN_DIR="${BIN_DIR:-/usr/local/bin}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "corvus: install requires root (sudo make install)" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_SYS" ]]; then
  echo "corvus: python not found; set PYTHON=" >&2
  exit 1
fi

if ! getent group "$GROUP" >/dev/null; then
  groupadd --system "$GROUP"
fi
if [[ -n "${SUDO_USER:-}" ]]; then
  usermod -aG "$GROUP" "$SUDO_USER"
fi

install -d -m 0750 -o root -g "$GROUP" "$PREFIX" "$RUNTIME_DIR"
install -d -m 0755 /etc/corvus-node "$BIN_DIR"

"$PYTHON_SYS" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install "$ROOT"
ln -sfn "$VENV/bin/corvus" "$BIN_DIR/corvus"
ln -sfn "$VENV/bin/corvus" "$BIN_DIR/corvus-node"

CACHE="${CORVUS_NODE_CACHE:-$ROOT/.cache/corvus-node}"
ASSETS="$RUNTIME_DIR/assets"
install -d -m 0750 -o root -g "$GROUP" "$ASSETS"

copy_asset() {
  local src="$1"
  local name
  name="$(basename "$src")"
  if [[ -f "$src" ]]; then
    cp -a "$src" "$ASSETS/$name"
    if [[ -f "${src}.sha256" ]]; then
      cp -a "${src}.sha256" "$ASSETS/${name}.sha256"
    fi
    echo "$ASSETS/$name"
    return 0
  fi
  echo "$src"
}

KERNEL="${CORVUS_NODE_KERNEL:-}"
ROOTFS="${CORVUS_NODE_ROOTFS:-}"
FIRECRACKER="${CORVUS_NODE_FIRECRACKER:-}"
JAILER="${CORVUS_NODE_JAILER:-}"
if [[ -z "$KERNEL" ]]; then
  KERNEL="$(copy_asset "$CACHE/vmlinux")"
fi
if [[ -z "$ROOTFS" ]]; then
  ROOTFS="$(copy_asset "$CACHE/rootfs.ext4")"
fi
if [[ -z "$FIRECRACKER" ]]; then
  FIRECRACKER="$(copy_asset "$CACHE/firecracker")"
fi
if [[ -z "$JAILER" ]]; then
  JAILER="$(copy_asset "$CACHE/jailer")"
fi

{
  echo "CORVUS_NODE_KERNEL=$KERNEL"
  echo "CORVUS_NODE_ROOTFS=$ROOTFS"
  echo "CORVUS_NODE_FIRECRACKER=$FIRECRACKER"
  echo "CORVUS_NODE_JAILER=$JAILER"
  echo "CORVUS_NODE_RUNTIME_DIR=$RUNTIME_DIR"
} >"$ENV_FILE"
chmod 0640 "$ENV_FILE"
chown root:"$GROUP" "$ENV_FILE"

sed "s|PYTHON_PLACEHOLDER|$VENV/bin/python|" "$ROOT/packaging/corvus-node.service.in" \
  >"$UNIT_DIR/corvus-node.service"
chmod 0644 "$UNIT_DIR/corvus-node.service"

if command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
  systemctl daemon-reload
  systemctl enable --now corvus-node.service
fi

echo "corvus: installed to $PREFIX (CLI: $BIN_DIR/corvus)."
echo "If you were added to group $GROUP, log out and back in (or: newgrp $GROUP)."
echo "Then: corvus vm start   # no sudo; stop shuts down the guest VM first"
echo "Updates: corvus update  (sudo if the prefix is not writable; skipped on unreleased trees)"

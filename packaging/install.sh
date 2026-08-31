#!/bin/bash
# Privileged install into $HOME/Corvus-Node. Jailer chroots stay /var/lib/corvus-node.
# Organization: Black Rain Labs — Research & Development Division
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_SYS="${PYTHON:-$(command -v python3)}"
GROUP="${CORVUS_NODE_GROUP:-corvus}"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"
JAIL_DIR="${CORVUS_NODE_JAIL_DIR:-/var/lib/corvus-node}"

operator_home() {
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    getent passwd "$SUDO_USER" | cut -d: -f6
    return
  fi
  echo "${HOME}"
}

if [[ -n "${CORVUS_NODE_PREFIX:-}" ]]; then
  PREFIX="$CORVUS_NODE_PREFIX"
else
  PREFIX="$(operator_home)/Corvus-Node"
fi
VENV="$PREFIX/venv"
BIN_DIR="$PREFIX/bin"
RUNTIME_DIR="${CORVUS_NODE_RUNTIME_DIR:-$PREFIX/run}"
ASSETS="$PREFIX/assets"
ENV_FILE="${CORVUS_NODE_ENV_FILE:-$PREFIX/env}"
CACHE="${CORVUS_NODE_CACHE:-$ROOT/.cache/corvus-node}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "corvus: privileged install requires root (./install.sh invokes sudo)" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_SYS" ]]; then
  echo "corvus: python not found; set PYTHON=" >&2
  exit 1
fi

if ! getent group "$GROUP" >/dev/null; then
  groupadd --system "$GROUP"
fi
OP_USER="${SUDO_USER:-}"
if [[ -n "$OP_USER" && "$OP_USER" != "root" ]]; then
  usermod -aG "$GROUP" "$OP_USER"
fi

install -d -m 0750 -o root -g "$GROUP" "$PREFIX" "$VENV" "$RUNTIME_DIR" "$ASSETS" "$JAIL_DIR"
install -d -m 0755 -o root -g "$GROUP" "$BIN_DIR"

"$PYTHON_SYS" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install "$ROOT"
chown -R root:"$GROUP" "$VENV"
chmod -R u=rwX,g=rX,o= "$VENV"

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
chown -R root:"$GROUP" "$ASSETS"
chmod -R u=rwX,g=rX,o= "$ASSETS"

{
  echo "CORVUS_NODE_PREFIX=$PREFIX"
  echo "CORVUS_NODE_KERNEL=$KERNEL"
  echo "CORVUS_NODE_ROOTFS=$ROOTFS"
  echo "CORVUS_NODE_FIRECRACKER=$FIRECRACKER"
  echo "CORVUS_NODE_JAILER=$JAILER"
  echo "CORVUS_NODE_RUNTIME_DIR=$RUNTIME_DIR"
} >"$ENV_FILE"
chmod 0640 "$ENV_FILE"
chown root:"$GROUP" "$ENV_FILE"

cat >"$BIN_DIR/corvus" <<EOF
#!/bin/sh
# Corvus-Node operator CLI. Sources install env (group corvus).
set -eu
PREFIX="$PREFIX"
ENVF="\$PREFIX/env"
if [ -r "\$ENVF" ]; then
  set -a
  # shellcheck disable=SC1090
  . "\$ENVF"
  set +a
fi
exec "\$PREFIX/venv/bin/python" -m corvus_node "\$@"
EOF
chmod 0755 "$BIN_DIR/corvus"
chown root:"$GROUP" "$BIN_DIR/corvus"
ln -sfn "$BIN_DIR/corvus" "$BIN_DIR/corvus-node"

sed \
  -e "s|PYTHON_PLACEHOLDER|$VENV/bin/python|" \
  -e "s|ENV_FILE_PLACEHOLDER|$ENV_FILE|" \
  "$ROOT/packaging/corvus-node.service.in" \
  >"$UNIT_DIR/corvus-node.service"
chmod 0644 "$UNIT_DIR/corvus-node.service"

if command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
  systemctl daemon-reload
  systemctl enable --now corvus-node.service
fi

missing=0
for p in "$KERNEL" "$ROOTFS" "$FIRECRACKER" "$JAILER"; do
  if [[ ! -e "$p" ]]; then
    echo "corvus: missing guest asset: $p" >&2
    missing=1
  fi
done

echo "corvus: installed to $PREFIX (CLI: $BIN_DIR/corvus)."
echo "corvus: Firecracker jail dir $JAIL_DIR (short path for vsock)."
if [[ "$missing" -ne 0 ]]; then
  echo "corvus: guest assets were not in $CACHE."
  echo "corvus: from this checkout: ./install.sh   (or make guest-assets && sudo make install)"
fi

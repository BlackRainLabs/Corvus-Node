#!/usr/bin/env bash
# Fetch a pinned Firecracker kernel and bake a slim Debian guest rootfs.
# Organization: Black Rain Labs — Research & Development Division

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="${CORVUS_NODE_CACHE:-$REPO_ROOT/.cache/corvus-node}"
KERNEL_OUT="${CORVUS_NODE_KERNEL:-$CACHE/vmlinux}"
ROOTFS_OUT="${CORVUS_NODE_ROOTFS:-$CACHE/rootfs.ext4}"
ARCH="$(uname -m)"
IMAGE_MIB="${CORVUS_NODE_ROOTFS_MIB:-768}"

KERNEL_BASE="https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.13"
FC_VERSION="v1.16.1"
FC_OUT="${CORVUS_NODE_FIRECRACKER:-$CACHE/firecracker}"
JAILER_OUT="${CORVUS_NODE_JAILER:-$CACHE/jailer}"

case "$ARCH" in
  x86_64)
    KERNEL_URL="${KERNEL_BASE}/x86_64/vmlinux-6.1.141"
    KERNEL_SHA256="b36a4a1b10f33b9cfdcde3d1a787d9c090556a3edb211cd06d1f3f9a6c7e8724"
    PIP_PLATFORM="manylinux_2_17_x86_64"
    FC_TGZ_URL="https://github.com/firecracker-microvm/firecracker/releases/download/${FC_VERSION}/firecracker-${FC_VERSION}-x86_64.tgz"
    FC_TGZ_SHA256="382a02a869e4d6d5cb14c40577f9545e8458021ea8b0b2d3fc10ec14d9c242e6"
    FC_BIN_NAME="firecracker-${FC_VERSION}-x86_64"
    JAILER_BIN_NAME="jailer-${FC_VERSION}-x86_64"
    FC_BIN_SHA256="2fd0171309af7e24cf8dafc8a6f921c1434c49b5f9349bb996b7ed0a4deb8aa7"
    JAILER_BIN_SHA256="1f3a0c1fe86212d0001819bfe0819071c01208b3ccc9398c3b3bc1b84cf21edd"
    ;;
  aarch64)
    KERNEL_URL="${KERNEL_BASE}/aarch64/vmlinux-6.1.141"
    KERNEL_SHA256="69aa3308219ec1a070bc9a8e7f80c3b34056fed8ae05efb44e55f73b31adde44"
    PIP_PLATFORM="manylinux_2_17_aarch64"
    FC_TGZ_URL="https://github.com/firecracker-microvm/firecracker/releases/download/${FC_VERSION}/firecracker-${FC_VERSION}-aarch64.tgz"
    FC_TGZ_SHA256="8d0e69f6d6f9a1724551f607f18504052c16c1828ee3d4d7b6e6c73380871e0e"
    FC_BIN_NAME="firecracker-${FC_VERSION}-aarch64"
    JAILER_BIN_NAME="jailer-${FC_VERSION}-aarch64"
    FC_BIN_SHA256="71ca0733576579a75cef268a8fd0ae0629b761b9844559c611f144132ac6038a"
    JAILER_BIN_SHA256="7db39d34991ccdd8d12aacab384b1dcbe35e79c27823e4e4d33725d4b504edd7"
    ;;
  *)
    echo "guest/bake.sh: unsupported architecture $ARCH" >&2
    exit 1
    ;;
esac

echo "corvus: downloading Firecracker, a guest kernel, and baking a disk image."
echo "corvus: the first run often takes several minutes (Debian rootfs)."

mkdir -p "$(dirname "$KERNEL_OUT")" "$(dirname "$ROOTFS_OUT")" "$CACHE"

WORK=""
CID=""
cleanup() {
  if [[ -n "${CID:-}" ]]; then
    docker rm -f "$CID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${WORK:-}" ]]; then
    rm -rf "$WORK"
  fi
}
trap cleanup EXIT

require_hash() {
  local path="$1"
  local want="$2"
  local label="$3"
  local actual
  actual="$(sha256sum "$path" | awk '{print $1}')"
  if [[ "$actual" != "$want" ]]; then
    echo "$label sha256 mismatch (got $actual, want $want)" >&2
    return 1
  fi
}

fetch_kernel() {
  if [[ -f "$KERNEL_OUT" ]] && require_hash "$KERNEL_OUT" "$KERNEL_SHA256" "kernel"; then
    echo "kernel already present: $KERNEL_OUT"
    return 0
  fi
  local tmp
  tmp="$(mktemp "$CACHE/vmlinux.XXXXXX")"
  echo "fetching kernel: $KERNEL_URL"
  curl -fL --retry 3 --retry-delay 2 -o "$tmp" "$KERNEL_URL"
  if ! require_hash "$tmp" "$KERNEL_SHA256" "kernel"; then
    rm -f "$tmp"
    exit 1
  fi
  mv "$tmp" "$KERNEL_OUT"
  chmod 644 "$KERNEL_OUT"
}

fetch_firecracker() {
  if [[ -x "$FC_OUT" && -x "$JAILER_OUT" ]] \
    && require_hash "$FC_OUT" "$FC_BIN_SHA256" "firecracker" \
    && require_hash "$JAILER_OUT" "$JAILER_BIN_SHA256" "jailer"; then
    echo "firecracker already present: $FC_OUT"
    echo "jailer already present: $JAILER_OUT"
    return 0
  fi
  local tgz extract bin jailer actual
  tgz="$(mktemp "$CACHE/firecracker.tgz.XXXXXX")"
  extract="$(mktemp -d "$CACHE/fc-extract.XXXXXX")"
  echo "fetching firecracker: $FC_TGZ_URL"
  curl -fL --retry 3 --retry-delay 2 -o "$tgz" "$FC_TGZ_URL"
  actual="$(sha256sum "$tgz" | awk '{print $1}')"
  if [[ "$actual" != "$FC_TGZ_SHA256" ]]; then
    echo "firecracker tarball sha256 mismatch (got $actual, want $FC_TGZ_SHA256)" >&2
    rm -f "$tgz"
    rm -rf "$extract"
    exit 1
  fi
  tar -xzf "$tgz" -C "$extract"
  bin="$(find "$extract" -type f -name "$FC_BIN_NAME" -print -quit)"
  jailer="$(find "$extract" -type f -name "$JAILER_BIN_NAME" -print -quit)"
  if [[ -z "$bin" || -z "$jailer" ]]; then
    echo "guest/bake.sh: firecracker or jailer not found in tarball" >&2
    rm -f "$tgz"
    rm -rf "$extract"
    exit 1
  fi
  mkdir -p "$(dirname "$FC_OUT")" "$(dirname "$JAILER_OUT")"
  cp "$bin" "$FC_OUT"
  cp "$jailer" "$JAILER_OUT"
  chmod 755 "$FC_OUT" "$JAILER_OUT"
  require_hash "$FC_OUT" "$FC_BIN_SHA256" "firecracker"
  require_hash "$JAILER_OUT" "$JAILER_BIN_SHA256" "jailer"
  rm -f "$tgz"
  rm -rf "$extract"
}

install_payload() {
  local tree="$1"
  mkdir -p "$tree/opt/corvus/src" "$tree/opt/corvus/guest" "$tree/opt/corvus/vendor"
  mkdir -p "$tree/dev" "$tree/proc" "$tree/sys" "$tree/tmp" "$tree/run" "$tree/var/tmp"
  PYTHONPATH="$REPO_ROOT/src" python3 -c "
from pathlib import Path
from corvus_node.vm.guest_payload import install_into
install_into(Path('$tree'), Path('$REPO_ROOT'))
"
}

install_pydantic() {
  local tree="$1"
  if [[ -d "$tree/opt/corvus/vendor/pydantic" ]]; then
    echo "pydantic already present in rootfs tree"
    return 0
  fi
  python3 -m pip install --disable-pip-version-check --target "$tree/opt/corvus/vendor" \
    --python-version 3.11 --only-binary=:all: --implementation cp --abi cp311 \
    --platform "$PIP_PLATFORM" "pydantic>=2.9.0"
}

populate_debian_tree() {
  local tree="$1"
  mkdir -p "$tree"
  if command -v mmdebstrap >/dev/null 2>&1; then
    echo "baking rootfs with mmdebstrap"
    mmdebstrap --variant=minbase --include=python3 \
      bookworm "$tree" http://deb.debian.org/debian
    return 0
  fi
  if command -v debootstrap >/dev/null 2>&1; then
    echo "baking rootfs with debootstrap"
    debootstrap --variant=minbase --include=python3 \
      bookworm "$tree" http://deb.debian.org/debian
    return 0
  fi
  if command -v docker >/dev/null 2>&1; then
    echo "baking rootfs with docker (debian:bookworm-slim)"
    docker pull debian:bookworm-slim
    CID="$(docker create debian:bookworm-slim sleep 3600)"
    docker start "$CID" >/dev/null
    docker exec -e DEBIAN_FRONTEND=noninteractive "$CID" bash -c \
      "apt-get update && apt-get install -y --no-install-recommends python3"
    docker stop "$CID" >/dev/null
    docker export "$CID" | tar -C "$tree" --exclude=./dev --exclude=./proc --exclude=./sys -xf -
    docker rm -f "$CID" >/dev/null
    CID=""
    mkdir -p "$tree/dev" "$tree/proc" "$tree/sys"
    return 0
  fi
  echo "guest/bake.sh: need mmdebstrap, debootstrap, or docker to build the rootfs" >&2
  exit 1
}

pack_ext4() {
  local tree="$1"
  local tmp
  tmp="$(mktemp "$CACHE/rootfs.XXXXXX")"
  rm -rf "$tree/dev" "$tree/proc" "$tree/sys"
  mkdir -p "$tree/dev" "$tree/proc" "$tree/sys" "$tree/tmp" "$tree/run"
  truncate -s "${IMAGE_MIB}M" "$tmp"
  mkfs.ext4 -F -L corvus-guest -d "$tree" "$tmp"
  mv "$tmp" "$ROOTFS_OUT"
  chmod 644 "$ROOTFS_OUT"
  sha256sum "$ROOTFS_OUT" | awk '{print $1}' > "${ROOTFS_OUT}.sha256"
  echo "rootfs sha256: $(cat "${ROOTFS_OUT}.sha256")"
}

fetch_kernel
fetch_firecracker

if [[ -f "$ROOTFS_OUT" && "${CORVUS_NODE_FORCE_ROOTFS:-0}" != "1" && "${CORVUS_NODE_REFRESH_PAYLOAD:-0}" == "1" ]]; then
  if ! command -v debugfs >/dev/null 2>&1; then
    echo "guest/bake.sh: CORVUS_NODE_REFRESH_PAYLOAD=1 needs debugfs (e2fsprogs)" >&2
    exit 1
  fi
  WORK="$(mktemp -d "$CACHE/bake.XXXXXX")"
  TREE="$WORK/root"
  mkdir -p "$TREE"
  echo "refreshing guest payload in $ROOTFS_OUT"
  debugfs -R "rdump / $TREE" "$ROOTFS_OUT" >/dev/null
  install_payload "$TREE"
  install_pydantic "$TREE"
  pack_ext4 "$TREE"
elif [[ -f "$ROOTFS_OUT" && "${CORVUS_NODE_FORCE_ROOTFS:-0}" != "1" ]]; then
  echo "rootfs already present: $ROOTFS_OUT"
  if [[ ! -f "${ROOTFS_OUT}.sha256" ]]; then
    sha256sum "$ROOTFS_OUT" | awk '{print $1}' > "${ROOTFS_OUT}.sha256"
  fi
else
  WORK="$(mktemp -d "$CACHE/bake.XXXXXX")"
  TREE="$WORK/root"
  populate_debian_tree "$TREE"
  install_payload "$TREE"
  install_pydantic "$TREE"
  pack_ext4 "$TREE"
fi

echo "kernel: $KERNEL_OUT"
echo "rootfs: $ROOTFS_OUT"
echo "firecracker: $FC_OUT"
echo "jailer: $JAILER_OUT"
echo "Next: ./install.sh   (or: sudo make install; then corvus status; corvus vm start; corvus chat)"

#!/bin/sh
# PID 1 inside the Corvus-Node microVM. Mount as root, then drop to corvus.
# Organization: Black Rain Labs — Research & Development Division

set -eu

mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mount -t tmpfs tmpfs /tmp
mount -t tmpfs tmpfs /run
mkdir -p /var/tmp
mount -t tmpfs tmpfs /var/tmp

if [ -b /dev/vdb ]; then
  mount -t ext4 /dev/vdb /workspace
  chown 1000:1000 /workspace 2>/dev/null || true
fi

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/opt/corvus/src:/opt/corvus/vendor
export CORVUS_NODE_HOST_CID=2
export CORVUS_NODE_VSOCK_PORT=4040

# Drop privileges. Root is only for mounts.
exec python3 -c '
import os
os.setgid(1000)
os.setuid(1000)
os.execv("/usr/bin/python3", ["python3", "/opt/corvus/guest/run_guest.py", "--port", "4040"])
'

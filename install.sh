#!/bin/sh
# Corvus-Node operator entry. Run as your user (not root).
# Organization: Black Rain Labs — https://www.BlackRainLabs.com
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
exec bash "$ROOT/packaging/operator-install.sh" "$@"

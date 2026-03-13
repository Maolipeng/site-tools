#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: $(basename "$0") DOMAIN [healthcheck options...]" >&2
  exit 1
fi

DOMAIN="$1"
shift

run_sitectl healthcheck "$DOMAIN" "$@"

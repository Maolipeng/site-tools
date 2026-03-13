#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ $# -ne 1 ]]; then
  echo "Usage: $(basename "$0") DOMAIN" >&2
  exit 1
fi

DOMAIN="$1"

echo "== status =="
run_sitectl status "$DOMAIN"
echo
echo "== certificate =="
run_sitectl cert-info "$DOMAIN"

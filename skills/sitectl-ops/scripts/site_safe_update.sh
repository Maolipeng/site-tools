#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

usage() {
  echo "Usage: $(basename "$0") DOMAIN [update options...] [--apply]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

DOMAIN="$1"
shift

APPLY=0
ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--apply" ]]; then
    APPLY=1
  else
    ARGS+=("$arg")
  fi
done

echo "== dry run =="
run_sitectl update "$DOMAIN" "${ARGS[@]}" --dry-run

if [[ "$APPLY" -ne 1 ]]; then
  echo
  echo "Dry run only. Re-run with --apply to execute."
  exit 0
fi

echo
echo "== apply =="
run_sitectl update "$DOMAIN" "${ARGS[@]}"
echo
echo "== status =="
run_sitectl status "$DOMAIN"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

usage() {
  echo "Usage: $(basename "$0") [create options...] [--apply]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

APPLY=0
ARGS=()
DOMAIN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --domain)
      DOMAIN="${2:-}"
      ARGS+=("$1" "$2")
      shift 2
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$DOMAIN" ]]; then
  echo "--domain is required." >&2
  usage
  exit 1
fi

echo "== dry run =="
run_sitectl create "${ARGS[@]}" --dry-run

if [[ "$APPLY" -ne 1 ]]; then
  echo
  echo "Dry run only. Re-run with --apply to execute."
  exit 0
fi

echo
echo "== apply =="
run_sitectl create "${ARGS[@]}"
echo
echo "== status =="
run_sitectl status "$DOMAIN"

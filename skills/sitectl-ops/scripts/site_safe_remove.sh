#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

usage() {
  echo "Usage: $(basename "$0") DOMAIN [--apply]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

DOMAIN="$1"
shift
APPLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

echo "== dry run =="
run_sitectl remove "$DOMAIN" --dry-run

if [[ "$APPLY" -ne 1 ]]; then
  echo
  echo "Dry run only. Re-run with --apply to execute."
  exit 0
fi

echo
echo "== apply =="
run_sitectl remove "$DOMAIN"

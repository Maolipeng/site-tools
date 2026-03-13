#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"

resolve_sitectl_runner() {
  if [[ -n "${SITECTL_BIN:-}" ]]; then
    printf '%s\n' "$SITECTL_BIN"
    return 0
  fi

  if command -v sitectl >/dev/null 2>&1; then
    printf '%s\n' "sitectl"
    return 0
  fi

  if [[ -x "$REPO_ROOT/.venv/bin/sitectl" ]]; then
    printf '%s\n' "$REPO_ROOT/.venv/bin/sitectl"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3 -m sitectl"
    return 0
  fi

  echo "Unable to locate sitectl or python3." >&2
  exit 1
}

run_sitectl() {
  local runner
  runner="$(resolve_sitectl_runner)"

  if [[ "$runner" == "python3 -m sitectl" ]]; then
    PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -m sitectl "$@"
    return 0
  fi

  "$runner" "$@"
}

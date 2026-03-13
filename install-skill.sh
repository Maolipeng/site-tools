#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$ROOT_DIR/skills/sitectl-ops/scripts/install_skill.sh" "$@"

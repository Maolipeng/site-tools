#!/usr/bin/env bash
set -euo pipefail

DEFAULT_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage: uninstall-skill.sh [options]

Remove the sitectl-ops skill from one or more agent skill directories.

Options:
  --target TARGET       One of: codex, claude, opencode, openclaw, agents, all
                        Repeatable. Default: codex
  --scope SCOPE         One of: global, project. Default: global
  --project-root PATH   Project root used for project-local installs.
                        Default: repo root
  --path PATH           Remove from an explicit skills directory path
  -h, --help            Show this help message
EOF
}

target_root() {
  local target="$1"
  local scope="$2"
  local project_root="$3"
  case "$scope:$target" in
    global:codex) echo "${CODEX_HOME:-$HOME/.codex}/skills" ;;
    global:claude) echo "$HOME/.claude/skills" ;;
    global:opencode) echo "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills" ;;
    global:openclaw) echo "$HOME/.openclaw/skills" ;;
    global:agents) echo "$HOME/.agents/skills" ;;
    project:claude) echo "$project_root/.claude/skills" ;;
    project:opencode) echo "$project_root/.opencode/skills" ;;
    project:openclaw) echo "$project_root/skills" ;;
    project:agents) echo "$project_root/.agents/skills" ;;
    project:codex)
      echo "Project-local codex skills are not supported by this installer." >&2
      return 1
      ;;
    *)
      echo "Unsupported target/scope combination: $scope:$target" >&2
      return 1
      ;;
  esac
}

remove_one() {
  local target="$1"
  local scope="$2"
  local project_root="$3"
  local explicit_path="$4"
  local root path

  if [[ -n "$explicit_path" ]]; then
    root="$explicit_path"
  else
    root="$(target_root "$target" "$scope" "$project_root")"
  fi
  path="$root/sitectl-ops"

  if [[ -L "$path" || -e "$path" ]]; then
    rm -rf "$path"
    echo "Removed skill:"
    echo "  target: $target"
    echo "  scope: $scope"
    echo "  path: $path"
  else
    echo "Skill not installed:"
    echo "  target: $target"
    echo "  scope: $scope"
    echo "  path: $path"
  fi
}

targets=()
scope="global"
project_root="$DEFAULT_PROJECT_ROOT"
explicit_path=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      targets+=("$2")
      shift 2
      ;;
    --scope)
      scope="$2"
      shift 2
      ;;
    --project-root)
      project_root="$2"
      shift 2
      ;;
    --path)
      explicit_path="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ${#targets[@]} -eq 0 ]]; then
  targets=("codex")
fi

if [[ "$scope" != "global" && "$scope" != "project" ]]; then
  echo "Invalid scope: $scope" >&2
  exit 1
fi

expanded_targets=()
for target in "${targets[@]}"; do
  if [[ "$target" == "all" ]]; then
    expanded_targets+=("codex" "claude" "opencode" "openclaw" "agents")
  else
    expanded_targets+=("$target")
  fi
done

seen=" "
for target in "${expanded_targets[@]}"; do
  if [[ "$target" != "codex" && "$target" != "claude" && "$target" != "opencode" && "$target" != "openclaw" && "$target" != "agents" ]]; then
    echo "Invalid target: $target" >&2
    exit 1
  fi
  if [[ "$seen" == *" $target "* ]]; then
    continue
  fi
  seen+=" $target "
  remove_one "$target" "$scope" "$project_root" "$explicit_path"
done

#!/usr/bin/env bash
set -euo pipefail

SITECTL_ARCHIVE_URL="${SITECTL_ARCHIVE_URL:-}"
SITECTL_REPO_URL="${SITECTL_REPO_URL:-https://github.com/Maolipeng/site-tools}"
SITECTL_REF="${SITECTL_REF:-main}"
SITECTL_DOWNLOAD_DIR="${SITECTL_DOWNLOAD_DIR:-}"

usage() {
  cat <<'EOF'
Usage:
  curl -fsSL <raw-install-remote-url> | bash
  curl -fsSL <raw-install-remote-url> | SITECTL_ARCHIVE_URL=https://example.com/sitectl.tar.gz bash
  curl -fsSL <raw-install-remote-url> | SITECTL_REPO_URL=https://github.com/Maolipeng/site-tools bash -s -- --user

Environment:
  SITECTL_ARCHIVE_URL   Direct .tar.gz source archive URL for the sitectl project.
  SITECTL_REPO_URL      GitHub repository URL used to derive the archive URL.
                        Default: https://github.com/Maolipeng/site-tools
  SITECTL_REF           Git ref to download when SITECTL_REPO_URL is used. Default: main
  SITECTL_DOWNLOAD_DIR  Working directory to keep extracted files instead of a temporary directory.

Arguments:
  Any arguments after '--' are passed to the inner ./install.sh script.
EOF
}

derive_archive_url() {
  local repo_url="$1"
  if [[ "$repo_url" =~ ^https://github\.com/([^/]+)/([^/]+?)(\.git)?/?$ ]]; then
    local owner="${BASH_REMATCH[1]}"
    local repo="${BASH_REMATCH[2]}"
    printf 'https://github.com/%s/%s/archive/refs/heads/%s.tar.gz\n' "$owner" "$repo" "$SITECTL_REF"
    return 0
  fi
  return 1
}

download_file() {
  local url="$1"
  local output_path="$2"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$output_path"
    return 0
  fi

  if command -v wget >/dev/null 2>&1; then
    wget -qO "$output_path" "$url"
    return 0
  fi

  echo "Either curl or wget is required to download sitectl." >&2
  exit 1
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "$SITECTL_ARCHIVE_URL" ]]; then
  if ! SITECTL_ARCHIVE_URL="$(derive_archive_url "$SITECTL_REPO_URL")"; then
    echo "Unable to derive archive URL from SITECTL_REPO_URL: $SITECTL_REPO_URL" >&2
    exit 1
  fi
fi

WORK_DIR="$SITECTL_DOWNLOAD_DIR"
cleanup() {
  if [[ -z "$SITECTL_DOWNLOAD_DIR" && -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
    rm -rf "$WORK_DIR"
  fi
}
trap cleanup EXIT

if [[ -z "$WORK_DIR" ]]; then
  WORK_DIR="$(mktemp -d)"
else
  mkdir -p "$WORK_DIR"
fi

ARCHIVE_PATH="$WORK_DIR/sitectl.tar.gz"
EXTRACT_DIR="$WORK_DIR/extract"
mkdir -p "$EXTRACT_DIR"

download_file "$SITECTL_ARCHIVE_URL" "$ARCHIVE_PATH"
tar -xzf "$ARCHIVE_PATH" -C "$EXTRACT_DIR"

PROJECT_DIR="$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ -z "$PROJECT_DIR" || ! -f "$PROJECT_DIR/install.sh" ]]; then
  echo "Downloaded archive does not contain install.sh at the project root." >&2
  exit 1
fi

bash "$PROJECT_DIR/install.sh" "$@"

#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_MODE="venv"
EDITABLE=1
RUN_SMOKE_TEST=1
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/.venv}"

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --user          Install into the current user's site-packages.
  --system        Install into the current Python environment.
  --venv PATH     Create/use a virtual environment at PATH (default: ./.venv).
  --no-editable   Install the package normally instead of editable mode.
  --no-test       Skip the final "sitectl --help" smoke test.
  --python PATH   Use a specific Python interpreter.
  -h, --help      Show this help message.

Environment overrides:
  PYTHON_BIN      Python interpreter to use.
  VENV_DIR        Virtual environment path when using venv mode.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      INSTALL_MODE="user"
      shift
      ;;
    --system)
      INSTALL_MODE="system"
      shift
      ;;
    --venv)
      INSTALL_MODE="venv"
      VENV_DIR="$2"
      shift 2
      ;;
    --no-editable)
      EDITABLE=0
      shift
      ;;
    --no-test)
      RUN_SMOKE_TEST=0
      shift
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required.")
PY

ensure_pip() {
  local python_bin="$1"
  if ! "$python_bin" -m pip --version >/dev/null 2>&1; then
    "$python_bin" -m ensurepip --upgrade >/dev/null
  fi
}

write_launcher() {
  local launcher_path="$1"
  local python_bin="$2"
  local source_root="$3"
  cat >"$launcher_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH="$source_root\${PYTHONPATH:+:\$PYTHONPATH}" exec "$python_bin" -m sitectl "\$@"
EOF
  chmod +x "$launcher_path"
}

install_package() {
  local python_bin="$1"
  if [[ "$EDITABLE" -eq 1 ]]; then
    "$python_bin" -m pip install --no-build-isolation -e "$PROJECT_DIR"
  else
    "$python_bin" -m pip install --no-build-isolation "$PROJECT_DIR"
  fi
}

print_success() {
  local sitectl_bin="$1"
  echo
  echo "Installation complete."
  echo "Command path: $sitectl_bin"
  echo
  echo "Examples:"
  echo "  $sitectl_bin --help"
  echo "  $sitectl_bin doctor"
}

if [[ "$INSTALL_MODE" == "venv" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  VENV_PYTHON="$VENV_DIR/bin/python"
  SITECTL_BIN="$VENV_DIR/bin/sitectl"
  if [[ "$EDITABLE" -eq 1 ]]; then
    SOURCE_ROOT="$PROJECT_DIR"
  else
    SITE_PACKAGES="$("$VENV_PYTHON" - <<'PY'
import sysconfig
print(sysconfig.get_path("purelib"))
PY
)"
    "$VENV_PYTHON" - "$PROJECT_DIR" "$SITE_PACKAGES" <<'PY'
import shutil
import sys
from pathlib import Path

project_dir = Path(sys.argv[1])
site_packages = Path(sys.argv[2])
site_packages.mkdir(parents=True, exist_ok=True)
shutil.copytree(project_dir / "sitectl", site_packages / "sitectl", dirs_exist_ok=True)
PY
    SOURCE_ROOT="$SITE_PACKAGES"
  fi
  write_launcher "$SITECTL_BIN" "$VENV_PYTHON" "$SOURCE_ROOT"
  if [[ "$RUN_SMOKE_TEST" -eq 1 ]]; then
    "$SITECTL_BIN" --help >/dev/null
  fi
  print_success "$SITECTL_BIN"
  echo
  echo "To use 'sitectl' directly in your shell:"
  echo "  source \"$VENV_DIR/bin/activate\""
  exit 0
fi

ensure_pip "$PYTHON_BIN"
install_package "$PYTHON_BIN"

if [[ "$INSTALL_MODE" == "user" ]]; then
  USER_BASE="$("$PYTHON_BIN" -m site --user-base)"
  SITECTL_BIN="$USER_BASE/bin/sitectl"
else
  SITECTL_BIN="$(command -v sitectl || true)"
  if [[ -z "$SITECTL_BIN" ]]; then
    SITECTL_BIN="sitectl"
  fi
fi

if [[ "$RUN_SMOKE_TEST" -eq 1 ]]; then
  if [[ -x "$SITECTL_BIN" ]]; then
    "$SITECTL_BIN" --help >/dev/null
  else
    "$PYTHON_BIN" -m sitectl --help >/dev/null
  fi
fi

print_success "$SITECTL_BIN"

if [[ "$INSTALL_MODE" == "user" ]]; then
  echo
  echo "If '$SITECTL_BIN' is not found, add this to PATH:"
  echo "  export PATH=\"$USER_BASE/bin:\$PATH\""
fi

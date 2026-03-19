#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"
INSTALL_MODE="venv"
EDITABLE=1
RUN_SMOKE_TEST=1
AUTO_INSTALL_DEPS="${AUTO_INSTALL_DEPS:-1}"
INTERACTIVE_MODE=0
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/.venv}"
TOTAL_STEPS=6
CURRENT_STEP=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --user          Install into the current user's site-packages.
  --system        Install into the current Python environment.
  --venv PATH     Create/use a virtual environment at PATH (default: ./.venv).
  --no-editable   Install the package normally instead of editable mode.
  --no-test       Skip the final "sitectl --help" smoke test.
  --no-install-deps
                  Skip auto-installing missing system dependencies.
  --interactive   Prompt for installation choices in the terminal.
  --python PATH   Use a specific Python interpreter.
  -h, --help      Show this help message.

Environment overrides:
  PYTHON_BIN      Python interpreter to use.
  VENV_DIR        Virtual environment path when using venv mode.
  AUTO_INSTALL_DEPS
                  Set to 0 to disable auto-installing missing system dependencies.
EOF
}

log_step() {
  CURRENT_STEP=$((CURRENT_STEP + 1))
  printf '[%d/%d] %s\n' "$CURRENT_STEP" "$TOTAL_STEPS" "$1"
}

log_info() {
  printf '      %s\n' "$1"
}

prompt_read() {
  local prompt_text="$1"
  local response
  printf '%s' "$prompt_text" >/dev/tty
  IFS= read -r response </dev/tty
  printf '%s' "$response"
}

prompt_with_default() {
  local label="$1"
  local current="$2"
  local response
  response="$(prompt_read "$label [$current]: ")"
  if [[ -z "$response" ]]; then
    printf '%s\n' "$current"
  else
    printf '%s\n' "$response"
  fi
}

prompt_yes_no() {
  local label="$1"
  local current="$2"
  local default_hint="Y/n"
  if [[ "$current" == "0" ]]; then
    default_hint="y/N"
  fi

  while true; do
    local response
    response="$(prompt_read "$label [$default_hint]: ")"
    if [[ -z "$response" ]]; then
      printf '%s\n' "$current"
      return
    fi
    case "${response,,}" in
      y|yes)
        printf '1\n'
        return
        ;;
      n|no)
        printf '0\n'
        return
        ;;
    esac
    printf 'Please answer y or n.\n' >/dev/tty
  done
}

run_interactive_setup() {
  if [[ ! -r /dev/tty || ! -w /dev/tty ]]; then
    echo "Interactive mode requires a terminal." >&2
    exit 1
  fi

  log_step "Collecting interactive installation choices"
  log_info "Interactive mode enabled"

  local mode_default="$INSTALL_MODE"
  while true; do
    INSTALL_MODE="$(prompt_with_default "Installation mode (venv/user/system)" "$mode_default")"
    case "$INSTALL_MODE" in
      venv|user|system)
        break
        ;;
    esac
    printf 'Please choose one of: venv, user, system.\n' >/dev/tty
  done

  if [[ "$INSTALL_MODE" == "venv" ]]; then
    VENV_DIR="$(prompt_with_default "Virtual environment path" "$VENV_DIR")"
  fi

  EDITABLE="$(prompt_yes_no "Install in editable mode?" "$EDITABLE")"
  AUTO_INSTALL_DEPS="$(prompt_yes_no "Auto-install missing system dependencies?" "$AUTO_INSTALL_DEPS")"
  RUN_SMOKE_TEST="$(prompt_yes_no "Run final smoke test?" "$RUN_SMOKE_TEST")"

  local python_default="${PYTHON_BIN:-auto-detect}"
  local python_choice
  python_choice="$(prompt_with_default "Python interpreter" "$python_default")"
  if [[ "$python_choice" == "auto-detect" ]]; then
    PYTHON_BIN=""
  else
    PYTHON_BIN="$python_choice"
  fi
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

run_with_privilege() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi
  if command_exists sudo; then
    log_info "Requesting sudo privileges for: $*"
    log_info "If prompted, enter your sudo password to continue"
    sudo "$@"
    return
  fi
  echo "Need root privileges to install system dependencies: $*" >&2
  exit 1
}

detect_package_manager() {
  if command_exists apt-get; then
    printf '%s\n' "apt"
    return
  fi
  if command_exists dnf; then
    printf '%s\n' "dnf"
    return
  fi
  if command_exists yum; then
    printf '%s\n' "yum"
    return
  fi
  if command_exists brew; then
    printf '%s\n' "brew"
    return
  fi
  printf '%s\n' "unknown"
}

supported_python_candidate() {
  local candidates=(python3 python3.13 python3.12 python3.11)
  local candidate
  for candidate in "${candidates[@]}"; do
    if command_exists "$candidate" && python_version_supported "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

install_system_packages() {
  local package_manager="$1"
  shift
  local packages=("$@")
  if [[ "${#packages[@]}" -eq 0 ]]; then
    return
  fi

  log_info "Installing system packages via $package_manager: ${packages[*]}"

  case "$package_manager" in
    apt)
      run_with_privilege apt-get update
      run_with_privilege apt-get install -y "${packages[@]}"
      ;;
    dnf)
      run_with_privilege dnf install -y "${packages[@]}"
      ;;
    yum)
      run_with_privilege yum install -y "${packages[@]}"
      ;;
    brew)
      brew install "${packages[@]}"
      ;;
    *)
      echo "Unable to auto-install packages because no supported package manager was found." >&2
      exit 1
      ;;
  esac
}

ensure_pm2_installed() {
  if command_exists pm2; then
    return
  fi

  if ! command_exists npm; then
    echo "npm is required to install pm2 automatically." >&2
    exit 1
  fi

  log_info "Installing pm2 globally with npm"

  if [[ "$(id -u)" -eq 0 ]]; then
    npm install -g pm2
    return
  fi
  if command_exists sudo; then
    log_info "Requesting sudo privileges for: npm install -g pm2"
    log_info "If prompted, enter your sudo password to continue"
    sudo npm install -g pm2
    return
  fi

  echo "Need root privileges to install pm2 globally with npm." >&2
  exit 1
}

ensure_system_dependencies() {
  log_step "Checking system dependencies"
  if [[ "${AUTO_INSTALL_DEPS}" == "0" ]]; then
    log_info "Auto-install disabled; skipping system dependency installation"
    return
  fi

  local missing_commands=()
  local command_name
  for command_name in nginx certbot openssl node npm pm2; do
    if ! command_exists "$command_name"; then
      missing_commands+=("$command_name")
    fi
  done

  if [[ "${#missing_commands[@]}" -eq 0 ]]; then
    log_info "All required system dependencies are already available"
    return
  fi

  echo "Missing system dependencies detected: ${missing_commands[*]}"

  local package_manager
  package_manager="$(detect_package_manager)"
  local packages=()
  local need_pm2=0
  local is_linux=0
  if [[ "$(uname -s)" == "Linux" ]]; then
    is_linux=1
  fi

  local has_node=0
  local has_certbot=0
  local has_openssl=0
  local has_nginx=0
  local has_ip=0
  local need_systemd_tools=0

  for command_name in "${missing_commands[@]}"; do
    case "$command_name" in
      nginx)
        has_nginx=1
        ;;
      certbot)
        has_certbot=1
        ;;
      openssl)
        has_openssl=1
        ;;
      node|npm)
        has_node=1
        ;;
      pm2)
        need_pm2=1
        ;;
    esac
  done

  if [[ "$is_linux" -eq 1 ]]; then
    if ! command_exists ip; then
      has_ip=1
    fi
    if [[ -d /run/systemd/system ]] && { ! command_exists systemctl || ! command_exists journalctl; }; then
      need_systemd_tools=1
    fi
  fi

  case "$package_manager" in
    apt)
      [[ "$has_nginx" -eq 1 ]] && packages+=(nginx)
      if [[ "$has_certbot" -eq 1 ]]; then
        packages+=(certbot python3-certbot-nginx)
      fi
      [[ "$has_openssl" -eq 1 ]] && packages+=(openssl)
      [[ "$has_node" -eq 1 ]] && packages+=(nodejs npm)
      [[ "$has_ip" -eq 1 ]] && packages+=(iproute2)
      [[ "$need_systemd_tools" -eq 1 ]] && packages+=(systemd)
      ;;
    dnf|yum)
      [[ "$has_nginx" -eq 1 ]] && packages+=(nginx)
      if [[ "$has_certbot" -eq 1 ]]; then
        packages+=(certbot python3-certbot-nginx)
      fi
      [[ "$has_openssl" -eq 1 ]] && packages+=(openssl)
      [[ "$has_node" -eq 1 ]] && packages+=(nodejs npm)
      [[ "$has_ip" -eq 1 ]] && packages+=(iproute)
      [[ "$need_systemd_tools" -eq 1 ]] && packages+=(systemd)
      ;;
    brew)
      [[ "$has_nginx" -eq 1 ]] && packages+=(nginx)
      [[ "$has_certbot" -eq 1 ]] && packages+=(certbot)
      [[ "$has_openssl" -eq 1 ]] && packages+=(openssl)
      [[ "$has_node" -eq 1 ]] && packages+=(node)
      ;;
  esac

  if [[ "${#packages[@]}" -gt 0 ]]; then
    install_system_packages "$package_manager" "${packages[@]}"
  fi
  if [[ "$need_pm2" -eq 1 ]]; then
    ensure_pm2_installed
  fi
  log_info "System dependency installation finished"
}

python_version_supported() {
  local python_bin="$1"
  "$python_bin" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

install_python_runtime() {
  local package_manager="$1"
  local packages=()

  case "$package_manager" in
    apt)
      packages=(python3.11 python3.11-venv)
      ;;
    dnf|yum)
      packages=(python3.11)
      ;;
    brew)
      packages=(python@3.11)
      ;;
    *)
      return 1
      ;;
  esac

  log_info "No usable Python 3.11+ detected; attempting automatic installation"
  install_system_packages "$package_manager" "${packages[@]}"
}

select_python_bin() {
  log_step "Selecting Python interpreter"
  if [[ -n "$PYTHON_BIN" ]]; then
    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
      echo "Python interpreter not found: $PYTHON_BIN" >&2
      exit 1
    fi
    if ! python_version_supported "$PYTHON_BIN"; then
      local detected_version
      detected_version="$("$PYTHON_BIN" -V 2>&1 || true)"
      echo "${detected_version:-$PYTHON_BIN} is too old. Python 3.11+ is required." >&2
      exit 1
    fi
    log_info "Using explicit Python interpreter: $PYTHON_BIN"
    return
  fi

  local candidate
  if candidate="$(supported_python_candidate)"; then
    PYTHON_BIN="$candidate"
    log_info "Using detected Python interpreter: $PYTHON_BIN"
    return
  fi

  if [[ "${AUTO_INSTALL_DEPS}" != "0" ]]; then
    local package_manager
    package_manager="$(detect_package_manager)"
    if install_python_runtime "$package_manager"; then
      if candidate="$(supported_python_candidate)"; then
        PYTHON_BIN="$candidate"
        log_info "Using auto-installed Python interpreter: $PYTHON_BIN"
        return
      fi
    fi
  fi

  local detected_version="not found"
  if command -v python3 >/dev/null 2>&1; then
    detected_version="$(python3 -V 2>&1 || true)"
  fi
  cat >&2 <<EOF
Unable to find a usable Python 3.11+ interpreter.
Detected python3: $detected_version

Install Python 3.11+ and retry, or run with an explicit interpreter, for example:
  PYTHON_BIN=python3.11 bash install.sh
EOF
  exit 1
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
    --no-install-deps)
      AUTO_INSTALL_DEPS=0
      shift
      ;;
    --interactive)
      INTERACTIVE_MODE=1
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

if [[ "$INTERACTIVE_MODE" -eq 1 ]]; then
  run_interactive_setup
fi

ensure_system_dependencies
select_python_bin

ensure_pip() {
  local python_bin="$1"
  if ! "$python_bin" -m pip --version >/dev/null 2>&1; then
    log_info "pip not found for $python_bin; bootstrapping with ensurepip"
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
    log_info "Installing sitectl in editable mode with $python_bin"
  else
    log_info "Installing sitectl in standard mode with $python_bin"
  fi
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

print_path_hint() {
  local path_dir="$1"
  echo
  echo "To add 'sitectl' to your zsh PATH permanently, append this to ~/.zshrc:"
  echo "  # site-tools"
  echo "  export PATH=\"$path_dir:\$PATH\""
}

if [[ "$INSTALL_MODE" == "venv" ]]; then
  log_step "Creating virtual environment"
  log_info "Virtual environment path: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  VENV_PYTHON="$VENV_DIR/bin/python"
  SITECTL_BIN="$VENV_DIR/bin/sitectl"
  if [[ "$EDITABLE" -eq 1 ]]; then
    SOURCE_ROOT="$PROJECT_DIR"
  else
    log_step "Copying package sources into the virtual environment"
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
  if [[ "$EDITABLE" -eq 1 ]]; then
    log_step "Linking launcher to the project source tree"
  fi
  write_launcher "$SITECTL_BIN" "$VENV_PYTHON" "$SOURCE_ROOT"
  if [[ "$RUN_SMOKE_TEST" -eq 1 ]]; then
    log_step "Running smoke test"
    log_info "Executing: $SITECTL_BIN --help"
    "$SITECTL_BIN" --help >/dev/null
  else
    log_step "Skipping smoke test"
  fi
  log_step "Finishing installation"
  print_success "$SITECTL_BIN"
  print_path_hint "$VENV_DIR/bin"
  echo
  echo "To use 'sitectl' directly in your shell:"
  echo "  source \"$VENV_DIR/bin/activate\""
  exit 0
fi

log_step "Preparing Python package installation"
ensure_pip "$PYTHON_BIN"
log_step "Installing Python package"
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
  log_step "Running smoke test"
  if [[ -x "$SITECTL_BIN" ]]; then
    log_info "Executing: $SITECTL_BIN --help"
    "$SITECTL_BIN" --help >/dev/null
  else
    log_info "Executing: $PYTHON_BIN -m sitectl --help"
    "$PYTHON_BIN" -m sitectl --help >/dev/null
  fi
else
  log_step "Skipping smoke test"
fi

log_step "Finishing installation"
print_success "$SITECTL_BIN"

if [[ "$INSTALL_MODE" == "user" ]]; then
  echo
  echo "If '$SITECTL_BIN' is not found, add this to PATH:"
  echo "  export PATH=\"$USER_BASE/bin:\$PATH\""
  print_path_hint "$USER_BASE/bin"
fi

#!/bin/zsh
set -euo pipefail

echo "Stopping Homebrew nginx so Tailscale can take over :443..."
brew services stop nginx || true
sleep 2

echo "Starting Tailscale..."
open -a Tailscale
sleep 2

echo
echo "Current :443 listeners:"
lsof -nP -iTCP:443 -sTCP:LISTEN || true

echo
echo "Current nginx service state:"
brew services list | grep nginx || true


#!/bin/zsh
set -euo pipefail

echo "Stopping Tailscale so nginx can take over :443..."
osascript -e 'tell application "Tailscale" to quit' >/dev/null 2>&1 || true
sleep 2

echo "Restarting Homebrew nginx..."
brew services restart nginx
sleep 2

echo
echo "Current :443 listeners:"
lsof -nP -iTCP:443 -sTCP:LISTEN || true

echo
echo "Current nginx service state:"
brew services list | grep nginx || true


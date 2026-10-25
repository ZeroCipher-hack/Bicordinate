#!/bin/bash
# Barcha CTF konteynerlarini to'xtatadi (sayt — up.sh ni Ctrl+C bilan to'xtatiladi).
set -euo pipefail
cd "$(dirname "$0")"
docker compose --env-file .flags.env down
docker ps -aq --filter "name=bico-" | xargs -r docker rm -f
echo "Konteynerlar to'xtatildi."

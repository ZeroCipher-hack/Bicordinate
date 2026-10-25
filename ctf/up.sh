#!/bin/bash
# BICO CTF — hammasini ishga tushiradi: masalalar, docker image'lar, konteynerlar, sayt.
#
# Ishlatish:
#   ./up.sh
#   CTF_START="2026-10-26T10:00:00+05:00" CTF_END="2026-10-26T13:00:00+05:00" ./up.sh
#
# Talab: Linux, Docker (daemon ishlab turgan bo'lishi kerak — `docker info` xato bermasin), Python 3.10+.
set -euo pipefail
cd "$(dirname "$0")"

say() { echo; echo "== $1 =="; }

say "1/6 Docker tekshirilmoqda"
if ! docker info >/dev/null 2>&1; then
  echo "XATO: Docker daemon ishlamayapti. 'sudo systemctl start docker' yoki Docker Desktop'ni oching." >&2
  exit 1
fi

say "2/6 Python kutubxonalari (alohida virtual muhitda — .venv/)"
[ -d .venv ] || python3 -m venv .venv
PY=.venv/bin/python
$PY -m pip install -q --upgrade pip
$PY -m pip install -q pillow pyyaml aiohttp flask

say "3/6 Masalalarni generatsiya qilish (build.py)"
$PY build.py

say "4/6 Tekshirish — barcha masalalar yechiladimi (check.py)"
if ! $PY check.py; then
  echo
  echo "XATO: yuqorida FAIL bo'lgan masala(lar) bor. Musobaqani boshlamang, avval shuni tuzating." >&2
  exit 1
fi

say "5/6 Docker image va konteynerlar (shell, web masalalar, machine)"
docker build -t bico-shell app/shell
docker compose --env-file .flags.env up -d --build

say "5.5/6 SSH 'machine' sinovi"
sleep 2
M_USER=$(grep ^M_USER= app/machine/setup.env | cut -d= -f2)
if docker compose --env-file .flags.env exec -T machine true 2>/dev/null; then
  echo "machine konteyner ishlamoqda. Qo'lda sinang:"
  echo "  ssh ${M_USER}@$(hostname -I 2>/dev/null | awk '{print $1}') -p 2222"
else
  echo "OGOHLANTIRISH: machine konteynerini tekshirib bo'lmadi — 'docker compose logs machine' ni ko'ring." >&2
fi

say "6/6 Sayt ishga tushmoqda (to'xtatish uchun Ctrl+C — konteynerlar ishlashda davom etadi)"
export TERM_MODE=docker
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "Sayt:    http://${IP:-SERVER_IP}:${PORT:-8080}"
echo "Web masalalar: 8001-8004, SSH machine: 2222"
[ -n "${CTF_START:-}" ] && echo "Boshlanish: $CTF_START"
[ -n "${CTF_END:-}" ] && echo "Tugash:     $CTF_END"
exec $PY app/server.py

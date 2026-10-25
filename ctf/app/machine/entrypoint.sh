#!/bin/bash
# setup.env dagi xeshni operator foydalanuvchisiga o'rnatadi, keyin sshd ni ishga tushiradi.
set -euo pipefail
source /setup.env
echo "${M_USER}:${M_PASS_HASH}" | chpasswd -e
exec /usr/sbin/sshd -D -e

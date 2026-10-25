#!/usr/bin/env python3
"""CTF masalalarini yig'adi: fayllar, challenge.yml (ctfcli) va .flags.env (docker-compose uchun).

Ishlatish:  python3 build.py        (Pillow kerak:  pip install pillow pyyaml)
Natija:     challenges/<kategoriya>/<slug>/{challenge.yml, fayllar}   — gitignore'da
"""
import base64
import codecs
import json
import random
import zlib
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).parent
OUT = ROOT / "challenges"
AUTHOR = "Bicoordinate"
HOST = "http://YOUR_HOST"  # README'da: o'zingizning server IP/domeningiz bilan almashtiring
rng = random.Random(20261025)  # deterministik: har safar bir xil fayllar

FLAGS = {
    "welcome": "BICO{xush_kelibsiz_jamoa}",
    "robots": "BICO{robots_txt_hamma_narsani_aytadi}",
    "cookie": "BICO{cookie_ishonchli_emas}",
    "sqli": "BICO{sql_inyeksiya_klassik}",
    "idor": "BICO{id_ni_almashtirish_yetarli}",
    "caesar": "BICO{sezar_7_qadam}",
    "layers": "BICO{base64_hex_rot13_qatlamlar}",
    "xor": "BICO{bir_baytli_xor_zaif}",
    "rsa": "BICO{e3_va_kichik_xabar}",
    "strings": "BICO{rasm_ichida_matn_bor}",
    "logs": "BICO{log_ichidan_topding}",
}

CHALLENGES = []  # (category, slug, name, value, description, files, web_port)


def add(cat, slug, name, value, desc, files=(), port=None, hints=()):
    CHALLENGES.append((cat, slug, name, value, desc, list(files), port, list(hints)))


def write(cat, slug, fname, data):
    d = OUT / cat / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / fname).write_bytes(data if isinstance(data, bytes) else data.encode())


# ---------------------------------------------------------------- misc
add("misc", "welcome", "Xush kelibsiz", 10,
    f"Flag formati: `BICO{{...}}`. Quyidagi flagni kiriting va sinab ko'ring:\n\n`{FLAGS['welcome']}`")

# ---------------------------------------------------------------- web
add("web", "robots", "Robot nima deydi?", 50,
    "Saytlar qidiruv robotlariga qayerga kirmaslikni aytadigan bitta fayl bor. Aynan shu yerga kiring.",
    port=8001, hints=["/robots.txt"])
add("web", "cookie", "Mehmon va admin", 100,
    "Sayt sizni mehmon deb biladi. Brauzeringiz sizga nima berganini ko'ring (DevTools → Application → Cookies).",
    port=8002, hints=["Cookie qiymati juda tanish ko'rinadi: oxirida `=` bor."])
add("web", "sqli", "Admin paroli yo'q", 150,
    "Admin parolini bilmaysiz. Lekin kirish formasi serverga nima yuborayotganiga unchalik ehtiyot emas.",
    port=8003, hints=["Login maydoniga `'` yozib ko'ring. Xato matnini o'qing.", "`--` SQL'da izoh."])
add("web", "idor", "Boshqaning eslatmasi", 150,
    "Bu eslatmalar sayti. Siz faqat o'zingiznikini ko'rishingiz kerak... shunday emasmi?",
    port=8004, hints=["Manzil satriga qarang. Raqam nimani bildiradi?"])

# ---------------------------------------------------------------- crypto
def caesar(s, k):
    return "".join(
        chr((ord(c) - 97 + k) % 26 + 97) if c.islower() else chr((ord(c) - 65 + k) % 26 + 65) if c.isupper() else c
        for c in s)

body = FLAGS["caesar"][5:-1]
write("crypto", "caesar", "shifr.txt", f"BICO{{{caesar(body, 7)}}}\n")
add("crypto", "caesar", "Yuliy Sezar", 50,
    "Qadimgi Rim generali xabarlarini harflarni surib shifrlagan. Faqat harflar siljigan, `BICO{}` va `_` o'z joyida.",
    files=["shifr.txt"], hints=["Faqat 25 ta variant bor."])

flag = FLAGS["layers"]
step = base64.b64encode(codecs.encode(flag, "rot13").encode().hex().encode()).decode()
write("crypto", "layers", "xabar.txt", step + "\n")
add("crypto", "layers", "Piyoz", 75,
    "Piyoz kabi — bir necha qavat. Har qavatni ochganingda yangi qavat chiqadi. Oxirida flag.",
    files=["xabar.txt"], hints=["`=` belgisi qaysi kodlashni eslatadi? Keyin faqat 0-9 va a-f. Oxirida harflar 13 ga surilgan."])

key = 0x5A
ct = bytes(b ^ key for b in FLAGS["xor"].encode()).hex()
write("crypto", "xor", "shifr.txt", ct + "\n")
add("crypto", "xor", "Bitta bayt", 100,
    "Flag har bir bayti **bitta** sirli bayt bilan XOR qilingan. Natija hex ko'rinishida.",
    files=["shifr.txt"], hints=["Kalit 0-255 oralig'ida: hammasini sinab ko'ring. Flag `BICO{` bilan boshlanadi."])

def is_prime(n, k=20):
    if n < 4:
        return n in (2, 3)
    if n % 2 == 0:
        return False
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(k):
        a = rng.randrange(2, n - 1)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True

def rand_prime(bits):
    while True:
        p = rng.getrandbits(bits) | (1 << (bits - 1)) | 1
        if is_prime(p):
            return p

p, q = rand_prime(512), rand_prime(512)
n, e = p * q, 3
m = int.from_bytes(FLAGS["rsa"].encode(), "big")
assert m**3 < n  # shu sababli xabar modulga "o'ralmaydi" — masalaning butun fokusi
write("crypto", "rsa", "chiqish.txt", f"n = {n}\ne = {e}\nc = {pow(m, e, n)}\n")
add("crypto", "rsa", "Kichik kalit", 200,
    "RSA ishlatilgan, modul 1024 bit — xavfsiz ko'rinadi. Lekin `e` ga va xabar uzunligiga qarang.",
    files=["chiqish.txt"], hints=["`m^3 < n` bo'lsa, `mod n` hech narsa qilmaydi. Butun son kub ildizi oling (`gmpy2.iroot` yoki o'zingiz binary search)."])

# ---------------------------------------------------------------- forensics
def png_with_trailer(path, text):
    img = Image.new("RGB", (400, 240))
    px = img.load()
    for y in range(240):
        for x in range(400):
            px[x, y] = (x * 255 // 399, y * 255 // 239, 160)
    img.save(path, "PNG")
    with open(path, "ab") as f:  # IEND dan keyin ham fayl "yaroqli" qoladi
        f.write(b"\n" + text.encode() + b"\n")

d = OUT / "forensics" / "strings"
d.mkdir(parents=True, exist_ok=True)
png_with_trailer(d / "manzara.png", f"hidden: {FLAGS['strings']}")
add("forensics", "strings", "Oddiy rasm", 50,
    "Oddiy gradient rasm. Ko'zga ko'rinmagan narsa faylning ichida bo'lishi mumkin.",
    files=["manzara.png"], hints=["Linux'da `strings` buyrug'i.", "Yoki `xxd manzara.png | tail`."])

ips = [f"10.0.{rng.randrange(0, 4)}.{rng.randrange(2, 250)}" for _ in range(40)]
paths = ["/", "/index.html", "/login", "/static/app.js", "/static/style.css", "/api/health", "/about", "/favicon.ico"]
uas = ["Mozilla/5.0 (X11; Linux x86_64) Firefox/118.0", "Mozilla/5.0 (Windows NT 10.0) Chrome/118.0",
       "curl/8.4.0", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1"]
lines = []
for i in range(4000):
    t = f"25/Oct/2026:{(i // 200) % 24:02d}:{(i * 7) % 60:02d}:{(i * 13) % 60:02d} +0500"
    lines.append(f'{rng.choice(ips)} - - [{t}] "GET {rng.choice(paths)} HTTP/1.1" '
                 f'{rng.choice([200, 200, 200, 304, 404])} {rng.randrange(200, 9000)} "-" "{rng.choice(uas)}"')
secret = base64.b64encode(FLAGS["logs"].encode()).decode()
lines[2718] = (f'203.0.113.66 - - [25/Oct/2026:13:37:00 +0500] "GET /backup.sql HTTP/1.1" 200 4096 "-" '
               f'"sqlmap-lite/{secret}"')
write("forensics", "logs", "access.log", "\n".join(lines) + "\n")
add("forensics", "logs", "Ukol ostida", 150,
    "Server logida 4000 qator. Ichida bitta begona mehmon bor — u boshqalardan farq qiladi. U nima olib ketdi va kim sifatida tanishtirdi?",
    files=["access.log"], hints=["Oddiy foydalanuvchilar `Mozilla` yoki `curl`. Boshqasini qidiring (`grep -v`).", "User-Agent ichidagi matn base64."])

# ---------------------------------------------------------------- chiqarish
for cat, slug, name, value, desc, files, port, hints in CHALLENGES:
    d = OUT / cat / slug
    d.mkdir(parents=True, exist_ok=True)
    spec = {
        "name": name, "author": AUTHOR, "category": cat.capitalize(), "description": desc,
        "value": value, "type": "standard", "state": "visible", "version": "0.1",
        "flags": [{"type": "static", "content": FLAGS[slug], "data": "case_sensitive"}],
        "hints": [{"content": h, "cost": 10} for h in hints] or None,
        "files": files or None,
        "connection_info": f"{HOST}:{port}" if port else None,
    }
    spec = {k: v for k, v in spec.items() if v is not None}
    (d / "challenge.yml").write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False))

(ROOT / ".flags.env").write_text("".join(f"FLAG_{k.upper()}={v}\n" for k, v in FLAGS.items()))
total = sum(c[3] for c in CHALLENGES)
print(f"{len(CHALLENGES)} ta masala, jami {total} ball -> {OUT}")

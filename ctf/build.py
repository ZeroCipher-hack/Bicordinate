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
    "l_hidden": "BICO{ls_dash_a_yashirinni_ochadi}",
    "l_headtail": "BICO{head_va_tail_birga}",
    "l_grep": "BICO{grep_r_butun_papkani_kezadi}",
    "l_findname": "BICO{find_name_topib_beradi}",
    "l_findsize": "BICO{find_size_katta_fayl}",
    "l_empty": "BICO{bosh_fayl_topildi}",
    "l_perm": "BICO{chmod_u_plus_r}",
    "l_dirperm": "BICO{papkada_x_huquqi_bor}",
    "l_env": "BICO{source_va_alias_ishladi}",
    "l_wild": "BICO{wildcard_katta_harf}",
    "l_shadow": "BICO{iloveyou}",
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

# ---------------------------------------------------------------- linux (konspekt asosida)
import io
import subprocess
import tarfile


def make_tar(slug, entries):
    """entries: (yo'l, bytes | None=papka, mode). Ruxsatlar tar ichida aniq belgilanadi."""
    d = OUT / "linux" / slug
    d.mkdir(parents=True, exist_ok=True)
    with tarfile.open(d / "uy.tar.gz", "w:gz") as tf:
        for path, data, mode in entries:
            ti = tarfile.TarInfo(path)
            ti.mode, ti.uid, ti.gid, ti.uname, ti.gname, ti.mtime = mode, 1000, 1000, "kali", "kali", 1761000000
            if data is None:
                ti.type = tarfile.DIRTYPE
                tf.addfile(ti)
            else:
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))


def lorem(n):
    w = ["tizim", "yangilandi", "foydalanuvchi", "kirdi", "xizmat", "ishga", "tushdi", "xato", "yo'q", "ulandi", "so'rov", "qabul"]
    return [" ".join(rng.choice(w) for _ in range(rng.randrange(4, 9))) for _ in range(n)]


def b(s):
    return s.encode()


TAR_NOTE = " Arxivni oching: `tar xzf uy.tar.gz`."

# 1. yashirin fayl
make_tar("l_hidden", [("uy", None, 0o755), ("uy/Downloads", None, 0o755), ("uy/eslatma.txt", b"Bu yerda hech narsa yo'q.\n", 0o644),
                      ("uy/.yashirin", b(FLAGS["l_hidden"] + "\n"), 0o644)])
add("linux", "l_hidden", "Ko'rinmas fayl", 25,
    "`ls` hamma narsani ko'rsatmaydi. Papkada yana bir fayl bor." + TAR_NOTE, files=["uy.tar.gz"], hints=["`ls -la`"])

# 2. head + tail
lines = lorem(3000)
lines[0] = "# 1-qism: BICO{head_va_"
lines[-1] = "# 2-qism: tail_birga}"
make_tar("l_headtail", [("uy", None, 0o755), ("uy/katta.txt", b("\n".join(lines) + "\n"), 0o644)])
add("linux", "l_headtail", "Boshi va oxiri", 50,
    "Flag ikkiga bo'lingan: bir qismi `katta.txt` boshida, ikkinchisi oxirida. 3000 qatorni qo'lda aylantirmang." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`head -n 1` va `tail -n 1`"])

# 3. grep -r
ents = [("uy", None, 0o755), ("uy/loglar", None, 0o755)]
target = rng.randrange(40)
for i in range(40):
    ls_ = lorem(300)
    if i == target:
        ls_[rng.randrange(300)] = "DEBUG token=" + FLAGS["l_grep"]
    ents.append((f"uy/loglar/xizmat_{i:02d}.log", b("\n".join(ls_) + "\n"), 0o644))
make_tar("l_grep", ents)
add("linux", "l_grep", "Igna ichida pichoq", 50,
    "40 ta log fayl, har birida 300 qator. Birida `token=` dan keyin flag turibdi." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`grep -rn \"BICO\" .`"])

# 4. find -name
ents = [("uy", None, 0o755)]
for a in range(5):
    for c in range(4):
        ents.append((f"uy/d{a}", None, 0o755)) if c == 0 else None
        ents.append((f"uy/d{a}/s{c}", None, 0o755))
        ents.append((f"uy/d{a}/s{c}/eslatma{a}{c}.txt", b"hech narsa\n", 0o644))
ents += [("uy/d3/s2/chuqur", None, 0o755), ("uy/d3/s2/chuqur/yana", None, 0o755),
         ("uy/d3/s2/chuqur/yana/salom.txt", b(FLAGS["l_findname"] + "\n"), 0o644)]
make_tar("l_findname", ents)
add("linux", "l_findname", "Salom qayerda?", 75,
    "Ichma-ich papkalar ichida `salom.txt` degan fayl bor. Hammasini `cd` bilan kezmang." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`find . -name \"salom.txt\"`"])

# 5. find -size
ents = [("uy", None, 0o755)]
for i in range(30):
    ents.append((f"uy/f{i:02d}.dat", rng.randbytes(rng.randrange(500, 2000)), 0o644))
ents.append(("uy/f17.dat", b(FLAGS["l_findsize"] + "\n") + rng.randbytes(300_000), 0o644))
ents = [e for e in ents if not (e[0] == "uy/f17.dat" and len(e[1]) < 1000)]
make_tar("l_findsize", ents)
add("linux", "l_findsize", "Og'ir fayl", 75,
    "30 ta fayl, bittasi qolganlaridan ancha katta (>100 KB). Flag uning ichida, birinchi qatorda." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`find . -size +100k`", "Ichida binar axlat bor: `head -n 1` yoki `strings`."])

# 6. find -empty (flag = fayl nomi)
ents = [("uy", None, 0o755)] + [(f"uy/n{i:02d}.txt", b"bor\n", 0o644) for i in range(25)]
ents.append((f"uy/{FLAGS['l_empty']}", b"", 0o644))
make_tar("l_empty", ents)
add("linux", "l_empty", "Bo'sh qo'l", 50,
    "26 ta fayl, bittasi butunlay bo'sh. **Flag — shu faylning nomi.**" + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`find . -empty`"])

# 7. chmod
make_tar("l_perm", [("uy", None, 0o755), ("uy/sir.txt", b(FLAGS["l_perm"] + "\n"), 0o000)])
add("linux", "l_perm", "Qulf", 100,
    "`cat sir.txt` — `Permission denied`. Fayl egasi sizsiz. Qulfni o'zingiz oching." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`ls -l sir.txt` ruxsatlarni ko'rsating, keyin `chmod`."])

# 8. papkada faqat x
make_tar("l_dirperm", [("uy", None, 0o755), ("uy/qorongu", None, 0o711),
                       ("uy/qorongu/maxfiy.txt", b(FLAGS["l_dirperm"] + "\n"), 0o644)])
add("linux", "l_dirperm", "Qorong'u xona", 100,
    "`qorongu/` papkasiga kirishingiz mumkin, lekin `ls qorongu` xato beradi. Ichida `maxfiy.txt` borligini bilasiz." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`drwx--x--x` — x bor, r yo'q. Nomini bilsangiz, ochish mumkin."])

# 9. env + alias
make_tar("l_env", [("uy", None, 0o755), ("uy/sozlama.sh", b(
    "export QISM1=source_va\nexport QISM2=alias_ishladi\n"
    "alias bayroq='echo \"BICO{${QISM1}_${QISM2}}\"'\n"), 0o644)])
add("linux", "l_env", "Alias sehri", 50,
    "`sozlama.sh` ichida o'zgaruvchilar va alias bor. Faylni shellga yuklab, `bayroq` buyrug'ini ishlating "
    "(yoki o'zgaruvchilarni qo'lda yig'ing)." + TAR_NOTE, files=["uy.tar.gz"],
    hints=["`source sozlama.sh`, keyin `bayroq`. `echo $QISM1` ham ishlaydi."])

# 10. wildcard
ents = [("uy", None, 0o755)] + [(f"uy/fayl_{i:03d}.txt", b"oddiy\n", 0o644) for i in range(1, 151)]
ents = [e for e in ents if e[0] != "uy/fayl_117.txt"] + [("uy/fAyl_117.txt", b(FLAGS["l_wild"] + "\n"), 0o644)]
make_tar("l_wild", ents)
add("linux", "l_wild", "Bitta katta harf", 75,
    "150 ta fayl, nomlari deyarli bir xil. Bittasining nomida **katta harf** bor. Flag shu faylda." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`ls *[A-Z]*`"])

# 11. /etc/shadow
salt_hash = subprocess.run(["openssl", "passwd", "-6", "-salt", "bicoctf1", "iloveyou"],
                           capture_output=True, text=True, check=True).stdout.strip()
make_tar("l_shadow", [("uy", None, 0o755),
    ("uy/passwd.txt", b"root:x:0:0:root:/root:/bin/bash\nctfuser:x:1001:1001::/home/ctfuser:/bin/bash\n", 0o644),
    ("uy/shadow.txt", b(f"root:*:20000:0:99999:7:::\nctfuser:{salt_hash}:20000:0:99999:7:::\n"), 0o644)])
add("linux", "l_shadow", "Parol buzish", 200,
    "Bu `/etc/passwd` va `/etc/shadow` nusxalari. `ctfuser` paroli rockyou ro'yxatida. **Flag: `BICO{` + parol + `}`.**" + TAR_NOTE,
    files=["uy.tar.gz"],
    hints=["`unshadow passwd.txt shadow.txt > hash.txt`", "`john --format=crypt --wordlist=/usr/share/wordlists/rockyou.txt hash.txt`"])

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

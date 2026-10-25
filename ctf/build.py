#!/usr/bin/env python3
"""CTF masalalarini yig'adi: fayllar, challenge.yml (ctfcli) va .flags.env (docker-compose uchun).

Ishlatish:  python3 build.py        (Pillow kerak:  pip install pillow pyyaml)
Natija:     challenges/<kategoriya>/<slug>/{challenge.yml, fayllar}   — gitignore'da
"""
import base64
import codecs
import json
import random
import shutil
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
    "machine1": "BICO{ssh_orqali_user_flagni_oldim}",
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
        for path, data, mode, *mt in entries:
            ti = tarfile.TarInfo(path)
            ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = mode, 1000, 1000, "kali", "kali"
            ti.mtime = mt[0] if mt else 1761000000
            if isinstance(data, tuple):
                ti.type, ti.linkname = tarfile.SYMTYPE, data[1]
                tf.addfile(ti)
            elif data is None:
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

# ---------------------------------------------------------------- qo'shimcha masalalar (jami 50)
FLAGS.update({
    "l_catn": "BICO{cat_n_qator_raqami}",
    "l_grepi": "BICO{grep_i_harf_farqsiz}",
    "l_grepe": "BICO{grep_e_ikki_soz}",
    "l_tail50": "BICO{tail_n_50_oxirgi_qatorlar}",
    "l_spaces": "BICO{bosh_joyli_fayl_nomi}",
    "l_stdout": "BICO{stderr_ni_dev_null_ga}",
    "l_stderr": "BICO{stdout_ni_yashirdim}",
    "l_exec": "BICO{chmod_plus_x}",
    "l_group": "BICO{tungi_smena}",
    "l_passwd": "BICO{ilhom_admin}",
    "l_osrel": "BICO{quyosh}",
    "l_symlink": "BICO{ln_s_havola_ishora}",
    "l_newest": "BICO{ls_t_eng_yangi_fayl}",
    "l_history": "BICO{history_hammasini_eslaydi}",
    "l_zshrc": "BICO{zshrc_ichidagi_alias}",
    "l_wildpdf": "BICO{a_yulduz_nuqta_pdf}",
    "l_wilddigit": "BICO{raqamli_nomli_fayl}",
    "l_finddir": "BICO{find_type_d_papka}",
    "l_combo": "BICO{find_uch_shart_birga}",
    "l_hiddendir": "BICO{yashirin_papka_ichida}",
    "c_hex": "BICO{hex_oddiy_kodlash}",
    "c_bin": "BICO{ikkilik_sanoq_tizimi}",
    "c_b32": "BICO{base32_ham_bor}",
    "c_rot47": "BICO{rot47_belgilarni_suradi}",
    "c_atbash": "BICO{atbash_ogirma_alifbo}",
    "c_morse": "BICO{morze_yozuvi}",
    "c_vig": "BICO{vijener_kalit_bilan}",
    "f_zip": "BICO{zip_ichida_zip_ichida_zip}",
})

# 1. cat -n
L = lorem(500)
L[236] = FLAGS["l_catn"]
make_tar("l_catn", [("uy", None, 0o755), ("uy/royxat.txt", b("\n".join(L) + "\n"), 0o644)])
add("linux", "l_catn", "237-qator", 25, "`royxat.txt` da 500 qator bor. Flag aynan **237-qatorda**." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`cat -n royxat.txt`"])

# 2. grep -i
L = lorem(120)
for i in range(0, 120, 7):
    L[i] = rng.choice(["secret: yo'q", "SECRET: yo'q", "Secret: hech narsa", "sECRET: bo'sh"])
L[83] = "sEcReT: " + FLAGS["l_grepi"]
make_tar("l_grepi", [("uy", None, 0o755), ("uy/eslatmalar.txt", b("\n".join(L) + "\n"), 0o644)])
add("linux", "l_grepi", "Katta-kichik harf", 50,
    "`secret` so'zi faylda har xil yozilgan (Secret, SECRET, sEcReT...). Flag bor qatorni toping." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`grep -i secret eslatmalar.txt`"])

# 3. grep -e
L = lorem(400)
L[50], L[310] = "kalit=" + FLAGS["l_grepe"][:-9], "parol=" + FLAGS["l_grepe"][-9:]
for i in (20, 120, 220, 330):
    L[i] = rng.choice(["kalit=eskirgan", "parol=eskirgan"])
make_tar("l_grepe", [("uy", None, 0o755), ("uy/sozlama.conf", b("\n".join(L) + "\n"), 0o644)])
add("linux", "l_grepe", "Ikki so'z", 50,
    "Flag ikkiga bo'lingan: `kalit=` qatorida boshi, `parol=` qatorida oxiri. `eskirgan` yozuvlari — yolg'on." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`grep -e kalit -e parol sozlama.conf`"])

# 4. tail -n 50
L = lorem(200)
L[165] = FLAGS["l_tail50"]
make_tar("l_tail50", [("uy", None, 0o755), ("uy/server.log", b("\n".join(L) + "\n"), 0o644)])
add("linux", "l_tail50", "Oxirgi 50", 25, "Flag `server.log` ning **oxirgi 50 qatori** ichida." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`tail -n 50 server.log`"])

# 5. bo'sh joyli fayl nomi
ents = [("uy", None, 0o755)] + [(f"uy/hujjat{i}.txt", b"hech narsa\n", 0o644) for i in range(5)]
ents.append(("uy/bu mening faylim.txt", b(FLAGS["l_spaces"] + "\n"), 0o644))
make_tar("l_spaces", ents)
add("linux", "l_spaces", "Bo'sh joy", 25, "`bu mening faylim.txt` ni o'qing. Nomida bo'sh joy bor — `cat bu mening faylim.txt` ishlamaydi." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["Qo'shtirnoq: `cat \"bu mening faylim.txt\"` yoki Tab."])

# 6-7. STDOUT / STDERR
noise = "".join(f'echo "OGOHLANTIRISH: modul {i} topilmadi" >&2\n' for i in range(150))
make_tar("l_stdout", [("uy", None, 0o755), ("uy/skan.sh", b("#!/bin/bash\n" + noise + f'echo "{FLAGS["l_stdout"]}"\n' + noise), 0o755)])
add("linux", "l_stdout", "Shovqin", 75,
    "`./skan.sh` ni ishga tushiring. Ekran xato xabarlariga to'ladi, flag shular orasida yo'qoladi. Xatolarni (STDERR) yo'q qiling." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`./skan.sh 2>/dev/null`"])
noise = "".join(f'echo "ish davom etmoqda: {i}%"\n' for i in range(150))
make_tar("l_stderr", [("uy", None, 0o755), ("uy/skan2.sh", b("#!/bin/bash\n" + noise + f'echo "{FLAGS["l_stderr"]}" >&2\n'), 0o755)])
add("linux", "l_stderr", "Teskari shovqin", 75,
    "`./skan2.sh` ekranga 150 qator yozadi, flag esa boshqa oqimda. Odatiy natijani (STDOUT) o'chirib, faqat flagni ko'ring." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`./skan2.sh 1>/dev/null`", "yoki `./skan2.sh 2>xato.txt` va `cat xato.txt`"])

# 8. chmod +x
make_tar("l_exec", [("uy", None, 0o755), ("uy/bayroq", b("#!/bin/bash\necho " + FLAGS["l_exec"] + "\n"), 0o644)])
add("linux", "l_exec", "Ishga tushmaydi", 50,
    "`./bayroq` — `Permission denied`. Bu dastur, lekin unga ishga tushirish huquqi berilmagan." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`ls -l bayroq` — `x` yo'q. `chmod +x bayroq`."])

# 9. /etc/group
names = ["adm", "dialout", "cdrom", "sudo", "audio", "video", "plugdev", "users", "kutubxona", "oshxona", "sport",
         "nosir", "bico_a", "bico_b", "labora", "tungi_smena", "ertalab", "ombor", "wifi", "printer"]
L = [f"root:x:0:"] + [f"{n}:x:{1000+i}:" + ",".join(rng.sample(["ali", "vali", "sardor", "dilnoza", "jasur"], rng.randrange(0, 3)))
                       for i, n in enumerate(names)]
L = [l for l in L if "talaba" not in l]
L = [l + ",talaba" if l.startswith("tungi_smena:") and l.endswith(",") is False and l.split(":")[3] else
     (l + "talaba" if l.startswith("tungi_smena:") else l) for l in L]
assert sum("talaba" in l for l in L) == 1
make_tar("l_group", [("uy", None, 0o755), ("uy/group.txt", b("\n".join(L) + "\n"), 0o644)])
add("linux", "l_group", "Qaysi guruh?", 75,
    "`group.txt` — `/etc/group` nusxasi. Foydalanuvchi `talaba` faqat bitta guruhning a'zosi. **Flag: `BICO{` + guruh nomi + `}`.**" + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`grep talaba group.txt` — qator boshidagi nom guruh nomi."])

# 10. /etc/passwd
L = ["root:x:0:0:root:/root:/bin/bash"] + [f"{n}:x:{i+1}:{i+1}::/var/{n}:/usr/sbin/nologin" for i, n in enumerate(
    ["daemon", "bin", "sys", "games", "man", "lp", "mail", "news", "uucp", "proxy", "www-data", "backup", "list"])]
L += [f"{n}:x:{1000+i}:{1000+i}::/home/{n}:/usr/sbin/nologin" for i, n in enumerate(["ali", "vali", "sardor", "jasur"])]
L.insert(9, "ilhom_admin:x:1010:1010::/home/ilhom_admin:/bin/bash")
make_tar("l_passwd", [("uy", None, 0o755), ("uy/passwd.txt", b("\n".join(L) + "\n"), 0o644)])
add("linux", "l_passwd", "Kim kira oladi?", 75,
    "`passwd.txt` — `/etc/passwd` nusxasi. Tizimga kira oladigan (shelli `/bin/bash`) **oddiy** foydalanuvchi (UID >= 1000) bitta. "
    "**Flag: `BICO{` + username + `}`.**" + TAR_NOTE, files=["uy.tar.gz"],
    hints=["Maydonlar `:` bilan ajralgan: 3-chisi UID, 7-chisi shell. `grep bash passwd.txt`"])

# 11. os-release
make_tar("l_osrel", [("uy", None, 0o755), ("uy/os-release", b(
    'PRETTY_NAME="CTF Linux 7"\nNAME="CTF Linux"\nVERSION_ID="7"\nVERSION="7 (Quyosh)"\n'
    'VERSION_CODENAME=quyosh\nID=ctflinux\nID_LIKE=debian\nHOME_URL="https://example.org/"\n'), 0o644)])
add("linux", "l_osrel", "Qaysi distro?", 25,
    "`os-release` — `cat /etc/os-release` ning nusxasi. **Flag: `BICO{` + `VERSION_CODENAME` qiymati + `}`.**" + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`cat os-release`"])

# 12. symlink
make_tar("l_symlink", [("uy", None, 0o755), ("uy/chuqur", None, 0o755), ("uy/chuqur/yashirin", None, 0o755),
    (f"uy/chuqur/yashirin/{FLAGS['l_symlink']}", b"bu fayl bo'sh emas, lekin flag uning nomida\n", 0o644),
    ("uy/kirish", ("link", f"chuqur/yashirin/{FLAGS['l_symlink']}"), 0o777)])
add("linux", "l_symlink", "Havola", 75,
    "`kirish` oddiy fayl emas — simvolik havola. U **qayerga ishora qiladi**? Flag — nishon fayl nomining o'zi." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`ls -l kirish`", "`readlink kirish`"])

# 13. ls -t
ents = [("uy", None, 0o755)]
order = list("abcdefghijkl")
rng.shuffle(order)
for i, nm in enumerate(order):
    body = FLAGS["l_newest"] if i == 11 else "eski ma'lumot"
    ents.append((f"uy/{nm}.txt", b(body + "\n"), 0o644, 1761000000 + i * 3600))
make_tar("l_newest", ents)
add("linux", "l_newest", "Eng yangi", 50,
    "12 ta fayl. Flag **eng oxirgi o'zgartirilgan** faylda." + TAR_NOTE, files=["uy.tar.gz"], hints=["`ls -lt` — yangisi tepada."])

# 14. history
H = ["ls", "cd Downloads", "pwd", "cat eslatma.txt", "sudo apt update", "ls -la", "cd ..", "nano maqsad.txt", "clear", "mkdir test", "rm -rf test", "uname -r"]
H = [rng.choice(H) for _ in range(80)]
H.insert(46, "export KALIT=" + FLAGS["l_history"])
make_tar("l_history", [("uy", None, 0o755), ("uy/.bash_history", b("\n".join(H) + "\n"), 0o600)])
add("linux", "l_history", "Eski buyruqlar", 50,
    "Bu foydalanuvchining buyruqlar tarixi (`.bash_history`). U qachondir flagni terminalga yozib yuborgan." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["Yashirin fayl: `ls -la`. `grep BICO .bash_history`"])

# 15. .zshrc
make_tar("l_zshrc", [("uy", None, 0o755), ("uy/.zshrc", b(
    "# oddiy sozlamalar\nalias c=clear\nalias yangilash=\"sudo apt update && sudo apt upgrade\"\nalias ll='ls -la'\n"
    f"alias nimadir='echo {FLAGS['l_zshrc']}'\nexport EDITOR=nano\n"), 0o644)])
add("linux", "l_zshrc", "G'alati alias", 25, "`.zshrc` ichidagi aliaslardan biri boshqalarga o'xshamaydi." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`cat .zshrc`"])

# 16. a*.pdf
ents = [("uy", None, 0o755)]
for nm in ["a_reja.txt", "a_hisob.txt", "b_kitob.pdf", "d_lug'at.pdf", "kitob.pdf", "rasm.png", "x_eslatma.txt"]:
    ents.append((f"uy/{nm}", b"bu emas\n", 0o644))
ents.append(("uy/a_konspekt.pdf", b(FLAGS["l_wildpdf"] + "\n"), 0o644))
make_tar("l_wildpdf", ents)
add("linux", "l_wildpdf", "A harfi va PDF", 50,
    "Flag **`a` harfi bilan boshlanadigan `.pdf`** faylda. Nomini yozmasdan, wildcard bilan oching." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`ls a*.pdf`, `cat a*.pdf`"])

# 17. *[0-9]*
ents = [("uy", None, 0o755)]
words = ["olma", "anor", "uzum", "behi", "nok", "shaftoli", "gilos", "qovun", "tarvuz", "limon"]
for i, w in enumerate(words * 6):
    ents.append((f"uy/{w}_{chr(97+i//10)}{chr(97+i%10)}.txt", b"bu emas\n", 0o644))
ents.append(("uy/fayl7.txt", b(FLAGS["l_wilddigit"] + "\n"), 0o644))
make_tar("l_wilddigit", ents)
add("linux", "l_wilddigit", "Raqamli nom", 50, "60 ta fayl. Bittasining nomida **raqam** bor. Flag shunda." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`ls *[0-9]*`"])

# 18. find -type d
ents = [("uy", None, 0o755), ("uy/a", None, 0o755), ("uy/a/b", None, 0o755),
        ("uy/a/BICO{bu_flag_emas}", b"bu fayl, papka emas\n", 0o644),
        (f"uy/a/b/{FLAGS['l_finddir']}", None, 0o755)]
make_tar("l_finddir", ents)
add("linux", "l_finddir", "Fayl emas, papka", 75,
    "Ichma-ich papkalarda `BICO` bilan boshlanadigan ikki narsa bor: bittasi fayl (yolg'on), bittasi **papka**. Flag — papka nomi." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`find . -type d -name \"BICO*\"`"])

# 19. find kombinatsiya
ents = [("uy", None, 0o755), ("uy/Hisobot_2024.txt", b"kichik\n", 0o644), ("uy/hisobot_dir", None, 0o755),
        ("uy/kitob.txt", b"x" * 9000, 0o644), ("uy/hisobot_eski.txt", b"juda kichik\n", 0o644),
        ("uy/hisobot_yillik.txt", b(FLAGS["l_combo"] + "\n") + b"." * 9000, 0o644)]
make_tar("l_combo", ents)
add("linux", "l_combo", "Uch shart", 100,
    "Kerakli fayl: nomi `hisobot` bilan boshlanadi (katta-kichik harf farqsiz), u **fayl** (papka emas) va **5 KB dan katta**." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`find . -iname \"hisobot*\" -type f -size +5k`"])

# 20. yashirin papka
make_tar("l_hiddendir", [("uy", None, 0o755), ("uy/Documents", None, 0o755), ("uy/.yashirin_papka", None, 0o755),
    ("uy/.yashirin_papka/.ichki", None, 0o755), ("uy/.yashirin_papka/.ichki/sir.txt", b(FLAGS["l_hiddendir"] + "\n"), 0o644)])
add("linux", "l_hiddendir", "Yashirin ichida yashirin", 50,
    "Yashirin papka ichida yana yashirin papka. Nuqta bilan boshlanadigan nomlar `ls` da ko'rinmaydi." + TAR_NOTE,
    files=["uy.tar.gz"], hints=["`ls -la`, keyin `cd`"])

# ------ Crypto (oson)
def body_of(k):
    return FLAGS[k][5:-1]

write("crypto", "c_hex", "xabar.txt", FLAGS["c_hex"].encode().hex() + "\n")
add("crypto", "c_hex", "Hex", 25, "Matn o'n oltilik (hex) ko'rinishda yozilgan.", files=["xabar.txt"], hints=["`xxd -r -p xabar.txt`"])

write("crypto", "c_bin", "xabar.txt", " ".join(f"{b_:08b}" for b_ in FLAGS["c_bin"].encode()) + "\n")
add("crypto", "c_bin", "Nol va bir", 50, "Har bir belgi 8 ta nol/bir bilan yozilgan.", files=["xabar.txt"],
    hints=["Har 8 bit — bitta ASCII belgi (`A` = 01000001)."])

write("crypto", "c_b32", "xabar.txt", base64.b32encode(FLAGS["c_b32"].encode()).decode() + "\n")
add("crypto", "c_b32", "Base... nechta?", 50, "Base64 emas. Faqat katta harflar va `2-7` raqamlari ishlatilgan.", files=["xabar.txt"],
    hints=["`base32 -d xabar.txt`"])


def rot47(s):
    return "".join(chr(33 + (ord(c) - 33 + 47) % 94) if 33 <= ord(c) <= 126 else c for c in s)


write("crypto", "c_rot47", "xabar.txt", rot47(FLAGS["c_rot47"]) + "\n")
add("crypto", "c_rot47", "Rot... 47", 50, "ROT13 harflarni suradi. Bu esa **barcha** ko'rinadigan belgilarni suradi (ASCII 33-126). Qavslar ham o'zgargan.",
    files=["xabar.txt"], hints=["`tr '!-~' 'P-~!-O' < xabar.txt`"])


def atbash(s):
    return "".join(chr(219 - ord(c)) if c.islower() else chr(155 - ord(c)) if c.isupper() else c for c in s)


write("crypto", "c_atbash", "xabar.txt", "BICO{" + atbash(body_of("c_atbash")) + "}\n")
add("crypto", "c_atbash", "Teskari alifbo", 50,
    "a↔z, b↔y, c↔x... Faqat `{}` ichidagi harflar almashtirilgan (`BICO` va `_` joyida).", files=["xabar.txt"],
    hints=["`tr 'a-z' 'z-a'`"])

MORSE = {"a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.", "g": "--.", "h": "....", "i": "..", "j": ".---",
         "k": "-.-", "l": ".-..", "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.", "s": "...", "t": "-",
         "u": "..-", "v": "...-", "w": ".--", "x": "-..-", "y": "-.--", "z": "--..", "_": "/"}
write("crypto", "c_morse", "xabar.txt", " ".join(MORSE[c] for c in body_of("c_morse")) + "\n")
add("crypto", "c_morse", "Nuqta va tire", 50,
    "Morze kodi. `/` — `_` belgisi. Natijani **kichik harflarda** `BICO{...}` ichiga joylang.", files=["xabar.txt"])


def vig(s, key, sign=1):
    out, j = [], 0
    for c in s:
        if c.isalpha():
            out.append(chr((ord(c) - 97 + sign * (ord(key[j % len(key)]) - 97)) % 26 + 97))
            j += 1
        else:
            out.append(c)
    return "".join(out)


write("crypto", "c_vig", "xabar.txt", "BICO{" + vig(body_of("c_vig"), "kali") + "}\n")
add("crypto", "c_vig", "Vijener", 100,
    "Vijener shifri. Kalit: `kali`. Faqat `{}` ichidagi harflar shifrlangan, `_` o'tkazib yuborilgan (kalit harfi sarflanmaydi).",
    files=["xabar.txt"], hints=["CyberChef → Vigenère Decode, yoki har harfni kalit harfi bo'yicha qo'lda orqaga suring."])

# ------ Forensics
import zipfile

inner = io.BytesIO()
with zipfile.ZipFile(inner, "w") as z:
    z.writestr("flag.txt", FLAGS["f_zip"] + "\n")
for lvl in ("c", "b"):
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr(f"{lvl}.zip", inner.getvalue())
    inner = outer
write("forensics", "f_zip", "a.zip", inner.getvalue())
add("forensics", "f_zip", "Matryoshka", 50, "Arxiv ichida arxiv ichida arxiv. Pastgacha oching.", files=["a.zip"],
    hints=["`unzip a.zip` ni takrorlang yoki `file` bilan har bir faylni tekshiring."])

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

# ---------------------------------------------------------------- machine (SSH orqali)
M_USER, M_PASS, M_SALT = "operator", "thunder", "bico_m1"
assert M_PASS in open("app/shell/rockyou-mini.txt").read().split(), "parol ro'yxatda bo'lishi shart"
M_HASH = subprocess.run(["openssl", "passwd", "-6", "-salt", M_SALT, M_PASS],
                        capture_output=True, text=True, check=True).stdout.strip()
add("machine", "machine1",
    "Birinchi qadam: SSH", 150,
    f"Bu alohida mashina — veb hujum shart emas, parol xeshi to'g'ridan-to'g'ri shu yerda.\n\n"
    f"Foydalanuvchi: `{M_USER}`\nXesh: `{M_HASH}`\n\n"
    f"1. Xeshni faylga yozing: `echo '{M_USER}:{M_HASH}' > hash.txt`\n\n"
    f"2. Buzing: `john --format=crypt --wordlist=/usr/share/wordlists/rockyou.txt hash.txt`\n\n"
    f"3. Ulaning: `ssh {M_USER}@MASHINA_IP` (port va IP — e'londa), topilgan parolni kiriting.\n\n"
    f"4. `cat user.txt` — flag shu yerda.",
    hints=["`john --show --format=crypt hash.txt` — allaqachon buzilgan bo'lsa shuni ko'rsatadi.",
           "SSH ulanishda `Host key verification` so'rasa — `yes` deb javob bering."])
(ROOT / "app" / "machine").mkdir(parents=True, exist_ok=True)
(ROOT / "app" / "machine" / "user.txt").write_text(FLAGS["machine1"] + "\n")
shutil.copy(ROOT / "app" / "shell" / "rockyou-mini.txt", ROOT / "app" / "machine" / "rockyou-mini.txt")
(ROOT / "app" / "machine" / "setup.env").write_text(f"M_USER={M_USER}\nM_PASS_HASH='{M_HASH}'\n")

# ---------------------------------------------------------------- sayt (app/) uchun eksport
import hashlib
import shutil

APP = ROOT / "app"
for sub in ("files", "shell/masalalar"):
    shutil.rmtree(APP / sub, ignore_errors=True)
CAT_ORDER = {"misc": 0, "linux": 1, "crypto": 2, "forensics": 3, "web": 4, "machine": 5}
export = []
for cat, slug, name, value, desc, files, port, hints in sorted(CHALLENGES, key=lambda c: (CAT_ORDER[c[0]], c[3], c[2])):
    for sub in (APP / "files" / slug, APP / "shell/masalalar" / slug):
        sub.mkdir(parents=True, exist_ok=True)
        for fn in files:
            shutil.copy(OUT / cat / slug / fn, sub / fn)
    export.append({
        "id": slug, "category": cat, "name": name, "points": value, "description": desc,
        "hints": [{"text": h, "cost": 10} for h in hints], "files": files, "web_port": port,
        # flag hech qachon ochiq saqlanmaydi — faqat xesh
        "flag_sha256": hashlib.sha256(FLAGS[slug].encode()).hexdigest(),
    })
(APP / "challenges.json").write_text(json.dumps(export, ensure_ascii=False, indent=1))
print(f"app/challenges.json: {len(export)} ta masala")

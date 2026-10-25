#!/usr/bin/env python3
"""Barcha masalalar yechilishini tekshiradi (organizator uchun). Avval build.py ni ishga tushiring."""
import base64
import codecs
import importlib.util
import os
import re
from pathlib import Path

ROOT = Path(__file__).parent
C = ROOT / "challenges"
FLAGS = dict(l.strip().split("=", 1) for l in (ROOT / ".flags.env").read_text().splitlines())
ok = True


def check(name, got):
    global ok
    want = FLAGS["FLAG_" + name.upper()]
    good = got == want
    ok &= good
    print(("OK  " if good else "FAIL"), name, "" if good else f"got={got!r}")


# --- crypto
s = (C / "crypto/caesar/shifr.txt").read_text().strip()
inner = s[5:-1]
shift = lambda t, k: "".join(chr((ord(ch) - 97 - k) % 26 + 97) if ch.islower() else ch for ch in t)
check("caesar", "BICO{" + next(d for k in range(26) if "sezar" in (d := shift(inner, k))) + "}")

x = (C / "crypto/layers/xabar.txt").read_text().strip()
check("layers", codecs.decode(bytes.fromhex(base64.b64decode(x).decode()).decode(), "rot13"))

ct = bytes.fromhex((C / "crypto/xor/shifr.txt").read_text().strip())
check("xor", next(p for k in range(256) if (p := bytes(b ^ k for b in ct)).startswith(b"BICO{")).decode())

vals = dict(re.findall(r"(\w) = (\d+)", (C / "crypto/rsa/chiqish.txt").read_text()))
n, e, c = (int(vals[k]) for k in "nec")
lo, hi = 0, 1 << 400
while lo < hi:  # butun kub ildizi
    mid = (lo + hi) // 2
    lo, hi = (mid + 1, hi) if mid**3 < c else (lo, mid)
check("rsa", lo.to_bytes((lo.bit_length() + 7) // 8, "big").decode())

# --- forensics
png = (C / "forensics/strings/manzara.png").read_bytes()
check("strings", re.search(rb"hidden: (BICO\{[^}]+\})", png).group(1).decode())

odd = [l for l in (C / "forensics/logs/access.log").read_text().splitlines() if not re.search(r'"(Mozilla|curl)/', l)]
assert len(odd) == 1, odd
check("logs", base64.b64decode(odd[0].split("sqlmap-lite/")[1].rstrip('"')).decode())

# --- web (Flask test client, docker'siz)
def load(chal):
    os.environ.update(CHAL=chal, FLAG=FLAGS["FLAG_" + chal.upper()])
    spec = importlib.util.spec_from_file_location("w_" + chal, ROOT / "web/app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.app.test_client()

t = load("robots")
path = re.search(r"Disallow: (\S+)", t.get("/robots.txt").text).group(1)
check("robots", re.search(r"BICO\{[^}]+\}", t.get(path).text).group(0))

t = load("cookie")
t.get("/")
t.set_cookie("role", base64.b64encode(b"admin").decode())
check("cookie", re.search(r"BICO\{[^}]+\}", t.get("/admin").text).group(0))

t = load("sqli")
check("sqli", re.search(r"BICO\{[^}]+\}", t.post("/", data={"u": "admin'--", "p": ""}).text).group(0))

t = load("idor")
check("idor", re.search(r"BICO\{[^}]+\}", t.get("/note/17").text).group(0))


# --- linux: arxivni ochib, konspektdagi haqiqiy buyruqlar bilan yechamiz
import subprocess
import tarfile
import tempfile


def sh(slug, cmd):
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(C / f"linux/{slug}/uy.tar.gz") as tf:
            tf.extractall(td, filter="tar")
        out = subprocess.run(["bash", "-c", cmd], cwd=td + "/uy", capture_output=True, text=True).stdout
    return out


def flag_in(out):
    m = re.search(r"BICO\{[^}]+\}", out)
    return m.group(0) if m else out.strip()


check("l_hidden", flag_in(sh("l_hidden", "ls -la >/dev/null; cat .yashirin")))
check("l_headtail", (lambda o: o[0].split("1-qism: ")[1] + o[1].split("2-qism: ")[1])(
    sh("l_headtail", "head -n 1 katta.txt; tail -n 1 katta.txt").splitlines()))
check("l_grep", flag_in(sh("l_grep", 'grep -rn "BICO" .')))
check("l_findname", flag_in(sh("l_findname", 'cat "$(find . -name salom.txt)"')))
check("l_findsize", flag_in(sh("l_findsize", 'head -c 100 "$(find . -size +100k)" | strings')))
check("l_empty", sh("l_empty", "basename $(find . -empty -type f)").strip())
check("l_perm", flag_in(sh("l_perm", "chmod u+r sir.txt; cat sir.txt")))
check("l_dirperm", flag_in(sh("l_dirperm", "chmod 711 qorongu; cat qorongu/maxfiy.txt")))
check("l_env", flag_in(sh("l_env", "shopt -s expand_aliases\nsource sozlama.sh\nbayroq")))
check("l_wild", flag_in(sh("l_wild", "cat *[A-Z]*")))
h = sh("l_shadow", "grep ^ctfuser shadow.txt | cut -d: -f2").strip()
salt = h.split("$")[2]
pw = subprocess.run(["openssl", "passwd", "-6", "-salt", salt, "iloveyou"], capture_output=True, text=True).stdout.strip()
check("l_shadow", "BICO{iloveyou}" if pw == h else "hash mos kelmadi")

# --- yangi Linux masalalar
check("l_catn", sh("l_catn", "cat -n royxat.txt | grep -P '^\\s+237\\t' | cut -f2").strip())
check("l_grepi", flag_in(sh("l_grepi", "grep -i secret eslatmalar.txt")))
parts = sh("l_grepe", "grep -e kalit -e parol sozlama.conf | grep -v eskirgan").splitlines()
check("l_grepe", parts[0].split("=", 1)[1] + parts[1].split("=", 1)[1])
check("l_tail50", flag_in(sh("l_tail50", "tail -n 50 server.log")))
check("l_spaces", flag_in(sh("l_spaces", 'cat "bu mening faylim.txt"')))
check("l_stdout", flag_in(sh("l_stdout", "./skan.sh 2>/dev/null")))
check("l_stderr", flag_in(sh("l_stderr", "./skan2.sh 2>&1 1>/dev/null")))
check("l_exec", flag_in(sh("l_exec", "chmod +x bayroq; ./bayroq")))
check("l_group", "BICO{" + sh("l_group", "grep talaba group.txt | cut -d: -f1").strip() + "}")
check("l_passwd", "BICO{" + sh("l_passwd", "awk -F: '$3>=1000 && $7==\"/bin/bash\"{print $1}' passwd.txt").strip() + "}")
check("l_osrel", "BICO{" + sh("l_osrel", "grep VERSION_CODENAME os-release | cut -d= -f2").strip() + "}")
check("l_symlink", flag_in(sh("l_symlink", "readlink kirish")))
check("l_newest", flag_in(sh("l_newest", "cat $(ls -t | head -1)")))
check("l_history", flag_in(sh("l_history", "grep BICO .bash_history")))
check("l_zshrc", flag_in(sh("l_zshrc", "cat .zshrc")))
check("l_wildpdf", flag_in(sh("l_wildpdf", "cat a*.pdf")))
check("l_wilddigit", flag_in(sh("l_wilddigit", "cat *[0-9]*")))
check("l_finddir", flag_in(sh("l_finddir", 'find . -type d -name "BICO*"')))
check("l_combo", flag_in(sh("l_combo", 'cat "$(find . -iname "hisobot*" -type f -size +5k)"')))
check("l_hiddendir", flag_in(sh("l_hiddendir", "cat .yashirin_papka/.ichki/sir.txt")))

# --- yangi Crypto / Forensics
rd = lambda p: (C / p).read_text().strip()
check("c_hex", bytes.fromhex(rd("crypto/c_hex/xabar.txt")).decode())
check("c_bin", "".join(chr(int(b_, 2)) for b_ in rd("crypto/c_bin/xabar.txt").split()))
check("c_b32", base64.b32decode(rd("crypto/c_b32/xabar.txt")).decode())
check("c_rot47", "".join(chr(33 + (ord(c) - 33 + 47) % 94) if 33 <= ord(c) <= 126 else c for c in rd("crypto/c_rot47/xabar.txt")))
check("c_atbash", "BICO{" + "".join(chr(219 - ord(c)) if c.islower() else c for c in rd("crypto/c_atbash/xabar.txt")[5:-1]) + "}")
M = {v: k for k, v in {"a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.", "g": "--.", "h": "....", "i": "..",
     "j": ".---", "k": "-.-", "l": ".-..", "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.", "s": "...",
     "t": "-", "u": "..-", "v": "...-", "w": ".--", "x": "-..-", "y": "-.--", "z": "--..", "_": "/"}.items()}
check("c_morse", "BICO{" + "".join(M[t] for t in rd("crypto/c_morse/xabar.txt").split()) + "}")
v, j, out = rd("crypto/c_vig/xabar.txt")[5:-1], 0, []
for ch in v:
    if ch.isalpha():
        out.append(chr((ord(ch) - 97 - (ord("kali"[j % 4]) - 97)) % 26 + 97)); j += 1
    else:
        out.append(ch)
check("c_vig", "BICO{" + "".join(out) + "}")
import zipfile
import io as _io
data = (C / "forensics/f_zip/a.zip").read_bytes()
while True:
    z = zipfile.ZipFile(_io.BytesIO(data))
    nm = z.namelist()[0]
    data = z.read(nm)
    if nm.endswith(".txt"):
        break
check("f_zip", data.decode().strip())


# --- machine (SSH): xeshni john bilan buzib, parolni tekshiramiz
import subprocess as _sp
m_user, m_hash = open(ROOT / "app/machine/setup.env").read().splitlines()
m_user, m_hash = m_user.split("=", 1)[1], m_hash.split("=", 1)[1].strip("'")
with tempfile.TemporaryDirectory() as td:
    (Path(td) / "hash.txt").write_text(f"{m_user}:{m_hash}\n")
    _sp.run(["john", "--format=crypt", "--wordlist=app/shell/rockyou-mini.txt", f"{td}/hash.txt"],
           cwd=ROOT, capture_output=True, text=True, timeout=30)
    shown = _sp.run(["john", "--show", "--format=crypt", f"{td}/hash.txt"], cwd=ROOT,
                    capture_output=True, text=True).stdout
assert (ROOT / "app/machine/user.txt").read_text().strip() == FLAGS["FLAG_MACHINE1"], "user.txt flag bilan mos emas"
check("machine1", FLAGS["FLAG_MACHINE1"] if f"{m_user}:" in shown else "crack qilinmadi")

check("welcome", FLAGS["FLAG_WELCOME"])
raise SystemExit(0 if ok else 1)

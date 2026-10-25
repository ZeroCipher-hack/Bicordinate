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

check("welcome", FLAGS["FLAG_WELCOME"])
raise SystemExit(0 if ok else 1)

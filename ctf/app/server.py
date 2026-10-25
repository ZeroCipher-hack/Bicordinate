#!/usr/bin/env python3
"""BICO CTF — yakka tartibli musobaqa sayti + brauzerdagi terminal.

Ishga tushirish:   python3 server.py                  (sozlamalar README.md da)
Boshqaruv:         python3 server.py reset-pin "Ism" 1234
                   python3 server.py delete-user "Ism"
"""
import asyncio
import collections
import fcntl
import hashlib
import hmac
import json
import os
import pty
import re
import secrets
import shutil
import signal
import sqlite3
import struct
import subprocess
import sys
import tempfile
import termios
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from aiohttp import WSMsgType, web

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
DATA = Path(os.environ.get("CTF_DATA", ROOT / "data"))
PORT = int(os.environ.get("PORT", "8080"))
TERM_MODE = os.environ.get("TERM_MODE", "docker")  # docker | local (faqat sinov uchun!)
HOST = os.environ.get("HOST", "127.0.0.1" if TERM_MODE == "local" else "0.0.0.0")
SHELL_IMAGE = os.environ.get("SHELL_IMAGE", "bico-shell")
TERM_IDLE = int(os.environ.get("TERM_IDLE", "1800"))  # soniya: terminal kiritishsiz yopiladi
MAX_TERMS = int(os.environ.get("MAX_TERMS", "40"))
SUBMIT_GAP = float(os.environ.get("SUBMIT_GAP", "1.0"))  # ketma-ket yuborish orasidagi minimal vaqt
NAME_RE = re.compile(r"^[\w'’.\- ]{2,20}$")


def parse_time(v):
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return datetime.fromisoformat(v).timestamp()


START, END = parse_time(os.environ.get("CTF_START")), parse_time(os.environ.get("CTF_END"))

if not (ROOT / "challenges.json").exists():
    sys.exit("challenges.json yo'q. Avval:  cd .. && python3 build.py")
CHALS = {c["id"]: c for c in json.loads((ROOT / "challenges.json").read_text())}

DATA.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect(DATA / "ctf.db", check_same_thread=False, isolation_level=None)
db.row_factory = sqlite3.Row
db.executescript("""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    salt BLOB NOT NULL, pin_hash BLOB NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS solves(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
    chal TEXT NOT NULL, points INTEGER NOT NULL, at REAL NOT NULL, UNIQUE(user_id, chal));
CREATE TABLE IF NOT EXISTS hints(user_id INTEGER NOT NULL, chal TEXT NOT NULL, idx INTEGER NOT NULL,
    cost INTEGER NOT NULL, PRIMARY KEY(user_id, chal, idx));
""")


# ------------------------------------------------------------------ yordamchilar
def hash_pin(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 100_000)


def status(now=None):
    now = now or time.time()
    if START and now < START:
        return "before"
    if END and now > END:
        return "ended"
    return "running"


def err(msg, code=400):
    return web.json_response({"error": msg}, status=code)


async def body(request):
    if request.content_type != "application/json":
        raise web.HTTPUnsupportedMediaType()
    try:
        data = await request.json()
    except ValueError:
        raise web.HTTPBadRequest()
    if not isinstance(data, dict):
        raise web.HTTPBadRequest()
    return data


def user_of(request):
    tok = request.cookies.get("sid")
    if not tok:
        return None
    return db.execute(
        "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?",
        (hashlib.sha256(tok.encode()).hexdigest(),)).fetchone()


def need_user(request):
    u = user_of(request)
    if not u:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "Avval kiring"}), content_type="application/json")
    return u


def scoreboard_rows():
    rows = db.execute("""
        SELECT u.id, u.name,
          COALESCE((SELECT SUM(points) FROM solves WHERE user_id=u.id),0)
            - COALESCE((SELECT SUM(cost) FROM hints WHERE user_id=u.id),0) AS score,
          (SELECT COUNT(*) FROM solves WHERE user_id=u.id) AS solved,
          (SELECT MAX(at) FROM solves WHERE user_id=u.id) AS last,
          (SELECT COUNT(*) FROM solves s WHERE s.user_id=u.id
             AND s.id=(SELECT MIN(id) FROM solves WHERE chal=s.chal)) AS bloods
        FROM users u""").fetchall()
    rows = sorted(rows, key=lambda r: (-r["score"], r["last"] or float("inf"), r["name"].lower()))
    return [dict(r, rank=i + 1) for i, r in enumerate(rows)]


# ------------------------------------------------------------------ API
async def api_state(request):
    return web.json_response({
        "now": time.time(), "start": START, "end": END, "status": status(), "challenges": len(CHALS),
        "points": sum(c["points"] for c in CHALS.values()),
        "players": db.execute("SELECT COUNT(*) FROM users").fetchone()[0]})


rate_login = collections.defaultdict(collections.deque)


async def api_login(request):
    d = await body(request)
    name = re.sub(r"\s+", " ", str(d.get("name", "")).strip())
    pin = str(d.get("pin", ""))
    if not NAME_RE.match(name):
        return err("Ism 2–20 belgi: harf, raqam, bo'sh joy, . - ' ruxsat etiladi")
    if not re.fullmatch(r"\d{4}", pin):
        return err("PIN aynan 4 ta raqam bo'lsin")
    q = rate_login[name.lower()]
    now = time.time()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= 10:
        return err("Juda ko'p urinish. 1 daqiqa kuting", 429)
    q.append(now)

    u = db.execute("SELECT * FROM users WHERE name=?", (name,)).fetchone()
    if u is None:
        salt = secrets.token_bytes(16)
        cur = db.execute("INSERT INTO users(name,salt,pin_hash,created) VALUES(?,?,?,?)",
                         (name, salt, hash_pin(pin, salt), now))
        uid, created = cur.lastrowid, True
    else:
        if not hmac.compare_digest(hash_pin(pin, u["salt"]), u["pin_hash"]):
            return err("Bu ism band yoki PIN noto'g'ri", 403)
        uid, created = u["id"], False
    tok = secrets.token_urlsafe(32)
    db.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(tok.encode()).hexdigest(), uid, now))
    resp = web.json_response({"ok": True, "created": created})
    resp.set_cookie("sid", tok, httponly=True, samesite="Lax", max_age=7 * 86400, path="/")
    return resp


async def api_logout(request):
    tok = request.cookies.get("sid")
    if tok:
        db.execute("DELETE FROM sessions WHERE token=?", (hashlib.sha256(tok.encode()).hexdigest(),))
    resp = web.json_response({"ok": True})
    resp.del_cookie("sid", path="/")
    return resp


async def api_session(request):
    return web.json_response({"logged_in": user_of(request) is not None})


async def api_me(request):
    u = need_user(request)
    me = next(r for r in scoreboard_rows() if r["id"] == u["id"])
    return web.json_response({"name": u["name"], "score": me["score"], "rank": me["rank"], "solved": me["solved"],
                              "total": len(CHALS)})


async def api_challenges(request):
    u = need_user(request)
    st = status()
    if st == "before":
        return web.json_response({"status": st, "challenges": []})
    counts = {r["chal"]: r["n"] for r in db.execute("SELECT chal, COUNT(*) n FROM solves GROUP BY chal")}
    bloods = {r["chal"]: r["name"] for r in db.execute(
        "SELECT s.chal, u.name FROM solves s JOIN users u ON u.id=s.user_id "
        "WHERE s.id IN (SELECT MIN(id) FROM solves GROUP BY chal)")}
    mine = {r["chal"] for r in db.execute("SELECT chal FROM solves WHERE user_id=?", (u["id"],))}
    opened = collections.defaultdict(set)
    for r in db.execute("SELECT chal, idx FROM hints WHERE user_id=?", (u["id"],)):
        opened[r["chal"]].add(r["idx"])
    out = []
    for c in CHALS.values():
        hints = c["hints"]
        got = sorted(opened[c["id"]])
        out.append({
            "id": c["id"], "category": c["category"], "name": c["name"], "points": c["points"],
            "description": c["description"], "files": c["files"], "web_port": c["web_port"],
            "solves": counts.get(c["id"], 0), "first_blood": bloods.get(c["id"]), "solved": c["id"] in mine,
            "hint_total": len(hints), "hints": [hints[i]["text"] for i in got],
            "next_hint_cost": hints[len(got)]["cost"] if len(got) < len(hints) else None,
        })
    return web.json_response({"status": st, "challenges": out})


async def api_hint(request):
    u = need_user(request)
    d = await body(request)
    c = CHALS.get(d.get("id"))
    if not c or status() != "running":
        return err("Hozir hint ochib bo'lmaydi", 403)
    n = db.execute("SELECT COUNT(*) FROM hints WHERE user_id=? AND chal=?", (u["id"], c["id"])).fetchone()[0]
    if n >= len(c["hints"]):
        return err("Boshqa hint yo'q")
    if db.execute("SELECT 1 FROM solves WHERE user_id=? AND chal=?", (u["id"], c["id"])).fetchone():
        return err("Bu masalani allaqachon yechgansiz")
    h = c["hints"][n]
    db.execute("INSERT INTO hints VALUES(?,?,?,?)", (u["id"], c["id"], n, h["cost"]))
    return web.json_response({"text": h["text"], "cost": h["cost"]})


last_submit = {}
wrongs = collections.defaultdict(collections.deque)


async def api_submit(request):
    u = need_user(request)
    d = await body(request)
    c = CHALS.get(d.get("id"))
    flag = str(d.get("flag", "")).strip()
    if not c or not flag or len(flag) > 200:
        return err("Flag noto'g'ri formatda")
    st = status()
    if st != "running":
        return err("Musobaqa hozir ochiq emas", 403)
    uid, now = u["id"], time.time()
    if now - last_submit.get(uid, 0) < SUBMIT_GAP:
        return err("Sekinroq. Bir soniya kuting", 429)
    w = wrongs[uid]
    while w and now - w[0] > 60:
        w.popleft()
    if len(w) >= 15:
        return err("Daqiqada 15 ta xato urinish mumkin. Biroz kuting", 429)
    last_submit[uid] = now

    if db.execute("SELECT 1 FROM solves WHERE user_id=? AND chal=?", (uid, c["id"])).fetchone():
        return web.json_response({"ok": True, "already": True})
    if not hmac.compare_digest(hashlib.sha256(flag.encode()).hexdigest(), c["flag_sha256"]):
        w.append(now)
        return web.json_response({"ok": False, "message": "Noto'g'ri flag"})
    cur = db.execute("INSERT INTO solves(user_id,chal,points,at) VALUES(?,?,?,?)", (uid, c["id"], c["points"], now))
    first = db.execute("SELECT MIN(id) FROM solves WHERE chal=?", (c["id"],)).fetchone()[0] == cur.lastrowid
    return web.json_response({"ok": True, "points": c["points"], "first_blood": first})


async def api_solvers(request):
    need_user(request)
    cid = request.match_info["id"]
    if cid not in CHALS:
        raise web.HTTPNotFound()
    rows = db.execute("SELECT u.name, s.at FROM solves s JOIN users u ON u.id=s.user_id "
                      "WHERE s.chal=? ORDER BY s.id", (cid,)).fetchall()
    return web.json_response([{"name": r["name"], "at": r["at"], "first": i == 0} for i, r in enumerate(rows)])


async def api_scoreboard(request):
    u = need_user(request)
    rows = scoreboard_rows()
    return web.json_response({"rows": rows, "me": u["id"], "count": len(rows), "total": len(CHALS)})


async def api_feed(request):
    need_user(request)
    rows = db.execute("""SELECT u.name, s.chal, s.points, s.at,
        s.id=(SELECT MIN(id) FROM solves WHERE chal=s.chal) AS blood
        FROM solves s JOIN users u ON u.id=s.user_id ORDER BY s.id DESC LIMIT 20""").fetchall()
    return web.json_response([{"name": r["name"], "task": CHALS[r["chal"]]["name"], "points": r["points"],
                               "at": r["at"], "blood": bool(r["blood"])} for r in rows])


async def get_file(request):
    need_user(request)
    c = CHALS.get(request.match_info["id"])
    fn = request.match_info["name"]
    if not c or fn not in c["files"] or status() == "before":
        raise web.HTTPNotFound()
    return web.FileResponse(ROOT / "files" / c["id"] / fn, headers={
        "Content-Disposition": f'attachment; filename="{fn}"'})


# ------------------------------------------------------------------ terminal
terminals = {}


def _ctty():
    try:
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    except OSError:
        pass


def set_winsize(fd, rows, cols):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


class Term:
    def __init__(self, uid, ws):
        self.uid, self.ws = uid, ws
        self.closed = False
        self.q = asyncio.Queue()
        self.reading = False
        self.last_input = time.time()
        self.tmp = None
        self.cname = f"bico-{uid}"

    def command(self):
        if TERM_MODE == "docker":
            cmd = ["docker", "run", "--rm", "-it", "--name", self.cname, "--hostname", "bico",
                   "--network", "none", "--memory", "128m", "--memory-swap", "128m", "--pids-limit", "64",
                   "--cpus", "0.5", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--read-only", "--user", "1000:1000",
                   "--tmpfs", "/home/talaba:rw,size=48m,uid=1000,gid=1000,mode=700",
                   "--tmpfs", "/tmp:rw,size=16m,mode=1777", SHELL_IMAGE]
            return cmd, dict(os.environ), None
        self.tmp = tempfile.mkdtemp(prefix="bico-term-")
        env = {"PATH": os.environ["PATH"], "HOME": self.tmp, "TERM": "xterm-256color", "LANG": "C.UTF-8",
               "BICO_SRC": str(ROOT / "shell" / "masalalar")}
        return ["bash", "--rcfile", str(ROOT / "shell" / "bashrc"), "-i"], env, self.tmp

    async def start(self):
        loop = asyncio.get_running_loop()
        self.master, slave = pty.openpty()
        set_winsize(self.master, 24, 80)
        cmd, env, cwd = self.command()
        if TERM_MODE == "docker":
            await (await asyncio.create_subprocess_exec("docker", "rm", "-f", self.cname,
                   stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)).wait()
        self.proc = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, start_new_session=True,
                                     close_fds=True, env=env, cwd=cwd, preexec_fn=_ctty)
        os.close(slave)
        os.set_blocking(self.master, False)
        self.loop = loop
        self._reader(True)
        self.tasks = [asyncio.create_task(self._pump()), asyncio.create_task(self._idle())]

    def _reader(self, on):
        if on and not self.reading and not self.closed:
            self.loop.add_reader(self.master, self._on_read)
            self.reading = True
        elif not on and self.reading:
            self.loop.remove_reader(self.master)
            self.reading = False

    def _on_read(self):
        try:
            data = os.read(self.master, 65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            self._reader(False)
            self.q.put_nowait(None)
            return
        self.q.put_nowait(data)
        if self.q.qsize() > 200:  # brauzer ulgurmayapti (masalan `yes`) — o'qishni to'xtatamiz
            self._reader(False)

    async def _pump(self):
        try:
            while True:
                data = await self.q.get()
                if data is None:
                    break
                await self.ws.send_bytes(data)
                if self.q.qsize() < 50:
                    self._reader(True)
        except (ConnectionResetError, RuntimeError):
            pass
        await self.close("Terminal yopildi")

    async def _idle(self):
        while not self.closed:
            await asyncio.sleep(15)
            if time.time() - self.last_input > TERM_IDLE:
                await self.close("Uzoq harakatsizlik — terminal yopildi")

    def write(self, text):
        self.last_input = time.time()
        try:
            os.write(self.master, text.encode())
        except (BlockingIOError, OSError):
            pass

    def resize(self, cols, rows):
        try:
            set_winsize(self.master, max(5, min(rows, 200)), max(20, min(cols, 400)))
        except OSError:
            pass

    async def close(self, msg=None):
        if self.closed:
            return
        self.closed = True
        self._reader(False)
        if terminals.get(self.uid) is self:
            del terminals[self.uid]
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        if TERM_MODE == "docker":
            await asyncio.create_subprocess_exec("docker", "rm", "-f", self.cname,
                                                 stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        self.loop.run_in_executor(None, self.proc.wait)
        try:
            os.close(self.master)
        except OSError:
            pass
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
        for t in getattr(self, "tasks", []):
            if t is not asyncio.current_task():
                t.cancel()
        if not self.ws.closed:
            if msg:
                await self.ws.send_str(json.dumps({"msg": msg}))
            await self.ws.close()


async def ws_terminal(request):
    u = need_user(request)
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).netloc != request.host:  # cross-site WebSocket hijacking'dan himoya
        raise web.HTTPForbidden()
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=64 * 1024)
    await ws.prepare(request)
    if status() == "before":
        await ws.send_str(json.dumps({"msg": "Musobaqa hali boshlanmagan"}))
        await ws.close()
        return ws
    old = terminals.get(u["id"])
    if old:
        await old.close("Terminal boshqa oynada ochildi")
    if len(terminals) >= MAX_TERMS:
        await ws.send_str(json.dumps({"msg": "Server band: terminallar soni chegaraga yetdi. Birozdan keyin urinib ko'ring"}))
        await ws.close()
        return ws
    term = Term(u["id"], ws)
    terminals[u["id"]] = term
    try:
        await term.start()
    except (OSError, ValueError) as e:
        terminals.pop(u["id"], None)
        await ws.send_str(json.dumps({"msg": f"Terminalni ishga tushirib bo'lmadi: {e}"}))
        await ws.close()
        return ws
    async for m in ws:
        if m.type != WSMsgType.TEXT:
            continue
        try:
            d = json.loads(m.data)
        except ValueError:
            continue
        if d.get("t") == "i" and isinstance(d.get("d"), str) and len(d["d"]) <= 8192:
            term.write(d["d"])
        elif d.get("t") == "r" and isinstance(d.get("c"), int) and isinstance(d.get("r"), int):
            term.resize(d["c"], d["r"])
    await term.close()
    return ws


# ------------------------------------------------------------------ sahifalar
@web.middleware
async def headers(request, handler):
    try:
        resp = await handler(request)
    except web.HTTPException as e:
        resp = e
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:; "
        "img-src 'self' data:; frame-ancestors 'none'")
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    if isinstance(resp, web.HTTPException):
        raise resp
    return resp


def page(name):
    async def h(request):
        return web.FileResponse(STATIC / name, headers={"Cache-Control": "no-cache"})
    return h


def make_app():
    app = web.Application(middlewares=[headers])
    r = app.router
    r.add_get("/", page("index.html"))
    for p in ("terminal", "challenges", "scoreboard"):
        r.add_get(f"/{p}", page(f"{p}.html"))
    r.add_get("/api/state", api_state)
    r.add_post("/api/login", api_login)
    r.add_post("/api/logout", api_logout)
    r.add_get("/api/session", api_session)
    r.add_get("/api/me", api_me)
    r.add_get("/api/challenges", api_challenges)
    r.add_post("/api/hint", api_hint)
    r.add_post("/api/submit", api_submit)
    r.add_get("/api/solvers/{id}", api_solvers)
    r.add_get("/api/scoreboard", api_scoreboard)
    r.add_get("/api/feed", api_feed)
    r.add_get("/files/{id}/{name}", get_file)
    r.add_get("/ws/terminal", ws_terminal)
    r.add_static("/assets", STATIC / "assets", follow_symlinks=False)

    async def cleanup(app):
        for t in list(terminals.values()):
            await t.close()
    app.on_cleanup.append(cleanup)
    return app


def cli():
    if len(sys.argv) >= 2 and sys.argv[1] in ("reset-pin", "delete-user"):
        cmd, name = sys.argv[1], sys.argv[2]
        u = db.execute("SELECT * FROM users WHERE name=?", (name,)).fetchone()
        if not u:
            sys.exit(f"'{name}' topilmadi")
        if cmd == "reset-pin":
            pin = sys.argv[3]
            assert re.fullmatch(r"\d{4}", pin), "PIN 4 raqam bo'lsin"
            salt = secrets.token_bytes(16)
            db.execute("UPDATE users SET salt=?, pin_hash=? WHERE id=?", (salt, hash_pin(pin, salt), u["id"]))
            db.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
        else:
            for t in ("sessions", "solves", "hints"):
                db.execute(f"DELETE FROM {t} WHERE user_id=?", (u["id"],))
            db.execute("DELETE FROM users WHERE id=?", (u["id"],))
        print("OK")
        return
    if TERM_MODE == "local":
        print("OGOHLANTIRISH: TERM_MODE=local — terminal serverning o'zida, izolyatsiyasiz ishlaydi. Faqat sinov uchun!")
    print(f"BICO CTF: http://{HOST}:{PORT}  (terminal: {TERM_MODE}, holat: {status()})")
    web.run_app(make_app(), host=HOST, port=PORT, print=None)


if __name__ == "__main__":
    cli()

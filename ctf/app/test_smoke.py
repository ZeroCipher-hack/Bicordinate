#!/usr/bin/env python3
"""Server smoke testi: o'z serverini (TERM_MODE=local) ishga tushirib, API va terminalni tekshiradi.
Ishlatish:  python3 test_smoke.py     (aiohttp kerak; avval ../build.py)"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import aiohttp

HERE = Path(__file__).parent
FLAGS = dict(l.strip().split("=", 1) for l in (HERE.parent / ".flags.env").read_text().splitlines())
flag = lambda cid: FLAGS["FLAG_" + cid.upper()]
fails = []


def check(name, cond, extra=""):
    print(("OK  " if cond else "FAIL"), name, extra if not cond else "")
    if not cond:
        fails.append(name)


async def main():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = dict(os.environ, TERM_MODE="local", PORT=str(port), CTF_DATA=tempfile.mkdtemp(), SUBMIT_GAP="0.05")
    srv = subprocess.Popen([sys.executable, str(HERE / "server.py")], env=env, stdout=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), 0.2).close(); break
            except OSError:
                await asyncio.sleep(0.1)

        opened = []

        async def client(name, pin="1234"):
            c = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
            opened.append(c)
            r = await c.post(base + "/api/login", json={"name": name, "pin": pin})
            return c, r.status

        async def post(c, path, **kw):
            r = await c.post(base + path, json=kw)
            return r.status, await r.json()

        anon = aiohttp.ClientSession()
        opened.append(anon)
        check("API kirishsiz 401", (await anon.get(base + "/api/challenges")).status == 401)
        check("sahifalar ochiladi", (await anon.get(base + "/")).status == 200)

        a, st = await client("Dilnoza")
        check("ro'yxatdan o'tish", st == 200)
        check("noto'g'ri PIN rad", (await client("Dilnoza", "9999"))[1] == 403)
        check("ism katta-kichik harfsiz band", (await client("dilnoza", "9999"))[1] == 403)
        check("XSS ism rad", (await client("<script>alert(1)</script>"))[1] == 400)
        check("PIN formati", (await client("Ali", "12"))[1] == 400)
        check("JSON bo'lmagan POST rad", (await a.post(base + "/api/submit", data="x")).status == 415)

        j = await (await a.get(base + "/api/challenges")).json()
        ch = {c["id"]: c for c in j["challenges"]}
        check("51 masala", len(ch) == 51)
        dump = json.dumps([c for c in j["challenges"] if c["id"] != "welcome"])
        check("flag/xesh mijozga chiqmaydi", "flag_sha256" not in dump and not any(
            flag(cid) in dump for cid in ch if cid != "welcome"))
        check("hint matni yopiq", ch["l_catn"]["hints"] == [] and ch["l_catn"]["next_hint_cost"] == 10)

        st, r = await post(a, "/api/submit", id="l_catn", flag="BICO{noto'g'ri}")
        check("xato flag", st == 200 and r["ok"] is False)
        await asyncio.sleep(0.1)
        st, r = await post(a, "/api/submit", id="l_catn", flag=flag("l_catn"))
        check("to'g'ri flag + first blood", r.get("ok") and r.get("first_blood") is True and r["points"] == 25, r)
        await asyncio.sleep(0.1)
        st, r = await post(a, "/api/submit", id="l_catn", flag=flag("l_catn"))
        check("qayta yuborish ball bermaydi", r.get("already") is True)

        b, _ = await client("Sardor")
        st, r = await post(b, "/api/submit", id="l_catn", flag=" " + flag("l_catn") + " ")
        check("ikkinchi o'quvchi first blood emas", r.get("ok") and r.get("first_blood") is False, r)
        await asyncio.sleep(0.1)
        st, r = await post(b, "/api/hint", id="l_hidden")
        await asyncio.sleep(0.1)
        check("hint -10 ball", r.get("cost") == 10 and "ls" in r.get("text", ""), r)
        st, r = await post(b, "/api/submit", id="l_hidden", flag=flag("l_hidden"))
        await asyncio.sleep(0.1)

        sol = await (await a.get(base + "/api/solvers/l_catn")).json()
        check("solvers: Dilnoza birinchi", [x["name"] for x in sol] == ["Dilnoza", "Sardor"] and sol[0]["first"])
        sb = await (await a.get(base + "/api/scoreboard")).json()
        by = {x["name"]: x for x in sb["rows"]}
        check("reyting: Dilnoza 25 ball, 1 blood", by["Dilnoza"]["score"] == 25 and by["Dilnoza"]["bloods"] == 1, by)
        check("reyting: Sardor 25+25-10=40, 1 blood (l_hidden)", by["Sardor"]["score"] == 40 and by["Sardor"]["bloods"] == 1, by)
        check("reyting tartibi", [x["name"] for x in sb["rows"]] == ["Sardor", "Dilnoza"])
        feed = await (await a.get(base + "/api/feed")).json()
        check("lenta", feed and feed[0]["task"] == "Ko'rinmas fayl" and feed[0]["blood"] is True, feed)

        # rate limit: 15 ta xato
        c, _ = await client("Tez")
        codes = []
        for _ in range(18):
            codes.append((await post(c, "/api/submit", id="l_catn", flag="BICO{x}"))[0])
            await asyncio.sleep(0.06)
        check("xato urinishlar cheklanadi (429)", 429 in codes, codes)

        check("fayl yuklash", (await a.get(base + "/files/l_catn/uy.tar.gz")).status == 200)
        check("ro'yxatda yo'q fayl 404", (await a.get(base + "/files/l_catn/../../server.py")).status in (404, 400))
        check("kirishsiz fayl 401", (await anon.get(base + "/files/l_catn/uy.tar.gz")).status == 401)

        # terminal
        bad = await anon.get(base + "/ws/terminal", headers={"Origin": "http://evil.example"})
        check("kirishsiz/begona origin terminal rad", bad.status in (401, 403))
        ws = await a.ws_connect(base + "/ws/terminal", headers={"Origin": base})
        await ws.send_str(json.dumps({"t": "r", "c": 100, "r": 30}))
        await ws.send_str(json.dumps({"t": "i", "d": "ls masalalar | wc -l; cd masalalar/l_catn && tar xzf uy.tar.gz && sed -n 237p uy/royxat.txt\n"}))
        out = b""
        t0 = time.time()
        while time.time() - t0 < 10 and flag("l_catn").encode() not in out:
            try:
                m = await ws.receive(timeout=1)
            except asyncio.TimeoutError:
                continue
            if m.type == aiohttp.WSMsgType.BINARY:
                out += m.data
        check("terminal: buyruq ishlaydi, flag topildi", flag("l_catn").encode() in out and b"51" in out, out[-300:])
        ws2 = await b.ws_connect(base + "/ws/terminal", headers={"Origin": base})
        await ws.close(); await ws2.close()
    finally:
        for c in opened:
            await c.close()
        srv.terminate()
        srv.wait(5)
    print("\nHAMMASI OK" if not fails else f"\nXATOLAR: {fails}")
    return 1 if fails else 0


sys.exit(asyncio.run(main()))

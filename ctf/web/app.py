"""Web masalalar — bitta image, CHAL env bilan tanlanadi (robots | cookie | sqli | idor)."""
import base64
import os
import sqlite3

from flask import Flask, abort, make_response, redirect, render_template_string, request

CHAL = os.environ["CHAL"]
FLAG = os.environ["FLAG"]
app = Flask(__name__)

PAGE = """<!doctype html><meta charset=utf-8><title>{{ title }}</title>
<style>body{font:16px/1.5 system-ui;max-width:640px;margin:3rem auto;padding:0 1rem}
code,pre{background:#eee;padding:.1rem .3rem}input{padding:.4rem;margin:.2rem 0}</style>
<h1>{{ title }}</h1>{{ body|safe }}"""


def page(title, body):
    return render_template_string(PAGE, title=title, body=body)


# --- robots ---------------------------------------------------------------
if CHAL == "robots":
    HIDDEN = "/s3cr3t-panel-7731"

    @app.get("/")
    def index():
        return page("Bicoordinate Studio", "<p>Sayt qurilmoqda. Tez orada ochiladi!</p>")

    @app.get("/robots.txt")
    def robots():
        return f"User-agent: *\nDisallow: {HIDDEN}\n", 200, {"Content-Type": "text/plain"}

    @app.get(HIDDEN)
    def secret():
        return page("Maxfiy panel", f"<p>Topding! <code>{FLAG}</code></p>")


# --- cookie ---------------------------------------------------------------
elif CHAL == "cookie":
    def enc(s):
        return base64.b64encode(s.encode()).decode()

    @app.get("/")
    def index():
        resp = make_response(page("Mehmon paneli", '<p>Salom, mehmon.</p><p><a href="/admin">Admin bo\'limi</a></p>'))
        if "role" not in request.cookies:
            resp.set_cookie("role", enc("guest"))
        return resp

    @app.get("/admin")
    def admin():
        try:
            role = base64.b64decode(request.cookies.get("role", "")).decode()
        except Exception:
            role = ""
        if role != "admin":
            return page("403", "<p>Faqat adminlar uchun.</p>"), 403
        return page("Admin", f"<p>Xush kelibsiz, admin. <code>{FLAG}</code></p>")


# --- sqli -----------------------------------------------------------------
elif CHAL == "sqli":
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE TABLE users (username TEXT, password TEXT)")
    db.execute("INSERT INTO users VALUES ('admin', ?)", (os.urandom(16).hex(),))
    db.execute("INSERT INTO users VALUES ('guest', 'guest')")

    FORM = '<form method=post>Login: <input name=u><br>Parol: <input name=p type=password><br><button>Kirish</button></form>'

    @app.route("/", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return page("Admin kirish", FORM)
        u, p = request.form.get("u", ""), request.form.get("p", "")
        try:
            row = db.execute(f"SELECT username FROM users WHERE username='{u}' AND password='{p}'").fetchone()
        except sqlite3.Error as e:
            return page("Xato", f"<pre>{e}</pre>" + FORM), 500
        if row and row[0] == "admin":
            return page("Admin", f"<p>Xush kelibsiz! <code>{FLAG}</code></p>")
        if row:
            return page("Mehmon", "<p>Siz oddiy foydalanuvchisiz. Admin kerak.</p>")
        return page("Xato", "<p>Login yoki parol noto'g'ri.</p>" + FORM), 401


# --- idor -----------------------------------------------------------------
elif CHAL == "idor":
    NOTES = {i: f"Eslatma #{i}: bugun hech narsa muhim emas." for i in range(1, 31)}
    NOTES[1] = "Eslatma #1: o'z eslatmalaringiz shu yerda: /note/1"
    NOTES[17] = f"ADMIN (maxfiy): {FLAG}"

    @app.get("/")
    def index():
        return redirect("/note/1")

    @app.get("/note/<int:nid>")
    def note(nid):
        if nid not in NOTES:
            abort(404)
        return page(f"Eslatma {nid}", f"<p>{NOTES[nid]}</p>")

else:
    raise SystemExit(f"noma'lum CHAL: {CHAL}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

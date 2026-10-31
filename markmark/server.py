"""Local web server. It only ever listens on this laptop."""
import base64
import binascii
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import core, db

STATIC = Path(__file__).parent / "static"
MAX_BODY = 700 * 1024 * 1024
ROUTES = []


def route(method, pattern):
    def register(fn):
        ROUTES.append((method, re.compile(f"^{pattern}$"), fn))
        return fn
    return register


def decoded(body):
    try:
        return body["filename"], base64.b64decode(body["data"], validate=True)
    except (KeyError, binascii.Error, TypeError, ValueError):
        raise core.Problem("bad_upload")


def name_of(body):
    name = str(body.get("name") or "").strip()
    if not name:
        raise core.Problem("name_required")
    return name


@route("GET", "/api/tree")
def _(c, b, q): return core.tree(c)


@route("POST", "/api/classes")
def _(c, b, q): return {"id": c.execute("INSERT INTO classes(name) VALUES(?)", (name_of(b),)).lastrowid}


@route("DELETE", r"/api/classes/(\d+)")
def _(c, b, q, i): c.execute("DELETE FROM classes WHERE id=?", (i,))


@route("GET", r"/api/classes/(\d+)/students")
def _(c, b, q, i): return core.rows(c.execute("SELECT * FROM students WHERE class_id=? ORDER BY name", (i,)))


@route("POST", r"/api/classes/(\d+)/students")
def _(c, b, q, i): return {"added": core.add_students(c, i, b.get("text", ""))}


@route("DELETE", r"/api/students/(\d+)")
def _(c, b, q, i): c.execute("DELETE FROM students WHERE id=?", (i,))


@route("POST", "/api/subjects")
def _(c, b, q): return {"id": c.execute("INSERT INTO subjects(name) VALUES(?)", (name_of(b),)).lastrowid}


@route("DELETE", r"/api/subjects/(\d+)")
def _(c, b, q, i): c.execute("DELETE FROM subjects WHERE id=?", (i,))


@route("PUT", r"/api/subjects/(\d+)/classes")
def _(c, b, q, i): core.set_subject_classes(c, i, b.get("class_ids", []))


@route("POST", r"/api/subjects/(\d+)/weeks")
def add_week(c, b, q, i):
    number = c.execute("SELECT COALESCE(MAX(number),0)+1 FROM weeks WHERE subject_id=?", (i,)).fetchone()[0]
    return {"id": c.execute("INSERT INTO weeks(subject_id,number,title) VALUES(?,?,?)",
                            (i, number, b.get("title", ""))).lastrowid}


@route("PUT", r"/api/weeks/(\d+)")
def _(c, b, q, i): c.execute("UPDATE weeks SET title=? WHERE id=?", (str(b.get("title", "")).strip(), i))


@route("DELETE", r"/api/weeks/(\d+)")
def _(c, b, q, i): c.execute("DELETE FROM weeks WHERE id=?", (i,))


@route("GET", r"/api/weeks/(\d+)")
def _(c, b, q, i): return core.week_view(c, i, int(q["class"]))


@route("POST", r"/api/weeks/(\d+)/modules")
def _(c, b, q, i): return core.add_module(c, i, *decoded(b))


@route("DELETE", r"/api/modules/(\d+)")
def _(c, b, q, i): c.execute("DELETE FROM modules WHERE id=?", (i,))


@route("POST", r"/api/weeks/(\d+)/key")
def _(c, b, q, i): return core.upload_key(c, i, *decoded(b))


@route("POST", r"/api/weeks/(\d+)/key/generate")
def _(c, b, q, i): core.generate_key(c, i)


@route("PUT", r"/api/weeks/(\d+)/key")
def _(c, b, q, i): core.edit_key(c, i, b.get("text", ""), bool(b.get("approve")))


@route("POST", r"/api/weeks/(\d+)/answers")
def _(c, b, q, i): return core.add_answers(c, i, int(q["class"]), *decoded(b))


@route("POST", r"/api/unmatched/(\d+)/assign")
def _(c, b, q, i): core.assign_unmatched(c, i, int(b["student_id"]))


@route("POST", r"/api/weeks/(\d+)/check")
def _(c, b, q, i): core.start_check(c, i, int(q["class"]))


@route("GET", "/api/job")
def _(c, b, q): return core.JOB.snapshot()


@route("POST", "/api/job/cancel")
def _(c, b, q): core.JOB.cancel.set()


@route("GET", r"/api/submissions/(\d+)")
def _(c, b, q, i): return {**core.review_view(c, i), "feedback": core.feedback(c, i)}


@route("PUT", r"/api/findings/(\d+)")
def _(c, b, q, i): core.decide(c, i, b.get("status"), b.get("description"))


@route("PUT", r"/api/submissions/(\d+)/grade")
def _(c, b, q, i): core.save_grade(c, i, b.get("score", ""), b.get("comment", ""))


@route("GET", "/api/settings")
def read_settings(c, b, q):
    settings = core.get_settings(c)
    settings["has_key"] = bool(settings.pop("api_key"))  # the key itself never leaves the backend
    return settings


@route("PUT", "/api/settings")
def _(c, b, q): core.put_settings(c, b)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def reply(self, body, kind="application/json", status=200, extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def simulation(self, body=None):
        """These run outside a request connection because they switch databases."""
        if self.command == "PUT":
            core.set_simulation(body.get("on"))
        elif self.command == "POST":
            core.reset_simulation()
        return {"on": db.SIMULATION}

    def trusted(self):
        """Stop other websites open in the browser from reaching this server (DNS rebinding, CSRF)."""
        port = self.server.server_address[1]
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return False
        return self.command == "GET" or self.headers.get("X-Markmark") == "1"

    def handle_any(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self.close_connection = True
            return self.reply({"error": "too_large"}, status=413)
        raw = self.rfile.read(length) if length else b""
        if not self.trusted():
            return self.reply({"error": "forbidden"}, status=403)
        url = urlparse(self.path)
        if self.command == "GET" and url.path == "/":
            return self.reply((STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.command == "GET" and (m := re.fullmatch(r"/static/fonts/([\w-]+\.woff2)", url.path)):
            path = STATIC / "fonts" / m[1]
            if path.exists():
                return self.reply(path.read_bytes(), "font/woff2")
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        if self.command == "GET" and (m := re.fullmatch(r"/api/weeks/(\d+)/export", url.path)):
            conn = db.connect()
            try:
                text = core.export_csv(conn, int(m[1]), int(query["class"]))
            finally:
                conn.close()
            return self.reply("﻿".encode() + text.encode(), "text/csv; charset=utf-8",
                              extra={"Content-Disposition": 'attachment; filename="markmark.csv"'})
        if url.path in ("/api/simulation", "/api/simulation/reset"):
            try:
                return self.reply(self.simulation(json.loads(raw) if raw else {}))
            except core.Problem as e:
                return self.reply({"error": e.code, **e.detail}, status=e.status)
        for method, pattern, fn in ROUTES:
            match = pattern.match(url.path)
            if method == self.command and match:
                conn = db.connect()
                try:
                    with conn:
                        body = json.loads(raw) if raw else {}
                        result = fn(conn, body, query, *map(int, match.groups()))
                    return self.reply({"ok": True} if result is None else result)
                except core.Problem as e:
                    return self.reply({"error": e.code, **e.detail}, status=e.status)
                except (KeyError, ValueError) as e:
                    return self.reply({"error": "bad_request", "message": str(e)}, status=400)
                finally:
                    conn.close()
        self.reply({"error": "not_found"}, status=404)

    do_GET = do_POST = do_PUT = do_DELETE = handle_any


class Server(ThreadingHTTPServer):
    allow_reuse_address = False  # on Windows it would let a second copy share the port with an old one


def make_server(port=8765):
    db.init()
    return Server(("127.0.0.1", port), Handler)

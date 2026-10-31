"""Business rules. HTTP lives in server.py; everything here works on a sqlite connection."""
import csv
import io
import re
import threading
from datetime import datetime, timezone

from . import ai, db, readers

try:
    import keyring
except ImportError:
    keyring = None

SERVICE = "markmark"


class Problem(Exception):
    def __init__(self, code, status=400, **detail):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


def rows(cursor):
    return [dict(r) for r in cursor]


def one(conn, sql, *args):
    row = conn.execute(sql, args).fetchone()
    if row is None:
        raise Problem("not_found", 404)
    return dict(row)


# ---------- settings ----------

def _key_file():
    return db.home() / "api_key"


def save_key(value):
    if keyring:
        try:
            keyring.set_password(SERVICE, "api_key", value)
            _key_file().unlink(missing_ok=True)
            return
        except Exception:
            pass  # no system keychain here; use the private file below
    path = _key_file()
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(value, encoding="utf-8")


def load_key():
    if keyring:
        try:
            value = keyring.get_password(SERVICE, "api_key")
            if value:
                return value
        except Exception:
            pass
    path = _key_file()
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def get_settings(conn):
    stored = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}
    return {"base_url": stored.get("base_url", ""), "model": stored.get("model", ""),
            "language": stored.get("language", "id"), "api_key": load_key()}


def put_settings(conn, data):
    for key in ("base_url", "model", "language"):
        if key in data:
            conn.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, str(data[key]).strip()))
    if data.get("api_key"):
        save_key(data["api_key"].strip())


def ai_settings(conn):
    settings = get_settings(conn)
    if not settings["base_url"] or not settings["model"]:
        raise Problem("ai_not_configured")
    return settings


# ---------- structure ----------

def tree(conn):
    classes = rows(conn.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM students s WHERE s.class_id=c.id) students FROM classes c ORDER BY name"))
    subjects = rows(conn.execute("SELECT * FROM subjects ORDER BY name"))
    for subject in subjects:
        subject["class_ids"] = [r[0] for r in conn.execute(
            "SELECT class_id FROM class_subjects WHERE subject_id=?", (subject["id"],))]
        subject["weeks"] = rows(conn.execute(
            "SELECT * FROM weeks WHERE subject_id=? ORDER BY number", (subject["id"],)))
    return {"classes": classes, "subjects": subjects}


def parse_students(text):
    """Accepts 'name' or 'number,name' lines; separators may be comma, semicolon or tab."""
    found = []
    for line in text.splitlines():
        parts = [p.strip() for p in re.split(r"[,;\t]", line) if p.strip()]
        numbers = [p for p in parts if re.fullmatch(r"[\d\-./]+", p)]
        names = [p for p in parts if p not in numbers]
        if names:
            found.append((names[0], numbers[0] if numbers else ""))
    return found


def add_students(conn, class_id, text):
    one(conn, "SELECT id FROM classes WHERE id=?", class_id)
    existing = {(r["name"].lower(), r["student_no"]) for r in
                conn.execute("SELECT name, student_no FROM students WHERE class_id=?", (class_id,))}
    new = [s for s in parse_students(text) if (s[0].lower(), s[1]) not in existing]
    conn.executemany("INSERT INTO students(class_id,name,student_no) VALUES(?,?,?)",
                     [(class_id, name, no) for name, no in new])
    return len(new)


def set_subject_classes(conn, subject_id, class_ids):
    conn.execute("DELETE FROM class_subjects WHERE subject_id=?", (subject_id,))
    conn.executemany("INSERT INTO class_subjects VALUES(?,?)", [(int(c), subject_id) for c in class_ids])


# ---------- week materials ----------

def _texts(filename, data):
    """Readable (path, text) pairs and skipped {file, reason} items from one upload."""
    good, skipped = [], []
    try:
        for path, content in readers.unpack(filename, data):
            try:
                good.append((path, readers.to_text(path, content)))
            except readers.Unreadable as e:
                skipped.append({"file": path, "reason": str(e)})
    except readers.Unreadable as e:
        skipped.append({"file": filename, "reason": str(e)})
    return good, skipped


def add_module(conn, week_id, filename, data):
    one(conn, "SELECT id FROM weeks WHERE id=?", week_id)
    good, skipped = _texts(filename, data)
    conn.executemany("INSERT INTO modules(week_id,filename,text) VALUES(?,?,?)",
                     [(week_id, path, text) for path, text in good])
    return {"added": len(good), "skipped": skipped}


def upload_key(conn, week_id, filename, data):
    one(conn, "SELECT id FROM weeks WHERE id=?", week_id)
    good, skipped = _texts(filename, data)
    if not good:
        raise Problem("unreadable_file", skipped=skipped)
    text = "\n\n".join(f"===== {path} =====\n{body}" for path, body in good)
    conn.execute("INSERT OR REPLACE INTO answer_keys VALUES(?,'upload','approved',?,?)", (week_id, filename, text))
    return {"skipped": skipped}


def generate_key(conn, week_id):
    modules = rows(conn.execute("SELECT filename, text FROM modules WHERE week_id=?", (week_id,)))
    if not modules:
        raise Problem("module_required")
    settings = ai_settings(conn)
    material = "\n\n".join(f"===== {m['filename']} =====\n{m['text']}" for m in modules)
    try:
        text = ai.draft_key(settings, material, settings["language"])
    except ai.AIError as e:
        raise Problem("ai_failed", 502, message=str(e))
    conn.execute("INSERT OR REPLACE INTO answer_keys VALUES(?,'ai','draft','',?)", (week_id, text))


def edit_key(conn, week_id, text, approve):
    key = one(conn, "SELECT * FROM answer_keys WHERE week_id=?", week_id)
    if not text.strip():
        raise Problem("empty_key")
    status = "approved" if approve else key["status"]
    conn.execute("UPDATE answer_keys SET text=?, status=? WHERE week_id=?", (text, status, week_id))


# ---------- submissions ----------

def _squash(text):
    return re.sub(r"[^0-9a-z]+", "", text.lower())


def match_student(students, path):
    """The one student this path belongs to, by number first, then full name. Ambiguity means no match."""
    numbered = [s for s in students if s["student_no"] and
                re.search(rf"(?<!\d)0*{re.escape(s['student_no'].lstrip('0') or '0')}(?!\d)", path)]
    if len(numbered) == 1:
        return numbered[0]
    if numbered:
        return None
    flat = _squash(path)
    named = [s for s in students if _squash(s["name"]) and _squash(s["name"]) in flat]
    return named[0] if len(named) == 1 else None


def _attach(conn, week_id, student_id, path, text):
    conn.execute("INSERT OR IGNORE INTO submissions(week_id,student_id) VALUES(?,?)", (week_id, student_id))
    sid = one(conn, "SELECT id FROM submissions WHERE week_id=? AND student_id=?", week_id, student_id)["id"]
    conn.execute("INSERT OR REPLACE INTO submission_files(submission_id,filename,text) VALUES(?,?,?)",
                 (sid, path.rsplit("/", 1)[-1], text))
    # New work invalidates earlier results for this student.
    conn.execute("DELETE FROM findings WHERE submission_id=?", (sid,))
    conn.execute("DELETE FROM grades WHERE submission_id=?", (sid,))
    conn.execute("UPDATE submissions SET status='waiting', error='', summary='', truncated=0 WHERE id=?", (sid,))


def check_linked(conn, week_id, class_id):
    linked = conn.execute(
        "SELECT 1 FROM weeks w JOIN class_subjects cs ON cs.subject_id=w.subject_id "
        "WHERE w.id=? AND cs.class_id=?", (week_id, class_id)).fetchone()
    if not linked:
        raise Problem("class_not_linked")


def add_answers(conn, week_id, class_id, filename, data):
    check_linked(conn, week_id, class_id)
    students = rows(conn.execute("SELECT * FROM students WHERE class_id=?", (class_id,)))
    good, skipped = _texts(filename, data)
    matched = unmatched = 0
    for path, text in good:
        student = match_student(students, path)
        if student:
            _attach(conn, week_id, student["id"], path, text)
            matched += 1
        else:
            conn.execute("INSERT INTO unmatched(week_id,class_id,filename,text) VALUES(?,?,?,?)",
                         (week_id, class_id, path, text))
            unmatched += 1
    return {"matched": matched, "unmatched": unmatched, "skipped": skipped}


def assign_unmatched(conn, unmatched_id, student_id):
    item = one(conn, "SELECT * FROM unmatched WHERE id=?", unmatched_id)
    one(conn, "SELECT id FROM students WHERE id=? AND class_id=?", student_id, item["class_id"])
    _attach(conn, item["week_id"], student_id, item["filename"], item["text"])
    conn.execute("DELETE FROM unmatched WHERE id=?", (unmatched_id,))


def blockers(conn, week_id, class_id):
    """Why checking cannot start. Empty means it can."""
    missing = []
    key = conn.execute("SELECT status FROM answer_keys WHERE week_id=?", (week_id,)).fetchone()
    if key is None:
        missing.append("key_missing")
    elif key["status"] != "approved":
        missing.append("key_not_approved")
    has_answers = conn.execute(
        "SELECT 1 FROM submissions su JOIN students st ON st.id=su.student_id "
        "WHERE su.week_id=? AND st.class_id=? LIMIT 1", (week_id, class_id)).fetchone()
    if not has_answers:
        missing.append("answers_missing")
    return missing


def week_view(conn, week_id, class_id):
    week = one(conn, "SELECT w.*, s.name subject FROM weeks w JOIN subjects s ON s.id=w.subject_id WHERE w.id=?",
               week_id)
    key = conn.execute("SELECT source,status,filename,text FROM answer_keys WHERE week_id=?", (week_id,)).fetchone()
    week["key"] = dict(key) if key else None
    week["modules"] = rows(conn.execute("SELECT id, filename FROM modules WHERE week_id=?", (week_id,)))
    week["students"] = rows(conn.execute(
        """SELECT st.id student_id, st.name, st.student_no, su.id submission_id, su.status, su.error, g.score,
             (SELECT COUNT(*) FROM findings f WHERE f.submission_id=su.id) findings,
             (SELECT COUNT(*) FROM findings f WHERE f.submission_id=su.id AND f.status='pending') pending
           FROM students st LEFT JOIN submissions su ON su.student_id=st.id AND su.week_id=?
           LEFT JOIN grades g ON g.submission_id=su.id WHERE st.class_id=? ORDER BY st.name""",
        (week_id, class_id)))
    week["unmatched"] = rows(conn.execute(
        "SELECT id, filename FROM unmatched WHERE week_id=? AND class_id=?", (week_id, class_id)))
    week["blockers"] = blockers(conn, week_id, class_id)
    return week


# ---------- checking job ----------

class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.state = {"running": False, "done": 0, "total": 0, "failed": 0}

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def update(self, **change):
        with self.lock:
            self.state.update(change)


JOB = Job()


def check_one(conn, settings, submission, key_text):
    files = rows(conn.execute("SELECT filename, text FROM submission_files WHERE submission_id=? ORDER BY filename",
                              (submission["id"],)))
    answer = "\n\n".join(f"===== {f['filename']} =====\n{f['text']}" for f in files)
    hidden = ai.anonymize(answer, submission["name"], submission["student_no"])
    found, summary, truncated = ai.check_answer(settings, key_text, hidden, settings["language"], JOB.cancel)
    reveal = lambda s: s.replace("STUDENT_NAME", submission["name"]).replace("STUDENT_NO", submission["student_no"])
    conn.execute("DELETE FROM findings WHERE submission_id=?", (submission["id"],))
    conn.executemany(
        "INSERT INTO findings(submission_id,section,kind,description,quote,verified) VALUES(?,?,?,?,?,?)",
        [(submission["id"], f["section"], f["kind"], reveal(f["description"]), reveal(f["quote"]), f["verified"])
         for f in found])
    conn.execute("UPDATE submissions SET status='review', error='', summary=?, truncated=? WHERE id=?",
                 (reveal(summary), int(truncated), submission["id"]))


def _run(week_id, class_id):
    conn = db.connect()
    done = failed = 0
    try:
        settings = get_settings(conn)
        key_text = one(conn, "SELECT text FROM answer_keys WHERE week_id=?", week_id)["text"]
        todo = rows(conn.execute(
            """SELECT su.id, st.name, st.student_no FROM submissions su JOIN students st ON st.id=su.student_id
               WHERE su.week_id=? AND st.class_id=? AND su.status IN ('waiting','error') ORDER BY st.name""",
            (week_id, class_id)))
        JOB.update(total=len(todo))
        for submission in todo:
            if JOB.cancel.is_set():
                break
            with conn:
                conn.execute("UPDATE submissions SET status='running' WHERE id=?", (submission["id"],))
            try:
                with conn:
                    check_one(conn, settings, submission, key_text)
                done += 1
            except ai.AIError as e:
                cancelled = JOB.cancel.is_set()
                with conn:
                    conn.execute("UPDATE submissions SET status=?, error=? WHERE id=?",
                                 ("waiting" if cancelled else "error", "" if cancelled else str(e)[:500],
                                  submission["id"]))
                failed += not cancelled
            JOB.update(done=done, failed=failed)
    finally:
        conn.close()
        JOB.update(running=False)


def start_check(conn, week_id, class_id):
    check_linked(conn, week_id, class_id)
    missing = blockers(conn, week_id, class_id)
    if missing:
        raise Problem("cannot_check", 409, missing=missing)
    ai_settings(conn)
    with JOB.lock:
        if JOB.state["running"]:
            raise Problem("already_running", 409)
        JOB.state.update(running=True, done=0, total=0, failed=0)
    JOB.cancel.clear()
    threading.Thread(target=_run, args=(week_id, class_id), daemon=True).start()


# ---------- human proof ----------

def review_view(conn, submission_id):
    item = one(conn, """SELECT su.*, st.name, st.student_no, g.score, g.comment FROM submissions su
                        JOIN students st ON st.id=su.student_id LEFT JOIN grades g ON g.submission_id=su.id
                        WHERE su.id=?""", submission_id)
    item["files"] = rows(conn.execute(
        "SELECT filename, text FROM submission_files WHERE submission_id=? ORDER BY filename", (submission_id,)))
    item["findings"] = rows(conn.execute("SELECT * FROM findings WHERE submission_id=?", (submission_id,)))
    return item


def decide(conn, finding_id, status, description=None):
    if status not in ("accepted", "rejected", "edited", "pending"):
        raise Problem("bad_status")
    finding = one(conn, "SELECT id, submission_id FROM findings WHERE id=?", finding_id)
    if status == "edited" and not (description or "").strip():
        raise Problem("empty_description")
    conn.execute("UPDATE findings SET status=?, description=COALESCE(?,description) WHERE id=?",
                 (status, description if status == "edited" else None, finding_id))
    # Changing your mind about a finding reopens the grade that relied on it.
    conn.execute("DELETE FROM grades WHERE submission_id=?", (finding["submission_id"],))


def save_grade(conn, submission_id, score, comment):
    submission = one(conn, "SELECT status FROM submissions WHERE id=?", submission_id)
    if submission["status"] != "review":
        raise Problem("not_reviewed")
    pending = conn.execute("SELECT COUNT(*) FROM findings WHERE submission_id=? AND status='pending'",
                           (submission_id,)).fetchone()[0]
    if pending:
        raise Problem("findings_pending", 409, pending=pending)
    if not str(score).strip():
        raise Problem("score_required")
    conn.execute("INSERT OR REPLACE INTO grades VALUES(?,?,?,?)",
                 (submission_id, str(score).strip(), comment or "", datetime.now(timezone.utc).isoformat()))


def feedback(conn, submission_id):
    """Student feedback built only from findings the grader confirmed."""
    items = conn.execute("SELECT section, description FROM findings WHERE submission_id=? "
                         "AND status IN ('accepted','edited')", (submission_id,)).fetchall()
    return "\n".join(f"• {r['section'] + ': ' if r['section'] else ''}{r['description']}" for r in items)


def export_csv(conn, week_id, class_id):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["student_no", "name", "score", "comment", "confirmed_findings", "feedback"])
    for s in week_view(conn, week_id, class_id)["students"]:
        grade = conn.execute("SELECT score, comment FROM grades WHERE submission_id=?",
                             (s["submission_id"],)).fetchone() if s["submission_id"] else None
        text = feedback(conn, s["submission_id"]) if s["submission_id"] else ""
        cells = [s["student_no"], s["name"], grade["score"] if grade else "", grade["comment"] if grade else "",
                 len(text.splitlines()), text]
        # Keep spreadsheets from evaluating supplied text as a formula.
        writer.writerow(["'" + c if isinstance(c, str) and c[:1] in ("=", "+", "-", "@") else c for c in cells])
    return out.getvalue()

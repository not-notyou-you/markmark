"""Local SQLite storage. Everything lives in ~/.markmark (or MARKMARK_HOME)."""
import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS classes(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS students(
  id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes ON DELETE CASCADE,
  name TEXT NOT NULL, student_no TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS class_subjects(
  class_id INTEGER NOT NULL REFERENCES classes ON DELETE CASCADE,
  subject_id INTEGER NOT NULL REFERENCES subjects ON DELETE CASCADE,
  PRIMARY KEY(class_id, subject_id));
CREATE TABLE IF NOT EXISTS weeks(
  id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL REFERENCES subjects ON DELETE CASCADE,
  number INTEGER NOT NULL, title TEXT NOT NULL DEFAULT '', UNIQUE(subject_id, number));
CREATE TABLE IF NOT EXISTS modules(
  id INTEGER PRIMARY KEY, week_id INTEGER NOT NULL REFERENCES weeks ON DELETE CASCADE,
  filename TEXT NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS answer_keys(
  week_id INTEGER PRIMARY KEY REFERENCES weeks ON DELETE CASCADE,
  source TEXT NOT NULL CHECK(source IN ('upload','ai')),
  status TEXT NOT NULL CHECK(status IN ('draft','approved')),
  filename TEXT NOT NULL DEFAULT '', text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS submissions(
  id INTEGER PRIMARY KEY, week_id INTEGER NOT NULL REFERENCES weeks ON DELETE CASCADE,
  student_id INTEGER NOT NULL REFERENCES students ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'waiting'
    CHECK(status IN ('waiting','running','review','error')),
  error TEXT NOT NULL DEFAULT '', truncated INTEGER NOT NULL DEFAULT 0, summary TEXT NOT NULL DEFAULT '',
  UNIQUE(week_id, student_id));
CREATE TABLE IF NOT EXISTS submission_files(
  id INTEGER PRIMARY KEY, submission_id INTEGER NOT NULL REFERENCES submissions ON DELETE CASCADE,
  filename TEXT NOT NULL, text TEXT NOT NULL, UNIQUE(submission_id, filename));
CREATE TABLE IF NOT EXISTS unmatched(
  id INTEGER PRIMARY KEY, week_id INTEGER NOT NULL REFERENCES weeks ON DELETE CASCADE,
  class_id INTEGER NOT NULL REFERENCES classes ON DELETE CASCADE,
  filename TEXT NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS findings(
  id INTEGER PRIMARY KEY, submission_id INTEGER NOT NULL REFERENCES submissions ON DELETE CASCADE,
  section TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'other',
  description TEXT NOT NULL, quote TEXT NOT NULL DEFAULT '', verified INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected','edited')));
CREATE TABLE IF NOT EXISTS grades(
  submission_id INTEGER PRIMARY KEY REFERENCES submissions ON DELETE CASCADE,
  score TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '', decided_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


SIMULATION = False  # simulation data lives in its own file and never mixes with real work


def home():
    path = Path(os.environ.get("MARKMARK_HOME") or Path.home() / ".markmark")
    path.mkdir(parents=True, exist_ok=True)
    return path


def connect():
    conn = sqlite3.connect(home() / ("simulation.db" if SIMULATION else "markmark.db"), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init():
    with connect() as conn:
        conn.executescript(SCHEMA)
        # A crash mid-run must not leave work stuck: it simply resumes next time.
        conn.execute("UPDATE submissions SET status='waiting' WHERE status='running'")

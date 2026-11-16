"""Database layer (Neon Postgres via psycopg 3). Plain SQL, no ORM.

Connection string, first match wins:
  1. DATABASE_URL environment variable  (GitHub Actions; Streamlit Cloud also exposes root secrets this way)
  2. DATABASE_URL in .streamlit/secrets.toml  (local runs of the app or of scripts)

Every function opens and closes its own short connection unless you pass `conn=`.
To do several calls on one page load, share one connection:

    with db.connect() as conn:
        kws = db.get_keywords(uid, conn=conn)
        author = db.get_author(uid, conn=conn)

Privacy rule: functions used by the app all take a `user_id` and only touch that user's rows.
The few that read across users (active_users, unsent_reports) are for the weekly job and n8n only.
"""
from __future__ import annotations

import datetime as dt
import os
import time
import tomllib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / ".streamlit" / "secrets.toml"
SCHEMA = ROOT / "db" / "schema.sql"
TZ = ZoneInfo("Asia/Seoul")   # report weeks start on Monday, Korea time
MIN_KEYWORDS, MAX_KEYWORDS = 2, 3
CONNECT_TIMEOUT = 15          # seconds; Neon wakes from idle in ~1 s but allow slack
CONNECT_RETRIES = 2


class ConfigError(RuntimeError):
    pass


# ---------------------------------------------------------------- connection

def get_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url and SECRETS.exists():
        url = tomllib.loads(SECRETS.read_text(encoding="utf-8")).get("DATABASE_URL")
    if not url or "<" in url:
        raise ConfigError("DATABASE_URL is not set (environment variable or .streamlit/secrets.toml).")
    return url


def connect(url: str | None = None) -> psycopg.Connection:
    """Open a connection. Used as `with connect() as conn:` it commits on success, rolls back on error."""
    url = url or get_url()
    for attempt in range(CONNECT_RETRIES + 1):
        try:
            return psycopg.connect(url, row_factory=dict_row, connect_timeout=CONNECT_TIMEOUT)
        except psycopg.OperationalError:
            if attempt == CONNECT_RETRIES:
                raise
            time.sleep(2 * (attempt + 1))   # compute endpoint may still be waking up
    raise AssertionError("unreachable")


@contextmanager
def _use(conn: psycopg.Connection | None) -> Iterator[psycopg.Connection]:
    if conn is not None:
        yield conn
    else:
        with connect() as c:
            yield c


def apply_schema(conn: psycopg.Connection | None = None) -> None:
    with _use(conn) as c:
        c.execute(SCHEMA.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- helpers

def week_start(day: dt.date | None = None) -> dt.date:
    """Monday of the week containing `day` (default: today in Korea)."""
    day = day or dt.datetime.now(TZ).date()
    return day - dt.timedelta(days=day.weekday())


def short_id(openalex_id: str) -> str:
    """'https://openalex.org/A123' -> 'A123'."""
    return openalex_id.rstrip("/").rsplit("/", 1)[-1]


# ---------------------------------------------------------------- users (app)

def login(auth_sub: str, email: str, name: str = "", conn=None) -> dict:
    """Find or create the user for an Auth0 login and return the row.

    Matches on auth_sub first, then on email (so the same person signing in with email code
    and with Google lands on one account). Only pass emails that Auth0 marks as verified.
    """
    email = email.strip()
    with _use(conn) as c:
        row = c.execute("UPDATE users SET email = %s, updated_at = now() WHERE auth_sub = %s RETURNING *",
                        (email, auth_sub)).fetchone()
        if row:
            return row
        row = c.execute("SELECT * FROM users WHERE lower(email) = lower(%s)", (email,)).fetchone()
        if row:
            return row
        return c.execute("INSERT INTO users (auth_sub, email, name) VALUES (%s, %s, %s) RETURNING *",
                         (auth_sub, email, name.strip())).fetchone()


def get_user(user_id: int, conn=None) -> dict | None:
    with _use(conn) as c:
        return c.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()


def update_profile(user_id: int, *, name: str | None = None, lab_name: str | None = None,
                   email_enabled: bool | None = None, onboarded: bool = False, conn=None) -> dict:
    fields = {k: v for k, v in (("name", name), ("lab_name", lab_name), ("email_enabled", email_enabled))
              if v is not None}
    sets = [f"{k} = %({k})s" for k in fields] + ["updated_at = now()"]
    if onboarded:
        sets.append("onboarded_at = coalesce(onboarded_at, now())")
    with _use(conn) as c:
        row = c.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = %(id)s RETURNING *",
                        {**{k: v.strip() if isinstance(v, str) else v for k, v in fields.items()},
                         "id": user_id}).fetchone()
    if row is None:
        raise LookupError(f"user {user_id} not found")
    return row


# ---------------------------------------------------------------- keywords & author (app)

def set_keywords(user_id: int, terms: Iterable[str], conn=None) -> list[str]:
    """Replace the user's keywords. Trims, drops blanks and case-insensitive duplicates."""
    clean: list[str] = []
    for t in terms:
        t = " ".join(t.split())
        if t and t.lower() not in {x.lower() for x in clean}:
            clean.append(t)
    if not MIN_KEYWORDS <= len(clean) <= MAX_KEYWORDS:
        raise ValueError(f"Please enter {MIN_KEYWORDS}-{MAX_KEYWORDS} different keywords.")
    with _use(conn) as c, c.transaction():
        c.execute("DELETE FROM keywords WHERE user_id = %s", (user_id,))
        c.cursor().executemany("INSERT INTO keywords (user_id, position, term) VALUES (%s, %s, %s)",
                               [(user_id, i, t) for i, t in enumerate(clean)])
    return clean


def get_keywords(user_id: int, conn=None) -> list[str]:
    with _use(conn) as c:
        rows = c.execute("SELECT term FROM keywords WHERE user_id = %s ORDER BY position", (user_id,)).fetchall()
    return [r["term"] for r in rows]


def set_author(user_id: int, openalex_id: str, display_name: str, institution: str = "", conn=None) -> dict:
    """Replace the user's followed author with the profile they confirmed."""
    with _use(conn) as c, c.transaction():
        c.execute("DELETE FROM followed_authors WHERE user_id = %s", (user_id,))
        return c.execute(
            "INSERT INTO followed_authors (user_id, openalex_id, display_name, institution) "
            "VALUES (%s, %s, %s, %s) RETURNING *",
            (user_id, short_id(openalex_id), display_name, institution or "")).fetchone()


def get_author(user_id: int, conn=None) -> dict | None:
    with _use(conn) as c:
        return c.execute("SELECT * FROM followed_authors WHERE user_id = %s ORDER BY confirmed_at DESC LIMIT 1",
                         (user_id,)).fetchone()


# ---------------------------------------------------------------- reports (app)

def list_reports(user_id: int, conn=None) -> list[dict]:
    """Past weeks for the picker, newest first (without the heavy report body)."""
    with _use(conn) as c:
        return c.execute("SELECT id, week_start, created_at, updated_at, emailed_at FROM reports "
                         "WHERE user_id = %s ORDER BY week_start DESC", (user_id,)).fetchall()


def get_report(user_id: int, week: dt.date | None = None, conn=None) -> dict | None:
    """The user's report for `week` (a Monday), or their latest one if `week` is None."""
    with _use(conn) as c:
        if week is None:
            return c.execute("SELECT * FROM reports WHERE user_id = %s ORDER BY week_start DESC LIMIT 1",
                             (user_id,)).fetchone()
        return c.execute("SELECT * FROM reports WHERE user_id = %s AND week_start = %s",
                         (user_id, week)).fetchone()


# ---------------------------------------------------------------- weekly job

def active_users(conn=None) -> list[dict]:
    """Users who finished onboarding, with their keywords and followed author."""
    with _use(conn) as c:
        return c.execute("""
            SELECT u.id, u.email, u.name, u.lab_name, u.email_enabled,
                   coalesce((SELECT array_agg(k.term ORDER BY k.position) FROM keywords k
                             WHERE k.user_id = u.id), '{}') AS keywords,
                   (SELECT to_jsonb(a) - 'user_id' FROM followed_authors a
                    WHERE a.user_id = u.id ORDER BY a.confirmed_at DESC LIMIT 1) AS author
            FROM users u
            WHERE u.onboarded_at IS NOT NULL
            ORDER BY u.id""").fetchall()


def start_run(trigger: str = "manual", conn=None) -> int:
    with _use(conn) as c:
        return c.execute("INSERT INTO runs (trigger) VALUES (%s) RETURNING id", (trigger,)).fetchone()["id"]


def finish_run(run_id: int, users_ok: int, users_failed: int, error: str | None = None, conn=None) -> str:
    """Close the run; status is derived from the counts. Returns the status."""
    if not (users_failed or error):
        status = "success"
    else:
        status = "partial" if users_ok else "failed"
    with _use(conn) as c:
        c.execute("UPDATE runs SET finished_at = now(), status = %s, users_ok = %s, users_failed = %s, "
                  "error = %s WHERE id = %s", (status, users_ok, users_failed, error, run_id))
    return status


def last_runs(limit: int = 10, conn=None) -> list[dict]:
    with _use(conn) as c:
        return c.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT %s", (limit,)).fetchall()


def save_report(user_id: int, week: dt.date, data: dict, markdown: str = "", email_html: str = "",
                run_id: int | None = None, conn=None) -> dict:
    """Insert or replace the user's report for `week`. A report already emailed keeps its
    emailed_at, so re-running the job does not send the same week twice."""
    with _use(conn) as c:
        return c.execute("""
            INSERT INTO reports (user_id, week_start, run_id, data, markdown, email_html)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, week_start) DO UPDATE SET
                run_id = EXCLUDED.run_id, data = EXCLUDED.data, markdown = EXCLUDED.markdown,
                email_html = EXCLUDED.email_html, updated_at = now()
            RETURNING id, user_id, week_start, created_at, updated_at, emailed_at""",
            (user_id, week, run_id, Jsonb(data), markdown, email_html)).fetchone()


def unseen(user_id: int, work_ids: Iterable[str], conn=None) -> list[str]:
    """The subset of `work_ids` this user has not been shown yet (input order kept)."""
    ids = list(dict.fromkeys(short_id(w) for w in work_ids))
    if not ids:
        return []
    with _use(conn) as c:
        seen = {r["work_id"] for r in c.execute(
            "SELECT work_id FROM seen_papers WHERE user_id = %s AND work_id = ANY(%s)", (user_id, ids))}
    return [w for w in ids if w not in seen]


def mark_seen(user_id: int, work_ids: Iterable[str], week: dt.date, conn=None) -> None:
    rows = [(user_id, short_id(w), week) for w in dict.fromkeys(work_ids)]
    if not rows:
        return
    with _use(conn) as c:
        c.cursor().executemany("INSERT INTO seen_papers (user_id, work_id, first_seen_week) VALUES (%s, %s, %s) "
                               "ON CONFLICT DO NOTHING", rows)


# ---------------------------------------------------------------- emailing (n8n can also run these as SQL)

def unsent_reports(week: dt.date | None = None, conn=None) -> list[dict]:
    """Reports not emailed yet, for users who have email turned on."""
    sql = ("SELECT r.id, r.user_id, r.week_start, r.email_html, u.email, u.name FROM reports r "
           "JOIN users u ON u.id = r.user_id WHERE r.emailed_at IS NULL AND u.email_enabled")
    params: tuple = ()
    if week is not None:
        sql += " AND r.week_start = %s"
        params = (week,)
    with _use(conn) as c:
        return c.execute(sql + " ORDER BY r.id", params).fetchall()


def mark_emailed(report_id: int, conn=None) -> None:
    with _use(conn) as c:
        c.execute("UPDATE reports SET emailed_at = now() WHERE id = %s AND emailed_at IS NULL", (report_id,))


# ---------------------------------------------------------------- shared OpenAlex cache (public data only)

def cache_get(cache_key: str, conn=None) -> dict | None:
    with _use(conn) as c:
        return c.execute("SELECT data, saved_at FROM openalex_cache WHERE cache_key = %s", (cache_key,)).fetchone()


def cache_put(cache_key: str, data: Any, conn=None) -> None:
    with _use(conn) as c:
        c.execute("INSERT INTO openalex_cache (cache_key, data) VALUES (%s, %s) ON CONFLICT (cache_key) "
                  "DO UPDATE SET data = EXCLUDED.data, saved_at = now()", (cache_key, Jsonb(data)))

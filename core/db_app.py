"""앱·주간 작업이 쓰는 DB 계약. 실제 DB 함수(core/db.py, Neon Postgres)를 이 모양으로 이어 준다.

로그인 화면(ui/account.py), 리포트 화면(ui/report.py), 주간 작업(weekly_run.py)은 `from core.store import db`
로 이 파일(또는 같은 계약을 파일로 구현한 core/db_fake.py, PR_DB=fake)만 쓴다. core/db.py 는 고치지 않는다.
계약을 바꿀 때는 이 파일과 core/db_fake.py 를 같이 바꾼다.

user   = {"id": int, "email": str(소문자), "name": str, "lab": str, "keywords": [str, ...],
          "author": {"id": "A5...", "name": str, "inst": str} 또는 None, "created_at": ISO 문자열 또는 None}
report = {"user_id": int, "week_start": "YYYY-MM-DD"(그 주 월요일), "data": dict(리포트 JSON),
          "created_at": ISO 문자열}

키워드는 KW_MIN~KW_MAX 개 (core/db.py 의 MIN_KEYWORDS, MAX_KEYWORDS 와 같다).
DATABASE_URL 이 없으면 NotConnected(NotImplementedError 의 한 종류)를 낸다.
"""
from __future__ import annotations

import datetime as dt
import os
from contextlib import contextmanager
from typing import Iterator

from core import db as neon

KW_MIN, KW_MAX = neon.MIN_KEYWORDS, neon.MAX_KEYWORDS
_run_id: int | None = None  # 지금 도는 주간 작업의 run id (리포트에 같이 적는다)


class NotConnected(NotImplementedError):
    """DATABASE_URL 이 설정되지 않음. 기존 화면·주간 작업의 'DB 미연결' 처리로 그대로 이어진다."""


@contextmanager
def _conn() -> Iterator:
    """연결 하나로 여러 함수를 묶는다. 끝나면 커밋, 중간에 오류가 나면 전부 취소."""
    try:
        conn = neon.connect()
    except neon.ConfigError as e:
        raise NotConnected(str(e)) from e
    with conn:
        yield conn


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _author(row: dict | None) -> dict | None:
    if not row:
        return None
    return {"id": row["openalex_id"], "name": row["display_name"], "inst": row.get("institution") or ""}


def _user(row: dict, keywords: list[str], author: dict | None) -> dict:
    return {"id": row["id"], "email": row["email"].strip().lower(), "name": row["name"], "lab": row["lab_name"],
            "keywords": list(keywords), "author": author, "created_at": _iso(row.get("created_at"))}


def _onboarded(conn, email: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE lower(email) = lower(%s) AND onboarded_at IS NOT NULL",
                       (email.strip(),)).fetchone()
    if row is None:
        return None
    return _user(row, neon.get_keywords(row["id"], conn=conn), _author(neon.get_author(row["id"], conn=conn)))


# ---------------------------------------------------------------- 로그인 화면

def get_user(email: str) -> dict | None:
    """email로 user 한 명. 첫 로그인 폼을 아직 안 끝냈으면 None."""
    with _conn() as conn:
        return _onboarded(conn, email)


def save_profile(email: str, name: str, lab: str, keywords: list[str], author: dict | None,
                 sub: str | None = None) -> dict:
    """첫 로그인 폼 저장. 이미 있으면 고치고, 없으면 새로 만든다. 저장된 user를 돌려준다.

    sub 는 Auth0 사용자 id. 개발용 로그인(PR_DEV_USER)처럼 없으면 "dev|<email>" 을 쓴다.
    키워드가 KW_MIN~KW_MAX 개가 아니면 ValueError (아무것도 저장되지 않음).
    """
    email = email.strip().lower()
    with _conn() as conn:
        row = neon.login(sub or f"dev|{email}", email, name, conn=conn)
        neon.update_profile(row["id"], name=name, lab_name=lab, onboarded=True, conn=conn)
        neon.set_keywords(row["id"], keywords, conn=conn)
        if author:
            neon.set_author(row["id"], author["id"], author["name"], author.get("inst", ""), conn=conn)
        else:
            conn.execute("DELETE FROM followed_authors WHERE user_id = %s", (row["id"],))
        return _onboarded(conn, email)


# ---------------------------------------------------------------- 리포트 화면

def latest_report(user_id: int) -> dict | None:
    """가장 최근 주의 report. 없으면 None."""
    with _conn() as conn:
        row = neon.get_report(user_id, conn=conn)
    if row is None:
        return None
    return {"user_id": row["user_id"], "week_start": row["week_start"].isoformat(), "data": row["data"],
            "created_at": _iso(row["created_at"])}


# ---------------------------------------------------------------- 주간 작업

def list_active_users() -> list[dict]:
    """주간 작업 대상: 첫 로그인 폼을 끝낸 user 전부."""
    with _conn() as conn:
        rows = neon.active_users(conn=conn)
    return [_user({**r, "created_at": None}, r["keywords"] or [], _author(r["author"])) for r in rows]


def seen_ids(user_id: int, before_week: str) -> set[str]:
    """before_week(YYYY-MM-DD)보다 앞선 주의 리포트에 이미 나간 논문 id."""
    with _conn() as conn:
        rows = conn.execute("SELECT work_id FROM seen_papers WHERE user_id = %s AND first_seen_week < %s",
                            (user_id, dt.date.fromisoformat(before_week))).fetchall()
    return {r["work_id"] for r in rows}


def save_report(user_id: int, week_start: str, data: dict, paper_ids: list[str]) -> None:
    """리포트와 '이미 본 논문' 기록을 한 번에 저장. 같은 (user_id, week_start)는 덮어쓴다.

    같은 주를 다시 돌리면 그 주에 처음 기록된 논문 목록도 새 결과로 바꾼다(지난주 기록은 그대로).
    """
    week = dt.date.fromisoformat(week_start)
    with _conn() as conn:
        neon.save_report(user_id, week, data, run_id=_run_id, conn=conn)
        conn.execute("DELETE FROM seen_papers WHERE user_id = %s AND first_seen_week = %s", (user_id, week))
        neon.mark_seen(user_id, paper_ids, week, conn=conn)


def run_started() -> int:
    """주간 작업 한 번의 시작을 기록하고 run_id를 돌려준다."""
    global _run_id
    trigger = "schedule" if os.environ.get("GITHUB_EVENT_NAME") == "schedule" else "manual"
    with _conn() as conn:
        _run_id = neon.start_run(trigger, conn=conn)
    return _run_id


def run_finished(run_id: int, ok: int, failed: int, errors: list[str]) -> None:
    """주간 작업 결과(성공·실패 사용자 수, 오류 메시지)를 기록한다."""
    global _run_id
    with _conn() as conn:
        neon.finish_run(run_id, ok, failed, "\n".join(errors) or None, conn=conn)
    _run_id = None

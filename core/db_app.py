"""첫 로그인 폼(ui/onboarding.py)이 쓰는 DB 계약. 실제 DB 함수(core/db.py, Neon Postgres)를 이 모양으로 이어 준다.

폼은 `from core.store import db` 로 이 파일(또는 같은 계약을 파일로 구현한 core/db_fake.py, PR_DB=fake)만 쓴다.
core/db.py 는 고치지 않는다. 계약을 바꿀 때는 이 파일과 core/db_fake.py 를 같이 바꾼다.

user = {"id": int, "email": str(소문자), "name": str, "lab": str, "keywords": [str, ...],
        "author": {"id": "A5...", "name": str, "inst": str} 또는 None, "created_at": ISO 문자열 또는 None}

키워드는 KW_MIN~KW_MAX 개 (core/db.py 의 MIN_KEYWORDS, MAX_KEYWORDS 와 같다).
DATABASE_URL 이 없으면 NotConnected(NotImplementedError 의 한 종류)를 낸다.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from core import db as neon

KW_MIN, KW_MAX = neon.MIN_KEYWORDS, neon.MAX_KEYWORDS


class NotConnected(NotImplementedError):
    """DATABASE_URL 이 설정되지 않음. 폼은 'DB 미연결' 안내를 보여 준다."""


@contextmanager
def _conn() -> Iterator:
    """연결 하나로 여러 함수를 묶는다. 끝나면 커밋, 중간에 오류가 나면 전부 취소."""
    try:
        conn = neon.connect()
    except neon.ConfigError as e:
        raise NotConnected(str(e)) from e
    with conn:
        yield conn


def _author(row: dict | None) -> dict | None:
    if not row:
        return None
    return {"id": row["openalex_id"], "name": row["display_name"], "inst": row.get("institution") or ""}


def _onboarded(conn, email: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE lower(email) = lower(%s) AND onboarded_at IS NOT NULL",
                       (email.strip(),)).fetchone()
    if row is None:
        return None
    created = row.get("created_at")
    return {"id": row["id"], "email": row["email"].strip().lower(), "name": row["name"], "lab": row["lab_name"],
            "keywords": list(neon.get_keywords(row["id"], conn=conn)),
            "author": _author(neon.get_author(row["id"], conn=conn)),
            "created_at": created.isoformat() if created is not None else None}


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

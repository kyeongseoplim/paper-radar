"""core/db_app.py 와 같은 계약을 파일 하나(cache/fake_db.json)로 구현한 것. 개발·테스트 전용.

cache/ 는 git에 올라가지 않는다. 처음부터 다시 하려면 cache/fake_db.json 을 지우면 된다.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "cache" / "fake_db.json"


def _load() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"users": [], "reports": [], "seen": [], "runs": []}


def _save(d: dict) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def get_user(email: str) -> dict | None:
    email = email.strip().lower()
    return next((u for u in _load()["users"] if u["email"] == email), None)


KW_MIN, KW_MAX = 2, 3  # 실제 DB(core/db.py)와 같은 키워드 개수 규칙


def save_profile(email: str, name: str, lab: str, keywords: list[str], author: dict | None,
                 sub: str | None = None) -> dict:
    if not KW_MIN <= len(keywords) <= KW_MAX:
        raise ValueError(f"Please enter {KW_MIN}-{KW_MAX} different keywords.")
    d = _load()
    email = email.strip().lower()
    user = next((u for u in d["users"] if u["email"] == email), None)
    if user is None:
        user = {"id": max((u["id"] for u in d["users"]), default=0) + 1, "email": email, "created_at": _now()}
        d["users"].append(user)
    user.update(name=name, lab=lab, keywords=list(keywords), author=author)
    _save(d)
    return user


def list_active_users() -> list[dict]:
    return _load()["users"]


def seen_ids(user_id: int, before_week: str) -> set[str]:
    return {s["paper_id"] for s in _load()["seen"] if s["user_id"] == user_id and s["week_start"] < before_week}


def save_report(user_id: int, week_start: str, data: dict, paper_ids: list[str]) -> None:
    d = _load()

    def other(row: dict) -> bool:
        return not (row["user_id"] == user_id and row["week_start"] == week_start)

    d["reports"] = [r for r in d["reports"] if other(r)]
    d["seen"] = [s for s in d["seen"] if other(s)]
    d["reports"].append({"user_id": user_id, "week_start": week_start, "data": data, "created_at": _now()})
    d["seen"] += [{"user_id": user_id, "week_start": week_start, "paper_id": p} for p in paper_ids]
    _save(d)


def latest_report(user_id: int) -> dict | None:
    mine = [r for r in _load()["reports"] if r["user_id"] == user_id]
    return max(mine, key=lambda r: r["week_start"]) if mine else None


def run_started() -> int:
    d = _load()
    run_id = len(d["runs"]) + 1
    d["runs"].append({"id": run_id, "started_at": _now(), "finished_at": None})
    _save(d)
    return run_id


def run_finished(run_id: int, ok: int, failed: int, errors: list[str]) -> None:
    d = _load()
    for r in d["runs"]:
        if r["id"] == run_id:
            r.update(finished_at=_now(), ok=ok, failed=failed, errors=list(errors))
    _save(d)

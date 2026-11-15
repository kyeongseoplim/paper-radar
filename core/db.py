"""DB 계약(초안): 함수 이름·인자·반환 형태만 정해 둔다. 본문은 실제 DB(Neon Postgres) 담당이 채운다.
같은 계약을 파일로 구현한 것이 core/db_fake.py 이다 (PR_DB=fake). 계약을 바꿀 때는 두 파일을 같이 바꾼다.

user   = {"id": int, "email": str(소문자), "name": str, "lab": str, "keywords": [str, ...],
          "author": {"id": "A5...", "name": str, "inst": str} 또는 None, "created_at": ISO 문자열}
report = {"user_id": int, "week_start": "YYYY-MM-DD"(그 주 월요일), "data": dict(리포트 JSON),
          "created_at": ISO 문자열}
"""
from __future__ import annotations


def get_user(email: str) -> dict | None:
    """email로 user 한 명. 없으면 None."""
    raise NotImplementedError


def save_profile(email: str, name: str, lab: str, keywords: list[str], author: dict | None) -> dict:
    """첫 로그인 폼 저장. 이미 있으면 고치고, 없으면 새로 만든다. 저장된 user를 돌려준다."""
    raise NotImplementedError


def list_active_users() -> list[dict]:
    """주간 작업 대상: 프로필을 끝낸 user 전부."""
    raise NotImplementedError


def seen_ids(user_id: int, before_week: str) -> set[str]:
    """before_week(YYYY-MM-DD)보다 앞선 주의 리포트에 이미 나간 논문 id."""
    raise NotImplementedError


def save_report(user_id: int, week_start: str, data: dict, paper_ids: list[str]) -> None:
    """리포트와 '이미 본 논문' 기록을 한 번에 저장. 같은 (user_id, week_start)는 덮어쓴다."""
    raise NotImplementedError


def latest_report(user_id: int) -> dict | None:
    """가장 최근 주의 report. 없으면 None."""
    raise NotImplementedError


def run_started() -> int:
    """주간 작업 한 번의 시작을 기록하고 run_id를 돌려준다."""
    raise NotImplementedError


def run_finished(run_id: int, ok: int, failed: int, errors: list[str]) -> None:
    """주간 작업 결과(성공·실패 사용자 수, 오류 메시지)를 기록한다."""
    raise NotImplementedError

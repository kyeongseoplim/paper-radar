"""DB 선택 스위치. 다른 파일은 `from core.store import db` 로만 DB를 쓴다.

PR_DB=fake → core/db_fake.py (cache/fake_db.json 파일. 계정·DB 없이 개발할 때)
그 외      → core/db.py (실제 DB)
값은 환경변수에서 먼저 찾고, 없으면 .streamlit/secrets.toml 에서 찾는다.
"""
from __future__ import annotations

import os


def flag(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, ""))
    except Exception:  # secrets.toml이 없거나 Streamlit 밖에서 실행
        return ""


if flag("PR_DB") == "fake":
    from core import db_fake as db
else:
    from core import db

__all__ = ["db", "flag"]

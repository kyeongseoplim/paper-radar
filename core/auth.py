"""로그인 계층: 지금 화면을 보는 사람의 email만 알려준다. 화면은 ui/account.py 가 그린다.

세 가지 상태
- secrets.toml 에 [auth] 가 있다       → 실제 로그인 (st.login, Auth0 이메일 코드)
- [auth] 가 없고 PR_DEV_USER 가 있다    → 그 이메일로 들어온 것으로 친다 (개발용)
- 둘 다 없다                           → 로그인 준비 중
"""
from __future__ import annotations

import streamlit as st

from core.store import flag


def configured() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:  # secrets.toml이 없으면 예외
        return False


def dev_email() -> str | None:
    """[auth] 가 있으면 항상 None. 실제 배포에서 개발용 우회가 켜지지 않게 한다."""
    if configured():
        return None
    return flag("PR_DEV_USER").strip().lower() or None


def available() -> bool:
    return configured() or dev_email() is not None


def current_email() -> str | None:
    """로그인한 사람의 email(소문자). 로그인 전이면 None."""
    if not configured():
        return dev_email()
    if not st.user.is_logged_in:
        return None
    email = st.user.get("email")
    return email.strip().lower() if email else None


def login() -> None:
    st.login()


def logout() -> None:
    st.logout()

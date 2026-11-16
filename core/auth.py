"""로그인 계층: 지금 화면을 보는 사람의 email만 알려준다. 화면(로그인 화면, 첫 로그인 폼)은 ui/onboarding.py 가 그린다.
로그인한 사람의 DB 행·관리자 확인은 ui/auth.py 가 맡는다. 둘 다 같은 [auth] 설정(st.login, Auth0)을 쓴다.

세 가지 상태
- secrets.toml 에 [auth] 가 채워져 있다  → 실제 로그인 (st.login, Auth0 이메일 코드)
- [auth] 가 없고 PR_DEV_USER 가 있다     → 그 이메일로 들어온 것으로 친다 (개발용)
- 둘 다 없다                            → 로그인 준비 중
"""
from __future__ import annotations

import time

import streamlit as st

from core.store import flag

FRESH_LOGIN_SECONDS = 120  # 로그인(토큰 발급) 후 이 시간 안에 첫 화면에 오면 '방금 로그인함'으로 본다


def _auth_section():
    try:
        return st.secrets.get("auth")
    except Exception:  # secrets.toml이 없으면 예외
        return None


def configured() -> bool:
    """[auth] 가 실제 값으로 채워져 있으면 True. 예시 파일의 "<...>" 자리표시가 남아 있으면 False (ui/auth.py 와 같은 기준)."""
    section = _auth_section()
    return bool(section) and not any("<" in str(v) for v in section.values())


def dev_email() -> str | None:
    """[auth] 가 있으면(자리표시라도) 항상 None. 실제 배포에서 개발용 우회가 켜지지 않게 한다."""
    if _auth_section() is not None:
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


@st.cache_resource
def _sent_to_my_radar() -> set:
    """이미 My radar로 보낸 로그인 목록 (사용자, 토큰 발급 시각). 서버가 켜져 있는 동안 공유된다."""
    return set()


def take_fresh_login() -> bool:
    """방금 로그인했으면 True를 로그인당 한 번만 돌려준다.

    Streamlit은 로그인이 끝나면 항상 첫 화면(/)으로 돌려보낸다. 첫 화면에서 이 함수로
    '방금 로그인함'을 알아내 My radar로 다시 보낸다. ID 토큰 발급 시각(iat)으로 판단한다.
    """
    if not configured() or not st.user.is_logged_in:
        return False
    try:
        issued = float(st.user.get("iat"))
    except (TypeError, ValueError):
        return False
    key = (st.user.get("sub") or st.user.get("email"), issued)
    if time.time() - issued > FRESH_LOGIN_SECONDS or key in _sent_to_my_radar():
        return False
    _sent_to_my_radar().add(key)
    return True


def current_sub() -> str | None:
    """로그인한 사람의 Auth0 사용자 id(sub). 개발용 로그인이나 로그인 전이면 None."""
    if not configured() or not st.user.is_logged_in:
        return None
    return st.user.get("sub")


def login() -> None:
    st.login()


def logout() -> None:
    st.logout()

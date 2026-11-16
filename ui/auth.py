"""Login via Streamlit's built-in OIDC (st.login) with Auth0, linked to the users table.

Needs an [auth] section in secrets (see .streamlit/secrets.toml.example). Without it the site
still works as the public demo and the Sign in button is hidden.
"""
from __future__ import annotations

import streamlit as st

from core import db


def _secrets() -> dict:
    try:
        return st.secrets.to_dict()
    except Exception:  # no secrets.toml
        return {}


def configured() -> bool:
    """True when [auth] is filled in (values still like "<Auth0 Client ID>" from the example count as not set)."""
    auth = _secrets().get("auth")
    return bool(auth) and not any("<" in str(v) for v in auth.values())


def current_user() -> dict | None:
    """The logged-in user's row from the database (created on first login), else None."""
    ss = st.session_state
    if not configured() or not st.user.is_logged_in:
        ss.pop("user", None)
        return None
    if st.user.get("email_verified") is False or not st.user.get("email"):
        st.error("Your email address is not verified. Please sign in with a verified email.")
        return None
    if ss.get("user") is None or ss.get("user_sub") != st.user.sub:
        ss.user = db.login(st.user.sub, st.user.email, st.user.get("name") or "")
        ss.user_sub = st.user.sub
    return ss.user


def refresh() -> None:
    """Reload the cached user row after it changed."""
    if st.session_state.get("user"):
        st.session_state.user = db.get_user(st.session_state.user["id"])


def is_admin(user: dict | None) -> bool:
    admins = {e.lower() for e in _secrets().get("ADMIN_EMAILS", [])}
    return bool(user) and user["email"].lower() in admins

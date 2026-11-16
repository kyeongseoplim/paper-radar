"""My radar 화면(주간 리포트). 지금은 자리만 잡아 둔 상태이고, 리포트 화면 담당이 채운다.

render(user) 는 로그인과 첫 로그인 폼을 통과한 user(core/db.py 의 user 형태)를 받는다.
"""
from __future__ import annotations

import html

import streamlit as st

from core.store import db
from ui import style


def render(user: dict) -> None:
    report = db.latest_report(user["id"])
    author = user.get("author")
    st.html(style.eyebrow("MY RADAR", dot=True)
            + f'<div class="pr-h1">Hello, {html.escape(user["name"])}.</div>'
            + f'<p class="pr-sub">{html.escape(user["lab"])} · Keywords: {html.escape(", ".join(user["keywords"]))}'
            + (f' · Following: {html.escape(author["name"])}' if author else "") + "</p>")
    if report is None:
        st.html('<div class="pr-soon"><b>Your first weekly report is on its way.</b>'
                '<p class="pr-note">It appears here after the next weekly run.</p></div>')
    else:
        st.caption(f'Week of {report["week_start"]}')
        st.json(report["data"], expanded=1)

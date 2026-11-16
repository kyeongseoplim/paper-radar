"""Paper Radar — type keywords and key people, get new papers and field trends (data: OpenAlex).

화면 전환은 URL 쿼리로 한다: ?kw=...&people=... 이 있으면 결과 화면, 없으면 검색 화면.
그래서 결과 링크를 그대로 공유하거나 새로고침해도 같은 결과가 열린다. ?offline=1 은 저장본만 사용.
"""
from __future__ import annotations

import os

import streamlit as st

from core import auth as login
from core import db
from core import openalex as oa
from core import query
from core.store import flag
from ui import account, auth, dbstatus, onboarding, report, results, roadmap, search, style

st.set_page_config(page_title="Paper Radar · new papers and trends for your lab", page_icon="📡",
                   layout="wide", initial_sidebar_state="collapsed")
style.inject_css()


def api_key() -> str | None:
    try:
        key = st.secrets.get("OPENALEX_API_KEY")
    except Exception:  # secrets.toml이 없으면 예외
        key = None
    return key or os.environ.get("OPENALEX_API_KEY")


ss = st.session_state
ss.setdefault("choices", {})
qp = st.query_params
kw, people = qp.get("kw", ""), qp.get("people", "")
offline = qp.get("offline") == "1"
view = "results" if (kw.strip() or people.strip()) else "search"
if qp.get("page") in ("roadmap", "db", "me", "settings"):
    view = qp.get("page")             # me = weekly report, settings = profile form

user = auth.current_user()
if view == "search" and login.take_fresh_login():  # Streamlit always returns to "/" after login → go to My radar
    st.query_params.from_dict({"page": "me"})
    st.rerun()
if user and user["onboarded_at"] is None and view not in ("roadmap", "me"):
    view = "me"                           # first login: finish the first-login form (?page=me) before anything else
elif view == "settings" and not user:
    view = "me"                           # not logged in: My radar shows the login screen
if view == "db" and auth.configured() and not auth.is_admin(user):
    view = "search"                       # status page: admins only once login is set up


def go(new_kw: str, new_people: str) -> None:
    params = {"kw": new_kw, "people": new_people}
    if offline:
        params["offline"] = "1"
    st.query_params.from_dict(params)
    st.rerun()


if style.nav(view, user, auth.configured()):
    if view == "search":
        go(query.EXAMPLE["kw"], query.EXAMPLE["people"])
    else:
        ss.prefill = (kw, people)
        st.query_params.from_dict({"offline": "1"} if offline else {})
        st.rerun()

if view == "roadmap":
    roadmap.render()
elif view == "db":
    dbstatus.render()
elif view == "settings":
    account.profile_form(oa.OpenAlex(api_key=api_key(), offline=offline), user)
elif view == "me":
    me = onboarding.gate(oa.OpenAlex(api_key=api_key(), offline=offline))  # login screen + first-login form
    if flag("PR_DB") == "fake":           # file DB for development: there is no report data to show
        st.info("Signed in with the file DB (PR_DB=fake). Weekly reports need the real database.",
                icon=":material/info:")
    else:
        report.render(db.get_user(me["id"]))  # always the fresh users row (name, lab, email setting)
elif view == "search":
    submitted = search.render(*ss.get("prefill", ("", "")))
    if submitted:
        go(*submitted)
else:
    client = oa.OpenAlex(api_key=api_key(), offline=offline)
    with st.spinner("Scanning OpenAlex for new papers, people and trends…"):
        radar = query.run(client, kw, people, ss.choices)
    results.render(client, radar)

style.footer()

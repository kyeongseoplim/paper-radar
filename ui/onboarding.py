"""My radar(?page=me) 앞단: 로그인 화면과 첫 로그인 폼(이름, 연구실, 키워드 2~3개, 팔로우할 사람 확인).

밖에서는 gate() 한 함수만 쓴다. 통과하면 app.py 가 리포트 화면(ui/report.py)을 그린다.
나중에 고치는 화면은 Settings(ui/account.py, ?page=settings)이다. session_state·위젯 key 접두어: auth_, onb_
"""
from __future__ import annotations

import html

import streamlit as st

from core import auth, query
from core import openalex as oa
from core.store import db
from ui import auth as user_row  # 로그인한 사람의 DB 행(세션에 저장된 것). 폼 저장 뒤 다시 읽는다.
from ui import style

KW_MIN, KW_MAX = db.KW_MIN, db.KW_MAX  # DB 규칙: 키워드 2~3개

SKIP = "skip"


def gate(client: oa.OpenAlex) -> dict:
    """로그인과 첫 로그인 폼을 통과한 user를 돌려준다. 통과 전에는 해당 화면을 그리고 멈춘다."""
    if not auth.available():
        _message("Login is coming soon.", "Weekly reports for your lab are on the way. "
                 "Until then, search works without an account.")
        _stop()
    email = auth.current_email()
    if email is None:
        _login_screen()
        _stop()
    try:
        user = db.get_user(email)
    except NotImplementedError:
        _message("Almost there.", "You are signed in, but the database is not connected yet.")
        _stop()
    except Exception:  # Neon이 잠에서 깨는 중이거나 네트워크 문제
        _message("We could not reach the database.", "Please refresh the page in a minute.")
        _stop()
    if user is None:
        _onboarding(client, email)
        _stop()
    if not auth.configured():  # 실제 로그인은 위쪽 바에 Sign out 이 있다. 개발용 사용자만 표시
        _account_bar(user)
    return user


def _stop() -> None:
    style.footer()
    st.stop()


def _message(title: str, text: str) -> None:
    st.html(f'<div class="pr-soon"><b>{html.escape(title)}</b>'
            f'<p class="pr-note">{html.escape(text)}</p></div>')


def _login_screen() -> None:
    st.html(style.eyebrow("MY RADAR", dot=True)
            + '<div class="pr-h1">Log in to see your weekly radar.</div>'
            + '<p class="pr-sub">Enter your email and we send you a one-time code. No password to remember.</p>')
    st.button("Log in with email", type="primary", icon=":material/mail:", key="auth_login", on_click=auth.login)


def _account_bar(user: dict) -> None:
    left, right = st.columns([5, 1], vertical_alignment="center")
    with left:
        note = "" if auth.configured() else " · dev user (no real login)"
        st.html(f'<div class="pr-note">Signed in as <b>{html.escape(user["email"])}</b>{note}</div>')
    with right:
        if auth.configured():
            st.button("Log out", key="auth_logout", on_click=auth.logout, width="stretch")


# ---------- 첫 로그인 폼 ----------

def _onboarding(client: oa.OpenAlex, email: str) -> None:
    st.html(style.eyebrow("WELCOME", dot=True)
            + '<div class="pr-h1">Set up your radar.</div>'
            + f'<p class="pr-sub">Signed in as {html.escape(email)}. This takes about a minute.</p>')
    draft = st.session_state.get("onb_draft")
    if draft is None:
        _step_profile()
    else:
        _step_person(client, email, draft)


def _step_profile() -> None:
    """1단계: 이름, 연구실, 키워드, 팔로우할 사람 이름."""
    prev = st.session_state.get("onb_prev", {})
    with st.form("onb_form", enter_to_submit=False):
        name = st.text_input("Your name", value=prev.get("name", ""), max_chars=80)
        lab = st.text_input("Lab name", value=prev.get("lab", ""), max_chars=120,
                            placeholder="e.g. Mobile Communications Lab")
        kw = st.text_input("Keywords", value=", ".join(prev.get("keywords", [])),
                           placeholder="e.g. MAC scheduler, O-RAN",
                           help=f"{KW_MIN} to {KW_MAX} keywords, separated by commas.")
        person = st.text_input("A researcher to follow (optional)", value=prev.get("person", ""),
                               placeholder="e.g. Tommaso Melodia")
        submitted = st.form_submit_button("Next", type="primary", icon=":material/arrow_forward:",
                                          icon_position="right")
    if not submitted:
        return
    keywords = query.parse_list(kw, 99)
    people = query.parse_list(person, 1)
    problems = []
    if not name.strip():
        problems.append("Enter your name.")
    if not lab.strip():
        problems.append("Enter your lab name.")
    if len(keywords) < KW_MIN:
        problems.append(f"Add at least {KW_MIN} keywords, separated by commas.")
    elif len(keywords) > KW_MAX:
        problems.append(f"Use at most {KW_MAX} keywords.")
    if problems:
        for p in problems:
            st.error(p, icon=":material/info:")
        return
    st.session_state.onb_draft = {"name": name.strip(), "lab": lab.strip(), "keywords": keywords,
                                  "person": people[0] if people else ""}
    st.rerun()


def _step_person(client: oa.OpenAlex, email: str, draft: dict) -> None:
    """2단계: 같은 이름의 저자 후보 중 맞는 사람을 고르고 저장."""
    author = None
    if draft["person"]:
        author = _pick_author(client, draft["person"])
    st.html('<div class="pr-note" style="margin-top:14px">'
            f'<b>{html.escape(draft["name"])}</b> · {html.escape(draft["lab"])} · '
            f'Keywords: {html.escape(", ".join(draft["keywords"]))}</div>')
    _preview(client, draft)
    back, save, _ = st.columns([1, 2, 5])
    with back:
        if st.button("Back", key="onb_back", width="stretch"):
            st.session_state.onb_prev = st.session_state.pop("onb_draft")
            st.rerun()
    with save:
        if st.button("Save and continue", type="primary", key="onb_save", width="stretch"):
            try:
                db.save_profile(email, draft["name"], draft["lab"], draft["keywords"], author, sub=auth.current_sub())
            except Exception as e:  # DB 규칙 위반이나 연결 문제: 폼은 그대로 두고 알린다
                st.error(f"Could not save your profile: {e}", icon=":material/error:")
                return
            user_row.refresh()  # 저장 전 행(onboarded_at 비어 있음)이 세션에 남아 있으면 계속 이 폼으로 돌아온다
            st.session_state.pop("onb_draft", None)
            st.session_state.pop("onb_prev", None)
            st.rerun()


PREVIEW_PHRASE = {7: "the last 7 days", 30: "the last 30 days", 90: "the last 3 months"}


def _use_term(old: str, new: str) -> None:
    d = st.session_state.onb_draft
    d["keywords"] = query.parse_list(query.swap_keyword(", ".join(d["keywords"]), old, new), 99)


def _preview(client: oa.OpenAlex, draft: dict) -> None:
    """저장 전 미리보기: 주간 리포트와 같은 규칙으로 찾은 최신 논문. 엉뚱하면 Back 으로 키워드를 고친다."""
    with st.spinner("Checking the newest papers for your keywords…"):
        pv = query.preview(client, draft["keywords"])
    st.html('<div class="pr-h2" style="margin-top:18px">Preview of your weekly report</div>'
            '<p class="pr-sub">The newest papers your keywords find right now. If they look off-topic, '
            'go Back and make a keyword more specific.</p>')
    p = pv["papers"]
    if p is None:
        st.info("The preview is not available right now. You can still save and change keywords later.",
                icon=":material/info:")
    elif not p["rows"]:
        st.info(f"No papers matched all of these keywords in {PREVIEW_PHRASE[p['days']]}. "
                "Try broader keywords, or save and check your first report.", icon=":material/search_off:")
    else:
        items = "".join(
            f'<li style="margin:6px 0"><a href="{html.escape(r["link"])}" target="_blank" rel="noopener">'
            f'{html.escape(r["title"])}</a><br><span class="pr-note">'
            f'{html.escape(r["venue"] or "Venue unknown")} · {html.escape(r["date"])}</span></li>' for r in p["rows"])
        n = p["total"]
        st.html(f'<ul style="padding-left:18px;margin:6px 0">{items}</ul>'
                f'<p class="pr-note">{n:,} matching paper{"s" if n != 1 else ""} in {PREVIEW_PHRASE[p["days"]]}.</p>')
    if query.mix_text(pv["mix"]):
        st.html(f'<p class="pr-note"><b>Main field</b> of the past year\'s papers on these keywords: '
                f'{html.escape(query.mix_text(pv["mix"]))}. If that is not your field, make a keyword more specific.</p>')
    for old, news in (pv["narrower"] or {}).items():
        for new in news:
            st.button(f"Use “{new}” instead of “{old}”", key=f"onb_term|{old}|{new}", type="tertiary",
                      icon=":material/manage_search:", on_click=_use_term, args=(old, new))


def _pick_author(client: oa.OpenAlex, name: str) -> dict | None:
    try:
        match = query.match_person(client, name)
    except oa.FetchError as e:
        st.warning(f"Could not look up authors right now ({e}). You can save now and add a person later.")
        return None
    cands = match["candidates"]
    if not cands:
        st.info(f'No author found for "{name}". You can save now and add a person later.')
        return None
    by_id = {c["id"]: c for c in cands}
    options = list(by_id) + [SKIP]

    def label(option: str) -> str:
        if option == SKIP:
            return "None of these (skip for now)"
        c = by_id[option]
        return f'**{c["name"]}** · {c["inst"]}'

    # 동명이인 구별(설문: 같은 이름 중 원하는 연구자 찾기가 헷갈림): 주 연구 주제·활동 연도를 한 줄로
    captions = [oa.author_caption(by_id[o]) if o != SKIP else "" for o in options]
    st.html(f'<div class="pr-h2">Which {html.escape(name)} do you mean?</div>'
            '<p class="pr-sub">Several authors can share a name. Check the main topic and the active years, '
            'then pick the one you want to follow.</p>')
    pick = st.radio("Author", options, index=options.index(match["chosen"]["id"]), format_func=label,
                    captions=captions, key="onb_pick", label_visibility="collapsed")
    if pick == SKIP:
        return None
    c = by_id[pick]
    return {"id": c["id"], "name": c["name"], "inst": c["inst"]}

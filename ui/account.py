"""Settings page (?page=settings): the profile form, also shown on first login (onboarding).
Edits name, lab, 2-3 keywords, the followed author (with confirmation) and email on/off (roadmap Steps 2 and 4)."""
from __future__ import annotations

import streamlit as st

from core import db
from core import openalex as oa
from ui import auth, style


def _find_person(client: oa.OpenAlex) -> None:
    q = st.session_state.get("pf_person_q", "").strip()
    st.session_state.pf_cands = []
    st.session_state.pf_find_error = None
    if not q:
        return
    try:
        st.session_state.pf_cands, _ = oa.find_authors(client, q)
    except oa.FetchError as e:
        st.session_state.pf_find_error = str(e)


def profile_form(client: oa.OpenAlex, user: dict) -> None:
    """Name, lab, 2-3 keywords and one confirmed OpenAlex author. Saves everything in one transaction."""
    ss = st.session_state
    first_time = user["onboarded_at"] is None
    uid = user["id"]
    with db.connect() as conn:
        kws = db.get_keywords(uid, conn=conn)
        author = db.get_author(uid, conn=conn)

    title = "Welcome! Set up your radar" if first_time else "Edit your radar"
    sub = ("Tell us what to watch. Every week we collect new papers on your topics and from the person you follow."
           if first_time else "Changes apply from the next weekly report.")
    st.html(style.eyebrow("Profile") + f'<div class="pr-h2">{title}</div><p class="pr-sub">{sub}</p>')

    with st.container(border=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Your name", value=user["name"])
        lab = c2.text_input("Lab name", value=user["lab_name"], placeholder="e.g. Wireless Networks Lab",
                            help="Shown on your report only. Your data is never shared with other users.")

        st.markdown(f"**Keywords** ({db.MIN_KEYWORDS}–{db.MAX_KEYWORDS} topics)")
        cols = st.columns(db.MAX_KEYWORDS)
        examples = ("e.g. O-RAN", "e.g. MAC scheduler", "e.g. network slicing")
        terms = [cols[i].text_input(f"Keyword {i + 1}", value=kws[i] if i < len(kws) else "",
                                    placeholder=examples[i % 3], label_visibility="collapsed")
                 for i in range(db.MAX_KEYWORDS)]

        st.markdown("**Person to follow** (optional)")
        if author:
            st.caption(f"Currently following **{author['display_name']}** · {author['institution']}")
        q1, q2 = st.columns([4, 1], vertical_alignment="bottom")
        q1.text_input("Search OpenAlex by name", key="pf_person_q", placeholder="e.g. Tommaso Melodia",
                      on_change=_find_person, args=(client,))
        q2.button("Find", icon=":material/search:", on_click=_find_person, args=(client,), width="stretch")
        cands = ss.get("pf_cands") or []
        pick = None
        if ss.get("pf_find_error"):
            st.warning(f"Could not search OpenAlex: {ss.pf_find_error}")
        elif ss.get("pf_person_q") and not cands:
            st.info("No author found with that name. Check the spelling.")
        if cands:
            by_id = {c["id"]: c for c in cands}
            pick_id = st.radio("Which one is the right person?", list(by_id),
                               format_func=lambda i: f'{by_id[i]["name"]} · {by_id[i]["inst"]} · '
                                                     f'{by_id[i]["works"]:,} papers',
                               index=None, key="pf_pick")
            pick = by_id.get(pick_id)

        email_on = st.checkbox("Email me the weekly report", value=user["email_enabled"])

        if st.button("Save and continue" if first_time else "Save changes", type="primary",
                     icon=":material/check:"):
            if not name.strip():
                st.error("Please enter your name.")
                return
            if cands and pick is None:
                st.error("Please choose the right person from the list, or clear the search box.")
                return
            try:
                with db.connect() as conn:   # all or nothing
                    db.set_keywords(uid, terms, conn=conn)
                    if pick:
                        db.set_author(uid, pick["id"], pick["name"],
                                      "" if pick["inst"] == "Affiliation unknown" else pick["inst"], conn=conn)
                    db.update_profile(uid, name=name, lab_name=lab, email_enabled=email_on, onboarded=True,
                                      conn=conn)
            except ValueError as e:
                st.error(str(e))
                return
            for k in ("pf_cands", "pf_pick", "pf_person_q", "pf_find_error"):
                ss.pop(k, None)
            auth.refresh()
            st.query_params.from_dict({"page": "me"})
            st.rerun()

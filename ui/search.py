"""Screen 1 — hero + two-field search card (Enter or button submits)."""
from __future__ import annotations

import streamlit as st

from core import query
from ui import style


def render(prefill_kw: str = "", prefill_people: str = "") -> tuple[str, str] | None:
    """제출되면 (keywords, people) 반환, 아니면 None. 예시 버튼이면 EXAMPLE 값 반환."""
    style.hero()

    left, right = st.columns([5, 6], gap="large", vertical_alignment="center")
    with left:
        st.html(style.eyebrow("New papers + field trends, free for your lab", dot=True)
                + '<div class="pr-h1">Your research radar,<br>in one search.</div>'
                + '<p class="pr-sub">Two inputs, one page of answers: the newest papers on your topics, '
                  'what the people you follow just published, and the topics on the rise.</p>')

    submitted_values = None
    with right:
        with st.container(key="searchcard"):
            with st.form("search_form", border=False, enter_to_submit=True):
                kw = st.text_input("Keywords", value=prefill_kw, placeholder="e.g. MAC scheduler, O-RAN",
                                   icon=":material/search:")
                people = st.text_input("Key people", value=prefill_people, placeholder="e.g. Tommaso Melodia",
                                       icon=":material/person:")
                go = st.form_submit_button("Show my radar", icon=":material/arrow_forward:", icon_position="right",
                                           type="primary", width="stretch")
            if go:
                if query.parse_list(kw, 9) or query.parse_list(people, 9):
                    submitted_values = (kw, people)
                else:
                    st.error("Add at least one keyword or person.", icon=":material/info:")
        hint, ex = st.columns([3, 2], vertical_alignment="center")
        with hint:
            st.html('<div class="pr-note">✓ Separate with commas · Enter to search</div>')
        with ex:
            if st.button("Try an example", icon=":material/play_circle:", type="tertiary", key="hint_example"):
                submitted_values = (query.EXAMPLE["kw"], query.EXAMPLE["people"])

    style.how_it_works()
    return submitted_values

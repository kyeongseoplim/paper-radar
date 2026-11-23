"""Screen 2 — results: summary + KPIs, narrow panel, 01 new papers, 02 key people, 03 trends, 04 summaries (soon),
survey link. The narrow panel writes ?fields=…&exclude=… into the URL, so a narrowed radar can be shared too."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from core import openalex as oa
from core import query
from ui import style

PHRASE = {30: "the last 30 days", 90: "the last 3 months", 365: "the last 12 months"}
TITLE = {30: "This month in your field", 90: "The last 3 months in your field", 365: "The past year in your field"}
SURVEY_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdGzhG6JRkWCYVnj3MOtpUZnQpH9N330myd1wUWRK_iC81jMw/viewform"


def _people_kpi(persons) -> tuple[str, str]:
    found = [p for p in persons if p.get("chosen") and "total" in p]
    if not found:
        return "—", "Add people to follow"
    days = {p["days"] for p in found}
    when = PHRASE.get(days.pop(), "recently") if len(days) == 1 else "recently"
    return f'{sum(p["total"] for p in found):,}', f"in {when}"


def _growth_kpi(field) -> tuple[str, str]:
    if not field or not field.get("growth"):
        return "—", "Not enough data"
    g = field["growth"]
    return (f"×{g:.0f}" if g >= 10 else f"×{g:.1f}"), f'papers per year, {field["growth_from"]} → {query.TREND_YEARS[1]}'


def _header(radar) -> None:
    kws, persons = radar["keywords"], radar["persons"]
    names = [p["chosen"]["name"] for p in persons if p.get("chosen")]
    title = " × ".join(k.replace("-", "‑") for k in kws) if kws else "People you follow"  # O‑RAN 줄바꿈 방지
    bits = []
    if names:
        bits.append("Following " + ", ".join(f"<b>{html.escape(n)}</b>" for n in names))
    bits.append("Data from OpenAlex")
    st.html(style.eyebrow("YOUR RADAR", dot=True)
            + f'<div class="pr-h1">{html.escape(title)}</div>'
            + f'<p class="pr-sub">{" · ".join(bits)}</p>')

    p = radar["papers"]
    pk = (f'{p["total"]:,}', f'in {PHRASE[p["days"]]}') if p else ("—", "Add keywords to search")
    ppl = _people_kpi(persons)
    gr = _growth_kpi(radar["field"])
    st.html('<div class="pr-kpis">' + "".join(
        f'<div class="pr-kpi"><b>{v}</b><span>{label}</span><small>{small}</small></div>'
        for (v, small), label in [(pk, "New papers"), (ppl, "From people you follow"), (gr, "Field growth")])
        + "</div>")

    metas = [p["meta"]] if p else []
    metas += [x.get("meta") for x in persons]
    if radar["field"]:
        metas += radar["field"]["metas"]
    style.source_line(metas)


# ---------- 좁히기: 세부 분야, 제외 단어, 더 구체적인 키워드 ----------

def _field_names(radar) -> dict[str, str]:
    return {f["id"]: f["name"] for f in ((radar.get("mix") or {}).get("fields") or [])}


def _scope_text(radar) -> str:
    """'Only in: … · Leaving out: …' (조건이 없으면 빈 문자열)."""
    scope, names = radar["scope"], _field_names(radar)
    bits = []
    if scope.subfields:
        bits.append("Only in: " + ", ".join(html.escape(names.get(i, f"field {i}")) for i in scope.subfields))
    if scope.exclude:
        bits.append("Leaving out: " + ", ".join(html.escape(t) for t in scope.exclude))
    return " · ".join(bits)


def _set_params(**values) -> None:
    for k, v in values.items():
        if v:
            st.query_params[k] = v
        elif k in st.query_params:
            del st.query_params[k]


def _forget_widgets() -> None:
    for k in [k for k in st.session_state if str(k).startswith("refine_")]:
        del st.session_state[k]


def _apply(key_f: str, key_x: str) -> None:
    ss = st.session_state
    _set_params(fields=",".join(ss.get(key_f) or []), exclude=(ss.get(key_x) or "").strip())


def _clear() -> None:
    _set_params(fields="", exclude="")
    _forget_widgets()


def _use_term(old: str, new: str) -> None:
    st.query_params["kw"] = query.swap_keyword(st.query_params.get("kw", ""), old, new)
    _clear()


def _section_refine(radar) -> None:
    """키워드가 여러 분야에 걸치면 분야를 골라 엉뚱한 논문을 거르게 한다(설문: 키워드와 안 맞는 논문 3/11)."""
    if not radar["groups"]:
        return
    mix, scope, narrower = radar.get("mix"), radar["scope"], radar.get("narrower") or {}
    fields = (mix or {}).get("fields") or []
    if not (fields or narrower or scope):
        return
    names = _field_names(radar)
    if fields:
        msg = (f"Main field of the past year's papers on these keywords: {html.escape(query.mix_text(mix))}. "
               "Pick your field to drop off-topic papers, or leave out words.")
    else:
        msg = "You can make your keywords more specific."
    tag = st.query_params.get("kw", "")  # 새 검색이면 위젯도 새로(URL 값으로) 그린다
    key_f, key_x = f"refine_fields|{tag}", f"refine_exclude|{tag}"
    with st.container(border=True, key="refine_box"):
        st.html(style.eyebrow("NARROW YOUR RADAR") + f'<p class="pr-sub" style="margin:4px 0 0">{msg}</p>')
        for old, news in narrower.items():
            cols = st.columns([2] + [3] * len(news), vertical_alignment="center")
            cols[0].html(f'<p class="pr-note" style="margin:0">More specific than “{html.escape(old)}”:</p>')
            for col, new in zip(cols[1:], news):
                col.button(f"Search “{new}”", key=f"refine_term|{old}|{new}", type="tertiary",
                           icon=":material/manage_search:", on_click=_use_term, args=(old, new))
        if fields or scope:
            options = [f["id"] for f in fields] + [i for i in scope.subfields if i not in names]
            shares = {f["id"]: f["share"] for f in fields}
            with st.form("refine_form", border=False, enter_to_submit=True):
                st.pills("Field", options, selection_mode="multi", default=list(scope.subfields), key=key_f,
                         format_func=lambda i: (f"{names[i]} · {shares[i]:.0%}" if i in names else f"Field {i}"),
                         help="% = share of the past year's papers whose main field is this. OpenAlex tags each "
                              "paper with up to three fields and a paper stays if any tag matches, so a few more "
                              "papers than this share stay.")
                st.text_input("Leave out papers that mention", value=", ".join(scope.exclude), key=key_x,
                              placeholder="e.g. road, vehicle", help="Single words, separated by commas.")
                c1, c2, _ = st.columns([1, 1, 4])
                c1.form_submit_button("Apply", type="primary", icon=":material/filter_alt:", width="stretch",
                                      on_click=_apply, args=(key_f, key_x))
                if scope:
                    c2.form_submit_button("Clear", icon=":material/close:", width="stretch", on_click=_clear)
        if radar.get("exclude_rejected"):
            bad = ", ".join(f"“{html.escape(t)}”" for t in radar["exclude_rejected"])
            st.html(f'<p class="pr-note" style="margin:4px 0 0">Skipped {bad}: use single words (e.g. road).</p>')
        if "mix" in radar["errors"] and not fields:
            st.html('<p class="pr-note" style="margin:4px 0 0">Field choices are not available right now.</p>')


def _papers_table(rows) -> None:
    df = pd.DataFrame([{
        "Date": r["date"], "Title": r["title"],
        "Authors": ", ".join(r["authors"][:4]) + (f" +{len(r['authors']) - 4}" if len(r["authors"]) > 4 else ""),
        "Venue": r["venue"], "Publisher": r["publisher"], "Type": style.TYPE_LABEL.get(r["type"], r["type"]),
        "Citations": r["cited"], "Link": r["link"],
    } for r in rows])
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open")})
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8-sig"), file_name="paper_radar.csv",
                       mime="text/csv", icon=":material/download:")


def _section_papers(radar, stars) -> None:
    p = radar["papers"]
    days = p["days"] if p else 30
    style.section_head("01", "NEW PAPERS", TITLE[days], first=True)
    if "papers" in radar["errors"]:
        st.error(radar["errors"]["papers"], icon=":material/error:")
        return
    if not p:
        st.info("Add keywords on the search page to see new papers.", icon=":material/info:")
        return
    notes = [f'Searching titles and abstracts for: {html.escape(radar["query_text"])}']
    if radar["scope"]:
        notes.append(_scope_text(radar))
    if p["widened_from"]:
        n0 = p["first_total"]
        notes.insert(0, f'Only {n0} paper{"s" if n0 != 1 else ""} in the last {p["widened_from"]} days, '
                        f'so we widened to {PHRASE[days]}.')
    st.html("".join(f'<p class="pr-note" style="margin:2px 0">{n}</p>' for n in notes))
    if not p["rows"]:
        st.info("No papers matched, even over the last 12 months. Try fewer or broader keywords.",
                icon=":material/search_off:")
        return
    view = st.segmented_control("View", ["Cards", "Table"], default="Cards", key="view_papers",
                                label_visibility="collapsed")
    if view == "Table":
        _papers_table(p["rows"])
    else:
        style.paper_cards(p["rows"], stars)
        if p["total"] > len(p["rows"]):
            st.html(f'<p class="pr-note">Showing the {len(p["rows"])} newest of {p["total"]:,} matches.</p>')


def _pick(name: str) -> None:
    st.session_state.choices[name] = st.session_state[f"pick_{name}"]


def _section_people(radar, stars) -> None:
    style.section_head("02", "KEY PEOPLE", "From the people you follow")
    persons = radar["persons"]
    if not persons:
        st.info("Add key people on the search page to follow their new papers.", icon=":material/info:")
        return
    for p in persons:
        if p.get("error"):
            st.warning(f'Could not look up “{p["query"]}”: {p["error"]}', icon=":material/warning:")
            continue
        c = p.get("chosen")
        if not c:
            st.warning(f'No author found for “{p["query"]}”. Check the spelling.', icon=":material/person_off:")
            continue
        initials = "".join(w[0] for w in c["name"].split()[:2]).upper()
        st.html(f'<div class="pr-person"><div class="pr-avatar">{html.escape(initials)}</div><div>'
                f'<h3>{html.escape(c["name"])}</h3><p>{html.escape(c["inst"])}</p>'
                f'<p>{c["works"]:,} papers · {c["cited"]:,} citations · '
                f'<b style="color:#0F766E">{p["total"]} new</b> in {PHRASE[p["days"]]}</p></div></div>')
        if len(p["candidates"]) > 1:
            ids = [x["id"] for x in p["candidates"]]
            labels = {x["id"]: f'{x["name"]} · {x["inst"]} · {x["works"]:,} papers' for x in p["candidates"]}
            with st.popover("Not the right person?", icon=":material/swap_horiz:"):
                st.radio("We picked the author with the most papers. Choose another match:", ids,
                         index=ids.index(c["id"]), format_func=labels.get, key=f'pick_{p["query"]}',
                         on_change=_pick, args=(p["query"],))
        if p["rows"]:
            style.paper_cards(p["rows"], stars)
        else:
            st.html(f'<p class="pr-note">No new papers in {PHRASE[p["days"]]}.</p>')


def _section_trends(client, radar) -> None:
    y0, y1 = query.TREND_YEARS
    style.section_head("03", "TRENDS", f"How the field has moved since {y0}",
                       "Word size = number of papers tagged with that keyword in OpenAlex.")
    persons = [p for p in radar["persons"] if p.get("chosen")]
    options = (["Your field"] if radar["groups"] else []) + [p["chosen"]["name"] for p in persons]
    if not options:
        st.info("Add keywords or people to see trends.", icon=":material/info:")
        return
    src = st.segmented_control("Trend source", options, default=options[0], key="trend_src",
                               label_visibility="collapsed") or options[0]
    if src == "Your field":
        if "field" in radar["errors"]:
            st.error(radar["errors"]["field"], icon=":material/error:")
            return
        data = radar["field"]
        terms = ", ".join(dict.fromkeys(t for g in radar["groups"] for t in g))
        basis = f"All papers mentioning any of: {html.escape(terms)}"
        if radar["scope"]:
            basis += " · " + _scope_text(radar)
    else:
        person = next(p for p in persons if p["chosen"]["name"] == src)
        try:
            with st.spinner(f"Reading {src}'s topics…"):
                data = query.person_trend(client, person["chosen"]["id"])
        except oa.FetchError as e:
            st.error(str(e), icon=":material/error:")
            return
        basis = f"All papers by {html.escape(src)}"
    st.html(f'<p class="pr-note" style="margin:2px 0 8px">{basis} · {y0}–{y1}</p>')
    style.source_line(data["metas"])

    years = list(range(y0, y1 + 1))
    chart = pd.DataFrame({"Year": [str(y) for y in years], "Papers": [data["counts"][y] for y in years]})
    st.bar_chart(chart, x="Year", y="Papers", color=style.TEAL, height=230)

    cols = st.columns(3)
    for i, y in enumerate(years):
        with cols[i % 3]:
            st.html(f'<div class="pr-year">{y} <span>· {data["counts"][y]:,} papers</span></div>')
            if len(data["freqs"][y]) >= 3:
                st.image(style.word_cloud(data["freqs"][y]), width="stretch")
            else:
                st.html('<p class="pr-note">Not enough keywords this year.</p>')

    rise = data["rising"]
    if rise:
        top = max(r["delta"] for r in rise)
        rows = "".join(
            f'<div class="pr-rise"><div><b style="color:#17212F">{html.escape(r["keyword"])}</b><br>'
            f'<span class="pr-note">{r["base"]:.1%} → {r["recent"]:.1%}</span></div>'
            f'<div class="bar"><i style="width:{max(4, r["delta"] / top * 100):.0f}%"></i></div>'
            f'<b>+{r["delta"] * 100:.1f} pp</b></div>' for r in rise)
        st.html(f'<div style="margin-top:22px">{style.eyebrow("RISING TOPICS")}'
                f'<p class="pr-sub">Share of papers tagged with each keyword, {rise[0]["base_label"]} → '
                f'{rise[0]["recent_label"]}</p>{rows}</div>')


def _section_summaries() -> None:
    style.section_head("04", "SUMMARIES", "AI summaries — coming soon",
                       "The next version turns this radar into a weekly briefing for your lab.")
    st.html('<div class="pr-soon"><div class="pr-steps">'
            '<div><b>1</b>Pick papers worth reading</div><div><b>2</b>AI writes a 3-line summary</div>'
            '<div><b>3</b>You approve it</div><div><b>4</b>Sent weekly to Telegram or email</div>'
            '</div></div>')


def _feedback() -> None:
    """결과 화면 맨 아래: 만족도 설문(구글 폼) 안내."""
    st.html('<div class="pr-section"><div class="pr-soon" style="display:flex;flex-wrap:wrap;gap:14px 24px;'
            'align-items:center;justify-content:space-between;background:var(--soft);border-style:solid;'
            'border-color:#99F6E4"><div><b style="color:var(--ink);font-size:16px">Help us make Paper Radar better</b>'
            '<p class="pr-sub" style="margin:4px 0 0">To help us improve the service, we would appreciate it if you '
            'could fill out our short satisfaction survey (Google Form).</p></div>'
            f'<a href="{SURVEY_URL}" target="_blank" rel="noopener" style="background:var(--teal);'
            'color:#fff !important;text-decoration:none !important;border-radius:10px;padding:10px 18px;'
            'font-weight:700;font-size:14px;white-space:nowrap">Take the survey ↗</a></div></div>')


def render(client: oa.OpenAlex, radar: dict) -> None:
    stars = {oa.norm_name(p["chosen"]["name"]) for p in radar["persons"] if p.get("chosen")}
    _header(radar)
    _section_refine(radar)
    _section_papers(radar, stars)
    _section_people(radar, stars)
    _section_trends(client, radar)
    _section_summaries()
    _feedback()

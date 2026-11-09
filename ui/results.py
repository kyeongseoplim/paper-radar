"""Screen 2 — results: summary + KPIs, 01 new papers, 02 key people, 03 trends, 04 summaries (soon)."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from core import openalex as oa
from core import query
from ui import style

PHRASE = {30: "the last 30 days", 90: "the last 3 months", 365: "the last 12 months"}
TITLE = {30: "This month in your field", 90: "The last 3 months in your field", 365: "The past year in your field"}


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


def render(client: oa.OpenAlex, radar: dict) -> None:
    stars = {oa.norm_name(p["chosen"]["name"]) for p in radar["persons"] if p.get("chosen")}
    _header(radar)
    _section_papers(radar, stars)
    _section_people(radar, stars)
    _section_trends(client, radar)
    _section_summaries()

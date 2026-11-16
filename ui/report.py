"""Report page (?page=me): the logged-in user's saved weekly report, with a picker for past weeks.
Roadmap Step 8. Reads only the database (no OpenAlex calls on page load); the reports are written by the
n8n weekly workflow (data format: blueprint.md, "Notation")."""
from __future__ import annotations

import html
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from core import db
from core import openalex as oa
from ui import style


def _days(n: int) -> str:
    return {7: "the last 7 days", 30: "the last 30 days", 90: "the last 3 months"}.get(n, f"the last {n} days")


def _header(user: dict, kws: list[str], author: dict | None) -> None:
    lab = f' · {html.escape(user["lab_name"])}' if user["lab_name"] else ""
    follow = f' · following <b>{html.escape(author["display_name"])}</b>' if author else ""
    st.html(style.eyebrow("YOUR WEEKLY RADAR", dot=True)
            + f'<div class="pr-h1">Hi, {html.escape(user["name"] or user["email"])}</div>'
            + f'<p class="pr-sub">{html.escape(" · ".join(kws))}{follow}{lab} · weekly email '
              f'{"on" if user["email_enabled"] else "off"} · <a href="?page=settings" target="_self">Settings</a></p>')


def _kpis(d: dict) -> None:
    p, a, t = d.get("papers"), d.get("author"), d.get("trends")
    up = [k for k in (t["keywords"] if t else []) if k["this_week"] > k["avg4"]]
    tiles = [
        (f'{len(p["rows"])}' if p else "—", "New papers", f'in {_days(p["days"])}' if p else "not available"),
        (f'{len(a["rows"])}' if a else "—", "From the person you follow",
         f'{a["name"]} · {_days(a["days"])}' if a else "nobody followed"),
        (f'{len(up)}/{len(t["keywords"])}' if t else "—", "Keywords up this week", "vs. their 4-week average"),
    ]
    st.html('<div class="pr-kpis">' + "".join(
        f'<div class="pr-kpi"><b>{v}</b><span>{html.escape(label)}</span><small>{html.escape(small)}</small></div>'
        for v, label, small in tiles) + "</div>")


def _papers(d: dict, stars: set[str]) -> None:
    p = d.get("papers")
    style.section_head("01", "NEW PAPERS", f'New on your topics in {_days(p["days"]) if p else "the last 7 days"}', first=True)
    if "papers" in d["errors"]:
        st.warning(f'New papers could not be fetched this week: {d["errors"]["papers"]}', icon=":material/warning:")
    if not p:
        return
    notes = [f'Searching titles and abstracts for: {html.escape(d["query_text"])}']
    if p["widened_from"]:
        notes.insert(0, f'Too few new papers in the last {p["widened_from"]} days, so we widened to {_days(p["days"])}.')
    if p["skipped_seen"]:
        notes.append(f'{p["skipped_seen"]} paper{"s" if p["skipped_seen"] != 1 else ""} from earlier reports left out.')
    st.html("".join(f'<p class="pr-note" style="margin:2px 0">{n}</p>' for n in notes))
    if p["rows"]:
        style.paper_cards(p["rows"], stars)
    else:
        st.info("No new papers matched this week.", icon=":material/search_off:")


def _author(d: dict, stars: set[str]) -> None:
    a = d.get("author")
    style.section_head("02", "KEY PERSON", f'From {a["name"]}' if a else "From the person you follow")
    if "author" in d["errors"]:
        st.warning(f'Papers of the person you follow could not be fetched: {d["errors"]["author"]}',
                   icon=":material/warning:")
    if not a:
        if "author" not in d["errors"]:
            st.info("Follow a person in Settings to see their new papers here.", icon=":material/person_add:")
        return
    st.html(f'<p class="pr-note">{html.escape(a["inst"] or "Affiliation unknown")} · '
            f'{a["total"]} paper{"s" if a["total"] != 1 else ""} in {_days(a["days"])}</p>')
    if a["rows"]:
        style.paper_cards(a["rows"], stars)
    else:
        st.html(f'<p class="pr-note">No new papers in {_days(a["days"])}.</p>')


def _trends(d: dict, author: dict | None) -> None:
    style.section_head("03", "TRENDS", "This week vs. the 4-week average",
                       "Papers published in the 7 days before the report, per keyword. Recent weeks are "
                       "undercounted a little because OpenAlex indexes new papers with a delay.")
    t = d.get("trends")
    if "trends" in d["errors"]:
        st.warning(f'Trends could not be computed this week: {d["errors"]["trends"]}', icon=":material/warning:")
    if t:
        chart = pd.DataFrame([{"Keyword": k["term"], "Period": p, "Papers": v}
                              for k in t["keywords"] for p, v in (("This week", k["this_week"]),
                                                                  ("4-week average", k["avg4"]))])
        st.bar_chart(chart, x="Keyword", y="Papers", color="Period", stack=False, height=260)
        if t["new_topics"]:
            chips = "".join(f'<span class="pr-chip on">{html.escape(x["keyword"])} · {x["count"]}</span>'
                            for x in t["new_topics"])
            st.html(f'{style.eyebrow("NEW THIS WEEK")}<p class="pr-sub">Topics tagged this week that did not '
                    f'appear in the 4 weeks before</p>{chips}')
    params = urlencode({"kw": ", ".join(d["keywords"]), "people": author["display_name"] if author else ""})
    st.html(f'<p class="pr-note" style="margin-top:14px"><a href="?{params}" target="_self">'
            f'See yearly trends since 2020 on the live search →</a></p>')


def render(user: dict) -> None:
    uid = user["id"]
    with db.connect() as conn:
        kws = db.get_keywords(uid, conn=conn)
        author = db.get_author(uid, conn=conn)
        weeks = db.list_reports(uid, conn=conn)
    _header(user, kws, author)
    if not weeks:
        st.info("Your first weekly report will appear here after the next weekly run (Mondays, 07:00 KST).",
                icon=":material/schedule:")
        return
    week = st.selectbox("Week", [w["week_start"] for w in weeks], format_func=lambda w: f"Week of {w:%d %b %Y}",
                        label_visibility="collapsed", width=260)
    d = db.get_report(uid, week)["data"]
    if d.get("summary"):
        st.html(f'<div class="pr-soon" style="background:#F0FDFA;border-style:solid;border-color:#99D5CF">'
                f'{style.eyebrow("SUMMARY")}<p style="margin:0;color:#17212F;line-height:1.6">'
                f'{html.escape(d["summary"])}</p></div>')
    _kpis(d)
    stars = {oa.norm_name(author["display_name"])} if author else set()
    _papers(d, stars)
    _author(d, stars)
    _trends(d, author)

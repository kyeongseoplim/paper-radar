"""Look & feel: CSS, nav, section headers, cards, word clouds. Agent1000-like tokens."""
from __future__ import annotations

import datetime as dt
import html
import random
from urllib.parse import quote, urlencode

import streamlit as st
from wordcloud import WordCloud

from core import query

TEAL = "#0F766E"
INK = "#17212F"

TYPE_LABEL = {"article": "Journal", "preprint": "Preprint", "conference-paper": "Conference",
              "review": "Review", "dissertation": "Thesis", "book-chapter": "Book chapter",
              "book": "Book", "report": "Report"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&display=swap');
:root{--teal:#0F766E;--teal-d:#115E59;--ink:#17212F;--ink2:#334155;--muted:#64748B;
      --line:#E2E8F0;--line2:#CBD5E1;--soft:#F0FDFA;--shadow:0 4px 16px rgba(23,33,47,.04);}
[data-testid="stHeader"]{display:none;}
[data-testid="stMainBlockContainer"]{max-width:1120px;padding-top:1.1rem;padding-bottom:3rem;}
a{color:var(--teal);}

/* nav */
.st-key-nav{border-bottom:1px solid var(--line);padding:2px 0 14px;margin-bottom:10px;}
.pr-logo{font-family:'Cormorant Garamond',Georgia,serif;font-size:29px;letter-spacing:.09em;color:#1A1A2E;
         line-height:1;white-space:nowrap;}
.pr-logo a{color:inherit !important;text-decoration:none !important;}
.pr-logo span{color:var(--teal);}
.pr-links{display:flex;gap:28px;justify-content:center;white-space:nowrap;}
.pr-links a{color:var(--ink2) !important;text-decoration:none !important;font-weight:500;font-size:15px;}
.pr-links a:hover{color:var(--teal) !important;}

/* hero */
.pr-hero{position:relative;overflow:hidden;border-radius:18px;min-height:280px;padding:44px 48px;
         background:linear-gradient(120deg,#0B3B38 0%,#0F766E 58%,#14B8A6 100%);color:#fff;
         display:flex;align-items:flex-end;margin:6px 0 34px;}
.pr-hero h1{color:#fff !important;font-size:44px !important;font-weight:780 !important;line-height:1.15 !important;
            margin:0 !important;padding:0 !important;max-width:60%;letter-spacing:-.01em;}
.pr-hero p{color:rgba(255,255,255,.82);font-size:16px;margin:12px 0 0;max-width:52%;}
.pr-hero svg{position:absolute;right:-30px;top:50%;transform:translateY(-50%);width:430px;height:430px;opacity:.95;}

/* eyebrow + headings */
.pr-eyebrow{color:var(--teal);font-size:13px;font-weight:700;letter-spacing:.04em;margin-bottom:8px;}
.pr-eyebrow.dot::before{content:"●";margin-right:8px;font-size:10px;vertical-align:2px;}
.pr-h1{font-size:32px;font-weight:770;line-height:1.25;color:var(--ink);margin:0 0 10px;letter-spacing:-.01em;}
.pr-h2{font-size:27px;font-weight:750;line-height:1.3;color:var(--ink);margin:0 0 6px;letter-spacing:-.01em;}
.pr-sub{color:var(--muted);font-size:15px;line-height:1.6;margin:0 0 6px;}
.pr-note{color:var(--muted);font-size:13px;}
.pr-section{margin-top:46px;padding-top:30px;border-top:1px solid var(--line);}

/* search card */
.st-key-searchcard{border:1px solid var(--line2);border-radius:14px;box-shadow:var(--shadow);
                   padding:14px 16px 6px;background:#fff;}
.st-key-searchcard label p{font-weight:650;font-size:13px;color:var(--ink2);}
.st-key-searchcard [data-testid^="stBaseButton-primary"]{min-height:48px;font-weight:700;}

/* cards */
.pr-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:18px;}
.pr-frame{border:1px solid var(--line);border-radius:14px;background:#fff;overflow:hidden;box-shadow:var(--shadow);}
.pr-frame-bar{background:#F8FAFC;border-bottom:1px solid var(--line);padding:8px 12px;font-size:11px;color:#94A3B8;
              display:flex;align-items:center;gap:6px;}
.pr-frame-bar i{width:7px;height:7px;border-radius:50%;background:#CBD5E1;display:inline-block;}
.pr-frame-bar span{flex:1;text-align:center;margin-right:26px;}
.pr-frame-body{padding:18px;min-height:120px;background:linear-gradient(180deg,#fff,#F8FAFC);}
.pr-frame-foot{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-top:1px solid var(--line);
               font-weight:700;color:var(--ink);}
.pr-frame-foot em{font-style:normal;color:#94A3B8;font-weight:500;margin-right:10px;}
.pr-mock-input{border:1px solid var(--line2);border-radius:10px;padding:9px 12px;color:var(--ink2);font-size:13px;background:#fff;margin-bottom:8px;}
.pr-mock-btn{background:var(--teal);color:#fff;border-radius:8px;text-align:center;padding:8px;font-size:12px;font-weight:700;}
.pr-chip{display:inline-block;border:1px solid var(--line2);border-radius:999px;padding:5px 11px;font-size:12px;color:var(--ink2);
         background:#fff;margin:0 6px 6px 0;}
.pr-chip.on{border-color:var(--teal);color:var(--teal);background:var(--soft);font-weight:650;}
.pr-bars{display:flex;align-items:flex-end;gap:7px;height:84px;}
.pr-bars div{flex:1;background:var(--teal);border-radius:4px 4px 0 0;opacity:.85;}

.pr-kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:22px 0 4px;}
.pr-kpi{border:1px solid var(--line);border-radius:14px;padding:16px 18px;background:#fff;box-shadow:var(--shadow);}
.pr-kpi b{display:block;font-size:34px;font-weight:780;color:var(--ink);line-height:1.1;}
.pr-kpi span{display:block;font-weight:650;color:var(--ink2);font-size:14px;margin-top:4px;}
.pr-kpi small{color:var(--muted);font-size:12px;}

.pr-paper{border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-bottom:12px;background:#fff;
          box-shadow:0 2px 6px rgba(23,37,44,.025);}
.pr-paper:hover{border-color:#99D5CF;}
.pr-top{display:flex;gap:10px;align-items:center;margin-bottom:6px;font-size:12.5px;color:var(--muted);}
.pr-badge{background:var(--soft);color:var(--teal);border-radius:999px;padding:2px 9px;font-weight:650;font-size:12px;}
a.pr-title{display:block;color:var(--ink) !important;font-weight:700;font-size:16.5px;line-height:1.4;
           text-decoration:none !important;margin-bottom:6px;}
a.pr-title:hover{color:var(--teal) !important;}
.pr-meta{color:var(--muted);font-size:13px;margin-bottom:6px;}
.pr-authors{color:var(--ink2);font-size:14px;}
.pr-star{color:var(--teal);font-weight:700;}

.pr-person{display:flex;gap:16px;align-items:center;border:1px solid var(--line);border-radius:14px;padding:16px 18px;
           background:#fff;box-shadow:var(--shadow);margin:14px 0 12px;}
.pr-avatar{width:52px;height:52px;border-radius:50%;background:var(--soft);color:var(--teal);font-weight:800;font-size:18px;
           display:flex;align-items:center;justify-content:center;flex:none;}
.pr-person h3{font-size:19px !important;font-weight:750 !important;margin:0 !important;padding:0 !important;color:var(--ink) !important;}
.pr-person p{margin:2px 0 0;color:var(--muted);font-size:13.5px;}

.pr-rise{display:grid;grid-template-columns:1fr 2fr 80px;gap:12px;align-items:center;padding:9px 0;
         border-bottom:1px solid var(--line);font-size:14px;color:var(--ink2);}
.pr-rise .bar{height:8px;border-radius:999px;background:#E2E8F0;position:relative;overflow:hidden;}
.pr-rise .bar i{position:absolute;left:0;top:0;bottom:0;background:var(--teal);border-radius:999px;}
.pr-rise b{color:var(--teal);text-align:right;}
.pr-year{font-weight:700;color:var(--ink);font-size:14px;margin:6px 0 2px;}
.pr-year span{color:var(--muted);font-weight:500;}

.pr-soon{border:1px dashed var(--line2);border-radius:14px;padding:22px;background:#F8FAFC;}
.pr-steps{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px;}
.pr-steps div{background:#fff;border:1px solid var(--line);border-radius:10px;padding:9px 13px;font-size:13.5px;color:var(--ink2);}
.pr-steps div b{color:var(--teal);margin-right:6px;}
.pr-footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:13px;
           display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;}
.pr-source{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;color:var(--muted);}
.pr-source i{width:8px;height:8px;border-radius:50%;display:inline-block;}

@media (max-width: 760px){
  .pr-hero{padding:28px 24px;min-height:240px;}
  .pr-hero h1{font-size:32px !important;max-width:100%;}
  .pr-hero p{max-width:100%;}
  .pr-hero svg{opacity:.25;right:-120px;}
  .pr-grid,.pr-kpis{grid-template-columns:1fr;}
  .pr-links{display:none;}
  .pr-rise{grid-template-columns:1fr 1fr 64px;}
}
</style>
"""

RADAR_SVG = """
<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg" width="400" height="400">
  <defs><radialGradient id="sw" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse"
     gradientTransform="translate(200 200) scale(190)"><stop offset="0" stop-color="#5EEAD4" stop-opacity=".55"/>
     <stop offset="1" stop-color="#5EEAD4" stop-opacity="0"/></radialGradient></defs>
  <g fill="none" stroke="rgba(255,255,255,.28)" stroke-width="1.2">
    <circle cx="200" cy="200" r="60"/><circle cx="200" cy="200" r="110"/><circle cx="200" cy="200" r="160"/>
    <line x1="200" y1="20" x2="200" y2="380"/><line x1="20" y1="200" x2="380" y2="200"/></g>
  <path d="M200 200 L200 30 A170 170 0 0 1 347 115 Z" fill="url(#sw)"/>
  <g fill="#fff"><circle cx="262" cy="96" r="5"/><circle cx="305" cy="160" r="3.5" opacity=".8"/>
    <circle cx="150" cy="122" r="3" opacity=".6"/><circle cx="246" cy="270" r="4" opacity=".7"/>
    <circle cx="118" cy="244" r="3" opacity=".5"/><circle cx="330" cy="230" r="2.5" opacity=".6"/></g>
  <circle cx="262" cy="96" r="12" fill="none" stroke="#fff" stroke-opacity=".6"/>
</svg>"""


def _hero_bg_css() -> str:
    """st.html은 <svg>를 지우므로 레이더 그림을 CSS 배경(data URI)으로 넣는다."""
    uri = "data:image/svg+xml," + quote(" ".join(RADAR_SVG.split()))
    grad = "linear-gradient(120deg,#0B3B38 0%,#0F766E 58%,#14B8A6 100%)"
    return (f'<style>.pr-hero{{background:url("{uri}") right -30px center/430px 430px no-repeat,{grad};}}'
            f'@media (max-width:760px){{.pr-hero{{background:url("{uri}") right -190px center/380px 380px no-repeat,{grad};}}}}'
            f'</style>')


def inject_css() -> None:
    st.html(CSS)
    st.html(_hero_bg_css())


def example_href() -> str:
    return "?" + urlencode(query.EXAMPLE)


def nav(view: str) -> bool:
    """상단 바. 오른쪽 버튼이 눌리면 True."""
    with st.container(key="nav", horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
        st.html('<div class="pr-logo"><a href="./" target="_self">PAPER<span>RADAR</span></a></div>', width="content")
        st.html(f'<div class="pr-links"><a href="#how-it-works" target="_self">How it works</a>'
                f'<a href="{example_href()}" target="_self">Sample radar</a></div>', width="content")
        if view == "search":
            return st.button("Try an example", icon=":material/arrow_forward:", icon_position="right",
                             type="primary", key="nav_example")
        return st.button("New search", icon=":material/arrow_back:", key="nav_new")


def hero() -> None:
    st.html("""<div class="pr-hero">
      <div><h1>Never miss a paper<br>in your field.</h1>
      <p>Type the topics you care about and the people you follow. See what is new this month
      and how the field has shifted since 2020.</p></div></div>""")


def eyebrow(text: str, dot: bool = False, anchor: str | None = None) -> str:
    aid = f' id="{anchor}"' if anchor else ""
    return f'<div class="pr-eyebrow{" dot" if dot else ""}"{aid}>{html.escape(text)}</div>'


def section_head(num: str, label: str, title: str, sub: str | None = None, first: bool = False) -> None:
    sub_html = f'<p class="pr-sub">{sub}</p>' if sub else ""
    st.html(f'<div class="{"" if first else "pr-section"}">{eyebrow(f"{num} · {label}")}'
            f'<div class="pr-h2">{html.escape(title)}</div>{sub_html}</div>')


def how_it_works() -> None:
    def frame(num, title, body):
        return (f'<div class="pr-frame"><div class="pr-frame-bar"><i></i><i></i><i></i><span>paper-radar</span></div>'
                f'<div class="pr-frame-body">{body}</div>'
                f'<div class="pr-frame-foot"><div><em>{num}</em>{title}</div><div>↗</div></div></div>')

    cards = [
        frame("01", "Type your topics",
              '<div class="pr-mock-input">MAC scheduler, O-RAN</div><div class="pr-mock-btn">Show my radar →</div>'),
        frame("02", "Add people you follow",
              '<span class="pr-chip on">Tommaso Melodia</span><span class="pr-chip">+ add a name</span>'
              '<p class="pr-note" style="margin-top:8px">We match the right author for you.</p>'),
        frame("03", "Get papers and trends",
              '<div class="pr-bars">' + "".join(f'<div style="height:{h}%"></div>' for h in (12, 22, 34, 48, 70, 100))
              + "</div>"),
    ]
    st.html(f'<div class="pr-section">{eyebrow("HOW IT WORKS", anchor="how-it-works")}'
            f'<div class="pr-h2">Three steps to your radar</div>'
            f'<p class="pr-sub">No sign-up. Results come from OpenAlex, an open index of 250M+ scholarly works.</p>'
            f'<div class="pr-grid">{"".join(cards)}</div></div>')


def fmt_date(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.strftime('%b')} {d.day}, {d.year}"  # Windows strftime에는 %-d가 없어 직접 조립


def paper_cards(rows: list[dict], stars: set[str]) -> None:
    from core.openalex import norm_name
    out = []
    for r in rows:
        names = r["authors"]
        shown = []
        for a in names[:6]:
            a_html = html.escape(a)
            shown.append(f'<span class="pr-star">★ {a_html}</span>' if norm_name(a) in stars else a_html)
        more = f" … +{len(names) - 6}" if len(names) > 6 else ""
        venue = html.escape(r["venue"] or "Venue unknown")
        cites = f'{r["cited"]:,} citation{"s" if r["cited"] != 1 else ""}'
        out.append(
            f'<div class="pr-paper"><div class="pr-top"><span class="pr-badge">'
            f'{TYPE_LABEL.get(r["type"], r["type"].title() or "Paper")}</span>{fmt_date(r["date"])}</div>'
            f'<a class="pr-title" href="{html.escape(r["link"], quote=True)}" target="_blank" rel="noopener">'
            f'{html.escape(r["title"])} ↗</a>'
            f'<div class="pr-meta">{venue} · {cites}</div>'
            f'<div class="pr-authors">{", ".join(shown) or "Authors unknown"}{more}</div></div>')
    st.markdown("".join(out), unsafe_allow_html=True)


def source_line(metas) -> None:
    metas = [m for m in metas if m]
    if not metas:
        return
    order = {"live": 0, "cache": 1, "stale": 2}
    worst = max(metas, key=lambda m: order[m["source"]])
    t = dt.datetime.fromisoformat(min(m["saved_at"] for m in metas))
    when = f"{t.strftime('%b')} {t.day}, {t.strftime('%H:%M')}"
    text, color = {
        "live": (f"Live from OpenAlex · {when}", "#16A34A"),
        "cache": (f"Saved result from {when}", "#0EA5E9"),
        "stale": (f"OpenAlex is busy — showing the saved result from {when}", "#F59E0B"),
    }[worst["source"]]
    st.html(f'<div class="pr-source"><i style="background:{color}"></i>{text}</div>')


_PALETTE = ["#0F766E", "#115E59", "#134E4A", "#0D9488", "#14B8A6", "#334155", "#475569", "#64748B"]


def _cloud_font() -> str | None:
    """wordcloud의 기본 글꼴은 고정폭이라, matplotlib에 들어 있는 DejaVu Sans Bold를 쓴다(클라우드에도 있음)."""
    try:
        from matplotlib import font_manager
        return font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight="bold"),
                                     fallback_to_default=True)
    except Exception:
        return None


def word_cloud(freq: dict):
    rnd = random.Random(7)
    wc = WordCloud(width=900, height=520, background_color="white", max_words=70, prefer_horizontal=0.95,
                   random_state=7, margin=6, font_path=_cloud_font(),
                   color_func=lambda *a, **k: rnd.choice(_PALETTE))
    return wc.generate_from_frequencies(freq).to_array()


def footer() -> None:
    st.html('<div class="pr-footer"><div><b style="color:#17212F">PAPER RADAR</b> · Data from '
            '<a href="https://openalex.org" target="_blank">OpenAlex</a> (CC0)</div>'
            '<div>Course project · Kyung Hee University · Demo</div></div>')

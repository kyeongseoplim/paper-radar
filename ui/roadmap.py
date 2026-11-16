"""Screen 3 — About + roadmap (?page=roadmap). Static content; no API calls."""
from __future__ import annotations

import html

import streamlit as st

from ui import style

CSS = """<style>
.pr-about{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:18px;}
.pr-about div{border:1px solid var(--line);border-radius:14px;padding:16px 18px;background:#fff;box-shadow:var(--shadow);}
.pr-about b{display:block;color:var(--ink);font-size:15px;margin-bottom:4px;}
.pr-about p{margin:0;color:var(--muted);font-size:13.5px;line-height:1.55;}
.pr-tl{position:relative;margin-top:22px;padding-left:28px;}
.pr-tl::before{content:"";position:absolute;left:8px;top:6px;bottom:6px;width:2px;background:var(--line);}
.pr-ms{position:relative;border:1px solid var(--line);border-radius:14px;padding:16px 18px;background:#fff;
       box-shadow:var(--shadow);margin-bottom:14px;}
.pr-ms::before{content:"";position:absolute;left:-26px;top:20px;width:14px;height:14px;border-radius:50%;
               background:#fff;border:3px solid var(--line2);}
.pr-ms.done::before{background:var(--teal);border-color:var(--teal);}
.pr-ms.next::before{border-color:var(--teal);}
.pr-ms.soon{border-style:dashed;background:#F8FAFC;}
.pr-ms-top{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:4px;}
.pr-ms-top h4{margin:0 !important;padding:0 !important;font-size:17px !important;font-weight:740 !important;color:var(--ink) !important;}
.pr-tag{border-radius:999px;padding:2px 10px;font-size:12px;font-weight:650;}
.pr-tag.done{background:var(--soft);color:var(--teal);}
.pr-tag.next{background:#FEF3C7;color:#92400E;}
.pr-tag.soon{background:#EEF2F7;color:var(--ink2);}
.pr-ms p{margin:2px 0 8px;color:var(--muted);font-size:14px;line-height:1.55;}
.pr-ms ul{margin:0;padding-left:18px;color:var(--ink2);font-size:13.5px;line-height:1.65;}
@media (max-width:760px){.pr-about{grid-template-columns:1fr;}}
</style>"""

ABOUT = [
    ("What it is", "A free research radar for labs: type topics and people you follow, get the newest papers, "
                   "their latest work, and how the field has moved since 2020."),
    ("Where the data comes from", "OpenAlex, an open (CC0) index of 250M+ scholarly works. Results are cached, "
                                  "so saved searches still open offline."),
    ("Who builds it", "A course project at Kyung Hee University (Fall 2026). Built with Streamlit; "
                      "the source is on GitHub."),
]

# (status, label, title, summary, bullet points)
MILESTONES = [
    ("done", "Shipped", "v0.1 · Demo", "The radar you can use today.", [
        "01 New papers — last 30 days, AND across keywords, synonyms expanded, window widens to 90 / 365 days",
        "02 Key people — up to 3 authors, automatic name matching with a “Not the right person?” switch",
        "03 Trends — papers per year, yearly word clouds and rising topics since 2020",
        "Card / table view with CSV export, shareable result links, offline mode and saved demo results",
    ]),
    ("next", "In progress", "arXiv as a second source", "More preprints in 01 New papers, merged with OpenAlex.", [
        "Fetch arXiv alongside OpenAlex with the same cache, retry and offline behaviour",
        "Remove duplicates by title or DOI; papers found in both sources are kept once",
        "Rank by freshness, source and citations, then show newest first",
        "Covers papers whose abstracts are missing in OpenAlex",
    ]),
    ("soon", "Planned", "04 · AI summaries & weekly digest", "Stay updated without opening the app.", [
        "Pick papers → AI writes a 3-line summary → you approve it",
        "Approved summaries are sent weekly by Telegram or email",
    ]),
    ("soon", "Planned", "Better matching & trends", "Fixes for today's known limitations.", [
        "Smarter author matching than “most papers wins” for shared names",
        "Fairer rising-topic scores for words that were rare in early years",
    ]),
]


def render() -> None:
    st.html(CSS)
    about = "".join(f"<div><b>{html.escape(t)}</b><p>{html.escape(d)}</p></div>" for t, d in ABOUT)
    st.html(f'<div>{style.eyebrow("ABOUT PAPER RADAR", dot=True)}'
            f'<div class="pr-h1">Built for labs that read<br>the newest papers first.</div>'
            f'<p class="pr-sub">What the project is, what works today, and what is on the way.</p>'
            f'<div class="pr-about">{about}</div></div>')

    items = []
    for status, label, title, summary, points in MILESTONES:
        lis = "".join(f"<li>{html.escape(p)}</li>" for p in points)
        items.append(f'<div class="pr-ms {status}"><div class="pr-ms-top"><h4>{html.escape(title)}</h4>'
                     f'<span class="pr-tag {status}">{label}</span></div>'
                     f'<p>{html.escape(summary)}</p><ul>{lis}</ul></div>')
    st.html(f'<div class="pr-section">{style.eyebrow("ROADMAP")}'
            f'<div class="pr-h2">What is shipped and what is coming</div>'
            f'<p class="pr-sub">Plans can change as we test with real users.</p>'
            f'<div class="pr-tl">{"".join(items)}</div></div>')

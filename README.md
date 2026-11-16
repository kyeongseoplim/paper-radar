# 📡 Paper Radar

**Never miss a paper in your field.**
Type the topics you care about and the people you follow, press Enter, and get the newest papers,
their latest work, and how the field has moved since 2020 — all on one page.

- **Live demo:** https://paper-radar-khu.streamlit.app
- **Sample radar:** [MAC scheduler, O-RAN · Tommaso Melodia](https://paper-radar-khu.streamlit.app/?kw=MAC+scheduler%2C+O-RAN&people=Tommaso+Melodia)
- **About & roadmap:** https://paper-radar-khu.streamlit.app/?page=roadmap

Data comes from [OpenAlex](https://openalex.org), an open (CC0) index of scholarly works.
A course project at Kyung Hee University (Fall 2026).

---

## Features

| Section | What you get |
|---|---|
| **01 New papers** | The newest papers whose title or abstract matches your keywords. If there are fewer than 3 in the last 30 days, the window widens to 90 and then 365 days, and the page tells you so. Card or table view, CSV export. |
| **02 Key people** | Recent papers by the people you follow (up to 3). The best-matching author is picked automatically; use **“Not the right person?”** to switch to another author with the same name. Their names are starred (★) in every author list. |
| **03 Trends** | Papers per year, yearly word clouds and rising topics since 2020 — for your whole field or for one person’s research. |
| **04 Summaries** | *Coming soon:* AI summaries sent as a weekly digest after your approval. |

## Search rules

| Input | How it is used |
|---|---|
| **Keywords** | Separate with commas. **Each comma-separated keyword is required (AND).** Common synonyms are added automatically (OR), e.g. *O-RAN = Open RAN = open radio access network*, *scheduler = scheduling*. The list lives in `SYNONYMS` in `core/query.py`. |
| **Time window** | Last 30 days → 90 days → 365 days, widening only when fewer than 3 papers match. |
| **Key people** | Separate with commas (up to 3). The author with the most papers is chosen by default; you can switch on the results page. |
| **Trends** | Papers that mention **any** of your keywords (OR), so each year has enough words. Your own search terms are removed from the word clouds. |

## Shareable links

Every search lives in the URL, so a results link can be shared or refreshed:

| Parameter | Example | Meaning |
|---|---|---|
| `kw` | `?kw=MAC+scheduler%2C+O-RAN` | Keywords |
| `people` | `&people=Tommaso+Melodia` | Key people |
| `offline` | `&offline=1` | Use saved results only (no live API calls) |
| `page` | `?page=roadmap` | About & roadmap page |

A small dot under each section shows where the data came from:
🟢 live from OpenAlex · 🔵 saved result · 🟠 OpenAlex was busy, so a saved result is shown.

## Run locally

Requires Python 3.12 or newer.

```bash
python -m venv .venv
```

Install the dependencies (Windows):

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

Install the dependencies (macOS / Linux):

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Start the app **from this folder** (so the theme and secrets are picked up), then open http://localhost:8501:

```bash
.venv\Scripts\python -m streamlit run app.py
```

On macOS / Linux use `.venv/bin/python` instead of `.venv\Scripts\python`.

### OpenAlex API key (recommended)

Without a key, everyone on the same network shares a small daily quota and requests start failing with HTTP 429.
A free key (about $1 of requests per day — plenty for this app) is available at https://openalex.org/settings/api.

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
2. Put your key in it:
   ```toml
   OPENALEX_API_KEY = "your-key"
   ```
3. Never commit `secrets.toml` — it is already listed in `.gitignore`.

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub (include the `seed_cache/` folder).
2. Go to https://share.streamlit.io → **Create app** → choose this repository, branch `main`, file `app.py`.
3. Pick an **App URL** (for example `paper-radar-khu`).
4. Open **Advanced settings**, choose Python **3.12**, and paste your key into **Secrets**:
   ```toml
   OPENALEX_API_KEY = "your-key"
   ```
5. Deploy. Every later `git push` to `main` updates the app automatically.

Notes:
- Apps with no visitors for 12 hours go to sleep. Open the URL a few minutes before a demo to wake it up.
- Files written while the app runs (`cache/`) may disappear when the app restarts, so demo results are kept in `seed_cache/` and committed.

## Before a demo

1. Refresh the saved demo results, then commit and push `seed_cache/`:
   ```bash
   .venv\Scripts\python prefetch.py
   ```
   You can also save other searches: `prefetch.py "network slicing, xApp" "Michele Polese"`.
   Add `--fresh` to ignore saved results and fetch everything again.
2. Open the live app a few minutes early and keep the sample radar link ready.
3. If the network is unreliable, add `&offline=1` to the results URL.
4. Stick to saved searches during the talk; brand-new searches depend on the live API.

## Project structure

```
app.py              Router: ?kw=&people= → results, ?page=roadmap → roadmap, otherwise search
core/openalex.py    OpenAlex calls, request spacing and retries, saved results (cache/, seed_cache/), de-duplication
core/query.py       Input parsing, synonyms, time-window widening, author matching, trend counts
ui/style.py         Look and feel: CSS, top bar, hero, cards, word clouds
ui/search.py        Search page (two inputs, Enter to submit)
ui/results.py       Results page: 01 New papers · 02 Key people · 03 Trends · 04 Summaries
ui/roadmap.py       About & roadmap page
prefetch.py         Saves search results to seed_cache/ before a demo or deployment
seed_cache/         Saved results committed with the code
.streamlit/         Theme (config.toml) and secrets template
```

## Roadmap

| Status | Item |
|---|---|
| ✅ Shipped | **v0.1 demo** — new papers, key people, trends, shareable links, offline mode |
| 🔄 In progress | **arXiv as a second source** — merged with OpenAlex, duplicates removed by title or DOI |
| 🗓 Planned | **Accounts** — log in and see your saved keywords and key people |
| 🗓 Planned | **Weekly agent on n8n** — every Monday, new papers plus AI summaries (Gemini) by email; sharing with the whole lab after one-tap approval |
| 🗓 Planned | **Better matching and trends** — smarter author matching, fairer rising-topic scores |

Course timeline:

| Week | Goal |
|---|---|
| Week 2 | Finish the demo |
| Week 3 | Contact other labs and invite them to try it |
| Week 4 | Collect feedback and improve the site |
| Week 5 | Final report |

## Known limitations

- OpenAlex has no abstract for some publishers’ papers, so phrases that appear only in an abstract can be missed.
- Picking the author with the most papers can choose the wrong person when names are shared — switch on the results page.
- Rising-topic scores use each year’s top keywords, so words that were rare in early years can look like they grew faster than they did.

## Data and license

Paper data © contributors, provided by [OpenAlex](https://openalex.org) under CC0.

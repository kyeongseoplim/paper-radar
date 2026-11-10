# 📡 Paper Radar

Type **keywords** and **key people**, press Enter, and get:

1. **New papers** on your topics (last 30 days, widened automatically when there are too few)
2. **New papers from the people you follow**
3. **Trends since 2020** — papers per year, yearly word clouds, rising topics
4. *(coming soon)* AI summaries sent weekly after your approval

Data: [OpenAlex](https://openalex.org) (CC0). Course project demo, Kyung Hee University.

---

## Running locally

Run the app from this folder (`paper_radar`) so that the theme (`.streamlit/config.toml`) and the API key (`secrets.toml`) are applied.

```bash
.venv/Scripts/python -m streamlit run app.py
```

First-time setup:

```bash
py -3.14 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

## Deploying (Streamlit Community Cloud → a real URL)

1. Create a new GitHub repository (e.g. `paper-radar`). A public repository gives a public app; a private one gives a private app (limit of 1).
2. Push this folder. `.gitignore` excludes `.venv/`, `cache/` and `secrets.toml`. **Make sure `seed_cache/` is pushed too.**
   ```bash
   git init -b main
   git add .
   git commit -m "Paper Radar demo"
   git remote add origin https://github.com/<your-username>/paper-radar.git
   git push -u origin main
   ```
3. Go to https://share.streamlit.io → **Create app** → repository `paper-radar`, branch `main`, file `app.py`.
4. Under **App URL**, pick a name (e.g. `paper-radar-khu` → `https://paper-radar-khu.streamlit.app`).
5. Open **Advanced settings** → choose Python **3.12**, paste the following into **Secrets** → Deploy.
   ```toml
   OPENALEX_API_KEY = "your_api_key"
   ```

### Cloud caveats

- **An API key is required.** Without one, requests use OpenAlex's shared quota ($0.10 per day). Cloud servers are likely to share IPs across many apps, so you will get blocked quickly. Free key: https://openalex.org/settings/api
- **The app goes to sleep after 12 hours without visits.** Open the URL 10 minutes before your presentation to wake it up.
- Results fetched while running (`cache/`) may be lost on restart. Put presentation results in `seed_cache/` and push them with git (see below).

## Before a presentation

1. **Prefetch** → saved to `seed_cache/` → commit and push to git
   ```bash
   .venv/Scripts/python prefetch.py
   ```
   You can prefetch other searches too: `prefetch.py "network slicing, xApp" "Michele Polese"`
2. Open results directly from a URL (for sharing links):
   `https://<app-url>/?kw=MAC+scheduler%2C+O-RAN&people=Tommaso+Melodia`
3. If the network is unreliable, add `&offline=1` to the end of the URL → only saved results are used.

The indicator at the bottom of the page shows where the data came from: 🟢 Live · 🔵 Saved result · 🟠 OpenAlex busy (using saved result).

## Search rules

| Input | Rule |
|---|---|
| Keywords | Comma-separated. **Each comma-separated term is a required topic (AND).** Equivalent expressions expand automatically (O-RAN = Open RAN = open radio access network, scheduler = scheduling, etc.; see `SYNONYMS` in `core/query.py`) |
| Time window | Last 30 days → if fewer than 3 papers, widens automatically to 90 days → 365 days, with a notice on screen |
| Key people | Comma-separated (up to 3 people). Among authors with the same name, the one with the most papers is picked automatically; change it under "Not the right person?" |
| Trends | Counted broadly over papers containing **any** of the keywords (OR). The search terms themselves are excluded from the word clouds |

## Files

```
app.py              Screen switching (results if the URL has ?kw=&people=, otherwise search)
core/openalex.py    OpenAlex queries, request spacing and retries, saved results (cache/, seed_cache/), deduplication
core/query.py       Input parsing, synonyms, automatic window widening, people matching, trend aggregation
ui/style.py         Design (CSS, top bar, hero, cards, word clouds)
ui/search.py        Search screen
ui/results.py       Results screen (01 New papers · 02 Key people · 03 Trends · 04 Summaries)
prefetch.py         Prefetch before a presentation or deployment → seed_cache/
.streamlit/config.toml   Theme (Agent1000-style colors, corner radius, Inter font)
```

## Known limitations

- OpenAlex has empty abstracts for some publishers' papers, so terms that appear only in the abstract may be missed.
- Rising keywords are based on each year's top keywords, so words that were outside the top ranks in early years can show an exaggerated increase.
- Automatic selection among authors with the same name uses "most papers" and may be wrong → change it on screen.

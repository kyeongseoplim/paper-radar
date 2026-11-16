# 📡 Paper Radar

Type **keywords** and **key people**, press Enter, and get:

1. **New papers** on your topics (last 30 days, widened automatically when there are too few)
2. **New papers from the people you follow**
3. **Trends since 2020** — papers per year, yearly word clouds, rising topics
4. **For members (sign in):** a weekly report every Monday — new papers on your 2–3 keywords, new papers by the person you follow, this week vs. the 4-week average, and a short Gemini summary — on the site (**Report**) and by email

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

## Database (Neon Postgres)

User accounts, keywords, followed authors, weekly reports and the run log live in a free [Neon](https://neon.tech) Postgres database.

1. Create a Neon project (region near your users, e.g. AWS Asia Pacific Tokyo). Optionally create a `dev` branch for testing.
2. In **Connect**, copy the **pooled** connection string (host contains `-pooler`) into `.streamlit/secrets.toml` as `DATABASE_URL` (see `secrets.toml.example`). Scripts and the weekly job can use a `DATABASE_URL` environment variable instead.
3. Create the tables (safe to re-run after `db/schema.sql` changes):
   ```bash
   .venv/Scripts/python scripts/init_db.py
   ```
   To use Neon's direct (non-pooled) string for schema changes, set `DATABASE_URL_DIRECT`.
4. Check everything works (creates two throwaway users, checks they can't see each other's data, then deletes them):
   ```bash
   .venv/Scripts/python scripts/smoke_db.py
   ```

## Login (Auth0)

Members sign in with a one-time code sent to their email (Auth0 passwordless), through Streamlit's built-in `st.login()`. Without an `[auth]` section in secrets the site still runs as the public demo and hides the Sign in button.

1. In the [Auth0 dashboard](https://manage.auth0.com): **Applications → Create Application → Regular Web Application** (name: Paper Radar).
2. In its **Settings**:
   - **Allowed Callback URLs**: `http://localhost:8501/oauth2callback` (add `https://<app>.streamlit.app/oauth2callback` when deploying)
   - **Allowed Logout URLs**: `http://localhost:8501` (add the cloud URL later)
3. **Authentication → Passwordless → Email**: turn it on, keep **OTP code**, and on its **Applications** tab enable Paper Radar.
4. Back in the application's **Connections** tab: turn off *Username-Password-Authentication*; leave *email* on (and *google-oauth2* if you want a Google button).
5. Copy **Domain**, **Client ID** and **Client Secret** into the `[auth]` section of `.streamlit/secrets.toml` (see `secrets.toml.example`). Generate `cookie_secret` with `python -c "import secrets; print(secrets.token_hex(32))"`.
6. Put your own email in `ADMIN_EMAILS` to keep access to the `?page=db` status page.
7. Restart Streamlit, click **Sign in**, enter your email, type the code. On the first login you fill in name, lab, 2–3 keywords and (optionally) the person to follow, then land on **My radar** (`?page=me`).

Auth0's built-in email sender is for testing only (low sending limit). Before the pilot, set up your own SMTP under **Branding → Email Provider**.

## Weekly reports (n8n)

The whole weekly job runs in **one n8n workflow** — no GitHub Actions and no extra server:

```
Every Monday 07:00 KST / Run by hand → Config → Start run → Load users → Build reports (OpenAlex)
  → Summarize + render (Gemini, email HTML) → Save reports (Neon) ─┬→ Email admin summary
                                                                   └→ Load unsent → Send report (one per user) → Mark emailed
```

Files: `n8n/src/*.js` (the two Code nodes), `n8n/sql/*.sql` (the Postgres nodes), `n8n/build_workflow.py` → `n8n/paper-radar-weekly.json` and `n8n/paper-radar-alert.json` (import these). Edit the `.js`/`.sql` files, run `python n8n/build_workflow.py`, and re-import.

Setup in n8n:

1. **Credentials** → add a **Postgres** credential for Neon: host = the endpoint *without* `-pooler`, database `neondb`, user, password, **SSL: require**. Add an **SMTP** credential for Gmail: user = your Gmail address, password = a Google **app password** (myaccount.google.com/apppasswords, needs 2-Step Verification), host `smtp.gmail.com`, port `465`, SSL/TLS on.
2. **Workflows → Import from file** → `n8n/paper-radar-alert.json`. Open **Email admin**, pick the SMTP credential and put your Gmail address in *From* and *To*. Save.
3. Import `n8n/paper-radar-weekly.json`. Open each Postgres node (Start run, Load users, Save reports, Load unsent, Mark emailed) and pick the Neon credential; open both Send Email nodes (Email admin summary, Send report) and pick the SMTP credential.
4. Open **Config** and fill in `ADMIN_EMAIL`, `FROM_EMAIL` (`Paper Radar <the Gmail address of the SMTP credential>`), `APP_URL` (your `.streamlit.app` address), `OPENALEX_API_KEY`, `GEMINI_API_KEY` (Google AI Studio). Leave `TEST_MODE` on.
5. Workflow **Settings** → **Error workflow** = *Paper Radar · error alert*; timezone should already be Asia/Seoul. Save.
6. Click **Execute workflow** (the *Run by hand* trigger). In test mode every report email goes to `ADMIN_EMAIL` with `[TEST to …]` in the subject, and reports are not marked as sent, so you can repeat it. Check the reports on the site (**Report** page).
7. When two scheduled runs in a row look right: set `TEST_MODE` to false and **activate** the workflow.

Re-running the workflow in the same week rebuilds the same week's report and never emails a report twice. Papers shown in an earlier week are not shown again.

Without n8n (development): `python n8n/run_local.py` runs the same JS and SQL against `DATABASE_URL` (no emails). It needs `node`, or docker.

## Tests

```bash
python -m pytest tests/                                                    # search logic + report page
docker run -i --rm -v $PWD:/app -w /app node:22-bullseye \
  node --test tests/test_build_reports.mjs tests/test_summarize_render.mjs # the two n8n Code nodes (or plain `node --test ...`)
python scripts/smoke_db.py                                                 # database, against DATABASE_URL
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
5. Open **Advanced settings** → choose Python **3.12**, paste your `.streamlit/secrets.toml` into **Secrets** (OpenAlex key, Neon `DATABASE_URL`, `ADMIN_EMAILS` and the `[auth]` section) → Deploy.
6. Change `[auth] redirect_uri` to `https://<app>.streamlit.app/oauth2callback`, and add that URL to Auth0's **Allowed Callback URLs** (and `https://<app>.streamlit.app` to **Allowed Logout URLs**).
7. Put the app address in the n8n **Config** node's `APP_URL` (used for the link in the emails).

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
core/db.py          Database helpers (users, keywords, author, reports, seen papers, run log, shared cache)
db/schema.sql       Table definitions for Neon Postgres
scripts/init_db.py  Create/update the tables · scripts/smoke_db.py  End-to-end database check
ui/auth.py          Login (st.login + Auth0) ↔ users table, admin check
ui/account.py       Settings page / first-login profile form (?page=settings)
ui/report.py        Weekly report page with past-week picker (?page=me)
n8n/                Weekly workflow: Code-node JS (src/), SQL (sql/), builder, importable JSON, local runner
tests/              pytest (search logic, report page) + node tests for the n8n Code nodes
blueprint.md        Implementation plan for roadmap Steps 3–11; reports/ holds the per-module test reports
ui/dbstatus.py      Database status page (?page=db, admins only)
prefetch.py         Prefetch before a presentation or deployment → seed_cache/
.streamlit/config.toml   Theme (Agent1000-style colors, corner radius, Inter font)
```

## Known limitations

- OpenAlex has empty abstracts for some publishers' papers, so terms that appear only in the abstract may be missed.
- Rising keywords are based on each year's top keywords, so words that were outside the top ranks in early years can show an exaggerated increase.
- Automatic selection among authors with the same name uses "most papers" and may be wrong → change it on screen.

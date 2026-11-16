"""Hidden page (?page=db): checks the app can reach the database. Not linked from the menu.
Shows only the host and table row counts (no credentials, no user data). Make it admin-only once login exists."""
from __future__ import annotations

import time
import uuid
from urllib.parse import urlparse

import streamlit as st

from core import db
from ui import style

TABLES = ("users", "keywords", "followed_authors", "reports", "seen_papers", "runs", "openalex_cache")


def render() -> None:
    st.html(style.eyebrow("Diagnostics") + '<div class="pr-h2">Database connection</div>')
    try:
        url = db.get_url()
    except db.ConfigError as e:
        st.error(f"{e} Add it to .streamlit/secrets.toml (see secrets.toml.example).")
        return
    host = urlparse(url).hostname or "?"

    t0 = time.perf_counter()
    try:
        with db.connect() as conn:
            info = conn.execute("SELECT current_database() AS db, split_part(version(), ' ', 2) AS ver").fetchone()
            ms = (time.perf_counter() - t0) * 1000
            existing = {r["table_name"] for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
            counts = {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] if t in existing else None
                      for t in TABLES}
    except Exception as e:  # show any connection / auth / SSL error as-is
        st.error(f"Could not connect to `{host}`: {type(e).__name__}: {e}")
        return

    st.success(f"Connected to `{host}` · database `{info['db']}` · Postgres {info['ver']} · {ms:.0f} ms "
               "(the first connection after Neon has been idle takes longer)")
    missing = [t for t, n in counts.items() if n is None]
    if missing:
        st.warning(f"Missing tables: {', '.join(missing)}. Run `python scripts/init_db.py`.")
    st.dataframe([{"table": t, "rows": "missing" if n is None else n} for t, n in counts.items()],
                 hide_index=True, width="content")

    if not missing and st.button("Test a write (insert, read back, delete)", icon=":material/sync:"):
        key = f"status-check:{uuid.uuid4().hex[:8]}"
        try:
            db.cache_put(key, {"ok": True})
            ok = (db.cache_get(key) or {}).get("data") == {"ok": True}
        finally:
            with db.connect() as conn:
                conn.execute("DELETE FROM openalex_cache WHERE cache_key = %s", (key,))
        (st.success if ok else st.error)("Write test passed." if ok else "Write test failed: value not read back.")

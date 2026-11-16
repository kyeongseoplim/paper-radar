"""Create or update the tables in db/schema.sql. Safe to run more than once.

    python scripts/init_db.py              # uses DATABASE_URL_DIRECT, else DATABASE_URL
    python scripts/init_db.py --check      # only list the tables that exist

Use Neon's *direct* (non "-pooler") connection string for schema changes when you have it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import db  # noqa: E402


def main() -> int:
    url = os.environ.get("DATABASE_URL_DIRECT") or db.get_url()
    with db.connect(url) as conn:
        if "--check" not in sys.argv:
            db.apply_schema(conn)
            print("Schema applied.")
        rows = conn.execute("SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public' ORDER BY table_name").fetchall()
    print("Tables:", ", ".join(r["table_name"] for r in rows) or "(none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

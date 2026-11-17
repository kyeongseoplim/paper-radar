"""Run the weekly job once WITHOUT n8n (dev/testing): same Code-node JS and same SQL as the workflow, no emails.

    python n8n/run_local.py        # uses DATABASE_URL, OPENALEX_API_KEY, GEMINI_API_KEY (env or .streamlit/secrets.toml)

Needs `node` on PATH, or docker (falls back to the node:22-bullseye image).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import db  # noqa: E402


def setting(name: str, default: str = "") -> str:
    secrets = ROOT / ".streamlit" / "secrets.toml"
    value = tomllib.loads(secrets.read_text(encoding="utf-8")).get(name) if secrets.exists() else None
    return os.environ.get(name) or value or default


def sql(name: str) -> str:
    """The workflow's SQL file with @name@ placeholders turned into psycopg parameters."""
    text = (ROOT / "n8n" / "sql" / f"{name}.sql").read_text(encoding="utf-8")
    for k in ("trigger", "items", "run_id"):
        text = text.replace(f"@{k}@", f"%({k})s")
    return text.replace("@user_filter@", "true")  # all users


def run_nodes(config: dict, users: list[dict]) -> list[dict]:
    node = ["node"] if shutil.which("node") else \
        ["docker", "run", "-i", "--rm", "-v", f"{ROOT}:/app", "-w", "/app", "node:22-bullseye", "node"]
    out = subprocess.run(node + ["n8n/harness.mjs", "n8n/src/build_reports.js", "n8n/src/summarize_render.js"],
                         input=json.dumps({"config": config, "items": users}, default=str), cwd=ROOT,
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def main() -> int:
    config = {"TEST_MODE": True, "ADMIN_EMAIL": "", "APP_URL": setting("APP_URL", "http://localhost:8501"),
              "OPENALEX_API_KEY": setting("OPENALEX_API_KEY"), "GEMINI_API_KEY": setting("GEMINI_API_KEY"),
              "GEMINI_MODEL": setting("GEMINI_MODEL", "gemini-2.5-flash")}
    with db.connect() as conn:
        run_id = conn.execute(sql("start_run"), {"trigger": "manual"}).fetchone()["id"]
        users = conn.execute(sql("load_users")).fetchall()
    print(f"run #{run_id}: {len(users)} users")
    items = run_nodes(config, users)
    for it in items:
        papers = len(it["data"]["papers"]["rows"]) if it["ok"] and it["data"]["papers"] else 0
        print(f"  user {it['user_id']}: {'ok' if it['ok'] else 'FAILED ' + it['error']} · {papers} papers"
              + (f" · errors {it['data']['errors']}" if it["ok"] and it["data"]["errors"] else ""))
    with db.connect() as conn:
        run = conn.execute(sql("save_reports"), {"items": json.dumps(items), "run_id": run_id}).fetchone()
    print(f"run #{run['id']}: {run['status']} ({run['users_ok']} ok, {run['users_failed']} failed)")
    return 0 if run["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

"""Build the importable n8n workflows from the Code-node sources (n8n/src) and SQL files (n8n/sql).

    python n8n/build_workflow.py      # writes n8n/paper-radar-weekly.json and n8n/paper-radar-alert.json

Edit the .js / .sql files, not the JSON, then re-run this and re-import the workflow in n8n.
SQL placeholders (@name@) become n8n expressions here; n8n/run_local.py turns them into psycopg parameters.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = "$('Config').first().json"

# SQL placeholder -> n8n expression. The report JSON goes in as a dollar-quoted literal because the Postgres
# node's "Query Parameters" option splits values on commas.
N8N_PARAMS = {
    "trigger": "'{{ $('On demand').isExecuted ? 'webhook' : $('Run by hand').isExecuted ? 'manual' : 'schedule' }}'",
    # Number() keeps anything but a number out of the SQL; schedule and manual runs load every user
    "user_filter": "{{ $('On demand').isExecuted ? 'u.id = ' + Number($('On demand').first().json.body.user_id) : 'true' }}",
    "items": "$pr${{ JSON.stringify($input.all().map(i => i.json)) }}$pr$",
    "run_id": "{{ $('Start run').first().json.id }}",
    "ids": "ARRAY[{{ $('Load unsent').all().map(i => i.json.id).join(',') }}]",
    "test_mode": "{{ " + CFG + ".TEST_MODE }}",
}

CONFIG = [  # (name, type, default) — edit the values in n8n after importing
    ("TEST_MODE", "boolean", True),
    ("ADMIN_EMAIL", "string", "you@gmail.com"),
    ("FROM_EMAIL", "string", "Paper Radar <you@gmail.com>"),   # must be the Gmail account of the SMTP credential
    ("APP_URL", "string", "https://<your-app>.streamlit.app"),
    ("OPENALEX_API_KEY", "string", ""),
    ("GEMINI_API_KEY", "string", ""),
    ("GEMINI_MODEL", "string", "gemini-2.5-flash"),
]


def sql(name: str) -> str:
    text = (HERE / "sql" / f"{name}.sql").read_text(encoding="utf-8")
    for k, v in N8N_PARAMS.items():
        text = text.replace(f"@{k}@", v)
    return "=" + text if "{{" in text else text


def node(name: str, type_: str, version: float, x: int, y: int, params: dict, **extra) -> dict:
    return {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"paper-radar/{name}")), "name": name, "type": type_,
            "typeVersion": version, "position": [x, y], "parameters": params, **extra}


def postgres(name: str, x: int, y: int, query: str, **extra) -> dict:
    return node(name, "n8n-nodes-base.postgres", 2.5, x, y,
                {"operation": "executeQuery", "query": query, "options": {}},
                credentials={"postgres": {"id": "", "name": "Neon (Paper Radar)"}}, **extra)


def code(name: str, x: int, y: int, file: str) -> dict:
    return node(name, "n8n-nodes-base.code", 2, x, y,
                {"mode": "runOnceForAllItems", "jsCode": (HERE / "src" / file).read_text(encoding="utf-8")})


def email(name: str, x: int, y: int, from_: str, to: str, subject: str, html: str) -> dict:
    """Send Email node over SMTP (e.g. Gmail with an app password)."""
    return node(name, "n8n-nodes-base.emailSend", 2.1, x, y,
                {"fromEmail": from_, "toEmail": to, "subject": subject, "emailFormat": "html", "html": html,
                 "options": {"appendAttribution": False}},
                credentials={"smtp": {"id": "", "name": "SMTP (Paper Radar)"}})


def chain(*names: str) -> dict:
    return {a: {"main": [[{"node": b, "type": "main", "index": 0}]]} for a, b in zip(names, names[1:])}


def weekly() -> dict:
    nodes = [
        node("Every Monday 07:00", "n8n-nodes-base.scheduleTrigger", 1.2, 0, 0,
             {"rule": {"interval": [{"field": "weeks", "triggerAtDay": [1], "triggerAtHour": 7}]}}),
        node("Run by hand", "n8n-nodes-base.manualTrigger", 1, 0, 200, {}),
        node("On demand", "n8n-nodes-base.webhook", 2, 0, 400,   # "Build my report now" button on the Report page
             {"httpMethod": "POST", "path": "paper-radar-run", "authentication": "headerAuth",
              "responseMode": "onReceived", "options": {}},
             webhookId=str(uuid.uuid5(uuid.NAMESPACE_URL, "paper-radar/webhook")),
             credentials={"httpHeaderAuth": {"id": "", "name": "X-Paper-Radar-Token"}}),
        node("Config", "n8n-nodes-base.set", 3.4, 220, 100, {"assignments": {"assignments": [
            {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, n)), "name": n, "type": t, "value": v} for n, t, v in CONFIG]},
            "options": {}}),
        postgres("Start run", 440, 100, sql("start_run")),
        postgres("Load users", 660, 100, sql("load_users")),
        code("Build reports", 880, 100, "build_reports.js"),
        code("Summarize + render", 1100, 100, "summarize_render.js"),
        postgres("Save reports", 1320, 100, sql("save_reports"), executeOnce=True),
        email("Email admin summary", 1540, 0, f"={{{{ {CFG}.FROM_EMAIL }}}}", f"={{{{ {CFG}.ADMIN_EMAIL }}}}",
              "={{ 'Paper Radar run #' + $json.id + ': ' + $json.status }}",
              "={{ '<p>Users OK: <b>' + $json.users_ok + '</b> · failed: <b>' + $json.users_failed + '</b></p>'"
              " + ($json.error ? '<pre>' + $json.error + '</pre>' : '')"
              f" + '<p>Test mode: ' + {CFG}.TEST_MODE + '</p>' }}}}"),
        postgres("Load unsent", 1540, 200, sql("load_unsent")),
        email("Send report", 1760, 200, f"={{{{ {CFG}.FROM_EMAIL }}}}",
              f"={{{{ {CFG}.TEST_MODE ? {CFG}.ADMIN_EMAIL : $json.email }}}}",
              f"={{{{ ({CFG}.TEST_MODE ? '[TEST to ' + $json.email + '] ' : '') + 'Paper Radar · week of ' + $json.week_start }}}}",
              "={{ $json.email_html }}"),
        postgres("Mark emailed", 1980, 200, sql("mark_emailed"), executeOnce=True),
    ]
    connections = {
        **chain("Every Monday 07:00", "Config"), **chain("Run by hand", "Config"),
        **chain("On demand", "Config"),
        **chain("Config", "Start run", "Load users", "Build reports", "Summarize + render", "Save reports"),
        "Save reports": {"main": [[{"node": "Email admin summary", "type": "main", "index": 0},
                                   {"node": "Load unsent", "type": "main", "index": 0}]]},
        **chain("Load unsent", "Send report", "Mark emailed"),
    }
    return {"name": "Paper Radar · weekly reports", "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1", "timezone": "Asia/Seoul"}, "pinData": {}}


def alert() -> dict:
    nodes = [
        node("On workflow error", "n8n-nodes-base.errorTrigger", 1, 0, 0, {}),
        email("Email admin", 220, 0, "Paper Radar <you@gmail.com>", "you@gmail.com",
              "={{ 'Paper Radar workflow failed: ' + $json.workflow.name }}",
              "={{ '<p>' + $json.execution.error.message + '</p><p><a href=\"' + $json.execution.url + '\">Open the execution</a></p>' }}"),
    ]
    return {"name": "Paper Radar · error alert", "nodes": nodes, "connections": chain("On workflow error", "Email admin"),
            "settings": {"executionOrder": "v1"}, "pinData": {}}


if __name__ == "__main__":
    for fname, wf in (("paper-radar-weekly.json", weekly()), ("paper-radar-alert.json", alert())):
        (HERE / fname).write_text(json.dumps(wf, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", HERE / fname)

"""Report page (ui/report.py) renders a saved report without touching OpenAlex or a real database.
The db functions are replaced with fakes returning a report in the n8n data format (blueprint.md, Notation)."""
import datetime as dt

from streamlit.testing.v1 import AppTest

WEEK = dt.date(2026, 11, 16)
PAPER = {"id": "W1", "title": "A <b>new</b> O-RAN scheduler", "date": "2026-11-12", "authors": ["Ann Lee", "Bo Kim"],
         "venue": "IEEE TWC", "publisher": "IEEE", "type": "article", "cited": 0, "link": "https://doi.org/10/x"}
DATA = {
    "version": 1, "week": str(WEEK), "generated_at": "2026-11-16T07:00:00Z", "keywords": ["O-RAN", "MAC scheduler"],
    "query_text": "(O-RAN OR Open RAN) AND (MAC scheduler OR MAC scheduling)",
    "papers": {"rows": [PAPER], "total": 1, "days": 30, "widened_from": 7, "skipped_seen": 2},
    "author": {"id": "A1", "name": "Bo Kim", "inst": "KHU", "rows": [PAPER], "total": 1, "days": 7},
    "trends": {"keywords": [{"term": "O-RAN", "this_week": 14, "avg4": 10.0, "change": 1.4},
                            {"term": "MAC scheduler", "this_week": 0, "avg4": 0.0, "change": None}],
               "new_topics": [{"keyword": "xApp energy", "count": 3}]},
    "summary": "Scheduling for O-RAN was busy this week.",
    "errors": {},
}


def app(data, weeks):
    from core import db
    from ui import report
    db.connect = lambda: __import__("contextlib").nullcontext()
    db.get_keywords = lambda uid, conn=None: ["O-RAN", "MAC scheduler"]
    db.get_author = lambda uid, conn=None: {"display_name": "Bo Kim", "institution": "KHU"}
    db.list_reports = lambda uid, conn=None: [{"week_start": w} for w in weeks]
    db.get_report = lambda uid, week=None, conn=None: {"week_start": week, "data": data}
    user = {"id": 1, "name": "Alice", "email": "a@x.com", "lab_name": "WN Lab", "email_enabled": True}
    report.render(user)


def run(data, weeks):
    at = AppTest.from_function(app, kwargs={"data": data, "weeks": weeks})
    return at.run(timeout=30)


def text_of(at):
    return " ".join(str(e.proto) for e in at.main)


def test_full_report_renders():
    at = run(DATA, [WEEK, WEEK - dt.timedelta(days=7)])
    assert not at.exception
    assert len(at.selectbox) == 1 and len(at.selectbox[0].options) == 2
    page = text_of(at)
    for snippet in ("Scheduling for O-RAN was busy", "widened", "xApp energy", "From Bo Kim", "&lt;b&gt;new"):
        assert snippet in page, snippet


def test_partial_report_shows_section_errors():
    data = {**DATA, "author": None, "trends": None, "summary": None, "errors": {"trends": "OpenAlex timeout"}}
    at = run(data, [WEEK])
    assert not at.exception
    assert any("OpenAlex timeout" in w.value for w in at.warning)


def test_no_report_yet():
    at = run(DATA, [])
    assert not at.exception
    assert any("first weekly report" in i.value for i in at.info)

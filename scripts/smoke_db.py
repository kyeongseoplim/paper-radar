"""End-to-end check of core/db.py against a real database. Creates two throwaway users,
exercises every function, checks that neither user can read the other's data, then deletes
everything it created (even on failure).

    python scripts/smoke_db.py        # uses DATABASE_URL; run scripts/init_db.py first
"""
from __future__ import annotations

import datetime as dt
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import db  # noqa: E402


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


def main() -> int:
    tag = uuid.uuid4().hex[:8]
    week = db.week_start()
    prev = week - dt.timedelta(days=7)
    users: list[int] = []
    run_id = None
    try:
        print("users")
        a = db.login(f"smoke|{tag}-a", f"smoke-a-{tag}@example.com", "Alice")
        b = db.login(f"smoke|{tag}-b", f"smoke-b-{tag}@example.com", "Bob")
        users += [a["id"], b["id"]]
        check(db.login(f"smoke|{tag}-a", f"smoke-a-{tag}@example.com")["id"] == a["id"], "same sub -> same user")
        check(db.login(f"google|{tag}", f"SMOKE-A-{tag}@example.com")["id"] == a["id"], "same email -> same user")
        db.update_profile(a["id"], lab_name="Shared Lab", onboarded=True)
        db.update_profile(b["id"], lab_name="Shared Lab", email_enabled=False, onboarded=True)
        check(db.get_user(a["id"])["onboarded_at"] is not None, "onboarding recorded")

        print("keywords & author")
        check(db.set_keywords(a["id"], ["O-RAN", " o-ran ", "MAC  scheduler"]) == ["O-RAN", "MAC scheduler"],
              "keywords trimmed and de-duplicated")
        db.set_keywords(b["id"], ["network slicing", "xApp", "digital twin"])
        try:
            db.set_keywords(a["id"], ["only one"])
            check(False, "too few keywords rejected")
        except ValueError:
            check(True, "too few keywords rejected")
        check(db.get_keywords(a["id"]) == ["O-RAN", "MAC scheduler"], "failed update left keywords intact")
        db.set_author(a["id"], "https://openalex.org/A5000000001", "Test Author", "Test Univ")
        db.set_author(a["id"], "A5000000002", "Right Author", "Test Univ")
        check(db.get_author(a["id"])["openalex_id"] == "A5000000002", "author replaced, id shortened")
        check(db.get_author(b["id"]) is None, "B has no author")
        mine = [u for u in db.active_users() if u["id"] in users]
        check(len(mine) == 2 and mine[0]["keywords"] == ["O-RAN", "MAC scheduler"], "active_users lists both")

        print("run + reports")
        run_id = db.start_run("manual")
        with db.connect() as conn:   # one shared connection, as the job will do
            db.save_report(a["id"], prev, {"who": "A", "week": "prev"}, "# A prev", run_id=run_id, conn=conn)
            db.save_report(a["id"], week, {"who": "A"}, "# A", "<p>A</p>", run_id, conn=conn)
            db.save_report(b["id"], week, {"who": "B"}, "# B", "<p>B</p>", run_id, conn=conn)
            db.save_report(a["id"], week, {"who": "A", "v": 2}, "# A v2", "<p>A2</p>", run_id, conn=conn)
        check(db.finish_run(run_id, 2, 0) == "success", "run logged as success")
        check(db.finish_run(run_id, 1, 1) == "partial" and db.finish_run(run_id, 0, 2) == "failed",
              "partial / failed statuses")

        print("privacy")
        ra, rb = db.list_reports(a["id"]), db.list_reports(b["id"])
        check([r["week_start"] for r in ra] == [week, prev], "A sees 2 weeks, newest first")
        check(len(rb) == 1, "B sees only its own report")
        check(db.get_report(a["id"])["data"] == {"who": "A", "v": 2}, "re-save replaced A's report")
        check(db.get_report(b["id"], prev) is None, "B cannot read a week it has no report for")
        check(not {r["id"] for r in ra} & {r["id"] for r in rb}, "no shared report rows")

        print("seen papers")
        check(db.unseen(a["id"], ["W1", "https://openalex.org/W2"]) == ["W1", "W2"], "all new at first")
        db.mark_seen(a["id"], ["W1"], week)
        db.mark_seen(a["id"], ["W1"], week)   # idempotent
        check(db.unseen(a["id"], ["W1", "W2"]) == ["W2"], "seen paper filtered for A")
        check(db.unseen(b["id"], ["W1", "W2"]) == ["W1", "W2"], "A's seen list does not affect B")

        print("emailing")
        unsent = [r for r in db.unsent_reports(week) if r["user_id"] in users]
        check([r["user_id"] for r in unsent] == [a["id"]], "only A (email on) is queued")
        db.mark_emailed(unsent[0]["id"])
        db.save_report(a["id"], week, {"who": "A", "v": 3})
        check(not [r for r in db.unsent_reports(week) if r["user_id"] in users], "re-save does not re-queue")

        print("cache")
        key = f"smoke:{tag}"
        db.cache_put(key, {"n": 1})
        db.cache_put(key, {"n": 2})
        check(db.cache_get(key)["data"] == {"n": 2}, "cache upsert")
        print("\nAll checks passed.")
        return 0
    finally:
        with db.connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ANY(%s)", (users,))   # cascades to all user rows
            conn.execute("DELETE FROM openalex_cache WHERE cache_key = %s", (f"smoke:{tag}",))
            if run_id:
                conn.execute("DELETE FROM runs WHERE id = %s", (run_id,))


if __name__ == "__main__":
    sys.exit(main())

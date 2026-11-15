"""주간 작업: 사용자마다 지난주(월~일, 한국 시간)의 새 논문을 찾아 리포트를 저장한다. 손으로도 돌릴 수 있다.

    .venv/Scripts/python.exe weekly_run.py --dry-run                 # 저장하지 않고 결과만 출력
    .venv/Scripts/python.exe weekly_run.py                           # 전원 실행 후 저장
    .venv/Scripts/python.exe weekly_run.py --user test1@example.com  # 한 명만
    .venv/Scripts/python.exe weekly_run.py --as-of 2026-11-23        # 이 날짜에 돌린 것처럼
    .venv/Scripts/python.exe weekly_run.py --fresh                   # 저장본을 쓰지 않고 새로 받기

규칙
- 리포트 한 건은 as_of 직전에 끝난 한 주(월~일)를 다룬다. 같은 주를 다시 돌리면 덮어쓴다.
- 새 논문: 키워드를 모두 포함한 논문을 그 주 7일에서 찾는다. 3편 미만이면 14일, 30일로 넓히고,
  그래도 부족하면 키워드 중 하나라도 포함한 논문으로 바꿔 같은 순서로 찾는다. 이전 주에 나간 논문은 뺀다.
- 한 사람이 실패해도 나머지는 계속한다. 실패가 하나라도 있으면 종료 코드 1.
- 로그에 이메일을 찍지 않는다(GitHub Actions 로그는 공개). 사용자는 id로만 표시한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from core import openalex as oa
from core import query
from core.store import db
from prefetch import read_key

KST = dt.timezone(dt.timedelta(hours=9))  # 한국은 서머타임이 없어 고정 +9시간
WINDOWS = (7, 14, 30)       # 새 논문을 찾는 기간(일). 앞에서부터 시도
AUTHOR_WINDOWS = (7, 30)    # 팔로우한 사람의 논문을 찾는 기간(일)
MIN_PAPERS = 3              # 이보다 적으면 기간을 넓힌다
N_SHOW = 10                 # 리포트에 싣는 최대 편수
N_FETCH = 40                # 이미 본 논문을 빼기 전에 넉넉히 받아 두는 편수
TYPE = f"type:{oa.WORK_TYPES}"


def last_week(as_of: dt.date) -> tuple[dt.date, dt.date]:
    """as_of 직전에 끝난 한 주의 (월요일, 일요일)."""
    this_monday = as_of - dt.timedelta(days=as_of.weekday())
    return this_monday - dt.timedelta(days=7), this_monday - dt.timedelta(days=1)


def _dates(start: dt.date, end: dt.date) -> list[str]:
    return [f"from_publication_date:{start}", f"to_publication_date:{end}"]


def fetch_works(client: oa.OpenAlex, base: list[str], start: dt.date, end: dt.date, key: str):
    """(정리된 논문 목록, 전체 건수). 저장본 키에 날짜를 넣어 다른 주의 결과와 섞이지 않게 한다."""
    params = {"filter": ",".join(base + _dates(start, end)), "sort": "publication_date:desc",
              "per-page": N_FETCH, "select": oa.SELECT}
    data, _ = client.get("works", params, f"weekly|{key}|{start}|{end}|{N_FETCH}")
    return oa.tidy([oa.parse_work(w) for w in data["results"]]), data["meta"]["count"]


def count_works(client: oa.OpenAlex, groups, start: dt.date, end: dt.date) -> int:
    """건수만 필요할 때: 한 편만 받아 비용을 줄인다."""
    params = {"filter": ",".join(oa.kw_filters(groups) + [TYPE] + _dates(start, end)),
              "per-page": 1, "select": "id"}
    data, _ = client.get("works", params, f"weeklycount|{oa.gkey(groups)}|{start}|{end}")
    return data["meta"]["count"]


def build_report(client: oa.OpenAlex, user: dict, week_start: dt.date, week_end: dt.date,
                 seen: set[str]) -> tuple[dict, list[str]]:
    """(리포트 JSON, 이번 주에 보여 준 논문 id 목록)."""
    keywords = list(user["keywords"])
    groups = query.expand(keywords)

    # 시도 순서: 키워드를 모두 포함(all) 7·14·30일 → 그래도 부족하면 하나라도 포함(any) 7·14·30일
    any_groups = query.field_groups(groups)
    ladder = [("all", groups, d) for d in WINDOWS]
    if any_groups != groups:
        ladder += [("any", any_groups, d) for d in WINDOWS]
    papers = {"rows": [], "days": WINDOWS[0], "widened_from": None, "match": "all"}
    new_after_seen = 0
    for match, gs, days in ladder if groups else []:
        start = week_end - dt.timedelta(days=days - 1)
        rows, _ = fetch_works(client, oa.kw_filters(gs) + [TYPE], start, week_end, "k:" + oa.gkey(gs))
        fresh = [r for r in rows if r["id"] not in seen]
        if len(fresh) > new_after_seen or not papers["rows"]:
            papers = {"rows": fresh[:N_SHOW], "days": days, "match": match,
                      "widened_from": WINDOWS[0] if days != WINDOWS[0] else None}
            new_after_seen = len(fresh)
        if len(fresh) >= MIN_PAPERS:
            break

    author = user.get("author")
    author_part, author_7d = None, 0
    if author:
        for days in AUTHOR_WINDOWS:
            start = week_end - dt.timedelta(days=days - 1)
            rows, total = fetch_works(client, [f"author.id:{author['id']}"], start, week_end, "a:" + author["id"])
            if days == AUTHOR_WINDOWS[0]:
                author_7d = total
            fresh = [r for r in rows if r["id"] not in seen]
            if fresh or days == AUTHOR_WINDOWS[-1]:
                author_part = {"id": author["id"], "name": author["name"], "inst": author.get("inst", ""),
                               "rows": fresh[:N_SHOW], "days": days}
                break

    counts = {
        "field_7d": count_works(client, query.field_groups(groups), week_start, week_end) if groups else 0,
        "per_keyword": {kw: count_works(client, [g], week_start, week_end) for kw, g in zip(keywords, groups)},
        "author_7d": author_7d,
        "new_after_seen": new_after_seen,
    }
    data = {"schema": 1, "week_start": str(week_start), "week_end": str(week_end),
            "generated_at": dt.datetime.now(KST).isoformat(timespec="seconds"),
            "keywords": keywords, "papers": papers, "author": author_part,
            "counts": counts, "summary": None, "errors": []}
    shown = [r["id"] for r in papers["rows"]] + [r["id"] for r in (author_part or {}).get("rows", [])]
    return data, list(dict.fromkeys(shown))


def main() -> int:
    sys.stdout.reconfigure(errors="replace")  # 콘솔이 못 찍는 글자는 ?로 바꿔 멈추지 않게
    ap = argparse.ArgumentParser(description="Paper Radar weekly job")
    ap.add_argument("--as-of", help="YYYY-MM-DD. 이 날짜에 돌린 것처럼 계산 (기본: 오늘, 한국 시간)")
    ap.add_argument("--user", help="이 이메일의 사용자 한 명만 처리")
    ap.add_argument("--dry-run", action="store_true", help="저장하지 않고 결과만 출력")
    ap.add_argument("--fresh", action="store_true", help="저장본을 쓰지 않고 전부 새로 받기")
    args = ap.parse_args()

    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else dt.datetime.now(KST).date()
    week_start, week_end = last_week(as_of)

    oa.MAX_RETRY, oa.MAX_WAIT = 4, 60  # 사람이 기다리는 화면이 아니므로 끈질기게 재시도
    client = oa.OpenAlex(api_key=read_key(), ttl_hours=0 if args.fresh else 12, patient=True)

    try:
        users = db.list_active_users()
    except NotImplementedError:
        print("core/db.py is not implemented yet. Set PR_DB=fake to use the file DB (cache/fake_db.json).")
        return 1
    if args.user:
        users = [u for u in users if u["email"] == args.user.strip().lower()]
    print(f"week {week_start} ~ {week_end} | as_of {as_of} | users {len(users)} | db {db.__name__}"
          f" | api key {'yes' if client.api_key else 'no'} | {'DRY RUN' if args.dry_run else 'SAVE'}")
    if not users:
        print("No users to process.")
        return 1 if args.user else 0

    run_id = None if args.dry_run else db.run_started()
    ok, errors = 0, []
    for user in users:
        tag = f"user {user['id']}"
        try:
            seen = db.seen_ids(user["id"], str(week_start))
            data, paper_ids = build_report(client, user, week_start, week_end, seen)
            if not args.dry_run:
                db.save_report(user["id"], str(week_start), data, paper_ids)
            ok += 1
            p, c, a = data["papers"], data["counts"], data["author"]
            widened = f" (widened from {p['widened_from']})" if p["widened_from"] else ""
            print(f"[ok] {tag}: {len(p['rows'])} papers in {p['days']}d, match {p['match']}{widened}"
                  f" | field_7d {c['field_7d']} | per_keyword {c['per_keyword']}"
                  f" | author {len(a['rows']) if a else '-'} in {a['days'] if a else '-'}d"
                  f" | seen in earlier weeks {len(seen)}")
            if args.dry_run:
                for r in p["rows"][:3]:
                    print(f"       {r['date']}  {r['title'][:90]}")
        except Exception as e:  # 한 사람이 실패해도 나머지는 계속
            errors.append(f"{tag}: {type(e).__name__}: {e}")
            print(f"[FAILED] {errors[-1]}")

    if run_id is not None:
        db.run_finished(run_id, ok, len(errors), errors)
    print(f"done: {ok} ok, {len(errors)} failed" + ("" if not args.dry_run else " (nothing saved)"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

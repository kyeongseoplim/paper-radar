"""발표·배포 전에 검색 결과를 미리 받아 seed_cache/에 저장합니다 (git에 함께 올리는 폴더).

    .venv/Scripts/python prefetch.py                                  # 예시 검색 (MAC scheduler, O-RAN / Tommaso Melodia)
    .venv/Scripts/python prefetch.py "network slicing, xApp" "Michele Polese"   # 다른 검색
    .venv/Scripts/python prefetch.py --fresh                          # 저장본 무시하고 전부 새로 받기

앱과 똑같은 엔진(core/query.py)을 쓰므로, 같은 검색어를 앱에 넣으면 저장본이 바로 쓰입니다.
"""
from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

from core import openalex as oa
from core import query


def read_key() -> str | None:
    f = Path(__file__).parent / ".streamlit" / "secrets.toml"
    if f.exists():
        key = tomllib.loads(f.read_text(encoding="utf-8")).get("OPENALEX_API_KEY")
        if key and "여기에" not in key:
            return key
    return os.environ.get("OPENALEX_API_KEY")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fresh = "--fresh" in sys.argv
    kw = args[0] if len(args) > 0 else query.EXAMPLE["kw"]
    people = args[1] if len(args) > 1 else query.EXAMPLE["people"]

    oa.MAX_RETRY, oa.MAX_WAIT = 4, 60  # 미리 받기는 느려도 되니 끈질기게 재시도
    client = oa.OpenAlex(api_key=read_key(), ttl_hours=0 if fresh else 12, patient=True,
                         write_dir=oa.SEED_DIR, copy_hits=True)
    print(f"API key: {'yes' if client.api_key else 'no (shared quota)'} | keywords: {kw!r} | people: {people!r}")

    radar = query.run(client, kw, people)
    ok = True
    p = radar["papers"]
    if p:
        print(f"[papers] {p['total']} found in last {p['days']} days (first try {p['first_total']}) → {len(p['rows'])} shown")
    for name, err in radar["errors"].items():
        ok = False
        print(f"[{name}] FAILED: {err}")
    for person in radar["persons"]:
        if person.get("error") or not person.get("chosen"):
            ok = False
            print(f"[person] {person['query']}: FAILED {person.get('error', 'no match')}")
            continue
        c = person["chosen"]
        print(f"[person] {c['name']} ({c['id']}): {person['total']} new in last {person['days']} days")
        try:
            t = query.person_trend(client, c["id"])
            print(f"[trend · {c['name']}] " + ", ".join(f"{y}:{n}" for y, n in t["counts"].items()))
        except oa.FetchError as e:
            ok = False
            print(f"[trend · {c['name']}] FAILED: {e}")
    if radar["field"]:
        print("[trend · field] " + ", ".join(f"{y}:{n}" for y, n in radar["field"]["counts"].items()))
    print(f"seed files: {len(list(oa.SEED_DIR.glob('*.json')))} in {oa.SEED_DIR}")
    print("DONE" if ok else "SOME STEPS FAILED — run again in a few minutes (saved parts are kept).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

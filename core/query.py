"""검색 엔진: 두 입력칸(Keywords, Key people)을 OpenAlex 조회로 바꾸고 결과 한 덩어리(radar)를 만든다.

규칙
- Keywords: 쉼표로 구분. 쉼표 하나 = 반드시 포함할 주제 하나(AND). 각 주제는 동의어로 자동 확장(OR).
- 신규 논문: 최근 30일에 3편 미만이면 90일 → 365일로 자동 확장.
- Key people: 쉼표로 구분. 후보 중 논문 수가 가장 많은 저자를 자동 선택(화면에서 바꿀 수 있음).
- 트렌드: 키워드 중 하나라도 포함(OR)한 논문으로 넓게 집계 → 연도별 단어가 충분히 모이게.
"""
from __future__ import annotations

import re

from . import openalex as oa

PAPER_WINDOWS = (30, 90, 365)
PEOPLE_WINDOWS = (90, 365)
MIN_PAPERS = 3
N_PAPERS = 10
TREND_YEARS = (2020, 2025)
MAX_KEYWORDS = 5
MAX_PEOPLE = 3

EXAMPLE = {"kw": "MAC scheduler, O-RAN", "people": "Tommaso Melodia"}

# 같은 뜻의 표현. 입력한 표현이 어느 묶음에 속하면 묶음 전체를 OR로 검색한다.
SYNONYMS = [
    ["O-RAN", "Open RAN", "open radio access network"],
    ["MAC scheduler", "MAC scheduling"],
    ["scheduler", "scheduling"],
    ["AI-RAN", "AI RAN"],
    ["RAN intelligent controller", "near-RT RIC"],
    ["traffic prediction", "traffic forecasting"],
    ["cellular traffic prediction", "cellular traffic forecasting",
     "mobile traffic prediction", "mobile traffic forecasting"],
    ["network slicing", "RAN slicing"],
    ["digital twin", "digital twins"],
    ["large language model", "LLM"],
]


def _key(s: str) -> str:
    """대소문자·하이픈·공백·끝의 복수형 s를 무시한 비교용 키."""
    k = re.sub(r"[^a-z0-9]", "", s.lower())
    return k[:-1] if len(k) > 3 and k.endswith("s") else k


_SYN_INDEX = {_key(t): group for group in SYNONYMS for t in group}


def parse_list(text: str, limit: int) -> list[str]:
    out, seen = [], set()
    for part in re.split(r"[,;\n]", text or ""):
        t = re.sub(r"\s+", " ", re.sub(r'["|]', " ", part)).strip()
        if t and _key(t) not in seen:
            seen.add(_key(t))
            out.append(t)
    return out[:limit]


def expand(terms: list[str]) -> list[tuple[str, ...]]:
    groups = []
    for t in terms:
        g = [t] + [s for s in _SYN_INDEX.get(_key(t), []) if _key(s) != _key(t)]
        groups.append(tuple(g))
    return groups


def describe(groups) -> str:
    return " AND ".join("(" + " OR ".join(g) + ")" if len(g) > 1 else g[0] for g in groups)


# ---------- 섹션별 조회 ----------

def find_papers(client: oa.OpenAlex, groups, n: int = N_PAPERS) -> dict:
    first_total = None
    for days in PAPER_WINDOWS:
        rows, total, meta = oa.recent_works(client, groups, days, n)
        if first_total is None:
            first_total = total
        if len(rows) >= MIN_PAPERS or days == PAPER_WINDOWS[-1]:
            return {"rows": rows, "total": total, "days": days, "meta": meta,
                    "widened_from": PAPER_WINDOWS[0] if days != PAPER_WINDOWS[0] else None,
                    "first_total": first_total}
    raise AssertionError("unreachable")


def match_person(client: oa.OpenAlex, name: str, chosen_id: str | None = None) -> dict:
    cands, meta = oa.find_authors(client, name)
    if not cands:
        return {"query": name, "candidates": [], "chosen": None, "meta": meta}
    by_id = {c["id"]: c for c in cands}
    chosen = by_id.get(chosen_id) or max(cands, key=lambda c: c["works"])
    return {"query": name, "candidates": cands, "chosen": chosen, "meta": meta}


def person_papers(client: oa.OpenAlex, author_id: str, n: int = N_PAPERS) -> dict:
    for days in PEOPLE_WINDOWS:
        rows, total, meta = oa.author_works(client, [author_id], days, n)
        if rows or days == PEOPLE_WINDOWS[-1]:
            return {"rows": rows, "total": total, "days": days, "meta": meta}
    raise AssertionError("unreachable")


def trend(client: oa.OpenAlex, groups=None, author_ids=None, stop_terms=(), years=TREND_YEARS) -> dict:
    y0, y1 = years
    counts, m0 = oa.year_counts(client, y0, y1, groups=groups, author_ids=author_ids)
    stops = [_key(s) for s in stop_terms if _key(s)]
    freqs, metas = {}, [m0]
    for y in range(y0, y1 + 1):
        f, m = oa.year_keywords(client, y, groups=groups, author_ids=author_ids)
        metas.append(m)
        freqs[y] = {k: v for k, v in f.items() if not any(s in _key(k) for s in stops)}
    first = next((y for y in range(y0, y1 + 1) if counts[y] > 0), None)
    growth = counts[y1] / counts[first] if first is not None and first != y1 else None
    return {"counts": counts, "freqs": freqs, "rising": rising(freqs, counts),
            "growth": growth, "growth_from": first, "metas": metas}


def rising(freqs: dict, counts: dict, top: int = 6) -> list[dict]:
    """처음 3년 대비 마지막 2년에 논문 비중이 가장 크게 늘어난 키워드."""
    years = sorted(freqs)
    if len(years) < 5:
        return []
    base, recent = years[:3], years[-2:]

    def share(y, k):
        return freqs[y].get(k, 0) / max(counts[y], 1)

    out = []
    for k in set().union(*(freqs[y] for y in recent)):
        b = sum(share(y, k) for y in base) / len(base)
        r = sum(share(y, k) for y in recent) / len(recent)
        out.append({"keyword": k, "base": b, "recent": r, "delta": r - b,
                    "base_label": f"{base[0]}–{base[-1]}", "recent_label": f"{recent[0]}–{recent[-1]}"})
    out.sort(key=lambda x: x["delta"], reverse=True)
    return [x for x in out if x["delta"] > 0][:top]


def field_groups(groups) -> list[tuple[str, ...]]:
    """트렌드용: 모든 키워드 표현을 하나의 OR 묶음으로."""
    terms = [t for g in groups for t in g]
    return [tuple(dict.fromkeys(terms))] if terms else []


def run(client: oa.OpenAlex, kw_text: str, people_text: str, choices: dict | None = None) -> dict:
    """화면 하나에 필요한 결과 전부. 섹션마다 실패를 따로 담는다."""
    choices = choices or {}
    keywords = parse_list(kw_text, MAX_KEYWORDS)
    people = parse_list(people_text, MAX_PEOPLE)
    groups = expand(keywords)
    out = {"keywords": keywords, "people": people, "groups": groups,
           "query_text": describe(groups) if groups else "", "papers": None, "persons": [], "field": None,
           "errors": {}}

    if groups:
        try:
            out["papers"] = find_papers(client, groups)
        except oa.FetchError as e:
            out["errors"]["papers"] = str(e)

    for name in people:
        try:
            p = match_person(client, name, choices.get(name))
            if p["chosen"]:
                p.update(person_papers(client, p["chosen"]["id"]))
            out["persons"].append(p)
        except oa.FetchError as e:
            out["persons"].append({"query": name, "candidates": [], "chosen": None, "error": str(e)})

    if groups:
        try:
            out["field"] = trend(client, groups=field_groups(groups), stop_terms=[t for g in groups for t in g])
        except oa.FetchError as e:
            out["errors"]["field"] = str(e)
    return out


def person_trend(client: oa.OpenAlex, author_id: str) -> dict:
    return trend(client, author_ids=[author_id])

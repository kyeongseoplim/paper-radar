"""검색 엔진: 두 입력칸(Keywords, Key people)을 OpenAlex 조회로 바꾸고 결과 한 덩어리(radar)를 만든다.

규칙
- Keywords: 쉼표로 구분. 쉼표 하나 = 반드시 포함할 주제 하나(AND). 각 주제는 동의어로 자동 확장(OR).
- 신규 논문: 최근 30일에 3편 미만이면 90일 → 365일로 자동 확장.
- Key people: 쉼표로 구분. 후보 중 논문 수가 가장 많은 저자를 자동 선택(화면에서 바꿀 수 있음).
- 트렌드: 키워드 중 하나라도 포함(OR)한 논문으로 넓게 집계 → 연도별 단어가 충분히 모이게.
- 좁히기(선택): 세부 분야(OpenAlex subfield)와 제외 단어. 신규 논문·트렌드에 함께 적용. 비우면 예전과 같다.
  예) "traffic forecasting"은 도로 교통(Transportation) 논문이 대부분 → Computer Networks 분야만 고르면 걸러진다.
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
MAX_SUBFIELDS = 5
MAX_EXCLUDE = 5
PREVIEW_WINDOWS = (7, 30, 90)   # 주간 리포트(n8n/src/build_reports.js)와 같은 창
PREVIEW_N = 5

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


# ---------- 좁히기: 세부 분야, 제외 단어, 더 구체적인 키워드 ----------

def parse_subfields(text: str) -> tuple[str, ...]:
    """URL의 fields=1705,2208 → ("1705", "2208"). 숫자 id만 받는다."""
    ids = [t.strip() for t in re.split(r"[,|\s]+", text or "") if t.strip().isdigit()]
    return tuple(dict.fromkeys(ids))[:MAX_SUBFIELDS]


def parse_exclude(text: str) -> tuple[tuple[str, ...], list[str]]:
    """제외 단어 (쓸 단어, 못 쓰는 항목). OpenAlex 부정 검색은 한 단어만 확실해서 띄어쓴 표현은 돌려보낸다."""
    words, rejected = [], []
    for t in parse_list(text, 99):
        (words if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", t) else rejected).append(t)
    return tuple(words[:MAX_EXCLUDE]), rejected


def make_scope(subfields_text: str = "", exclude_text: str = "") -> tuple[oa.Scope, list[str]]:
    words, rejected = parse_exclude(exclude_text)
    return oa.Scope(parse_subfields(subfields_text), words), rejected


def _words(s: str) -> list[str]:
    return [_key(w) for w in re.split(r"[^A-Za-z0-9]+", s) if w]


def narrower_terms(keywords: list[str], limit: int = 2) -> dict[str, list[str]]:
    """동의어 목록에서 입력 키워드를 품은 더 구체적인 표현. 예) traffic forecasting → mobile traffic forecasting."""
    out = {}
    for kw in keywords:
        w = _words(kw)
        own = {_key(t) for t in _SYN_INDEX.get(_key(kw), [])} | {_key(kw)}
        picks = []
        for group in SYNONYMS:
            for t in group:
                tw = _words(t)
                longer = len(tw) > len(w)
                inside = any(tw[i:i + len(w)] == w for i in range(len(tw) - len(w) + 1))
                if w and longer and inside and _key(t) not in own:
                    picks.append(t)
                    break                      # 한 묶음에서 하나만
        if picks:
            out[kw] = picks[:limit]
    return out


def swap_keyword(kw_text: str, old: str, new: str) -> str:
    """키워드 입력값에서 old 하나를 new로 바꾼 문자열."""
    terms = parse_list(kw_text, 99)
    return ", ".join(new if _key(t) == _key(old) else t for t in terms)


def mix_text(mix: dict | None, top: int = 3) -> str:
    """'Transportation 67% · Computer Networks and Communications 9% · …' (분야 정보가 없으면 빈 문자열)."""
    return " · ".join(f'{f["name"]} {f["share"]:.0%}' for f in ((mix or {}).get("fields") or [])[:top])


# ---------- 섹션별 조회 ----------

def find_papers(client: oa.OpenAlex, groups, n: int = N_PAPERS, scope: oa.Scope = oa.NO_SCOPE,
                windows=PAPER_WINDOWS) -> dict:
    first_total = None
    for days in windows:
        rows, total, meta = oa.recent_works(client, groups, days, n, scope)
        if first_total is None:
            first_total = total
        if len(rows) >= MIN_PAPERS or days == windows[-1]:
            return {"rows": rows, "total": total, "days": days, "meta": meta,
                    "widened_from": windows[0] if days != windows[0] else None,
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


def trend(client: oa.OpenAlex, groups=None, author_ids=None, stop_terms=(), years=TREND_YEARS,
          scope: oa.Scope = oa.NO_SCOPE) -> dict:
    y0, y1 = years
    counts, m0 = oa.year_counts(client, y0, y1, groups=groups, author_ids=author_ids, scope=scope)
    stops = [_key(s) for s in stop_terms if _key(s)]
    freqs, metas = {}, [m0]
    for y in range(y0, y1 + 1):
        f, m = oa.year_keywords(client, y, groups=groups, author_ids=author_ids, scope=scope)
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


def run(client: oa.OpenAlex, kw_text: str, people_text: str, choices: dict | None = None,
        subfields_text: str = "", exclude_text: str = "") -> dict:
    """화면 하나에 필요한 결과 전부. 섹션마다 실패를 따로 담는다."""
    choices = choices or {}
    keywords = parse_list(kw_text, MAX_KEYWORDS)
    people = parse_list(people_text, MAX_PEOPLE)
    groups = expand(keywords)
    scope, rejected = make_scope(subfields_text, exclude_text)
    out = {"keywords": keywords, "people": people, "groups": groups,
           "query_text": describe(groups) if groups else "", "papers": None, "persons": [], "field": None,
           "scope": scope, "exclude_rejected": rejected, "mix": None, "narrower": narrower_terms(keywords),
           "errors": {}}

    if groups:
        try:
            out["papers"] = find_papers(client, groups, scope=scope)
        except oa.FetchError as e:
            out["errors"]["papers"] = str(e)
        try:  # 좁히기 선택지: 조건을 고르기 전 키워드 전체 기준이라 선택해도 목록이 바뀌지 않는다
            out["mix"], _ = oa.subfield_mix(client, groups)
        except oa.FetchError as e:  # 저장본만 쓰는 모드 등. 좁히기 칸만 숨긴다
            out["errors"]["mix"] = str(e)

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
            out["field"] = trend(client, groups=field_groups(groups), stop_terms=[t for g in groups for t in g],
                                 scope=scope)
        except oa.FetchError as e:
            out["errors"]["field"] = str(e)
    return out


def preview(client: oa.OpenAlex, keywords: list[str]) -> dict:
    """첫 로그인 폼 미리보기: 주간 리포트와 같은 규칙(AND·동의어·7→30→90일)으로 최신 논문 몇 편 + 분야 분포."""
    groups = expand(keywords)
    out = {"papers": None, "mix": None, "narrower": narrower_terms(keywords), "errors": {}}
    try:
        out["papers"] = find_papers(client, groups, n=PREVIEW_N, windows=PREVIEW_WINDOWS)
    except oa.FetchError as e:
        out["errors"]["papers"] = str(e)
    try:
        out["mix"], _ = oa.subfield_mix(client, groups)
    except oa.FetchError as e:
        out["errors"]["mix"] = str(e)
    return out


def person_trend(client: oa.OpenAlex, author_id: str) -> dict:
    return trend(client, author_ids=[author_id])

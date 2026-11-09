"""OpenAlex 조회 계층: 요청 간격·재시도, 디스크 캐시(실패 시 저장본 사용), 결과 정리.

저장본 위치
- cache/       실행 중에 받은 결과 (git에 올리지 않음)
- seed_cache/  발표용으로 미리 받아 git에 함께 올리는 결과 (클라우드 재시작에도 남음)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path

import requests

BASE = "https://api.openalex.org"
ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
SEED_DIR = ROOT / "seed_cache"
MIN_INTERVAL = 1.5   # 실시간 요청 사이 최소 간격(초)
MAX_RETRY = 2        # 저장본이 없을 때 429 재시도 횟수
MAX_WAIT = 30        # 429 때 한 번에 기다리는 최대 시간(초)
WORK_TYPES = "article|preprint|conference-paper|review"
SKIP_TYPES = {"dataset", "paratext", "erratum", "retraction", "peer-review", "other", "supplementary-materials"}
SELECT = "id,display_name,publication_date,authorships,primary_location,doi,cited_by_count,type"


class FetchError(RuntimeError):
    pass


def _fname(cache_key: str) -> str:
    return hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:20] + ".json"


def _read(f: Path):
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except (OSError, ValueError):
        return None


class OpenAlex:
    def __init__(self, api_key: str | None = None, offline: bool = False, ttl_hours: float = 12,
                 patient: bool = False, write_dir: Path | None = None, copy_hits: bool = False):
        """patient=False(앱): 저장본이 있으면 429 때 기다리지 않고 바로 저장본을 씀.
        patient=True(prefetch): 저장본이 있어도 재시도하며 끝까지 새로 받으려 함.
        copy_hits=True(prefetch → seed): 저장본을 그대로 쓸 때도 write_dir에 복사해 둠."""
        self.api_key = api_key
        self.offline = offline
        self.ttl = dt.timedelta(hours=ttl_hours)
        self.patient = patient
        self.write_dir = write_dir or CACHE_DIR
        self.copy_hits = copy_hits
        self._last = 0.0
        self._blocked = False  # 한 번 429를 맞으면, 이후 요청은 저장본이 있는 한 바로 저장본 사용

    def _cached(self, cache_key: str):
        """cache/와 seed_cache/ 중 더 최근 것."""
        found = [c for c in (_read(d / _fname(cache_key)) for d in (CACHE_DIR, SEED_DIR)) if c]
        return max(found, key=lambda c: c["saved_at"]) if found else None

    def get(self, path: str, params: dict, cache_key: str):
        """(data, meta) 반환. meta["source"]: live | cache | stale(실시간 실패 후 저장본)."""
        cached = self._cached(cache_key)
        if cached:
            age = dt.datetime.now() - dt.datetime.fromisoformat(cached["saved_at"])
            if self.offline or age < self.ttl:
                if self.copy_hits:
                    self._write(cache_key, path, params, cached["data"], cached["saved_at"])
                return cached["data"], {"source": "cache", "saved_at": cached["saved_at"]}
        if self.offline:
            raise FetchError("Offline mode is on and there is no saved result for this search.")
        if cached and self._blocked and not self.patient:
            return cached["data"], {"source": "stale", "saved_at": cached["saved_at"], "error": "429"}
        try:
            data = self._live(path, params, MAX_RETRY if (self.patient or not cached) else 0)
        except Exception as e:  # 네트워크 오류, 429, 5xx
            if cached:
                return cached["data"], {"source": "stale", "saved_at": cached["saved_at"], "error": str(e)}
            raise FetchError(str(e)) from e
        saved_at = dt.datetime.now().isoformat(timespec="seconds")
        self._write(cache_key, path, params, data, saved_at)
        return data, {"source": "live", "saved_at": saved_at}

    def _write(self, cache_key, path, params, data, saved_at) -> None:
        self.write_dir.mkdir(parents=True, exist_ok=True)
        (self.write_dir / _fname(cache_key)).write_text(
            json.dumps({"saved_at": saved_at, "key": cache_key, "path": path, "params": params, "data": data},
                       ensure_ascii=False), encoding="utf-8")

    def _live(self, path: str, params: dict, retries: int):
        q = dict(params)
        if self.api_key:
            q["api_key"] = self.api_key
        for attempt in range(retries + 1):
            wait = MIN_INTERVAL - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            r = requests.get(f"{BASE}/{path}", params=q, timeout=15)
            if r.status_code == 429:
                if attempt < retries:
                    time.sleep(min(float(r.headers.get("Retry-After", 5)), MAX_WAIT))
                    continue
                self._blocked = True
                raise FetchError("OpenAlex is busy right now (rate limit). Please try again in a minute.")
            r.raise_for_status()
            return r.json()
        raise FetchError("OpenAlex request failed.")


# ---------- 필터 조립 ----------

def kw_filters(groups) -> list[str]:
    """groups: [(동의어, ...), ...] → 그룹끼리 AND, 그룹 안은 OR."""
    return ["title_and_abstract.search:" + "|".join(f'"{t}"' for t in g) for g in groups]


def window(days: int) -> list[str]:
    today = dt.date.today()
    return [f"from_publication_date:{today - dt.timedelta(days=days)}", f"to_publication_date:{today}"]


def gkey(groups) -> str:
    return " & ".join("|".join(t.lower() for t in g) for g in groups)


# ---------- 결과 정리 ----------

def clean(s: str | None) -> str:
    return (s or "").replace("‐", "-").replace("‑", "-").strip()


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z]", "", clean(s).lower())


def parse_work(w: dict) -> dict:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    return {
        "id": w["id"].rsplit("/", 1)[-1],
        "title": clean(w.get("display_name")) or "(untitled)",
        "date": w.get("publication_date") or "",
        "authors": [clean(a["author"]["display_name"]) for a in w.get("authorships", [])],
        "venue": clean(src.get("display_name")),
        "publisher": clean(src.get("host_organization_name")),
        "type": w.get("type") or "",
        "cited": w.get("cited_by_count") or 0,
        "link": w.get("doi") or loc.get("landing_page_url") or w["id"],
    }


def tidy(rows: list[dict], exclude_zenodo: bool = True) -> list[dict]:
    """제목 중복 제거(정식 출판본 우선), Zenodo·데이터셋 등 제외, 최신순."""
    def is_zenodo(r):
        return "zenodo" in r["venue"].lower() or "zenodo" in r["link"].lower()

    rows = [r for r in rows if r["type"] not in SKIP_TYPES]
    if exclude_zenodo:
        rows = [r for r in rows if not is_zenodo(r)]
    seen, out = set(), []
    for r in sorted(rows, key=is_zenodo):  # Zenodo가 아닌 쪽을 먼저 채택
        k = re.sub(r"[^a-z0-9]", "", r["title"].lower())
        if k and k not in seen:
            seen.add(k)
            out.append(r)
    return sorted(out, key=lambda r: r["date"], reverse=True)


# ---------- 조회 함수 ----------

def recent_works(client: OpenAlex, groups, days: int, n: int):
    filt = kw_filters(groups) + window(days) + [f"type:{WORK_TYPES}"]
    params = {"filter": ",".join(filt), "sort": "publication_date:desc",
              "per-page": min(50, n * 2 + 5), "select": SELECT}
    data, meta = client.get("works", params, f"recent|{gkey(groups)}|{days}|{n}")
    rows = tidy([parse_work(w) for w in data["results"]])[:n]
    return rows, data["meta"]["count"], meta


def find_authors(client: OpenAlex, name: str, n: int = 6):
    params = {"search": name, "per-page": n,
              "select": "id,display_name,works_count,cited_by_count,last_known_institutions"}
    data, meta = client.get("authors", params, f"authors|{name.strip().lower()}|{n}")
    cands = []
    for a in data["results"]:
        inst = ", ".join(i.get("display_name", "") for i in (a.get("last_known_institutions") or []))
        cands.append({"id": a["id"].rsplit("/", 1)[-1], "name": clean(a["display_name"]),
                      "inst": inst or "Affiliation unknown", "works": a.get("works_count") or 0,
                      "cited": a.get("cited_by_count") or 0})
    return cands, meta


def author_works(client: OpenAlex, author_ids, days: int, n: int):
    ids = sorted(author_ids)
    filt = ["author.id:" + "|".join(ids)] + window(days)
    params = {"filter": ",".join(filt), "sort": "publication_date:desc",
              "per-page": min(50, n * 2 + 5), "select": SELECT}
    data, meta = client.get("works", params, f"author|{','.join(ids)}|{days}|{n}")
    rows = tidy([parse_work(w) for w in data["results"]])[:n]
    return rows, data["meta"]["count"], meta


def _trend_base(groups=None, author_ids=None) -> tuple[list[str], str]:
    if author_ids:
        ids = sorted(author_ids)
        return ["author.id:" + "|".join(ids)], "a:" + ",".join(ids)
    return kw_filters(groups) + [f"type:{WORK_TYPES}"], "k:" + gkey(groups)


def year_counts(client: OpenAlex, y0: int, y1: int, groups=None, author_ids=None):
    base, key = _trend_base(groups, author_ids)
    params = {"filter": ",".join(base + [f"publication_year:{y0}-{y1}"]), "group_by": "publication_year"}
    data, meta = client.get("works", params, f"years|{key}|{y0}-{y1}")
    counts = {y: 0 for y in range(y0, y1 + 1)}
    for g in data["group_by"]:
        if str(g["key"]).isdigit() and int(g["key"]) in counts:
            counts[int(g["key"])] = g["count"]
    return counts, meta


def year_keywords(client: OpenAlex, year: int, groups=None, author_ids=None):
    base, key = _trend_base(groups, author_ids)
    params = {"filter": ",".join(base + [f"publication_year:{year}"]), "group_by": "keywords.id"}
    data, meta = client.get("works", params, f"kw|{key}|{year}")
    return {clean(g["key_display_name"]): g["count"] for g in data["group_by"]}, meta

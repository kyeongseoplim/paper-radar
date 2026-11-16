"""Search logic (core/query.py), no network.   python -m pytest tests/"""
from core import query


def test_parse_list_trims_dedupes_and_limits():
    assert query.parse_list(' O-RAN , o ran;MAC  scheduler\n"xApp"', 5) == ["O-RAN", "MAC scheduler", "xApp"]
    assert query.parse_list("a, b, c", 2) == ["a", "b"]


def test_expand_adds_synonyms_and_ignores_case_and_plural():
    assert query.expand(["open ran"]) == [("open ran", "O-RAN", "open radio access network")]
    assert query.expand(["MAC schedulers"]) == [("MAC schedulers", "MAC scheduling")]   # "MAC scheduler" = same key
    assert query.expand(["xApp"]) == [("xApp",)]


def test_describe():
    assert query.describe([("a", "b"), ("c",)]) == "(a OR b) AND c"


def test_rising_picks_keywords_whose_share_grew():
    counts = {y: 100 for y in range(2020, 2025)}
    freqs = {y: {"old": 50 if y < 2023 else 10, "new": 0 if y < 2023 else 40} for y in range(2020, 2025)}
    out = query.rising(freqs, counts)
    assert [r["keyword"] for r in out] == ["new"]
    assert round(out[0]["delta"], 2) == 0.4


class FakeClient:
    """Stands in for oa.OpenAlex; recent_works asks for one window at a time."""

    def __init__(self, sizes):
        self.sizes = sizes      # days -> number of rows returned
        self.calls = []

    def get(self, path, params, cache_key):
        days = int(cache_key.split("|")[2])
        self.calls.append(days)
        rows = [{"id": f"https://openalex.org/W{days}{i}", "display_name": f"Paper {days}-{i}",
                 "publication_date": "2026-11-01", "type": "article"} for i in range(self.sizes[days])]
        return {"results": rows, "meta": {"count": len(rows)}}, {"source": "live", "saved_at": "2026-11-16T00:00:00"}


def test_find_papers_widens_until_enough():
    client = FakeClient({30: 1, 90: 5, 365: 9})
    out = query.find_papers(client, [("O-RAN",)])
    assert client.calls == [30, 90]
    assert out["days"] == 90 and out["widened_from"] == 30 and out["first_total"] == 1 and len(out["rows"]) == 5


def test_find_papers_stops_at_first_window_when_enough():
    client = FakeClient({30: 4, 90: 5, 365: 9})
    out = query.find_papers(client, [("O-RAN",)])
    assert client.calls == [30] and out["widened_from"] is None

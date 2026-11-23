"""Narrowing rules (fields, exclude words, more specific keywords), no network.   python -m pytest tests/"""
from core import openalex as oa
from core import query


def test_empty_scope_keeps_old_filters_and_cache_keys():
    assert not oa.NO_SCOPE and oa.NO_SCOPE.filters() == [] and oa.NO_SCOPE.key() == ""


def test_scope_filters_and_key():
    s = oa.Scope(("1705", "2208"), ("road", "Urban"))
    assert s.filters() == ["topics.subfield.id:1705|2208", "title_and_abstract.search:!road|Urban"]
    assert s.key() == "|f:1705,2208|x:road,urban"
    assert oa.Scope(("2208", "1705")).key() == oa.Scope(("1705", "2208")).key()   # order does not matter


def test_parse_subfields_keeps_numeric_ids_only():
    assert query.parse_subfields("1705, 2208,abc,1705") == ("1705", "2208")
    assert query.parse_subfields("") == ()


def test_parse_exclude_rejects_phrases():
    words, rejected = query.parse_exclude("road, vehicle, road traffic, 5G")
    assert words == ("road", "vehicle", "5G") and rejected == ["road traffic"]


def test_narrower_terms_from_synonyms():
    assert query.narrower_terms(["traffic forecasting"]) == {"traffic forecasting": ["cellular traffic forecasting"]}
    assert query.narrower_terms(["scheduler"]) == {"scheduler": ["MAC scheduler"]}
    assert query.narrower_terms(["O-RAN", "xApp"]) == {}           # already specific / unknown


def test_swap_keyword():
    assert query.swap_keyword("Traffic forecasting, 5G", "traffic forecasting", "cellular traffic forecasting") \
        == "cellular traffic forecasting, 5G"


def test_mix_text():
    mix = {"fields": [{"name": "Transportation", "share": 0.67}, {"name": "Computer Networks", "share": 0.09}]}
    assert query.mix_text(mix) == "Transportation 67% · Computer Networks 9%"
    assert query.mix_text(None) == ""


class FakeClient:
    """Records each request; works and group_by answers are canned."""

    def __init__(self):
        self.calls = []

    def get(self, path, params, cache_key):
        self.calls.append((params, cache_key))
        meta = {"source": "live", "saved_at": "2026-11-23T00:00:00"}
        if "group_by" in params:
            return {"meta": {"count": 100}, "group_by": [
                {"key": "https://openalex.org/subfields/3313", "key_display_name": "Transportation", "count": 70},
                {"key": "https://openalex.org/subfields/1705", "key_display_name": "Computer Networks and Communications",
                 "count": 20}]}, meta
        rows = [{"id": f"https://openalex.org/W{i}", "display_name": f"Paper {i}", "publication_date": "2026-11-20",
                 "type": "article"} for i in range(4)]
        return {"results": rows, "meta": {"count": 4}}, meta


def test_find_papers_sends_scope_filters():
    client = FakeClient()
    query.find_papers(client, [("traffic forecasting",)], scope=oa.Scope(("1705",), ("road",)))
    params, key = client.calls[0]
    assert "topics.subfield.id:1705" in params["filter"] and "title_and_abstract.search:!road" in params["filter"]
    assert key.split("|")[2] == "30" and key.endswith("|f:1705|x:road")


def test_subfield_mix_uses_main_field_shares():
    client = FakeClient()
    mix, _ = oa.subfield_mix(client, [("traffic forecasting",)])
    assert client.calls[0][0]["group_by"] == "primary_topic.subfield.id"
    assert [f["id"] for f in mix["fields"]] == ["3313", "1705"]
    assert mix["fields"][0]["share"] == 0.7


def test_preview_uses_weekly_windows():
    client = FakeClient()
    out = query.preview(client, ["traffic forecasting"])
    assert out["papers"]["days"] == 7 and len(out["papers"]["rows"]) == 4
    assert out["narrower"] == {"traffic forecasting": ["cellular traffic forecasting"]}

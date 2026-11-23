"""Author candidates carry topic, field, active years and ORCID to tell same-name authors apart. No network."""
from core import openalex as oa


class FakeClient:
    def __init__(self, results):
        self.results = results
        self.params = None

    def get(self, path, params, cache_key):
        self.params = params
        return {"results": self.results}, {"source": "live", "saved_at": "2026-11-23T00:00:00"}


NETWORKS = {
    "id": "https://openalex.org/A1", "display_name": "Tommaso Melodia", "works_count": 501, "cited_by_count": 20000,
    "last_known_institutions": [{"display_name": "Northeastern University"}],
    "topics": [{"display_name": "Software-Defined Networks and 5G",
                "subfield": {"display_name": "Computer Networks and Communications"}},
               {"display_name": "Cognitive Radio Networks", "subfield": {"display_name": "Computer Networks"}},
               {"display_name": "Third topic", "subfield": {"display_name": "x"}}],
    "counts_by_year": [{"year": 2026, "works_count": 40}, {"year": 2003, "works_count": 2}, {"year": 2010, "works_count": 0}],
    "orcid": "https://orcid.org/0000-0000-0000-0000",
}
SURGEON = {  # same name, other person
    "id": "https://openalex.org/A2", "display_name": "Tommaso Melodia", "works_count": 3, "cited_by_count": 10,
    "last_known_institutions": [], "topics": [{"display_name": "Bladder Cancer Treatments",
                                               "subfield": {"display_name": "Surgery"}}],
    "counts_by_year": [{"year": 1991, "works_count": 1}, {"year": 1996, "works_count": 2}], "orcid": None,
}
OLD_CACHE = {  # saved before topics/years were requested
    "id": "https://openalex.org/A3", "display_name": "Old Entry", "works_count": 5, "cited_by_count": 1,
    "last_known_institutions": [{"display_name": "Somewhere"}],
}


def test_find_authors_asks_for_profile_fields_and_parses_them():
    client = FakeClient([NETWORKS, SURGEON])
    cands, _ = oa.find_authors(client, "Tommaso Melodia")
    assert {"topics", "counts_by_year", "orcid"} <= set(client.params["select"].split(","))
    net, surg = cands
    assert net["topics"] == ["Software-Defined Networks and 5G", "Cognitive Radio Networks"]
    assert net["field"] == "Computer Networks and Communications"
    assert net["years"] == (2003, 2026) and net["orcid"] is True     # a year with 0 works is ignored
    assert surg["field"] == "Surgery" and surg["years"] == (1991, 1996) and surg["inst"] == "Affiliation unknown"


def test_author_caption_tells_same_names_apart():
    net, surg = oa.find_authors(FakeClient([NETWORKS, SURGEON]), "x")[0]
    assert oa.author_caption(net) == ("501 papers · Software-Defined Networks and 5G "
                                      "(Computer Networks and Communications) · active 2003–2026 · ORCID")
    assert oa.author_caption(surg) == "3 papers · Bladder Cancer Treatments (Surgery) · active 1991–1996"


def test_old_saved_results_without_profile_still_work():
    (old,), _ = oa.find_authors(FakeClient([OLD_CACHE]), "x")
    assert old["topics"] == [] and old["years"] is None and old["orcid"] is False
    assert oa.author_caption(old) == "5 papers"

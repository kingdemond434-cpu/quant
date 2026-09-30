"""A refused fetch and uncertified series must not become usable regional data."""
from types import SimpleNamespace

from desks.mt5.research.countries import _declared_data_plane as D


def test_attempt_persistence_and_pit_authority_are_separate(monkeypatch):
    url = "https://example.test/data.csv"
    dataset = SimpleNamespace(name="macro", how_to_fetch=url, source=url,
                              coverage="global", frequency="monthly",
                              publication_lag_days=1, revisions=True, pit_feasible=True)
    monkeypatch.setattr(D.CL, "resolve_pack", lambda _: SimpleNamespace(datasets=[dataset]))
    registry = {"by_url": {url: {"status": "REFUSED", "at": "2026-09-29",
                                 "refusal": "unreachable"}},
                "series": {"old": {"url": url, "pit_authority": False}}}
    monkeypatch.setattr(D, "_registry", lambda: registry)
    report = D.run(code="test", dry_run=True)
    lane = report["lanes"][0]
    assert lane["last_successful_fetch"] is None
    assert lane["last_attempt"] == "2026-09-29"
    assert lane["stored"] == 1 and lane["pit_usable"] == 0
    assert lane["feature_ids"] == []
    assert report["unresolved"] == 1
    registry["by_url"][url]["status"] = "SUCCESS"
    registry["series"]["old"]["pit_authority"] = True
    report = D.run(code="test", dry_run=True)
    assert report["lanes"][0]["feature_ids"] == ["old"]
    assert report["lanes"][0]["last_successful_fetch"] == "2026-09-29"
    assert report["unresolved"] == 0

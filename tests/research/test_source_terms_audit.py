"""Rule E25: every host has a terms/robots/paid verdict, and unknown is never clear."""
from __future__ import annotations

from libs.research import source_terms_audit as sta

TERMS = {"api.gdeltproject.org": {"quote": "unrestricted use"}}
REFUSED = {"www.mql5.com": "Terms 3.7: no automated means"}


def _g(name: str, url: str, **kw):
    return {"name": name, "url": url, "region": "us", **kw}


def _frontier(**outcomes: str):
    return {"vectors": {k: {"outcome": v} for k, v in outcomes.items()}}


def test_unreadable_grounds_are_unmeasured_not_empty() -> None:
    assert sta.audit(None, None, TERMS, REFUSED)["status"] == "UNMEASURED"


def test_clear_needs_terms_a_successful_anonymous_read_and_no_refusal() -> None:
    doc = {"grounds": [_g("gdelt", "https://api.gdeltproject.org/x")]}
    out = sta.audit(doc, _frontier(gdelt="YIELDED"), TERMS, REFUSED)
    assert out["hosts"]["api.gdeltproject.org"]["verdict"] == "CLEAR"


def test_an_unread_host_is_unread_never_clear() -> None:
    doc = {"grounds": [_g("a", "https://example.org/p")]}
    out = sta.audit(doc, _frontier(a="NAMED_ONLY"), TERMS, REFUSED)
    row = out["hosts"]["example.org"]
    assert row["verdict"] == "UNREAD" and row["paid"] == "PAID_UNMEASURED"
    assert row["robots"] == "ROBOTS_UNMEASURED" and out["counts"]["UNREAD"] >= 1


def test_a_refused_host_stays_refused_even_after_a_read() -> None:
    doc = {"grounds": [_g("m", "https://www.mql5.com/en")]}
    out = sta.audit(doc, _frontier(m="YIELDED"), TERMS, REFUSED)
    assert out["hosts"]["www.mql5.com"]["verdict"] == "REFUSED"


def test_a_blocked_read_is_refused_and_alt_urls_are_audited() -> None:
    doc = {"grounds": [_g("b", "https://a.example/x", alt=["https://b.example/y"])]}
    out = sta.audit(doc, _frontier(b="BLOCKED"), TERMS, REFUSED)
    assert out["hosts"]["a.example"]["verdict"] == "REFUSED"
    assert "b.example" in out["hosts"]


def test_the_real_grounds_file_is_audited_without_error() -> None:
    out = sta.current()
    assert out["status"] == "MEASURED" and out["n_hosts"] > 100
    assert sum(out["counts"].values()) == out["n_hosts"]

"""Reviewed-terms records (LAWS 5e act 6): the loader fails closed, the lookup covers a host and
its subdomains, and seeding never fabricates -- every seeded record cites a repository object
whose text IS its quote. Synthetic fixtures; no network."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_records as tr  # noqa: E402
from scripts import seed_terms_records as seed  # noqa: E402


def _rec(host: str, verdict: str = "permits", quote: str = "you may reuse") -> dict[str, Any]:
    ev = {"verdict": verdict, "terms_url": f"https://{host}/terms", "date_read": "2026-11-17",
          "quote": quote, "quote_kind": "verbatim_terms", "source_label": "confirmed",
          "source": {"file": "fixture.py", "object": "EV", "key": host}}
    return {"host": host, "verdict": verdict, "terms_url": ev["terms_url"],
            "date_read": "2026-11-17", "quote": quote, "recorded_by": "fixture",
            "evidence": [ev]}


def _doc(*recs: dict[str, Any]) -> dict[str, Any]:
    return {"records": {r["host"]: r for r in recs}}


# ------------------------------------------------------------------------- loader, fail closed
def test_loader_reads_a_valid_registry(tmp_path: Path) -> None:
    p = tmp_path / "r.json"
    p.write_text(json.dumps(_doc(_rec("example.org"))), encoding="utf-8")
    assert tr.load(p)["example.org"]["verdict"] == "permits"


@pytest.mark.parametrize("text", [None, "", "{not json", "[]", '{"records": []}'])
def test_loader_fails_closed_on_an_unreadable_file(tmp_path: Path, text: str | None) -> None:
    p = tmp_path / "r.json"
    if text is not None:
        p.write_text(text, encoding="utf-8")
    with pytest.raises(tr.TermsRecordsUnreadable):
        tr.load(p)


def test_loader_fails_closed_on_an_invalid_record(tmp_path: Path) -> None:
    bad = _rec("example.org")
    bad["verdict"] = "probably_fine"
    p = tmp_path / "r.json"
    p.write_text(json.dumps(_doc(bad)), encoding="utf-8")
    with pytest.raises(tr.TermsRecordsUnreadable):
        tr.load(p)


def test_validator_names_every_missing_field_and_a_soft_verdict() -> None:
    r = _rec("example.org")
    r["quote"] = ""
    r["evidence"][0]["source"] = {}
    r["evidence"].append({**r["evidence"][0], "verdict": "forbids",
                          "source": {"file": "f", "object": "o"}})
    problems = " ".join(tr.validate(_doc(r)))
    assert "no quote" in problems
    assert "source must name" in problems
    assert "most refusing" in problems          # verdict permits but a reading forbids


def test_validator_rejects_an_unnormalised_key() -> None:
    r = _rec("www.example.org")
    assert any("normalised host" in p for p in tr.validate(_doc(r)))


# ------------------------------------------------------------------------------ the lookup
def test_lookup_covers_host_and_subdomain_and_prefers_the_most_specific() -> None:
    recs = _doc(_rec("example.org"), _rec("api.example.org", "forbids", "no bots"))["records"]
    assert tr.terms_record_for("https://example.org/x", recs)["host"] == "example.org"
    assert tr.terms_record_for("https://www.example.org/x", recs)["host"] == "example.org"
    assert tr.terms_record_for("https://deep.sub.example.org/", recs)["host"] == "example.org"
    assert tr.terms_record_for("https://v2.api.example.org/q", recs)["verdict"] == "forbids"
    assert tr.terms_record_for("https://EXAMPLE.org.:443/", recs)["host"] == "example.org"


def test_lookup_never_infers_a_record_for_a_sibling_or_lookalike() -> None:
    recs = _doc(_rec("a.example.org"))["records"]
    assert tr.terms_record_for("https://b.example.org/", recs) is None
    assert tr.terms_record_for("https://example.org/", recs) is None
    assert tr.terms_record_for("https://xa.example.org/", recs) is None
    assert tr.terms_record_for("not a url", recs) is None


def test_record_key_normalises() -> None:
    assert tr.record_key("https://WWW.Example.ORG./p") == "example.org"
    assert tr.record_key("www.example.org") == "example.org"
    assert tr.record_key("www.com") == "www.com"
    assert tr.record_key("") is None


# ------------------------------------------------------------------ seeding never fabricates
def test_the_committed_registry_loads_and_is_what_the_held_evidence_seeds() -> None:
    held = tr.load()
    assert held, "the committed registry is empty"
    assert seed.build()["records"] == json.loads(
        tr.REGISTRY.read_text(encoding="utf-8"))["records"]


def test_every_seeded_record_cites_an_object_whose_text_is_its_quote() -> None:
    for host, rec in tr.load().items():
        for ev in rec["evidence"]:
            assert seed.resolve(ev["source"]) == ev["quote"], (host, ev["source"])
        assert rec["quote"] in [e["quote"] for e in rec["evidence"]]
        assert rec["verdict"] == max((e["verdict"] for e in rec["evidence"]),
                                     key=tr.SEVERITY.__getitem__)


def test_seeding_keeps_settled_refusals_and_skips_third_party_terms_hosts() -> None:
    held = tr.load()
    for host in ("stlouisfed.org", "yahoo.com", "comtrade.un.org", "archive.org",
                 "youtube.com", "theice.com", "cboe.com", "dukascopy.com"):
        assert held[host]["verdict"] == "forbids", host
    for host in seed.THIRD_PARTY_TERMS_HOSTS:
        assert host not in held
    # a reading the desk has not settled is listed, never turned into a verdict
    assert any(n.get("source_label") == "to_confirm" for n in seed.build()["not_seeded"])


def test_unreadable_notes_never_become_permits() -> None:
    for rec in tr.load().values():
        for ev in rec["evidence"]:
            if ev["quote_kind"] == "not_readable_note":
                assert ev["verdict"] == "unreadable"

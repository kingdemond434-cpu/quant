"""Reviewed-terms records (LAWS 5e act 6): the loader fails closed, the lookup covers a host and
its subdomains, and seeding never fabricates -- every seeded record cites a repository object
whose text IS its quote. Synthetic fixtures; no network."""
from __future__ import annotations

import ast
import hashlib
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


def _write(d: Path, doc: dict[str, Any]) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for name, text in tr.split(doc).items():
        (d / name).write_text(text, encoding="utf-8")
    return d


# ------------------------------------------------------------------------- loader, fail closed
def test_loader_reads_a_valid_registry(tmp_path: Path) -> None:
    d = _write(tmp_path / "r", _doc(_rec("example.org"), _rec("ecb.europa.eu")))
    assert sorted(p.name for p in d.iterdir()) == ["_meta.json", "e.json"]
    assert tr.load(d)["example.org"]["verdict"] == "permits"


@pytest.mark.parametrize("text", [None, "", "{not json", "[]", '{"records": []}',
                                  '{"records": {}, "extra": 1}'])
def test_loader_fails_closed_on_an_unreadable_group_file(tmp_path: Path,
                                                         text: str | None) -> None:
    d = _write(tmp_path / "r", _doc(_rec("example.org"), _rec("other.org")))
    if text is None:
        (d / "e.json").unlink()
    else:
        (d / "e.json").write_text(text, encoding="utf-8")
    # the other file is fine, and it is NOT served alone: the registry never silently shrinks
    with pytest.raises(tr.TermsRecordsUnreadable):
        tr.load(d)


@pytest.mark.parametrize("meta", [None, "{", "[]", '{"files": []}'])
def test_loader_fails_closed_on_an_absent_or_broken_meta(tmp_path: Path,
                                                         meta: str | None) -> None:
    d = _write(tmp_path / "r", _doc(_rec("example.org")))
    if meta is None:
        (d / tr.META).unlink()
    else:
        (d / tr.META).write_text(meta, encoding="utf-8")
    with pytest.raises(tr.TermsRecordsUnreadable):
        tr.load(d)


def test_loader_fails_closed_on_an_absent_directory(tmp_path: Path) -> None:
    with pytest.raises(tr.TermsRecordsUnreadable):
        tr.load(tmp_path / "nowhere")


def test_loader_fails_closed_on_a_file_meta_does_not_name(tmp_path: Path) -> None:
    d = _write(tmp_path / "r", _doc(_rec("example.org")))
    (d / "z.json").write_text(json.dumps({"records": {}}), encoding="utf-8")
    with pytest.raises(tr.TermsRecordsUnreadable, match="not named"):
        tr.load(d)


def test_the_same_host_in_two_files_refuses_that_host(tmp_path: Path) -> None:
    d = _write(tmp_path / "r", _doc(_rec("example.org"), _rec("other.org")))
    meta = json.loads((d / tr.META).read_text("utf-8"))
    (d / "o.json").write_text(json.dumps({"records": {"other.org": _rec("other.org"),
                                                      "example.org": _rec("example.org")}}),
                              encoding="utf-8")
    meta["files"]["o.json"] = 2
    (d / tr.META).write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(tr.TermsRecordsUnreadable) as exc:
        tr.load(d)
    assert "example.org" in exc.value.hosts


def test_a_record_with_no_host_or_in_the_wrong_group_refuses(tmp_path: Path) -> None:
    d = _write(tmp_path / "r", _doc(_rec("example.org")))
    rec = _rec("example.org")
    del rec["host"]
    (d / "e.json").write_text(json.dumps({"records": {"example.org": rec}}), encoding="utf-8")
    with pytest.raises(tr.TermsRecordsUnreadable) as exc:
        tr.load(d)
    assert exc.value.hosts == ("example.org",)
    d2 = _write(tmp_path / "r2", _doc(_rec("example.org")))
    (d2 / "e.json").rename(d2 / "x.json")
    meta = json.loads((d2 / tr.META).read_text("utf-8"))
    meta["files"] = {"x.json": 1}
    (d2 / tr.META).write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(tr.TermsRecordsUnreadable, match=r"belongs in e\.json"):
        tr.load(d2)


def test_a_count_that_disagrees_with_meta_refuses(tmp_path: Path) -> None:
    d = _write(tmp_path / "r", {**_doc(_rec("example.org")), "counts": {"records": 2}})
    with pytest.raises(tr.TermsRecordsUnreadable, match="counts 2"):
        tr.load(d)


def test_loader_fails_closed_on_an_invalid_record(tmp_path: Path) -> None:
    bad = _rec("example.org")
    bad["verdict"] = "probably_fine"
    d = _write(tmp_path / "r", _doc(bad))
    with pytest.raises(tr.TermsRecordsUnreadable):
        tr.load(d)


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
    assert seed.build()["records"] == held
    assert seed.main(["--check"]) == 0


# ------------------------------------------------- the split (Governance ruling 2026-11-18)
#: THE UNION PROOF, by hash rather than by `git show`: the single file this directory replaced
#: (libs/data/terms_records.json at dfd2e55368) hashed canonically (sort_keys, no whitespace,
#: UTF-8). A test that read git history would fail on a shallow clone; a hash does not. The
#: first is the whole document (records AND its description: _doc, schema, seeded_by, counts,
#: not_seeded); the second is the record set alone. A migration proof for the PR that split the
#: file: when a session re-seeds new evidence these hashes change by design, and the test goes.
_SINGLE_FILE_SHA256 = "3211854a327fa7e47b5d44e3197bda45cd15cb5aa5b07c0cb1be3b13b0845c62"
_SINGLE_FILE_RECORDS_SHA256 = "818408e11c179a7cf1219c412674011d79591b4a613c3776ec36eec14a4d2069"


def _canonical_sha(obj: Any) -> str:
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_the_split_files_union_to_the_single_file_record_for_record() -> None:
    whole = tr.load_document()
    assert _canonical_sha(whole["records"]) == _SINGLE_FILE_RECORDS_SHA256
    assert _canonical_sha(whole) == _SINGLE_FILE_SHA256
    assert len(whole["records"]) == whole["counts"]["records"] == 61


def _review_part_chars() -> int:
    src = (ROOT / "ops" / "release" / "independent_review.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "PART_CHARS" for t in node.targets):
            return int(ast.literal_eval(node.value))
    raise AssertionError("PART_CHARS is no longer a constant in independent_review.py")


def test_the_size_limit_mirrors_the_independent_review() -> None:
    assert _review_part_chars() == tr.MAX_FILE_CHARS


def test_every_registry_file_is_a_hunk_the_review_reads_whole() -> None:
    files = sorted(tr.REGISTRY.iterdir())
    assert files and tr.META in {p.name for p in files}
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert tr.hunk_chars(text) <= tr.MAX_FILE_CHARS, (p.name, tr.hunk_chars(text))


def test_each_record_lives_in_its_group_file() -> None:
    for p in sorted(tr.REGISTRY.iterdir()):
        if p.name != tr.META:
            for host in json.loads(p.read_text("utf-8"))["records"]:
                assert tr.group_file(host) == p.name


def test_the_seeder_refuses_a_file_past_the_limit(tmp_path: Path, monkeypatch,
                                                  capsys) -> None:
    big = _rec("example.org", quote="x" * tr.MAX_FILE_CHARS)
    big["evidence"][0]["quote"] = big["quote"]
    monkeypatch.setattr(seed, "build", lambda: {"counts": {"records": 1}, **_doc(big)})
    monkeypatch.setattr(tr, "REGISTRY", tmp_path / "terms_records")
    assert seed.main([]) == 2
    assert "REFUSED" in capsys.readouterr().err
    assert not (tmp_path / "terms_records").exists()     # nothing was written


def test_the_seeder_writes_each_record_to_its_group_and_drops_stale_files(
        tmp_path: Path, monkeypatch) -> None:
    d = tmp_path / "terms_records"
    _write(d, _doc(_rec("zeta.org")))
    monkeypatch.setattr(seed, "build", lambda: {"counts": {"records": 2},
                                                **_doc(_rec("alpha.org"), _rec("beta.org"))})
    monkeypatch.setattr(tr, "REGISTRY", d)
    assert seed.main([]) == 0
    assert sorted(p.name for p in d.iterdir()) == ["_meta.json", "a.json", "b.json"]
    assert set(tr.load(d)) == {"alpha.org", "beta.org"}
    assert seed.main(["--check"]) == 0


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

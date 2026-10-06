"""DOC -> CODE citations: only a present-tense existence claim (line-cited or asserted-live) can
break, a negating phrase in the same sentence exempts it with that phrase as the reason, fenced
blocks are quoted material, and an unreadable document stays in the denominator."""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.ops import doc_citations as dc

ROOTS = frozenset({"scripts", "libs", "docs"})


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, "utf-8")
    return p


def test_forms_line_cited_asserted_live_and_mentioned() -> None:
    text = "\n".join([
        "See libs/a/real.py:12 for the rule.",
        "Recurrence detector: scripts/check_axis_clocks.py (daily cron) pages the cycle",
        "Background reading: libs/a/other.py is interesting.",
        "Range libs/a/range.py:45-52 and en dash libs/a/dash.py:3\u20139.",
    ])
    cits = dc.extract(text, "docs/x.md", ROOTS)
    forms = {c.path: c.form for c in cits}
    assert forms == {"libs/a/real.py": dc.LINE_CITED,
                     "scripts/check_axis_clocks.py": dc.ASSERTED_LIVE,
                     "libs/a/other.py": dc.MENTIONED,
                     "libs/a/range.py": dc.LINE_CITED, "libs/a/dash.py": dc.LINE_CITED}
    assert {c.path: c.line for c in cits}["libs/a/other.py"] == 3
    assert all(c.asserts_existence for c in cits if c.form != dc.MENTIONED)


def test_negation_exempts_with_the_documents_own_phrase() -> None:
    text = ("scripts/check_axis_clocks.py (daily cron) never existed in any tree\n"
            "scripts/pdf_text.py is mentioned but does not exist\n")
    a, b = dc.extract(text, "docs/fix.md", ROOTS)
    assert a.form == dc.ASSERTED_LIVE and a.exempt_reason == "never existed"
    assert not a.asserts_existence
    # a MENTIONED path never carries an exemption: there is no claim to exempt
    assert b.form == dc.MENTIONED and b.exempt_reason == ""


def test_foreign_roots_placeholders_elisions_and_fences_are_skipped() -> None:
    text = "\n".join([
        "foreign/thing.py:3 and scripts/X.py:4 and scripts/foo.py (hourly)",
        "libs/.../knowledge_engine.py:9 is a human elision",
        "data/ledger.json:4 is not code",
        "```",
        "libs/quoted/inside.py:1 (daily cron)",
        "```",
        "~~~",
        "libs/unterminated/fence.py:2",
    ])
    assert dc.extract(text, "docs/x.md", ROOTS) == []


def test_live_marker_must_sit_within_the_window() -> None:
    far = "libs/a/mod.py" + " " * (dc.LIVE_WINDOW + 5) + "(hourly)"
    near = "libs/a/mod.py is enforced by the gate"
    assert dc.extract(far, "d", ROOTS)[0].form == dc.MENTIONED
    assert dc.extract(near, "d", ROOTS)[0].form == dc.ASSERTED_LIVE


def test_resolve_records_tracked_then_disk_then_unresolved(tmp_path: Path) -> None:
    _write(tmp_path / "libs" / "a" / "disk.py", "x = 1\n")
    cits = dc.extract("libs/a/tracked.py:1\nlibs/a/disk.py:1\nlibs/a/gone.py:1\n", "d",
                      ROOTS)
    out = {c.path: (c.resolved, c.resolved_by)
           for c in dc.resolve(cits, tmp_path, frozenset({"libs/a/tracked.py"}))}
    assert out == {"libs/a/tracked.py": (True, "tracked"), "libs/a/disk.py": (True, "disk"),
                   "libs/a/gone.py": (False, "")}


def test_repo_roots_discovers_directories_and_skips_tooling(tmp_path: Path) -> None:
    for d in ("libs", "scripts", ".git", "node_modules", ".claude"):
        (tmp_path / d).mkdir()
    _write(tmp_path / "README.md", "x")
    assert dc.repo_roots(tmp_path) == frozenset({"libs", "scripts"})
    assert dc.repo_roots(tmp_path / "absent") == frozenset()


def test_scan_and_summarise_end_to_end(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "real.py", "pass\n")
    _write(tmp_path / "libs" / "untracked.py", "pass\n")
    _write(tmp_path / "docs" / "good.md",
           "scripts/real.py:1 holds it; libs/untracked.py (hourly) runs it\n")
    _write(tmp_path / "docs" / "sub" / "bad.md",
           "scripts/ghost_rail.py (daily cron) pages the cycle\n"
           "scripts/old_rail.py (daily cron) was retired\n"
           "scripts/just_named.py appears in prose\n")
    (tmp_path / "docs" / "binary.md").write_bytes(b"\xff\xfe\x00bad")
    results = dc.scan(tmp_path, frozenset({"scripts/real.py"}))
    assert [r.doc for r in results] == ["docs/binary.md", "docs/good.md", "docs/sub/bad.md"]
    assert results[0].read is False and "UnicodeDecodeError" in results[0].error
    s = dc.summarise(results)
    assert (s["n_docs_found"], s["n_docs_read"], s["n_docs_unreadable"]) == (3, 2, 1)
    assert s["n_citations"] == 5 and s["n_mentioned"] == 1
    assert s["n_line_cited"] == 1 and s["n_asserted_live"] == 3
    assert s["n_asserted"] == 3 and s["n_exempt"] == 1 and s["n_broken"] == 1
    assert s["n_untracked_resolved"] == 1
    (broken,) = s["broken"]
    assert broken["path"] == "scripts/ghost_rail.py" and broken["line"] == 1
    assert "asserts `scripts/ghost_rail.py` exists" in broken["repair"]
    assert s["exempt"][0]["exempt_reason"] == "retired"
    assert s["unreadable"][0]["doc"] == "docs/binary.md"


def test_scan_without_docs_is_empty_not_an_error(tmp_path: Path) -> None:
    assert dc.scan(tmp_path, frozenset()) == []
    assert dc.summarise([])["n_docs_found"] == 0


@pytest.mark.parametrize("stem", ["x", "foo", "your_tool", "my_thing", "example"])
def test_placeholder_stems(stem: str) -> None:
    assert dc.extract(f"scripts/{stem}.py:1", "d", ROOTS) == []

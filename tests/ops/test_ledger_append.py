"""LEDGER_APPEND (ops/release/authority/ledger_append.py): one pinned refusal per condition.

Governance 20:12Z and Auditor 20:17Z/20:18Z, 2026-11-17: the Auditor's ADOPT rows reach LIVE by a
PR the merger App opens, and the authority recomputes every row from GitHub itself."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


la = _load("t_ledger_append", ROOT / "ops/release/authority/ledger_append.py")
pol = _load("t_ledger_policy", ROOT / "ops/release/authority/policy.py")

C = "d020cadbffb07f8e170fcdd6f27b1ced49f4e997"
PR = 1254
MERGER = "quant-merger[bot]"
REPORT = f"reports/audit/2026-11-17/adopt_clear_pr{PR}_{C[:9]}.md"
TWIN = REPORT[:-3] + ".row.json"
BODY = b"# audit report\n"
PATHS = {"desks/mt5/research/event_states.py": "a" * 40, "desks/mt5/research/gone.py": None}
BASE = b'{"commit": "' + b"e" * 40 + b'", "verdict": "CLEAR"}\n'


def _row(**over: Any) -> bytes:
    d = {"commit": C, "verdict": "CLEAR", "report": REPORT,
         "report_sha256": hashlib.sha256(BODY).hexdigest(), "paths": dict(PATHS)}
    d.update(over)
    return json.dumps(d).encode()


class World:
    def __init__(self) -> None:
        self.row = _row()
        self.files: list[dict[str, Any]] = [
            {"filename": la.LEDGER, "status": "modified"},
            {"filename": REPORT, "status": "added"}, {"filename": TWIN, "status": "added"}]
        self.opener = MERGER
        self.base: bytes | None = BASE
        self.head: bytes | None = None
        self.twin: bytes | None = None
        self.body: bytes | None = BODY
        self.target: dict[str, Any] | None = {
            "head_ref": "claude/futures-state",
            "files": {"desks/mt5/research/event_states.py": "modified",
                      "desks/mt5/research/gone.py": "removed"}}
        self.blobs: dict[str, tuple[bool, str | None]] = {
            "desks/mt5/research/event_states.py": (True, "a" * 40),
            "desks/mt5/research/gone.py": (True, None)}
        self.verdicts: list[dict[str, str]] | None = [
            {"verdict": "CLEAR", "sha": C, "at": "2026-11-17T20:07:00Z", "by": "kingdemond434-cpu"}]
        self.excluded: tuple[str, ...] | None = (".github/workflows/*", "libs/ops/release.py")

    def run(self) -> list[str]:
        head = self.head if self.head is not None else (self.base or b"") + self.row + b"\n"
        twin = self.twin if self.twin is not None else self.row
        reads = {REPORT: self.body, TWIN: twin}
        return la.check(self.files, self.opener, MERGER, self.base, head, reads.get,
                        lambda n, c: self.target if (n, c) == (PR, C) else None,
                        lambda c, p: self.blobs.get(p, (False, None)),
                        lambda n: self.verdicts if n == PR else None, self.excluded)


def _refused(w: World, needle: str) -> None:
    bad = w.run()
    assert any(needle in b for b in bad), bad


def test_a_verbatim_auditor_row_passes() -> None:
    assert World().run() == []


def test_c9_only_the_merger_app_may_open_it() -> None:
    w = World()
    w.opener = "kingdemond434-cpu"
    _refused(w, "not the merger App")
    assert la.check(w.files, MERGER, None, BASE, BASE, lambda n: None, lambda n, c: None,
                    lambda c, p: (False, None), lambda n: [], ())[0].startswith("opened by")


def test_c2_an_edited_or_deleted_row_is_not_append_only() -> None:
    w = World()
    w.head = BASE.replace(b"CLEAR", b"HOLD!") + w.row + b"\n"
    _refused(w, "not append-only")
    w = World()
    w.head = w.row + b"\n"
    _refused(w, "not append-only")
    w = World()
    w.head = BASE + w.row
    _refused(w, "newline")
    w = World()
    w.head = BASE + json.dumps(json.loads(w.row), indent=1).encode() + b"\n"
    _refused(w, "single-line JSON")


def test_c3_any_other_path_or_a_changed_report_refuses() -> None:
    for extra in ({"filename": "libs/x.py", "status": "added"},
                  {"filename": "reports/audit/2026-11-14/old.md", "status": "modified"},
                  {"filename": REPORT.replace("pr1254", "pr9"), "status": "modified"},
                  {"filename": "reports/audit/x.md", "status": "renamed",
                   "previous_filename": "reports/audit/y.md"}):
        w = World()
        w.files.append(extra)
        assert w.run(), extra
    w = World()
    w.files = w.files[1:]
    _refused(w, "is not modified")


def test_c8_row_and_report_must_be_the_files_the_pr_adds() -> None:
    w = World()
    w.twin = _row(paths={"desks/mt5/research/event_states.py": "a" * 40})
    _refused(w, "byte-identical")
    w = World()
    w.body = b"another report\n"
    _refused(w, "report_sha256")
    w = World()
    w.files = [f for f in w.files if f["filename"] != TWIN]
    _refused(w, "does not add both")
    w = World()
    w.row = _row(report=REPORT.replace(C[:9], "0" * 9))
    _refused(w, "is not adopt_clear_pr")


def test_c10_the_authority_recomputes_every_path_and_blob() -> None:
    w = World()
    w.blobs["desks/mt5/research/event_states.py"] = (True, "b" * 40)
    _refused(w, "the row says")
    w = World()
    w.row = _row(paths={**PATHS, "desks/mt5/research/extra.py": "c" * 40})
    _refused(w, "does not change it")
    w = World()
    w.blobs["desks/mt5/research/gone.py"] = (True, "d" * 40)    # null, yet the commit has it
    _refused(w, "the row says None")


def test_c11_the_newest_verdict_for_that_commit_must_be_clear() -> None:
    w = World()
    assert w.verdicts is not None
    w.verdicts.append({"verdict": "HOLD", "sha": C, "at": "2026-11-17T20:10:00Z", "by": "x"})
    w.verdicts.append({"verdict": "CLEAR", "sha": "f" * 40, "at": "2026-11-17T20:11:00Z",
                       "by": "x"})
    _refused(w, "is not CLEAR")
    w = World()
    w.verdicts = []
    _refused(w, "is not CLEAR")


def test_c12_excluded_paths_and_seal_carriers_are_forged_by_definition() -> None:
    for p in (".github/workflows/ci.yml", "ops/release/authority/policy.py", "ops/box/x.ps1",
              "ops/money_closure.txt", "libs/ops/release.py", la.LEDGER,
              "desks/mt5/scripts/Adopt-Release.ps1"):
        w = World()
        w.row = _row(paths={p: "a" * 40})
        assert w.target is not None
        w.target["files"][p] = "modified"
        w.blobs[p] = (True, "a" * 40)
        _refused(w, "excluded path")
    w = World()
    assert w.target is not None
    w.target["head_ref"] = "claude/seal-carrier-x"
    _refused(w, "seal carrier")


def test_c13_one_row_per_pr_and_commit() -> None:
    w = World()
    w.base = BASE + w.row + b"\n"
    _refused(w, "already has a row")
    w = World()
    w.head = BASE + w.row + b"\n" + w.row + b"\n"
    _refused(w, "two rows")


def test_c14_seal_rows_are_not_this_class() -> None:
    w = World()
    w.files.append({"filename": la.SEAL_LEDGER, "status": "modified"})
    _refused(w, "SEAL_CLEARS")


def test_c5_anything_unreadable_refuses() -> None:
    w = World()
    w.verdicts = None
    _refused(w, "cannot be read")
    w = World()
    w.target = None
    _refused(w, "cannot be read")
    w = World()
    w.blobs = {}
    _refused(w, "cannot be read")
    w = World()
    w.body = None
    _refused(w, "cannot be read")
    w = World()
    w.base = None
    _refused(w, "cannot be read")
    w = World()
    w.excluded = None
    _refused(w, "fail closed")


def _classify(ledger: list[str] | None) -> tuple[str, list[str]]:
    return pol.classify([la.LEDGER, REPORT], "AUTO", {"root_files": []}, lambda n: None,
                        lambda n: None, ledger=ledger)


def test_a_ledger_change_is_ledger_append_or_root_never_auto() -> None:
    assert _classify([])[0] == "LEDGER_APPEND"
    assert _classify(None)[0] == "ROOT"
    cls, why = _classify(["row 1: forged"])
    assert cls == "ROOT" and "forged" in why[0]
    assert pol.CLEAR_LEDGERS == (la.LEDGER, la.SEAL_LEDGER)
    assert pol.required_jobs("LEDGER_APPEND", ("smoke",), ("full",), {}) == ("smoke",)
    f = {"open": True, "same_repo": True, "base_ok": True, "cls": "LEDGER_APPEND",
         "patch_id": "p", "checks": ("pass", "ok"), "fresh": True}
    assert pol.decide(f)[0] == "CLEAR"
    assert pol.decide({**f, "hold": "AUDIT HOLD x"})[0] == "HOLD"

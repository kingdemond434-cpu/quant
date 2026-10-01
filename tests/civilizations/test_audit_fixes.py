"""The #161 audit's NOT READY list, pinned: licence enforcement, the if/else regime switch, fail
closed grammar checks, the Renaissance scope, pacing on the judge's backlog, the D36 own-cells
rule, the ROI fetch plan and the knowledge graph as the outcome ledgers' reader."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.civilizations import backpressure as BP
from libs.civilizations import expression as E
from libs.civilizations import licence as LIC
from libs.research import alpha_dsl as D
from libs.research import alpha_grammar as AG

ROOT = Path(__file__).resolve().parents[2]

MIT = "MIT License\n\nCopyright (c) 2021 Jane Doe\n\nPermission is hereby granted, free of charge"
GPL = "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007"
CODE = "def momentum(close):\n    return ts_rank(close, 10) - RSI(14)\n"


# ------------------------------------------------------------------------------ licence
def test_licence_detection_and_permissive_set() -> None:
    assert LIC.detect(MIT) == "MIT" and LIC.detect(GPL) == "GPL-3.0"
    assert LIC.detect("all rights reserved") == "NOASSERTION"
    assert LIC.is_permissive("MIT") and not LIC.is_permissive("GPL-3.0")
    assert not LIC.is_permissive("NOASSERTION") and not LIC.is_permissive(None)


def test_permissive_file_is_kept_with_its_notice() -> None:
    body, meta = LIC.keep("a.py", CODE, "MIT", MIT, "o/r")
    assert body.startswith("[licence MIT: Copyright (c) 2021 Jane Doe")
    assert CODE in body and meta == {"licence": "MIT", "licence_permissive": True}


def test_gpl_and_unlicensed_files_keep_metadata_only_never_the_text() -> None:
    for spdx in ("GPL-3.0", "NOASSERTION"):
        body, meta = LIC.keep("a.py", CODE, spdx, GPL, "o/r")
        assert meta["metadata_only"] is True and not meta["licence_permissive"]
        assert "return ts_rank" not in body and "text not kept" in body
        # the facts the extractors need survive as a description of our own
        assert "momentum" in body and "RSI(14)" in body


def test_notebook_outputs_are_stripped_for_every_licence() -> None:
    nb = json.dumps({"cells": [{"cell_type": "code", "source": ["x = ts_rank(close, 10)\n"],
                                "outputs": [{"data": {"text/plain": "SECRET TABLE"}}]}]})
    body, _ = LIC.keep("n.ipynb", nb, "MIT", MIT, "o/r")
    assert "ts_rank" in body and "SECRET TABLE" not in body


def test_data_files_and_weights_are_out_of_reach() -> None:
    from libs.civilizations import fetchers as F
    for p in ("x.json", "x.jsonl", "x.txt", "x.tsv", "x.csv", "m.pt", "a.zip", "w.h5"):
        assert any(Path(p).match(g) for g in F.DATA_EXCLUDE), p
    ignored = (ROOT / ".gitignore").read_text("utf-8")
    assert "desks/mt5/data/civilizations/" in ignored


# ---------------------------------------------------------------------- if/else switch
def test_if_pos_is_a_typed_exact_regime_switch() -> None:
    t = ["if_pos", ["sign", "ret"], "ret", ["neg", "ret"]]
    assert AG.is_valid(t) and AG.type_of(t) == "RETURN"
    assert AG.is_valid(["if_pos", ["zscore", "ret", 24], "ret", 0])
    assert not AG.is_valid(["if_pos", 0, "ret", "ret"])          # literal gate
    assert not AG.is_valid(["if_pos", "ret", 0, 0])              # both branches constant
    assert "if_pos" not in AG.OPERATORS                          # never sampled blindly
    idx = pd.date_range("2026-01-01", periods=6, freq="h")
    ret = pd.Series([0.1, -0.2, 0.3, -0.4, 0.0, 0.5], index=idx)
    frames = {"ret": ret, "close": ret.cumsum(), "open": ret.cumsum(), "high": ret.cumsum(),
              "low": ret.cumsum()}
    out = AG.evaluate(t, frames)
    assert np.allclose(out.to_numpy(), np.where(ret > 0, ret, -ret))


def test_alpha101_style_ternary_transpiles_exactly() -> None:
    g = D.transpile("x", "((0 < ts_min(delta(close, 1), 5)) ? delta(close, 1) : "
                         "(-1 * delta(close, 1)))")
    assert g.status == "TESTABLE"
    assert any("exact" in t for t in g.translations)


def test_grammar_check_fails_closed(monkeypatch: Any) -> None:
    assert E.grammar_valid(["no_such_op", "close"])[0] is False
    import libs.research as pkg
    monkeypatch.delattr(pkg, "alpha_grammar", raising=False)
    monkeypatch.setitem(sys.modules, "libs.research.alpha_grammar", None)
    ok, why = E.grammar_valid(["zscore", "ret", 24])       # valid, but nobody could ask
    assert ok is False and "not importable" in why


# ------------------------------------------------------------------------ RenTec scope
def test_renaissance_scope_keeps_papers_patents_courts_interviews_only() -> None:
    from libs.civilizations.resident import _in_scope
    meta = {"scope_hosts": ["arxiv.org", "patents.google.com", "courtlistener.com"],
            "scope_title_regex": r"(?i)\binterview\b"}
    assert _in_scope(meta, "https://arxiv.org/abs/1", "")
    assert _in_scope(meta, "https://www.courtlistener.com/x", "")
    assert _in_scope(meta, "https://example.com/p", "An interview with Jim Simons")
    assert not _in_scope(meta, "https://someblog.com/rentec-secret", "Medallion leaked")
    assert _in_scope({}, "https://anything", "")


# ---------------------------------------------------------------------------- pacing
def _load(unjudged: int | None, cap: float | None = 24_000,
          draining: bool | None = False) -> BP.JudgeLoad:
    return BP.JudgeLoad(unjudged, None if cap is None else int(cap), draining)


def test_release_pauses_while_the_judge_backlog_grows(tmp_path: Path) -> None:
    hist = tmp_path / "h.txt"
    assert BP.backlog_growing(hist, _load(1000), now=0.0) is None          # no old reading
    assert BP.backlog_growing(hist, _load(1500), now=4000.0) is True
    assert BP.release_budget(_load(1500), growing=True) == 0
    assert BP.release_budget(_load(1500, draining=True), growing=True) > 0
    assert BP.backlog_growing(hist, _load(900), now=8000.0) is False
    assert BP.release_budget(_load(900), growing=False) == BP.FLOOR_PER_HOUR   # share < floor
    assert BP.release_budget(_load(900, cap=240_000), growing=False) == 1000
    assert BP.release_budget(BP.JudgeLoad(None, None, None)) == BP.FLOOR_PER_HOUR


def test_hourly_release_budget_is_shared_across_processes(tmp_path: Path) -> None:
    log = tmp_path / "rel.txt"
    BP.log_release(log, 150, now=1000.0)
    BP.log_release(log, 60, now=4000.0)
    assert BP.released_within(log, 3600, now=4500.0) == 210
    assert BP.released_within(log, 3600, now=7000.0) == 60


def test_file_lock_is_exclusive_and_breaks_when_stale(tmp_path: Path) -> None:
    import os
    p = tmp_path / "x.lock"
    a, b = BP.FileLock(p), BP.FileLock(p)
    assert a.acquire() and not b.acquire()
    a.release()
    assert b.acquire()
    os.utime(p, (0, 0))                                   # the holder died long ago
    assert BP.FileLock(p).acquire()


def test_parked_queue_appends_hold_the_lock(tmp_path: Path) -> None:
    q = BP.ParkedQueue(tmp_path / "parked.jsonl")
    assert q.park([{"candidate_id": "a"}, {"candidate_id": "b"}]) == 2
    q.mark_released(["a"])
    assert [r["candidate_id"] for r in q.pending()] == ["b"]
    assert not q.lock.path.exists()


def _resident(tmp: Path, roster: list[dict[str, Any]] | None = None) -> Any:
    from libs.civilizations.resident import Resident
    r = Resident(data_dir=tmp / "d", reports_dir=tmp / "r" / "civilizations", root=tmp)
    if roster is not None:
        r.meta = {x["id"]: x for x in roster}
    return r


def test_after_pass_skips_when_the_other_process_holds_the_store(tmp_path: Path) -> None:
    r = _resident(tmp_path)
    lock = BP.FileLock(r.data / "after_pass.lock")
    assert lock.acquire()
    out = r.after_pass(object())
    assert "skipped" in out
    lock.release()


def test_fetch_plan_reads_roi_and_never_cuts_below_the_default(tmp_path: Path) -> None:
    r = _resident(tmp_path)
    (r.reports / "SOURCE_ROI.json").write_text(json.dumps(
        {"next_pass_item_budget": {"hi": 900, "lo": 10}}), "utf-8")
    plan = r.fetch_plan()
    assert plan["hi"] == (0, 900) and plan["lo"] == (1, 200)


# ------------------------------------------------------------------------ D36 own cells
class _Cells:
    def __init__(self, last: dict[str, str]) -> None:
        self.last = last

    def last_evaluated_by_source(self) -> dict[str, str]:
        return self.last


class _Store:
    def last_runs(self) -> dict[str, Any]:
        return {}


class _Pipe:
    def __init__(self, status: dict[str, Any], last: dict[str, str]) -> None:
        self._s, self.cells, self.store = status, _Cells(last), _Store()

    def source_status(self, t: Any) -> dict[str, Any]:
        return self._s


def test_d36_lane_is_active_only_on_its_own_evaluated_cells(tmp_path: Path) -> None:
    roster = [{"id": "borrow", "civilization": "aqr"}, {"id": "own", "civilization": "aqr"}]
    r = _resident(tmp_path, roster)
    status = {"borrow": {"status": "ACTIVE", "evaluated_via": {"mining": 0, "docket": 7}},
              "own": {"status": "ACTIVE", "evaluated_via": {"mining": 3, "docket": 0}}}
    r.lane_status(_Pipe(status, {"own": "2026-09-30T10:00:00+00:00"}))
    doc = json.loads((tmp_path / "r" / "CIVILIZATION_LANES.json").read_text("utf-8"))
    rows = {x["id"]: x for x in doc["lanes"]}
    assert rows["borrow"]["status"] == "COLD" and rows["borrow"]["last_evaluated_at"] == "NEVER"
    assert rows["borrow"]["docket_attributed_30d"] == 7
    assert rows["own"]["status"] == "ACTIVE" and rows["own"]["evaluated_cells_30d"] == 3
    # the contradiction the audit found can no longer be written
    assert not any(x["status"] == "ACTIVE" and x["last_evaluated_at"] == "NEVER"
                   for x in doc["lanes"])


# -------------------------------------------------------------- outcome ledger readers
def test_knowledge_graph_reads_the_ten_non_alpha_outcome_ledgers(tmp_path: Path) -> None:
    path = ROOT / "desks" / "mt5" / "research" / "knowledge_graph.py"
    for p in (str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location("kg_civ_test", path)
    assert spec and spec.loader
    kg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kg)
    out = tmp_path / "outcomes"
    out.mkdir()
    row = {"source": "civ:qc_forum", "url": "https://q/x", "title": "Fill model misses "
           "rollover slippage on EURUSD", "outcomes": ["EXECUTION_IDEA"]}
    for name in ("EXECUTION_IDEA", "ALPHA_MECHANISM", "NO_VALUE"):
        (out / f"{name}.jsonl").write_text(json.dumps(row) + "\n", "utf-8")
    paths = kg.intake_paths(roots=[tmp_path / "none"], frontier=tmp_path / "f.jsonl",
                            civ_outcomes=out)
    assert [p.stem for p in paths] == ["EXECUTION_IDEA"]
    rows = list(kg.iter_intake(paths, set(), 10))
    leads = kg.ls.leads_from_intelligence_row(rows[0][0], seat=rows[0][1], run=rows[0][2])
    assert leads and leads[0].source_id == "civ:qc_forum" and leads[0].url_or_ref == "https://q/x"
    # a test that redirects the roots never reads the desk's live ledgers
    assert all(p.parent != kg.CIV_OUTCOMES for p in kg.intake_paths(roots=[tmp_path]))


def test_git_mirror_stores_text_only_under_a_permissive_licence(tmp_path: Path) -> None:
    import subprocess
    import time as _t

    from libs.civilizations import fetchers as F
    from libs.mining import acquirer as acq

    def git(*a: str, cwd: Path) -> None:
        subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True,
                       env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                            "PATH": __import__("os").environ.get("PATH", ""),
                            "HOME": str(cwd)})

    bodies: dict[str, tuple[str, dict[str, Any]]] = {}
    for name, lic in (("mit", MIT), ("gpl", GPL), ("none", None)):
        repo = tmp_path / name
        repo.mkdir()
        (repo / "alpha.py").write_text(CODE)
        (repo / "prices.json").write_text('{"close": [1, 2, 3]}')
        if lic:
            (repo / "LICENSE").write_text(lic)
        git("init", "-q", cwd=repo)
        git("add", "-A", cwd=repo)
        git("commit", "-q", "-m", "seed", cwd=repo)
        src = acq.normalise_row({"id": f"m_{name}", "kind": "code", "fetcher": "git_mirror",
                                 "cadence_minutes": 60, "uses": ["direct_cells"],
                                 "config": {"repo": f"file://{repo}", "paths": ["*"]}},
                                origin="t")
        assert src is not None
        ctx = acq.FetchContext(http_get=lambda u, h: acq.HttpResult(None, "", "x"),
                               deadline=_t.monotonic() + 60, root=tmp_path / "root")
        items = [i for i in F.fetch_git_mirror(src, {}, ctx) if i.uri]
        assert [i.title for i in items] == ["alpha.py"]           # the data file never read
        bodies[name] = (items[0].body, dict(items[0].meta or {}))
    assert CODE in bodies["mit"][0] and bodies["mit"][1]["licence"] == "MIT"
    for name in ("gpl", "none"):
        body, meta = bodies[name]
        assert "return ts_rank" not in body and meta["metadata_only"] is True, name
    assert bodies["none"][1]["licence"] == "NONE"
    notices = list((tmp_path / "root" / F.NOTICES).glob("*.txt"))
    assert len(notices) == 2                                        # MIT and GPL texts kept

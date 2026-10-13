"""The learned pre-judge sets queue priority and never rejects (research/prejudge_model.py)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.frontier_identity import docket_cell_id  # noqa: E402

from research import prejudge_model as pm  # noqa: E402

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
SYMS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "XAUUSD")


def _row(sym: str, fam: str, i: int) -> dict[str, Any]:
    return {"symbol": sym, "family": fam, "params": {"k": i}, "source": "test"}


def _docket(n_per_fam: int = 40, fams: tuple[str, ...] = ("good", "bad")) -> list[dict]:
    rows = []
    for i in range(n_per_fam):
        for fam in fams:
            rows.append(_row(SYMS[i % len(SYMS)], fam, i))
    return rows


def _ledger(path: Path, n: int = 300) -> Path:
    """`good` passes half the time, `bad` never; every row a real terminal gate."""
    lines = []
    for i in range(n):
        sym = SYMS[i % len(SYMS)]
        for fam in ("good", "bad"):
            cell = docket_cell_id(_row(sym, fam, 10_000 + i))
            passed = fam == "good" and i % 2 == 0
            lines.append({"at": "2026-10-01T00:00:00+00:00", "cell": cell, "sym": sym,
                          "family": fam, "passed": passed,
                          "terminal_gate": "PASSED" if passed else "cpcv"})
    # unmeasured rows are not failures and must not be counted
    lines.append({"cell": docket_cell_id(_row("EURUSD", "good", 1)), "family": "good",
                  "sym": "EURUSD", "passed": False, "terminal_gate": "UNKNOWN"})
    path.write_text("\n".join(json.dumps(r) for r in lines) + "\n", "utf-8")
    return path


class FixedScorer(pm.Scorer):
    """P(survive) = the row's params.k / 100, so the ranking is known in advance."""

    def __init__(self) -> None:
        super().__init__(None)
        self.status = "TEST"

    def p_many(self, cells: list[str]) -> list[float]:
        return [self.by_cell[c] for c in cells]


def _fixed(rows: list[dict]) -> FixedScorer:
    sc = FixedScorer()
    sc.by_cell = {docket_cell_id(r): (r["params"]["k"] + 1) / 100.0 for r in rows}
    return sc


def _flagged(rows: list[dict]) -> set[str]:
    return {docket_cell_id(r) for r in rows
            if pm.FLAG in ((r.get("prejudge") or {}).get("flags") or [])}


def test_flags_only_reorder_never_drop() -> None:
    rows = _docket()
    before = [docket_cell_id(r) for r in rows]
    fam_slots = [r["family"] for r in rows]
    out, doc = pm.apply(rows, now=NOW, scorer=_fixed(rows), seen=set(), report=None)
    assert len(out) == len(before)
    assert sorted(docket_cell_id(r) for r in out) == sorted(before)
    assert [r["family"] for r in out] == fam_slots          # family slots are untouched
    assert doc["flagged"] > 0 and doc["status"] == "APPLIED"
    # inside each family every flagged row sits behind every unflagged one
    for fam in ("good", "bad"):
        seq = [pm.FLAG in ((r.get("prejudge") or {}).get("flags") or [])
               for r in out if r["family"] == fam]
        assert seq == sorted(seq)


def test_exploration_quota_honoured_and_deterministic() -> None:
    rows = _docket()
    _, doc = pm.apply(rows, now=NOW, scorer=_fixed(rows), seen=set(), report=None,
                      percentile=50, quota=0.10)
    # 40 per family -> 20 strictly below the median -> 2 explored, 18 flagged
    for fam in ("good", "bad"):
        assert doc["families"][fam]["explored"] == 2
        assert doc["families"][fam]["flagged"] == 18
    first = _flagged(rows)
    rows2 = _docket()
    pm.apply(rows2, now=NOW, scorer=_fixed(rows2), seen=set(), report=None)
    assert _flagged(rows2) == first
    # the explored rows really are bottom-half rows left unflagged
    low = {docket_cell_id(r) for r in rows if r["params"]["k"] < 20}
    assert first < low and len(low - first) == 4


def test_judged_rows_never_flagged_and_stale_flags_removed() -> None:
    rows = _docket()
    judged = {docket_cell_id(r) for r in rows if r["params"]["k"] % 3 == 0}
    for r in rows:                                    # last hour flagged every row
        r["prejudge"] = {"flags": [pm.FLAG], "by": "prejudge_model"}
    out, _ = pm.apply(rows, now=NOW, scorer=_fixed(rows), seen=judged, report=None)
    assert not (_flagged(out) & judged)
    assert all("prejudge" not in r for r in out if docket_cell_id(r) in judged)


def test_rule_screen_flags_survive_the_strip() -> None:
    rows = [_row("EURUSD", "good", 1)]
    rows[0]["prejudge"] = {"status": "SCREENED", "flags": ["rq_rule", pm.FLAG], "rules_hash": "h"}
    assert pm.strip_stale(rows) == 1
    assert rows[0]["prejudge"] == {"status": "SCREENED", "flags": ["rq_rule"], "rules_hash": "h"}


def test_fail_open_without_model_ledger_or_seen_index(tmp_path: Path) -> None:
    rows = _docket()
    snapshot = json.dumps(rows, sort_keys=True)
    sc = pm.Scorer.load(tmp_path / "absent")
    assert sc.model is None and sc.status == "FAMILY_PRIOR"
    out, doc = pm.apply(rows, now=NOW, scorer=sc, seen=set(), report=None)
    assert doc["flagged"] == 0                        # equal priorities are never split
    assert json.dumps(out, sort_keys=True) == snapshot
    out, doc = pm.apply(rows, now=NOW, scorer=_fixed(rows),
                        seen_path=tmp_path / "missing.json", report=None)
    assert doc["status"].startswith("NOT_APPLIED") and doc["flagged"] == 0
    assert json.dumps(out, sort_keys=True) == snapshot


def test_fail_open_when_sklearn_import_fails(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "sklearn", None)
    monkeypatch.setitem(sys.modules, "sklearn.ensemble", None)
    doc = pm.train(ledger=_ledger(tmp_path / "ledger.jsonl"), model_dir=tmp_path / "m",
                   force=True)
    assert doc["status"] == "PRIOR_FALLBACK" and doc["model_sha256"] is None
    sc = pm.Scorer.load(tmp_path / "m")
    assert sc.model is None and sc.status == "PRIOR_FALLBACK"
    good, bad = sc.p_many([docket_cell_id(_row("EURUSD", "good", 1)),
                           docket_cell_id(_row("EURUSD", "bad", 1))])
    assert good > bad


def test_priority_monotone_in_p_survive() -> None:
    tables = pm.Tables()
    cell = docket_cell_id(_row("EURUSD", "good", 1))
    vals = [pm.priority(p, cell, tables, {}) for p in (0.0, 0.01, 0.2, 0.5, 0.9)]
    assert vals == sorted(vals) and len(set(vals)) == len(vals)


def test_tiny_ledger_trains_and_ranks_high_pass_family_first(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    doc = pm.train(ledger=_ledger(tmp_path / "ledger.jsonl"), model_dir=tmp_path / "m",
                   force=True)
    assert doc["status"] == "MODEL", doc.get("why")
    assert doc["n_pos"] == 150 and doc["n_neg"] == 450          # UNKNOWN row not counted
    assert doc["auc_holdout"] != pm.UNMEASURED and doc["auc_holdout"] > 0.7
    sc = pm.Scorer.load(tmp_path / "m")
    assert sc.status == "MODEL"
    goods = sc.p_many([docket_cell_id(_row(s, "good", 1)) for s in SYMS])
    bads = sc.p_many([docket_cell_id(_row(s, "bad", 1)) for s in SYMS])
    assert min(goods) > max(bads)
    # a second call inside the refit window reuses the model
    assert pm.train(ledger=tmp_path / "ledger.jsonl", model_dir=tmp_path / "m")["refit"] is False


def test_tampered_model_falls_back_to_tables(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pm.train(ledger=_ledger(tmp_path / "ledger.jsonl"), model_dir=tmp_path / "m", force=True)
    (tmp_path / "m" / "model.pkl").write_bytes(b"not the model")
    sc = pm.Scorer.load(tmp_path / "m")
    assert sc.model is None and sc.status == "PRIOR_FALLBACK"


def test_report_names_unmeasured_terms(tmp_path: Path) -> None:
    rows = _docket()
    rep = tmp_path / "PREJUDGE.json"
    pm.apply(rows, now=NOW, scorer=_fixed(rows), seen=set(), report=rep)
    doc = json.loads(rep.read_text("utf-8"))
    assert doc["apply"]["flagged"] > 0
    assert doc["apply"]["terms"]["compute_cost"].startswith(pm.UNMEASURED)
    assert doc["feature_terms"]["session"].startswith(pm.UNMEASURED)
    assert doc["model"]["auc_holdout"] == pm.UNMEASURED

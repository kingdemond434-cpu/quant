"""The learned pre-judge sets queue priority and never rejects (research/prejudge_model.py)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
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


def _row(sym: str, fam: str, i: int, seen_h: float = 1.0) -> dict[str, Any]:
    return {"symbol": sym, "family": fam, "params": {"k": i}, "source": "test",
            "first_seen": (NOW - timedelta(hours=seen_h)).isoformat()}


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


def test_a_row_older_than_the_flag_bound_is_never_flagged() -> None:
    """Audit of #330: no flag outlives FLAG_MAX_AGE_H, and an unknown age counts as old."""
    rows = _docket()
    for r in rows[:20]:
        r["first_seen"] = (NOW - timedelta(hours=pm.FLAG_MAX_AGE_H + 1)).isoformat()
    for r in rows[20:30]:
        del r["first_seen"]
    out, doc = pm.apply(rows, now=NOW, scorer=_fixed(rows), seen=set(), report=None)
    aged = {docket_cell_id(r) for r in rows[:30]}
    assert not (_flagged(out) & aged) and doc["aged_unflaggable"] == 30


def test_a_family_with_few_low_rows_still_explores_one() -> None:
    rows = _docket(n_per_fam=8, fams=("good",))
    _, doc = pm.apply(rows, now=NOW, scorer=_fixed(rows), seen=set(), report=None,
                      percentile=50, quota=0.10)
    assert doc["families"]["good"]["explored"] == 1


def test_a_model_no_better_than_a_coin_orders_nothing(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pm.train(ledger=_ledger(tmp_path / "ledger.jsonl"), model_dir=tmp_path / "m", force=True)
    schema = tmp_path / "m" / "model.json"
    for auc in (0.5, pm.UNMEASURED):
        doc = json.loads(schema.read_text("utf-8"))
        doc["auc_holdout"] = auc
        schema.write_text(json.dumps(doc), "utf-8")
        sc = pm.Scorer.load(tmp_path / "m")
        assert sc.model is None and sc.status == "PRIOR_FALLBACK", auc


def test_no_symbol_starves_under_a_backlog_that_never_empties() -> None:
    """The audit's starvation case: inflow 100/h against capacity 60/h, two symbols the scorer
    ranks last. With the age bound their oldest wait stays within FIFO's plus the bound."""
    def run(bound: float) -> float:
        old = pm.FLAG_MAX_AGE_H
        pm.FLAG_MAX_AGE_H = bound
        try:
            queue: list[dict] = []
            worst = 0.0
            for hour in range(150):
                now = NOW + timedelta(hours=hour)
                for i in range(100):
                    sym = SYMS[i % len(SYMS)]
                    r = {"symbol": sym, "family": "f", "params": {"k": hour * 100 + i},
                         "source": "sim", "first_seen": now.isoformat()}
                    queue.append(r)
                sc = FixedScorer()
                sc.by_cell = {docket_cell_id(r): (0.01 if r["symbol"] in SYMS[3:] else 0.5)
                              for r in queue}
                queue, _ = pm.apply(queue, now=now, scorer=sc, seen=set(), report=None)
                queue = queue[60:]
                for r in queue:
                    seen = datetime.fromisoformat(r["first_seen"])
                    worst = max(worst, (now - seen).total_seconds() / 3600.0)
            return worst
        finally:
            pm.FLAG_MAX_AGE_H = old

    fifo = run(-1.0)                      # nothing is ever young enough to flag: pure FIFO
    bounded = run(pm.FLAG_MAX_AGE_H)
    assert bounded <= fifo + pm.FLAG_MAX_AGE_H + 1.0, (bounded, fifo)

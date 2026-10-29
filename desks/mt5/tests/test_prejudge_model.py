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


def test_a_flag_delays_a_row_in_the_judges_own_order_by_at_most_the_age_bound(
        tmp_path: Path) -> None:
    """Audit S1 of 680f2856e: through `judge_docket_order.order` -- the sort the judge runs, which
    has no age key -- a flagged row sorts behind its clean siblings, and once it is older than
    FLAG_MAX_AGE_H the next apply leaves it unflagged, so it sorts exactly as if never flagged."""
    from types import SimpleNamespace

    from desks.mt5.scripts import external_gauntlet as G
    from research import judge_docket_order as O

    def specs(rows: list[dict]) -> list[dict]:
        return [{"sym": r["symbol"], "family": r["family"], "params": r["params"],
                 "_never_judged": True,
                 "prejudge_flagged": bool((r.get("prejudge") or {}).get("flags"))} for r in rows]

    fake = SimpleNamespace(BASE=tmp_path, _build_cursor=dict, timeframe_of=G.timeframe_of)
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    rows = _docket(20, fams=("f",))
    sc = _fixed(rows)
    flagged, _ = pm.apply([dict(r) for r in rows], now=NOW, scorer=sc, seen=set(), report=None,
                          quota=0.0)
    order = O.order(fake, specs(flagged))
    n_flag = sum(sp["prejudge_flagged"] for sp in order)
    assert n_flag and all(sp["prejudge_flagged"] for sp in order[-n_flag:])
    later = NOW + timedelta(hours=pm.FLAG_MAX_AGE_H + 2)
    aged, _ = pm.apply(flagged, now=later, scorer=sc, seen=set(), report=None, quota=0.0)
    assert not any(sp["prejudge_flagged"] for sp in specs(aged))
    clean = [{k: v for k, v in r.items() if k != "prejudge"} for r in rows]
    # Same sort keys, position by position (ties keep their input order, as `sorted` does).
    assert ([sp["sym"] for sp in O.order(fake, specs(aged))]
            == [sp["sym"] for sp in O.order(fake, specs(clean))])


# ------------------------------------------------- audit MF1 of 680f2856e: the stream resumes

def _tables_and_sample(st: dict) -> tuple[dict, list]:
    return st["tables"].c, st["sample"]


def test_a_resumed_stream_equals_one_uninterrupted_pass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pm, "PER_KEY_CAP", 20)      # the reservoir fills, so its RNG matters
    led = _ledger(tmp_path / "ledger.jsonl", n=400)
    whole = pm.stream_ledger(led, seed=3)
    text = led.read_text("utf-8").splitlines(keepends=True)
    part = tmp_path / "grow.jsonl"
    part.write_text("".join(text[:300]), "utf-8")
    state = tmp_path / "state.pkl"
    first = pm.stream_ledger(part, seed=3, state_path=state)
    assert first["complete"] and not first["resumed"]
    with part.open("a", encoding="utf-8") as fh:
        fh.write("".join(text[300:]))
    led2 = tmp_path / "ledger.jsonl"
    resumed = pm.stream_ledger(part, seed=3, state_path=state)
    assert resumed["resumed"] and resumed["read"] == whole["read"]
    assert _tables_and_sample(resumed) == _tables_and_sample(whole)
    assert led2.exists()


def test_a_deadline_keeps_progress_and_the_next_pass_finishes(tmp_path: Path,
                                                              monkeypatch) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", n=3000)
    whole = pm.stream_ledger(led, seed=1)
    monkeypatch.setattr(pm, "_STREAM_CHECK_EVERY", 500)
    ticks = iter(range(10**6))
    monkeypatch.setattr(pm.time, "monotonic", lambda: float(next(ticks)))
    state = tmp_path / "state.pkl"
    cut = pm.stream_ledger(led, seed=1, state_path=state, deadline=3.0)
    assert not cut["complete"] and 0 < cut["offset"] < cut["size"]
    monkeypatch.undo()
    done = pm.stream_ledger(led, seed=1, state_path=state)
    assert done["complete"] and done["resumed"]
    assert _tables_and_sample(done) == _tables_and_sample(whole)


def test_a_rewritten_ledger_is_read_again_from_the_start(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", n=200)
    state = tmp_path / "state.pkl"
    pm.stream_ledger(led, seed=0, state_path=state)
    lines = led.read_text("utf-8").splitlines(keepends=True)
    led.write_text("".join(lines[:150]) + "".join(reversed(lines[150:])), "utf-8")
    again = pm.stream_ledger(led, seed=0, state_path=state)
    assert not again["resumed"]
    assert _tables_and_sample(again) == _tables_and_sample(pm.stream_ledger(led, seed=0))


def test_train_saves_progress_and_keeps_the_model_while_the_stream_catches_up(
        tmp_path: Path, monkeypatch) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", n=3000)
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "4")
    monkeypatch.setattr(pm, "_STREAM_CHECK_EVERY", 500)
    ticks = iter(range(10**6))
    monkeypatch.setattr(pm.time, "monotonic", lambda: float(next(ticks)))
    doc = pm.train(ledger=led, model_dir=tmp_path / "m", force=True)
    assert doc["refit"] is False and str(doc["stream"]).startswith("CATCHING_UP")
    assert (tmp_path / "m" / pm.STREAM_STATE.name).exists()
    assert not (tmp_path / "m" / "model.json").exists()


def test_a_fit_that_will_not_fit_the_time_left_is_deferred(tmp_path: Path,
                                                            monkeypatch) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", n=50)
    mdir = tmp_path / "m"
    mdir.mkdir()
    (mdir / "model.json").write_text(json.dumps({"schema": pm.SCHEMA, "trained_ts": 0,
                                                 "fit_seconds": 500.0, "status": "MODEL"}),
                                     "utf-8")
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "600")
    doc = pm.train(ledger=led, model_dir=mdir)
    assert doc["refit"] is False and str(doc["stream"]).startswith("FIT_DEFERRED")
    assert doc["status"] == "MODEL"


def test_the_refit_window_is_longer_than_the_hourly_cadence() -> None:
    assert pm.REFIT_MIN_S > 3600


def test_labels_never_carry_the_holdout_outcome() -> None:
    """Audit S4: a cell's lockbox result must not decide which cells are judged first."""
    base = {"cell": "EURUSD.f.p=1", "passed": False}
    assert pm._label({**base, "terminal_gate": "lockbox", "failed_gates": ["lockbox"]}) == 1
    assert pm._label({**base, "terminal_gate": "lockbox",
                      "failed_gates": ["lockbox", "expected_value"]}) == 0
    assert pm._label({**base, "terminal_gate": "cpcv", "failed_gates": ["cpcv", "lockbox"]}) == 0
    assert pm._label({**base, "terminal_gate": "lockbox"}) is None
    assert pm._label({**base, "terminal_gate": "cpcv"}) == 0
    assert pm._label({**base, "passed": True, "terminal_gate": "PASSED"}) == 1


# ---- audit of 66412eb26: the refit's liveness reaches the report, and the state is JSON ----------

def test_the_stream_state_is_json_and_a_pickle_is_never_loaded(tmp_path: Path) -> None:
    import pickle
    led = _ledger(tmp_path / "ledger.jsonl", n=100)
    state = tmp_path / "m" / pm.STREAM_STATE.name
    pm.stream_ledger(led, seed=0, state_path=state)
    snap = json.loads(state.read_text("utf-8"))
    assert snap["v"] == pm.STREAM_STATE_V
    # A pickle in its place (the v1 format, or anything else) is not read: the pass restarts.
    state.write_bytes(pickle.dumps({"v": pm.STREAM_STATE_V}))
    again = pm.stream_ledger(led, seed=0, state_path=state)
    assert not again["resumed"]
    assert _tables_and_sample(again) == _tables_and_sample(pm.stream_ledger(led, seed=0))


def test_catching_up_reaches_the_report_and_reads_unmeasured(tmp_path: Path, monkeypatch) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", n=3000)
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "4")
    monkeypatch.setattr(pm, "_STREAM_CHECK_EVERY", 500)
    ticks = iter(range(10**6))
    monkeypatch.setattr(pm.time, "monotonic", lambda: float(next(ticks)))
    mdir = tmp_path / "m"
    doc = pm.train(ledger=led, model_dir=mdir, force=True)
    report = tmp_path / "PREJUDGE.json"
    pm._write_report(report, None, model_doc=doc, model_dir=mdir)
    out = json.loads(report.read_text("utf-8"))
    assert str(out["model"]["stream"]).startswith("CATCHING_UP")
    assert 0 < out["model"]["stream_offset"] < out["model"]["stream_size"]
    assert out["liveness"]["status"] == "UNMEASURED"


def test_a_model_past_twice_the_refit_window_is_red(tmp_path: Path) -> None:
    now = 10.0 * pm.STALE_MODEL_S
    stale = pm.model_liveness({"trained_ts": now - pm.STALE_MODEL_S - 60,
                               "stream": "FIT_DEFERRED: ..."}, now=now, model_dir=tmp_path)
    assert stale["status"] == "RED" and "FIT_DEFERRED" in stale["why"]
    fresh = pm.model_liveness({"trained_ts": now - 3600}, now=now, model_dir=tmp_path)
    assert fresh["status"] == "OK"


def test_a_fit_killed_mid_way_leaves_a_marker_that_reads_red(tmp_path: Path) -> None:
    (tmp_path / pm.FIT_MARKER.name).write_text(json.dumps({"started_ts": 100.0}), "utf-8")
    live = pm.model_liveness({"trained_ts": 99.0}, now=200.0, model_dir=tmp_path)
    assert live["status"] == "RED" and live["fit_started_age_s"] == 100.0


def test_a_finished_fit_removes_its_marker_and_times_the_whole_phase(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", n=300)
    mdir = tmp_path / "m"
    doc = pm.train(ledger=led, model_dir=mdir, force=True)
    assert doc["refit"] is True and doc["stream"] == "CURRENT"
    assert not (mdir / pm.FIT_MARKER.name).exists()
    if doc["status"] == "MODEL":
        assert doc["fit_seconds"] >= 0.0
    assert pm.model_liveness(doc, model_dir=mdir)["status"] == "OK"


def test_atomic_bytes_retries_a_refused_replace_and_leaves_no_temp(tmp_path: Path,
                                                                   monkeypatch) -> None:
    real = pm.os.replace
    calls = {"n": 0}

    def refuse_twice(src, dst):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError(13, "held open")
        return real(src, dst)

    monkeypatch.setattr(pm.os, "replace", refuse_twice)
    target = tmp_path / "x.json"
    pm._atomic_bytes(target, b"{}", sleep=lambda s: None)
    assert target.read_bytes() == b"{}" and calls["n"] == 3
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]
    monkeypatch.setattr(pm.os, "replace", lambda s, d: (_ for _ in ()).throw(
        PermissionError(13, "held open")))
    with pytest.raises(PermissionError):
        pm._atomic_bytes(tmp_path / "y.json", b"{}", sleep=lambda s: None)
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]


def test_a_red_model_fails_the_hourly_leg(tmp_path: Path, monkeypatch) -> None:
    """Audit MF1 of 8c77ac60e: the liveness RED needs a reader -- the leg's exit code."""
    monkeypatch.setattr(pm, "REPORT", tmp_path / "PREJUDGE.json")
    monkeypatch.setattr(pm, "MODEL_DIR", tmp_path / "m")
    old = {"schema": pm.SCHEMA, "trained_ts": 0.0, "fit_ok_ts": 0.0, "status": "MODEL",
           "refit": False}
    monkeypatch.setattr(pm, "train", lambda force=False: dict(old))
    assert pm.main(["--train"]) == 1
    fresh = {**old, "trained_ts": pm.time.time(), "fit_ok_ts": pm.time.time()}
    monkeypatch.setattr(pm, "train", lambda force=False: dict(fresh))
    assert pm.main(["--train"]) == 0


def test_liveness_follows_the_last_successful_fit_not_the_last_attempt(tmp_path: Path) -> None:
    now = 10.0 * pm.STALE_MODEL_S
    failing = {"trained_ts": now - 60, "fit_ok_ts": now - pm.STALE_MODEL_S - 60,
               "status": "PRIOR_FALLBACK"}
    assert pm.model_liveness(failing, now=now, model_dir=tmp_path)["status"] == "RED"
    never_ok = {"trained_ts": now - 60, "fit_ok_ts": None}
    assert pm.model_liveness(never_ok, now=now, model_dir=tmp_path)["status"] == "UNMEASURED"


def test_a_thin_ledger_pass_clears_a_killed_fits_marker(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", n=3)            # below MIN_TRAIN
    mdir = tmp_path / "m"
    mdir.mkdir()
    (mdir / pm.FIT_MARKER.name).write_text(json.dumps({"started_ts": 1.0}), "utf-8")
    doc = pm.train(ledger=led, model_dir=mdir, force=True)
    assert doc["status"] in ("PRIOR_FALLBACK", "NO_EVIDENCE")
    assert not (mdir / pm.FIT_MARKER.name).exists()
    assert pm.model_liveness(doc, model_dir=mdir)["status"] == "OK"


def test_a_fit_that_raises_keeps_the_last_good_stamp(tmp_path: Path, monkeypatch) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", n=300)
    mdir = tmp_path / "m"
    first = pm.train(ledger=led, model_dir=mdir, force=True)
    ok = first["fit_ok_ts"]
    assert isinstance(ok, float)

    def boom(*a, **k):
        raise RuntimeError("fit exploded")

    monkeypatch.setattr(pm, "_fit", boom)
    second = pm.train(ledger=led, model_dir=mdir, force=True, now=ok + 100.0)
    if first["status"] == "MODEL":
        assert second["status"] == "PRIOR_FALLBACK" and second["fit_ok_ts"] == ok

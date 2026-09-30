"""Tier S outputs WITH a consumer: S02 (bitemporal store on a research data path), S13 (the failure
memory ordering a real generator) and S31 (FORMAL.json read back into a claim, a fence and the
self-model).

Every test runs on synthetic inputs in tmp_path; none reads or writes the desk's live data.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(ROOT / "scripts"), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import breadth_sweep as bs  # noqa: E402
import run_edges_macro_fusion_sweep as emf  # noqa: E402
import tier_s as ts  # noqa: E402

from libs.tiers import bitemporal, failure_memory, formal, self_model  # noqa: E402

# ---------------------------------------------------------------------- S02 bitemporal read path


def _brute(store: bitemporal.BitemporalStore, ent: str, att: str, t: str) -> Any:
    known = store.as_of(t, entity=ent, attribute=att)
    if not known:
        return None
    return max(known.values(), key=lambda d: d.valid_time)


def test_latest_known_agrees_with_as_of_for_every_query_time() -> None:
    rng = random.Random(7)  # noqa: S311 - a fixed synthetic panel, not a secret
    base = datetime(2026, 1, 1, tzinfo=UTC)
    store = bitemporal.BitemporalStore()
    for _i in range(60):
        vt = base + timedelta(days=rng.randrange(30))
        kt = vt + timedelta(hours=rng.randrange(1, 90))
        store.add(bitemporal.Datum("DGS10", "favourable", rng.random(), vt.isoformat(),
                                   kt.isoformat(), revision=rng.randrange(3)))
    store.add(bitemporal.Datum("OTHER", "favourable", 1.0, base.isoformat(), base.isoformat()))
    qs = [(base + timedelta(hours=h)).isoformat() for h in range(0, 34 * 24, 7)]
    got = store.latest_known("DGS10", "favourable", qs)
    for q, g in zip(qs, got, strict=True):
        want = _brute(store, "DGS10", "favourable", q)
        assert (g is None) == (want is None)
        if g is not None:
            assert g.valid_time == want.valid_time and g.value == want.value


def test_a_revision_is_read_only_once_it_was_known() -> None:
    s = bitemporal.BitemporalStore([
        bitemporal.Datum("GDP", "v", 1.0, "2026-06-30", "2026-07-30", revision=0),
        bitemporal.Datum("GDP", "v", 2.0, "2026-06-30", "2026-09-30", revision=1)])
    flash, revised, before = s.latest_known("GDP", "v", ["2026-08-01", "2026-10-01",
                                                          "2026-07-01"])
    assert flash is not None and flash.value == 1.0
    assert revised is not None and revised.value == 2.0
    assert before is None


def test_the_macro_sweep_conditions_on_what_was_known_at_the_signal() -> None:
    """A 03:00 signal on day d may not read day d's close; after the lag it reads it."""
    days = pd.date_range("2026-03-02", periods=4, freq="D")
    fav = pd.Series([False, True, False, True], index=days)
    store = emf.favourable_store(fav, "DGS10")
    assert len(store.rows) == 4
    d1 = days[1]
    early = SimpleNamespace(time=pd.Timestamp(d1, tz="UTC") + pd.Timedelta(hours=3))
    after = SimpleNamespace(time=pd.Timestamp(d1, tz="UTC") + emf.MACRO_KNOWABLE_AFTER
                            + pd.Timedelta(hours=1))
    # the same-date join admitted `early` on day 1's (True) state; the PIT read sees day 0 (False)
    assert early.time.date() in set(fav[fav].index.date)
    assert emf.pit_conditioned([early], store, "DGS10") == []
    assert emf.pit_conditioned([after], store, "DGS10") == [after]
    # before any print was knowable nothing is conditioned at all
    first = SimpleNamespace(time=pd.Timestamp(days[0], tz="UTC"))
    assert emf.pit_conditioned([first], store, "DGS10") == []


def test_data_os_reports_the_pit_consumer() -> None:
    """organ_data_os publishes the sweep's PIT block (or UNMEASURED) beside its audits."""
    src = (DESK / "research" / "tier_s.py").read_text("utf-8")
    assert "\"pit_reads\": pit_reads" in src and "edges_macro_fusion_sweep.json" in src
    sweep_src = (DESK / "research" / "run_edges_macro_fusion_sweep.py").read_text("utf-8")
    assert "cond = pit_conditioned(sigs, store, col)" in sweep_src
    assert "s.time.date() in fav_dates]" not in sweep_src


# ---------------------------------------------------------------------- S13 failure memory -> gen


def _memory() -> dict[str, Any]:
    return {"generated_utc": datetime.now(UTC).isoformat(),
            "theorems": [{"mechanism": "breakout", "asset_class": "FX_MAJOR", "selector": "asia",
                          "n": 61, "survivors": 0, "cause": "COSTS_KILLED",
                          "statement": "breakout on FX_MAJOR in asia fails by COSTS_KILLED",
                          "provenance": {"evidence_hash": "abc", "sample_cells": []}}],
            "rules": []}


def _desc(r: dict[str, Any]) -> dict[str, Any]:
    return {"mechanism": r["mech"], "asset_class": r["ac"], "selector": r.get("sel", "?")}


def test_prioritise_reorders_within_a_tier_and_drops_nothing() -> None:
    rows = [{"id": 0, "mech": "breakout", "ac": "FX_MAJOR", "tier": 0},
            {"id": 1, "mech": "carry", "ac": "FX_MAJOR", "tier": 0},
            {"id": 2, "mech": "breakout", "ac": "FX_MAJOR", "tier": 1},
            {"id": 3, "mech": "carry", "ac": "METAL", "tier": 1}]
    out, st = failure_memory.prioritise(rows, _memory(), _desc, rank=lambda r: r["tier"])
    assert [r["id"] for r in out] == [1, 0, 3, 2]
    assert sorted(r["id"] for r in out) == [0, 1, 2, 3]
    assert st["tagged"] == 2 and st["consulted"] and st["rows"] == 4
    assert "COSTS_KILLED" in out[1]["failure_memory"]["theorems"][0]
    assert "failure_memory" not in out[0]


def test_an_empty_or_stale_memory_changes_nothing(tmp_path: Path) -> None:
    rows = [{"id": i, "mech": "breakout", "ac": "FX_MAJOR"} for i in range(3)]
    out, st = failure_memory.prioritise(rows, {}, _desc)
    assert out == rows and not st["consulted"]
    p = tmp_path / "fm.json"
    old = {**_memory(), "generated_utc": (datetime.now(UTC) - timedelta(hours=30)).isoformat()}
    p.write_text(json.dumps(old))
    assert failure_memory.load(p) == {}
    p.write_text(json.dumps(_memory()))
    assert failure_memory.load(p)["theorems"]
    assert failure_memory.load(tmp_path / "absent.json") == {}


def test_breadth_sweep_consults_the_memory_and_keeps_every_cell(monkeypatch: Any) -> None:
    import axis_registry
    import universe_policy
    monkeypatch.setattr(axis_registry, "classify_family",
                        lambda f: ("breakout" if f == "dead_fam" else "carry", "x", "y"))
    monkeypatch.setattr(universe_policy, "asset_class_of", lambda s: "FX_MAJOR")
    now = datetime.now(UTC).isoformat()
    # the theorem is (breakout, FX_MAJOR, asia); `live_fam` shares only the asset class, which
    # is one axis of three and below the neighbourhood's two-axis match
    cells = [bs._cell("EURUSD", fam, {"session": "asia" if fam == "dead_fam" else "ny",
                                      **({"timeframe": tf} if tf else {})}, {"why": "t"}, now)
             for tf in ("M5", None) for fam in ("dead_fam", "live_fam")]
    out, st = bs.order_by_failure_memory(list(cells), memory=_memory())
    assert len(out) == len(cells) and all(any(c is o for o in out) for c in cells)
    assert [(r["family"], (r["params"] or {}).get("timeframe")) for r in out] == [
        ("live_fam", "M5"), ("dead_fam", "M5"), ("live_fam", None), ("dead_fam", None)]
    assert st["tagged"] == 2
    assert all("failure_memory" in r for r in out if r["family"] == "dead_fam")


def test_breadth_sweep_calls_the_memory_on_its_generation_path() -> None:
    src = (DESK / "research" / "breadth_sweep.py").read_text("utf-8")
    body = src.split("def cells(", 1)[1].split("\ndef ", 1)[0]
    assert "order_by_failure_memory(out)" in body


# ---------------------------------------------------------------------- S31 FORMAL.json consumer


def _formal_doc(knobs: dict[str, bool | None], *, violated: str | None = None,
                gaps: list[dict[str, Any]] | None = None, age_h: float = 0.0) -> dict[str, Any]:
    invs = {n: {"verdict": "VIOLATED" if n == violated else "PROVEN"} for n in formal.INVARIANTS}
    return {"generated_utc": (datetime.now(UTC) - timedelta(hours=age_h)).isoformat(),
            "protocol": {"invariants": invs, "depends_on": {
                "ZERO_MEANS_NO_ORDER": ["recheck_alloc_at_send"],
                "NO_DUPLICATE_FILL": ["persist_before_send+reconcile_on_restart"],
                "NO_FUTURE_DATA": ["clamp_data_to_clock"]}},
            "conformance": {"knobs": knobs},
            "decision_core_drive": {"core_gaps": gaps or []}}


ALL_ON: dict[str, bool | None] = dict.fromkeys(
    ("recheck_alloc_at_send", "persist_before_send", "reconcile_on_restart",
     "clamp_data_to_clock"), True)


def test_the_claim_is_verified_only_when_the_gateway_backs_every_invariant() -> None:
    assert formal.claim(_formal_doc(ALL_ON))["claim"] == "VERIFIED"
    c = formal.claim(_formal_doc({**ALL_ON, "clamp_data_to_clock": False}))
    assert c["claim"] == "MODEL_ONLY"
    assert c["invariants"]["NO_FUTURE_DATA"]["missing_knobs"] == ["clamp_data_to_clock"]
    # a pair is satisfied by EITHER knob
    one = formal.claim(_formal_doc({**ALL_ON, "persist_before_send": False}))
    assert one["invariants"]["NO_DUPLICATE_FILL"]["verdict"] == "IMPLEMENTED"
    gap = formal.claim(_formal_doc(ALL_ON, gaps=[{"function": "f",
                                                  "invariants": ["ZERO_MEANS_NO_ORDER"]}]))
    assert gap["claim"] == "MODEL_ONLY"


def test_violation_staleness_absence_and_regression() -> None:
    assert formal.claim(_formal_doc(ALL_ON, violated="EXPOSURE_LIMIT"))["claim"] == "VIOLATED"
    assert formal.claim(_formal_doc(ALL_ON, age_h=10))["claim"] == "UNMEASURED"
    assert formal.claim(None)["claim"] == "UNMEASURED"
    assert formal.claim({"status": "ERROR"})["claim"] == "UNMEASURED"
    r = formal.claim(_formal_doc({**ALL_ON, "clamp_data_to_clock": False}),
                     best_implemented=len(formal.INVARIANTS))
    assert r["regressed"] and r["best_implemented"] == len(formal.INVARIANTS)


def test_the_fence_exits_on_violation_regression_and_missing_state(tmp_path: Path) -> None:
    import check_formal_claim as cfc
    f, rat = tmp_path / "FORMAL.json", tmp_path / "ratchet.json"
    args = ["--formal", str(f), "--ratchet", str(rat)]
    assert cfc.main(args) == 0                              # no state, portable half
    assert cfc.main([*args, "--require-state"]) == 2        # no state on the box
    f.write_text(json.dumps(_formal_doc({**ALL_ON, "clamp_data_to_clock": False})))
    assert cfc.main([*args, "--require-state"]) == 0        # MODEL_ONLY is stated, not failed
    rat.write_text(json.dumps({"best_implemented": len(formal.INVARIANTS)}))
    assert cfc.main([*args, "--require-state"]) == 2        # regressed below the ratchet
    rat.unlink()
    f.write_text(json.dumps(_formal_doc(ALL_ON, violated="NO_DUPLICATE_FILL")))
    assert cfc.main(args) == 2                              # a violated model always fails


def test_the_fence_is_registered_in_the_box_gate() -> None:
    import run_law_gate as gate
    assert ("check_formal_claim.py", ("--require-state",)) in gate._STATE_FENCES


def test_organ_formal_claim_reads_the_published_report(tmp_path: Path, monkeypatch: Any) -> None:
    rep = tmp_path / "FORMAL.json"
    rep.write_text(json.dumps(_formal_doc({**ALL_ON, "clamp_data_to_clock": False})))
    monkeypatch.setattr(ts, "FORMAL_REPORT", rep)
    monkeypatch.setattr(ts, "STATE", tmp_path / "state")
    monkeypatch.setattr(ts, "ROOT", tmp_path)
    out = ts.organ_formal_claim()
    assert out["claim"] == "MODEL_ONLY" and out["metric"]["protocol_verified"] == 0.0
    saved = json.loads((tmp_path / "state" / "formal_claim.json").read_text())
    assert saved["best_implemented"] == out["implemented"]
    assert "(\"formal_claim\", organ_formal_claim)" in (DESK / "research" / "tier_s.py"
                                                       ).read_text("utf-8")


def test_the_self_model_counts_the_claim() -> None:
    fc = {"claim": "MODEL_ONLY", "verified_share": 0.25, "reasons": ["lacking clamp"]}
    inv = {d["area"]: d for d in self_model.inventory({"formal_claim": fc})}
    assert inv["ops.protocol_verified"]["gap"] == 0.75
    card = self_model.sealed_scorecard({"formal_claim": fc})
    assert card["protocol_verified"] == 0.25
    assert self_model.SEALED_METRICS["protocol_verified"] == "up"
    bad = {d["area"]: d for d in self_model.inventory({"formal_claim": {"claim": "VIOLATED"}})}
    assert bad["ops.protocol_verified"]["gap"] == 1.0

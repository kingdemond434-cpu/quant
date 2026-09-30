"""The review panel and the theory graph at the promotion door (libs/tiers/door_evidence)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.tiers import door_evidence as de


def _ch(resolves: str, state: str = "FAILED", sev: str = "HIGH") -> dict[str, Any]:
    return {"reviewer": "r", "kind": "K", "state": state, "severity": sev,
            "resolves_when": resolves}


def test_only_candidate_specific_high_failures_count() -> None:
    row = {"challenges": [_ch("red_queen_survives"), _ch("replication_agrees"),
                          _ch("stress_x5_positive", sev="MEDIUM"),
                          _ch("forward_n_40", state="OPEN")]}
    assert de.review_failed(row) == [], "only candidate-specific HIGH failures"
    assert de.review_failed({"challenges": [_ch("stress_x5_positive")]}) == ["r:K"]


def test_theory_ignores_backtest_and_needs_min_oos() -> None:
    bt = [(False, "backtest")] * 500
    assert de.oos_posterior(bt)["status"] == "UNMEASURED", "backtest failures never refute"
    few = [(False, "forward")] * (de.MIN_OOS - 1)
    assert de.oos_posterior(few)["status"] == "UNMEASURED"
    assert de.oos_posterior([(False, "forward")] * 12)["status"] == "REFUTED"
    assert de.oos_posterior([(True, "live")] * 12)["status"] == "SUPPORTED"


def test_build_and_reason() -> None:
    rows = de.build([{"candidate": "a.EURUSD.x", "verdict": "FAILED",
                      "challenges": [_ch("forward_n_40")]},
                     {"candidate": "b.GBPUSD.y", "verdict": "CLEAR", "challenges": []},
                     {"candidate": "c.AUDUSD.z", "verdict": "CLEAR", "challenges": []}],
                    {"a.EURUSD.x": "f1", "b.GBPUSD.y": "f2", "c.AUDUSD.z": "f3"},
                    {"f2": [(False, "forward")] * 12, "f3": [(False, "backtest")] * 99})
    assert (de.door_reason(rows["a.EURUSD.x"]) or "").startswith("REVIEW_PANEL_FAILED")
    assert (de.door_reason(rows["b.GBPUSD.y"]) or "").startswith("THEORY_REFUTED")
    assert de.door_reason(rows["c.AUDUSD.z"]) is None


def test_door_reads_fresh_verdicts_and_respects_suspension(monkeypatch: Any,
                                                           tmp_path: Path) -> None:
    from libs.tiers import authority
    from libs.tiers import promotion_authority as pa
    dv = tmp_path / "door.json"
    monkeypatch.setattr(pa, "ROOT", tmp_path)
    monkeypatch.setattr(pa, "DOOR_VERDICTS", dv)
    monkeypatch.setattr(pa.firewall, "may", lambda *a, **k: True)
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: False)
    row = {"review_failed": ["execution:X"], "family": "f",
           "theory": {"status": "REFUTED", "n_oos": 12, "confidence": 0.1}}
    import pytest
    with pytest.raises(pa.DoorReadError):
        pa._panel_and_theory("EURUSD.x")                 # absent: the door cannot vouch
    dv.write_text(json.dumps({"generated_utc": "2020-01-01T00:00:00+00:00",
                              "rows": {"ext.EURUSD.x": row}}), "utf-8")
    with pytest.raises(pa.DoorReadError):
        pa._panel_and_theory("EURUSD.x")                 # stale: the verifier stopped
    dv.write_text(json.dumps({"generated_utc": datetime.now(UTC).isoformat(),
                              "rows": {"ext.EURUSD.x": row}}), "utf-8")
    assert (pa._panel_and_theory("EURUSD.x") or "").startswith("REVIEW_PANEL_FAILED")
    assert pa._panel_and_theory("GBPUSD.x") is None
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: organ == "review")
    assert (pa._panel_and_theory("EURUSD.x") or "").startswith("THEORY_REFUTED")
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: True)
    assert pa._panel_and_theory("EURUSD.x") is None


def test_door_fails_closed_when_a_check_raises(monkeypatch: Any) -> None:
    from libs.tiers import promotion_authority as pa

    def boom(*a: Any, **k: Any) -> None:
        raise RuntimeError("firewall table unreadable")

    for fn in ("_constitution", "_replication", "_fdr", "_panel_and_theory"):
        monkeypatch.setattr(pa, fn, lambda name: None)
    monkeypatch.setattr(pa, "_freeze", lambda: None)
    assert pa.block("EURUSD.x") is None
    monkeypatch.setattr(pa, "_fdr", boom)
    why = pa.block("EURUSD.x") or ""
    assert why.startswith("DOOR_ERROR: the fdr check raised RuntimeError"), why
    monkeypatch.setattr(pa, "_fdr", lambda name: None)
    monkeypatch.setattr(pa, "_freeze", boom)
    assert (pa.block("EURUSD.x") or "").startswith("DOOR_ERROR: the freeze check")


def test_done_needs_the_trading_boxs_own_attestation(tmp_path: Path) -> None:
    import importlib.util
    import sys as _sys

    from libs.tiers import box_evidence as be
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("chk_ts", root / "scripts" /
                                                  "check_tier_s_program.py")
    assert spec and spec.loader
    chk = importlib.util.module_from_spec(spec)
    _sys.modules["chk_ts"] = chk
    spec.loader.exec_module(chk)
    ledger = json.loads((root / "docs" / "research" / "tier_s_program.json").read_text("utf-8"))
    problems, _ = chk.check(ledger, root, evidence={})
    assert problems == [], problems
    lid = next(r["id"] for r in ledger["layers"] if r["status"] == "BUILT")
    for r in ledger["layers"]:
        if r["id"] == lid:
            r["status"], r["remaining"] = "DONE", ""
    problems, _ = chk.check(ledger, root, evidence={})
    assert any("without the trading box's attestation" in p for p in problems), problems
    cloud = {"host": "runsc", "layers": {lid: {"ok": True}}}
    problems, _ = chk.check(ledger, root, evidence=cloud)
    assert any(lid in p for p in problems), "a cloud host's word never counts"
    box = {"host": be.TRADING_HOST, "layers": {lid: {"ok": True}}}
    problems, _ = chk.check(ledger, root, evidence=box)
    assert problems == [], problems


def test_attest_reads_freshness_and_the_contract_verdict(tmp_path: Path) -> None:
    from libs.tiers import box_evidence as be
    now = datetime.now(UTC)
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "research" / "tier_s_program.json").write_text(json.dumps(
        {"layers": [{"id": "S01", "artifact": "a.json"}, {"id": "S02", "artifact": "b.json"},
                    {"id": "S03", "artifact": "c.json"}, {"id": "S04", "artifact": "d.json"}]}),
        "utf-8")
    (tmp_path / "a.json").write_text(json.dumps({"generated_utc": now.isoformat()}), "utf-8")
    (tmp_path / "b.json").write_text(json.dumps({"generated_utc": "2020-01-01T00:00:00+00:00"}),
                                     "utf-8")
    (tmp_path / "c.json").write_text(json.dumps({"generated_utc": now.isoformat()}), "utf-8")
    cp = tmp_path / be.CONTRACTS.relative_to(be.ROOT)
    cp.parent.mkdir(parents=True)
    cp.write_text(json.dumps({"layers": {"S03": {"verdict": "REJECTED"}}}), "utf-8")
    doc = be.attest(root=tmp_path, out=tmp_path / "ev.json", host=be.TRADING_HOST, now=now)
    ok = {k for k, v in doc["layers"].items() if v["ok"]}
    assert ok == {"S01"}, doc
    assert be.attested(doc) == {"S01"}
    assert be.attested({**doc, "host": "runsc"}) == set()


def test_a_cited_artifact_needs_a_writer_and_outputs_are_digested(tmp_path: Path) -> None:
    import importlib.util
    import sys as _sys

    from libs.tiers import box_evidence as be
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("chk_ts2", root / "scripts" /
                                                  "check_tier_s_program.py")
    assert spec and spec.loader
    chk = importlib.util.module_from_spec(spec)
    _sys.modules["chk_ts2"] = chk
    spec.loader.exec_module(chk)
    ledger = json.loads((root / "docs" / "research" / "tier_s_program.json").read_text("utf-8"))
    ledger["layers"][0]["artifact"] = "desks/mt5/reports/tier_s/NOBODY_WRITES_THIS.json"
    problems, _ = chk.check(ledger, root, evidence={})
    assert any("has no writer" in p for p in problems), problems
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"generated_utc": "2026-09-30T00:00:00+00:00",
                             "authoritative": True, "rows": [{"over_budget": True}, {}]}),
                 "utf-8")
    d = be.digest(p)
    assert d["exists"] and d["head"]["authoritative"] is True
    assert d["head"]["n_rows"] == 2 and d["head"]["n_rows_over_budget"] == 1
    assert be.digest(tmp_path / "absent.json") == {"exists": False}
    err = tmp_path / "e.json"
    err.write_text(json.dumps({"status": "ERROR",
                               "generated_utc": datetime.now(UTC).isoformat()}), "utf-8")
    row = be.layer_evidence({"id": "S01", "artifact": "e.json"}, {}, tmp_path,
                            datetime.now(UTC))
    assert row["ok"] is False and "ERROR" in row["why"]


def test_the_door_reviews_rows_already_live(monkeypatch: Any) -> None:
    from libs.tiers import promotion_authority as pa
    monkeypatch.setattr(pa, "block",
                        lambda n: "REPLICATION_MISMATCH: x" if n == "bad" else None)
    assert pa.review_live(["good", "bad"]) == {"bad": "REPLICATION_MISMATCH: x"}


def _door_sandbox(monkeypatch: Any, tmp_path: Path) -> Any:
    from libs.tiers import authority
    from libs.tiers import promotion_authority as pa
    monkeypatch.setattr(pa, "ROOT", tmp_path)
    for attr in ("REPLICATION", "FDR_ROWS", "FREEZE", "LEDGER", "DOOR_VERDICTS",
                 "CONSTITUTION"):
        monkeypatch.setattr(pa, attr, tmp_path / f"{attr}.json")
    monkeypatch.setattr(pa, "RATIFICATIONS", tmp_path / "RATIFICATIONS.jsonl")
    monkeypatch.setattr(pa.firewall, "may", lambda *a, **k: True)
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: False)
    return pa


def test_every_door_input_fails_closed_when_damaged(monkeypatch: Any, tmp_path: Path) -> None:
    """Absent withholds nothing; a PRESENT input that is torn, not JSON, not an object, or holds
    the wrong shape withholds with DOOR_ERROR -- on every one of the door's inputs."""
    from libs.tiers import truth_kernel
    pa = _door_sandbox(monkeypatch, tmp_path)
    now = datetime.now(UTC).isoformat()
    fresh = {"REPLICATION": {"at": now}, "FDR_ROWS": {"generated_utc": now},
             "FREEZE": {"at": now, "verdict": "OK"},
             "DOOR_VERDICTS": {"generated_utc": now, "rows": {}}}
    for attr in fresh:
        assert (pa.block("EURUSD.x") or "").startswith("DOOR_ERROR"), f"{attr} absent"
        getattr(pa, attr).write_text(json.dumps(fresh[attr]), "utf-8")
    assert pa.block("EURUSD.x") is None, "every required verdict fresh, none against it"
    for attr in fresh:
        getattr(pa, attr).write_text(json.dumps({**fresh[attr], "at": "2020-01-01T00:00:00",
                                                 "generated_utc": "2020-01-01T00:00:00"}),
                                     "utf-8")
        assert (pa.block("EURUSD.x") or "").startswith("DOOR_ERROR"), f"{attr} stale"
        getattr(pa, attr).write_text(json.dumps(fresh[attr]), "utf-8")
    damaged = {
        "REPLICATION": ["{torn", "[1, 2]", json.dumps({"verdicts": {"a": 1}})],
        "FDR_ROWS": ["{torn", json.dumps({"generated_utc": now, "certified": {"a": 1}})],
        "FREEZE": ["not json", "3"],
        "DOOR_VERDICTS": ["{", json.dumps({"generated_utc": now, "rows": [1]})],
        "CONSTITUTION": ["{", json.dumps({"rules": [1]})],
    }
    for attr, bodies in damaged.items():
        for body in bodies:
            getattr(pa, attr).write_text(body, "utf-8")
            why = pa.block("EURUSD.x") or ""
            assert why.startswith("DOOR_ERROR"), (attr, body, why)
        if attr in fresh:
            getattr(pa, attr).write_text(json.dumps(fresh[attr]), "utf-8")
        else:
            getattr(pa, attr).unlink()
    assert pa.block("EURUSD.x") is None
    pa.CONSTITUTION.write_text(json.dumps(truth_kernel.constitution_doc()), "utf-8")
    pa.RATIFICATIONS.write_text("{torn\n", "utf-8")
    loosened = truth_kernel.constitution_doc()
    loosened["rules"]["cert.dsr_threshold"]["value"] = 0.5
    pa.CONSTITUTION.write_text(json.dumps(loosened), "utf-8")
    assert (pa.block("EURUSD.x") or "").startswith("DOOR_ERROR"), "damaged ratifications"


def test_a_suspension_lookup_that_raises_withholds(monkeypatch: Any, tmp_path: Path) -> None:
    from libs.tiers import authority
    pa = _door_sandbox(monkeypatch, tmp_path)

    def boom(*a: Any, **k: Any) -> bool:
        raise OSError("authority table locked")

    monkeypatch.setattr(authority, "suspended", boom)
    assert (pa.block("EURUSD.x") or "").startswith("DOOR_ERROR")


def test_a_door_input_missing_past_its_grace_is_a_loud_defect(monkeypatch: Any,
                                                              tmp_path: Path) -> None:
    import sys as _sys
    from datetime import timedelta
    _research = str(Path(__file__).resolve().parents[1] / "research")
    if _research not in _sys.path:
        _sys.path.insert(0, _research)
    import tier_s as ts  # type: ignore[import-not-found]

    pa = _door_sandbox(monkeypatch, tmp_path)
    for key, (_path, stamp, writer) in list(pa.REQUIRED.items()):
        monkeypatch.setitem(pa.REQUIRED, key, (getattr(pa, {
            "replication": "REPLICATION", "online_fdr": "FDR_ROWS", "immune": "FREEZE",
            "door": "DOOR_VERDICTS"}[key]), stamp, writer))
    store: dict[str, Any] = {}
    monkeypatch.setattr(ts, "_state", lambda n: dict(store.get(n) or {}))
    monkeypatch.setattr(ts, "_save_state", lambda n, d: store.__setitem__(n, dict(d)))
    t0 = ts.NOW
    first = ts._door_input_health()
    assert not first["all_ok"] and first["defects"] == [], "inside the grace: tracked, quiet"
    monkeypatch.setattr(ts, "NOW", t0 + timedelta(hours=2.5))
    later = ts._door_input_health()
    assert len(later["defects"]) == 4 and all("DEFECT door input" in d for d in later["defects"])
    now = datetime.now(UTC).isoformat()
    pa.REPLICATION.write_text(json.dumps({"at": now}), "utf-8")
    pa.FDR_ROWS.write_text(json.dumps({"generated_utc": now}), "utf-8")
    pa.FREEZE.write_text(json.dumps({"at": now, "verdict": "OK"}), "utf-8")
    pa.DOOR_VERDICTS.write_text(json.dumps({"generated_utc": now, "rows": {}}), "utf-8")
    healed = ts._door_input_health()
    assert healed["all_ok"] and healed["defects"] == [] and store["door_inputs"]["bad_since"] == {}


def test_freeze_tilts_heat_toward_out_of_sample_evidence_heat_neutrally() -> None:
    from libs.tiers import allocator_tilts as at
    book = {"a": 0.1, "b": 0.1}
    calm = at.build(book, {}, {}, {}, freeze=False, oos_n_by_group={"a": 200, "b": 0})
    assert calm["a"]["freeze_factor"] == calm["b"]["freeze_factor"] == 1.0
    fz = at.build(book, {}, {}, {}, freeze=True, oos_n_by_group={"a": 200, "b": 0})
    assert fz["a"]["freeze_factor"] > 1.0 > fz["b"]["freeze_factor"]
    assert fz["a"]["tilt"] > 1.0 > fz["b"]["tilt"]
    mean = (fz["a"]["freeze_factor"] + fz["b"]["freeze_factor"]) / 2
    assert abs(mean - 1.0) < 1e-6, "the book's total heat is untouched"
    held = at.build(book, {}, {}, {}, held_out=lambda k: k == "b", freeze=True,
                    oos_n_by_group={"a": 200, "b": 0})
    assert held["b"]["freeze_factor"] == 1.0 and held["b"]["tilt"] == 1.0, "control is pinned"


def test_the_exchange_organ_passes_the_immune_freeze_to_the_tilts(monkeypatch: Any,
                                                                   tmp_path: Path) -> None:
    import sys as _sys
    _research = str(Path(__file__).resolve().parents[1] / "research")
    if _research not in _sys.path:
        _sys.path.insert(0, _research)
    import tier_s as ts  # type: ignore[import-not-found]

    from libs.tiers import authority
    from libs.tiers import promotion_authority as pa
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: False)
    monkeypatch.setattr(ts, "ALLOCATOR_TILTS", tmp_path / "tilts.json")
    monkeypatch.setattr(ts, "shadow_rows", lambda: {})
    monkeypatch.setattr(ts, "live_rows", lambda: [])
    monkeypatch.setattr(pa, "_freeze", lambda: "IMMUNE_FREEZE: test")
    out = ts._allocator_tilts({}, {"a.EURUSD.x": 0.1, "b.GBPUSD.y": 0.1})
    assert out["freeze"] is True
    assert json.loads((tmp_path / "tilts.json").read_text("utf-8"))["freeze"] is True
    monkeypatch.setattr(pa, "_freeze", lambda: None)
    assert ts._allocator_tilts({}, {"a.EURUSD.x": 0.1})["freeze"] is False

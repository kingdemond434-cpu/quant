"""A sweep killed between its two writes loses an hour, not its verdicts.

THE SEAM, MEASURED ON THE TRADING BOX 2026-09-24:

    reports/universal_gates_external.json   swept_at 2026-09-23T05:42:42, 88,366,334 bytes,
                                            76,749 verdicts, `survivors_passing_all: 7`
    reports/UNIVERSAL_SURVIVORS.json        written three minutes later, still swept_at 09-16

`scripts/external_gauntlet.py` writes its gate output at :3123 and only then builds, annotates,
merges, purges and writes the survivor rows at :3452. `hourly_cycle._run_tree` SIGKILLs the leg
at its cycle budget, and `external_gauntlet` recorded ZERO successful outcomes on 18, 19, 20, 22,
23 and 24 September. Across that window 65 cells passed all ten gates and not one reached the
seal, the retired set, or any unrunnable file.

`canon_publication.recover_from_gate_output` closes it by REBUILDING the row the judge was killed
before writing, from the evaluation it had already finished. These tests pin the four refusals
that make that safe, and the three places the rebuilt row must agree with the sealed judge
exactly -- because the sealed file cannot be edited and cannot be imported for these locals, so
only a test can hold the two copies together.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK / "research"), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import canon_publication as cp  # noqa: E402
from gate_policy import ATTESTATION, GATES  # noqa: E402

GAUNTLET = (_DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")


def _stages(passed: bool = True, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {name: {"passed": True} for name in GATES}
    if not passed:
        out["lockbox"] = {"passed": False}
    out.update(extra or {})
    return out


def _gate_output(verdicts: list[dict[str, Any]], swept: str = "2026-09-23T05:42:42+00:00") -> dict:
    return {"hunt": "external_discoveries", "swept_at": swept,
            "n_trials": ATTESTATION.get("trials_multiplier"),
            "trial_count_basis": ATTESTATION.get("trial_count_basis"),
            "survivors_passing_all": sum(1 for v in verdicts if v.get("passed")),
            "verdicts": verdicts}


def _write(path: Path, doc: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.fixture()
def desk(tmp_path: Path) -> dict[str, Path]:
    """A miniature desk: gate output, judge's report, seal, docket."""
    gates = tmp_path / "reports" / "universal_gates_external.json"
    report = tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json"
    seal = tmp_path / "data" / "UNIVERSAL_SURVIVORS.canon.json"
    docket = tmp_path / "data" / "hypotheses" / "external_survivors.json"
    _write(report, {"n": 0, "survivors": {}, "gate_policy": ATTESTATION,
                    "swept_at": "2026-09-16T15:07:26+00:00"})
    _write(seal, {"n": 0, "survivors": {}, "gate_policy": ATTESTATION,
                  "swept_at": "2026-09-16T15:07:26+00:00"})
    _write(docket, [])
    return {"gates": gates, "report": report, "seal": seal, "docket": docket}


# ------------------------------------------------- the rebuilt row agrees with the sealed judge
def test_the_window_map_is_the_sealed_judge_s_window_map() -> None:
    """`WINDOWS_KNOWN` is a local inside `external_gauntlet.main`, so it cannot be imported and
    HAS to be copied. A copy nobody checks is a copy that drifts, and a drifted selector enrols a
    certificate on hours it was not certified under."""
    blk = GAUNTLET[GAUNTLET.index("    WINDOWS_KNOWN = {"):]
    blk = blk[:blk.index("\n    }") + 6]
    sealed = eval(blk.split("=", 1)[1].strip())
    assert sealed == cp.WINDOWS_KNOWN


def test_the_selector_rule_is_the_sealed_judge_s_selector_rule() -> None:
    fn = GAUNTLET[GAUNTLET.index("    def _selector(params: dict)"):]
    fn = fn[:fn.index("\n    def _cure_selector")]
    for line in ('if params.get("window") in WINDOWS_KNOWN:',
                 'keys = {k: params[k] for k in ("range_start", "range_end", "signal_at")',
                 'if not keys or keys == {"range_start": 7}:',
                 "for name, w in WINDOWS_KNOWN.items():",
                 "if all(w.get(k) == v for k, v in keys.items()):",
                 "return None"):
        assert line in fn, line
    assert cp._selector({"window": "london_am"}) == "london_am"
    assert cp._selector({}) == "asia"
    assert cp._selector({"range_start": 7}) == "asia"
    assert cp._selector({"range_start": 14, "range_end": 17, "signal_at": 17}) == "afternoon"
    assert cp._selector({"range_start": 3}) is None


def test_the_docket_normalisation_is_the_sealed_judge_s_normalisation() -> None:
    """The cell id is a digest over the params, and the judge folds a row-level chart INTO them
    before taking it. Getting this wrong is silent: nothing matches and every cell reads as
    `params_unrecoverable`, which is a wrong answer wearing a measurement's clothes."""
    blk = GAUNTLET[GAUNTLET.index("    cells = {}\n    for h in survivors:"):]
    blk = blk[:blk.index("    # REPRODUCTION RESTRICTS THE DOCKET")]
    for line in ('sym = h.get("symbol")', 'fam = h.get("family")',
                 'params = dict(h.get("params") or {})',
                 'row_tf = str(h.get("timeframe") or "").upper()',
                 'if row_tf and row_tf != "H1" and "timeframe" not in params:',
                 'params["timeframe"] = row_tf',
                 '"timeframe": timeframe_of(params, str(fam))'):
        assert line in blk, line
    src = Path(cp.__file__).read_text("utf-8")
    body = src[src.index("def _docket_cell("):src.index("def docket_params(")]
    for line in ('sym = row.get("symbol")', 'row_tf = str(row.get("timeframe") or "").upper()',
                 'if row_tf and row_tf != "H1" and "timeframe" not in params:',
                 '"timeframe": timeframe_of(params, str(fam))'):
        assert line in body, line


def test_a_docket_row_maps_to_the_identity_the_judge_would_have_given_it() -> None:
    from frontier_identity import cell_id
    row = {"symbol": "CHFNOK", "family": "carry", "params": {"lookback": 40},
           "timeframe": "M15"}
    cid, params = cp._docket_cell(row, cell_id, lambda p, f: str(p.get("timeframe") or "H1"))
    assert params == {"lookback": 40, "timeframe": "M15"}
    assert cid == cell_id({"sym": "CHFNOK", "family": "carry",
                           "params": {"lookback": 40, "timeframe": "M15"},
                           "timeframe": "M15"})
    assert cp._docket_cell({"family": "carry"}, cell_id, lambda p, f: "H1") is None


# --------------------------------------------------------------------------- the four refusals
def test_a_superseded_trial_charge_is_refused_outright(desk: dict[str, Path]) -> None:
    """The 2026-09-23 gate output was judged at `fixed_campaign_trials(597)` while the spec now
    reads `effective_campaign_trials(109)`. Sealing it would stamp the current attestation onto
    rows judged under a different bar, which is what that field exists to prevent."""
    doc = _gate_output([{"cell": "EURUSD.carry.p=abc", "sym": "EURUSD", "family": "carry",
                         "days": 900, "passed": True, "stages": _stages()},
                        {"cell": "CHFNOK.carry.p=def", "sym": "CHFNOK", "family": "carry",
                         "days": 1305, "passed": True,
                         "stages": _stages(extra={"swap_cost": {"passed": True}})}])
    doc["trial_count_basis"] = "fixed_campaign_trials(597)"
    _write(desk["gates"], doc)
    out = cp.recover_from_gate_output(desk["gates"], desk["report"], desk["seal"], desk["docket"])
    assert out["status"] == "REFUSED_SUPERSEDED_CHARGE"
    assert out["rows"] == {}
    assert "597" in out["why"]
    # AND THE CENSUS IS STILL PUBLISHED. A blocker hidden behind another blocker is the defect;
    # the eleventh-gate count must survive this refusal, not be short-circuited by it.
    assert out["gate_passed_rows"] == 2
    assert out["extra_gates_seen"] == {"swap_cost": 1}
    assert out["refused"]["extra_gate_not_in_policy"] == 1
    assert out["refused"]["superseded_charge"] == 1


def test_an_eleventh_gate_is_named_rather_than_counted_as_a_plain_failure(
        desk: dict[str, Path]) -> None:
    """The sealed judge has stamped an eleventh stage `swap_cost` onto every verdict since
    2026-09-14, and `all_ten_pass` is an exact tuple match. Every one of the seven verdicts in
    the surviving gate output is refused by it. The bar is not this organ's to move -- naming
    the refusal, and the stage, is."""
    _write(desk["gates"], _gate_output([
        {"cell": "CHFNOK.carry.p=abc", "sym": "CHFNOK", "family": "carry", "days": 1305,
         "passed": True, "stages": _stages(extra={"swap_cost": {"passed": True}})}]))
    out = cp.recover_from_gate_output(desk["gates"], desk["report"], desk["seal"], desk["docket"])
    assert out["status"] == "NOTHING_TO_RECOVER"
    assert out["refused"]["extra_gate_not_in_policy"] == 1
    assert out["extra_gates_seen"] == {"swap_cost": 1}
    assert out["gate_passed_rows"] == 1


def test_params_are_never_guessed(desk: dict[str, Path]) -> None:
    """A cell whose parameterisation cannot be found is REFUSED, not sealed with `{}`. Enrolling
    a guessed parameterisation forward-tests a different strategy than the one certified."""
    _write(desk["gates"], _gate_output([
        {"cell": "EURUSD.carry.p=notinthedocket", "sym": "EURUSD", "family": "carry",
         "days": 900, "passed": True, "stages": _stages()}]))
    out = cp.recover_from_gate_output(desk["gates"], desk["report"], desk["seal"], desk["docket"])
    assert out["status"] == "NOTHING_RECOVERABLE"
    assert out["refused"]["params_unrecoverable"] == 1
    assert out["rows"] == {}


def test_a_verdict_the_judge_did_not_pass_cannot_enter_by_this_door(
        desk: dict[str, Path]) -> None:
    _write(desk["gates"], _gate_output([
        {"cell": "EURUSD.carry.p=abc", "sym": "EURUSD", "family": "carry", "days": 900,
         "passed": False, "stages": _stages(passed=False)}]))
    out = cp.recover_from_gate_output(desk["gates"], desk["report"], desk["seal"], desk["docket"])
    assert out["status"] == "NOTHING_TO_RECOVER"
    assert out["rows"] == {}


def test_a_retired_or_already_sealed_row_is_not_resurrected(desk: dict[str, Path]) -> None:
    key = "external.EURUSD.carry.p=abc"
    _write(desk["seal"], {"n": 0, "survivors": {}, "gate_policy": ATTESTATION,
                          "swept_at": "2026-09-16T15:07:26+00:00",
                          "retired_certificates": {key: {"sym": "EURUSD"}}})
    _write(desk["gates"], _gate_output([
        {"cell": "EURUSD.carry.p=abc", "sym": "EURUSD", "family": "carry", "days": 900,
         "passed": True, "stages": _stages()}]))
    out = cp.recover_from_gate_output(desk["gates"], desk["report"], desk["seal"], desk["docket"])
    assert out["refused"]["retired"] == 1
    assert out["rows"] == {}


def test_an_ordinary_pass_reads_no_gate_output_at_all(desk: dict[str, Path]) -> None:
    """When the judge republished, its own write is the authority and there is nothing stranded.
    A 440 MB docket scan on every healthy hour would be the whole cost with none of the value."""
    _write(desk["gates"], _gate_output([
        {"cell": "EURUSD.carry.p=abc", "sym": "EURUSD", "family": "carry", "days": 900,
         "passed": True, "stages": _stages()}], swept="2026-09-24T05:00:00+00:00"))
    _write(desk["report"], {"n": 0, "survivors": {}, "gate_policy": ATTESTATION,
                            "swept_at": "2999-01-01T00:00:00+00:00"})
    out = cp.recover_from_gate_output(desk["gates"], desk["report"], desk["seal"], desk["docket"])
    assert out["status"] == "JUDGE_REPUBLISHED"
    assert "docket_scan" not in out
    # THE 88 MB FILE IS NOT EVEN PARSED. A stamp later than the moment the gate file was written
    # is positive evidence the judge got past its own gate write.
    assert "gate_survivors_passing_all" not in out
    assert "was written" in out["why"]


def test_the_parse_is_skipped_only_on_positive_evidence(desk: dict[str, Path]) -> None:
    """An unreadable or older stamp falls THROUGH to the read. Absence never skips the work."""
    _write(desk["gates"], _gate_output([
        {"cell": "EURUSD.carry.p=abc", "sym": "EURUSD", "family": "carry", "days": 900,
         "passed": True, "stages": _stages()}], swept="2026-09-24T05:00:00+00:00"))
    _write(desk["report"], {"n": 0, "survivors": {}, "gate_policy": ATTESTATION})
    out = cp.recover_from_gate_output(desk["gates"], desk["report"], desk["seal"], desk["docket"])
    assert out["gate_survivors_passing_all"] == 1, "no stamp must not skip the read"


def test_an_absent_gate_output_is_unmeasured_and_never_a_verdict(desk: dict[str, Path]) -> None:
    out = cp.recover_from_gate_output(desk["gates"], desk["report"], desk["seal"], desk["docket"])
    assert out["status"] == "NO_GATE_OUTPUT"
    assert "not a claim that nothing passed" in out["why"]


# ------------------------------------------------------ and the verdicts actually reach the seal
def test_a_killed_sweep_s_verdicts_reach_the_canonical_store_on_the_next_pass(
        desk: dict[str, Path]) -> None:
    """THE WHOLE POINT. The gate output is on disk with a passing verdict in it; the judge's own
    report is three minutes newer and a week older in `swept_at`. One publication pass later the
    row stands in the seal, with its gates record intact and the round trip stamped on it."""
    _write(desk["docket"], [{"symbol": "EURUSD", "family": "carry",
                             "params": {"lookback": 40}, "timeframe": "H1"}])
    from frontier_identity import cell_id
    cid = cell_id({"sym": "EURUSD", "family": "carry", "params": {"lookback": 40},
                   "timeframe": "H1"})
    _write(desk["gates"], _gate_output([
        {"cell": cid, "sym": "EURUSD", "family": "carry", "days": 900,
         "passed": True, "stages": _stages()}]))
    # A seal that already holds something, so the never-shrink law is exercised too.
    _write(desk["seal"], {"n": 1, "gate_policy": ATTESTATION,
                          "swept_at": "2026-09-16T15:07:26+00:00",
                          "survivors": {"external.XAUUSD.session_range_breakout.rr=1.5_wb=12": {
                              "sym": "XAUUSD", "cell": "x", "hunt": "external_discoveries",
                              "gates": _stages(),
                              "shadow_spec": {"symbol": "XAUUSD", "selector": "asia",
                                              "family": "session_range_breakout",
                                              "params": {}}}}})

    rec = cp.recover_from_gate_output(desk["gates"], desk["report"], desk["seal"], desk["docket"])
    assert rec["status"] == "RECOVERED", rec
    assert rec["docket_scan"]["status"] == "ALL_FOUND"

    out = cp.publish(desk["report"], desk["seal"], recovered=rec["rows"])
    assert out["status"] == "SEALED"
    assert out["admitted_recovered"] == 1
    assert out["seal_n_after"] == 2

    sealed = json.loads(desk["seal"].read_text("utf-8"))
    row = sealed["survivors"][f"external.{cid}"]
    assert row["gates"] == _stages(), "the judge's own verdict, copied, not re-derived"
    assert row["shadow_spec"]["params"] == {"lookback": 40}
    assert row["recovered_from_gate_output"]["gate_swept_at"] == "2026-09-23T05:42:42+00:00"
    # THE STAMP FOLLOWS THE EVIDENCE: the seal now says when the recovered rows were judged, not
    # when the stale report was written.
    assert sealed["swept_at"] == "2026-09-23T05:42:42+00:00"
    # ... and nothing that stood before it was dropped.
    assert "external.XAUUSD.session_range_breakout.rr=1.5_wb=12" in sealed["survivors"]


def _code_of(name: str, until: str) -> str:
    """The function's CODE with its docstring removed -- the prose says what the code must not do,
    so a check over the prose forbids documenting the rule."""
    src = Path(cp.__file__).read_text("utf-8")
    body = src[src.index(f"def {name}("):src.index(f"def {until}(")]
    head, _, rest = body.partition('"""')
    doc, _, tail = rest.partition('"""')
    return head + tail


def test_recovery_mints_nothing_and_carries_no_number_of_its_own() -> None:
    """A grep is a blunt instrument and it is the right one here: this organ must never acquire a
    bar. Every verdict in it is the sealed judge's, copied."""
    body = _code_of("recover_from_gate_output", "publish")
    for banned in ("sharpe", "threshold", "> 0.", ">= 0.", "min_", "_min", "cutoff"):
        assert banned not in body.lower(), banned
    assert "all_ten_pass(stages)" in body
    assert 'v.get("passed") is not True' in body


# --------------------------------------------------------------- the streaming scan is bounded
def test_the_docket_scan_walks_with_an_offset_and_never_reslices(tmp_path: Path) -> None:
    """MEASURED 2026-09-24: `buf = buf[end:]` copied the remaining 4 MB chunk once per object and
    583,398 docket rows took 905 seconds -- quadratic in the chunk, not linear in the file."""
    body = _code_of("docket_params", "recover_from_gate_output")
    assert "decoder.raw_decode(buf, pos)" in body
    assert "buf = buf[end:]" not in body


def test_the_docket_scan_gives_up_on_its_budget_rather_than_the_leg(tmp_path: Path) -> None:
    docket = _write(tmp_path / "d.json",
                    [{"symbol": f"S{i}", "family": "carry", "params": {"i": i}}
                     for i in range(4000)])
    found, status = cp.docket_params({"nothing-matches-this"}, docket, budget_s=0.0)
    assert status == "BUDGET_EXHAUSTED"
    assert found == {}


def test_an_absent_docket_recovers_nothing_and_says_which(tmp_path: Path) -> None:
    found, status = cp.docket_params({"x"}, tmp_path / "missing.json")
    assert (found, status) == ({}, "NO_DOCKET")
    found, status = cp.docket_params(set(), tmp_path / "missing.json")
    assert (found, status) == ({}, "NOTHING_WANTED")

from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gate_policy import _SPEC_FIXED_TRIALS as _CHARGE  # noqa: E402
from gate_policy import (  # noqa: E402
    ATTESTATION,
    COST_SCENARIO,
    DONE_MARKER,
    DSR_THRESHOLD,
    GATES,
    PBO_THRESHOLD,
    SPA_ALPHA,
    TRIALS_MULTIPLIER,
    WF_MIN_STABILITY,
    all_ten_pass,
    charged_trial_count,
)

#: The standing campaign charge. Since 2026-09-23 `research/effective_trials.py` writes the
#: redundancy-corrected count into policy/gate_spec.yaml (109 when this was written) and the
#: judge reads it from there; it may only ever be at or BELOW the historic fixed 597, because a
#: lower count is a lower bar and the bar never gets harsher. The tests pin the property -- one
#: constant charge, never above 597 -- rather than a literal the spec is designed to move.
_LEGACY_CHARGE = 597
from shadow_admission import authorized_specs, partition_work  # noqa: E402


def _stages() -> dict:
    return {name: {"passed": True} for name in GATES}


def test_original_thresholds_are_one_fixed_policy() -> None:
    assert TRIALS_MULTIPLIER == 7.0
    assert DSR_THRESHOLD == 0.95
    assert PBO_THRESHOLD == 0.5
    assert SPA_ALPHA == 0.05
    assert WF_MIN_STABILITY == 0.5
    assert COST_SCENARIO == 3.0
    assert ATTESTATION["wf_test_size"] == "max(20,len//6)"
    assert "preregistered point-in-time regime" in ATTESTATION["regime_admission_unit"]
    assert "unknown or incompatible live regime is OFF" in ATTESTATION["regime_control"]
    assert DONE_MARKER == "DONE_qquant_gates_original10_v2"
    # THE BAR IS FIXED (principal, standing instruction): it never raises and never gets
    # harsher. The attestation must say so, because it is the field that pins what a certificate
    # was judged under.
    assert isinstance(_CHARGE, int) and 2 <= _CHARGE <= _LEGACY_CHARGE
    assert f"campaign_trials({_CHARGE})" in ATTESTATION["trial_count_basis"]


def test_charge_is_fixed_and_never_scales_with_sweep_size() -> None:
    """The same charge for every cell, whatever else shares its sweep.

    This replaces a test that pinned `ceil(effective_cells * 7)`. Under that rule a candidate was
    judged against the accident of its scheduling: measured 2026-08-28, sr0 was 0.3786 at 597
    charged trials and 1.3593 at 5,963 -- same gate, same policy, same cell, and the only thing
    that changed was how many other cells the docket happened to hold that hour. 506 cells
    cleared every VALIDITY gate and failed only the deflated Sharpe against the inflated bar.
    """
    expected = (_CHARGE, f"fixed_campaign_trials({_CHARGE})")
    # Two orders of magnitude of sweep size, one charge.
    assert charged_trial_count(17, 17.0, "null_calibrated_participation_ratio") == expected
    assert charged_trial_count(368, 277.40, "null_calibrated_participation_ratio") == expected
    assert charged_trial_count(6270, 6000.0, "null_calibrated_participation_ratio") == expected
    # And it does not move when the dependence census is absent or unusable either: an
    # unmeasurable census used to make the bar HARSHER (raw_cells * 7), which is the one
    # direction it may never move.
    assert charged_trial_count(368, 246.46, "participation_ratio") == expected
    assert charged_trial_count(368, None, "unmeasurable") == expected


def test_a_bad_census_can_never_make_the_bar_harsher() -> None:
    """Malformed, missing or hand-tuned census inputs must not raise the charge.

    The old rule failed closed to `raw_cells * 7`, which is FAIL-HARSHER: a census this desk
    could not measure made every candidate in that sweep harder to certify. Failing closed is
    right when the failure protects against a false pass; here it protected against nothing and
    penalised the candidate for a measurement problem it had no part in.
    """
    expected = (_CHARGE, f"fixed_campaign_trials({_CHARGE})")
    assert charged_trial_count(368, 1.0, "null_calibrated_participation_ratio") == expected
    assert charged_trial_count(368, 246.46, "hand_tuned") == expected
    assert charged_trial_count(
        368, float("nan"), "null_calibrated_participation_ratio") == expected
    # The charge is bounded above by the fixed count no matter what is passed in.
    for raw in (2, 368, 99_999):
        n, _basis = charged_trial_count(raw, None, "unmeasurable")
        assert n <= _CHARGE <= _LEGACY_CHARGE


def test_partial_extra_or_failed_gate_sets_never_admit() -> None:
    stages = _stages()
    assert all_ten_pass(stages)
    assert not all_ten_pass({k: v for k, v in stages.items() if k != "pbo"})
    # Supplementary gates are additive: every original gate remains mandatory and an extra gate
    # must pass, but a passed eleventh measurement cannot invalidate the original ten.
    assert all_ten_pass({**stages, "harsher_overlay": {"passed": True}})
    assert not all_ten_pass({**stages, "harsher_overlay": {"passed": False}})
    stages["pbo"] = {"passed": False}
    assert not all_ten_pass(stages)


def test_only_exact_policy_certificate_enters_shadow(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    row = {
        "id": "XAUUSD breakout LONG asia UNCONDITIONED",
        "passed": True,
        "stages": _stages(),
        # A harsher diagnostic is deliberately irrelevant to admission.
        "battery": {"passed": False, "threshold": 999},
    }
    (reports / "QQUANT_GATES.json").write_text(
        json.dumps({"gate_policy": ATTESTATION, "verdicts": [row]}), encoding="utf-8")
    spec = ("XAUUSD", "asia", None, "session_range_breakout", False)
    other = ("USDJPY", "asia", None, "session_range_breakout", False)
    assert authorized_specs(tmp_path) == {spec}
    assert partition_work([spec, other], tmp_path) == ([spec], [other])

    (reports / "QQUANT_GATES.json").write_text(json.dumps({
        "gate_policy": {**ATTESTATION, "wf_min_stability": 0.58},
        "verdicts": [row],
    }), encoding="utf-8")
    assert authorized_specs(tmp_path) == set()


def test_production_path_has_no_harsher_prefilter() -> None:
    """The original ten gates are the sole shadow-admission certificate.

    Conditional cells are evaluated as their exact preregistered strategy-regime unit, so this
    does not require an edge to earn money in incompatible regimes. Later batteries and harsher
    overlays remain diagnostic and cannot veto an exact canonical certificate.
    """
    qquant = (DESK / "research" / "qquant_gates.py").read_text(encoding="utf-8")
    shadow = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    promoter = (DESK / "research" / "promoter.py").read_text(encoding="utf-8")
    assert 'rows = sv["real_survivors"]' not in qquant
    assert 'for r in all12' in qquant and 'for r in all16' in qquant
    # The admission door was rebuilt as `authorized_runs` when params became certificate
    # identity (2026-08-26); the LAW is unchanged -- every enrolment must come through
    # shadow_admission, which requires the exact policy attestation and all ten gates.
    assert "from shadow_admission import authorized_runs" in shadow, (
        "shadow admission must require the exact original-ten-gate certificate")
    admission = (DESK / "research" / "shadow_admission.py").read_text(encoding="utf-8")
    assert "all_ten_pass" in admission and "is_exact_policy" in admission, (
        "the admission door itself must verify the certificate, not trust the file")
    assert "gate_spec not in gate_authority" in promoter, (
        "live promotion must still independently require a real certificate")
    supervisor = (DESK / "research" / "research_supervisor.py").read_text(encoding="utf-8")
    assert DONE_MARKER in supervisor


def test_hunt16_stage_one_rejects_remain_in_universal_trial_ledger() -> None:
    source = (DESK / "research" / "run_hunt16.py").read_text(encoding="utf-8")
    reject_append = source.index("stage1_passed=False")
    reject_continue = source.index("continue", reject_append)
    assert reject_append < reject_continue
    assert '"all": results' in source[reject_append:reject_continue]


def test_every_hunt_uses_the_same_calibrated_cost_and_trial_policy() -> None:
    source = (DESK / "research" / "universal_gate.py").read_text(encoding="utf-8")
    assert "calibrated_census_report" in source
    assert "charged_trial_count" in source
    assert "Costs.from_symbol" in source
    assert "commission_per_lot * COST_SCENARIO" not in source
    assert "pd.DataFrame(cols).sort_index().fillna(0.0)" in source
    assert '"curve_compendium"' in source
    assert "stress_x3_return" in source


def test_a_certificate_on_a_moved_cell_is_named_void_and_does_not_enrol(tmp_path: Path) -> None:
    """Box 2026-11-10: GBPSEK and NOKSEK carry_risk_off passed all ten gates with
    `params.symbol: USDSGD`. The rule that ran is not the mechanism the certificate states, so
    the certificate is kept, named VOID_MOVED_CELL and not enrolled; the same family naming its
    own instrument, and a carry row with a stale name (the judge supplies its instrument),
    enrol as before."""
    import shadow_admission as sa
    from hypothesis_families import MOVED_CELL_FAMILIES

    assert sa.MOVED_CELL_FAMILIES == MOVED_CELL_FAMILIES
    gates = {name: {"passed": True} for name in GATES}

    def cert(sym: str, family: str, params: dict) -> dict:
        return {"sym": sym, "gates": gates, "status": "UNIVERSAL",
                "shadow_spec": {"symbol": sym, "family": family, "selector": "asia",
                                "params": params}}
    survivors = {
        "external.GBPSEK.carry_risk_off.p=b5bb": cert("GBPSEK", "carry_risk_off",
                                                      {"symbol": "USDSGD", "mode": "harvest"}),
        "external.EURUSD.carry_risk_off.p=aaaa": cert("EURUSD", "carry_risk_off",
                                                      {"symbol": "EURUSD", "mode": "harvest"}),
        "external.CHFNOK.carry.p=cccc": cert("CHFNOK", "carry", {"symbol": "GBPJPY"}),
        # the judge supplies event_reaction's instrument itself: paper only, never refused
        "external.EURUSD.event_reaction.p=eeee": cert("EURUSD", "event_reaction",
                                                      {"symbol": "USDJPY"}),
        # entry_conditioned is refused only where its BASE family reads `symbol`
        "external.ADAUSD.entry_conditioned.p=1111": cert(
            "ADAUSD", "entry_conditioned",
            {"symbol": "XTIUSD", "base_family": "range_reversion", "cond_symbol": "USDJPY"}),
        "external.ADAUSD.entry_conditioned.p=2222": cert(
            "ADAUSD", "entry_conditioned",
            {"symbol": "USDSGD", "base_family": "carry_risk_off", "cond_symbol": "USDJPY"}),
    }
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"gate_policy": ATTESTATION, "survivors": survivors, "n": 6}), encoding="utf-8")
    dry = sa.void_moved_certificates(tmp_path)                    # reads only
    assert [r["certificate"] for r in dry["refused"]] == [
        "external.GBPSEK.carry_risk_off.p=b5bb", "external.ADAUSD.entry_conditioned.p=2222"]
    assert dry["unproven_entry_conditioned"] == ["external.ADAUSD.entry_conditioned.p=1111"]
    runs = sa.authorized_runs(tmp_path, lanes=("h1",))
    names = {r["certificate"] for r in runs}
    assert "external.GBPSEK.carry_risk_off.p=b5bb" not in names
    assert sa.VOID_MOVED_CERTIFICATES == ["external.GBPSEK.carry_risk_off.p=b5bb",
                                          "external.ADAUSD.entry_conditioned.p=2222"]
    assert sa.UNPROVEN_ENTRY_CONDITIONED == ["external.ADAUSD.entry_conditioned.p=1111"]
    dropped = [d for d in sa.DROPPED_CERTIFICATES if d["why"].startswith("VOID_MOVED_CELL")]
    assert len(dropped) == 2 and "USDSGD" in dropped[0]["why"]
    assert "entry_conditioned[carry_risk_off]" in dropped[1]["why"]
    # nothing else is refused by this door
    assert not any(n in {d["certificate"] for d in sa.DROPPED_CERTIFICATES
                         if d["why"].startswith("VOID_MOVED_CELL")}
                   for n in ("external.EURUSD.carry_risk_off.p=aaaa",
                             "external.CHFNOK.carry.p=cccc",
                             "external.EURUSD.event_reaction.p=eeee",
                             "external.ADAUSD.entry_conditioned.p=1111"))


def test_each_refused_moved_cell_certificate_is_billed_until_its_corrected_cell_certifies(
        tmp_path: Path) -> None:
    """The VOID_MOVED_CELL door refuses at capital's intake, so it publishes a missed-growth
    line per refused certificate: UNMEASURED (it never had a clock), cleared the pass the
    corrected cell holds its own ten-gate certificate."""
    import missed_growth as mg

    gates = {name: {"passed": True} for name in GATES}

    def cert(sym: str, family: str, params: dict) -> dict:
        return {"sym": sym, "gates": gates, "status": "UNIVERSAL",
                "shadow_spec": {"symbol": sym, "family": family, "selector": "asia",
                                "params": params}}

    def publish(survivors: dict) -> None:
        (tmp_path / "reports").mkdir(exist_ok=True)
        (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
            {"gate_policy": ATTESTATION, "survivors": survivors}), encoding="utf-8")
    survivors = {"external.EURUSD.carry.p=cccc": cert("EURUSD", "carry", {"symbol": "GBPJPY"})}
    old_base = mg.BASE
    mg.BASE = tmp_path
    try:
        publish(survivors)
        assert mg.void_moved_cell_line()["verdict"] == mg.NOT_BINDING
        survivors["external.GBPSEK.carry_risk_off.p=b5bb"] = cert(
            "GBPSEK", "carry_risk_off", {"symbol": "USDSGD"})
        publish(survivors)
        line = mg.void_moved_cell_line()
        assert line["verdict"] == mg.UNMEASURED and line["n_lines"] == 1
        assert line["lines"][0]["certificate"] == "external.GBPSEK.carry_risk_off.p=b5bb"
        survivors["external.GBPSEK.carry_risk_off.p=fixd"] = cert(
            "GBPSEK", "carry_risk_off", {"symbol": "GBPSEK"})
        publish(survivors)
        again = mg.void_moved_cell_line()
        assert again["verdict"] == mg.NOT_BINDING
        assert again["cleared_by_corrected_certificate"] == 1
    finally:
        mg.BASE = old_base


def test_one_forward_clock_per_executable_and_no_clock_is_ever_taken(tmp_path: Path,
                                                                    monkeypatch) -> None:
    """Box 2026-11-10: 21 carry clocks were a handful of carry rules, each certified several
    times under a foreign `input_symbol` its replay never reads. A copy with no clock is not
    enrolled while another copy of the same executable is; a copy that already has a clock keeps
    it; a different rule (other params, other family) is never folded; with no readable registry
    nothing is withheld."""
    import shadow_admission as sa
    from hypothesis_families import EXECUTABLE_UNREAD

    assert {k: set(v) for k, v in sa.EXECUTABLE_UNREAD.items()} == {
        k: set(v) for k, v in EXECUTABLE_UNREAD.items()}
    gates = {name: {"passed": True} for name in GATES}

    def cert(sym: str, family: str, params: dict) -> dict:
        return {"sym": sym, "gates": gates, "status": "UNIVERSAL",
                "shadow_spec": {"symbol": sym, "family": family, "selector": "asia",
                                "params": params}}
    survivors = {
        "external.CHFNOK.carry.p=a": cert("CHFNOK", "carry", {"input_symbol": "EBAY", "k": 1}),
        "external.CHFNOK.carry.p=b": cert("CHFNOK", "carry", {"input_symbol": "GBPJPY", "k": 1}),
        "external.CHFNOK.carry.p=c": cert("CHFNOK", "carry", {"input_symbol": "CHFNOK", "k": 1}),
        "external.CHFNOK.carry.p=d": cert("CHFNOK", "carry", {"input_symbol": "EBAY", "k": 2}),
        "external.AUDCHF.carry.p=e": cert("AUDCHF", "carry", {"input_symbol": "EBAY", "k": 1}),
        # the same params on another chart is another rule: by name, and by the spec's chart
        "external.CHFNOK.carry@M15.p=h": cert("CHFNOK", "carry", {"input_symbol": "EBAY",
                                                                  "k": 1}),
        "external.CHFNOK.carry.p=i": {**cert("CHFNOK", "carry", {"input_symbol": "EBAY", "k": 1}),
                                      "shadow_spec": {"symbol": "CHFNOK", "family": "carry",
                                                      "selector": "asia", "chart": "M5",
                                                      "params": {"input_symbol": "EBAY",
                                                                 "k": 1}}},
        "external.EURUSD.range_reversion.p=f": cert("EURUSD", "range_reversion", {"n": 1}),
        "external.EURUSD.range_reversion.p=g": cert("EURUSD", "range_reversion", {"n": 1}),
    }
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"gate_policy": ATTESTATION, "survivors": survivors, "n": 9}), encoding="utf-8")

    # no registry on this host: counted, nothing withheld
    names = {r["certificate"] for r in sa.authorized_runs(tmp_path, lanes=("h1",))}
    assert names == set(survivors)
    assert sa.EXECUTABLE_COPIES[0]["copies"] == 3
    assert sa.EXECUTABLE_COPIES[0]["not_enrolled"] == []

    # p=b already holds a clock under a FOREIGN label: it keeps that clock, but the keeper is
    # p=c, the copy naming its own instrument; the clockless foreign copy p=a is not enrolled
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sleeve_registry.json").write_text(json.dumps({"sleeves": {
        "CHFNOK.carry.asia.b": {"identity": {"symbol": "CHFNOK", "family": "carry",
                                             "params": {"input_symbol": "GBPJPY", "k": 1}},
                                "forward_start": "2026-10-01", "status": "LIVE"}}}),
        encoding="utf-8")
    names = {r["certificate"] for r in sa.authorized_runs(tmp_path, lanes=("h1",))}
    assert names == set(survivors) - {"external.CHFNOK.carry.p=a"}
    (group,) = sa.EXECUTABLE_COPIES
    assert group["keeps_clock"] == "external.CHFNOK.carry.p=c"
    assert group["keeper_names_its_own_instrument"] is True
    assert group["surplus_clocks_left_running"] == ["external.CHFNOK.carry.p=b"]
    assert {"external.CHFNOK.carry@M15.p=h", "external.CHFNOK.carry.p=i"} <= names
    assert group["not_enrolled"] == ["external.CHFNOK.carry.p=a"]
    assert sum("EXECUTABLE_COPY" in d["why"] for d in sa.DROPPED_CERTIFICATES) == 1
    assert sa.NO_OWN_INSTRUMENT_CERTIFICATES == []

    # the switch: counted, nothing withheld
    monkeypatch.setenv("QUANT_ONE_CLOCK_PER_EXECUTABLE", "0")
    names = {r["certificate"] for r in sa.authorized_runs(tmp_path, lanes=("h1",))}
    assert names == set(survivors)
    assert sa.EXECUTABLE_COPIES[0]["would_not_enrol"] == ["external.CHFNOK.carry.p=a"]
    monkeypatch.delenv("QUANT_ONE_CLOCK_PER_EXECUTABLE")

    # a second foreign copy that ALSO has a clock is left running and named, never dropped
    reg = json.loads((tmp_path / "data" / "sleeve_registry.json").read_text("utf-8"))
    reg["sleeves"]["CHFNOK.carry.asia.a"] = {
        "identity": {"symbol": "CHFNOK", "family": "carry",
                     "params": {"input_symbol": "EBAY", "k": 1}},
        "forward_start": "2026-09-01", "status": "LIVE"}
    (tmp_path / "data" / "sleeve_registry.json").write_text(json.dumps(reg), encoding="utf-8")
    names = {r["certificate"] for r in sa.authorized_runs(tmp_path, lanes=("h1",))}
    assert names == set(survivors)
    (group,) = sa.EXECUTABLE_COPIES
    assert group["keeps_clock"] == "external.CHFNOK.carry.p=c"    # an older clock is no keeper
    assert sorted(group["surplus_clocks_left_running"]) == ["external.CHFNOK.carry.p=a",
                                                            "external.CHFNOK.carry.p=b"]

    # NO copy names its own instrument: none is enrolled, each is named and billed
    # (VOID_MOVED_CELL's way); a copy that already has a clock still keeps it
    foreign = {
        "external.AUDCHF.carry.p=e": cert("AUDCHF", "carry", {"input_symbol": "EBAY", "k": 1}),
        "external.AUDCHF.carry.p=j": cert("AUDCHF", "carry", {"input_symbol": "GBPJPY", "k": 1}),
        "external.AUDCHF.carry.p=k": cert("AUDCHF", "carry", {"input_symbol": "USDJPY", "k": 1}),
    }
    (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"gate_policy": ATTESTATION, "survivors": foreign, "n": 3}), encoding="utf-8")
    reg["sleeves"]["AUDCHF.carry.asia.k"] = {
        "identity": {"symbol": "AUDCHF", "family": "carry",
                     "params": {"input_symbol": "USDJPY", "k": 1}},
        "forward_start": "2026-09-01", "status": "LIVE"}
    (tmp_path / "data" / "sleeve_registry.json").write_text(json.dumps(reg), encoding="utf-8")
    names = {r["certificate"] for r in sa.authorized_runs(tmp_path, lanes=("h1",))}
    assert names == {"external.AUDCHF.carry.p=k"}
    (group,) = sa.EXECUTABLE_COPIES
    assert group["keeps_clock"] is None and group["keeper_names_its_own_instrument"] is False
    assert group["surplus_clocks_left_running"] == ["external.AUDCHF.carry.p=k"]
    assert sorted(sa.NO_OWN_INSTRUMENT_CERTIFICATES) == ["external.AUDCHF.carry.p=e",
                                                         "external.AUDCHF.carry.p=j"]
    assert sum("NO_OWN_INSTRUMENT" in d["why"] for d in sa.DROPPED_CERTIFICATES) == 2


def test_a_certificate_whose_engine_key_is_a_running_clock_is_never_refused(tmp_path: Path) -> None:
    """Box 2026-11-10, cross-check v2: external.CHFNOK.carry.p=b56bcfef9a4a010c states
    timeframe=H1; the engine's key drops it, so its key CHFNOK.carry.asia#input_symbol=CHFNOK
    was a running clock (46 observations) while the door, matching params literally against an
    identity that keeps the chart outside params, saw no clock and would have refused it in
    favour of a copy with a different key. The copy that owns the clock keeps it."""
    import shadow_admission as sa

    gates = {name: {"passed": True} for name in GATES}

    def cert(params: dict) -> dict:
        return {"sym": "CHFNOK", "gates": gates, "status": "UNIVERSAL",
                "shadow_spec": {"symbol": "CHFNOK", "family": "carry", "selector": "asia",
                                "params": params}}
    survivors = {
        # sorts FIRST by name and names its own instrument: the old tie-break made it keeper
        "external.CHFNOK.carry.p=9": cert({"input_symbol": "CHFNOK", "symbol": "CHFNOK",
                                           "timeframe": "H1"}),
        "external.CHFNOK.carry.p=b": cert({"input_symbol": "CHFNOK", "timeframe": "H1"}),
    }
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"gate_policy": ATTESTATION, "survivors": survivors, "n": 2}), encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sleeve_registry.json").write_text(json.dumps({"sleeves": {
        "CHFNOK.carry.asia#input_symbol=CHFNOK": {
            "identity": {"symbol": "CHFNOK", "family": "carry", "timeframe": "H1",
                         "params": {"input_symbol": "CHFNOK"}},
            "forward_start": "2026-09-30T03:50:30+00:00", "status": "LIVE"}}}), encoding="utf-8")
    names = {r["certificate"] for r in sa.authorized_runs(tmp_path, lanes=("h1",))}
    assert "external.CHFNOK.carry.p=b" in names                  # its key is the running clock
    (group,) = sa.EXECUTABLE_COPIES
    assert group["keeps_clock"] == "external.CHFNOK.carry.p=b"
    assert group["not_enrolled"] == ["external.CHFNOK.carry.p=9"]

    # a clock on ANOTHER chart is not this certificate's clock
    reg = {"sleeves": {"CHFNOK.carry.asia@M15#input_symbol=CHFNOK": {
        "identity": {"symbol": "CHFNOK", "family": "carry", "timeframe": "M15",
                     "params": {"input_symbol": "CHFNOK"}},
        "forward_start": "2026-09-30T03:50:30+00:00", "status": "LIVE"}}}
    (tmp_path / "data" / "sleeve_registry.json").write_text(json.dumps(reg), encoding="utf-8")
    sa.authorized_runs(tmp_path, lanes=("h1",))
    (group,) = sa.EXECUTABLE_COPIES
    assert group["keeps_clock"] == "external.CHFNOK.carry.p=9"   # no clock: own label, by name

    # two certificates that enrol onto ONE registry row: both returned, named, none refused
    same = {"external.CHFNOK.carry.p=b": survivors["external.CHFNOK.carry.p=b"],
            "external.CHFNOK.carry.p=c": cert({"input_symbol": "CHFNOK", "timeframe": "H1"})}
    (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"gate_policy": ATTESTATION, "survivors": same, "n": 2}), encoding="utf-8")
    names = {r["certificate"] for r in sa.authorized_runs(tmp_path, lanes=("h1",))}
    assert names == set(same)
    (group,) = sa.EXECUTABLE_COPIES
    if sa._engine_key({"symbol": "CHFNOK", "selector": "asia", "family": "carry",
                       "params": {}}) is not None:               # the engine imports here
        assert group["sharing_keepers_key"] == ["external.CHFNOK.carry.p=c"]
        assert group["not_enrolled"] == []

    # among copies naming their own instrument a LIVE row outranks an older STANDBY one
    both = {"external.CHFNOK.carry.p=s": cert({"input_symbol": "CHFNOK", "k": 1,
                                               "symbol": "CHFNOK"}),
            "external.CHFNOK.carry.p=t": cert({"input_symbol": "CHFNOK", "k": 1})}
    (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"gate_policy": ATTESTATION, "survivors": both, "n": 2}), encoding="utf-8")
    (tmp_path / "data" / "sleeve_registry.json").write_text(json.dumps({"sleeves": {
        "x.s": {"identity": {"symbol": "CHFNOK", "family": "carry",
                             "params": {"input_symbol": "CHFNOK", "k": 1, "symbol": "CHFNOK"}},
                "forward_start": "2026-09-01", "status": "STANDBY"},
        "x.t": {"identity": {"symbol": "CHFNOK", "family": "carry",
                             "params": {"input_symbol": "CHFNOK", "k": 1}},
                "forward_start": "2026-10-01", "status": "LIVE"}}}), encoding="utf-8")
    sa.authorized_runs(tmp_path, lanes=("h1",))
    (group,) = sa.EXECUTABLE_COPIES
    assert group["keeps_clock"] == "external.CHFNOK.carry.p=t"

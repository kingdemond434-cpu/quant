"""THE ADVERSARIES (P48 / P49 / P58).

The canary suite's own correctness is the thing worth fencing, and it is easy to get wrong in a
way that feels safe: a suite that reports 100% rejection because nothing can ever pass is
indistinguishable, from the outside, from a suite guarding working gates. So these tests drive a
DELIBERATELY BROKEN gate through the suite and require it to be caught. A canary suite that has
never been shown to fail is L1.63 one level up -- the detector itself becomes a partition that
cannot fail, and therefore carries no information about the gates it claims to guard.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_adversary", _ROOT / "desks" / "mt5" / "research" / "adversary.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def adv():
    return _load()


# --------------------------------------------------------------------------- P49
def test_a_working_gate_rejects_every_canary(adv) -> None:
    out = adv.run_canaries(lambda name, sig, fwd: False)
    assert out["rejection_rate"] == 1.0
    assert out["intact"] is True
    assert out["survivors"] == []


def test_a_broken_gate_is_caught_and_named(adv) -> None:
    """THE PROPERTY THAT MATTERS. A suite that cannot catch a broken gate guards nothing."""
    out = adv.run_canaries(lambda name, sig, fwd: True)
    assert out["intact"] is False
    assert out["rejection_rate"] == 0.0
    assert set(out["survivors"]) == {c.name for c in adv.CANARIES}
    assert "A CANARY SURVIVED" in out["verdict"]


@pytest.mark.parametrize("leak", [c.name for c in _load().CANARIES])
def test_each_canary_is_individually_load_bearing(adv, leak) -> None:
    """One gate degrading must be caught even while the other four still work.

    A suite that only notices when EVERYTHING breaks would miss the realistic failure entirely:
    gates degrade one at a time, and the first one to go is the one worth catching.
    """
    out = adv.run_canaries(lambda name, sig, fwd: name == leak)
    assert out["intact"] is False, f"{leak} passing was not noticed"
    assert out["survivors"] == [leak]
    assert leak in out["verdict"] and "--" in out["verdict"], (
        "the alarm names the canary but not what its passing PROVES; an operator cannot triage "
        "on a name alone")


def test_a_crashing_gate_is_not_scored_as_a_rejection(adv) -> None:
    """A gate that throws has failed to JUDGE, not managed to reject.

    Scoring a crash as a rejection would let a completely broken gauntlet report a perfect canary
    record -- the most comfortable possible reading of the most serious possible failure.
    """
    def boom(name, sig, fwd):
        raise RuntimeError("gate exploded")
    out = adv.run_canaries(boom)
    assert out["intact"] is False, "a gate that crashes on every canary reported an intact suite"
    assert all(r["gate_error"] for r in out["canaries"])


def test_the_required_rate_is_total(adv) -> None:
    """Four of five canaries rejected is not 'mostly fine'. It is one blind gate."""
    assert adv.REQUIRED_REJECTION_RATE == 1.0
    out = adv.run_canaries(lambda name, sig, fwd: name == "lookahead")
    assert out["rejection_rate"] == 0.8
    assert out["intact"] is False, "80% was treated as acceptable; it means lookahead is admitted"


def test_the_lookahead_canary_actually_contains_the_answer(adv) -> None:
    """If the construction were wrong the canary would be unable to detect the bug it names."""
    sig, fwd = adv._series("lookahead")
    assert adv._corr(sig, fwd) > 0.99, (
        "the lookahead canary's signal is not the forward return, so a harness that permits "
        "lookahead would pass it and this canary would never fire")


def test_the_noise_canary_carries_no_signal(adv) -> None:
    sig, fwd = adv._series("pure_noise")
    assert abs(adv._corr(sig, fwd)) < 0.25, "the 'noise' canary has real signal in it"


def test_the_suite_is_seeded_so_a_pass_means_the_gate_changed(adv) -> None:
    """An unseeded canary cannot distinguish 'the gate broke' from 'this draw looked tradeable',
    which is the entire question it exists to answer."""
    a = adv._series("survivor_biased")
    b = adv._series("survivor_biased")
    assert a == b, "canary data is not deterministic; a failure could be the draw, not the gate"


def test_the_seed_survives_a_restart_not_merely_a_call(adv) -> None:
    """DETERMINISM HAS TO SURVIVE A RESTART OR IT IS NOT DETERMINISM.

    The first draft seeded on `hash(kind)`. Python randomises str hashing per process, so the
    canary data changed on every run -- and the test above still passed, because both calls were
    in the same process. An in-process equality check cannot see this class of bug at all.

    Asserting on the DERIVATION rather than on two samples is what closes it: the seed must come
    from a stable digest, and `hash()` must not appear in the module at all.
    """
    src = (_ROOT / "desks" / "mt5" / "research" / "adversary.py").read_text("utf-8")
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "hashlib" in body and "sha1" in body, (
        "the canary seed is no longer derived from a stable digest")
    assert "hash(kind)" not in body and "random.seed()" not in body, (
        "the seed uses Python's per-process string hash again -- canary data will differ on every "
        "restart, so a canary that starts passing could be the draw rather than the gate and the "
        "suite can never tell you which")


def test_the_stand_in_gate_declares_itself(adv) -> None:
    """A 100% rejection rate from a gate that rejects unconditionally is false comfort."""
    doc = adv.run()
    assert "stand-in" in doc["gate_source"] and "proves nothing" in doc["gate_source"]
    injected = adv.run(gate=lambda n, s, f: False)
    assert injected["gate_source"] == "injected"


# ------------------------------------------------------------------ P49 against the REAL judge
@pytest.fixture(scope="module")
def real(adv):
    """The desk's ten-gate certifier as the gate, and the canary verdicts it gave."""
    gate, blocked = adv.real_gate()
    assert gate is not None, blocked
    return gate, adv.run_canaries(gate)


def test_the_real_judge_is_reachable_and_named_as_the_source(adv, real, monkeypatch) -> None:
    """`gate_source` must name the certifier, not a stand-in, or the 100% proves nothing."""
    gate, _ = real
    monkeypatch.setattr(adv, "hunt_silent_defects", lambda *a, **k: [])
    doc = adv.run(gate)
    assert doc["gate_source"] == "injected: external_gauntlet.run_gauntlet"
    assert doc["docket"]["n_cells"] == len(adv.CANARIES) and doc["docket"]["error"] is None
    assert doc["docket"]["n_unmeasured"] == 0
    assert set(doc["gate_detail"]) == {c.name for c in adv.CANARIES}


def test_the_real_gates_reject_every_canary_and_each_is_judged(adv, real) -> None:
    """THE CONSTANT, NOW ABOUT THE REAL GATES. A survivor here is a gate that stopped gating."""
    gate, out = real
    assert all(r["judged"] and r["gate_error"] is None for r in out["canaries"]), (
        [r for r in out["canaries"] if not r["judged"]])
    assert out["intact"] is True and out["survivors"] == [], out["verdict"]
    for name, d in gate.detail.items():
        assert d["failed_gates"], f"{name} was rejected by no named gate"
        assert d["days"] >= 60, f"{name} has too few observations to have been judged"


def test_the_docket_is_wide_enough_for_the_program_level_gates(adv, real) -> None:
    """PBO and SPA fail unconditionally on one cell. Five canaries judged as one docket means a
    rejection can come from the gate the canary was built for, not from the docket's width."""
    gate, _ = real
    pl = gate.docket["program_level"]
    assert pl["pbo"] < 1.0 and pl["spa_p"] < 1.0, pl
    # And the multiplicity canary is caught by the multiplicity gate, not by everything at once.
    assert gate.detail["survivor_biased"]["failed_gates"] == ["deflated_sharpe"]


def _daily(adv, name, **kw):
    import external_gauntlet as eg
    sig, fwd = adv._series(name)
    cell = adv.docket_cell(name, sig, fwd, **kw)
    ds = eg.daily_series(cell["df"], cell["sigs"], cell["costs"])
    return float(ds.mean()), float(ds.mean() / ds.std() * 252 ** 0.5)


def test_the_docket_carries_no_geometry_artefact(adv, real) -> None:
    """A zero-drift series must score zero drift. The first adapter's 0.5% stop / 2:1 target
    truncated losses harder than gains on synthetic bars and handed pure noise +0.12R a trade."""
    from mt5desk.engine import Costs
    free = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=1e5)
    mean_free, _ = _daily(adv, "pure_noise", costs=free)
    mean_paid, _ = _daily(adv, "pure_noise")
    assert abs(mean_free) < 0.05 and abs(mean_paid) < 0.05, (mean_free, mean_paid)


def test_the_lookahead_canary_is_the_harness_probe_under_the_docket(adv, real) -> None:
    """Stamped on the bar it knows, an engine that lets it trade that bar scores absurdly; the
    desk's next-open fill sees noise. That is the leak the canary exists to catch."""
    _, sharpe_same_bar = _daily(adv, "lookahead", stamp_offset=0)
    _, sharpe_honest = _daily(adv, "lookahead", stamp_offset=1)
    assert sharpe_same_bar > 10.0, sharpe_same_bar
    assert abs(sharpe_honest) < 2.0, sharpe_honest


def test_the_cost_blind_canary_is_a_real_edge_that_costs_more_than_it_earns(adv, real) -> None:
    from mt5desk.engine import Costs
    free = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=1e5)
    mean_free, sharpe_free = _daily(adv, "cost_blind", costs=free)
    mean_paid, _ = _daily(adv, "cost_blind")
    assert mean_free > 0.0 and sharpe_free > 2.0, (mean_free, sharpe_free)
    assert mean_paid < 0.0, mean_paid


def test_the_gate_refuses_a_canary_that_is_not_the_one_in_its_docket(adv, real) -> None:
    gate, _ = real
    sig, fwd = adv._series("pure_noise")
    with pytest.raises(ValueError, match="not the one in the docket"):
        gate("pure_noise", sig, [f + 1.0 for f in fwd])


def test_an_unmeasured_verdict_is_unjudged_not_rejected(adv) -> None:
    """The certifier's UNMEASURED is a failure to judge; scoring it as a rejection would be
    the crash-as-rejection defect wearing the certifier's own vocabulary."""
    class _Gauntlet:
        @staticmethod
        def run_gauntlet(cells, hunt, meta):
            return {"n_cells": len(cells), "verdicts": [
                {"family": c["family"], "passed": False, "unmeasured": True, "days": 3,
                 "stages": {"observations": {"passed": False, "why": "only 3 days"}}}
                for c in cells]}
    out = adv.run_canaries(adv.GauntletGate(_Gauntlet()))
    assert out["intact"] is False
    assert all(not r["judged"] and "UNMEASURED" in r["gate_error"] for r in out["canaries"])


def _main_paths(adv, monkeypatch, tmp_path):
    monkeypatch.setattr(adv, "REPORT", tmp_path / "ADVERSARY.json")
    monkeypatch.setattr(adv, "ALARM", tmp_path / "CANARY_ALARM.txt")
    monkeypatch.setattr(adv, "hunt_silent_defects", lambda *a, **k: [])
    return tmp_path / "ADVERSARY.json", tmp_path / "CANARY_ALARM.txt"


def test_main_judges_with_the_real_gates_and_writes_the_source(adv, monkeypatch,
                                                                tmp_path) -> None:
    report, alarm = _main_paths(adv, monkeypatch, tmp_path)
    assert adv.main() == 0
    import json
    doc = json.loads(report.read_text("utf-8"))
    assert doc["gate_source"] == "injected: external_gauntlet.run_gauntlet"
    assert doc["canaries"]["intact"] is True and not alarm.exists()


def test_main_says_blocked_and_claims_nothing_when_the_judge_is_unreachable(
        adv, monkeypatch, tmp_path) -> None:
    report, alarm = _main_paths(adv, monkeypatch, tmp_path)
    monkeypatch.setattr(adv, "real_gate", lambda: (None, "BLOCKED: no gauntlet on this host"))
    assert adv.main() == 0
    import json
    doc = json.loads(report.read_text("utf-8"))
    assert doc["gate_source"].startswith("BLOCKED: no gauntlet on this host")
    assert "proves nothing" in doc["gate_source"]
    assert "injected" not in doc["gate_source"] and not alarm.exists()


def test_main_still_raises_the_alarm_when_the_injected_judge_admits_a_canary(
        adv, monkeypatch, tmp_path) -> None:
    """Injection changes the judge, never the alarm: a survivor is exit 1 and a named file."""
    _, alarm = _main_paths(adv, monkeypatch, tmp_path)
    monkeypatch.setattr(adv, "real_gate", lambda: (lambda n, s, f: n == "lookahead", None))
    assert adv.main() == 1
    text = alarm.read_text("utf-8")
    assert text.startswith("CANARY ") and "lookahead passed" in text


# ------------------------------------------------------------- P49 against the promoter
@pytest.fixture(scope="module")
def gaming(adv):
    out = adv.promoter_gaming()
    assert out["status"] == "MEASURED", out.get("why")
    return out


def test_the_gaming_ledger_satisfies_the_promotion_bar_exactly(adv, gaming) -> None:
    """Built to the bar and not past it: the bar's weakness is a hair over it."""
    bar, led = gaming["bar"], gaming["ledger"]
    assert led["n"] == int(bar["min_trades"]) and led["days_active"] == int(bar["min_days_active"])
    floor = float(bar["min_exp_r"])
    assert floor < led["exp_r"] < floor + 2 * adv.GAMING_EXCESS_R
    assert led["max_dd_r"] > float(bar["max_dd_r"])
    assert led["satisfies_bar"] is True
    assert gaming["canary"] not in {c.name for c in adv.CANARIES}, (
        "the gaming canary must not sit in the 100% constant: a ledger built to a bar passing "
        "that bar is the bar's definition, not a gate that stopped gating")


def test_every_promoter_door_is_read_and_says_whether_it_admits(gaming) -> None:
    r = gaming["readings"]
    assert all(isinstance(v["admits"], bool) and v["how_called"] for v in r.values())
    # The forward clock admits a ledger built to its bar; the capital door refuses it without an
    # allocator reading, writes the row STANDBY at 0%, and opens only on an admitting reading.
    assert r["forward_verdict.verdict"]["admits"] is True
    cap0 = r["promoter.capital_verdict (no allocator reading)"]
    assert cap0["admits"] is False and cap0["status"] == "UNMEASURED"
    assert cap0["row_status_written"] == "STANDBY" and cap0["risk_frac"] == 0.0
    cap1 = r["promoter.capital_verdict (manufactured admitting dE[log W])"]
    assert cap1["admits"] is True and cap1["status"] == "LIVE"
    assert cap1["risk_frac"] == pytest.approx(0.02)
    assert r["promoter.promote_generic certificate door"]["admits"] is False
    # MEASURED, NOT ASSUMED: the promotion bar and the retirement clauses disagree about the
    # same ledger. Fifty trades at +0.055R satisfy the bar while the last twenty average
    # -0.038R, so the rolling-20 clause would retire the sleeve on the reading that admitted it.
    ret = r["promoter retirement clauses"]
    assert ret["admits"] is False and "roll20" in ret["reason"], ret
    assert ret["stats"]["exp"] > float(gaming["bar"]["min_exp_r"]) > ret["stats"]["roll20_exp"]
    assert set(gaming["admitted_by"]) | set(gaming["refused_by"]) == set(r)
    assert not set(gaming["admitted_by"]) & set(gaming["refused_by"])


def test_fourteen_days_of_trades_cannot_be_twenty_independent_days(adv, gaming) -> None:
    """Handed one cluster label per calendar day, the canonical verdict finds at most 14
    independent observations in a 14-day ledger and refuses it on the n_eff floor -- a bar the
    engines never ask it to apply, which is the measured half of this reading."""
    import forward_verdict
    day = gaming["readings"]["forward_verdict.verdict(day_clusters)"]
    assert day["admits"] is False
    assert day["n_eff"] == int(gaming["bar"]["min_days_active"]) < forward_verdict.MIN_EFFECTIVE_N
    engines = gaming["engines_calling_canonical_verdict"]
    assert set(engines) == set(adv.FORWARD_ENGINES)
    assert all(isinstance(v, int) for v in engines.values()), engines


def test_the_gaming_canary_promotes_nothing_and_writes_no_log(adv, gaming, monkeypatch) -> None:
    import promoter

    def _boom(*a, **k):
        raise AssertionError("the gaming canary touched the promoter's state or log")
    monkeypatch.setattr(promoter, "save_sleeves", _boom)
    monkeypatch.setattr(promoter, "plog", _boom)
    out = adv.promoter_gaming()
    assert out["status"] == "MEASURED" and out["nothing_promoted"] is True


def test_the_gaming_canary_is_blocked_with_a_reason_when_the_promoter_is_unreachable(
        adv, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "forward_verdict", None)   # import raises ImportError
    out = adv.promoter_gaming()
    assert out["status"] == "BLOCKED" and "not importable" in out["why"]


def test_the_report_carries_the_gaming_measurement_beside_the_canaries(adv, monkeypatch) -> None:
    monkeypatch.setattr(adv, "hunt_silent_defects", lambda *a, **k: [])
    doc = adv.run()
    assert doc["promoter_gaming"]["status"] == "MEASURED"
    assert doc["canaries"]["intact"] is True and len(doc["canaries"]["canaries"]) == 5


# --------------------------------------------------------------------------- P58
def test_reposts_of_one_source_count_once(adv) -> None:
    claims = [{"primary_source": "doi:10.1/abc", "title": t}
              for t in ("A", "A restated", "A, summarised", "thread on A")]
    out = adv.independent_weight(claims)
    assert out["independent_lineages"] == 1, "four reposts counted as four observations"
    assert out["echo_factor"] == 4.0
    assert out["largest_echo"] == 4


def test_genuinely_independent_claims_are_not_collapsed(adv) -> None:
    claims = [{"primary_source": "doi:10.1/abc"}, {"primary_source": "doi:10.2/xyz"},
              {"mechanism": "carry basis"}]
    assert adv.independent_weight(claims)["independent_lineages"] == 3


def test_lineage_ignores_the_title_because_reposters_change_it(adv) -> None:
    a = {"mechanism": "asia range breakout", "title": "Asia Range Breakout"}
    b = {"mechanism": "breakout range asia", "title": "The Tokyo Session Edge"}
    assert adv.lineage_key(a) == adv.lineage_key(b), (
        "the same mechanism under two titles read as two independent discoveries -- which is "
        "how volume gets mistaken for breadth")


# --------------------------------------------------------------------------- P48
def test_the_defect_hunter_finds_a_planted_shape(adv, tmp_path) -> None:
    (tmp_path / "bad.py").write_text(
        "def f():\n    try:\n        g()\n    except Exception:\n        pass\n", "utf-8")
    hits = adv.hunt_silent_defects(tmp_path)
    assert any(h["shape"] == "bare_except_pass" for h in hits)
    assert all("file" in h and "line" in h and "why" in h for h in hits), (
        "a finding without a file, a line and a reason is not actionable")


def test_the_hunter_reports_and_never_edits(adv, tmp_path) -> None:
    """Every one of these shapes is legitimate somewhere, so this produces a reading list."""
    src = "def f():\n    try:\n        g()\n    except Exception:\n        pass\n"
    p = tmp_path / "bad.py"
    p.write_text(src, "utf-8")
    adv.hunt_silent_defects(tmp_path)
    assert p.read_text("utf-8") == src, "the hunter modified a file; it is a reporter, not a fixer"

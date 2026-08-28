"""2026-07-12 external-review fixes: NW t-stat, Holm bar, shrunk Kelly, dead-man trigger,
root-cause unknown class. Every fix that guards money gets an invariant here."""

from __future__ import annotations

import numpy as np

from libs.research.root_cause import classify
from libs.risk.kelly_shrink import shrink_fraction, shrunk_kelly
from libs.validation.forward_stats import autocorr_factor, holm_bar, nw_tstat


# ---------------- forward stats: the corrected t can only be honest, never inflated ----------
def test_nw_tstat_shrinks_under_positive_autocorrelation():
    rng = np.random.default_rng(7)
    noise = rng.normal(0.004, 0.01, 400)                           # clear positive drift
    sticky = np.convolve(noise, np.ones(5) / 5.0, mode="same")     # strongly autocorrelated
    naive_t = float(np.mean(sticky) / np.std(sticky, ddof=1)) * np.sqrt(400)
    assert naive_t > 0
    assert abs(nw_tstat(sticky)) < abs(naive_t)                    # |significance| shrunk
    assert autocorr_factor(sticky) > 1.5


def test_nw_tstat_matches_naive_for_iid():
    rng = np.random.default_rng(1)
    r = rng.normal(0.001, 0.01, 400)
    naive_t = float(np.mean(r) / np.std(r, ddof=1)) * np.sqrt(400)
    assert abs(nw_tstat(r) - naive_t) < 0.35                       # clamp >=1 keeps it <= naive


def test_nw_tstat_degenerate_inputs_are_zero():
    assert nw_tstat(np.array([])) == 0.0
    assert nw_tstat(np.zeros(50)) == 0.0


def test_holm_bar_orders_cohort_and_exceeds_single_bar():
    assert holm_bar(1) <= 1.65                                     # single candidate ~= plain bar
    assert holm_bar(4, rank=1) > holm_bar(4, rank=4)               # strongest pays the worst bar
    assert holm_bar(4, rank=1) > 1.9                               # alpha/4 is a real correction


# ---------------- shrunk Kelly: max-E[log] under estimation error --------------------------
def test_shrink_monotone_in_evidence_and_bounded():
    s = [shrink_fraction(2.3, n) for n in (15, 40, 90, 180, 365)]
    assert all(0.0 < a < 1.0 for a in s)
    assert s == sorted(s)                                          # more days -> more size
    assert 0.4 < shrink_fraction(2.3, 90) < 0.7                    # ~0.56 reference point


def test_shrink_zero_when_unproven():
    assert shrink_fraction(0.0, 200) == 0.0
    assert shrink_fraction(-1.0, 200) == 0.0
    assert shrink_fraction(2.0, 3) == 0.0
    assert shrunk_kelly(4.0, 2.0, 3, floor=0.25) == 0.25           # operational floor holds


def test_fast_track_strength_authorizes_more_than_old_half_start():
    # a day-40 fast-track needs S~5; the shrink then starts ABOVE the old 1/2-Kelly rung
    assert shrink_fraction(5.0, 40) > 0.5


def test_first_inversion_cap_scales_with_nav_then_expires():
    from libs.risk.kelly_shrink import first_inversion_cap
    small = first_inversion_cap(0.7, 10, False, nav=5_000)
    assert abs(small - 0.525) < 1e-9                       # light 0.75x drag at micro scale
    big = first_inversion_cap(0.7, 10, False, nav=500_000)
    assert abs(big - 0.35) < 1e-9                          # full 0.5x insurance at scale
    assert first_inversion_cap(0.7, 10, True, nav=5_000) == 0.7    # survived -> full
    assert first_inversion_cap(0.7, 60, False, nav=500_000) == 0.7  # 60d expiry
    assert first_inversion_cap(0.7, 59.9, False, nav=500_000) == 0.35  # capped to the end


def test_shrink_se_respects_autocorrelation_vif():
    # round-2 fix: the sizing SE must live on the SAME effective N as the NW t-stat --
    # sticky returns (vif>1) must authorize LESS size, and a saturated vif much less
    assert shrink_fraction(2.3, 90, vif=3.0) < shrink_fraction(2.3, 90)
    assert shrink_fraction(2.3, 90, vif=5.0) < shrink_fraction(2.3, 90, vif=2.0)
    assert shrink_fraction(2.3, 20, vif=5.0) == 0.0        # eff-N 4 < 5 -> unproven


def test_unknown_novel_requires_material_deviation():
    v = classify({"net_pnl": -18.0, "expected_pnl": 6.0})  # ambiguous but only $24 -- noise
    assert v["top_cause"] != "unknown_novel"
    assert v["action"] == "monitor_only"                   # no page on immaterial ambiguity
    big = classify({"net_pnl": -200.0, "expected_pnl": 5.0, "nav": 15000.0})
    assert big["top_cause"] == "unknown_novel"             # $205 > 0.3% of 15k -> pages


# ---------------- root cause: novel failures pause, never force-fit ------------------------
def test_large_unexplained_deviation_is_unknown_novel():
    v = classify({"net_pnl": -200.0, "expected_pnl": 5.0})
    assert v["top_cause"] == "unknown_novel"
    assert v["action"] == "pause_and_page"


def test_evidenced_causes_still_classify_normally():
    v = classify({"net_pnl": -180.0, "expected_pnl": 10.0, "funding_earned": 10.0,
                  "orphan_or_drift_events": 3, "restarts": 3})
    assert v["top_cause"] == "infrastructure_bug"                  # evidence beats unknown


# ---------------- dead-man switch: pure trigger logic ---------------------------------------
def test_deadman_needs_consecutive_breaches_and_ratchets_highwater():
    from scripts.run_deadman_switch import _HW_CONFIRM, should_fire
    st: dict = {}
    # High-water is SUSTAINED, not set on a single spike (incident #5 fix, 2026-07-22,
    # commit b158b8b): a new peak establishes only after _HW_CONFIRM consecutive valid
    # readings, so one upward glitch can no longer inflate the fire line.
    for _ in range(_HW_CONFIRM):
        assert not should_fire(10_000.0, st)                       # establishes high-water
    assert st["high_water"] == 10_000.0
    for _ in range(4):
        assert not should_fire(6_000.0, st)                        # 4 breaches: no fire yet
    assert not should_fire(None, st)                               # API outage changes nothing
    assert should_fire(6_000.0, st)                                # 5th valid breach fires
    st2: dict = {}
    for _ in range(_HW_CONFIRM):
        should_fire(10_000.0, st2)                                 # establish high-water
    for _ in range(3):
        should_fire(6_000.0, st2)                                  # 3 breaches accrue
    assert st2["breaches"] == 3
    assert not should_fire(9_000.0, st2)                           # recovery (>=65%) resets
    assert st2["breaches"] == 0


def test_deadman_ignores_dust_accounts():
    from scripts.run_deadman_switch import should_fire
    st: dict = {}
    for _ in range(10):
        assert not should_fire(100.0, st)                          # below MIN high-water


# ---------------- panel dossier: secrets never leave the machine -------------------------
def test_panel_mission_rotation_and_consensus():
    from pathlib import Path

    from scripts.run_external_panel import _MISSIONS, _ROTATION, _consensus, _mission
    name, prompt = _mission()
    # THE ROTATION IS NO LONGER THE ONLY DOOR. `69fd240c` made the verify pass repay its own debt
    # at this choke point: while a triage-bearing run stands unaudited, the NEXT panel run is the
    # verify mission -- and "verify" is deliberately kept OUT of _ROTATION so a clock cannot burn
    # a paid run when there is nothing to audit. This assertion still read `name in _ROTATION`, so
    # it failed for every run carrying verify debt and had the committed-code CI gate red on
    # 2026-08-27, which makes every other CI verdict since then uninformative (L1.49). The
    # property worth pinning is that a REAL mission with a REAL prompt was selected, by either
    # door -- not that one of the two doors is the only one.
    assert name in (*_ROTATION, "verify", "tier1"), f"{name} is not a known mission"
    assert (Path(_MISSIONS) / f"{name}.txt").exists(), f"{name} has no prompt file"
    assert len(prompt) > 200                            # a real mission prompt loaded
    resp = [{"response": "ADL liquidation squeeze risk"},
            {"response": "adl force-close and kelly overbet"},
            {"response": "nothing relevant here"}]
    cons = dict(_consensus(resp))
    assert cons["ADL/liquidation"] == 2                  # agreement across 2 models tallied
    assert cons.get("sizing/kelly") == 1


def test_all_panel_missions_exist():
    from pathlib import Path
    for m in ("audit", "generate", "data", "premortem", "tier1", "synthesize"):
        assert (Path("prompts/panel_missions") / f"{m}.txt").read_text("utf-8").strip()


def test_information_value_accounting(tmp_path):
    from libs.research.information_value import log_experiment, summary, surprise_bits
    # a surprising survival (low prior) carries MORE bits than an expected failure
    assert surprise_bits(0.02, True) > surprise_bits(0.02, False)
    log = tmp_path / "iv.jsonl"
    log_experiment("h1", "funding", 0.30, survived=True, forward_validated=True, log=log)
    log_experiment("h2", "price_only", 0.02, survived=False, lesson="crowded", log=log)
    s = summary(log=log)
    assert s["experiments"] == 2 and s["survivors"] == 1
    assert s["forward_validated_survivors"] == 1 and s["distinct_families"] == 2
    assert s["total_information_bits"] > 0


def test_roster_conservative_keeps_alive_replaces_dead_fills_gaps():
    from scripts.refresh_panel_roster import select_roster
    catalog = [
        {"id": "x-ai/grok-8", "created": 100},              # current pick still alive -> KEEP
        {"id": "x-ai/grok-9", "created": 200},              # newer, but NOT auto-swapped
        {"id": "openai/gpt-9", "created": 250},             # replacement for dead openai pick
        {"id": "openai/gpt-9-mini", "created": 300},        # weak -> not used as replacement
        {"id": "google/gemini-9", "created": 150},          # fills the google gap
    ]
    current = ["x-ai/grok-8", "openai/gpt-DEAD"]            # grok alive, openai pick delisted
    roster = select_roster(catalog, "KEY", "https://openrouter.ai/api/v1", current=current)
    models = {p["model"] for p in roster}
    assert "x-ai/grok-8" in models and "x-ai/grok-9" not in models   # working model NOT swapped
    assert "openai/gpt-9" in models                                  # dead replaced, strong pick
    assert "openai/gpt-9-mini" not in models                         # weak variant avoided
    assert "google/gemini-9" in models                               # empty lab filled
    assert all(p["key"] == "KEY" for p in roster)                    # key preserved


def test_panel_mission_override(monkeypatch):
    import sys

    from scripts.run_external_panel import _mission
    monkeypatch.setattr(sys, "argv", ["run_external_panel.py", "tier1"])
    name, prompt = _mission()
    assert name == "tier1" and "E[log wealth]" in prompt   # monthly forces tier1 over rotation


def test_dossier_sanitizer_blocks_tokens_keeps_ledger_ids():
    from scripts.generate_external_review_doc import sanitize
    s = sanitize("token 3FjnBqKnHCZJshortenedFAKEFAKEFAKE99 topic quant-desk-6bec2ceef782 "
                 "path data/secrets/x.json id 2026-07-12-first-inversion-rule-adopted")
    assert "quant-desk" not in s and "data/secrets" not in s
    assert "FAKEFAKE" not in s                                     # long unhyphenated token gone
    assert "2026-07-12-first-inversion-rule-adopted" in s          # ledger ids stay readable


def test_deadman_single_spike_cannot_inflate_highwater():
    """REGRESSION (incident #5, 2026-07-22, commit b158b8b): ONE noisy upward reading must not
    become the high-water. Before the fix a single spike permanently raised the fire line, so
    ordinary equity then sat below 65% of a phantom peak and the rail false-fired day after day.

    NOTE: this test previously lived in scripts/test_review_fixes.py, which pytest never collects
    (pyproject testpaths=["tests"]) -- so it could not catch the regression it exists to prevent.
    Relocated here 2026-07-23."""
    from scripts.run_deadman_switch import _HW_CONFIRM, should_fire
    st: dict = {}
    for _ in range(_HW_CONFIRM):
        should_fire(4_000.0, st)                                   # real sustained level
    assert st["high_water"] == 4_000.0
    should_fire(9_000.0, st)                                       # single glitch spike
    assert st["high_water"] == 4_000.0, "a lone spike must never ratchet the high-water"
    for _ in range(5):                                             # normal equity, no phantom fire
        assert not should_fire(3_600.0, st)


def test_deadman_still_fires_on_a_real_sustained_drawdown():
    """The incident-#5 fix must NOT weaken ruin protection: a genuine 35%+ drawdown from a REAL
    sustained peak still fires within the same _CONSECUTIVE budget."""
    from scripts.run_deadman_switch import _HW_CONFIRM, should_fire
    st: dict = {}
    for _ in range(_HW_CONFIRM):
        should_fire(10_000.0, st)
    assert st["high_water"] == 10_000.0
    for _ in range(4):
        assert not should_fire(6_000.0, st)
    assert should_fire(6_000.0, st), "real ruin must still fire on the 5th breach"

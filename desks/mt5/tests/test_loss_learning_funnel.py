"""THE LOSS-LEARNING LOOP (2026-11-03): the two root causes of the DEAD loss seats, and the
funnel report that would have caught them.

Root causes pinned here:
  * missed_trade_archaeologist parked every live loss whose sleeve wrote no `taken` decision
    row as UNMEASURED -- the fill's own entry instant is now its decision time;
  * it donated each non-fired cell once in its life -- it now re-donates when the cell has
    grown by NF_REDONATE_GROWTH setups;
  * residual_queue built every `strategy_loss` item with no family, which its own door
    refuses -- the family is now the sleeve's registry row (exact or unique prefix).
And the funnel: RED when work waited on a stage for three days (the check exits 1), QUIET when
nothing reached it, UNMEASURED when an input is absent.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import missed_trade_archaeologist as MT  # noqa: E402
from research import residual_queue as rq  # noqa: E402

_spec = importlib.util.spec_from_file_location("check_loss_learning",
                                               _ROOT / "scripts" / "check_loss_learning.py")
assert _spec and _spec.loader
LL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LL)

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
SLEEVES = {"usdnok_carry_asia_p_ff35bb7c8427d66f": {"name": "usdnok_carry_asia_p_ff35bb7c8427d66f",
                                                    "family": "carry", "symbol": "USDNOK"},
           "usdnok_carry_asia_p_3411bcff02687f5a": {"name": "usdnok_carry_asia_p_3411bcff02687f5a",
                                                    "family": "carry", "symbol": "USDNOK"},
           "gold_asia": {"name": "gold_asia", "symbol": "XAUUSD"}}


# ------------------------------------------------------------------ archaeologist root causes
def test_a_live_loss_with_no_decision_row_is_dug_from_its_own_entry() -> None:
    entry = NOW - timedelta(hours=6)
    fill = {"sleeve": "usdnok_carry_asia_p_ff35bb7", "symbol": "USDNOK",
            "time": NOW.isoformat(), "entry_time": entry.isoformat(), "r_multiple": -9.4,
            "deal": 1, "entry_side": 1}
    eps = MT.find_episodes([], [fill], {}, lambda _s: None)
    assert len(eps) == 1
    assert eps[0]["status"] == "SELECTED"
    assert eps[0]["decision_time"] == entry
    assert eps[0]["decision_time_basis"] == "fill_entry_time"


def test_a_loss_with_neither_decision_nor_entry_stays_unmeasured() -> None:
    fill = {"sleeve": "x", "symbol": "EURUSD", "time": NOW.isoformat(), "r_multiple": -2.0}
    assert MT.find_episodes([], [fill], {}, lambda _s: None)[0]["status"] == MT.UNMEASURED


def test_a_donated_cell_is_donated_again_only_after_it_grows() -> None:
    cell = {"evidence": {"n_setups": 10}}
    assert MT.redonate(None, cell)
    assert MT.redonate("2026-10-01T00:00:00+00:00", cell), "legacy record reads as zero setups"
    assert not MT.redonate({"n_setups": 10 - MT.NF_REDONATE_GROWTH + 1}, cell)
    assert MT.redonate({"n_setups": 10 - MT.NF_REDONATE_GROWTH}, cell)


def test_a_truncated_sleeve_resolves_only_when_unique() -> None:
    assert MT.resolve_sleeve("usdnok_carry_asia_p_ff35bb7", SLEEVES) == \
        "usdnok_carry_asia_p_ff35bb7c8427d66f"
    assert MT.resolve_sleeve("usdnok_carry_asia_p_", SLEEVES) is None


def test_a_dug_loss_becomes_a_tweak_cell_of_its_parent_family() -> None:
    dug = [{"kind": "large_adverse_move", "lane": "live", "symbol": "USDNOK",
            "sleeve": "usdnok_carry_asia_p_ff35bb7", "decision_time": NOW.isoformat(),
            "outcome": {"r": -9.4}, "episode_id": "ep_1", "hypotheses": ["h1", "h2"]}]
    hyps = [{"hypothesis_id": "h1", "absent": "feature", "what": "vol regime",
             "frozen_at": NOW.isoformat()},
            {"hypothesis_id": "h2", "absent": "dataset", "what": "a feed",
             "frozen_at": NOW.isoformat()}]
    cells = MT.tweak_cells(dug, hyps, SLEEVES)
    assert len(cells) == 1, "a dataset request is the acquirer's, never a cell"
    c = cells[0]
    assert (c["kind"], c["family"], c["symbols"]) == ("hypothesis", "carry", ["USDNOK"])
    assert c["evidence"]["parent_sleeve"] == "usdnok_carry_asia_p_ff35bb7c8427d66f"
    assert c["available_time"] == NOW.isoformat()
    assert "params" not in c


def test_a_forward_win_on_a_day_the_book_never_decided_is_a_missed_move() -> None:
    day1, day2 = NOW - timedelta(days=2), NOW - timedelta(days=1)
    shadow = {"XAUUSD.asia": [{"entry_time": day1.isoformat(), "r_multiple": 1.5},
                              {"entry_time": day2.isoformat(), "r_multiple": 1.2},
                              {"entry_time": day2.isoformat(), "r_multiple": -1.0}]}
    live = [{"sleeve": "gold_asia", "entry_time": day1.isoformat(), "time": day1.isoformat()}]
    eps = MT.unfilled_forward(shadow, [], live)
    assert [e["decision_time"] for e in eps] == [day2]
    assert eps[0]["sleeve"] == "gold_asia" and eps[0]["lane"] == "shadow_unfilled"
    assert MT.clock_sleeve("EURUSD.asia") is None


# ------------------------------------------------------------------- residual queue root cause
def test_a_strategy_loss_carries_its_sleeves_family_and_is_donated(tmp_path: Path,
                                                                    monkeypatch:
                                                                    pytest.MonkeyPatch) -> None:
    p = tmp_path / "sleeves.json"
    p.write_text(json.dumps({"sleeves": list(SLEEVES.values())}), "utf-8")
    monkeypatch.setattr(rq, "SLEEVES", p)
    assert rq.sleeve_family("usdnok_carry_asia_p_ff35bb7") == "carry"
    assert rq.sleeve_family("usdnok_carry_asia_p_") is None, "ambiguous prefix"
    assert rq.sleeve_family("gold_asia") == "session_range_breakout"
    monkeypatch.setattr(rq, "may_hypothesise", lambda _s: True)
    monkeypatch.setattr(rq, "registered_families", lambda: {"carry"})
    row = rq.item("strategy_loss", "USDNOK", "sleeve_shortfall:usdnok_carry_asia_p_ff35bb7",
                  9.4, "R", 1.0, "live_ledger", "loss",
                  family=rq.sleeve_family("usdnok_carry_asia_p_ff35bb7"))
    assert row is not None
    row["status"] = "OPEN"
    cands, refused = rq.donation_candidates([row], 5)
    assert len(cands) == 1 and not refused and cands[0]["family"] == "carry"


# ------------------------------------------------------------------------------- the funnel
def _point(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name, rel in (("LIVE", "live.jsonl"), ("NON_FIRED", "nf.jsonl"),
                      ("MISSED", "MISSED_TRADES.json"), ("VERDICTS", "verdicts.jsonl"),
                      ("SLEEVES", "sleeves.json"), ("OUT", "reports/LOSS_LEARNING.json"),
                      ("LINEAGE", "ll/lineage.jsonl"), ("REPLACEMENTS", "ll/replacements.jsonl"),
                      ("ROLLOUTS", "ll/BOOK_ROLLOUTS.json"),
                      ("LEARNER_REPORT", "reports/LOSS_LEARNER.json")):
        monkeypatch.setattr(LL, name, tmp_path / rel)
    monkeypatch.setattr(LL, "INTEL_ROOTS", (tmp_path / "intel",))
    return tmp_path


def _jsonl(p: Path, rows: list[dict]) -> None:
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def _seat(root: Path, at: datetime, fam: str = "carry", sym: str = "USDNOK") -> None:
    d = root / "intel" / "missed_trade_archaeologist"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"discoveries_{at:%Y%m%d_%H%M}.json").write_text(json.dumps(
        {"generated_at": at.isoformat(), "discoveries": [
            {"family": fam, "symbol": sym, "evidence": {"parent_sleeve": "p"}}]}), "utf-8")


def test_absent_inputs_are_unmeasured_never_zero(tmp_path, monkeypatch) -> None:
    _point(tmp_path, monkeypatch)
    doc = LL.build(NOW)
    assert doc["status"] == LL.UNMEASURED
    assert all(s["n_window"] == LL.UNMEASURED for s in doc["stages"].values())


def test_losses_that_never_became_cells_are_red_and_the_check_fails(tmp_path,
                                                                     monkeypatch) -> None:
    root = _point(tmp_path, monkeypatch)
    _jsonl(root / "live.jsonl", [{"time": (NOW - timedelta(hours=5)).isoformat(),
                                  "r_multiple": -9.4}])
    _jsonl(root / "nf.jsonl", [])
    _seat(root, NOW - timedelta(days=10))          # the seat has been silent for ten days
    _jsonl(root / "verdicts.jsonl", [])
    (root / "sleeves.json").write_text(json.dumps({"sleeves": []}), "utf-8")
    monkeypatch.setattr(LL, "build", lambda now=None, _b=LL.build: _b(NOW))
    doc = LL.build()
    assert doc["stages"]["losses_seen"]["status"] == "GREEN"
    assert doc["stages"]["tweak_cells_generated"]["status"] == "RED"
    assert doc["status"] == "RED" and "tweak_cells_generated" in doc["red_stages"]
    assert LL.main(["--check"]) == 1
    assert json.loads((root / "reports" / "LOSS_LEARNING.json").read_text())["status"] == "RED"
    assert LL.main([]) == 0, "without --check the leg never fails the cycle"


def test_a_loss_free_week_is_quiet_not_red(tmp_path, monkeypatch) -> None:
    root = _point(tmp_path, monkeypatch)
    _jsonl(root / "live.jsonl", [{"time": (NOW - timedelta(days=9)).isoformat(),
                                  "r_multiple": -2.0}])
    _jsonl(root / "nf.jsonl", [{"known_at": (NOW - timedelta(days=9)).isoformat()}])
    _seat(root, NOW - timedelta(days=8))
    _jsonl(root / "verdicts.jsonl", [{"at": (NOW - timedelta(days=7)).isoformat(),
                                      "family": "carry", "sym": "USDNOK"}])
    (root / "sleeves.json").write_text(json.dumps({"sleeves": []}), "utf-8")
    doc = LL.build(NOW)
    assert doc["stages"]["losses_seen"]["status"] == "QUIET"
    assert doc["stages"]["tweak_cells_generated"]["status"] == "QUIET"
    assert doc["stages"]["judged"]["status"] == "QUIET"
    assert doc["stages"]["promoted"]["status"] == "RED", "judged cells waited on the promoter"


def test_replaced_reads_the_loss_learners_verdicts_and_never_rejudges(tmp_path,
                                                                       monkeypatch) -> None:
    root = _point(tmp_path, monkeypatch)
    t = NOW - timedelta(hours=10)
    _jsonl(root / "live.jsonl", [{"time": t.isoformat(), "r_multiple": -1.5}])
    _jsonl(root / "nf.jsonl", [{"known_at": t.isoformat()}])
    (root / "ll").mkdir()
    _jsonl(root / "ll" / "lineage.jsonl", [{"at": t.isoformat(), "id": "v1", "parent": "p",
                                            "family": "carry", "symbol": "USDNOK"}])
    _jsonl(root / "verdicts.jsonl", [{"at": (t + timedelta(hours=1)).isoformat(),
                                      "family": "carry", "sym": "USDNOK"}])
    # A child with a far better shadow_exp: the funnel must NOT call it replaced by itself.
    (root / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "p", "family": "carry", "symbol": "USDNOK", "shadow_exp": 0.10},
        {"name": "child", "family": "carry", "symbol": "USDNOK", "shadow_exp": 0.90,
         "vs_armed": {"margin_r": 5.0}, "promoted_at": (t + timedelta(hours=2)).isoformat()}]}),
        "utf-8")
    doc = LL.build(NOW)
    assert doc["stages"]["tweak_cells_generated"]["n_window"] == 1, "lineage rows are cells"
    assert doc["stages"]["promoted"]["n_window"] == 1
    assert doc["stages"]["replaced"]["status"] == LL.UNMEASURED, "no learner output: unmeasured"
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports" / "LOSS_LEARNER.json").write_text(json.dumps(
        {"generated_at": (t + timedelta(hours=3)).isoformat(), "replacements": {"verdicts": [
            {"verdict": "REPLACE"}, {"verdict": "HOLD_PARENT"}]}}), "utf-8")
    _jsonl(root / "ll" / "replacements.jsonl", [{"at": (t + timedelta(hours=4)).isoformat()}])
    (root / "ll" / "BOOK_ROLLOUTS.json").write_text(json.dumps(
        {"at": NOW.isoformat(), "requests": [{}, {}]}), "utf-8")
    doc = LL.build(NOW)
    assert doc["stages"]["replaced"]["n_window"] == 2, "one REPLACE verdict + one acted row"
    assert doc["book_rollouts"]["requests"] == 2
    assert doc["status"] == "GREEN"
    assert "MARGIN" not in (_ROOT / "scripts" / "check_loss_learning.py").read_text("utf-8")


def test_the_leg_is_wired_and_owns_its_artifact() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"loss_learning_funnel", "scripts/check_loss_learning.py"' in src
    assert '"loss_learning",' not in src, "the old leg name is gone"
    assert LL.OUT == _DESK / "reports" / "LOSS_LEARNING.json"

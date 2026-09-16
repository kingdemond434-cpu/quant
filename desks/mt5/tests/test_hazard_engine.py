"""The hazard engine: P(the desk's own retire rule fires within k) per live sleeve and clock.

BLUEPRINT ITEM 19. `decay_monitor` says an alpha is dead once the evidence is in; this organ says
how likely the bar is to be crossed in the next twenty fills, so the successor hunt starts while
the incumbent still earns. What is pinned here, and each is a way this could quietly become
something it must not be:

  * a decaying alpha reads RED and QUEUES a successor search; a healthy one reads GREEN and
    queues nothing -- the queue is the whole action, and it is a hunt, not a kill;
  * the empirical fallback engages below the fit floor and is LABELLED on every card, so a
    number from arithmetic is never read as a number from a model;
  * the logistic path fits on the desk's own sliced ledgers, learns that a falling t raises the
    hazard, and beats the base rate in-sample;
  * the successor queue dedupes by name per day, so an hourly clock cannot spam the hunt;
  * absent inputs are UNMEASURED cards, never a clean GREEN and never a crash;
  * and the organ writes NO roster, NO risk_frac and NO close queue -- the desk never reduces
    aggressiveness by fiat, and a hazard report is not a licence to.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import decay_monitor as D  # noqa: E402
from research import hazard_engine as H  # noqa: E402

NOW = datetime.now(tz=UTC).replace(microsecond=0)


def _ledger(rs: list[float], phase: str = "forward") -> list[dict]:
    """A forward-clock ledger in the shape shadow_forward writes: hourly closes, oldest first."""
    n = len(rs)
    return [{"entry_time": (NOW - timedelta(hours=n - i)).isoformat(),
             "exit_time": (NOW - timedelta(hours=n - i - 0.5)).isoformat(),
             "r_multiple": float(r), "phase": phase, "reason": "ttl"}
            for i, r in enumerate(rs)]


def _decaying(n: int = 60) -> list[float]:
    """Flat-to-falling: the trailing t sits near zero early and turns hard negative, so the
    desk's own rule fires at the n=20 bar and every earlier window is a live death-in-k."""
    return [0.05 - 0.02 * i + 0.15 * math.sin(float(i)) for i in range(n)]


def _healthy(n: int = 60) -> list[float]:
    return [0.4 + 0.1 * math.sin(float(i)) for i in range(n)]


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """Every path the engine reads or writes, on tmp_path. Nothing here may touch the real desk."""
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    monkeypatch.setattr(H, "SLEEVES_FILE", tmp_path / "sleeves.json")
    monkeypatch.setattr(H, "LIVE_LEDGER", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(H, "DECAY_ACTIONS", tmp_path / "decay_actions.jsonl")
    monkeypatch.setattr(H, "SHADOW_DIR", shadow)
    monkeypatch.setattr(H, "SHADOW_STATE", shadow / "shadow_state.json")
    monkeypatch.setattr(H, "SURVIVORS", tmp_path / "UNIVERSAL_SURVIVORS.json")
    monkeypatch.setattr(H, "COST_SURFACE", tmp_path / "cost_surface.json")
    monkeypatch.setattr(H, "REGIME_STATE", tmp_path / "regime_state.json")
    monkeypatch.setattr(H, "OUT", tmp_path / "ALPHA_HAZARD.json")
    monkeypatch.setattr(H, "QUEUE", tmp_path / "hypotheses" / "successor_queue.jsonl")
    # A stub classifier: the replacement search must be pinned on the desk's LANE logic, not on
    # whether this box happens to hold a synced MetaTrader registry.
    monkeypatch.setattr(H, "_asset_class",
                        lambda s: "forex" if len(str(s)) == 6 else ("metal" if s else ""))

    class Desk:
        root = tmp_path

        def clock(self, key: str, rs: list[float], status: str = "ACTIVE") -> None:
            sym, fam, win = H.clock_ident(key)
            name = H.ledger_basename(sym, fam, win)
            (shadow / name).write_text(json.dumps(_ledger(rs)), "utf-8")
            state = json.loads((shadow / "shadow_state.json").read_text("utf-8")) \
                if (shadow / "shadow_state.json").exists() else {}
            state[key] = {"status": status, "n": len(rs)}
            (shadow / "shadow_state.json").write_text(json.dumps(state), "utf-8")

        def orphan_ledger(self, basename: str, rs: list[float]) -> None:
            """A ledger with no clock of its own: training evidence the desk still holds."""
            (shadow / basename).write_text(json.dumps(_ledger(rs)), "utf-8")

        def roster(self, rows: list[dict]) -> None:
            (tmp_path / "sleeves.json").write_text(json.dumps({"sleeves": rows}), "utf-8")

        def live(self, rows: list[dict]) -> None:
            (tmp_path / "live_ledger.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows), "utf-8")

        def actions(self, rows: list[dict]) -> None:
            (tmp_path / "decay_actions.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows), "utf-8")

        def survivors(self, rows: dict) -> None:
            (tmp_path / "UNIVERSAL_SURVIVORS.json").write_text(
                json.dumps({"n": len(rows), "survivors": rows}), "utf-8")

        def out(self) -> dict:
            return json.loads((tmp_path / "ALPHA_HAZARD.json").read_text("utf-8"))

        def queue(self) -> list[dict]:
            p = tmp_path / "hypotheses" / "successor_queue.jsonl"
            return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()] \
                if p.exists() else []

        def card(self, cards: list[dict], name: str) -> dict:
            return next(c for c in cards if c["name"] == name)

    return Desk()


# ------------------------------------------------------------------- the two readings that matter
def _two_clock_desk(desk) -> None:
    """One alpha whose edge is gone and one whose edge is intact, in DIFFERENT families so the
    pooled family rail cannot decide either of them."""
    desk.clock("EURUSD.fading.asia", [-0.3, -0.5] * 9)
    desk.clock("AUDCAD.thriving.asia", [0.3, 0.5] * 9)


def test_a_decaying_alpha_reads_red_and_queues_a_successor_search(desk) -> None:
    _two_clock_desk(desk)
    desk.survivors({"h.AUDNZD.carry": {"sym": "AUDNZD", "hunt": "h", "days": 400,
                                       "shadow_spec": {"symbol": "AUDNZD", "family": "carry"}}})
    assert H.main() == 0
    card = desk.card(desk.out()["cards"], "EURUSD.fading.asia")
    assert card["health"] == "RED" and card["p_die_k"] >= H.RED_P
    assert card["lane"] == "forward" and card["n"] == 18
    assert card["trailing_t"] < -2.0 and card["mean_r"] < 0.0
    # the incumbent is not yet dead by the desk's own rule -- that is the entire point
    assert not H.dies([r for _, r in [(None, x) for x in [-0.3, -0.5] * 9]])[0]
    rows = desk.queue()
    assert [r["kind"] for r in rows] == ["successor_search"]
    assert rows[0]["for"] == "EURUSD.fading.asia" and rows[0]["symbol"] == "EURUSD"
    assert rows[0]["family"] == "fading" and "p_die" in rows[0]["why"]
    assert rows[0]["replacement_candidates"][0]["family"] == "carry"


def test_a_healthy_alpha_reads_green_and_queues_nothing(desk) -> None:
    _two_clock_desk(desk)
    assert H.main() == 0
    card = desk.card(desk.out()["cards"], "AUDCAD.thriving.asia")
    assert card["health"] == "GREEN" and card["p_die_k"] < H.AMBER_P
    assert card["posterior_edge"] == pytest.approx(0.4 * 18 / 48, abs=0.02)
    assert [r["for"] for r in desk.queue()] == ["EURUSD.fading.asia"]


def test_the_empirical_fallback_engages_below_the_fit_floor_and_is_labelled(desk) -> None:
    _two_clock_desk(desk)
    H.main()
    model = desk.out()["model"]
    assert model["basis"] == "empirical" and model["n_train"] < H.MIN_TRAIN_ROWS
    assert model["coefficients"] is None and "decoration" in model["why_empirical"]
    assert "Phi(" in model["rule"]
    for card in desk.out()["cards"]:
        assert card["basis"].startswith("empirical (analytic) rule")


# ----------------------------------------------------------------------------- the fitted path
def _training_desk(desk, clocks: int = 8) -> None:
    """Sixteen ledgers of sixty trades: eight that die by the desk's rule and eight that do not.
    Their families are separate from the scored pair's, so no pooled rail crosses between them."""
    for i in range(clocks):
        desk.orphan_ledger(f"ledger_EURUSD_traindead_c{i:02d}.json", _decaying())
        desk.orphan_ledger(f"ledger_AUDCAD_trainlive_c{i:02d}.json", _healthy())
    desk.clock("EURUSD.scoredead.asia", _decaying(19))
    desk.clock("AUDCAD.scorelive.asia", _healthy(19))


def test_the_logistic_path_fits_on_the_desks_own_ledgers_and_separates_them(desk) -> None:
    _training_desk(desk)
    assert H.main() == 0
    doc = desk.out()
    model = doc["model"]
    assert model["basis"] == "logistic" and model["n_train"] >= 200
    assert model["training"]["n_positive"] >= H.MIN_TRAIN_POS
    # a FALLING trailing t must raise the hazard; the sign is the claim, not the magnitude
    assert model["coefficients"]["trailing_t"] < 0.0
    assert model["calibration"]["scope"] == "in_sample"
    assert model["calibration"]["skill"] > 0.0
    dying = desk.card(doc["cards"], "EURUSD.scoredead.asia")
    living = desk.card(doc["cards"], "AUDCAD.scorelive.asia")
    assert dying["basis"].startswith("logistic hazard") and living["basis"].startswith("logistic")
    assert dying["p_die_k"] > living["p_die_k"]
    assert dying["health"] in ("AMBER", "RED") and living["health"] == "GREEN"


def test_an_alpha_the_rule_already_fires_on_is_priced_at_one_not_modelled(desk) -> None:
    desk.clock("EURUSD.gone.asia", [-0.3, -0.5] * 12)          # n=24, past the n>=20 bar at t<0
    H.main()
    card = desk.card(desk.out()["cards"], "EURUSD.gone.asia")
    assert card["p_die_k"] == 1.0 and card["health"] == "RED"
    assert "ALREADY fires" in card["basis"]
    # nothing certified to swap in is a reading, not a shrug -- it is why the hunt is queued
    assert card["replacement_candidates"] == []
    assert "not already live or forward" in card["replacement_note"]


# ------------------------------------------------------------------------------- the queue rails
def test_the_successor_queue_dedupes_by_name_per_day(desk) -> None:
    _two_clock_desk(desk)
    H.main()
    H.main()
    H.main()
    assert [r["for"] for r in desk.queue()] == ["EURUSD.fading.asia"]
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    cards = [{"name": "EURUSD.fading.asia", "health": "RED", "symbol": "EURUSD",
              "family": "fading", "k": 20, "p_die_k": 0.9, "trailing_t": -4.0, "n": 18,
              "mean_r": -0.4, "drawdown_r": -7.2, "basis": "x", "lane": "forward",
              "replacement_candidates": []}]
    assert H.queue_successors(cards, now) == []                 # same name, same day
    tomorrow = (datetime.now(tz=UTC) + timedelta(days=1)).isoformat(timespec="seconds")
    assert len(H.queue_successors(cards, tomorrow)) == 1        # a new day is a new hunt


def test_the_organ_writes_no_roster_no_size_and_no_close_queue(desk) -> None:
    _two_clock_desk(desk)
    desk.roster([{"name": "eurusd_fading", "symbol": "EURUSD", "family": "fading",
                  "status": "LIVE", "risk_frac": 0.03, "lot": "auto_ramp"}])
    before = (desk.root / "sleeves.json").read_bytes()
    H.main()
    assert (desk.root / "sleeves.json").read_bytes() == before
    assert not (desk.root / "RETIRED_CLOSE_QUEUE.json").exists()
    assert not (desk.root / "decay_live.json").exists()
    assert not (desk.root / "decay_actions.jsonl").exists()
    card = desk.card(desk.out()["cards"], "eurusd_fading")
    assert card["lane"] == "live" and "risk_frac=0.03" in card["capacity"]


# --------------------------------------------------------------------------------- absence
def test_absent_inputs_are_unmeasured_rows_and_never_a_crash(desk) -> None:
    assert H.main() == 0
    doc = desk.out()
    assert doc["n_alphas"] == 0 and doc["cards"] == [] and doc["queued"] == 0
    assert doc["by_health"] == {} and "not a stalled loop" in doc["unchanged_because"]
    assert doc["model"]["basis"] == "empirical" and doc["model"]["n_train"] == 0


def test_an_alpha_with_no_trades_is_unmeasured_with_its_zero(desk) -> None:
    desk.roster([{"name": "ghost_sleeve", "symbol": "XAUUSD", "family": "carry",
                  "status": "STANDBY"}])
    H.main()
    card = desk.card(desk.out()["cards"], "ghost_sleeve")
    assert card["health"] == "UNMEASURED" and card["n"] == 0
    assert card["p_die_k"] is None and card["trailing_t"] is None
    assert "UNMEASURED" in card["basis"] and card["series_id"] is None
    assert desk.queue() == []                                   # UNMEASURED hunts nothing


def test_an_unreadable_shadow_state_is_read_as_no_clocks_not_as_health(desk) -> None:
    (desk.root / "shadow" / "shadow_state.json").write_text("{not json", "utf-8")
    assert H.main() == 0
    assert desk.out()["n_alphas"] == 0


# ------------------------------------------------------------------------- the arithmetic itself
def test_the_empirical_rule_is_monotone_bounded_and_refuses_an_unreachable_bar() -> None:
    ps = [H.empirical_p_die(t, 18, 20) for t in (-6.0, -3.0, -1.0, 0.0, 1.0, 3.0, 6.0)]
    assert ps == sorted(ps, reverse=True)                       # a worse t is a higher hazard
    assert all(0.0 <= p <= 1.0 for p in ps)
    assert H.empirical_p_die(0.0, 18, 20) == pytest.approx(0.5)
    # WITHIN k, not AT k: a longer horizon may only ever raise a first-passage probability
    ks = [H.empirical_p_die(2.0, 18, k) for k in range(2, 30)]
    assert ks == sorted(ks) and ks[-1] > ks[0]
    assert all(H.empirical_p_die(-2.0, 18, k) >= H.empirical_p_die(-2.0, 18, k - 1)
               for k in range(3, 30))
    # k=5 on a 5-trade record cannot reach n>=20, so the rule cannot fire: not a small number
    assert H.empirical_p_die(-9.0, 5, 5) == 0.0
    assert H.empirical_p_die(-9.0, 0, 20) == 0.0


def test_the_death_rule_is_the_decay_monitors_own_bars(desk) -> None:
    assert H.N_MIN_VERDICT == D.N_MIN_VERDICT and H.T_PROMOTE == D.T_PROMOTE
    assert H.DD_HARD_R == D.DD_HARD_R and H.POOL_FADE_N == D.POOL_FADE_N
    assert H.POOL_FADE_T == D.POOL_FADE_T and H.TRAIL_MAX_TRADES == D.TRAIL_MAX_TRADES
    assert H.CONSTANTS_BASIS == "imported from research.decay_monitor"
    assert H.dies([-1.0] * 19)[0] is False                      # below the n bar: no verdict
    assert H.dies([-1.0] * 20)[0] is True                       # at it: the edge is absent
    assert "hard rail" in H.dies([-30.0])[1]                    # the DD rail, at any n
    assert H.pool_dies(D.POOL_FADE_N, D.POOL_FADE_T) is True
    assert H.pool_dies(D.POOL_FADE_N - 1, -9.0) is False


# ------------------------------------------------------------------------------ the extra inputs
def test_optional_features_join_only_when_their_input_file_parses(desk) -> None:
    _two_clock_desk(desk)
    H.main()
    assert desk.out()["model"]["features"] == list(H.BASE_FEATURES)
    (desk.root / "cost_surface.json").write_text(
        json.dumps({"symbols": {"EURUSD": {"stress_p90_over_p50": 2.5}}}), "utf-8")
    (desk.root / "regime_state.json").write_text(
        json.dumps({"sleeves": {"EURUSD|fading_asia": {"flag": "hibernate"}}}), "utf-8")
    H.main()
    doc = desk.out()
    assert doc["model"]["features"] == [*H.BASE_FEATURES, "cost_stress", "regime_flagged"]
    card = desk.card(doc["cards"], "EURUSD.fading.asia")
    assert card["features"]["cost_stress"] == 2.5
    assert card["features"]["regime_flagged"] == 1.0


def test_recorded_demotions_become_training_labels(desk) -> None:
    rows = [{"time": (NOW - timedelta(hours=40 - i)).isoformat(), "sleeve": "eurusd_fading",
             "symbol": "EURUSD", "r_multiple": r} for i, r in enumerate(_decaying(40))]
    desk.live(rows)
    desk.roster([{"name": "eurusd_fading", "symbol": "EURUSD", "family": "fading",
                  "status": "LIVE", "risk_frac": 0.03}])
    desk.actions([{"at": (NOW - timedelta(hours=18)).isoformat(), "sleeve": "eurusd_fading",
                   "action": "RETIRE", "why": "trailing t"}])
    H.main()
    assert desk.out()["model"]["training"]["n_recorded_actions"] >= 1
    card = desk.card(desk.out()["cards"], "eurusd_fading")
    assert card["series_basis"] == "live_ledger" and card["n"] == 40


def test_replacement_candidates_are_certified_same_class_and_a_different_family(desk) -> None:
    _two_clock_desk(desk)
    desk.survivors({
        "h.EURGBP.carry": {"sym": "EURGBP", "hunt": "h", "days": 900,
                           "shadow_spec": {"symbol": "EURGBP", "family": "carry"}},
        "h.EURUSD.fading": {"sym": "EURUSD", "hunt": "h",
                            "shadow_spec": {"symbol": "EURUSD", "family": "fading"}},
        "h.AUDCAD.thriving": {"sym": "AUDCAD", "hunt": "h",
                              "shadow_spec": {"symbol": "AUDCAD", "family": "thriving"}},
        "h.XAUUSD.gap": {"sym": "XAUUSD", "hunt": "h",
                         "shadow_spec": {"symbol": "XAUUSD", "family": "overnight_gap_decay"}},
        "h.GBPJPY.gap": {"sym": "GBPJPY", "hunt": "h",
                         "shadow_spec": {"symbol": "GBPJPY", "family": "overnight_gap_decay"}},
        "h.CADJPY.pca": {"sym": "CADJPY", "hunt": "h",
                         "shadow_spec": {"symbol": "CADJPY", "family": "pca_residual"}},
        "h.CHFNOK.rv": {"sym": "CHFNOK", "hunt": "h",
                        "shadow_spec": {"symbol": "CHFNOK", "family": "relative_value"}}})
    H.main()
    cands = desk.card(desk.out()["cards"], "EURUSD.fading.asia")["replacement_candidates"]
    assert 1 <= len(cands) <= 3
    fams = {c["family"] for c in cands}
    assert "fading" not in fams                                 # never the incumbent's mechanism
    assert "thriving" not in fams                               # never one already on the book
    assert all(c["asset_class"] == "forex" for c in cands)      # XAUUSD is another class
    assert all(c["cell"].startswith("h.") for c in cands)


def test_an_unclassifiable_symbol_gets_no_replacements_rather_than_a_guess() -> None:
    assert H._asset_class("") == ""
    assert H.replacement_candidates("", "carry", set(), {"k": {"sym": "X"}}) == []


# ------------------------------------------------------------------------------------- the CLI
def test_the_cli_dry_run_prints_the_table_and_writes_nothing(desk, capsys) -> None:
    _two_clock_desk(desk)
    assert H.cli(["--dry-run", "--k", "20"]) == 0
    printed = capsys.readouterr().out
    assert "p_die" in printed and "health" in printed
    assert "EURUSD.fading.asia" in printed and "RED" in printed
    assert "dry run: nothing written" in printed
    assert not (desk.root / "ALPHA_HAZARD.json").exists()
    assert desk.queue() == []


def test_the_horizon_is_the_cli_flags_and_the_card_carries_it(desk, capsys) -> None:
    _two_clock_desk(desk)
    assert H.cli(["--k", "3"]) == 0
    capsys.readouterr()
    short = desk.card(desk.out()["cards"], "AUDCAD.thriving.asia")
    assert short["k"] == 3 and short["health"] == "GREEN"
    assert H.cli([]) == 0
    capsys.readouterr()
    long_k = desk.card(desk.out()["cards"], "AUDCAD.thriving.asia")
    # three more draws is a shorter reach than twenty: a healthy edge has less room to turn
    assert long_k["k"] == H.K_DEFAULT and long_k["p_die_k"] >= short["p_die_k"]

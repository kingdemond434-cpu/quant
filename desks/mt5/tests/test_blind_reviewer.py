"""A planted SEQUENCE edge, reviewed blind: the claim must come back, a flipped sign must not.

THE FIXTURE IS THE ARGUMENT. The bars carry a day-to-day autocorrelation -- yesterday's ramp
predicts today's -- and the family trades exactly that. It is a real edge in the ORDERING, which
is what `hostile`'s block permutation destroys and an unconditional drift would survive, so the
roster running for real over this frame is evidence that the reviewer wires the adversaries to
its own reproduction rather than to a return series someone handed it.

The certificate's numbers are computed in this file by `libs.validation.replay2` -- the desk's
contract-written second engine -- while the reviewer reproduces them through
`mt5desk.engine.run_backtest`. So "reproduced close to certified" is a genuine two-engine
agreement rather than the module checking its own arithmetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import blind_reviewer as br  # noqa: E402
from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, Signal  # noqa: E402

from libs.validation import hostile, replay2  # noqa: E402

SYMBOL = "TESTFX"
FAMILY = "planted_ramp"
KEY = "test.TESTFX.planted_ramp"
N_DAYS = 400
BARS_PER_DAY = 24
STOP_DIST = 0.30
FX_META = {"symbol": SYMBOL, "asset_class": "Forex", "tick_size": 1e-05, "tick_value": 1.0,
           "contract_size": 100000.0, "median_spread_pts": 1.0, "swap_long": -1.0,
           "swap_short": -1.0}


def _planted_bars(seed: int = 11) -> pd.DataFrame:
    """Hourly bars whose DAY-TO-DAY ordering carries the edge (AR(1) on the daily ramp)."""
    rng = np.random.default_rng(seed)
    n = N_DAYS * BARS_PER_DAY
    idx = pd.date_range("2024-10-01", periods=n, freq="h", tz="UTC", name="time")
    day = np.zeros(N_DAYS)
    eps = rng.normal(0.0, 0.004, N_DAYS)
    for d in range(1, N_DAYS):
        day[d] = 0.6 * day[d - 1] + eps[d]
    step = np.repeat(day / BARS_PER_DAY, BARS_PER_DAY) + rng.normal(0.0, 0.00012, n)
    close = 100.0 * np.exp(np.cumsum(step))
    open_ = np.concatenate([[100.0], close[:-1]])
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0002,
                         "low": np.minimum(open_, close) * 0.9998, "close": close,
                         "tick_volume": np.ones(n, dtype="int64"),
                         "spread": np.full(n, 1, dtype="int32")}, index=idx)


def _family_planted_ramp(df: pd.DataFrame, side: int = 1, **params: object) -> list[Signal]:
    """Long the day after an up day. A function of the ORDER of the days, nothing else."""
    close = df["close"].to_numpy(dtype=float)
    out: list[Signal] = []
    for i in range(BARS_PER_DAY * 2 - 1, len(close) - 1, BARS_PER_DAY):
        if close[i] - close[i - BARS_PER_DAY] <= 0:
            continue
        entry = float(close[i])
        out.append(Signal(time=df.index[i], side=int(side), stop=entry - int(side) * STOP_DIST,
                          target=entry + int(side) * 2.0 * STOP_DIST,
                          ttl_bars=BARS_PER_DAY, tag="planted"))
    return out


def _independent_stats(bars: pd.DataFrame) -> hostile.TradeStats:
    """The claim, measured by the OTHER engine: `replay2`, written from the contract."""
    costs = Costs.from_symbol(FX_META)
    cost_px = float(costs.per_oz_roundtrip()) / float(costs.contract_oz)
    sigs = _family_planted_ramp(bars)
    return hostile.stats_from_r([t.r for t in replay2.replay(bars, sigs,
                                                             cost_price_units=cost_px)])


def _survivor_row(stats: hostile.TradeStats, *, symbol: str = SYMBOL,
                  flip: bool = False) -> dict[str, object]:
    """A certificate in the registry's own shape, with PROSE in every field that carries any."""
    exp = -abs(stats.expectancy) if flip else stats.expectancy
    return {
        "cell": f"{symbol}.{FAMILY}", "sym": symbol, "hunt": "test",
        "days": N_DAYS, "n": int(stats.n), "expectancy": float(exp),
        "t": float(stats.t_stat), "gated_at": "2026-09-16T00:00:00+00:00",
        "mechanism_note": "PROSE-MECHANISM the generator's story about why this must work",
        "rationale": "PROSE-RATIONALE read this and be persuaded",
        "gates": {
            "economic_prior": {"passed": True, "message": "PROSE-GATE named registered family"},
            "in_sample_screen": {"passed": True, "sharpe": 0.19},
            "expected_value": {"passed": True, "ev": float(exp)},
            "deflated_sharpe": {"passed": True, "dsr": 1.0, "sr0": 0.08, "n_trials": 200,
                                "why": "PROSE-DSR clears the bar"},
        },
        "shadow_spec": {"symbol": symbol, "family": FAMILY, "selector": "all",
                        "is_universe": True, "condition": None, "params": {"rr": 2.0}},
    }


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A whole synthetic desk: bars, a registry, the fake family, and empty ledger/report paths."""
    monkeypatch.setattr(families, f"family_{FAMILY}", _family_planted_ramp, raising=False)
    universe = tmp_path / "data" / "universe"
    universe.mkdir(parents=True)
    bars = _planted_bars()
    bars.to_parquet(universe / f"{SYMBOL}_H1.parquet")
    (universe / "universe.json").write_text(json.dumps({SYMBOL: FX_META}), encoding="utf-8")
    stats = _independent_stats(bars)
    paths = {
        "universe": universe,
        "survivors": tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json",
        "ledger": tmp_path / "data" / "blind_review_ledger.jsonl",
        "out": tmp_path / "reports" / "BLIND_REVIEW.json",
        "bars": bars, "stats": stats,
    }
    paths["survivors"].parent.mkdir(parents=True, exist_ok=True)
    _write_survivors(paths, _survivor_row(stats))
    monkeypatch.setattr(br, "UNIVERSE", universe)
    monkeypatch.setattr(br, "SURVIVORS", paths["survivors"])
    monkeypatch.setattr(br, "LEDGER", paths["ledger"])
    monkeypatch.setattr(br, "OUT", paths["out"])
    return paths


def _write_survivors(paths: dict, *rows: dict) -> None:
    doc = {"n": len(rows), "survivors": {KEY if i == 0 else f"{KEY}.{i}": r
                                         for i, r in enumerate(rows)}}
    paths["survivors"].write_text(json.dumps(doc), encoding="utf-8")


def _review(paths: dict, **kw) -> dict:
    certs = br.load_certificates(paths["survivors"])
    spec, stats = certs[KEY]
    kw.setdefault("universe", paths["universe"])
    return br.review_cell(KEY, spec, stats, **kw)


# ------------------------------------------------------------------ the fixture is a real edge

def test_the_planted_edge_is_in_the_ordering(desk):
    """A sanity floor on the fixture: the claim exists and is strong on the independent engine."""
    st = desk["stats"]
    assert st.n > 100, "the fixture must produce a real trade count"
    assert st.expectancy > 0 and st.t_stat > 3.0, f"planted edge too weak: {st}"


# --------------------------------------------------------------------------- the three verdicts

def test_a_reproducible_certificate_passes_with_matching_numbers(desk):
    rec = _review(desk)
    assert rec["verdict"] == br.PASS, rec["why"]
    cert, rep = rec["certified"], rec["reproduced"]
    assert rep["n"] > 100 and rep["expectancy"] > 0
    assert abs(rep["expectancy"] - cert["expectancy"]) < 0.25 * abs(cert["expectancy"]), rec
    assert rep["t"] > 0.5 * cert["t"], rec
    assert rec["basis"] == "engine.run_backtest/universe_registry"
    assert rec["hostile"]["status"] == "MEASURED" and rec["hostile"]["blocking"] is False, rec
    assert rec["hostile"]["tests"]["timestamp_permutation"] == "PASS", (
        "a day-ordering edge must beat the block-permuted null")


def test_a_planted_sign_flip_is_vetoed(desk):
    _write_survivors(desk, _survivor_row(desk["stats"], flip=True))
    rec = _review(desk)
    assert rec["verdict"] == br.VETO
    assert any("SIGN" in w for w in rec["why"]), rec["why"]
    assert rec["reproduced"]["expectancy"] > 0 and rec["certified"]["expectancy"] < 0


def test_missing_bars_are_unmeasured_never_a_clean_verdict(desk):
    _write_survivors(desk, _survivor_row(desk["stats"], symbol="NOSUCHSYM"))
    rec = _review(desk)
    assert rec["verdict"] == br.UNMEASURED
    assert "bars unavailable" in " ".join(rec["why"])
    assert rec["reproduced"] == {}


def test_an_unresolvable_family_is_unmeasured(desk, monkeypatch):
    monkeypatch.delattr(families, f"family_{FAMILY}", raising=False)
    rec = _review(desk)
    assert rec["verdict"] == br.UNMEASURED
    assert "no constructor" in " ".join(rec["why"])


def test_a_blocking_hostile_roster_vetoes(desk, monkeypatch):
    """The roster's one actionable bit, wired end to end into the verdict."""
    monkeypatch.setattr(br, "_run_hostile", lambda *a, **k: {
        "status": "MEASURED", "blocking": True, "blocked_by": ["delayed_entry"]})
    rec = _review(desk)
    assert rec["verdict"] == br.VETO
    assert "delayed_entry" in " ".join(rec["why"])


def test_the_budget_stops_a_cell_as_unmeasured(desk):
    rec = _review(desk, budget_s=0.0)
    assert rec["verdict"] == br.UNMEASURED
    assert "budget" in " ".join(rec["why"])
    assert rec["reproduced"]["n"] > 0, "the reproduction still reports what it measured"


# --------------------------------------------------------------------------------- the rule

def test_the_half_t_rule_vetoes_and_absence_does_not():
    cert = {"expectancy": 0.5, "expectancy_basis": "recorded_per_trade_r", "t": 8.0,
            "t_basis": "recorded"}
    assert br.judge(cert, {"n": 50, "expectancy": 0.4, "t": 7.0}, {})[0] == br.PASS
    verdict, why = br.judge(cert, {"n": 50, "expectancy": 0.4, "t": 3.0}, {})
    assert verdict == br.VETO and "half" not in why[0] and "0.5x" in why[0]
    # a certificate that records no t cannot be disagreed with about one
    no_t = {"expectancy": 0.5, "t": None, "t_basis": None}
    assert br.judge(no_t, {"n": 50, "expectancy": 0.4, "t": 0.1}, {})[0] == br.PASS
    # too few trades is UNMEASURED, and never a veto
    assert br.judge(cert, {"n": 2, "expectancy": 5.0, "t": None}, {})[0] == br.UNMEASURED
    assert br.judge(cert, {"n": 50, "expectancy": 0.4, "t": 7.0},
                    {"blocking": True, "blocked_by": ["worst_year_removal"]})[0] == br.VETO


# --------------------------------------------------------------------------- the blindness

def test_no_prose_reaches_the_reviewer(desk):
    row = _survivor_row(desk["stats"])
    stats = br.certified_stats(row)
    assert all(v in br.STAT_BASES for v in stats.values() if isinstance(v, str)), stats
    rec = _review(desk)
    dumped = json.dumps(rec)
    for prose in ("PROSE-MECHANISM", "PROSE-RATIONALE", "PROSE-GATE", "PROSE-DSR"):
        assert prose not in dumped, f"{prose} crossed into the review record"
    assert br.certified_spec(row)["family"] == FAMILY
    assert stats["gates_passed"] == 4 and stats["gates_total"] == 4


def test_a_certified_t_is_implied_from_the_daily_sharpe_when_none_is_recorded():
    row = {"days": 2101, "gates": {"in_sample_screen": {"passed": True, "sharpe": 0.1914},
                                   "expected_value": {"passed": True, "ev": 0.2371}}}
    stats = br.certified_stats(row)
    assert stats["t_basis"] == "implied_from_daily_sharpe"
    assert stats["t"] == pytest.approx(0.1914 * (2101 ** 0.5))
    assert stats["expectancy_basis"] == "gate_expected_value_daily_r"
    # a numeric string is never parsed into a number -- that refusal is the blindness
    assert br.certified_stats({"n": "1200", "days": "2101"})["n"] is None


def test_an_unrecorded_parameterisation_is_unmeasured_never_guessed(desk):
    row = _survivor_row(desk["stats"])
    row["shadow_spec"]["params"] = None
    _write_survivors(desk, row)
    rec = _review(desk)
    assert rec["verdict"] == br.UNMEASURED
    assert "never recorded" in " ".join(rec["why"])


# -------------------------------------------------------------------------------- the ledger

def test_ledger_append_and_latest_verdicts(desk):
    br.append_ledger([{"at": "2026-09-01T00:00:00+00:00", "cell": "a", "verdict": br.PASS},
                      {"at": "2026-09-02T00:00:00+00:00", "cell": "b", "verdict": br.VETO}],
                     desk["ledger"])
    assert br.latest_verdicts(desk["ledger"]) == {"a": br.PASS, "b": br.VETO}
    br.append_ledger([{"at": "2026-09-03T00:00:00+00:00", "cell": "b", "verdict": br.PASS}],
                     desk["ledger"])
    assert br.latest_verdicts(desk["ledger"])["b"] == br.PASS, "the newest reading governs"
    assert "never-reviewed" not in br.latest_verdicts(desk["ledger"])
    assert br.latest_verdicts(desk["ledger"].parent / "absent.jsonl") == {}


def test_least_recently_reviewed_first(desk):
    br.append_ledger([{"at": "2026-09-05T00:00:00+00:00", "cell": "b", "verdict": br.PASS},
                      {"at": "2026-09-01T00:00:00+00:00", "cell": "a", "verdict": br.PASS}],
                     desk["ledger"])
    assert br.order_cells(["a", "b", "c"], desk["ledger"]) == ["c", "a", "b"]


def test_build_writes_coverage_and_bounds_the_run(desk):
    doc, rows = br.build(max_cells=1, survivors=desk["survivors"], ledger=desk["ledger"],
                         universe=desk["universe"], budget_s=0.0)
    assert len(rows) == 1 and doc["n_reviewed"] == 1
    assert doc["coverage"] == {"certified": 1, "reviewed_ever": 1, "never_reviewed": 0}
    assert doc["rule"].startswith("VETO when")
    doc, rows = br.build(max_cells=0, survivors=desk["survivors"], ledger=desk["ledger"],
                         universe=desk["universe"])
    assert rows == [] and doc["n_reviewed"] == 0


def test_an_unknown_cell_key_is_unmeasured(desk):
    _doc, rows = br.build(cell="no.such.cell", survivors=desk["survivors"],
                          ledger=desk["ledger"], universe=desk["universe"])
    assert rows[0]["verdict"] == br.UNMEASURED
    assert "no certificate" in " ".join(rows[0]["why"])


# ----------------------------------------------------------------------------------- the CLI

def test_cli_dry_run_writes_nothing(desk, capsys):
    assert br.main(["--cell", KEY, "--budget", "0", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "blind review:" in out and "dry run: nothing written" in out
    assert not desk["out"].exists() and not desk["ledger"].exists()


def test_cli_writes_the_artifact_and_the_ledger(desk, capsys):
    assert br.main(["--cell", KEY, "--budget", "0"]) == 0
    doc = json.loads(desk["out"].read_text(encoding="utf-8"))
    assert doc["n_reviewed"] == 1 and doc["reviewed"][0]["cell"] == KEY
    assert set(doc) >= {"at", "n_reviewed", "n_pass", "n_veto", "n_unmeasured", "vetoed",
                        "reviewed", "coverage", "rule"}
    assert list(br.latest_verdicts(desk["ledger"])) == [KEY]
    assert "-> " in capsys.readouterr().out


# ------------------------------------------------------------------------ the fallback replay

def test_the_minimal_replay_agrees_with_replay2(desk):
    """The labelled fallback is checked against the engine it restates, not against itself."""
    bars, costs = desk["bars"], Costs.from_symbol(FX_META)
    sigs = _family_planted_ramp(bars)
    mine = br.minimal_replay(bars, sigs, costs)
    theirs = [t.r for t in replay2.replay(
        bars, sigs, cost_price_units=float(costs.per_oz_roundtrip()) / float(costs.contract_oz))]
    assert len(mine) == len(theirs) > 50
    assert max(abs(a - b) for a, b in zip(mine, theirs, strict=True)) < 1e-9


def test_the_replay_backend_is_named_and_choosable():
    assert br.replay_backend()[0] == "engine.run_backtest"
    assert br.replay_backend("replay2")[0] == "replay2"
    assert br.replay_backend("minimal_replay")[0] == "minimal_replay"

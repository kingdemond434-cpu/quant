"""The breadth lane: effective breadth, the drawdown-alpha factory, survivor-neighbourhood mining.

What is pinned, and every item is a way one of these three could have produced a flattering number
instead of a true one:

  * the alpha-cluster taxonomy is DECLARED and a session selector may never claim a sleeve whose
    family is unknown -- `USDJPY_asia` is session structure, `EURGBP_discovered_asia` is
    UNCLASSIFIED, and the difference is whether an empty cluster reads as occupied on the strength
    of a timestamp;
  * effective breadth is N for N independent sleeves and 1 for N copies of one trade, refuses a
    non-PSD correlation matrix rather than reporting the enormous bet count it implies, refuses to
    measure on a silent subset of the book, and takes the MINIMUM over measured readings while
    naming every unmeasured one;
  * the stress conditioner is strictly LAGGED -- perturbing the last observation must not move it
    -- because conditioning on the book's own bad days reports a book that diversifies itself
    precisely when it is losing;
  * the realised-return floor of 20 overlapping days is not lowered to produce an answer;
  * every drawdown band is cut on the book EXCLUDING the candidate being scored, a slice below the
    sample floor is UNMEASURED and never a candidate, and the multiplicity burden is ONE
    denominator over every test each module ran;
  * a conditional lift is computed against a base that clears the desk's own coverage floor, and
    the verdict is taken on the SHRUNK mean, not the raw one;
  * none of the three names a crypto exchange.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import alpha_clusters as ac  # noqa: E402
from libs.research import effective_breadth as eb  # noqa: E402
from research import alpha_breadth as ab  # noqa: E402
from research import drawdown_alpha as da  # noqa: E402
from research import survivor_neighbourhood as sn  # noqa: E402


# --------------------------------------------------------------------------------- the taxonomy
def test_taxonomy_is_declared_and_sized_for_the_target_band() -> None:
    keys = [c.key for c in ac.CLUSTERS]
    assert len(keys) == len(set(keys)) == 15
    assert ac.TARGET_MIN <= len(keys) <= ac.TARGET_MAX
    # Every cluster names a PAYER and a hunt; a cluster without one is a label, not a phenomenon.
    for c in ac.CLUSTERS:
        assert c.payer.strip() and c.hunt.strip() and c.title.strip()
    # Every declared family maps to a declared cluster -- no orphan keys.
    assert set(ac.FAMILY_CLUSTER.values()) <= set(keys)


@pytest.mark.parametrize(("sleeve", "cluster"), [
    ("USDJPY_asia", "session_liquidity"),            # the session IS the family
    ("XAUUSD_london_am", "session_liquidity"),
    ("CADJPY_london_am_NORMAL_DAY", "session_liquidity"),
    ("GBPUSD_session_range_breakout", "session_liquidity"),
    ("GBPZAR_overnight_gap_decay_asia", "mean_reversion"),
    ("xau_m15_anti_breakout", "mean_reversion"),      # longest key wins over "anti_breakout"
    ("xau_m5_anti_momentum_ny", "mean_reversion"),
    ("CHFNOK_carry_asia", "macro_rates"),
    ("NZDJPY_dow_effect", "fixing_roll_calendar"),
    ("BTCUSD_monday_gap", "fixing_roll_calendar"),
    ("CADJPY_fair_value_gap", "mean_reversion"),
])
def test_sleeve_labels_map_to_their_phenomenon(sleeve: str, cluster: str) -> None:
    assert ac.classify_sleeve(sleeve) == cluster


def test_a_session_selector_never_claims_an_unknown_family() -> None:
    """THE ERROR THIS CATCHES MAKES AN EMPTY CLUSTER READ AS OCCUPIED.

    `EURGBP_discovered_asia` is a family called `discovered` that happens to trade in Asia. A
    plain substring search finds "asia" in it and files it as session structure, so the cluster
    looks occupied, no research goes to it, and the occupancy was an assumption about a timestamp.
    """
    assert ac.classify_sleeve("EURGBP_discovered_asia") == ac.UNCLASSIFIED
    assert ac.classify_sleeve("EURCHF_discovered_asia") == ac.UNCLASSIFIED
    assert ac.classify_sleeve("") == ac.UNCLASSIFIED
    assert ac.classify_sleeve("SOMETHING_nobody_declared") == ac.UNCLASSIFIED


def test_occupancy_names_the_empty_clusters_and_keeps_unclassified_separate() -> None:
    o = ac.occupancy(["session_liquidity", "session_liquidity", "mean_reversion",
                      ac.UNCLASSIFIED])
    assert o["n_occupied"] == 2
    assert o["n_empty"] == 13
    assert o["n_unclassified"] == 1
    # UNCLASSIFIED is NOT distributed over the real clusters -- it is its own count.
    assert ac.UNCLASSIFIED not in o["occupied"]
    assert "crisis_drawdown" in o["empty"]
    # Every empty cluster arrives with the payer a hunter would go and find.
    assert {d["cluster"] for d in o["empty_detail"]} == set(o["empty"])
    assert all(d["payer"] for d in o["empty_detail"])


# ------------------------------------------------------------------------------ breadth measure
def test_independent_sleeves_count_as_many_bets_and_copies_count_as_one() -> None:
    n = 6
    ident = np.eye(n)
    assert eb.exposure_neff(float(n), np.ones(n), ident) == pytest.approx(float(n))
    ones = np.ones((n, n))
    assert eb.exposure_neff(float(n), np.ones(n), ones) == pytest.approx(1.0)
    # Four sleeves expressed on ONE instrument in ONE direction are one bet, not four.
    assert eb.exposure_neff(4.0, np.array([4.0]), np.eye(1)) == pytest.approx(1.0)


def test_a_non_psd_correlation_matrix_is_refused_not_reported() -> None:
    """An impossible correlation structure implies an enormous bet count, and an enormous number
    that looks like an answer is worse than an exception."""
    bad = np.array([[1.0, -1.0], [-1.0, 1.0]])
    with pytest.raises(ValueError, match="positive"):
        eb.exposure_neff(2.0, np.array([1.0, 1.0]), bad)
    with pytest.raises(ValueError, match="does not match"):
        eb.exposure_neff(2.0, np.array([1.0, 1.0]), np.eye(3))


def _panel(n: int = 600, k: int = 4, seed: int = 7) -> dict[str, list[float]]:
    rng = np.random.default_rng(seed)
    m = rng.normal(size=(n, k))
    return {f"S{i}": [float(v) for v in m[:, i]] for i in range(k)}


def test_breadth_is_never_measured_on_a_silent_subset_of_the_book() -> None:
    panel = _panel()
    with pytest.raises(KeyError, match="no return series"):
        eb.exposure_breadth(5.0, {"S0": 1.0, "MISSING": 1.0}, panel)


def test_a_thin_panel_is_unmeasured_rather_than_estimated() -> None:
    r = eb.exposure_breadth(3.0, {"S0": 1.0, "S1": 1.0}, _panel(n=40))
    assert not r.measured
    assert r.status == eb.UNMEASURED
    assert r.n_eff is None
    assert "floor" in r.why


def test_independent_columns_read_near_their_own_count() -> None:
    panel = _panel(n=2000, k=4, seed=3)
    r = eb.exposure_breadth(4.0, {k: 1.0 for k in panel}, panel)
    assert r.measured
    assert r.n_eff is not None
    assert 3.0 < r.n_eff <= 4.6           # four independent unit bets, up to estimation noise


def test_the_stress_conditioner_cannot_see_the_observation_it_labels() -> None:
    """THE COLLIDER GUARD. If the conditioner at t depended on the returns at t, selecting on it
    would decorrelate the series being measured and report a book that diversifies itself exactly
    when it is losing. Perturbing the LAST observation must leave every label untouched."""
    panel = _panel(n=300, k=3, seed=11)
    a = eb.lagged_vol_regime(panel, window=20)
    bumped = {k: list(v) for k, v in panel.items()}
    for k in bumped:
        bumped[k][-1] = 500.0
    b = eb.lagged_vol_regime(bumped, window=20)
    assert np.allclose(a[np.isfinite(a)], b[np.isfinite(b)])
    assert np.isfinite(a).sum() > 200                   # it is a real series, not all NaN
    # No label exists until an expanding scale and a full window both do, and it says so.
    assert not np.isfinite(a[:eb.MIN_SCALE_OBS + 20]).any()
    # And nothing at t enters its own label: perturbing observation j moves no label at or before
    # j, whatever j is.
    j = 150
    poked = {k: list(v) for k, v in panel.items()}
    for k in poked:
        poked[k][j] = 900.0
    c = eb.lagged_vol_regime(poked, window=20)
    head = slice(0, j + 1)
    assert np.allclose(a[head][np.isfinite(a[head])], c[head][np.isfinite(c[head])])


def test_an_unaligned_regime_label_is_refused() -> None:
    panel = _panel(n=400, k=3)
    r = eb.conditional_breadth(3.0, {k: 1.0 for k in panel}, panel, [0.0] * 7)
    assert not r.measured
    assert "regime" in r.why


def test_the_realised_overlap_floor_is_not_lowered_to_produce_an_answer() -> None:
    days = [f"2026-01-{d:02d}" for d in range(1, 12)]         # 11 days, floor is 20
    series = {"a": {d: 0.1 for d in days}, "b": {d: -0.1 for d in days}}
    r = eb.realised_breadth(series)
    assert not r.measured
    assert str(eb.MIN_PAIR_OVERLAP) in r.why
    long_days = [f"2026-01-{d:02d}" for d in range(1, 26)]
    rng = np.random.default_rng(5)
    ok = {"a": {d: float(x) for d, x in zip(long_days, rng.normal(size=25))},
          "b": {d: float(x) for d, x in zip(long_days, rng.normal(size=25))}}
    r2 = eb.realised_breadth(ok)
    assert r2.measured
    assert r2.n_eff is not None and 1.0 <= r2.n_eff <= 2.0


def test_the_headline_is_the_minimum_and_names_every_refusal() -> None:
    good = eb.Reading("wide", eb.MEASURED, 9.0, 10, 500, "")
    narrow = eb.Reading("narrow", eb.MEASURED, 1.4, 10, 500, "")
    missing = eb.Reading("absent", eb.UNMEASURED, None, 10, 0, "no overlapping history")
    h = eb.headline([good, narrow, missing], 10)
    assert h["effective_breadth"] == pytest.approx(1.4)      # the minimum, not the mean or the max
    assert h["binding_reading"] == "narrow"
    assert [u["name"] for u in h["unmeasured"]] == ["absent"]
    assert h["sharpe_multiplier_vs_one_bet"] == pytest.approx(np.sqrt(1.4), rel=1e-3)
    only_missing = eb.headline([missing], 10)
    assert only_missing["effective_breadth"] is None
    assert only_missing["status"] == eb.UNMEASURED


# ------------------------------------------------------------------------------ the book ledger
def _write_ledger(d: Path, sleeve: str, rows: list[dict]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / f"ledger_{sleeve}.json").write_text(json.dumps(rows), "utf-8")


def _row(day: int, side: int, r: float, hour: int = 9) -> dict:
    return {"entry_time": f"2026-08-{day:02d}T{hour:02d}:00:00+00:00", "side": side,
            "r_multiple": r, "reason": "target" if r > 0 else "stop"}


def test_an_undirectional_sleeve_is_dropped_rather_than_diluted(monkeypatch, tmp_path) -> None:
    """A sleeve that traded both ways nets a small directional loading while still carrying a full
    unit of variance. Crediting the small loading would understate book risk and OVERSTATE
    breadth, so it leaves the measurement and is counted by name."""
    led = tmp_path / "ledgers"
    _write_ledger(led, "EURJPY_asia", [_row(d, 1, 0.5) for d in range(1, 6)])
    _write_ledger(led, "GBPJPY_asia", [_row(1, 1, 0.5), _row(2, -1, 0.5)])   # nets to zero
    monkeypatch.setattr(ab, "LEDGER_DIRS", (led,))
    monkeypatch.setattr(ab, "UNIVERSE", tmp_path / "universe")
    (tmp_path / "universe").mkdir()
    (tmp_path / "universe" / "EURJPY_H1.parquet").write_bytes(b"")
    (tmp_path / "universe" / "GBPJPY_H1.parquet").write_bytes(b"")
    exp = ab.book_exposure()
    assert exp["kept"] == ["EURJPY_asia"]
    assert exp["dropped"]["undirectional"] == ["GBPJPY_asia"]
    assert exp["exposure"] == {"EURJPY": 1.0}


def test_an_instrument_without_bars_adds_no_breadth_and_is_named(monkeypatch, tmp_path) -> None:
    led = tmp_path / "ledgers"
    _write_ledger(led, "GBPZAR_overnight_gap_decay_asia", [_row(d, 1, 0.5) for d in range(1, 4)])
    monkeypatch.setattr(ab, "LEDGER_DIRS", (led,))
    monkeypatch.setattr(ab, "UNIVERSE", tmp_path / "empty_universe")
    exp = ab.book_exposure()
    assert exp["exposure"] == {}
    assert exp["dropped"]["no_price_history"] == ["GBPZAR_overnight_gap_decay_asia"]
    assert exp["n_sleeves_measured"] == 0


def test_both_shadow_ledger_schemas_reach_the_measurement(monkeypatch, tmp_path) -> None:
    """FOUND BY THIS TEST'S ABSENCE. The scalp ledgers write `opened_at`/`direction`/`r` and every
    other ledger writes `entry_time`/`side`/`r_multiple`. Reading only the second dropped all four
    `xau_*` sleeves -- 140 of 487 trades on the desk's flagship instrument -- into a
    `no_recorded_side` bucket, so the largest part of the book left the exposure measurement and
    nothing failed. The trade COUNT looked right the whole time, because `load_trades` already
    tolerated both."""
    led = tmp_path / "ledgers"
    _write_ledger(led, "EURJPY_asia", [_row(1, 1, 0.5), _row(2, 1, 0.5)])
    (led / "ledger_xau_m15_anti_breakout.json").write_text(json.dumps([
        {"opened_at": "2026-08-01T09:00:00+00:00", "closed_at": "2026-08-01T10:00:00+00:00",
         "direction": -1, "r": 0.4, "depth": 1, "risk_allocated_r": 1.0},
        {"opened_at": "2026-08-02T09:00:00+00:00", "closed_at": "2026-08-02T10:00:00+00:00",
         "direction": -1, "r": -0.2, "depth": 1, "risk_allocated_r": 1.0},
    ]), "utf-8")
    monkeypatch.setattr(ab, "LEDGER_DIRS", (led,))
    uni = tmp_path / "universe"
    uni.mkdir()
    for sym in ("EURJPY", "XAUUSD"):
        (uni / f"{sym}_H1.parquet").write_bytes(b"")
    monkeypatch.setattr(ab, "UNIVERSE", uni)
    exp = ab.book_exposure()
    assert exp["dropped"].get("no_recorded_side") is None
    assert exp["exposure"] == {"EURJPY": 1.0, "XAUUSD": -1.0}
    daily = ab.daily_sleeve_returns()
    assert sorted(daily["xau_m15_anti_breakout"]) == ["2026-08-01", "2026-08-02"]


def test_a_day_a_sleeve_did_not_trade_is_absent_not_zero(monkeypatch, tmp_path) -> None:
    led = tmp_path / "ledgers"
    _write_ledger(led, "EURJPY_asia", [_row(1, 1, 0.5), _row(3, 1, -0.5)])
    monkeypatch.setattr(ab, "LEDGER_DIRS", (led,))
    daily = ab.daily_sleeve_returns()
    assert sorted(daily["EURJPY_asia"]) == ["2026-08-01", "2026-08-03"]   # no 2026-08-02 zero


def test_the_breadth_history_is_one_append_only_row_per_run(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ab, "HISTORY", tmp_path / "effective_breadth.jsonl")
    doc = {"generated_utc": "2026-09-05T00:00:00+00:00",
           "effective": {"n_nominal": 27, "effective_breadth": 1.3, "binding_reading": "x"},
           "clusters": {"occupied_either": ["a"], "empty_in_both": ["b", "c"]}}
    ab._append_history(doc)
    ab._append_history(doc)
    rows = ab.history()
    assert len(rows) == 2
    assert rows[0]["effective_breadth"] == 1.3
    assert rows[0]["n_clusters_empty"] == 2


# -------------------------------------------------------------------- the drawdown-alpha factory
def test_a_candidate_never_cuts_its_own_drawdown_band() -> None:
    """LEAVE-ONE-OUT, AND WITHOUT IT THE MEASUREMENT IS CIRCULAR. `hog` loses enormously in the
    periods where `quiet` earns. Ranking on the FULL book would put those periods in the worst
    band and credit `quiet` for them AND condemn `hog` for its own losses. The band must be cut on
    the book without the candidate, so here `hog`'s own band is set by `quiet` alone."""
    periods = [f"p{i:02d}" for i in range(20)]
    quiet = {p: (1.0 if i % 2 else -1.0) for i, p in enumerate(periods)}
    hog = {p: -50.0 for p in periods[:10]}
    series = {"quiet": quiet, "hog": hog}

    r_hog = da._score("hog", hog, series, periods, 0.5)
    # hog's band is cut on `quiet` alone: the ten periods where quiet returned -1.0, and a
    # threshold that is quiet's own median rather than anything hog's -50R could have set.
    assert r_hog["n_bad_periods"] == 10
    assert r_hog["band_threshold_r"] == pytest.approx(0.0)
    assert r_hog["n"] == 5                # hog traded in five of quiet's ten bad periods

    # The counterfactual this exists to prevent: ranking on the FULL book puts hog's own -50R
    # periods in the worst band, so hog is condemned by its own losses and quiet is credited for
    # sitting in them. The band moves by two orders of magnitude between the two framings.
    full = dict(series)
    full["_book"] = {p: quiet[p] + hog.get(p, 0.0) for p in periods}
    r_circular = da._score("hog", hog, {"_book": full["_book"]}, periods, 0.5)
    assert r_circular["band_threshold_r"] < -1.0
    assert r_circular["band_threshold_r"] != pytest.approx(r_hog["band_threshold_r"])

    r_quiet = da._score("quiet", quiet, series, periods, 0.5)
    # quiet's band is cut on `hog` alone, whose only periods are its first ten.
    assert r_quiet["n_bad_periods"] == 10
    assert r_quiet["band_threshold_r"] == pytest.approx(-50.0)


def test_a_slice_below_the_sample_floor_is_unmeasured_and_never_a_candidate() -> None:
    periods = [f"p{i:02d}" for i in range(40)]
    other = {p: float(-i) for i, p in enumerate(periods)}
    thin = {periods[0]: 5.0, periods[1]: 5.0}
    r = da._score("thin", thin, {"thin": thin, "other": other}, periods, 0.20)
    assert r["verdict"] == da.UNMEASURED
    assert r["n"] < da.MIN_N
    assert "UNMEASURED is not a weak candidate" in r["why"]
    assert "mean_r_in_drawdown" not in r


def test_the_drawdown_bars_are_the_desks_own_and_are_not_loosened() -> None:
    assert da.MIN_N == 8                 # regime_coverage / opportunity_curve's conditional floor
    assert da.T_LINE == 2.0              # research/multiplicity's standing deflated-t bar
    assert tuple(da.BANDS) == (0.05, 0.10, 0.20)


def test_every_drawdown_row_carries_one_shared_multiplicity_denominator(monkeypatch,
                                                                       tmp_path) -> None:
    """Splitting the burden per band or per granularity is the standard way to make a conditional
    slice look significant. One denominator over every test the module ran."""
    led = tmp_path / "ledgers"
    rng = np.random.default_rng(2)
    for name in ("EURJPY_asia", "GBPJPY_asia", "xau_m15_anti_breakout"):
        _write_ledger(led, name, [_row(1 + (i // 6), 1, float(rng.normal()), hour=i % 24)
                                  for i in range(60)])
    import research.state_admission_run as sar
    monkeypatch.setattr(sar, "LEDGER_DIRS", (led,))
    monkeypatch.setattr(da, "OUT", tmp_path / "DRAWDOWN_ALPHA.json")
    doc = da.run(write_queue=False)
    rows = doc["rows"]
    assert rows
    assert len({r["n_tests"] for r in rows}) == 1
    assert next(iter({r["n_tests"] for r in rows})) == len(rows)
    for r in rows:
        if r["verdict"] == da.UNMEASURED:
            continue
        # t_deflated is always the RAW t minus a positive haircut; it never flatters.
        assert r["t_deflated"] <= r["t_raw"]
        if r["verdict"] == da.CANDIDATE:
            assert r["n"] >= da.MIN_N and r["t_deflated"] >= da.T_LINE


def test_the_drawdown_windows_declare_whether_they_reach_the_floor(monkeypatch, tmp_path) -> None:
    led = tmp_path / "ledgers"
    _write_ledger(led, "EURJPY_asia", [_row(1 + i % 5, 1, -float(i), hour=i % 24)
                                       for i in range(12)])
    import research.state_admission_run as sar
    monkeypatch.setattr(sar, "LEDGER_DIRS", (led,))
    monkeypatch.setattr(da, "OUT", tmp_path / "DRAWDOWN_ALPHA.json")
    doc = da.run(write_queue=False)
    day = doc["windows"]["day"]
    assert day["n_periods"] == 5
    for key in ("worst_5pct", "worst_10pct", "worst_20pct"):
        assert day[key]["measurable"] is False        # a five-day book measures no tail
        assert isinstance(day[key]["periods"], list)


# --------------------------------------------------------------- survivor-neighbourhood mining
def test_a_lift_is_not_computed_against_a_base_that_is_barely_positive() -> None:
    """`xau_m15_anti_momentum` earns +0.005R unconditionally on this desk's own history, and
    dividing a +0.060R slice by it produced a '6.1x edge' on a sleeve with no edge to multiply."""
    assert sn.COVERED_R == 0.05
    assert sn.MIN_SLEEVE_N == 20
    assert sn.MIN_SLICE_N == 8
    assert sn.T_LINE == 2.0
    assert sn.LIFT_STRONG == 2.0


def test_a_near_zero_edge_is_not_decomposed_and_says_why(monkeypatch, tmp_path) -> None:
    led = tmp_path / "ledgers"
    # 30 trades alternating +0.5/-0.5 with a tiny positive tilt: n clears the floor, edge does not.
    rows = [_row(1 + i % 20, 1, 0.5 if i % 2 else -0.49, hour=i % 24) for i in range(30)]
    _write_ledger(led, "EURJPY_asia", rows)
    import research.state_admission_run as sar
    monkeypatch.setattr(sar, "LEDGER_DIRS", (led,))
    monkeypatch.setattr(sn, "OUT", tmp_path / "SURVIVOR_NEIGHBOURHOOD.json")
    doc = sn.run(write_queue=False)
    why = " ".join(doc["not_decomposed"].values())
    assert "coverage floor" in why
    assert doc["stronger"] == []


def test_the_verdict_is_taken_on_the_shrunk_mean_not_the_raw_one() -> None:
    """The raw lift is what excites; the shrunk lift is what would be sized. At n=8 the k_state
    prior keeps only 8/48 of the slice's own mean, which is why an eight-trade '3x edge' is not
    one."""
    base = 0.2
    raw_mean = 1.0
    shrunk = sn._shrunk([raw_mean] * 8, base)
    assert shrunk == pytest.approx((8 / 48) * raw_mean + (40 / 48) * base)
    assert shrunk < raw_mean / 2.0
    assert sn._shrunk([raw_mean] * 8, base) / base < raw_mean / base


def test_reliably_positive_is_not_reliably_stronger() -> None:
    """A slice can differ from ZERO with a huge t and be identical to the rest of its own sleeve.
    `_t_stat` cannot tell those apart and `_t_contrast` can, which is why STRONGER needs both."""
    same = [0.5] * 30
    rest_same = [0.5] * 30
    assert sn._t_stat(same) == 0.0                       # zero variance: no t against zero either
    noisy = [0.5, 0.4, 0.6, 0.5, 0.55, 0.45, 0.5, 0.52, 0.48, 0.5]
    assert sn._t_stat(noisy) > 10.0                      # reliably positive
    assert abs(sn._t_contrast(noisy, noisy)) < 1e-9      # and not different from itself
    stronger = [x + 1.0 for x in noisy]
    assert sn._t_contrast(stronger, noisy) > 10.0
    # No complement is not "no difference": a single-bucket dimension has no contrast to make.
    assert sn._t_contrast(noisy, []) == 0.0
    del same, rest_same


def test_the_contrast_deflation_can_never_manufacture_a_difference() -> None:
    """The repo's `deflate_t` is a ONE-SIDED haircut (t - E[max Z]) and turns a contrast of zero
    into a large NEGATIVE number, which reads as a strong finding in the other direction. The
    contrast is deflated in magnitude and floored at zero instead, so deflation only ever moves a
    result toward 'no difference'."""
    rng = np.random.default_rng(21)
    vals = [float(x) for x in rng.normal(size=40)]
    rows = [{"verdict": sn.NEUTRAL, "t_raw": 0.0, "t_vs_rest": 0.0, "mean_r_shrunk": 0.1,
             "mean_r_raw": 0.1, "sleeve_mean_r": 0.1, "lift_shrunk": 1.0, "lift_raw": 1.0,
             "n": 40}]
    sn._verdicts(rows)
    assert rows[0]["t_vs_rest_deflated"] == 0.0          # never -E[max Z]
    rows2 = [dict(rows[0], t_vs_rest=-8.0), dict(rows[0], t_vs_rest=8.0)]
    sn._verdicts(rows2)
    assert rows2[0]["t_vs_rest_deflated"] < 0 > -8.0
    assert abs(rows2[0]["t_vs_rest_deflated"]) < 8.0     # the haircut shrinks the magnitude
    assert 0.0 < rows2[1]["t_vs_rest_deflated"] < 8.0
    assert rows2[0]["t_vs_rest_deflated"] == pytest.approx(-rows2[1]["t_vs_rest_deflated"])
    none_row = [dict(rows[0], t_vs_rest=None)]
    sn._verdicts(none_row)
    assert none_row[0]["t_vs_rest_deflated"] is None
    del vals


def test_a_well_powered_contrast_is_published_even_when_it_misses_the_lift_line(monkeypatch,
                                                                                tmp_path) -> None:
    """The result this module exists to not lose: a large, well-sampled contrast under a 2x lift.
    The lift line is NOT lowered to admit it and it is NOT buried for missing the line."""
    led = tmp_path / "ledgers"
    rng = np.random.default_rng(31)
    rows = []
    for i in range(120):
        # Hour 01 pays much more than every other hour, but not twice the sleeve's average.
        hour = 1 if i % 2 == 0 else 9 + (i % 5)
        r = (0.9 if hour == 1 else 0.1) + float(rng.normal() * 0.15)
        rows.append(_row(1 + i % 20, 1, r, hour=hour))
    _write_ledger(led, "EURJPY_asia", rows)
    import research.state_admission_run as sar
    monkeypatch.setattr(sar, "LEDGER_DIRS", (led,))
    monkeypatch.setattr(sn, "OUT", tmp_path / "SURVIVOR_NEIGHBOURHOOD.json")
    monkeypatch.setattr(sn, "DRAWDOWN", tmp_path / "absent.json")
    doc = sn.run(write_queue=False)
    hot = [r for r in doc["contrast"] if r["dimension"] == "hour_utc" and r["bucket"] == "01"]
    assert hot, "a 0.9R-vs-0.1R hour on n=60 must reach the contrast list"
    r = hot[0]
    assert r["n"] >= sn.MIN_SLICE_N
    assert r["t_vs_rest_deflated"] >= sn.T_LINE
    assert r["mean_r_rest"] is not None and r["mean_r_raw"] > r["mean_r_rest"]
    assert sn.LIFT_STRONG == 2.0                         # the line stands where it stood
    titles = " ".join(t["title"] for t in doc["tasks"])
    assert "hour_utc=01" in titles                       # and the finding reaches the queue


def test_bookkeeping_buckets_never_become_research_targets(monkeypatch, tmp_path) -> None:
    """`no_prior` means the conditioner did not exist yet, not that the world was in that state."""
    led = tmp_path / "ledgers"
    rng = np.random.default_rng(4)
    _write_ledger(led, "EURJPY_asia",
                  [_row(1 + i % 20, 1, float(0.4 + rng.normal() * 0.2), hour=i % 24)
                   for i in range(60)])
    import research.state_admission_run as sar
    monkeypatch.setattr(sar, "LEDGER_DIRS", (led,))
    monkeypatch.setattr(sn, "OUT", tmp_path / "SURVIVOR_NEIGHBOURHOOD.json")
    doc = sn.run(write_queue=False)
    assert doc["rows"]
    assert all(r["bucket"] != "no_prior" for r in doc["rows"])
    assert len({r["n_tests"] for r in doc["rows"]}) == 1


def test_survivor_slices_carry_their_sample_and_their_burden(monkeypatch, tmp_path) -> None:
    led = tmp_path / "ledgers"
    rng = np.random.default_rng(9)
    _write_ledger(led, "EURJPY_asia",
                  [_row(1 + i % 20, 1, float(0.4 + rng.normal() * 0.2), hour=i % 24)
                   for i in range(60)])
    import research.state_admission_run as sar
    monkeypatch.setattr(sar, "LEDGER_DIRS", (led,))
    monkeypatch.setattr(sn, "OUT", tmp_path / "SURVIVOR_NEIGHBOURHOOD.json")
    doc = sn.run(write_queue=False)
    for r in doc["rows"]:
        assert "n" in r
        if r["verdict"] == sn.UNMEASURED:
            assert r["n"] < sn.MIN_SLICE_N
            assert "lift_shrunk" not in r
            continue
        assert r["n"] >= sn.MIN_SLICE_N
        assert r["t_deflated"] <= r["t_raw"]
        if r["verdict"] == sn.STRONGER:
            assert r["lift_shrunk"] >= sn.LIFT_STRONG and r["t_deflated"] >= sn.T_LINE


# ------------------------------------------------------------------------------------- the chain
def test_cluster_occupancy_has_one_owner_and_the_fallback_is_said_out_loud(monkeypatch,
                                                                          tmp_path) -> None:
    """The drawdown factory sees only what has TRADED; the breadth ledger classifies the certified
    book too. Recomputing occupancy locally would report the crisis cluster empty while a
    certified crisis sleeve sat in the canon, and the two artifacts would disagree about one word.
    """
    monkeypatch.setattr(da, "BREADTH", tmp_path / "EFFECTIVE_BREADTH.json")
    empty, why = da._crisis_cluster_empty([("EURJPY_asia", "2026-08-01T00:00:00+00:00", 0.1)])
    assert empty is True
    assert "absent" in why and "TRADED book alone" in why      # the fallback is never silent

    (tmp_path / "EFFECTIVE_BREADTH.json").write_text(json.dumps(
        {"clusters": {"empty_in_both": ["trend", "options_implied"],
                      "occupied_either": ["crisis_drawdown", "mean_reversion"]}}), "utf-8")
    empty2, why2 = da._crisis_cluster_empty([("EURJPY_asia", "2026-08-01T00:00:00+00:00", 0.1)])
    assert empty2 is False        # the artifact knows about a certified sleeve that never traded
    assert why2 == ""


def test_an_absent_drawdown_report_is_unmeasured_not_no_overlap(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sn, "DRAWDOWN", tmp_path / "DRAWDOWN_ALPHA.json")
    states, why = sn.drawdown_states()
    assert states == {}
    assert "absent" in why

    (tmp_path / "DRAWDOWN_ALPHA.json").write_text(json.dumps({
        "min_n": 8,
        "state_signature": {"hour": {
            "worst_5pct": [{"dimension": "weekday", "state": "Tue", "n_in_drawdown": 3,
                            "lift": 9.0}],                       # below the sample floor: ignored
            "worst_20pct": [{"dimension": "weekday", "state": "Tue", "n_in_drawdown": 11,
                             "lift": 1.8},
                            {"dimension": "weekday", "state": "Fri", "n_in_drawdown": 10,
                             "lift": 1.05}],                     # below the lift floor: ignored
        }}}), "utf-8")
    states2, why2 = sn.drawdown_states()
    assert states2 == {("weekday", "Tue"): 1.8}
    assert why2 == ""


def test_a_survivor_state_is_marked_when_it_is_also_a_drawdown_state(monkeypatch,
                                                                     tmp_path) -> None:
    led = tmp_path / "ledgers"
    rng = np.random.default_rng(13)
    _write_ledger(led, "EURJPY_asia",
                  [_row(1 + i % 20, 1, float(0.4 + rng.normal() * 0.2), hour=i % 24)
                   for i in range(60)])
    import research.state_admission_run as sar
    monkeypatch.setattr(sar, "LEDGER_DIRS", (led,))
    monkeypatch.setattr(sn, "OUT", tmp_path / "SURVIVOR_NEIGHBOURHOOD.json")
    dd = tmp_path / "DRAWDOWN_ALPHA.json"
    dd.write_text(json.dumps({"min_n": 8, "state_signature": {"hour": {"worst_20pct": [
        {"dimension": "weekday", "state": "Mon", "n_in_drawdown": 12, "lift": 2.0}]}}}), "utf-8")
    monkeypatch.setattr(sn, "DRAWDOWN", dd)
    doc = sn.run(write_queue=False)
    assert doc["drawdown_states"] == [{"dimension": "weekday", "state": "Mon", "lift": 2.0}]
    marked = [r for r in doc["rows"] if r["in_book_drawdown_state"]]
    assert marked and all(r["bucket"] == "Mon" and r["drawdown_lift"] == 2.0 for r in marked)
    assert all(not r["in_book_drawdown_state"] for r in doc["rows"] if r["bucket"] != "Mon")
    # And the caveat is carried in the artifact, not only in the docstring.
    assert "CONSISTENCY CHECK" in doc["rule"]


# ---------------------------------------------------------------------------------- the mandate
def test_the_breadth_lane_names_no_crypto_exchange() -> None:
    banned = ("binance", "bybit", "okx", "hyperliquid", "kucoin", "coinbase", "kraken", "bitget",
              "deribit", "mexc", "gate.io")
    for mod in (ac, eb, ab, da, sn):
        src = Path(mod.__file__ or "").read_text("utf-8").lower()
        for name in banned:
            assert name not in src, f"{mod.__name__} names {name}"

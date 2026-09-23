"""THE RESIDUAL HUNT, OVER A STORE WHOSE ONE UNEXPLAINED CELL IS PLANTED.

The hunt's whole value is telling a cell the world model genuinely cannot explain from a cell
that merely looks unusual in a noisy panel — and a broken version of it is indistinguishable from
a working one on live data, because both produce a list of plausible-sounding search targets. So
the store here is synthetic and one cell is deliberately shifted: the tests demand the hunt find
THAT cell, flag nothing in a store that is pure noise, and refuse to judge a cell below the named
minimum n rather than calling it clean.

The rest is the contract an hourly organ is trusted on: a target is idempotent under re-running
(the same cell is one target with one id), the six explanation classes are all populated and
derived from the cluster rather than boilerplate, a donation carries a registered family and
never a single-name equity, a residual a later pass explains is CLOSED with its evidence and its
dataset credited, a target nobody has re-measured goes STALE rather than disappearing, and
`--dry-run` writes nothing.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as REG  # noqa: E402
from research import miner_candidate_compiler as MC  # noqa: E402
from research import residual_hunt as rh  # noqa: E402
from research import universe_policy as up  # noqa: E402
from research import world_model as wm  # noqa: E402

REGISTRY = {"EURUSD": {"asset_class": "Forex"}, "USDJPY": {"asset_class": "Forex"},
            "XAUUSD": {"asset_class": "Commodities"}, "Apple": {"asset_class": "Equities"}}
PLANTED_SHIFT = 0.006


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


def _rows(symbol: str, *, n: int = 1400, planted: bool = True, seed: int = 4,
          scale: float = 1.0) -> list[dict]:
    """A residual panel. The `asia` + `low`-vol + `night` cell is shifted when planted."""
    rng = np.random.default_rng(seed)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    out: list[dict] = []
    for i in range(n):
        when = start + timedelta(hours=i)
        hour = when.hour
        session = wm.session_of(hour)
        regime = ("low", "mid", "high")[(i // 97) % 3]
        eps = float(rng.normal(0.0, 0.002)) * scale
        if planted and session == "asia" and regime == "low":
            eps += PLANTED_SHIFT
        out.append({"target": symbol, "symbol": symbol, "horizon": "1h",
                    "time": when.isoformat(), "y": eps + 0.001, "yhat": 0.001,
                    "epsilon": eps, "regime": regime, "session": session})
    return out


@pytest.fixture
def desk(tmp_path, monkeypatch):
    store = tmp_path / "world_model"
    store.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(wm, "STORE", store)
    monkeypatch.setattr(wm, "HORIZONS", {"1h": 1})
    monkeypatch.setattr(wm, "OUT", tmp_path / "reports" / "WORLD_MODEL.json")
    monkeypatch.setattr(wm, "REPRESENTATIONS", tmp_path / "representations")
    monkeypatch.setattr(rh, "STATE", tmp_path / "residual_targets.json")
    monkeypatch.setattr(rh, "OUT", tmp_path / "reports" / "RESIDUAL_HUNT.json")
    monkeypatch.setattr(rh, "DONATIONS", tmp_path / "intel" / "residual_hunt")
    monkeypatch.setattr(rh, "UNIVERSE_JSON", tmp_path / "universe.json")
    monkeypatch.setattr(rh, "EVENT_CALENDAR", tmp_path / "event_calendar.json")
    _write(tmp_path / "universe.json", REGISTRY)
    _write(tmp_path / "event_calendar.json",
           {"valid_through": "2027-01-01T00:00:00+00:00",
            "events": [{"utc": "2026-01-10T19:00:00Z", "name": "FOMC decision"}]})
    _write(tmp_path / "reports" / "WORLD_MODEL.json",
           {"at": "2026-09-17T00:00:00+00:00",
            "dataset_credit": {"price": {"targets": 1, "mean_delta_r2": 0.01}}})
    monkeypatch.setattr(up, "UNIVERSE", tmp_path / "universe.json")
    up._registry.cache_clear()
    monkeypatch.setattr(REG, "BACKUP", tmp_path / "no_backup")
    REG.set_path(tmp_path / "alpha_registry.sqlite")
    yield {"tmp": tmp_path, "store": store}
    REG.set_path(None)
    up._registry.cache_clear()


def _plant(desk, rows) -> None:
    _write(desk["store"] / "residuals_1h.json",
           {"at": "2026-09-17T00:00:00+00:00", "horizon": "1h", "n": len(rows), "rows": rows})


# ------------------------------------------------------------------ the planted residual
def test_the_planted_cell_is_found_and_the_rest_of_the_panel_is_not(desk):
    _plant(desk, _rows("EURUSD"))
    report = rh.run(budget_s=90.0, permutations=120)
    persistent = report["top_clusters"]
    assert persistent, "the planted cell must be flagged"
    top = persistent[0]
    assert top["cell"]["session"] == "asia" and top["cell"]["regime"] == "low"
    assert top["p_mean"] is not None and top["p_mean"] <= rh.P_THRESHOLD
    assert top["effect_sd"] >= rh.MIN_ABS_EFFECT_SD
    others = [c for c in persistent if not (c["cell"]["session"] == "asia"
                                            and c["cell"]["regime"] == "low")]
    assert len(others) <= 1, f"a noise panel should not light up: {others}"


def test_a_pure_noise_store_flags_nothing(desk):
    _plant(desk, _rows("EURUSD", planted=False))
    report = rh.run(budget_s=90.0, permutations=120)
    assert report["clusters"]["persistent"] == 0, report["top_clusters"][:3]
    assert report["targets_opened"] == 0


def test_a_cell_below_the_named_minimum_is_unmeasured_not_clean(desk):
    _plant(desk, _rows("EURUSD", n=200))
    report = rh.run(budget_s=60.0, permutations=40)
    assert report["clusters"]["unmeasured_below_min_n"] > 0
    assert report["clusters"]["min_cluster_n"] == rh.MIN_CLUSTER_N
    for row in report["unmeasured"]:
        assert str(rh.MIN_CLUSTER_N) in row["why"]
        assert row["n"] < rh.MIN_CLUSTER_N


def test_the_null_is_circular_and_a_shifted_block_beats_it():
    rng = np.random.default_rng(9)
    values = rng.normal(size=900)
    mask = np.zeros(900, dtype=bool)
    mask[100:250] = True
    values[mask] += 1.5
    stat, p = rh.circular_block_p(values, mask, "mean", permutations=200)
    assert stat > 1.0 and p <= 0.05
    flat = rng.normal(size=900)
    _, p_flat = rh.circular_block_p(flat, mask, "mean", permutations=200)
    assert p_flat > 0.05


def test_the_permutation_p_is_deterministic_under_the_seed():
    values = np.random.default_rng(1).normal(size=400)
    mask = np.zeros(400, dtype=bool)
    mask[:120] = True
    a = rh.circular_block_p(values, mask, "mean", permutations=64)
    b = rh.circular_block_p(values, mask, "mean", permutations=64)
    assert a == b


# ------------------------------------------------------------------ the search target
def test_the_target_answers_the_six_class_question_from_the_cluster(desk):
    _plant(desk, _rows("USDJPY"))
    report = rh.run(budget_s=90.0, permutations=120)
    assert report["targets_opened"] >= 1
    target = report["targets"][0]
    classes = target["candidate_explanations"]
    assert set(classes) == {"missing_dataset", "participant_class", "region", "representation",
                            "causal_mechanism", "market_interaction"}
    assert all(classes[k] for k in ("missing_dataset", "participant_class", "region",
                                    "causal_mechanism"))
    assert "JP" in classes["region"], "USDJPY names Japan; the region class is derived, not fixed"
    assert any("fix" in p.lower() for p in classes["participant_class"])
    assert "What missing dataset" in target["question"]
    assert target["state"] == "UNPROCESSED"
    assert target["variance_at_open"] > 0


def test_targets_are_idempotent_across_passes(desk):
    _plant(desk, _rows("EURUSD"))
    first = rh.run(budget_s=90.0, permutations=80)
    second = rh.run(budget_s=90.0, permutations=80)
    assert first["targets_opened"] >= 1
    assert second["targets_opened"] == 0, "the same cell is one target, not one per pass"
    assert second["targets_open_total"] == first["targets_open_total"]
    state = json.loads(rh.STATE.read_text(encoding="utf-8"))
    assert len(state["targets"]) == first["targets_open_total"]


# ------------------------------------------------------------------ the donation door
def test_every_routed_family_is_one_the_compiler_actually_accepts():
    """The route table is only useful if the compiler compiles what it names. A family outside
    `_FAMILY_VOCAB` would queue an extraction call that can never succeed."""
    families = {f for _, _, f in rh.FAMILY_ROUTE} | {rh.DEFAULT_FAMILY}
    assert families <= set(MC._FAMILY_VOCAB), families - set(MC._FAMILY_VOCAB)
    for family in families:
        assert MC._text_params(family, "asian session") is not None


def test_donations_compile_and_never_carry_a_single_name_equity(desk):
    _plant(desk, _rows("EURUSD"))
    report = rh.run(budget_s=90.0, permutations=80)
    assert report["donations"]["rows"] >= 1
    rows = json.loads(Path(report["donations"]["path"]).read_text(encoding="utf-8"))
    universe = set(REGISTRY)
    for row in rows:
        assert row["kind"] == "hypothesis"
        assert row["family"] in MC._FAMILY_VOCAB
        assert row["symbols"] and all(up.may_hypothesise(s) for s in row["symbols"])
        candidates, disposition = MC.compile_row("residual_hunt", row, universe)
        assert disposition in {"STRUCTURED_HYPOTHESIS", "EXACT_RECIPE", "TEXT_EXTRACTED"}
        assert candidates, row

    equity = dict(rows[0])
    equity["symbols"] = ["Apple"]
    assert rh.donation_rows([{**report["targets"][0], "cell": {**report["targets"][0]["cell"],
                                                               "target": "Apple"}}],
                            set(up.split(REGISTRY.keys())[up.HYPOTHESIS])) == []


def test_the_discovery_and_frontier_row_land_in_the_registry(desk):
    _plant(desk, _rows("EURUSD"))
    rh.run(budget_s=90.0, permutations=80)
    found = REG.discoveries(state="UNPROCESSED")
    assert any(d["generator"] == "residual_hunt" for d in found)
    row = next(d for d in found if d["generator"] == "residual_hunt")
    assert row["source_type"] == "residual_target"
    assert row["discovery_id"].startswith("rh_")
    conn = REG.connect()
    try:
        cells = conn.execute("SELECT cell FROM frontier_map WHERE cell LIKE 'residual:%'"
                             ).fetchall()
    finally:
        conn.close()
    assert cells, "a residual cell is cold ground the scouts must be able to see"


# ------------------------------------------------------------------ delayed credit
def test_a_residual_a_later_dataset_explains_is_closed_and_the_dataset_credited(desk):
    _plant(desk, _rows("EURUSD"))
    first = rh.run(budget_s=90.0, permutations=80)
    assert first["targets_opened"] >= 1
    # The world model gains a dataset and the cell's residual variance collapses.
    _write(wm.OUT, {"at": "2026-09-17T01:00:00+00:00",
                    "dataset_credit": {"price": {"targets": 1, "mean_delta_r2": 0.01},
                                       "axis:boj_fix": {"targets": 3, "mean_delta_r2": 0.2}}})
    _plant(desk, _rows("EURUSD", seed=4, scale=0.05))
    second = rh.run(budget_s=90.0, permutations=80)
    assert second["targets_closed"] >= 1
    closure = second["closures"][0]
    assert closure["variance_drop"] >= rh.EXPLAINED_DROP
    assert "axis:boj_fix" in closure["credited_datasets"]
    memories = REG.memories(kind="residual_closed")
    assert memories and "residual variance" in memories[0]["statement"]


def test_a_target_nobody_re_measures_goes_stale_rather_than_disappearing(desk):
    old = (datetime.now(tz=UTC) - timedelta(days=rh.STALE_DAYS + 5)).isoformat()
    book = rh.Book(targets={"rh_gone": {"cluster_id": "rh_gone", "opened_at": old,
                                        "variance_at_open": 1.0, "cell": {"target": "EURUSD"}}},
                   datasets_seen=[])
    closures, still_open = rh.settle(book, {}, set())
    assert closures == []
    assert still_open[0]["state"] == "STALE"
    assert "not a deletion" in still_open[0]["why"]


# ------------------------------------------------------------------ the empty and dry cases
def test_an_empty_store_reads_unmeasured_and_names_its_clock(desk):
    report = rh.run(budget_s=30.0)
    assert report["status"] == "UNMEASURED"
    assert "hourly_cycle:world_model" in report["measured_by"]


def test_dry_run_writes_nothing(desk):
    _plant(desk, _rows("EURUSD"))
    report = rh.run(budget_s=60.0, permutations=40, dry_run=True)
    assert report["dry_run"] is True
    assert not rh.OUT.exists() and not rh.STATE.exists()
    assert not rh.DONATIONS.exists()
    assert report["registry"]["status"] == "SKIPPED_DRY_RUN"


def test_the_calendar_reports_three_states_never_two(desk):
    calendar = rh.load_calendar(desk["tmp"] / "event_calendar.json")
    event = datetime(2026, 1, 10, 19, tzinfo=UTC).timestamp()
    stamps = np.asarray([event, event + 40 * 3600, datetime(2020, 1, 1, tzinfo=UTC).timestamp()])
    assert calendar.classify(stamps) == ["event", "endogenous", "uncovered"]


def test_time_of_day_buckets_cover_every_hour():
    assert {rh.time_of_day(h) for h in range(24)} == {"night", "morning", "afternoon", "evening"}


def test_the_exact_null_matches_a_brute_force_roll():
    """The FFT enumeration must BE the loop it replaces. A transform-convention slip (correlation
    vs convolution) would shift the null by one and pass every eyeball test."""
    rng = np.random.default_rng(17)
    values = rng.normal(size=257)
    mask = np.zeros(257, dtype=bool)
    mask[np.asarray([3, 9, 40, 41, 42, 200, 256])] = True
    fast = rh.all_shift_means(values, mask)
    brute = np.asarray([np.roll(values, s)[mask].mean() for s in range(257)])
    assert fast == pytest.approx(brute, abs=1e-12)


def test_benjamini_hochberg_charges_the_whole_pass_for_its_trials():
    """One p of 0.01 among sixty cells is not a finding; the same p among two is."""
    many = [0.01] + [0.4 + i / 100 for i in range(59)]
    assert rh.benjamini_hochberg(many, q=0.05) == 0.0
    assert rh.benjamini_hochberg([0.001, 0.9], q=0.05) == pytest.approx(0.001)
    assert rh.benjamini_hochberg([], q=0.05) == 0.0
    assert rh.benjamini_hochberg([float("nan")], q=0.05) == 0.0


def test_the_report_names_the_multiplicity_charge_it_paid(desk):
    _plant(desk, _rows("EURUSD"))
    report = rh.run(budget_s=90.0, permutations=80)
    null = report["null"]
    assert null["fdr_q"] == rh.FDR_Q
    assert null["cells_charged"] == report["clusters"]["measured"]
    assert null["bh_cut"] >= 0.0
    assert "shared cost" in null["why"]

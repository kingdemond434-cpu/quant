"""The conversion maximiser: a planted row of every blocker class leaves with a disposition.

EVERY INPUT IS SYNTHETIC. The registry is a fresh sqlite file in `tmp_path`, the universe
registry and the bar files are written by these tests, and the seat directory is redirected --
so nothing here depends on what the box happened to have on disk, and nothing here writes a
tracked file.

THE LOAD-BEARING TESTS.

`test_every_planted_blocker_class_leaves_with_a_disposition` is the mandate in one assertion: one
row of each class is planted and NOT ONE may be examined and dropped. `silent_drops` must be 0,
and every unrepaired row must carry a named blocker AND an owner.

`test_nothing_off_universe_is_ever_converted` runs the REAL `universe_policy` over a synthetic
broker registry. A crypto-exchange row and a single-name equity are the only two permanent
refusals the addendum admits, and neither may reach the queue as a hypothesis cell.

`test_a_row_that_cannot_be_repaired_stays_queued_with_its_blocker` pins the principal's addendum
of 2026-09-23: an unrepairable row stays QUEUED carrying its blocker and its owner. It is never
parked in a siding, because a siding is how a backlog stops being counted.

`test_a_coarser_chart_is_built_from_the_bars_the_desk_holds` and
`test_a_finer_chart_binds_to_the_finest_series_held` are "never blocked on bars": H4 IS four H1
bars, so it is built; M5 cannot be made from H1 by any honest arithmetic, so the cell is bound to
H1 and the fetch is requested -- and in neither case is the row refused.

`test_breadth_is_the_desks_own_effective_rank` pins the closed form against
`libs.risk.fx_exposure.effective_rank`, so the number this organ publishes as breadth is the same
number the desk means by breadth everywhere else.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import conversion_maximiser as cm  # noqa: E402

from libs.moat import registry as R  # noqa: E402
from research import universe_policy as up  # noqa: E402

#: A synthetic broker registry: two hypothesis-lane instruments and one single name.
REGISTRY: dict[str, dict[str, Any]] = {
    "TESTFX": {"asset_class": "Forex"},
    "TESTXAU": {"asset_class": "Metals"},
    "TESTCO": {"asset_class": "Equities"},
}


def _bars(n: int, freq: str = "1h") -> pd.DataFrame:
    idx = pd.date_range("2022-01-03", periods=n, freq=freq, tz=UTC, name="time")
    rng = np.random.default_rng(7)
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.1, n))
    return pd.DataFrame({"open": close, "high": close + 0.2, "low": close - 0.2,
                         "close": close, "tick_volume": np.arange(n) % 97 + 1,
                         "spread": 12, "real_volume": 0}, index=idx)


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A whole synthetic desk: registry, universe, bars and seat dir, all in tmp_path."""
    uni = tmp_path / "universe"
    uni.mkdir()
    (uni / "universe.json").write_text(json.dumps(REGISTRY), encoding="utf-8")
    _bars(1200).to_parquet(uni / "TESTFX_H1.parquet")
    _bars(1200).to_parquet(uni / "TESTXAU_H1.parquet")
    seat = tmp_path / "seat"
    seat.mkdir()
    monkeypatch.setattr(cm, "UNIVERSE_DIR", uni)
    monkeypatch.setattr(cm, "UNIVERSE_JSON", uni / "universe.json")
    monkeypatch.setattr(cm, "SEAT_DIR", seat)
    monkeypatch.setattr(cm, "REPO", tmp_path)
    monkeypatch.setattr(up, "UNIVERSE", uni / "universe.json")
    up._registry.cache_clear()
    R.set_path(tmp_path / "reg.sqlite")
    conn = R.connect()
    try:
        yield {"conn": conn, "universe": uni, "seat": seat, "root": tmp_path}
    finally:
        conn.close()
        R.set_path(None)
        up._registry.cache_clear()


def _plant(conn, cid: str, **fields: Any) -> str:
    base: dict[str, Any] = {"family": "", "symbol": "", "params": {"cid": cid},
                            "origin": "DESK", "mechanism": "", "status": "donated",
                            "candidate_id": cid, "chart": "H1", "conn": conn}
    base.update(fields)
    new_id, _created = R.enqueue_candidate(**base)
    return new_id


def _plant_the_seven(conn) -> dict[str, str]:
    """One row of every blocker class the compile contract can name."""
    ids = {}
    ids["NO_FALSIFIER"] = _plant(
        conn, "c_nofals", family="range_reversion", symbol="TESTFX",
        mechanism="mean reversion after an overnight gap",
        required_data="universe/TESTFX_H1.parquet")
    ids["NO_DATA"] = _plant(
        conn, "c_nodata", family="range_reversion", symbol="TESTXAU", chart="H4",
        mechanism="mean reversion after an overnight gap", falsifier="re-judged and it fails")
    ids["NO_FAMILY"] = _plant(
        conn, "c_nofam", family="", symbol="TESTFX",
        mechanism="mean reversion after an overnight gap")
    ids["NO_INSTRUMENT"] = _plant(
        conn, "c_noinst", family="range_reversion", symbol="",
        mechanism="mean reversion after an overnight gap on TESTXAU")
    ids["PROSE_ONLY"] = _plant(
        conn, "c_prose", family="", symbol="",
        mechanism="traders talk about liquidity drying up before the fix and it feels tradable")
    ids["OFF_UNIVERSE"] = _plant(
        conn, "c_offuni", family="range_reversion", symbol="TESTFX",
        mechanism="funding rate reversal on binance perpetuals",
        falsifier="re-judged and it fails", required_data="universe/TESTFX_H1.parquet")
    ids["EVENT_LANE"] = _plant(
        conn, "c_event", family="", symbol="",
        mechanism="mean reversion after an overnight gap on TESTCO")
    return ids


def _run(desk, **kw) -> dict[str, Any]:
    body = cm.run(budget=cm.Budget(kw.pop("budget_s", 60.0)), conn=desk["conn"],
                  max_rows=kw.pop("max_rows", 50), dry_run=kw.pop("dry_run", False),
                  universe_dir=desk["universe"], seat_dir=desk["seat"],
                  carry_path=kw.pop("carry_path", desk["root"] / "carry.json"), **kw)
    body["largest_blocker"] = cm.largest_blocker(body)
    body["conversion_rate"] = cm._conversion_rates(body)
    return body


# ------------------------------------------------------------------ the mandate, in one test
def test_every_planted_blocker_class_leaves_with_a_disposition(desk) -> None:
    _plant_the_seven(desk["conn"])
    out = _run(desk)

    assert out["examined"] == 7
    assert out["conversion_rate"]["silent_drops"] == 0, (
        "a row was examined and dropped -- silence is the one disposition the mandate forbids")
    assert out["conversion_rate"]["disposition_rate"] == 1.0

    # Every row that was NOT converted must name its blocker AND the organ that owns it.
    for entry in out["still_blocked_rows"] + out["refusals"]:
        assert entry["reason"], entry
        assert entry["owner"] and entry["owner"] != "unassigned", entry
        assert entry["detail"], entry

    # The three repairable classes are actually repaired, not merely re-described.
    repaired = {r["reason"] for r in out["repairs"]}
    assert "NO_FALSIFIER" in repaired
    assert {"NO_FAMILY", "NO_INSTRUMENT", "NO_DATA"} & repaired


def test_per_blocker_class_publishes_count_repair_rate_and_median_age(desk) -> None:
    _plant_the_seven(desk["conn"])
    out = _run(desk)
    table = out["per_blocker_class"]
    assert table, "the per-class table is the daily visibility the addendum asks for"
    for name, stat in table.items():
        assert stat["seen"] >= 1
        assert stat["repair_rate"] is not None
        assert stat["median_age_days"] is not None, f"{name} has no measured age"
        assert stat["owner"]
    # The daily attack names ONE class and ONE owner.
    largest = out["largest_blocker"]
    assert largest["status"] == "MEASURED"
    assert largest["blocker"] in cm.DEFECT_OWNER
    assert largest["owner"] and "LARGEST BLOCKER" in largest["line"]


# ------------------------------------------------------------------------ the two refusals
def test_nothing_off_universe_is_ever_converted(desk) -> None:
    ids = _plant_the_seven(desk["conn"])
    out = _run(desk)

    refused = {r["reason"] for r in out["refusals"]}
    assert "OFF_UNIVERSE" in refused, "a crypto-exchange-native row reached the queue"
    row = desk["conn"].execute("SELECT status, rejection_reason FROM research_candidates "
                               "WHERE id=?", (ids["OFF_UNIVERSE"],)).fetchone()
    assert row["status"] == cm.RETIRED
    assert "OFF_UNIVERSE" in str(row["rejection_reason"])

    # No cell anywhere in the registry names the banned venue.
    banned = desk["conn"].execute(
        "SELECT COUNT(*) FROM research_candidates WHERE status IN "
        "('queued','claimed') AND LOWER(mechanism) LIKE '%binance%'").fetchone()[0]
    assert banned == 0


def test_a_single_name_equity_is_never_hunted_for_a_hypothesis(desk) -> None:
    ids = _plant_the_seven(desk["conn"])
    out = _run(desk)
    by_id = {e["id"]: e for e in out["refusals"] + out["still_blocked_rows"]}
    entry = by_id[ids["EVENT_LANE"]]
    assert entry["reason"] in ("EVENT_LANE", "PROSE_ONLY", "NO_INSTRUMENT")
    row = desk["conn"].execute("SELECT symbol FROM research_candidates WHERE id=?",
                               (ids["EVENT_LANE"],)).fetchone()
    assert str(row["symbol"] or "") != "TESTCO", (
        "the two-lane law (2026-09-06) forbids binding a single name into the hypothesis lane")


# -------------------------------------------------------------- nothing is parked and forgotten
def test_a_row_that_cannot_be_repaired_stays_queued_with_its_blocker(desk) -> None:
    cid = _plant(desk["conn"], "c_unknown", family="", symbol="",
                 mechanism="something nobody has named yet and no instrument is given")
    out = _run(desk)
    assert out["still_blocked"] >= 1
    row = desk["conn"].execute("SELECT status, rejection_reason, failure_class "
                               "FROM research_candidates WHERE id=?", (cid,)).fetchone()
    assert row["status"] == "queued", "an unrepaired row must never be parked in a siding"
    assert row["status"] != cm.ROUTED
    assert row["failure_class"], "the blocker must be written onto the row"
    assert "owner:" in str(row["rejection_reason"])


def test_the_debt_falls_when_rows_are_repaired(desk) -> None:
    for i in range(6):
        _plant(desk["conn"], f"c_f{i}", family="range_reversion", symbol="TESTFX",
               mechanism="mean reversion after an overnight gap",
               required_data="universe/TESTFX_H1.parquet")
    out = _run(desk)
    before = out["debt_before"]["total_debt"]
    after = out["debt_after"]["total_debt"]
    assert before is not None and after is not None
    assert after < before, "a pass that repairs rows must lower the measured debt"
    assert out["debt_after"]["status"] == "MEASURED"


def test_the_debt_components_are_named_and_never_silently_zero(desk) -> None:
    debt = cm.measure_debt(desk["conn"])
    assert set(debt["components"]) == {"silent_discoveries", "unreasoned_blocks",
                                       "donated_never_cell", "untestable_queued",
                                       "parked_past_grace"}
    for name in debt["components"]:
        assert debt["why"][name], f"{name} has no stated reason for being debt"
    assert debt["total_debt"] == sum(debt["components"].values())


# ------------------------------------------------------------------------------- the bars
def test_a_coarser_chart_is_built_from_the_bars_the_desk_holds(desk) -> None:
    chart, action, why = cm.ensure_bars("TESTFX", "H4", universe_dir=desk["universe"])
    assert chart == "H4"
    assert action.startswith("resampled from H1"), (action, why)
    built = desk["universe"] / "TESTFX_H4.parquet"
    assert built.exists()
    frame = pd.read_parquet(built)
    # H4 IS four H1 bars: the aggregation must be exact, not interpolated.
    src = pd.read_parquet(desk["universe"] / "TESTFX_H1.parquet")
    assert len(frame) == pytest.approx(len(src) / 4, rel=0.02)
    assert frame["high"].max() <= src["high"].max() + 1e-9
    assert frame["low"].min() >= src["low"].min() - 1e-9


def test_a_finer_chart_binds_to_the_finest_series_held(desk) -> None:
    chart, action, why = cm.ensure_bars("TESTFX", "M5", universe_dir=desk["universe"])
    assert action == "rebound"
    assert chart == "H1", "the cell must be bound to a series the desk holds, not refused"
    assert "finer" in why and "bar request" in why
    assert not (desk["universe"] / "TESTFX_M5.parquet").exists(), (
        "finer bars may never be manufactured from coarser ones")


def test_a_symbol_with_no_series_is_a_request_and_never_a_refusal(desk) -> None:
    chart, action, why = cm.ensure_bars("TESTCO", "H1", universe_dir=desk["universe"])
    assert action == "request"
    assert chart == ""
    assert "bar request" in why


def test_the_bar_coverage_report_drives_the_backfill(desk) -> None:
    cov = cm.bar_coverage(["TESTFX", "TESTXAU", "TESTCO"], universe_dir=desk["universe"])
    assert cov["symbols_measured"] == 2, "single names are not required to carry the ladder"
    assert cov["per_symbol"]["TESTFX"]["H1"] == "held"
    assert cov["per_symbol"]["TESTFX"]["H4"] == "resampleable"
    assert cov["per_symbol"]["TESTFX"]["M5"] == "fetch"
    assert cov["fetch_requests"] >= 1
    assert cov["owner"]
    assert {"symbol": "TESTFX", "chart": "H4"} in cov["resampleable"]


def test_the_backfill_builds_every_series_the_arithmetic_allows(desk) -> None:
    cov = cm.bar_coverage(["TESTFX", "TESTXAU"], universe_dir=desk["universe"])
    out = cm.backfill_bars(cov, budget=cm.Budget(60.0), universe_dir=desk["universe"])
    assert out["built"] >= 2, "the coverage report is a work list, not a description"
    for sym in ("TESTFX", "TESTXAU"):
        assert (desk["universe"] / f"{sym}_H4.parquet").exists()
        assert not (desk["universe"] / f"{sym}_M1.parquet").exists(), (
            f"{sym}: a finer bar may never be invented to make a ladder look full")
    # 1,200 H1 bars make 300 H4 bars but only 50 D1 bars, which is below the minimum a cell can
    # be judged on. That series is NOT written and the shortfall is named: replacing "no data"
    # with "data that fails the next gate" is not a conversion.
    assert not (desk["universe"] / "TESTFX_D1.parquet").exists()
    assert any(f["chart"] == "D1" and "minimum" in f["why"] for f in out["failures"]), \
        out["failures"]
    # Run again: what is already held is not rebuilt, and the same shortfall is named the same way.
    again = cm.backfill_bars(cm.bar_coverage(["TESTFX"], universe_dir=desk["universe"]),
                             budget=cm.Budget(60.0), universe_dir=desk["universe"])
    assert again["built"] == 0
    assert all("minimum" in f["why"] for f in again["failures"])


# ------------------------------------------------------------------------------ the breadth
def test_breadth_is_measured_before_and_after(desk) -> None:
    for i in range(4):
        _plant(desk["conn"], f"c_b{i}", family="range_reversion", symbol="TESTFX",
               mechanism="mean reversion after an overnight gap",
               required_data="universe/TESTFX_H1.parquet")
    out = _run(desk)
    delta = out["breadth_delta"]
    assert delta["status"] == "MEASURED"
    assert delta["effective_breadth_after"] >= delta["effective_breadth_before"]
    assert out["breadth_before"]["status"] in ("MEASURED", "UNMEASURED")
    assert out["breadth_after"]["status"] == "MEASURED"
    assert out["breadth_after"]["basis"], "the breadth number must say what it is a ratio of"


def test_breadth_is_the_desks_own_effective_rank() -> None:
    from libs.risk.fx_exposure import effective_rank
    for counts in ([5.0], [3.0, 3.0, 3.0], [100.0, 1.0, 1.0], [7.0, 2.0, 11.0, 4.0]):
        mine = cm.participation_ratio(counts)
        theirs = effective_rank(np.diag(np.sqrt(np.asarray(counts, dtype="float64"))))
        assert mine == pytest.approx(theirs, rel=1e-9), counts
    assert cm.participation_ratio([]) == 0.0
    assert cm.participation_ratio([0.0, 0.0]) == 0.0


def test_the_queue_is_ordered_by_breadth_and_not_by_raw_count() -> None:
    crowded = {"forex|range_reversion|unknown|price_only|h1|all|sub_1d|unknown": 900}
    empty_cell = {"family": "carry_rollover", "symbol": "TESTXAU", "mechanism": "carry",
                  "chart": "D1", "id": "b"}
    crowded_cell = {"family": "range_reversion", "symbol": "TESTFX", "chart": "H1",
                    "session": "all", "horizon": "sub_1d", "mechanism": "range_reversion",
                    "asset_class": "forex", "information": "price_only", "id": "a"}
    counts = {R.grid_cell(crowded_cell): 900, **crowded}
    ranked = sorted([crowded_cell, empty_cell], key=lambda r: cm._rank_key(r, counts))
    assert ranked[0]["id"] == "b", (
        "LAWS 5b: a row landing in an empty axis region outranks one landing where the docket "
        "is already 900 deep")


# ------------------------------------------------------------------------- trials and writes
def test_the_pass_charges_effective_trials_not_raw_count(desk) -> None:
    for i in range(8):
        _plant(desk["conn"], f"c_t{i}", family="range_reversion", symbol="TESTFX",
               mechanism="mean reversion after an overnight gap",
               required_data="universe/TESTFX_H1.parquet")
    out = _run(desk)
    charge = out["effective_trials_charged"]
    assert charge["n_raw"] >= 8
    assert charge["n_effective"] is not None
    assert charge["n_effective"] <= charge["n_raw"], (
        "eight mutations of one rule are not eight independent looks at the tape")
    assert "participation ratio" in charge["basis"]


def test_a_dry_run_writes_nothing(desk) -> None:
    ids = _plant_the_seven(desk["conn"])
    before = {r[0]: r[1] for r in desk["conn"].execute(
        "SELECT id, status FROM research_candidates")}
    out = _run(desk, dry_run=True)
    after = {r[0]: r[1] for r in desk["conn"].execute(
        "SELECT id, status FROM research_candidates")}
    assert before == after
    assert out["examined"] == len(ids)
    assert list(desk["seat"].iterdir()) == []


def test_prose_is_routed_to_the_naming_seat(desk) -> None:
    _plant(desk["conn"], "c_p", family="", symbol="",
           mechanism="a feeling about the fix that names neither instrument nor rule")
    out = _run(desk)
    assert out["naming_requests"]["rows"] >= 1
    path = Path(out["naming_requests"]["path"])
    assert path.exists() and path.parent == desk["seat"]
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["task"] == "NAME_THE_MECHANISM"
    assert doc["owner"] and doc["naming_requests"]


def test_an_old_parked_row_counts_as_debt_again(desk) -> None:
    cid = _plant(desk["conn"], "c_old", family="range_reversion", symbol="TESTFX")
    stale = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
    desk["conn"].execute("UPDATE research_candidates SET status=?, updated_at=? WHERE id=?",
                         (cm.ROUTED, stale, cid))
    desk["conn"].commit()
    debt = cm.measure_debt(desk["conn"])
    assert debt["components"]["parked_past_grace"] == 1, (
        "an owner that never collects is silence with extra steps")


# ----------------------------------------------------------------- no queues, no legal gate
def test_the_leftover_is_the_first_work_of_the_next_pass(desk) -> None:
    for i in range(12):
        _plant(desk["conn"], f"c_c{i}", family="range_reversion", symbol="TESTFX",
               mechanism="mean reversion after an overnight gap",
               required_data="universe/TESTFX_H1.parquet")
    carry = desk["root"] / "carry.json"
    first = _run(desk, max_rows=3, carry_path=carry)
    assert first["carried_in"] == 0
    assert first["carried_out"] >= 1, "a budget-capped pass must hand its remainder forward"
    left = json.loads(carry.read_text(encoding="utf-8"))["ids"]
    assert left

    second = _run(desk, max_rows=3, carry_path=carry)
    assert second["carried_in"] == len(left)
    touched = {r["id"] for r in second["repairs"]} | {
        e["id"] for e in second["still_blocked_rows"] + second["refusals"]}
    assert touched & set(left), "the leftover must be worked FIRST, not re-ranked to the back"


def test_the_oldest_unconverted_age_is_published_every_pass(desk) -> None:
    cid = _plant(desk["conn"], "c_old2", family="range_reversion", symbol="TESTFX")
    old = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
    desk["conn"].execute("UPDATE research_candidates SET created_at=? WHERE id=?", (old, cid))
    desk["conn"].commit()
    oldest = cm.oldest_unconverted(desk["conn"])
    assert oldest["status"] == "MEASURED"
    assert oldest["age_days"] >= 39.0
    out = _run(desk, dry_run=True)
    assert out["oldest_unconverted"]["status"] in ("MEASURED", "NONE")


def test_no_licence_or_access_label_is_ever_a_blocker(desk) -> None:
    """The 2026-09-23 order removed "public and licensed ground only" everywhere."""
    cid = _plant(desk["conn"], "c_lic", family="range_reversion", symbol="TESTFX",
                 mechanism="mean reversion after an overnight gap",
                 required_data="universe/TESTFX_H1.parquet",
                 information="scraped from a site whose licence is unclear; robots unknown")
    out = _run(desk)
    assert cid in {r["id"] for r in out["repairs"]}, (
        "a licence or access label is provenance metadata, never a reason to refuse a row")
    assert not any("licen" in str(e).lower() or "robots" in str(e).lower()
                   for e in out["refusals"])
    policy = out["refusal_policy"]
    assert len(policy["admissible_permanent_refusals"]) == 2
    assert any("licence" in s for s in policy["never_a_refusal"])


# ------------------------------------------------- the judge is scarce and the docket is broad
def test_a_live_banned_family_is_kept_for_study_and_never_judged(desk) -> None:
    """`discovered` took 22,009 judgements and passed zero; it cannot reach the book at all."""
    cid = _plant(desk["conn"], "c_banned", family="discovered", symbol="TESTFX",
                 mechanism="mean reversion after an overnight gap",
                 required_data="universe/TESTFX_H1.parquet")
    out = _run(desk)
    assert out["routed_to_study"] == 1
    assert "discovered" in out["banned_from_live"]
    row = desk["conn"].execute("SELECT status, rejection_reason FROM research_candidates "
                               "WHERE id=?", (cid,)).fetchone()
    assert row is not None, "the row must be kept: mining stays unrestricted"
    assert row["status"] == cm.STUDY
    assert "banned from live capital" in str(row["rejection_reason"])
    assert cid not in {r["id"] for r in out["repairs"]}, "it must not reach the judging queue"
    assert out["conversion_rate"]["silent_drops"] == 0


def test_the_docket_order_sends_the_least_judged_family_to_the_gates_first() -> None:
    from research.merge_hypotheses import breadth_order
    rows = ([{"family": "carry", "i": i} for i in range(3)]
            + [{"family": "cross_asset_residual", "i": i} for i in range(5)])
    judged = {"carry": 900, "cross_asset_residual": 0}
    ordered = breadth_order(rows, judged)
    assert ordered[0]["family"] == "cross_asset_residual", (
        "the gauntlet takes the docket in order under a bar budget, so order IS selection")
    assert [r["i"] for r in ordered[:5]] == [0, 1, 2, 3, 4], "row order within a family is kept"
    assert len(ordered) == len(rows), "ordering may never drop a row"


def test_the_judged_versus_docket_ratio_is_published(desk, monkeypatch) -> None:
    from research import merge_hypotheses as mh
    docket = desk["root"] / "docket.json"
    docket.write_text(json.dumps(
        [{"family": "cross_asset_residual"}] * 50 + [{"family": "carry"}] * 2), encoding="utf-8")
    monkeypatch.setattr(mh, "TARGET", docket)
    monkeypatch.setattr(mh, "STUDY_BANK", desk["root"] / "study.json")
    monkeypatch.setattr(mh, "judged_by_family", lambda *a, **k: {"carry": 800, "discovered": 200})
    table = cm.judged_vs_docket()
    assert table["status"] == "MEASURED"
    worst = next(iter(table["least_judged_first"]))
    assert worst == "cross_asset_residual", table["least_judged_first"]
    assert table["least_judged_first"]["carry"]["judged_per_docket_row"] == 400.0
    freed = table["judge_capacity_freed"]
    assert freed["judgements"] == 200
    assert freed["share_of_judge"] == pytest.approx(0.2)


def test_the_pass_cap_is_derived_from_measured_memory_not_a_machine_size(monkeypatch) -> None:
    monkeypatch.setattr(cm, "_free_bytes", lambda: None)
    assert cm.max_rows_per_pass() == cm.MAX_ROWS_FLOOR
    monkeypatch.setattr(cm, "_free_bytes", lambda: 80 * 1024 ** 3)
    assert cm.max_rows_per_pass() > cm.MAX_ROWS_FLOOR
    monkeypatch.setattr(cm, "_free_bytes", lambda: 64 * 1024 ** 2)
    assert cm.max_rows_per_pass() == cm.MAX_ROWS_FLOOR

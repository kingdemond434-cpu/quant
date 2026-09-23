"""THE MIDDLE EAST INTERACTION MINER -- six families, two cross-region triples, one screen.

EVERY READER IS INJECTED. The context takes `series_fn`, `bars_fn` and `record_fn`, so these tests
touch no axis store, no parquet and no registry: the series are planted in memory and the
discoveries are captured in a list. A test that needed the desk's own data would measure the box
rather than the miner.

WHAT THESE TESTS REFUSE TO LET THROUGH:

  * A SCREEN THAT CANNOT FIND A PLANTED EFFECT. One family is given a relationship that exists
    ONLY in the upper half of a conditioning state. The screen must find it, must report the
    complement as the control, and must set `separates` -- because a conditional claim whose
    control is equally strong has been refuted, not confirmed.
  * AN ABSENCE REPORTED AS A ZERO. A missing leg is UNMEASURED WITH THE LEG NAMED, the family
    still records its question, and the payload carries what is missing -- the compiler's blocked
    backlog IS the data-acquisition plan (L1.28a).
  * A LOOK-AHEAD JOIN. The lead joins at its AVAILABLE time, never at the period it describes.
    That single choice is the difference between a tradable screen and a fiction.
  * A DRY RUN THAT WRITES. `--dry-run` must leave no report and persist no discovery.
  * A TARGET THE BOX CANNOT TRADE. Every family's targets are checked against the broker registry
    and against the two-lane order.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import middle_east_interaction as M  # noqa: E402
from countries import resolve, universe_symbols  # noqa: E402

N_DAYS = 420


# ------------------------------------------------------------------------------ the plant
def _planted() -> dict[str, list[tuple[str, float]]]:
    """A lead whose CHANGE moves the target one day later -- but only in the HIGH state.

    Deterministic: a fixed-seed generator, a sign-alternating conditioning state, and a target
    whose next-day return is a multiple of the lead's change in the high half and pure noise in
    the low half. That is the exact shape a conditional transmission claim has, so a screen that
    cannot recover it here cannot recover one anywhere.
    """
    import numpy as np
    rng = np.random.default_rng(20260917)
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(N_DAYS)]
    deltas = rng.normal(0.0, 0.01, N_DAYS)
    lead, level = [], 100.0
    for d in deltas:
        level *= 1.0 + d
        lead.append(level)
    # the state: high for the first half of every ten-day block, low for the rest
    cond = [1.0 if (i // 10) % 2 == 0 else -1.0 for i in range(N_DAYS)]
    price, prices = 50.0, []
    noise = rng.normal(0.0, 0.0004, N_DAYS)
    for i in range(N_DAYS):
        prices.append(price)
        effect = 0.6 * deltas[i] if cond[i] > 0 else 0.0
        price *= float(np.exp(effect + noise[i]))
    iso = [d.isoformat() for d in days]
    return {"lead": list(zip(iso, lead, strict=True)),
            "target": list(zip(iso, prices, strict=True)),
            "cond": list(zip(iso, cond, strict=True))}


PLANT = _planted()

PLANTED_FAMILY = M.Family(
    fid="planted_conditional",
    title="a planted conditional lead-lag, for the screen's own calibration",
    country="sa",
    lead=M.Leg(kind="series", what="the planted lead", country="sa", lane="test",
               series="lead"),
    condition=M.Leg(kind="series", what="the planted state", country="sa", lane="test",
                    series="cond"),
    targets=("XAUUSD",),
    horizon=1,
    mechanism="a synthetic relationship that exists only in the high state",
    control="the complement half of the state, screened identically",
    falsifier="the conditional and control legs become indistinguishable",
)


def _ctx(series: dict[str, list[tuple[str, float]]] | None = None,
         bars: dict[str, list[tuple[str, float]]] | None = None, **kw: Any) -> M.Ctx:
    table = series or {}
    price = bars or {}
    recorded: list[dict[str, Any]] = []

    def series_fn(country: str, lane: str, name: str) -> list[tuple[str, float]]:
        return list(table.get(name, []))

    def bars_fn(symbol: str) -> list[tuple[str, float]]:
        return list(price.get(symbol, []))

    def record_fn(**row: Any) -> tuple[str, bool]:
        recorded.append(row)
        return f"disc_{len(recorded)}", True

    ctx = M.Ctx(series_fn=series_fn, bars_fn=bars_fn, record_fn=record_fn, **kw)
    ctx.captured = recorded          # type: ignore[attr-defined]
    return ctx


# ------------------------------------------------------------------------------ the screen
def test_the_screen_recovers_a_planted_conditional_effect() -> None:
    """The claim, its control and the separation verdict, all published together."""
    got = M.conditional_lead_lag(PLANT["lead"], PLANT["target"], PLANT["cond"], horizon=1)
    assert got["verdict"] == "SCREENED", got
    assert got["n"] >= M.MIN_OBS
    assert abs(got["ic"]) >= M.MIN_ABS_IC
    assert got["p_permutation"] <= M.PERM_P_MAX
    assert "permutation" in got["null"]

    assert got["conditional"]["verdict"] == "SCREENED", got["conditional"]
    assert got["control"]["verdict"] == "NOT_SEPARATED", got["control"]
    assert got["separates"] is True
    assert abs(got["conditional"]["ic"]) > abs(got["control"]["ic"])


def test_an_effect_present_in_both_halves_does_not_separate() -> None:
    """A conditional CLAIM that is equally true in the control half has been refuted."""
    got = M.conditional_lead_lag(PLANT["lead"], PLANT["target"],
                                 [(d, 1.0) for d, _ in PLANT["cond"]], horizon=1)
    # A CONSTANT STATE CANNOT SPLIT A SAMPLE. Every observation lands in the claim half and the
    # control half is empty, so the control comes back UNMEASURED -- and an unmeasured control is
    # never evidence that the effect is absent there. The screen must refuse to call that a
    # separation and must name the degeneracy (L1.28a).
    assert got["verdict"] == "SCREENED"
    assert got["conditional"]["verdict"] == "SCREENED"
    assert got["control"]["verdict"] == "UNMEASURED"
    assert got["separates"] is False
    assert "DEGENERATE SPLIT" in got["conditioning"]


def test_pure_noise_is_not_separated_rather_than_screened() -> None:
    """The null has to be able to fail. A shuffled target must not screen."""
    import numpy as np
    rng = np.random.default_rng(7)
    days = [d for d, _ in PLANT["target"]]
    walk, price = [], 50.0
    for step in rng.normal(0.0, 0.004, len(days)):
        price *= float(np.exp(step))
        walk.append(price)
    got = M.conditional_lead_lag(PLANT["lead"], list(zip(days, walk, strict=True)), horizon=1)
    assert got["verdict"] == "NOT_SEPARATED", got
    assert got["p_permutation"] > M.PERM_P_MAX or abs(got["ic"]) < M.MIN_ABS_IC


def test_too_few_observations_is_unmeasured_and_never_no_effect() -> None:
    """A screen that never ran is not a screen that found nothing (L1.28a)."""
    short = M.conditional_lead_lag(PLANT["lead"][:40], PLANT["target"][:40], horizon=1)
    assert short["verdict"] == "UNMEASURED"
    assert short["n"] < M.MIN_OBS and "UNMEASURED" not in str(short.get("ic", ""))
    assert "< 120" in short["why"] or "min_obs" in short

    empty = M.conditional_lead_lag([], PLANT["target"], horizon=1)
    assert empty["verdict"] == "UNMEASURED" and empty["n"] == 0


def test_the_join_is_point_in_time() -> None:
    """The lead joins at its AVAILABLE time; a value published later must not appear earlier."""
    lead = [("2026-01-10", 1.0), ("2026-02-10", 2.0)]
    target = [("2026-01-05", 10.0), ("2026-01-15", 11.0), ("2026-02-15", 12.0)]
    joined = M.as_of_join(lead, target)
    assert joined == [("2026-01-15", 1.0, 11.0), ("2026-02-15", 2.0, 12.0)]
    assert all(row[0] >= "2026-01-10" for row in joined), "a pre-publication row leaked in"


def test_rank_ic_is_rank_based_and_outlier_resistant() -> None:
    """One outlier must not manufacture a correlation."""
    assert M.rank_ic([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)
    assert M.rank_ic([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert M.rank_ic([1, 1, 1, 1], [1, 2, 3, 4]) == pytest.approx(0.0)
    assert M.rank_ic([], []) == 0.0


# ------------------------------------------------------------------------------ the families
def test_every_family_targets_only_instruments_the_box_can_trade() -> None:
    """The universe is the broker's, and no single name is ever a target (two-lane order)."""
    assert universe_symbols(), "the broker registry is unreadable -- nothing here is checked"
    for fam in M.ALL_FAMILIES:
        split = resolve(fam.targets)
        assert split["absent"] == [], f"{fam.fid}: {split['absent']} is not in the registry"
        assert split["equities"] == [], f"{fam.fid}: {split['equities']} is a single-name equity"
        assert fam.control and fam.falsifier, f"{fam.fid}: a family with no control is a story"
        assert fam.mechanism and fam.mechanism_families


def test_the_six_families_and_two_triples_are_all_present() -> None:
    """The principal's list, by name, so a silent deletion fails here."""
    assert {f.fid for f in M.FAMILIES} == {
        "oil_liquidity_state", "domestic_demand_nowcast", "petrodollar_liquidity",
        "usd_liquidity_regional_funding", "trade_shipping", "il_rates_ils_tech"}
    assert {f.fid for f in M.CROSS_REGION} == {
        "saudi_liquidity_x_oil_x_brazil", "gulf_risk_x_jpy_funding_x_us_vol"}
    assert all(f.cross_region for f in M.CROSS_REGION)
    assert not any(f.cross_region for f in M.FAMILIES)


def test_the_cross_region_legs_name_their_neighbours() -> None:
    """Brazil is read when a `br` lane exists and Suez when an Egypt pack does; both by NAME."""
    triple = next(f for f in M.CROSS_REGION if f.fid == "saudi_liquidity_x_oil_x_brazil")
    br = [leg for leg in triple.legs() if leg.country == "br"]
    assert br and br[0].optional, "the Brazilian leg must degrade the screen, not kill the family"
    shipping = next(f for f in M.FAMILIES if f.fid == "trade_shipping")
    eg = [leg for leg in shipping.legs() if leg.country == "eg"]
    assert eg and eg[0].optional
    assert "Africa" in eg[0].what and "Egypt" in eg[0].what
    assert "br" in {leg.country for leg in triple.legs()}


def test_a_family_records_one_discovery_with_its_generator() -> None:
    """One DiscoveryObject per family, stamped `mena:<family>`, carrying its screens."""
    ctx = _ctx(series={"lead": PLANT["lead"], "cond": PLANT["cond"]},
               bars={"XAUUSD": PLANT["target"]}, dry_run=False)
    row = M.run_family(ctx, PLANTED_FAMILY)

    assert row["verdict"] == "SCREENED"
    assert len(row["screens"]) == 1 and row["screens"][0]["target"] == "XAUUSD"
    assert row["missing"] == []
    assert row["discovery_id"] == "disc_1"

    recorded = ctx.captured           # type: ignore[attr-defined]
    assert len(recorded) == 1
    got = recorded[0]
    assert got["generator"] == "mena:planted_conditional"
    assert got["source_id"] == "mena:planted_conditional"
    assert got["source_type"] == "mena_interaction"
    assert got["assets"] == ["XAUUSD"]
    assert got["falsifier"] and got["economic_rationale"]
    assert got["payload"]["region"] == "middle_east"
    assert got["payload"]["verdict"] == "SCREENED"
    assert got["payload"]["screens"][0]["separates"] is True
    assert got["required_data"] == ["sa:test:lead", "sa:test:cond"]
    assert "AVAILABLE time" in " ".join(got["pit_requirements"])


def test_a_missing_lead_is_unmeasured_by_name_and_still_records_the_question() -> None:
    """The backlog of blocked families IS the acquisition plan, so the question is kept."""
    ctx = _ctx(series={}, bars={"XAUUSD": PLANT["target"]}, dry_run=False)
    row = M.run_family(ctx, PLANTED_FAMILY)

    assert row["verdict"] == "UNMEASURED"
    assert row["screens"] == []
    assert "sa:test:lead" in row["missing"]
    assert ctx.unmeasured, "an absent leg produced no UNMEASURED row"
    named = {u["leg"] for u in ctx.unmeasured}
    assert {"sa:test:lead", "sa:test:cond"} <= named
    assert all("UNMEASURED" in u["why"] or "not stored" in u["why"] for u in ctx.unmeasured)
    recorded = ctx.captured           # type: ignore[attr-defined]
    assert len(recorded) == 1, "the question was dropped instead of being recorded as blocked"
    assert recorded[0]["payload"]["missing"] == ["sa:test:lead", "sa:test:cond"]


def test_a_missing_target_is_unmeasured_and_never_flat() -> None:
    """No bars for a symbol is UNMEASURED, not a flat price."""
    ctx = _ctx(series={"lead": PLANT["lead"], "cond": PLANT["cond"]}, bars={}, dry_run=False)
    row = M.run_family(ctx, PLANTED_FAMILY)
    assert row["verdict"] == "UNMEASURED"
    assert "bars:XAUUSD" in row["missing"]
    assert any("not flat" in u["why"] for u in ctx.unmeasured)


def test_an_optional_leg_degrades_the_screen_without_killing_the_family() -> None:
    """An optional neighbour that has not landed is named and the family still runs."""
    fam = M.Family(fid="optional_probe", title="an optional leg", country="sa",
                   lead=PLANTED_FAMILY.lead, targets=("XAUUSD",), horizon=1,
                   mechanism="m", control="c", falsifier="f",
                   extra_legs=(M.Leg(kind="series", what="a neighbour that has not landed",
                                     country="br", lane="bcb", series="commodity_index",
                                     optional=True),))
    ctx = _ctx(series={"lead": PLANT["lead"]}, bars={"XAUUSD": PLANT["target"]}, dry_run=False)
    row = M.run_family(ctx, fam)
    assert row["verdict"] in ("SCREENED", "NOT_SEPARATED")
    assert row["screens"], "an optional leg killed the family"
    assert "br:bcb:commodity_index" in row["missing"]


# ------------------------------------------------------------------------------ the whole pass
def test_a_dry_run_writes_nothing_and_records_nothing(tmp_path: Path) -> None:
    """`--dry-run` measures, prints and persists NOTHING."""
    report = tmp_path / "MIDDLE_EAST_INTERACTION.json"
    ctx = _ctx(series={}, bars={}, dry_run=True)
    doc = M.run(ctx=ctx, report_path=report)

    assert not report.exists()
    assert doc["dry_run"] is True
    assert ctx.captured == []                      # type: ignore[attr-defined]
    assert doc["discoveries_recorded"] == len(M.ALL_FAMILIES)
    assert all(r["discovery_id"] == "" for r in doc["families"] + doc["cross_region"])


def test_a_wet_run_writes_the_report_the_principal_asked_for(tmp_path: Path) -> None:
    """{at, families, discoveries_recorded, cross_region, screens, unmeasured, rule}."""
    report = tmp_path / "MIDDLE_EAST_INTERACTION.json"
    ctx = _ctx(series={"money_supply_weekly_sar": PLANT["lead"]},
               bars={"XBRUSD": PLANT["target"], "XTIUSD": PLANT["target"]}, dry_run=False)
    doc = M.run(ctx=ctx, report_path=report)

    assert doc["dry_run"] is False
    assert report.exists()
    written = json.loads(report.read_text(encoding="utf-8"))
    for field in ("at", "families", "discoveries_recorded", "cross_region", "screens",
                  "unmeasured", "rule"):
        assert field in written, f"the report is missing {field}"
    assert written["rule"] == M.RULE
    assert len(written["families"]) == len(M.FAMILIES)
    assert len(written["cross_region"]) == len(M.CROSS_REGION)
    assert written["discoveries_recorded"] == len(M.ALL_FAMILIES)
    assert written["counts"]["unmeasured_legs"] > 0, "every leg resolved, so nothing was named"

    oil = next(r for r in written["families"] if r["family"] == "oil_liquidity_state")
    assert oil["screens"], "the family whose lead WAS planted did not screen"
    assert {s["target"] for s in oil["screens"]} == {"XBRUSD", "XTIUSD"}


def test_a_family_filter_runs_only_what_it_names() -> None:
    """`--family` narrows the pass; an unknown name simply selects nothing."""
    doc = M.run(ctx=_ctx(dry_run=True), families=["trade_shipping"])
    assert len(doc["families"]) == 1 and doc["cross_region"] == []
    assert doc["families"][0]["family"] == "trade_shipping"


def test_the_cli_runs_dry_without_touching_the_desk(capsys: Any) -> None:
    """The entry point the scheduler calls, exercised end to end on this box's own data."""
    assert M.main(["--dry-run", "--budget-s", "60", "--family", "il_rates_ils_tech"]) == 0
    out = capsys.readouterr().out
    assert "il_rates_ils_tech" in out
    assert "dry run" in out

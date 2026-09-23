"""THE THREE MIDDLE EAST LANES -- SAMA, CBUAE with Fujairah, and the Bank of Israel's SDMX.

NOTHING HERE TOUCHES THE NETWORK. Every lane runs in `no_fetch` mode, which makes the one network
door a FIXTURE READER: the parse path exercised by these tests is byte-for-byte the live one, and
`Guard.calls` is asserted to be zero so a future edit that reaches for a socket fails here rather
than on a box with no egress. Every path is redirected into `tmp_path` -- axes, fixtures and
report -- so a test run cannot write into the desk's own axis store.

WHAT THESE TESTS REFUSE TO LET THROUGH:

  * A LANE THAT REPORTS A BARREN GROUND WHEN IT HAS NO KEY. An absent key makes a lane UNMEASURED
    BY NAME, with the key path in the row and a discovery recorded that names it (L1.28a). A lane
    that returns an empty frame instead is indistinguishable from a ground with nothing on it.
  * A KEY IN A REPORT. The secret value is planted as a recognisable token and asserted absent
    from every row, note and serialised report the lane produces.
  * AN OVERWRITTEN VINTAGE. A flash and its final are TWO observations of one period. The store is
    append-only and `as_of` answers what was knowable at an instant, not what is true now -- which
    is the only property that makes any of this tradable.
  * AN SDMX PAYLOAD READ AS A FLAT TABLE. SDMX-JSON separates structure from data and addresses
    observations by index; a reader that expects `[{"date":..., "value":...}]` gets nothing and
    calls the ground barren. The parser is tested on both envelope shapes.
  * A STATE VERDICT WITHOUT ITS CONTROL. `funding_state` must not say STRESS on a rate leg alone:
    a Gulf funding widening that deposit growth explains is a credit cycle. Both branches are
    pinned here, because that distinction is the whole reason the UAE lane exists.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from countries.ae import data_plane as AE  # noqa: E402
from countries.il import data_plane as IL  # noqa: E402
from countries.sa import data_plane as SA  # noqa: E402

SECRET = "not-a-real-key-0000"  # noqa: S105 -- a planted token, asserted ABSENT


# ------------------------------------------------------------------------------ helpers
def _fixture(root: Path, lane: str, dataset_id: str, payload: Any) -> Path:
    path = root / lane / f"{dataset_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _weeks(n: int, *, end: date = date(2026, 9, 12)) -> list[date]:
    """`n` weekly period ends, oldest first, finishing before today so they are knowable."""
    return [end - timedelta(weeks=(n - 1 - i)) for i in range(n)]


def _lane(cls: Any, tmp_path: Path, keys: dict[str, str] | None = None, **kw: Any) -> Any:
    return cls(desk=tmp_path, axes=tmp_path / "axes", fixtures=tmp_path / "fx", no_fetch=True,
               dry_run=False, keys=keys if keys is not None else {}, **kw)


ALL_LANES = (SA.SamaLane, AE.CbuaeLane, AE.FujairahLane, IL.BoiLane)


# ------------------------------------------------------------------------------ the catalogue
@pytest.mark.parametrize("cls", ALL_LANES, ids=lambda c: c.LANE)
def test_catalogue_is_a_catalogue(cls: Any, tmp_path: Path) -> None:
    """Every row owes every field, a licence, an access class and a point-in-time verdict."""
    lane = _lane(cls, tmp_path)
    rows = lane.catalogue()
    assert rows, f"{cls.LANE}: an empty catalogue is not a lane"
    assert SA.check_catalogue(rows) == []
    for row in rows:
        got = row.as_dict()
        for field in ("dataset_id", "institution", "coverage", "frequency", "revisions",
                      "licence", "history_from", "how_to_fetch"):
            assert str(got[field]).strip(), f"{cls.LANE}/{got['dataset_id']}: {field} is empty"
        assert got["pit_feasible"] in (SA.PIT_SAFE, SA.NOT_PIT_SAFE, SA.UNMEASURED)
        assert got["access"] in (SA.PUBLIC, SA.LICENSED)
        assert float(got["publication_lag_days"]) >= 0.0
        assert got["verified"] is False, (
            f"{cls.LANE}/{got['dataset_id']}: an endpoint that has never returned bytes on this "
            f"box must stay verified=False -- declared, not asserted")


@pytest.mark.parametrize("cls", ALL_LANES, ids=lambda c: c.LANE)
def test_key_requirements_are_declared_and_nameable(cls: Any, tmp_path: Path) -> None:
    """A row that needs a key must name WHICH key, and it must be one the secrets file holds."""
    for row in _lane(cls, tmp_path).catalogue():
        if row.key_required:
            assert row.key_name in SA.KEY_NAMES
        if row.access == SA.LICENSED:
            assert row.series == (), "a licensed product may not declare stored series"
            assert not row.url, "a licensed product may not carry a fetchable url"


def test_the_israeli_lane_needs_no_key_and_says_so(tmp_path: Path) -> None:
    """The Bank of Israel publishes a documented SDMX API with no key. That is a FACT, not a gap."""
    lane = _lane(IL.BoiLane, tmp_path)
    assert IL.BoiLane.KEY == ""
    assert lane.key_present() is True
    assert all(not row.key_required for row in lane.catalogue())


def test_key_status_reports_verdicts_and_never_values(tmp_path: Path) -> None:
    """`key_status` answers PRESENT/ABSENT. The value never leaves `read_keys`."""
    secrets = tmp_path / "mena_apis.json"
    secrets.write_text(json.dumps({"sama": SECRET, "boi": ""}), encoding="utf-8")
    status = SA.key_status(secrets)
    assert status == {"sama": "PRESENT", "cbuae": "ABSENT", "boi": "ABSENT"}
    assert SECRET not in json.dumps(status)
    assert SA.read_keys(tmp_path / "does-not-exist.json") == {}


# ------------------------------------------------------------------------------ UNMEASURED
@pytest.mark.parametrize("cls,key_name", [(SA.SamaLane, "sama"), (AE.CbuaeLane, "cbuae")],
                         ids=["sama", "cbuae"])
def test_a_lane_without_its_key_is_unmeasured_by_name(cls: Any, key_name: str,
                                                      tmp_path: Path) -> None:
    """Not an empty series, not a barren ground: UNMEASURED, with the key path named (L1.28a)."""
    lane = _lane(cls, tmp_path, keys={})
    res = lane.fetch(budget_s=5.0)
    assert res.key_present is False
    assert res.stored == 0 and res.rows == []
    assert "UNMEASURED" in res.why
    assert res.unmeasured, "a keyless lane that names nothing has reported a clean zero"
    named = {row["dataset"] for row in res.unmeasured if "dataset" in row}
    assert named, "no dataset was named in the UNMEASURED rows"
    for row in res.unmeasured:
        if row.get("key_name"):
            assert row["key_name"] == key_name
            assert "mena_apis.json" in row["key_path"]
    # the question is still recorded, because the backlog of blocked datasets IS the acquisition
    # plan -- a lane that goes quiet when a key is missing produces no plan at all
    assert lane.recorded, "a keyless lane recorded no discovery, so nothing asks for the key"
    assert all(r["generator"].startswith("mena:data_plane") for r in lane.recorded)


def test_no_key_value_ever_reaches_a_row_a_note_or_a_report(tmp_path: Path) -> None:
    """The one rule with no exceptions: `data/secrets/**` never leaves the box."""
    lane = _lane(SA.SamaLane, tmp_path, keys={"sama": SECRET})
    res = lane.fetch(budget_s=5.0)
    blob = json.dumps({"row": res.row(), "recorded": lane.recorded}, ensure_ascii=False,
                      default=str)
    assert SECRET not in blob
    assert SA.redact(f"https://x/api?apikey={SECRET}&b=1", [SECRET]) == \
        "https://x/api?apikey=***&b=1"
    assert SECRET not in SA.redact(f"ConnectionError: {SECRET} refused", [SECRET])


def test_a_missing_fixture_is_unmeasured_and_never_barren(tmp_path: Path) -> None:
    """The lane has its key and the ground answers nothing: still UNMEASURED, still named."""
    lane = _lane(SA.SamaLane, tmp_path, keys={"sama": SECRET})
    res = lane.fetch(budget_s=5.0)
    assert res.key_present is True
    assert res.fetched == 0
    whys = " ".join(str(row.get("why")) for row in res.unmeasured)
    assert "no fixture" in whys
    licensed = [row for row in res.unmeasured if row.get("licence")]
    assert licensed, "the licensed row must be reported as deliberately not fetched"
    assert "licensed" in str(licensed[0]["why"]).lower()


def test_no_lane_opens_a_socket_in_no_fetch_mode(tmp_path: Path) -> None:
    """`no_fetch` makes the one network door a fixture reader, and nothing else may open one."""
    guard = SA.Guard(no_fetch=True, fixtures=tmp_path / "fx")
    payload, why = guard.get("https://example.invalid/x", lane="sama", dataset_id="nope")
    assert payload is None and "no fixture" in why
    assert guard.calls == 0
    _fixture(tmp_path / "fx", "sama", "yes", [{"date": "2026-01-31", "value": 1.0}])
    payload, why = guard.get("https://example.invalid/x", lane="sama", dataset_id="yes")
    assert payload == [{"date": "2026-01-31", "value": 1.0}]
    assert guard.calls == 0


# ------------------------------------------------------------------------------ the PIT store
def test_the_store_appends_vintages_and_never_overwrites(tmp_path: Path) -> None:
    """A flash and its final are TWO observations of one period, and both survive."""
    axes = tmp_path / "axes"
    period = date(2026, 6, 30)
    flash = SA.observe("m3_sar", 100.0, period, lag_days=25.0, vintage="provisional",
                       source_id="sama:m3_sar")
    doc = SA.store_series(axes, "sa", "sama", "m3_sar", [flash])
    assert doc["n"] == 1 and doc["n_periods"] == 1 and doc["n_vintages"] == 0

    final = SA.Observation(series="m3_sar", value=104.0, period_time=flash.period_time,
                           publication_time=flash.publication_time,
                           available_time="2026-08-15T00:00:00+00:00", vintage="final",
                           vintage_id="v2", source_id="sama:m3_sar")
    doc = SA.store_series(axes, "sa", "sama", "m3_sar", [final])
    assert doc["n"] == 2, "the revision overwrote the flash instead of appending to it"
    assert doc["n_periods"] == 1 and doc["n_vintages"] == 1
    assert doc["points"][-1]["revision_n"] == 1
    assert set(SA.OBS_FIELDS) <= set(doc["points"][0])

    # idempotent: the same pass twice adds nothing
    again = SA.store_series(axes, "sa", "sama", "m3_sar", [flash, final])
    assert again["added"] == 0 and again["n"] == 2

    # THE PIT READER: what the desk knew, at the instant it knew it
    assert SA.as_of(axes, "sa", "sama", "m3_sar", "2026-07-01") == {}
    assert SA.as_of(axes, "sa", "sama", "m3_sar", "2026-08-01") == \
        {flash.period_time: 100.0}
    assert SA.as_of(axes, "sa", "sama", "m3_sar", "2026-09-01") == \
        {flash.period_time: 104.0}
    pit = SA.read_series(axes, "sa", "sama", "m3_sar")
    assert [v for _, v in pit] == [100.0, 104.0]
    assert pit == sorted(pit), "the PIT reader must return learning order, not period order"


def test_observe_stamps_the_available_time_from_the_publication_lag() -> None:
    """A weekly figure describing a week is knowable three days later, not on the week's end."""
    obs = SA.observe("pos_value_sar", 42.0, date(2026, 6, 6), lag_days=3.0, vintage="final",
                     source_id="sama:pos")
    assert obs.period_time.startswith("2026-06-06")
    assert obs.available_time.startswith("2026-06-09")
    assert obs.point()["knowable_at"] == "2026-06-09"
    assert obs.vintage_id


# ------------------------------------------------------------------------------ SAMA weekly POS
def _pos_fixture(tmp_path: Path, n: int = 60, *, ramp: float = 1.0) -> None:
    rows = [{"week_end": d.isoformat(),
             "pos_value_sar": 1_000.0 + ramp * i,
             "pos_transactions": 50_000 + 10 * i,
             "pos_terminals": 900_000}
            for i, d in enumerate(_weeks(n))]
    _fixture(tmp_path / "fx", "sama", "sama_pos_weekly", {"data": rows})


def test_the_weekly_pos_print_becomes_a_demand_state(tmp_path: Path) -> None:
    """The Gulf's only weekly official demand series, parsed, stored and read point-in-time."""
    _pos_fixture(tmp_path, 60, ramp=5.0)
    lane = _lane(SA.SamaLane, tmp_path, keys={"sama": SECRET})
    res = lane.fetch(budget_s=10.0)

    assert res.fetched == 1
    assert {"pos_value_sar", "pos_transactions", "pos_terminals"} <= set(res.series_written)
    assert len([o for o in res.rows if o.series == "pos_value_sar"]) == 60

    stored = lane.series("pos_value_sar")
    assert len(stored) == 60
    assert stored == sorted(stored)

    state = lane.demand_state()
    assert state["state"] == "EXPANSION", state
    assert state["n"] == 60
    assert state["z"] > 0.5
    assert state["label"] == "domestic_demand"
    assert state["control"], "a state with no control is a number, not a measurement"


def test_a_weekly_money_print_becomes_a_liquidity_state(tmp_path: Path) -> None:
    """The same machinery on the weekly money aggregate: the high-frequency liquidity read."""
    rows = [{"week_end": d.isoformat(), "money_supply_weekly_sar": 2_000.0 - 3.0 * i,
             "bank_deposits_weekly_sar": 1_500.0}
            for i, d in enumerate(_weeks(40))]
    _fixture(tmp_path / "fx", "sama", "sama_money_weekly", rows)
    lane = _lane(SA.SamaLane, tmp_path, keys={"sama": SECRET})
    lane.fetch(budget_s=10.0)
    state = lane.liquidity_state()
    assert state["state"] == "CONTRACTION", state
    assert state["z"] < -0.5 and state["n"] == 40
    # the provisional vintage is carried through from the catalogue's own declaration
    assert any(o.vintage == "provisional" for o in lane.fetch(budget_s=10.0).rows)


def test_a_short_series_is_unmeasured_rather_than_neutral(tmp_path: Path) -> None:
    """Four weekly points cannot say EXPANSION or NEUTRAL. They say UNMEASURED (L1.28a)."""
    _pos_fixture(tmp_path, 4)
    lane = _lane(SA.SamaLane, tmp_path, keys={"sama": SECRET})
    lane.fetch(budget_s=10.0)
    state = lane.demand_state()
    assert state["state"] == SA.UNMEASURED
    assert state["n"] == 4
    assert "UNMEASURED" in state["why"]


def test_arabic_indic_digits_and_separators_parse(tmp_path: Path) -> None:
    """A Gulf platform may answer with Arabic-Indic digits and thousands separators."""
    assert SA.row_value({"value": "١٢٣٤"}) == pytest.approx(1234.0)
    assert SA.row_value({"value": "1,234.5"}) == pytest.approx(1234.5)
    assert SA.row_value({"value": "12\u00a0345"}) == pytest.approx(12345.0)
    assert SA.row_value({"value": ".."}) is None
    assert SA.row_date({"week_end": "2026-06-06"}) == date(2026, 6, 6)
    assert SA.row_date({"period": "2026-06"}) == date(2026, 6, 30)
    assert SA.row_date({"period": "2026Q2"}) is None      # not a shape this lane claims to read
    assert SA.row_date({"date": "nonsense"}) is None


def test_the_payload_wrapper_does_not_have_to_be_guessed(tmp_path: Path) -> None:
    """`data`, `records`, `items`, a bare list -- the wrapper changes between releases."""
    rows = [{"a": 1}]
    for payload in (rows, {"data": rows}, {"records": rows}, {"items": rows},
                    {"result": {"records": rows}}):
        assert SA.rows_of(payload) == rows
    assert SA.rows_of({"nothing": "recognisable"}) == []
    assert SA.rows_of("a string") == []


# ------------------------------------------------------------------------------ CBUAE
def _cbuae_fixtures(tmp_path: Path, *, deposits_rising: bool) -> None:
    days = [date(2026, 9, 12) - timedelta(days=(39 - i)) for i in range(40)]
    rates = [{"date": d.isoformat(), "eibor_3m": 4.0 + (0.9 if i >= 36 else 0.0),
              "eibor_1m": 3.9, "base_rate": 4.15}
             for i, d in enumerate(days)]
    _fixture(tmp_path / "fx", "cbuae", "cbuae_daily_liquidity", rates)
    step = 20.0 if deposits_rising else -20.0
    months = [{"period": f"2026-{m:02d}", "bank_deposits_aed": 2_000.0 + step * m,
               "loan_to_deposit": 85.0, "m3_aed": 1_800.0 + 5.0 * m}
              for m in range(1, 9)]
    _fixture(tmp_path / "fx", "cbuae", "cbuae_banking_indicators", months)
    _fixture(tmp_path / "fx", "cbuae", "cbuae_monetary_aggregates", months)


def test_a_funding_widening_with_deposit_growth_is_a_drain_not_stress(tmp_path: Path) -> None:
    """THE control this lane exists for. The 2022-2023 Gulf widenings were a credit cycle."""
    _cbuae_fixtures(tmp_path, deposits_rising=True)
    lane = _lane(AE.CbuaeLane, tmp_path, keys={"cbuae": SECRET})
    res = lane.fetch(budget_s=10.0)
    assert res.fetched >= 2
    state = lane.funding_state()
    assert state["state"] == "DRAIN", state
    assert state["z"] > 0.5 and state["deposit_growth"] > 0
    assert "credit" in state["why"]


def test_a_funding_widening_without_deposit_growth_is_stress(tmp_path: Path) -> None:
    """Same rate leg, opposite control leg, opposite verdict. That is what a control is for."""
    _cbuae_fixtures(tmp_path, deposits_rising=False)
    lane = _lane(AE.CbuaeLane, tmp_path, keys={"cbuae": SECRET})
    lane.fetch(budget_s=10.0)
    state = lane.funding_state()
    assert state["state"] == "STRESS", state
    assert state["deposit_growth"] < 0


def test_a_rate_leg_without_its_control_is_unmeasured_not_stress(tmp_path: Path) -> None:
    """The refusal that matters: no deposit series means no verdict, not a convenient one."""
    days = [date(2026, 9, 12) - timedelta(days=(39 - i)) for i in range(40)]
    _fixture(tmp_path / "fx", "cbuae", "cbuae_daily_liquidity",
             [{"date": d.isoformat(), "eibor_3m": 4.0 + (0.9 if i >= 36 else 0.0)}
              for i, d in enumerate(days)])
    lane = _lane(AE.CbuaeLane, tmp_path, keys={"cbuae": SECRET})
    lane.fetch(budget_s=10.0)
    state = lane.funding_state()
    assert state["state"] == SA.UNMEASURED
    assert state["n_control"] == 0
    assert "control" in state["why"] and "UNMEASURED" in state["why"]


def test_the_fujairah_lane_needs_no_key_and_reads_a_weekly_physical_series(
        tmp_path: Path) -> None:
    """The region's best public high-frequency PHYSICAL series, and the only keyless Gulf ground."""
    rows = [{"week_end": d.isoformat(), "fujairah_middle_distillates": 2_000.0 + 40.0 * i,
             "fujairah_light_distillates": 6_000.0, "fujairah_heavy_residues": 9_000.0,
             "fujairah_total_stocks": 17_000.0}
            for i, d in enumerate(_weeks(30))]
    _fixture(tmp_path / "fx", "fujairah", "fujairah_oil_stocks_weekly", rows)
    lane = _lane(AE.FujairahLane, tmp_path, keys={})
    res = lane.fetch(budget_s=10.0)
    assert res.key_present is True, "this ground needs no key and must not report as blocked"
    assert res.fetched == 1 and res.stored == 4
    state = lane.inventory_state()
    assert state["state"] == "BUILD", state
    assert state["n"] == 30 and state["change_4w"] > 0
    assert "Hormuz" in AE.FujairahLane.__doc__ or "chokepoint" in AE.FujairahLane.__doc__


# ------------------------------------------------------------------------------ SDMX
SDMX_10 = {
    "data": {
        "structure": {"dimensions": {
            "series": [{"id": "SERIES_CODE",
                        "values": [{"id": "ILS_USD"}, {"id": "ILS_EUR"}]}],
            "observation": [{"id": "TIME_PERIOD",
                             "values": [{"id": "2026-01-01"}, {"id": "2026-01-02"}]}]}},
        "dataSets": [{"series": {"0": {"observations": {"0": [3.71], "1": [3.68]}},
                                 "1": {"observations": {"0": [4.02]}}}}],
    }
}

SDMX_20 = {
    "data": {
        "structures": [{"dimensions": {
            "series": [{"id": "SERIES_CODE", "values": [{"id": "BOI_RATE"}]}],
            "observation": [{"id": "TIME_PERIOD", "values": [{"id": "2026-01"},
                                                             {"id": "2026-02"}]}]}}],
        "dataSets": [{"series": {"0": {"observations": {"0": [4.5], "1": [4.25]}}}}],
    }
}


def test_sdmx_json_is_parsed_from_both_envelopes() -> None:
    """1.0 puts the structure at `data.structure`; 2.0 moved it to `data.structures[0]`."""
    rows = IL.parse_sdmx_json(SDMX_10)
    assert len(rows) == 3
    assert rows[0] == {"key": {"SERIES_CODE": "ILS_USD"}, "period": "2026-01-01", "value": 3.71}
    assert {r["key"]["SERIES_CODE"] for r in rows} == {"ILS_USD", "ILS_EUR"}

    rows20 = IL.parse_sdmx_json(SDMX_20)
    assert [r["value"] for r in rows20] == [4.5, 4.25]
    assert rows20[0]["key"] == {"SERIES_CODE": "BOI_RATE"}


def test_an_unrecognised_envelope_is_empty_and_the_lane_calls_it_shape_not_barren(
        tmp_path: Path) -> None:
    """A parser that cannot read a payload must not report the ground as having nothing on it."""
    assert IL.parse_sdmx_json({"nothing": "recognisable"}) == []
    assert IL.parse_sdmx_json("a string") == []
    assert IL.parse_sdmx_json({"data": {"dataSets": []}}) == []

    _fixture(tmp_path / "fx", "boi", "boi_exchange_rates", {"data": {"dataSets": [{}]}})
    lane = _lane(IL.BoiLane, tmp_path, keys={})
    res = lane.fetch(budget_s=10.0)
    whys = " ".join(str(row.get("why")) for row in res.unmeasured)
    assert "shape unrecognised, not barren" in whys


def test_sdmx_time_periods_resolve_to_the_last_day_they_describe() -> None:
    """A monthly observation describes a month; joining it to the first is a look-ahead."""
    assert IL.sdmx_period_end("2026-01-31") == date(2026, 1, 31)
    assert IL.sdmx_period_end("2026-02") == date(2026, 2, 28)
    assert IL.sdmx_period_end("2026-Q1") == date(2026, 3, 31)
    assert IL.sdmx_period_end("2026") == date(2026, 12, 31)
    assert IL.sdmx_period_end("later") is None


def test_the_boi_lane_stores_sdmx_series_with_their_keys(tmp_path: Path) -> None:
    """End to end through the fixture door: SDMX in, stamped vintages out."""
    _fixture(tmp_path / "fx", "boi", "boi_exchange_rates", SDMX_10)
    _fixture(tmp_path / "fx", "boi", "boi_interest_rates", SDMX_20)
    lane = _lane(IL.BoiLane, tmp_path, keys={})
    res = lane.fetch(budget_s=10.0)

    assert res.key_present is True
    assert "usdils_representative" in res.series_written
    assert "eurils_representative" in res.series_written
    assert "boi_policy_rate" in res.series_written
    assert [v for _, v in lane.series("usdils_representative")] == [3.71, 3.68]
    assert lane.as_of("boi_policy_rate", "2026-12-31") == {
        "2026-01-31T00:00:00+00:00": 4.5, "2026-02-28T00:00:00+00:00": 4.25}
    keyed = [o for o in res.rows if o.series == "usdils_representative"]
    assert keyed and keyed[0].meta["sdmx_key"] == {"SERIES_CODE": "ILS_USD"}


def test_an_unmatched_sdmx_key_is_skipped_rather_than_attributed(tmp_path: Path) -> None:
    """With two declared series an unknown key is DROPPED: a wrong attribution is worse than a
    missing point. With one declared series there is nothing to guess between."""
    lane = _lane(IL.BoiLane, tmp_path, keys={})
    rows = {row.dataset_id: row for row in lane.catalogue()}
    assert lane.series_name({"SERIES_CODE": "MYSTERY"}, rows["boi_exchange_rates"]) is None
    assert lane.series_name({"SERIES_CODE": "MYSTERY"}, rows["boi_reserves"]) == "fx_reserves_usd"
    assert lane.series_name({"CURRENCY": "USD"}, rows["boi_exchange_rates"]) == \
        "usdils_representative"


def test_the_israeli_hedge_gain_refuses_to_report_on_one_leg(tmp_path: Path) -> None:
    """The channel's GAIN needs the pool AND the ratio. One leg is UNMEASURED, never a gain of 1."""
    lane = _lane(IL.BoiLane, tmp_path, keys={})
    state = lane.hedge_gain_state()
    assert state["state"] == SA.UNMEASURED
    assert set(state["missing"]) == {"institutional_hedge_ratio",
                                     "institutional_foreign_assets_ils"}
    assert "conditionable" in state["why"]

    axes = tmp_path / "axes"
    for i, period in enumerate(_weeks(14)):
        SA.store_series(axes, "il", "boi", "institutional_hedge_ratio",
                        [SA.observe("institutional_hedge_ratio", 40.0 + i, period, lag_days=1.0,
                                    vintage="final", source_id="boi:r")])
        SA.store_series(axes, "il", "boi", "institutional_foreign_assets_ils",
                        [SA.observe("institutional_foreign_assets_ils", 1_000.0, period,
                                    lag_days=1.0, vintage="final", source_id="boi:p")])
    state = lane.hedge_gain_state()
    assert state["state"] == "HIGH", state
    assert state["gain"] == pytest.approx(1_000.0 * (40.0 + 13) / 100.0)


# ------------------------------------------------------------------------------ the whole pass
def test_a_dry_run_writes_nothing_anywhere(tmp_path: Path) -> None:
    """A dry run measures and persists nothing: no axis file, no report, no discovery."""
    _pos_fixture(tmp_path, 20)
    report = tmp_path / "REPORT.json"
    doc = SA.run(desk=tmp_path, axes=tmp_path / "axes", fixtures=tmp_path / "fx",
                 keys={"sama": SECRET}, no_fetch=True, dry_run=True, report_path=report,
                 budget_s=10.0)
    assert not report.exists()
    assert not (tmp_path / "axes").exists()
    assert doc["dry_run"] is True
    assert doc["catalogue_problems"] == []
    assert doc["lanes"] and doc["lanes"][0]["lane"] == "sama"


@pytest.mark.parametrize("module,registry", [(SA, None), (AE, AE.LANES), (IL, IL.LANES)],
                         ids=["sa", "ae", "il"])
def test_a_wet_run_writes_a_report_with_its_states(module: Any, registry: Any,
                                                   tmp_path: Path) -> None:
    """The report carries the lanes, the catalogue verdict, the key status and the states."""
    report = tmp_path / "REPORT.json"
    doc = SA.run(desk=tmp_path, axes=tmp_path / "axes", fixtures=tmp_path / "fx", keys={},
                 no_fetch=True, dry_run=False, report_path=report, budget_s=10.0,
                 registry=registry)
    assert report.exists()
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["rule"] == SA.RULE
    assert written["catalogue_problems"] == []
    assert set(written["key_status"]) == set(SA.KEY_NAMES)
    assert all("state" in s for s in written["states"])
    assert datetime.fromisoformat(written["at"]).tzinfo is not None
    assert SECRET not in report.read_text(encoding="utf-8")
    assert doc["mode"] == "no-fetch"


def test_the_report_merges_rather_than_clobbers(tmp_path: Path) -> None:
    """Three lanes write one civilization's report; each must keep the others' sections."""
    report = tmp_path / "REPORT.json"
    report.write_text(json.dumps({"kept": "a section another lane wrote"}), encoding="utf-8")
    doc = SA.merge_report({"lanes": []}, path=report, dry_run=False)
    assert doc["kept"] == "a section another lane wrote"
    assert json.loads(report.read_text(encoding="utf-8"))["kept"]


def test_month_end_and_iso_stamps_are_timezone_aware() -> None:
    """A naive datetime here is either a TypeError later or silently wrong arithmetic."""
    assert SA.month_end(2026, 2) == date(2026, 2, 28)
    assert SA.month_end(2024, 2) == date(2024, 2, 29)
    assert SA.month_end(2026, 12) == date(2026, 12, 31)
    stamp = SA.now_iso()
    assert datetime.fromisoformat(stamp).tzinfo is not None
    assert datetime.fromisoformat(stamp).tzinfo == UTC or \
        datetime.fromisoformat(stamp).utcoffset() == timedelta(0)

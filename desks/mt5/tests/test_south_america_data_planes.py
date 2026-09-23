"""THE SOUTH AMERICA LANES: catalogue, fixtures, vintages, and a point-in-time reader that refuses.

    python -m pytest desks/mt5/tests/test_south_america_data_planes.py -q

NO TEST HERE TOUCHES THE NETWORK, and one of them proves it: `urllib.request.urlopen` is replaced
with a function that fails the test if it is ever called, and every lane is then driven through
its `--no-fetch` path. That is stronger than a convention, because the network branch exists in
all three lanes and a default flipped by accident would otherwise be discovered by a rate limit.

THE PROPERTY THESE LANES EXIST FOR is that `read_pit` answers with what the desk COULD HAVE KNOWN
and never with the current revision. Two truncations are required and both are asserted: the
VINTAGE must be the newest whose realtime date is on or before the morning asked about, and its
OBSERVATIONS must be cut to that morning. A vintage stored after the date asked about produces
UNMEASURED WITH A REASON -- never a value, because a revised series labelled point-in-time is a
silent lookahead in every backtest that touches it.

THE ARGENTINE BRECHA is the one genuinely new measurement in this command, and its test plants a
regime transition with a known date and asserts the detector finds THAT date -- not the day the
persistence rule confirmed it, which is a different and later day. A second fixture plants a
one-day excursion across a band edge and asserts the detector does NOT record a transition,
because a detector that fires on noise dates every downstream event study to noise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.countries.ar import data_plane as AR  # noqa: E402
from research.countries.br import data_plane as BR  # noqa: E402
from research.countries.cl import data_plane as CL  # noqa: E402

LANES = (BR, CL, AR)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any lane that reaches the network in a test fails the test, loudly and by name."""
    import urllib.request

    def _forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a lane touched the network during a test; --no-fetch is the default "
                            "and the network branch must be asked for explicitly")

    monkeypatch.setattr(urllib.request, "urlopen", _forbidden)


@pytest.fixture
def fixtures(tmp_path: Path) -> Path:
    """One fixture directory carrying a raw payload per lane, in each provider's own shape."""
    fx = tmp_path / "fixtures"
    fx.mkdir()
    # BCB SGS: DD/MM/YYYY dates and STRING values -- both are parsing traps.
    (fx / "BCB_SGS_432.json").write_text(json.dumps([
        {"data": "02/01/2024", "valor": "11.75"},
        {"data": "01/02/2024", "valor": "11.25"},
        {"data": "01/03/2024", "valor": "10.75"}]), encoding="utf-8")
    # Olinda Focus: every row carries its OWN survey date, so the vintage is exact.
    (fx / "FOCUS_IPCA.json").write_text(json.dumps({"value": [
        {"Indicador": "IPCA", "Data": "2024-01-05", "DataReferencia": "01/2024",
         "Mediana": "0.42", "numeroRespondentes": 95},
        {"Indicador": "IPCA", "Data": "2024-01-12", "DataReferencia": "01/2024",
         "Mediana": "0.48", "numeroRespondentes": 97},
        {"Indicador": "Selic", "Data": "2024-01-12", "DataReferencia": "2024",
         "Mediana": "9.00", "numeroRespondentes": 90}]}), encoding="utf-8")
    # BCCh: DD-MM-YYYY, a "NaN" string for a missing observation, and a statusCode per row.
    (fx / "BCCH_TPM.json").write_text(json.dumps({"Codigo": 0, "Series": {
        "seriesId": "F022.TPM.TIN.D001.NO.Z.D", "Obs": [
            {"indexDateString": "02-01-2024", "value": "11.25", "statusCode": "OK"},
            {"indexDateString": "03-01-2024", "value": "NaN", "statusCode": "ND"},
            {"indexDateString": "04-01-2024", "value": "11.00", "statusCode": "PROV"}]}}),
        encoding="utf-8")
    return fx


@pytest.fixture
def secrets(tmp_path: Path) -> Path:
    p = tmp_path / "latam_apis.json"
    p.write_text(json.dumps({"bcch_user": "u", "bcch_pass": "p", "banxico_token": "t"}),
                 encoding="utf-8")
    return p


# --------------------------------------------------------------------------- catalogue
def test_every_catalogue_row_declares_its_point_in_time_fields() -> None:
    for lane in LANES:
        rows = lane.catalogue()
        assert rows, f"{lane.LANE}: empty catalogue"
        for row in rows:
            assert "observation_date" in row["pit_fields"]
            assert "realtime_date" in row["pit_fields"]
            assert isinstance(row["pit_feasible"], bool)
            assert float(row["publication_lag_days"]) >= 0.0
            assert row["why"], f"{lane.LANE}/{row['series_id']}: no reason to carry this row"


def test_unresolved_provider_ids_are_named_and_never_fetched(fixtures: Path,
                                                             tmp_path: Path) -> None:
    """A guessed provider code returns a real series that is the WRONG series, and nothing
    downstream can detect that -- so an unresolved row is UNMEASURED by name instead."""
    for lane in LANES:
        status = lane.catalogue_status()
        assert status["n_resolved"] >= 1, f"{lane.LANE}: nothing is fetchable at all"
        pending = (status.get("needs_lookup")
                   or [r for c in status.get("by_country", {}).values()
                       for r in c["needs_lookup"]])
        for row in pending:
            assert row["why"], f"{lane.LANE}/{row['series_id']}: unresolved with no reason"
        got = lane.fetch(no_fetch=True, fixtures=fixtures, root=tmp_path / lane.LANE)
        named = {u["series_id"] for u in got["unmeasured"]}
        for row in pending:
            assert row["series_id"] in named, f"{lane.LANE}: {row['series_id']} silently skipped"


def test_credentials_are_reported_by_presence_and_never_by_value(secrets: Path,
                                                                 tmp_path: Path) -> None:
    """A key never leaves the box and no tool prints one; the lane answers PRESENT / ABSENT."""
    with_keys = CL.key_status(secrets)
    assert with_keys["providers"]["bcch_siete"]["outcome"] == "ok"
    blob = json.dumps(with_keys)
    assert '"u"' not in blob and '"p"' not in blob, "a credential value reached the report"

    without = CL.key_status(tmp_path / "absent.json")
    bcch = without["providers"]["bcch_siete"]
    assert bcch["outcome"] == "UNMEASURED"
    assert "bcch_user" in bcch["why"] and "credential gap" in bcch["why"]

    # Brazil needs no key of its own but still reports Banxico's, so a caller can see WHY the
    # Mexican rows of this command are silent.
    assert BR.key_status(tmp_path / "absent.json")["providers"]["banxico_sie"]["needs_key"] is True
    assert all(p["needs_key"] is False for p in AR.key_status(tmp_path / "x.json")
               ["providers"].values())


def test_a_lane_without_credentials_reports_a_credential_gap_not_a_data_gap(
        fixtures: Path, tmp_path: Path) -> None:
    got = CL.fetch(no_fetch=True, fixtures=fixtures, root=tmp_path / "s",
                   secrets_path=tmp_path / "absent.json")
    assert got["n_fetched"] == 0
    why = " ".join(u["why"] for u in got["unmeasured"])
    assert "credential gap, not a data gap" in why


# --------------------------------------------------------------------------- parsers
def test_sgs_parser_survives_the_two_brazilian_traps() -> None:
    rows = BR.parse_sgs([{"data": "03/02/2024", "valor": "10.5"},
                         {"data": "02/01/2024", "valor": "11.75"},
                         {"data": "bad", "valor": "1"},
                         {"data": "01/03/2024", "valor": ""}])
    assert [r["observation_date"] for r in rows] == ["2024-01-02", "2024-02-03"]
    assert rows[0]["value"] == pytest.approx(11.75)


def test_olinda_focus_is_natively_point_in_time(fixtures: Path) -> None:
    payload = json.loads((fixtures / "FOCUS_IPCA.json").read_text(encoding="utf-8"))
    rows = BR.parse_olinda(payload, indicator="IPCA")
    assert len(rows) == 2
    assert {r["realtime_date"] for r in rows} == {"2024-01-05", "2024-01-12"}
    assert all(r["observation_date"] == "01/2024" for r in rows)


def test_bcch_parser_keeps_the_status_code_and_drops_nan(fixtures: Path) -> None:
    payload = json.loads((fixtures / "BCCH_TPM.json").read_text(encoding="utf-8"))
    rows = CL.parse_bcch(payload)
    assert [r["observation_date"] for r in rows] == ["2024-01-02", "2024-01-04"]
    assert [r["status_code"] for r in rows] == ["OK", "PROV"]


def test_bcrp_parser_reads_spanish_periods_and_drops_unavailable() -> None:
    rows = CL.parse_bcrp({"periods": [{"name": "Ene.2024", "values": ["5.25"]},
                                      {"name": "Feb.2024", "values": ["n.d."]},
                                      {"name": "Mar.2024", "values": ["5.00"]}]})
    assert [r["observation_date"] for r in rows] == ["2024-01-01", "2024-03-01"]
    assert rows[-1]["value"] == pytest.approx(5.00)


def test_bcra_parser_reads_both_endpoint_shapes() -> None:
    flat = AR.parse_bcra({"status": 200, "results": [{"fecha": "2024-01-02", "valor": 808.5}]})
    assert flat == [{"observation_date": "2024-01-02", "value": 808.5}]
    nested = AR.parse_bcra({"status": 200, "results": [
        {"fecha": "2024-01-03", "detalle": [{"codigoMoneda": "EUR", "tipoCotizacion": 900.0},
                                            {"codigoMoneda": "USD", "tipoCotizacion": 810.0}]}]})
    assert nested == [{"observation_date": "2024-01-03", "value": 810.0}]


def test_tracker_parser_uses_the_sell_side_only() -> None:
    """A brecha built from a bid on one leg and an ask on the other is part spread, and the
    spread is exactly what changes when a market gets thin."""
    rows = AR.parse_tracker([{"casa": "blue", "fecha": "2024-01-02", "compra": 900, "venta": 950}],
                            casa="blue")
    assert rows == [{"observation_date": "2024-01-02", "value": 950.0}]


# --------------------------------------------------------------------------- vintages and PIT
def test_a_new_fetch_adds_a_vintage_and_never_overwrites_the_old_one(fixtures: Path,
                                                                     tmp_path: Path) -> None:
    root = tmp_path / "store"
    BR.fetch(["BCB_SGS_432"], no_fetch=True, fixtures=fixtures, root=root, realtime="2024-02-15")
    BR.fetch(["BCB_SGS_432"], no_fetch=True, fixtures=fixtures, root=root, realtime="2024-03-15")
    assert BR.vintages("BCB_SGS_432", root=root) == ("2024-02-15", "2024-03-15")


def test_read_pit_truncates_the_vintage_and_the_observations(fixtures: Path,
                                                             tmp_path: Path) -> None:
    root = tmp_path / "store"
    BR.fetch(["BCB_SGS_432"], no_fetch=True, fixtures=fixtures, root=root, realtime="2024-02-15")
    BR.fetch(["BCB_SGS_432"], no_fetch=True, fixtures=fixtures, root=root, realtime="2024-03-15")

    early = BR.read_pit("BCB_SGS_432", "2024-02-20", root=root)
    assert early["vintage"] == "2024-02-15"                    # the newest at or before that day
    assert [r["observation_date"] for r in early["rows"]] == ["2024-01-02", "2024-02-01"]

    late = BR.read_pit("BCB_SGS_432", "2024-04-01", root=root)
    assert late["vintage"] == "2024-03-15"
    assert len(late["rows"]) == 3


def test_read_pit_refuses_a_vintage_that_did_not_exist_yet(fixtures: Path,
                                                           tmp_path: Path) -> None:
    """The whole reason the store exists: never answer a morning from a later revision."""
    root = tmp_path / "store"
    BR.fetch(["BCB_SGS_432"], no_fetch=True, fixtures=fixtures, root=root, realtime="2024-03-15")
    got = BR.read_pit("BCB_SGS_432", "2023-12-31", root=root)
    assert got["outcome"] == "UNMEASURED"
    assert got["rows"] == []
    assert "lookahead" in got["why"]
    assert got["stored_vintages"] == ["2024-03-15"]

    absent = BR.read_pit("BCB_SGS_432", "2024-03-20", root=tmp_path / "empty")
    assert absent["outcome"] == "UNMEASURED" and "not fetched" in absent["why"]


def test_provisional_observations_are_kept_and_counted(fixtures: Path, tmp_path: Path,
                                                       secrets: Path) -> None:
    """A provisional value IS the point-in-time value -- it is what the desk could have known."""
    root = tmp_path / "store"
    CL.fetch(["BCCH_TPM"], no_fetch=True, fixtures=fixtures, root=root, realtime="2024-02-01",
             secrets_path=secrets)
    got = CL.read_pit("BCCH_TPM", "2024-03-01", root=root)
    assert got["outcome"] == "ok"
    assert got["n_provisional"] == 1


# --------------------------------------------------------------------------- the brecha
def _brecha_fixture(tmp_path: Path, gaps: list[float], *, start_day: int = 1) -> Path:
    fx = tmp_path / "ar_fx"
    fx.mkdir(exist_ok=True)
    official, blue = [], []
    for i, gap in enumerate(gaps):
        day = f"2024-01-{start_day + i:02d}"
        rate = 1000.0 + i
        official.append({"fecha": day, "valor": rate})
        blue.append({"casa": "blue", "fecha": day, "venta": round(rate * (1.0 + gap), 4)})
    (fx / "BCRA_A3500.json").write_text(json.dumps({"status": 200, "results": official}),
                                        encoding="utf-8")
    (fx / "AR_DOLAR_BLUE.json").write_text(json.dumps(blue), encoding="utf-8")
    return fx


def test_the_brecha_flags_a_planted_regime_transition_at_its_first_day(tmp_path: Path) -> None:
    fx = _brecha_fixture(tmp_path, [0.10] * 10 + [0.70] * 10)
    root = tmp_path / "store"
    AR.fetch(no_fetch=True, fixtures=fx, root=root, realtime="2024-02-01")
    state = AR.brecha_state(root, as_of="2024-03-01", kind="blue")

    assert state["outcome"] == "ok"
    assert state["state"] == "cepo_hard"
    assert state["n_transitions"] == 1
    tr = state["transitions"][0]
    assert tr["from"] == "managed" and tr["to"] == "cepo_hard"
    assert tr["date"] == "2024-01-11", "the transition is dated to the FIRST day in the new band"
    assert tr["confirmed_on"] == "2024-01-13", "and confirmed three observations later"


def test_the_brecha_does_not_fire_on_a_one_day_excursion(tmp_path: Path) -> None:
    """A detector that fires on noise dates every downstream event study to noise."""
    fx = _brecha_fixture(tmp_path, [0.10] * 8 + [0.70] + [0.10] * 8)
    root = tmp_path / "store2"
    AR.fetch(no_fetch=True, fixtures=fx, root=root, realtime="2024-02-01")
    state = AR.brecha_state(root, as_of="2024-03-01", kind="blue")
    assert state["n_transitions"] == 0
    assert state["state"] == "managed"


def test_the_brecha_is_unmeasured_when_a_leg_is_missing(tmp_path: Path) -> None:
    fx = _brecha_fixture(tmp_path, [0.10] * 12)
    root = tmp_path / "store3"
    AR.fetch(no_fetch=True, fixtures=fx, root=root, realtime="2024-02-01")
    got = AR.brecha_state(root, as_of="2024-03-01", kind="mep")
    assert got["outcome"] == "UNMEASURED"
    assert got["missing_legs"] == ["AR_DOLAR_MEP"]

    nothing = AR.brecha([], [], kind="blue")
    assert nothing["outcome"] == "UNMEASURED"
    assert "ratio with one leg is not a small brecha" in nothing["why"]


def test_bands_are_declared_and_cover_the_whole_line() -> None:
    assert AR.band_of(0.01) == "convertible"
    assert AR.band_of(0.10) == "managed"
    assert AR.band_of(0.35) == "cepo_light"
    assert AR.band_of(0.80) == "cepo_hard"
    assert AR.band_of(2.50) == "cepo_extreme"


def test_mep_ccl_spread_divides_the_peso_out() -> None:
    mep = [{"observation_date": "2024-01-02", "value": 1000.0}]
    ccl = [{"observation_date": "2024-01-02", "value": 1050.0}]
    got = AR.mep_ccl_spread(mep, ccl)
    assert got["outcome"] == "ok"
    assert got["spread"] == pytest.approx(0.05)
    assert AR.mep_ccl_spread(mep, [])["outcome"] == "UNMEASURED"


# --------------------------------------------------------------------------- derived states
def test_copper_state_is_discrete_and_refuses_a_short_series() -> None:
    rows = [{"observation_date": f"2024-{m:02d}-01", "value": 100.0 + 3 * m} for m in range(1, 9)]
    got = CL.copper_state(rows)
    assert got["outcome"] == "ok" and got["state"] == "expanding"
    flat = [{"observation_date": f"2024-{m:02d}-01", "value": 100.0} for m in range(1, 9)]
    assert CL.copper_state(flat)["state"] == "flat"
    short = CL.copper_state(rows[:3])
    assert short["outcome"] == "UNMEASURED" and "acceleration" in short["why"]


def test_cvm_sensors_aggregate_and_never_emit_a_single_name() -> None:
    """The two-lane order is enforced by WHICH FUNCTION IS PUBLIC, not by taste."""
    rows = [
        {"DT_COMPTC": "2024-01-02", "CNPJ_FUNDO": "11.111", "CAPTC_DIA": "100",
         "RESG_DIA": "40", "VL_PATRIM_LIQ": "1000", "CLASSE": "Acoes"},
        {"DT_COMPTC": "2024-01-02", "CNPJ_FUNDO": "22.222", "CAPTC_DIA": "50",
         "RESG_DIA": "10", "VL_PATRIM_LIQ": "1000", "CLASSE": "Acoes"},
        {"DT_COMPTC": "2024-01-02", "CNPJ_FUNDO": "33.333", "CAPTC_DIA": "10",
         "RESG_DIA": "0", "VL_PATRIM_LIQ": "500", "CLASSE": "Cambial"},
    ]
    got = BR.cvm_sensors(rows)
    assert got["outcome"] == "ok" and got["days"] == 1
    day = got["series"][0]
    assert day["net_flow"] == pytest.approx(110.0)
    assert day["n_funds"] == 3
    assert set(day["class_shares"]) == {"Acoes"}, "a one-fund class must be suppressed"
    assert day["suppressed_classes"] == ["Cambial"]
    assert "33.333" not in json.dumps(got) and "11.111" not in json.dumps(got)
    assert BR.cvm_sensors([])["outcome"] == "UNMEASURED"


# --------------------------------------------------------------------------- reports and CLI
def test_reports_can_be_written_without_touching_the_real_desk(fixtures: Path, tmp_path: Path,
                                                               secrets: Path,
                                                               monkeypatch: pytest.MonkeyPatch
                                                               ) -> None:
    for lane in LANES:
        monkeypatch.setattr(lane, "REPORT", tmp_path / f"{lane.LANE}.json")
        kwargs: dict[str, Any] = {"root": tmp_path / f"{lane.LANE}_store", "fixtures": fixtures,
                                  "no_fetch": True}
        if lane is CL:
            kwargs["secrets_path"] = secrets
        doc = lane.report(**kwargs)
        assert doc["lane"] == lane.LANE
        assert (tmp_path / f"{lane.LANE}.json").exists()
        assert all(row["why"] for row in doc["fetch"]["unmeasured"]), (
            f"{lane.LANE}: an unfetchable row with no reason is an absence, not a measurement")


def test_dry_run_writes_no_report(fixtures: Path, tmp_path: Path,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "must_not_exist.json"
    monkeypatch.setattr(AR, "REPORT", target)
    rc = AR.main(["--dry-run", "--fixtures", str(fixtures), "--root", str(tmp_path / "s"),
                  "--brecha"])
    assert rc == 0
    assert not target.exists()


def test_catalogue_cli_prints_and_exits_clean(capsys: pytest.CaptureFixture[str]) -> None:
    for lane in LANES:
        assert lane.main(["--catalogue"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["lane"] == lane.LANE

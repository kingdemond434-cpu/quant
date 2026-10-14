"""A sleeve the principal or the CRO stopped stays off LIVE until the principal's recorded resume.

2026-10-13/14: the AUDCHF, EURZAR and USDZAR gap-decay sleeves were stood down with a
`standby_reason` heal_silent_demotions did not read; it lifted all three back to LIVE and the
principal book re-sized them. #397 fixes the healer's read; this record holds a stop that carries
no reason on the row at all.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import principal_stops as ps  # noqa: E402

AUD = {
    "name": "audchf_overnight_gap_decay_asia_p_44136fa355b3678a_principal_20261007",
    "symbol": "AUDCHF",
    "family": "overnight_gap_decay",
    "selector": "asia",
    "status": "LIVE",
    "risk_frac": 0.1,
    "risk_frac_source": "principal_cert_book",
    "restored_by": "heal_silent_demotions",
    "exec": "family_market",
}
CARRY = {
    "name": "eurzar_carry_asia",
    "symbol": "EURZAR",
    "family": "carry",
    "selector": "asia",
    "status": "LIVE",
    "risk_frac": 0.05,
    "exec": "family_market",
}
STOP = {
    "identity": "audchf|overnight_gap_decay|asia",
    "by": "principal",
    "at": "2026-10-13T20:41:00+00:00",
    "authority": "Yes remove from fusion live",
    "resumed": None,
}


def _write(tmp: Path, rows: list[dict], stops: list[dict] | None) -> Path:
    sl = tmp / "sleeves.json"
    sl.write_text(json.dumps({"sleeves": rows}), "utf-8")
    if stops is not None:
        (tmp / "PRINCIPAL_STOPS.json").write_text(json.dumps({"stops": stops}), "utf-8")
    return sl


def test_an_identity_stop_covers_every_re_mint_and_spares_other_families() -> None:
    remint = {**AUD, "name": "audchf_overnight_gap_decay_asia_p_4e3e7963cfc9ce12"}
    assert ps.match(AUD, [STOP]) is STOP and ps.match(remint, [STOP]) is STOP
    assert ps.match(CARRY, [STOP]) is None


def test_only_a_recorded_principal_resume_lifts_a_stop() -> None:
    assert not ps.resumed({**STOP, "resumed": {"by": "coordinator", "message": "ok"}})
    assert not ps.resumed({**STOP, "resumed": {"by": "principal", "message": ""}})
    assert ps.resumed({**STOP, "resumed": {"by": "principal", "message": "cmsg_x resume AUDCHF"}})


def test_the_gateway_roster_drops_a_stopped_live_row(tmp_path, monkeypatch) -> None:
    import mt5desk.live_policy as lp

    monkeypatch.setattr(lp, "admit", lambda rows: (list(rows), []))
    sl = _write(tmp_path, [AUD, CARRY], [STOP])
    keep, notes = dc.load_sleeves_verbose(sl)
    assert [r["name"] for r in keep] == ["eurzar_carry_asia"]
    assert any(n.startswith("PRINCIPAL STOP holds audchf") for n in notes)
    resumed = {**STOP, "resumed": {"by": "principal", "at": "x", "message": "cmsg_y"}}
    _write(tmp_path, [AUD, CARRY], [resumed])
    assert len(dc.load_sleeves_verbose(sl)[0]) == 2


def test_no_readable_stops_file_holds_the_built_in_stops_at_the_gateway(
    tmp_path, monkeypatch
) -> None:
    import mt5desk.live_policy as lp

    monkeypatch.setattr(lp, "admit", lambda rows: (list(rows), []))
    sl = _write(tmp_path, [AUD, CARRY], None)
    for content in (None, "{not json", '{"other": 1}'):
        if content is not None:
            (tmp_path / "PRINCIPAL_STOPS.json").write_text(content, "utf-8")
        keep, notes = dc.load_sleeves_verbose(sl)
        assert [r["name"] for r in keep] == ["eurzar_carry_asia"], content
        assert any("plus the built-in" in n for n in notes)


def test_a_malformed_entry_is_skipped_and_the_valid_stops_still_hold(tmp_path, monkeypatch) -> None:
    import mt5desk.live_policy as lp

    from scripts import check_principal_stops as fence

    monkeypatch.setattr(lp, "admit", lambda rows: (list(rows), []))
    sl = _write(tmp_path, [AUD, CARRY], [STOP, {"by": "nobody"}])
    keep, _notes = dc.load_sleeves_verbose(sl)
    assert [r["name"] for r in keep] == ["eurzar_carry_asia"]
    doc = fence.check(sl, tmp_path / "PRINCIPAL_STOPS.json")
    assert doc["status"] == "RED" and doc["breaches"] and "skipped 1" in doc["why"]


def _heal(tmp: Path, monkeypatch):
    path = _DESK / "scripts" / "heal_silent_demotions.py"
    spec = importlib.util.spec_from_file_location("heal_silent_demotions_ps", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "SLEEVES", tmp / "sleeves.json")
    return mod


def test_the_healer_never_lifts_a_stopped_row(tmp_path, monkeypatch) -> None:
    stood_down = {**AUD, "status": "STANDBY", "risk_frac": 0.0}
    silent = {**CARRY, "status": "STANDBY"}
    _write(tmp_path, [stood_down, silent], [STOP])
    heal = _heal(tmp_path, monkeypatch)
    assert heal.heal(apply=True) == 0
    rows = {r["name"]: r for r in json.loads((tmp_path / "sleeves.json").read_text())["sleeves"]}
    assert rows[AUD["name"]]["status"] == "STANDBY"
    assert rows["eurzar_carry_asia"]["status"] == "LIVE"


def test_the_healer_restores_nothing_when_the_stops_are_unreadable(tmp_path, monkeypatch) -> None:
    _write(tmp_path, [{**CARRY, "status": "STANDBY"}], None)
    (tmp_path / "PRINCIPAL_STOPS.json").write_text("{not json", "utf-8")
    heal = _heal(tmp_path, monkeypatch)
    assert heal.heal(apply=True) == 1
    rows = json.loads((tmp_path / "sleeves.json").read_text())["sleeves"]
    assert rows[0]["status"] == "STANDBY"


def test_the_fence_is_red_on_a_stopped_live_row_and_names_its_writer(tmp_path) -> None:
    from scripts import check_principal_stops as fence

    sl = _write(tmp_path, [AUD, CARRY], [STOP])
    doc = fence.check(sl, tmp_path / "PRINCIPAL_STOPS.json")
    assert (
        doc["status"] == "RED"
        and doc["breaches"][0]["written_by"] == "restored_by=heal_silent_demotions"
    )
    _write(tmp_path, [{**AUD, "status": "STANDBY", "risk_frac": 0.0}, CARRY], [STOP])
    doc = fence.check(sl, tmp_path / "PRINCIPAL_STOPS.json")
    assert doc["status"] == "OK" and doc["held_off_live"] == 1
    assert (
        fence.check(tmp_path / "absent.json", tmp_path / "PRINCIPAL_STOPS.json")["status"]
        == "UNMEASURED"
    )


def test_the_committed_stops_hold_the_three_gap_decay_sleeves() -> None:
    stops, problem = ps.load(_DESK / "data" / "PRINCIPAL_STOPS.json")
    assert problem is None
    assert {s["identity"] for s in stops} == {
        "audchf|overnight_gap_decay|asia",
        "usdzar|overnight_gap_decay|asia",
        "eurzar|overnight_gap_decay|asia",
    }
    assert ps.match(CARRY | {"symbol": "EURZAR"}, stops) is None, "EURZAR carry is in the book"


def test_the_fence_runs_hourly_and_its_red_is_a_verdict() -> None:
    from research import hourly_cycle as hc

    assert "principal_stops" in hc.CORE_LEGS
    assert hc.VERDICT_EXITS["principal_stops"] == (1,)


def test_an_absent_stops_file_lifts_nothing_and_the_fence_reads_unmeasured(
    tmp_path, monkeypatch
) -> None:
    from scripts import check_principal_stops as fence

    sl = _write(tmp_path, [{**AUD, "status": "STANDBY", "risk_frac": 0.0}], None)
    heal = _heal(tmp_path, monkeypatch)
    assert heal.heal(apply=True) == 1
    assert json.loads(sl.read_text())["sleeves"][0]["status"] == "STANDBY"
    doc = fence.check(sl, tmp_path / "PRINCIPAL_STOPS.json")
    assert doc["status"] == "UNMEASURED" and doc["why"].endswith("absent")


def test_an_emptied_file_or_a_typo_in_a_stop_never_releases_a_built_in_stop(
    tmp_path, monkeypatch
) -> None:
    import mt5desk.live_policy as lp
    from scripts import check_principal_stops as fence

    monkeypatch.setattr(lp, "admit", lambda rows: (list(rows), []))
    typo = {k: v for k, v in STOP.items() if k != "identity"} | {"identiy": STOP["identity"]}
    for stops in ([], [typo]):
        sl = _write(tmp_path, [AUD, CARRY], stops)
        keep, _notes = dc.load_sleeves_verbose(sl)
        assert [r["name"] for r in keep] == ["eurzar_carry_asia"], stops
        doc = fence.check(sl, tmp_path / "PRINCIPAL_STOPS.json")
        assert doc["status"] == "RED" and doc["breaches"], stops
    resume = {**STOP, "resumed": {"by": "principal", "at": "x", "message": "cmsg_z resume"}}
    sl = _write(tmp_path, [AUD, CARRY], [resume])
    assert len(dc.load_sleeves_verbose(sl)[0]) == 2, "only the recorded resume releases it"

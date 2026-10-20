"""The principal's Fusion book (zuck, BOOKS_PATCH v5, approved 2026-10-13; widened to all three
gold windows 2026-10-20 16:58Z; sizing changed 2026-10-20 after the audit HOLD on 50ef074f9).

    python -m pytest desks/mt5/tests/test_fusion_minlot_book.py -q

The live Fusion account trades exactly SIX sleeves and nothing else: gold_asia, gold_london_am,
gold_afternoon, usdnok_carry_asia_p_ff35bb7c8427d66f, eurils_formula_asia_p_673857a649d3c271 and
eurzar_carry_asia_p_8339edce23032d21, each at max(0.01, the lot at 0.75% risk at its own stop),
inside the MAX_RISK_FRAC envelope. The three overnight_gap_decay principal rows, NZDJPY, the XAU m5
scalp and USDJPY send nothing. Pinned here:

  * the book's lot: the 0.01 floor at a small equity, 0.75% risk once equity carries it, the
    envelope above, an allocator zero and an unpriceable stop at 0, sovereignty-off steps aside;
  * one order per signal for each FX name, never boosted past the book's lot (`min`);
  * 0 orders for NZDJPY, XAU m5, USDJPY and the three gap_decay rows;
  * a seventh name cannot ride the override, and the file can only narrow the code's set;
  * the switch is bound to the Fusion LIVE account: the login the box declares in the gitignored
    data/FUSION_LIVE_ACCOUNT.json (never committed), server FusionMarkets-Live, kind live;
    absent / unreadable / disabled / wrong-typed / a committed login is NO override;
  * one gold trade at risk at a time, as strict as E8's; the daily-loss rail; the rail lines.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mt5desk  # noqa: E402
from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import live_policy  # noqa: E402
from mt5desk import provenance as _prov  # noqa: E402

# The gateway adapter harness (AST-extracted gateway functions over the real core), loaded by
# path so this file collects under --import-mode=importlib as well as from the tests directory.
_spec = importlib.util.spec_from_file_location("_fusion_minlot_adapter",
                                               _DESK / "tests" / "test_gateway_adapter.py")
assert _spec is not None and _spec.loader is not None
adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adapter)

GOLD = "gold_asia"
USDNOK = "usdnok_carry_asia_p_ff35bb7c8427d66f"
EURILS = "eurils_formula_asia_p_673857a649d3c271"
EURZAR = "eurzar_carry_asia_p_8339edce23032d21"
GOLDS = {"gold_asia", "gold_london_am", "gold_afternoon"}
FOUR = GOLDS | {USDNOK, EURILS, EURZAR}             # the six (name kept from the v5 four)
FX = (USDNOK, EURILS, EURZAR)
TWINS = ("usdnok_carry_asia_p_d5391837ec28998b", "eurzar_carry_asia_p_55e2dabcb8c43d1f")
GAP_DECAY = tuple(f"{s}_overnight_gap_decay_asia_p_44136fa355b3678a_principal_20261007"
                  for s in ("audchf", "eurzar", "usdzar"))
NZDJPY = "nzdjpy_clock_transition_asia_p_caebb3dcbda3756e"
EQUITY = 485.0
SYMBOL_OF = {USDNOK: "USDNOK", EURILS: "EURILS", EURZAR: "EURZAR"}


def _committed_rows() -> dict[str, dict]:
    doc = json.loads((_DESK / "data" / "sleeves.json").read_text(encoding="utf-8"))
    return {r["name"]: r for r in doc["sleeves"] if isinstance(r, dict) and "name" in r}


#: A SYNTHETIC login. The real one is never written into a tracked file
#: (tests/ops/test_live_infrastructure_is_not_published.py); the box declares it in the
#: gitignored data/FUSION_LIVE_ACCOUNT.json, which each test here points at a tmp copy.
LOGIN = 7_000_001
SERVER = "FusionMarkets-Live"


def _override_file(tmp_path: Path, **doc) -> Path:
    body = {"enabled": True, "lot": 0.01, "server": SERVER, "sleeves": sorted(FOUR), **doc}
    body = {k: v for k, v in body.items() if v is not _DROP}
    p = tmp_path / "MINLOT_OVERRIDE.json"
    p.write_text(json.dumps(body), encoding="utf-8")
    return p


_DROP = object()


def _account_file(tmp_path: Path, **doc) -> Path:
    p = tmp_path / "FUSION_LIVE_ACCOUNT.json"
    p.write_text(json.dumps({"login": LOGIN, "server": SERVER, **doc}), encoding="utf-8")
    return p


def _on(p: Path | None = None, login: object = LOGIN, server: object = SERVER,
        kind: object = "live") -> tuple[frozenset[str], str]:
    return dc.minlot_override_active(login, p, server=server, kind=kind)


@pytest.fixture(autouse=True)
def _sovereign(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dc, "ALLOCATOR_SOVEREIGN", True)
    monkeypatch.setattr(dc, "ALLOCATOR_SOVEREIGN_FILE", tmp_path / "ALLOCATOR_SOVEREIGN.json")
    monkeypatch.setattr(dc, "MIN_LOT_FILE", tmp_path / "MIN_LOT.json")
    monkeypatch.setattr(dc, "FUSION_ACCOUNT_FILE", _account_file(tmp_path))


# ------------------------------------------------------------------ the set and the switch

def test_the_code_names_exactly_the_six_and_pins_each_certificate() -> None:
    assert dc.MINLOT_OVERRIDE_SLEEVES == FOUR
    assert dc.MINLOT_OVERRIDE_LOT == 0.01
    assert dc.MINLOT_OVERRIDE_TARGET_FRAC == 0.0075
    assert dc.FUSION_LIVE_SERVER == SERVER
    assert not hasattr(dc, "FUSION_LIVE_LOGIN"), "the live login is never a constant in code"
    assert dc.MINLOT_OVERRIDE_PINS == {
        "gold_asia": None, "gold_london_am": None, "gold_afternoon": None,
        USDNOK: "external.USDNOK@M5.carry.p=ff35bb7c8427d66f",
        EURILS: "external.EURILS.formula.p=673857a649d3c271",
        EURZAR: "external.EURZAR@M15.carry.p=8339edce23032d21"}
    for name in (*TWINS, *GAP_DECAY, NZDJPY, "xau_m5_anti_breakout_overlap",
                 "USDJPY.asia#rr=2.5", "gold_asia_v2", "gold_ny_open"):
        assert name not in dc.MINLOT_OVERRIDE_SLEEVES


def test_the_committed_switch_turns_on_exactly_the_six_on_the_declared_live_account() -> None:
    active, why = _on()
    assert active == FOUR, why
    doc = json.loads(dc.MINLOT_OVERRIDE_FILE.read_text(encoding="utf-8"))
    assert "account" not in doc and doc["server"] == SERVER
    assert doc["lot"] == 0.01 and doc["target_risk"] == 0.0075
    for other in (None, 12345, str(LOGIN), True):
        assert _on(login=other)[0] == frozenset()
    assert _on(server="FusionMarkets-Demo")[0] == frozenset()
    assert _on(kind="demo")[0] == frozenset() and _on(kind="unknown")[0] == frozenset()


def test_an_absent_file_is_no_override(tmp_path: Path) -> None:
    active, why = _on(tmp_path / "absent.json")
    assert active == frozenset() and "off" in why


@pytest.mark.parametrize("doc", [
    {"enabled": False},
    {"enabled": "true"},
    {"lot": 0.02},
    {"lot": "0.01"},
    {"lot": True},
    {"sleeves": {}},
    {"sleeves": "gold_asia"},
    {"server": "FusionMarkets-Demo"},
    {"server": _DROP},
    {"account": LOGIN},                       # a committed login is refused, not trusted
    {"account": None},
    {"target_risk": 0.01},
    {"target_risk": "0.0075"},
])
def test_wrong_values_or_types_fail_closed(tmp_path: Path, doc: dict) -> None:
    active, why = _on(_override_file(tmp_path, **doc))
    assert active == frozenset(), why


@pytest.mark.parametrize("acct", [
    None,                                      # no declaration on the box
    "{not json",
    {"login": str(LOGIN), "server": SERVER},
    {"login": True, "server": SERVER},
    {"login": 0, "server": SERVER},
    {"login": LOGIN, "server": "FusionMarkets-Demo"},
    {"login": LOGIN},
])
def test_an_undeclared_or_bad_account_file_is_off(tmp_path: Path, monkeypatch, acct) -> None:
    p = tmp_path / "acct.json"
    if acct is not None:
        p.write_text(acct if isinstance(acct, str) else json.dumps(acct), encoding="utf-8")
    monkeypatch.setattr(dc, "FUSION_ACCOUNT_FILE", p)
    active, why = _on(_override_file(tmp_path))
    assert active == frozenset() and "UNBOUND" in why, why


def test_garbage_and_non_dict_files_fail_closed(tmp_path: Path) -> None:
    for text in ("{not json", "[]", "null", '"enabled"'):
        p = tmp_path / "MINLOT_OVERRIDE.json"
        p.write_text(text, encoding="utf-8")
        assert _on(p)[0] == frozenset()


def test_the_binding_is_the_declared_login_server_and_kind(tmp_path: Path) -> None:
    p = _override_file(tmp_path)
    assert _on(p)[0] == FOUR
    assert _on(p, login=None)[0] == frozenset()
    assert _on(p, login=54321)[0] == frozenset()
    why = _on(p, login=54321)[1]
    assert "ACCOUNT_MISMATCH" in why and "54321" not in why     # no login echoed into the log


def test_the_file_can_only_narrow_the_code_set(tmp_path: Path) -> None:
    p = _override_file(tmp_path, sleeves=[USDNOK, NZDJPY, TWINS[0], 7, "gold_london_am",
                                          "gold_asia_v3"])
    active, why = _on(p)
    assert active == {USDNOK, "gold_london_am"}
    assert NZDJPY in why and "ignored" in why


# ------------------------------------------------------------------ the mark and the lot

def test_only_named_and_active_entries_are_marked_and_a_written_mark_is_popped() -> None:
    rows = [{"name": n} for n in (*FOUR, NZDJPY, "gold_asia_v2", *GAP_DECAY)]
    rows[-1]["minlot_override"] = True           # a mark arriving from a file is not authority
    dc.stamp_minlot_override(rows, frozenset(FOUR), EQUITY)
    assert {r["name"] for r in rows if r.get("minlot_override")} == FOUR
    dc.stamp_minlot_override(rows, frozenset({GOLD}), EQUITY)
    assert {r["name"] for r in rows if r.get("minlot_override")} == {GOLD}


def test_below_the_ruin_line_nothing_is_marked() -> None:
    rows = [{"name": n} for n in FOUR]
    notes = dc.stamp_minlot_override(rows, frozenset(FOUR), dc.PROMOTED_MIN_EQUITY - 1)
    assert not any(r.get("minlot_override") for r in rows) and len(notes) == 6
    dc.stamp_minlot_override(rows, frozenset(FOUR), float("nan"))
    assert not any(r.get("minlot_override") for r in rows)


_FX_INFO = SimpleNamespace(volume_min=0.01, volume_step=0.01, volume_max=100.0,
                           trade_tick_size=0.00001, trade_tick_value=1.0)


def _size(name: str, symbol: str, info, equity: float, dist: float, **row):
    return dc.minlot_override_size({"name": name, "minlot_override": True, **row}, symbol, info,
                                   equity, dist)


def test_the_book_lot_is_the_floor_at_a_small_equity_and_075_risk_above_it() -> None:
    unit = dc._eur_per_price_unit("XAUUSD", None)
    # At ~EUR 485 the 0.75% target is below 0.01: the floor sends 0.01, and says so.
    lot, target, basis = _size("gold_asia", "XAUUSD", None, EQUITY, 19.1)
    assert (lot, target) == (0.01, 0.0) and "0.01 floor" in basis
    # Once equity carries it, the lot IS 0.75% at this stop (snapped down), and grows with equity.
    for equity in (5_000.0, 50_000.0):
        lot, target, basis = _size("gold_asia", "XAUUSD", None, equity, 19.1)
        assert lot == target > 0.01 and "0.75% risk" in basis
        assert lot * 19.1 * unit <= 0.0075 * equity + 1e-9
        assert (lot + 0.01) * 19.1 * unit > 0.0075 * equity
    assert _size("gold_asia", "XAUUSD", None, 50_000.0, 19.1)[0] \
        > _size("gold_asia", "XAUUSD", None, 5_000.0, 19.1)[0]
    # FX the same way through the venue's own tick value.
    lot, _, _ = _size(USDNOK, "USDNOK", _FX_INFO, 100_000.0, 0.02)
    assert lot == pytest.approx(0.0075 * 100_000.0 / (0.02 * 100_000.0), abs=0.01)


def test_unmarked_or_seventh_names_or_sovereignty_off_are_not_sized_here(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert dc.minlot_override_size({"name": USDNOK}, "USDNOK", _FX_INFO, EQUITY, 0.02) is None
    assert _size(NZDJPY, "NZDJPY", _FX_INFO, EQUITY, 0.2) is None          # forged mark
    # ALLOCATOR_SOVEREIGN off: the revert path's own floors size these sleeves, not the book.
    (tmp_path / "ALLOCATOR_SOVEREIGN.json").write_text('{"enabled": false}', encoding="utf-8")
    assert _size("gold_asia", "XAUUSD", None, EQUITY, 19.1) is None


@pytest.mark.parametrize("row,info,equity,dist,flag", [
    ({"sized_by": "allocator_book", "risk_frac": 0.0}, _FX_INFO, EQUITY, 0.02, "pins this"),
    ({"sized_by": "allocator_book", "risk_frac": None}, _FX_INFO, EQUITY, 0.02, "pins this"),
    ({}, _FX_INFO, EQUITY, 0.0, "not positive"),
    ({}, _FX_INFO, float("nan"), 0.02, "not positive"),
    ({}, SimpleNamespace(volume_min=0.1, volume_step=0.1, trade_tick_size=0.00001,
                         trade_tick_value=1.0), EQUITY, 0.02, "step"),
    ({}, SimpleNamespace(volume_min=0.02, volume_step=0.01, trade_tick_size=0.00001,
                         trade_tick_value=1.0), EQUITY, 0.02, "venue minimum"),
    ({}, _FX_INFO, EQUITY, 60.0, "envelope"),           # 0.01 at this stop > 10% of equity
])
def test_a_zero_an_unpriceable_stop_or_the_envelope_sends_nothing(row, info, equity, dist,
                                                                 flag) -> None:
    lot, _target, why = _size(USDNOK, "USDNOK", info, equity, dist, **row)
    assert lot == 0.0 and flag in why, why


def test_a_positive_allocator_fraction_is_still_the_book_lot_not_the_allocators() -> None:
    lot, _, _ = _size("gold_asia", "XAUUSD", None, 50_000.0, 19.1,
                      sized_by="allocator_book", risk_frac=0.10)
    assert lot == _size("gold_asia", "XAUUSD", None, 50_000.0, 19.1)[0]


def test_the_envelope_caps_the_book_lot_below_the_target_when_it_binds(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dc, "MAX_RISK_FRAC", 0.005)          # an envelope tighter than 0.75%
    lot, target, _ = _size("gold_asia", "XAUUSD", None, 50_000.0, 19.1)
    assert 0.01 <= lot < target


# ------------------------------------------------------------------ admission of the pinned rows

def _sleeves_file(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "sleeves.json"
    p.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
    return p


def test_the_three_retired_fx_rows_are_admitted_by_exact_name_and_nothing_else(
        tmp_path: Path) -> None:
    rows = _committed_rows()
    for n in FX:
        assert rows[n]["status"] == "RETIRED" and rows[n]["retired_by"] == "live_policy"
    pool = [rows[n] for n in (*FX, *TWINS, *GAP_DECAY) if n in rows]
    got, notes = dc.minlot_override_rows(_sleeves_file(tmp_path, pool), frozenset(FOUR))
    assert sorted(r["name"] for r in got) == sorted(FX), notes
    for r in got:
        assert r["status"] == "LIVE" and r["risk_frac"] == 0.0
        assert "retire_reason" not in r and "minlot_override" not in r
    # Each refuses under the policy the box has before this patch (USDNOK/EURILS outside it).
    old = live_policy.Policy(live_symbols=frozenset({"XAUUSD", "USDJPY", "EURZAR", "USDZAR",
                                                     "AUDCHF"}))
    got_old, notes_old = dc.minlot_override_rows(_sleeves_file(tmp_path, pool),
                                                 frozenset(FOUR), pol=old)
    assert sorted(r["name"] for r in got_old) == [EURZAR]
    assert sum("OVERRIDE_POLICY_REFUSED" in n for n in notes_old) == 2


def test_a_sibling_only_allowlist_refuses_the_pinned_row(tmp_path: Path) -> None:
    rows = _committed_rows()
    pol = live_policy.Policy(live_symbols=frozenset({"USDNOK"}),
                             live_sleeves={"USDNOK": frozenset({TWINS[0]})})
    got, notes = dc.minlot_override_rows(_sleeves_file(tmp_path, [rows[USDNOK]]),
                                         frozenset({USDNOK}), pol=pol)
    assert got == [] and any("OVERRIDE_POLICY_REFUSED" in n for n in notes)


@pytest.mark.parametrize("change,flag", [
    ({"status": "KILL"}, "OVERRIDE_STATUS_REFUSED"),
    ({"status": "RETIRED", "retired_by": "decay_monitor"}, "OVERRIDE_STATUS_REFUSED"),
    ({"status": "QUARANTINED"}, "OVERRIDE_STATUS_REFUSED"),
    ({"status": "STANDBY", "standby_reason": "principal stop"}, "OVERRIDE_HOLD"),
    ({"certificate": {"cell": "external.USDNOK@M5.carry.p=d5391837ec28998b"}},
     "OVERRIDE_PIN_MISMATCH"),
    ({"exec": "scalp_market"}, "OVERRIDE_EXEC_REFUSED"),
])
def test_a_verdict_a_hold_or_a_wrong_pin_is_never_traded(tmp_path: Path, change: dict,
                                                         flag: str) -> None:
    row = {**_committed_rows()[USDNOK], **change}
    got, notes = dc.minlot_override_rows(_sleeves_file(tmp_path, [row]), frozenset({USDNOK}))
    assert got == [] and any(flag in n for n in notes), notes


def test_a_duplicate_or_missing_name_is_not_guessed(tmp_path: Path) -> None:
    row = _committed_rows()[USDNOK]
    got, notes = dc.minlot_override_rows(_sleeves_file(tmp_path, [row, dict(row)]),
                                         frozenset({USDNOK}))
    assert got == [] and "OVERRIDE_ROW_MISSING" in notes[0]
    got, notes = dc.minlot_override_rows(_sleeves_file(tmp_path, [_committed_rows()[TWINS[0]]]),
                                         frozenset({USDNOK}))
    assert got == [] and "OVERRIDE_ROW_MISSING" in notes[0]


def test_a_live_pinned_row_is_left_to_the_ordinary_roster(tmp_path: Path) -> None:
    row = {**_committed_rows()[USDNOK], "status": "LIVE"}
    assert dc.minlot_override_rows(_sleeves_file(tmp_path, [row]), frozenset({USDNOK})) \
        == ([], [])


# ------------------------------------------------------------------ the gateway door: the zeros

def test_gap_decay_nzdjpy_xau_scalp_and_usdjpy_never_reach_the_roster(tmp_path: Path) -> None:
    rows = _committed_rows()
    live = [{**rows[n], "status": "LIVE", "risk_frac": 0.1} for n in GAP_DECAY]
    live += [
        {"name": NZDJPY, "symbol": "NZDJPY", "family": "clock_transition", "selector": "asia",
         "exec": "family_market", "status": "LIVE", "risk_frac": 0.03},
        {"name": "xau_m5_anti_breakout_overlap", "symbol": "XAUUSD", "timeframe": "M5",
         "family": "anti_breakout", "exec": "scalp_market", "status": "LIVE", "risk_frac": 0.03},
        {"name": "USDJPY.asia#rr=2.5", "symbol": "USDJPY", "status": "LIVE", "risk_frac": 0.03},
        *({**rows[t], "status": "LIVE", "risk_frac": 0.03} for t in TWINS if t in rows),
    ]
    kept, notes = dc.load_sleeves_verbose(_sleeves_file(tmp_path, live))
    assert kept == [], [r["name"] for r in kept]
    assert len(notes) == len(live)
    # ... and none of them can be appended by the override either.
    got, _ = dc.minlot_override_rows(_sleeves_file(tmp_path, live), frozenset(FOUR))
    assert got == []


# ------------------------------------------------------------------ the gateway: one order at 0.01

def _family_ns(tmp_path, monkeypatch, multiplier=1.0):
    rows = adapter._rows()
    venue = adapter._fake_mt5(rows)
    ns = adapter._family_ns(tmp_path, venue, monkeypatch, armed_file=True,
                            sig_hour=adapter._sig_hour(rows))
    ns["promoted_lot"] = dc.promoted_lot
    fake_leg = SimpleNamespace(multiplier=lambda *a, **k: (1.0, "neutral"),
                               already_held=lambda *a, **k: 0)
    fake_macro = SimpleNamespace(multiplier=lambda *a, **k: (multiplier, "synthetic"))
    for name, module in (("leg_balance", fake_leg), ("macro_view", fake_macro)):
        monkeypatch.setitem(sys.modules, f"mt5desk.{name}", module)
        monkeypatch.setattr(mt5desk, name, module, raising=False)
    return ns, venue


def _fx_sleeve(name: str, **over) -> dict:
    # A POSITIVE allocator-book fraction: the book sizes it (an allocator zero sends nothing,
    # pinned below). Tiny on purpose -- sovereign alone it is sub-minimum at EUR 485.
    row = {"risk_frac": 0.001, "sized_by": "allocator_book", **over}
    return adapter._sleeve(name=name, symbol=SYMBOL_OF.get(name, "NZDJPY"), **row)


@pytest.mark.parametrize("name", FX)
@pytest.mark.parametrize("multiplier", [1.0, 1.4])
def test_each_fx_name_sends_exactly_one_001_order_per_signal(tmp_path, monkeypatch, name,
                                                             multiplier) -> None:
    ns, venue = _family_ns(tmp_path, monkeypatch, multiplier)
    st = {"armed": True}
    sleeve = _fx_sleeve(name)
    dc.stamp_minlot_override([sleeve], frozenset(FOUR), EQUITY)
    adapter._run_family(ns, st, [sleeve], EQUITY)
    (req,) = venue.sent
    # At EUR 485 the 0.75% target is below the floor: 0.01, and a 1.4x macro boost is clipped
    # back to the book's own lot (`min`), never lifted past it.
    assert req["volume"] == 0.01
    adapter._run_family(ns, st, [sleeve], EQUITY)
    assert len(venue.sent) == 1, "one order per signal"


@pytest.mark.parametrize("name", FX)
def test_an_allocator_zero_on_a_marked_fx_name_sends_nothing(tmp_path, monkeypatch, name) -> None:
    ns, venue = _family_ns(tmp_path, monkeypatch)
    sleeve = _fx_sleeve(name, risk_frac=0.0)
    dc.stamp_minlot_override([sleeve], frozenset(FOUR), EQUITY)
    assert sleeve.get("minlot_override") is True
    adapter._run_family(ns, {"armed": True}, [sleeve], EQUITY)
    assert venue.sent == []


@pytest.mark.parametrize("name", [*FX, NZDJPY])
def test_without_the_mark_sovereignty_sends_nothing(tmp_path, monkeypatch, name) -> None:
    ns, venue = _family_ns(tmp_path, monkeypatch)
    sleeve = _fx_sleeve(name, risk_frac=0.0)                       # the allocator's zero
    dc.stamp_minlot_override([sleeve], frozenset(), EQUITY)        # override file absent
    adapter._run_family(ns, {"armed": True}, [sleeve], EQUITY)
    assert venue.sent == []


def test_a_seventh_name_cannot_ride_the_override(tmp_path, monkeypatch) -> None:
    ns, venue = _family_ns(tmp_path, monkeypatch)
    sleeve = _fx_sleeve(NZDJPY, minlot_override=True)             # mark forged by hand
    adapter._run_family(ns, {"armed": True}, [sleeve], EQUITY)
    assert venue.sent == []
    sleeve = _fx_sleeve(NZDJPY)
    dc.stamp_minlot_override([sleeve], frozenset(FOUR | {NZDJPY}), EQUITY)
    assert "minlot_override" not in sleeve


def _bracket_ns() -> dict:
    return adapter._exec(("bracket_lane_lot", "promoted_lot"),
                         {"sleeve_live_n": lambda name: 0})


def test_every_gold_window_sends_the_book_lot() -> None:
    ns = _bracket_ns()
    sleeves = [{"name": f"gold_{w[0]}", "symbol": "XAUUSD", "lot": "auto",
                "sized_by": "allocator_book", "risk_frac": 0.001} for w in dc.GOLD_WINDOWS]
    assert {s["name"] for s in sleeves} == GOLDS
    dc.stamp_minlot_override(sleeves, frozenset(FOUR), EQUITY)
    for s in sleeves:
        lot, basis = ns["bracket_lane_lot"](s, EQUITY, 19.1, None)
        assert lot == 0.01 and basis.startswith("fusion book") and "0.01 floor" in basis
        assert s["fusion_book_target"] == 0.0                     # the floor lift is billable
    # At a larger equity the book sizes 0.75% at the stop, whatever the allocator's fraction.
    big = {**sleeves[0], "risk_frac": 0.10}
    dc.stamp_minlot_override([big], frozenset(FOUR), 50_000.0)
    assert ns["bracket_lane_lot"](big, 50_000.0, 19.1, None)[0] \
        == _size("gold_asia", "XAUUSD", None, 50_000.0, 19.1)[0] > 0.01
    # An allocator zero sends nothing even on a marked window.
    zero = {**sleeves[0], "risk_frac": 0.0}
    dc.stamp_minlot_override([zero], frozenset(FOUR), EQUITY)
    assert ns["bracket_lane_lot"](zero, EQUITY, 19.1, None)[0] == 0.0
    # A file that narrows to gold_asia leaves the other two windows sovereign (sub-minimum).
    dc.stamp_minlot_override(sleeves, frozenset({GOLD}), EQUITY)
    lots = {s["name"]: ns["bracket_lane_lot"](s, EQUITY, 19.1, None)[0] for s in sleeves}
    assert lots == {"gold_asia": 0.01, "gold_london_am": 0.0, "gold_afternoon": 0.0}
    # Override off: every window is sovereign again (sub-minimum at 485 -> no order).
    dc.stamp_minlot_override(sleeves, frozenset(), EQUITY)
    assert all(ns["bracket_lane_lot"](s, EQUITY, 19.1, None)[0] == 0.0 for s in sleeves)


def test_the_gateway_roster_appends_the_three_and_marks_the_six(tmp_path, monkeypatch) -> None:
    rows = _committed_rows()
    pool = [rows[n] for n in (*FX, *TWINS, *GAP_DECAY) if n in rows]
    logs: list[str] = []
    acc = SimpleNamespace(login=LOGIN, server=SERVER, trade_mode=2)          # real money
    venue = SimpleNamespace(account_info=lambda: acc)
    ns = adapter._exec(("minlot_override_roster",),
                       {"mt5": venue, "log": logs.append, "_prov": _prov,
                        "SLEEVES_FILE": _sleeves_file(tmp_path, pool)})
    base, _ = dc.roster({}, [])
    monkeypatch.setattr(dc, "MINLOT_OVERRIDE_FILE", _override_file(tmp_path))
    out = ns["minlot_override_roster"]([dict(s) for s in base], EQUITY)
    names = [s["name"] for s in out]
    assert sorted(n for n in names if not n.startswith("gold_")) == sorted(FX)
    assert len(names) == len(set(names))
    assert {s["name"] for s in out if s.get("minlot_override")} == FOUR
    assert all(s.get("exec") == "family_market" for s in out if s["name"] in FX)
    # Off on another login: nothing appended, nothing marked.
    acc.login = 1
    out = ns["minlot_override_roster"]([dict(s) for s in base], EQUITY)
    assert [s["name"] for s in out] == [s["name"] for s in base]
    assert not any(s.get("minlot_override") for s in out)
    # Absent file: the same.
    monkeypatch.setattr(dc, "MINLOT_OVERRIDE_FILE", tmp_path / "absent.json")
    out = ns["minlot_override_roster"]([dict(s) for s in base], EQUITY)
    assert not any(s.get("minlot_override") for s in out) and len(out) == len(base)


def test_no_organ_writes_the_switch() -> None:
    hits = []
    for root in ("desks/mt5", "libs", "scripts", "research"):
        for path in (_ROOT / root).rglob("*.py"):
            if "tests" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "MINLOT_OVERRIDE.json" in text or "MINLOT_OVERRIDE_FILE" in text:
                hits.append(path.relative_to(_ROOT).as_posix())
    # The core reads it; the gateway only names it in a log/basis line. Nothing else may.
    assert sorted(hits) == ["desks/mt5/mt5desk/decision_core.py",
                            "desks/mt5/mt5desk/gateway.py"], hits
    for line in (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8").splitlines():
        if "MINLOT_OVERRIDE" in line:
            assert not any(w in line for w in ("write_text", "json.dump", "os.replace"))
    src = (_DESK / "mt5desk" / "decision_core.py").read_text(encoding="utf-8")
    block = src[src.index("MINLOT_OVERRIDE_FILE ="):src.index("def ramped_fraction")]
    for writer in ("write_text", "json.dump(", "os.replace", ".open("):
        assert writer not in block


# ------------------------------------------------------------ one gold trade at risk at a time

def _pos(kind: int, entry: float, sl: float, symbol: str = "XAUUSD", ticket: int = 1):
    return SimpleNamespace(symbol=symbol, type=kind, price_open=entry, sl=sl, ticket=ticket)


def _ord(comment: str, symbol: str = "XAUUSD", ticket: int = 7):
    return SimpleNamespace(symbol=symbol, comment=comment, ticket=ticket)


def test_a_flat_gold_book_lets_the_window_place() -> None:
    assert dc.gold_at_risk_block([], [], own_tag="DWgold_london_am") is None
    # Other symbols never block gold.
    assert dc.gold_at_risk_block([_pos(0, 1.10, 0.0, symbol="EURZAR")],
                                 [_ord("DWx", symbol="USDNOK")], own_tag="DWgold_asia") is None


@pytest.mark.parametrize("pos", [
    _pos(0, 2400.0, 2390.0),          # buy, stop below entry
    _pos(1, 2400.0, 2410.0),          # sell, stop above entry
    _pos(0, 2400.0, 0.0),             # no stop at all
    _pos(1, 2400.0, 0.0),
])
def test_an_earlier_gold_position_still_at_risk_blocks(pos) -> None:
    why = dc.gold_at_risk_block([pos], [], own_tag="DWgold_london_am")
    assert why and "at risk" in why


@pytest.mark.parametrize("pos", [
    _pos(0, 2400.0, 2400.0), _pos(0, 2400.0, 2405.0),     # buy at / above break-even
    _pos(1, 2400.0, 2400.0), _pos(1, 2400.0, 2395.0),     # sell at / below break-even
])
def test_a_break_even_ratcheted_position_does_not_block(pos) -> None:
    assert dc.gold_at_risk_block([pos], [], own_tag="DWgold_afternoon") is None


def test_an_earlier_windows_resting_bracket_blocks_but_its_own_does_not() -> None:
    why = dc.gold_at_risk_block([], [_ord("DWgold_asia")], own_tag="DWgold_london_am")
    assert why and "pending order" in why
    assert dc.gold_at_risk_block([], [_ord("DWgold_london_am")],
                                 own_tag="DWgold_london_am") is None


@pytest.mark.parametrize("positions,orders", [
    (None, []), ([], None), (None, None), (5, []),
    ([SimpleNamespace(symbol="XAUUSD", ticket=3)], []),           # side/prices unreadable
    ([_pos(7, 2400.0, 2400.0)], []),                               # unknown side
])
def test_unreadable_positions_or_orders_fail_closed(positions, orders) -> None:
    assert dc.gold_at_risk_block(positions, orders, own_tag="DWgold_asia")


def test_the_gateway_reads_this_accounts_gold_book_and_fails_closed(tmp_path, monkeypatch) -> None:
    from mt5desk import config
    monkeypatch.setattr(config, "desk_root", lambda: tmp_path)     # no intents journal yet
    venue = SimpleNamespace(positions_get=lambda symbol=None: (_pos(0, 2400.0, 2390.0),),
                            orders_get=lambda symbol=None: ())
    ns = adapter._exec(("gold_one_at_risk", "order_comment"), {"mt5": venue})
    assert "at risk" in ns["gold_one_at_risk"]("gold_london_am")
    venue.positions_get = lambda symbol=None: (_pos(0, 2400.0, 2401.0),)
    assert ns["gold_one_at_risk"]("gold_london_am") is None
    venue.orders_get = lambda symbol=None: None                  # terminal error
    assert ns["gold_one_at_risk"]("gold_london_am")

    def boom(symbol=None):
        raise RuntimeError("IPC down")
    venue.positions_get = boom
    assert "fail closed" in ns["gold_one_at_risk"]("gold_afternoon")


def test_the_bracket_loop_consults_the_guard_for_gold_windows_only() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    main = src[src.index("\ndef main() -> None:"):]
    i = main.index('_gold_why = gold_one_at_risk(s["name"], _gold_placed_this_pass, day_key)')
    guard = main[i - 1200:i + 300]
    assert 's.get("lot") == "auto" and s.get("symbol") == GOLD_SYMBOL' in guard
    assert "NOT PLACED (one gold trade at risk)" in guard and "continue" in guard
    # It sits before the order is built and sent.
    assert i < main.index("place_bracket(st, spec")


def test_one_gold_is_as_strict_as_e8_this_pass_the_journal_and_unreadable_symbols() -> None:
    # A gold window placed earlier in THIS pass blocks the next, before the venue shows it.
    why = dc.gold_at_risk_block([], [], own_tag="DWgold_london_am",
                                placed_this_pass=["gold_asia"])
    assert why and "gold_asia" in why and "this pass" in why
    # A ticket journalled today for another window still resting blocks, whatever its comment.
    why = dc.gold_at_risk_block([], [_ord("DWgold_london_am", ticket=41)],
                                own_tag="DWgold_london_am", lane_tickets=[41])
    assert why and "journalled" in why
    # A journal that cannot be read fails closed; a position/order without a symbol is gold.
    assert dc.gold_at_risk_block([], [], own_tag="DWgold_asia", lane_tickets=None)
    assert dc.gold_at_risk_block([SimpleNamespace(symbol=None, ticket=3)], [],
                                 own_tag="DWgold_asia")
    assert dc.gold_at_risk_block([], [SimpleNamespace(symbol="", ticket=4)],
                                 own_tag="DWgold_asia")


def test_the_gateway_counts_todays_journalled_gold_tickets_and_fails_closed_on_a_bad_journal(
        tmp_path, monkeypatch) -> None:
    from mt5desk import config
    monkeypatch.setattr(config, "desk_root", lambda: tmp_path)
    (tmp_path / "data").mkdir()
    journal = tmp_path / "data" / "order_intents.jsonl"
    journal.write_text("\n".join(json.dumps(r) for r in (
        {"time": "2026-10-20T07:00:01", "sleeve": "gold_asia", "symbol": "XAUUSD", "ticket": 41},
        {"time": "2026-10-19T07:00:01", "sleeve": "gold_asia", "symbol": "XAUUSD", "ticket": 9},
    )) + "\n", encoding="utf-8")
    venue = SimpleNamespace(positions_get=lambda symbol=None: (),
                            orders_get=lambda symbol=None: (_ord("renamed", ticket=41),))
    ns = adapter._exec(("gold_one_at_risk", "order_comment"), {"mt5": venue})
    assert "journalled" in ns["gold_one_at_risk"]("gold_london_am", (), "2026-10-20")
    venue.orders_get = lambda symbol=None: (_ord("DWgold_london_am", ticket=9),)
    assert ns["gold_one_at_risk"]("gold_london_am", (), "2026-10-20") is None   # yesterday's
    assert "this pass" in ns["gold_one_at_risk"]("gold_afternoon", ["gold_asia"], "2026-10-20")
    journal.write_text("{not json\n", encoding="utf-8")
    assert "journal" in ns["gold_one_at_risk"]("gold_london_am", (), "2026-10-20")


# ------------------------------------------------------------------- the Fusion daily-loss rail

def test_the_daily_loss_rail_anchors_once_latches_and_resets_with_the_day() -> None:
    assert dc.FUSION_DAILY_LOSS_FRAC == 0.05                 # coordinator, audit round 2
    st: dict = {}
    assert dc.fusion_daily_loss(st, 500.0, "2026-10-20")[0] is False
    assert st["day_start_equity"] == {"date": "2026-10-20", "equity": 500.0}
    assert dc.fusion_daily_loss(st, 476.0, "2026-10-20")[0] is False     # above 475
    down, why = dc.fusion_daily_loss(st, 475.0, "2026-10-20")
    assert down and "rest of 2026-10-20" in why
    # Latched: a bounce back does not re-open the day; the next day re-anchors.
    assert dc.fusion_daily_loss(st, 520.0, "2026-10-20")[0] is True
    assert dc.fusion_daily_loss(st, 430.0, "2026-10-21")[0] is False
    assert st["day_start_equity"]["equity"] == 430.0


@pytest.mark.parametrize("equity", [None, "x", float("nan"), 0.0, -5.0])
def test_an_unreadable_equity_stands_the_pass_down_without_anchoring(equity) -> None:
    st: dict = {}
    down, why = dc.fusion_daily_loss(st, equity, "2026-10-20")
    assert down and "unreadable" in why and "day_start_equity" not in st


def test_the_gateway_wires_the_daily_loss_rail_before_any_new_risk() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    main = src[src.index("\ndef main() -> None:"):]
    i = main.index("fusion_daily_loss(st")
    assert "NEW_RISK_OK = False" in main[i:i + 1500]
    assert '_rails.line("fusion_daily_loss"' in main[i:i + 1500]
    assert i < main.index("place_bracket(st, spec")


# ------------------------------------------------------------- the cross-account opposite fence

from mt5desk import cross_account as xa  # noqa: E402
from mt5desk import fusion_rails  # noqa: E402


def test_exposure_reads_both_venues_and_raises_on_an_unreadable_row() -> None:
    mt5 = SimpleNamespace(
        positions_get=lambda: (SimpleNamespace(symbol="XAUUSD", type=1),),
        orders_get=lambda: (SimpleNamespace(symbol="EURZAR.pro", type=4),
                            SimpleNamespace(symbol="USDNOK", type=8)))       # close-by: no entry
    assert xa.mt5_exposure(mt5) == {"XAUUSD": {"long": False, "short": True},
                                    "EURZAR": {"long": True, "short": False}}
    with pytest.raises(ValueError):
        xa.mt5_exposure(SimpleNamespace(positions_get=lambda: None, orders_get=lambda: ()))
    with pytest.raises(ValueError):
        xa.exposure_from_rows([("XAUUSD", "flat")])
    venue = SimpleNamespace(_by_key={"XAUUSD": 6102, "USDNOK": 7})
    got = xa.tradelocker_exposure(
        venue, positions=[{"tradableInstrumentId": 6102, "side": "buy"}],
        orders=[{"tradableInstrumentId": 6102, "side": "sell"},             # its protective SL
                {"tradableInstrumentId": 7, "side": "sell", "stopLoss": 10.9}])
    assert got == {"XAUUSD": {"long": True, "short": False},
                   "USDNOK": {"long": False, "short": True}}
    with pytest.raises(ValueError):
        xa.tradelocker_exposure(venue, positions=[{"tradableInstrumentId": 99, "side": "buy"}],
                                orders=[])


def test_the_fence_blocks_only_the_opposite_side_and_fails_closed_on_any_unknown() -> None:
    xa.publish("e8", {"XAUUSD": {"long": False, "short": True}}, source="test",
               key=xa.account_key("e8-test", "tl"))
    book, _why = xa.read_book("e8")
    assert book is not None
    assert xa.opposite_block(book, "XAUUSD", "buy_stop", account="e8")
    assert xa.opposite_block(book, "XAUUSD+", 1, account="e8")
    assert xa.opposite_block(book, "XAUUSD", "sell_stop", account="e8") is None
    assert xa.opposite_block(book, "EURZAR", "buy", account="e8") is None
    assert "fail closed" in xa.opposite_block(book, "XAUUSD", "flat", account="e8")
    assert "fail closed" in xa.opposite_block(None, "EURZAR", "buy", account="e8",
                                              why_absent="gone")


def test_an_absent_stale_or_foreign_book_is_no_book(tmp_path) -> None:
    from datetime import UTC, datetime, timedelta
    xa.book_path("e8").unlink()
    assert xa.read_book("e8")[0] is None
    xa.publish("e8", {}, source="t", now=datetime.now(tz=UTC) - timedelta(seconds=1000),
               key=xa.account_key("e8-test", "tl"))
    book, why = xa.read_book("e8")
    assert book is None and "old" in why
    xa.book_path("e8").write_text(json.dumps({"account": "fusion", "covers": "all",
                                              "at": datetime.now(tz=UTC).isoformat(),
                                              "symbols": {}}), encoding="utf-8")
    assert xa.read_book("e8")[0] is None


def _foreign_lock(**doc) -> Path:
    lock = xa.XACCT_DIR / "placement.lock"
    lock.write_text(json.dumps({"holder": "other", "token": "t-other", **doc}), encoding="utf-8")
    return lock


def test_the_lock_is_reentrant_in_process_and_released_only_by_its_owner() -> None:
    lock = xa.XACCT_DIR / "placement.lock"
    with xa.placement_lock("a") as first:
        assert first and lock.exists()
        with xa.placement_lock("a-nested", wait_s=0.0) as nested:
            assert nested                                 # a publish inside a placement
        assert lock.exists()                              # the inner exit released nothing
    assert not lock.exists()
    # Release checks the token: a lock someone else holds now is never deleted by us.
    with xa.placement_lock("b") as got:
        assert got
        _foreign_lock(pid=os.getpid(), host=xa._HOST)
    assert lock.exists()


def test_a_live_foreign_holder_is_never_broken_however_old() -> None:
    lock = _foreign_lock(pid=os.getpid(), host=xa._HOST)            # alive: this process
    os.utime(lock, (1.0, 1.0))
    t0 = time.monotonic()
    with xa.placement_lock("me", wait_s=0.5) as got:
        assert not got
    assert 0.4 <= time.monotonic() - t0 < 5.0                        # waited, then gave up
    assert json.loads(lock.read_text())["token"] == "t-other"


def test_a_miss_makes_the_rest_of_the_pass_wait_nothing() -> None:
    _foreign_lock(pid=os.getpid(), host=xa._HOST)
    with xa.placement_lock("me", wait_s=0.3) as got:
        assert not got
    t0 = time.monotonic()
    with xa.placement_lock("me-again", wait_s=10.0) as got:
        assert not got
    assert time.monotonic() - t0 < 1.0


def test_a_dead_or_released_holder_is_broken() -> None:
    _foreign_lock(pid=2**22 + 12345, host=xa._HOST)                 # no such pid
    with xa.placement_lock("me", wait_s=1.0) as got:
        assert got
    xa._RELEASED.add("t-mine")
    lock = xa.XACCT_DIR / "placement.lock"
    lock.write_text(json.dumps({"token": "t-mine", "pid": os.getpid(), "host": xa._HOST}),
                    encoding="utf-8")
    with xa.placement_lock("me", wait_s=1.0) as got:
        assert got


def test_an_unprovable_holder_is_broken_only_when_abandoned() -> None:
    lock = _foreign_lock(pid=1, host="another-host")
    with xa.placement_lock("me", wait_s=0.0) as got:
        assert not got
    xa._MISSED_AT.clear()
    os.utime(lock, (1.0, 1.0))                                         # older than abandoned
    with xa.placement_lock("me", wait_s=0.5) as got:
        assert got


def test_a_break_the_os_refuses_waits_to_its_deadline_and_never_spins(monkeypatch) -> None:
    lock = _foreign_lock(pid=2**22 + 12345, host=xa._HOST)           # dead: breakable
    calls = []

    def refused(src, dst):                                             # WinError 32 / 5
        calls.append(src)
        raise PermissionError(32, "The process cannot access the file")
    monkeypatch.setattr(xa.os, "replace", refused)
    t0 = time.monotonic()
    with xa.placement_lock("me", wait_s=0.6) as got:
        assert not got
    took = time.monotonic() - t0
    assert 0.5 <= took < 5.0
    assert 1 <= len(calls) <= 10, len(calls)                           # slept between tries
    assert lock.exists()


def test_every_publish_runs_under_the_lock_from_a_fresh_read() -> None:
    _foreign_lock(pid=os.getpid(), host=xa._HOST)
    reads = []
    why = xa.publish_under_lock(lambda: reads.append(1), holder="t", wait_s=0.0)
    assert why and "not published" in why and reads == []
    src = {n: (_DESK / n).read_text(encoding="utf-8")
           for n in ("mt5desk/gateway.py", "prop/e8_gold.py", "prop/e8_executor.py")}
    # No publish from a snapshot: every site reads inside the call (publish_mt5 /
    # publish_tradelocker) and none passes an earlier positions/orders reading.
    for text in src.values():
        assert "_xa.publish(" not in text
        assert "tradelocker_exposure(venue, positions=" not in text
    assert "publish_under_lock(lambda: _xa.publish_mt5(mt5" in src["mt5desk/gateway.py"]
    assert "publish_under_lock(\n        lambda: _xa.publish_tradelocker(venue" \
        in src["prop/e8_executor.py"]
    assert src["prop/e8_gold.py"].count("_xa.publish_under_lock(") == 2


def test_a_family_order_opposite_an_e8_position_is_refused_and_billed(
        tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(fusion_rails, "LEDGER", tmp_path / "rails.jsonl")
    ns, venue = _family_ns(tmp_path, monkeypatch)
    sleeve = _fx_sleeve(USDNOK)                         # LONG
    dc.stamp_minlot_override([sleeve], frozenset(FOUR), EQUITY)
    xa.publish("e8", {"USDNOK": {"long": False, "short": True}}, source="test",
               key=xa.account_key("e8-test", "tl"))
    adapter._run_family(ns, {"armed": True}, [sleeve], EQUITY)
    assert venue.sent == []
    (row,) = [json.loads(ln) for ln in (tmp_path / "rails.jsonl").read_text().splitlines()]
    assert row["rail"] == "cross_account_opposite" and row["sleeve"] == USDNOK


def test_a_family_order_with_no_readable_e8_book_is_refused(tmp_path, monkeypatch) -> None:
    ns, venue = _family_ns(tmp_path, monkeypatch)
    sleeve = _fx_sleeve(USDNOK)
    dc.stamp_minlot_override([sleeve], frozenset(FOUR), EQUITY)
    xa.book_path("e8").unlink()
    adapter._run_family(ns, {"armed": True}, [sleeve], EQUITY)
    assert venue.sent == []
    assert any("fail closed" in ln for ln in ns["_logs"])


def test_a_same_side_e8_position_does_not_block_and_the_fusion_book_is_published(
        tmp_path, monkeypatch) -> None:
    ns, venue = _family_ns(tmp_path, monkeypatch)
    venue.positions_get = lambda *a, **k: ()
    venue.orders_get = lambda *a, **k: ()
    venue.account_info = lambda: SimpleNamespace(login=LOGIN, server=SERVER, trade_mode=2)
    sleeve = _fx_sleeve(USDNOK)
    dc.stamp_minlot_override([sleeve], frozenset(FOUR), EQUITY)
    xa.publish("e8", {"USDNOK": {"long": True, "short": False}}, source="test",
               key=xa.account_key("e8-test", "tl"))
    adapter._run_family(ns, {"armed": True}, [sleeve], EQUITY)
    assert len(venue.sent) == 1
    book, _ = xa.read_book("fusion")
    assert book is not None


def test_the_bracket_loop_fences_each_leg_under_the_lock_and_waits_when_both_are_fenced() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    main = src[src.index("\ndef main() -> None:"):]
    i = main.index('_xa.placement_lock(f"gateway:{s[\'name\']}")')
    j = main.index("res = place_bracket(st, spec", i)
    block = main[i:j]
    assert '_xa.read_book("e8")' in block and "opposite_block" in block
    assert '{"buy_stop", "sell_stop"} <= _all_blocked' in block and "continue" in block
    assert '_rails.line("cross_account_opposite"' in block
    assert '_xa.publish_mt5(mt5, source="gateway")' in main[j:j + 900]


def test_e8_executor_fences_its_send_against_the_fusion_book() -> None:
    src = (_DESK / "prop" / "e8_executor.py").read_text(encoding="utf-8")
    i = src.index("_xa.placement_lock(f\"e8_executor:")
    block = src[i:i + 2500]
    assert '_xa.read_book("fusion")' in block and "opposite_block" in block
    assert 'row["rail"] = "cross_account_opposite"' in block
    assert "missed_growth_risk_usd" in block
    assert '_xa.publish_tradelocker(venue, source="e8_executor")' in block


# --------------------------------------------------- E8-Gold: the same fence from the other side

def _e8_harness(monkeypatch, tmp_path, fusion_positions=(), fusion_orders=(),
                fusion_login=LOGIN):
    sys.path.insert(0, str(_DESK / "tests"))
    import test_e8_gold_guard_and_open_risk as h

    class _V(h._Venue):
        _by_key: ClassVar[dict[str, int]] = {"XAUUSD": 6102}

        def __init__(self) -> None:
            super().__init__()
            self.placed: list[tuple] = []
            self._raw_api = SimpleNamespace(acc_id=31337)

        def place_stop(self, symbol, side, lot, *, price, stop, take_profit):
            self.placed.append((side, lot))
            return 500 + len(self.placed)

    class _M(h._MT5):
        def account_info(self):
            return SimpleNamespace(login=fusion_login, server=SERVER, trade_mode=2)

        def positions_get(self, symbol=None):
            return fusion_positions

        def orders_get(self, symbol=None):
            return fusion_orders

    h._sandbox(monkeypatch, tmp_path)
    venue = _V()
    doc = h.g.run(venue, _M(), armed=True)
    intents = [json.loads(ln) for ln in (tmp_path / "intents.json").read_text().splitlines()
               if ln.strip()] if (tmp_path / "intents.json").exists() else []
    return doc, venue, intents


def test_e8_gold_places_both_legs_against_a_flat_fusion_book(monkeypatch, tmp_path) -> None:
    _doc, venue, _ = _e8_harness(monkeypatch, tmp_path)
    assert sorted(s for s, _ in venue.placed) == ["buy", "sell"]
    assert xa.read_book("e8")[0] is not None and xa.read_book("fusion")[0] == {}


def test_e8_gold_skips_the_leg_opposite_a_fusion_gold_short(monkeypatch, tmp_path) -> None:
    _doc, venue, intents = _e8_harness(monkeypatch, tmp_path, fusion_positions=(
        SimpleNamespace(symbol="XAUUSD", type=1),))
    assert [s for s, _ in venue.placed] == ["sell"]
    (blocked,) = [r for r in intents if r.get("status") == "RAIL_BLOCKED"]
    assert blocked["rail"] == "cross_account_opposite" and blocked["side"] == "buy_stop"
    assert blocked["missed_growth_risk_usd"] > 0


def test_e8_gold_waits_unplaced_when_fusion_rests_both_sides_or_cannot_be_read(
        monkeypatch, tmp_path) -> None:
    doc, venue, _ = _e8_harness(monkeypatch, tmp_path, fusion_orders=(
        SimpleNamespace(symbol="XAUUSD", type=4), SimpleNamespace(symbol="XAUUSD", type=5)))
    assert venue.placed == [] and doc["placed"] == []
    # Not marked placed: the next pass retries -- and an unreadable Fusion book fences it again.
    doc, venue, _ = _e8_harness(monkeypatch, tmp_path, fusion_positions=None)
    assert venue.placed == [] and doc["placed"] == []
    # And a terminal on another account than the declared Fusion one is no Fusion book.
    doc, venue, _ = _e8_harness(monkeypatch, tmp_path, fusion_login=LOGIN + 1)
    assert venue.placed == [] and doc["placed"] == []


# --------------------------------------------------------------------------- the rails' bill

def test_every_fusion_rail_publishes_its_bill_in_missed_growth(tmp_path, monkeypatch) -> None:
    from research import missed_growth as mg
    assert set(mg.FUSION_RAIL_NAMES) == set(fusion_rails.RAILS)
    monkeypatch.setattr(fusion_rails, "LEDGER", tmp_path / "rails.jsonl")
    monkeypatch.setattr(mg, "FUSION_RAILS", tmp_path / "rails.jsonl")
    monkeypatch.setattr(mg, "E8_INTENTS", tmp_path / "e8_gold_intents.jsonl")
    monkeypatch.setattr(mg, "E8_EXEC_INTENTS", tmp_path / "e8_intents.jsonl")
    out = mg.published_fusion_book_lines()
    # ABSENT IS NOT A CLEAN ZERO (L1.28a): no ledger on this machine reads UNMEASURED.
    assert all(v["verdict"] == mg.UNMEASURED for v in out["rails"].values())
    assert fusion_rails.ensure()
    for name in ("e8_gold_intents.jsonl", "e8_intents.jsonl"):
        (tmp_path / name).write_text("", encoding="utf-8")
    out = mg.published_fusion_book_lines()
    assert all(v["verdict"] == mg.NOT_BINDING for v in out["rails"].values())
    # A missing E8 ledger blinds only the rail it feeds.
    (tmp_path / "e8_intents.jsonl").unlink()
    out = mg.published_fusion_book_lines()["rails"]
    assert out["cross_account_opposite"]["verdict"] == mg.UNMEASURED
    assert out["one_gold_at_risk"]["verdict"] == mg.NOT_BINDING
    (tmp_path / "e8_intents.jsonl").write_text("", encoding="utf-8")
    fusion_rails.line("one_gold_at_risk", sleeve="gold_london_am", lot=0.01, risk_frac=0.034)
    fusion_rails.line("fusion_book_floor_lift", sleeve="gold_asia", lot=0.01, risk_frac=0.034)
    (tmp_path / "e8_gold_intents.jsonl").write_text(json.dumps(
        {"status": "RAIL_BLOCKED", "rail": "cross_account_opposite",
         "missed_growth_risk_usd": 750.0}) + "\n", encoding="utf-8")
    out = mg.published_fusion_book_lines()["rails"]
    assert out["one_gold_at_risk"]["verdict"] == mg.UNMEASURED
    assert out["one_gold_at_risk"]["risk_frac_total"] == 0.034
    assert out["cross_account_opposite"]["n_e8"] == 1
    assert out["cross_account_opposite"]["e8_undeployed_risk_usd"] == 750.0
    assert out["fusion_daily_loss"]["verdict"] == mg.NOT_BINDING
    (tmp_path / "rails.jsonl").write_text("{broken\n", encoding="utf-8")
    assert "unreadable" in mg.published_fusion_book_lines()


# ----------------------------------------------------------------------- audit round 2 (r4)

@pytest.mark.parametrize("raw", ["XAUUSD", "XAUUSD+", "XAUUSD.pro", "XAUUSD_i", "XAUUSD#",
                                 "XAUUSDm", "XAUUSDpro", "GOLD", "gold", "xau/usd", "XAU/USD"])
def test_every_alias_of_gold_is_gold(raw) -> None:
    assert xa.norm(raw) == "XAUUSD"


def test_an_unknown_suffix_blocks_rather_than_passes() -> None:
    book = {"XAUUSDX": {"long": False, "short": True}}
    assert xa.opposite_block(book, "XAUUSD", "buy", account="e8")
    assert xa.opposite_block({"XAUUSD": {"long": False, "short": True}}, "XAUUSDX", "buy",
                             account="e8")
    assert xa.opposite_block(book, "EURUSD", "buy", account="e8") is None
    with pytest.raises(ValueError):
        xa.exposure_from_rows([("??", "buy")])
    assert "fail closed" in xa.opposite_block({}, "", "buy", account="e8")


def test_a_tradelocker_entry_without_a_stop_counts_and_only_named_protection_is_skipped() -> None:
    venue = SimpleNamespace(_by_key={"XAUUSD": 6102})
    pos = [{"id": 1, "tradableInstrumentId": 6102, "side": "buy", "stopLossId": 11,
            "takeProfitId": 12}]
    orders = [{"id": 11, "tradableInstrumentId": 6102, "side": "sell"},       # its SL
              {"id": 12, "tradableInstrumentId": 6102, "side": "sell"}]       # its TP
    assert xa.tradelocker_exposure(venue, positions=pos, orders=orders) == {
        "XAUUSD": {"long": True, "short": False}}
    # A resting entry with NO stopLoss is an entry (round 2 skipped it: fail open).
    got = xa.tradelocker_exposure(venue, positions=[], orders=[
        {"id": 13, "tradableInstrumentId": 6102, "side": "sell"}])
    assert got == {"XAUUSD": {"long": False, "short": True}}
    # An order that names its position is protective too.
    got = xa.tradelocker_exposure(venue, positions=[{"id": 2, "tradableInstrumentId": 6102,
                                                     "side": "sell"}],
                                  orders=[{"id": 14, "tradableInstrumentId": 6102,
                                           "side": "buy", "positionId": 2}])
    assert got == {"XAUUSD": {"long": False, "short": True}}


def test_a_book_names_its_account_hashed_and_a_wrong_or_unnamed_one_is_refused() -> None:
    key = xa.account_key(LOGIN, SERVER)
    assert key.startswith("sha256:") and str(LOGIN) not in key
    xa.publish("fusion", {}, source="t", key=key)
    assert str(LOGIN) not in xa.book_path("fusion").read_text(encoding="utf-8")
    assert xa.read_book("fusion")[0] == {}                     # the declared account
    xa.publish("fusion", {}, source="t", key=xa.account_key(LOGIN + 1, SERVER))
    book, why = xa.read_book("fusion")
    assert book is None and "another account" in why
    with pytest.raises(ValueError):
        xa.publish("fusion", {}, source="t", key="")
    doc = json.loads(xa.book_path("fusion").read_text(encoding="utf-8"))
    doc.pop("account_key")
    xa.book_path("fusion").write_text(json.dumps(doc), encoding="utf-8")
    assert xa.read_book("fusion")[0] is None
    with pytest.raises(ValueError):
        xa.account_key(None, SERVER)


def test_the_e8_gold_retry_goes_through_the_fence_and_the_lock() -> None:
    from prop import e8_gold as g
    src = (_DESK / "prop" / "e8_gold.py").read_text(encoding="utf-8")
    body = src[src.index("def _retry_failed_legs("):src.index("def connect_terminal(")]
    assert "fenced_send(mt5, venue, doc" in body and "venue.place_stop(" in body
    assert body.index("fenced_send(") < body.index("venue.place_stop(")
    assert "_xa_retry_blocked(" in body
    sent: list[int] = []
    m = SimpleNamespace(account_info=lambda: SimpleNamespace(login=LOGIN, server=SERVER),
                        positions_get=lambda: (SimpleNamespace(symbol="XAUUSD", type=1),),
                        orders_get=lambda: ())
    v = SimpleNamespace(_by_key={"XAUUSD": 6102}, _raw_api=SimpleNamespace(acc_id=7),
                        positions=lambda: [], orders=lambda: [])
    doc: dict = {}
    res, why = g.fenced_send(m, v, doc, holder="t", side="buy_stop",
                             send=lambda: sent.append(1) or 99)
    assert res is None and why and "short" in why and sent == []
    res, why = g.fenced_send(m, v, doc, holder="t", side="sell_stop",
                             send=lambda: sent.append(1) or 99)
    assert (res, why) == (99, None) and sent == [1]
    assert xa.read_book("e8")[0] == {}                         # republished under the lock
    m.positions_get = lambda: None                              # Fusion unreadable
    assert g.fenced_send(m, v, doc, holder="t", side="sell_stop", send=lambda: 1)[0] is None
    _foreign_lock(pid=os.getpid(), host=xa._HOST)
    m.positions_get = lambda: ()
    res, why = g.fenced_send(m, v, doc, holder="t", side="sell_stop", send=lambda: 1)
    assert res is None and "lock" in why and doc["xacct_lock_missed"] is True


def test_no_entry_risks_more_than_ten_percent_and_each_refusal_is_billed_once(
        tmp_path, monkeypatch) -> None:
    assert dc.FUSION_MAX_TRADE_RISK_FRAC == 0.10
    monkeypatch.setattr(dc, "MAX_RISK_FRAC", 0.50)              # even a wider envelope
    lot, _t, why = _size("gold_afternoon", "XAUUSD", None, EQUITY, 111.0)
    assert lot == 0.0 and why.startswith(dc.FUSION_TRADE_RISK_REFUSAL)
    monkeypatch.setattr(fusion_rails, "LEDGER", tmp_path / "rails.jsonl")
    ns = _bracket_ns()
    s = {"name": "gold_afternoon", "symbol": "XAUUSD", "lot": "auto"}
    dc.stamp_minlot_override([s], frozenset(FOUR), EQUITY)
    for _ in range(3):                                          # re-checked every pass
        assert ns["bracket_lane_lot"](s, EQUITY, 111.0, None)[0] == 0.0
    rows = [json.loads(ln) for ln in (tmp_path / "rails.jsonl").read_text().splitlines()]
    assert [r["rail"] for r in rows] == ["fusion_trade_risk_cap"]
    assert rows[0]["sleeve"] == "gold_afternoon" and rows[0]["dist"] == 111.0
    # A stop the cap allows sends, and writes no refusal.
    assert ns["bracket_lane_lot"](s, EQUITY, 19.1, None)[0] == 0.01


def test_the_terminal_volume_min_is_honoured_when_its_tick_value_is_not() -> None:
    info = SimpleNamespace(volume_min=0.1, volume_step=0.01, volume_max=100.0,
                           trade_tick_size=None, trade_tick_value=None)
    lot, _t, why = _size("gold_asia", "XAUUSD", info, EQUITY, 19.1)
    assert lot == 0.0 and "venue minimum" in why


def test_a_rails_line_that_cannot_be_written_is_surfaced(tmp_path, monkeypatch, capsys) -> None:
    (tmp_path / "blocker").write_text("x", encoding="utf-8")
    monkeypatch.setattr(fusion_rails, "LEDGER", tmp_path / "blocker" / "rails.jsonl")
    monkeypatch.setattr(fusion_rails, "WRITE_FAILURES", {})
    assert fusion_rails.line("one_gold_at_risk", sleeve="gold_asia") is False
    assert fusion_rails.WRITE_FAILURES == {"one_gold_at_risk": 1}
    assert "NOT written" in capsys.readouterr().err
    assert fusion_rails.ensure() is False
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    assert "_rails_pass.WRITE_FAILURES" in src and "_rails_pass.ensure()" in src

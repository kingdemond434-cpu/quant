"""The principal's Fusion minimum-lot book (zuck, BOOKS_PATCH v5, approved 2026-10-13).

    python -m pytest desks/mt5/tests/test_fusion_minlot_book.py -q

The live Fusion account trades exactly FOUR sleeves, each at a FIXED 0.01 lot, and nothing else:
gold_asia, usdnok_carry_asia_p_ff35bb7c8427d66f, eurils_formula_asia_p_673857a649d3c271 and
eurzar_carry_asia_p_8339edce23032d21. The three overnight_gap_decay principal rows, NZDJPY, the
XAU m5 scalp and USDJPY send nothing. Pinned here:

  * one order per signal at exactly 0.01 for each of the three FX names (RETIRED in sleeves.json,
    exactly as on origin) and gold_asia's lot is exactly 0.01;
  * 0 orders for NZDJPY, XAU m5, USDJPY and the three gap_decay rows;
  * a fifth name cannot ride the override, and the file can only narrow the code's set;
  * an absent / unreadable / disabled / wrong-typed file is NO override;
  * nothing the override sizes exceeds 0.01.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mt5desk  # noqa: E402
import test_gateway_adapter as adapter  # noqa: E402
from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import live_policy  # noqa: E402
from mt5desk import provenance as _prov  # noqa: E402

GOLD = "gold_asia"
USDNOK = "usdnok_carry_asia_p_ff35bb7c8427d66f"
EURILS = "eurils_formula_asia_p_673857a649d3c271"
EURZAR = "eurzar_carry_asia_p_8339edce23032d21"
FOUR = {GOLD, USDNOK, EURILS, EURZAR}
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


def _override_file(tmp_path: Path, **doc) -> Path:
    body = {"enabled": True, "lot": 0.01, "sleeves": sorted(FOUR), **doc}
    p = tmp_path / "MINLOT_OVERRIDE.json"
    p.write_text(json.dumps(body), encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _sovereign(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dc, "ALLOCATOR_SOVEREIGN", True)
    monkeypatch.setattr(dc, "ALLOCATOR_SOVEREIGN_FILE", tmp_path / "ALLOCATOR_SOVEREIGN.json")
    monkeypatch.setattr(dc, "MIN_LOT_FILE", tmp_path / "MIN_LOT.json")


# ------------------------------------------------------------------ the set and the switch

def test_the_code_names_exactly_the_four_and_pins_each_certificate() -> None:
    assert dc.MINLOT_OVERRIDE_SLEEVES == FOUR
    assert dc.MINLOT_OVERRIDE_LOT == 0.01
    assert dc.MINLOT_OVERRIDE_PINS == {
        GOLD: None,
        USDNOK: "external.USDNOK@M5.carry.p=ff35bb7c8427d66f",
        EURILS: "external.EURILS.formula.p=673857a649d3c271",
        EURZAR: "external.EURZAR@M15.carry.p=8339edce23032d21"}
    for name in (*TWINS, *GAP_DECAY, NZDJPY, "xau_m5_anti_breakout_overlap", "gold_london_am",
                 "gold_afternoon"):
        assert name not in dc.MINLOT_OVERRIDE_SLEEVES


def test_the_committed_switch_turns_on_exactly_the_four() -> None:
    active, why = dc.minlot_override_active(None)
    assert active == FOUR, why


def test_an_absent_file_is_no_override(tmp_path: Path) -> None:
    active, why = dc.minlot_override_active(None, tmp_path / "absent.json")
    assert active == frozenset() and "off" in why


@pytest.mark.parametrize("doc", [
    {"enabled": False},
    {"enabled": "true"},
    {"lot": 0.02},
    {"lot": "0.01"},
    {"lot": True},
    {"sleeves": {}},
    {"sleeves": "gold_asia"},
    {"account": "12345"},
    {"account": 999},
])
def test_wrong_values_or_types_fail_closed(tmp_path: Path, doc: dict) -> None:
    active, why = dc.minlot_override_active(12345, _override_file(tmp_path, **doc))
    assert active == frozenset(), why


def test_garbage_and_non_dict_files_fail_closed(tmp_path: Path) -> None:
    for text in ("{not json", "[]", "null", '"enabled"'):
        p = tmp_path / "MINLOT_OVERRIDE.json"
        p.write_text(text, encoding="utf-8")
        assert dc.minlot_override_active(None, p)[0] == frozenset()


def test_the_account_binding_holds_when_the_file_names_one(tmp_path: Path) -> None:
    p = _override_file(tmp_path, account=12345)
    assert dc.minlot_override_active(12345, p)[0] == FOUR
    assert dc.minlot_override_active(None, p)[0] == frozenset()
    assert dc.minlot_override_active(54321, p)[0] == frozenset()
    assert "ACCOUNT_MISMATCH" in dc.minlot_override_active(54321, p)[1]


def test_the_file_can_only_narrow_the_code_set(tmp_path: Path) -> None:
    p = _override_file(tmp_path, sleeves=[USDNOK, NZDJPY, TWINS[0], 7, "gold_london_am"])
    active, why = dc.minlot_override_active(None, p)
    assert active == {USDNOK}
    assert NZDJPY in why and "ignored" in why


# ------------------------------------------------------------------ the mark and the lot

def test_only_named_and_active_entries_are_marked_and_a_written_mark_is_popped() -> None:
    rows = [{"name": n} for n in (*FOUR, NZDJPY, "gold_london_am", "gold_afternoon")]
    rows[-1]["minlot_override"] = True           # a mark arriving from a file is not authority
    dc.stamp_minlot_override(rows, frozenset(FOUR), EQUITY)
    assert {r["name"] for r in rows if r.get("minlot_override")} == FOUR
    dc.stamp_minlot_override(rows, frozenset({GOLD}), EQUITY)
    assert {r["name"] for r in rows if r.get("minlot_override")} == {GOLD}


def test_below_the_ruin_line_nothing_is_marked() -> None:
    rows = [{"name": n} for n in FOUR]
    notes = dc.stamp_minlot_override(rows, frozenset(FOUR), dc.PROMOTED_MIN_EQUITY - 1)
    assert not any(r.get("minlot_override") for r in rows) and len(notes) == 4
    dc.stamp_minlot_override(rows, frozenset(FOUR), float("nan"))
    assert not any(r.get("minlot_override") for r in rows)


def test_the_lot_is_exactly_the_venue_minimum_and_never_more() -> None:
    info = SimpleNamespace(volume_min=0.01, volume_step=0.01, trade_tick_size=0.00001,
                           trade_tick_value=1.0)
    for name in FOUR:
        assert dc.minlot_override_lot({"name": name, "minlot_override": True}, "EURZAR",
                                      info) == 0.01
        assert dc.minlot_override_lot({"name": name}, "EURZAR", info) is None
    # A fifth name with the mark set by hand still gets none.
    assert dc.minlot_override_lot({"name": NZDJPY, "minlot_override": True}, "NZDJPY",
                                  info) is None
    # A venue that cannot take exactly 0.01 gets 0.0 (no order), never a larger lot.
    for vmin, step in ((0.1, 0.1), (0.01, 0.02)):
        coarse = SimpleNamespace(volume_min=vmin, volume_step=step, trade_tick_size=0.00001,
                                 trade_tick_value=1.0)
        assert dc.minlot_override_lot({"name": USDNOK, "minlot_override": True}, "USDNOK",
                                      coarse) == 0.0


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
    return adapter._sleeve(name=name, symbol=SYMBOL_OF.get(name, "NZDJPY"), risk_frac=0.0,
                           sized_by="allocator_book", **over)


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
    assert req["volume"] == 0.01
    adapter._run_family(ns, st, [sleeve], EQUITY)
    assert len(venue.sent) == 1, "one order per signal"


@pytest.mark.parametrize("name", [*FX, NZDJPY])
def test_without_the_mark_sovereignty_sends_nothing(tmp_path, monkeypatch, name) -> None:
    ns, venue = _family_ns(tmp_path, monkeypatch)
    sleeve = _fx_sleeve(name)
    dc.stamp_minlot_override([sleeve], frozenset(), EQUITY)        # override file absent
    adapter._run_family(ns, {"armed": True}, [sleeve], EQUITY)
    assert venue.sent == []


def test_a_fifth_name_cannot_ride_the_override(tmp_path, monkeypatch) -> None:
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


def test_gold_asia_sends_exactly_001_and_the_other_windows_stay_sovereign() -> None:
    ns = _bracket_ns()
    sleeves = [{"name": f"gold_{w[0]}", "symbol": "XAUUSD", "lot": "auto",
                "sized_by": "allocator_book", "risk_frac": 0.0} for w in dc.GOLD_WINDOWS]
    dc.stamp_minlot_override(sleeves, frozenset(FOUR), EQUITY)
    lots = {s["name"]: ns["bracket_lane_lot"](s, EQUITY, 19.1, None) for s in sleeves}
    assert lots[GOLD][0] == 0.01 and lots[GOLD][1].startswith("minlot_override")
    assert lots["gold_london_am"][0] == 0.0 and lots["gold_afternoon"][0] == 0.0
    # Even an allocator fraction that would size gold above 0.01 sends exactly 0.01.
    big = {**sleeves[0], "risk_frac": 0.10}
    dc.stamp_minlot_override([big], frozenset(FOUR), 50_000.0)
    assert ns["bracket_lane_lot"](big, 50_000.0, 19.1, None)[0] == 0.01
    # Override off: gold_asia is sovereign again (sub-minimum at 485 -> no order).
    dc.stamp_minlot_override(sleeves, frozenset(), EQUITY)
    assert ns["bracket_lane_lot"](sleeves[0], EQUITY, 19.1, None)[0] == 0.0


def test_the_gateway_roster_appends_the_three_and_marks_the_four(tmp_path, monkeypatch) -> None:
    rows = _committed_rows()
    pool = [rows[n] for n in (*FX, *TWINS, *GAP_DECAY) if n in rows]
    logs: list[str] = []
    venue = SimpleNamespace(account_info=lambda: SimpleNamespace(login=12345, server="x",
                                                                 trade_mode=0))
    ns = adapter._exec(("minlot_override_roster",),
                       {"mt5": venue, "log": logs.append, "_prov": _prov,
                        "SLEEVES_FILE": _sleeves_file(tmp_path, pool)})
    base, _ = dc.roster({}, [])
    monkeypatch.setattr(dc, "MINLOT_OVERRIDE_FILE", _override_file(tmp_path, account=12345))
    out = ns["minlot_override_roster"]([dict(s) for s in base], EQUITY)
    names = [s["name"] for s in out]
    assert sorted(n for n in names if not n.startswith("gold_")) == sorted(FX)
    assert len(names) == len(set(names))
    assert {s["name"] for s in out if s.get("minlot_override")} == FOUR
    assert all(s.get("exec") == "family_market" for s in out if s["name"] in FX)
    # Off on another login: nothing appended, nothing marked.
    monkeypatch.setattr(dc, "MINLOT_OVERRIDE_FILE", _override_file(tmp_path, account=1))
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
    assert hits == ["desks/mt5/mt5desk/decision_core.py"], hits
    src = (_DESK / "mt5desk" / "decision_core.py").read_text(encoding="utf-8")
    block = src[src.index("MINLOT_OVERRIDE_FILE ="):src.index("def ramped_fraction")]
    for writer in ("write_text", "json.dump(", "os.replace", ".open("):
        assert writer not in block

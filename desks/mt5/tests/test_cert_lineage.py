"""Certificate lineage of every live window (2026-10-20; v3 after audit CERT_LINEAGE_1b89d5176).

Pins: lineage is IDENTITY -- a gold window is RESOLVED only to a certificate whose cell is the
bracket the gateway trades (`params["as_traded"]` equal to gold_window_params.traded_params);
every join is judged, a unique one included (M1); a certificate on the window that is not the
traded cell is NEAREST_CERT with its differing fields, and NEAREST_CERT is not lineage (M2); the
fence enumerates every gold window decision_core.roster emits (M3); a held-back certificate keeps
its name (PENDING_REJUDGE, not UNRESOLVED); explicit fields are cross-checked and the module's own
`cert_id` is never read back as one; stamping is additive; the report is written only on the box
or to an explicit --out; the fence fails only with --require-state on the trading box.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import cert_lineage as cl  # noqa: E402

_SPEC = importlib.util.spec_from_file_location("check_cert_lineage",
                                               ROOT / "scripts" / "check_cert_lineage.py")
assert _SPEC and _SPEC.loader
FENCE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(FENCE)


def _cert(sym: str, sel: str, family: str = "session_range_breakout",
          **params: Any) -> dict[str, Any]:
    return {"gated_at": "2026-10-12T07:06:44+00:00",
            "shadow_spec": {"symbol": sym, "family": family, "selector": sel, "params": params}}


def _as_traded(window: str, **override: Any) -> dict[str, Any]:
    """A certificate of the as-traded cell (research/traded_gold_cells) for `window`."""
    tp = {**cl.traded_params(window), **override}
    return _cert("XAUUSD", window, rr=tp["rr"], as_traded={**tp, "contract_oz": 100.0})


CANON = {"survivors": {"external.XAUUSD.srb.rr=1.5": _cert("XAUUSD", "asia", rr=1.5),
                       "external.XAUUSD.srb.rr=2.0": _cert("XAUUSD", "asia", rr=2.0),
                       "external.XAUUSD.srb.london": _cert("XAUUSD", "london_am", rr=1.5),
                       "external.AUDCHF.ogd": {**_cert("AUDCHF", "asia",
                                                       family="overnight_gap_decay"),
                                               "gated_at": "2026-09-29T00:00:00+00:00"}},
         "pending_rejudge": {"external.USDZAR.ogd": {}}}
PROMO = {"fusion": [{"book_key": "AUDCHF_overnight_gap_decay_asia", "name": "audchf_p",
                     "certificate": "external.AUDCHF.ogd"}]}


def test_explicit_fields_win_and_carry_hash_and_gated_at() -> None:
    got = cl.resolve({"certificate": {"cell": "external.AUDCHF.ogd"}}, CANON)
    assert got["lineage"] == cl.RESOLVED and got["cert_id"] == "external.AUDCHF.ogd"
    assert got["cert_gated_at"] == "2026-09-29T00:00:00+00:00"
    assert got["cert_spec_hash"] and len(got["cert_spec_hash"]) == 64
    # forward_clock is a marker, not a canon key
    assert cl.resolve({"certificate": "forward_clock"}, CANON)["lineage"] == cl.UNRESOLVED


def test_the_modules_own_cert_id_is_never_read_back_as_an_explicit_field() -> None:
    """Should-fix: a stamped cert_id would otherwise confirm itself on the next pass."""
    got = cl.resolve({"cert_id": "external.AUDCHF.ogd"}, CANON)
    assert got["lineage"] == cl.UNRESOLVED and got["cert_id"] is None


def test_a_unique_join_is_judged_too_m1() -> None:
    """M1: london_am has ONE candidate, at rr=1.5, and the book trades RR=2.0: never RESOLVED."""
    lon = cl.resolve({"symbol": "XAUUSD", "window": "london_am"}, CANON)
    assert lon["lineage"] == cl.UNRESOLVED and lon["cert_id"] is None
    assert lon["candidates"] == ["external.XAUUSD.srb.london"] and lon["traded_match"] == []
    # the audit's probe: only rr=1.5 is re-judged back while the book trades 2.0
    only = {"survivors": {"rr1.5_wb8": _cert("XAUUSD", "asia", rr=1.5, wait_bars=8)}}
    assert cl.resolve(None, only, book_key="gold_asia")["lineage"] == cl.UNRESOLVED
    assert cl.resolve({"symbol": "XAUUSD", "window": "afternoon"}, CANON)["lineage"] \
        == cl.UNRESOLVED


def test_the_familys_bracket_is_only_the_nearest_cert_m2() -> None:
    """M2: the rr=2.0 family cell differs on entry window, exit, stop and management."""
    got = cl.resolve(None, CANON, book_key="gold_asia")
    assert got["lineage"] == cl.NEAREST_CERT and got["cert_id"] is None
    assert got["nearest_cert"] == "external.XAUUSD.srb.rr=2.0"
    assert got["nearest_cert_state"] == cl.RESOLVED
    diff = got["differing_fields"]
    assert {"entry_window", "exit", "stop", "management"} <= set(diff) and "rr" not in diff
    tp = cl.traded_params("asia")
    assert diff["entry_window"]["cert"] == {"wait_bars": 8}   # the family default, read
    assert diff["entry_window"]["traded"]["h1_bars"] == tp["trigger_life_h1_bars"]
    assert diff["exit"]["cert"] == {"ttl_bars": 12}
    assert diff["exit"]["traded"]["force_close_server_hour"] == tp["close_hour"]
    assert diff["stop"]["traded"]["atr_floor"] == tp["atr_floor"]
    assert cl.NEAREST_CERT not in cl.LINEAGE_OK and {cl.RESOLVED} == cl.LINEAGE_OK


def test_the_as_traded_cell_is_the_lineage() -> None:
    canon = {"survivors": {**CANON["survivors"],
                           "external.XAUUSD.as_traded.asia": _as_traded("asia")}}
    got = cl.resolve(None, canon, book_key="gold_asia")
    assert got["lineage"] == cl.RESOLVED
    assert got["cert_id"] == "external.XAUUSD.as_traded.asia"
    assert got["cert_spec_hash"] and "IS the traded bracket" in got["basis"]
    # an as-traded cell built under another floor is not the traded bracket any more
    stale = {"survivors": {"x": _as_traded("asia", atr_floor=4.0)}}
    drift = cl.resolve(None, stale, book_key="gold_asia")
    assert drift["lineage"] == cl.NEAREST_CERT
    assert drift["differing_fields"] == {"atr_floor": {"cert": 4.0, "traded": 5.0}}
    # two traded cells are two candidates, never a pick
    twice = {"survivors": {"x": _as_traded("asia"), "y": _as_traded("asia")}}
    assert cl.resolve(None, twice, book_key="gold_asia")["lineage"] == cl.AMBIGUOUS


def test_a_held_back_certificate_keeps_its_name() -> None:
    """Audit (c): after the lockbox moves every asia cert to pending_rejudge, the join still sees
    them -- PENDING_REJUDGE for the traded cell, NEAREST_CERT naming its state otherwise."""
    pending = {"survivors": {}, "pending_rejudge": {"t": _as_traded("asia")}}
    assert cl.resolve(None, pending, book_key="gold_asia")["lineage"] == cl.PENDING_REJUDGE
    fam = {"survivors": {}, "pending_rejudge": {"f": _cert("XAUUSD", "asia", rr=2.0)}}
    got = cl.resolve(None, fam, book_key="gold_asia")
    assert got["lineage"] == cl.NEAREST_CERT and got["nearest_cert_state"] == cl.PENDING_REJUDGE


def test_book_keys_map_through_principal_promotions_and_canon_state_is_read() -> None:
    got = cl.resolve(None, CANON, PROMO, book_key="AUDCHF_overnight_gap_decay_asia")
    assert got["lineage"] == cl.RESOLVED and "PRINCIPAL_PROMOTIONS" in got["basis"]
    assert cl.resolve({"certificate": "external.USDZAR.ogd"}, CANON)["lineage"] \
        == cl.PENDING_REJUDGE
    assert cl.resolve({"certificate": "external.NOPE"}, CANON)["lineage"] == cl.NOT_IN_CANON
    assert cl.resolve({"certificate": "external.NOPE"}, None)["lineage"] == cl.UNMEASURED


def test_explicit_fields_are_cross_checked_against_the_row() -> None:
    """Should-fix probes: an EURUSD row carrying a XAUUSD cert, and a gold row naming rr=2.5."""
    eur = cl.resolve({"symbol": "EURUSD", "certificate": "external.XAUUSD.srb.rr=2.0"}, CANON)
    assert eur["lineage"] == cl.EXPLICIT_MISMATCH and eur["cert_id"] is None
    assert eur["mismatch"]["symbol"] == {"row": "EURUSD", "cert": "XAUUSD"}
    canon = {"survivors": {"rr2.5": _cert("XAUUSD", "asia", rr=2.5)}}
    gold = cl.resolve({"symbol": "XAUUSD", "window": "asia", "certificate": "rr2.5"}, canon)
    assert gold["lineage"] == cl.EXPLICIT_MISMATCH and "traded.rr" in gold["mismatch"]
    wrong_window = cl.resolve({"symbol": "XAUUSD", "window": "afternoon",
                               "certificate": "external.XAUUSD.srb.rr=2.0"}, CANON)
    assert wrong_window["mismatch"]["selector"] == {"row": "afternoon", "cert": "asia"}
    declared = cl.resolve({"symbol": "AUDCHF", "certificate": "external.AUDCHF.ogd",
                           "params": {"rr": 9}}, {"survivors": {
                               "external.AUDCHF.ogd": _cert("AUDCHF", "asia", rr=1.0)}})
    assert declared["mismatch"] == {"params.rr": {"row": 9, "cert": 1.0}}
    # an explicit gold certificate that agrees on rr is still judged for identity
    right = cl.resolve({"symbol": "XAUUSD", "window": "asia",
                        "certificate": "external.XAUUSD.srb.rr=2.0"}, CANON)
    assert right["lineage"] == cl.NEAREST_CERT


def test_a_stamped_hash_that_changed_is_spec_drift() -> None:
    canon = {"survivors": {"c": _cert("AUDCHF", "asia", family="overnight_gap_decay", k=1)}}
    row = {"certificate": "c", "cert_id": "c"}
    first = cl.resolve(row, canon)
    assert first["lineage"] == cl.RESOLVED
    assert cl.resolve({**row, "cert_spec_hash": first["cert_spec_hash"]}, canon)["lineage"] \
        == cl.RESOLVED
    got = cl.resolve({**row, "cert_spec_hash": "0" * 64}, canon)
    assert got["lineage"] == cl.SPEC_DRIFT and got["stamped_spec_hash"] == "0" * 64


def test_an_unreadable_traded_bracket_is_unmeasured_never_a_match() -> None:
    got = cl.resolve(None, CANON, book_key="gold_asia", traded={})
    assert got["lineage"] == cl.UNMEASURED and got["cert_id"] is None


def test_non_gold_joins_need_declared_params() -> None:
    canon = {"survivors": {"a": _cert("EURUSD", "london", family="fam_x", k=1),
                           "b": _cert("EURUSD", "london", family="fam_x", k=2)}}
    row = {"symbol": "EURUSD", "family": "fam_x", "session": "london"}
    assert cl.resolve(row, canon)["lineage"] == cl.AMBIGUOUS
    got = cl.resolve({**row, "params": {"k": 2}}, canon)
    assert got["lineage"] == cl.RESOLVED and got["cert_id"] == "b"
    one = {"survivors": {"a": canon["survivors"]["a"]}}
    assert cl.resolve(row, one)["lineage"] == cl.NEAREST_CERT


def test_stamping_is_additive_and_only_live_or_standby() -> None:
    rows = [{"name": "a", "status": "LIVE", "risk_frac": 0.05,
             "certificate": {"cell": "external.AUDCHF.ogd"}},
            {"name": "g", "status": "STANDBY", "risk_frac": 0.0, "symbol": "XAUUSD",
             "window": "asia"},
            {"name": "r", "status": "RETIRED", "certificate": "external.AUDCHF.ogd"}]
    assert cl.stamp_rows(rows, CANON) == 2
    assert rows[0]["cert_id"] == "external.AUDCHF.ogd" and rows[0]["risk_frac"] == 0.05
    assert rows[0]["status"] == "LIVE" and rows[0]["certificate"] == {"cell": "external.AUDCHF.ogd"}
    # a nearest certificate is recorded, never stamped as the row's cert_id
    assert rows[1]["cert_id"] is None and rows[1]["cert_spec_hash"] is None
    assert rows[1]["cert_lineage"]["lineage"] == cl.NEAREST_CERT
    assert rows[1]["cert_lineage"]["nearest_cert"] == "external.XAUUSD.srb.rr=2.0"
    assert "differing_fields" in rows[1]["cert_lineage"]
    assert rows[1]["status"] == "STANDBY" and rows[1]["risk_frac"] == 0.0
    assert "cert_id" not in rows[2]


def _desk(tmp: Path, sleeves: list[dict], book: dict, canon: dict | None = None,
          retired: dict | None = None) -> dict[str, Any]:
    for name, doc in (("s.json", {"sleeves": sleeves}), ("c.json", canon or CANON),
                      ("b.json", book), ("p.json", PROMO), ("r.json", retired or {})):
        (tmp / name).write_text(json.dumps(doc), "utf-8")
    return cl.build(sleeves=tmp / "s.json", canon=tmp / "c.json", book=tmp / "b.json",
                    promotions=tmp / "p.json", retired=tmp / "r.json")


def test_build_enumerates_every_roster_window_m3(tmp_path: Path) -> None:
    """M3: london_am and afternoon trade (roster emits them) even when the cert book is silent."""
    doc = _desk(tmp_path, [
        {"name": "audchf_p", "status": "LIVE", "principal_certificate": "external.AUDCHF.ogd"}],
        {"enabled": True, "fusion": {"AUDCHF_overnight_gap_decay_asia": 0.1}})
    assert doc["roster_readable"] is True
    kinds = sorted((v["kind"], v["key"], v["lineage"]) for v in doc["violations"])
    assert kinds == [("roster_window", "gold_afternoon", cl.UNRESOLVED),
                     ("roster_window", "gold_asia", cl.NEAREST_CERT),
                     ("roster_window", "gold_london_am", cl.UNRESOLVED)]
    # a window GOLD_RETIRED names is not emitted, so it is not enumerated
    retired = _desk(tmp_path, [], {"enabled": False},
                    retired={"gold_afternoon": {"reason": "t"}, "gold_london_am": {}})
    assert [w["key"] for w in retired["roster_windows"]] == ["gold_asia"]


def test_build_is_green_only_when_every_window_is_its_traded_cell(tmp_path: Path) -> None:
    canon = {"survivors": {f"t.{w}": _as_traded(w) for w in ("asia", "london_am", "afternoon")}}
    doc = _desk(tmp_path, [
        {"name": "gold_asia_v2", "status": "LIVE", "symbol": "XAUUSD", "window": "asia"}],
        {"enabled": True, "fusion": {"gold_asia": 0.08}, "e8": {"gold_asia": 0.01}}, canon)
    assert doc["n_violations"] == 0, doc["violations"]
    nearest = _desk(tmp_path, [
        {"name": "gold_asia_v2", "status": "LIVE", "symbol": "XAUUSD", "window": "asia"}],
        {"enabled": True, "fusion": {"gold_asia": 0.08}, "e8": {"gold_asia": 0.01}})
    kinds = sorted(v["kind"] for v in nearest["violations"])
    assert kinds == ["cert_book_window", "cert_book_window", "live_row", "roster_window",
                     "roster_window", "roster_window"]


def test_an_unreadable_roster_is_a_violation(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cl, "roster_windows", lambda retired: None)
    doc = _desk(tmp_path, [], {"enabled": False})
    assert doc["roster_readable"] is False
    assert [(v["kind"], v["lineage"]) for v in doc["violations"]] == [("roster_window",
                                                                       cl.UNMEASURED)]


def test_the_report_is_written_only_on_the_box_or_to_an_explicit_out(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cl, "on_trading_box", lambda: False)
    assert cl.out_path(None) is None
    assert cl.out_path(tmp_path / "x.json") == tmp_path / "x.json"
    monkeypatch.setattr(cl, "on_trading_box", lambda: True)
    assert cl.out_path(None) == cl.OUT
    # the fence follows the same rule: off the box with no --out it writes nothing
    monkeypatch.setattr(cl, "on_trading_box", lambda: False)
    wrote: list[Path] = []
    monkeypatch.setattr(cl, "write", lambda doc, out: wrote.append(out))
    monkeypatch.setattr(cl, "build", lambda: {"sleeves_readable": True, "canon_readable": True,
                                              "n_violations": 0})
    assert FENCE.main([]) == 0 and wrote == []
    assert FENCE.main(["--out", str(tmp_path / "y.json")]) == 0
    assert wrote == [tmp_path / "y.json"]


def test_the_fence_fails_only_on_the_box_with_state() -> None:
    bad = {"sleeves_readable": True, "canon_readable": True, "n_violations": 1,
           "violations": [{"kind": "roster_window", "key": "gold_asia",
                           "lineage": cl.NEAREST_CERT}]}
    rc, why = FENCE.judge(bad, require_state=True, box=True)
    assert rc == 1 and "roster_window:gold_asia (NEAREST_CERT)" in why
    assert FENCE.judge(bad, require_state=True, box=False)[0] == 0
    assert FENCE.judge(bad, require_state=False, box=True)[0] == 0
    blind = {"sleeves_readable": False, "canon_readable": True}
    assert FENCE.judge(blind, require_state=True, box=True)[0] == 1
    ok = {"sleeves_readable": True, "canon_readable": True, "n_violations": 0}
    assert FENCE.judge(ok, require_state=True, box=True)[0] == 0


def test_the_fence_is_wired_into_the_box_gate() -> None:
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert '("check_cert_lineage.py", ("--require-state",)),' in gate


# -------------------------------------------------- one traded-params reader (2026-10-20)

def test_traded_params_are_the_shared_reader_verbatim() -> None:
    from mt5desk import decision_core as dc

    from research import gold_window_params as gwp
    for w in gwp.windows():
        assert cl.traded_params(w) == gwp.traded_params(w)
    tp = cl.traded_params("asia")
    assert tp["rr"] == float(dc.RR)
    assert tp["trigger_life_h1_bars"] == dc.window_end_hour("asia") - 7.0
    assert cl.traded_params("not_a_window") == {}


def _four() -> dict[str, Any]:
    return {"survivors": {
        "rr1.5_wb12": _cert("XAUUSD", "asia", rr=1.5, wait_bars=12),
        "rr1.5_wb8": _cert("XAUUSD", "asia", rr=1.5, wait_bars=8),
        "rr2.0_wb12": _cert("XAUUSD", "asia", rr=2.0, wait_bars=12),
        "rr2.5_wb12": _cert("XAUUSD", "asia", rr=2.5, wait_bars=12)}}


def test_the_traded_rr_names_the_nearest_of_several() -> None:
    got = cl.resolve({"symbol": "XAUUSD", "window": "asia"}, _four())
    assert got["lineage"] == cl.NEAREST_CERT and got["nearest_cert"] == "rr2.0_wb12"
    assert got["differing_fields"]["entry_window"]["cert"] == {"wait_bars": 12}


def test_no_or_several_rr_matches_stay_ambiguous() -> None:
    tp = cl.traded_params("asia")
    none = cl.resolve({"symbol": "XAUUSD", "window": "asia"}, _four(), traded={**tp, "rr": 3.0})
    assert none["lineage"] == cl.AMBIGUOUS and none["traded_match"] == []
    two = cl.resolve({"symbol": "XAUUSD", "window": "asia"}, _four(), traded={**tp, "rr": 1.5})
    assert two["lineage"] == cl.AMBIGUOUS
    assert two["traded_match"] == ["rr1.5_wb12", "rr1.5_wb8"]

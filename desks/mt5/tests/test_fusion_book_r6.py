"""Fusion book r6: the principal's zeros fail closed, the retired scalp sleeves send nothing, the
deadman is armed only by the principal, an overlong pass ends itself, and a timed-out send keeps
its symbol held on the other account.

Each section names the finding it closes:

  * live-safety 2026-10-20 23:15Z -- pf.book funded the retired xau_m5_anti_breakout_overlap at
    0.042909 while a LIVE sleeves row existed for it;
  * audit r5 must-fix 1 -- a void cert book handed london_am/afternoon back to the allocator
    (Fusion) or to RISK_FRAC / the KELLY_SURVIVAL value (E8);
  * audit r5 must-fix 2 -- `gold_london_am_v3` missed `cert_book_zero`;
  * audit r5 must-fix 4/5 and should-fixes -- the armed deadman, the pass watchdog, the in-flight
    hold and the pending-aware stale rail;
  * hourly pass 15 -- an enabled E8 book that omits a gold window returned RISK_FRAC for it;
  * coordinator 2026-10-20 -- a fresh KELLY_SURVIVAL merged under the cert book, and a per-window
    `sizing_source`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import cross_account as xa  # noqa: E402
from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import kelly_sizing  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


adapter = _load("_r6_adapter", _DESK / "tests" / "test_gateway_adapter.py")
scalp = _load("_r6_scalp", _DESK / "tests" / "test_scalp_promotion.py")

SCALP = ("xau_m5_anti_breakout_overlap", "xau_m15_anti_breakout", "xau_m5_anti_momentum_ny")
GOLD_PINNED = ("gold_london_am", "gold_afternoon")
EQUITY = 485.0


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dc, "ALLOCATOR_SOVEREIGN", True)
    monkeypatch.setattr(dc, "ALLOCATOR_SOVEREIGN_FILE", tmp_path / "ALLOCATOR_SOVEREIGN.json")
    monkeypatch.setattr(dc, "MIN_LOT_FILE", tmp_path / "MIN_LOT.json")
    monkeypatch.setattr(xa, "_ABANDONED", set())


def _revert(tmp_path: Path) -> None:
    (tmp_path / "ALLOCATOR_SOVEREIGN.json").write_text('{"enabled": false}', encoding="utf-8")
    assert not dc.allocator_sovereign()


def _cert(tmp_path: Path, doc: object, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "CERT_BOOK_LIVE.json"
    if doc is not None:
        p.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE", p)
    return p


# Every way the cert book can be void: absent, disabled, torn, one value out of range.
VOID_BOOKS = (None, {"enabled": False, "fusion": {"gold_london_am": 0.0}, "e8": {}},
              "{not json", {"enabled": True, "fusion": {"gold_london_am": 7.0},
                            "e8": {"gold_asia": 7.0}})


# ------------------------------------------------------------ the pins, in code (must-fix 1, 2)

def test_the_principal_zeros_are_named_in_code_with_their_venues() -> None:
    assert set(SCALP) == dc.SCALP_LANE_ZERO
    assert set(GOLD_PINNED) == dc.GOLD_ASIA_ONLY_ZERO
    assert dc.PRINCIPAL_ZERO["fusion"] == dc.GOLD_ASIA_ONLY_ZERO | dc.SCALP_LANE_ZERO \
        | dc.GAP_DECAY_ZERO
    assert dc.PRINCIPAL_ZERO["e8"] == dc.GOLD_ASIA_ONLY_ZERO
    assert "gold_asia" not in dc.PRINCIPAL_ZERO["fusion"] | dc.PRINCIPAL_ZERO["e8"]


@pytest.mark.parametrize("doc", VOID_BOOKS)
def test_a_void_cert_book_still_zeroes_every_pinned_name_in_any_version_or_case(
        tmp_path, monkeypatch, doc) -> None:
    _cert(tmp_path, doc, monkeypatch)
    for base in (*GOLD_PINNED, *SCALP):
        for name in (base, f"{base}_v2", f"{base}_v3", f"{base}_v4", base.upper(), f" {base} "):
            assert dc.principal_zero(name) and dc.cert_book_zero(name), name
    for name in GOLD_PINNED:
        assert dc.cert_book_zero(name, "e8") and dc.cert_book_zero(f"{name}_v3", "e8")
    for name in ("gold_asia", "gold_asia_v2", "usdnok_carry_asia_p_ff35bb7c8427d66f", "", None):
        assert not dc.cert_book_zero(name), name
    # A scalp pin is a Fusion pin: the E8 lanes never read the allocator book.
    assert not dc.cert_book_zero(SCALP[0], "e8")


def test_book_name_strips_only_a_trailing_version() -> None:
    assert dc.book_name("gold_london_am_v3") == "gold_london_am"
    assert dc.book_name("gold_v2_asia") == "gold_v2_asia"
    assert dc.book_name(None) == "" and dc.book_name("gold_asia") == "gold_asia"


def test_the_cert_book_lookup_and_the_book_join_normalise_the_same_way(
        tmp_path, monkeypatch) -> None:
    """MUST 2: a versioned row is zeroed by a cert-book key it is joined to, not only by the
    code pin -- and `_book_key` and `cert_book_zero` use the one `book_name` rule."""
    _cert(tmp_path, {"enabled": True, "fusion": {"GOLD_NEW_window": 0.0},
                     "e8": {"gold_asia": 0.006}}, monkeypatch)
    assert dc.cert_book_zero("gold_new_window_v3") and dc.cert_book_zero("GOLD_NEW_WINDOW")
    ns = adapter._exec(("_book_key",), {})
    book = {"gold_london_am": 0.01, "gold_new_window": 0.02}
    assert ns["_book_key"]({"name": "gold_london_am_v4"}, book) == "gold_london_am"
    assert ns["_book_key"]({"name": "GOLD_NEW_WINDOW_v2"}, book) == "gold_new_window"
    assert ns["_book_key"]({"name": "gold_london_am_v4x"}, book) is None
    # A row whose own name is unpinned is still zeroed through the book key it joined.
    assert dc.cert_zero_row({"name": "anything_p_1", "book_key": "gold_afternoon"})
    assert not dc.cert_zero_row({"name": "anything_p_1", "book_key": "gold_asia"})


@pytest.mark.parametrize("doc", VOID_BOOKS)
def test_the_revert_path_sends_nothing_for_a_pinned_versioned_gold_row(
        tmp_path, monkeypatch, doc) -> None:
    _cert(tmp_path, doc, monkeypatch)
    _revert(tmp_path)
    ns = adapter._exec(("bracket_lane_lot", "promoted_lot"), {"sleeve_live_n": lambda name: 0})
    for name in ("gold_london_am_v3", "gold_afternoon_v2", "GOLD_AFTERNOON_v4"):
        assert dc.gold_book_lot(EQUITY, 19.1, None, 0.0, name=name)[0] == 0.0
        for lot_kind in ("auto", "auto_ramp"):
            row = {"name": name, "symbol": "XAUUSD", "lot": lot_kind,
                   "sized_by": "allocator_book", "risk_frac": 0.0}
            lot, basis = ns["bracket_lane_lot"](row, EQUITY, 19.1, None)
            assert lot == 0.0, (name, lot_kind, basis)
    # gold_asia keeps the revert path's floor.
    assert dc.gold_book_lot(EQUITY, 19.1, None, 0.0, name="gold_asia_v2")[0] > 0.0


@pytest.mark.parametrize("sovereign", [True, False])
def test_promoted_lot_with_a_cert_zero_is_zero_on_both_paths(tmp_path, sovereign) -> None:
    if not sovereign:
        _revert(tmp_path)
    for from_book in (True, False):
        assert dc.promoted_lot(10_000.0, 5, 2.0, "XAUUSD", None, 0.05,
                               from_book=from_book, cert_zero=True) == 0.0
    assert dc.promoted_lot(10_000.0, 5, 2.0, "XAUUSD", None, 0.05, from_book=True) > 0.0


# ------------------------------------------------- the retired scalp sleeves (live-safety finding)

PF_BOOK = {"xau_m5_anti_breakout_overlap": 0.042909, "xau_m15_anti_breakout": 0.03,
           "xau_m5_anti_momentum_ny": 0.02, "XAUUSD_anti_donchian_breakout": 0.03,
           "gold_london_am": 0.01, "gold_asia": 0.004}


@pytest.mark.parametrize("doc", (*VOID_BOOKS, "committed"))
def test_allocator_book_lays_the_principal_zeros_over_pf_book_whatever_the_cert_book(
        tmp_path, monkeypatch, doc) -> None:
    if doc == "committed":
        monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE",
                            _DESK / "data" / "CERT_BOOK_LIVE.json")
    else:
        _cert(tmp_path, doc, monkeypatch)
    ns = adapter._exec(("allocator_book",),
                       {"_allocator_book": lambda: (dict(PF_BOOK), "pf.book (test)")})
    book, why = ns["allocator_book"]()
    assert book is not None and "principal zeros" in why
    for k in (*SCALP, "gold_london_am", "gold_afternoon"):
        assert book[k] == 0.0, (k, why)
    assert book["XAUUSD_anti_donchian_breakout"] == 0.03     # an unpinned key is the allocator's
    # No allocator book: the cert book alone (with the pins over it) when it is valid, else None
    # (rank, do not size) -- and the per-row pin holds either way.
    ns = adapter._exec(("allocator_book",), {"_allocator_book": lambda: (None, "no proof")})
    book, why = ns["allocator_book"]()
    if doc == "committed":
        assert book is not None and all(book[k] == 0.0 for k in SCALP)
    else:
        assert book is None and "principal zeros apply per row" in why
    assert all(dc.cert_zero_row({"name": k}) for k in SCALP)


def _scalp_row(name: str, risk_frac: float) -> dict:
    # The row exactly as the sizing loop leaves it once pf.book priced it.
    return {"name": name, "symbol": "XAUUSD", "exec": "scalp_market", "timeframe": "M15",
            "family": "anti_donchian_breakout", "session": "all", "stop_atr": 1.0,
            "target_atr": 1.5, "max_hold": 6, "risk_frac": risk_frac, "lot": "auto_ramp",
            "sized_by": "allocator_book", "book_key": name}


@pytest.mark.parametrize("sovereign", [True, False])
@pytest.mark.parametrize("doc", (None, "committed"))
def test_pf_book_funding_a_retired_scalp_sleeve_with_a_live_row_sends_nothing(
        tmp_path, monkeypatch, sovereign, doc) -> None:
    """The finding itself: pf.book funds xau_m5_anti_breakout_overlap at 0.0429, a LIVE sleeves
    row exists, the gateway's scalp lane runs armed -- and sends nothing, on the sovereign and
    the ALLOCATOR_SOVEREIGN-off path, with or without the cert book. A contrast sleeve that is
    not pinned sends on the same pass, so "nothing" is the pin and not a dead harness."""
    if doc == "committed":
        monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE",
                            _DESK / "data" / "CERT_BOOK_LIVE.json")
    else:
        _cert(tmp_path, None, monkeypatch)
    if not sovereign:
        _revert(tmp_path)
    bars = scalp._with_forming(scalp._bars(recent=True))
    mt5 = scalp._fake_mt5(bars)
    ns = scalp._ns(tmp_path, mt5, armed_file=True)
    ns["promoted_lot"] = dc.promoted_lot          # the real sizer, not the harness's 0.12
    st = {"armed": True}
    retired = _scalp_row("xau_m5_anti_breakout_overlap", PF_BOOK["xau_m5_anti_breakout_overlap"])
    scalp._run_scalp(ns, st, [retired], 10_000.0)
    assert mt5.sent == [], mt5.sent
    contrast = _scalp_row("xau_m15_contrast_p_1", 0.03)
    scalp._run_scalp(ns, {"armed": True}, [contrast], 10_000.0)
    assert len(mt5.sent) >= 1


def test_every_promoted_lot_call_site_passes_the_cert_zero() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    calls = src.count("lot = promoted_lot(")
    assert calls == 4 and src.count("cert_zero=cert_zero_row(s)") == calls


# ----------------------------------------------------------------------------- E8 gold windows

def _e8(monkeypatch, tmp_path, *, hour: float, kelly: dict | None, cert: object,
        principal: bool = True):
    import test_e8_gold_guard_and_open_risk as h
    h._sandbox(monkeypatch, tmp_path)
    if principal:      # the sandbox lifts the pin for its mechanics tests; these test the pin
        monkeypatch.setitem(dc.PRINCIPAL_ZERO, "e8", dc.GOLD_ASIA_ONLY_ZERO)
    monkeypatch.setattr(dc, "GOLD_SEND_GRACE_MIN", 5.0)      # the sandbox lifts it too
    if kelly is not None:
        (tmp_path / "kelly_file.json").write_text(json.dumps({
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "e8": {"status": "OK", "windows": {k: {"risk_frac": v} for k, v in kelly.items()}}}),
            encoding="utf-8")
    if cert is not None:
        (tmp_path / "cert_book_file.json").write_text(
            cert if isinstance(cert, str) else json.dumps(cert), encoding="utf-8")
    day = h._DAY
    now = day + pd.Timedelta(hours=hour)

    class _At(h._MT5):
        class _Tick:
            time = int(now.timestamp())

        def copy_rates_from_pos(self, symbol, tf, start, count):
            idx = pd.date_range(end=now.floor("h"), periods=120, freq="h")
            return [{"time": int(t.timestamp()), "open": 4300.0,
                     "high": 4310.0 if t.date() == day.date() else 4320.0,
                     "low": 4290.0 if t.date() == day.date() else 4280.0, "close": 4300.0}
                    for t in idx]

    doc = h.g.run(h._Venue(), _At(), armed=False)
    intents = [json.loads(ln) for ln in (tmp_path / "intents.json").read_text().splitlines()
               if ln.strip()] if (tmp_path / "intents.json").exists() else []
    return doc, intents


ASIA_H, LONDON_H, AFTERNOON_H = 7 + 2 / 60, 13 + 2 / 60, 17 + 2 / 60     # on time
FRESH_KELLY = {"asia": 0.005, "london_am": 0.0025, "afternoon": 0.004}
VALID = {"enabled": True, "fusion": {"gold_london_am": 0.0},
         "e8": {"gold_asia": 0.006, "gold_london_am": 0.0, "gold_afternoon": 0.0}}


def _placed(doc, intents=()) -> dict[str, set]:
    """{window placed this pass: {(risk_frac, risk_source)} of its legs' intent rows}."""
    out: dict[str, set] = {p["window"]: set() for p in doc["placed"]}
    for r in intents:
        if r.get("window") in out and "risk_source" in r:
            out[r["window"]].add((r["risk_frac"], r["risk_source"]))
    return out


def test_fresh_kelly_under_a_valid_cert_book_london_sends_nothing_and_asia_is_the_cert(
        monkeypatch, tmp_path) -> None:
    doc, _ = _e8(monkeypatch, tmp_path, hour=LONDON_H, kelly=FRESH_KELLY, cert=VALID)
    assert "london_am" not in _placed(doc)
    assert doc["kelly_risk"]["london_am"] == 0.0
    assert doc["sizing_source"]["london_am"] == "pinned_zero"
    (tmp_path / "a").mkdir()
    doc, intents = _e8(monkeypatch, tmp_path / "a", hour=ASIA_H, kelly=FRESH_KELLY, cert=VALID)
    assert _placed(doc, intents)["asia"] == {(0.006, "cert_book")}
    assert doc["sizing_source"] == {"asia": "cert_book", "london_am": "pinned_zero",
                                    "afternoon": "pinned_zero"}


@pytest.mark.parametrize("void", VOID_BOOKS[1:])
def test_fresh_kelly_under_a_void_cert_book_keeps_both_pins_and_asia_is_the_solve(
        monkeypatch, tmp_path, void) -> None:
    """Void book: london_am/afternoon stay at 0 (the code pin, whatever Kelly says); asia is the
    fresh survival-constrained solve -- the safe choice documented in e8_gold.run: standing the
    one funded window aside for a torn file is a Rule-1 loss, and the solve is itself the
    survival-bounded size. Without a fresh solve asia is RISK_FRAC (0.005, below the box's
    0.006)."""
    for hour in (LONDON_H, AFTERNOON_H):
        doc, intents = _e8(monkeypatch, tmp_path, hour=hour, kelly=FRESH_KELLY, cert=void)
        assert doc["placed"] == [], doc["placed"]
        assert doc["sizing_source"]["london_am"] == "pinned_zero"
        assert doc["sizing_source"]["afternoon"] == "pinned_zero"
        assert doc["kelly_risk"]["london_am"] == 0.0 == doc["kelly_risk"]["afternoon"]
        assert any(r.get("rail") == "principal_zero_pin" and r["missed_growth_risk_usd"] > 0
                   for r in intents)
    (tmp_path / "k").mkdir()
    doc, intents = _e8(monkeypatch, tmp_path / "k", hour=ASIA_H, kelly=FRESH_KELLY, cert=void)
    assert _placed(doc, intents)["asia"] == {(0.005, "kelly_survival")}
    (tmp_path / "nk").mkdir()
    doc, intents = _e8(monkeypatch, tmp_path / "nk", hour=ASIA_H, kelly=None, cert=void)
    assert _placed(doc, intents)["asia"] == {(0.005, "RISK_FRAC")}
    assert doc["sizing_source"]["asia"] == "RISK_FRAC"


def test_an_enabled_book_missing_london_am_sends_nothing_even_with_the_pin_lifted(
        monkeypatch, tmp_path) -> None:
    """Pass 15: absent from an ENABLED book is 0.0, never RISK_FRAC or the Kelly value -- proven
    with the code pin lifted, so the absence rule alone is what holds it."""
    cert = {"enabled": True, "e8": {"gold_asia": 0.006}}
    doc, intents = _e8(monkeypatch, tmp_path, hour=LONDON_H, kelly=FRESH_KELLY, cert=cert,
                       principal=False)
    assert "london_am" not in _placed(doc)
    assert doc["sizing_source"]["london_am"] == "cert_book_absent"
    (row,) = [r for r in intents if r.get("window") == "london_am"]
    assert row["rail"] == "cert_book_absent_window" and row["missed_growth_risk_usd"] > 0
    # With the pin in place too, it is still nothing (and labelled the pin).
    (tmp_path / "p").mkdir()
    doc, _ = _e8(monkeypatch, tmp_path / "p", hour=LONDON_H, kelly=FRESH_KELLY, cert=cert)
    assert doc["placed"] == [] and doc["sizing_source"]["london_am"] == "pinned_zero"


def test_an_enabled_book_missing_asia_stands_asia_aside_with_a_missed_growth_line(
        monkeypatch, tmp_path) -> None:
    cert = {"enabled": True, "e8": {"gold_london_am": 0.0, "gold_afternoon": 0.0,
                                    "XAUUSD_twin_fade_x": 0.004}}
    doc, intents = _e8(monkeypatch, tmp_path, hour=ASIA_H, kelly=FRESH_KELLY, cert=cert)
    assert doc["placed"] == [] and doc["sizing_source"]["asia"] == "cert_book_absent"
    assert any("absent from the enabled cert book" in str(s.get("why")) for s in doc["skipped"])
    (row,) = [r for r in intents if r.get("window") == "asia"]
    assert row["rail"] == "cert_book_absent_window" and row["status"] == "RAIL_BLOCKED"
    assert row["missed_growth_risk_usd"] == round(100_000.0 * 0.005, 2)


def test_window_sources_name_the_real_source_per_window() -> None:
    from prop import e8_gold as g
    assert g.window_sources(None, None, None, None) == dict.fromkeys(
        ("asia", "london_am", "afternoon"), "RISK_FRAC")
    assert g.window_sources({"asia": 0.005}, {"asia": 0.006}, {"london_am": "x"},
                            {"afternoon": 0.0}) == {
        "asia": "cert_book", "london_am": "cert_book_absent", "afternoon": "pinned_zero"}
    assert g.window_sources({"asia": 0.005}, {}, {}, {})["asia"] == "kelly_survival"


def test_the_committed_e8_block_is_the_box_value_and_needs_no_scalp_zeros() -> None:
    e8 = kelly_sizing.load_cert_book(kelly_sizing.CERT_BOOK_FILE, "e8")
    assert e8 is not None and e8["gold_asia"] == 0.006
    assert not any(k in e8 for k in SCALP)   # the E8 lanes trade only cert-positive keys


# ----------------------------------------------------------------- the armed deadman (must 4)

@pytest.fixture
def fd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import test_fusion_deadman_dry_run as base
    mod = base._load()
    data = tmp_path / "data"
    data.mkdir()
    for attr, p in (("STATE", "gateway_state.json"), ("LEDGER", "live_ledger.jsonl"),
                    ("INTENTS", "order_intents.jsonl"), ("PAUSED", "GATEWAY_PAUSED"),
                    ("STAMP", "fusion_deadman_state.json"),
                    ("ARMED_MARKER", "FUSION_DEADMAN_ARMED.json")):
        monkeypatch.setattr(mod, attr, data / p)
    monkeypatch.setattr(mod, "BREACH_LOG", tmp_path / "logs" / "fusion_deadman.log")
    monkeypatch.setitem(sys.modules, "MetaTrader5", base._NoTerminal())
    (data / "gateway_state.json").write_text(json.dumps({
        "equity": 20_000.0, "margin_free": 15_000.0, "position": [], "pending": [],
        "last_reconcile": datetime.now(tz=UTC).isoformat()}), encoding="utf-8")
    return mod


@pytest.mark.parametrize("doc,ok", [(None, False), ("{bad", False), ({"armed_by": "codex"}, False),
                                    ({"armed_by": "Zuck"}, False), ([], False),
                                    ({"armed_by": "zuck", "at": "2026-10-21"}, True)])
def test_only_the_principals_marker_arms_the_rail(fd, doc, ok) -> None:
    if doc is not None:
        fd.ARMED_MARKER.write_text(doc if isinstance(doc, str) else json.dumps(doc), "utf-8")
    assert fd.principal_armed()[0] is ok


def test_live_without_the_marker_is_a_dry_run_and_says_so(fd) -> None:
    assert fd.main(dry_run=False) == 0
    stamp = json.loads(fd.STAMP.read_text("utf-8"))
    assert stamp["mode"] == "DRY-RUN"
    assert stamp["armed"]["live_requested_but_unarmed"] is True
    assert stamp["would"]["executed"] is False
    assert not dc.fusion_deadman_armed(fd.STAMP)[0]


def test_live_with_the_marker_stamps_live_and_the_dry_run_row_stands_aside(fd) -> None:
    fd.ARMED_MARKER.write_text(json.dumps({"armed_by": "zuck"}), "utf-8")
    assert fd.main(dry_run=True) == 0 and not fd.STAMP.exists()
    assert fd.main(dry_run=False) == 0
    stamp = json.loads(fd.STAMP.read_text("utf-8"))
    assert stamp["mode"] == "LIVE" and stamp["armed"]["principal"] is True
    assert dc.fusion_deadman_armed(fd.STAMP) == (True, dc.fusion_deadman_armed(fd.STAMP)[1])
    before = fd.STAMP.read_text("utf-8")
    fd.main(dry_run=True)                                     # does not overwrite LIVE
    assert fd.STAMP.read_text("utf-8") == before


def test_resting_pendings_alone_make_a_stale_gateway(fd) -> None:
    old = (datetime.now(tz=UTC) - timedelta(minutes=fd.STALE_HEARTBEAT_MIN + 1)).isoformat()
    acct = {"equity": 20_000.0, "margin_free": 15_000.0, "last_reconcile": old,
            "pending": [{"ticket": 1}]}
    breaches = fd.evaluate(acct, [], [], 20_000.0)
    assert [c for c, _ in breaches] == ["STALE_GATEWAY"] and "1 pending" in breaches[0][1]
    assert fd.evaluate({**acct, "last_reconcile": None}, [], [], 20_000.0)[0][0] \
        == "STALE_GATEWAY"
    assert fd.evaluate({**acct, "pending": []}, [], [], 20_000.0) == []


def _stamp(tmp_path: Path, mode: str, age_s: float) -> Path:
    p = tmp_path / "stamp.json"
    p.write_text(json.dumps({"mode": mode, "checked_at": (
        datetime.now(tz=UTC) - timedelta(seconds=age_s)).isoformat()}), "utf-8")
    return p


def test_the_gateway_gate_reads_the_stamp_fail_closed(tmp_path) -> None:
    assert not dc.fusion_deadman_armed(tmp_path / "absent.json")[0]
    assert not dc.fusion_deadman_armed(_stamp(tmp_path, "DRY-RUN", 10))[0]
    assert dc.fusion_deadman_armed(_stamp(tmp_path, "LIVE", 10))[0]
    assert not dc.fusion_deadman_armed(_stamp(tmp_path, "LIVE",
                                              dc.FUSION_DEADMAN_MAX_AGE_S + 5))[0]
    assert not dc.fusion_deadman_armed(_stamp(tmp_path, "LIVE", -600))[0]
    naive = tmp_path / "naive.json"
    naive.write_text(json.dumps({"mode": "LIVE", "checked_at": "2026-10-20T10:00:00"}), "utf-8")
    assert not dc.fusion_deadman_armed(naive)[0]


def test_an_unarmed_deadman_stops_the_gateway_opening_new_risk(tmp_path, monkeypatch) -> None:
    """`main` with the REAL gate and no stamp: the asia bracket the harness otherwise sends is
    not sent, and the reason is logged."""
    monkeypatch.setattr(dc, "FUSION_DEADMAN_STAMP", tmp_path / "no_stamp.json")
    rows = adapter._gold_rows()
    mt5 = adapter._Terminal(rows, *adapter._quote(rows))
    ns = adapter._main_ns(tmp_path, monkeypatch, mt5, paused=False, state={"armed": True})
    ns["fusion_deadman_armed"] = dc.fusion_deadman_armed
    ns["main"]()
    assert mt5.sent == []
    assert any("fusion deadman" in x and "managing open positions only" in x
               for x in ns["_logs"])
    # Armed and fresh, the same pass sends.
    monkeypatch.setattr(dc, "FUSION_DEADMAN_STAMP", _stamp(tmp_path, "LIVE", 5))
    mt5 = adapter._Terminal(rows, *adapter._quote(rows))
    (tmp_path / "b").mkdir()
    ns = adapter._main_ns(tmp_path / "b", monkeypatch, mt5, paused=False, state={"armed": True})
    ns["fusion_deadman_armed"] = dc.fusion_deadman_armed
    ns["main"]()
    assert len(mt5.sent) == 2


def test_the_live_task_is_registered_and_declared() -> None:
    text = (_DESK / "scripts" / "Install-QuantWindows.ps1").read_text("utf-8")
    i = text.index('Name = "MT5-FusionDeadmanLive"')
    block = text[i:text.index("@{", i)]
    assert 'Script = "proposals\\\\fusion_deadman.py"' in block
    assert 'Args = "--live"' in block and "New-TimeSpan -Minutes 5" in block
    rows = [ln for ln in (_DESK / "ops" / "box_tasks.manifest").read_text("utf-8").splitlines()
            if ln.startswith("TASK") and 'name="MT5-FusionDeadmanLive"' in ln]
    assert len(rows) == 1 and 'trigger="every 5 minutes"' in rows[0]
    assert 'runs="desks/mt5/proposals/fusion_deadman.py"' in rows[0]
    ignore = (_ROOT / ".gitignore").read_text("utf-8")
    assert "desks/mt5/data/FUSION_DEADMAN_ARMED.json" in ignore


# ---------------------------------------------------------------- the pass watchdog (must 5)

def test_an_overlong_pass_ends_its_own_process_and_frees_the_lock(tmp_path, monkeypatch) -> None:
    pytest.importorskip("MetaTrader5")
    loop = _load("_r6_gateway_loop", _DESK / "research" / "run_gateway_loop.py")
    lock = tmp_path / "gateway.lock"
    lock.write_text("123", "utf-8")
    monkeypatch.setattr(loop, "LOCK", lock)
    monkeypatch.setattr(loop, "WATCHDOG_STAMP", tmp_path / "GATEWAY_WATCHDOG.json")
    fired = threading.Event()
    codes: list[int] = []
    import os
    monkeypatch.setattr(os, "_exit", lambda code: (codes.append(code), fired.set()))
    dog = loop.start_watchdog(0.05)
    assert fired.wait(5.0)
    dog.cancel()
    assert codes == [70] and not lock.exists()
    assert json.loads((tmp_path / "GATEWAY_WATCHDOG.json").read_text("utf-8"))["why"]
    # A pass that returns in time cancels it.
    fired.clear()
    dog = loop.start_watchdog(0.5)
    dog.cancel()
    time.sleep(0.8)
    assert not fired.is_set()
    src = (_DESK / "research" / "run_gateway_loop.py").read_text("utf-8")
    body = src[src.index("\ndef main("):]
    assert body.index("dog = start_watchdog()") < body.index("gateway.main()")
    assert "dog.cancel()" in body


# ------------------------------------------------- a timed-out send keeps the symbol held

def test_a_timed_out_send_holds_its_symbol_on_the_other_accounts_reading() -> None:
    release = threading.Event()
    with pytest.raises(xa.LockedCallTimeout):
        xa.bounded(lambda: release.wait(5.0), timeout_s=0.05, what="e8 send",
                   account="e8", symbol="XAUUSD")
    try:
        book, why = xa.read_book("e8")
        assert book is not None and book["XAUUSD"] == {"long": True, "short": True}
        assert "in-flight send" in why
        assert xa.opposite_block(book, "XAUUSD", "buy", account="e8")
        assert xa.opposite_block(book, "XAUUSD", "sell", account="e8")
        later = datetime.now(tz=UTC) + timedelta(seconds=xa.MAX_AGE_S + 1)
        assert xa.inflight("e8", now=later) == set()
        xa.inflight_path("e8").write_text("{torn", "utf-8")
        assert xa.read_book("e8")[0] is None
    finally:
        release.set()


def test_an_abandoned_publish_never_writes() -> None:
    key = xa.account_key("conftest-fusion", "test")
    go = threading.Event()

    def late() -> None:
        go.wait(5.0)
        xa.publish("fusion", {"XAUUSD": {"long": True, "short": False}}, source="late", key=key)

    with pytest.raises(xa.LockedCallTimeout):
        xa.bounded(late, timeout_s=0.05, what="publish")
    go.set()
    deadline = time.time() + 5.0
    while xa._ABANDONED and time.time() < deadline:
        time.sleep(0.01)
    assert xa.read_book("fusion")[0] == {}


# --------------------------------------------------------------------------- the rails' bill

def test_the_new_rails_are_billed() -> None:
    from mt5desk import fusion_rails

    from research import missed_growth as mg

    assert {"principal_zero_pin", "cert_book_absent_window"} <= set(fusion_rails.RAILS)
    assert set(mg.FUSION_RAIL_NAMES) == set(fusion_rails.RAILS)


def test_the_committed_fusion_block_carries_the_scalp_zeros() -> None:
    fusion = kelly_sizing.load_cert_book(_DESK / "data" / "CERT_BOOK_LIVE.json", "fusion")
    assert fusion is not None and all(fusion[k] == 0.0 for k in SCALP)


# ------------------------------------------ the daily-loss latch is the broker day's (r6 must-fix)

def _gw_state(fd, *, equity: float, opening: float | None = None, day: str | None = None) -> None:
    st = {"equity": equity, "margin_free": equity * 0.9, "position": [], "pending": [],
          "last_reconcile": datetime.now(tz=UTC).isoformat()}
    if opening is not None:
        st["day_start_equity"] = {"date": day or fd.broker_day(), "equity": opening}
    fd.STATE.write_text(json.dumps(st), encoding="utf-8")


def _live_terminal(monkeypatch) -> list:
    calls: list = []
    fake = SimpleNamespace(
        TRADE_ACTION_DEAL=1, ORDER_TYPE_SELL=1, ORDER_TYPE_BUY=0, POSITION_TYPE_BUY=0,
        positions_get=lambda: [], orders_get=lambda: [],
        symbol_info_tick=lambda s: None,
        order_send=lambda req: calls.append(("send", req)),
        order_delete=lambda t: calls.append(("delete", t)))
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    return calls


def test_arming_over_a_stale_previous_day_daily_loss_flattens_nothing_and_clears_it(fd) -> None:
    """The box at 22:20Z: a DRY-RUN stamp latched [DAILY_LOSS] (no day recorded, and a confirm
    count) with a flat book and no loss on the current broker day. Arming flattens nothing --
    the terminal is never touched -- and the latch clears."""
    fd.ARMED_MARKER.write_text(json.dumps({"armed_by": "zuck"}), "utf-8")
    fd.STAMP.write_text(json.dumps({"mode": "DRY-RUN", "peak_equity": 20_000.0,
                                    "consecutive": 5, "halt_codes": ["DAILY_LOSS"],
                                    "rearm_history": {}, "escalated": [], "cleared_at": None}),
                        "utf-8")
    _gw_state(fd, equity=20_000.0, opening=20_050.0)
    assert fd.main(dry_run=False) == 0                     # _NoTerminal: any touch fails
    stamp = json.loads(fd.STAMP.read_text("utf-8"))
    assert stamp["mode"] == "LIVE" and stamp["halt_codes"] == [] and stamp["consecutive"] == 0
    assert stamp["stale_daily_loss_cleared"].startswith("stale DAILY_LOSS")
    assert stamp["armed"]["refused"] is None and not fd.PAUSED.exists()
    assert dc.fusion_deadman_armed(fd.STAMP)[0]


def test_a_dated_previous_day_latch_also_clears(fd) -> None:
    stamp = {"halt_codes": ["DAILY_LOSS", "MARGIN"], "daily_loss_day": "2026-10-19"}
    assert fd.clear_stale_daily_loss(stamp, "2026-10-20")
    assert stamp["halt_codes"] == ["MARGIN"] and stamp["daily_loss_day"] is None
    today = {"halt_codes": ["DAILY_LOSS"], "daily_loss_day": "2026-10-20"}
    assert fd.clear_stale_daily_loss(today, "2026-10-20") is None
    assert today["halt_codes"] == ["DAILY_LOSS"]
    ours = {"halt_codes": ["DAILY_LOSS"], "daily_loss_day": "2026-10-19"}
    fd.clear_stale_daily_loss(ours, "2026-10-20", ours=True)
    assert ours["halt_codes"] == ["DAILY_LOSS"]          # try_rearm lifts our own pause


def test_arming_refuses_while_the_current_day_halt_is_set_and_says_why(fd) -> None:
    fd.ARMED_MARKER.write_text(json.dumps({"armed_by": "zuck"}), "utf-8")
    _gw_state(fd, equity=17_000.0, opening=20_000.0)       # -15% on today's opening
    fd.STAMP.write_text(json.dumps({"mode": "DRY-RUN", "consecutive": 3,
                                    "halt_codes": ["DAILY_LOSS"],
                                    "daily_loss_day": fd.broker_day()}), "utf-8")
    assert fd.main(dry_run=False) == 1                     # _NoTerminal: nothing flattened
    stamp = json.loads(fd.STAMP.read_text("utf-8"))
    assert stamp["mode"] == "DRY-RUN" and "arming refused" in stamp["armed"]["refused"]
    assert stamp["would"]["executed"] is False and not fd.PAUSED.exists()
    ok, why = dc.fusion_deadman_armed(fd.STAMP)
    assert not ok and "arming refused" in why


def test_a_genuine_current_day_daily_loss_halts_as_designed(fd, monkeypatch) -> None:
    fd.ARMED_MARKER.write_text(json.dumps({"armed_by": "zuck"}), "utf-8")
    _gw_state(fd, equity=20_000.0, opening=20_000.0)
    _live_terminal(monkeypatch)
    assert fd.main(dry_run=False) == 0                     # arms on a clean day
    _gw_state(fd, equity=17_500.0, opening=20_000.0)       # then loses 12.5% today
    assert fd.main(dry_run=False) == 1
    s = json.loads(fd.STAMP.read_text("utf-8"))
    assert s["would"]["action"] == "WAIT_FOR_CONFIRMATION" and not fd.PAUSED.exists()
    assert fd.main(dry_run=False) == 1
    s = json.loads(fd.STAMP.read_text("utf-8"))
    assert s["mode"] == "LIVE" and s["would"]["action"] == "HALT_AND_FLATTEN"
    assert s["halt_codes"] == ["DAILY_LOSS"] and s["daily_loss_day"] == fd.broker_day()
    assert fd.PAUSED.exists()
    ok, why = dc.fusion_deadman_armed(fd.STAMP)
    assert not ok and "DAILY_LOSS halt set" in why


def test_the_daily_loss_rolls_over_at_the_servers_midnight(fd) -> None:
    """17:00 New York: 21:00Z in summer, 22:00Z in winter (prop/e8_guard.server_day)."""
    for before, after, loss_at in (("2026-10-20T20:59:00+00:00", "2026-10-20T21:00:00+00:00",
                                    "2026-10-20T20:30:00+00:00"),
                                   ("2026-12-15T21:59:00+00:00", "2026-12-15T22:00:00+00:00",
                                    "2026-12-15T21:30:00+00:00")):
        b, a = datetime.fromisoformat(before), datetime.fromisoformat(after)
        assert fd.broker_day(b) != fd.broker_day(a)
        assert fd.broker_day_start(a) == a
        rows = [{"time": loss_at, "pl_quote": -2_500.0}]
        acct = {"equity": 20_000.0, "margin_free": 18_000.0}
        assert [c for c, _ in fd.evaluate(acct, [], rows, 20_000.0, now=b)] == ["DAILY_LOSS"]
        assert fd.evaluate(acct, [], rows, 20_000.0, now=a) == []
        # The opening anchor counts only on its own broker day.
        anch = {**acct, "equity": 17_000.0,
                "day_start_equity": {"date": fd.broker_day(b), "equity": 20_000.0}}
        assert [c for c, _ in fd.evaluate(anch, [], [], 20_000.0, now=b)] == ["DAILY_LOSS"]
        assert fd.evaluate(anch, [], [], 20_000.0, now=a) == []


# ------------------------------------------------- a late gold send is refused (Judge, r6)

def test_the_grace_is_the_measured_constant_and_the_rule_is_pure() -> None:
    assert dc.GOLD_SEND_GRACE_MIN == 5.0
    assert dc.gold_send_late("asia", 7.0) is None
    assert dc.gold_send_late("gold_asia", 7 + 5 / 60) is None
    assert "late_send" in dc.gold_send_late("gold_asia", 7 + 6 / 60)
    assert "late_send" in dc.gold_send_late("gold_london_am_v3", 13 + 6 / 60)
    assert dc.gold_send_late("eurusd_asia", 23.0) is None             # not a gold window
    # The Judge's sends, on the 07:00 broker placement: every one is refused.
    for hour in (8 + 56 / 60, 16 + 50 / 60, 15 + 28 / 60, 7 + 27 / 60, 7 + 57 / 60):
        assert dc.gold_send_late("gold_asia", hour), hour


def _fusion_main_at(tmp_path, monkeypatch, when):
    idx = pd.date_range(end=pd.Timestamp(when).floor("h"), periods=400, freq="h")
    rows = [{"time": int(t.timestamp()), "open": 2000.0 + i * 0.01, "high": 2001.0 + i * 0.01,
             "low": 1999.0 + i * 0.01, "close": 2000.2 + i * 0.01, "tick_volume": 50.0}
            for i, t in enumerate(idx)]
    hi, lo, _ = dc.bracket_from_bars(dc.h1_frame(rows), None, 7, 0.01, 20)
    mid = (hi + lo) / 2.0

    class _At(adapter._Terminal):
        def symbol_info_tick(self, symbol):
            return SimpleNamespace(time=int(when.timestamp()), bid=self.bid, ask=self.ask)

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return when.astimezone(tz) if tz else when.replace(tzinfo=None)

    mt5 = _At(rows, mid - 0.05, mid + 0.05)
    ns = adapter._main_ns(tmp_path, monkeypatch, mt5, paused=False, state={"armed": True})
    ns["datetime"] = _Clock
    monkeypatch.setattr(dc, "GOLD_SEND_GRACE_MIN", 5.0)     # _main_ns lifts it; the rule is on
    ns["main"]()
    return mt5, ns


def test_fusion_gold_asia_sends_on_time(tmp_path, monkeypatch) -> None:
    mt5, ns = _fusion_main_at(tmp_path, monkeypatch, datetime(2026, 9, 8, 7, 2, tzinfo=UTC))
    assert len(mt5.sent) == 2 and {r["comment"] for r in mt5.sent} == {"DWgold_asia"}
    assert not any(r.get("reason") == "late_send" for r in ns["_intents"])


@pytest.mark.parametrize("when", [datetime(2026, 9, 8, 7, 6, tzinfo=UTC),     # open+grace+1
                                  datetime(2026, 9, 8, 9, 30, tzinfo=UTC)])   # another hour
def test_fusion_gold_asia_late_sends_nothing_and_bills_it(tmp_path, monkeypatch, when) -> None:
    from mt5desk import fusion_rails
    mt5, ns = _fusion_main_at(tmp_path, monkeypatch, when)
    assert mt5.sent == []
    (row,) = [r for r in ns["_intents"] if r.get("reason") == "late_send"]
    assert row["status"] == "SKIPPED" and row["sleeve"] == "gold_asia"
    lines = [json.loads(ln) for ln in fusion_rails.LEDGER.read_text("utf-8").splitlines()
             if ln.strip()]
    assert any(ln.get("rail") == "gold_late_send" and ln.get("sleeve") == "gold_asia"
               for ln in lines)
    # Once per window per day, however many passes refuse it.
    ns["main"]()
    assert len([r for r in ns["_intents"] if r.get("reason") == "late_send"]) == 1


@pytest.mark.parametrize("hour,placed", [(ASIA_H, True), (7 + 6 / 60, False), (9.5, False)])
def test_e8_gold_asia_on_time_late_and_another_hour(monkeypatch, tmp_path, hour,
                                                    placed) -> None:
    doc, intents = _e8(monkeypatch, tmp_path, hour=hour, kelly=None, cert=VALID)
    assert ("asia" in _placed(doc)) is placed
    late = [r for r in intents if r.get("reason") == "late_send"]
    if placed:
        assert late == []
    else:
        (row,) = late
        assert row["status"] == "SKIPPED" and row["rail"] == "gold_late_send"
        assert row["missed_growth_risk_usd"] == round(100_000.0 * 0.006, 2)


def test_an_e8_retry_past_the_grace_is_abandoned() -> None:
    from prop import e8_gold as g
    st = {"windows": {"asia": {"orders": {}, "position_id": None,
                               "failed": {"buy_stop": {"price": 4340.0, "attempts": 1}}}}}
    (dec,) = g.retry_decisions(st, 7 + 6 / 60, 4300.0, 4300.4, {})
    assert dec["act"] == "abandon" and "late_send" in dec["why"]
    (dec,) = g.retry_decisions(st, 7 + 2 / 60, 4300.0, 4300.4, {})
    assert dec["act"] == "retry"


def test_late_sends_are_billed_in_missed_growth() -> None:
    from mt5desk import fusion_rails

    from research import missed_growth as mg

    assert "gold_late_send" in fusion_rails.RAILS and "gold_late_send" in mg.FUSION_RAIL_NAMES


def test_every_account_key_call_normalises_the_login_to_one_type() -> None:
    k = xa.account_key(7000001, "FusionMarkets-Live")
    assert k == xa.account_key("7000001", "FusionMarkets-Live") \
        == xa.account_key(" 7000001 ", " FusionMarkets-Live ") \
        == xa.account_key(7000001.0, "FusionMarkets-Live")
    # Unchanged for an int login: no key the box already declared moves because of this.
    import hashlib
    assert k == "sha256:" + hashlib.sha256(b"7000001@FusionMarkets-Live").hexdigest()[:16]
    assert xa.account_key("trader", "tl") != xa.account_key("trader2", "tl")
    with pytest.raises(ValueError):
        xa.account_key(True, "x")

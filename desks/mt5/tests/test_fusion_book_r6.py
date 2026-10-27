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
        principal: bool = True, venue: object = None, deferred: tuple[str, ...] = ()):
    import test_e8_gold_guard_and_open_risk as h
    h._sandbox(monkeypatch, tmp_path)
    if deferred:
        _st = json.loads((tmp_path / "state.json").read_text("utf-8"))
        (tmp_path / "state.json").write_text(json.dumps({**_st, "deferred": list(deferred)}),
                                             encoding="utf-8")
    if principal:      # the sandbox lifts the pin for its mechanics tests; these test the pin
        monkeypatch.setitem(dc.PRINCIPAL_ZERO, "e8", dc.GOLD_ASIA_ONLY_ZERO)
    monkeypatch.setattr(dc, "GOLD_SEND_GRACE_MIN", 5.0)      # the sandbox lifts it too
    monkeypatch.setattr(dc, "E8_GOLD_SEND_GRACE_MIN", 10.0)
    if kelly is not None:
        (tmp_path / "kelly_file.json").write_text(json.dumps({
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "e8": {"status": "OK", "windows": {k: {"risk_frac": v} for k, v in kelly.items()}}}),
            encoding="utf-8")
    if cert is None:      # the sandbox writes a funded book; None means an ABSENT (void) book
        (tmp_path / "cert_book_file.json").unlink(missing_ok=True)
    else:
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

    doc = h.g.run(venue if venue is not None else h._Venue(), _At(), armed=False)
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


@pytest.mark.parametrize("void", VOID_BOOKS)
def test_fresh_kelly_under_a_void_cert_book_sends_nothing_on_any_window(
        monkeypatch, tmp_path, void) -> None:
    """AUDIT r6 MUST-FIX 1 (ruling): a void cert book sizes every E8 window at 0 -- no KELLY or
    RISK_FRAC fallback (the solve's grid reaches 0.015). london_am/afternoon are labelled by the
    code pin, asia `cert_book_void`, each with its missed-growth line."""
    for i, hour in enumerate((ASIA_H, LONDON_H, AFTERNOON_H)):
        (tmp_path / str(i)).mkdir()
        for kelly in (FRESH_KELLY, {"asia": 0.015, "london_am": 0.01, "afternoon": 0.0075},
                      None):
            doc, intents = _e8(monkeypatch, tmp_path / str(i), hour=hour, kelly=kelly,
                               cert=void)
            assert doc["placed"] == [], (hour, kelly, doc["placed"])
            assert doc["sizing_source"] == {"asia": "cert_book_void",
                                            "london_am": "pinned_zero",
                                            "afternoon": "pinned_zero"}
            assert all(v == 0.0 for k, v in doc["kelly_risk"].items()
                       if k in ("asia", "london_am", "afternoon"))
    rows = [json.loads(ln) for ln in (tmp_path / "0" / "intents.json").read_text().splitlines()
            if ln.strip()]
    # One line per pass here: each _e8 call re-seeds the day's state, so the once-per-window-
    # per-day dedupe (state["pin_logged"], shared with the pin rail) restarts with it.
    void_rows = [r for r in rows if r.get("rail") == "cert_book_void"]
    assert len(void_rows) == 3
    assert all(r["window"] == "asia" and r["status"] == "RAIL_BLOCKED"
               and r["missed_growth_risk_usd"] > 0 for r in void_rows)


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
    assert row["missed_growth_risk_usd"] == round(100_000.0 * dc.E8_CERT_CEILING, 2)   # r7.1


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
    # The arming precondition (r7): a readable ledger of the DECLARED Fusion live account.
    monkeypatch.setattr(mod, "FUSION_ACCOUNT", data / "FUSION_LIVE_ACCOUNT.json")
    (data / "FUSION_LIVE_ACCOUNT.json").write_text(json.dumps(
        {"login": 7_000_001, "server": "FusionMarkets-Live"}), encoding="utf-8")
    (data / "live_ledger.jsonl").write_text("", encoding="utf-8")
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


def _stamp(tmp_path: Path, mode: str, age_s: float, **extra) -> Path:
    p = tmp_path / "stamp.json"
    p.write_text(json.dumps({"mode": mode, "checked_at": (
        datetime.now(tz=UTC) - timedelta(seconds=age_s)).isoformat(),
        "broker_day": "2026-10-21", "ledger": {"ok": True, "why": "test"}, **extra}), "utf-8")
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
    key = xa.account_key(7000101, "test")
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


@pytest.mark.parametrize("hour,placed", [(7 + 1 / 60, True),       # the 07:01 pass
                                         (7 + 6 / 60, True),       # its retry pass, 07:06
                                         (7 + 10 / 60, True),      # open + E8 grace
                                         (7 + 11 / 60, False),     # open + grace + 1 min
                                         (9.5, False)])            # another hour
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
    for hour in (7 + 1 / 60, 7 + 6 / 60, 7 + 10 / 60):    # the 07:01 pass and its retries
        (dec,) = g.retry_decisions(st, hour, 4300.0, 4300.4, {})
        assert dec["act"] == "retry", hour
    (dec,) = g.retry_decisions(st, 7 + 11 / 60, 4300.0, 4300.4, {})
    assert dec["act"] == "abandon" and dec["late"] and "late_send" in dec["why"]


def test_late_sends_are_billed_in_missed_growth() -> None:
    from mt5desk import fusion_rails

    from research import missed_growth as mg

    assert "gold_late_send" in fusion_rails.RAILS and "gold_late_send" in mg.FUSION_RAIL_NAMES


def test_every_account_key_call_normalises_the_login_to_one_type() -> None:
    k = xa.account_key(7000001, "FusionMarkets-Live")
    assert k == xa.account_key("7000001", "FusionMarkets-Live") \
        == xa.account_key(" 7000001 ", " FusionMarkets-Live ") \
        == xa.account_key(7000001.0, "FusionMarkets-Live")
    assert xa.valid_key(k) and xa.account_key(7000002, "FusionMarkets-Live") != k
    # r7: a username, a bool or None is no login -- None (unresolvable, fail closed), never raise.
    assert xa.account_key("trader", "tl") is None and xa.account_key(True, "x") is None
    assert xa.account_key(None, "x") is None


# ------------------------------------------------------------------------------ r7 must-fixes

def test_the_e8_grace_is_its_own_and_derived_from_its_cadence() -> None:
    assert dc.E8_GOLD_SEND_GRACE_MIN == 10.0 and dc.GOLD_SEND_GRACE_MIN == 5.0
    ps1 = (_DESK / "scripts" / "install_e8_tasks.ps1").read_text("utf-8")
    block = ps1[ps1.index('-Name "E8-Gold"'):ps1.index('-Name "E8-Book"')]
    assert "AddMinutes(1)" in block and "New-TimeSpan -Minutes 5" in block
    assert "-LimitMinutes 4" in block                          # 1 + 5 + 4 = 10
    assert dc.gold_send_late("asia", 7 + 10 / 60, dc.E8_GOLD_SEND_GRACE_MIN) is None
    assert dc.gold_send_late("asia", 7 + 11 / 60, dc.E8_GOLD_SEND_GRACE_MIN)


def test_each_abandoned_e8_retry_is_billed(monkeypatch, tmp_path) -> None:
    import test_e8_reconnect as rc
    from prop import e8_gold as g
    monkeypatch.setattr(g, "INTENTS", tmp_path / "intents.jsonl")
    (tmp_path / "intents.jsonl").write_text("", "utf-8")
    monkeypatch.setattr(dc, "E8_GOLD_SEND_GRACE_MIN", 10.0)
    v, st = rc._Venue(), rc._state()
    rc._retry(v, st, hour=7 + 30 / 60)
    assert v.sent == []
    rows = [json.loads(ln) for ln in (tmp_path / "intents.jsonl").read_text().splitlines()
            if ln.strip()]
    (row,) = [r for r in rows if r.get("status") == "SKIPPED"]
    assert row["rail"] == "gold_late_send" and row["reason"] == "late_send"
    assert "missed_growth_risk_usd" in row
    from mt5desk import fusion_rails

    from research import missed_growth as mg

    for rail in ("gold_retry_abandoned", "cert_book_void"):
        assert rail in fusion_rails.RAILS and rail in mg.FUSION_RAIL_NAMES


@pytest.mark.parametrize("setup,why", [
    ("absent", "absent or unreadable"), ("no_account", "FUSION_LIVE_ACCOUNT.json"),
    ("torn_middle", "does not parse")])
def test_arming_refuses_an_unmeasured_ledger_and_the_gate_refuses_it_too(fd, setup,
                                                                          why) -> None:
    fd.ARMED_MARKER.write_text(json.dumps({"armed_by": "zuck"}), "utf-8")
    if setup == "absent":
        fd.LEDGER.unlink()
    elif setup == "no_account":
        fd.FUSION_ACCOUNT.unlink()
    else:
        fd.LEDGER.write_text('{"a": 1}\n{torn\n{"b": 2}\n', "utf-8")
    assert fd.main(dry_run=False) == 0
    stamp = json.loads(fd.STAMP.read_text("utf-8"))
    assert stamp["mode"] == "DRY-RUN" and stamp["ledger"]["ok"] is False
    assert "ledger is UNMEASURED" in stamp["armed"]["refused"] and why in stamp["ledger"]["why"]
    assert not dc.fusion_deadman_armed(fd.STAMP)[0]


def test_the_ledger_is_filtered_to_the_declared_live_account(fd) -> None:
    rows = [{"account": 7_000_001, "server": "FusionMarkets-Live", "account_kind": "live",
             "pl_quote": -1.0, "time": "2026-10-21T01:00:00+00:00"},
            {"account": 7_000_002, "server": "FusionMarkets-Live", "account_kind": "live",
             "pl_quote": -9_999.0, "time": "2026-10-21T01:00:00+00:00"},
            {"account": 7_000_001, "server": "FusionMarkets-Demo", "account_kind": "demo",
             "pl_quote": -9_999.0, "time": "2026-10-21T01:00:00+00:00"}]
    fd.LEDGER.write_text("\n".join(json.dumps(r) for r in rows) + "\n{torn", "utf-8")
    got, why = fd.ledger_checked()
    assert got is not None and [r["pl_quote"] for r in got] == [-1.0] and "1 live row" in why


def test_a_gate_stamp_without_a_ledger_check_or_with_a_dateless_daily_loss_refuses(
        tmp_path) -> None:
    ok, _ = dc.fusion_deadman_armed(_stamp(tmp_path, "LIVE", 5))
    assert ok
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"mode": "LIVE", "checked_at": datetime.now(tz=UTC).isoformat(),
                             "broker_day": "2026-10-21"}), "utf-8")
    ok, why = dc.fusion_deadman_armed(p)
    assert not ok and "ledger UNMEASURED" in why
    ok, why = dc.fusion_deadman_armed(_stamp(tmp_path, "LIVE", 5, halt_codes=["DAILY_LOSS"]))
    assert not ok and "no day field" in why
    ok, why = dc.fusion_deadman_armed(_stamp(tmp_path, "LIVE", 5, halt_codes=["DAILY_LOSS"],
                                             daily_loss_day="2026-10-20"))
    assert ok                                          # yesterday's latch is not today's halt


def test_no_send_goes_out_without_an_in_flight_hold(monkeypatch) -> None:
    sent: list[int] = []

    def refuse(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(xa.os, "replace", refuse)
    with pytest.raises(OSError):
        xa.bounded(lambda: sent.append(1), timeout_s=1.0, what="send", account="e8",
                   symbol="XAUUSD")
    assert sent == []
    monkeypatch.undo()
    # A send that returns clears its hold; one that raised keeps it (it may have landed).
    assert xa.bounded(lambda: 7, timeout_s=1.0, account="e8", symbol="XAUUSD") == 7
    assert xa.inflight("e8") == set()

    def boom():
        raise ConnectionError("reset after the request was written")

    with pytest.raises(ConnectionError):
        xa.bounded(boom, timeout_s=1.0, account="e8", symbol="XAUUSD")
    assert xa.inflight("e8") == {"XAUUSD"}


def test_the_watchdog_releases_the_singleton_before_the_successor(tmp_path, monkeypatch) -> None:
    pytest.importorskip("MetaTrader5")
    loop = _load("_r7_gateway_loop", _DESK / "research" / "run_gateway_loop.py")
    monkeypatch.setattr(loop, "LOCK", tmp_path / "gateway.lock")
    monkeypatch.setattr(loop, "WATCHDOG_STAMP", tmp_path / "GATEWAY_WATCHDOG.json")
    order: list[str] = []
    fake_main = SimpleNamespace(_HANDLE=1234,
                                _release_singleton=lambda h: order.append(f"release {h}"),
                                _spawn_successor=lambda: order.append("spawn"))
    monkeypatch.setitem(sys.modules, "__main__", fake_main)
    import os
    monkeypatch.setattr(os, "_exit", lambda code: order.append(f"exit {code}"))
    loop._watchdog_fire(time.time())
    assert order == ["release 1234", "spawn", "exit 70"]
    src = (_DESK / "research" / "gateway_resident.py").read_text("utf-8")
    assert "_HANDLE = handle" in src


# ------------------------------------------------- r7 additions: the one account key (auditor)

def _prov_module(calls: list | None = None):
    """A provenance stand-in that records how it is called (the v5c signature)."""
    import types

    def account_key(login, server, *, create=False):
        if calls is not None:
            calls.append((login, server, create))
        if login is None or isinstance(login, bool) or not str(login).strip().isdigit():
            return None
        return "sha256:" + format(abs(hash((int(str(login).strip()), str(server).strip()))),
                                  "016x")[:16]

    mod = types.ModuleType("libs.ops.provenance")
    mod.account_key = account_key
    return mod


def _tl_venue(*, credentials: object = None, server_attr: object = "NOT-THIS", **ids):
    api = SimpleNamespace(server=server_attr, **ids)
    if credentials is not None:
        api._credentials = credentials
    return SimpleNamespace(_raw_api=api, _creds=SimpleNamespace(server="NOR-THIS"))


def test_every_account_key_delegates_to_provenance_and_never_hashes_alone(monkeypatch) -> None:
    """Key-join ruling 1: cross_account.account_key and tradelocker_account_key are
    provenance.account_key; with provenance not importable both are None (fail closed), never
    a local sha256."""
    import libs.ops as ops
    calls: list = []
    mod = _prov_module(calls)
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", mod)
    monkeypatch.setattr(ops, "provenance", mod, raising=False)
    assert xa.account_key(7000001, " Srv ") == mod.account_key(7000001, " Srv ")
    assert calls[0] == (7000001, " Srv ", False)          # normalised INSIDE provenance
    v = _tl_venue(credentials={"username": "u", "password": "p", "server": "E8-Live"},
                  account_id=4242)
    assert xa.tradelocker_account_key(v) == mod.account_key(4242, "E8-Live")
    # Not importable: None, and no book can be published under it.
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", None)
    monkeypatch.delattr(ops, "provenance", raising=False)
    assert xa.account_key(7000001, "Srv") is None
    assert xa.tradelocker_account_key(v) is None
    with pytest.raises(ValueError):
        xa.publish("e8", {}, source="t", key=xa.tradelocker_account_key(v))
    src = (_DESK / "mt5desk" / "cross_account.py").read_text("utf-8")
    assert "import hashlib" not in src and "hashlib.sha256(" not in src


def test_the_e8_server_is_tlapi_credentials_only_and_a_missing_one_pages(monkeypatch,
                                                                       tmp_path) -> None:
    """Key-join ruling 2: the server is TLAPI 0.56.2's `_credentials["server"]`, never
    `api.server`, `_creds.server` or a "tradelocker" default; missing -> None and a page."""
    ledger = tmp_path / "alert_ledger.json"
    monkeypatch.setenv("E8_ALERT_LEDGER", str(ledger))
    good = _tl_venue(credentials={"server": " E8-Live "}, acc_id=31337)
    assert xa.tradelocker_identity(good) == (31337, "E8-Live", xa.TL_OK)
    assert xa.tradelocker_account_key(good) == xa.account_key(31337, "E8-Live")
    assert not ledger.exists()
    for creds in (None, {}, {"server": ""}, {"server": None}, SimpleNamespace(server="E8")):
        v = _tl_venue(credentials=creds, acc_id=31337)
        login, server, status = xa.tradelocker_identity(v)
        assert server is None and status == xa.TL_SERVER_UNREADABLE, creds
        assert xa.tradelocker_account_key(v) is None
    doc = json.loads(ledger.read_text("utf-8"))
    assert xa.TL_ALERT_ID in json.dumps(doc)
    assert "31337" not in ledger.read_text("utf-8")            # the page names no value
    # acc_num is an index, never the id.
    v = _tl_venue(credentials={"server": "E8-Live"}, acc_num=1)
    assert xa.tradelocker_identity(v)[2] == xa.TL_LOGIN_UNREADABLE
    assert xa.tradelocker_account_key(v) is None


def test_an_unresolvable_key_never_reads_as_a_flat_other_book(monkeypatch) -> None:
    """Key-join ruling 3: a DECLARED Fusion login whose key cannot be resolved refuses the Fusion
    book (it used to read as "undeclared" and skip the check), so the fence fails closed with a
    reason; an E8 venue with no server publishes nothing, so its book ages and is refused."""
    import libs.ops as ops
    from mt5desk import decision_core as _dc
    _dc.FUSION_ACCOUNT_FILE.write_text(json.dumps({"login": 7000101,
                                                   "server": _dc.FUSION_LIVE_SERVER}), "utf-8")
    xa.publish("fusion", {}, source="t", key=xa.account_key(7000101, _dc.FUSION_LIVE_SERVER))
    assert xa.read_book("fusion")[0] == {}                  # resolvable: joins, reads flat
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", None)
    monkeypatch.delattr(ops, "provenance", raising=False)
    assert str(xa.expected_key("fusion")).startswith("invalid:")
    book, why = xa.read_book("fusion")
    assert book is None and "another account" in why
    block = xa.opposite_block(book, "XAUUSD", "buy_stop", account="fusion", why_absent=why)
    assert block and "fail closed" in block
    m = SimpleNamespace(account_info=lambda: SimpleNamespace(login=7000101,
                                                             server=_dc.FUSION_LIVE_SERVER),
                        positions_get=lambda symbol=None: (), orders_get=lambda symbol=None: ())
    book, why = xa.mt5_book_checked(m)
    assert book is None and "unresolvable" in why
    venue = SimpleNamespace(_by_key={"XAUUSD": 6102}, positions=lambda: [], orders=lambda: [],
                            _raw_api=SimpleNamespace(acc_id=31337))     # no _credentials
    with pytest.raises(ValueError):
        xa.publish_tradelocker(venue, source="t")


def test_e8_gold_writes_a_reasoned_row_when_the_fusion_key_is_unresolvable(monkeypatch,
                                                                         tmp_path) -> None:
    """Ruling 3 end to end on E8-Gold: no new gold leg, and a RAIL_BLOCKED row that says why."""
    import libs.ops as ops
    import test_fusion_minlot_book as mb
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", None)
    monkeypatch.delattr(ops, "provenance", raising=False)
    doc, venue, intents = mb._e8_harness(monkeypatch, tmp_path)
    assert venue.placed == [] and doc["placed"] == []
    # r7.2: with no key function the venue's own E8 key is unresolvable too, so the account rail
    # refuses first; either way the row is RAIL_BLOCKED and says why.
    rows = [r for r in intents if r.get("rail") in ("cross_account_opposite",
                                                    "e8_account_undeclared")]
    assert rows and all(r["status"] == "RAIL_BLOCKED" and ("fail closed" in r["why"] or
                                                           "no new E8 gold risk" in r["why"])
                        for r in rows)


def test_the_same_fake_tlapi_keys_identically_through_both_rules(monkeypatch) -> None:
    """cross_account's E8 identity is bracket v5.1's e8_evidence rule (8fe4edce): one fake TLAPI
    object, one key, through both. Compared against prop.e8_evidence when the tree has it, and
    always against the v5.1 rule reproduced verbatim below."""
    import libs.ops as ops
    mod = _prov_module()
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", mod)
    monkeypatch.setattr(ops, "provenance", mod, raising=False)

    def v51_key(venue):                     # e8_evidence.account_key_status, v5.1, verbatim rule
        api = getattr(venue, "_raw_api", None)
        api = api if api is not None else getattr(venue, "_api", None)
        login = None
        for attr in ("account_id", "acc_id"):
            v = getattr(api, attr, None)
            if v is None or isinstance(v, bool) or str(v).strip() in ("", "0"):
                continue
            login = v
            break
        creds = getattr(api, "_credentials", None)
        server = creds.get("server") if isinstance(creds, dict) else None
        server = server.strip() if isinstance(server, str) and server.strip() else None
        if login is None or server is None:
            return None
        return mod.account_key(login, server, create=False)

    cases = [_tl_venue(credentials={"server": "E8-Live"}, account_id=5, acc_id=9, acc_num=1),
             _tl_venue(credentials={"server": " E8-Live "}, account_id="0", acc_id="77"),
             _tl_venue(credentials={"server": "E8-Live"}, acc_num=3),
             _tl_venue(credentials=None, account_id=5)]
    try:
        from prop import e8_evidence as ev
    except ImportError:
        ev = None
    for v in cases:
        assert xa.tradelocker_account_key(v) == v51_key(v)
        if ev is not None and hasattr(ev, "account_key"):
            assert xa.tradelocker_account_key(v) == ev.account_key(v)
    assert xa.tradelocker_account_key(cases[0]) == mod.account_key(5, "E8-Live")


def test_no_venue_reason_or_heat_cap_note_carries_a_login(tmp_path, monkeypatch) -> None:
    """Coordinator ruling: the venue-bar and heat-cap reasons name the account by its HMAC key,
    or "declared prop account" -- never "<login>@<server>" or the bare login."""
    import re

    import libs.ops as ops
    from mt5desk import account_profile as ap
    login, server = 9123457, "E8-Server-01"
    acc = {"login": login, "server": server, "kind": "LIVE"}
    p = tmp_path / Path(*ap.DECLARATIONS_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(rf"{login}|\d{{5,}}@\S+")
    for prov in (_prov_module(), None):
        monkeypatch.setitem(sys.modules, "libs.ops.provenance", prov)
        if prov is None:
            monkeypatch.delattr(ops, "provenance", raising=False)
        else:
            monkeypatch.setattr(ops, "provenance", prov, raising=False)
        reasons = []
        for decl in ({f"{login}@{server}": "e8-pro-v2"}, {f"{login}@{server}": "no-such"},
                     {"1@other": "e8-pro-v2"}):
            p.write_text(json.dumps({"accounts": decl}), "utf-8")
            cap, why = ap.venue_heat_cap(acc, tmp_path)
            reasons.append(why)
            _, note = dc.cap_by_heat([{"name": f"s{i}", "q": 0.05} for i in range(4)], 10_000.0,
                                     per_sleeve_q=0.05, allocation=(0.20, "measured"),
                                     venue_cap=(0.015 if cap is None else cap, why))
            reasons.append(note or "")
        for r in reasons:
            assert not pattern.search(r), r
        label = "account sha256:" if prov is not None else "declared prop account"
        assert all(label in r for r in reasons[::2]), reasons


# ---------------------------------------------------------------------- r7.1 (audit r7 SFs)

def test_a_stale_book_above_the_code_ceiling_places_at_0006_and_bills_the_cut(
        monkeypatch, tmp_path) -> None:
    """r7.1 item 1: E8 gold risk is min(book, E8_CERT_CEILING) whatever the book says; the cut
    is billed `e8_cert_ceiling` (status CAPPED) and missed_growth reads it."""
    from mt5desk import fusion_rails
    assert dc.E8_CERT_CEILING == 0.006
    src = (_DESK / "mt5desk" / "decision_core.py").read_text("utf-8")
    block = src[src.index("E8 GOLD'S CODE CEILING"):src.index("E8_CERT_CEILING = 0.006")]
    assert "zuck" in block and "Max-growth" in block and "PRINCIPAL EDIT" in block
    stale = {"enabled": True, "e8": {"gold_asia": 0.01, "gold_london_am": 0.0,
                                     "gold_afternoon": 0.0}}
    doc, intents = _e8(monkeypatch, tmp_path, hour=ASIA_H, kelly=None, cert=stale)
    assert _placed(doc, intents)["asia"] == {(0.006, "cert_book")}
    assert doc["e8_cert_ceiling"] == {"ceiling": 0.006, "cut": {"asia": 0.01}}
    (cut,) = [r for r in intents if r.get("rail") == "e8_cert_ceiling"]
    assert cut["status"] == "CAPPED" and cut["book_risk_frac"] == 0.01
    assert cut["missed_growth_risk_usd"] == round(100_000.0 * 0.004, 2)
    from research import missed_growth as mg
    assert "e8_cert_ceiling" in mg.FUSION_RAIL_NAMES and "e8_cert_ceiling" in fusion_rails.RAILS
    ms = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '("RAIL_BLOCKED", "SKIPPED", "CAPPED")' in ms
    # At or below the ceiling nothing is cut.
    (tmp_path / "b").mkdir()
    doc, intents = _e8(monkeypatch, tmp_path / "b", hour=ASIA_H, kelly=None, cert=VALID)
    assert doc["e8_cert_ceiling"]["cut"] == {}
    assert not [r for r in intents if r.get("rail") == "e8_cert_ceiling"]


def test_every_key_failure_pages_and_a_resolved_key_closes_the_alert(monkeypatch,
                                                                     tmp_path) -> None:
    """r7.1 item 2, r7.2: KEY_UNAVAILABLE, the `invalid:` sentinel and a key that does not match
    the declaration each open THAT CHECK's alert in the desk alert ledger and page it through
    send_all (v5e's helper); the same check, resolving and joining again, closes it (FIXED) and
    pages the recovery. Another check passing never closes it (no flap)."""
    import libs.ops as ops
    from libs.ops import provenance
    from libs.ops.alert_ledger import AlertLedger
    from mt5desk import decision_core as _dc
    ledger = tmp_path / "alert_ledger.json"
    monkeypatch.setenv("E8_ALERT_LEDGER", str(ledger))
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(provenance, "SENDER",
                        lambda title, body: sent.append((title, body)) or {"delivered": 1})
    monkeypatch.setattr(provenance, "_ENQUEUED", {})        # v5f: enqueue-only, per test
    monkeypatch.setattr(provenance, "_ENQUEUE_FAILED", {})
    monkeypatch.setattr(provenance, "_page_state_path", lambda: tmp_path / "page_state.json")

    def state(account, source):
        a = AlertLedger(ledger).alerts.get(xa.key_alert_id(account, source))
        return None if a is None else a.state

    mine = xa.account_key(31337, "E8-Test")              # the conftest's declared E8 key
    with pytest.raises(ValueError, match="declares"):
        xa.publish("e8", {}, source="t", key=xa.account_key(7000999, "test"))
    assert state("e8", "publish") == "OPEN"
    assert sent == []                                  # v5f: nothing is sent on the order path
    provenance.deliver_pending()                       # ... the heartbeat delivers it
    assert sent and xa.KEY_MISMATCH in sent[-1][0]               # it reached send_all
    # ANOTHER check joining does not close it (r7.2, audit r7.1 SF-2) ...
    assert xa.read_book("e8")[0] == {}
    assert state("e8", "publish") == "OPEN"
    # ... the same check does, and pages the recovery once.
    xa.publish("e8", {}, source="t", key=mine)
    provenance.deliver_pending()
    assert state("e8", "publish") == "FIXED" and "OK again" in sent[-1][0]
    # KEY_UNAVAILABLE: a well-formed venue on a tree with no provenance.
    v = _tl_venue(credentials={"server": "E8-Live"}, account_id=4242)
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", None)
    monkeypatch.delattr(ops, "provenance", raising=False)
    assert xa.tradelocker_key_status(v) == (None, xa.TL_KEY_UNAVAILABLE)
    assert state("e8", "venue_key") == "OPEN"
    # The invalid: sentinel: a declared Fusion login whose key cannot be resolved.
    _dc.FUSION_ACCOUNT_FILE.write_text(json.dumps({"login": 7000101,
                                                   "server": _dc.FUSION_LIVE_SERVER}), "utf-8")
    assert xa.read_book("fusion")[0] is None
    assert state("fusion", "read_book") == "OPEN"
    assert xa.KEY_DECLARATION_INVALID in AlertLedger(ledger).alerts[
        xa.key_alert_id("fusion", "read_book")].message
    # Provenance back: the same checks resolve and join -> closed.
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", provenance)
    monkeypatch.setattr(ops, "provenance", provenance, raising=False)
    xa.publish("fusion", {}, source="t", key=xa.account_key(7000101, _dc.FUSION_LIVE_SERVER))
    assert xa.read_book("fusion")[0] == {} and state("fusion", "read_book") == "FIXED"
    assert xa.tradelocker_key_status(_tl_venue(credentials={"server": "E8-Test"},
                                               account_id=31337))[1] == xa.TL_OK
    assert state("e8", "venue_key") == "FIXED"
    blob = ledger.read_text("utf-8") + json.dumps(sent)
    assert "7000101" not in blob and "31337" not in blob         # pages name no value


def test_an_undeclared_e8_account_refuses_new_e8_gold_risk_with_a_reasoned_row(
        monkeypatch, tmp_path) -> None:
    """r7.1 item 3: E8_ACCOUNT.json absent -> no new E8 gold leg on an armed pass, and one
    billed RAIL_BLOCKED `e8_account_undeclared` row per window per day (it used to skip the
    account check)."""
    from mt5desk import fusion_rails
    import test_fusion_minlot_book as mb
    real = mb._e8_harness

    def harness(monkeypatch, tmp_path):
        xa.E8_ACCOUNT_FILE.unlink(missing_ok=True)
        return real(monkeypatch, tmp_path)

    doc, venue, intents = harness(monkeypatch, tmp_path)
    assert venue.placed == [] and doc["placed"] == []
    rows = [r for r in intents if r.get("rail") == "e8_account_undeclared"]
    assert rows and all(r["status"] == "RAIL_BLOCKED" and "E8_ACCOUNT.json is absent" in r["why"]
                        and r["missed_growth_risk_usd"] > 0 for r in rows)
    assert "e8_account_undeclared" in fusion_rails.RAILS
    # Declared again (the conftest's own declaration): the same harness places.
    xa.E8_ACCOUNT_FILE.write_text(json.dumps({"account_key": xa.account_key(31337, "E8-Test")}),
                                  "utf-8")
    (tmp_path / "again").mkdir()
    doc, venue, _ = real(monkeypatch, tmp_path / "again")
    assert sorted(s for s, _ in venue.placed) == ["buy", "sell"]


def test_a_cert_book_zero_on_gold_asia_writes_its_missed_growth_line(monkeypatch,
                                                                     tmp_path) -> None:
    """r7.1 item 4: gold_asia 0.0 in the book stood aside with a Kelly reason and no line."""
    zero = {"enabled": True, "e8": {"gold_asia": 0.0, "gold_london_am": 0.0,
                                    "gold_afternoon": 0.0}}
    doc, intents = _e8(monkeypatch, tmp_path, hour=ASIA_H, kelly=FRESH_KELLY, cert=zero)
    assert doc["placed"] == [] and doc["sizing_source"]["asia"] == "cert_book"
    (row,) = [r for r in intents if r.get("rail") == "cert_book_zero"]
    assert row["window"] == "asia" and row["status"] == "RAIL_BLOCKED"
    assert row["missed_growth_risk_usd"] == round(100_000.0 * 0.006, 2)
    assert any("sets gold_asia to 0.0" in str(s.get("why")) for s in doc["skipped"])


@pytest.mark.parametrize("cert,rail", [(None, "cert_book_void"),
                                       ({"enabled": True, "e8": {"gold_london_am": 0.0}},
                                        "cert_book_absent_window")])
def test_void_and_absent_windows_bill_at_the_last_certified_0006(monkeypatch, tmp_path, cert,
                                                                 rail) -> None:
    """r7.1 item 5: billed at E8_CERT_CEILING (0.006), not RISK_FRAC (0.005)."""
    doc, intents = _e8(monkeypatch, tmp_path, hour=ASIA_H, kelly=FRESH_KELLY, cert=cert)
    (row,) = [r for r in intents if r.get("rail") == rail and r.get("window") == "asia"]
    assert row["missed_growth_risk_usd"] == round(100_000.0 * 0.006, 2)
    assert doc["placed"] == []


# ---------------------------------------------------------------------- r7.2 (audit r7.1 HOLD)

def _bad_declaration(kind: str, monkeypatch) -> None:
    p = xa.E8_ACCOUNT_FILE
    other = xa.account_key(7000999, "E8-Test")
    if kind == "absent":
        p.unlink(missing_ok=True)
    elif kind == "empty":
        p.write_text("", "utf-8")
    elif kind == "torn":
        p.write_text('{"account_key": "sha256:ab', "utf-8")
    elif kind == "garbage":
        p.write_text("\x00\xffnot json at all", "utf-8")
    elif kind == "invalid_sentinel":           # parses, but no valid key -> the invalid: sentinel
        p.write_text(json.dumps({"account_key": "sha256:NOTHEX"}), "utf-8")
    elif kind == "wrong_account":
        p.write_text(json.dumps({"account_key": other}), "utf-8")
    elif kind == "unreadable":
        class _Denied(type(p)):
            def read_text(self, *a, **k):
                raise PermissionError(13, "Permission denied")

            def exists(self, *a, **k):
                raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(xa, "E8_ACCOUNT_FILE", _Denied(str(p)))


BAD_DECLARATIONS = ("absent", "empty", "torn", "garbage", "invalid_sentinel", "wrong_account",
                    "unreadable")


@pytest.mark.parametrize("kind", BAD_DECLARATIONS)
def test_e8_gold_refuses_unless_the_declaration_joins_the_venues_own_key(
        monkeypatch, tmp_path, kind) -> None:
    """r7.2 MUST-FIX 1: r7.1 checked only exists(), so every one of these placed both legs. Each
    now refuses new E8 gold with a billed RAIL_BLOCKED row, pages, and never aborts the pass
    (a PermissionError included)."""
    import test_fusion_minlot_book as mb
    from libs.ops import provenance
    sent: list[str] = []
    monkeypatch.setattr(provenance, "SENDER",
                        lambda title, body: sent.append(title) or {"delivered": 1})
    monkeypatch.setattr(provenance, "_ENQUEUED", {})        # v5f: enqueue-only, per test
    monkeypatch.setattr(provenance, "_ENQUEUE_FAILED", {})
    monkeypatch.setattr(provenance, "_page_state_path", lambda: tmp_path / "page_state.json")
    _bad_declaration(kind, monkeypatch)
    doc, venue, intents = mb._e8_harness(monkeypatch, tmp_path)   # returns: the pass completed
    assert sent == []                                  # v5f: nothing is sent on the order path
    provenance.deliver_pending()
    assert venue.placed == [] and doc["placed"] == []
    assert doc["e8_account"]["ok"] is False
    rows = [r for r in intents if r.get("rail") == "e8_account_undeclared"]
    assert rows and all(r["status"] == "RAIL_BLOCKED" and r["missed_growth_risk_usd"] > 0
                        and "no new E8 gold risk" in r["why"] for r in rows)
    assert any("ACCOUNT KEY: e8" in t for t in sent), sent      # it reached send_all


def test_the_conftest_venue_joins_its_declaration_and_places(monkeypatch, tmp_path) -> None:
    """The contrast, now honest (audit r7.1: the harness venue did not match the declaration):
    the venue's own key IS the declared one, the check says so, and both legs place."""
    import test_fusion_minlot_book as mb
    from prop import e8_gold as g
    want = xa.expected_key("e8")
    assert want == xa.account_key(31337, "E8-Test")
    doc, venue, _ = mb._e8_harness(monkeypatch, tmp_path)
    assert doc["e8_account"] == {"ok": True, "why": "the E8 declaration joins this venue's key"}
    assert sorted(s for s, _ in venue.placed) == ["buy", "sell"]
    assert g.e8_account_check(SimpleNamespace(_raw_api=SimpleNamespace(
        acc_id=31337, _credentials={"server": "E8-Test"})))[0] is True


@pytest.mark.parametrize("ok", [False, True])
def test_the_0706_retry_honours_the_account_rail(monkeypatch, tmp_path, ok) -> None:
    """r7.2 (audit r7.1 SF-1): a retry is new E8 gold risk; with the declaration not joining it
    is held (not sent) and billed under `e8_account_undeclared`; joined, it goes ahead."""
    import test_e8_reconnect as rc
    from prop import e8_gold as g
    monkeypatch.setattr(g, "INTENTS", tmp_path / "intents.jsonl")
    (tmp_path / "intents.jsonl").write_text("", "utf-8")
    monkeypatch.setattr(dc, "E8_GOLD_SEND_GRACE_MIN", 10.0)
    v, st = rc._Venue(), rc._state()
    doc = rc._retry(v, st, hour=7 + 6 / 60, account_ok=(ok, "test declaration"))
    rows = [json.loads(ln) for ln in (tmp_path / "intents.jsonl").read_text().splitlines()
            if ln.strip()]
    held = [r for r in rows if r.get("rail") == "e8_account_undeclared"]
    if ok:
        assert v.sent and not held
    else:
        assert v.sent == [] and held and "retry held" in held[0]["why"]
        assert any("does not join" in w for w in doc["retry_skipped"]["why"])
    src = (_DESK / "prop" / "e8_gold.py").read_text("utf-8")
    assert "account_ok=(e8_declared, e8_account_why)" in src       # run() wires it


def test_the_e8_ceiling_binds_every_certified_entry_not_only_gold() -> None:
    """r7.2 (coordinator ruling): e8_executor's FX sleeves are capped at E8_CERT_CEILING too, and
    each cut is a CAPPED `e8_cert_ceiling` missed-growth row."""
    from prop import e8_executor as ex
    from prop import e8_guard
    bal = e8_guard.START_BALANCE
    usd, cut = ex.cert_ceiling(0.01 * bal, "USDJPY_session_range_breakout_asia")
    assert usd == pytest.approx(0.006 * bal)
    assert cut["status"] == "CAPPED" and cut["rail"] == "e8_cert_ceiling"
    assert cut["missed_growth_risk_usd"] == round(0.004 * bal, 2)
    assert ex.cert_ceiling(0.006 * bal, "k") == (0.006 * bal, None)
    assert ex.cert_ceiling(0.002 * bal, "k") == (0.002 * bal, None)
    # r7.3: the run path applies it to the FINAL post-multiplier risk (size_certified_entry).
    src = (_DESK / "prop" / "e8_executor.py").read_text("utf-8")
    assert "_capped_usd, _cut = cert_ceiling(row_risk_usd, _ckey)" not in src
    assert "_, cut = cert_ceiling(final_usd, key)" in src


# ---------------------------------------------------------------------- r7.3 (audit r7.2 HOLD)
#
# MF1 (coordinator ruling): v5f (a446bcc0) is merged under r7.x -- `provenance._page` only
# enqueues, so a hanging or raising sender can never hold the order path. These pin it in time.
# MF2 (ruling (a)): the E8 ceiling binds the FINAL post-multiplier risk.

def _pager(monkeypatch, tmp_path, kind: str):
    """A SENDER that hangs (blocks on an event, up to 5 s) or raises, and records each call with
    whether the placement lock was held at that moment."""
    import contextlib

    from libs.ops import provenance
    monkeypatch.setenv("E8_ALERT_LEDGER", str(tmp_path / "alert_ledger.json"))
    monkeypatch.setattr(provenance, "_ENQUEUED", {})
    monkeypatch.setattr(provenance, "_ENQUEUE_FAILED", {})
    monkeypatch.setattr(provenance, "_page_state_path", lambda: tmp_path / "page_state.json")
    release = threading.Event()
    held: list[bool] = []
    calls: list[tuple[str, bool]] = []

    def sender(title, body):
        calls.append((title, bool(held)))
        if kind == "raise":
            raise RuntimeError("pager down")
        release.wait(5.0)
        return {"delivered": 1}

    monkeypatch.setattr(provenance, "SENDER", sender)
    real_lock = xa.placement_lock
    entered: list[float] = []

    @contextlib.contextmanager
    def lock(*a, **k):
        with real_lock(*a, **k) as got:
            entered.append(time.perf_counter())
            held.append(True)
            try:
                yield got
            finally:
                held.pop()

    monkeypatch.setattr(xa, "placement_lock", lock)
    return SimpleNamespace(calls=calls, entered=entered, release=release, held=held)


@pytest.mark.parametrize("sender_kind", ["hang", "raise"])
@pytest.mark.parametrize("case", ["joined", "wrong_account", "venue_key_none"])
def test_a_hanging_or_raising_sender_never_delays_management_or_placement(
        monkeypatch, tmp_path, sender_kind, case) -> None:
    """r7.3 MF1: with a page already queued and the pass paging again (a wrong declaration, or a
    venue key that does not resolve), management and placement both START within 0.5 s of the
    pass, the sender is NEVER called on the order path, and never while placement_lock is held.
    Delivery happens later, off the path, and a raising sender does not escape it."""
    import test_fusion_minlot_book as mb
    from libs.ops import provenance
    from libs.ops.alert_ledger import AlertLedger
    from prop import e8_gold as g
    pg = _pager(monkeypatch, tmp_path, sender_kind)
    xa.page_key("fusion", xa.KEY_MISMATCH, source="read_book")      # a page already pending
    if case == "wrong_account":
        _bad_declaration("wrong_account", monkeypatch)
    elif case == "venue_key_none":
        monkeypatch.setattr(xa, "tradelocker_account_key", lambda venue: None)
    managed: list[float] = []
    real_manage = g.manage_actions

    def manage(*a, **k):
        managed.append(time.perf_counter())
        return real_manage(*a, **k)

    monkeypatch.setattr(g, "manage_actions", manage)
    t0 = time.perf_counter()
    doc, venue, _ = mb._e8_harness(monkeypatch, tmp_path)
    elapsed = time.perf_counter() - t0
    assert pg.calls == []                              # nothing sends on the order path
    assert elapsed < 2.0                               # never the 5 s hang
    assert managed and managed[0] - t0 < 0.5, (managed, t0)
    if case == "joined":
        assert sorted(s for s, _ in venue.placed) == ["buy", "sell"]
        assert pg.entered and pg.entered[0] - t0 < 0.5
    else:
        assert venue.placed == [] and doc["e8_account"]["ok"] is False
        alert = AlertLedger(tmp_path / "alert_ledger.json").alerts.get(
            xa.key_alert_id("e8", "e8_gold"))
        assert alert is not None and alert.state == "OPEN"
        want = xa.KEY_MISMATCH if case == "wrong_account" else xa.TL_KEY_UNAVAILABLE
        assert want in alert.message                   # r7.3 SF: a None key pages itself
    # Delivery, off the path: a thread for the hang (released), in-line for the raise.
    if sender_kind == "hang":
        t = threading.Thread(target=provenance.deliver_pending, daemon=True)
        t.start()
        deadline = time.monotonic() + 3.0
        while not pg.calls and time.monotonic() < deadline:
            time.sleep(0.01)
        pg.release.set()
        t.join(5.0)
    else:
        provenance.deliver_pending()                   # never raises
    assert pg.calls and not any(h for _, h in pg.calls)  # never under placement_lock


def test_management_and_placement_start_under_half_a_second_with_a_hung_sender(
        monkeypatch, tmp_path) -> None:
    """r7.3 MF1, stated as the auditor asked: elapsed time from pass start to management and to
    placement, with a sender that would hang for 5 s. Measured, not inferred."""
    import test_fusion_minlot_book as mb
    pg = _pager(monkeypatch, tmp_path, "hang")
    xa.page_key("e8", xa.KEY_MISMATCH, source="publish")
    t0 = time.perf_counter()
    _doc, venue, _ = mb._e8_harness(monkeypatch, tmp_path)
    assert time.perf_counter() - t0 < 2.0              # a 5 s hang never entered the pass
    assert pg.entered and pg.entered[0] - t0 < 0.5
    assert sorted(s for s, _ in venue.placed) == ["buy", "sell"]
    assert pg.calls == []
    pg.release.set()


@pytest.mark.parametrize("sender_kind", ["hang", "raise"])
def test_the_gateways_read_book_e8_only_enqueues(monkeypatch, tmp_path, sender_kind) -> None:
    """r7.3 MF1 (gateway.py :3709 / :4229 / :5162): `_xa.read_book("e8")` reaches the pager only
    through key_joins -> page_key -> _send -> provenance._page (enqueue-only). A mismatched
    declaration pages, returns at once, and calls no sender."""
    import ast

    from libs.ops import provenance
    pg = _pager(monkeypatch, tmp_path, sender_kind)
    xa.publish("e8", {}, source="t", key=xa.account_key(31337, "E8-Test"))
    _bad_declaration("wrong_account", monkeypatch)
    t0 = time.perf_counter()
    book, _why = xa.read_book("e8")
    assert time.perf_counter() - t0 < 0.5
    assert book is None and pg.calls == []
    assert provenance._outbox_path().exists()
    gw = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    assert gw.count('_xa.read_book("e8")') == 3 and "send_all" not in gw
    xs = (_DESK / "mt5desk" / "cross_account.py").read_text("utf-8")
    calls = {n.func.attr for n in ast.walk(ast.parse(xs))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "send_all" not in calls and 'getattr(provenance, "_page", None)' in xs
    pg.release.set()


# -- MF2: the post-multiplier ceiling, through the executor's own sizing stage and run() --------

class _FxVenue:
    """EURUSD-style: 100,000 contract, 0.01 step, USD quote. 10 pips = $100/lot."""

    def __init__(self, vmin: float = 0.01) -> None:
        self._vmin = vmin
        self._by_key = {"EURUSD": 1}
        self._raw_api = SimpleNamespace()

    def min_lot(self, symbol):
        return self._vmin

    def details(self, symbol):
        return {"contractSize": 100_000, "lotStep": 0.01, "currency": "USD"}

    def quote(self, symbol):
        return 1.10000, 1.10002


def _mults(monkeypatch, fade=1.0, leg=1.0, macro=1.0) -> None:
    from mt5desk import leg_balance, macro_view
    from prop import e8_executor as ex
    monkeypatch.setattr(ex, "twin_fade", lambda *a, **k: (fade, "t"))
    monkeypatch.setattr(leg_balance, "multiplier", lambda *a, **k: (leg, "leg"))
    monkeypatch.setattr(macro_view, "multiplier", lambda *a, **k: (macro, "macro"))


def _size(book_frac: float, venue=None, stop=0.0010):
    from prop import e8_executor as ex
    from prop import e8_guard
    row: dict = {}
    out = ex.size_certified_entry(
        venue or _FxVenue(), "EURUSD", "buy", "session_range_breakout",
        SimpleNamespace(ttl_bars=None), stop, book_frac * e8_guard.START_BALANCE,
        "EURUSD_session_range_breakout_asia", now=datetime(2026, 10, 21, tzinfo=UTC),
        leg_positions=[], pending_legs={}, row=row)
    return (*out, row)


def test_leg_and_macro_at_their_maxima_are_held_to_0006_post_multiplier(monkeypatch) -> None:
    """r7.3 MF2: book 0.006 x leg 1.45 x macro 1.4 = 0.01218 used to go out. The executor's
    sizing stage (the one run() calls) sends 0.006 and bills the cut CAPPED e8_cert_ceiling."""
    _mults(monkeypatch, leg=1.45, macro=1.4)
    lot, _basis, risk, cut, row = _size(0.006)
    assert row["leg_mult"] == 1.45 and row["macro_mult"] == 1.4
    assert lot == pytest.approx(6.00) and risk == pytest.approx(600.0)
    assert cut["status"] == "CAPPED" and cut["rail"] == "e8_cert_ceiling"
    # 6.00 x 2.03 = 12.18 in decimal; the venue-step FLOOR of the binary product is 12.17 lots.
    assert cut["wanted_risk_frac"] == pytest.approx(0.01217)
    assert cut["risk_frac"] == pytest.approx(0.006)
    assert cut["missed_growth_risk_usd"] == pytest.approx(617.0)
    assert "post-multiplier" in cut["why"]


@pytest.mark.parametrize("book,leg,macro,lot", [(0.002, 1.45, 1.4, 4.06),   # boost, under it
                                                (0.004, 0.5, 1.0, 2.00),    # scaled down
                                                (0.006, 1.0, 1.0, 6.00)])   # exactly at it
def test_below_the_ceiling_every_multiplier_applies_untouched(monkeypatch, book, leg, macro,
                                                             lot) -> None:
    _mults(monkeypatch, leg=leg, macro=macro)
    got, _basis, risk, cut, _row = _size(book)
    assert cut is None and got == pytest.approx(lot) and risk == pytest.approx(lot * 100.0)


def test_lot_for_risk_refuses_a_min_lot_lift_over_the_ceiling_and_it_is_billed(
        monkeypatch) -> None:
    """r7.3 SF: a venue minimum of 1.0 lot on a 100-pip stop risks $1,000 > $600: refused and
    billed RAIL_BLOCKED e8_cert_ceiling, never lifted. Without a ceiling (gold's call) the old
    lift stands."""
    from prop import e8_executor as ex
    _mults(monkeypatch)
    v = _FxVenue(vmin=1.0)
    lot, basis = ex.lot_for_risk(v, "EURUSD", 0.0100, 300.0, ceiling_usd=600.0)
    assert lot == 0.0 and basis.startswith(ex.CEILING_REFUSED)
    assert ex.lot_for_risk(v, "EURUSD", 0.0100, 300.0)[0] == 1.0        # no ceiling: unchanged
    assert ex.lot_for_risk(v, "EURUSD", 0.0050, 300.0, ceiling_usd=600.0)[0] == 1.0  # $500 ok
    lot, _b, risk, cut, _row = _size(0.003, venue=v, stop=0.0100)
    assert lot == 0.0 and risk == 0.0
    assert cut["status"] == "RAIL_BLOCKED" and cut["rail"] == "e8_cert_ceiling"
    assert cut["missed_growth_risk_usd"] == pytest.approx(300.0)
    # A multiplier lift that lands under the minimum's cap is refused the same way.
    _mults(monkeypatch, leg=1.45, macro=1.4)
    lot, _b, _risk, cut, _row = _size(0.006, venue=_FxVenue(vmin=1.0), stop=0.0070)
    assert cut["status"] == "RAIL_BLOCKED" and lot == 0.0                 # 1 lot = $700 > $600


def _run_one_fx_sleeve(monkeypatch, tmp_path, *, cert_frac: float, room: float,
                       leg=1.0, macro=1.0):
    """Drive e8_executor.run() end to end on one certified EURUSD sleeve (shadow), every
    authority door stubbed open, so the sizing stage, the ceiling and the daily floor run in
    the order run() puts them."""
    import admission_integrity
    from mt5desk import decision_core as _dc
    from mt5desk import families, family_call, kelly_sizing, order_door
    from prop import e8_executor as ex
    from prop import e8_guard

    from libs.tiers import promotion_authority
    _mults(monkeypatch, leg=leg, macro=macro)
    now = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
    idx = pd.date_range(end=now, periods=80, freq="h", tz=UTC)
    frame = pd.DataFrame({"open": 1.1, "high": 1.101, "low": 1.099, "close": 1.1}, index=idx)
    sig = SimpleNamespace(time=idx[-2], side=1, stop=1.10002 - 0.0010, target=1.1020,
                          ttl_bars=None)
    book = tmp_path / "E8_BOOK.json"
    book.write_text(json.dumps({"generated_utc": now.isoformat(), "risk_frac": 0.005,
                                "sleeves": [{"symbol": "EURUSD",
                                             "family": "session_range_breakout",
                                             "selector": "asia", "key": "c1"}]}), "utf-8")
    certf = tmp_path / "CERT_BOOK_LIVE.json"
    certf.write_text(json.dumps({"excluded": {}}), "utf-8")
    monkeypatch.setattr(ex, "BOOK", book)
    monkeypatch.setattr(ex, "INTENTS", tmp_path / "e8_intents.jsonl")
    monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE", certf)
    monkeypatch.setattr(kelly_sizing, "load_cert_book",
                        lambda p, v: {"EURUSD_session_range_breakout_asia": cert_frac})
    monkeypatch.setattr(order_door, "guard_venue", lambda v, caller=None: v)
    monkeypatch.setattr(e8_guard, "assess", lambda eq, now=None: SimpleNamespace(
        may_open=True, flatten=False, room_to_daily_floor=room, as_dict=lambda: {},
        verdict=SimpleNamespace(value="OK"), why=""))
    monkeypatch.setattr(ex, "manage_breakeven", lambda *a, **k: [])
    monkeypatch.setattr(ex, "outstanding_stop_risk", lambda *a, **k: (0.0, "flat"))
    monkeypatch.setattr(xa, "publish_under_lock", lambda *a, **k: None)
    monkeypatch.setattr(admission_integrity.IntegrityGate, "load", classmethod(
        lambda cls: SimpleNamespace(alarm={}, replication=lambda c, f: (
            admission_integrity.REPLICATED, "ok"))))
    monkeypatch.setattr(promotion_authority, "block", lambda cid: None)
    monkeypatch.setattr(families, "get_family_func", lambda fam: (lambda fr, **k: [sig]))
    monkeypatch.setattr(family_call, "certified_session_filter", lambda sigs, s: sigs)
    monkeypatch.setattr(ex, "_frame", lambda api, iid, tf="H1": frame)
    monkeypatch.setattr(ex, "_call_params", lambda *a, **k: {})

    def _no_bracket(*a, **k):
        raise RuntimeError("levels kept")

    monkeypatch.setattr(_dc, "family_bracket", _no_bracket)

    class _V(_FxVenue):
        def account(self):
            return {"equity": 100_000.0}

        def positions(self):
            return []

        def orders(self):
            return []

        def instrument_id(self, sym):
            return 1

    doc = ex.run(_V(), armed=False, now=now, entry_enabled=True)
    ip = tmp_path / "e8_intents.jsonl"
    intents = ([json.loads(ln) for ln in ip.read_text("utf-8").splitlines() if ln.strip()]
               if ip.exists() else [])
    (row,) = [r for r in doc["sleeves"] if r["symbol"] == "EURUSD"]
    return doc, row, intents


def test_run_itself_caps_the_final_risk_and_bills_it(monkeypatch, tmp_path) -> None:
    """r7.3 MF2, INSIDE run(): a certified EURUSD sleeve at 0.006 with leg 1.45 x macro 1.4 is
    sized 6.00 lots ($600 = 0.006), not 12.17, and one CAPPED e8_cert_ceiling row is written."""
    _doc, row, intents = _run_one_fx_sleeve(monkeypatch, tmp_path, cert_frac=0.006,
                                           room=10_000.0, leg=1.45, macro=1.4)
    assert row["status"] == "WOULD_SEND", row
    assert row["lot"] == pytest.approx(6.00) and row["risk_usd"] == pytest.approx(600.0)
    assert row["book_risk_usd"] == pytest.approx(600.0)
    assert row["ceiling_cut_from_usd"] == pytest.approx(1217.0)      # 12.17 lots wanted
    (cut,) = [r for r in intents if r.get("rail") == "e8_cert_ceiling"]
    assert cut["status"] == "CAPPED" and cut["missed_growth_risk_usd"] == pytest.approx(617.0)
    # Below the ceiling, the boost goes out whole.
    (tmp_path / "b").mkdir()
    _doc, row, intents = _run_one_fx_sleeve(monkeypatch, tmp_path / "b", cert_frac=0.002,
                                            room=10_000.0, leg=1.45, macro=1.4)
    assert row["status"] == "WOULD_SEND" and row["lot"] == pytest.approx(4.06)
    assert not [r for r in intents if r.get("rail") == "e8_cert_ceiling"]


def test_the_daily_floor_is_checked_with_post_multiplier_risk(monkeypatch, tmp_path) -> None:
    """r7.3 SF: book $200 x 1.45 x 1.4 = $406. With $300 left to the floor it is refused (the
    pre-multiplier $200 would have passed); with $500 it goes."""
    _doc, row, _ = _run_one_fx_sleeve(monkeypatch, tmp_path, cert_frac=0.002, room=300.0,
                                      leg=1.45, macro=1.4)
    assert row["status"] == "WOULD_BREACH_DAILY" and "$406" in row["why"], row
    (tmp_path / "b").mkdir()
    _doc, row, _ = _run_one_fx_sleeve(monkeypatch, tmp_path / "b", cert_frac=0.002, room=500.0,
                                      leg=1.45, macro=1.4)
    assert row["status"] == "WOULD_SEND"


def test_gold_is_unaffected_by_the_post_multiplier_ceiling(monkeypatch, tmp_path) -> None:
    """r7.3 MF2: gold keeps its own min(book, ceiling) and carries no multipliers -- with leg and
    macro pinned at their maxima, gold still places at 0.006 / its book, and e8_gold never
    calls the FX sizing stage nor passes a ceiling to lot_for_risk."""
    _mults(monkeypatch, leg=1.45, macro=1.4)
    stale = {"enabled": True, "e8": {"gold_asia": 0.01, "gold_london_am": 0.0,
                                     "gold_afternoon": 0.0}}
    doc, intents = _e8(monkeypatch, tmp_path, hour=ASIA_H, kelly=None, cert=stale)
    assert _placed(doc, intents)["asia"] == {(0.006, "cert_book")}
    (tmp_path / "b").mkdir()
    doc, intents = _e8(monkeypatch, tmp_path / "b", hour=ASIA_H, kelly=None, cert=VALID)
    assert _placed(doc, intents)["asia"] == {(0.006, "cert_book")}
    gsrc = (_DESK / "prop" / "e8_gold.py").read_text("utf-8")
    assert "size_certified_entry" not in gsrc and "ceiling_usd" not in gsrc


# ============================== a 429 at the signal hour costs one pass, never the window (10-27)

def _rate_limited_venue():
    import test_e8_gold_guard_and_open_risk as h
    from requests.exceptions import HTTPError

    class _429(h._Venue):
        def orders(self, symbol=None):
            raise HTTPError("status 429, error 'Too Many Requests'")
    return _429()


def test_a_venue_error_at_the_signal_hour_is_recorded_as_a_deferral(monkeypatch, tmp_path):
    doc, _ = _e8(monkeypatch, tmp_path, hour=ASIA_H, kelly=None, cert=VALID,
                 venue=_rate_limited_venue())
    assert "asia" not in _placed(doc)
    assert any("DEFERRED" in str(x) or "unmeasurable" in str(x.get("why"))
               for x in doc["skipped"] if x.get("window") == "asia")
    assert json.loads((tmp_path / "state.json").read_text("utf-8"))["deferred"] == ["asia"]


@pytest.mark.parametrize("hour,deferred,placed", [
    (7 + 11 / 60, ("asia",), True),     # the 10-27 case: deferred at :01/:06, decided at :11
    (7 + 15 / 60, ("asia",), True),     # grace + one E8 pass
    (7 + 16 / 60, ("asia",), False),    # never more than one extra pass
    (7 + 11 / 60, (), False)])          # not deferred: the late rule as before
def test_a_deferred_window_gets_one_more_pass_and_no_more(monkeypatch, tmp_path, hour, deferred,
                                                          placed) -> None:
    doc, intents = _e8(monkeypatch, tmp_path, hour=hour, kelly=None, cert=VALID,
                       deferred=deferred)
    assert ("asia" in _placed(doc)) is placed
    assert any(r.get("reason") == "late_send" for r in intents) is (not placed)


def test_the_deferral_does_not_outlive_its_server_day() -> None:
    from prop import e8_gold as g
    assert "deferred" not in g.rollover_state({"date": "2026-10-26", "deferred": ["asia"],
                                               "windows": {}}, "2026-10-27")
    assert g.window_grace("asia", {"deferred": ["asia"]}) == g.e8_grace() + 5.0
    assert g.window_grace("london_am", {"deferred": ["asia"]}) == g.e8_grace()

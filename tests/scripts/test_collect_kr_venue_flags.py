"""R0299 KR venue flag recorder -- a failed fetch must never read as 'all flags cleared'."""
from __future__ import annotations

import json

from scripts.collect_kr_venue_flags import (
    _is_active,
    _norm_bithumb_assets,
    _norm_bithumb_markets,
    _norm_upbit,
    collect,
    diff_venue,
)

_RECV = "2026-08-12T06:00:00+00:00"

# Shapes captured from the LIVE endpoints on 2026-08-12 -- the widest real schema, per the
# causal-guard lesson (a fixture built from the narrow case cannot reveal what a parser misses).
_UPBIT_DOC = [
    {"market": "KRW-GEOD", "korean_name": "지오드넷", "english_name": "GEODNET",
     "market_event": {"warning": False,
                      "caution": {"PRICE_FLUCTUATIONS": False, "TRADING_VOLUME_SOARING": True,
                                  "DEPOSIT_AMOUNT_SOARING": True,
                                  "GLOBAL_PRICE_DIFFERENCES": False,
                                  "CONCENTRATION_OF_SMALL_ACCOUNTS": False}}},
    {"market": "BTC-FIL", "korean_name": "파일코인", "english_name": "Filecoin",
     "market_event": {"warning": False,
                      "caution": {"PRICE_FLUCTUATIONS": False, "TRADING_VOLUME_SOARING": False,
                                  "DEPOSIT_AMOUNT_SOARING": False,
                                  "GLOBAL_PRICE_DIFFERENCES": False,
                                  "CONCENTRATION_OF_SMALL_ACCOUNTS": False}}},
]
_BITHUMB_MKT_DOC = [{"market": "KRW-BTC", "korean_name": "비트코인",
                     "english_name": "Bitcoin", "market_warning": "NONE"}]
_BITHUMB_AST_DOC = {"status": "0000",
                    "data": {"BTC": {"withdrawal_status": 1, "deposit_status": 1},
                             "XRP": {"withdrawal_status": 0, "deposit_status": 1}}}


def test_normalizers_parse_live_shapes():
    up = _norm_upbit(_UPBIT_DOC)
    assert up is not None
    assert up["KRW-GEOD"]["caution.TRADING_VOLUME_SOARING"] is True
    assert up["BTC-FIL"]["warning"] is False
    bm = _norm_bithumb_markets(_BITHUMB_MKT_DOC)
    assert bm is not None and bm["KRW-BTC"]["market_warning"] == "NONE"
    ba = _norm_bithumb_assets(_BITHUMB_AST_DOC)
    assert ba is not None and ba["XRP"]["withdrawal_status"] == 0


def test_unrecognised_shape_is_failed_fetch_not_empty_venue():
    # None (not {}) so the caller can NEVER diff it -- an empty dict would record every
    # market as delisted and every flag as cleared.
    assert _norm_upbit({"error": "maintenance"}) is None
    assert _norm_upbit([]) is None
    assert _norm_bithumb_assets({"status": "5500"}) is None


def test_is_active_defaults_per_surface():
    assert _is_active(True) and not _is_active(False)          # upbit warning/caution
    assert _is_active("CAUTION") and not _is_active("NONE")    # bithumb market_warning
    assert _is_active(0) and not _is_active(1)                 # rails: 0 = CLOSED = active alarm


def test_first_sight_emits_baseline_with_active_flags_only():
    snap = _norm_upbit(_UPBIT_DOC)
    assert snap is not None
    (row,) = diff_venue("upbit", None, snap, _RECV)
    assert row["kind"] == "baseline" and row["n_markets"] == 2
    assert row["active"] == {"KRW-GEOD": ["caution.DEPOSIT_AMOUNT_SOARING",
                                          "caution.TRADING_VOLUME_SOARING"]}
    assert row["clock"] == "recv_only"                         # L1.46: venue stamps nothing


def test_flag_flip_emits_one_transition_row():
    old = {"KRW-XRP": {"warning": False}}
    new = {"KRW-XRP": {"warning": True}}
    (row,) = diff_venue("upbit", old, new, _RECV)
    assert row == {"recv": _RECV, "clock": "recv_only", "venue": "upbit",
                   "kind": "transition", "market": "KRW-XRP", "field": "warning",
                   "old": False, "new": True}


def test_market_appears_and_vanishes_as_present_transitions():
    old = {"KRW-OLD": {"warning": False}}
    new = {"KRW-NEW": {"warning": False, "caution.PRICE_FLUCTUATIONS": True}}
    rows = diff_venue("upbit", old, new, _RECV)
    by = {(r["market"], r["field"]): r for r in rows}
    assert by[("KRW-NEW", "market_present")]["new"] is True    # listing, for free
    assert by[("KRW-NEW", "caution.PRICE_FLUCTUATIONS")]["new"] is True
    assert by[("KRW-OLD", "market_present")]["new"] is False   # delisting/removal


def test_failed_fetch_never_diffs_and_prior_state_survives(tmp_path):
    up = _norm_upbit(_UPBIT_DOC)
    rep1 = collect(tmp_path, {"upbit": up}, {})
    assert rep1["status"] == "OK" and rep1["n_baselines"] == 1
    # Venue down next tick: no transitions, state retained, tick marked UNMEASURED.
    rep2 = collect(tmp_path, {"upbit": None}, {"upbit": "URLError: timeout"})
    assert rep2["status"] == "UNMEASURED"                      # unmeasured never looks quiet
    assert rep2["n_transitions"] == 0 and rep2["n_baselines"] == 0
    assert rep2["venue_census"]["upbit"] == "UNMEASURED-THIS-TICK"
    # Venue back with one flag flipped: exactly that ONE transition -- and no re-baseline,
    # which proves the prior state survived the outage verbatim.
    assert up is not None
    up2 = {m: dict(f) for m, f in up.items()}
    up2["BTC-FIL"]["warning"] = True
    rep3 = collect(tmp_path, {"upbit": up2}, {})
    assert rep3["status"] == "OK"
    assert rep3["n_transitions"] == 1 and rep3["n_baselines"] == 0
    lines = [json.loads(x) for x in
             (tmp_path / "data/kr_venue_flags.jsonl").read_text("utf-8").splitlines()]
    assert lines[-1]["market"] == "BTC-FIL" and lines[-1]["new"] is True


def test_partial_outage_is_degraded_not_ok(tmp_path):
    up = _norm_upbit(_UPBIT_DOC)
    rep = collect(tmp_path, {"upbit": up, "bithumb_assets": None},
                  {"bithumb_assets": "URLError: down"})
    assert rep["status"] == "DEGRADED" and "bithumb_assets" in rep["source_errors"]


def test_corrupt_state_rebaselines_loudly(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/kr_venue_flags_state.json").write_text("{not json", "utf-8")
    rep = collect(tmp_path, {"upbit": _norm_upbit(_UPBIT_DOC)}, {})
    assert rep["n_baselines"] == 1 and "rebaselined" in rep["state_error"]

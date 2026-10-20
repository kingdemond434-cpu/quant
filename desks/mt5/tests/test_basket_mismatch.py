"""The judge's BASKET_MISMATCH ruling (2026-10-20), pinned on synthetic certificates.

  * detection is a RULE (basket family + certified before ef11ff615 + a named factor with no bars
    on the certificate's chart), never a list;
  * a hit can never promote: the clock law reads BASKET_MISMATCH and the forward engine pins the
    row to UNMEASURED_BASKET_MISMATCH, withdrawing a candidacy and never writing one;
  * the true basket is LINKED to an existing verdict (charged 0) or MINTED once (charged 1 at the
    fixed N bar), and an hourly re-run never charges it again;
  * LIVE/STANDBY sleeves are retired on --apply, RETIRED rows are untouched, nothing is deleted;
  * the PIT rates re-mint (fred_ust) is gated: absent series -> PENDING_SERIES:fred_ust, mints 0;
    present with its PIT clock -> NEW cells naming fred_ust, the old ones untouched;
  * NEEDS_PROXY_FACTOR / FACTOR_FRAME_STARVED read as one class.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT), str(_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_certificate_clock_law as law  # noqa: E402
import shadow_forward as sf  # noqa: E402
from mt5desk import factor_inputs as fi  # noqa: E402
from research.frontier_identity import cell_id  # noqa: E402

from research import basket_mismatch as bm  # noqa: E402

BASE = {"beta_win": 240, "entry_z": 2.0, "factor_symbols": ["USDX", "UST10Y"],
        "lookback": 240, "session": "asia", "side_mode": "revert", "ttl_bars": 8,
        "timeframe": "M15"}
BEFORE = "2026-09-20T10:00:00+00:00"
AFTER = "2026-10-01T10:00:00+00:00"


def _cert(sym: str = "XAUAUD", params: dict | None = None, at: str = BEFORE,
          family: str = "cross_asset_residual") -> dict:
    p = dict(params or BASE)
    return {"name": "external." + cell_id({"sym": sym, "family": family, "params": p}),
            "symbol": sym, "family": family, "selector": "asia", "side": "LONG", "params": p,
            "certified_at": at, "key": f"{sym}.{family}.asia#k"}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "CLOCK_LAW", tmp_path / "law.json")
    monkeypatch.setattr(bm, "VERDICT_INDEX", tmp_path / "index.json")
    monkeypatch.setattr(bm, "SEEN_CELLS", tmp_path / "seen.json")
    monkeypatch.setattr(bm, "_registry", lambda: {"USDX": {"trade_mode": 4},
                                                  "UST05Y": {"trade_mode": 4}})
    monkeypatch.setattr(bm, "_close_only", lambda: {"UST10Y"})
    return tmp_path


# ------------------------------------------------------------------------------- detection

def test_detection_is_the_rule_not_a_list(isolated) -> None:
    hit = _cert()
    after = _cert("XAUEUR", at=AFTER)                       # certified after the fix
    h1 = _cert("XAGUSD", dict(BASE, timeframe="H1"))       # H1 bars exist for every symbol
    clean = _cert("NAS100", dict(BASE, factor_symbols=["USDX", "UST05Y"]))
    other = _cert("EURUSD", family="session_range_breakout")
    doc = bm.detect([hit, after, h1, clean, other])
    assert doc["certificates"] == [hit["name"]]
    row = doc["hits"][0]
    assert row["status"] == "BASKET_MISMATCH" and row["may_promote"] is False
    assert row["clock_status"] == "UNMEASURED_BASKET_MISMATCH"
    assert [m["factor"] for m in row["missing_factors"]] == ["UST10Y"]
    assert row["true_basket"] == ["USDX"]


def test_registry_evidence_outranks_the_close_only_list(isolated, monkeypatch) -> None:
    monkeypatch.setattr(bm, "_close_only", lambda: set())
    monkeypatch.setattr(bm, "_registry", lambda: {"UST10Y": {"trade_mode": 1}})
    assert bm.detect([_cert()])["n_hits"] == 1
    monkeypatch.setattr(bm, "_registry", lambda: {
        "UST10Y": {"intraday_coverage": {"M15": {"bars": 0, "reason": "NOT_TRADEABLE"}}}})
    assert bm.detect([_cert()])["n_hits"] == 1
    monkeypatch.setattr(bm, "_registry", lambda: {"UST10Y": {"trade_mode": 4}})
    assert bm.detect([_cert()])["n_hits"] == 0


def test_params_round_trip_from_the_engines_own_key() -> None:
    p = dict(BASE, timeframe="M5")
    key = sf.sleeve_key("XAUEUR", "asia", dict(p), "cross_asset_residual", "LONG")
    got = bm.params_from_key(key, "cross_asset_residual")
    assert cell_id({"sym": "XAUEUR", "family": "cross_asset_residual", "params": got}) == \
        cell_id({"sym": "XAUEUR", "family": "cross_asset_residual", "params": p})


# ------------------------------------------------------------------------------- re-judge

def test_true_basket_links_to_an_existing_verdict_and_charges_nothing(isolated) -> None:
    twin = cell_id({"sym": "XAUAUD", "family": "cross_asset_residual",
                    "params": dict(BASE, factor_symbols=["USDX"])})
    (isolated / "seen.json").write_text(json.dumps({twin: "2026-09-01"}))
    rj = bm.detect([_cert()])["hits"][0]["rejudge"]
    assert rj["status"] == "LINKED" and rj["cell"] == twin and rj["charged"] == 0


def test_absent_true_basket_is_minted_once_at_the_fixed_bar(isolated) -> None:
    doc = bm.detect([_cert(), _cert()])                     # duplicate cert -> one cell
    rj = doc["hits"][0]["rejudge"]
    assert rj["status"] == "MINTED" and rj["charged_trials"] == 1 and rj["bar_n"] == 5
    assert rj["params"]["factor_symbols"] == ["USDX"]
    rows = bm.rejudge_rows(doc)
    assert len(rows) == 1 and rows[0]["trial_charge"] == {"bar_n": 5, "charged_trials": 1,
                                                          "once": True}
    ledger = isolated / "minted.json"
    fresh, led = bm.emit_once(rows, ledger)
    assert len(fresh) == 1
    ledger.write_text(json.dumps(led))
    again, _ = bm.emit_once(rows, ledger)
    assert again == []                                      # an hourly re-run charges nothing


def test_unverifiable_params_are_detected_but_never_rejudged(isolated) -> None:
    c = dict(_cert(), params_verified=False)
    rj = bm.detect([c])["hits"][0]["rejudge"]
    assert rj["status"] == "NOT_JUDGEABLE"


# ------------------------------------------------------------------------------- sleeves

def test_live_and_standby_sleeves_are_retired_and_nothing_is_deleted(tmp_path) -> None:
    cert = _cert()["name"]
    roster = {"sleeves": [
        {"name": "a", "status": "STANDBY", "risk_frac": 0.0, "certificate": {"cell": cert}},
        {"name": "b", "status": "LIVE", "risk_frac": 0.01, "certificate": {"cell": cert}},
        {"name": "c", "status": "RETIRED", "certificate": {"cell": cert}},
        {"name": "d", "status": "LIVE", "certificate": {"cell": "external.other"}}]}
    path = tmp_path / "sleeves.json"
    path.write_text(json.dumps(roster))
    doc = {"certificates": [cert]}
    assert [r["name"] for r in bm.retire_sleeves(doc, path, apply=False)] == ["a", "b"]
    assert json.loads(path.read_text()) == roster            # a dry run writes nothing
    bm.retire_sleeves(doc, path, apply=True)
    after = {r["name"]: r for r in json.loads(path.read_text())["sleeves"]}
    assert len(after) == 4
    assert after["a"]["status"] == after["b"]["status"] == "RETIRED"
    assert after["b"]["risk_frac"] == 0.0 and "BASKET_MISMATCH" in after["b"]["retire_reason"]
    assert after["c"] == roster["sleeves"][2] and after["d"]["status"] == "LIVE"


# ------------------------------------------------------------------------------- readers

def _law_cert() -> dict:
    c = _cert()
    return {k: c[k] for k in ("name", "symbol", "family", "selector", "side", "certified_at")}


def test_clock_law_reads_basket_mismatch_and_never_a_breach() -> None:
    now = datetime(2026, 10, 20, tzinfo=UTC)
    row = {"n": 0, "status": "UNMEASURED_BASKET_MISMATCH", "lane": "shadow_state.json",
           "forward_start": BEFORE}
    hit = {"certificate": _cert()["name"], "missing_factors": [{"factor": "UST10Y"}],
           "true_basket": ["USDX"], "rejudge": {"status": "MINTED", "cell": "c",
                                                "charged_trials": 1, "bar_n": 5}}
    e = law.judge(_law_cert(), "k", row, [], 72.0, "", now, hit)
    assert e["verdict"] == "BASKET_MISMATCH" and e["breach"] is False
    assert e["may_promote"] is False and e["rejudge"]["status"] == "MINTED"
    assert e["unknown_class"] == "BASKET_MISMATCH"
    # without the ruling the same named status is a block, never a silent pass
    assert law.judge(_law_cert(), "k", row, [], 72.0, "", now)["verdict"] == "BLOCKED"


def test_blocked_named_causes_read_as_one_class() -> None:
    now = datetime(2026, 10, 20, tzinfo=UTC)
    for status in ("NEEDS_PROXY_FACTOR", "FACTOR_FRAME_STARVED"):
        e = law.judge(_law_cert(), "k", {"n": 0, "status": status}, [], 72.0, "", now)
        assert e["unknown_class"] == "NEEDS_PROXY_FACTOR"
    assert law.UNKNOWN_CLASS_ALIASES == fi.UNKNOWN_CLASS_ALIASES
    assert fi.unknown_class("FACTOR_FRAME_STARVED: 12 rows") == "NEEDS_PROXY_FACTOR"
    assert fi.unknown_class("BLOCKED_NO_BARS") == "BLOCKED_NO_BARS"


def test_forward_engine_pins_the_row_and_withdraws_a_candidacy() -> None:
    info = {"certificate": "c", "missing_factors": [{"factor": "UST10Y"}],
            "true_basket": ["USDX"], "rejudge": {"status": "MINTED", "cell": "x"}}
    for before, want in (("ACTIVE", sf.BASKET_MISMATCH_STATUS),
                         ("PROMOTION CANDIDATE", sf.BASKET_MISMATCH_STATUS),
                         ("BLOCKED_NO_BARS", sf.BASKET_MISMATCH_STATUS),
                         ("KILL", "KILL")):
        st = {"status": before, "promotion_authority": True}
        assert sf.apply_basket_mismatch(st, info)
        assert st["status"] == want and st["promotion_authority"] is False
        assert st["basket_mismatch"]["missing_factors"] == ["UST10Y"]
    assert sf._is_terminal(sf.BASKET_MISMATCH_STATUS)
    assert not sf.apply_basket_mismatch({"status": "ACTIVE"}, None)


# ------------------------------------------------------------------------------- PIT re-mint

def _fred_ust(root: Path, *, calendar_join: bool = False) -> None:
    days = pd.date_range("2026-01-01", periods=200, freq="B", tz="UTC")
    rng = np.random.default_rng(3)
    ev = pd.Series(days)
    avail = ev if calendar_join else ev.dt.normalize() + pd.Timedelta(days=1, hours=23)
    pd.DataFrame({"y_DGS5": 4.0 + np.cumsum(rng.normal(0, .02, len(days))),
                  "y_DGS10": 4.3 + np.cumsum(rng.normal(0, .02, len(days))),
                  "available_time": avail, "event_time": ev, "source_id": "fred_ust",
                  "retrieval_time": "2026-10-20T00:00:00+00:00"}).to_parquet(
        root / "fred_ust.parquet", index=False)


def test_pit_remint_absent_series_is_a_named_pending_and_mints_nothing(isolated) -> None:
    doc = bm.detect([_cert()])
    out = bm.pit_remint(doc, isolated)
    assert out["status"] == "PENDING_SERIES:fred_ust" and out["minted"] == 0
    assert out["rows"] == [] and out["candidates"] == 1


def test_pit_remint_refuses_a_calendar_day_join(isolated) -> None:
    _fred_ust(isolated, calendar_join=True)
    out = bm.pit_remint(bm.detect([_cert()]), isolated)
    assert out["status"] == "PENDING_SERIES:fred_ust" and "calendar-day" in out["why"]


def test_pit_remint_waits_for_the_judge_to_read_the_series(isolated, monkeypatch) -> None:
    _fred_ust(isolated)
    monkeypatch.setattr(bm, "gauntlet_reads_pit", lambda path=None: False)
    out = bm.pit_remint(bm.detect([_cert()]), isolated)
    assert out["status"].startswith("PENDING_SEALED") and out["minted"] == 0


def test_pit_remint_present_mints_new_cells_naming_the_series(isolated, monkeypatch) -> None:
    _fred_ust(isolated)
    monkeypatch.setattr(bm, "gauntlet_reads_pit", lambda path=None: True)
    old = _cert()
    doc = bm.detect([old])
    out = bm.pit_remint(doc, isolated)
    assert out["status"] == "MINTED" and out["minted"] == 1
    row = out["rows"][0]
    assert row["params"]["factor_symbols"] == ["USDX", "fred_ust:y_DGS10"]
    assert row["trial_charge"]["bar_n"] == 5 and row["source"] == bm.PIT_SOURCE
    new = "external." + cell_id({"sym": "XAUAUD", "family": "cross_asset_residual",
                                 "params": row["params"]})
    assert new != old["name"]                               # a NEW cell, never swapped in place
    assert doc["hits"][0]["status"] == "BASKET_MISMATCH"    # the old one stays a mismatch


# ------------------------------------------------------------------------------- PIT factor

def test_pit_factor_is_joined_as_of_its_stamp_never_earlier(tmp_path, monkeypatch) -> None:
    import mt5desk.family_exogenous_conditioner as ec
    _fred_ust(tmp_path)
    monkeypatch.setattr(ec, "SERIES_DIR", tmp_path)
    idx = pd.date_range("2026-03-02", periods=24 * 20, freq="h", tz="UTC")
    prim = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
    got = fi.pit_aligned("fred_ust:y_DGS10", prim)
    assert got is not None and len(got)
    src = pd.read_parquet(tmp_path / "fred_ust.parquet")
    usable = pd.to_datetime(src["available_time"], utc=True) + pd.Timedelta(hours=24)
    for t, v in got["close"].iloc[::37].items():
        ok = src.loc[usable <= t, "y_DGS10"]
        assert v == ok.iloc[-1]                             # the latest value usable at t
    _frames, why, prov = fi.build_basket(["fred_ust:y_DGS10"], {"lookback": 5, "beta_win": 5},
                                        prim, lambda s: None)
    assert why == "ok" and prov["factors"][0]["source"] == "PIT_SERIES"
    _f, why, prov = fi.build_basket(["fred_ust:y_DGS30"], {}, prim, lambda s: None)
    assert why.startswith("NEEDS_PROXY_FACTOR") and prov["needs"] == ["fred_ust:y_DGS30"]


# ------------------------------------------------------------------------------- false positives

def _roster(tmp: Path, certs: list[dict]) -> Path:
    path = tmp / "sleeves.json"
    path.write_text(json.dumps({"sleeves": [
        {"name": f"s{i}", "status": "LIVE", "risk_frac": 0.01, "certificate": {"cell": c["name"]}}
        for i, c in enumerate(certs)]}))
    return path


def test_same_family_and_period_with_every_factor_intraday_is_never_flagged(isolated) -> None:
    """Same family, same pre-fix certification date, but every named factor HAS intraday bars:
    not a mismatch, never retired, no missed-growth line."""
    healthy = [_cert("XAUAUD", dict(BASE, factor_symbols=["USDX", "UST05Y"])),
               _cert("XAUEUR", dict(BASE, factor_symbols=["USDX"])),
               _cert("XAUUSD", dict(BASE, factor_symbols=["USDX", "UST05Y"]),
                     family="pca_residual")]
    doc = bm.detect(healthy)
    assert doc["n_hits"] == 0 and doc["certificates"] == []
    path = _roster(isolated, healthy)
    before = path.read_text()
    assert bm.retire_sleeves(doc, path, apply=True) == []
    assert path.read_text() == before
    assert bm.missed_growth_lines([], doc, "t") == []


def test_basket_certified_after_the_fix_is_never_flagged(isolated) -> None:
    """The same USDX+UST10Y identity certified after ef11ff615 was built on its full basket
    (build_cell refuses a partial one), so it is not a mismatch, and its boundary is exact."""
    fixed = bm.PARTIAL_BASKET_FIXED_AT.isoformat()
    after = [_cert("XAUAUD", at=AFTER), _cert("XAUEUR", at=fixed)]
    doc = bm.detect(after)
    assert doc["n_hits"] == 0
    path = _roster(isolated, after)
    before = path.read_text()
    assert bm.retire_sleeves(doc, path, apply=True) == []
    assert path.read_text() == before
    one_second_before = "2026-09-28T06:00:58+00:00"
    assert bm.detect([_cert("XAUEUR", at=one_second_before)])["n_hits"] == 1


# ------------------------------------------------------------------------------- missed growth

def test_every_retirement_carries_an_unmeasured_missed_growth_line(isolated) -> None:
    hit = _cert()
    doc = bm.detect([hit])
    path = isolated / "sleeves.json"
    path.write_text(json.dumps({"sleeves": [
        {"name": "a", "status": "STANDBY", "risk_frac": 0.0, "certificate": {"cell": hit["name"]}},
        {"name": "b", "status": "LIVE", "risk_frac": 0.012, "risk_frac_source": "allocator",
         "certificate": {"cell": hit["name"]}}]}))
    retired = bm.retire_sleeves(doc, path, apply=True)
    lines = bm.missed_growth_lines(retired, doc, "2026-10-20T00:00:00+00:00")
    assert [x["sleeve"] for x in lines] == ["a", "b"]
    b = lines[1]
    assert b["gate"] == "basket_mismatch" and b["certificate"] == hit["name"]
    assert b["risk_frac_before"] == 0.012 and b["from_status"] == "LIVE"
    assert b["forward_evidence"]["status"] == "UNMEASURED" and b["verdict"] == "UNMEASURED"
    assert "UST10Y" in b["why"] and b["value"] is None
    # cumulative: the next pass retires nothing new and keeps the bill
    again = bm.missed_growth_lines([], doc, "later", lines)
    assert again == lines


def test_missed_growth_carries_the_gates_published_lines(tmp_path, monkeypatch) -> None:
    import missed_growth as mg
    path = tmp_path / "BASKET_MISMATCH.json"
    monkeypatch.setattr(mg, "BASKET_MISMATCH", path)
    assert mg.basket_mismatch_lines()["verdict"] == mg.UNMEASURED      # absent: never a zero
    path.write_text(json.dumps({"missed_growth": []}))
    assert mg.basket_mismatch_lines()["verdict"] == mg.NOT_BINDING
    path.write_text(json.dumps({"missed_growth": [
        {"gate": "basket_mismatch", "sleeve": "b", "risk_frac_before": 0.012,
         "verdict": "UNMEASURED"}]}))
    m = mg.basket_mismatch_lines()
    assert m["verdict"] == mg.UNMEASURED and m["n_retired"] == 1
    assert m["risk_frac_retired"] == pytest.approx(0.012)

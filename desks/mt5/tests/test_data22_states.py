"""DATA-22: upgraded BETA, multi-country GC, OMST unusual-options ranking and HDS holder state.

Everything is synthetic and offline: bars are generated, the rate archives and the option-chain
snapshots are written to tmp_path, and the EDGAR documents are minimal hand-built filings."""
from __future__ import annotations

import gzip
import json
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import beta_state as bs  # noqa: E402
from macro import global_curves as gc  # noqa: E402
from macro import market_state as ms  # noqa: E402
from macro import option_chains as oc  # noqa: E402
from macro import ownership_state as hds  # noqa: E402
from macro import unusual_options as uo  # noqa: E402

from libs.research import sensor_contract as sc  # noqa: E402

NOW = datetime(2026, 10, 6, 15, 0, tzinfo=UTC)


def _days(n: int, end: date = date(2026, 10, 5)) -> list[str]:
    return [(end - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


def _pair(n: int = 600, seed: int = 7, up: float = 0.5, down: float = 1.5
          ) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 0.01, n)
    y = np.where(x > 0, up * x, down * x) + rng.normal(0, 0.002, n)
    days = _days(n + 1)
    bx = 100 * np.exp(np.concatenate([[0], np.cumsum(x)]))
    by = 50 * np.exp(np.concatenate([[0], np.cumsum(y)]))
    return list(zip(days, bx.tolist(), strict=True)), list(zip(days, by.tolist(), strict=True))


# ============================================================================== BETA
def test_conditional_beta_recovers_planted_up_and_down_betas() -> None:
    b, s = _pair()
    st = bs.symbol_state(b, s)
    cb = st["conditional"]
    assert cb["up_beta"] == pytest.approx(0.5, abs=0.05)
    assert cb["down_beta"] == pytest.approx(1.5, abs=0.05)
    assert cb["beta_asym"] == pytest.approx(1.0, abs=0.08)
    short = bs.symbol_state(b[:100], s[:100])
    assert short["status"] == "UNMEASURED" and "< 253" in short["why"]


def test_tail_dependence_is_one_for_comonotone_and_near_q_for_independent() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(size=2000)
    td = bs.tail_dependence(x, 2 * x)
    assert td["lower_tail"] == 1.0 and td["upper_tail"] == 1.0
    ind = bs.tail_dependence(x, rng.normal(size=2000))
    assert ind["lower_tail"] < 0.15 and ind["upper_tail"] < 0.15
    thin = bs.tail_dependence(x[:100], x[:100])
    assert thin["lower_tail"] is None and "exceedances" in thin["why"]


def test_engle_granger_finds_a_planted_cointegration_and_its_half_life() -> None:
    rng = np.random.default_rng(3)
    n = 1500
    lx = np.cumsum(rng.normal(0, 0.01, n)) + 4.0
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = 0.9 * e[i - 1] + rng.normal(0, 0.005)
    eg = bs.engle_granger(0.8 * lx + 1.0 + e, lx)
    assert eg["cointegrated_5pct"] is True and eg["p_band"] == "1%"
    assert eg["hedge_ratio"] == pytest.approx(0.8, abs=0.05)
    assert eg["half_life_days"] == pytest.approx(-math.log(2) / math.log(0.9), rel=0.35)
    walk = bs.engle_granger(np.cumsum(rng.normal(0, 0.01, n)), lx)
    assert walk["cointegrated_5pct"] is False
    assert bs.engle_granger(lx[:30], lx[:30])["status"] == "UNMEASURED"


def _own(days: list[str]) -> dict[str, list[tuple[str, float]]]:
    """Own-bars regime: the first half calm contango, the second half inverted and high."""
    half = len(days) // 2
    lvl = [(d, 12.0 + 0.001 * i if i < half else 40.0 + 0.001 * i) for i, d in enumerate(days)]
    inv = [(d, 0.0 if i < half else 1.0) for i, d in enumerate(days)]
    return {"OWN_VIX": lvl, "OWN_VIX_INVERTED": inv}


def test_regime_beta_conditions_on_the_prior_close_regime() -> None:
    rng = np.random.default_rng(5)
    n = 600
    days = _days(n + 1)
    x = rng.normal(0, 0.01, n)
    half = (n + 1) // 2
    # beta 0.3 while calm, 1.8 once the own-bars state inverts
    y = np.array([(0.3 if i + 1 <= half else 1.8) * v for i, v in enumerate(x)]) \
        + rng.normal(0, 0.001, n)
    b = list(zip(days, (100 * np.exp(np.concatenate([[0], np.cumsum(x)]))).tolist(),
                 strict=True))
    s = list(zip(days, (50 * np.exp(np.concatenate([[0], np.cumsum(y)]))).tolist(),
                 strict=True))
    regimes = bs.regime_by_day(_own(days))
    # PIT: day 21's tier is ranked against the days BEFORE it only
    assert days[0] not in regimes and days[25] in regimes
    st = bs.symbol_state(b, s, regimes)
    rb = st["regime_beta"]
    calm = [v for k, v in rb.items() if k.startswith("vol_contango") and v.get("beta")]
    stress = [v for k, v in rb.items() if k.startswith("vol_backwardation") and v.get("beta")]
    assert calm and stress
    assert max(v["beta"] for v in calm) < 0.5 and min(v["beta"] for v in stress) > 1.5
    assert bs.regime_betas(days[1:], x, y, {})["status"] == "UNMEASURED"


def test_rolling_rows_are_stamped_next_midnight_and_never_after_now() -> None:
    b, s = _pair(400)
    rows = bs.rolling_rows(b, s, now=NOW, roll_days=50)
    assert rows and len(rows) <= 50
    assert all(datetime.fromisoformat(r["available_time"]) <= NOW for r in rows)
    last = rows[-1]
    assert last["available_time"] == bs.available_time(last["event_time"])
    assert last["available_time"].endswith("T00:00:00+00:00")
    # the window ending on the newest day (2026-10-05) is knowable 10-06 00:00 <= NOW
    assert last["event_time"] == "2026-10-05"
    early = bs.rolling_rows(b, s, now=datetime(2026, 10, 5, 23, tzinfo=UTC), roll_days=50)
    assert early[-1]["event_time"] == "2026-10-04"


def _bars(rows: list[tuple[str, float]]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=20) for d, _ in rows])
    vals = [v for _, v in rows]
    return pd.DataFrame({"open": vals, "close": vals}, index=idx)


def test_market_state_carries_the_upgraded_beta_and_emits_through_the_gate(
        tmp_path: Path) -> None:
    b, s = _pair(400)
    charts = {"US500": _bars(b), "XAUUSD": _bars(s)}
    ext = ms.extended(charts, {}, NOW, own=_own([d for d, _ in b]),
                      ownership_root=tmp_path / "none")
    blk = ext["beta_upgraded"]
    assert blk["status"] == "MEASURED" and blk["data_source"] == "mt5:bars"
    assert blk["symbols"]["XAUUSD"]["status"] == "MEASURED"
    assert blk["symbols"]["EURUSD"]["status"] == "UNMEASURED"
    assert ext["ownership"]["status"] == "UNMEASURED"
    out = ms.emit_extended({"beta_upgraded": blk, "global_curves": {}}, charts, NOW,
                           dry_run=True)
    cells = out["beta_upgraded"]
    assert [c["symbol"] for c in cells] == ["XAUUSD"]
    assert cells[0]["cells"]["emitted"] > 0               # mt5:bars is admitted
    obs = bs.observations(blk, NOW)
    assert obs and all(not sc.defects(o) for o in obs)
    assert {o.metric for o in obs} >= {"up_beta", "down_beta", "coint_adf_t"}


# ============================================================================== GC
def _monthly(n: int, v0: float, step: float) -> list[tuple[str, float]]:
    out, d = [], date(2020, 1, 1)
    for i in range(n):
        out.append((d.isoformat(), v0 + step * i))
        d = date(d.year + (d.month // 12), d.month % 12 + 1, 1)
    return out


def test_global_curves_pit_terms_and_partial_countries(tmp_path: Path) -> None:
    ser = {"IRLTLT01DEM156N": _monthly(80, 1.0, 0.02),
           "IR3TIB01DEM156N": _monthly(80, 0.5, 0.01)}
    ecb = tmp_path / "ecb.json"
    pts10 = [{"d": d, "v": 3.0 + 0.001 * i} for i, d in enumerate(_days(300))]
    pts1 = [{"d": d, "v": 2.0} for d in _days(300)]
    ecb.write_text(json.dumps({"series": {"eur_aaa_10y": {"points": pts10},
                                          "eur_aaa_1y": {"points": pts1}}}), "utf-8")
    bis = tmp_path / "bis.json"
    bis.write_text(json.dumps({"rows": [
        {"knowable_at": "2026-09", "base": "JPY", "quote": "USD", "base_rate": 0.5,
         "quote_rate": 4.0}]}), "utf-8")
    g = gc.build(now=NOW, series=ser, ecb=ecb, bis=bis, boe=tmp_path / "no.jsonl",
                 snb=tmp_path / "no.jsonl")
    de = g["countries"]["DE"]
    assert de["status"] == "MEASURED" and de["terms"] == "admitted"
    assert de["long_source"] == "fred:IRLTLT01DEM156N"
    # PIT: a month-start stamp is knowable 75 days later, so the newest readable month is the
    # last one whose stamp + 75 days <= NOW
    assert datetime.fromisoformat(de["knowable_at"]) <= NOW
    assert date.fromisoformat(de["slope_date"]) <= (NOW - gc.MONTHLY_LAG).date()
    ea = g["countries"]["EA"]
    assert ea["status"] == "MEASURED" and ea["terms"] == "HELD"
    assert ea["long_source"] == "ecb:yc:aaa_10y" and ea["slope"] == pytest.approx(1.299, abs=1e-3)
    jp = g["countries"]["JP"]
    assert jp["status"] == "PARTIAL" and jp["short"] == 0.5 and jp["long"]["status"] == "UNMEASURED"
    assert g["countries"]["NO"]["status"] == "UNMEASURED"
    cells = {c["country"]: c for c in gc.emit(g, dry_run=True)}
    assert cells["DE"]["cells"]["emitted"] > 0
    assert cells["EA"]["cells"]["emitted"] == 0 and cells["EA"]["cells"]["status"] == "HELD_TERMS"
    assert "history" not in gc.public(g)["countries"]["DE"]
    obs = gc.observations(g, NOW)
    assert obs and all(not sc.defects(o) for o in obs)


# ============================================================================== OMST
def _snap(path: Path, stamp: str, strikes: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump({"knowable_at": stamp, "quote_time": stamp, "front_strikes": strikes}, fh)


def _c(k: float, cp: str, oi: float, vol: float, mid: float = 2.0) -> dict[str, Any]:
    return {"expiry": "2026-10-16", "cp": cp, "strike": k, "oi": oi, "volume": vol,
            "bid": mid - 0.05, "ask": mid + 0.05}


def test_unusual_options_ranks_new_positioning_and_holds_cells(tmp_path: Path) -> None:
    d = tmp_path / "oc"
    base = [_c(500 + i, "C" if i % 2 else "P", 1000, 50) for i in range(10)]
    _snap(d / "SPY" / "20261005T150000Z.json.gz", "2026-10-05T15:00:00+00:00", base)
    hot = [dict(c) for c in base]
    hot[3] = _c(503, "C", 4000, 5000, mid=3.0)            # volume 5x OI and OI quadrupled
    _snap(d / "SPY" / "20261006T150000Z.json.gz", "2026-10-06T15:00:00+00:00", hot)
    terms = oc.terms_status()
    assert terms["status"] == "HELD"
    doc = uo.build(d, {"SPY": "US500", "GLD": "XAUUSD"}, terms=terms,
                   series_root=tmp_path / "lake")
    spy = doc["symbols"]["SPY"]
    assert spy["status"] == "MEASURED" and spy["snapshots"] == 2 and spy["has_prior"]
    assert spy["top"][0]["strike"] == 503 and spy["top"][0]["unusual"] is True
    assert spy["top"][0]["oi_change_z"] is not None and spy["top"][0]["oi_change_z"] > 3
    assert spy["unusual_count"] == 1 and spy["unusual_call_premium_share"] == 1.0
    assert spy["cells"]["emitted"] == 0 and spy["cells"]["status"] == "HELD_TERMS"
    assert spy["lake"]["status"] == "WRITTEN" and spy["lake"]["rows"] == 2
    assert doc["symbols"]["GLD"]["status"] == "UNMEASURED"
    assert doc["cells_emitted"] == 0 and doc["status"] == "MEASURED"
    empty = uo.build(tmp_path / "nothing", {"SPY": "US500"}, terms=terms, dry_run=True)
    assert empty["status"] == "UNMEASURED"


# ============================================================================== HDS
FORM4 = """<SEC-HEADER>ACCEPTANCE-DATETIME>20260915163000
</SEC-HEADER>
<?xml version="1.0"?>
<ownershipDocument>
 <issuer><issuerCik>1</issuerCik><issuerName>Acme Corp</issuerName>
  <issuerTradingSymbol>ACME</issuerTradingSymbol></issuer>
 <reportingOwner><reportingOwnerId><rptOwnerName>{owner}</rptOwnerName></reportingOwnerId>
 </reportingOwner>
 <nonDerivativeTable>
  <nonDerivativeTransaction>
   <transactionDate><value>2026-09-14</value></transactionDate>
   <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
   <transactionAmounts><transactionShares><value>1,000</value></transactionShares>
    <transactionPricePerShare><value>20.5</value></transactionPricePerShare>
    <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
   </transactionAmounts>
  </nonDerivativeTransaction>
 </nonDerivativeTable>
</ownershipDocument>"""

F13 = """ACCEPTANCE-DATETIME>{acc}
CONFORMED SUBMISSION TYPE:\t13F-HR
CONFORMED PERIOD OF REPORT:\t{period}
FILER:
\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME:\t\t\t{filer}
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
 <infoTable><nameOfIssuer>ACME CORP</nameOfIssuer><cusip>000000AA1</cusip><value>100</value>
  <shrsOrPrnAmt><sshPrnamt>{shares}</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
 </infoTable>
 <infoTable><nameOfIssuer>ACME CORP</nameOfIssuer><cusip>000000AA1</cusip><value>5</value>
  <shrsOrPrnAmt><sshPrnamt>999</sshPrnamt></shrsOrPrnAmt><putCall>Call</putCall></infoTable>
</informationTable>"""

D13 = """ACCEPTANCE-DATETIME>20260920090000
CONFORMED SUBMISSION TYPE:\tSC 13D
SUBJECT COMPANY:
\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME:\t\t\tACME CORP
FILED BY:
\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME:\t\t\tActivist LP
(13) PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (11): 7.4%"""


def test_ownership_parsers_and_state(tmp_path: Path) -> None:
    root = tmp_path / "edgar"
    assert hds.build(now=NOW, root=root)["why"] == hds.NO_FETCHER
    root.mkdir()
    (root / "f4a.xml").write_text(FORM4.format(owner="CEO", code="P"), "utf-8")
    (root / "f4b.xml").write_text(FORM4.format(owner="CFO", code="S"), "utf-8")
    (root / "q1.txt").write_text(F13.format(acc="20260515120000", period="20260331",
                                            filer="Fund A", shares="1,000"), "utf-8")
    (root / "q2.txt").write_text(F13.format(acc="20260814120000", period="20260630",
                                            filer="Fund A", shares="1,500"), "utf-8")
    (root / "d.txt").write_text(D13, "utf-8")
    (root / "late.txt").write_text(D13.replace("20260920", "20261020"), "utf-8")
    (root / "junk.txt").write_text("nothing here", "utf-8")
    st = hds.build(now=NOW, root=root)
    assert st["status"] == "MEASURED" and st["parse_failed"] == 1
    assert st["not_yet_knowable"] == 1                    # a filing accepted after NOW
    ins = st["insider_90d"]["ACME"]
    assert ins["buy_value"] == 20500.0 and ins["sell_value"] == 20500.0
    assert ins["n_buyers"] == 1 and ins["n_sellers"] == 1 and ins["net_value"] == 0.0
    blk = st["blockholders_90d"]["ACME CORP"]
    assert blk["activist"] == 1 and blk["max_percent"] == 7.4
    inst = st["institutional"]
    assert inst["period"] == "2026-06-30" and inst["prior_period"] == "2026-03-31"
    row = inst["holdings"]["000000AA1"]
    assert row["shares"] == 1500.0 and row["change_common_filers"] == 500.0   # put/call excluded
    assert "no statistical cell" in st["lane"]


def test_option_chains_report_carries_the_unusual_block(tmp_path: Path) -> None:
    doc = oc.run(now=datetime(2026, 10, 5, 20, 5, tzinfo=UTC), fetch=False, etfs=["SPY"],
                 data_dir=tmp_path / "oc", registry={"US500": {"symbol": "US500"}},
                 closes_fn=lambda s, n: [], vol_index_fn=lambda t: {}, dry_run=True)
    assert doc["unusual_options"]["status"] == "UNMEASURED"
    assert doc["unusual_options"]["terms"]["status"] == "HELD"

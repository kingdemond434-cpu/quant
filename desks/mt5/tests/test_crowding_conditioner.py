"""Crowding is measured from CFTC positioning, proposed two-sided, and only as far as evidenced."""
from __future__ import annotations

import contextlib
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import crowding_conditioner as C  # noqa: E402

NOW = datetime(2026, 11, 13, 21, 0, tzinfo=UTC)


def _weekly(vals: np.ndarray) -> pd.Series:
    idx = pd.date_range("2015-01-06", periods=len(vals), freq="7D", tz="UTC")
    return pd.Series(vals, index=idx)


def _crowded_series(n: int = 520) -> pd.Series:
    rng = np.random.default_rng(7)
    v = rng.normal(0, 0.02, n)
    v[-1] = 0.4                                      # a fresh extreme long
    v[-2] = 0.4
    return _weekly(v)


def test_state_reads_extremes_both_ways() -> None:
    assert C.state_of(2.5) == "CROWDED_LONG" and C.state_of(-2.1) == "CROWDED_SHORT"
    assert C.state_of(0.3) == "NEUTRAL" and C.state_of(None) == "UNMEASURED"


def test_zscore_is_lagged_and_sign_aligned() -> None:
    s = _crowded_series()
    z = C.zscore(s, -1.0)
    assert z.index[-1] == s.index[-1]
    assert z.iloc[-1] < -2          # lagged: reads the week before, already extreme
    assert C.zscore(s.iloc[:40], 1.0).empty


def test_modifier_is_two_sided_and_neutral_without_evidence() -> None:
    doc = {"evidence": {"k": 0.2}, "instruments": {"XAUUSD": {"state": "CROWDED_LONG"},
                                                    "EURUSD": {"state": "NEUTRAL"}}}
    assert C.modifier("XAUUSD", -1, doc) == 1.2       # against the crowd: more
    assert C.modifier("XAUUSD", +1, doc) == 0.8       # with it: less
    assert C.modifier("EURUSD", +1, doc) == 1.0
    assert C.modifier("XAUUSD", -1, {**doc, "evidence": {"k": 0.0}}) == 1.0


def _closes(sym: str, z: pd.Series, edge: float) -> pd.DataFrame:
    days = pd.date_range("2015-01-01", "2026-11-13", freq="B", tz="UTC")
    zd = z.reindex(z.index.union(days)).sort_index().ffill().reindex(days).fillna(0.0)
    rng = np.random.default_rng(3)
    r = rng.normal(0, 0.002, len(days)) - edge * np.sign(zd.to_numpy()) * (zd.abs() >= 2)
    return pd.DataFrame({sym: 100 * np.exp(np.cumsum(r))}, index=days)


def test_evidence_needs_a_measured_contrarian_return() -> None:
    rng = np.random.default_rng(11)
    z = _weekly(np.where(rng.random(620) < 0.25, rng.choice([-3.0, 3.0], 620), 0.0))
    good = C.evidence({"XAUUSD": z}, _closes("XAUUSD", z, 0.004))
    assert good["status"] == "EVIDENCED" and 0 < good["k"] <= C.K_MAX and good["n"] >= C.N_MIN
    flat = C.evidence({"XAUUSD": z}, _closes("XAUUSD", z, 0.0))
    assert flat["status"] == "UNPROVEN" and flat["k"] == 0.0


def test_build_gates_on_robots_and_names_what_it_cannot_read() -> None:
    called: list[str] = []

    def legacy(code):
        called.append(code)
        return _crowded_series()
    doc = C.build(legacy=legacy, tff=lambda c: pd.Series(dtype="float64"),
                  refusal=lambda u: "robots.txt disallows this path" if "gpe5" in u else None,
                  closes=pd.DataFrame(), now=NOW)
    assert doc["instruments"]["XAUUSD"]["legacy"]["state"] in ("CROWDED_LONG", "CROWDED_SHORT")
    assert doc["instruments"]["EURUSD"]["tff"]["why"].startswith("ROBOTS_REFUSED")
    assert "tff" not in doc["instruments"]["XAUUSD"]
    assert doc["evidence"]["status"] == "UNPROVEN" and doc["missed_growth"]
    assert doc["retail_sentiment"]["status"] == "UNMEASURED"     # no retail feed asked for
    assert len(called) == len(C.CS.COT_MAP)

    none = C.build(legacy=legacy, tff=legacy, refusal=lambda u: "unreadable",
                   closes=pd.DataFrame(), now=NOW)
    assert all(r["state"] == "UNMEASURED" for r in none["instruments"].values())


def test_tff_rows_parse_leveraged_funds_net_of_open_interest() -> None:
    rows = [{"report_date_as_yyyy_mm_dd": "2026-11-03", "lev_money_positions_long": "300",
             "lev_money_positions_short": "100", "open_interest_all": "1000"}]
    s = C._net_tff(rows)
    assert abs(float(s.iloc[0]) - 0.2) < 1e-12
    assert C._net_tff([{"report_date_as_yyyy_mm_dd": "2026-11-03"}]).empty


def test_robots_is_evaluated_for_the_agent_cot_source_sends(monkeypatch) -> None:
    """robots.txt disallowing only the agent the CFTC fetch sends refuses it (audit MF3)."""
    import io
    import urllib.request

    from libs.data import datahub_feeds as F

    sent: list[str] = []

    def fake(req, *_a, **_k):
        ua = req.get_header("User-agent")
        sent.append(ua)
        if req.full_url.endswith("/robots.txt"):
            return io.BytesIO(b"User-agent: quant-research\nDisallow: /\n\n"
                              b"User-agent: *\nAllow: /\n")
        raise AssertionError("a refused feed was requested")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    F._ROBOTS.clear()
    gate = C.robots_gate()
    assert gate(C.CS._BASE) and gate(C.TFF_BASE)
    assert F.robots_refusal(C.CS._BASE) is None        # datahub's agent would have passed
    assert set(sent) == {C.COT_AGENT, F.UA}
    F._ROBOTS.clear()


def test_the_gate_agent_is_the_agent_cot_source_sends(monkeypatch) -> None:
    import urllib.request
    seen: list[str] = []

    def fake(req, *_a, **_k):
        seen.append(req.get_header("User-agent"))
        raise OSError("stop")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with contextlib.suppress(OSError):
        C.CS._get("https://publicreporting.cftc.gov/resource/x.json")
    assert seen == [C.COT_AGENT]


def _ffaj_frame(n_months: int = 120, pair: str = "USDJPY") -> pd.DataFrame:
    """Synthetic FFAJ rows (no raw FFAJ data is ever committed): quiet, then retail piles long."""
    from libs.data import ffaj_retail_fx as FF
    rng = np.random.default_rng(5)
    rows = []
    for i in range(n_months):
        year, month = 2015 + i // 12, i % 12 + 1
        long_ = 100.0 + rng.normal(0, 2) + (60.0 if i >= n_months - 2 else 0.0)
        rows.append([float(month), float(year), 1.0, 100.0, long_, 100.0 + long_])
    return FF.parse_workbook([type("S", (), {"name": pair, "rows": rows})()])


def test_retail_crowd_is_measured_from_ffaj_and_judged_on_its_own_evidence() -> None:
    frame = _ffaj_frame()
    doc = C.build(legacy=lambda c: pd.Series(dtype="float64"),
                  tff=lambda c: pd.Series(dtype="float64"), refusal=lambda u: None,
                  closes=pd.DataFrame(), now=NOW, retail=lambda: (frame, ""))
    usdjpy = doc["instruments"]["USDJPY"]["retail"]
    assert usdjpy["state"] == "CROWDED_LONG" and usdjpy["z"] >= C.EXTREME_Z
    assert doc["retail_sentiment"]["status"] == "MEASURED"
    assert doc["retail_sentiment"]["pairs"] == ["USDJPY"]
    # a pair the frame does not carry is named, not guessed
    assert doc["instruments"]["EURJPY"]["retail"]["state"] == "UNMEASURED"
    assert doc["retail_evidence"]["status"] == "UNPROVEN" and doc["missed_growth"]


def test_retail_z_is_point_in_time() -> None:
    from libs.data import ffaj_retail_fx as FF
    s = FF.net_series(_ffaj_frame(), "USDJPY")
    last_month_end = pd.Timestamp("2024-12-31", tz="UTC")
    assert s.index[-1] == last_month_end + pd.Timedelta(days=FF.AVAILABLE_LAG_D)
    assert C.retail_zscore(s.iloc[:10]).empty


def test_retail_feed_failure_reads_unmeasured() -> None:
    def boom() -> tuple[pd.DataFrame, str]:
        raise OSError("down")
    for retail in (boom, lambda: (pd.DataFrame(), "ROBOTS_REFUSED: disallowed"), None):
        doc = C.build(legacy=lambda c: pd.Series(dtype="float64"),
                      tff=lambda c: pd.Series(dtype="float64"), refusal=lambda u: None,
                      closes=pd.DataFrame(), now=NOW, retail=retail)
        assert doc["retail_sentiment"]["status"] == "UNMEASURED"
        assert doc["retail_evidence"]["k"] == 0.0


def test_speculator_and_retail_factors_multiply_two_sided() -> None:
    doc = {"evidence": {"k": 0.2}, "retail_evidence": {"k": 0.1},
           "instruments": {"USDJPY": {"state": "CROWDED_LONG",
                                      "retail": {"state": "CROWDED_LONG"}},
                           "EURJPY": {"state": "UNMEASURED",
                                      "retail": {"state": "CROWDED_SHORT"}}}}
    assert abs(C.modifier("USDJPY", -1, doc) - 1.2 * 1.1) < 1e-12
    assert abs(C.modifier("USDJPY", +1, doc) - 0.8 * 0.9) < 1e-12
    assert abs(C.modifier("EURJPY", +1, doc) - 1.1) < 1e-12
    assert C.modifier("USDJPY", -1, {**doc, "retail_evidence": {"k": 0.0}}) == 1.2

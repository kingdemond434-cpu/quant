"""dealer_gamma_proxy: the gate refuses before it fetches, the math has the right sign, and the
ingest self-records a PIT series the exogenous conditioner can read."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import dealer_gamma_proxy as dg  # noqa: E402


class _Resp:
    def __init__(self, status: int, text: str = "", payload: object = None) -> None:
        self.status_code = status
        self.text = text
        self.content = text.encode("latin-1")
        self._payload = payload

    def json(self) -> object:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _getter(routes: dict[str, _Resp], seen: list[str]):
    def get(url: str, **_kw: object) -> _Resp:
        seen.append(url)
        for key, resp in routes.items():
            if key in url:
                return resp
        return _Resp(404)
    return get


@pytest.fixture
def terms(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stand-in host with terms on record: the real Deribit host is refused by its terms."""
    monkeypatch.delitem(dg.REFUSED_HOSTS, "www.deribit.com", raising=False)
    monkeypatch.setitem(dg.TERMS, "www.deribit.com",
                        {"url": "https://example.invalid/terms", "quote": "test", "checked": "x"})


def _deribit_payload() -> dict[str, object]:
    rows = []
    for k, cp, oi in ((90.0, "P", 500.0), (100.0, "C", 100.0), (100.0, "P", 100.0),
                      (110.0, "C", 50.0)):
        rows.append({"instrument_name": f"BTC-26DEC30-{int(k)}-{cp}", "open_interest": oi,
                     "mark_iv": 60.0, "underlying_price": 100.0})
    return {"result": rows}


def test_unknown_host_is_never_fetched() -> None:
    seen: list[str] = []
    feed = dg.Feed(_getter({}, seen), pace_s=0.0)
    assert feed.fetch("https://unlisted.example.com/x") is None
    assert seen == []
    assert feed.refused["unlisted.example.com"].startswith("TERMS_UNCONFIRMED")


def test_refused_host_is_never_fetched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(dg.TERMS, "cdn-api.cboe.com", {"url": "", "quote": "", "checked": ""})
    seen: list[str] = []
    feed = dg.Feed(_getter({}, seen), pace_s=0.0)
    url = "https://cdn-api.cboe.com/api/global/delayed_quotes/options/_SPX.json"
    assert feed.fetch(url) is None
    assert seen == []
    assert feed.refused["cdn-api.cboe.com"].startswith("TERMS_REFUSED")


@pytest.mark.parametrize("robots", [_Resp(500), _Resp(200, "<!DOCTYPE html><html>"),
                                    _Resp(200, "User-agent: *\nDisallow: /api/\n")])
def test_robots_fails_closed(terms: None, robots: _Resp) -> None:
    seen: list[str] = []
    feed = dg.Feed(_getter({"robots.txt": robots}, seen), pace_s=0.0)
    url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC"
    assert feed.fetch(url, as_json=True) is None
    assert seen == ["https://www.deribit.com/robots.txt"]
    assert feed.refused["www.deribit.com"].startswith("ROBOTS_REFUSED")


def test_hard_stop_is_not_retried(terms: None) -> None:
    seen: list[str] = []
    feed = dg.Feed(_getter({"get_book": _Resp(429)}, seen), pace_s=0.0)
    url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC"
    assert feed.fetch(url, as_json=True) is None
    assert feed.fetch(url, as_json=True) is None
    assert sum("get_book" in u for u in seen) == 1
    assert feed.refused["www.deribit.com"] == "HARD_STOP: HTTP 429"


def test_profile_sign_and_flip() -> None:
    t = 30 / 365
    calls_only = dg.profile([(100.0, t, 0.3, 1000.0, True)], 100.0, 1.0)
    puts_only = dg.profile([(100.0, t, 0.3, 1000.0, False)], 100.0, 1.0)
    assert calls_only["net_gex_per_1pct"] > 0 and calls_only["net_gex_norm"] == 1.0
    assert puts_only["net_gex_per_1pct"] < 0 and puts_only["net_gex_norm"] == -1.0
    mixed = dg.profile([(110.0, t, 0.3, 1000.0, True), (90.0, t, 0.3, 1000.0, False)],
                       100.0, 1.0)
    assert mixed["zero_gamma_flip"] is not None and 90.0 < mixed["zero_gamma_flip"] < 110.0
    assert mixed["pcr_oi"] == 1.0
    assert mixed["call_wall"] == 110.0 and mixed["put_wall"] == 90.0


def test_hkex_expiry_is_second_last_business_day() -> None:
    assert dg.hkex_expiry("NOV-26") == dt.date(2026, 11, 27)
    assert dg.hkex_expiry("DEC-26") == dt.date(2026, 12, 30)


def test_ingest_self_records_and_publishes_pit_series(tmp_path: Path, terms: None,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("pyarrow")
    monkeypatch.setattr(dg, "BOOKS", tuple(b for b in dg.BOOKS if b[0] == "deribit_btc"))
    seen: list[str] = []
    get = _getter({"robots.txt": _Resp(404),
                   "get_book": _Resp(200, payload=_deribit_payload())}, seen)
    now = dt.datetime(2026, 11, 24, 12, 0, tzinfo=dt.UTC)
    snap = dg.ingest(get=get, now=now, data_dir=tmp_path, pace_s=0.0)
    assert snap["new_rows"] == 1 and snap["books"]["deribit_btc"]["state"] == "LIVE"
    again = dg.ingest(get=get, now=now, data_dir=tmp_path, pace_s=0.0)
    assert again["new_rows"] == 0                           # one row per (book, day)
    hist = (tmp_path / "dealer_gamma" / "history.jsonl").read_text().splitlines()
    assert len(hist) == 1 and json.loads(hist[0])["symbol"] == "BTCUSD"
    import pandas as pd
    frame = pd.read_parquet(tmp_path / "lake" / "series" / "dealer_gamma_BTCUSD.parquet")
    assert "available_time" in frame.columns and "net_gex_norm" in frame.columns
    assert json.loads((tmp_path / "dealer_gamma_proxy.json").read_text())["history_rows"] == 1


def test_ingest_records_refusals_without_writing_rows(tmp_path: Path) -> None:
    seen: list[str] = []
    snap = dg.ingest(get=_getter({}, seen), now=dt.datetime(2026, 11, 24, 12, tzinfo=dt.UTC),
                     data_dir=tmp_path, pace_s=0.0)
    unconfirmed = [b for b, c in snap["books"].items() if c["host"] not in dg.TERMS]
    for b in unconfirmed:
        assert snap["books"][b]["state"] == "REFUSED"
    assert snap["new_rows"] == 0
    assert not any(u.split("/")[2] not in dg.TERMS for u in seen)


def test_cells_wait_for_history(tmp_path: Path) -> None:
    rep = dg.run(dry_run=True, series_dir=tmp_path)
    assert rep["cells_proposed"] == 0
    assert rep["cells_declared"] == (len(dg.CELLS) * len({b[1] for b in dg.BOOKS})
                                     + len(dg.PRICE_CELLS) * len(dg.PRICE_SYMBOLS))
    assert all(w["needs"] == dg.MIN_HISTORY_DAYS for w in rep["cells_waiting_for_history"])


def test_every_book_host_has_a_terms_verdict() -> None:
    """No book points at a host with neither terms on record nor a recorded refusal."""
    for book, _sym, host, _eod, _pull in dg.BOOKS:
        assert host in dg.TERMS or host in dg.REFUSED_HOSTS, book
        assert not (host in dg.TERMS and host in dg.REFUSED_HOSTS), book


def _synthetic_bars(sign: float, days: int = 80, seed: int = 7):
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-05", periods=days * 24, freq="h", tz="UTC")
    eps = rng.normal(0, 0.002, len(idx))
    r = np.zeros(len(idx))
    for i in range(1, len(idx)):
        r[i] = sign * 0.6 * r[i - 1] + eps[i]
    close = 100.0 * np.exp(np.cumsum(r))
    return pd.DataFrame({"high": close * 1.0005, "low": close * 0.9995, "close": close},
                        index=idx)


def test_price_proxy_reads_pinning_and_chasing() -> None:
    pinned = dg.price_proxy_frame(_synthetic_bars(-1.0), 1.0)
    chasing = dg.price_proxy_frame(_synthetic_bars(1.0), 1.0)
    assert pinned is not None and chasing is not None
    assert pinned["pin_score"].dropna().mean() > 0.3
    assert chasing["pin_score"].dropna().mean() < -0.3
    assert chasing["range_rv"].dropna().mean() > pinned["range_rv"].dropna().mean()


def test_price_proxy_has_no_lookahead() -> None:
    bars = _synthetic_bars(1.0)
    full = dg.price_proxy_frame(bars, 1.0)
    cut = dg.price_proxy_frame(bars.iloc[: 50 * 24], 1.0)
    common = cut["day"]
    a = full.set_index("day").loc[common, ["pin_score", "range_rv", "volvol"]]
    b = cut.set_index("day")[["pin_score", "range_rv", "volvol"]]
    assert ((a - b).abs().fillna(0) < 1e-12).all().all()
    stamp = full["available_time"].dt.tz_convert(None)
    import pandas as pd
    assert (stamp > pd.to_datetime(full["day"])).all()


def test_price_proxy_publishes_and_its_cells_reach_the_grid(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    out = dg.publish_price_proxy(tmp_path, bars_for=lambda s: _synthetic_bars(-1.0)
                                 if s == "XAUUSD" else None)
    assert isinstance(out["XAUUSD"], int) and out["US500"].startswith("UNMEASURED")
    indices, pairs, cells = dg.declared(tmp_path)
    assert ("gamma_price:XAUUSD.pin_score", "XAUUSD") in pairs
    xau = [c for c in cells if c["symbol"] == "XAUUSD" and c["index"].startswith("gamma_price")]
    assert {c["cell_name"] for c in xau} == {c[0] for c in dg.PRICE_CELLS}
    assert all(c["params"]["source"] == "gamma_price_XAUUSD" for c in xau)

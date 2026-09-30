"""The keyless feeds the mined repos use: shaped, first-printed, certified, never knowable early."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.data import pit_certificate as pit  # noqa: E402
from libs.data import repo_mined_feeds as rmf  # noqa: E402

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def _days(n: int = 400) -> pd.DatetimeIndex:
    return pd.date_range(end=NOW.date() - timedelta(days=1), periods=n, freq="D")


def _gpr_raw(bump: float = 0.0) -> pd.DataFrame:
    d = _days()
    rng = np.random.default_rng(1)
    return pd.DataFrame({"DAY": d.strftime("%Y%m%d").astype(int),
                         "GPRD": rng.gamma(4, 25, len(d)) + bump,
                         "GPRD_ACT": rng.gamma(3, 20, len(d)),
                         "GPRD_THREAT": rng.gamma(3, 30, len(d)), "event": ""})


def _epu_raw() -> pd.DataFrame:
    d = _days()
    return pd.DataFrame({"day": d.day, "month": d.month, "year": d.year,
                         "daily_policy_index": np.random.default_rng(2).gamma(5, 30, len(d))})


def _fng_raw() -> pd.DataFrame:
    d = _days()
    vals = np.random.default_rng(3).integers(5, 95, len(d))
    return pd.DataFrame({"value": [str(x) for x in vals],
                         "value_classification": "Fear",
                         "timestamp": [str(int(t.timestamp())) for t in d]})


def test_shapers_read_each_documented_format():
    g = rmf._gpr_daily(_gpr_raw())
    assert list(g.columns) == ["gprd", "gprd_act", "gprd_threat"] and len(g) == 400
    assert g.index[-1] == pd.Timestamp(_days()[-1], tz="UTC")
    e = rmf._epu_daily(_epu_raw())
    assert list(e.columns) == ["daily_policy_index"] and e.index.is_monotonic_increasing
    f = rmf._fear_greed(_fng_raw())
    assert f["fng"].between(5, 95).all() and len(f) == 400
    assert rmf._gpr_daily(pd.DataFrame({"x": [1]})) is None


def _absorb(tmp_path: Path, now: datetime, raw: dict[str, pd.DataFrame]) -> dict:
    reg: dict = {"by_url": {}, "series": {}}
    by_url = {f.url: raw[f.name] for f in rmf.FEEDS}
    rep = rmf.absorb(reg, tmp_path, fetch=lambda u: (b"x", "csv"),
                     parse=lambda b, u: by_url[u], certify=pit.certify,
                     write_certificate=lambda c: None, now=now)
    return {"reg": reg, "rep": rep}


def test_every_feed_is_certified_with_authority_and_never_knowable_early(tmp_path):
    raw = {"gpr_daily": _gpr_raw(), "epu_us_daily": _epu_raw(), "crypto_fear_greed": _fng_raw()}
    first = _absorb(tmp_path, NOW, raw)
    # the first pass records the schema hash; like every acquired series, authority comes on the
    # next hourly pass, once the schema has something to be compared with
    assert {m["pit_blocking"] == ["schema"] for m in first["reg"]["series"].values()} == {True}
    reg = first["reg"]
    by_url = {f.url: raw[f.name] for f in rmf.FEEDS}
    rep = rmf.absorb(reg, tmp_path, fetch=lambda u: (b"x", "csv"), parse=lambda b, u: by_url[u],
                     certify=pit.certify, write_certificate=lambda c: None,
                     now=NOW + timedelta(hours=1))
    out = {"reg": reg, "rep": rep}
    series = out["reg"]["series"]
    assert out["rep"]["kept"] == 3
    assert {"gpr_daily_gprd", "epu_us_daily_daily_policy_index",
            "crypto_fear_greed_fng"} <= set(series)
    for name, meta in series.items():
        assert meta["pit_authority"] is True, (name, meta["pit_blocking"])
        s = pd.read_parquet(meta["path"])["value"]
        assert s.index.max() <= pd.Timestamp(NOW + timedelta(hours=1))
    # pre-ledger history of a restated index is stamped `settle` after its event
    first = pd.read_parquet(series["epu_us_daily_daily_policy_index"]["path"]).index[0]
    assert first == pd.Timestamp(_days()[0], tz="UTC") + pd.Timedelta(days=30)


def test_the_first_print_is_served_after_the_source_restates(tmp_path):
    raw = {"gpr_daily": _gpr_raw(), "epu_us_daily": _epu_raw(), "crypto_fear_greed": _fng_raw()}
    one = _absorb(tmp_path, NOW, raw)
    path = one["reg"]["series"]["gpr_daily_gprd"]["path"]
    before = pd.read_parquet(path)["value"].copy()
    later = NOW + timedelta(days=2)
    restated = _gpr_raw(bump=500.0)
    extra = restated.iloc[[-1]].copy()
    extra["DAY"] = int((NOW + timedelta(days=1)).strftime("%Y%m%d"))
    two = _absorb(tmp_path, later, {**raw, "gpr_daily": pd.concat([restated, extra])})
    after = pd.read_parquet(two["reg"]["series"]["gpr_daily_gprd"]["path"])["value"]
    pd.testing.assert_series_equal(after.loc[before.index], before)   # restatement ignored
    assert after.index[-1] == pd.Timestamp(later)                     # new day: seen now
    ledger = json.loads((tmp_path / "first_print" / "gpr_daily.json").read_text())
    assert ledger["started_at"] == NOW.isoformat()


def test_unreachable_or_misshapen_feeds_are_refused_by_name(tmp_path):
    reg: dict = {"by_url": {}, "series": {}}
    rep = rmf.absorb(reg, tmp_path, fetch=lambda u: (None, "unreachable"),
                     parse=lambda b, u: None, certify=pit.certify,
                     write_certificate=lambda c: None, now=NOW)
    assert rep["kept"] == 0 and rep["refusals"] == {"unreachable": 3}
    assert all(v["status"] == "REFUSED" for v in reg["by_url"].values())


def test_acquirer_runs_the_mined_feeds():
    text = (_DESK / "research" / "acquire_datasets.py").read_text("utf-8")
    assert "repo_mined_feeds" in text and "_rmf.absorb(" in text

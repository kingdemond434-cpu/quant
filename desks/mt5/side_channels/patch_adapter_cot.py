#!/usr/bin/env python3
"""Patch crypto_adapter.py: attach COT positioning series to BTC/ETH symbols."""
from pathlib import Path

p = Path("/home/quant/quant-platform/libs/autodiscovery/crypto_adapter.py")
src = p.read_text()

# 1) Add the COT loader after _load_producer_economics usage in _read_frames
old_read = '''def _read_frames(symbols: Sequence[str], timeframe: Timeframe, lake_root: str) -> dict[str, Any]:
    """Read + cache each symbol's lake frame once (indexed by timestamp)."""
    lake = ParquetLake(lake_root)
    econ, econ_symbols = _load_producer_economics(_PRODUCER_ECONOMICS)
    frames = {}
    for s in symbols:
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        frames[s] = lake.read_bars(Layer.BRONZE, s, timeframe).set_index("timestamp")
        # ONLY the symbols these economics belong to. Miners of BTC are compelled to sell BTC; the
        # forced flow lands in that book and nowhere else. Stamping the series onto an alt would
        # assert a structural seller in a market that does not have one, which is how one genuine
        # mechanism gets laundered into a spurious edge across an entire universe.
        if econ and s in econ_symbols:
            _attach_producer(frames[s], econ)
    return frames'''

new_read = '''def _load_cot_series() -> dict[str, pd.Series]:
    """Load CFTC COT spec-share series per asset (btc/eth) from data/cot/*.parquet.

    NO-LOOKAHEAD: each COT row is stamped with ``pub_date`` = report date + 4 calendar days
    (published every Friday ~15:30 ET; +4d is the honest "available from" stamp for D1 bars
    that timestamp at bar START). Series are reindexed onto a symbol's bar index with
    PAST-ONLY ffill keyed on pub_date, exactly like the BTC reference close: a bar sees the
    last COT report whose publication preceded it, never the current one.
    """
    base = Path(_LAKE_ROOT).parent / "data" / "cot"
    out: dict[str, pd.Series] = {}
    for asset in ("btc", "eth"):
        path = base / f"{asset}.parquet"
        if not path.exists():
            continue
        cot = pd.read_parquet(path)
        if cot.empty or "pub_date" not in cot.columns:
            continue
        out[asset] = pd.Series(
            cot["net_spec"].to_numpy("float64") / cot["oi"].clip(lower=1.0).to_numpy("float64"),
            index=pd.DatetimeIndex(pd.to_datetime(cot["pub_date"])),
        ).sort_index()
    return out


def _attach_cot(df: pd.DataFrame, asset: str | None, cot: dict[str, pd.Series]) -> None:
    """Attach COT spec/comm share columns to one symbol frame (past-only ffill)."""
    if asset is None or asset not in cot:
        return
    s = cot[asset].reindex(df.index, method="ffill")
    if not s.isna().all():
        df["cot_spec_share"] = s.to_numpy("float64")


_COT_ASSET: dict[str, str] = {
    "BTCUSDT": "btc", "BTCUSD": "btc", "BTCUSDC": "btc",
    "ETHUSDT": "eth", "ETHUSD": "eth", "ETHUSDC": "eth",
}


def _read_frames(symbols: Sequence[str], timeframe: Timeframe, lake_root: str) -> dict[str, Any]:
    """Read + cache each symbol's lake frame once (indexed by timestamp)."""
    lake = ParquetLake(lake_root)
    econ, econ_symbols = _load_producer_economics(_PRODUCER_ECONOMICS)
    cot = _load_cot_series()
    frames = {}
    for s in symbols:
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        frames[s] = lake.read_bars(Layer.BRONZE, s, timeframe).set_index("timestamp")
        # ONLY the symbols these economics belong to. Miners of BTC are compelled to sell BTC; the
        # forced flow lands in that book and nowhere else. Stamping the series onto an alt would
        # assert a structural seller in a market that does not have one, which is how one genuine
        # mechanism gets laundered into a spurious edge across an entire universe.
        if econ and s in econ_symbols:
            _attach_producer(frames[s], econ)
        # COT is per-ASSET (CME futures on BTC and ETH), so only symbols of that asset get it.
        # Same discipline as producer economics: a BTC positioning meter on an alt's book would
        # assert a crowd that is not there.
        if s in _COT_ASSET:
            _attach_cot(frames[s], _COT_ASSET[s], cot)
    return frames'''

if old_read not in src:
    print("_read_frames pattern not found")
    raise SystemExit(2)
src = src.replace(old_read, new_read)

# 2) Wire into provider
old_prov = '''        funding = df["funding"].to_numpy("float64") if "funding" in df.columns else None
        # PRODUCER ECONOMICS, for treasury_cost_base_liquidation. Attached exactly as funding is:'''
new_prov = '''        funding = df["funding"].to_numpy("float64") if "funding" in df.columns else None
        cot_spec = (df["cot_spec_share"].to_numpy("float64")
                    if "cot_spec_share" in df.columns else None)
        # PRODUCER ECONOMICS, for treasury_cost_base_liquidation. Attached exactly as funding is:'''
if old_prov not in src:
    print("provider funding pattern not found")
    raise SystemExit(3)
src = src.replace(old_prov, new_prov)

old_kw = '''            funding=funding,
            hashprice=hashprice,'''
new_kw = '''            funding=funding,
            cot_spec_share=cot_spec,
            hashprice=hashprice,'''
if old_kw not in src:
    print("MarketSeries kwargs pattern not found")
    raise SystemExit(4)
src = src.replace(old_kw, new_kw)

p.write_text(src)
print("Patched crypto_adapter.py")
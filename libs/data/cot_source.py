"""CFTC Commitments-of-Traders (COT) source -- free weekly speculator positioning.

Pulls legacy futures-only non-commercial (large speculator) positioning from the CFTC public
reporting API and turns it into a per-instrument *positioning z-score* aligned to MT5 symbols. This
is the orthogonal-to-price sleeve: positioning extremes (crowded specs) precede mean reversion, a
documented risk premium not captured by trend/momentum. Weekly data (Tuesday snapshot, published
Friday); we lag it and forward-fill to daily, so no look-ahead.

Sign convention: CFTC FX futures are FOREIGN/USD. EUR/GBP/AUD futures match EURUSD/GBPUSD/AUDUSD
directly; JPY/CHF/CAD futures are the inverse of USDJPY/USDCHF/USDCAD, so their sign is flipped so a
positive z always means "specs crowded long the MT5 instrument".
"""

from __future__ import annotations

import urllib.request
from io import StringIO
from pathlib import Path

import pandas as pd

_BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# MT5 symbol -> (CFTC legacy contract_market_code, sign vs the MT5 instrument's direction)
COT_MAP: dict[str, tuple[str, float]] = {
    "XAUUSD": ("088691", +1.0),   # GOLD
    "XAGUSD": ("084691", +1.0),   # SILVER
    "XPTUSD": ("076651", +1.0),   # PLATINUM
    "XPDUSD": ("075651", +1.0),   # PALLADIUM
    "EURUSD": ("099741", +1.0),   # EURO FX  (EUR/USD)
    "GBPUSD": ("096742", +1.0),   # BRITISH POUND (GBP/USD)
    "AUDUSD": ("232741", +1.0),   # AUSTRALIAN DOLLAR (AUD/USD)
    "USDJPY": ("097741", -1.0),   # JAPANESE YEN (JPY/USD) -> invert for USDJPY
    "USDCHF": ("092741", -1.0),   # SWISS FRANC (CHF/USD) -> invert for USDCHF
    "USDCAD": ("090741", -1.0),   # CANADIAN DOLLAR (CAD/USD) -> invert for USDCAD
    # NYMEX 067651, the primary WTI venue (CFTC now names it "WTI-PHYSICAL"), as
    # scripts/refresh_cot_zcache.py:CODES already uses. 067411 is the ICE Europe WTI
    # look-alike: a different, thinner speculator book for the same MT5 instrument.
    "XTIUSD": ("067651", +1.0),   # WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE
}


#: THE DEFINITION OF `data/cot_zcache.parquet`, versioned (audit COT_AXIS_DEEPENING MF2,
#: 2026-10-14). Version 1 was the banked z history extended by a rolling z over a MIXTURE of
#: banked z-scores and raw contract counts on a daily forward-filled index; version 2 is the
#: 52-REPORT rolling z of RAW nets only (`scripts/refresh_cot_zcache.py:zscores_from_raw`),
#: rebuilt from source. The refresh stamps it into the parquet's own schema metadata, so the stamp
#: travels with the file wherever it is copied. The reader (`orthogonal_sweep._cot_frame`) refuses
#: a cache whose stamp differs, and `families_orthogonal.family_cot_positioning` carries the same
#: number as a LITERAL in its body -- so the family's code identity (`sleeve_registry.code_hash`,
#: `behaviour_hash`) changes with the definition, and every forward clock on the family is
#: restarted by the existing organs (shadow_forward verify -> IDENTITY_BROKEN ->
#: heal_identity_broken_clocks -> sleeve_registry.rebase_code, window RESET) instead of carrying
#: on over a redefined series. Bump this, the family's literal and the refresh together; the
#: suite fails if they disagree (tests/research/test_cot_zcache_refresh.py).
COT_ZCACHE_VERSION = 2
ZCACHE_VERSION_KEY = b"cot_zcache_version"
#: Where the refresh writes it and every reader looks (repository root `data/`).
ZCACHE = Path(__file__).resolve().parents[2] / "data" / "cot_zcache.parquet"


def write_zcache(frame: pd.DataFrame, path: object) -> None:
    """Write a z cache WITH its definition stamp in the parquet schema metadata (not atomic: the
    refresh writes a temporary file through this and renames it)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(frame)
    meta = dict(table.schema.metadata or {})
    meta[ZCACHE_VERSION_KEY] = str(COT_ZCACHE_VERSION).encode("ascii")
    pq.write_table(table.replace_schema_metadata(meta), str(path))  # type: ignore[no-untyped-call]


def zcache_definition_refusal(path: object = None) -> str | None:
    """Why a cot_positioning cell may not be BUILT on this machine right now, or None.

    Until the zcache here carries the current definition stamp, neither the judge nor a forward
    clock may build the family: over the old file it would judge a series nobody now defines, and
    with no COT it would judge an absence (zero signals) as a verdict. A failed build BY NAME is
    the honest answer -- UNMEASURED until `scripts/refresh_cot_zcache.py` rebuilds it. No zcache
    at all refuses nothing: the family then reads its other sources, as before.
    """
    cache = Path(str(path)) if path is not None else ZCACHE
    if not cache.exists():
        return None
    have = zcache_version(cache)
    if have == COT_ZCACHE_VERSION:
        return None
    label = have if have is not None else "1 (unstamped)"
    return (f"BLOCKED_DATA: COT zcache is definition {label}, not v{COT_ZCACHE_VERSION}; "
            f"UNMEASURED until scripts/refresh_cot_zcache.py rebuilds it")


#: THE BOX COMMANDS THAT CLEAR THE WAIT, in order (run from the repository root on the trading
#: box): rebuild the z history as definition v2 from source, then refetch the TFF parquets.
ZCACHE_ADOPTION = ("python scripts/refresh_cot_zcache.py",
                   "cd desks/mt5 && python -m mt5desk.fetch_tff")


def zcache_wait_line(path: object = None, *, at: str | None = None) -> dict[str, object]:
    """The GROWTH-GOVERNANCE line for the v2-definition wait (audit COT_AXIS_DEEPENING should-fix).

    While `zcache_definition_refusal` refuses, the whole `cot_positioning` family is BLOCKED_DATA
    on this machine: no judge build, no forward clock. That is a hold, and every hold is billed:
    its cost in forward E[log W] is UNMEASURED (no cell of the family can be judged while it
    lasts, so nothing prices what it withholds) -- never a zero -- and it names the box commands
    that clear it (`adoption`). A current-definition cache, or none at all, holds nothing and
    reads NOT_BINDING with a measured zero.
    """
    from datetime import UTC, datetime
    stamp = at or datetime.now(tz=UTC).isoformat(timespec="seconds")
    cache = Path(str(path)) if path is not None else ZCACHE
    why = zcache_definition_refusal(cache)
    line: dict[str, object] = {
        "day": stamp[:10], "at": stamp, "rail": "cot_zcache_definition_wait",
        "kind": "data_hold", "family": "cot_positioning", "zcache": str(cache),
        "units": "E[log W] per day",
        "adoption": " ; then ".join(ZCACHE_ADOPTION), "adoption_steps": list(ZCACHE_ADOPTION)}
    if why is None:
        line.update(value=0.0, delta_elogw=0.0, verdict="NOT_BINDING", held=False,
                    cause=(f"zcache is definition v{COT_ZCACHE_VERSION}"
                           if cache.exists() else "no zcache here: the family reads its other "
                           "sources and nothing is held"))
        return line
    line.update(value=None, delta_elogw="UNMEASURED", verdict="UNMEASURED", held=True,
                cause=why,
                why=(f"cot_positioning is BLOCKED_DATA until the zcache carries the "
                     f"v{COT_ZCACHE_VERSION} stamp; its forgone growth cannot be priced while "
                     f"no cell of the family can be judged"))
    return line


def zcache_version(path: object) -> int | None:
    """The definition version stamped in a zcache parquet's schema metadata.

    None when the file is absent, unreadable or carries no stamp -- an unstamped cache is the
    version-1 history (it predates the stamp), and a reader treats None as NOT the current
    version, never as a pass (L1.28a).
    """
    try:
        import pyarrow.parquet as pq
        meta = pq.read_schema(str(path)).metadata or {}  # type: ignore[no-untyped-call]
        raw = meta.get(ZCACHE_VERSION_KEY)
        return int(raw.decode("ascii")) if raw is not None else None
    except Exception:
        return None


def _get(url: str) -> list[dict[str, str]]:
    req = urllib.request.Request(url.replace(" ", "%20"), headers={"User-Agent": "quant-research"})
    with urllib.request.urlopen(req, timeout=40) as r:
        records = pd.read_json(StringIO(r.read().decode("utf-8"))).to_dict("records")
    return [dict(rec) for rec in records]


def fetch_net_spec(code: str) -> pd.Series:
    """Weekly net-speculator positioning as a fraction of open interest for one CFTC contract."""
    url = (f"{_BASE}?$where=cftc_contract_market_code='{code}'"
           "&$select=report_date_as_yyyy_mm_dd,pct_of_oi_noncomm_long_all,"
           "pct_of_oi_noncomm_short_all&$order=report_date_as_yyyy_mm_dd ASC&$limit=5000")
    rows = _get(url)
    if not rows:
        return pd.Series(dtype="float64")
    df = pd.DataFrame(rows)
    dt = pd.to_datetime(df["report_date_as_yyyy_mm_dd"], utc=True)
    net = (df["pct_of_oi_noncomm_long_all"].astype("float64")
           - df["pct_of_oi_noncomm_short_all"].astype("float64")) / 100.0
    return pd.Series(net.to_numpy(), index=dt).sort_index()


def cot_zscore_daily(
    symbols: list[str],
    daily_index: pd.DatetimeIndex,
    *,
    z_weeks: int = 156,
) -> pd.DataFrame:
    """Per-symbol COT positioning z-score (3y rolling), sign-aligned, lagged, daily-ffilled.

    Returns a DataFrame on ``daily_index`` with one column per mapped symbol. A positive value means
    speculators are crowded LONG the MT5 instrument (relative to its own 3-year history).
    """
    cols: dict[str, pd.Series] = {}
    for sym in symbols:
        if sym not in COT_MAP:
            continue
        code, sign = COT_MAP[sym]
        net = fetch_net_spec(code)
        if len(net) < z_weeks // 2:
            continue
        z = (net - net.rolling(z_weeks, min_periods=52).mean()) / net.rolling(
            z_weeks, min_periods=52).std()
        z = (sign * z).shift(1)                          # publication lag (no look-ahead)
        cols[sym] = z.reindex(z.index.union(daily_index)).sort_index().ffill().reindex(daily_index)
    return pd.DataFrame(cols, index=daily_index)

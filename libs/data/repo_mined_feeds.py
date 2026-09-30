"""Keyless feeds the mined public repos rely on, absorbed into the hourly dataset acquisition.

Found by reading what the repos mined on 2026-09-30 fetch or cite:
  * the Caldara-Iacoviello Geopolitical Risk index (daily), cited by je-suis-tm/quant-trading
    and HKUDS/Vibe-Trading;
  * the Baker-Bloom-Davis daily news-based Economic Policy Uncertainty index, the same authors'
    site that the GPR page links (policyuncertainty.com);
  * the alternative.me crypto Fear & Greed index, which Vibe-Trading reads for its crypto agent.
    Here it is a SENSOR for Fusion's crypto CFDs, never a hunted venue (LAWS: crypto reference
    data only where it informs an MT5 instrument).

WHY THIS IS NOT JUST THREE MORE SEED URLS. `research/acquire_datasets.py` parses what it fetches
and dates it by a date column. None of these three has one it recognises (GPR carries yyyymmdd
integers, EPU splits day/month/year, Fear & Greed carries epoch seconds), and two of them are
news-count indices whose recent values are RESTATED as newspaper archives fill in. A series
that restates and carries no vintage fails the point-in-time certificate, correctly.

So each feed is stamped by WHEN THE DESK COULD HAVE KNOWN IT, and restated feeds keep a first-
print ledger:
  * a value first seen by this desk is stamped with the moment it was first seen, and that
    first print is what every later pass serves, whatever the source says now;
  * history that pre-dates the ledger is stamped `settle` after its event time: the assumption,
    declared here and in the certificate meta, is that a news-count index stops moving within
    that window. It is an assumption, named, not a vintage;
  * nothing is stamped earlier than its event plus the declared publication lag.
Each series is certified with an `available_time` column, so the revision and availability
checks judge the stamps rather than trusting a declaration.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DAY_S = 86_400
SELECTION = "full_history_no_filter"


def _gpr_daily(df: pd.DataFrame) -> pd.DataFrame | None:
    cols = {str(c).strip().lower(): c for c in df.columns}
    if "day" in cols:
        raw = pd.to_numeric(df[cols["day"]], errors="coerce")
        when = pd.to_datetime(raw.astype("Int64").astype(str), format="%Y%m%d", errors="coerce",
                              utc=True)
    elif "date" in cols:
        when = pd.to_datetime(df[cols["date"]], errors="coerce", utc=True)
    else:
        return None
    keep = [cols[k] for k in ("gprd", "gprd_act", "gprd_threat") if k in cols]
    if not keep:
        return None
    out = df[keep].apply(pd.to_numeric, errors="coerce")
    out.columns = [str(c).lower() for c in keep]
    return out.set_index(pd.DatetimeIndex(when)).loc[lambda f: f.index.notna()]


def _epu_daily(df: pd.DataFrame) -> pd.DataFrame | None:
    cols = {str(c).strip().lower(): c for c in df.columns}
    if not {"day", "month", "year", "daily_policy_index"} <= set(cols):
        return None
    parts = pd.DataFrame({k: pd.to_numeric(df[cols[k]], errors="coerce")
                          for k in ("year", "month", "day")})
    when = pd.to_datetime(parts, errors="coerce", utc=True)
    out = pd.DataFrame({"daily_policy_index": pd.to_numeric(df[cols["daily_policy_index"]],
                                                            errors="coerce")})
    return out.set_index(pd.DatetimeIndex(when)).loc[lambda f: f.index.notna()]


def _fear_greed(df: pd.DataFrame) -> pd.DataFrame | None:
    if not {"value", "timestamp"} <= set(df.columns):
        return None
    secs = pd.to_numeric(df["timestamp"], errors="coerce")
    when = pd.to_datetime(secs, unit="s", errors="coerce", utc=True)
    out = pd.DataFrame({"fng": pd.to_numeric(df["value"], errors="coerce").to_numpy()},
                       index=pd.DatetimeIndex(when))
    return out.loc[out.index.notna()]


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    shape: Callable[[pd.DataFrame], pd.DataFrame | None]
    lag_s: int          #: the earliest a row can be known after its event time
    settle_s: int       #: pre-ledger history is stamped this long after its event
    revised: bool       #: does the publisher restate history (then the first print is served)
    use: str            #: which MT5 instruments it is meant to inform
    origin: str


FEEDS: tuple[Feed, ...] = (
    Feed("gpr_daily", "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls",
         _gpr_daily, lag_s=DAY_S, settle_s=14 * DAY_S, revised=True,
         use="XAUUSD, XAGUSD, USDJPY, USDCHF, XBRUSD, XTIUSD, indices: geopolitical risk as a "
             "regime and conditioner",
         origin="github.com/je-suis-tm/quant-trading; github.com/HKUDS/Vibe-Trading"),
    Feed("epu_us_daily", "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv",
         _epu_daily, lag_s=DAY_S, settle_s=30 * DAY_S, revised=True,
         use="US500, US30, NAS100, USD crosses, XAUUSD: policy uncertainty as a conditioner",
         origin="policyuncertainty.com, linked from the GPR page the repos cite"),
    Feed("crypto_fear_greed", "https://api.alternative.me/fng/?limit=0",
         _fear_greed, lag_s=0, settle_s=0, revised=False,
         use="Fusion crypto CFDs (BTCUSD, ETHUSD, ...) as a sentiment sensor, never a venue",
         origin="github.com/HKUDS/Vibe-Trading"),
)


def _stamp(event: pd.DatetimeIndex, first_seen: dict[str, str], feed: Feed, now: datetime,
           ledger_started: bool) -> pd.DatetimeIndex:
    """When each row became knowable to this desk."""
    now_ts = pd.Timestamp(now)
    out = []
    for t in event:
        key = t.isoformat()
        if key in first_seen:
            out.append(pd.Timestamp(first_seen[key]))
            continue
        floor = t + pd.Timedelta(seconds=feed.lag_s)
        if not feed.revised:
            seen = floor
        elif ledger_started:
            seen = max(now_ts, floor)
        else:
            seen = min(max(t + pd.Timedelta(seconds=feed.settle_s), floor), max(now_ts, floor))
        out.append(seen)
    return pd.DatetimeIndex(out)


def _ledger_path(root: Path, feed: Feed) -> Path:
    return root / f"{feed.name}.json"


def first_print_frames(feed: Feed, frame: pd.DataFrame, root: Path, now: datetime
                       ) -> dict[str, pd.DataFrame]:
    """Per numeric column: a frame indexed by event time with `value` and `available_time`,
    serving the FIRST print this desk saw of every event. Updates the ledger on disk."""
    path = _ledger_path(root, feed)
    try:
        ledger = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        ledger = {}
    started = bool(ledger.get("started_at"))
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    frame = frame.loc[frame.index <= pd.Timestamp(now)]
    out: dict[str, pd.DataFrame] = {}
    cols: dict[str, Any] = ledger.setdefault("columns", {})
    for col in frame.columns:
        s = pd.to_numeric(frame[col], errors="coerce").dropna()
        book: dict[str, Any] = cols.setdefault(str(col), {"value": {}, "seen": {}})
        avail = _stamp(pd.DatetimeIndex(s.index), book["seen"], feed, now, started)
        values = []
        for t, v, a in zip(s.index, s.to_numpy(), avail, strict=True):
            key = t.isoformat()
            if key not in book["value"]:
                book["value"][key] = float(v)
                book["seen"][key] = a.isoformat()
            values.append(book["value"][key] if feed.revised else float(v))
        f = pd.DataFrame({"value": values, "available_time": avail}, index=s.index)
        f = f.loc[f["available_time"] <= pd.Timestamp(now)]
        if len(f):
            out[f"{feed.name}_{col}"] = f
    ledger["started_at"] = ledger.get("started_at") or now.isoformat()
    ledger["url"] = feed.url
    root.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, sort_keys=True), "utf-8")
    tmp.replace(path)
    return out


def as_available(f: pd.DataFrame) -> pd.Series:
    """The series a join may read: each value placed at the moment it became knowable."""
    s = pd.Series(f["value"].to_numpy(dtype=float),
                  index=pd.DatetimeIndex(f["available_time"]), name="value")
    return s[~s.index.duplicated(keep="last")].sort_index()


def absorb(reg: dict[str, Any], store: Path, *, fetch: Callable[[str], tuple[bytes | None, str]],
           parse: Callable[[bytes, str], pd.DataFrame | None],
           certify: Callable[..., Any], write_certificate: Callable[[Any], Any],
           now: datetime | None = None, feeds: tuple[Feed, ...] = FEEDS) -> dict[str, Any]:
    """Fetch, shape, first-print, certify and register every feed into the acquirer's registry."""
    now = now or datetime.now(UTC)
    report: dict[str, Any] = {"tried": 0, "kept": 0, "new_series": [], "refusals": {}}

    def _refuse(feed: Feed, why: str) -> None:
        report["refusals"][why] = report["refusals"].get(why, 0) + 1
        reg["by_url"][feed.url] = {"host": "repo_mined_feeds", "series": [],
                                   "at": now.isoformat(timespec="seconds"),
                                   "status": "REFUSED", "refusal": why}

    for feed in feeds:
        report["tried"] += 1
        raw, ctype = fetch(feed.url)
        if raw is None:
            _refuse(feed, "served HTML, not data" if ctype == "html" else "unreachable")
            continue
        df = parse(raw, feed.url)
        shaped = feed.shape(df) if df is not None and not df.empty else None
        if shaped is None or shaped.empty:
            _refuse(feed, "unparseable in the shape this feed is documented to have")
            continue
        frames = first_print_frames(feed, shaped, store / "first_print", now)
        persisted = [n for name, f in frames.items()
                     if (n := _register(reg, store, name, f, url=feed.url, provider=feed.origin,
                                        revised=feed.revised, lag_s=feed.lag_s,
                                        settle_s=feed.settle_s, use=feed.use,
                                        certify=certify, write_certificate=write_certificate,
                                        now=now))]
        report["new_series"].extend(persisted)
        reg["by_url"][feed.url] = {"host": "repo_mined_feeds", "series": persisted,
                                   "at": now.isoformat(timespec="seconds"),
                                   "status": "SUCCESS" if persisted else "REFUSED",
                                   "refusal": None if persisted else "no series with history"}
        report["kept"] += int(bool(persisted))
    return report


def _register(reg: dict[str, Any], store: Path, name: str, f: pd.DataFrame, *, url: str,
              provider: str, revised: bool, lag_s: int, settle_s: int, use: str,
              certify: Callable[..., Any], write_certificate: Callable[[Any], Any],
              now: datetime) -> str | None:
    """Persist one available-time series, certify it, and enter it in the acquirer's registry."""
    name = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")[:48]
    if len(f) < 200 or f["value"].nunique() < 10:
        return None
    path = store / f"{name}.parquet"
    as_available(f).to_frame().to_parquet(path)
    prior = reg["series"].get(name) or {}
    try:
        cert = certify({"dataset": name, "url": url, "host": "repo_mined_feeds",
                        "provider": provider, "selection": SELECTION, "revised": revised,
                        "publication_lag_s": lag_s, "history_starts": prior.get("first"),
                        "schema_hash": prior.get("schema_hash"), "settle_backfill_s": settle_s},
                       f, now=now)
        write_certificate(cert)
        blocking = sorted(set(cert.failures()) | set(cert.unmeasured()))
        authority, cert_id = bool(cert.authority), cert.certificate_id
        schema_hash = cert.span.get("schema_hash")
    except Exception as exc:
        blocking = [f"certify failed: {type(exc).__name__}: {exc}"]
        authority, cert_id, schema_hash = False, "", prior.get("schema_hash")
    reg["series"][name] = {
        "path": str(path), "url": url, "host": "repo_mined_feeds",
        "rows": len(f), "first": str(f.index.min()), "last": str(f.index.max()),
        "acquired_at": now.isoformat(timespec="seconds"), "schema_hash": schema_hash,
        "pit_certificate": cert_id, "pit_authority": authority,
        "pit_blocking": blocking, "stamped_by": "available_time",
        "mt5_use": use, "origin": provider,
    }
    return name


def absorb_dtcc(reg: dict[str, Any], store: Path, *,
                fetch: Callable[[str], tuple[bytes | None, str]],
                certify: Callable[..., Any], write_certificate: Callable[[Any], Any],
                now: datetime | None = None) -> dict[str, Any]:
    """The DTCC public FX option tape (`libs/data/dtcc_fx_options.py`): reduce this pass's
    slices, then register every pair feature with enough history."""
    from libs.data import dtcc_fx_options as dtcc
    now = now or datetime.now(UTC)
    root = store / "dtcc_fx"
    rep = dtcc.ingest(root, fetch=fetch, now=now)
    names = [n for name, f in dtcc.frames(root, now).items()
             if (n := _register(reg, store, name, f, url=dtcc.MANIFEST_URL,
                                provider="DTCC PPD via github.com/OpenBB-finance/OpenBB",
                                revised=False, lag_s=int(dtcc.AVAILABLE_AFTER.total_seconds()),
                                settle_s=0, use="the MT5 FX pair named in the series",
                                certify=certify, write_certificate=write_certificate, now=now))]
    reg["by_url"][dtcc.MANIFEST_URL] = {"host": "repo_mined_feeds", "series": names,
                                        "at": now.isoformat(timespec="seconds"),
                                        "status": "SUCCESS" if names else "PENDING",
                                        "refusal": None if names else rep.get("status")}
    return {**rep, "new_series": names}


def settle_note() -> dict[str, Any]:
    """What the certificate meta means by `settle_backfill_s`, for any reader of the registry."""
    return {f.name: {"settle_days": f.settle_s / DAY_S, "revised": f.revised,
                     "lag_days": f.lag_s / DAY_S} for f in FEEDS} | {
        "rule": "pre-ledger history is stamped `settle` after its event; everything after the "
                "ledger started is the first print this desk saw, stamped when it saw it"}


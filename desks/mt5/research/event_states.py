"""EVENT STATES -- free-source event and regime states (backlog ideas N4..N12) for the futures-state
factory.

Not a framework of its own. The rows live in `futures_state_sources.json` under `event_states`,
every network read goes through the futures-state organ's own door (`fetch_text` / `fetch_json`:
the desk's polite fetcher, one honest User-Agent, no retries, 401/403/429/451 a HARD STOP written
to state) and is asked of the host's robots.txt first (`robots_allow`: an unread policy is never
a yes). What is built becomes a stamped frame in the same `build_market_series` pass, so it lands
in `data/lake/series/evt_<id>.parquet` and mints `exogenous_conditioner` cells through the same
once-in-its-life door as every other futures-state series. The hourly `futures_state` leg is the
clock; nothing new is scheduled.

WHICH IDEA IS WHAT (terms read 2026-11-17 unless the row says otherwise):

  N4  BoJ rinban          FENCED  boj.or.jp/en/copyright.htm: copying for commercial purposes
                                  needs the Bank's prior permission; trading is commercial use.
  N5  SNB sight deposits  FENCED  non-commercial clause (#1087 carries the adapter, TERMS_BLOCKED).
  N6  TIC net purchases   BUILT   ticdata.treasury.gov slt_table1.txt (US government work).
  N7  USDA export sales   FENCED  the FAS OpenData ESR API is key-gated and the catalogue holds no
                                  key; the March 2026 ESRQS API paths are unconfirmed.
  N8  EIA gas storage     BUILT   derived from the keyed_sources EIA store (the key is read there,
                                  through env_keys.read_key, and never reaches this organ).
  N9  Chicago Fed NFCI    FENCED  chicagofed.org legal notices: reproduction only when "not for the
                                  purpose of private and/or commercial gain", else written
                                  permission. FRED is refused too (2026-11-13 ruling).
  N10 Fed SLOOS           BUILT   federalreserve.gov DDP zip (Board data is public domain).
  N11 JOLTS quits         BUILT   derived from the keyed_sources BLS store (series added there).
  N12 Treasury buybacks   BUILT   api.fiscaldata.treasury.gov (open, commercial use allowed).

POINT IN TIME. Every row is stamped by its release rule, late by construction, and a value first
seen live is stamped at max(rule, first seen). The FIRST value seen for a period is kept for ever:
a later revision is counted, never back-dated into the series.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import zipfile
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
#: The keyed_sources leg's PIT store (`research/keyed_sources.py`): read, never written here.
KEYED_OBS = DESK / "data" / "keyed_sources" / "obs"
#: Weekly or slower sources: one read a day is ample and polite.
REFETCH_S = 20 * 3600
#: Bytes we accept from a zip member before refusing it (the SLOOS package is ~0.5 MB).
MAX_XML_BYTES = 40 * 1024 * 1024
ET_TZ = "America/New_York"


# ------------------------------------------------------------------------------ PIT store

def merge_store(store: dict[str, Any], frame: pd.DataFrame, rule: pd.Series,
                seen: datetime) -> dict[str, int]:
    """Keep the FIRST value seen per period. `frame` is indexed by period; `rule` gives each
    period's release-rule stamp (UTC). A store that was empty before this read is BACKFILL,
    stamped at the rule; later new periods are stamped at max(rule, first seen)."""
    backfill = not store
    added = revised = 0
    t_seen = pd.Timestamp(seen).tz_convert("UTC") if pd.Timestamp(seen).tzinfo \
        else pd.Timestamp(seen, tz="UTC")
    for per, row in frame.iterrows():
        key = pd.Timestamp(per).date().isoformat()
        vals = {str(c): (None if pd.isna(v) else float(v)) for c, v in row.items()}
        held = store.get(key)
        if held is None:
            r = pd.Timestamp(rule.loc[per])
            at = r if backfill else max(r, t_seen)
            store[key] = {"values": vals, "available_time": at.isoformat(),
                          "first_seen_at": t_seen.isoformat(),
                          "pit": "backfill" if backfill else "live", "n_revisions": 0}
            added += 1
        elif held.get("values") != vals:
            held["n_revisions"] = int(held.get("n_revisions") or 0) + 1
            held["last_revision_at"] = t_seen.isoformat()
            revised += 1
    return {"added": added, "revised": revised}


def store_frame(store: Mapping[str, Any]) -> tuple[pd.DataFrame, pd.Series]:
    """The held first values (indexed by period) and their availability stamps."""
    if not store:
        return pd.DataFrame(), pd.Series(dtype="datetime64[ns, UTC]")
    keys = sorted(store)
    df = pd.DataFrame([store[k]["values"] for k in keys],
                      index=pd.DatetimeIndex([pd.Timestamp(k) for k in keys]))
    at = pd.Series(pd.to_datetime([store[k]["available_time"] for k in keys], utc=True),
                   index=df.index)
    return df, at


def rule_stamp(periods: pd.DatetimeIndex, rule: Mapping[str, Any]) -> pd.Series:
    """Period + lag_days at hour UTC (the release rule), late by construction."""
    lag = int(rule.get("lag_days", 1))
    hour = int(rule.get("hour", 23))
    base = pd.Series(periods, index=periods).dt.normalize()
    return (base + pd.Timedelta(days=lag, hours=hour)).dt.tz_localize("UTC")


# ------------------------------------------------------------------------------ parsers

def _num(s: Any) -> float | None:
    try:
        v = float(str(s).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def parse_tic_slt(text: str, total_code: str = "99996", value_col: int = 4) -> pd.DataFrame:
    """ticdata.treasury.gov `slt_table1.txt` (tab-delimited, millions of USD) -> the Grand Total
    row's monthly NET U.S. SALES of long-term U.S. securities, column `tic_net_lt`, indexed by
    month end. TIC books transactions from the U.S. reporter's side, so a U.S. sale to a
    foreigner is a foreign purchase: positive = net foreign buying. Columns are Country, Country
    Code, Date (YYYY-MM), then Holdings / Net U.S. Sales / Valuation Change per security class;
    `value_col` is the Total-securities net sales field. Anything else parses to nothing."""
    rows: dict[pd.Timestamp, float] = {}
    for line in text.splitlines():
        f = [x.strip().strip('"') for x in line.split("\t")]
        if len(f) <= value_col or not re.fullmatch(r"\d{4}-\d{2}", f[2] if len(f) > 2 else ""):
            continue
        if f[1] != total_code and "grand total" not in f[0].lower():
            continue
        v = _num(f[value_col])
        if v is not None:
            rows[pd.Timestamp(f[2] + "-01") + pd.offsets.MonthEnd(0)] = v
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame({"tic_net_lt": pd.Series(rows)}).sort_index()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _period_start(s: str) -> pd.Timestamp | None:
    s = s.strip()
    m = re.fullmatch(r"(\d{4})-?Q([1-4])", s)
    if m:
        return pd.Timestamp(int(m.group(1)), 3 * int(m.group(2)) - 2, 1)
    try:
        t = pd.Timestamp(s)
    except (ValueError, TypeError):
        return None
    return None if pd.isna(t) else t


def parse_frb_xml(xml: bytes, series: str) -> pd.Series:
    """A Federal Reserve Data Download Program XML (SDMX-style: a Series element carrying
    `SERIES_NAME`, Obs children with `TIME_PERIOD` / `OBS_VALUE`) -> that series, indexed by the
    period's first day. Namespaces are ignored; a missing series is an empty Series."""
    out: dict[pd.Timestamp, float] = {}
    for _ev, el in ElementTree.iterparse(io.BytesIO(xml), events=("end",)):
        if _local(el.tag) != "Series":
            continue
        if str(el.attrib.get("SERIES_NAME", "")).upper() == series.upper():
            for ob in el:
                if _local(ob.tag) != "Obs":
                    continue
                t = _period_start(str(ob.attrib.get("TIME_PERIOD", "")))
                v = _num(ob.attrib.get("OBS_VALUE"))
                if t is not None and v is not None:
                    out[t] = v
        el.clear()
    return pd.Series(out, dtype=float).sort_index()


def parse_frb_zip(blob: bytes, series: str) -> pd.Series:
    """The DDP zip package -> the named series from whichever XML member carries it."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        return pd.Series(dtype=float)
    for info in zf.infolist():
        if not info.filename.lower().endswith(".xml") or info.file_size > MAX_XML_BYTES:
            continue
        try:
            s = parse_frb_xml(zf.read(info), series)
        except ElementTree.ParseError:
            continue
        if len(s):
            return s
    return pd.Series(dtype=float)


def parse_buybacks(doc: Any) -> pd.DataFrame:
    """fiscaldata `od/buybacks_operations` JSON -> one row per operation DAY: accepted par (USD
    bn), offered par, capacity (max par redeemed), and the close time in UTC (`closed_utc`,
    the operation's ET close; NaT when unreadable). Several operations on one day are summed."""
    rows = []
    for r in (doc or {}).get("data") or [] if isinstance(doc, dict) else []:
        try:
            day = pd.Timestamp(str(r.get("operation_date")))
        except (ValueError, TypeError):
            continue
        acc, off = _num(r.get("total_par_amt_accepted")), _num(r.get("total_par_amt_offered"))
        cap = _num(r.get("max_par_amt_redeemed"))
        if pd.isna(day) or acc is None:
            continue
        close = pd.NaT
        with contextlib.suppress(ValueError, TypeError):
            close = (pd.Timestamp(f"{day.date()} {r.get('operation_close_time_est')}")
                     .tz_localize(ET_TZ).tz_convert("UTC"))
        rows.append({"day": day.normalize(), "accepted": acc / 1e9,
                     "offered": (off or 0.0) / 1e9, "capacity": (cap or 0.0) / 1e9,
                     "liquidity": 1.0 if "liquidity" in str(r.get("operation_type")).lower()
                     else 0.0, "closed_utc": close})
    if not rows:
        return pd.DataFrame()
    d = pd.DataFrame(rows)
    g = d.groupby("day")
    out = pd.DataFrame({"accepted": g["accepted"].sum(), "offered": g["offered"].sum(),
                        "capacity": g["capacity"].sum(), "liquidity": g["liquidity"].max(),
                        "closed_utc": g["closed_utc"].max()})
    return out.sort_index()


# ------------------------------------------------------------------------------ features

def tic_features(held: pd.DataFrame) -> pd.DataFrame:
    """Net foreign purchases (USD bn) and the surprise against the median of the PRIOR twelve
    months (the reading itself never enters its own baseline)."""
    if held.empty or "tic_net_lt" not in held.columns:
        return pd.DataFrame()
    v = pd.to_numeric(held["tic_net_lt"], errors="coerce") / 1000.0
    med = v.shift(1).rolling(12, min_periods=6).median()
    base = pd.DataFrame({"tic_net": v, "tic_vs_med12": v - med}, index=held.index)
    return _dyn(base.dropna(subset=["tic_vs_med12"]), list(base.columns), window=60)


def sloos_features(held: pd.DataFrame) -> pd.DataFrame:
    """Net % of banks tightening C&I standards and its change against the prior survey."""
    if held.empty or "sloos_ci_tight" not in held.columns:
        return pd.DataFrame()
    v = pd.to_numeric(held["sloos_ci_tight"], errors="coerce")
    base = pd.DataFrame({"sloos_ci_tight": v, "sloos_ci_shock": v.diff()}, index=held.index)
    return _dyn(base.dropna(subset=["sloos_ci_shock"]), list(base.columns), window=40)


def buyback_features(held: pd.DataFrame) -> pd.DataFrame:
    """Size and acceptance of each operation day: accepted par (bn), take-up of the announced
    capacity (accepted / max), and the cover (offered / max: how much the street wanted out)."""
    if held.empty or "accepted" not in held.columns:
        return pd.DataFrame()
    cap = pd.to_numeric(held["capacity"], errors="coerce").replace(0.0, np.nan)
    base = pd.DataFrame({"bb_accepted": pd.to_numeric(held["accepted"], errors="coerce"),
                         "bb_takeup": held["accepted"] / cap,
                         "bb_cover": held["offered"] / cap}, index=held.index)
    feat = _dyn(base, list(base.columns), window=104)
    feat["bb_liquidity"] = held["liquidity"]
    return feat


def gas_storage_features(levels: pd.Series) -> pd.DataFrame:
    """Weekly working-gas change (Bcf) against the five-year average change for the same ISO
    week, from the PRIOR five years only (at least three of them)."""
    s = pd.to_numeric(levels, errors="coerce").dropna().sort_index()
    chg = s.diff().dropna()
    if chg.empty:
        return pd.DataFrame()
    iso = chg.index.isocalendar()
    wk, yr = iso["week"].astype(int).to_numpy(), iso["year"].astype(int).to_numpy()
    avg = []
    for i in range(len(chg)):
        prior = chg.to_numpy()[(wk == wk[i]) & (yr < yr[i]) & (yr >= yr[i] - 5)]
        avg.append(float(prior.mean()) if len(prior) >= 3 else np.nan)
    base = pd.DataFrame({"ng_stor_chg": chg, "ng_stor_vs5y": chg - np.asarray(avg)},
                        index=chg.index)
    return _dyn(base.dropna(subset=["ng_stor_vs5y"]), list(base.columns), window=156)


def quits_features(levels: pd.Series) -> pd.DataFrame:
    """JOLTS quits rate and its gap to the mean of the PRIOR three months."""
    s = pd.to_numeric(levels, errors="coerce").dropna().sort_index()
    base = pd.DataFrame({"jolts_quits": s, "jolts_quits_vs3m": s - s.shift(1).rolling(3).mean()},
                        index=s.index)
    return _dyn(base.dropna(subset=["jolts_quits_vs3m"]), list(base.columns), window=60)


_DYN: Callable[..., pd.DataFrame] | None = None


def _dyn(df: pd.DataFrame, cols: list[str], window: int) -> pd.DataFrame:
    if _DYN is None or df.empty:
        return df
    return _DYN(df, cols, window=window)


# ------------------------------------------------------------------------------ collectors

def terms_status(row: Mapping[str, Any]) -> str:
    return (f"{row.get('terms')}: {row.get('terms_clause') or 'terms not OPEN'} "
            f"({row.get('terms_url') or 'terms URL unrecorded'}, "
            f"read {row.get('terms_read') or 'never'})")


def _due(state: dict[str, Any], sid: str, now: datetime) -> bool:
    last = float((state.get("event_fetched_at") or {}).get(sid, 0.0) or 0.0)
    return now.timestamp() - last >= REFETCH_S


def _read_store(fs: Any, sid: str) -> dict[str, Any]:
    out = fs._read(fs.RAW / f"evt_{sid}_store.json", {}) or {}
    return out if isinstance(out, dict) else {}


def collect_remote(fs: Any, row: Mapping[str, Any], state: dict[str, Any],
                   notes: list[dict[str, Any]], now: datetime,
                   get_text: Callable[[str], str] | None, get: Callable[[str], Any] | None,
                   get_bytes: Callable[[str], bytes] | None) -> tuple[pd.DataFrame, pd.Series]:
    """Read the row's source once a day when robots allows, merge first values into its PIT store,
    and return what is held. Offline, stopped or disallowed, it returns the held store."""
    sid = str(row["id"])
    store = _read_store(fs, sid)
    adapter = str(row.get("adapter"))
    online = get_text is not None and sid not in state.get("hard_stops", {})
    if online and _due(state, sid, now):
        url = str(row["url"])
        try:
            assert get_text is not None
            if not fs.robots_allow(url, get_text):
                notes.append({"source": sid, "status": "UNMEASURED", "why": "robots disallows"})
            else:
                frame = pd.DataFrame()
                rule: pd.Series | None = None
                if adapter == "tic_slt":
                    frame = parse_tic_slt(get_text(url), str(row.get("total_code", "99996")),
                                          int(row.get("value_col", 4)))
                elif adapter == "frb_ddp_zip" and get_bytes is not None:
                    s = parse_frb_zip(get_bytes(url), str(row["series_name"]))
                    frame = pd.DataFrame({str(row["column"]): s}) if len(s) else frame
                elif adapter == "fiscaldata_buybacks" and get is not None:
                    bb = parse_buybacks(get(url))
                    if not bb.empty:
                        late = (pd.Series(bb.index, index=bb.index).dt.tz_localize("UTC")
                                + pd.Timedelta(hours=23))
                        rule = bb["closed_utc"].fillna(late).astype("datetime64[ns, UTC]") \
                            + pd.Timedelta(minutes=int(row.get("results_after_min", 60)))
                        frame = bb.drop(columns=["closed_utc"])
                if frame.empty:
                    notes.append({"source": sid, "status": "UNPARSED"})
                else:
                    if rule is None:
                        rule = rule_stamp(pd.DatetimeIndex(frame.index), row.get("rule") or {})
                    m = merge_store(store, frame, rule, now)
                    fs._write(fs.RAW / f"evt_{sid}_store.json", store)
                    notes.append({"source": sid, "status": "READ", **m})
                state.setdefault("event_fetched_at", {})[sid] = now.timestamp()
        except fs.HardStop as hs:
            state.setdefault("hard_stops", {})[sid] = {"code": hs.code, "at": fs._now()}
        except Exception as exc:
            notes.append({"source": sid, "error": f"{type(exc).__name__}"})
    return store_frame(store)


def keyed_series(row: Mapping[str, Any]) -> tuple[pd.Series, pd.Series]:
    """One series out of the keyed_sources PIT store: first values by period and their stamps."""
    p = KEYED_OBS / f"{row['keyed_source']}.json"
    try:
        store = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return pd.Series(dtype=float), pd.Series(dtype="datetime64[ns, UTC]")
    want = str(row["keyed_series"])
    rows = [r for r in (store.values() if isinstance(store, dict) else [])
            if isinstance(r, dict) and r.get("series") == want]
    if not rows:
        return pd.Series(dtype=float), pd.Series(dtype="datetime64[ns, UTC]")
    idx = pd.DatetimeIndex([pd.Timestamp(r["period"]) for r in rows])
    val = pd.Series([float(r["value_first"]) for r in rows], index=idx).sort_index()
    at = pd.Series(pd.to_datetime([r["available_time"] for r in rows], utc=True),
                   index=idx).sort_index()
    keep = ~val.index.duplicated(keep="first")
    return val[keep], at[keep]


FEATURES: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "tic_slt": tic_features, "frb_ddp_zip": sloos_features,
    "fiscaldata_buybacks": buyback_features}
KEYED_FEATURES: dict[str, Callable[[pd.Series], pd.DataFrame]] = {
    "gas_storage_vs5y": gas_storage_features, "quits_vs3m": quits_features}


def build(fs: Any, registry: Mapping[str, Any], state: dict[str, Any],
          notes: list[dict[str, Any]], *, now: datetime | None,
          get_text: Callable[[str], str] | None, get: Callable[[str], Any] | None,
          get_bytes: Callable[[str], bytes] | None = None
          ) -> tuple[dict[str, dict[str, Any]], dict[str, pd.DataFrame]]:
    """Every `event_states` row -> a stamped frame `evt_<id>`, or a named note saying why not.
    `fs` is the futures-state module that called (its fetch door, robots check and stamping)."""
    global _DYN
    _DYN = fs.dynamics
    now = now or datetime.now(UTC)
    built: dict[str, dict[str, Any]] = {}
    frames: dict[str, pd.DataFrame] = {}
    for row in registry.get("event_states") or []:
        sid, adapter = str(row["id"]), str(row.get("adapter"))
        if row.get("terms") != "OPEN" or adapter == "none":
            notes.append({"source": sid, "idea": row.get("idea"), "status": terms_status(row)})
            continue
        if adapter == "keyed_store":
            val, at = keyed_series(row)
            derive = KEYED_FEATURES.get(str(row.get("derive")))
            feat = derive(val) if derive is not None and len(val) else pd.DataFrame()
        elif adapter in FEATURES:
            held, at = collect_remote(fs, row, state, notes, now, get_text, get, get_bytes)
            feat = FEATURES[adapter](held)
        else:
            notes.append({"source": sid, "status": "UNMEASURED",
                          "why": f"no adapter {adapter!r}"})
            continue
        if len(feat) < fs.MIN_ROWS:
            notes.append({"source": sid, "idea": row.get("idea"), "status": "UNMEASURED",
                          "why": f"{len(feat)} rows held (< {fs.MIN_ROWS})"})
            continue
        oid = f"evt_{sid}"
        idx = pd.Series(feat.index)
        avail = pd.Series(at.reindex(feat.index).to_numpy())
        frames[oid] = fs.stamped(feat.reset_index(drop=True), avail, oid, idx)
        built[oid] = {"targets": list(row.get("targets") or []), "kind": f"event_{adapter}",
                      "rows": len(feat), "last_event": str(feat.index.max()),
                      "idea": row.get("idea"), "why": str(row.get("why", ""))}
    return built, frames

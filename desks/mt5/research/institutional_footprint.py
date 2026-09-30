"""THE INSTITUTIONAL FOOTPRINT ENGINE -- public exhaust in, latent actor states and cells out.

THE PRINCIPAL, 2026-09-30 17:47-18:14Z: reconstruct who is likely doing what from public
regulatory, exchange, central-bank and physical-market exhaust, in every jurisdiction, merged into
the country packs -- and every state carries its uncertainty. The chain this organ runs, hourly:

    atlas rows (source_rosters/institutional_footprint.yaml, one canonical id per dataset)
      -> fetch (a recipe per public API, or an existing lane's frame read in place)
      -> PIT frame in data/lake/series/<id>.csv   (event_time, available_time, numeric columns)
      -> features (level, change, acceleration, percentile, z, extreme, divergence vs price)
      -> latent states per MT5 asset: P(state) with a 95% interval and the share of evidence
         measured, fused in log-odds from stated prior weights (ontology.LATENT_STATES)
      -> dealer gamma as a POSTERIOR OVER THREE SCENARIOS, never a signed number
      -> conditioner cells through the one registry door (`libs.moat.registry.enqueue_candidate`,
         family `exogenous_conditioner`), each carrying its source id and the culture fields
      -> INSTITUTIONAL_COVERAGE.json: the jurisdiction x class grid with exactly one status per
         cell, the role grid, commodity triangulation, the future-source watch, the unfed count
         and the age of every latent state
      -> INSTITUTIONAL_STATE.json: the latest state per asset, the allocator's input

WHAT THIS IS NOT. It does not judge, size, veto or promote: every cell goes to the one gauntlet
and is charged there, once (a cell key already enqueued is never re-enqueued, so a pass never
inflates a search count). It never throttles a miner: the budget is a wall clock and whatever a
pass does not reach leads the next pass. It fetches only public, keyless endpoints; a recipe that
fails is recorded with its reason and the row stays DISCOVERED -- absence is UNMEASURED, never a
zero. No crypto venue is ever fetched; the public-chain row is a sensor with no recipe here.

    python desks/mt5/research/institutional_footprint.py --once --budget-s 300
    python desks/mt5/research/institutional_footprint.py --once --offline     # no network
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import re
import sys
import time
import zipfile
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROSTER = DESK / "data" / "source_rosters" / "institutional_footprint.yaml"
SERIES = DESK / "data" / "lake" / "series"
STATE_DIR = DESK / "data" / "institutional"
EMITTED = STATE_DIR / "cells_emitted.json"
FETCH_STATE = STATE_DIR / "fetch_state.json"
WATCH_STATE = STATE_DIR / "watch_state.json"
RULINGS = DESK / "data" / "institutional_coverage_rulings.json"
#: Culture rows per cell, kept here until #139's registry columns stamp them at the door.
CULTURE_LOG = STATE_DIR / "cell_culture.jsonl"
REPORT = DESK / "reports" / "INSTITUTIONAL_COVERAGE.json"
STATE_REPORT = DESK / "reports" / "INSTITUTIONAL_STATE.json"
#: The full equivalence-search queue, for the dataset hunters on the box; the report carries counts.
SEARCH_QUEUE = STATE_DIR / "search_queue.json"

LEG = "institutional_footprint"
STATE_SERIES_PREFIX = "institutional_state"
#: The charts and transforms a state conditioner is asked on -- the same set pack_cells mints.
CHARTS: tuple[str, ...] = ("H1", "H4", "D1")
TRANSFORMS: tuple[str, ...] = ("level_z", "delta")
SIDES: tuple[int, ...] = (1, -1)
#: Observations the rolling percentile and z are measured over (156 weeks ~ 3 years of COT).
ROLL = 156
MIN_OBS = 20


def _ontology() -> Any:
    for name in ("research.countries.institutional.ontology", "countries.institutional.ontology"):
        with contextlib.suppress(ImportError):
            import importlib
            return importlib.import_module(name)
    raise ImportError("countries.institutional.ontology is not importable")


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    tmp.replace(p)


# =========================================================================== the atlas
def load_roster(path: Path = ROSTER) -> list[dict[str, Any]]:
    """The atlas rows. An unreadable roster is an empty atlas and the report says so."""
    try:
        import yaml
        doc = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    except Exception:
        return []
    rows = doc.get("sources") if isinstance(doc, Mapping) else doc
    return [dict(r) for r in rows or [] if isinstance(r, Mapping) and r.get("id")]


def rows_for(jurisdiction: str, rows: Iterable[Mapping[str, Any]] | None = None
             ) -> list[dict[str, Any]]:
    """One jurisdiction's slice of the atlas: what a country pack's footprint reads."""
    src = load_roster() if rows is None else rows
    return [dict(r) for r in src if str(r.get("jurisdiction")) == jurisdiction]


# =========================================================================== PIT frames
def series_path(sid: str) -> Path:
    return SERIES / f"{sid}.csv"


def write_frame(sid: str, df: pd.DataFrame, *, lag_hours: float) -> int:
    """Stamp and write one frame. `available_time` is event_time plus the publication lag,
    never earlier: history is reconstructed as the desk COULD have known it, not as it was
    revised later. Numeric columns only beside the stamp."""
    if df is None or df.empty or "event_time" not in df.columns:
        return 0
    out = df.copy()
    out["event_time"] = pd.to_datetime(out["event_time"], utc=True, errors="coerce")
    out = out.dropna(subset=["event_time"]).sort_values("event_time")
    out["available_time"] = out["event_time"] + pd.Timedelta(hours=float(lag_hours))
    out["source_id"] = sid
    out["retrieval_time"] = now_utc().isoformat(timespec="seconds")
    stamp = ["event_time", "available_time", "source_id", "retrieval_time"]
    keep = stamp + [c for c in out.columns
                    if c not in stamp and pd.api.types.is_numeric_dtype(out[c])]
    out = out[keep].drop_duplicates(subset=["event_time"], keep="last")
    SERIES.mkdir(parents=True, exist_ok=True)
    out.to_csv(series_path(sid), index=False)
    return len(out)


def read_frame(sid: str) -> pd.DataFrame | None:
    p = series_path(sid)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
    except Exception:
        return None
    if "available_time" not in df.columns:
        return None
    df["available_time"] = pd.to_datetime(df["available_time"], utc=True, errors="coerce")
    df["event_time"] = pd.to_datetime(df.get("event_time"), utc=True, errors="coerce")
    return df.dropna(subset=["available_time"]).sort_values("available_time")


def lag_hours_of(row: Mapping[str, Any]) -> float:
    """Publication lag in hours, conservative: the declared lag in days plus the whole day of
    publication, so a series never reaches a bar before the day it was released has ended.
    A recipe may state its exact offset (the COT is out Friday 19:30 UTC in summer)."""
    fetch = row.get("fetch") or {}
    if fetch.get("available_offset_hours") is not None:
        return float(fetch["available_offset_hours"])
    return (float(row.get("publication_lag_days") or 0) + 1.0) * 24.0


# =========================================================================== fetch recipes
HttpGet = Callable[[str], tuple[int | None, bytes, str]]


def polite_get(deadline: float) -> HttpGet:
    """The desk's polite transport, bounded by the leg's deadline. Returns (status, body, error)."""
    from libs.data import polite_fetch

    def get(url: str) -> tuple[int | None, bytes, str]:
        if url.lower().endswith(".zip"):
            # polite_fetch decodes to text; an archive needs its bytes. Same TLS context, same
            # deadline, one attempt.
            import urllib.request
            left = max(1.0, min(60.0, deadline - time.monotonic()))
            # The SEC's fair-access rule wants a declared agent; this is the one
            # side_channels/sec_edgar_miner.py already declares.
            ua = {"User-Agent": "QuantResearch quant@example.com"}
            req = urllib.request.Request(url, headers=ua)
            try:
                with urllib.request.urlopen(req, timeout=left,
                                            context=polite_fetch.ssl_context()) as resp:
                    return int(resp.status), resp.read(), ""
            except Exception as exc:
                return getattr(exc, "code", None), b"", f"{type(exc).__name__}: {exc}"[:120]
        r = polite_fetch.get(url, headers={"Accept": "*/*"}, timeout=25.0, retries=1,
                             deadline=deadline, leg=LEG)
        return r.status, (r.text or "").encode("utf-8", "replace"), str(r.error or "")
    return get


def _ok(status: int | None, err: str) -> bool:
    return status is not None and 200 <= status < 300 and not err


def _fred_csv(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    frames = []
    for col, series in (row["fetch"].get("series") or {}).items():
        st, body, err = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}")
        if not _ok(st, err):
            return None, f"FRED {series}: HTTP {st} {err}"[:160]
        df = pd.read_csv(io.BytesIO(body))
        if df.shape[1] < 2:
            return None, f"FRED {series}: unexpected shape"
        df.columns = ["event_time", col]
        df[col] = pd.to_numeric(df[col], errors="coerce")
        frames.append(df.set_index("event_time"))
    if not frames:
        return None, "no series named"
    out = pd.concat(frames, axis=1).reset_index()
    return out, ""


def _dig(doc: Any, path: Iterable[str]) -> Any:
    for k in path:
        doc = doc.get(k) if isinstance(doc, Mapping) else None
    return doc


def _nyfed_json(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    f = row["fetch"]
    end = now_utc().date()
    url = str(f["url"]).format(start=(end - timedelta(days=730)).isoformat(), end=end.isoformat())
    st, body, err = get(url)
    if not _ok(st, err):
        return None, f"HTTP {st} {err}"[:160]
    items = _dig(json.loads(body), f.get("path") or [])
    if not isinstance(items, list) or not items:
        return None, "the response carried no rows at the declared path"
    df = pd.DataFrame(items)
    if f["date"] not in df.columns or f["value"] not in df.columns:
        return None, f"columns {f['date']}/{f['value']} absent"
    df["event_time"] = pd.to_datetime(df[f["date"]], errors="coerce", utc=True)
    df["v"] = pd.to_numeric(df[f["value"]], errors="coerce")
    grp = f.get("group")
    if grp and grp in df.columns:
        wide = df.pivot_table(index="event_time", columns=grp, values="v", aggfunc="sum")
        wide.columns = [re.sub(r"\W+", "_", str(c)).strip("_").lower() for c in wide.columns]
        return wide.reset_index(), ""
    return df.groupby("event_time", as_index=False)["v"].sum().rename(
        columns={"v": re.sub(r"\W+", "_", f["value"]).lower()}), ""


def _nyfed_pd(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    f = row["fetch"]
    st, body, err = get(f["list"])
    if not _ok(st, err):
        return None, f"list HTTP {st} {err}"[:160]
    doc = json.loads(body)
    keys = [str(_dig(x, ["keyid"]) or "") for x in (_dig(doc, ["pd", "timeseries"]) or [])]
    want = [k for k in keys if any(k.startswith(m) for m in f.get("match") or [])][:12]
    if not want:
        return None, "no primary-dealer series matched the declared prefixes"
    frames = []
    for k in want:
        st, body, err = get(str(f["get"]).format(keyid=k))
        if not _ok(st, err):
            continue
        ts = _dig(json.loads(body), ["pd", "timeseries"]) or []
        df = pd.DataFrame(ts)
        if df.empty or "asofdate" not in df.columns or "value" not in df.columns:
            continue
        df["event_time"] = pd.to_datetime(df["asofdate"], errors="coerce", utc=True)
        col = re.sub(r"\W+", "_", k).lower()
        df[col] = pd.to_numeric(df["value"], errors="coerce")
        frames.append(df[["event_time", col]].set_index("event_time"))
    if not frames:
        return None, "every matched series failed to fetch"
    return pd.concat(frames, axis=1).reset_index(), ""


def _fiscaldata(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    f = row["fetch"]
    st, body, err = get(f["url"])
    if not _ok(st, err):
        return None, f"HTTP {st} {err}"[:160]
    df = pd.DataFrame(json.loads(body).get("data") or [])
    if df.empty or f["date"] not in df.columns:
        return None, "no rows"
    df["event_time"] = pd.to_datetime(df[f["date"]], errors="coerce", utc=True)
    cols = [c for c in f.get("fields") or [] if c in df.columns]
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    g = df.groupby("event_time", as_index=False)[cols].sum()
    if {"indirect_bidder_accepted", "total_accepted"} <= set(g.columns):
        g["indirect_share"] = g["indirect_bidder_accepted"] / g["total_accepted"].replace(0, np.nan)
    if {"primary_dealer_accepted", "total_accepted"} <= set(g.columns):
        g["dealer_share"] = g["primary_dealer_accepted"] / g["total_accepted"].replace(0, np.nan)
    return g, ""


def _ofr_search(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    """OFR's documented API: search the metadata, then pull each matched series. Discovery-based
    so a renamed mnemonic is found again rather than hard-coded and silently lost."""
    f = row["fetch"]
    base = str(f["base"]).rstrip("/")
    mnems: list[str] = []
    for q in f.get("queries") or []:
        st, body, err = get(f"{base}/metadata/search?query={q.replace(' ', '%20')}")
        if not _ok(st, err):
            continue
        with contextlib.suppress(ValueError):
            for hit in json.loads(body) or []:
                m = str(hit.get("mnemonic") or "") if isinstance(hit, Mapping) else ""
                if m and m not in mnems:
                    mnems.append(m)
    mnems = mnems[: int(f.get("max_series") or 12)]
    if not mnems:
        return None, "the OFR metadata search returned no mnemonics"
    frames = []
    for m in mnems:
        st, body, err = get(f"{base}/series/timeseries?mnemonic={m}")
        if not _ok(st, err):
            continue
        with contextlib.suppress(ValueError, TypeError):
            pts = json.loads(body)
            df = pd.DataFrame(pts, columns=["event_time", "v"])
            df["event_time"] = pd.to_datetime(df["event_time"], errors="coerce", utc=True)
            col = re.sub(r"\W+", "_", m).lower()
            df[col] = pd.to_numeric(df["v"], errors="coerce")
            frames.append(df[["event_time", col]].dropna().set_index("event_time"))
    if not frames:
        return None, "every matched OFR series failed to fetch"
    return pd.concat(frames, axis=1).reset_index(), ""


def _finra_regsho(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    """Aggregate short-volume ratio across the consolidated tape, one number per day. Single
    names are summed away: this is an index-level crowding read, never a single-name signal."""
    f = row["fetch"]
    old = read_frame(str(row["id"]))
    have = set(old["event_time"].dt.strftime("%Y%m%d")) if old is not None else set()
    out = [] if old is None else [old[["event_time", "short_volume", "total_volume"]]]
    day = now_utc().date()
    tried = 0
    while tried < int(f.get("days") or 20):
        day -= timedelta(days=1)
        if day.weekday() >= 5:
            continue
        tried += 1
        key = day.strftime("%Y%m%d")
        if key in have:
            continue
        st, body, err = get(str(f["url"]).format(yyyymmdd=key))
        if not _ok(st, err):
            continue
        with contextlib.suppress(Exception):
            df = pd.read_csv(io.BytesIO(body), sep="|")
            sv = pd.to_numeric(df.get("ShortVolume"), errors="coerce").sum()
            tv = pd.to_numeric(df.get("TotalVolume"), errors="coerce").sum()
            out.append(pd.DataFrame({"event_time": [pd.Timestamp(day, tz="UTC")],
                                     "short_volume": [sv], "total_volume": [tv]}))
    if not out:
        return None, "no daily file fetched"
    g = pd.concat(out, ignore_index=True)
    g["short_volume_ratio"] = g["short_volume"] / g["total_volume"].replace(0, np.nan)
    return g, ""


def _sec_ftd(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    f = row["fetch"]
    out = []
    d = now_utc().date().replace(day=1)
    for _ in range(int(f.get("periods") or 6)):
        d = (d - timedelta(days=1)).replace(day=1)
        for half in ("a", "b"):
            st, body, err = get(str(f["url"]).format(yyyymm=d.strftime("%Y%m"), half=half))
            if not _ok(st, err):
                continue
            with contextlib.suppress(Exception):
                z = zipfile.ZipFile(io.BytesIO(body))
                txt = z.read(z.namelist()[0]).decode("latin-1")
                df = pd.read_csv(io.StringIO(txt), sep="|")
                df["event_time"] = pd.to_datetime(df.iloc[:, 0].astype(str), format="%Y%m%d",
                                                  errors="coerce", utc=True)
                df["qty"] = pd.to_numeric(df.iloc[:, 3], errors="coerce")
                out.append(df.groupby("event_time", as_index=False)["qty"].sum()
                           .rename(columns={"qty": "fails_shares"}))
    if not out:
        return None, "no FTD file fetched"
    return pd.concat(out, ignore_index=True), ""


RECIPES: dict[str, Callable[[Mapping[str, Any], HttpGet], tuple[pd.DataFrame | None, str]]] = {
    "fred_csv": _fred_csv, "nyfed_json": _nyfed_json, "nyfed_pd": _nyfed_pd,
    "fiscaldata": _fiscaldata, "ofr_search": _ofr_search, "finra_regsho_daily": _finra_regsho,
    "sec_ftd_zip": _sec_ftd,
}


def fetch_all(rows: list[dict[str, Any]], *, get: HttpGet | None, deadline: float
              ) -> dict[str, Any]:
    """Run every recipe the atlas declares, oldest-fetched first, until the wall clock is spent.
    A row not reached leads the next pass (the cursor is the last-fetch time)."""
    state = _read_json(FETCH_STATE, {})
    order = sorted((r for r in rows if (r.get("fetch") or {}).get("kind") in RECIPES),
                   key=lambda r: str((state.get(r["id"]) or {}).get("at") or ""))
    for r in order:
        if get is None or time.monotonic() > deadline:
            break
        sid = str(r["id"])
        try:
            df, why = RECIPES[r["fetch"]["kind"]](r, get)
            n = write_frame(sid, df, lag_hours=lag_hours_of(r)) if df is not None else 0
            state[sid] = {"at": now_utc().isoformat(timespec="seconds"), "rows": n,
                          "outcome": "OK" if n else (why or "EMPTY")}
        except Exception as exc:
            state[sid] = {"at": now_utc().isoformat(timespec="seconds"), "rows": 0,
                          "outcome": f"ERROR {type(exc).__name__}: {str(exc)[:120]}"}
    _write_json(FETCH_STATE, state)
    return state


# =========================================================================== features
def pct_rank(s: pd.Series, window: int = ROLL) -> pd.Series:
    return s.rolling(window, min_periods=MIN_OBS).apply(
        lambda a: float((a[:-1] <= a[-1]).mean()) if len(a) > 1 else np.nan, raw=True)


def zscore(s: pd.Series, window: int = ROLL) -> pd.Series:
    mu = s.rolling(window, min_periods=MIN_OBS).mean()
    sd = s.rolling(window, min_periods=MIN_OBS).std(ddof=0)
    return (s - mu) / sd.replace(0.0, np.nan)


def explode(s: pd.Series) -> pd.DataFrame:
    """The controlled feature family for one series (ontology.FEATURE_FAMILY, first eight)."""
    chg = s.diff()
    z = zscore(s)
    return pd.DataFrame({"level": s, "change": chg, "acceleration": chg.diff(),
                         "pct": pct_rank(s), "z": z, "chg_z": zscore(chg),
                         "extreme": (z.abs() > 2.0).astype(float).where(z.notna())})


#: COT frames -> MT5 asset, and the sign that turns the futures' long into the MT5 symbol's long.
COT_MAP: dict[str, tuple[str, str, int]] = {
    "cot_tff/eur": ("tff", "EURUSD", 1), "cot_tff/jpy": ("tff", "USDJPY", -1),
    "cot_tff/gbp": ("tff", "GBPUSD", 1), "cot_tff/cad": ("tff", "USDCAD", -1),
    "cot_tff/aud": ("tff", "AUDUSD", 1), "cot_tff/nzd": ("tff", "NZDUSD", 1),
    "cot_tff/chf": ("tff", "USDCHF", -1), "cot_tff/sp500": ("tff", "US500", 1),
    "cot_tff/nasdaq100": ("tff", "NAS100", 1),
    "cot_disagg/gold": ("disagg", "XAUUSD", 1), "cot_disagg/silver": ("disagg", "XAGUSD", 1),
}
#: Tuesday snapshot -> Friday 15:30 ET release: +3 days 20 hours covers both DST regimes.
COT_AVAILABLE_OFFSET = pd.Timedelta(days=3, hours=20)


def _main_market(df: pd.DataFrame) -> pd.DataFrame:
    """One row per report date: the largest-OI market. `fetch_tff` matches by substring, so a
    file can carry a cross (EURO FX/JAPANESE YEN) beside the outright; the outright is the one
    with the open interest."""
    oi = "oi" if "oi" in df.columns else "open_interest_all"
    return df.sort_values(oi).groupby("report_date", as_index=False).tail(1)


def cot_features(data_dir: Path = DESK / "data") -> dict[str, pd.DataFrame]:
    """Per-asset COT features on the PIT clock, read from the existing lane's frames."""
    out: dict[str, pd.DataFrame] = {}
    for key, (kind, asset, sign) in COT_MAP.items():
        p = data_dir / f"{key}.parquet"
        if not p.exists():
            continue
        try:
            df = _main_market(pd.read_parquet(p))
        except Exception:
            continue
        df["report_date"] = pd.to_datetime(df["report_date"], utc=True, errors="coerce")
        df = df.dropna(subset=["report_date"]).sort_values("report_date")
        if kind == "tff":
            oi = df["oi"].astype(float)
            lev = (df["lm_l"] - df["lm_s"]) / oi
            dealer = (df["dealer_l"] - df["dealer_s"]) / oi
            am = (df["am_l"] - df["am_s"]) / oi
            swap = pd.Series(np.nan, index=df.index)
            conc = pd.Series(np.nan, index=df.index)
        else:
            oi = df["open_interest_all"].astype(float)
            lev = (df["m_money_positions_long_all"] - df["m_money_positions_short_all"]) / oi
            swap = (df["swap_positions_long_all"] - df["swap__positions_short_all"]) / oi
            dealer = swap
            am = pd.Series(np.nan, index=df.index)
            conc = df["conc_net_le_4_tdr_long_all"].astype(float)
        f = pd.DataFrame({"available_time": df["report_date"] + COT_AVAILABLE_OFFSET})
        f["cot.lev_net_pct"] = pct_rank(sign * lev).to_numpy()
        f["cot.lev_net_z"] = zscore(sign * lev).to_numpy()
        f["cot.dealer_net_pct"] = pct_rank(sign * dealer).to_numpy()
        f["cot.swap_net_pct"] = pct_rank(sign * swap).to_numpy()
        f["cot.swap_net_z"] = zscore(sign * swap).to_numpy()
        f["cot.am_net_chg_z"] = zscore((sign * am).diff()).to_numpy()
        f["cot.oi_chg_z"] = zscore(oi.pct_change(fill_method=None)).to_numpy()
        f["cot.conc_top4_pct"] = pct_rank(conc).to_numpy()
        out[asset] = f.set_index("available_time")
    return out


#: Macro features: (atlas id, column regex, feature key, transform). The column is found by regex
#: so an OFR or NY Fed rename that keeps the meaning keeps the feature.
_US = "institutional.us."
MACRO_FEATURES: tuple[tuple[str, str, str, str], ...] = tuple((_US + a, b, c, d) for a, b, c, d in (
    ("nyfed.repo_reverse_repo_operations", r"reverse", "nyfed.rrp_chg_z", "chg_z"),
    ("fed.rrp_overnight", r"on_rrp", "nyfed.rrp_chg_z", "chg_z"),
    ("nyfed.securities_lending_soma", r".", "nyfed.seclending_demand_z", "z"),
    ("nyfed.primary_dealer_statistics", r"pdposgst", "nyfed.pd_net_positions_z", "z"),
    ("nyfed.primary_dealer_statistics", r"pdft", "nyfed.pd_fails_z", "z"),
    ("nyfed.reference_rates", r"sofr|tgcr|bgcr", "ofr.repo_rate_spread_z", "spread_z"),
    ("ofr.short_term_funding_monitor", r"rate", "ofr.repo_rate_spread_z", "spread_z"),
    ("ofr.short_term_funding_monitor", r"vol", "ofr.repo_volume_chg_z", "chg_z"),
    ("ofr.hedge_fund_monitor", r"lev", "ofr.hf_leverage_z", "z"),
    ("ofr.hedge_fund_monitor", r"repo", "ofr.hf_repo_borrowing_z", "z"),
    ("fed.h41_foreign_custody", r"custody_total", "fed.custody_chg_z", "chg_z"),
    ("fed.h8_bank_balance_sheet", r"bank_securities", "h8.securities_chg_z", "chg_z"),
    ("treasury.auction_investor_class", r"indirect_share", "treasury.auction_indirect_z", "z"),
    ("finra.regsho_daily_short_volume", r"short_volume_ratio", "finra.short_volume_ratio_z", "z"),
    ("sec.fails_to_deliver", r"fails_shares", "sec.ftd_z", "z"),
))


def macro_features() -> dict[str, tuple[pd.Series, str]]:
    """Asset-independent features: key -> (series on available_time, source id)."""
    out: dict[str, tuple[pd.Series, str]] = {}
    for sid, rx, key, how in MACRO_FEATURES:
        if key in out:
            continue          # the first measured source for a key wins; the next is a fallback
        df = read_frame(sid)
        if df is None or len(df) < MIN_OBS:
            continue
        cols = [c for c in df.columns if c not in ("event_time", "available_time", "source_id",
                                                   "retrieval_time", "vintage_id")
                and re.search(rx, c, re.I) and pd.api.types.is_numeric_dtype(df[c])]
        if not cols:
            continue
        s = df.set_index("available_time")[cols].astype(float)
        # dispersion across repo benchmarks, or the one column
        v = s.max(axis=1) - s.min(axis=1) if how == "spread_z" and len(cols) >= 2 else s[cols[0]]
        v = v[~v.index.duplicated(keep="last")].dropna()
        f = explode(v)
        col = {"chg_z": "chg_z", "z": "z", "spread_z": "z"}[how]
        out[key] = (f[col].dropna(), sid)
    return out


def price_features(asset: str, cot: pd.DataFrame | None) -> dict[str, pd.Series]:
    """Features read off the desk's own bars: drawdown z and positioning-vs-price divergence.
    Daily closes, shifted one day so a broker-time bar cannot lead the UTC clock."""
    try:
        from research import proposer_common as pc
        bars = pc.bars(asset)
    except Exception:
        bars = None
    if bars is None or bars.empty:
        return {}
    close = bars["close"].astype(float).resample("1D").last().dropna()
    close.index = close.index + pd.Timedelta(days=1)
    dd = close / close.rolling(60, min_periods=20).max() - 1.0
    out = {"price.drawdown_z": -zscore(dd, 250)}
    if cot is not None and "cot.lev_net_pct" in cot:
        ret4w = close.pct_change(20, fill_method=None)
        pos = cot["cot.lev_net_pct"].reindex(close.index, method="ffill")
        # Crowded long while price fails to advance: high positioning percentile, low return rank.
        out["price.div_vs_positioning"] = (pos - pct_rank(ret4w, 250)).astype(float)
    return out


def calendar_features(index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    """Deterministic calendar flows: month end (pension rebalance, fixing concentration) and the
    third-Friday index/option expiry, both known in advance and therefore lookahead-free."""
    if len(index) == 0:
        return {}
    idx = pd.DatetimeIndex(index)
    bme = (idx + pd.offsets.BMonthEnd(0)).normalize()
    days_to_me = (bme - idx.normalize()).days
    third_fri = [(d.weekday() == 4 and 15 <= d.day <= 21 and d.month % 3 == 0) for d in idx]
    return {"calendar.month_end": pd.Series((days_to_me <= 2).astype(float), index=idx),
            "calendar.index_event": pd.Series(np.asarray(third_fri, dtype=float), index=idx)}


# =========================================================================== latent states
def _as_z(key: str, v: float) -> float:
    """Every input on one scale: a percentile maps to an equivalent z, a z is clipped to +/-3."""
    if key.endswith("_pct") or key.endswith(".pct"):
        v = (v - 0.5) * 3.5
    if key.startswith("calendar."):
        v = 2.0 * v
    return float(max(-3.0, min(3.0, v)))


def fuse(state: Mapping[str, Any], inputs: Mapping[str, float]) -> dict[str, Any]:
    """P(state) from stated evidence weights, in log-odds, with a 95% interval.

    Every UNMEASURED input still costs its weight in variance: an input the desk cannot see is a
    N(0,1) unknown, so a state built on one of four inputs is wide and says so. `coverage` is the
    measured share of total weight. Below `min_inputs` the state is not emitted at all."""
    logit = 0.0
    var = 0.0
    wsum = wmeas = 0.0
    n = 0
    for key, sign, w in state["evidence"]:
        wsum += w
        v = inputs.get(key)
        if v is None or not math.isfinite(v):
            var += w * w
            continue
        n += 1
        wmeas += w
        logit += sign * w * _as_z(key, v)
        var += (0.35 * w) ** 2                  # a measured input is itself a noisy proxy
    if n < int(state.get("min_inputs", 1)):
        return {"p": None, "reason": f"UNMEASURED: {n} of {len(state['evidence'])} inputs"}
    sd = math.sqrt(var)
    sig = lambda x: 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))  # noqa: E731
    return {"p": round(sig(logit), 4), "lo": round(sig(logit - 1.96 * sd), 4),
            "hi": round(sig(logit + 1.96 * sd), 4), "coverage": round(wmeas / wsum, 3),
            "n_inputs": n}


def dealer_gamma_posterior(bars: pd.DataFrame | None, *, window_days: int = 5
                           ) -> pd.DataFrame | None:
    """Posterior over (long, neutral, short) dealer gamma from observed intraday behaviour.

    Long dealer gamma dampens: hourly returns mean-revert (negative lag-1 autocorrelation).
    Short dealer gamma amplifies: they trend (positive). Each day's trailing autocorrelation is
    scored under three Gaussians at -0.10 / 0 / +0.10 with the sampling error 1/sqrt(n), from a
    flat prior -- the public OI cannot say which side the dealer holds, so no prior pretends to."""
    if bars is None or bars.empty or "close" not in bars:
        return None
    r = np.log(bars["close"].astype(float)).diff().dropna()
    n = int(window_days * 23)
    ac = r.rolling(n, min_periods=30).corr(r.shift(1))
    daily = ac.groupby(ac.index.normalize()).last().dropna()
    if daily.empty:
        return None
    se = 1.0 / math.sqrt(n)
    means = np.array([-0.10, 0.0, 0.10])
    lik = np.exp(-0.5 * ((daily.to_numpy()[:, None] - means[None, :]) / se) ** 2)
    tot = lik.sum(axis=1, keepdims=True)
    post = np.where(tot > 0, lik / np.where(tot > 0, tot, 1.0), 1.0 / 3.0)
    return pd.DataFrame({"gamma_autocorr": daily.to_numpy(),
                         "p_dealer_long_gamma": post[:, 0], "p_dealer_neutral": post[:, 1],
                         "p_dealer_short_gamma": post[:, 2]},
                        index=pd.DatetimeIndex(daily.index + pd.Timedelta(days=1),
                                               name="available_time"))


def carry_forward(s: pd.Series, idx: pd.DatetimeIndex) -> pd.Series:
    """As-of join with a staleness horizon: a reading is carried forward for 2.5x the series'
    own median spacing (at least three days) and is UNMEASURED after that. A weekly COT read is
    good for ~17 days; a quarterly OFR read for ~7 months; a stopped feed goes dark, not flat."""
    s = s.dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if s.empty:
        return pd.Series(np.nan, index=idx)
    gaps = pd.Series(s.index).diff().dropna()
    spacing = gaps.median() if not gaps.empty else pd.Timedelta(days=7)
    horizon = max(pd.Timedelta(days=3), spacing * 2.5)
    stamp = pd.Series(s.index, index=s.index).reindex(idx, method="ffill")
    out = s.reindex(idx, method="ffill")
    return out.where((idx - pd.DatetimeIndex(stamp)) <= horizon)


def build_states(assets: Iterable[str] | None = None) -> dict[str, pd.DataFrame]:
    """One state frame per MT5 asset on the PIT clock, written to the lake."""
    onto = _ontology()
    cot = cot_features()
    macro = macro_features()
    want = set(assets) if assets else {a for s in onto.LATENT_STATES for a in s["assets"]}
    out: dict[str, pd.DataFrame] = {}
    for asset in sorted(want):
        cols: dict[str, pd.Series] = {}
        srcs: set[str] = set()
        if asset in cot:
            cols.update({k: cot[asset][k] for k in cot[asset].columns})
            srcs.add("institutional.us.cftc.cot_tff" if asset not in ("XAUUSD", "XAGUSD")
                     else "institutional.us.cftc.cot_disaggregated")
        for key, (s, sid) in macro.items():
            cols[key] = s
            srcs.add(sid)
        cols.update(price_features(asset, cot.get(asset)))
        if not cols:
            continue
        idx = sorted(set().union(*[set(s.dropna().index) for s in cols.values()]))
        if not idx:
            continue
        idx = pd.DatetimeIndex(idx)
        cols.update(calendar_features(idx))
        # A value older than its staleness horizon is UNMEASURED, not carried forever.
        panel = pd.DataFrame({k: carry_forward(v, idx) for k, v in cols.items()})
        rec = {}
        for st in onto.LATENT_STATES:
            if asset not in st["assets"]:
                continue
            ps, lo, hi, cov = [], [], [], []
            for _t, row in panel.iterrows():
                r = fuse(st, {k: row[k] for k in panel.columns if pd.notna(row[k])})
                ps.append(r.get("p"))
                lo.append(r.get("lo"))
                hi.append(r.get("hi"))
                cov.append(r.get("coverage"))
            rec[f"p_{st['id']}"] = ps
            rec[f"p_{st['id']}_lo"] = lo
            rec[f"p_{st['id']}_hi"] = hi
            rec[f"cov_{st['id']}"] = cov
        frame = pd.DataFrame(rec, index=idx).astype(float)
        if asset in ("US500", "NAS100", "US30", "US2000"):
            with contextlib.suppress(Exception):
                from research import proposer_common as pc
                g = dealer_gamma_posterior(pc.bars(asset))
                if g is not None:
                    frame = frame.join(pd.DataFrame({c: carry_forward(g[c], idx)
                                                     for c in g.columns}), how="left")
        frame = frame.dropna(axis=1, how="all").dropna(axis=0, how="all")
        if frame.empty:
            continue
        frame.index.name = "event_time"
        sid = f"{STATE_SERIES_PREFIX}.{asset}"
        f2 = frame.reset_index()
        f2.attrs["sources"] = sorted(srcs)
        # States are computed from inputs already on their PIT clock: available == event.
        write_frame(sid, f2, lag_hours=0.0)
        f2 = f2.set_index("event_time")
        f2.attrs["sources"] = sorted(srcs)
        out[asset] = f2
    return out


# =========================================================================== cells
def _culture(row: Mapping[str, Any] | None) -> dict[str, str]:
    row = row or {}
    return {k: str(row.get(k) or "") for k in ("source_culture", "participant_structure",
                                               "failure_mode_hypothesis", "crowding_prior")}


def _may_hunt(symbol: str) -> bool:
    try:
        import universe_policy as up
    except ImportError:
        try:
            from research import universe_policy as up  # type: ignore[no-redef]
        except ImportError:
            return False
    return bool(up.may_hypothesise(symbol))


def planned_cells(states: Mapping[str, pd.DataFrame], rows: list[dict[str, Any]]
                  ) -> list[dict[str, Any]]:
    """Every conditioner cell this pass owes: the latent states on their assets, and every raw
    atlas frame on disk against its declared targets (the dataset rule: no frame goes unfed)."""
    by_id = {r["id"]: r for r in rows}
    plans: list[dict[str, Any]] = []
    for asset, frame in states.items():
        if not _may_hunt(asset):
            continue
        srcs = list(frame.attrs.get("sources") or [])
        culture = _culture(by_id.get(srcs[0]) if srcs else None)
        culture["participant_structure"] = "institutional"
        for col in frame.columns:
            if not col.startswith("p_") or col.endswith(("_lo", "_hi")):
                continue
            plans.append({"source": f"{STATE_SERIES_PREFIX}.{asset}", "signal": col,
                          "symbol": asset, "source_id": srcs[0] if srcs else LEG,
                          "source_ids": srcs, "culture": culture, "kind": "state"})
    for r in rows:
        df = read_frame(str(r["id"]))
        if df is None or len(df) < MIN_OBS:
            continue
        sigs = [c for c in df.columns if c not in ("event_time", "available_time", "source_id",
                                                   "retrieval_time", "vintage_id")
                and pd.api.types.is_numeric_dtype(df[c])][:6]
        for sym in r.get("targets") or []:
            if not _may_hunt(sym):
                continue
            for sig in sigs:
                plans.append({"source": str(r["id"]), "signal": sig, "symbol": sym,
                              "source_id": str(r["id"]), "source_ids": [str(r["id"])],
                              "culture": _culture(r), "kind": "raw"})
    return plans


def emit_cells(plans: list[dict[str, Any]], *, deadline: float, dry_run: bool = False
               ) -> dict[str, Any]:
    """Through the one door, once per cell key, ever. The emitted set is the charge ledger's
    guard: a key already enqueued is never re-sent, so no pass inflates a search count."""
    prev = _read_json(EMITTED, {})
    done = set(prev.get("keys") or [])
    credited = set(prev.get("credited") or [])
    made = created = skipped = 0
    errors: list[str] = []
    culture_rows: list[dict[str, Any]] = []
    for p in plans:
        for tf in TRANSFORMS:
            for side in SIDES:
                for chart in CHARTS:
                    key = f"{p['source']}|{p['signal']}|{tf}|{side}|{p['symbol']}|{chart}"
                    if key in done:
                        skipped += 1
                        continue
                    if time.monotonic() > deadline:
                        break
                    made += 1
                    if dry_run:
                        continue
                    try:
                        from libs.moat.registry import enqueue_candidate
                        mech = (f"{p['signal']} of {p['source']} (public institutional footprint) "
                                f"conditions {p['symbol']}: side {side:+d} when high")
                        cid, new = enqueue_candidate(
                            family="exogenous_conditioner", symbol=p["symbol"],
                            params={"source": p["source"], "signal": p["signal"],
                                    "transform": tf, "side_when_high": side},
                            origin=LEG, mechanism=mech, chart=chart, horizon=chart,
                            source_id=p["source_id"], generator=LEG, department="information",
                            asset_class="", transformation="institutional_state"
                            if p["kind"] == "state" else "institutional_series",
                            required_data=[f"desks/mt5/data/lake/series/{p['source']}.csv"],
                            pit_status="STAMPED", causal_rationale=mech,
                            falsifier=(f"the {tf} of {p['source']}.{p['signal']} has no "
                                       f"measurable relation to {p['symbol']} at {chart} out of "
                                       "sample"), **p["culture"])
                        created += int(bool(new))
                        done.add(key)
                        credited.update(p["source_ids"])
                        culture_rows.append({"cell_id": cid, "source_id": p["source_id"],
                                             "source_ids": p["source_ids"], "origin": LEG,
                                             **p["culture"]})
                    except Exception as exc:
                        errors.append(f"{key}: {type(exc).__name__}: {str(exc)[:60]}")
    if not dry_run:
        _write_json(EMITTED, {"at": now_utc().isoformat(timespec="seconds"),
                              "keys": sorted(done), "credited": sorted(credited)})
        if culture_rows:
            CULTURE_LOG.parent.mkdir(parents=True, exist_ok=True)
            with CULTURE_LOG.open("a", encoding="utf-8") as fh:
                for c in culture_rows:
                    fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    return {"cells_attempted": made, "cells_created": created, "already_enqueued": skipped,
            "errors": errors[:5], "n_errors": len(errors),
            "sources_planned": sorted({p["source_id"] for p in plans}),
            "sources_credited": sorted(credited)}


# =========================================================================== watcher
def watch(rows: list[dict[str, Any]], get: HttpGet | None, deadline: float) -> dict[str, Any]:
    """The future-source watcher (principal 18:08Z item 16): every WATCH row's probe page is read
    and its markers searched. A marker found flips the row to DISCOVERED_NOT_INGESTED in the
    watch state and names it in the report -- onboarding needs no code redesign, only a recipe.
    Every fetched row's recipe failing twice running is flagged BROKEN, so a moved dataset is
    noticed rather than silently going stale."""
    st = _read_json(WATCH_STATE, {})
    for r in rows:
        f = r.get("fetch") or {}
        if f.get("kind") != "watch" or get is None or time.monotonic() > deadline:
            continue
        code, body, err = get(str(f["probe"]))
        text = body.decode("utf-8", "replace") if body else ""
        hits = [m for m in f.get("markers") or [] if m.lower() in text.lower()]
        prev = st.get(r["id"]) or {}
        st[r["id"]] = {"at": now_utc().isoformat(timespec="seconds"), "http": code,
                       "error": err[:120], "markers_found": hits,
                       "status": "DISCOVERED_NOT_INGESTED" if hits else "WATCH",
                       "first_seen": prev.get("first_seen") or (
                           now_utc().isoformat(timespec="seconds") if hits else "")}
    _write_json(WATCH_STATE, st)
    return st


# =========================================================================== coverage
def row_status(r: Mapping[str, Any], fetch_state: Mapping[str, Any],
               watch_state: Mapping[str, Any], emitted_sources: set[str]) -> str:
    """Measured, not declared: ACTIVE needs a frame on disk AND cells enqueued from it."""
    sid = str(r["id"])
    declared = str(r.get("declared_status") or "DISCOVERED_NOT_INGESTED")
    if declared == "WATCH":
        return str((watch_state.get(sid) or {}).get("status") or "WATCH")
    has_frame = series_path(sid).exists()
    if (r.get("fetch") or {}).get("kind") == "lake_parquet":
        has_frame = any(ROOT.glob(str(r["fetch"]["glob"])))
    if has_frame and sid in emitted_sources:
        return "ACTIVE"
    if declared in ("PAID_PUBLIC_PROXY", "BLOCKED_SUBSTITUTE", "NOT_PUBLISHED",
                    "TESTED_NO_INFORMATION", "NOT_RELEVANT"):
        return declared
    return "DISCOVERED_NOT_INGESTED"


def coverage(rows: list[dict[str, Any]], *, fetch_state: Mapping[str, Any] | None = None,
             watch_state: Mapping[str, Any] | None = None,
             emitted_sources: set[str] | None = None,
             rulings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The jurisdiction x class grid, one status per cell; the role grid; triangulation; the
    equivalence-search queue that asks each jurisdiction for what its peers publish."""
    onto = _ontology()
    fs = fetch_state or {}
    ws = watch_state or {}
    em = emitted_sources or set()
    rul = dict(rulings if rulings is not None else _read_json(RULINGS, {}))
    rank = {s: i for i, s in enumerate(("ACTIVE", "TESTED_NO_INFORMATION",
                                        "DISCOVERED_NOT_INGESTED", "PAID_PUBLIC_PROXY",
                                        "BLOCKED_SUBSTITUTE", "WATCH", "NOT_PUBLISHED",
                                        "NOT_RELEVANT"))}
    status_of = {str(r["id"]): row_status(r, fs, ws, em) for r in rows}
    grid: dict[str, dict[str, dict[str, Any]]] = {}
    roles: dict[str, dict[str, list[str]]] = {}
    for j in onto.coverage_jurisdictions():
        grid[j] = {}
        roles[j] = {role: [] for role in onto.JURISDICTION_ROLES}
        for cls in onto.CLASS_IDS:
            ids = [str(r["id"]) for r in rows if r.get("jurisdiction") == j
                   and r.get("source_class") == cls]
            ruled = rul.get(f"{j}|{cls}")
            if ids:
                st = min((status_of[i] for i in ids), key=lambda s: rank.get(s, 99))
                if st == "WATCH":
                    st = "DISCOVERED_NOT_INGESTED"
            elif ruled:
                st = str(ruled.get("status") if isinstance(ruled, Mapping) else ruled)
            elif j != "global" and cls in onto.GLOBAL_ONLY_CLASSES:
                st = "NOT_RELEVANT"
            else:
                st = onto.UNSEARCHED
            grid[j][cls] = {"status": st, "sources": ids}
        for r in rows:
            if r.get("jurisdiction") == j:
                for role in onto.roles_of(r):
                    roles[j][role].append(str(r["id"]))
    counts: dict[str, int] = {}
    for j in grid.values():
        for c in j.values():
            counts[c["status"]] = counts.get(c["status"], 0) + 1
    queue = []
    for j, cells in grid.items():
        for cls, c in cells.items():
            if c["status"] != onto.UNSEARCHED:
                continue
            peers = [pid for jj, cc in grid.items() if jj != j for pid in cc[cls]["sources"]][:3]
            if peers:
                queue.append({"jurisdiction": j, "source_class": cls, "peer_examples": peers,
                              "ask": f"does {j} publish a local equivalent of {cls}? "
                                     "ingest it, else name a public proxy, else rule "
                                     "NOT_PUBLISHED"})
    for j, rr in roles.items():
        if j == "global" or j not in onto.JURISDICTION_CODES:
            continue          # region packs owe classes, not a national institution set
        for role, ids in rr.items():
            if not ids:
                queue.append({"jurisdiction": j, "role": role,
                              "ask": f"name {j}'s {role.replace('_', ' ')} and its public "
                                     "datasets, or rule that it publishes none"})
    tri = {}
    for com, views in onto.COMMODITY_TRIANGULATION.items():
        tri[com] = {v: {i: status_of.get(i, "NOT_IN_ATLAS") for i in ids}
                    for v, ids in views.items()}
        tri[com]["views_covered"] = sum(
            1 for v, ids in views.items()
            if any(status_of.get(i) in ("ACTIVE", "DISCOVERED_NOT_INGESTED") for i in ids))
    return {"grid": grid, "status_counts": counts, "roles": roles,
            "role_gaps": {j: sorted(k for k, v in rr.items() if not v) for j, rr in roles.items()},
            "row_status": status_of, "search_queue": queue, "triangulation": tri,
            "n_cells": sum(len(v) for v in grid.values())}


def state_ages(states: Mapping[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    """The age of each latent state per asset (CRO D37 reads this): hours since the last
    available_time at which the state was measured, and the latest reading with its interval."""
    now = pd.Timestamp(now_utc())
    out: dict[str, dict[str, Any]] = {}
    for asset, f in states.items():
        out[asset] = {}
        for col in f.columns:
            if not col.startswith("p_") or col.endswith(("_lo", "_hi")):
                continue
            s = f[col].dropna()
            if s.empty:
                continue
            t = s.index[-1]
            sid = col[2:]
            out[asset][sid] = {
                "p": round(float(s.iloc[-1]), 4),
                "lo": _last(f, f"{col}_lo"), "hi": _last(f, f"{col}_hi"),
                "coverage": _last(f, f"cov_{sid}"),
                "as_of": pd.Timestamp(t).isoformat(),
                "age_hours": round((now - pd.Timestamp(t)).total_seconds() / 3600.0, 1)}
    return out


def regimes(ages: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, dict[str, str]]:
    """The discrete reading a consumer can react to without re-solving on every decimal: HIGH
    when the whole 95% interval sits above one half and p > 0.7, LOW when it sits below and
    p < 0.3, else NEUTRAL; the dealer scenarios report their argmax. `allocator_trigger` hashes
    this block, so the book re-solves when a state CROSSES, never when it drifts."""
    scen = set(_ontology().DEALER_GAMMA_SCENARIOS)
    out: dict[str, dict[str, str]] = {}
    for asset, states in ages.items():
        row: dict[str, str] = {}
        gamma = {k: v["p"] for k, v in states.items() if k in scen}
        for sid, v in states.items():
            if sid in scen:
                continue
            p, lo, hi = v.get("p"), v.get("lo"), v.get("hi")
            if p is None:
                continue
            row[sid] = ("HIGH" if lo is not None and lo > 0.5 and p > 0.7 else
                        "LOW" if hi is not None and hi < 0.5 and p < 0.3 else "NEUTRAL")
        if gamma:
            row["dealer_gamma"] = max(gamma, key=lambda k: gamma[k])
        out[asset] = row
    return out


def _last(f: pd.DataFrame, col: str) -> float | None:
    if col not in f.columns:
        return None
    s = f[col].dropna()
    return round(float(s.iloc[-1]), 4) if not s.empty else None


def load_states() -> dict[str, pd.DataFrame]:
    out = {}
    for p in sorted(SERIES.glob(f"{STATE_SERIES_PREFIX}.*.csv")):
        df = read_frame(p.stem)
        if df is not None:
            out[p.stem.split(".", 1)[1]] = df.set_index("available_time")
    return out


# =========================================================================== the pass
def run(budget_s: float = 300.0, *, offline: bool = False, dry_run: bool = False,
        get: HttpGet | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + budget_s
    rows = load_roster()
    transport = get if get is not None else (None if offline else polite_get(deadline))
    fs = fetch_all(rows, get=transport, deadline=t0 + budget_s * 0.45)
    ws = watch(rows, transport, deadline=t0 + budget_s * 0.55)
    states = build_states()
    plans = planned_cells(states, rows)
    cells = emit_cells(plans, deadline=deadline, dry_run=dry_run)
    emitted_sources = set(cells["sources_credited"])
    cov = coverage(rows, fetch_state=fs, watch_state=ws, emitted_sources=emitted_sources)
    ages = state_ages(states or load_states())
    fetched = {k: v for k, v in fs.items() if isinstance(v, Mapping)}
    # THE DATASET RULE (principal 2026-09-30 15:33Z): a frame on disk with no cell is UNFED.
    unfed = sorted(sid for sid, st in cov["row_status"].items()
                   if series_path(sid).exists() and st != "ACTIVE")
    report = {
        "at": now_utc().isoformat(timespec="seconds"), "leg": LEG,
        "atlas": {"rows": len(rows), "jurisdictions": len({r.get('jurisdiction') for r in rows}),
                  "with_recipe": sum(1 for r in rows if (r.get("fetch") or {}).get("kind")
                                     in RECIPES)},
        "status_counts": cov["status_counts"], "n_cells": cov["n_cells"],
        "grid": {j: {c: v["status"] for c, v in cells_.items()}
                 for j, cells_ in cov["grid"].items()},
        "grid_sources": {j: {c: v["sources"] for c, v in cells_.items() if v["sources"]}
                         for j, cells_ in cov["grid"].items()},
        "role_gaps": cov["role_gaps"],
        "search_queue_n": len(cov["search_queue"]),
        "search_queue_by_class": _count_by(cov["search_queue"], "source_class"),
        "search_queue_by_role": _count_by(cov["search_queue"], "role"),
        "search_queue_head": cov["search_queue"][:40],
        "search_queue_path": "desks/mt5/data/institutional/search_queue.json",
        "triangulation": cov["triangulation"], "row_status": cov["row_status"],
        "fetch": fetched, "watch": ws, "latent_state_age": ages,
        "cells": cells, "unfed": unfed, "unfed_count": len(unfed),
        "offline": bool(offline and get is None), "elapsed_s": round(time.monotonic() - t0, 1),
        "rule": ("one status per jurisdiction x class cell; ACTIVE is measured (frame on disk "
                 "and cells enqueued), never declared; UNSEARCHED is red and every UNSEARCHED "
                 "cell a peer jurisdiction covers is in search_queue; states are probabilities "
                 "with 95% intervals and dealer gamma is a scenario posterior"),
    }
    if not dry_run:
        _write_json(SEARCH_QUEUE, {"at": report["at"], "queue": cov["search_queue"]})
        _write_json(REPORT, report)
        _write_json(STATE_REPORT, {"at": report["at"], "states": ages,
                                   "regimes": regimes(ages),
                                   "use": "allocator and conditioner input: P(state) per asset "
                                          "with its interval and evidence coverage; a state "
                                          "absent here is UNMEASURED"})
    return report


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        if r.get(key):
            out[str(r[key])] = out.get(str(r[key]), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--offline", action="store_true", help="no network; build from frames on disk")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run(a.budget_s, offline=a.offline, dry_run=a.dry_run)
    print(json.dumps({k: rep[k] for k in ("at", "atlas", "status_counts", "unfed_count",
                                          "elapsed_s")}, default=str))
    print(json.dumps(rep["cells"], default=str)[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""ASIA RELATIVE-VALUE STATES -- the Hong Kong carry state and the Singapore band state, refreshed.

One pass, run at the head of the hourly `culture_gap_cells` leg (whose recipes consume what this
writes, in the same pass):

  1. reads `asia_rv_sources.json`; a row whose `terms` is not OPEN is REPORTED with its clause and
     never fetched (TERMS_BLOCKED, BLOCKED_INPUT, REFUSED);
  2. HONG KONG: fetches the HKMA interbank-liquidity API and the NY Fed SOFR API (robots.txt
     read first with our own User-Agent, an unread policy never a yes; no retries; 401/403/429/451
     a HARD STOP held in state), merges first prints into a PIT store, and writes
     `data/lake/series/hk_hibor_sofr_carry.parquet` (`countries/hk/carry_state.py`);
  3. SINGAPORE: builds the S$NEER band position from broker bars and writes
     `data/lake/series/sg_neer_band.parquet`, and keeps `data/calendars/mas_mps.json` equal to the
     scheduled MPS record (`countries/sg/band_state.py`);
  4. writes `reports/ASIA_RV_STATES.json`: every source's terms state, every series' status, and
     the ADR/H-share basis named BLOCKED_INPUT.

    python desks/mt5/research/countries/asia_rv_states.py --once
    python desks/mt5/research/countries/asia_rv_states.py --once --offline   # held stores only
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.robotparser
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[2]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.countries.hk import carry_state as HK  # noqa: E402
from research.countries.sg import band_state as SG  # noqa: E402

REGISTRY = Path(__file__).resolve().with_name("asia_rv_sources.json")
STORE = DESK / "data" / "lake" / "country_states"
STATE = STORE / "state.json"
SERIES = DESK / "data" / "lake" / "series"
BARS = DESK / "data" / "universe"
OUT = DESK / "reports" / "ASIA_RV_STATES.json"
UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; asia_rv_states)"
HARD_STOP = frozenset({401, 403, 429, 451})
#: Daily sources: one read every 20 hours is ample and polite.
REFETCH_S = 20 * 3600
HKMA_MAX_PAGES = 8
#: Wall budget of one pass inside the culture_gap_cells leg (its own budget is 240 s).
BUDGET_S = 75.0


class HardStop(Exception):
    def __init__(self, code: int, url: str):
        super().__init__(f"HTTP {code} {url}")
        self.code = code


class FetchError(Exception):
    def __init__(self, code: int | None, why: str):
        super().__init__(why)
        self.code = code


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(p)


def registry(path: Path = REGISTRY) -> list[dict[str, Any]]:
    doc = _read(path, {})
    rows = doc.get("sources") if isinstance(doc, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def fetchable(row: Mapping[str, Any]) -> bool:
    """Only an OPEN row with a named network adapter is ever fetched."""
    return row.get("terms") == "OPEN" and str(row.get("adapter")) in ("hkma_api", "nyfed_sofr")


# ------------------------------------------------------------------------------ the one door

def get_text(url: str, timeout: float = 20.0, deadline: float | None = None) -> str:
    """One honest GET: our UA, no retries, a refusal status is a hard stop. `deadline` (a
    `time.monotonic()` value) caps the call so the pass cannot outlive its budget."""
    from libs.data import polite_fetch
    r = polite_fetch.get(url, headers={"User-Agent": UA,
                                       "Accept": "application/json,text/plain;q=0.8"},
                         timeout=timeout, retries=0, deadline=deadline, leg="asia_rv_states",
                         max_bytes=8_000_000)
    if r.status in HARD_STOP:
        raise HardStop(int(r.status or 0), url)
    if not r.ok:
        raise FetchError(r.status, r.error or f"HTTP {r.status}")
    return r.text


def robots_allow(url: str, fetch: Callable[[str], str]) -> bool:
    """robots.txt for the host, read with our UA. 404 allows (the standard); any other failure
    to read it does not."""
    p = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(fetch(f"{p.scheme}://{p.netloc}/robots.txt").splitlines())
    except FetchError as exc:
        return exc.code == 404
    except HardStop:
        return False
    return rp.can_fetch(UA, url)


def _due(state: Mapping[str, Any], sid: str, now: datetime) -> bool:
    last = float((state.get("fetched_at") or {}).get(sid, 0.0) or 0.0)
    return now.timestamp() - last >= REFETCH_S


def collect(row: Mapping[str, Any], state: dict[str, Any], now: datetime,
            fetch: Callable[[str], str] | None, store: dict[str, Any]) -> dict[str, Any]:
    """Read one OPEN source when due and allowed, merging first prints into `store`."""
    sid, url = str(row["id"]), str(row["url"])
    if fetch is None:
        return {"status": "OFFLINE", "held": len(store)}
    if sid in (state.get("hard_stops") or {}):
        return {"status": "HARD_STOP", "held": len(store), **state["hard_stops"][sid]}
    if not _due(state, sid, now):
        return {"status": "NOT_DUE", "held": len(store)}
    try:
        if not robots_allow(url, fetch):
            return {"status": "UNMEASURED", "why": "robots disallows or was unreadable",
                    "held": len(store)}
        if row["adapter"] == "hkma_api":
            fresh: dict[str, dict[str, float]] = {}
            pages = 1 if store else HKMA_MAX_PAGES
            for page in range(pages):
                got, size = HK.parse_hkma(json.loads(fetch(
                    f"{url}?pagesize={HK.HKMA_PAGE}&offset={page * HK.HKMA_PAGE}")))
                fresh.update(got)
                if not got or size is None or (page + 1) * HK.HKMA_PAGE >= size:
                    break
            rule = "hkma"
        else:
            held = sorted(store)
            start = (pd.Timestamp(held[-1]) - pd.Timedelta(days=14)).date().isoformat() \
                if held else HK.SOFR_FIRST
            end = now.date().isoformat()
            fresh = HK.parse_sofr(json.loads(fetch(f"{url}?startDate={start}&endDate={end}")))
            rule = "sofr"
        if not fresh:
            return {"status": "UNPARSED", "held": len(store)}
        merged = HK.merge_first(store, fresh, rule, now)
        state.setdefault("fetched_at", {})[sid] = now.timestamp()
        return {"status": "READ", "held": len(store), **merged}
    except HardStop as hs:
        state.setdefault("hard_stops", {})[sid] = {"code": hs.code, "at": _now()}
        return {"status": "HARD_STOP", "code": hs.code, "held": len(store)}
    except Exception as exc:  # one source's failure is named, never fatal to the pass
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {str(exc)[:120]}",
                "held": len(store)}


# ------------------------------------------------------------------------------ outputs

def _write_series(sid: str, frame: pd.DataFrame, series_dir: Path) -> str:
    out = frame.copy()
    out["source_id"] = sid
    out["retrieval_time"] = _now()
    series_dir.mkdir(parents=True, exist_ok=True)
    p = series_dir / f"{sid}.parquet"
    tmp = p.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    tmp.replace(p)
    return str(p.relative_to(DESK)) if p.is_relative_to(DESK) else str(p)


def bars_loader(bars_dir: Path = BARS) -> Callable[[str], pd.DataFrame | None]:
    def load(sym: str) -> pd.DataFrame | None:
        p = bars_dir / f"{sym}_H1.parquet"
        if not p.exists():
            return None
        try:
            return pd.read_parquet(p, columns=["close"])
        except Exception:
            return None
    return load


def run(*, offline: bool = False, now: datetime | None = None, budget_s: float = BUDGET_S,
        fetch: Callable[[str], str] | None = None, store_dir: Path = STORE,
        series_dir: Path = SERIES, bars: Callable[[str], pd.DataFrame | None] | None = None,
        calendar_path: Path = SG.CALENDAR_PATH, registry_path: Path = REGISTRY
        ) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or datetime.now(UTC)
    deadline = t0 + max(5.0, budget_s)
    door = None if offline else (fetch or (lambda u: get_text(u, deadline=deadline)))
    rows = registry(registry_path)
    state_path = store_dir / "state.json"
    state = _read(state_path, {})
    state = state if isinstance(state, dict) else {}
    sources: list[dict[str, Any]] = []
    stores: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = str(row.get("id"))
        base = {"id": sid, "terms": row.get("terms"), "terms_url": row.get("terms_url"),
                "terms_read": row.get("terms_read"), "feeds": row.get("feeds")}
        if not fetchable(row):
            sources.append({**base, "status": "NOT_FETCHED" if row.get("terms") == "OPEN"
                            else str(row.get("terms")), "clause": row.get("terms_clause")})
            continue
        sp = store_dir / f"{sid}.json"
        store = _read(sp, {})
        store = store if isinstance(store, dict) else {}
        res = collect(row, state, now, door, store)
        if res.get("status") == "READ":
            _write(sp, store)
        stores[str(row["adapter"])] = store
        sources.append({**base, **res})
    series: dict[str, Any] = {}
    # HONG KONG
    carry = HK.carry_frame(stores.get("hkma_api", {}), stores.get("nyfed_sofr", {}))
    if len(carry) >= HK.MIN_ROWS:
        last = carry.iloc[-1]
        series[HK.SERIES_ID] = {
            "status": "BUILT", "targets": ["USDHKD"], "rows": len(carry),
            "path": _write_series(HK.SERIES_ID, carry, series_dir),
            "last_event": str(pd.Timestamp(last["event_time"]).date()),
            "last": {k: round(float(last[k]), 4) for k in ("hibor_on_sofr", "hibor_1m_sofr")
                     if k in carry.columns and pd.notna(last[k])}}
    else:
        series[HK.SERIES_ID] = {"status": f"UNMEASURED: {len(carry)} rows (< {HK.MIN_ROWS})",
                                "targets": ["USDHKD"]}
    blocked = next((r for r in rows if r.get("id") == "hk_adr_h_basis"), {})
    series["hk_adr_h_basis"] = {"status": str(blocked.get("terms") or "BLOCKED_INPUT"),
                                "targets": ["HK50"], "why": blocked.get("terms_clause")}
    # SINGAPORE
    band, info = SG.build(bars or bars_loader())
    if not band.empty:
        info["path"] = _write_series(SG.SERIES_ID, band, series_dir)
    series[SG.SERIES_ID] = info
    cal_changed = SG.write_calendar(calendar_path)
    _write(state_path, state)
    return {
        "generated_at": _now(), "organ": "asia_rv_states", "clock": "hourly leg culture_gap_cells",
        "offline": door is None, "sources": sources, "series": series,
        "calendar": {"name": "mas_mps", "path": str(calendar_path), "rewritten": cal_changed,
                     **SG.record_summary()},
        "consumers": {
            "data/lake/series/<id>.parquet": "family_exogenous_conditioner via the culture-gap "
                                             "recipes hk_hibor_sofr_carry_state and "
                                             "sg_neer_band_state",
            "data/calendars/mas_mps.json": "fx_fixing_reversal via the culture-gap recipe "
                                           "sg_mas_mps_hour (mt5desk/local_clock.calendar_mask)"},
        "wall_s": round(time.monotonic() - t0, 2)}


def refresh(*, offline: bool = False) -> dict[str, Any]:
    """The hourly entry point: run, write the report, return a one-line summary block."""
    doc = run(offline=offline)
    _write(OUT, doc)
    return {"report": str(OUT.relative_to(DESK)),
            "series": {k: v.get("status") for k, v in doc["series"].items()},
            "wall_s": doc["wall_s"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--offline", action="store_true", help="held stores and bars only")
    a = ap.parse_args(argv)
    print(json.dumps(refresh(offline=a.offline), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

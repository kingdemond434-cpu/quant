"""Taiwan options positioning: the TAIFEX TXO put/call ratio as a world-sensor state (ASIA-0510).

TAIFEX publishes, every trading day after the 13:45 Taipei close, the put/call ratio of TAIEX
options (TXO) in VOLUME and in OPEN INTEREST. Taiwan is the semiconductor state: TSMC is a third
of the TAIEX, so the hedging demand of the people closest to the chip cycle is a read on the
same industrial state that moves TSMC, NAS100, JPN225, HK50 and the Australian dollar -- one the
desk's price bars do not carry.

THE STATE, per Taipei trading day d (all trailing, never centred):
    pcr_oi, pcr_vol            the ratios as published (%, puts / calls)
    pcr_oi_z, pcr_vol_z        z against the trailing 252 days BEFORE d
    d_pcr_oi_z                 5-day change of pcr_oi, z against its own trailing 252 days
available_time = d 10:00 UTC (18:00 Taipei), a declared lag past the publication, so the row is
knowable before the MT5 broker day d closes (21:00 UTC) and the return it is scored on is
close(d) -> close(d+1), strictly after it.

THE CONTRACTS (sensor_engines), per MT5 target with bars here:
    puts_heavy->long      long the next broker day only while pcr_oi_z >= 1 (hedged market,
                          contrarian) vs long ungated: Kelly growth, block-shuffled gate null
    calls_heavy->short    short while pcr_oi_z <= -1 vs short ungated
    pcr_vol_z ~ |r_next|  Spearman of hedging-volume surprise on the next day's absolute move
Nothing is a trade: cells go to the gauntlet through the exogenous_conditioner family.

TERMS, FAIL-CLOSED. The numbers come from taifex.com.tw, whose site terms this desk has not read
(the cloud proxy refuses the host). `libs.data.terms_hold` holds the key "taifex": the series is
collected and measured, and no cell reaches the gauntlet until a CLEARED row with the quoted
clause is recorded in desks/mt5/data/terms_clearances.json.

    python desks/mt5/macro/taiwan_options.py [--days 1500] [--no-fetch] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_engines as se  # noqa: E402

ENGINE = "taiwan_options"
REPORT = DESK / "reports" / "TAIWAN_OPTIONS.json"
STORE = DESK / "data" / "taifex" / "pc_ratio.csv"
UNIVERSE_DIR = DESK / "data" / "universe"
URL = "https://www.taifex.com.tw/cht/3/pcRatioDown"
DATA_SOURCE = "taifex:pc_ratio"
SERIES_ID = "ws_tw_txo_pcr"
UNMEASURED = "UNMEASURED"
TRAIL = 252
CHUNK_DAYS = 30
FIELDS = ("date", "put_vol", "call_vol", "pcr_vol", "put_oi", "call_oi", "pcr_oi")
SIGNALS = ("pcr_oi_z", "pcr_vol_z", "d_pcr_oi_z")
#: MT5 instruments the Taiwan chip state transmits to, most direct first.
TARGETS: tuple[str, ...] = ("TSMC", "NAS100", "JPN225", "HK50", "AUDUSD")
#: Publication after the 13:45 Taipei close; 10:00 UTC is 18:00 Taipei.
AVAILABLE_UTC_HOUR = 10


# ============================================================================== the source
def _num(text: str) -> float | None:
    t = str(text or "").replace(",", "").replace("%", "").strip()
    try:
        v = float(t)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _day(text: str) -> str | None:
    t = str(text or "").strip().replace("-", "/")
    try:
        y, m, d = (int(x) for x in t.split("/"))
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_csv(body: bytes) -> list[dict[str, Any]]:
    """TAIFEX's download: one row per trading day, the date first, then put volume, call volume,
    volume ratio %, put OI, call OI, OI ratio % (Big5 headers; read by position, not by name)."""
    text = ""
    for enc in ("utf-8-sig", "cp950", "big5"):
        try:
            text = body.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    out: list[dict[str, Any]] = []
    for cells in csv.reader(io.StringIO(text)):
        if len(cells) < 7:
            continue
        day = _day(cells[0])
        vals = [_num(c) for c in cells[1:7]]
        if day is None or any(v is None for v in vals):
            continue
        out.append(dict(zip(FIELDS, [day, *vals], strict=True)))
    return out


def fetch(start: date, end: date, timeout: float = 30.0) -> list[dict[str, Any]]:
    data = urllib.parse.urlencode({"queryStartDate": start.strftime("%Y/%m/%d"),
                                   "queryEndDate": end.strftime("%Y/%m/%d")}).encode()
    req = urllib.request.Request(URL, data=data, headers={
        "User-Agent": "Mozilla/5.0 (research; daily statistics)",
        "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:   # a fixed https host
        return parse_csv(resp.read())


def load_store(path: Path = STORE) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                day = _day(r.get("date", "").replace("-", "/"))
                if day:
                    out[day] = {"date": day, **{k: _num(r.get(k, "")) for k in FIELDS[1:]},
                                "fetched_at": r.get("fetched_at", "")}
    except OSError:
        pass
    return out


def save_store(rows: Mapping[str, Mapping[str, Any]], path: Path = STORE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[*FIELDS, "fetched_at"])
        w.writeheader()
        for day in sorted(rows):
            w.writerow({k: rows[day].get(k, "") for k in (*FIELDS, "fetched_at")})
    tmp.replace(path)


def refresh(days: int, now: datetime, path: Path = STORE, fetcher: Any = fetch,
            budget_s: float = 240.0) -> dict[str, Any]:
    """Fill the store back `days` calendar days, newest chunk always re-read (a late print),
    older chunks only where the store has no row. Resumable: each chunk is saved as it lands."""
    have = load_store(path)
    end = now.date()
    start = end - timedelta(days=days)
    started = time.monotonic()
    got = failed = 0
    errors: list[str] = []
    hi = end
    while hi >= start and time.monotonic() - started < budget_s:
        lo = max(start, hi - timedelta(days=CHUNK_DAYS - 1))
        span = {(lo + timedelta(days=i)).isoformat() for i in range((hi - lo).days + 1)}
        if hi != end and any(d in have for d in span):
            hi = lo - timedelta(days=1)
            continue
        try:
            rows = fetcher(lo, hi)
        except Exception as exc:
            failed += 1
            errors.append(f"{lo}..{hi}: {type(exc).__name__}: {str(exc)[:80]}")
            if failed >= 3:
                break
            hi = lo - timedelta(days=1)
            continue
        stamp = now.isoformat(timespec="seconds")
        for r in rows:
            have[r["date"]] = {**r, "fetched_at": stamp}
        got += len(rows)
        save_store(have, path)
        hi = lo - timedelta(days=1)
    return {"rows_fetched": got, "chunks_failed": failed, "errors": errors[:4],
            "store_rows": len(have), "status": "OK" if not failed else "PARTIAL"}


# ============================================================================== the state
def _z(hist: Sequence[float], x: float) -> float | None:
    if len(hist) < 60:
        return None
    m = sum(hist) / len(hist)
    sd = math.sqrt(sum((v - m) ** 2 for v in hist) / (len(hist) - 1))
    return round((x - m) / sd, 6) if sd > 0 else None


def build_rows(store: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    days = sorted(d for d in store if isinstance(store[d].get("pcr_oi"), float)
                  and isinstance(store[d].get("pcr_vol"), float))
    oi = [float(store[d]["pcr_oi"]) for d in days]
    vol = [float(store[d]["pcr_vol"]) for d in days]
    d5 = [oi[i] - oi[i - 5] if i >= 5 else math.nan for i in range(len(oi))]
    out: list[dict[str, Any]] = []
    for i, d in enumerate(days):
        lo = max(0, i - TRAIL)
        prev_d5 = [v for v in d5[lo:i] if math.isfinite(v)]
        avail = datetime.fromisoformat(d).replace(hour=AVAILABLE_UTC_HOUR, tzinfo=UTC)
        out.append({"event_time": d, "available_time": avail.isoformat(),
                    "knowable_basis": "declared_lag", "source_id": DATA_SOURCE,
                    "pcr_oi": oi[i], "pcr_vol": vol[i],
                    "pcr_oi_z": _z(oi[lo:i], oi[i]), "pcr_vol_z": _z(vol[lo:i], vol[i]),
                    "d_pcr_oi_z": _z(prev_d5, d5[i]) if math.isfinite(d5[i]) else None})
    return out


def daily_closes(symbol: str, universe_dir: Path = UNIVERSE_DIR) -> dict[str, float]:
    try:
        from macro.vol_conditioner import daily_closes as dc
    except ImportError:                                  # pragma: no cover - import context
        from desks.mt5.macro.vol_conditioner import daily_closes as dc  # type: ignore[no-redef]
    return dc(symbol, universe_dir)


def align(rows: Sequence[Mapping[str, Any]], closes: Mapping[str, float]
          ) -> list[tuple[Mapping[str, Any], float]]:
    """(state on Taipei day d, return close(d) -> close(next broker day)) for every d the
    broker also traded. The state is knowable at 10:00 UTC, before close(d) at 21:00 UTC."""
    bdays = sorted(closes)
    pos = {d: i for i, d in enumerate(bdays)}
    out: list[tuple[Mapping[str, Any], float]] = []
    for r in rows:
        i = pos.get(str(r["event_time"]))
        if i is None or i + 1 >= len(bdays):
            continue
        c0, c1 = closes[bdays[i]], closes[bdays[i + 1]]
        if c0 > 0 and c1 > 0:
            out.append((r, c1 / c0 - 1.0))
    return out


def contracts(symbol: str, rows: Sequence[Mapping[str, Any]],
              closes: Mapping[str, float]) -> list[dict[str, Any]]:
    al = align(rows, closes)
    r1 = [r for _, r in al]

    def g(key: str, test: Any) -> list[bool]:
        return [bool(isinstance(s.get(key), float) and test(float(s[key]))) for s, _ in al]

    out = [
        se.gated_gain(r1, g("pcr_oi_z", lambda v: v >= 1.0), engine=ENGINE, cards=["ASIA-0510"],
                      falsifier="long-while-puts-heavy no better than long ungated against the "
                                "block-shuffled gate", baseline=f"{symbol} long, ungated"),
        se.gated_gain([-x for x in r1], g("pcr_oi_z", lambda v: v <= -1.0), engine=ENGINE,
                      cards=["ASIA-0510"], falsifier="short-while-calls-heavy no better than "
                                                     "short ungated",
                      baseline=f"{symbol} short, ungated"),
        se.monotone_gain([s.get("pcr_vol_z") if isinstance(s.get("pcr_vol_z"), float)
                          else math.nan for s, _ in al], [abs(x) for x in r1], engine=ENGINE,
                         cards=["ASIA-0510"], falsifier="hedging-volume surprise does not order "
                                                        "the next day's absolute move"),
    ]
    for c, label in zip(out, ("puts_heavy->long", "calls_heavy->short", "pcr_vol_z~|r_next|"),
                        strict=True):
        c["label"] = label
        c["symbol"] = symbol
    return out


# ============================================================================== the run
def run(*, days: int = 1500, fetch_live: bool = True, dry_run: bool = False,
        now: datetime | None = None, store_path: Path = STORE,
        universe_dir: Path = UNIVERSE_DIR, fetcher: Any = fetch) -> dict[str, Any]:
    when = now or datetime.now(UTC)
    from libs.data.terms_hold import gauntlet_terms
    terms_ok, terms_why = gauntlet_terms(DATA_SOURCE)
    report: dict[str, Any] = {"at": when.isoformat(timespec="seconds"), "engine": ENGINE,
                              "cards": ["ASIA-0510"], "data_source": DATA_SOURCE,
                              "terms": {"gauntlet": "admitted" if terms_ok else "HELD",
                                        "why": terms_why}, "authority": "NONE"}
    if fetch_live and not dry_run:
        report["fetch"] = refresh(days, when, store_path, fetcher)
    store = load_store(store_path)
    rows = [r for r in build_rows(store)
            if datetime.fromisoformat(str(r["available_time"])) <= when]
    report["rows"] = len(rows)
    report["last"] = rows[-1] if rows else None
    if not rows:
        report["status"] = UNMEASURED
        report["why"] = "no TAIFEX put/call history in the store on this host"
        if not dry_run:
            se.publish(ENGINE, [], extra={"status": UNMEASURED, "why": report["why"]})
        return report
    all_contracts: list[dict[str, Any]] = []
    targets: dict[str, Any] = {}
    tradeable: list[str] = []
    for sym in TARGETS:
        closes = daily_closes(sym, universe_dir)
        if not closes:
            targets[sym] = {"status": UNMEASURED, "why": f"no {sym}_H1.parquet bars here"}
            continue
        cs = contracts(sym, rows, closes)
        all_contracts.extend(cs)
        tradeable.append(sym)
        targets[sym] = {"status": "MEASURED", "broker_days": len(closes),
                        "verdicts": {c["label"]: c["verdict"] for c in cs}}
    report.update({"status": "MEASURED", "targets": targets, "contracts": all_contracts})
    if not dry_run:
        report["lake"] = se.write_lake_series(SERIES_ID, [
            {k: v for k, v in r.items() if k != "knowable_basis"} for r in rows])
        report["cells"] = se.emit_conditioner_cells(
            SERIES_ID, [s for s in SIGNALS if any(isinstance(r.get(s), float) for r in rows)],
            tradeable or list(TARGETS),
            mechanism="TAIEX option hedging demand (TXO put/call ratio in volume and open "
                      "interest, z against its trailing year) is the positioning of the market "
                      "closest to the semiconductor cycle; extreme hedging precedes relief in "
                      "TSMC and the chip-linked indices and currencies",
            falsifier="gate effect indistinguishable from the shuffled-state gate across the "
                      "judged cells", generator=ENGINE, sides=(1, -1), data_source=DATA_SOURCE)
        se.publish(ENGINE, all_contracts, extra={"terms": report["terms"]})
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TAIFEX TXO put/call state (ASIA-0510)")
    ap.add_argument("--days", type=int, default=1500)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run(days=a.days, fetch_live=not a.no_fetch, dry_run=a.dry_run)
    if not a.dry_run:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(rep, indent=1, default=str) + "\n", "utf-8")
    print(f"TAIWAN OPTIONS {rep.get('status')} rows={rep.get('rows')} "
          f"terms={rep['terms']['gauntlet']} contracts={len(rep.get('contracts') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

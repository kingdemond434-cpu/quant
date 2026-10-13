"""Fetch CFTC legacy futures-only COT for the full desk universe.

Data: CFTC Socrata "Disaggregated Futures-Only" schema 6dca-aqww (legacy
noncomm/comm series, history to 1986). Weekly, report date = Tuesday,
published Friday ~19:30 UTC. noncomm = large speculators; comm = commercials.

Contracts: gold, silver, FX currencies (each MT5 pair maps to one currency
future), US dollar index, S&P 500, NASDAQ 100 (conditioning-only).

Output: data/cot/{slug}.parquet per contract + data/cot_gold.parquet (legacy).

ON A CLOCK SINCE 2026-10-13 (hourly leg `cot_refresh`, `--if-due`). Until then nothing in the
repository ran this file: the parquets the search, sweep and gauntlet read had stopped at the
2026-08-11 report. `--if-due` fetches only when a newer Friday release should exist (or a
contract file is missing), backs off six hours after a pass that found nothing new, and always
writes `reports/COT_REFRESH.json` with the POSITIONING STATE -- per contract the speculators' net
share of open interest, its trailing three-year rank and z and its weekly change, point in time
by the release lag -- which `research/state_vector_build.py` carries on the state vector the
allocator reads (`StateVector.positioning`, information, never authority).

    python mt5desk/fetch_cot.py              # refetch every contract
    python mt5desk/fetch_cot.py --if-due     # the hourly leg
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

if __package__ in (None, ""):                       # run as a script by the hourly cycle
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
# WRITE WHERE THE READERS LOOK. This wrote to the retired laptop's checkout
# (C:\Users\dell\mt5-research), while `research/edge_search.py` and
# `research/orthogonal_sweep.py` read COT from the desk's own tree. Writer and reader
# never agreed, so the SEARCH and SWEEP legs found no COT and produced nothing -- and
# because the mkdir SUCCEEDS, it failed by filling a directory nobody reads rather than
# by raising. `config.desk_root()` is the single source of truth for every path here.
from mt5desk.config import DATA, REPORTS  # noqa: E402

OUT = DATA / "cot"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = REPORTS / "COT_REFRESH.json"
#: A Tuesday report is public on Friday ~19:30 UTC; four days on (Saturday 00:00 UTC) is the
#: desk's standing "available from" stamp (`owned_data._COT_PUBLICATION_LAG_DAYS = 4`).
PUBLICATION_LAG = timedelta(days=4)
#: After a pass that found no newer report (a holiday-delayed release), wait this long.
RETRY_AFTER = timedelta(hours=6)
#: Trailing prints a rank / z is taken over: three years of weekly reports.
RANK_WINDOW = 156
RANK_MIN = 52
#: The MT5 instruments each contract reads on, with the sign of "speculators longer" for the
#: instrument (a long yen future is a SHORT USDJPY). Every symbol is in the broker registry.
CONTRACT_INSTRUMENTS: dict[str, dict[str, int]] = {
    "gold": {"XAUUSD": 1}, "silver": {"XAGUSD": 1},
    "jpy": {"USDJPY": -1, "EURJPY": -1, "GBPJPY": -1, "AUDJPY": -1},
    "eur": {"EURUSD": 1}, "gbp": {"GBPUSD": 1}, "cad": {"USDCAD": -1}, "aud": {"AUDUSD": 1},
    "nzd": {"NZDUSD": 1}, "chf": {"USDCHF": -1}, "dxy": {"USDX": 1},
    "sp500": {"US500": 1}, "nasdaq100": {"NAS100": 1},
}

SELECT = (
    "report_date_as_yyyy_mm_dd,commodity_name,contract_market_name,open_interest_all,"
    "noncomm_positions_long_all,noncomm_positions_short_all,"
    "comm_positions_long_all,comm_positions_short_all,"
    "change_in_noncomm_long_all,change_in_noncomm_short_all,"
    "change_in_open_interest_all"
)

# commodity_name candidates tried in order (first non-empty wins)
TARGETS: list[tuple[str, list[str]]] = [
    ("gold", ["GOLD"]),
    ("silver", ["SILVER"]),
    ("jpy", ["JAPANESE YEN"]),
    ("eur", ["EURO FX"]),
    ("gbp", ["POUND STERLING"]),
    ("cad", ["CANADIAN DOLLAR"]),
    ("aud", ["AUSTRALIAN DOLLAR"]),
    ("nzd", ["NEW ZEALAND DOLLAR"]),
    ("chf", ["SWISS FRANC"]),
    ("dxy", ["US DOLLAR INDEX", "U.S. DOLLAR INDEX"]),
    ("sp500", ["S&P BROAD BASED STOCK INDICES"]),
    ("nasdaq100", ["NASDAQ  BROADBASED INDICES"]),
]

# MT5 symbol -> cot slug (a pair trades its base-currency future; JPY crosses
# all use the yen contract; conditioning-only symbols DXY/SP500/NDX exposed)
SYMBOL_SLUG = {
    "XAUUSD": "gold", "XAGUSD": "silver",
    "USDJPY": "jpy", "EURJPY": "jpy", "GBPJPY": "jpy", "CADJPY": "jpy",
    "AUDJPY": "jpy", "NZDJPY": "jpy", "CHFJPY": "jpy",
    "EURUSD": "eur", "EURGBP": "eur", "EURCHF": "eur",
    "GBPUSD": "gbp", "USDCAD": "cad", "AUDUSD": "aud", "NZDUSD": "nzd",
    "USDCHF": "chf",
    "DXY": "dxy", "SP500": "sp500", "NDX": "nasdaq100",
}


def fetch_contract(commodity: str) -> pd.DataFrame | None:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "$where": f"commodity_name='{commodity}'",
            "$select": SELECT,
            "$order": "report_date_as_yyyy_mm_dd",
            "$limit": "5000",
            "$offset": str(offset),
        }
        url = f"{BASE}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            batch = json.load(resp)
        rows.extend(batch)
        if len(batch) < 5000:
            break
        offset += 5000
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["report_date_as_yyyy_mm_dd"] = pd.to_datetime(
        df["report_date_as_yyyy_mm_dd"], format="ISO8601", utc=True
    )
    for col in df.columns:
        if col not in ("report_date_as_yyyy_mm_dd", "commodity_name",
                       "contract_market_name"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # prefer the outright contract when multiple markets exist
    best = (df.groupby("contract_market_name").size().idxmax()
            if df["contract_market_name"].nunique() > 1 else df["contract_market_name"].iloc[0])
    df = df[df["contract_market_name"] == best]
    df = df.rename(columns={"report_date_as_yyyy_mm_dd": "report_date"})
    df = df.sort_values("report_date").drop_duplicates("report_date", keep="last")
    return df


def _last_report(slug: str, out: Path = OUT) -> pd.Timestamp | None:
    try:
        d = pd.read_parquet(out / f"{slug}.parquet", columns=["report_date"])
    except Exception:
        return None
    return None if d.empty else pd.Timestamp(d["report_date"].max())


def due(now: datetime, out: Path = OUT, state: dict[str, Any] | None = None
        ) -> tuple[bool, str]:
    """Is a newer release than the files hold already public? The last Tuesday whose Saturday
    availability has passed is the newest report the world can know.

    THE NEWEST FILE DECIDES, NOT THE OLDEST: a contract CFTC stopped reporting under its old
    name (`sp500` ends 2021-09-14) or one that never resolved (`eur`) would otherwise make every
    hour due forever. Those stay named in the report and in the positioning gaps; a pass that
    found nothing newer waits `RETRY_AFTER` whatever the reason."""
    lasts = {slug: _last_report(slug, out) for slug, _ in TARGETS}
    missing = sorted(s for s, t in lasts.items() if t is None)
    held = [t for t in lasts.values() if t is not None]
    knowable = now - PUBLICATION_LAG
    tues = knowable - timedelta(days=(knowable.weekday() - 1) % 7)
    expected = pd.Timestamp(tues.date(), tz="UTC")
    newest = max(held) if held else None
    if newest is not None and newest >= expected:
        return False, (f"files hold the {newest.date()} report, the newest public one"
                       + (f"; never resolved: {', '.join(missing)}" if missing else ""))
    why = (f"files hold {newest.date()}; the {expected.date()} report is public"
           if newest is not None else "no contract file at all")
    tried = (state or {}).get("last_attempt")
    if tried and now - datetime.fromisoformat(tried) < RETRY_AFTER:
        return False, f"{why}, but a pass at {tried} found nothing newer; retry after {RETRY_AFTER}"
    return True, why


def positioning_state(now: datetime | None = None, out: Path = OUT) -> dict[str, Any]:
    """The cross-asset POSITIONING state from the contract files, point in time.

    Per contract, only reports whose availability (report date + `PUBLICATION_LAG`) is at or
    before `now`: speculators' (non-commercial) net as a share of open interest, its percentile
    rank and z over the trailing `RANK_WINDOW` prints, its one-week change, and a crowding label
    at the 10th / 90th percentile. A contract with too short a history is named UNMEASURED,
    never ranked 0.5."""
    now = now or datetime.now(tz=UTC)
    contracts: dict[str, Any] = {}
    gaps: dict[str, str] = {}
    by_instrument: dict[str, list[dict[str, Any]]] = {}
    for slug, inst in CONTRACT_INSTRUMENTS.items():
        try:
            df = pd.read_parquet(out / f"{slug}.parquet")
        except Exception as exc:
            gaps[slug] = f"UNMEASURED: no readable data/cot/{slug}.parquet ({type(exc).__name__})"
            continue
        need = {"report_date", "open_interest_all", "noncomm_positions_long_all",
                "noncomm_positions_short_all"}
        if not need <= set(df.columns):
            gaps[slug] = f"UNMEASURED: {slug}.parquet lacks {sorted(need - set(df.columns))}"
            continue
        df = df.sort_values("report_date")
        avail = pd.to_datetime(df["report_date"], utc=True) + PUBLICATION_LAG
        df = df[avail <= pd.Timestamp(now)]
        oi = pd.to_numeric(df["open_interest_all"], errors="coerce")
        net = (pd.to_numeric(df["noncomm_positions_long_all"], errors="coerce")
               - pd.to_numeric(df["noncomm_positions_short_all"], errors="coerce"))
        pct = (net / oi.where(oi > 0)).dropna()
        if len(pct) < RANK_MIN:
            gaps[slug] = f"UNMEASURED: {len(pct)} public reports < {RANK_MIN}"
            continue
        win = pct.iloc[-RANK_WINDOW:]
        last = float(win.iloc[-1])
        rank = float((win <= last).mean())
        sd = float(win.std(ddof=0))
        rd = pd.Timestamp(df.loc[pct.index[-1], "report_date"])
        age_d = (pd.Timestamp(now) - (rd + PUBLICATION_LAG)).total_seconds() / 86400
        row = {"report_date": rd.date().isoformat(),
               "available_at": (rd + PUBLICATION_LAG).isoformat(),
               "age_days": round(age_d, 2), "stale": age_d > 14,
               "spec_net_pct_oi": round(last, 6), "rank_3y": round(rank, 4),
               "z_3y": round((last - float(win.mean())) / sd, 4) if sd > 0 else None,
               "chg_1w": round(last - float(pct.iloc[-2]), 6) if len(pct) > 1 else None,
               "crowding": ("long_extreme" if rank >= 0.9 else
                            "short_extreme" if rank <= 0.1 else "mid"),
               "n": len(win), "instruments": inst}
        contracts[slug] = row
        for sym, sign in inst.items():
            by_instrument.setdefault(sym, []).append({
                "contract": slug, "sign": sign, "rank_3y": row["rank_3y"],
                "signed_rank": round(0.5 + sign * (rank - 0.5), 4),
                "crowding": row["crowding"], "stale": row["stale"]})
    return {"as_of": now.isoformat(timespec="seconds"),
            "status": "MEASURED" if contracts else "UNMEASURED",
            "contracts": contracts, "instruments": by_instrument, "gaps": gaps,
            "source": "CFTC legacy futures-only COT (publicreporting.cftc.gov 6dca-aqww)",
            "rule": ("point in time by a four-day release lag; speculators' net share of open "
                     "interest ranked over the trailing three years. INFORMATION, NOT "
                     "AUTHORITY: carried on the state vector, it sizes nothing")}


def _read_json(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def refresh(*, if_due: bool, now: datetime | None = None) -> dict[str, Any]:
    """The hourly leg: fetch when due, then always publish the positioning state."""
    now = now or datetime.now(tz=UTC)
    # The backoff stamp lives in this host's own (gitignored) report, never in data/cot: the
    # contract files are shared state, a per-host attempt time is not.
    state = {"last_attempt": _read_json(REPORT).get("last_attempt")}
    go, why = due(now, OUT, state) if if_due else (True, "forced (no --if-due)")
    fetched: dict[str, Any] = {}
    if go:
        fetched = main()
        state["last_attempt"] = now.isoformat(timespec="seconds")
    pos = positioning_state(now)
    report = {"generated_utc": now.isoformat(timespec="seconds"), "writer": "mt5desk/fetch_cot.py",
              "due": go, "why": why, "fetched": fetched,
              "last_attempt": state.get("last_attempt"),
              "last_report": {slug: (str(t.date()) if (t := _last_report(slug)) is not None
                                     else "UNMEASURED") for slug, _ in TARGETS},
              "positioning": pos,
              "consumer": "research/state_vector_build.py -> StateVector.positioning"}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    return report


def main() -> dict[str, Any]:
    done: dict[str, Any] = {}
    for slug, candidates in TARGETS:
        df = None
        err = ""
        for cand in candidates:
            try:
                df = fetch_contract(cand)
            except Exception as exc:     # one unreachable contract never costs the others
                err = f"{type(exc).__name__}: {str(exc)[:120]}"
                df = None
            if df is not None:
                break
        if df is None or df.empty:
            print(f"{slug:>10}: FAILED ({err or f'no rows for {candidates}'})")
            done[slug] = f"FAILED: {err or 'no rows'}"
            continue
        df.to_parquet(OUT / f"{slug}.parquet", index=False)
        done[slug] = {"rows": len(df), "last": str(df["report_date"].max().date())}
        print(f"{slug:>10}: {len(df)} rows  "
              f"{df['report_date'].min().date()} -> {df['report_date'].max().date()}"
              f"  market={df['contract_market_name'].iloc[0]}")
    # legacy gold alias
    g = OUT / "gold.parquet"
    if g.exists():
        import shutil
        shutil.copy(g, DATA / "cot_gold.parquet")
        print("legacy cot_gold.parquet refreshed")
    return done


def _cli() -> int:
    ap = argparse.ArgumentParser(description="CFTC COT fetch + positioning state")
    ap.add_argument("--if-due", action="store_true",
                    help="fetch only when a newer release is public (the hourly leg)")
    a = ap.parse_args()
    rep = refresh(if_due=a.if_due)
    pos = rep["positioning"]
    print(f"cot_refresh: due={rep['due']} ({rep['why']}); positioning {pos['status']} on "
          f"{len(pos['contracts'])} contract(s); gaps {sorted(pos['gaps'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())

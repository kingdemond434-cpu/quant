"""ALFRED VINTAGES ON A CLOCK -- point-in-time US macro, refreshed, laid into the lake, judged.

WHY THIS EXISTS. `research/fetch_alfred.py` has been able to pull every vintage of the revised US
releases since 2026-08, and `libs.portfolio.macro_state` prefers its files over the revised FRED
archive whenever they exist. Nothing ran it. The Tier-1 ledger row C2 has said "still open: ALFRED
... ingest on a clock" since 2026-09-16, and on top of that the module looked for its key at
`secrets/fred_api_key`, a path nothing on the box writes, while the box keeps the key at
`data/secrets/fred.json`. So the PIT macro layer the judge's discipline depends on was a module
that would have said UNAVAILABLE beside a key that was there, on a schedule that did not exist.

WHAT ONE PASS DOES

  1. REFRESH. Each series in `fetch_alfred.SERIES` whose vintage file is missing or older than
     `REFRESH_H` is re-pulled (every vintage, one request), checked by fetch_alfred's own
     single-vintage and release-lag refusals, and written to `data/lake/alfred/<SID>.parquet` --
     the file `macro_state.alfred_rows` already reads. Through the robots gate, honest UA.
  2. LAY INTO THE LAKE. Each series becomes `data/lake/series/alfred_<sid>.parquet`: ONE ROW PER
     VINTAGE DATE, i.e. per moment the desk learned something, with
         available_time   the vintage date + 1 day, 00:00 UTC. ALFRED dates a vintage, it does
                          not time it; a US release at 08:30 ET is known by the end of its day,
                          so the stamp is the END of the realtime date -- never the start
         yoy_pit          the newest observation's year-on-year change AS THAT VINTAGE PRINTED
                          IT (both ends read from the same vintage, so no later revision leaks)
         revision_pct     how much this vintage moved the previous vintage's last three
                          observations, relative -- the revision surprise itself
  3. MINT. `exogenous_conditioner` cells on those two columns against the hypothesis-lane
     instruments US macro moves (US500, USDJPY, EURUSD, XAUUSD, UST10Y), at one transform and
     threshold and both sides, donated to `data/intelligence/alfred_vintages/`. A cell is minted
     ONCE: identities already donated are remembered, so the hourly clock never re-charges the
     shared trial budget for the same rule.

IT FAILS CLOSED AND SAYS SO. No key: status UNMEASURED with the reason, nothing written to the
lake, nothing minted -- the revised series is never relabelled point-in-time. A series that
fails its fetch keeps its previous file and is named in `failed`.

    python desks/mt5/research/alfred_vintages.py --once [--budget-s 600] [--no-fetch]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "alfred_vintages"
VINTAGES = DESK / "data" / "lake" / "alfred"
SERIES_DIR = DESK / "data" / "lake" / "series"
STATE = DESK / "data" / "alfred_vintages" / "minted.json"
REPORT = DESK / "reports" / "ALFRED_VINTAGES.json"

#: A release prints at most daily; a day keeps every new vintage within a day of publication
#: without re-pulling a whole revision history every hour.
REFRESH_H = 24.0
#: The two PIT columns each series is laid out with.
SIGNALS: tuple[str, ...] = ("yoy_pit", "revision_pct")
#: Hypothesis-lane instruments US macro releases move. Bonds, FX, gold and the index.
SYMBOLS: tuple[str, ...] = ("US500", "USDJPY", "EURUSD", "XAUUSD", "UST10Y")
#: One shape per cell family -- the grid is small on purpose: trial count is a shared cost.
GRID = {"transform": ("level_z",), "threshold": (1.5,), "side_when_high": (1, -1)}
CHART = "H4"
#: Rows a lake file needs before cells are minted on it (the family's own MIN_OBSERVATIONS).
MIN_ROWS = 30
#: Observations whose revision is measured, newest first, excluding none.
REVISION_DEPTH = 3


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), "utf-8")


def _age_h(p: Path, now: datetime) -> float | None:
    try:
        return (now.timestamp() - p.stat().st_mtime) / 3600.0
    except OSError:
        return None


# ------------------------------------------------------------------------------ 1. refresh

def refresh(series: list[str], key: str, *, budget_s: float, now: datetime,
            fetch: Any = None, gate: Any = None, out_dir: Path = VINTAGES) -> dict[str, Any]:
    """Re-pull the series whose vintage file is missing or older than REFRESH_H."""
    import fetch_alfred as fa
    fetch = fetch or fa.fetch_vintages
    t0 = time.monotonic()
    done: list[str] = []
    fresh: list[str] = []
    failed: dict[str, str] = {}
    deferred: list[str] = []
    for sid in series:
        path = out_dir / f"{sid}.parquet"
        age = _age_h(path, now)
        if age is not None and age < REFRESH_H:
            fresh.append(sid)
            continue
        if time.monotonic() - t0 > budget_s:
            deferred.append(sid)
            continue
        try:
            df = fetch(sid, key, gate=gate)
        except Exception as exc:
            failed[sid] = f"{type(exc).__name__}: {str(exc)[:120]}"
            continue
        if df is None or df.empty:
            failed[sid] = "no vintages returned (HTTP failure, robots refusal or empty body)"
            continue
        n_vint = int(df["realtime_date"].nunique())
        if n_vint < 2:
            failed[sid] = f"only {n_vint} vintage: the revised series, refused as PIT"
            continue
        lag = fa.release_lag(df)
        med = lag.get("median_days") if lag else None
        if med is not None and med == med and med > 400:
            failed[sid] = f"median release lag {med:.0f}d is not a publication delay"
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)
        done.append(sid)
    return {"refreshed": done, "fresh": fresh, "failed": failed, "deferred_by_budget": deferred}


# ----------------------------------------------------------------------- 2. lay into the lake

def pit_frame(df: pd.DataFrame) -> pd.DataFrame:
    """One row per vintage date: what that vintage said, never what a later one said."""
    cols = ["available_time", "realtime_date", "observation_date", "value", *SIGNALS]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    wide = (df.pivot_table(index="observation_date", columns="realtime_date", values="value",
                           aggfunc="last")
              .sort_index().sort_index(axis=1))
    # A vintage reports the series as published on that date; a value not repeated in it is the
    # one an earlier vintage published. Forward along the VINTAGE axis only -- an observation not
    # yet published stays empty, because nothing earlier ever held it.
    wide = wide.ffill(axis=1)
    rows: list[dict[str, Any]] = []
    prev: pd.Series | None = None
    for v in wide.columns:
        known = wide[v].dropna()
        if known.empty:
            continue
        last_obs = known.index[-1]
        value = float(known.iloc[-1])
        yoy = float("nan")
        target = last_obs - pd.DateOffset(years=1)
        before = known.loc[:target]
        if not before.empty and abs((before.index[-1] - target).days) <= 10:
            base = float(before.iloc[-1])
            if base > 0:
                yoy = value / base - 1.0
        rev = float("nan")
        if prev is not None:
            common = known.index.intersection(prev.index)
            common = common[common < last_obs][-REVISION_DEPTH:]
            if len(common):
                old = prev.loc[common]
                nz = old.abs() > 0
                if nz.any():
                    rev = float(((known.loc[common][nz] - old[nz]) / old[nz].abs()).mean())
        rows.append({"available_time": pd.Timestamp(v).tz_localize(UTC) + pd.Timedelta(days=1),
                     "realtime_date": pd.Timestamp(v), "observation_date": last_obs,
                     "value": value, "yoy_pit": yoy, "revision_pct": rev})
        prev = known
    return pd.DataFrame(rows, columns=cols)


def lay_into_lake(series: list[str], *, vint_dir: Path = VINTAGES,
                  series_dir: Path = SERIES_DIR) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sid in series:
        src = vint_dir / f"{sid}.parquet"
        if not src.exists():
            out[sid] = {"status": "UNMEASURED", "why": "no vintage file on this host"}
            continue
        try:
            frame = pit_frame(pd.read_parquet(src))
        except Exception as exc:
            out[sid] = {"status": "ERROR", "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
            continue
        series_dir.mkdir(parents=True, exist_ok=True)
        dst = series_dir / f"alfred_{sid.lower()}.parquet"
        tmp = dst.with_suffix(".parquet.tmp")
        frame.to_parquet(tmp, index=False)
        os.replace(tmp, dst)
        out[sid] = {"status": "OK", "rows": len(frame),
                    "non_null": {s: int(frame[s].notna().sum()) for s in SIGNALS},
                    "last_vintage": (str(frame["realtime_date"].iloc[-1].date())
                                     if len(frame) else None),
                    "path": str(dst.relative_to(DESK)) if dst.is_relative_to(DESK) else str(dst)}
    return out


# ------------------------------------------------------------------------------------ 3. mint

def grid(lake: dict[str, Any]) -> list[dict[str, Any]]:
    """Every cell the laid-out series support, in a stable order."""
    import fetch_alfred as fa
    from proposer_common import candidate
    out: list[dict[str, Any]] = []
    for sid in sorted(lake):
        info = lake[sid]
        if info.get("status") != "OK":
            continue
        for sig in SIGNALS:
            if int((info.get("non_null") or {}).get(sig) or 0) < MIN_ROWS:
                continue
            for sym, (t, thr, side) in product(SYMBOLS, product(*GRID.values())):
                src = f"alfred_{sid.lower()}"
                params = {"source": src, "signal": sig, "transform": t, "threshold": thr,
                          "side_when_high": side, "lag_hours": 24, "timeframe": CHART}
                mech = (f"{fa.SERIES.get(sid, sid)}: the {sig} as the release PRINTED it on "
                        f"each vintage date (ALFRED, point-in-time) conditions {sym}")
                c = candidate(SEAT, sym, "exogenous_conditioner", params, mech,
                              f"exogenous_conditioner on {src}.{sig} -> {sym} {CHART}",
                              {"source_row": f"alfred:{sid}", "column": sig,
                               "arm": "direct:level"})
                c["chart"] = CHART
                c["required_data"] = [f"desks/mt5/data/lake/series/{src}.parquet"]
                c["falsifier"] = (f"{src}.{sig} at |z|>={thr} has no measurable relation to "
                                  f"{sym} at {CHART} out of sample")
                out.append(c)
    return out


def mint(cells: list[dict[str, Any]], *, dry_run: bool, state_path: Path = STATE
         ) -> dict[str, Any]:
    """Donate only identities never donated before; remember what was donated."""
    from proposer_common import identity
    state = _read(state_path, {}) or {}
    seen = set(state.get("identities") or [])
    new = [c for c in cells
           if identity(c["symbol"], c["family"], c["params"]) not in seen]
    rep: dict[str, Any] = {"grid": len(cells), "already_minted": len(cells) - len(new),
                           "new": len(new), "minted": 0, "contract": None}
    if not new or dry_run:
        return rep
    from proposer_common import donate, donation_counts
    path = donate(source=SEAT, candidates=new, tests_run=len(new))
    counts = donation_counts()
    rep.update({"minted": int(counts.get("donated") or 0),
                "refused_wrong_lane": int(counts.get("refused_wrong_lane") or 0),
                "refused_unstamped": int(counts.get("refused_unstamped") or 0),
                "contract": str(path) if path else None, "trials_charged": len(new) if path else 0})
    # Remembered once the door has answered -- donated or refused, the same rule is not re-sent.
    seen.update(identity(c["symbol"], c["family"], c["params"]) for c in new)
    _write_json(state_path, {"identities": sorted(seen), "updated": _now().isoformat()})
    return rep


# ------------------------------------------------------------------------------------ main

def run(*, budget_s: float = 600.0, fetch_live: bool = True, dry_run: bool = False,
        now: datetime | None = None, key: str | None = None) -> dict[str, Any]:
    import fetch_alfred as fa
    now = now or _now()
    series = sorted(fa.SERIES)
    doc: dict[str, Any] = {"generated_utc": now.isoformat(timespec="seconds"),
                           "writer": "research/alfred_vintages.py", "seat": SEAT,
                           "series": series}
    key = key if key is not None else fa.api_key()
    if fetch_live and not key:
        doc["fetch"] = {"status": "UNMEASURED",
                        "why": ("no FRED/ALFRED key (data/secrets/fred.json or FRED_API_KEY): "
                                "vintages cannot be refreshed; the revised series is never "
                                "relabelled point-in-time")}
    elif fetch_live:
        from libs.data.robots_gate import RobotsGate
        gate = RobotsGate("alfred_vintages")
        doc["fetch"] = {"status": "RAN", **refresh(series, str(key), budget_s=budget_s, now=now,
                                                   gate=gate),
                        "robots": gate.consulted}
    else:
        doc["fetch"] = {"status": "SKIPPED", "why": "--no-fetch"}
    lake = lay_into_lake(series)
    doc["lake"] = lake
    cells = grid(lake)
    doc["mint"] = mint(cells, dry_run=dry_run)
    ok = sum(1 for v in lake.values() if v.get("status") == "OK")
    doc["series_in_lake"] = ok
    doc["status"] = "OK" if ok else "UNMEASURED"
    if not ok:
        doc["why"] = ("no ALFRED vintage file on this host yet; "
                      + str((doc["fetch"] or {}).get("why") or "see fetch.failed"))
    _write_json(REPORT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, fetch_live=not a.no_fetch, dry_run=a.dry_run)
    f = doc.get("fetch") or {}
    print(f"alfred_vintages: {doc['status']}; fetch {f.get('status')} "
          f"refreshed={len(f.get('refreshed') or [])} failed={len(f.get('failed') or {})}; "
          f"lake {doc['series_in_lake']}/{len(doc['series'])}; "
          f"minted {doc['mint'].get('minted')} of {doc['mint'].get('new')} new")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

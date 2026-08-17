"""OPTIONS DESK (meta item 4: options-implied, unblocked with FREE Deribit data).

Perpetual supervised desk. Every cycle (hourly):
  1. Deribit public book summary (all BTC/ETH option contracts, mark_iv; no key)
  2. surface: ATM IV (nearest strike to index), skew proxy (call-IV - put-IV
     band), term slope (shortest vs longest expiry ATM IV), DVOL index
  3. realized vol from our own BTCUSD/ETHUSD H1 parquets => IV-RV ratio
  4. append to the proprietary options archive (data/options_archive.parquet)
     -- this is the proprietary dataset being built from NOW (no paid history)
  5. data/options_state.json + data/options_candidates.json (forward shadow
     candidates: IV-RV z, skew z, term z, expected move). Candidates enter the
     forward clock once enough archive history exists for z-scoring.

Honest boundary (docs/NEWS_LINEAGE-style): options candidates have NO
historical backtest (we started collecting today); they are forward-shadow
only until the archive has enough vintages.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import free_data as fd
from run_hunt17 import resample

BASE = Path(__file__).resolve().parent.parent
ARCHIVE = BASE / "data" / "options_archive.parquet"
STATE_F = BASE / "data" / "options_state.json"
CAND_F = BASE / "data" / "options_candidates.json"
LOG = BASE / "logs" / "options_desk.log"
UNIVERSE = BASE / "data" / "universe"

CURRENCIES = {"BTC": "BTCUSD", "ETH": "ETHUSD"}


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _rv_1w(sym: str) -> float | None:
    p = UNIVERSE / f"{sym}_H1.parquet"
    if not p.exists():
        return None
    try:
        h1 = pd.read_parquet(p)
        r = np.log(h1["close"].to_numpy(float))
        r = np.diff(r)
        return float(np.std(r[-168:]) * np.sqrt(24 * 7))
    except Exception:
        return None


def surface(currency: str) -> dict | None:
    book = fd.deribit_book_summary(currency)
    idx = fd.deribit_index(currency)
    if not book or idx is None:
        return None
    rows = []
    for b in book:
        iv = b.get("mark_iv")
        name = b.get("instrument_name", "")
        parts = name.split("-")
        if len(parts) != 4:
            continue
        exp, strike, is_call = parts[1], float(parts[2]), parts[3].startswith("C")
        if iv is None or iv <= 0:
            continue
        rows.append((exp, strike, float(iv), is_call))
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["exp", "strike", "iv", "is_call"])
    df = df[df["iv"] > 0]
    if df.empty:
        return None
    atm = df.iloc[(df["strike"] - idx).abs().argsort()].iloc[0]
    calls = df[df["is_call"] & (df["strike"] > idx * 1.05)]
    puts = df[~df["is_call"] & (df["strike"] < idx * 0.95)]
    skew = None
    if not calls.empty and not puts.empty:
        skew = float(calls["iv"].mean() - puts["iv"].mean())
    exps = sorted(set(df["exp"]))
    term = None
    if len(exps) >= 2:
        def atm_iv(e):
            sub = df[df["exp"] == e]
            return float(sub.iloc[(sub["strike"] - idx).abs().argsort()].iloc[0]["iv"])
        term = atm_iv(exps[0]) - atm_iv(exps[-1])
    dvol = fd.deribit_vol_index(currency)
    return {"ts": fd.now_iso(), "currency": currency, "index": idx,
            "atm_iv": float(atm["iv"]), "skew": skew, "term_slope": term,
            "dvol": dvol, "n_contracts": len(df)}


def cycle() -> None:
    rows = []
    for cur, sym in CURRENCIES.items():
        try:
            s = surface(cur)
            if not s:
                log(f"{cur}: no surface")
                continue
            rv = _rv_1w(sym)
            if rv and rv > 0:
                s["rv_1w"] = rv
                s["iv_rv"] = s["atm_iv"] / rv if rv else None
            s["expected_move_1w"] = (s["atm_iv"] * s["index"] / np.sqrt(52)
                                     if s["atm_iv"] else None)
            rows.append(s)
        except Exception as e:
            log(f"{cur} error: {e!r}")

    if not rows:
        return
    df = pd.DataFrame(rows)
    old = None
    if ARCHIVE.exists():
        try:
            old = pd.read_parquet(ARCHIVE)
        except Exception:
            old = None
    df = pd.concat([old, df], ignore_index=True) if old is not None else df
    df = df.drop_duplicates(subset=["ts", "currency"], keep="last")
    df.to_parquet(ARCHIVE)
    STATE_F.write_text(json.dumps({"updated": fd.now_iso(),
                                   "archive_rows": int(len(df)),
                                   "latest": rows}), "utf-8")

    # candidates: z-scores once archive is deep enough (>=120 hourly vintages)
    cands = []
    if old is not None and len(old) >= 120:
        for cur in CURRENCIES:
            sub = old[old["currency"] == cur]
            if len(sub) < 120:
                continue
            cur_row = df[df["currency"] == cur].iloc[-1]
            for f in ["atm_iv", "iv_rv", "skew", "term_slope"]:
                if f in cur_row and sub[f].notna().sum() >= 60:
                    z = (cur_row[f] - sub[f].mean()) / (sub[f].std() + 1e-12)
                    if abs(z) > 1.5:
                        cands.append({"currency": cur, "field": f, "z": round(float(z), 2),
                                      "ts": fd.now_iso(),
                                      "hypothesis": f"{cur} {f} at z={z:.2f}: "
                                                    f"{'rich -> fade' if z > 0 else 'cheap -> buy'}"})
    CAND_F.write_text(json.dumps({"updated": fd.now_iso(), "candidates": cands,
                                  "note": "forward-shadow only; archive age "
                                          f"{len(old) if old is not None else 0} vintages"},
                                 indent=1), "utf-8")
    log(f"options archive now {len(df)} rows; candidates {len(cands)}")


def main() -> None:
    log("options desk started (Deribit public, no key)")
    while True:
        t0 = time.time()
        try:
            cycle()
        except Exception as e:
            log(f"cycle error: {e!r}")
        time.sleep(max(60, 3600 - (time.time() - t0)))


if __name__ == "__main__":
    main()
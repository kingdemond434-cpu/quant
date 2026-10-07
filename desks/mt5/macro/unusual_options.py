"""OMST -- unusual-options ranking on the option-chain archive (state only while its source is
HELD).

WHY (DATA-22, the OMST row). `macro/option_chains.py` keeps, per ETF snapshot, the front two
expiries' strikes within +-10% of spot with their open interest, volume and quotes
(`front_strikes` in data/option_chains/<ETF>/<stamp>.json.gz). Nothing ranked them. The
terminal's "most unusual options" screen asks three questions of each contract, and each is
computed here from that archive alone:

    vol_oi         today's volume over open interest: > 1 means more contracts traded than
                   were open, i.e. new positioning rather than churn
    oi_change_z    open interest now minus the same contract's in the PREVIOUS snapshot,
                   as a robust z (median / 1.4826 MAD) across the snapshot's contracts
    premium        volume x mid x 100: the dollars that traded

The score is the mean of the three cross-sectional percentile ranks (a contract with no prior
snapshot ranks on the other two). A contract is UNUSUAL when vol_oi >= UNUSUAL_VOL_OI and its
volume >= MIN_VOLUME. Per ETF the state is the count of unusual contracts, the call share of
unusual premium and the top TOP_N contracts.

TERMS. The archive is CBOE delayed quotes (`option_chains.DATA_SOURCE`), HELD by the terms gate
until a quoted clearance is recorded. The state is computed and reported anyway (a held source is
measured and kept); the cell door is asked and says HELD, so no cell is emitted, and the report
says so. Measure "Q" positioning only; options never trade here.
"""
from __future__ import annotations

import gzip
import json
import statistics
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

UNMEASURED = "UNMEASURED"
ENGINE = "unusual_options"
UNUSUAL_VOL_OI = 1.0
MIN_VOLUME = 100.0
TOP_N = 10
SIGNALS = ("unusual_count", "unusual_call_premium_share")


def _key(c: Mapping[str, Any]) -> str:
    return f"{c.get('expiry')}|{c.get('cp')}|{float(c.get('strike') or 0):.4f}"


def snapshots(data_dir: Path, etf: str) -> list[dict[str, Any]]:
    """Every archived snapshot of `etf`, oldest first; unreadable files are skipped."""
    d = data_dir / etf
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.json.gz")):
        try:
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError, EOFError):
            continue
        if isinstance(doc, dict) and isinstance(doc.get("front_strikes"), list):
            out.append(doc)
    out.sort(key=lambda s: str(s.get("knowable_at") or s.get("quote_time") or ""))
    return out


def _rank(vals: Sequence[float | None]) -> list[float | None]:
    present = sorted(v for v in vals if v is not None)
    n = len(present)
    if n == 0:
        return [None] * len(vals)
    out: list[float | None] = []
    for v in vals:
        if v is None:
            out.append(None)
            continue
        below = sum(1 for x in present if x < v)
        eq = sum(1 for x in present if x == v)
        out.append((below + 0.5 * eq) / n)
    return out


def rank(snap: Mapping[str, Any], prev: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Every front contract of one snapshot with its three measures and score, best first."""
    old = {_key(c): float(c.get("oi") or 0.0) for c in (prev or {}).get("front_strikes") or []}
    rows = []
    for c in snap.get("front_strikes") or []:
        oi, vol = float(c.get("oi") or 0.0), float(c.get("volume") or 0.0)
        bid, ask = c.get("bid"), c.get("ask")
        mid = (0.5 * (float(bid) + float(ask)) if isinstance(bid, int | float)
               and isinstance(ask, int | float) and 0 <= bid <= ask else None)
        k = _key(c)
        rows.append({"contract": k, "expiry": c.get("expiry"), "cp": c.get("cp"),
                     "strike": c.get("strike"), "oi": oi, "volume": vol,
                     "vol_oi": vol / oi if oi > 0 else (None if vol == 0 else float("inf")),
                     "oi_change": oi - old[k] if k in old else None,
                     "premium": vol * mid * 100.0 if mid is not None else None})
    chg = [r["oi_change"] for r in rows if r["oi_change"] is not None]
    if len(chg) >= 5:
        med = statistics.median(chg)
        mad = statistics.median(abs(x - med) for x in chg) * 1.4826
        for r in rows:
            r["oi_change_z"] = (round((r["oi_change"] - med) / mad, 4)
                                if r["oi_change"] is not None and mad > 0 else None)
    else:
        for r in rows:
            r["oi_change_z"] = None
    finite_voi = [None if r["vol_oi"] is None else min(r["vol_oi"], 1e9) for r in rows]
    ranks = [_rank(finite_voi), _rank([r["oi_change_z"] for r in rows]),
             _rank([r["premium"] for r in rows])]
    for i, r in enumerate(rows):
        parts = [float(v) for rk in ranks if (v := rk[i]) is not None]
        r["score"] = round(sum(parts) / len(parts), 4) if parts else None
        r["unusual"] = bool(r["vol_oi"] is not None and r["vol_oi"] >= UNUSUAL_VOL_OI
                            and r["volume"] >= MIN_VOLUME)
        if r["vol_oi"] == float("inf"):
            r["vol_oi"] = None
            r["vol_oi_note"] = "volume on zero prior open interest"
    rows.sort(key=lambda r: -(r["score"] if r["score"] is not None else -1.0))
    return rows


def summary(snap: Mapping[str, Any], prev: Mapping[str, Any] | None) -> dict[str, Any]:
    rows = rank(snap, prev)
    unusual = [r for r in rows if r["unusual"]]
    prem = [r for r in unusual if r["premium"] is not None]
    tot = sum(r["premium"] for r in prem)
    calls = sum(r["premium"] for r in prem if r["cp"] == "C")
    return {"status": "MEASURED" if rows else UNMEASURED,
            "available_time": snap.get("knowable_at"), "event_time": snap.get("quote_time"),
            "contracts": len(rows), "has_prior": prev is not None,
            "unusual_count": len(unusual),
            "unusual_premium": round(tot, 2),
            "unusual_call_premium_share": round(calls / tot, 4) if tot > 0 else None,
            "top": rows[:TOP_N]}


def build(data_dir: Path, etfs: Mapping[str, str | None], *, terms: Mapping[str, Any],
          series_root: Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Ranking per ETF from the archive; lake rows written; the cell door asked (HELD today)."""
    from libs.research import sensor_engines as se
    out: dict[str, Any] = {"engine": ENGINE, "terms": dict(terms), "symbols": {},
                           "thresholds": {"vol_oi": UNUSUAL_VOL_OI, "min_volume": MIN_VOLUME}}
    for etf, sym in etfs.items():
        snaps = snapshots(data_dir, etf)
        if not snaps:
            out["symbols"][etf] = {"status": UNMEASURED,
                                   "why": "no archived snapshot with front strikes on this host"}
            continue
        hist = [summary(s, snaps[i - 1] if i else None) for i, s in enumerate(snaps)]
        latest = hist[-1]
        entry: dict[str, Any] = {**latest, "snapshots": len(snaps)}
        sid = f"ws_omst_{etf.lower()}"
        lake = [{"available_time": h["available_time"], "event_time": h["event_time"],
                 "unusual_count": h["unusual_count"],
                 "unusual_call_premium_share": h["unusual_call_premium_share"]}
                for h in hist if h["status"] == "MEASURED" and h["available_time"]]
        if not dry_run and lake:
            entry["lake"] = se.write_lake_series(sid, lake, root=series_root)
        if terms.get("status") == "CLEARED" and sym:
            entry["cells"] = se.emit_conditioner_cells(
                sid, list(SIGNALS), [sym], mechanism=(
                    f"{etf} unusual options flow (volume over open interest, OI change, "
                    f"premium) as positioning state of {sym}"),
                falsifier="gate effect indistinguishable from the shuffled-state gate",
                generator=ENGINE, sides=(1, -1), dry_run=dry_run,
                data_source=str(terms.get("data_source")))
        else:
            entry["cells"] = {"series_id": sid, "emitted": 0, "status": "HELD_TERMS",
                              "data_source": terms.get("data_source"),
                              "why": (terms.get("why") or "source held by the terms gate")
                              if terms.get("status") != "CLEARED"
                              else "no MT5 instrument mapped for this ETF"}
        out["symbols"][etf] = entry
    ok = [v for v in out["symbols"].values() if v.get("status") == "MEASURED"]
    out["status"] = "MEASURED" if ok else UNMEASURED
    if not ok:
        out["why"] = "no ETF has an archived chain snapshot with front strikes on this host"
    out["cells_emitted"] = sum(int((v.get("cells") or {}).get("emitted") or 0)
                               for v in out["symbols"].values())
    return out

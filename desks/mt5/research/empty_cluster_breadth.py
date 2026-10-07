#!/usr/bin/env python3
"""MINT CELLS INTO THE SIX EMPTY ALPHA CLUSTERS, EVERY HOUR, AND SAY WHERE EACH ONE LANDED.

    python desks/mt5/research/empty_cluster_breadth.py --once --budget-s 900
    python desks/mt5/research/empty_cluster_breadth.py --once --dry-run      # measure only

THE ORDER (principal, 2026-09-30): fill cross_asset_lead_lag, event_surprise, execution_entry,
news_reaction, options_implied and positioning_flow. k_eff read 2.53 on 453 nominal sleeves.

WHY THEY WERE EMPTY, MEASURED (LIVE's committed docket `external_survivors.json`, 2026-09-24,
classified by `libs.research.alpha_clusters.classify_family`):

    cluster                cells   gauntlet-seen   with a measured n   cause
    cross_asset_lead_lag    1062             611                   0   build_cell has no lead_lag
                                                                      branch: driver=None -> []
    event_surprise            97             210                   0   the branch passes a bare
                                                                      DatetimeIndex -> []
    positioning_flow          18              64                   3   the cot_* families take a
                                                                      positional frame nobody
                                                                      passes; unclassified too
    execution_entry            0               0                   0   no family classified here
    news_reaction              0               0                   0   no family classified here
    options_implied            0               0                   0   no family classified here

So none of the six was "attacked and nothing survived" in the sense the gates would mean: the
SEALED judge never saw a signal from any of them. The remedy that does not touch the sealed file
is `mt5desk/families_empty_clusters.py` -- fourteen families that load their own input from
what the cell names (implied_vol_term_inversion was dropped 2026-10-07 for PR #234's
implied_vol_state) -- and this organ, which mints them.

WHAT A PASS DOES, in order:
  0. Refreshes the free observables (`scripts/fetch_free_observables.py`: CBOE implied indices,
     the Fed calendar, live COT) when they are older than FETCH_MAX_AGE_H. Unscheduled until now.
  1. Reads `reports/EMPTY_CLUSTER_FORCER.json` -- the forcer's per-cluster verdict (UNREACHABLE,
     BLOCKED_BY_SEALED_GAUNTLET, ...) -- and carries it beside this organ's own count, so that
     artifact has a reader and the two can be compared cluster by cluster.
  2. For every family x declared instrument (the maps in the family module: implied index, COT
     contract, Fed-calendar instruments, driver pairs, entry bases) x `PARAM_GRID` cell, runs the
     family on the instrument's own bars and counts its firing (`cross_sectional_breadth.firing`:
     a lower bound on trade days). A cell under SEED_FLOOR is HELD BACK and counted -- the sealed
     gauntlet drops a daily series under 60 days and a held-back cell never becomes UNKNOWN.
  3. CHARGES EVERY MEASURED CELL to the trial census, clearing the floor or not, in
     `data/EMPTY_CLUSTER_TRIALS.jsonl` (hypothesis-graph node ids, so `experiment_ledger` counts
     each once and skips one the graph already holds as judged).
  4. Donates the cells that clear the floor through `proposer_common.donate` -- the two-lane
     filter, the point-in-time stamp, preregistration and the registry -- into
     `data/intelligence/empty_cluster_breadth/`, which `miner_candidate_compiler` compiles into
     the docket. Every row carries `alpha_cluster` and the four `libs/research/cell_culture` fields.
  5. Appends one row per cluster to `data/empty_cluster_mint_ledger.jsonl` and writes
     `reports/EMPTY_CLUSTER_BREADTH.json`: per cluster, cells minted this pass and in 24h, held
     back, the missing artifact where nothing can fire, the gauntlet's verdicts on these families
     and the fence verdict `scripts/check_empty_cluster_minting.py` reads.

ADDITIVE ONLY. No other miner is capped, reordered or slowed. A cell is measured at most once a
day (the state file carries the day), so a pass that runs out of budget resumes the next hour.

UNMEASURED IS AN ANSWER (L1.28a). An input this box does not hold (an implied index not yet
fetched, no consensus store) is named per cluster; it never reads as zero cells "found nothing".
"""
from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402
from mt5desk import families_empty_clusters as ec  # noqa: E402

SOURCE = "empty_cluster_breadth"
OUT = BASE / "reports" / "EMPTY_CLUSTER_BREADTH.json"
STATE = BASE / "data" / "empty_cluster_breadth_state.json"
MINT_LEDGER = BASE / "data" / "empty_cluster_mint_ledger.jsonl"
TRIALS = BASE / "data" / "EMPTY_CLUSTER_TRIALS.jsonl"
FORCER = BASE / "reports" / "EMPTY_CLUSTER_FORCER.json"
BREADTH = BASE / "reports" / "EFFECTIVE_BREADTH.json"
VERDICTS = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
UNIVERSE_DIR = BASE / "data" / "universe"
FETCHER = ROOT / "scripts" / "fetch_free_observables.py"
UNMEASURED = "UNMEASURED"

#: The six clusters this organ owns, in the principal's order.
CLUSTERS: tuple[str, ...] = ("cross_asset_lead_lag", "event_surprise", "execution_entry",
                             "news_reaction", "options_implied", "positioning_flow")

#: The sealed gauntlet drops a daily series under 60 days; a cell must clear 10% more here.
FIRE_FLOOR = 60
SEED_FLOOR = 66
FETCH_MAX_AGE_H = 20.0
VERDICT_TAIL_BYTES = 64 * 1024 * 1024
WINDOW_H = 24

#: Instruments the Fed calendar families are minted on: the ones a US policy headline reprices
#: first. Share CFDs are the event lane's and are refused at the door anyway.
FED_INSTRUMENTS: tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "XAUUSD", "XAGUSD",
    "US500", "NAS100", "US30", "USDX", "UST10Y")
#: Instruments the consensus family is minted on (currency legs it can sign).
CONSENSUS_INSTRUMENTS: tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY",
    "AUDJPY")
#: Instruments the entry operators are minted on: the liquid ground, where a spread state and a
#: session open are properties of the venue rather than of an illiquid quote.
EXECUTION_INSTRUMENTS: tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURJPY", "GBPJPY", "AUDJPY", "EURGBP",
    "XAUUSD", "XAGUSD", "US500", "NAS100", "GER40")

#: target -> drivers, written from economic priors BEFORE any data was read: the driver's market
#: prices a shared driver first because its participants watch a different screen.
LEAD_LAG_DRIVERS: dict[str, tuple[str, ...]] = {
    "AUDUSD": ("XCUUSD", "AUS200"), "AUDJPY": ("US500", "USDJPY"), "NZDUSD": ("AUDUSD",),
    "NZDJPY": ("AUDJPY",), "USDCAD": ("XTIUSD", "XBRUSD"), "CADJPY": ("XTIUSD",),
    "USDJPY": ("UST10Y", "US500"), "XAGUSD": ("XAUUSD",), "XPTUSD": ("XAUUSD",),
    "XAUUSD": ("USDX", "UST10Y"), "JPN225": ("USDJPY", "US500"), "AUS200": ("US500",),
    "HK50": ("US500", "CHINAH"), "GER40": ("US500", "EUSTX50"), "UK100": ("US500",),
    "EURNOK": ("XBRUSD",), "EURJPY": ("GER40",), "XCUUSD": ("CHINAH",),
}

#: (target, driver, read_hour, session_h, decision_hour): the driver's session, read when it
#: closes, traded on the target at its next open. Broker hours.
HANDOFFS: tuple[tuple[str, str, int, int, int], ...] = (
    ("AUDJPY", "US500", 22, 8, 1), ("JPN225", "US500", 22, 8, 2), ("AUS200", "US500", 22, 8, 2),
    ("HK50", "US500", 22, 8, 4), ("NZDJPY", "US500", 22, 8, 1), ("USDJPY", "UST10Y", 22, 8, 1),
    ("GER40", "JPN225", 8, 7, 9), ("EURJPY", "JPN225", 8, 7, 9), ("UK100", "HK50", 10, 6, 10),
)

#: The four culture fields (libs/research/cell_culture.py), declared per cluster: where the
#: input comes from and who is on the other side. The failure-mode sentence and the crowding
#: prior are inferred by `cell_culture.carry` from these and are named `inferred:<rule>`.
CULTURE: dict[str, tuple[str, str]] = {
    "options_implied": ("US/en", "institutional"),
    "positioning_flow": ("US/en", "institutional"),
    "execution_entry": ("GLOBAL", "broker_specific"),
    "news_reaction": ("US/en", "policy_driven"),
    "event_surprise": ("US/en", "policy_driven"),
    "cross_asset_lead_lag": ("GLOBAL", "mixed"),
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _grid(family: str) -> list[dict[str, Any]]:
    spec = ec.PARAM_GRID.get(family) or {}
    keys = sorted(spec)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(spec[k] for k in keys))]


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _has_bars(symbol: str) -> bool:
    return (UNIVERSE_DIR / f"{symbol}_H1.parquet").exists()


def _lane_ok(symbol: str, family: str) -> bool:
    try:
        from research.universe_policy import may_hypothesise
        return bool(may_hypothesise(symbol, family))
    except Exception:
        return True                 # an unreadable policy is not a refusal; the door re-checks


# --------------------------------------------------------------------------------- the plan ---
def plan() -> tuple[list[tuple[str, str, dict[str, Any]]], dict[str, list[str]]]:
    """(cells, missing inputs per cluster). A cell is (symbol, family, params incl. `symbol`).

    Instruments come from each family's declared input map, never a symbol list invented here: a
    family is minted where its input exists for the instrument, and where it does not the input
    is named as the cluster's missing artifact."""
    cells: list[tuple[str, str, dict[str, Any]]] = []
    missing: dict[str, list[str]] = {c: [] for c in CLUSTERS}

    def add(sym: str, fam: str, extra: dict[str, Any] | None = None) -> None:
        if not _has_bars(sym) or not _lane_ok(sym, fam):
            return
        for g in _grid(fam):
            cells.append((sym, fam, {"symbol": sym, **(extra or {}), **g}))

    indices = sorted({v[0] for v in ec.IMPLIED_MAP.values()})
    for idx in indices:
        if ec.implied_series(idx) is None:
            missing["options_implied"].append(_rel(ec.implied_file(idx)))
    for sym, (idx, _r) in sorted(ec.IMPLIED_MAP.items()):
        if ec.implied_series(idx) is None:
            continue
        add(sym, "implied_vol_risk_premium")
        add(sym, "implied_vol_shock_fade")

    cot_syms = sorted({p.stem.rpartition("_")[0] for p in UNIVERSE_DIR.glob("*_H1.parquet")})
    have: set[str] = set()
    for sym in cot_syms:
        if ec.cot_frame(sym) is None:
            got = ec.cot_contract(sym)
            if got is not None:
                have.add(_rel(ec.COT_DIR / f"{got[0]}.parquet"))
            continue
        for fam in ("positioning_crowding_unwind", "positioning_hedging_pressure",
                    "positioning_flow_momentum"):
            add(sym, fam)
    missing["positioning_flow"] = sorted(p for p in have if not (ROOT / p).exists())

    # The limit operator mints nothing until the engine declares a limit order type (PR #222):
    # its cells would be judged on an inferred touch-fill. The wait is named, not charged.
    entry_fams = ["entry_alpha_spread_gate", "entry_alpha_open_offset"]
    if ec.limit_engine_ready():
        entry_fams.insert(0, "entry_alpha_limit_pullback")
    else:
        missing["execution_entry"].append(ec.LIMIT_ENGINE_WAIT)
    for sym in EXECUTION_INSTRUMENTS:
        for base in ec.ENTRY_BASES:
            for fam in entry_fams:
                add(sym, fam, {"base_family": base, "base_params": {}})

    if not ec.fed_calendar():
        rel = _rel(ec.FED_CALENDAR)
        missing["news_reaction"].append(rel)
        missing["event_surprise"].append(rel)
    else:
        for sym in FED_INSTRUMENTS:
            add(sym, "cb_tone_speech_reaction")
            add(sym, "news_reaction_unscheduled_shock")
            add(sym, "event_surprise_impact_drift")
    if not ec.CONSENSUS_STORE.exists():
        missing["event_surprise"].append(_rel(ec.CONSENSUS_STORE))
    else:
        for sym in CONSENSUS_INSTRUMENTS:
            add(sym, "event_surprise_consensus")

    for tgt, drivers in sorted(LEAD_LAG_DRIVERS.items()):
        for drv in drivers:
            if not _has_bars(drv):
                missing["cross_asset_lead_lag"].append(f"data/universe/{drv}_H1.parquet")
                continue
            add(tgt, "cross_asset_lead_lag", {"cond_symbol": drv})
    for tgt, drv, rh, sh, dh in HANDOFFS:
        if not _has_bars(drv):
            missing["cross_asset_lead_lag"].append(f"data/universe/{drv}_H1.parquet")
            continue
        add(tgt, "lead_lag_session_handoff",
            {"cond_symbol": drv, "read_hour": rh, "session_h": sh, "decision_hour": dh})
    return cells, {k: sorted(set(v)) for k, v in missing.items()}


# ------------------------------------------------------------------------------ the state -----
def _load_state() -> dict[str, Any]:
    doc = _read(STATE)
    return doc if isinstance(doc, dict) and isinstance(doc.get("cells"), dict) else {"cells": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True), "utf-8")
    tmp.replace(STATE)


def _append(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")


def _node(sym: str, fam: str, params: dict[str, Any]) -> str:
    from libs.research.hypothesis_graph import node_id
    return node_id(sym, fam, dict(params))


def _bars(symbol: str) -> pd.DataFrame | None:
    try:
        return pd.read_parquet(UNIVERSE_DIR / f"{symbol}_H1.parquet")
    except Exception:
        return None


def refresh_observables(*, max_age_h: float = FETCH_MAX_AGE_H,
                        timeout_s: float = 300.0) -> dict[str, Any]:
    """Run the free-observables fetcher when the implied/calendar files are stale. Never raises."""
    probe = ec.implied_file("vix")
    try:
        age_h = (time.time() - probe.stat().st_mtime) / 3600.0
    except OSError:
        age_h = float("inf")
    if age_h < max_age_h:
        return {"status": "FRESH", "age_h": round(age_h, 1)}
    try:
        cp = subprocess.run([sys.executable, str(FETCHER)], cwd=str(ROOT), capture_output=True,
                            text=True, timeout=timeout_s, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "FETCH_FAILED", "why": f"{type(exc).__name__}"}
    return {"status": "FETCHED" if cp.returncode == 0 else "FETCH_FAILED", "rc": cp.returncode,
            "tail": (cp.stdout or "")[-600:]}


# ------------------------------------------------------------------------------- the seeding --
def _cell_row(sym: str, fam: str, params: dict[str, Any], firing: dict[str, int]) -> dict:
    from libs.research import cell_culture as CC

    from research import proposer_common as pc
    cluster = ec.TARGETS[fam]
    mech = (f"{fam} on {sym}, built for the empty {cluster} alpha cluster: "
            f"{_prior(fam)} Loads its own input ({ec.INPUTS[fam][0]}), so the sealed gauntlet "
            "builds it through its ordinary call.")
    row = pc.candidate(SOURCE, sym, fam, params, mech, f"{sym} {fam} [{cluster}]",
                       {"firing": firing, "seed_floor": SEED_FLOOR, "gauntlet_floor": FIRE_FLOOR,
                        "target_cluster": cluster})
    culture, structure = CULTURE[cluster]
    row["alpha_cluster"] = cluster
    row[CC.SOURCE_CULTURE] = culture
    row[CC.PARTICIPANT_STRUCTURE] = structure
    return CC.carry(row)


def _prior(fam: str) -> str:
    doc = ec.__doc__ or ""
    i = doc.find(f"    {fam} ")
    if i < 0:
        return ""
    j = doc.find("Payer:", i)
    k = doc.find(".", j) if j > 0 else -1
    return " ".join(doc[i:k + 1].split()) if k > 0 else ""


def seed(*, budget_s: float = 900.0, dry_run: bool = False,
         only: list[str] | None = None) -> dict[str, Any]:
    from research.cross_sectional_breadth import firing
    started = time.monotonic()
    today = _now().date().isoformat()
    cells, missing = plan()
    if only:
        cells = [c for c in cells if c[0] in only]
    state = _load_state()
    cs: dict[str, Any] = state["cells"]
    by_cluster: dict[str, Counter] = {c: Counter() for c in CLUSTERS}
    errors: Counter = Counter()
    charged: dict[str, list[str]] = {}
    cands: list[tuple[str, str, dict[str, Any], dict[str, int], str]] = []
    stopped = "grid exhausted"
    frames: dict[str, pd.DataFrame | None] = {}
    # least-recently measured first, so a budget-bound pass rotates through the whole grid
    order = sorted(cells, key=lambda c: str((cs.get(_node(*c)) or {}).get("day") or ""))
    for sym, fam, params in order:
        cl = ec.TARGETS[fam]
        ident = _node(sym, fam, params)
        prior = cs.get(ident) or {}
        by_cluster[cl]["grid"] += 1
        if prior.get("day") != today:
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached; resumes next pass"
                by_cluster[cl]["deferred"] += 1
                continue
            if sym not in frames:
                if len(frames) > 24:
                    frames.clear()
                frames[sym] = _bars(sym)
            d = frames[sym]
            if d is None:
                errors[f"{sym}: no bars"] += 1
                continue
            try:
                fn = ec.EMPTY_CLUSTER_FAMILIES[fam]
                got = firing(list(fn(d, **params) or []), ec._h1(d))
            except Exception as exc:
                errors[f"{fam}: {type(exc).__name__}"] += 1
                continue
            prior = {**prior, **got, "day": today, "family": fam, "symbol": sym,
                     "params": params, "cluster": cl}
            cs[ident] = prior
            by_cluster[cl]["measured_this_pass"] += 1
            if not prior.get("charged_at"):
                charged.setdefault(fam, []).append(ident)
        ok = int(prior.get("trade_days_lb") or 0) >= SEED_FLOOR
        by_cluster[cl]["clears_floor" if ok else "held_back_under_floor"] += 1
        if ok and not prior.get("donated_at"):
            cands.append((sym, fam, params,
                          {k: int(prior.get(k) or 0) for k in ("signal_days", "trade_days_lb")},
                          ident))

    ts = _now().isoformat(timespec="seconds")
    trial_rows = [{"ts": ts, "family": f, "cluster": ec.TARGETS[f], "cells_screened": len(ids),
                   "cells": sorted(ids), "source": SOURCE, "dry_run": bool(dry_run),
                   "rule": ("every MEASURED cell is a trial of its family, clearing the floor or "
                            "not; `cells` are hypothesis-graph node ids so experiment_ledger "
                            "charges each once and skips it when the graph holds it judged")}
                  for f, ids in sorted(charged.items())]
    donated: dict[str, int] = dict.fromkeys(CLUSTERS, 0)
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    if not dry_run:
        _append(TRIALS, trial_rows)
        for rows in charged.values():
            for ident in rows:
                cs[ident]["charged_at"] = ts
    if cands and not dry_run:
        from research import proposer_common as pc
        rows = [_cell_row(s, f, p, fi) for s, f, p, fi, _i in cands]
        # tests_run=0 ON PURPOSE: every one of these cells (and every held-back one) is already
        # charged in EMPTY_CLUSTER_TRIALS.jsonl; carrying the count here too would charge the
        # proposer ledger a second time for the same trials.
        path = pc.donate(SOURCE, rows, 0)
        counts = pc.donation_counts()
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None,
                    "donated": counts.get("donated"),
                    "refused_wrong_lane": counts.get("refused_wrong_lane"),
                    "refused_unstamped": counts.get("refused_unstamped")}
        if path:
            refused = {(str(r.get("symbol")), str(r.get("family")))
                       for r in (counts.get("lane_refusals") or [])}
            for s, f, _p, _fi, ident in cands:
                if (s, f) in refused:
                    continue
                cs[ident]["donated_at"] = ts
                donated[ec.TARGETS[f]] += 1
    for cl in CLUSTERS:
        by_cluster[cl]["minted_this_pass"] = donated[cl]
    if not dry_run:
        _save_state(state)
        _append(MINT_LEDGER, [{"ts": ts, "cluster": cl, "minted": donated[cl],
                               "measured": int(by_cluster[cl]["measured_this_pass"]),
                               "clears_floor": int(by_cluster[cl]["clears_floor"]),
                               "held_back": int(by_cluster[cl]["held_back_under_floor"]),
                               "missing_inputs": missing.get(cl, [])} for cl in CLUSTERS])
    seeded = Counter(str(v.get("cluster")) for v in cs.values() if v.get("donated_at"))
    return {
        "status": "OK", "dry_run": bool(dry_run), "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 2),
        "grid_cells": len(cells), "seed_floor_trade_days": SEED_FLOOR,
        "by_cluster": {cl: {**dict(by_cluster[cl]), "seeded_total": int(seeded.get(cl, 0)),
                            "missing_inputs": missing.get(cl, [])} for cl in CLUSTERS},
        "trials_charged_this_pass": sum(len(v) for v in charged.values()),
        "donation": donation, "errors": dict(errors),
    }


# ------------------------------------------------------------------------------ the report ----
def minted_in_window(*, hours: float = WINDOW_H, now: datetime | None = None,
                     ledger: Path | None = None) -> dict[str, Any]:
    """Cells minted per cluster in the last `hours`, read from the mint ledger. The fence's
    measurement. An absent ledger is UNMEASURED, never zero."""
    path = ledger or MINT_LEDGER
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return {"status": UNMEASURED, "why": f"{path.name} absent: this organ has never run here"}
    cut = (now or _now()) - timedelta(hours=hours)
    out: Counter = Counter()
    passes = 0
    last: dict[str, Any] = {}
    for ln in lines:
        try:
            r = json.loads(ln)
            t = datetime.fromisoformat(str(r["ts"]))
        except (ValueError, KeyError, TypeError):
            continue
        if t < cut or r.get("cluster") not in CLUSTERS:
            continue
        passes += 1
        out[r["cluster"]] += int(r.get("minted") or 0)
        last[r["cluster"]] = r
    return {"status": "MEASURED", "window_h": hours, "passes_in_window": passes,
            "minted": {c: int(out.get(c, 0)) for c in CLUSTERS},
            "zero_minted": [c for c in CLUSTERS if not out.get(c)],
            "last_missing_inputs": {c: (last.get(c) or {}).get("missing_inputs", [])
                                    for c in CLUSTERS}}


def forcer_view() -> dict[str, Any]:
    """The empty-cluster forcer's verdict per cluster (its artifact's reader)."""
    doc = _read(FORCER)
    if not isinstance(doc, dict) or not isinstance(doc.get("clusters"), list):
        return {"status": UNMEASURED, "why": f"{FORCER.name} absent or has no clusters list"}
    rows = {str(r.get("cluster")): {"verdict": r.get("verdict"),
                                    "cells_in_docket": r.get("cells_in_docket"),
                                    "families": r.get("families")}
            for r in doc["clusters"] if isinstance(r, dict)}
    return {"status": "MEASURED", "generated_utc": doc.get("generated_utc"),
            "clusters": {c: rows.get(c, {"verdict": "NOT_EMPTY_PER_FORCER"}) for c in CLUSTERS}}


def verdicts() -> dict[str, Any]:
    """Verdicts the sealed gauntlet has recorded on these families, per cluster and gate."""
    fams = set(ec.EMPTY_CLUSTER_FAMILIES)
    try:
        size = VERDICTS.stat().st_size
        with VERDICTS.open("rb") as fh:
            if size > VERDICT_TAIL_BYTES:
                fh.seek(size - VERDICT_TAIL_BYTES)
                fh.readline()
            blob = fh.read()
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__} reading {VERDICTS.name}"}
    out: dict[str, Counter] = {}
    for line in blob.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        fam = str(row.get("family") or "")
        if fam in fams:
            out.setdefault(ec.TARGETS[fam], Counter())[str(row.get("terminal_gate") or "?")] += 1
    if not out:
        return {"status": UNMEASURED, "why": "the gauntlet has judged none of these cells yet"}
    return {"status": "MEASURED", "by_cluster": {k: dict(v) for k, v in out.items()},
            "clusters_with_judged_cells": sorted(out)}


def report(seeded: dict[str, Any]) -> dict[str, Any]:
    win = minted_in_window()
    return {
        "at": _now().isoformat(timespec="seconds"),
        "organ": "desks/mt5/research/empty_cluster_breadth.py",
        "clusters": list(CLUSTERS),
        "rule": (f"a cell is donated only when its lower-bound trade days clear {SEED_FLOOR} (the "
                 f"sealed gauntlet drops a series under {FIRE_FLOOR} days); every measured cell "
                 "is charged to the census; additive, no other miner is touched"),
        "families": {f: {"cluster": c, "input": ec.INPUTS[f][0], "source": ec.INPUTS[f][1],
                         "grid_per_instrument": len(_grid(f))}
                     for f, c in ec.TARGETS.items()},
        "seeding": seeded,
        "minted_24h": win,
        "fence": {"verdict": ("RED" if win.get("status") != "MEASURED" or win["zero_minted"]
                              else "GREEN"),
                  "zero_minted_24h": win.get("zero_minted", list(CLUSTERS)),
                  "checked_by": "scripts/check_empty_cluster_minting.py"},
        "forcer": forcer_view(),
        "verdicts": verdicts(),
        "consumer": ("data/intelligence/empty_cluster_breadth/ -> "
                     "research/miner_candidate_compiler.py -> the docket -> "
                     "scripts/external_gauntlet.py build_cell (sealed; resolves each family via "
                     "families_orthogonal.ORTHOGONAL_FAMILIES)"),
    }


def run(*, budget_s: float = 900.0, dry_run: bool = False, fetch: bool = True,
        only: list[str] | None = None, out: Path | None = None) -> dict[str, Any]:
    fetched = refresh_observables() if (fetch and not dry_run) else {"status": "SKIPPED"}
    seeded = seed(budget_s=budget_s, dry_run=dry_run, only=only)
    seeded["observables"] = fetched
    doc = report(seeded)
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(target)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled form)")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and report, donate nothing")
    ap.add_argument("--no-fetch", action="store_true", help="do not refresh the observables")
    ap.add_argument("--symbols", nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    doc = run(budget_s=args.budget_s, dry_run=args.dry_run, fetch=not args.no_fetch,
              only=args.symbols, out=args.out)
    s = doc["seeding"]
    print(f"empty_cluster_breadth: grid={s['grid_cells']} charged={s['trials_charged_this_pass']} "
          f"donation={s['donation'].get('status')} stopped={s['stopped_because']!r} "
          f"elapsed={s['elapsed_s']}s fence={doc['fence']['verdict']} -> {args.out or OUT}")
    for cl, c in s["by_cluster"].items():
        print(f"  {cl:22} grid={c.get('grid', 0):5} clears={c.get('clears_floor', 0):5} "
              f"held={c.get('held_back_under_floor', 0):5} minted={c.get('minted_this_pass', 0):4}"
              f" seeded_total={c.get('seeded_total', 0):5}"
              + (f"  missing={c['missing_inputs'][:3]}" if c.get("missing_inputs") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

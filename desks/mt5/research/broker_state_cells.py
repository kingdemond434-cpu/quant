#!/usr/bin/env python3
"""BROKER-STATE CELLS: the venue's own recorded state, turned into cells the ten gates can judge.

    python desks/mt5/research/broker_state_cells.py --once --budget-s 600
    python desks/mt5/research/broker_state_cells.py --once --dry-run      # measure, donate nothing

FOUR INPUTS THE DESK ALREADY HELD AND NOTHING CONVERTED (2026-10-14):

  N7 broker-risk events  `mt5desk/tape.py` records `margin_initial`, `margin_maintenance` and
                         `trade_mode` (CLOSEONLY flips) for every symbol every hour, PIT-stamped,
                         in `data/tape/contract_terms/*.parquet`. Read by nothing.
  swap state             the same tape and the broker swap panel (`data/intelligence/broker_swaps`,
                         ~250k rows in three days) carry every swap change, and produced 0 cells/h.
                         `data/carry_state.json` was last written 2026-08-29 by the VPS cron
                         (`ops/crontab.manifest:3263`), whose branch stopped arriving 2026-09-11;
                         the box's daily `MT5-CostState` runs it through `ops/run_cost_state.cmd`,
                         which ends `exit /b 0` whatever the module returned, and the box has never
                         published a carry state since. This leg rebuilds it HOURLY and records
                         the outcome by name (`carry_state` in the report) so a failure is visible.
  Amihud impact          |return| / tick_volume, hour-of-week normalised (`mt5desk/family_amihud`),
                         seeded here on index CFDs; share CFDs reach it only through the class book
                         `cross_sectional_class_illiquidity`, seeded by `cross_sectional_breadth`.
  options state          the retired archive's BTC/ETH surface vintages, recovered read-only into
                         `data/options_state/vintages.jsonl`, conditioning the BTCUSD/ETHUSD CFDs.

WHAT A PASS DOES:
  1. Rebuild the event store `data/broker_state/events.jsonl` from the whole tape (+ the panel
     before the tape covers a symbol, terminal-captured rows only): margin hikes/cuts,
     CLOSEONLY on/off, swap changes, swap sign flips and carry-tercile changes within the asset
     class, each stamped `knowable_at` = the first record that showed the new value.
     Deterministic; nothing is backfilled.
  2. Rebuild `data/carry_state.json` through `research/carry_state.py` (the existing organ).
  3. Merge any new options vintage into the options store (units normalised, see below).
  4. For every cell of the fixed grids below, run the family on the symbol's own H1 bars and count
     how it fires (`cross_sectional_breadth.firing`: distinct signal days and a lower bound on
     trade days). A cell whose lower bound clears SEED_FLOOR is donated ONCE through
     `proposer_common.donate` (two-lane door, PIT stamp, preregistration, registry). A cell that
     does not is SERIES_ACCRUING -- pending, with its event count -- never refused: the tape
     began 2026-08-26 and a margin hike is a rare event, so most event cells will accrue for a
     long time and the report says exactly how many events each holds.
  5. Write `reports/BROKER_STATE_CELLS.json`.

TRIALS. Every grid cell is ONE trial, charged once, at the unchanged Tier S bar: `declared_width`
is 1 on every row and `tests_run` is the number of cells donated. Nothing is screened on outcome
here -- the firing count reads signals, never returns -- so there is no selection to charge.

UNMEASURED IS AN ANSWER (L1.28a). No contract-terms tape on this host -> the event store is not
rewritten and every N7 cell reads UNMEASURED with that reason, never zero events.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from mt5desk import family_amihud as fam_amihud  # noqa: E402
from mt5desk import family_broker_state as fbs  # noqa: E402
from mt5desk import family_options_state as fos  # noqa: E402

SOURCE = "broker_state_cells"
TERMS = BASE / "data" / "tape" / "contract_terms"
PANEL = BASE / "data" / "intelligence" / "broker_swaps"
UNIVERSE = BASE / "data" / "universe"
OPTIONS_STATE = BASE / "data" / "options_state.json"
OPTIONS_CANDIDATES = BASE / "data" / "options_candidates.json"
OPTIONS_ARCHIVE = BASE / "data" / "options_archive.parquet"
OUT = BASE / "reports" / "BROKER_STATE_CELLS.json"
STATE = BASE / "data" / "broker_state" / "cells_state.json"
UNMEASURED = "UNMEASURED"
ACCRUING = "SERIES_ACCRUING"

#: N7's named instruments. BTCUSD is Fusion's CFD, an MT5 instrument like the rest.
BROKER_SYMBOLS = ("XAUUSD", "XAGUSD", "US500", "NAS100", "USDZAR", "USDMXN", "USDTRY", "BTCUSD")
#: Swap-drift cells run on FX and metals (GAP_MAP row 52: "delta-swap cells on FX and gold").
SWAP_CLASSES = ("forex", "forex exotics", "forex majors", "forex minors", "commodities",
                "metals")
#: The time-series Amihud family runs on index CFDs (shares go through the class book only).
AMIHUD_CLASSES = ("indices",)

#: The fixed grids. Every combination is one cell, charged once.
MARGIN_GRID: dict[str, list[Any]] = {"event": list(fbs.MARGIN_EVENTS), "mode": list(fbs.MODES),
                                     "hold_bars": [1, 6, 24]}
SWAP_GRID: dict[str, list[Any]] = {"event": list(fbs.SWAP_EVENTS), "mode": list(fbs.MODES),
                                   "hold_bars": [24, 120]}
AMIHUD_GRID: list[dict[str, Any]] = [
    {"mode": "premium", "hold_bars": 24}, {"mode": "premium", "hold_bars": 120},
    {"mode": "shock_reversal", "hold_bars": 1}, {"mode": "shock_reversal", "hold_bars": 4}]
OPTIONS_GRID: dict[str, list[Any]] = {"field": list(fos.FIELDS), "mode": list(fos.MODES),
                                      "hold_bars": [24]}

#: Same floor as the class-book seeder: the sealed gauntlet drops a cell whose daily series has
#: fewer than 60 days, so a cell is donated when its LOWER-BOUND trade days clear 66.
SEED_FLOOR = 66
#: A carry tercile needs at least this many measured members in the class that day.
MIN_RANK_MEMBERS = 6
#: Mode-5 annual percent and mode-1 money are compared on one scale: annual % of notional.
DAY_COUNT = 360.0
#: An options vintage with ATM IV above this was recorded in PERCENT (the retired archive switched
#: to a fraction on 2026-08-25: 37.14 -> 0.5199); it is divided by 100 with its skew and slope.
PERCENT_ERA_IV = 3.0


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    tmp.replace(path)


def _fnum(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


# ------------------------------------------------------------------------------ the tape -----
TERM_COLUMNS = ("observed_at", "symbol", "margin_initial", "margin_maintenance", "trade_mode",
                "swap_long", "swap_short", "swap_mode", "tick_value", "tick_size")


def load_terms(terms_dir: Path = TERMS) -> pd.DataFrame | None:
    """Every contract-terms row, sorted by (symbol, observed_at). None when the tape is absent."""
    files = sorted(terms_dir.glob("*.parquet")) if terms_dir.exists() else []
    frames = []
    for f in files:
        try:
            frames.append(pd.read_parquet(f))
        except Exception:
            continue
    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True)
    for c in TERM_COLUMNS:
        if c not in df.columns:
            df[c] = None
    df = df[list(TERM_COLUMNS)].copy()
    df["observed_at"] = df["observed_at"].astype(str)
    df = df.drop_duplicates(subset=["observed_at", "symbol"], keep="last")
    return df.sort_values(["symbol", "observed_at"], kind="stable").reset_index(drop=True)


def _change_points(rows: list[tuple[str, Any]]) -> list[tuple[str, Any, Any]]:
    """(knowable_at, prev, new) at every change of a series of (observed_at, value), skipping
    absent values (an unread field is not a change)."""
    out: list[tuple[str, Any, Any]] = []
    prev: Any = None
    for t, v in rows:
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            continue
        if prev is not None and v != prev:
            out.append((t, prev, v))
        prev = v
    return out


def margin_events(terms: pd.DataFrame) -> list[dict[str, Any]]:
    """Margin hikes/cuts and CLOSEONLY on/off, per symbol, from the hourly tape."""
    out: list[dict[str, Any]] = []
    for sym, g in terms.groupby("symbol", sort=True):
        t = g["observed_at"].tolist()
        for field in ("margin_initial", "margin_maintenance"):
            vals = [_fnum(v) for v in g[field].tolist()]
            for at, prev, new in _change_points(list(zip(t, vals, strict=True))):
                out.append({"symbol": str(sym), "kind": "margin_hike" if new > prev
                            else "margin_cut", "field": field, "knowable_at": at,
                            "prev": prev, "new": new, "direction": 0,
                            "source": "contract_terms"})
        modes = []
        for v in g["trade_mode"].tolist():
            f = _fnum(v)
            modes.append(None if f is None else int(f))
        for at, prev, new in _change_points(list(zip(t, modes, strict=True))):
            kind = ("closeonly_on" if new == 3 and prev != 3
                    else "closeonly_off" if prev == 3 and new != 3 else None)
            if kind:
                out.append({"symbol": str(sym), "kind": kind, "field": "trade_mode",
                            "knowable_at": at, "prev": prev, "new": new, "direction": 0,
                            "source": "contract_terms"})
    # margin_initial and margin_maintenance often move together: one dated instruction is ONE
    # event, so a second field changing in the same record does not count twice.
    seen: set[tuple[str, str, str]] = set()
    uniq = []
    for e in sorted(out, key=lambda e: (e["symbol"], e["knowable_at"], e["field"])):
        key = (e["symbol"], e["kind"], e["knowable_at"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq


#: Only panel rows the box's terminal wrote are venue evidence (`tape.swap_panel_rows` stamps
#: them). The VPS seed miner's rows re-read the swap fields out of a git copy of `universe.json`
#: and FLIP-FLOP between registry copies: measured 2026-10-14 on the committed panel, XAUUSD
#: "changed" 15 times between 2026-08-27 and 09-12, toggling -67.06/32.75 <-> -61.76/29.45 eight
#: times in nine days -- a reader's alternation between two files, not a broker repricing. Those
#: rows are counted and never become events.
TERMINAL_CAPTURE = "mt5desk.tape"
_PANEL_SKIPPED: Counter = Counter()


def _panel_rows(panel_dir: Path) -> dict[str, list[tuple[str, float, float]]]:
    """Per-symbol (stamp, swap_long, swap_short) of the TERMINAL-captured panel rows, from the
    panel's JSON files and daily rollups."""
    series: dict[str, list[tuple[str, float, float]]] = {}
    _PANEL_SKIPPED.clear()
    if not panel_dir.exists():
        return series

    def take(r: Any) -> None:
        if not isinstance(r, dict) or r.get("kind") != "swap_table":
            return
        if not str(r.get("captured_by") or "").startswith(TERMINAL_CAPTURE):
            _PANEL_SKIPPED["registry_reread_rows"] += 1
            return
        syms = r.get("symbols") or []
        lo, sh = _fnum(r.get("swap_long")), _fnum(r.get("swap_short"))
        at = r.get("observed_at") or r.get("found_at")
        if not syms or lo is None or sh is None or not at:
            return
        series.setdefault(str(syms[0]), []).append((str(at), lo, sh))

    for f in sorted(panel_dir.glob("*.json")):
        doc = _read(f)
        for r in doc if isinstance(doc, list) else []:
            take(r)
    for f in sorted(panel_dir.glob("rollup_*.jsonl.gz")):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        take(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            continue
    for v in series.values():
        v.sort()
    return series


def swap_series(terms: pd.DataFrame | None,
                panel: dict[str, list[tuple[str, float, float]]]
                ) -> dict[str, list[tuple[str, float, float, int | None]]]:
    """(stamp, long, short, swap_mode) per symbol. The tape wins wherever it covers a symbol; the
    panel supplies only rows BEFORE the tape's first observation of it, so a stale registry copy
    re-read on the VPS can never interleave with the terminal's own value."""
    out: dict[str, list[tuple[str, float, float, int | None]]] = {}
    tape: dict[str, list[tuple[str, float, float, int | None]]] = {}
    if terms is not None:
        for sym, g in terms.groupby("symbol", sort=True):
            rows = []
            for at, lo, sh, md in zip(g["observed_at"], g["swap_long"], g["swap_short"],
                                      g["swap_mode"], strict=True):
                lo_f, sh_f, md_f = _fnum(lo), _fnum(sh), _fnum(md)
                if lo_f is None or sh_f is None:
                    continue
                rows.append((str(at), lo_f, sh_f, None if md_f is None else int(md_f)))
            if rows:
                tape[str(sym)] = rows
    for sym in sorted(set(tape) | set(panel)):
        first_tape = tape[sym][0][0] if sym in tape else None
        early = [(t, lo, sh, None) for t, lo, sh in panel.get(sym, [])
                 if first_tape is None or t < first_tape]
        out[sym] = early + tape.get(sym, [])
    return out


def swap_events(series: dict[str, list[tuple[str, float, float, int | None]]]
                ) -> list[dict[str, Any]]:
    """Swap-differential changes and sign flips. Direction = sign of the change in
    (long - short); within one swap mode both sides share one positive scale, so the raw sign is
    the money sign. A change of MODE is a unit change, never an event."""
    out: list[dict[str, Any]] = []
    for sym, rows in series.items():
        prev: tuple[str, float, float, int | None] | None = None
        for row in rows:
            if prev is not None and (row[1], row[2]) != (prev[1], prev[2]):
                if row[3] is not None and prev[3] is not None and row[3] != prev[3]:
                    prev = row
                    continue
                d_new, d_old = row[1] - row[2], prev[1] - prev[2]
                direction = int(np.sign(d_new - d_old))
                if direction != 0:
                    base = {"symbol": sym, "knowable_at": row[0], "direction": direction,
                            "prev": [prev[1], prev[2]], "new": [row[1], row[2]],
                            "source": "contract_terms" if row[3] is not None else "swap_panel"}
                    out.append({**base, "kind": "swap_change"})
                    flipped = any(a != 0 and b != 0 and (a > 0) != (b > 0)
                                  for a, b in ((prev[1], row[1]), (prev[2], row[2])))
                    if flipped:
                        out.append({**base, "kind": "swap_sign_flip"})
            prev = row
    return out


def _closes(symbol: str, universe: Path) -> pd.Series | None:
    try:
        df = pd.read_parquet(universe / f"{symbol}_H1.parquet", columns=["close"])
    except Exception:
        return None
    idx = pd.DatetimeIndex(df.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    s = pd.Series(df["close"].to_numpy(dtype="float64"), index=idx).sort_index()
    return s[np.isfinite(s.to_numpy()) & (s.to_numpy() > 0)]


def carry_rank_events(terms: pd.DataFrame | None, registry: dict[str, Any],
                      universe: Path = UNIVERSE) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Carry-tercile changes within each asset class, from daily snapshots of the tape.

    Carry = long-minus-short financing as annual percent of notional (mode 5 is already annual
    percent; mode 1 money per night is scaled by notional at the snapshot's last H1 close,
    PIT). The rank needs every member's value, so the event is knowable at the LATEST
    observation used for the class that day."""
    from libs.regime.session_clock import utc_to_server
    from research.carry_state import money_per_lot_night
    if terms is None or terms.empty:
        return [], {"status": UNMEASURED, "why": "no contract-terms tape on this host"}
    t = terms.copy()
    t["day"] = t["observed_at"].str.slice(0, 10)
    last = t.groupby(["symbol", "day"], sort=True).tail(1)
    closes: dict[str, pd.Series | None] = {}
    snap: list[dict[str, Any]] = []
    for r in last.itertuples(index=False):
        sym = str(r.symbol)
        mode = _fnum(r.swap_mode)
        lo, sh = _fnum(r.swap_long), _fnum(r.swap_short)
        if mode is None or lo is None or sh is None:
            continue
        mode_i = int(mode)
        if mode_i == 5:
            carry = lo - sh
        elif mode_i == 1:
            if sym not in closes:
                closes[sym] = _closes(sym, universe)
            px_s = closes[sym]
            at = utc_to_server(r.observed_at)
            if px_s is None or at is None:
                continue
            j = int(px_s.index.searchsorted(at, side="right")) - 1
            tv, ts_ = _fnum(r.tick_value), _fnum(r.tick_size)
            if j < 0 or not tv or not ts_:
                continue
            terms_d = {"swap_mode": 1, "tick_value": tv, "tick_size": ts_}
            m_lo = money_per_lot_night(lo, terms_d, None)[0]
            m_sh = money_per_lot_night(sh, terms_d, None)[0]
            notional = float(px_s.iloc[j]) * tv / ts_
            if m_lo is None or m_sh is None or notional <= 0:
                continue
            carry = (m_lo - m_sh) * DAY_COUNT / notional * 100.0
        else:
            continue
        klass = str((registry.get(sym) or {}).get("asset_class") or "").lower()
        if klass:
            snap.append({"symbol": sym, "day": r.day, "klass": klass, "carry": carry,
                         "at": str(r.observed_at)})
    if not snap:
        return [], {"status": UNMEASURED, "why": "no symbol-day resolved to a carry value"}
    frame = pd.DataFrame(snap)
    out: list[dict[str, Any]] = []
    prev_t: dict[str, int] = {}
    n_days = 0
    for (_day, klass), g in frame.groupby(["day", "klass"], sort=True):
        if len(g) < MIN_RANK_MEMBERS:
            continue
        n_days += 1
        pct = g["carry"].rank(pct=True, method="average")
        terc = np.ceil(pct * 3).clip(1, 3).astype(int)
        knowable = str(g["at"].max())
        for sym, tv_ in zip(g["symbol"], terc, strict=True):
            old = prev_t.get(sym)
            if old is not None and int(tv_) != old:
                out.append({"symbol": sym, "kind": "carry_rank_change", "knowable_at": knowable,
                            "direction": int(np.sign(int(tv_) - old)), "prev": old,
                            "new": int(tv_), "klass": klass, "source": "contract_terms"})
            prev_t[sym] = int(tv_)
    return out, {"status": "MEASURED", "class_days_ranked": n_days,
                 "symbol_days": len(frame)}


def build_store(terms_dir: Path = TERMS, panel_dir: Path = PANEL, universe: Path = UNIVERSE,
                store: Path | None = None, write: bool = True) -> dict[str, Any]:
    """Rebuild the event store from the whole tape. Returns the census; never raises on data."""
    terms = load_terms(terms_dir)
    panel = _panel_rows(panel_dir)
    registry = _read(universe / "universe.json") or {}
    events: list[dict[str, Any]] = []
    tape: dict[str, Any]
    if terms is None:
        tape = {"status": UNMEASURED, "why": f"no contract-terms parquet under {terms_dir}"}
    else:
        tape = {"status": "MEASURED", "rows": len(terms), "symbols": int(terms["symbol"].nunique()),
                "first": str(terms["observed_at"].min()), "last": str(terms["observed_at"].max()),
                "hours": int(terms["observed_at"].str.slice(0, 13).nunique())}
        events += margin_events(terms)
    events += swap_events(swap_series(terms, panel))
    rank, rank_status = carry_rank_events(terms, registry, universe)
    events += rank
    events.sort(key=lambda e: (e["knowable_at"], e["symbol"], e["kind"]))
    path = store or fbs.store_path()
    wrote = False
    # A host with neither the tape nor terminal panel rows has NO evidence; it never overwrites a
    # store a host with evidence wrote (the store is the box's state).
    if write and (terms is not None or panel):
        _write_atomic(path, "".join(json.dumps(e, sort_keys=True, default=str) + "\n"
                                    for e in events))
        wrote = True
    by_kind = Counter(e["kind"] for e in events)
    by_sym_kind: dict[str, dict[str, int]] = {}
    for e in events:
        by_sym_kind.setdefault(e["symbol"], Counter())[e["kind"]] += 1   # type: ignore[index]
    return {"tape": tape, "panel_symbols": len(panel),
            "panel_rows": sum(len(v) for v in panel.values()),
            "panel_rows_not_venue_evidence": dict(_PANEL_SKIPPED),
            "carry_rank": rank_status, "n_events": len(events), "by_kind": dict(by_kind),
            "n7_symbols": {s: dict(by_sym_kind.get(s, {})) for s in BROKER_SYMBOLS},
            "store": str(path), "store_written": wrote}


# ---------------------------------------------------------------------------- carry state ---
def rebuild_carry_state(write: bool = True) -> dict[str, Any]:
    """Run the existing carry-state organ and say what happened, by name."""
    try:
        from research import carry_state
        rep = carry_state.build()
    except Exception as exc:
        return {"status": "ERROR", "why": f"{type(exc).__name__}: {str(exc)[:200]}"}
    if not rep.get("symbols"):
        reasons = Counter(str(s.get("why", ""))[:60] for s in rep.get("skipped") or [])
        return {"status": "NOT_WRITTEN", "why": "no symbol resolved (carry_state refuses an "
                "empty state)", "n_skipped": rep.get("n_skipped"),
                "skip_reasons": dict(reasons.most_common(5))}
    if write:
        try:
            _write_atomic(carry_state._OUT, json.dumps(rep, indent=1, sort_keys=True,
                                                       default=str) + "\n")
        except (OSError, TypeError, ValueError) as exc:
            return {"status": "ERROR", "why": f"write failed: {type(exc).__name__}: {exc}"}
    return {"status": "REBUILT" if write else "DRY_RUN", "generated_at": rep.get("generated_at"),
            "n_symbols": rep.get("n_symbols"), "n_measured_sides": rep.get("n_measured_sides"),
            "n_changed_symbols": rep.get("n_changed_symbols"),
            "n_sign_flipped_sides": rep.get("n_sign_flipped_sides"),
            "window": [rep.get("window_start"), rep.get("window_end")]}


# ------------------------------------------------------------------------- options store ----
def normalise_vintage(r: dict[str, Any], source: str) -> dict[str, Any] | None:
    """One surface vintage in ONE unit (fractions). None when it carries no stamp or currency."""
    ts, cur = r.get("ts"), r.get("currency")
    if not ts or not cur:
        return None
    iv = _fnum(r.get("atm_iv"))
    scale = 0.01 if (iv is not None and iv > PERCENT_ERA_IV) else 1.0
    row: dict[str, Any] = {"kind": "vintage", "currency": str(cur), "ts": str(ts),
                           "source": source, "unit_normalised": scale != 1.0}
    for k in ("atm_iv", "skew", "term_slope"):
        v = _fnum(r.get(k))
        row[k] = None if v is None else v * scale
    row["dvol"] = _fnum(r.get("dvol"))
    row["iv_rv_raw"] = _fnum(r.get("iv_rv"))          # kept, never read: rv_1w changed units
    return row


def refresh_options_store(store: Path | None = None, write: bool = True) -> dict[str, Any]:
    """Merge any options vintage on disk into the store. Read-only on every source."""
    path = store or fos.store_path()
    rows: dict[tuple[Any, ...], dict[str, Any]] = {}
    try:
        for line in path.read_text("utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict):
                rows[(r.get("kind"), r.get("currency"), r.get("field"), r.get("ts"))] = r
    except OSError:
        pass
    before = len(rows)
    state = _read(OPTIONS_STATE) or {}
    for r in state.get("latest") or [] if isinstance(state, dict) else []:
        v = normalise_vintage(r, "options_state.json") if isinstance(r, dict) else None
        if v:
            rows.setdefault(("vintage", v["currency"], None, v["ts"]), v)
    cands = _read(OPTIONS_CANDIDATES) or {}
    for c in cands.get("candidates") or [] if isinstance(cands, dict) else []:
        if isinstance(c, dict) and c.get("ts"):
            rows.setdefault(("candidate", c.get("currency"), c.get("field"), c.get("ts")), {
                "kind": "candidate", "currency": c.get("currency"), "field": c.get("field"),
                "z": c.get("z"), "ts": c.get("ts"), "z_trusted": False,
                "why_untrusted": "z computed against an archive whose ATM IV switched from "
                                 "percent to fraction on 2026-08-25",
                "source": "options_candidates.json"})
    archive = "ABSENT"
    if OPTIONS_ARCHIVE.exists():
        try:
            arc = pd.read_parquet(OPTIONS_ARCHIVE)
            for r in arc.to_dict("records"):
                v = normalise_vintage(r, "options_archive.parquet")
                if v:
                    rows.setdefault(("vintage", v["currency"], None, v["ts"]), v)
            archive = f"READ {len(arc)} rows"
        except Exception as exc:
            archive = f"UNREADABLE {type(exc).__name__}"
    out = sorted(rows.values(), key=lambda r: (str(r.get("ts")), str(r.get("kind")),
                                               str(r.get("currency")), str(r.get("field"))))
    if write and len(out) != before:
        _write_atomic(path, "".join(json.dumps(r, sort_keys=True) + "\n" for r in out))
    vint = [r for r in out if r.get("kind") == "vintage"]
    return {"store": str(path), "rows": len(out), "added": len(out) - before,
            "vintages": dict(Counter(str(r.get("currency")) for r in vint)),
            "first": min((str(r["ts"]) for r in vint), default=None),
            "last": max((str(r["ts"]) for r in vint), default=None),
            "candidates_untrusted": sum(1 for r in out if r.get("kind") == "candidate"
                                        and r.get("z_trusted") is not True),
            "archive": archive}


# ------------------------------------------------------------------------------- cells ------
def _grid(spec: dict[str, list[Any]]) -> list[dict[str, Any]]:
    import itertools
    keys = sorted(spec)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(spec[k] for k in keys))]


def _class_of(sym: str, registry: dict[str, Any]) -> str:
    return str((registry.get(sym) or {}).get("asset_class") or "").lower()


def plan(registry: dict[str, Any], universe: Path = UNIVERSE) -> list[dict[str, Any]]:
    """Every (family, symbol, params) cell this organ owns, with the item it belongs to."""
    from research.universe_policy import may_hypothesise
    cells: list[dict[str, Any]] = []
    for sym in BROKER_SYMBOLS:
        for p in _grid(MARGIN_GRID):
            cells.append({"item": "N7_broker_risk", "family": "broker_margin_event",
                          "symbol": sym, "params": {"symbol": sym, **p}})
    swap_syms = sorted(s for s in registry if _class_of(s, registry) in SWAP_CLASSES
                       and may_hypothesise(s, "carry_swap_drift"))
    for sym in swap_syms:
        for p in _grid(SWAP_GRID):
            cells.append({"item": "swap_drift", "family": "carry_swap_drift", "symbol": sym,
                          "params": {"symbol": sym, **p}})
    idx_syms = sorted(s for s in registry if _class_of(s, registry) in AMIHUD_CLASSES
                      and may_hypothesise(s, "amihud_illiquidity"))
    for sym in idx_syms:
        for p in AMIHUD_GRID:
            cells.append({"item": "amihud_index", "family": "amihud_illiquidity", "symbol": sym,
                          "params": dict(p)})
    for sym in fos.UNDERLYING:
        for p in _grid(OPTIONS_GRID):
            cells.append({"item": "options_state", "family": "crypto_options_state",
                          "symbol": sym, "params": {"symbol": sym, **p}})
    return cells


FAMILY_FN = {"broker_margin_event": fbs.family_broker_margin_event,
             "carry_swap_drift": fbs.family_carry_swap_drift,
             "amihud_illiquidity": fam_amihud.family_amihud_illiquidity,
             "crypto_options_state": fos.family_crypto_options_state}

MECHANISM = {
    "broker_margin_event": ("forced_liquidation: the broker's own dated margin/CLOSEONLY change "
                            "forces holders to cut size; the flow is liquidity, not information"),
    "carry_swap_drift": ("carry_rollover: a published change in the overnight financing "
                         "differential is a rate-expectation shift carry holders reallocate on"),
    "amihud_illiquidity": ("liquidity premium / thin-book concession: Amihud impact per tick, "
                           "hour-of-week normalised, trailing"),
    "crypto_options_state": ("options-implied state (BTC/ETH surface, read-only) as a PIT "
                             "conditioner on the Fusion crypto CFD"),
}


def _n_events(cell: dict[str, Any]) -> int | None:
    fam, p = cell["family"], cell["params"]
    if fam in ("broker_margin_event", "carry_swap_drift"):
        return len(fbs.event_times(p["symbol"], p["event"]))
    if fam == "crypto_options_state":
        return len(fos.state_events(fos.UNDERLYING[p["symbol"]], p["field"], z_threshold=1.5,
                                    min_prior=5))
    return None


def seed(*, budget_s: float = 600.0, dry_run: bool = False, universe: Path = UNIVERSE,
         state_path: Path = STATE) -> dict[str, Any]:
    """Measure every cell's firing and donate the ones that clear SEED_FLOOR, once each.

    One pass at a time (`proposer_common.run_lock` on the state file); the donation is
    two-phase (`proposer_common.donate_once`), so a crash between the door and the state write
    is settled from the door's own file on the next pass and never donates or charges twice."""
    if dry_run:
        return _seed(budget_s=budget_s, dry_run=True, universe=universe, state_path=state_path)
    from research import proposer_common as pc
    with pc.run_lock(state_path) as held:
        if not held:
            return {"stopped_because": "LOCKED: another broker_state_cells pass holds the state",
                    "elapsed_s": 0.0, "seed_floor_trade_days": SEED_FLOOR, "cells_planned": 0,
                    "by_item": {}, "donated_this_pass": 0, "donation": {"status": "LOCKED"},
                    "errors": {}, "cells": []}
        return _seed(budget_s=budget_s, dry_run=False, universe=universe, state_path=state_path)


#: The donation lineage of the broker-state grids: each donated cell is one trial, charged by the
#: donation that carries it, and the donation's id is this lineage plus exactly its cells.
DONATION_LINEAGE = "bsc-v1"


def _seed(*, budget_s: float, dry_run: bool, universe: Path,
          state_path: Path) -> dict[str, Any]:
    from research import proposer_common as pc
    from research.cross_sectional_breadth import firing, identity
    started = time.monotonic()
    today = datetime.now(tz=UTC).date().isoformat()
    registry = _read(universe / "universe.json") or {}
    st = _read(state_path)
    state: dict[str, Any] = st if isinstance(st, dict) and isinstance(st.get("cells"), dict) \
        else {"cells": {}}
    cells_state: dict[str, Any] = state["cells"]

    def settle(intent: dict[str, Any], at: str) -> None:
        for k in intent.get("cells") or []:
            if isinstance(cells_state.get(k), dict):
                cells_state[k]["donated_at"] = at

    recovered = ({"landed": 0, "dropped": 0} if dry_run
                 else pc.reconcile_donations(state, SOURCE, settle))
    cells = plan(registry, universe)
    bars: dict[str, pd.DataFrame | None] = {}
    by_item: dict[str, Counter] = {}
    rows_out: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    errors: Counter = Counter()
    stopped = "grid exhausted"
    for cell in cells:
        if time.monotonic() - started > budget_s:
            stopped = f"time budget {budget_s:g}s reached; resumes next pass"
            break
        item, fam, sym, params = cell["item"], cell["family"], cell["symbol"], cell["params"]
        cnt = by_item.setdefault(item, Counter())
        cnt["grid"] += 1
        ident = identity(sym, fam, params)
        prior = cells_state.get(ident) or {}
        n_ev = _n_events(cell)
        if prior.get("day") != today or prior.get("n_events") != n_ev:
            if sym not in bars:
                try:
                    from mt5desk.families import _h1
                    bars[sym] = _h1(pd.read_parquet(universe / f"{sym}_H1.parquet"))
                except Exception:
                    bars[sym] = None
            d = bars[sym]
            if d is None:
                prior = {**prior, "day": today, "status": UNMEASURED,
                         "why": f"no H1 bars for {sym} on this host", "n_events": n_ev}
            else:
                try:
                    got = firing(list(FAMILY_FN[fam](d, **params) or []), d)
                except Exception as exc:
                    errors[f"{fam}: {type(exc).__name__}: {str(exc)[:60]}"] += 1
                    continue
                prior = {**prior, **got, "day": today, "n_events": n_ev, "why": None}
            prior.update({"family": fam, "symbol": sym, "params": params, "item": item})
            cells_state[ident] = prior
            cnt["measured_this_pass"] += 1
        if prior.get("status") == UNMEASURED and prior.get("why"):
            cnt["unmeasured_no_bars"] += 1
            status = UNMEASURED
        elif int(prior.get("trade_days_lb") or 0) >= SEED_FLOOR:
            status = "DONATED" if prior.get("donated_at") else "CLEARS_FLOOR"
            if not prior.get("donated_at"):
                cands.append({"ident": ident, **cell, "firing": {
                    k: prior.get(k) for k in ("signal_days", "trade_days_lb", "n_events")}})
        else:
            status = ACCRUING
        prior["status"] = status
        cnt[status.lower()] += 1
        # The report lists the cells worth reading by name: anything with an event, and anything
        # that cleared the floor. The rest are counted in `by_item`.
        if (n_ev or 0) > 0 or status in ("CLEARS_FLOOR", "DONATED"):
            rows_out.append({"family": fam, "symbol": sym, "params": params, "status": status,
                             "n_events": n_ev, "signal_days": prior.get("signal_days"),
                             "trade_days_lb": prior.get("trade_days_lb")})
    donated = 0
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW",
                                "recovered": recovered}
    if cands and not dry_run:
        rows = []
        for c in cands:
            row = pc.candidate(SOURCE, c["symbol"], c["family"], c["params"],
                               f"{c['family']} on {c['symbol']}: {MECHANISM[c['family']]}",
                               f"{c['symbol']} {c['family']} {json.dumps(c['params'])}"[:120],
                               {"firing": c["firing"], "seed_floor": SEED_FLOOR,
                                "item": c["item"]})
            row["evidence"]["screen"] = ("input-only firing count (signals, never returns): "
                                         "no outcome screen, so no selection to charge")
            row["declared_width"] = 1
            rows.append(row)
        idents = [c["ident"] for c in cands]
        path = pc.donate_once(
            state, lambda: _write_atomic(state_path, json.dumps(state, sort_keys=True,
                                                                default=str)),
            SOURCE, rows, len(rows), lineage=DONATION_LINEAGE, cells=idents, charged=idents,
            apply=settle)
        counts = pc.donation_counts()
        donated = int(counts.get("donated") or 0)
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None, "recovered": recovered,
                    "refused_wrong_lane": counts.get("refused_wrong_lane"),
                    "refused_unstamped": counts.get("refused_unstamped")}
        if path:
            for c in cands:
                by_item[c["item"]]["donated_this_pass"] += 1
    if not dry_run:
        _write_atomic(state_path, json.dumps(state, sort_keys=True, default=str))
    return {"stopped_because": stopped, "elapsed_s": round(time.monotonic() - started, 2),
            "seed_floor_trade_days": SEED_FLOOR, "cells_planned": len(cells),
            "by_item": {k: dict(v) for k, v in by_item.items()},
            "donated_this_pass": donated, "donation": donation, "errors": dict(errors),
            "cells": rows_out}


def run(*, budget_s: float = 600.0, dry_run: bool = False, out: Path = OUT) -> dict[str, Any]:
    store = build_store(write=not dry_run)
    carry = rebuild_carry_state(write=not dry_run)
    options = refresh_options_store(write=not dry_run)
    seeded = seed(budget_s=budget_s, dry_run=dry_run)
    rep = {"generated_at": _now(), "source": SOURCE, "dry_run": dry_run,
           "rule": ("each grid cell is one trial charged once at the unchanged Tier S bar "
                    "(declared_width 1); a cell under the seed floor is SERIES_ACCRUING (pending), "
                    "never refused; no tape -> UNMEASURED, never zero events"),
           "event_store": store, "carry_state": carry, "options_store": options,
           "cells": seeded}
    _write_atomic(out, json.dumps(rep, indent=1, sort_keys=True, default=str) + "\n")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's call)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and report, write no store")
    args = ap.parse_args(argv)
    rep = run(budget_s=args.budget_s, dry_run=args.dry_run)
    st, c = rep["event_store"], rep["cells"]
    print(f"broker_state_cells: tape {st['tape'].get('status')} events={st['n_events']} "
          f"{st['by_kind']} carry_state={rep['carry_state'].get('status')} "
          f"cells planned={c['cells_planned']} donated={c['donated_this_pass']} "
          f"stopped={c['stopped_because']!r}")
    for item, cnt in c["by_item"].items():
        print(f"  {item}: {cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

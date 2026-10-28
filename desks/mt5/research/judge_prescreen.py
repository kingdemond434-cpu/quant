"""THE JUDGE'S PRE-BUILD SCREEN: kill what cannot survive before a signal is built, in SHADOW first.

    python desks/mt5/research/judge_prescreen.py --once        # hourly leg: replay + tables
    python desks/mt5/research/judge_prescreen.py --once --ledger X --out-dir Y   # offline replay

WHY (principal, 2026-10-28). The sealed judge clears ~5k verdicts a day against a docket of
1.65M rows, and ~76% of a built cell's CPU is the family's own signal code (per-row pandas), ~20%
the trade replay, 2-5% the bars (reports/judge/PREWARM_CEILING_2026-10-27.md). A screen that has
to build the signal saves almost nothing, so everything here is decided from what is known BEFORE
the build: the cell's identity (symbol, chart, family), its chart's calendar, its family's own
input guard, and the verdicts the judge has already recorded for its siblings.

WHAT ALREADY EXISTS AND IS REUSED, NOT REBUILT.
  * gate 0 / gate 1 (`external_gauntlet.partition_at_economic_prior`, `modifier_preflight`):
    tradeability, chart presence, economic prior, unwired modifiers. Sealed; pre-build already.
  * `research/fire_inputs.probe`: the family's own input guard, run on the inputs the judge would
    hand it. NEEDS_DATA is a PROOF that the series is empty. Reused verbatim (rule `needs_data`).
  * `judge_coverage.order_docket`: the one intake funnel, which already filters the unrunnable
    bank and orders never-firing ground and NEEDS_DATA rows to the tail. This screen is called
    from there, after the bank filter, and in SHADOW returns the rows untouched.
  * Stage 0 (`external_gauntlet.stage0_prefilter`) is report-only on CACHED series -- it judges a
    return stream, so it cannot save a build. Not duplicated.

THE STANDING LAW THIS DESIGN LIVES INSIDE (`tests/test_fire_prescreen_not_separable.py`). The
sealed judge takes ONE lockbox cut over the UNION of every cell's trading days, builds ONE program
matrix aligned on the shortest valid column, and reports a structural trial census over every
cell. So removing a cell that would have produced days can move the cut and the named verdicts
of every other cell in its sweep (harness test 2), and changes the sweep's census (test 3). The
ONLY class proven byte-separable is a provably EMPTY series (test 5). Hence three rule classes:

  PROVABLE_SEPARABLE      `needs_data`  -- the family's own guard returns [] on the inputs the
                          judge would hand it (fire_inputs NEEDS_DATA) and the chart has bars, so
                          the series is empty: the judge's verdict is UNKNOWN with days 0 in any
                          sweep and nothing else moves. Zero false kills BY CONSTRUCTION. The only
                          canon-eligible rule.
  PROVABLE_NOT_SEPARABLE  `chart_short` -- the cell's chart cannot hold 60 trading days (a cell
                          trades only on dates its bars exist, and a UTC date maps onto at most
                          two dates under any fixed clock offset), so the judge MUST return
                          UNKNOWN. Zero false kills by construction, but the cell's days can still
                          enter the union cut, so it is NEVER canon (harness test 2). Shadow only.
  STATISTICAL             `sibling_dead` -- the cell's (symbol, chart, family) bucket already
                          holds >= K cells with a named verdict and NOT ONE of them ever cleared
                          `in_sample_screen`. Not an implication. NOT canon-eligible in code
                          (audit 3570928159 M5: removing a sibling moved the union cut +70 days
                          and, by culling losers from the program matrix, loosens PBO/SPA) until
                          a principal or sealed ruling lands AS A CODE CHANGE. Its false-kill rate
                          is still MEASURED every hour by a look-ahead-free replay (see `replay`).

TRIALS ARE NEVER INFLATED OR DEFLATED, AND EACH CELL IS CHARGED EXACTLY ONCE. Every lifetime
trial the sealed judge charges is a graph fate, and every verdict it writes (gate-0 reject,
UNKNOWN, ten-gate) is one fate. The kill ledger `data/hypotheses/prescreen_verdicts.jsonl` is the
SINGLE source of truth (append-only, written under an OS lock; `prescreen_killed.json` is a
derived cache nobody decides from). Its events fold per cell:
  KILL     the cell leaves the docket; it is charged one trial unless already charged.
  READMIT  the rule stopped firing; the cell returns to the judge and STAYS charged (one trial),
           until the judge's own fate replaces the charge.
  JUDGED   the gate ledger shows the judge ruled on the cell: the charge moves to the judge's fate
           and the cell can never be killed again.
A row the judge has already ruled on is never screened. Any unparsable ledger line RAISES -- a
truncated tail or a merge conflict is never silently counted as fewer kills.

ZERO PROMOTION AUTHORITY, NO GATE MOVES. The screen can only send a cell AWAY from the judge;
it never passes anything, never touches a sealed file, never changes a threshold (DSR >= 0.95
included). The default is SHADOW: it records what it would kill and kills nothing. CANON is the
module constant `CANON` below, flipped only by a reviewed commit -- never by box state. Even then
a deterministic 5% of would-kills (`HOLDOUT_MOD`) still go to the judge, so the false-kill rate
stays measurable after the flip.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
HYP = DATA / "hypotheses"
REPORTS = DESK / "reports"
UNIVERSE = DATA / "universe"
LEDGER = HYP / "gate_verdict_ledger.jsonl"
REPORT = REPORTS / "JUDGE_PRESCREEN.json"
INTAKE_REPORT = REPORTS / "JUDGE_PRESCREEN_INTAKE.json"
TABLES = HYP / "prescreen_tables.json"
VERDICTS = HYP / "prescreen_verdicts.jsonl"
KILLED = HYP / "prescreen_killed.json"
LOCK = HYP / "prescreen_verdicts.lock"

SCHEMA = "judge_prescreen/1.2"

#: THE CANON SWITCH IS CODE (audit 3570928159 M5). A reviewed commit flips it; no state file,
#: no session and no box can. False = SHADOW: every row reaches the judge.
CANON = False

#: The sealed judge's own floor: CPCV, walk-forward and the matrix need 60 daily observations
#: (`external_gauntlet.run_gauntlet` keeps `len(d) >= 60`; `cell_dev_cut(need=60)`).
MIN_DAYS = 60

#: K grid for `sibling_dead`.
K_GRID: tuple[int, ...] = (5, 10, 20, 40, 80)
#: A replay half holding fewer AT-RISK true survivors than this cannot select or confirm any K.
MIN_AT_RISK_PER_HALF = 20
#: A replay report older than this cannot authorise anything.
REPORT_MAX_AGE_S = 6 * 3600.0
#: One would-kill in HOLDOUT_MOD (by a hash of its cell id) still goes to the judge in canon, so
#: the rule's false kills stay visible in the gate ledger after the flip (audit M4, self-censoring).
HOLDOUT_MOD = 20
#: Seconds a writer waits for the kill ledger's lock before the pass fails open (kills nothing).
LOCK_WAIT_S = 10.0

RULES: dict[str, dict[str, Any]] = {
    "needs_data": {
        "class": "PROVABLE_SEPARABLE",
        "verdict": "PRESCREEN_UNKNOWN",
        "canon_eligible": True,
        "implies": "UNKNOWN (never_fires / needs_data)",
        "why": (
            "research/fire_inputs NEEDS_DATA: the family's own input guard returns [] on the "
            "inputs build_cell would hand it, and the chart has bars, so the series is empty; "
            "harness test 5 proves such a cell is judged the same in any sweep and moves nothing"
        ),
    },
    "chart_short": {
        "class": "PROVABLE_NOT_SEPARABLE",
        "verdict": "PRESCREEN_UNKNOWN",
        "canon_eligible": False,
        "implies": "UNKNOWN (too_rare / short history)",
        "why": (
            "the chart cannot hold 60 trading days: a cell trades only on dates its bars exist "
            "and one UTC date maps onto at most two dates under any fixed offset, so "
            "min(2 x UTC dates, span + 2) < 60 forces UNKNOWN; NEVER canon, because its days can "
            "still move the union lockbox cut (harness test 2)"
        ),
    },
    "sibling_dead": {
        "class": "STATISTICAL",
        "verdict": "PRESCREEN_REJECT",
        "canon_eligible": False,
        "implies": "nothing (measured, not implied)",
        "why": (
            "the (symbol, chart, family) bucket holds >= K cells with a named verdict and none "
            "ever cleared in_sample_screen. NOT canon-eligible (audit 3570928159 M5): removing "
            "a sibling moves the union lockbox cut and culls losers from the program matrix, "
            "loosening PBO/SPA; it needs a principal or sealed ruling landed as a code change"
        ),
    },
}

#: Terminal gates that are not a judgement of the series (gate 0 runs before any build).
_PRE_BUILD_GATES = frozenset({"", "symbol_eligibility", "economic_prior"})

#: Outcome tiers, best-ever per cell. 3 is a true survivor.
UNKNOWN_T, IS_FAIL_T, CLEARED_IS_T, PASSED_T = 0, 1, 2, 3
TIER_NAMES = {
    UNKNOWN_T: "unknown",
    IS_FAIL_T: "in_sample_fail",
    CLEARED_IS_T: "cleared_in_sample",
    PASSED_T: "true_survivor",
}

_CELL_RE = re.compile(r"^(?P<sym>[^@]+?)(?:@(?P<tf>[A-Za-z0-9]+))?\.(?P<fam>[a-z0-9_]+)\.p=")
_EVENTS = frozenset({"KILL", "READMIT", "JUDGED", "UNATTRIBUTED", "QUARANTINED"})
#: Git conflict-marker lines: never an event, dropped (both sides' events are kept) on repair.
_MARKER = re.compile(r"^(<{7}|={7}|>{7}|\|{7})( |$)")
_CELL_HINT = re.compile(r'"cell"\s*:\s*"((?:[^"\\]|\\.)*)"')


class KillLedgerCorrupt(ValueError):
    """A kill-ledger line that cannot be parsed: the ledger is refused, never partially counted."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def bucket_of(cell: str) -> str | None:
    """`SYM|TF|family` from a judge cell id (`SYM@TF.family.p=...`; H1 carries no `@TF`)."""
    m = _CELL_RE.match(str(cell or ""))
    if not m:
        return None
    return f"{m['sym']}|{(m['tf'] or 'H1').upper()}|{m['fam']}"


def tier_of(row: dict[str, Any]) -> int | None:
    """The outcome tier one ledger row records, or None when it is not a series judgement."""
    if row.get("passed") is True:
        return PASSED_T
    if str(row.get("downstream_status") or "").startswith("NOT_RUN"):
        return None
    gate = str(row.get("terminal_gate") or "")
    if gate in _PRE_BUILD_GATES:
        return None
    if gate == "UNKNOWN":
        return UNKNOWN_T
    if gate == "in_sample_screen":
        return IS_FAIL_T
    return CLEARED_IS_T


def iter_ledger(path: Path) -> Iterator[dict[str, Any]]:
    """The judge's gate ledger, in append (= time) order. Read-only here; a malformed line of
    the JUDGE's ledger is skipped (it is the judge's file; `replay` counts rows it saw)."""
    try:
        fh = path.open(encoding="utf-8")
    except OSError:
        return
    with fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def is_holdout(cell: str) -> bool:
    """Deterministic 1-in-HOLDOUT_MOD sample of would-kills that the judge still rules."""
    h = hashlib.sha256(str(cell).encode("utf-8")).hexdigest()
    return int(h[:8], 16) % HOLDOUT_MOD == 0


# ------------------------------------------------------------------ protected buckets
def _cert_rows() -> Iterator[tuple[str, str, str, str | None]]:
    """(symbol, chart, family, dated-at or None) of every known certificate and sleeve."""
    try:
        doc = json.loads((DATA / "sleeves.json").read_text("utf-8"))
        for s in doc.get("sleeves") or []:
            if isinstance(s, dict) and s.get("family") and s.get("symbol"):
                cert = s.get("certificate") if isinstance(s.get("certificate"), dict) else {}
                at = cert.get("gated_at") or s.get("promoted_at")
                yield (
                    str(s["symbol"]),
                    str(s.get("timeframe") or "H1").upper(),
                    str(s["family"]),
                    str(at) if at else None,
                )
    except (OSError, ValueError, AttributeError):
        pass
    for p in (DATA / "UNIVERSAL_SURVIVORS.canon.json", REPORTS / "UNIVERSAL_SURVIVORS.json"):
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        surv = doc.get("survivors") if isinstance(doc, dict) else None
        rows = surv.values() if isinstance(surv, dict) else (surv or [])
        for r in rows:
            if not isinstance(r, dict):
                continue
            spec = r.get("shadow_spec") if isinstance(r.get("shadow_spec"), dict) else {}
            sym = r.get("sym") or spec.get("symbol")
            fam = spec.get("family") or (str(r.get("cell") or "").split(".")[1:2] or [""])[0]
            tf = str(
                spec.get("timeframe") or (spec.get("params") or {}).get("timeframe") or "H1"
            ).upper()
            at = r.get("gated_at")
            if sym and fam:
                yield (str(sym), tf, str(fam), str(at) if at else None)


def protected_buckets() -> set[str]:
    """Every bucket holding a known certificate or sleeve, now (the LIVE intake's guard)."""
    return {f"{s}|{t}|{f}" for s, t, f, _ in _cert_rows()}


def protected_buckets_dated() -> dict[str, str | None]:
    """Bucket -> the EARLIEST date a certificate or sleeve is known to have existed in it, or None
    when no date is recorded. The replay protects a cell only by protection dated before it."""
    out: dict[str, str | None] = {}
    for s, t, f, at in _cert_rows():
        b = f"{s}|{t}|{f}"
        cur = out.get(b)
        if b not in out or (at is not None and (cur is None or at < cur)):
            out[b] = at
    return out


# ------------------------------------------------------------------ the replay
def replay(
    rows: Iterable[dict[str, Any]],
    *,
    k_grid: tuple[int, ...] = K_GRID,
    protected: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Time-ordered, look-ahead-free shadow of `sibling_dead` against the judge's own verdicts.

    * Each cell is screened ONCE, at its first recorded series judgement, on its bucket's state
      from rows strictly before it -- the evidence a pre-build screen would have had.
    * A bucket protects a cell only when its certificate/sleeve is DATED at or before that cell's
      first verdict (`protected`: bucket -> earliest date; an undated entry protects nothing
      here, the conservative direction: more measured false kills, never fewer).
    * A cell's outcome is its BEST tier over the whole record (a cell that later passed is a true
      survivor). A true survivor is REACHED by K when, at its first verdict, its bucket already
      held >= K named siblings and no dated protection (audit M4-bis): only there does the rule
      decide on its own evidence, so only there can a zero mean anything. Reached and uncleared
      is a kill by identity; reached and cleared is the rule correctly sparing it.
    * SELECT on the earlier half, CONFIRM on the later, PER K: that K's reached survivors are
      split at their time-ordered median; `canon_k` is the smallest K whose halves each hold
      >= MIN_AT_RISK_PER_HALF reached survivors, with zero survivor kills in the first half,
      kept only if it also kills none in the second. Otherwise None: not measured, not ready.
    """
    protected = protected or {}
    buckets: dict[str, list[int]] = {}  # bucket -> [named, cleared, judged] cells
    best: dict[str, int] = {}
    # cell -> (order, named, cleared, judged, protected_then) BEFORE its first verdict
    first_state: dict[str, tuple[int, int, int, int, bool]] = {}
    bucket_cell: dict[str, str] = {}
    n_rows = n_judgements = 0
    for row in rows:
        n_rows += 1
        cell = str(row.get("cell") or "")
        t = tier_of(row)
        if not cell or t is None:
            continue
        b = bucket_of(cell)
        if b is None:
            continue
        n_judgements += 1
        st = buckets.setdefault(b, [0, 0, 0])
        if cell not in first_state:
            p_at = _epoch(protected.get(b)) if protected.get(b) else None
            at = _epoch(row.get("at"))
            prot = bool(p_at is not None and at is not None and p_at <= at)
            first_state[cell] = (len(first_state), st[0], st[1], st[2], prot)
            bucket_cell[cell] = b
        old = best.get(cell, -1)
        if old < 0:
            st[2] += 1
        if t > old:
            if old < IS_FAIL_T <= t:
                st[0] += 1
            if old < CLEARED_IS_T <= t:
                st[1] += 1
            best[cell] = t
    n = len(first_state)
    pop = dict.fromkeys(TIER_NAMES.values(), 0)
    for c in first_state:
        pop[TIER_NAMES[best[c]]] += 1
    survivors = [
        (o, named, cleared)
        for c, (o, named, cleared, _judged, prot) in first_state.items()
        if best[c] == PASSED_T and not prot
    ]

    by_k: dict[str, Any] = {}
    any_basis: dict[str, Any] = {}
    reach_by_k: dict[str, Any] = {}
    selected_k: int | None = None
    canon_k: int | None = None
    for k in sorted(k_grid):
        # M4-bis: the survivors this K REACHED -- at their first verdict the bucket already held
        # >= K named siblings, and no dated protection. Only on these does the rule decide on its
        # own evidence (cleared sibling or not), so only these can show it is safe. A survivor in
        # a fresh bucket (named < K) is out of every K's reach and proves nothing.
        reached = sorted(o for o, named, _cl in survivors if named >= k)
        exposed = sum(1 for _o, named, cl in survivors if named >= k and cl == 0)
        split = reached[len(reached) // 2] if reached else n
        r_half = (sum(1 for o in reached if o < split), sum(1 for o in reached if o >= split))
        floor_met = min(r_half) >= MIN_AT_RISK_PER_HALF
        killed = dict.fromkeys(TIER_NAMES.values(), 0)
        halves = [dict.fromkeys(TIER_NAMES.values(), 0) for _ in (0, 1)]
        kb = dict.fromkeys(TIER_NAMES.values(), 0)
        n_killed = 0
        sample_false: list[str] = []
        for c, (order, named, cleared, judged, prot) in first_state.items():
            if prot or cleared > 0:
                continue
            name = TIER_NAMES[best[c]]
            if judged >= k:
                kb[name] += 1  # basis B, report-only: UNKNOWN siblings count as evidence too
            if named < k:
                continue
            n_killed += 1
            killed[name] += 1
            halves[0 if order < split else 1][name] += 1
            if best[c] >= CLEARED_IS_T and len(sample_false) < 20:
                sample_false.append(c)
        reach_by_k[str(k)] = {
            "reached": len(reached),
            "reached_by_half": {"select": r_half[0], "confirm": r_half[1]},
            "exposed_uncleared": exposed,
            "floor_met": floor_met,
        }
        by_k[str(k)] = {
            "k": k,
            "killed": n_killed,
            "kill_rate": round(n_killed / n, 6) if n else None,
            "killed_by_tier": killed,
            "false_kill_rate_by_tier": {
                nm: (round(killed[nm] / pop[nm], 6) if pop[nm] else None)
                for nm in TIER_NAMES.values()
            },
            "true_survivors_reached": reach_by_k[str(k)],
            "killed_by_tier_select_half": halves[0],
            "killed_by_tier_confirm_half": halves[1],
            "sample_false_kills_cleared_or_better": sample_false,
        }
        any_basis[str(k)] = {
            "killed": sum(kb.values()),
            "kill_rate": round(sum(kb.values()) / n, 6) if n else None,
            "killed_by_tier": kb,
        }
        if floor_met and selected_k is None and halves[0]["true_survivor"] == 0:
            selected_k = k
            if halves[1]["true_survivor"] == 0:
                canon_k = k
    dead = {
        b: st
        for b, st in buckets.items()
        if st[1] == 0 and st[0] >= min(k_grid) and b not in protected
    }
    return {
        "ledger_rows": n_rows,
        "series_judgements": n_judgements,
        "cells_replayed": n,
        "population_by_tier": pop,
        "true_survivors_unprotected": len(survivors),
        "true_survivors_reached_by_k": reach_by_k,
        "at_risk_floor_per_half": MIN_AT_RISK_PER_HALF,
        "by_k": by_k,
        "by_k_any_judged_basis_report_only": any_basis,
        "selected_k_on_select_half": selected_k,
        "canon_k": canon_k,
        "canon_ready": canon_k is not None,
        "canon_eligible_in_code": RULES["sibling_dead"]["canon_eligible"],
        "canon_rule": (
            "per K, only the true survivors that K REACHED count (>= K named siblings at their "
            "first verdict, no protection dated before it); split them at their time-ordered "
            f"median, require >= {MIN_AT_RISK_PER_HALF} in each half, pick the smallest K with "
            "zero survivor kills on the earlier half and confirm zero on the later. A survivor "
            "no K could reach proves nothing, so a world of fresh-bucket survivors reads None. "
            "Even when ready, the rule acts only if RULES['sibling_dead']['canon_eligible'] is "
            "set True by a reviewed commit."
        ),
        "holdout": (
            f"1 in {HOLDOUT_MOD} would-kills (sha256 of the cell id) still reach the judge in "
            "canon, so false kills stay in the gate ledger this replay reads"
        ),
        "dead_buckets": {b: st[0] for b, st in dead.items()},
        "buckets": len(buckets),
    }


# ------------------------------------------------------------------ chart calendars
def chart_days(path: Path) -> dict[str, Any] | None:
    """Distinct UTC dates and the calendar span of one bar file, from its time column alone."""
    try:
        import numpy as np
        import pyarrow.parquet as pq

        tbl = pq.read_table(path, columns=["time"])
        ts = tbl.column("time").to_numpy()
        if len(ts) == 0:
            return {"utc_days": 0, "span_days": 0}
        d = ts.astype("datetime64[D]")
        lo, hi = d.min(), d.max()
        return {
            "utc_days": len(np.unique(d)),
            "span_days": int((hi - lo).astype(int)) + 1,
            "first": str(lo),
            "last": str(hi),
        }
    except Exception:
        return None


def chart_table(universe: Path = UNIVERSE, prior: dict[str, Any] | None = None) -> dict[str, Any]:
    """`SYM|TF` -> calendar facts for every bar file, re-read only when its size/mtime moved."""
    prior = prior or {}
    out: dict[str, Any] = {}
    for p in sorted(universe.glob("*_*.parquet")):
        sym, _, tf = p.stem.rpartition("_")
        if not sym or not tf:
            continue
        key = f"{sym}|{tf.upper()}"
        try:
            st = p.stat()
        except OSError:
            continue
        stamp = [st.st_size, int(st.st_mtime)]
        old = prior.get(key)
        if isinstance(old, dict) and old.get("stamp") == stamp:
            out[key] = old
            continue
        facts = chart_days(p)
        if facts is not None:
            out[key] = {**facts, "stamp": stamp}
    return out


def chart_is_short(facts: dict[str, Any] | None) -> bool:
    """True only on proof: neither the date count bound nor the span bound reaches 60."""
    if not isinstance(facts, dict):
        return False
    try:
        bound = min(2 * int(facts["utc_days"]), int(facts["span_days"]) + 2)
    except (KeyError, TypeError, ValueError):
        return False
    return bound < MIN_DAYS


# ------------------------------------------------------------------ the kill ledger
def fold_ledger(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Per-cell state folded from the append-only kill ledger -- the ONE source of truth.

    {cell: {killed, charged, judged, family, rule}}. Absent ledger: {}. ANY line that is not a
    complete JSON event (a truncated tail, a git conflict marker, a foreign row) RAISES
    KillLedgerCorrupt: a ledger that cannot be read whole is never counted in part.
    """
    p = path or VERDICTS
    try:
        text = p.read_text("utf-8")
    except FileNotFoundError:
        return {}
    state: dict[str, dict[str, Any]] = {}
    for i, ln in enumerate(text.split("\n"), 1):
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError as exc:
            raise KillLedgerCorrupt(f"{p.name}:{i}: not JSON ({ln[:60]!r})") from exc
        if isinstance(r, dict) and r.get("event") == "QUARANTINED":
            continue  # the repair's own marker: no cell, no charge
        if not isinstance(r, dict) or r.get("event") not in _EVENTS or not r.get("cell"):
            raise KillLedgerCorrupt(f"{p.name}:{i}: not a kill-ledger event ({ln[:60]!r})")
        cell = str(r["cell"])
        s = state.setdefault(
            cell,
            {"killed": False, "charged": False, "judged": False, "family": None, "rule": None},
        )
        ev = r["event"]
        if ev == "KILL":
            if not s["judged"]:
                s["killed"] = True
                s["charged"] = True
            s["family"] = str(r.get("family") or s["family"] or "prescreen")
            s["rule"] = r.get("rule") or s["rule"]
        elif ev == "UNATTRIBUTED":
            # A line the repair could not read: charged as one trial (the most it could have
            # been), never a removal -- the cell, if named, stays in the docket.
            if not s["judged"]:
                s["charged"] = True
            s["family"] = str(r.get("family") or s["family"] or "prescreen_unattributed")
        elif ev == "READMIT":
            s["killed"] = False  # still charged: the judge has not yet given it a fate
        else:  # JUDGED: the judge's fate carries the trial from here on
            s["killed"] = False
            s["charged"] = False
            s["judged"] = True
    return state


def judge_ruled(cells: Iterable[str], path: Path | None = None) -> set[str]:
    """The subset of `cells` the judge has given a fate in its gate ledger (any verdict but a
    NOT_RUN deferral -- the same rule as `judge_coverage._LedgerScan.cell_ruled`).

    A cheap regex prefilter on the cell id; only matching lines are parsed. Any failure to read
    returns what was found so far (possibly nothing): a missed join leaves a cell CHARGED here,
    the inflation direction, never the deflation one."""
    want = {c for c in cells if not c.startswith("unattributed:")}
    if not want:
        return set()
    out: set[str] = set()
    try:
        with (path or LEDGER).open("r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                m = _CELL_HINT.search(raw)
                if not m:
                    continue
                c = m.group(1)
                if "\\" in c:
                    try:
                        c = json.loads(f'"{c}"')
                    except ValueError:
                        continue
                if c not in want or c in out:
                    continue
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(row, dict) or str(row.get("cell") or "") != c:
                    continue
                if str(row.get("downstream_status") or "").startswith("NOT_RUN"):
                    continue
                out.add(c)
    except OSError:
        pass
    return out


def lifetime_kills(
    path: Path | None = None,
    *,
    ruled: set[str] | None = None,
    gate_ledger: Path | None = None,
) -> tuple[int, dict[str, int]]:
    """(cells, per family) charged to the screen: each is the one trial the judge would have
    recorded.

    * READ-TIME JOIN (audit v1.1, M3 transient): a charged cell the judge has since ruled is the
      judge's trial already (its graph fate counts it), so it is not counted here -- whether or
      not an intake has written JUDGED yet. `ruled` defaults to a scan of the gate ledger for
      the charged cells only (no scan at all when nothing is charged, i.e. always in SHADOW).
    * A CORRUPT LEDGER is re-read under the writer's lock (a reader can catch a writer
      mid-append) and, if still corrupt, QUARANTINED: moved aside byte-for-byte, rebuilt with
      every unreadable line charged as one trial, and a PLUMBING_DEFECT event raised. The count
      is then an upper bound, never smaller and never a silent zero. If the lock or the repair
      fails, this RAISES and the caller keeps its last good count.
    """
    p = path or VERDICTS
    try:
        state = fold_ledger(p)
    except KillLedgerCorrupt:
        with _ledger_lock():
            state = _fold_or_quarantine_locked(p)
    charged = {c: s for c, s in state.items() if s["charged"]}
    if ruled is None:
        ruled = judge_ruled(charged, gate_ledger) if charged else set()
    by_fam: dict[str, int] = {}
    for c, s in charged.items():
        if c in ruled:
            continue
        f = str(s["family"] or "prescreen")
        by_fam[f] = by_fam.get(f, 0) + 1
    return sum(by_fam.values()), by_fam


def _fold_or_quarantine_locked(p: Path) -> dict[str, dict[str, Any]]:
    """Caller holds the lock. Fold; on corruption quarantine and rebuild, then fold the rebuild."""
    try:
        return fold_ledger(p)
    except KillLedgerCorrupt as exc:
        quarantine(p, why=str(exc))
        return fold_ledger(p)


def quarantine(p: Path, *, why: str = "") -> dict[str, Any]:
    """Move a corrupt kill ledger aside and rebuild it, CHARGING CONSERVATIVELY. Caller holds
    the lock.

    Kept: every complete event line. Dropped: git conflict-marker lines (both sides' events are
    kept, which can only add charges). Every other unreadable line becomes one UNATTRIBUTED
    charge -- for the cell it names if one can be read from it, else for a synthetic id -- so the
    rebuilt ledger never charges fewer trials than the original could have recorded. The
    original is kept as `<stem>.corrupt-<UTC>.jsonl` and a PLUMBING_DEFECT event is raised."""
    raw = p.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = p.with_name(f"{p.stem}.corrupt-{stamp}{p.suffix}")
    kept: list[str] = []
    n_markers = n_garbled = 0
    for i, ln in enumerate(text.split("\n"), 1):
        line = ln.rstrip("\r")
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            r = None
        if (
            isinstance(r, dict)
            and r.get("event") in _EVENTS
            and (r.get("cell") or r.get("event") == "QUARANTINED")
        ):
            kept.append(json.dumps(r, separators=(",", ":"), default=str))
            continue
        if _MARKER.match(line):
            n_markers += 1
            continue
        n_garbled += 1
        m = _CELL_HINT.search(line)
        sha = hashlib.sha256(f"{i}:{line}".encode()).hexdigest()[:16]
        kept.append(
            json.dumps(
                {
                    "at": _now(),
                    "event": "UNATTRIBUTED",
                    "cell": m.group(1) if m else f"unattributed:{sha}",
                    "line": i,
                    "line_sha": sha,
                    "quarantined_to": dest.name,
                },
                separators=(",", ":"),
            )
        )
    marker = {
        "at": _now(),
        "event": "QUARANTINED",
        "quarantined_to": dest.name,
        "original_sha256": hashlib.sha256(raw).hexdigest(),
        "conflict_marker_lines": n_markers,
        "unreadable_lines_charged": n_garbled,
        "why": why[:300],
    }
    os.replace(p, dest)
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write("\n".join([*kept, json.dumps(marker, separators=(",", ":"))]) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, p)
    try:
        from libs.ops.events import emit

        emit(
            "PLUMBING_DEFECT",
            producer="judge_prescreen",
            organ="judge_prescreen.kill_ledger",
            evidence=marker,
        )
    except Exception as exc:  # the alert is best-effort; the quarantine already happened
        print(f"judge_prescreen: PLUMBING_DEFECT not emitted ({type(exc).__name__})", flush=True)
    print(
        f"judge_prescreen: KILL LEDGER QUARANTINED -> {dest.name} "
        f"({n_garbled} unreadable line(s) charged, {n_markers} conflict marker(s) dropped)",
        file=sys.stderr,
        flush=True,
    )
    return marker


@contextlib.contextmanager
def _ledger_lock(timeout_s: float = LOCK_WAIT_S) -> Iterator[None]:
    """The kill ledger's writer lock (an OS lock on a sidecar, `libs.ops.alert_ledger.os_lock`).
    A writer that cannot get it RAISES -- it never writes unlocked."""
    from libs.ops.alert_ledger import os_lock

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with os_lock(LOCK, timeout_s=timeout_s):
        yield


def _append_durable(rows: list[dict[str, Any]]) -> None:
    VERDICTS.parent.mkdir(parents=True, exist_ok=True)
    with VERDICTS.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def reconcile_and_kill(
    kill_now: dict[str, dict[str, Any]], present: set[str], ruled: set[str]
) -> dict[str, Any]:
    """Under the lock: fold the ledger, append KILL / READMIT / JUDGED, rewrite the cache.

    Returns {"removable": cells whose KILL is durable, ...}. A row leaves the docket ONLY when
    the ledger durably says it is killed, so a lost or unwritable ledger can never leave a cell
    out of the docket uncharged.
    """
    at = _now()
    with _ledger_lock():
        state = _fold_or_quarantine_locked(VERDICTS)
        out_rows: list[dict[str, Any]] = []
        # JUDGED first: a charged cell the judge has since ruled hands its trial to the judge.
        handed = [c for c, s in state.items() if not s["judged"] and c in ruled]
        for c in handed:
            out_rows.append(
                {
                    "at": at,
                    "event": "JUDGED",
                    "cell": c,
                    "family": state[c]["family"],
                    "why": "the gate ledger holds the judge's fate; the judge carries the trial",
                }
            )
            state[c].update(killed=False, charged=False, judged=True)
        new_kills = 0
        for cell, k in kill_now.items():
            s = state.get(cell)
            if cell in ruled or (s and s["judged"]) or (s and s["killed"]):
                continue
            row = k["row"]
            out_rows.append(
                {
                    "at": at,
                    "event": "KILL",
                    "cell": cell,
                    "sym": row.get("sym") or row.get("symbol"),
                    "family": row.get("family"),
                    "rule": k["rule"],
                    "verdict": RULES[k["rule"]]["verdict"],
                    "class": RULES[k["rule"]]["class"],
                    "evidence": k["evidence"],
                    "passed": False,
                    "already_charged": bool(s and s["charged"]),
                }
            )
            new_kills += 1
        lifted = [c for c, s in state.items() if s["killed"] and c in present and c not in kill_now]
        for c in lifted:
            out_rows.append(
                {
                    "at": at,
                    "event": "READMIT",
                    "cell": c,
                    "family": state[c]["family"],
                    "rule": state[c]["rule"],
                    "why": "the rule no longer fires; the judge rules it, still charged once",
                }
            )
        if out_rows:
            _append_durable(out_rows)
        final = fold_ledger()
        killed = {c: s for c, s in final.items() if s["killed"]}
        _atomic_json(
            KILLED,
            {
                "schema": SCHEMA,
                "updated_at": at,
                "derived_from": VERDICTS.name,
                "note": "a CACHE of the kill ledger's fold; nothing decides from this file",
                "cells": {c: {"family": s["family"], "rule": s["rule"]} for c, s in killed.items()},
            },
        )
    return {
        "removable": {c for c in kill_now if c in killed},
        "killed_new": new_kills,
        "readmitted": len(lifted),
        "handed_to_judge": len(handed),
        "killed_standing": len(killed),
        "charged_standing": sum(1 for s in final.values() if s["charged"]),
    }


# ------------------------------------------------------------------ the per-row screen
def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _report_fresh(rep: Any, now: float | None = None) -> bool:
    if not isinstance(rep, dict):
        return False
    try:
        at = datetime.fromisoformat(str(rep.get("generated_at"))).timestamp()
    except (TypeError, ValueError):
        return False
    return ((now or time.time()) - at) <= REPORT_MAX_AGE_S


class Screen:
    """One intake pass's screen: tables loaded once, every row decided in microseconds."""

    def __init__(
        self,
        tables: dict[str, Any] | None,
        report: dict[str, Any] | None,
        probe: Callable[[str, str], dict[str, Any]] | None = None,
        *,
        canon: bool = False,
    ) -> None:
        tables = tables if isinstance(tables, dict) else {}
        self.charts: dict[str, Any] = tables.get("charts") or {}
        self.dead: dict[str, int] = tables.get("dead_buckets") or {}
        self.protected: set[str] = set(tables.get("protected_buckets") or [])
        self.probe = probe
        rep = report if isinstance(report, dict) else {}
        sib = rep.get("sibling_dead") or {}
        self.sibling_k: int | None = sib.get("canon_k") if isinstance(sib, dict) else None
        # SHADOW counts at the canon K once the replay has named one, and until then at the MOST
        # aggressive K -- the upper bound of what the rule could ever remove.
        self.shadow_k: int = int(self.sibling_k or min(K_GRID))
        fresh = _report_fresh(rep)
        self.canon = bool(canon)
        self.ready = {
            "needs_data": True,  # proven, not measured
            "chart_short": False,  # never: not separable
            "sibling_dead": bool(
                fresh and self.sibling_k is not None and sib.get("canon_ready") is True
            ),
        }
        # the replay's measured cost at the K sibling_dead would act on (missed-growth line)
        self.sib_cost = (
            ((sib.get("by_k") or {}).get(str(self.shadow_k)) or {}).get("killed_by_tier")
            if isinstance(sib, dict)
            else None
        )

    def decide(self, row: dict[str, Any], cell: str) -> tuple[str, dict[str, Any]] | None:
        """(rule, evidence) for the FIRST rule that fires on this row, or None (escalate)."""
        sym = str(row.get("sym") or row.get("symbol") or "")
        fam = str(row.get("family") or "")
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        tf = str(params.get("timeframe") or row.get("timeframe") or "H1").upper()
        facts = self.charts.get(f"{sym}|{tf}")
        if self.probe is not None and facts and int(facts.get("utc_days") or 0) > 0:
            res = self.probe(sym, fam)
            if isinstance(res, dict) and res.get("status") == "NEEDS_DATA":
                return "needs_data", {
                    "missing_input": res.get("missing_input"),
                    "why": str(res.get("why") or "")[:240],
                }
        if chart_is_short(facts):
            return "chart_short", {
                "chart": f"{sym}|{tf}",
                "utc_days": facts.get("utc_days") if facts else None,
                "span_days": facts.get("span_days") if facts else None,
            }
        b = bucket_of(cell)
        if b is not None and b not in self.protected:
            named = self.dead.get(b)
            if named is not None and named >= min(K_GRID):
                return "sibling_dead", {
                    "bucket": b,
                    "named_cells": named,
                    "cleared_cells": 0,
                    "k": self.shadow_k,
                }
        return None

    def acts(self, rule: str) -> bool:
        return bool(self.canon and RULES[rule]["canon_eligible"] and self.ready.get(rule))


def missed_growth_lines(
    *,
    acting: dict[str, bool],
    removed: int,
    would: dict[str, int],
    seconds_per_cell: float | None,
    sibling_cost: dict[str, int] | None,
    sibling_k: int | None,
) -> list[dict[str, Any]]:
    """THE TWO-SIDED LEDGER LINE (GROWTH_GOVERNANCE Rule 1; deepening_worker precedent).

    COST: true survivors and in-sample-cleared cells the ACTING rules kill -- zero by construction
    for `needs_data`, and the replay's measured count for any statistical rule -- priced in
    E[log W] as UNMEASURED, said, never zero. GAIN: judge build seconds freed. Both lines are
    written whether or not anything acted, so a shadow reading carries what canon WOULD cost.
    """
    now = datetime.now(UTC)
    day, at = now.date().isoformat(), now.isoformat(timespec="seconds")
    sib_acts = bool(acting.get("sibling_dead"))
    cost = {
        "day": day,
        "at": at,
        "rail": "judge_prescreen",
        "side": "cost",
        "kind": "opportunity_cost",
        "value": None,
        "verdict": "UNMEASURED",
        "units": "cells killed that the judge would have passed or cleared in_sample",
        "e_log_w": "UNMEASURED",
        "acting": {
            "needs_data": {
                "true_survivors_killed": 0,
                "cleared_in_sample_killed": 0,
                "basis": "PROVEN (empty series)",
            }
            if acting.get("needs_data")
            else None,
            "sibling_dead": None,
        },
        "would_act_sibling_dead": {
            "k": sibling_k,
            "true_survivors_killed": (sibling_cost or {}).get("true_survivor"),
            "cleared_in_sample_killed": (sibling_cost or {}).get("cleared_in_sample"),
            "basis": "MEASURED by the look-ahead-free ledger replay"
            if sibling_cost
            else "UNMEASURED: no replay at this K",
        },
    }
    if sib_acts:
        cost["acting"]["sibling_dead"] = cost["would_act_sibling_dead"]
    freed = None if seconds_per_cell is None else round(removed * seconds_per_cell, 1)
    would_freed = (
        None if seconds_per_cell is None else round(sum(would.values()) * seconds_per_cell, 1)
    )
    gain = {
        "day": day,
        "at": at,
        "rail": "judge_prescreen",
        "side": "gain",
        "kind": "compute_freed",
        "value": freed,
        "verdict": "MEASURED" if freed is not None else "UNMEASURED",
        "units": "judge build seconds freed (rows removed x measured judge seconds per cell)",
        "rows_removed": removed,
        "seconds_per_cell": seconds_per_cell,
        "would_free_seconds_if_all_rules_acted": would_freed,
    }
    return [cost, gain]


def intake(
    rows: list[dict[str, Any]],
    *,
    cell_of: Callable[[dict[str, Any]], str | None],
    probe: Callable[[str, str], dict[str, Any]] | None = None,
    publish: bool = True,
    tables_path: Path | None = None,
    report_path: Path | None = None,
    ruled: set[str] | None = None,
    seconds_per_cell: float | None = None,
    canon: bool | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Screen the docket at intake. SHADOW: rows returned untouched, would-kills counted.

    `ruled`: every cell the judge has recorded a fate for (gate ledger). Such a row is never
    screened, and in canon a charged cell found there is handed to the judge (JUDGED). In canon
    with `ruled` unknown (None) nothing is killed: exactly-once cannot be verified.
    `canon` defaults to the module constant CANON; only tests pass it.

    CANON: killed rows leave the docket only once their KILL is durable in the ledger; a
    deterministic HOLDOUT of would-kills still goes to the judge. Never raises (SystemExit
    included): any failure returns the rows untouched.
    """
    t0 = time.perf_counter()
    try:
        canon = CANON if canon is None else bool(canon)
        scr = Screen(_read(tables_path or TABLES), _read(report_path or REPORT), probe, canon=canon)
        ruled_known = ruled is not None
        ruled = ruled or set()
        would: dict[str, int] = dict.fromkeys(RULES, 0)
        samples: dict[str, list[dict[str, Any]]] = {r: [] for r in RULES}
        kept: list[dict[str, Any]] = []
        kill_now: dict[str, dict[str, Any]] = {}
        by_k: dict[str, int] = {str(k): 0 for k in K_GRID}
        holdout = skipped_ruled = 0
        cells: list[str | None] = []
        for row in rows:
            cell = cell_of(row)
            cells.append(cell)
            if cell and cell in ruled:
                skipped_ruled += 1
                continue
            got = scr.decide(row, cell) if cell else None
            if got is None:
                continue
            rule, ev = got
            if rule == "sibling_dead":
                for k in K_GRID:
                    if int(ev["named_cells"]) >= k:
                        by_k[str(k)] += 1
                if int(ev["named_cells"]) < scr.shadow_k:
                    continue
            would[rule] += 1
            if len(samples[rule]) < 25:
                samples[rule].append({"cell": cell, **ev})
            if scr.acts(rule):
                if is_holdout(str(cell)):
                    holdout += 1
                else:
                    kill_now[str(cell)] = {"rule": rule, "row": row, "evidence": ev}
        ledger: dict[str, Any] = {}
        removable: set[str] = set()
        if canon:
            if not ruled_known:
                ledger = {"refused": "the judge's ruled set is UNMEASURED; nothing killed"}
            else:
                ledger = reconcile_and_kill(kill_now, {str(c) for c in cells if c}, ruled)
                removable = set(ledger.pop("removable"))
        kept = [r for r, c in zip(rows, cells, strict=True) if str(c) not in removable]
        elapsed = time.perf_counter() - t0
        acting = {r: scr.acts(r) for r in RULES}
        doc: dict[str, Any] = {
            "schema": SCHEMA,
            "generated_at": _now(),
            "mode": "CANON" if canon else "SHADOW",
            "rows": len(rows),
            "rows_already_ruled_not_screened": skipped_ruled,
            "would_kill": would,
            "would_kill_total": sum(would.values()),
            "would_kill_share": round(sum(would.values()) / len(rows), 6) if rows else None,
            "removed_from_docket": len(rows) - len(kept),
            "holdout_sent_to_judge": holdout,
            "rule_acts": acting,
            "sibling_k": scr.shadow_k,
            "sibling_canon_k": scr.sibling_k,
            "sibling_would_kill_by_k": by_k,
            "ms_per_row": round(1000.0 * elapsed / len(rows), 5) if rows else None,
            "seconds": round(elapsed, 3),
            "samples": samples,
            "missed_growth": missed_growth_lines(
                acting=acting,
                removed=len(rows) - len(kept),
                would=would,
                seconds_per_cell=seconds_per_cell,
                sibling_cost=scr.sib_cost,
                sibling_k=scr.shadow_k,
            ),
            "note": (
                "SHADOW records what each rule WOULD remove and removes nothing; every row "
                "still reaches the sealed judge. CANON (a code constant) removes only rules "
                "marked rule_acts, minus a 1-in-20 holdout, and only after a durable KILL."
            ),
        }
        if canon:
            doc["ledger"] = ledger
        if publish:
            _atomic_json(INTAKE_REPORT, doc)
        return (kept if canon else rows), doc
    except (Exception, SystemExit) as exc:  # fail open: an ordering organ never costs a docket
        return rows, {
            "schema": SCHEMA,
            "mode": "UNMEASURED",
            "why": f"{type(exc).__name__}: {str(exc)[:200]}",
            "removed_from_docket": 0,
        }


def _atomic_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        with contextlib.suppress(OSError):
            path.write_text(tmp.read_text("utf-8"), encoding="utf-8")
        with contextlib.suppress(OSError):
            tmp.unlink()


# ------------------------------------------------------------------ provable rules on survivors
def survivor_spec_audit(
    charts: dict[str, Any], probe: Callable[[str, str], dict[str, Any]] | None
) -> dict[str, Any]:
    """Run the two PROVABLE rules on every known certificate / sleeve spec. A provable rule that
    fires on a certified cell is a broken proof, so this must read zero."""
    seen: set[tuple[str, str, str]] = set()
    fired: list[dict[str, Any]] = []
    for sym, tf, fam, _ in _cert_rows():
        if (sym, tf, fam) in seen:
            continue
        seen.add((sym, tf, fam))
        facts = charts.get(f"{sym}|{tf}")
        if chart_is_short(facts):
            fired.append({"rule": "chart_short", "sym": sym, "tf": tf, "family": fam})
        if probe is not None and facts and int(facts.get("utc_days") or 0) > 0:
            res = probe(sym, fam)
            if isinstance(res, dict) and res.get("status") == "NEEDS_DATA":
                fired.append({"rule": "needs_data", "sym": sym, "tf": tf, "family": fam})
    return {
        "specs_audited": len(seen),
        "provable_rule_fired_on_certified": len(fired),
        "fired": fired[:50],
    }


def _probe_fn() -> Callable[[str, str], dict[str, Any]] | None:
    try:
        from research.fire_inputs import probe
    except Exception:
        return None
    memo: dict[tuple[str, str], dict[str, Any]] = {}
    return lambda sym, fam: probe(sym, fam, memo=memo)


def _below_normal() -> dict[str, Any]:
    """The judge never outranks the miners: lower this leg's priority, and SAY whether it took."""
    try:
        import psutil

        me = psutil.Process()
        want = psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10
        me.nice(want)
        got = me.nice()
        return {
            "applied": bool(got == want),
            "requested": str(want),
            "observed": str(got),
            "how": "psutil",
        }
    except Exception as exc:
        try:
            got = os.nice(10)  # type: ignore[attr-defined]
            return {"applied": True, "observed": str(got), "how": "os.nice"}
        except Exception as exc2:
            return {
                "applied": False,
                "how": "none",
                "why": f"{type(exc).__name__}; {type(exc2).__name__}",
            }


def _intake_seconds_per_cell(intake_doc: Any) -> float | None:
    """The judge seconds per cell the last intake priced its gain line at, or None."""
    for line in (
        (intake_doc or {}).get("missed_growth") or [] if isinstance(intake_doc, dict) else []
    ):
        if isinstance(line, dict) and line.get("side") == "gain":
            v = line.get("seconds_per_cell")
            return float(v) if isinstance(v, int | float) else None
    return None


def _epoch(raw: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def run_once(
    ledger: Path = LEDGER,
    out_dir: Path | None = None,
    universe: Path = UNIVERSE,
    priority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    rep_path = (out_dir / REPORT.name) if out_dir else REPORT
    tab_path = (out_dir / TABLES.name) if out_dir else TABLES
    prior_tables = _read(tab_path) or {}
    charts = chart_table(
        universe, prior_tables.get("charts") if isinstance(prior_tables, dict) else None
    )
    protected_now = protected_buckets()
    protected_dated = protected_buckets_dated()
    led_ok = ledger.exists()
    t1 = time.perf_counter()
    rp = replay(iter_ledger(ledger), protected=protected_dated) if led_ok else None
    t2 = time.perf_counter()
    probe = _probe_fn()
    audit = survivor_spec_audit(charts, probe)
    sib: dict[str, Any]
    dead: dict[str, int] = {}
    if rp is None:
        sib = {
            "status": "UNMEASURED",
            "why": f"no gate ledger at {ledger}",
            "canon_ready": False,
            "canon_k": None,
        }
    else:
        dead = {b: n for b, n in rp.pop("dead_buckets").items() if b not in protected_now}
        sib = {"status": "MEASURED", **rp}
    tables = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "charts": charts,
        "dead_buckets": dead,
        "protected_buckets": sorted(protected_now),
    }
    _atomic_json(tab_path, tables)
    short = sorted(k for k, v in charts.items() if chart_is_short(v))
    try:
        trials: dict[str, Any] = {"charged_to_screen": lifetime_kills()[0]}
    except (OSError, ValueError) as exc:
        trials = {"charged_to_screen": None, "error": f"{type(exc).__name__}: {exc}"[:200]}
    trials["rule"] = (
        "each killed cell is charged exactly once (KILL), stays charged through READMIT, and "
        "hands its charge to the judge's fate on JUDGED; shadow writes nothing"
    )
    last_intake = _read(INTAKE_REPORT) if out_dir is None else None
    sib_k = sib.get("canon_k") or min(K_GRID)
    sib_cost = ((sib.get("by_k") or {}).get(str(sib_k)) or {}).get("killed_by_tier")
    acting = {r: bool(CANON and RULES[r]["canon_eligible"]) for r in RULES}
    acting["sibling_dead"] = bool(acting["sibling_dead"] and sib.get("canon_ready"))
    doc = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "producer": "desks/mt5/research/judge_prescreen.py (hourly leg judge_prescreen)",
        "mode": "CANON" if CANON else "SHADOW",
        "canon_switch": "the code constant judge_prescreen.CANON (a reviewed commit flips it)",
        "rules": RULES,
        "needs_data": {
            "status": "PROVEN",
            "canon_ready": True,
            "false_kills_by_construction": 0,
            "basis": "fire_inputs NEEDS_DATA + bars present = empty series",
        },
        "chart_short": {
            "status": "PROVEN_NOT_SEPARABLE",
            "canon_ready": False,
            "charts_short": len(short),
            "sample": short[:40],
            "false_kills_by_construction": 0,
        },
        "sibling_dead": sib,
        "survivor_spec_audit": audit,
        "ledger": {
            "path": str(ledger),
            "present": led_ok,
            "bytes": ledger.stat().st_size if led_ok else None,
        },
        "timing_s": {
            "charts": round(t1 - t0, 3),
            "replay": round(t2 - t1, 3),
            "total": round(time.perf_counter() - t0, 3),
        },
        "priority": priority or {"applied": False, "how": "not requested (library call)"},
        "trials": trials,
        "missed_growth": missed_growth_lines(
            acting=acting,
            removed=int((last_intake or {}).get("removed_from_docket") or 0),
            would=dict((last_intake or {}).get("would_kill") or {}),
            seconds_per_cell=_intake_seconds_per_cell(last_intake),
            sibling_cost=sib_cost,
            sibling_k=sib_k,
        ),
    }
    _atomic_json(rep_path, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--universe", type=Path, default=UNIVERSE)
    a = ap.parse_args(argv)
    prio = _below_normal()
    doc = run_once(a.ledger, a.out_dir, a.universe, priority=prio)
    sib = doc["sibling_dead"]
    print(
        f"judge_prescreen: {doc['mode']}; sibling_dead {sib.get('status')} canon_k="
        f"{sib.get('canon_k')}; chart_short charts={doc['chart_short']['charts_short']}; "
        f"provable-on-certified={doc['survivor_spec_audit']['provable_rule_fired_on_certified']}"
        f"; priority applied={prio.get('applied')}; {doc['timing_s']['total']}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

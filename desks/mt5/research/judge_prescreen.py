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
                          sweep and nothing else moves. Zero false kills BY CONSTRUCTION.
  PROVABLE_NOT_SEPARABLE  `chart_short` -- the cell's chart cannot hold 60 trading days (a cell
                          trades only on dates its bars exist, and a UTC date maps onto at most
                          two dates under any fixed clock offset), so the judge MUST return
                          UNKNOWN. Zero false kills by construction, but the cell's days can still
                          enter the union cut, so it is NEVER canon (harness test 2). Shadow only.
  STATISTICAL             `sibling_dead` -- the cell's (symbol, chart, family) bucket already
                          holds >= K cells with a named verdict and NOT ONE of them ever cleared
                          `in_sample_screen`. Not an implication. Its false-kill rate is MEASURED
                          by a time-ordered replay of the judge's own gate ledger (each cell is
                          screened on the evidence that existed before its first verdict) and it
                          may go canon only at a K the replay shows killed zero true survivors in
                          both halves of the record. A bucket holding a known certificate or LIVE
                          sleeve is never dead.

TRIALS ARE NEVER INFLATED OR DEFLATED. Every lifetime trial the sealed judge charges is a graph
fate, and every verdict the judge writes (gate-0 reject, UNKNOWN, ten-gate) is one fate. A canon
kill is appended to `data/hypotheses/prescreen_verdicts.jsonl` as a terminal, recorded verdict
(PRESCREEN_REJECT / PRESCREEN_UNKNOWN with its evidence), and `libs.research.experiment_ledger`
counts each killed cell exactly once -- the trial the judge would have recorded. A kill that is
later lifted (the evidence changed) writes READMIT and stops counting, so the judge's own fate
replaces it rather than doubling it. In SHADOW nothing is killed and the file is never written.

ZERO PROMOTION AUTHORITY, NO GATE MOVES. The screen can only send a cell AWAY from the judge;
it never passes anything, never touches a sealed file, never changes a threshold (DSR >= 0.95
included). The default is SHADOW: it records what it would kill and kills nothing. The single
switch is `desks/mt5/data/JUDGE_PRESCREEN_CANON.json` = {"enabled": true}; even then a rule acts
only while the latest replay report (fresh, on the box's own ledger) names it canon-ready.
"""
from __future__ import annotations

import argparse
import contextlib
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
CANON_SWITCH = DATA / "JUDGE_PRESCREEN_CANON.json"

SCHEMA = "judge_prescreen/1"

#: The sealed judge's own floor: CPCV, walk-forward and the matrix need 60 daily observations
#: (`external_gauntlet.run_gauntlet` keeps `len(d) >= 60`; `cell_dev_cut(need=60)`).
MIN_DAYS = 60

#: K grid for `sibling_dead`. The smallest K the replay clears becomes the canon K.
K_GRID: tuple[int, ...] = (5, 10, 20, 40, 80)
#: A replay that saw fewer true survivors than this cannot call any K safe: UNMEASURED, not ready.
MIN_TRUE_SURVIVORS = 20
#: A replay report older than this cannot authorise a canon kill.
REPORT_MAX_AGE_S = 6 * 3600.0

RULES: dict[str, dict[str, Any]] = {
    "needs_data": {"class": "PROVABLE_SEPARABLE", "verdict": "PRESCREEN_UNKNOWN",
                   "canon_eligible": True, "implies": "UNKNOWN (never_fires / needs_data)",
                   "why": ("research/fire_inputs NEEDS_DATA: the family's own input guard returns "
                           "[] on the inputs build_cell would hand it, and the chart has bars, so "
                           "the series is empty; harness test 5 proves such a cell is judged the "
                           "same in any sweep and moves nothing else")},
    "chart_short": {"class": "PROVABLE_NOT_SEPARABLE", "verdict": "PRESCREEN_UNKNOWN",
                    "canon_eligible": False, "implies": "UNKNOWN (too_rare / short history)",
                    "why": ("the chart cannot hold 60 trading days: a cell trades only on dates "
                            "its bars exist and one UTC date maps onto at most two dates under any "
                            "fixed offset, so min(2 x UTC dates, span + 2) < 60 forces UNKNOWN; "
                            "NEVER canon, because its days can still move the union lockbox cut "
                            "(harness test 2)")},
    "sibling_dead": {"class": "STATISTICAL", "verdict": "PRESCREEN_REJECT",
                     "canon_eligible": True, "implies": "nothing (measured, not implied)",
                     "why": ("the (symbol, chart, family) bucket holds >= K cells with a named "
                             "verdict and none ever cleared in_sample_screen; canon only at the K "
                             "the time-ordered ledger replay shows killed zero true survivors")},
}

#: Terminal gates that are not a judgement of the series (gate 0 runs before any build).
_PRE_BUILD_GATES = frozenset({"", "symbol_eligibility", "economic_prior"})

#: Outcome tiers, best-ever per cell. 3 is a true survivor.
UNKNOWN_T, IS_FAIL_T, CLEARED_IS_T, PASSED_T = 0, 1, 2, 3
TIER_NAMES = {UNKNOWN_T: "unknown", IS_FAIL_T: "in_sample_fail",
              CLEARED_IS_T: "cleared_in_sample", PASSED_T: "true_survivor"}

_CELL_RE = re.compile(r"^(?P<sym>[^@]+?)(?:@(?P<tf>[A-Za-z0-9]+))?\.(?P<fam>[a-z0-9_]+)\.p=")


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
    """The judge's gate ledger, in append (= time) order. A malformed line is skipped, counted
    by the caller through the difference between lines and rows."""
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


# ------------------------------------------------------------------ protected buckets
def _cert_rows() -> Iterator[tuple[str, str, str]]:
    """(symbol, chart, family) of every known certificate and LIVE/STANDBY sleeve on this tree."""
    try:
        doc = json.loads((DATA / "sleeves.json").read_text("utf-8"))
        for s in doc.get("sleeves") or []:
            if isinstance(s, dict) and s.get("family") and s.get("symbol"):
                yield (str(s["symbol"]), str(s.get("timeframe") or "H1").upper(),
                       str(s["family"]))
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
            tf = str(spec.get("timeframe") or (spec.get("params") or {}).get("timeframe")
                     or "H1").upper()
            if sym and fam:
                yield (str(sym), tf, str(fam))


def protected_buckets() -> set[str]:
    return {f"{s}|{t}|{f}" for s, t, f in _cert_rows()}


# ------------------------------------------------------------------ the replay
def replay(rows: Iterable[dict[str, Any]], *, k_grid: tuple[int, ...] = K_GRID,
           protected: set[str] | None = None, survivor_cells: set[str] | None = None
           ) -> dict[str, Any]:
    """Time-ordered shadow of `sibling_dead` against the judge's own recorded verdicts.

    Each cell is screened ONCE, at its first recorded series judgement, on the bucket's state from
    rows strictly before it -- the evidence a pre-build screen would have had. Its outcome is its
    BEST tier over the whole record (a cell that later passed is a true survivor), plus any cell
    in `survivor_cells`. Kill = bucket had >= K named cells and zero that cleared in_sample.
    """
    protected = protected or set()
    survivor_cells = survivor_cells or set()
    buckets: dict[str, list[int]] = {}           # bucket -> [named cells, cleared cells]
    best: dict[str, int] = {}
    first_state: dict[str, tuple[int, int, int]] = {}   # cell -> (order, named, cleared)
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
        st = buckets.setdefault(b, [0, 0])
        if cell not in first_state:
            first_state[cell] = (len(first_state), st[0], st[1])
            bucket_cell[cell] = b
        old = best.get(cell, -1)
        if t > old:
            if old < IS_FAIL_T <= t:
                st[0] += 1
            if old < CLEARED_IS_T <= t:
                st[1] += 1
            best[cell] = t
    n = len(first_state)
    half = n // 2
    tiers = {c: (PASSED_T if c in survivor_cells else best[c]) for c in first_state}
    pop = dict.fromkeys(TIER_NAMES.values(), 0)
    for t in tiers.values():
        pop[TIER_NAMES[t]] += 1
    by_k: dict[str, Any] = {}
    canon_k = None
    n_true = pop["true_survivor"]
    for k in sorted(k_grid):
        killed = dict.fromkeys(TIER_NAMES.values(), 0)
        halves = [dict.fromkeys(TIER_NAMES.values(), 0) for _ in (0, 1)]
        n_killed = 0
        sample_false: list[str] = []
        for c, (order, named, cleared) in first_state.items():
            if bucket_cell[c] in protected or cleared > 0 or named < k:
                continue
            n_killed += 1
            name = TIER_NAMES[tiers[c]]
            killed[name] += 1
            halves[0 if order < half else 1][name] += 1
            if tiers[c] >= CLEARED_IS_T and len(sample_false) < 20:
                sample_false.append(c)
        fk_true = killed["true_survivor"]
        row = {"k": k, "killed": n_killed,
               "kill_rate": round(n_killed / n, 6) if n else None,
               "killed_by_tier": killed,
               "false_kill_rate_by_tier": {name: (round(killed[name] / pop[name], 6)
                                                  if pop[name] else None)
                                           for name in TIER_NAMES.values()},
               "killed_by_tier_first_half": halves[0],
               "killed_by_tier_second_half": halves[1],
               "sample_false_kills_cleared_or_better": sample_false}
        by_k[str(k)] = row
        if (canon_k is None and n_true >= MIN_TRUE_SURVIVORS and fk_true == 0
                and halves[0]["true_survivor"] == 0 and halves[1]["true_survivor"] == 0):
            canon_k = k
    dead = {b: st for b, st in buckets.items()
            if st[1] == 0 and st[0] >= min(k_grid) and b not in protected}
    return {"ledger_rows": n_rows, "series_judgements": n_judgements, "cells_replayed": n,
            "population_by_tier": pop, "by_k": by_k, "canon_k": canon_k,
            "canon_ready": canon_k is not None,
            "canon_rule": (f"smallest K in {list(k_grid)} with ZERO true-survivor kills overall "
                           f"and in each half of the record, and >= {MIN_TRUE_SURVIVORS} true "
                           f"survivors replayed"),
            "dead_buckets": {b: st[0] for b, st in dead.items()},
            "buckets": len(buckets)}


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
        return {"utc_days": len(np.unique(d)),
                "span_days": int((hi - lo).astype(int)) + 1,
                "first": str(lo), "last": str(hi)}
    except Exception:
        return None


def chart_table(universe: Path = UNIVERSE, prior: dict[str, Any] | None = None
                ) -> dict[str, Any]:
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


# ------------------------------------------------------------------ the per-row screen
def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def canon_enabled(path: Path | None = None) -> bool:
    doc = _read(path or CANON_SWITCH)
    return isinstance(doc, dict) and doc.get("enabled") is True


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

    def __init__(self, tables: dict[str, Any] | None, report: dict[str, Any] | None,
                 probe: Callable[[str, str], dict[str, Any]] | None = None,
                 *, canon: bool = False) -> None:
        tables = tables if isinstance(tables, dict) else {}
        self.charts: dict[str, Any] = tables.get("charts") or {}
        self.dead: dict[str, int] = tables.get("dead_buckets") or {}
        self.protected: set[str] = set(tables.get("protected_buckets") or [])
        self.probe = probe
        rep = report if isinstance(report, dict) else {}
        sib = rep.get("sibling_dead") or {}
        self.sibling_k: int | None = sib.get("canon_k") if isinstance(sib, dict) else None
        self.shadow_k: int = int(self.sibling_k or max(K_GRID))
        fresh = _report_fresh(rep)
        self.canon = bool(canon)
        self.ready = {
            "needs_data": True,                      # proven, not measured
            "chart_short": False,                    # never: not separable
            "sibling_dead": bool(fresh and self.sibling_k is not None
                                 and sib.get("canon_ready") is True),
        }

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
                return "needs_data", {"missing_input": res.get("missing_input"),
                                      "why": str(res.get("why") or "")[:240]}
        if chart_is_short(facts):
            return "chart_short", {"chart": f"{sym}|{tf}", "utc_days": facts.get("utc_days"),
                                   "span_days": facts.get("span_days")}
        b = bucket_of(cell)
        if b is not None and b not in self.protected:
            named = self.dead.get(b)
            if named is not None and named >= self.shadow_k:
                return "sibling_dead", {"bucket": b, "named_cells": named, "cleared_cells": 0,
                                        "k": self.shadow_k}
        return None

    def acts(self, rule: str) -> bool:
        return bool(self.canon and RULES[rule]["canon_eligible"] and self.ready.get(rule))


def intake(rows: list[dict[str, Any]], *, cell_of: Callable[[dict[str, Any]], str | None],
           probe: Callable[[str, str], dict[str, Any]] | None = None,
           publish: bool = True, tables_path: Path | None = None,
           report_path: Path | None = None, switch: Path | None = None
           ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Screen the docket at intake. SHADOW: rows returned untouched, would-kills counted.

    CANON (switch on AND the rule canon-ready): killed rows leave the docket and each newly killed
    cell is appended to `prescreen_verdicts.jsonl` as a recorded terminal verdict; a cell killed
    before and no longer killed is READMITTED (and stops counting as a trial). Never raises: any
    failure returns the rows untouched.
    """
    t0 = time.perf_counter()
    try:
        canon = canon_enabled(switch)
        scr = Screen(_read(tables_path or TABLES), _read(report_path or REPORT), probe,
                     canon=canon)
        would: dict[str, int] = dict.fromkeys(RULES, 0)
        samples: dict[str, list[dict[str, Any]]] = {r: [] for r in RULES}
        kept: list[dict[str, Any]] = []
        kill_now: dict[str, dict[str, Any]] = {}
        for row in rows:
            cell = cell_of(row)
            got = scr.decide(row, cell) if cell else None
            if got is None:
                kept.append(row)
                continue
            rule, ev = got
            would[rule] += 1
            if len(samples[rule]) < 25:
                samples[rule].append({"cell": cell, **ev})
            if scr.acts(rule):
                kill_now[str(cell)] = {"rule": rule, "row": row, "evidence": ev}
            else:
                kept.append(row)
        elapsed = time.perf_counter() - t0
        doc: dict[str, Any] = {
            "schema": SCHEMA, "generated_at": _now(),
            "mode": "CANON" if canon else "SHADOW",
            "rows": len(rows), "would_kill": would,
            "would_kill_total": sum(would.values()),
            "would_kill_share": round(sum(would.values()) / len(rows), 6) if rows else None,
            "removed_from_docket": len(kill_now),
            "rule_acts": {r: scr.acts(r) for r in RULES},
            "sibling_k": scr.shadow_k, "sibling_canon_k": scr.sibling_k,
            "ms_per_row": round(1000.0 * elapsed / len(rows), 5) if rows else None,
            "seconds": round(elapsed, 3), "samples": samples,
            "note": ("SHADOW records what each rule WOULD remove and removes nothing; every row "
                     "still reaches the sealed judge. CANON removes only rules marked rule_acts.")}
        if canon:
            doc["ledger"] = _record_canon(kill_now, {str(cell_of(r)) for r in rows})
        if publish:
            _atomic_json(INTAKE_REPORT, doc)
        return (kept if canon else rows), doc
    except Exception as exc:                                     # pragma: no cover - fail open
        return rows, {"schema": SCHEMA, "mode": "UNMEASURED",
                      "why": f"{type(exc).__name__}: {str(exc)[:200]}", "removed_from_docket": 0}


def _record_canon(kill_now: dict[str, dict[str, Any]], present: set[str]) -> dict[str, Any]:
    """Append KILL for newly killed cells and READMIT for lifted ones; rewrite the killed set."""
    prior = _read(KILLED)
    prior = prior.get("cells") if isinstance(prior, dict) else None
    prior = prior if isinstance(prior, dict) else {}
    at = _now()
    out_rows: list[dict[str, Any]] = []
    for cell, k in kill_now.items():
        if cell in prior:
            continue
        row = k["row"]
        out_rows.append({"at": at, "event": "KILL", "cell": cell,
                         "sym": row.get("sym") or row.get("symbol"),
                         "family": row.get("family"), "rule": k["rule"],
                         "verdict": RULES[k["rule"]]["verdict"],
                         "class": RULES[k["rule"]]["class"], "evidence": k["evidence"],
                         "passed": False, "trial": 1})
    lifted = [c for c in prior if c in present and c not in kill_now]
    for cell in lifted:
        p = prior[cell]
        out_rows.append({"at": at, "event": "READMIT", "cell": cell, "family": p.get("family"),
                         "rule": p.get("rule"), "trial": -1,
                         "why": "the rule no longer fires on this cell; the judge rules it"})
    if out_rows:
        VERDICTS.parent.mkdir(parents=True, exist_ok=True)
        with VERDICTS.open("a", encoding="utf-8") as fh:
            for r in out_rows:
                fh.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")
    cells = {c: v for c, v in prior.items() if c not in lifted}
    for cell, k in kill_now.items():
        cells.setdefault(cell, {"family": k["row"].get("family"), "rule": k["rule"], "at": at})
    _atomic_json(KILLED, {"schema": SCHEMA, "updated_at": at, "cells": cells})
    return {"killed_new": sum(1 for r in out_rows if r["event"] == "KILL"),
            "readmitted": len(lifted), "killed_standing": len(cells)}


def lifetime_kills(path: Path | None = None) -> tuple[int, dict[str, int]]:
    """(cells, per family) standing as canon kills: each is one trial the judge would have
    charged. KILL counts once per cell; a READMIT returns the cell to the judge's own count."""
    state: dict[str, str] = {}
    try:
        lines = (path or VERDICTS).read_text("utf-8").splitlines()
    except FileNotFoundError:
        return 0, {}
    # Any other read failure RAISES: a kill ledger that exists but cannot be read must never be
    # counted as zero trials (that would deflate the lifetime charge).
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(r, dict) or not r.get("cell"):
            continue
        if r.get("event") == "KILL":
            state[str(r["cell"])] = str(r.get("family") or "prescreen")
        elif r.get("event") == "READMIT":
            state.pop(str(r["cell"]), None)
    by_fam: dict[str, int] = {}
    for f in state.values():
        by_fam[f] = by_fam.get(f, 0) + 1
    return len(state), by_fam


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
def survivor_spec_audit(charts: dict[str, Any], probe: Callable[[str, str], dict[str, Any]] | None
                        ) -> dict[str, Any]:
    """Run the two PROVABLE rules on every known certificate / sleeve spec. A provable rule that
    fires on a certified cell is a broken proof, so this must read zero."""
    seen: set[tuple[str, str, str]] = set()
    fired: list[dict[str, Any]] = []
    for sym, tf, fam in _cert_rows():
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
    return {"specs_audited": len(seen), "provable_rule_fired_on_certified": len(fired),
            "fired": fired[:50]}


def _probe_fn() -> Callable[[str, str], dict[str, Any]] | None:
    try:
        from research.fire_inputs import probe
    except Exception:
        return None
    memo: dict[tuple[str, str], dict[str, Any]] = {}
    return lambda sym, fam: probe(sym, fam, memo=memo)


def _below_normal() -> None:
    """The judge never outranks the miners: this leg lowers its own priority first."""
    try:
        import psutil
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10)
    except Exception:
        with contextlib.suppress(Exception):
            os.nice(10)  # type: ignore[attr-defined]


def run_once(ledger: Path = LEDGER, out_dir: Path | None = None,
             universe: Path = UNIVERSE) -> dict[str, Any]:
    t0 = time.perf_counter()
    rep_path = (out_dir / REPORT.name) if out_dir else REPORT
    tab_path = (out_dir / TABLES.name) if out_dir else TABLES
    prior_tables = _read(tab_path) or {}
    charts = chart_table(universe, prior_tables.get("charts") if isinstance(prior_tables, dict)
                         else None)
    protected = protected_buckets()
    led_ok = ledger.exists()
    t1 = time.perf_counter()
    rp = replay(iter_ledger(ledger), protected=protected) if led_ok else None
    t2 = time.perf_counter()
    probe = _probe_fn()
    audit = survivor_spec_audit(charts, probe)
    sib: dict[str, Any]
    if rp is None:
        sib = {"status": "UNMEASURED", "why": f"no gate ledger at {ledger}", "canon_ready": False,
               "canon_k": None}
        dead: dict[str, int] = {}
    else:
        dead = rp.pop("dead_buckets")
        sib = {"status": "MEASURED", **rp}
    tables = {"schema": SCHEMA, "generated_at": _now(), "charts": charts,
              "dead_buckets": dead, "protected_buckets": sorted(protected)}
    _atomic_json(tab_path, tables)
    short = sorted(k for k, v in charts.items() if chart_is_short(v))
    doc = {
        "schema": SCHEMA, "generated_at": _now(),
        "producer": "desks/mt5/research/judge_prescreen.py (hourly leg judge_prescreen)",
        "mode": "CANON" if canon_enabled() else "SHADOW",
        "canon_switch": str(CANON_SWITCH.relative_to(ROOT)) if CANON_SWITCH.is_relative_to(ROOT)
        else str(CANON_SWITCH),
        "rules": RULES,
        "needs_data": {"status": "PROVEN", "canon_ready": True,
                       "false_kills_by_construction": 0,
                       "basis": "fire_inputs NEEDS_DATA + bars present = empty series"},
        "chart_short": {"status": "PROVEN_NOT_SEPARABLE", "canon_ready": False,
                        "charts_short": len(short), "sample": short[:40],
                        "false_kills_by_construction": 0},
        "sibling_dead": sib,
        "survivor_spec_audit": audit,
        "ledger": {"path": str(ledger), "present": led_ok,
                   "bytes": ledger.stat().st_size if led_ok else None},
        "timing_s": {"charts": round(t1 - t0, 3), "replay": round(t2 - t1, 3),
                     "total": round(time.perf_counter() - t0, 3)},
        "trials": {"canon_kills_standing": lifetime_kills()[0],
                   "rule": ("each canon kill is one lifetime trial (experiment_ledger), exactly "
                            "the one fate the judge would have recorded; shadow writes none")},
    }
    _atomic_json(rep_path, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--universe", type=Path, default=UNIVERSE)
    a = ap.parse_args(argv)
    _below_normal()
    doc = run_once(a.ledger, a.out_dir, a.universe)
    sib = doc["sibling_dead"]
    print(f"judge_prescreen: {doc['mode']}; sibling_dead {sib.get('status')} canon_k="
          f"{sib.get('canon_k')}; chart_short charts={doc['chart_short']['charts_short']}; "
          f"provable-on-certified={doc['survivor_spec_audit']['provable_rule_fired_on_certified']}"
          f"; {doc['timing_s']['total']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


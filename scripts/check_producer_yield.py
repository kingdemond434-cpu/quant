"""EVERY PRODUCER PRODUCES, OR IT IS REPLACED. Names the dead, and names what takes their budget.

THE LAW (principal, 2026-09-15): every single miner, source, seat and proposer must produce. One
that cannot is replaced with an alternative.

WHY THIS IS A DIFFERENT LAW FROM THE TWO NEXT TO IT, because all three sound similar and they
catch different failures:

    check_ground_conversion   a ground must have MACHINERY pointing at the gauntlet.
    check_row_conversion      a mined row must reach a TERMINAL disposition.
    this file                 a producer must have OUTPUT. Machinery that runs, converts, and
                              yields nothing for weeks is not a pipeline, it is a heater.

AND THE THREE VERDICTS ARE NOT THE SAME PROBLEM. Collapsing them is how a desk spends a year
"fixing the miners":

    PRODUCING   output in the window. Nothing to do.
    STARVED     output, but far below its peers. Usually a BUDGET or an input problem, never a
                reason to delete the producer. `alpha_evolution` measured 2026-09-15: it runs,
                it does not crash, and it proposed ONE cell from 72 tests -- because it evolves
                against a book `pf_allocation` reports as 1 funded sleeve. Deleting it would
                have thrown away a working organ for the sin of being fed nothing.
    DEAD        zero output across the whole window. THIS is the one the law is about, and the
                remedy is not another look: it is a named REPLACEMENT that takes the budget.
    UNMEASURED  no artifact records this producer's output at all. A verdict, never a pass, and
                in practice the most common real state of a new organ (L1.28a).

A REPLACEMENT MUST BE NAMED, NOT IMPLIED. "Try something else" is not a remedy; it is the absence
of one. Every producer declared here carries the alternative that inherits its budget when it
dies, so the decision is made once, in advance, by whoever understood the producer -- and not at
3am by whoever happened to notice the zero.

SECOND HALF, ADDED 2026-09-23 -- EVERY PRODUCER OWES CELLS (LAWS 7). The half above asks whether
a SEAT wrote rows. That is donation, not production. The desk's one judge eats CELLS, so the
second half measures, per producer per hour: cells emitted, unique cells after dedup, cells that
reached the judge, and THE ORTHOGONALITY EACH ADDED -- because a hundred copies of one momentum
rule is one cell's worth of breadth and must score as such. The producer set is DERIVED (the
census, which is itself derived from the component registry and the registry's own generators),
never a hand list, so a producer that lands today is judged today.

    python scripts/check_producer_yield.py
    python scripts/check_producer_yield.py --window-days 7
    python scripts/check_producer_yield.py --yield-window-hours 24
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "PRODUCER_YIELD.json"

#: The census this fence consumes. It is NOT re-derived here: the census already merges
#: `PRODUCER_CENSUS.json` (every seat/miner/organ with a clock), `COMPONENT_REGISTRY.json` (every
#: executable with a ComponentSpec) and every generator the registry has actually seen. Deriving
#: the roster a second time is how two organs come to disagree about who exists.
CENSUS = DESK / "reports" / "PRODUCTIVITY_CENSUS.json"
REGISTRY_DB = ROOT / "data" / "alpha_registry.sqlite"

#: Declared exemptions and named blockers, SHARED with `scripts/check_productivity_census.py` so
#: an organ declares itself once. A row is either a BLOCKER (`why` >= 20 chars + `owner`) or an
#: EXEMPTION (`exempt: true` + `produces` + `consumer`) -- the second is how a genuinely
#: exploratory organ says what it makes instead of cells and who reads it.
BLOCKERS = ROOT / "docs" / "research" / "productivity_blockers.json"

#: The ratchet. Falls only: the owing count may never rise, the throughput bests may never fall.
RATCHET = ROOT / "docs" / "research" / "producer_yield_ratchet.json"

#: A day of registry rows. Shorter than the census's 7-day compute window on purpose: the census
#: asks "has this thing ever paid", this asks "is it paying NOW", and an hourly desk that has
#: emitted nothing for a day is the failure being looked for.
YIELD_WINDOW_HOURS = 24.0

#: Below this, a LEDGER hour is a costed import or an interrupted leg, not a shift of work. Same
#: figure as the sibling fence, for the same reason: a fence that fires on a hundredth of a ledger
#: hour trains its readers to ignore it. It does NOT apply to registry-attributed compute, which
#: is seconds a generator recorded for a pass it actually ran -- there, any positive number is a
#: pass that happened, and holding it to a ledger-sized floor is how this fence went blind on a
#: host whose compute ledger keys on leg names that name no roster producer.
MIN_COMPUTE_HOURS = 0.25

#: How far throughput may fall below its own best before the fence calls it a regression. It is a
#: FLOOR and never a cap -- nothing here throttles a productive organ, and the remedy for a breach
#: is always to make the barren producer produce, never to slow a working one. Half is wide enough
#: to absorb a cycle that ran short and narrow enough that a collapsed lane cannot hide in it.
THROUGHPUT_FLOOR_FRACTION = 0.5

#: Distinct (family|symbol|horizon) cells read per producer for the orthogonality matrix. The
#: breadth measure is a participation ratio of a singular-value spectrum, so it saturates long
#: before this; the cap bounds the SVD on an 8 GB box rather than shaping the answer.
MAX_CELLS_PER_PRODUCER = 600

#: A verdict, never a zero (L1.28a).
UNMEASURED_STR = "UNMEASURED"

#: Output below this share of the median producer's output is STARVED rather than healthy. It is
#: a RATIO and not a count on purpose: an absolute floor would condemn a deliberately narrow
#: producer and excuse a broad one that collapsed.
STARVED_FRACTION = 0.05

#: producer -> the alternative that inherits its budget if it is ever declared DEAD. Declared in
#: advance, by intent, so a dead producer has a decision attached to it rather than a question.
REPLACEMENTS: dict[str, str] = {
    "alpha_evolution": "representation_discovery -- same expression search, driven by measured "
                       "representations rather than by a funded book it does not have",
    "plumbing_miner": "microstructure_miner",
    "transition_alpha": "regime_transition sweep inside external_gauntlet",
    "weak_signal_compiler": "combination lane of external_gauntlet",
    "fund_playbook": "institutional_cards -- the same mechanism claims, declared rather than mined",
    "microstructure_miner": "execution_twin markout study",
    "style_premia_sweep": "cross_sectional family sweep",
    "cross_asset_graph": "asia_transmission -- economically declared chains at the CAUSAL_ROLE bar",
    "anomaly_factory": "external_gauntlet exploration floor",
    "tail_alpha_search": "drawdown_conditional family sweep",
    "survivor_distiller": "survivor_neighbourhood",
    "factor_model_coevolution": "residual_factors",
    "deep_forest_miner": "asia_plane -- the hard-data half, where the number is the observation",
    "asia_plane": "deep_forest_miner -- the practitioner half; each is the other's fallback",
    "asia_transmission": "cross_asset_graph",
    # The eight seats measured DEAD on 2026-09-15. Each gets a named inheritor rather than a
    # question mark: three of them are MQL5 sub-crawlers whose work the surviving MQL5 seats
    # already do, and the rest have a live organ covering the same ground.
    "brain": "deepening_worker -- the same LLM reasoning, on the queue rather than freeform",
    "cohorts": "cohort_independence in libs/research",
    "fxmerge": "fxblue -- the same public MT4/MT5 account statistics, from a live route",
    "mql5_catalog": "mql5_signals -- the catalogue is a crawl of what the signals seat already reads",
    "mql5_prospector": "mql5_survivors -- survivorship-aware and still writing",
    "mql5_reputation": "mql5_survivors -- reputation is one of its phenotypes",
    "plumbing": "plumbing_miner (the proposer), which is the organ this seat fed",
    "scheduled_chatgpt": "deepseek_cycle -- the seat that is actually donating today",
}


def _rel(p: Path) -> str:
    """A repo-relative path for a message, never an exception. A fence that crashes while
    explaining a breach reports nothing at all, which is worse than the breach."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _seat_output(window_days: float) -> dict[str, int]:
    """Rows each intelligence seat donated inside the window, from the files themselves.

    Measured off FILE MTIME rather than a row's own stamp: a seat that stopped writing is the
    thing being looked for, and a stale row's internal timestamp would report it as alive.
    """
    cutoff = time.time() - window_days * 86400.0
    out: Counter[str] = Counter()
    for root in (DESK / "data" / "intelligence", ROOT / "data" / "intelligence"):
        for pat in ("*/*.json", "*/*.jsonl"):
            for f in glob.glob(str(root / pat)):
                seat = os.path.basename(os.path.dirname(f))
                try:
                    if os.path.getmtime(f) < cutoff:
                        out.setdefault(seat, 0)
                        continue
                    with open(f, encoding="utf-8", errors="replace") as fh:
                        n = sum(1 for _ in fh)
                except OSError:
                    continue
                out[seat] += max(n, 1)
    return dict(out)


def audit(window_days: float = 3.0) -> dict[str, Any]:
    seats = _seat_output(window_days)
    rows: list[dict[str, Any]] = []

    # THE PROPOSERS, from the daily cycle's own list rather than a copy of it. A list that can
    # drift from the runner is a list that reports on organs nobody runs.
    proposers: list[str] = []
    try:
        src = (DESK / "research" / "daily_cycle.py").read_text(encoding="utf-8")
        start = src.find('for name in ("plumbing_miner"')
        if start > 0:
            block = src[start:src.find("):", start)]
            proposers = [t.strip().strip('"') for t in block.split("(", 1)[1].split(",")
                         if t.strip().strip('"').isidentifier()]
    except OSError:
        pass

    # THE SEAT DIRECTORY IS NOT ALWAYS THE MODULE NAME, and a mismatch reads as DEAD. `asia_plane`
    # donates into `data/intelligence/asia/`, so without this it would be reported as producing
    # nothing on the same night it produced 513 cells -- the exact false negative this gate
    # exists to avoid making about anything else.
    for producer, seat in (("asia_plane", "asia"), ("asia_transmission", "asia_transmission"),
                           ("deep_forest_miner", "deep_forest")):
        if producer not in seats and seat in seats:
            seats[producer] = seats[seat]

    universe = list(seats.values())
    median = sorted(universe)[len(universe) // 2] if universe else 0

    for name in sorted(set(proposers) | set(seats) | set(REPLACEMENTS)):
        n = seats.get(name)
        rec: dict[str, Any] = {"producer": name, "rows_in_window": n,
                               "window_days": window_days}
        if n is None:
            rec.update({"verdict": "UNMEASURED",
                        "why": ("no intelligence seat records this producer's output. It may "
                                "write elsewhere, or it may write nowhere -- and those are not "
                                "the same thing, so neither is assumed.")})
        elif n == 0:
            rec.update({"verdict": "DEAD",
                        "why": f"zero rows in {window_days:g} day(s)",
                        "replacement": REPLACEMENTS.get(name,
                                                        "NONE DECLARED -- a dead producer with "
                                                        "no named alternative is an open "
                                                        "decision, which is the defect")})
        elif median and n < median * STARVED_FRACTION:
            rec.update({"verdict": "STARVED",
                        "why": (f"{n} row(s) against a median of {median}. A budget or input "
                                f"problem, NOT a reason to replace the producer.")})
        else:
            rec["verdict"] = "PRODUCING"
        rows.append(rec)

    census = Counter(str(r["verdict"]) for r in rows)
    dead = [r for r in rows if r["verdict"] == "DEAD"]
    undeclared = [r for r in dead if "NONE DECLARED" in str(r.get("replacement"))]
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("EVERY PRODUCER PRODUCES, OR IT IS REPLACED BY A NAMED ALTERNATIVE. Zero output "
                "is DEAD and carries a replacement; low output is STARVED and carries a budget "
                "question; no artifact is UNMEASURED and carries neither."),
        "window_days": window_days,
        "median_rows": median,
        "n_producers": len(rows),
        "census": dict(census),
        "dead_without_a_declared_replacement": undeclared,
        "producers": sorted(rows, key=lambda r: (r["verdict"], -(r["rows_in_window"] or 0))),
    }


# ------------------------------------------------------------ EVERY PRODUCER OWES CELLS (LAWS 7)

def _declarations() -> dict[str, dict[str, Any]]:
    """Named blockers and declared exemptions, keyed by producer, from the shared document.

    An absent file is an empty set, never an error: a desk with nothing to declare should not
    have to keep an empty document current, and the failure message says where to write one.
    """
    blob = _read(BLOCKERS, default={})
    rows = blob.get("blockers", blob) if isinstance(blob, dict) else blob
    out: dict[str, dict[str, Any]] = {}
    if isinstance(rows, dict):
        items = list(rows.items())
    elif isinstance(rows, list):
        items = [(r.get("producer") or r.get("key"), r) for r in rows if isinstance(r, dict)]
    else:
        items = []
    for key, val in items:
        if not key:
            continue
        entry = val if isinstance(val, dict) else {"why": str(val)}
        why = str(entry.get("why") or entry.get("reason") or entry.get("blocker") or "").strip()
        owner = str(entry.get("owner") or entry.get("by") or "").strip()
        produces = str(entry.get("produces") or "").strip()
        consumer = str(entry.get("consumer") or entry.get("read_by") or "").strip()
        # TWO WAYS TO PASS, AND THEY MEAN DIFFERENT THINGS. A BLOCKER says "this is broken, here
        # is who owns the fix"; an EXEMPTION says "this makes something other than cells, and
        # here is who reads it". Neither is inferred -- an organ that says nothing is a defect.
        if entry.get("exempt") and len(produces) >= 3 and len(consumer) >= 3:
            out[str(key).strip().lower()] = {"kind": "EXEMPTION", "produces": produces,
                                             "consumer": consumer}
        elif len(why) >= 20 and owner:
            out[str(key).strip().lower()] = {"kind": "BLOCKER", "why": why, "owner": owner}
    return out


def _window_cells(window_hours: float, db: Path | None = None) -> dict[str, Any]:
    """Per-producer cells inside the window, and the cell identities breadth is measured on.

    Read from the registry rather than from the census's funnel because the funnel is ALL-TIME:
    a producer that died a week ago still carries its lifetime cells there, and this fence is
    about the hour. An unreadable registry is UNMEASURED with the reason, never zero (L1.28a).
    """
    # Resolved at CALL time, never bound as a default: a default argument freezes the path at
    # import and quietly ignores every later reconfiguration, which is how a fence comes to read
    # one desk's registry while reporting on another's.
    db = db if db is not None else REGISTRY_DB
    out: dict[str, Any] = {"available": False, "why": "", "per": {}, "cells": {},
                           "window_hours": window_hours}
    if not db.exists():
        out["why"] = f"UNMEASURED: no registry at {db}"
        return out
    # Cut on a normalised prefix so a row stored with a space separator instead of `T` is not
    # silently excluded -- an undercount here would read as a barren producer, the exact false
    # positive this fence must never make.
    cutoff = (datetime.now(UTC) - timedelta(hours=window_hours)).strftime("%Y-%m-%dT%H:%M:%S")
    when = "replace(substr(created_at,1,19),' ','T') >= ?"
    judged = ("(donated_cell is not null or status in "
              "('donated','claimed','retired','judged'))")
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        out["why"] = f"UNMEASURED: registry unopenable ({type(exc).__name__}: {exc})"
        return out
    try:
        cur = con.cursor()
        # CREDIT THE PRODUCER THAT CAUSED THE CELL, NOT THE COMPILER THAT STAMPED IT. Measured
        # 2026-09-17 and documented in `desks/mt5/research/japan/dashboard.py`: cells reach
        # `research_candidates` through `discovery_compiler`, which writes its OWN generator, so
        # `generator LIKE 'japan:%'` returns zero while the department has 54 cells queued. The
        # link that survives the compiler is `discovery_id`. Reading the candidate's stamp alone
        # credits one pass-through with the desk's whole output and reports every real producer
        # as barren -- the exact false accusation this fence exists to avoid making.
        gen = ("lower(coalesce(nullif(d.generator,''), nullif(c.generator,''),"
               "'_unattributed_generator'))")
        cell = ("lower(coalesce(nullif(c.family,''),'?'))||'|'||"
                "lower(coalesce(nullif(c.symbol,''),'?'))||'|'||"
                "lower(coalesce(nullif(c.horizon,''),'?'))")
        src = ("research_candidates c left join discoveries d "
               "on d.discovery_id = c.discovery_id")
        when = when.replace("created_at", "c.created_at")
        judged = judged.replace("donated_cell", "c.donated_cell").replace("status", "c.status")
        per: dict[str, dict[str, int]] = {}
        for key, raw, uniq, sent in cur.execute(
                f"select {gen}, count(*), "  # noqa: S608 -- fragments are literals above
                f"count(distinct coalesce(nullif(c.grid_cell,''), c.content_hash)), "
                f"sum(case when {judged} then 1 else 0 end) "
                f"from {src} where {when} group by 1", (cutoff,)):
            per[str(key)] = {"cells_emitted": int(raw or 0), "unique_cells": int(uniq or 0),
                             "cells_to_judge": int(sent or 0)}
        cells: dict[str, list[str]] = {}
        for key, ident in cur.execute(
                f"select distinct {gen}, {cell} from {src} "  # noqa: S608
                f"where {when} and {judged}", (cutoff,)):
            cells.setdefault(str(key), []).append(str(ident))
        # A window in which NOTHING was created is UNMEASURED, never a verdict on any one
        # producer: if the whole registry is silent the failure is the desk's, and convicting
        # every organ on it would be the fence accusing everybody of one organ's outage (L1.28a).
        out.update({"available": bool(per), "per": per,
                    "cells": {k: sorted(v)[:MAX_CELLS_PER_PRODUCER] for k, v in cells.items()}})
        if not per:
            out["why"] = (f"UNMEASURED: no research_candidates row was created in the last "
                          f"{window_hours:g}h on this host, so no producer can be judged barren "
                          f"against it")
    except sqlite3.Error as exc:
        out["why"] = f"UNMEASURED: registry query failed ({type(exc).__name__}: {exc})"
    finally:
        con.close()
    return out


def _breadth(cells: dict[str, list[str]]) -> dict[str, Any]:
    """The desk's own effective-rank breadth, REUSED rather than re-implemented.

    `libs.research.sandbox_rotation.breadth` is the participation ratio of the singular-value
    spectrum of the producer x (family|symbol|horizon) indicator matrix, with each producer's
    marginal contribution measured as the drop when its row is removed. Two producers emitting
    the same cells therefore each score 0.0 added breadth, which is the whole point. A guarded
    import: numpy absent makes orthogonality UNMEASURED, never a crash in a law gate.
    """
    if not cells:
        return {"available": False, "why": "UNMEASURED: no judged cell in the window"}
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.research.sandbox_rotation import breadth as _b
    except Exception as exc:  # pragma: no cover - environment-dependent
        return {"available": False,
                "why": f"UNMEASURED: effective-rank machinery unimportable ({type(exc).__name__})"}
    try:
        got = _b(cells)
    except Exception as exc:  # pragma: no cover - defensive
        return {"available": False,
                "why": f"UNMEASURED: breadth failed ({type(exc).__name__}: {exc})"}
    got["available"] = True
    return got


def _ratchet_doc() -> dict[str, Any]:
    doc = _read(RATCHET, default={})
    return doc if isinstance(doc, dict) else {}


def yield_audit(window_hours: float = YIELD_WINDOW_HOURS) -> dict[str, Any]:
    """EVERY PRODUCER OWES CELLS: who is paying for its compute, and how orthogonally."""
    census = _read(CENSUS, default={})
    declared = _declarations()
    win = _window_cells(window_hours)
    per = win["per"]
    br = _breadth(win["cells"])
    marginal = br.get("marginal") or {}

    rows: list[dict[str, Any]] = []
    owing: list[dict[str, Any]] = []
    exempted: list[dict[str, Any]] = []
    unattributed: list[str] = []
    census_rows = census.get("producers") if isinstance(census.get("producers"), list) else []
    seen: set[str] = set()
    for src in list(census_rows) + [{"producer": k, "key": k} for k in per]:
        if not isinstance(src, dict):
            continue
        key = str(src.get("key") or src.get("producer") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        m = per.get(key) or {}
        hours = src.get("compute_hours")
        hours = float(hours) if isinstance(hours, (int, float)) else None
        led = src.get("compute_hours_ledger")
        led = float(led) if isinstance(led, (int, float)) else 0.0
        reg_h = src.get("compute_hours_registry")
        reg_h = float(reg_h) if isinstance(reg_h, (int, float)) else 0.0
        # TWO SOURCES OF "IT RAN", TWO FLOORS. A ledger hour is a leg's wall clock and needs the
        # floor; a registry second is a generator recording a pass it actually made, so any
        # positive value is that pass. Neither is inferred from a clock existing: an organ whose
        # compute nothing measured is UNMEASURED here and is counted in `compute_unattributed`
        # rather than accused (L1.28a).
        spent = (led >= MIN_COMPUTE_HOURS) or (reg_h > 0.0)
        row = {
            "producer": src.get("producer") or key,
            "key": key,
            "clock": src.get("clock"),
            "compute_hours_window7d": hours if hours is not None else UNMEASURED_STR,
            # THE FOUR COLUMNS THE LAW ASKS FOR, all per hour so producers on different clocks
            # are comparable at all.
            "cells_emitted_per_hour": round(m.get("cells_emitted", 0) / window_hours, 4),
            "unique_cells_per_hour": round(m.get("unique_cells", 0) / window_hours, 4),
            "cells_to_judge_per_hour": round(m.get("cells_to_judge", 0) / window_hours, 4),
            "orthogonality_added": (round(float(marginal.get(key, 0.0)), 4)
                                    if br.get("available") else UNMEASURED_STR),
        }
        decl = declared.get(key)
        if decl:
            row["declared"] = decl
        # OWING: it spent real compute and the judge saw NOTHING from it in the window, and it
        # has not said why. Not "low" -- zero. Low is a budget question and is never a failure
        # here, because cutting the tail of the search distribution is the one reduction in
        # aggressiveness this desk refuses.
        if spent and m.get("unique_cells", 0) == 0 and win.get("available"):
            if decl:
                exempted.append(row)
            else:
                owing.append(row)
        elif (not spent and str(src.get("clock") or "")
                and not str(src.get("clock")).startswith(("invoked:", "import:"))):
            unattributed.append(key)
        rows.append(row)

    n_judge = sum(int(v.get("cells_to_judge", 0)) for v in per.values())
    to_judge_per_h = round(n_judge / window_hours, 4)
    # THE ORTHOGONALITY-WEIGHTED EQUIVALENT, and it is the number to optimise. Total effective
    # rank over the number of producers that reached the judge: 1.0 when every producer works a
    # disjoint region of the cell space, and 1/n when they all emit the same rule n times. So a
    # hundred copies of one momentum rule score as one cell's worth of breadth, exactly as the
    # law says -- volume alone can never move this figure.
    n_rows_matrix = len(win["cells"])
    weight = (float(br.get("total") or 0.0) / n_rows_matrix) if (br.get("available")
                                                                 and n_rows_matrix) else None
    ortho_per_h = round(to_judge_per_h * weight, 4) if weight is not None else UNMEASURED_STR

    rat = _ratchet_doc()
    owing_max = rat.get("owing_max")
    best_judge = rat.get("cells_to_judge_per_hour_best")
    best_ortho = rat.get("orthogonal_cells_to_judge_per_hour_best")
    reason = str(rat.get("regression_reason") or "").strip()

    failures: list[str] = []
    if isinstance(owing_max, (int, float)) and len(owing) > owing_max:
        failures.append(
            f"{len(owing)} producer(s) owe cells against a ratchet of {owing_max:g}: the count "
            "of producers burning compute with no unique cell, no declared exemption and no "
            "named blocker may only FALL. Make them produce, declare what they make instead and "
            f"who reads it in {_rel(BLOCKERS)}, or retire them with a reason -- "
            "never throttle a producing one. Owing: "
            + ", ".join(str(r["producer"]) for r in owing[:12]))
    if (isinstance(best_judge, (int, float)) and win.get("available")
            and to_judge_per_h < best_judge * THROUGHPUT_FLOOR_FRACTION and not reason):
        failures.append(
            f"cells reaching the judge fell to {to_judge_per_h:g}/h against a best of "
            f"{best_judge:g}/h (floor {THROUGHPUT_FLOOR_FRACTION:g}x) with no stated reason: set "
            f"`regression_reason` in {_rel(RATCHET)} or find the lane that stopped")
    if (isinstance(best_ortho, (int, float)) and isinstance(ortho_per_h, float)
            and ortho_per_h < best_ortho * THROUGHPUT_FLOOR_FRACTION and not reason):
        failures.append(
            f"ORTHOGONAL cells reaching the judge fell to {ortho_per_h:g}/h against a best of "
            f"{best_ortho:g}/h with no stated reason: the desk is still emitting volume but the "
            "producers have collapsed onto each other's cells, which is the failure this column "
            "exists to catch")

    rows.sort(key=lambda r: (-(r["cells_to_judge_per_hour"] or 0.0),
                             str(r["producer"])))
    return {
        "law": ("EVERY PRODUCER OWES CELLS (LAWS 7). An organ that runs on a clock, consumes "
                "compute and emits no cell inside its own window is a defect with an owner. "
                "Exploratory organs pass by DECLARING what they produce instead and who reads "
                "it. Ratchets fall only; nothing here caps a producer."),
        "window_hours": window_hours,
        "registry": {"available": win.get("available"), "why": win.get("why")},
        "census_at": census.get("at"),
        "breadth": {k: v for k, v in br.items() if k != "marginal"},
        "n_producers": len(rows),
        "n_owing": len(owing),
        "n_declared": len(exempted),
        # THE MEASUREMENT GAP, NAMED RATHER THAN SILENT. These carry a self-turning clock and no
        # measured compute at all, so this fence cannot say whether they owe. That is UNMEASURED,
        # which is a verdict about the measurement (L1.28a) -- and the remedy is to make the
        # compute ledger key on producers, not to accuse or excuse them here.
        "compute_unattributed": len(unattributed),
        "compute_unattributed_why": (
            "producers with a declared self-turning clock and no ledger hour and no registry "
            "second: `cost_by_run` keys on the LEG name, and a leg that runs many producers "
            "prices none of them individually"),
        "compute_unattributed_sample": sorted(unattributed)[:20],
        "cells_to_judge_per_hour": to_judge_per_h,
        "orthogonal_cells_to_judge_per_hour": ortho_per_h,
        "orthogonality_weight": None if weight is None else round(weight, 4),
        "ratchet": {"owing_max": owing_max, "cells_to_judge_per_hour_best": best_judge,
                    "orthogonal_cells_to_judge_per_hour_best": best_ortho,
                    "regression_reason": reason or None},
        "failures": failures,
        "owing": owing,
        "declared": exempted,
        "producers": rows,
    }


def tighten_ratchet(doc: dict[str, Any]) -> dict[str, Any] | None:
    """Ratchets fall only. Returns the new document when it moved, else None.

    The owing count may only fall and the two throughput bests may only rise. Seeding on a first
    run is not an improvement claim -- it is the baseline, recorded so the NEXT run has something
    to be measured against (an absent ratchet is UNMEASURED, never a pass by default).
    """
    rat = _ratchet_doc()
    moved = False
    if doc.get("registry", {}).get("available"):
        cur = rat.get("owing_max")
        if not isinstance(cur, (int, float)) or doc["n_owing"] < cur:
            rat["owing_max"] = doc["n_owing"]
            moved = True
        for field, key in (("cells_to_judge_per_hour_best", "cells_to_judge_per_hour"),
                           ("orthogonal_cells_to_judge_per_hour_best",
                            "orthogonal_cells_to_judge_per_hour")):
            val = doc.get(key)
            if not isinstance(val, (int, float)):
                continue
            cur = rat.get(field)
            if not isinstance(cur, (int, float)) or val > cur:
                rat[field] = val
                moved = True
    if not moved:
        return None
    rat["updated_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    rat.setdefault("law", "LAWS 7 -- EVERY PRODUCER OWES CELLS. This ratchet falls only.")
    return rat


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window-days", type=float, default=3.0)
    ap.add_argument("--yield-window-hours", type=float, default=YIELD_WINDOW_HOURS)
    ap.add_argument("--no-ratchet", action="store_true",
                    help="measure and report without tightening the ratchet on disk")
    # THE TWO HALVES KEEP THEIR OWN VERDICTS. The seat half (EVERY PRODUCER PRODUCES, 2026-09-15)
    # is fatal on a dead producer with no named inheritor and rides the fence battery, where that
    # backlog is the worklist. The law gate enforces the CELLS half, so a debt one half is still
    # working through cannot silence the other -- one exit code for two different laws is how a
    # gate comes to be disabled wholesale.
    ap.add_argument("--cells-only", action="store_true",
                    help="judge only EVERY PRODUCER OWES CELLS (the law-gate half)")
    args = ap.parse_args(argv)

    doc = audit(window_days=args.window_days)
    doc["cells_owed"] = yld = yield_audit(window_hours=args.yield_window_hours)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    if not args.no_ratchet:
        moved = tighten_ratchet(yld)
        if moved is not None:
            RATCHET.parent.mkdir(parents=True, exist_ok=True)
            RATCHET.write_text(json.dumps(moved, indent=1) + "\n", encoding="utf-8")

    print(f"producer yield: {doc['n_producers']} producer(s) over {args.window_days:g}d -> "
          f"{doc['census']}   (median {doc['median_rows']} rows)"
          + ("   [seat half REPORTED ONLY under --cells-only]" if args.cells_only else ""))
    for v in ((), ("DEAD", "STARVED", "UNMEASURED"))[not args.cells_only]:
        rs = [r for r in doc["producers"] if r["verdict"] == v]
        if not rs:
            continue
        print(f"\n  {v} {len(rs)}:")
        for r in rs[:12]:
            tail = (f" -> {str(r.get('replacement'))[:60]}" if v == "DEAD"
                    else f"  {str(r.get('why'))[:60]}")
            print(f"    {str(r['producer'])[:26]:26} {r['rows_in_window']!s:>7}{tail}")
    print(f"\nEVERY PRODUCER OWES CELLS ({yld['window_hours']:g}h): {yld['n_producers']} producer(s), "
          f"{yld['n_owing']} owing, {yld['n_declared']} declared")
    print(f"  cells to judge/h {yld['cells_to_judge_per_hour']}   orthogonal equivalent/h "
          f"{yld['orthogonal_cells_to_judge_per_hour']} "
          f"(weight {yld['orthogonality_weight']})   ratchet {yld['ratchet']}")
    top = [r for r in yld["producers"] if r["cells_to_judge_per_hour"]][:10]
    if top:
        print(f"  {'producer':30} {'emit/h':>9} {'uniq/h':>9} {'judge/h':>9} {'ortho':>8}")
        for r in top:
            print(f"  {str(r['producer'])[:30]:30} {r['cells_emitted_per_hour']:>9} "
                  f"{r['unique_cells_per_hour']:>9} {r['cells_to_judge_per_hour']:>9} "
                  f"{r['orthogonality_added']!s:>8}")
    for r in yld["owing"][:12]:
        print(f"  OWES  {str(r['producer'])[:28]:28} {r['compute_hours_window7d']!s:>8}h compute, "
              f"0 unique cells, no declaration")
    for f in yld["failures"]:
        print(f"  FAIL  {f}")
    print(f"  -> {OUT}")
    # A dead producer with NO declared alternative is the fatal state: the law says replace, and
    # there is nothing to replace it with. The second half is fatal on its own ratchets.
    seat_half = [] if args.cells_only else doc["dead_without_a_declared_replacement"]
    return 1 if (seat_half or yld["failures"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

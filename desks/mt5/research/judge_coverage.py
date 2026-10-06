"""JUDGE COVERAGE -- the judge tests 100% of what this desk mines, every hour, by BACKLOG.

    "the judge should test 100 percent of what this desk ever mines, every hour, 24/7, always"
    "all families should be hunted, all mechanisms, all unknowns, for maximum breadth -- not
     fixed like these six, every time"                                -- the principal, 2026-09-23

WHAT WAS MEASURED, AND WHY ORDER IS THE WHOLE PROBLEM. From 120,000 recent gate verdicts on the
trading box, 60 families were judged -- and the judged distribution had almost nothing to do with
the mined one. The docket's five largest populations were `cross_asset_residual` 55,190,
`overnight_drift` 26,721, `discovered` 24,052, `clock_transition` 20,081 and `execution_state`
13,660; the judged counts were `discovered` 22,009 (18% of the judge's whole recent capacity, on
a family BANNED from live capital, passing 0), then `orderflow_imbalance` 5,654, `vol_transition`
4,869, `liquidity_regime` 3,785, `session_range_breakout` 3,723. So the scarce judge re-tested a
handful of families every hour while the largest mined populations waited, and spent a fifth of
itself on cells that could never reach the book.

That is not a gauntlet defect. `external_gauntlet` is SEALED and takes the docket it is handed
under a bar budget, so **the order of the docket IS the selection**: a family at the tail is not
"lower priority", it is never judged at all. This organ therefore does its whole job at INTAKE,
upstream of the sealed judge, and changes nothing about how a cell is judged once it arrives.

COVERAGE, NOT ROTATION. Rotation asks "whose turn is it"; coverage asks "what has never been
answered". The quantity this organ drives to zero is the UNJUDGED BACKLOG, per family:

    backlog(family) = docket rows of that family carrying NO verdict in the gate ledger

Every family holding backlog is given a quota of the hour -- a FLOOR first, so a family of nine
cells is reached at all, and then THE REMAINDER GOES BY EXPECTED VALUE PER JUDGE-SECOND, not by
who mined hardest. The floor is the breadth mandate and never moves; the remainder is where the
return is, and spending it in proportion to backlog spends it on the desk's own output rather
than on what an hour of judge is worth. The ranking is
`p_optimistic x net-of-cost value if it passes x (1 + marginal breadth) / (seconds per cell x the
family's bar cost)`, every term measured by an organ that already exists -- the decayed Beta
posterior in `libs/research/research_priors` (which THIS organ also feeds, see `learn_priors`),
`reports/NET_EDGE.json`, `reports/EFFECTIVE_BREADTH.json` cluster occupancy, and the bar ratios
the sealed gauntlet budgets in. A family with no record yet ranks on the UPPER credible bound, so
it is explored rather than buried. The docket is then emitted as a weighted
interleave of the families, which makes EVERY PREFIX of it family-balanced: whatever slice of the
docket the gauntlet's budget actually reaches this hour, that slice contains every family with
backlog, at its quota. Nothing is truncated, nothing is deleted, nothing is deferred by this
organ -- the whole corpus still ships, in an order that spends the budget on coverage.

WHAT IT NEVER DOES (GROWTH_GOVERNANCE Rule 1). It removes no cell, lowers no bar, caps no book
and shrinks no budget. Reordering is the one intervention that cannot cost throughput: the same
rows reach the same judge under the same budget, and the only thing that changes is which
question the hour answers first. Mining stays unrestricted; a family's population may grow as
fast as the miners can grow it.

THE RATCHET, AND WHY IT IS ON THE CARRIED COHORT. `data/judge_backlog_ratchet.json` records, per
family, the backlog at each reading. Raw backlog RISES whenever miners outrun the judge, which is
mining working, not intake failing -- a fence on the raw number would punish the desk for mining
and would be switched off inside a week. So the ratcheted quantity is the CARRIED cohort: rows
that were already in the backlog at the previous reading and are still unjudged now. A cell
leaves that cohort exactly one way, by being judged, so the carried count can only fall, and any
family whose carried count fails to fall while it held backlog was starved -- which is the defect
this organ exists to make impossible. `scripts/check_judge_coverage.py` is that fence.

WHAT IT PUBLISHES -- `reports/JUDGE_COVERAGE.json`, per family:
`mined`, `queued` (this hour's realised quota in the head window), `judged_window`,
`unjudged`, `oldest_unjudged_age_h`, `carried`, `drained`, `window_h`, plus the full
`value_ranking` so the remainder's choice is inspectable and the fence can check it was followed.

AND THE OPPORTUNITY COST, which is what makes this ROI rather than bookkeeping: `value_at_risk`
(expected value sitting unjudged), `value_deferred` (the part this hour cannot reach),
`value_forgone_per_hour` and `capacity_short`. Those go to `research/judging_throughput.py`,
which is the organ that can answer them -- when the hour cannot reach the value at risk the box
raises workers and cadence. The answer to a valuable backlog is always MORE JUDGE, never a
smaller docket: nothing here throttles a miner to make a number look green.

THE BANNED FAMILY IS ALREADY OUT, AND THIS ORGAN DOES NOT RE-DO IT. `merge_hypotheses` routes
every row of a family banned from live capital (`mt5desk.live_policy.DEFAULT_BANNED_FAMILIES`)
into `data/hypotheses/study_bank.json` with the ban as the recorded reason, before the docket is
written; `external_gauntlet` sets banned cells aside again at its own door. Those rows are kept
forever and the miners keep producing them -- what stops is the SPENDING. This organ reads the
study bank only to report `mined` honestly: a family's mined population is what the desk mined,
not what it chose to judge.

NO FIXED FAMILY SET. The family universe here is `mt5desk.families.live_family_names()` -- the
union of every registered population the forward engine can actually resolve -- unioned with
whatever the docket and the ledger name. A family invented tomorrow is queued and judged the hour
it first appears in the docket, with no edit to this file.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
HYP = BASE / "data" / "hypotheses"
DOCKET = HYP / "external_survivors.json"
STUDY_BANK = HYP / "study_bank.json"
GATE_LEDGER = HYP / "gate_verdict_ledger.jsonl"
REPORTS = BASE / "reports"
REPORT = REPORTS / "JUDGE_COVERAGE.json"
#: research/occupancy_map.py's hourly artifact: target cells and per-candidate orthogonality.
OCCUPANCY_REPORT = REPORTS / "OCCUPANCY_MAP.json"
RATCHET = BASE / "data" / "judge_backlog_ratchet.json"

#: The judging window every family is measured against: one hour, because the principal's order
#: is "every hour, 24/7". A family's OWN window widens from here by how long its own quota needs
#: to drain its own backlog -- a family of 55,190 cells is not starved for being large.
WINDOW_H = 1.0

#: The share of the hour handed out as an equal FLOOR before anything is proportional. A floor is
#: what makes a nine-cell family reachable at all; without it proportional allocation is a
#: winner-take-all rule that rediscovers the exact starvation this organ was built to end.
FLOOR_SHARE = 0.25

#: The judge's capacity is MEASURED from its own ledger (the busiest recent hour), never assumed
#: off a machine size -- CLAUDE.md's 8 GB/96 GB note is the standing lesson about inventing one.
#: The floor exists only so a cold tree with no ledger still produces a usable allocation.
CAPACITY_FLOOR = 500
CAPACITY_LOOKBACK_H = 168.0

#: Ledger rows whose downstream status begins with this were never actually judged -- the sweep's
#: build budget ran out before the cell was computed. Counting them as judged is precisely the
#: trap `external_gauntlet._stamped_but_unjudged` documents: it starved 1,544 cells forever.
NOT_JUDGED_PREFIX = "NOT_RUN"


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _ts(raw: object) -> datetime | None:
    txt = str(raw or "").strip()
    if not txt:
        return None
    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _cell_id(row: dict[str, Any]) -> str | None:
    """The gauntlet's OWN identity function, imported, never re-implemented.

    Two implementations of an identity are two identities, and the whole measurement here turns
    on matching a docket row to the verdict the sealed judge recorded for it.
    """
    try:
        desk = str(BASE)
        if desk not in sys.path:
            sys.path.insert(0, desk)
        from research.frontier_identity import docket_cell_id
    except Exception:
        return None
    try:
        return str(docket_cell_id(row))
    except Exception:
        return None


def live_families() -> frozenset[str]:
    """Every family the desk can actually resolve -- the registry's live set, never a literal.

    An unreadable registry returns EMPTY and the caller then falls back to the docket's own
    families: losing this import must never narrow what gets judged (L1.28a).
    """
    try:
        desk = str(BASE)
        if desk not in sys.path:
            sys.path.insert(0, desk)
        from mt5desk.families import live_family_names
        return frozenset(live_family_names())
    except Exception:
        return frozenset()


def banned_from_capital() -> frozenset[str]:
    """Families the desk has forbidden from live capital, read from the policy that enforces it.

    `merge_hypotheses` already routes these rows OUT of the judging docket and into the study
    bank, and `external_gauntlet` sets them aside again at its own door. This is the same answer
    at the allocator: a family that cannot reach the book is given no quota, so no hour of the
    scarce judge is allocated to an outcome the desk has already refused. The rows are still
    counted as MINED -- mining is unrestricted and stays so -- and they still ship in the docket,
    behind every family that can actually repay a gate-second.
    """
    try:
        desk = str(BASE)
        if desk not in sys.path:
            sys.path.insert(0, desk)
        from research.merge_hypotheses import live_banned_families
        return frozenset(live_banned_families())
    except Exception:
        return frozenset()


def judged_index(path: Path | None = None, *, now: datetime | None = None,
                 window_h: float = WINDOW_H) -> tuple[set[str], dict[str, int], dict[str, int]]:
    """(cells carrying a real verdict, judged-per-family all-time, judged-per-family in window).

    A row is JUDGED only when the ledger recorded a real terminal gate or a successful pass.
    `UNKNOWN` is the sealed evaluator's unmeasured path, even when it carries passed=False.
    Neither that path nor a `NOT_RUN_*` deferral clears the backlog or earns judge capacity.
    """
    seen: set[str] = set()
    total: dict[str, int] = {}
    in_window: dict[str, int] = {}
    cutoff = (now or datetime.now(tz=UTC)).timestamp() - window_h * 3600.0
    try:
        with (path or GATE_LEDGER).open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return seen, total, in_window
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
            continue
        if row.get("passed") is not True and str(row.get("terminal_gate") or "") in ("", "UNKNOWN"):
            continue
        fam = str(row.get("family") or "")
        cell = str(row.get("cell") or "")
        if cell:
            seen.add(cell)
        if not fam:
            continue
        total[fam] = total.get(fam, 0) + 1
        at = _ts(row.get("at"))
        if at is not None and at.timestamp() >= cutoff:
            in_window[fam] = in_window.get(fam, 0) + 1
    return seen, total, in_window


def measured_capacity(judged_total: dict[str, int], ledger: Path | None = None,
                      *, now: datetime | None = None) -> int:
    """Cells the judge demonstrably rules on in ONE hour -- its busiest recent hour, measured.

    Measured and never assumed: the allocation below divides THIS number, so inventing it off a
    machine size would size the hour for a machine the code is not on.
    """
    best = 0
    cutoff = (now or datetime.now(tz=UTC)).timestamp() - CAPACITY_LOOKBACK_H * 3600.0
    per_hour: dict[str, int] = {}
    try:
        with (ledger or GATE_LEDGER).open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
                    continue
                if row.get("passed") is not True and str(row.get("terminal_gate") or "") in ("", "UNKNOWN"):
                    continue
                at = _ts(row.get("at"))
                if at is None or at.timestamp() < cutoff:
                    continue
                key = at.strftime("%Y-%m-%dT%H")
                per_hour[key] = per_hour.get(key, 0) + 1
    except OSError:
        per_hour = {}
    if per_hour:
        best = max(per_hour.values())
    return max(best, CAPACITY_FLOOR, sum(judged_total.values()) // 24)


def sustained_rate(ledger: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    """Cells the judge ACTUALLY rules on per hour, averaged over 24 h and 7 d. The drain meter.

    WHY THE PEAK HOUR CANNOT BE THE DRAIN RATE (measured 2026-09-30 on the box). The sweep stamps
    every verdict of one pass with ONE `at`, so a single large pass lands in a single hour and
    `measured_capacity` reads that hour as the judge's hourly speed. JUDGE_COVERAGE then published
    `hours_to_drain 25.1` on 1,398,253 unjudged cells while the same box's JUDGING_RATE counted
    ~220 verdicts/hour -- a true drain of ~265 days, and in fact no drain at all, because the desk
    creates ~8,300 cells a day against ~5,300 verdicts. The peak stays the ALLOCATION size (how far
    down the docket one pass can reach); the drain is the average, and it is net of creation.
    """
    t = now or datetime.now(tz=UTC)
    cuts = {"24h": t.timestamp() - 24 * 3600.0, "7d": t.timestamp() - 168 * 3600.0}
    counts = {"24h": 0, "7d": 0}
    # THE SAME WINDOW'S UNKNOWN ROWS, counted beside it (2026-09-30). The ledger holds only the
    # verdicts `run_gauntlet` emitted -- judged cells and its unmeasured branch, never a NOT_RUN
    # row -- so UNKNOWN / rows here is the share of cells that REACHED the judge and got no
    # ruling. That is what the 7-day "43%" was; it is published here so it is never again set
    # against a per-sweep figure computed over a different denominator (see `unknown_breakdown`).
    unknown = {"24h": 0, "7d": 0}
    try:
        with (ledger or GATE_LEDGER).open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
                    continue
                at = _ts(row.get("at"))
                if at is None:
                    continue
                _unk = (row.get("passed") is not True
                        and str(row.get("terminal_gate") or "") in ("", "UNKNOWN"))
                for w, cut in cuts.items():
                    if at.timestamp() >= cut:
                        counts[w] += 1
                        unknown[w] += int(_unk)
    except OSError:
        return {"status": "UNMEASURED", "why": "gate ledger unreadable"}
    return {"status": "MEASURED", "counts": counts,
            "per_hour_24h": round(counts["24h"] / 24.0, 3),
            "per_hour_7d": round(counts["7d"] / 168.0, 3),
            "unknown_counts": unknown,
            # None, never 0.0, on an empty window: no verdicts is UNMEASURED (L1.28a).
            "unknown_share_24h": (round(unknown["24h"] / counts["24h"], 6)
                                  if counts["24h"] else None),
            "unknown_share_7d": (round(unknown["7d"] / counts["7d"], 6)
                                 if counts["7d"] else None),
            # The drain rate above counts an UNKNOWN as judged; this is the rate of RULINGS.
            "named_per_hour_24h": round((counts["24h"] - unknown["24h"]) / 24.0, 3)}


def drain(backlog_now: int, per_hour: float | None, *, prior_backlog: int | None,
          prior_at: datetime | None, now: datetime) -> dict[str, Any]:
    """Hours to drain on the SUSTAINED rate, and whether the backlog is falling at all.

    The backlog's own movement between two readings is the net of judging and creation, so it
    needs no separate creation meter: growing means no finite ETA exists, and saying so is the
    measurement (a large finite number would be a lie of a different size).
    """
    out: dict[str, Any] = {"sustained_per_hour": per_hour}
    growth = None
    if prior_backlog is not None and prior_at is not None:
        hours = (now.timestamp() - prior_at.timestamp()) / 3600.0
        if hours >= 0.25:
            growth = (backlog_now - prior_backlog) / hours
    out["backlog_growth_per_hour"] = round(growth, 3) if growth is not None else None
    if not per_hour or per_hour <= 0:
        out.update(status="UNMEASURED", hours=None,
                   why="no judged verdicts in the last 24 h: the drain rate is unmeasured")
        return out
    out["hours_at_zero_creation"] = round(backlog_now / per_hour, 1)
    if backlog_now == 0:
        out.update(status="DRAINED", hours=0.0)
    elif growth is not None and growth >= 0:
        out.update(status="GROWING", hours=None,
                   net_per_day=round(growth * 24.0, 1),
                   why="the backlog rose since the last reading: creation outpaces the judge")
    elif growth is not None:
        out.update(status="DRAINING", hours=round(backlog_now / -growth, 1))
    else:
        out.update(status="DRAINING_GROSS", hours=out["hours_at_zero_creation"],
                   why="no prior reading: ETA ignores creation")
    return out


#: Judge cost is BUDGETED IN BARS, not in cells -- the sealed gauntlet says so in its own
#: docstring -- so one M5 cell costs about twelve H1 cells of the same hour. These are the bar
#: ratios against H1, which is what makes "per judge-second" a real denominator rather than a
#: constant that cancels out of the ranking.
_BAR_COST = {"M1": 60.0, "M5": 12.0, "M15": 4.0, "M30": 2.0, "H1": 1.0, "H4": 0.25, "D1": 0.042}


def _tf_of(row: dict[str, Any]) -> str:
    params = row.get("params") or {}
    tf = str(params.get("timeframe") or row.get("timeframe") or "H1").upper()
    return tf if tf in _BAR_COST else "H1"


def realised_pass_rates(path: Path | None = None) -> dict[str, dict[str, float]]:
    """WHAT EACH FAMILY ACTUALLY DID AT THE JUDGE, counted from the gate ledger itself.

    THE MEASUREMENT THAT MADE THIS NECESSARY (2026-09-23). The ranking below spends
    `p_optimistic`, and every family in the published ranking carried `prior_n: 0`,
    `prior_status: PRIOR`, `p_optimistic: 1.0` -- a flat pass probability, so the aim was being
    set by net value and breadth alone while 3,368 verdicts across 27 families sat in
    `gate_verdict_ledger.jsonl` saying exactly which families pass. `learn_priors` below feeds the
    stored posterior, but its cursor advances past rows it could not charge, so a verdict lost
    that way is lost for good. THE LEDGER IS THE EVIDENCE AND IT IS RE-READABLE: counting it here
    every pass cannot be made stale by a cursor, and the two numbers are published side by side so
    a disagreement between them is visible rather than silent.

    Returned per family: `judged`, `passed`, `pass_rate`, and the Beta(1+passed, 1+failed)
    posterior this evidence supports -- mean and 95% upper bound. A family with no verdicts gets
    Beta(1,1): mean 0.5, upper bound 1.0, which is how an unjudged family stays EXPLORED rather
    than being ranked below a family measured to fail.
    """
    judged: dict[str, int] = {}
    passed: dict[str, int] = {}
    try:
        with (path or GATE_LEDGER).open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
            continue
        fam = str(row.get("family") or "")
        if not fam:
            continue
        ok = row.get("passed")
        gate = str(row.get("terminal_gate") or "")
        # AN UNMEASURED CELL IS NOT A FAILURE. `UNKNOWN` is the sealed judge's unmeasured path, so
        # it counts toward nothing here: charging it as a rejection would teach the aim that a
        # family does not work when what happened is that nobody looked.
        if ok is not True and gate in ("", "UNKNOWN"):
            continue
        judged[fam] = judged.get(fam, 0) + 1
        if ok is True or str(ok).lower() == "true":
            passed[fam] = passed.get(fam, 0) + 1
    out: dict[str, dict[str, float]] = {}
    for fam, n in judged.items():
        k = passed.get(fam, 0)
        a, b = 1.0 + k, 1.0 + (n - k)
        mean = a / (a + b)
        sd = math.sqrt(max(mean * (1.0 - mean) / (a + b + 1.0), 0.0))
        out[fam] = {"judged": float(n), "passed": float(k),
                    "pass_rate": (k / n) if n else 0.0,
                    "mean": mean, "hi": min(1.0, mean + 1.96 * sd)}
    return out


def family_priors(families: list[str],
                  realised: dict[str, dict[str, float]] | None = None
                  ) -> dict[str, dict[str, float]]:
    """The desk's OWN learned pass probability per family, with its optimism kept.

    `libs/research/research_priors.prior_for("family", fam)` is a decayed Beta posterior whose
    unseen state is Beta(1,1) -- mean 0.5, never zero. The ranking below uses the UPPER credible
    bound, not the mean, so a family with no record yet is EXPLORED rather than buried: optimism
    under uncertainty is the only rule that can discover that a new family is good. A family with
    a long record has a tight interval and is ranked on what it actually did.

    AND IT NOW USES THE EVIDENCE THAT IS ACTUALLY THERE. When the ledger holds MORE verdicts for a
    family than the stored posterior was ever taught -- which was true of every family on the desk
    the day this was written -- the realised counts are the better-informed posterior and they are
    the one the ranking spends. The stored number is still published beside it, so the gap between
    what the desk learned and what it recorded is inspectable rather than silently papered over.
    Optimism is unchanged in both directions: an unjudged family still ranks on 1.0.
    """
    out: dict[str, dict[str, float]] = {}
    seen = realised if realised is not None else realised_pass_rates()
    try:
        root = str(BASE.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.research.research_priors import prior_for
    except Exception:
        def prior_for(_dim: str, _key: str) -> Any:                  # type: ignore[misc]
            raise RuntimeError("research_priors unavailable")
    for fam in families:
        row = {"p": 0.5, "p_optimistic": 1.0, "n": 0.0, "status": 0.0, "source": 0.0}
        try:
            pr = prior_for("family", fam)
            row = {"p": float(pr.mean), "p_optimistic": float(pr.interval()[1]),
                   "n": float(pr.n), "status": 1.0 if pr.status == "POSTERIOR" else 0.0,
                   "source": 0.0}
        except Exception:
            pass
        r = seen.get(fam)
        if r and float(r["judged"]) > float(row["n"]):
            row = {"p": float(r["mean"]), "p_optimistic": float(r["hi"]),
                   "n": float(r["judged"]), "status": 1.0, "source": 1.0,
                   "stored_n": float(row["n"]), "stored_p": float(row["p"])}
        out[fam] = row
    return out


def learn_priors(ledger: Path | None = None, *, since: str = "",
                 limit: int = 20_000, state_dir: Path | None = None) -> dict[str, Any]:
    """FEED THE PRIOR THE RANKING SPENDS. Every new gate verdict updates its family's posterior.

    THE LOOP WAS OPEN AND THE RANKING WOULD HAVE BEEN FLAT FOREVER. Measured when this was
    written: `data/research_priors/beta.json` held ZERO rows under the `family` dimension, so
    `prior_for("family", ...)` returned Beta(1,1) for every family on the desk -- an allocator
    ranking by a learned pass probability that nothing was teaching. Eight organs call
    `record_outcome` and not one of them passes a family, so the dimension existed and was never
    fed.

    Each verdict is classified by `research_priors.classify` from its terminal gate, because WHY
    a family failed is the part that matters: one killed by costs is not one with no edge, and
    the two should move the next hour's allocation opposite ways. `since` is the previous
    reading's high-water stamp, so a verdict is charged exactly once however often this runs --
    double-counting a ledger is how a posterior becomes confident about nothing.
    """
    out: dict[str, Any] = {"recorded": 0, "families": 0, "cursor": since, "status": "OK"}
    try:
        root = str(BASE.parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.research.research_priors import load, record_outcome, save
    except Exception as exc:
        out.update(status="UNMEASURED", why=f"{type(exc).__name__}: {exc}")
        return out
    try:
        with (ledger or GATE_LEDGER).open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()[-limit:]
    except OSError as exc:
        out.update(status="UNMEASURED", why=f"{type(exc).__name__}: {exc}")
        return out
    state = load(state_dir)
    taught = state.get("beta") if isinstance(state, dict) else None
    taught_fams = set((taught or {}).get("family") or {}) if isinstance(taught, dict) else set()
    untaught: set[str] = set()
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            fam_seen = str(json.loads(ln).get("family") or "")
        except (ValueError, AttributeError):
            continue
        if fam_seen and fam_seen not in taught_fams:
            untaught.add(fam_seen)
    out["backfilled_families"] = len(untaught)
    seen_fams: set[str] = set()
    high = since
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        at = str(row.get("at") or "")
        fam = str(row.get("family") or "")
        if not fam or not at:
            continue
        # THE CURSOR SKIPS ROWS THE POSTERIOR NEVER GOT (measured 2026-09-23). `high` only
        # advances on a row that recorded, but a LATER row that records carries the cursor past
        # every row before it -- so one failure loses the whole block behind it, permanently. The
        # ledger held 3,368 verdicts across 27 families and the stored posterior held 2 families
        # and 9 updates, with the cursor already at the ledger's last stamp: unrecoverable by
        # `since` alone. A family with NO stored row has demonstrably never been taught, so it is
        # backfilled whatever the cursor says. It gains a row on the first such pass and is
        # cursor-governed from then on, so this cannot double-count a family twice.
        if since and at <= since and fam not in untaught:
            continue
        if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
            continue
        passed = row.get("passed")
        survived = passed is True or str(passed).lower() == "true"
        gate = str(row.get("terminal_gate") or "")
        # AN UNMEASURED CELL IS NOT EVIDENCE AGAINST THE FAMILY, and charging it as one is the
        # exact mistake `record_outcome` documents: "charging it as a Beta failure would teach the
        # allocator that the thing does not work when what happened is that nobody looked."
        # `UNKNOWN` is the sealed judge's unmeasured path (see `unknown_breakdown`), so it is
        # recorded in the Dirichlet as `unmeasured` and moves no pass probability at all.
        outcome = ("survived" if survived
                   else ("unmeasured" if gate in ("", "UNKNOWN") else "REJECTED"))
        try:
            record_outcome(outcome, family=fam,
                           rejection_reason=gate, failure_class=gate, state=state,
                           state_dir=state_dir, persist=False)
        except Exception:
            continue
        seen_fams.add(fam)
        out["recorded"] = int(out["recorded"]) + 1
        high = max(high, at)
    if out["recorded"]:
        try:
            save(state, state_dir)
        except Exception as exc:                                         # pragma: no cover
            out.update(status="UNMEASURED", why=f"save failed: {type(exc).__name__}: {exc}")
    out["families"] = len(seen_fams)
    out["cursor"] = high
    return out


#: The sealed judge's own artifact, read (never written) for the census below.
GATES_REPORT = REPORTS / "universal_gates_external.json"


#: What `unknown_share` is divided by. A share read under another basis is not comparable, so
#: the ratchet treats a basis change as a first reading (UNMEASURED) rather than a rise or a fall.
UNKNOWN_SHARE_BASIS = "judged_verdicts"


def unknown_breakdown(path: Path | None = None) -> dict[str, Any]:
    """WHAT `terminal_gate: UNKNOWN` ACTUALLY IS -- measured, not assumed.

    MEASURED ON THE BOX across 60,000 verdicts (2026-09-22T22:46 -> 2026-09-23T05:42): UNKNOWN
    44,432 (74%), in_sample_screen 13,915 (23%), deflated_sharpe 1,641 (2.7%), PASSED 4. So the
    multiple-testing charge everyone blames kills under 3%, and three quarters of the judge
    returned no named gate at all.

    IT IS NOT A MISSING GATE AND IT IS NOT MISSING BARS. `external_gauntlet._append_gate_ledger`
    writes `str(v.get("terminal_gate") or ("PASSED" if v.get("passed") else "UNKNOWN"))`, and
    exactly one verdict path omits `terminal_gate`: the UNMEASURED branch, which emits
    `{"passed": False, "unmeasured": True, "stages": {"observations": ...}}` for a cell whose
    signals produced fewer than the 60 daily observations CPCV needs. UNKNOWN IS THAT BRANCH.

    MEASURED ON THIS TREE, 748 unmeasured of 6,787 verdicts: 615 of them (82%) have days == 0 --
    the cell fired NOT ONCE -- and EVERY ONE of those symbols has its H1 parquet present, so the
    cause is not absent bars and nothing needs converting. They are specs that never fire,
    concentrated in four families (session_range_breakout 336, carry 140, discovered 79,
    event_reaction 56). The remaining 133 fire between 1 and 59 days: too rare to judge, which is
    a fact about the SEARCH that proposed them and not evidence against any edge.

    So the route is UPSTREAM, to whatever mints these specs, and this census is what it needs:
    per family, how many of its cells never fired at all. Nothing here removes a cell -- a
    never-firing spec on a short history can fire on a longer one, and an order is not a ban.
    """
    doc = _read(path or GATES_REPORT)
    out: dict[str, Any] = {"status": "UNMEASURED", "source": str(path or GATES_REPORT)}
    verdicts = (doc or {}).get("verdicts") if isinstance(doc, dict) else None
    if not isinstance(verdicts, list) or not verdicts:
        out["why"] = "the sealed judge has written no verdicts here"
        return out
    never: dict[str, int] = {}
    too_rare: dict[str, int] = {}
    n_unmeasured = 0
    for v in verdicts:
        if not isinstance(v, dict) or not v.get("unmeasured"):
            continue
        n_unmeasured += 1
        fam = str(v.get("family") or "")
        if int(v.get("days") or 0) == 0:
            never[fam] = never.get(fam, 0) + 1
        else:
            too_rare[fam] = too_rare.get(fam, 0) + 1
    named = name_unknowns(path)
    by_reason: dict[str, int] = {}
    for row in named.values():
        r = str(row.get("reason") or "unnamed")
        by_reason[r] = by_reason.get(r, 0) + 1
    total = len(verdicts)
    # THE DENOMINATOR IS THE CELLS THAT REACHED THE JUDGE (2026-09-30). This divided by EVERY row
    # in the report, and the report also carries the cells the sweep never built -- NOT_RUN_*
    # (data missing, build failed, modifier refused, budget deferred, gate-1 prior rejections),
    # `passed: null`, none of which ever reached the gates. Measured on the box's noon sweep:
    # 20,247 of 29,466 rows were NOT_RUN, so the published 9.55% UNKNOWN (2,814 cells) was really
    # >=30.5% of the ~9,219 cells actually judged -- and it FELL whenever more cells failed to
    # build, which is the ratchet rewarding the wrong thing. The gate ledger has only ever held
    # `run_gauntlet`'s own verdicts, so its 7-day 43% (53,460 of 124,342) was the right basis all
    # along; this now uses the same one, and publishes the old ratio beside it by name.
    judged = sum(1 for v in verdicts if isinstance(v, dict) and (
        v.get("unmeasured") or (v.get("passed") is not None and not str(
            v.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX))))
    out.update({
        "by_reason": by_reason,
        "named_cells": len(named),
        "status": "OK",
        "verdicts": total,
        "judged_verdicts": judged,
        "not_run_rows": total - judged,
        "unknown_total": n_unmeasured,
        "unknown_share": (round(n_unmeasured / judged, 6) if judged else None),
        "unknown_share_basis": UNKNOWN_SHARE_BASIS,
        "unknown_share_of_all_rows": round(n_unmeasured / max(total, 1), 6),
        "causes": {
            "never_fires_days_0": {
                "cells": sum(never.values()),
                "by_family": dict(sorted(never.items(), key=lambda kv: -kv[1])),
                "route": ("the spec never fired on bars that ARE present -- upstream, to the "
                          "compiler that mints it; nothing to convert, no bars are missing"),
            },
            "too_rare_1_to_59_days": {
                "cells": sum(too_rare.values()),
                "by_family": dict(sorted(too_rare.items(), key=lambda kv: -kv[1])[:20]),
                "route": ("fires too rarely for CPCV's 60 observations -- a fact about the "
                          "search, recorded as `unmeasured` in the priors so it moves no pass "
                          "probability (nobody looked; that is not evidence against the edge)"),
            },
        },
        "why_unknown": ("external_gauntlet emits no `terminal_gate` on its UNMEASURED branch and "
                        "_append_gate_ledger defaults that to UNKNOWN; the judge is sealed, so "
                        "this is named here rather than fixed there"),
    })
    return out


#: The bank of cells the judge PROVED it cannot rule on, with the named reason and the bar file
#: size at the moment they were parked. Kept forever, never deleted, and re-admitted the moment
#: the symbol's bars grow -- a spec that never fired on a short history can fire on a longer one,
#: so this is a filter with a measured re-open condition, never a ban.
UNRUNNABLE_BANK = HYP / "unrunnable_specs.json"
UNIVERSE = BASE / "data" / "universe"


def _bar_bytes(sym: str, tf: str = "H1") -> int:
    """The symbol's bar file size on `tf` -- the cheap monotone proxy for "the history grew"."""
    try:
        return (UNIVERSE / f"{sym}_{tf or 'H1'}.parquet").stat().st_size
    except OSError:
        return 0


#: THE OTHER HALF OF THE PERMANENT CELL LEAK (2026-09-30). A cell the judge could not BUILD --
#: its bars absent on its own chart, or its signal construction failing -- is recorded
#: `passed: None, downstream_status: NOT_RUN_*`, which `judged_index` rightly refuses to call
#: judged. So it stayed "never judged", which is the FIRST key of the docket order, and came back
#: at the head of every sweep to fail again: measured on the box, 20,247 of 29,466 pre-warm
#: builds failed on build/data in one sweep. Those cells are parked here with a named reason and
#: re-admitted on the one event that could change the outcome -- their bars appearing or growing,
#: or, for a construction failure, the passage of BUILD_FAILED_RETRY_DAYS (code ships in between).
#: Deferrals for budget (NOT_RUN_BUILD_BUDGET_DEFERRED) are work not yet done and are never parked.
PARKED_NOT_RUN = {"NOT_RUN_DATA_MISSING": "data_missing",
                  "NOT_RUN_BUILD_FAILED": "build_failed"}
BUILD_FAILED_RETRY_DAYS = 7.0


def _prewarm_share(path: Path | None = None) -> float | None:
    """The share of the last sweep's pre-warm builds that failed on build or data."""
    doc = _read(path or GATES_REPORT)
    pw = (doc or {}).get("prewarm") if isinstance(doc, dict) else None
    if not isinstance(pw, dict):
        return None
    sub = int(pw.get("submitted") or 0)
    fails = pw.get("failures") if isinstance(pw.get("failures"), dict) else {}
    bad = sum(int(v or 0) for k, v in fails.items()
              if str(k) in ("NOT_RUN_DATA_MISSING", "NOT_RUN_BUILD_FAILED", "FAIL_3X", "ERROR",
                            "SAVE_FAILED"))
    return round(bad / sub, 6) if sub else None


def name_not_run(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Every cell the judge could not build, with its named reason and the bars it needs."""
    doc = _read(path or GATES_REPORT)
    out: dict[str, dict[str, Any]] = {}
    verdicts = (doc or {}).get("verdicts") if isinstance(doc, dict) else None
    if not isinstance(verdicts, list):
        return out
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        reason = PARKED_NOT_RUN.get(str(v.get("downstream_status") or ""))
        cell = str(v.get("cell") or "")
        if not reason or not cell:
            continue
        sym = str(v.get("sym") or "")
        tf = _tf_of(v)
        why = str(v.get("why") or "")
        for cand in ("M1", "M5", "M15", "M30", "H4", "D1"):
            if f" {cand} parquet" in f" {why}":
                tf = cand
        out[cell] = {"reason": reason, "sym": sym, "family": v.get("family"), "tf": tf,
                     "days": 0, "bar_bytes": _bar_bytes(sym, tf), "why": why[:200],
                     "route": ("bars absent on the cell's own chart: re-admitted the moment "
                               "they appear" if reason == "data_missing" else
                               "signal construction failed: re-admitted on bar growth or after "
                               f"{BUILD_FAILED_RETRY_DAYS:.0f} days of code changes")}
    return out


def name_unknowns(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """EVERY UNKNOWN GETS A NAMED REASON. The class stops existing as a category.

    An unnamed terminal state is the defect, whatever the cause turns out to be -- so this joins
    the sealed judge's own verdict rows to a reason per CELL, and the residue that cannot be
    joined is named too (`no_verdict_row`) rather than left inside a bucket. A new cause appears
    as its own name the day it appears.
    """
    doc = _read(path or GATES_REPORT)
    out: dict[str, dict[str, Any]] = {}
    verdicts = (doc or {}).get("verdicts") if isinstance(doc, dict) else None
    if not isinstance(verdicts, list):
        return out
    for v in verdicts:
        if not isinstance(v, dict) or not v.get("unmeasured"):
            continue
        cell = str(v.get("cell") or "")
        if not cell:
            continue
        sym = str(v.get("sym") or "")
        fam = str(v.get("family") or "")
        days = int(v.get("days") or 0)
        why = str((((v.get("stages") or {}).get("observations")) or {}).get("why") or "")
        # THE CELL'S OWN CHART, not H1: an M15 cell with no M15 file read as "bars present" off
        # its H1 sibling and was parked as a spec that never fires.
        tf = _tf_of(v)
        _head = cell.split(".", 1)[0]
        if "@" in _head and _head.rsplit("@", 1)[1].upper() in _BAR_COST:
            tf = _head.rsplit("@", 1)[1].upper()          # `cell_id` writes `<sym>@<TF>.`
        bars = _bar_bytes(sym, tf)
        # WHAT THE WRITER SAYS, WHEN IT SAYS IT (patch unknown_verdict_named): the judge names the
        # cause it saw -- an exception while building the series, a history the lockbox carve
        # consumed, signals that never became trades -- and that beats any inference made here.
        declared = str(v.get("unknown_reason") or "")
        params = v.get("params") if isinstance(v.get("params"), dict) else None
        need = REQUIRED_INPUT_KEY.get(fam)
        if declared == "series_exception":
            reason, route = "series_exception", (
                "the backtest raised while building this cell's daily series: a code defect, "
                f"re-admitted after {BUILD_FAILED_RETRY_DAYS:.0f} days like a build failure")
        elif params is not None and need and not params.get(need):
            reason, route = "missing_identity_input", (
                f"{fam} trades against a second instrument and this cell names no {need}, so it "
                "built with no input and fired nowhere. Its twin with the input named is minted "
                "by discovery_compiler.complete_inputs; this one is kept, never deleted")
        elif declared == "lockbox_consumed_history":
            reason, route = "lockbox_consumed_history", (
                "the cell fires, but its chart's history begins after the campaign lockbox cut, "
                "so the carve left under 60 development days: re-admitted as history grows")
        elif declared == "short_history_after_cut":
            reason, route = "short_history_after_cut", (
                "the cell traded, but on under 60 days, all of them after the lockbox cut, so the "
                "carve left no development window: re-admitted as history grows")
        elif days == 0 and bars == 0:
            reason, route = "missing_bars", ("no H1 bar file for this symbol: the conversion "
                                             "organ's bar supply (research/local_converter.py) "
                                             "owns it")
        elif days == 0:
            reason, route = "never_fires", ("the spec produced not one daily observation on bars "
                                            "that ARE present: an unrunnable spec, filtered at "
                                            "intake so it never reaches the docket again until "
                                            "this symbol's history grows")
        else:
            reason, route = "too_rare", (f"fires on {days} days, under the 60 CPCV needs: a fact "
                                         "about the search, re-admitted when the history grows")
        out[cell] = {"reason": reason, "route": route, "sym": sym, "family": v.get("family"),
                     "tf": tf, "days": days, "bar_bytes": bars, "why": why[:200],
                     **({"detail": declared} if declared else {})}
    return out


#: The key that names a peer/driver/factor/triangle family's other instrument. Mirrors
#: `discovery_compiler.PEER_KEY_BY_FAMILY` + `FACTOR_FAMILIES` + the first key of
#: `LEG_FAMILIES` (a test pins them together).
REQUIRED_INPUT_KEY: dict[str, str] = {"relative_value": "peer_symbol",
                                      "correlation_regime": "peer_symbol",
                                      "lead_lag": "driver_symbol",
                                      "cross_asset_residual": "factor_symbols",
                                      "pca_residual": "factor_symbols",
                                      "triangle": "leg_b_symbol"}


def unrunnable_bank(path: Path | None = None) -> dict[str, dict[str, Any]]:
    doc = _read(path or UNRUNNABLE_BANK)
    if not isinstance(doc, dict):
        return {}
    return {str(k): v for k, v in doc.items() if isinstance(v, dict)}


#: HOW MUCH THE HISTORY MUST GROW BEFORE A PARKED CELL IS WORTH THE JUDGE AGAIN.
#:
#: THE DEFECT THIS REPLACES (2026-09-30). Re-admission fired on `bar_bytes > parked bar_bytes`,
#: and the bar refresh rewrites every H1 parquet many times a day (238 of 239 symbols fresh inside
#: 48 h on the box), so every parked cell was re-admitted within hours and judged again -- a spec
#: that fired on 0 of ~2,100 days does not reach 60 because one more hour of bars arrived. The box
#: meanwhile read 43% of a week's verdicts as UNKNOWN (53,460 of 124,342). The judge was paying
#: for the same never-firing cells over and over; the ledger's cell|key de-duplication hid the
#: repeats from the verdict count, not from the compute.
#:
#: The rule now: a never-firing cell returns when its history has grown by a quarter; a too-rare
#: cell that fired on d days returns when the history has grown by the factor that would carry d
#: to the 60 observations CPCV needs (capped, so nothing waits longer than tripling); and every
#: parked cell returns after READMIT_MAX_DAYS regardless, so a new regime is always re-asked.
READMIT_GROWTH = 1.25
READMIT_GROWTH_CAP = 3.0
READMIT_MAX_DAYS = 90.0
CPCV_MIN_DAYS = 60


def readmit_due(row: dict[str, Any], *, now: datetime | None = None,
                bar_sizes: dict[tuple[str, str], int] | None = None) -> bool:
    """True when a parked cell's history has grown enough, or it has waited long enough."""
    parked_bytes = int(row.get("bar_bytes") or 0)
    key = (str(row.get("sym") or ""), str(row.get("tf") or "H1"))
    # A pass measures each chart once. Never retain this snapshot across passes: new
    # bars must re-admit every eligible sibling on the next reading.
    if bar_sizes is None:
        bars = _bar_bytes(*key)
    else:
        if key not in bar_sizes:
            bar_sizes[key] = _bar_bytes(*key)
        bars = bar_sizes[key]
    if parked_bytes <= 0:
        return bars > 0
    if row.get("reason") in ("build_failed", "series_exception"):
        _at = _ts(row.get("parked_at"))
        _t = now or datetime.now(tz=UTC)
        if _at is not None and (_t.timestamp() - _at.timestamp()) / 86400.0 \
                >= BUILD_FAILED_RETRY_DAYS:
            return True
    days = int(row.get("days") or 0)
    need = READMIT_GROWTH if days <= 0 else min(
        READMIT_GROWTH_CAP, max(READMIT_GROWTH, CPCV_MIN_DAYS / float(days)))
    if bars >= parked_bytes * need:
        return True
    parked_at = _ts(row.get("parked_at"))
    t = now or datetime.now(tz=UTC)
    return (parked_at is not None
            and (t.timestamp() - parked_at.timestamp()) / 86400.0 >= READMIT_MAX_DAYS)


def update_unrunnable_bank(named: dict[str, dict[str, Any]], *, at: str,
                           path: Path | None = None) -> dict[str, Any]:
    """Park every newly-named unrunnable cell, and RE-ADMIT any whose bars have since grown."""
    target = path or UNRUNNABLE_BANK
    bank = unrunnable_bank(target)
    now_ts = _ts(at)
    bar_sizes: dict[tuple[str, str], int] = {}
    readmitted = [cell for cell, row in bank.items()
                  if readmit_due(row, now=now_ts, bar_sizes=bar_sizes)]
    for cell in readmitted:
        bank.pop(cell, None)
    added = 0
    for cell, row in named.items():
        if row.get("reason") == "missing_bars":
            continue                       # owned by the conversion organ, not filtered here
        if cell not in bank:
            added += 1
        bank[cell] = {**row, "parked_at": at}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(bank, indent=1, default=str), "utf-8")
    except OSError:
        pass
    return {"parked_this_pass": added, "readmitted_on_bar_growth": len(readmitted),
            "bank_size": len(bank), "path": str(target)}


def family_value(path: Path | None = None) -> tuple[dict[str, float], float]:
    """What one PASS of this family is worth, net of cost: `reports/NET_EDGE.json`.

    `forward_slot_ranking_by_net` is the desk's own net-of-cost slot value per (family, symbol),
    already through the cost surface, the impact lab and the fusion cost model -- so nothing is
    re-derived here. A family the ranker has never scored takes the MEDIAN of those it has, which
    is the honest "no reason to think it is worse than typical"; zero would be a claim.
    """
    doc = _read(path or (REPORTS / "NET_EDGE.json"))
    best: dict[str, float] = {}
    if isinstance(doc, dict):
        for row in doc.get("forward_slot_ranking_by_net") or []:
            if not isinstance(row, dict):
                continue
            fam = str(row.get("family") or "")
            try:
                v = float(row.get("net_slot_value") or 0.0)
            except (TypeError, ValueError):
                continue
            if fam and v > best.get(fam, 0.0):
                best[fam] = v
    vals = sorted(best.values())
    # An ABSENT or empty NET_EDGE is UNMEASURED, not a measured zero (L1.28a). Returning 0.0 here
    # multiplied every family's ev to 0, so the ranking fell back to alphabetical order and the
    # prior, breadth and bar-cost terms it publishes stopped steering anything. Unit value keeps
    # every family at par on the value axis and lets the measured terms order them.
    median = vals[len(vals) // 2] if vals else 1.0
    return best, median


def family_breadth(path: Path | None = None) -> dict[str, float]:
    """Marginal BREADTH per family, from the effective-breadth machinery's cluster occupancy.

    `reports/EFFECTIVE_BREADTH.json` already answers "how many independent bets does this book
    actually hold" by mapping every sleeve to a cluster; a family that occupies no cluster adds a
    genuinely new bet and a family that already occupies six adds a sixth correlated one. The
    gain is 1/(1+occupancy) -- the diminishing return the effective rank itself exhibits. An
    absent artifact returns {} and every family scores the full gain, because an unmeasured
    breadth must never quietly demote a family (L1.28a).
    """
    doc = _read(path or (REPORTS / "EFFECTIVE_BREADTH.json"))
    occ: dict[str, float] = {}
    if isinstance(doc, dict):
        for sleeve in (doc.get("sleeve_clusters") or {}):
            parts = str(sleeve).split("_")
            if len(parts) >= 3:
                fam = "_".join(parts[1:-1])
                occ[fam] = occ.get(fam, 0.0) + 1.0
    return occ


def certified_family_shares() -> tuple[dict[str, float], int]:
    """The certified canon's family occupancy, from the existing search fitness reader.

    A missing or unreadable canon leaves the ranking neutral. It never becomes evidence that all
    families are empty. The judge's family floor is independent of this optional priority input.
    """
    try:
        from libs.research.alpha_fitness import certified_family_shares as read_shares
        return read_shares()
    except Exception:
        return {}, 0


def judge_seconds_per_cell(capacity: int) -> float:
    """Measured seconds of judge per H1-equivalent cell: one hour divided by what it judges."""
    return 3600.0 / float(max(capacity, 1))


def producer_signals(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """The two measured per-producer signals from `orthogonality_yield`, or {} when unmeasured.

    Read as a published ARTIFACT rather than imported, for the reason `research_budget` reads
    every one of its factors that way: a missing or unmeasured report must leave every producer at
    par, and an import that raised would be an outage in the ranking instead of a par reading.
    """
    for mod in ("research.orthogonality_yield", "orthogonality_yield"):
        try:
            oy = __import__(mod, fromlist=["published_factors"])
            table = oy.published_factors(path)
            return {str(k): v for k, v in table.items() if isinstance(v, dict)}
        except Exception:
            continue
    return {}


def _docket_keff() -> Any:
    """The marginal-k_eff scorer (research/docket_keff.py), or None when it cannot import."""
    for mod in ("research.docket_keff", "docket_keff"):
        try:
            return __import__(mod, fromlist=["score"])
        except Exception:
            continue
    return None


def _keff_family_factor(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not any("_keff" in r for r in rows):
        return {}
    dk = _docket_keff()
    return dk.family_factor(rows) if dk is not None else {}


def keff_stamp(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Stamp `_keff` (the cell's marginal-k_eff priority) on every row; return the evidence.

    Never raises and never removes a row: a failure leaves the rows unstamped, which ranks every
    one of them exactly as before, and the reason is published as UNMEASURED (L1.28a).
    """
    dk = _docket_keff()
    if dk is None:
        return {"status": "UNMEASURED", "why": "research/docket_keff.py did not import"}
    try:
        doc = dk.score(rows)
        doc["status"] = "MEASURED"
        return dict(doc)
    except Exception as exc:
        for r in rows:
            r.pop("_keff", None)
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:300]}


def _occupancy_map() -> Any:
    """The occupancy map + orthogonality scorer (research/occupancy_map.py), or None."""
    for mod in ("research.occupancy_map", "occupancy_map"):
        try:
            return __import__(mod, fromlist=["stamp"])
        except Exception:
            continue
    return None


def occupancy_stamp(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Stamp `_occ` (the row's cell is an EMPTY/UNDER-TRIED target next to proven ground) and
    `_orth` (its expected orthogonality to the LIVE book and the certified set, centred on par)
    on every row, plus the published `orthogonality` score, from reports/OCCUPANCY_MAP.json.

    Read as a published artifact, like `producer_signals`: an absent or stale map stamps nothing
    and every row ranks exactly as before. Never raises, never removes a row (L1.28a).
    """
    om = _occupancy_map()
    if om is None:
        return {"status": "UNMEASURED", "why": "research/occupancy_map.py did not import"}
    try:
        doc, why = om.load(OCCUPANCY_REPORT)
        if doc is None:
            return {"status": "UNMEASURED", "why": why, "rows": len(rows)}
        return dict(om.stamp(rows, doc))
    except Exception as exc:
        for r in rows:
            r.pop("_occ", None)
            r.pop("_orth", None)
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:300]}


def _saturation() -> Any:
    """The certificate saturation map (research/certificate_saturation.py), or None."""
    for mod in ("research.certificate_saturation", "certificate_saturation"):
        try:
            return __import__(mod, fromlist=["stamp"])
        except Exception:
            continue
    return None


def saturation_stamp(rows: list[dict[str, Any]], capacity: int | None = None) -> dict[str, Any]:
    """Stamp `_sat` (breadth value = novelty credit against the CERTIFIED book's effective local
    density), `_satq` (QUALITY / replacement channel) and `_dup` (strong duplicate in saturated
    ground, no exception A-H) from reports/CERTIFICATE_SATURATION.json, and return the evidence
    with per-producer feedback. Read as a published artifact: absent or stale stamps nothing and
    every row ranks exactly as before. Never raises, never removes a row (L1.28a)."""
    cs = _saturation()
    if cs is None:
        return {"status": "UNMEASURED", "why": "research/certificate_saturation.py did not import"}
    try:
        spc = judge_seconds_per_cell(capacity) if capacity else None
        return dict(cs.stamp(rows, seconds_per_cell=spc))
    except Exception as exc:
        for r in rows:
            for k in _SAT_KEYS:
                r.pop(k, None)
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:300]}


#: Every ordering stamp the saturation map adds; popped before the docket is written.
_SAT_KEYS = ("_sat", "_satq", "_dup", "_satq_arch")


def _tf_session_key() -> Any:
    """`breadth_rotation.tf_session_key()` (PR #200's timeframe x session tier: under-target
    (chart, session) buckets rank 0), or a neutral key when it cannot be read. With no census
    every row ranks 0, so the composed order is exactly the order without it."""
    for mod in ("research.breadth_rotation", "breadth_rotation"):
        try:
            key = __import__(mod, fromlist=["tf_session_key"]).tf_session_key()
            return key if callable(key) else (lambda _r: 0)
        except Exception:
            continue
    return lambda _r: 0


def quality_share() -> float:
    """The protected QUALITY / REPLACEMENT share of each family stream (law section 15): the
    ladder's adaptive B budget (research/breadth_ladder.py `budget_split`), bounded to
    [QUALITY_SHARE_BOUNDS]; the default when the ladder is unreadable."""
    try:
        doc = json.loads((REPORTS / "BREADTH_LADDER.json").read_text("utf-8"))
        raw: Any = ((doc.get("budget_split") or {}).get("split") or {}).get("B")
        v = float(raw)
        if math.isfinite(v):
            return min(max(v, QUALITY_SHARE_BOUNDS[0]), QUALITY_SHARE_BOUNDS[1])
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return QUALITY_SHARE_DEFAULT


#: A breadth-only docket leaves a mediocre incumbent untouched forever (law section 15), so
#: quality challengers keep this share of every family stream whenever they exist.
QUALITY_SHARE_DEFAULT = 0.2
QUALITY_SHARE_BOUNDS = (0.1, 0.5)


def _row_value(row: dict[str, Any]) -> float:
    """VALUE inside a family stream (law section 15):

        P_SURVIVOR (the row's own premortem, 1.0 when absent) x BREADTH_VALUE (novelty credit)
        x (1 + max(0, marginal k_eff + occupancy + orthogonality))   [portfolio need]

    The family's own P(survivor), edge value and effective-trial charge are constant inside a
    stream and are applied by `rank_by_value` at the family level. NOT divided by bar cost: that
    would bury every intraday chart, and timeframe breadth is a standing order of its own."""
    pm = row.get("premortem")
    p = pm.get("p_survivor") if isinstance(pm, dict) else None
    try:
        p_s = min(max(float(p), 0.0), 1.0) if p is not None else 1.0
    except (TypeError, ValueError):
        p_s = 1.0
    need = (float(row.get("_keff") or 0.0) + float(row.get("_occ") or 0.0)
            + float(row.get("_orth") or 0.0))
    return p_s * float(row.get("_sat", 1.0)) * (1.0 + max(0.0, need))


def _keff_summary(keff: dict[str, Any]) -> dict[str, Any]:
    """The compact k_eff block JUDGE_COVERAGE.json carries; the full table has its own report."""
    if keff.get("status") != "MEASURED":
        return {k: keff.get(k) for k in ("status", "why")}
    dk = _docket_keff()
    out = dk.summary(keff) if dk is not None else {}
    out["status"] = "MEASURED"
    return out


def rank_by_value(backlog: dict[str, int], rows: list[dict[str, Any]],
                  capacity: int) -> list[dict[str, Any]]:
    """EXPECTED VALUE PER JUDGE-SECOND, per family, published so the choice is inspectable.

        ev_per_cell = p_optimistic * net_value_if_it_passes * (1 + marginal_breadth)
                                   * orthogonality_factor * certificate_factor
                                   * certified_breadth_factor
        ev_per_s    = ev_per_cell / (seconds_per_cell * this family's bar cost)

    Every term is something the desk already measures -- the learned prior, the net-of-cost slot
    value, the cluster occupancy behind effective breadth, and the bar ratio the sealed gauntlet
    budgets in. Nothing here is a preference; a family that ranks low ranks low on its own record,
    and a family with NO record ranks on the optimistic bound, which is how it gets explored.

    THE LAST TWO TERMS ARE THE PRINCIPAL'S ORDER OF 2026-09-23 -- "compute should always go more to
    discovering things which produce orthogonality along with ones who produce the most certis."
    `orthogonality_yield` measures both per producer: the LEAVE-ONE-OUT drop in the candidate
    grid's effective rank when that producer's cells are removed, and certificates per judge-hour
    from the gate ledger. Both arrive as one-sided multipliers at or above 1.0, so they can lift a
    producer and can never demote one, and a producer no judge has reached sits at par on the
    certificate axis rather than being scored as a measured zero (L1.28a). Absent report, both are
    1.0 and this function is exactly what it was.
    """
    fams = [f for f, n in backlog.items() if n > 0]
    realised = realised_pass_rates()
    priors = family_priors(fams, realised)
    values, median = family_value()
    occ = family_breadth()
    certified_shares, certified_n = certified_family_shares()
    # EFFECTIVE, NOT NOMINAL (anti-saturation law section 18): 1 + mean novelty credit of the
    # family's stamped rows, measured against the certified book's effective local density.
    # Falls back to the nominal canon share below when the saturation map is unmeasured.
    _cs = _saturation()
    sat_f = _cs.family_factor(rows) if (_cs is not None and any("_sat" in r for r in rows)) \
        else {}
    signals = producer_signals()
    # MARGINAL k_eff PER FAMILY (research/docket_keff.py): 1 + max(0, mean cell priority) over the
    # rows `build` stamped. One-sided like the two factors above, and exactly 1.0 for rows that
    # carry no stamp, so a caller that never scored is ranked as it always was.
    keff_f = _keff_family_factor(rows)
    per_cell_s = judge_seconds_per_cell(capacity)
    cost_units: dict[str, list[float]] = {}
    for row in rows:
        fam = str(row.get("family") or "")
        if fam in backlog:
            cost_units.setdefault(fam, []).append(_BAR_COST[_tf_of(row)])
    out: list[dict[str, Any]] = []
    for fam in fams:
        pr = priors.get(fam) or {"p": 0.5, "p_optimistic": 1.0, "n": 0.0, "status": 0.0}
        units = cost_units.get(fam) or [1.0]
        bars = sum(units) / len(units)
        cost_s = max(1e-6, per_cell_s * bars)
        value = values.get(fam, median)
        breadth = 1.0 / (1.0 + occ.get(fam, 0.0))
        sig = signals.get(fam) or {}
        ortho_f = float(sig.get("orthogonality_factor") or 1.0)
        cert_f = float(sig.get("certificate_factor") or 1.0)
        kf = float(keff_f.get(fam, 1.0))
        cert_share = float(certified_shares.get(fam, 0.0)) if certified_n else None
        # A family absent from a readable certified canon gets the strongest discovery bonus;
        # an already dominant family gets less. This is a one-sided research-priority credit,
        # so neither the family floor nor any cell's eligibility is reduced. The candidate-level
        # scorer separately recognises a new session/chart/regime inside an incumbent family.
        cert_breadth = 2.0 - cert_share if cert_share is not None else 1.0
        breadth_basis = "NOMINAL_CANON_SHARE" if cert_share is not None else "UNMEASURED"
        if fam in sat_f:
            cert_breadth, breadth_basis = float(sat_f[fam]), "EFFECTIVE_SATURATION_MAP"
        ev_cell = (float(pr["p_optimistic"]) * value * (1.0 + breadth) * ortho_f * cert_f
                   * kf * cert_breadth)
        rl = realised.get(fam) or {}
        out.append({
            "family": fam, "unjudged": backlog[fam],
            "p": round(pr["p"], 6), "p_optimistic": round(pr["p_optimistic"], 6),
            "prior_n": int(pr["n"]), "prior_status": "POSTERIOR" if pr["status"] else "PRIOR",
            # THE AIM, INSPECTABLE. What the family actually did at the judge, beside the number
            # the ranking spent, and which of the two the spend came from.
            "realised_judged": int(rl.get("judged", 0)),
            "realised_passed": int(rl.get("passed", 0)),
            "realised_pass_rate": round(float(rl.get("pass_rate", 0.0)), 6) if rl else None,
            "prior_source": "LEDGER_REALISED" if pr.get("source") else "STORED_POSTERIOR",
            "stored_prior_n": int(pr.get("stored_n", pr["n"])),
            "net_value_if_pass": value, "value_source": "NET_EDGE" if fam in values else "median",
            "breadth_gain": round(breadth, 4), "cluster_occupancy": occ.get(fam, 0.0),
            "certified_family_share": round(cert_share, 6) if cert_share is not None else None,
            "certified_family_count": (round(cert_share * certified_n)
                                       if cert_share is not None else None),
            "certified_breadth_factor": round(cert_breadth, 6),
            "certified_breadth_status": "MEASURED" if certified_n else "UNMEASURED",
            "certified_breadth_basis": breadth_basis,
            # THE TWO SIGNALS THE PRINCIPAL ORDERED COMPUTE STEERED BY (2026-09-23), measured per
            # producer in `orthogonality_yield` and published here beside the number they moved.
            # `breadth_gain` above stays exactly as it was -- it reads the LIVE BOOK's clusters and
            # belongs to the effective-breadth lane -- but it is measured to be ANTI-correlated
            # with true marginal orthogonality, which is the defect these two factors correct.
            # Both are one-sided (>= 1.0), so no family's ev is ever REDUCED by them and the
            # 25% floor below is untouched: this re-orders the remainder, it never starves.
            "orthogonality_factor": round(ortho_f, 4), "certificate_factor": round(cert_f, 4),
            "keff_factor": round(kf, 4),
            "marginal_rank": sig.get("marginal_rank"),
            "certs_per_judge_hour": sig.get("certs_per_judge_hour"),
            # BANNED / UNMEASURED / UNDER_JUDGED / MEASURED_ZERO / CERTIFYING -- a zero pass rate
            # is not one thing, and an UNMEASURED producer is never scored as a failing one.
            "producer_state": sig.get("state") or "UNMEASURED",
            "bar_cost_units": round(bars, 3), "cost_s_per_cell": round(cost_s, 4),
            "ev_per_cell": ev_cell, "ev_per_judge_second": ev_cell / cost_s,
        })
    out.sort(key=lambda r: (-float(r["ev_per_judge_second"]), str(r["family"])))
    for i, row in enumerate(out):
        row["rank"] = i + 1
    return out


def allocate(backlog: dict[str, int], capacity: int,
             floor_share: float = FLOOR_SHARE,
             ranking: list[dict[str, Any]] | None = None) -> dict[str, int]:
    """Quota per family: an equal FLOOR for every family holding backlog, then BY VALUE.

    THE FLOOR IS THE BREADTH MANDATE AND IT NEVER MOVES. Every family holding an unjudged cell
    gets an equal share of the first `FLOOR_SHARE` of the hour, because starving a family is how
    this desk reached a six-family concentration in the first place, and a ranking that could
    zero a family would rebuild it inside a week.

    THE REMAINDER IS WHERE THE RETURN IS. Spending it in proportion to backlog spends it on
    whichever miner ran hardest, which is a measure of the desk's own output and not of what an
    hour of judge is worth. So the remainder goes down the published ranking -- expected value per
    judge-second, highest first -- each family capped at its own backlog, until the hour is gone.
    Passing no ranking falls back to proportional, so a caller that cannot measure value still
    allocates rather than stalling.

    Two properties are load-bearing and both are tested. EVERY family with backlog gets at least
    one cell of the hour, and no family is given more than its own backlog (a quota is a promise
    to drain, not a licence to re-judge).
    """
    live = {f: n for f, n in backlog.items() if n > 0}
    if not live or capacity <= 0:
        return {}
    floor_pool = int(capacity * max(0.0, min(1.0, floor_share)))
    per_family_floor = max(1, floor_pool // len(live))
    quota = {f: min(n, per_family_floor) for f, n in live.items()}
    spare = capacity - sum(quota.values())
    if spare <= 0:
        return quota
    if ranking:
        for row in ranking:
            fam = str(row.get("family") or "")
            room = live.get(fam, 0) - quota.get(fam, 0)
            if room <= 0:
                continue
            take = min(room, spare)
            quota[fam] += take
            spare -= take
            if spare <= 0:
                break
        return quota
    room_by_size = {f: live[f] - quota[f] for f in live if live[f] > quota[f]}
    weight = sum(room_by_size.values())
    if weight > 0:
        for fam, r in sorted(room_by_size.items(), key=lambda kv: (-kv[1], kv[0])):
            take = min(r, int(spare * r / weight))
            quota[fam] += take
    return quota


def grid_cell(row: dict[str, Any]) -> str:
    """(family|symbol|horizon) -- THE SAME KEY the yield fence weighs orthogonality on.

    `scripts/check_producer_yield.py` measures the desk's orthogonality as the participation
    ratio of the producer x (family|symbol|horizon) indicator matrix, and `libs/moat/registry.py`
    pays its empty-cell bonus on the same key. Ordering intake on any other key would order it
    on something the desk is not paid for, so this is that key, spelled the same way.
    """
    params = row.get("params") or {}
    fam = str(row.get("family") or "?").strip().lower() or "?"
    sym = str(row.get("symbol") or row.get("sym") or "?").strip().lower() or "?"
    hor = str(row.get("horizon") or params.get("horizon") or "?").strip().lower() or "?"
    return f"{fam}|{sym}|{hor}"


def structural_cell(row: dict[str, Any]) -> str:
    """A family's distinct research condition within the existing coverage grid.

    The public grid key stays family|symbol|horizon for its established consumers. For ordering
    variants inside one family, chart, session, regime, direction and representation matter too.
    Threshold-only parameter changes do not, and no structural distinction certifies an edge.
    """
    params = row.get("params") or {}

    def axis(*values: Any) -> str:
        chosen = next((v for v in values if v is not None and str(v).strip()), "?")
        return str(chosen).strip().lower()
    return "|".join((
        grid_cell(row), axis(params.get("timeframe"), row.get("timeframe"), "H1"),
        axis(row.get("session"), row.get("selector"), params.get("session"),
             params.get("selector")),
        axis(row.get("regime"), row.get("condition"), params.get("regime"),
             params.get("condition")),
        axis(row.get("direction"), row.get("side"), params.get("direction"),
             params.get("side")),
        axis(row.get("representation"), params.get("representation"),
             params.get("feature")),
    ))


def variant_split(rows: list[dict[str, Any]],
                  unjudged_ids: set[str] | None = None) -> dict[str, Any]:
    """Mark each docket row UNSEEN MECHANISM or VARIANT, and say how many of each there are.

    Charge repeated parameter settings against their first structural cell. A different chart,
    session, regime, direction or representation remains a distinct experiment within the same
    family. The legacy family|symbol|horizon grid count is reported separately for its consumers.

    NOTHING IS DROPPED AND NOTHING IS CAPPED. The queue stays whole and uncapped; the variant is
    marked `_variant = 1` and ranks below an unseen mechanism inside its own family stream, after
    the never-judged test, so the family floors, the value ranking and the interleave are all
    untouched. First-claim is decided by the same (never-judged, oldest-first) order the stream
    itself uses, so the row that would have gone first still goes first.
    """
    ids = unjudged_ids or set()

    def _fresh(row: dict[str, Any]) -> int:
        cid = str(row.get("_cell") or "")
        return 0 if (not ids or cid in ids) else 1

    order = sorted(range(len(rows)),
                   key=lambda i: (_fresh(rows[i]), str(rows[i].get("first_seen") or "9999"), i))
    seen: set[str] = set()
    grid_seen: set[str] = set()
    variants = 0
    for i in order:
        cell = structural_cell(rows[i])
        is_variant = 1 if cell in seen else 0
        seen.add(cell)
        grid_seen.add(grid_cell(rows[i]))
        rows[i]["_variant"] = is_variant
        variants += is_variant
    return {"rows": len(rows), "unseen_mechanisms": len(rows) - variants, "variants": variants,
            "distinct_grid_cells": len(grid_seen),
            "distinct_structural_cells": len(seen),
            "variant_share": round(variants / len(rows), 4) if rows else None,
            "collapse_raw_per_grid_cell": (round(len(rows) / len(grid_seen), 3)
                                           if grid_seen else None)}


def _unseen_in_prefix(rows: list[dict[str, Any]], n: int) -> int:
    """How many of the first `n` rows the judge will reach are unseen mechanisms."""
    return sum(1 for r in rows[:max(int(n), 0)] if not int(r.get("_variant") or 0))


def coverage_order(rows: list[dict[str, Any]], quota: dict[str, int],
                   unjudged_ids: set[str] | None = None, *,
                   demote_variants: bool = True,
                   use_keff: bool = True,
                   use_occupancy: bool = True,
                   use_saturation: bool = True,
                   quality: float | None = None,
                   tf_key: Any = None) -> list[dict[str, Any]]:
    """Weighted interleave of the families, so EVERY PREFIX of the docket is family-balanced.

    Each family is emitted on its own virtual clock ticking at 1/quota, and the family whose next
    tick is earliest goes next -- classic weighted fair queueing. The result: in any first N rows
    the gauntlet's budget reaches, family f holds about N * quota[f] / sum(quota) of them. Within
    a family, NEVER-JUDGED rows go first, then DISTINCT STRUCTURAL CELLS before parameter variants
    of a rule already claiming the same chart/session/regime/direction/representation, then oldest.
    The head of a family's stream is exactly the backlog the ratchet measures, spent on independent
    ground rather than on the same rule's constants. `demote_variants=False` reproduces the
    pre-2026-09-23 order, which is how the freed-slot count below is measured.

    MARGINAL k_eff (2026-09-30): among rows tied on those two tests, the cell whose instrument and
    cluster add the most independent bets to the book goes first (`_keff`, stamped by
    `keff_stamp`), and only then the oldest. A row with no stamp scores 0 and keeps its old place;
    `use_keff=False` reproduces the order before this term existed.

    OCCUPANCY AND ORTHOGONALITY (2026-09-30): the same tie-break term also carries `_occ` (the
    row's cell is an empty or under-tried cell one axis from proven ground, research/
    occupancy_map.py) and `_orth` (the row's expected orthogonality to the LIVE book and the
    certified set, centred on par). Both are in the same effective-bet units as `_keff` and are
    simply added to it; unstamped rows score 0 and keep their place. `use_occupancy=False`
    reproduces the order before these two terms existed.

    THE ANTI-SATURATION LAW (2026-10-05). With `use_saturation`, the tie-break term becomes the
    row's VALUE (`_row_value`: premortem P(survivor) x novelty credit against the certified
    book's effective local density x (1 + the k_eff/occupancy/orthogonality need)), a STRONG
    DUPLICATE (`_dup`: saturated ground, no exception A-H) ranks after every non-duplicate of its
    stream's same freshness, and QUALITY / REPLACEMENT rows (`_satq`) are served on their own
    protected share `quality` of each stream (default `quality_share()`), challengers of an
    archived variant last. Unstamped rows score par and keep their place; `use_saturation=False`
    reproduces the order before this law.

    THE TIMEFRAME x SESSION TIER (breadth_rotation.tf_session_key, PR #200) is composed right
    after the anti-saturation terms (freshness, strong duplicate, archived challenger) and before
    the variant / value terms: inside each saturation tier, rows in under-target (chart, session)
    buckets go first. It reorders and never filters; with no census it is 0 for every row.
    `tf_key` overrides it (a callable row -> int); `use_saturation=False` leaves it out.

    No row is dropped. A family with no quota still ships, after the quota'd stream, because the
    docket this returns is the whole docket and the judge's budget -- not this order -- decides
    where the hour stops.
    """
    if not rows:
        return []
    ids = unjudged_ids or set()
    tf = (tf_key if tf_key is not None else _tf_session_key()) if use_saturation else None

    def rank(row: dict[str, Any]) -> tuple[Any, ...]:
        cid = str(row.get("_cell") or "")
        fresh = 0 if (not ids or cid in ids) else 1
        # A parameter variant of a rule already claiming this grid cell ranks below an unseen
        # mechanism -- inside the family stream, after the never-judged test. It is never
        # dropped and the stream is never shortened; only the order changes.
        variant = int(row.get("_variant") or 0) if demote_variants else 0
        keff = -float(row.get("_keff") or 0.0) if use_keff else 0.0
        if use_occupancy:
            keff -= float(row.get("_occ") or 0.0) + float(row.get("_orth") or 0.0)
        tier = int(tf(row)) if tf is not None else 0
        if use_saturation and "_sat" in row:
            return (fresh, int(row.get("_dup") or 0), int(row.get("_satq_arch") or 0), tier,
                    variant, -_row_value(row), str(row.get("first_seen") or "9999"))
        return (fresh, 0, 0, tier, variant, keff, str(row.get("first_seen") or "9999"))

    streams: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        streams.setdefault(str(row.get("family") or ""), []).append(row)
    q_share = (quality_share() if quality is None else float(quality)) if use_saturation else 0.0
    for fam in streams:
        streams[fam].sort(key=rank)
        if q_share > 0.0 and any(r.get("_satq") for r in streams[fam]):
            streams[fam] = _protect_quality(streams[fam], ids, q_share)

    # Virtual finish time of each family's next row; a family with no quota rides at weight 1 so
    # it is still interleaved rather than appended in a block.
    import heapq
    heap: list[tuple[float, str, int]] = []
    for fam in streams:
        w = float(max(quota.get(fam, 0), 1))
        heapq.heappush(heap, (1.0 / w, fam, 0))
    out: list[dict[str, Any]] = []
    while heap:
        vtime, fam, idx = heapq.heappop(heap)
        out.append(streams[fam][idx])
        nxt = idx + 1
        if nxt < len(streams[fam]):
            w = float(max(quota.get(fam, 0), 1))
            heapq.heappush(heap, (vtime + 1.0 / w, fam, nxt))
    return out


def _protect_quality(stream: list[dict[str, Any]], ids: set[str],
                     share: float) -> list[dict[str, Any]]:
    """Interleave a family stream's QUALITY rows at `share` of every prefix (fresh rows first,
    then already-judged rows), each sub-stream keeping its own order. Breadth rows fill every
    slot the quality channel cannot. Same rows, same count."""
    def fresh(r: dict[str, Any]) -> bool:
        return not ids or str(r.get("_cell") or "") in ids

    out: list[dict[str, Any]] = []
    for want_fresh in (True, False):
        q = [r for r in stream if bool(r.get("_satq")) and fresh(r) == want_fresh]
        b = [r for r in stream if not r.get("_satq") and fresh(r) == want_fresh]
        qi = bi = 0
        while qi < len(q) or bi < len(b):
            served = qi + bi
            if qi < len(q) and (bi >= len(b) or qi < share * (served + 1)):
                out.append(q[qi])
                qi += 1
            else:
                out.append(b[bi])
                bi += 1
    return out


def _mined(docket: list[dict[str, Any]]) -> dict[str, int]:
    """Mined population per family: the docket PLUS the study bank.

    The study bank holds families banned from live capital. They are not judged -- a gate-second
    there buys an outcome the desk has already forbidden -- but they were mined, and a coverage
    report that hid them would be reporting the desk's choices as if they were its output.
    """
    mined: dict[str, int] = {}
    for row in docket:
        fam = str(row.get("family") or "")
        mined[fam] = mined.get(fam, 0) + 1
    bank = _read(STUDY_BANK)
    if isinstance(bank, list):
        for row in bank:
            if isinstance(row, dict):
                fam = str(row.get("family") or "")
                mined[fam] = mined.get(fam, 0) + 1
    return mined


def build(docket: list[dict[str, Any]] | None = None, *, ledger: Path | None = None,
          ratchet: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """The per-family coverage table, the quotas, and the carried-cohort ratchet."""
    at = now or datetime.now(tz=UTC)
    rows = docket if docket is not None else (_read(DOCKET) or [])
    rows = [r for r in rows if isinstance(r, dict)]
    if not rows:
        return {"at": at.isoformat(timespec="seconds"), "verdict": "UNMEASURED",
                "why": "the judging docket is absent or empty -- nothing mined to cover",
                "families": {}, "totals": {}, "quota": {}}

    prior = _read(ratchet or RATCHET) or {}
    judged_cells, judged_total, judged_window = judged_index(ledger, now=at)
    for row in rows:
        row["_cell"] = _cell_id(row)

    mined = _mined(rows)
    banned = banned_from_capital()
    study_only: dict[str, int] = {}
    backlog: dict[str, int] = {}
    oldest: dict[str, float | None] = {}
    unjudged_ids: set[str] = set()
    for row in rows:
        fam = str(row.get("family") or "")
        cid = row.get("_cell")
        if cid and cid in judged_cells:
            continue
        if fam in banned:
            # NOT backlog: a cell that cannot reach the book is not work the judge owes. It is
            # counted, named and kept -- it is simply not something the hour is allocated to.
            study_only[fam] = study_only.get(fam, 0) + 1
            continue
        backlog[fam] = backlog.get(fam, 0) + 1
        if cid:
            unjudged_ids.add(str(cid))
        seen = _ts(row.get("first_seen"))
        if seen is not None:
            age = max(0.0, (at.timestamp() - seen.timestamp()) / 3600.0)
            prev = oldest.get(fam)
            oldest[fam] = age if prev is None else max(prev, age)
        else:
            oldest.setdefault(fam, None)

    capacity = measured_capacity(judged_total, ledger, now=at)
    # TEACH THE PRIOR BEFORE SPENDING IT: every verdict since the last reading updates its
    # family's posterior, so the ranking below is spending a number this desk actually learned.
    learned = learn_priors(ledger, since=str((prior or {}).get("priors_cursor") or ""))
    realised_seen = realised_pass_rates(ledger)
    unknown = unknown_breakdown()
    named_unknowns = name_unknowns()
    not_run = name_not_run()
    unrunnable = update_unrunnable_bank({**named_unknowns, **not_run},
                                        at=at.isoformat(timespec="seconds"))
    bars_wanted: dict[str, int] = {}
    for _r in not_run.values():
        if _r.get("reason") == "data_missing":
            _k = f"{_r.get('sym')}_{_r.get('tf')}"
            bars_wanted[_k] = bars_wanted.get(_k, 0) + 1
    # MARGINAL k_eff, STAMPED BEFORE THE RANKING READS IT (research/docket_keff.py). Reorders
    # only: the family factor lifts a family's share of the remainder, the per-cell stamp orders
    # rows inside each family stream. Nothing is removed and the floor is untouched.
    keff = keff_stamp(rows)
    # OCCUPANCY + ORTHOGONALITY, stamped beside k_eff (research/occupancy_map.py). Reorders only.
    occ = occupancy_stamp(rows)
    # CERTIFICATE SATURATION, stamped beside k_eff and occupancy (research/
    # certificate_saturation.py): novelty credit, duplicate and quality-channel marks. Reorders
    # only; the producer feedback it returns is published by `write`.
    sat = saturation_stamp(rows, capacity)
    ranking = rank_by_value(backlog, rows, capacity)
    quota = allocate(backlog, capacity, ranking=ranking)
    judgeable = [r for r in rows if str(r.get("family") or "") not in banned]
    study_rows = [r for r in rows if str(r.get("family") or "") in banned]
    # Mark the variants BEFORE the order is taken, so the head this table reports is the head
    # that actually ships (`order_docket` re-derives the same marks and measures what they freed).
    variant_split(judgeable, unjudged_ids)
    ordered = coverage_order(judgeable, quota, unjudged_ids) + study_rows
    head = ordered[:capacity]
    if keff.get("status") == "MEASURED":
        dk = _docket_keff()
        if dk is not None:
            keff["head"] = {"shipped": dk.head_census(ordered, capacity, keff.get("_terms") or {})}
    queued: dict[str, int] = {}
    for row in head:
        fam = str(row.get("family") or "")
        queued[fam] = queued.get(fam, 0) + 1

    prior_fams = prior.get("families") if isinstance(prior, dict) else {}
    prior_fams = prior_fams if isinstance(prior_fams, dict) else {}
    prior_at = _ts(prior.get("at") if isinstance(prior, dict) else None)
    # THE CARRIED COHORT: rows already in the backlog at the previous reading and STILL unjudged.
    # It can only fall, because a cell leaves it exactly one way -- by being judged.
    carried: dict[str, int] = {}
    if prior_at is not None:
        for row in rows:
            cid = row.get("_cell")
            if cid and cid in judged_cells:
                continue
            if str(row.get("family") or "") in banned:
                continue
            seen = _ts(row.get("first_seen"))
            if seen is not None and seen.timestamp() <= prior_at.timestamp():
                fam = str(row.get("family") or "")
                carried[fam] = carried.get(fam, 0) + 1

    fams = sorted(set(mined) | set(backlog) | set(judged_window) | live_families())
    table: dict[str, dict[str, Any]] = {}
    for fam in fams:
        if not fam:
            continue
        back = backlog.get(fam, 0)
        q = quota.get(fam, 0)
        # A FAMILY'S OWN WINDOW: the hours its own quota needs to drain its own backlog. A family
        # of 55,190 cells is not starved for being large, and a family of nine is not excused for
        # being small -- each is held to the clock its own size implies, floored at the hour.
        window = WINDOW_H if q <= 0 else max(WINDOW_H, back / max(q, 1) * WINDOW_H)
        was = int(prior_fams.get(fam, {}).get("unjudged", 0)) if isinstance(
            prior_fams.get(fam), dict) else 0
        table[fam] = {
            "mined": mined.get(fam, 0),
            "queued": queued.get(fam, 0),
            "judged_window": judged_window.get(fam, 0),
            "judged_total": judged_total.get(fam, 0),
            "unjudged": back,
            "oldest_unjudged_age_h": (round(float(oldest[fam] or 0.0), 2)
                                      if oldest.get(fam) is not None else None),
            "quota": q,
            "window_h": round(window, 2),
            "carried": carried.get(fam, 0) if prior_at is not None else None,
            "prior_unjudged": was if prior_at is not None else None,
            # The previous reading's oldest age, so the fence can ask the only question about an
            # age that a clock cannot answer for itself: is the oldest cell FALLING. An age rises
            # by the wall time between two readings whatever the desk does -- the coverage-drain
            # fence failed on exactly that and the lesson is written there -- so what is ratcheted
            # is movement, never the raw number.
            "prior_oldest_age_h": (prior_fams.get(fam, {}).get("oldest_unjudged_age_h")
                                   if isinstance(prior_fams.get(fam), dict) else None),
            "drained": (was - carried.get(fam, 0)) if (prior_at is not None and was) else None,
        }
        if fam in banned:
            table[fam]["judging_status"] = "STUDY_ONLY"
            table[fam]["study_only"] = study_only.get(fam, 0)
            table[fam]["judging_reason"] = (
                f"family {fam!r} is banned from live capital (mt5desk/live_policy.py "
                "DEFAULT_BANNED_FAMILIES) and refused at both live doors, so it cannot reach "
                "the book even if it passes and is given no share of the scarce judge. Mining "
                "is unrestricted; the rows are kept in data/hypotheses/study_bank.json")

    # NO FIXED FAMILY SET. The table's rows come from the LIVE registry unioned with whatever the
    # docket and the ledger name, so a family registered tomorrow has a row the same hour -- with
    # `mined: 0` until a miner reaches it, which is a measurement of the miners and not of this
    # organ. It is published, never failed on: intake allocates the judge, it does not mine.
    unmined = sorted(f for f in live_families() if f and table.get(f, {}).get("mined", 0) == 0)
    # THE PREVIOUS READING'S UNKNOWN SHARE, so the fence can ratchet it: this quantity is a
    # SHARE and not a count, because a count rises with throughput and throughput rising is the
    # desk working. The share falls only when fewer never-firing specs reach the judge.
    # A PRIOR READ ON ANOTHER DENOMINATOR IS NO BASELINE: the move from all-rows to judged-only
    # lifts the share several-fold with nothing changing on the desk, and ratcheting across it
    # would fail the fence for a unit conversion. It re-enters as a first reading instead.
    prior_unknown_share = (prior.get("unknown_share")
                           if isinstance(prior, dict)
                           and prior.get("unknown_share_basis") == UNKNOWN_SHARE_BASIS
                           else None)
    # THE OPPORTUNITY COST, which is the number that makes this ROI rather than bookkeeping.
    # `value_at_risk` is the expected value sitting unjudged right now; `value_deferred` is the
    # part of it this hour cannot reach; `value_forgone_per_hour` is that deferred value spread
    # over the hours the current capacity needs to drain it -- the rate at which waiting costs
    # the desk. It is handed to `judging_throughput`, which is the organ that can DO something
    # about it: when the value at risk exceeds what an hour can judge, the box raises workers and
    # cadence. Nothing here throttles mining to make the number smaller.
    ev_cell = {str(r["family"]): float(r["ev_per_cell"]) for r in ranking}
    value_at_risk = sum(ev_cell.get(f, 0.0) * n for f, n in backlog.items())
    value_deferred = sum(ev_cell.get(f, 0.0) * max(0, n - quota.get(f, 0))
                         for f, n in backlog.items())
    total_backlog = sum(backlog.values())
    rate = sustained_rate(ledger, now=at)
    _prior_total = (sum(int(v.get("unjudged", 0)) for v in prior_fams.values()
                        if isinstance(v, dict)) if prior_at is not None else None)
    drain_eta = drain(total_backlog, rate.get("per_hour_24h"), prior_backlog=_prior_total,
                      prior_at=prior_at, now=at)
    hours_to_drain = drain_eta.get("hours")
    _h_gross = drain_eta.get("hours_at_zero_creation")
    forgone_per_hour = (value_deferred / max(_h_gross or 1.0, 1.0) if _h_gross else 0.0)
    for row in ranking:
        fam = str(row["family"])
        row["quota"] = quota.get(fam, 0)
        row["floor"] = min(backlog.get(fam, 0), max(1, int(capacity * FLOOR_SHARE) // max(
            sum(1 for v in backlog.values() if v > 0), 1)))
        row["remainder"] = max(0, row["quota"] - row["floor"])
        row["value_at_risk"] = row["ev_per_cell"] * row["unjudged"]
        row["value_deferred"] = row["ev_per_cell"] * max(0, row["unjudged"] - row["quota"])
    for fam, row in table.items():
        rk = next((r for r in ranking if r["family"] == fam), None)
        if rk is not None:
            row.update({"rank": rk["rank"], "ev_per_cell": rk["ev_per_cell"],
                        "ev_per_judge_second": rk["ev_per_judge_second"],
                        "p_optimistic": rk["p_optimistic"], "prior_status": rk["prior_status"],
                        "value_at_risk": rk["value_at_risk"],
                        "value_deferred": rk["value_deferred"],
                        "floor": rk["floor"], "remainder": rk["remainder"]})

    covered = sum(1 for f, r in table.items() if r["unjudged"] > 0 and r["queued"] > 0)
    starved = sorted((f for f, r in table.items() if r["unjudged"] > 0 and r["queued"] == 0),
                     key=lambda f: -table[f]["unjudged"])
    totals = {
        "docket_rows": len(rows),
        "mined": sum(mined.values()),
        "families_mined": sum(1 for r in table.values() if r["mined"] > 0),
        "families_live": len(live_families()),
        "families_unmined": len(unmined),
        "families_with_backlog": sum(1 for r in table.values() if r["unjudged"] > 0),
        "families_queued": covered,
        "families_starved": len(starved),
        "unjudged_total": sum(backlog.values()),
        "study_only_total": sum(study_only.values()),
        "study_only_families": sorted(study_only),
        "carried_total": sum(carried.values()) if prior_at is not None else None,
        "prior_unjudged_total": (sum(int(v.get("unjudged", 0)) for v in prior_fams.values()
                                     if isinstance(v, dict)) if prior_at is not None else None),
        "capacity_measured": capacity,
        "value_at_risk": value_at_risk,
        "value_deferred": value_deferred,
        "value_forgone_per_hour": forgone_per_hour,
        # capacity_measured above is the PEAK hour (the allocation size); these are the drain.
        "capacity_sustained_per_hour": rate.get("per_hour_24h"),
        "capacity_sustained_per_hour_7d": rate.get("per_hour_7d"),
        "drain_status": drain_eta.get("status"),
        "backlog_growth_per_hour": drain_eta.get("backlog_growth_per_hour"),
        "hours_to_drain": round(hours_to_drain, 3) if hours_to_drain else None,
        "hours_to_drain_at_zero_creation": drain_eta.get("hours_at_zero_creation"),
        "capacity_short": bool(drain_eta.get("status") in ("GROWING", "UNMEASURED")
                               or (hours_to_drain and hours_to_drain > 1.0)),
        # THE LARGEST SINGLE WASTE IN THE DESK, named and ratcheted: the share of the judge's own
        # verdicts that return no gate at all. Driven DOWN by the compiler that stops minting
        # never-firing specs, never by judging less.
        "unknown_share": unknown.get("unknown_share"),
        "unknown_share_basis": unknown.get("unknown_share_basis"),
        "unknown_share_of_all_rows": unknown.get("unknown_share_of_all_rows"),
        "unknown_total": unknown.get("unknown_total"),
        "judged_verdicts": unknown.get("judged_verdicts"),
        # The same class over the ledger's rolling windows -- the figure a git reading quotes.
        "unknown_share_24h": rate.get("unknown_share_24h"),
        "unknown_share_7d": rate.get("unknown_share_7d"),
        "unknown_counts_window": rate.get("unknown_counts"),
        "named_verdicts_per_hour_24h": rate.get("named_per_hour_24h"),
        "unknown_by_reason": unknown.get("by_reason"),
        "prior_unknown_share": prior_unknown_share,
        "never_fires_cells": ((unknown.get("causes") or {}).get("never_fires_days_0")
                              or {}).get("cells"),
        "unknown_unnamed": max(0, int(unknown.get("unknown_total") or 0)
                               - int(unknown.get("named_cells") or 0)),
        "not_run_named": len(not_run),
        "not_run_by_reason": dict(Counter(str(r.get("reason")) for r in not_run.values())),
        "prewarm_fail_share": _prewarm_share(),
        "prior_prewarm_fail_share": (prior.get("prewarm_fail_share")
                                     if isinstance(prior, dict) else None),
        "prior_drain_status": (prior.get("drain_status") if isinstance(prior, dict) else None),
        "unrunnable_parked": unrunnable.get("parked_this_pass"),
        "unrunnable_bank": unrunnable.get("bank_size"),
        "oldest_unjudged_age_h": (round(max(v for v in oldest.values() if v is not None), 2)
                                  if any(v is not None for v in oldest.values()) else None),
    }
    return {
        "at": at.isoformat(timespec="seconds"),
        "verdict": "COVERED" if not starved else "STARVED",
        "why": ("every family holding unjudged cells is in this hour's queue at its own quota"
                if not starved else
                f"{len(starved)} family(ies) hold unjudged cells and are absent from the queue: "
                f"{', '.join(starved[:5])}"),
        "rule": ("floor first (an equal share of "
                 f"{FLOOR_SHARE:.0%} of measured capacity to every family holding backlog), then "
                 "the remainder in proportion to backlog; the docket ships whole, interleaved, "
                 "so every prefix the judge's budget reaches is family-balanced"),
        "families": table,
        "totals": totals,
        "quota": quota,
        "starved": starved[:20],
        "unmined_live_families": unmined[:40],
        # THE RANKING IS PUBLISHED SO THE CHOICE IS INSPECTABLE -- and so the fence can check that
        # the remainder actually followed it, which is what stops a future session quietly
        # reverting this to round-robin.
        "priors_learned": learned,
        # THE AIM, BESIDE THE PRIOR THAT SET IT. Every family the judge has actually ruled on,
        # ordered by what it MEASURABLY did, so "the desk spent its largest block of judging on a
        # family that certified nothing" is a line anyone can read off the artifact instead of a
        # thing that has to be re-derived from 3,368 ledger rows.
        "realised_pass_rate": [
            {"family": f, "judged": int(r["judged"]), "passed": int(r["passed"]),
             "pass_rate": round(float(r["pass_rate"]), 6),
             "posterior_mean": round(float(r["mean"]), 6),
             "posterior_hi": round(float(r["hi"]), 6)}
            for f, r in sorted(realised_seen.items(),
                               key=lambda kv: (-float(kv[1]["pass_rate"]),
                                               -float(kv[1]["judged"]), kv[0]))],
        "realised_pass_rate_rule": (
            "counted from gate_verdict_ledger.jsonl every pass, so no cursor can make it stale; "
            "terminal_gate UNKNOWN is the sealed judge's UNMEASURED path and counts toward "
            "neither judged nor passed, because nobody looked is not a failure"),
        "unknown_reasons": unknown,
        "unrunnable": unrunnable,
        "keff_order": _keff_summary(keff),
        "_keff_detail": keff,
        "occupancy_order": occ,
        "saturation_order": {k: v for k, v in sat.items() if k != "producers"},
        "_saturation_detail": sat,
        # N_CERTIFICATES IS NEVER QUOTED WITHOUT N_EFFECTIVE_CERTIFICATES (law section 13).
        "certificates": sat.get("certificates") or {"status": "UNMEASURED"},
        # THE BARS THE JUDGE ASKED FOR AND DID NOT HAVE, per symbol and chart: the demand the
        # bar refresh reads (research/refresh_bars.py) so a missing chart is fetched, not waited on.
        "bars_wanted": dict(sorted(bars_wanted.items(), key=lambda kv: -kv[1])),
        "value_ranking": ranking,
        "value_rule": ("remainder after every family's floor goes down expected value per "
                       "judge-second: p_optimistic (upper credible bound of the desk's own Beta "
                       "prior, so an unseen family is explored) x net-of-cost slot value "
                       "(NET_EDGE.json) x (1 + marginal breadth from EFFECTIVE_BREADTH cluster "
                       "occupancy) x keff_factor (1 + max(0, mean marginal-k_eff priority of the "
                       "family's cells, research/docket_keff.py)), divided by measured seconds "
                       "per cell x the family's bar cost"),
        "worst_backlog": [
            {"family": f, "unjudged": table[f]["unjudged"], "queued": table[f]["queued"],
             "oldest_unjudged_age_h": table[f]["oldest_unjudged_age_h"],
             "mined": table[f]["mined"]}
            for f in sorted(table, key=lambda f: -table[f]["unjudged"])[:10]
            if table[f]["unjudged"] > 0],
        "banned_routed_out": {
            "where": str(STUDY_BANK),
            "by": "research/merge_hypotheses.py (live_banned_families -> study bank)",
            "why": ("a family banned from live capital cannot reach the book even if it passes, "
                    "so the scarce judge is not spent on it; mining stays unrestricted and the "
                    "rows are kept, never deleted"),
        },
    }


#: A (family, symbol) pair whose parked cells include at least this many that NEVER fired, and
#: which has never produced one cell the judge could rule on, is a ground this family's rule
#: grammar does not reach on this instrument. Its remaining unseen cells go to the TAIL of the
#: docket -- still there, still judged whenever the head is exhausted, never dropped -- so the
#: hour's judge goes to cells that can fire first.
SIBLING_NEVER_FIRES_MIN = 20


def fired_pairs(path: Path | None = None) -> set[tuple[str, str]]:
    """(family, sym) pairs holding at least one verdict with a named gate -- they CAN fire."""
    out: set[tuple[str, str]] = set()
    try:
        with (path or GATE_LEDGER).open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"UNKNOWN"' in line or not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("terminal_gate"):
                    out.add((str(row.get("family") or ""), str(row.get("sym") or "")))
    except OSError:
        pass
    return out


def never_fire_pairs(bank: dict[str, dict[str, Any]],
                     fired: set[tuple[str, str]]) -> set[tuple[str, str]]:
    counts: dict[tuple[str, str], int] = {}
    for row in bank.values():
        if row.get("reason") != "never_fires":
            continue
        key = (str(row.get("family") or ""), str(row.get("sym") or ""))
        counts[key] = counts.get(key, 0) + 1
    return {k for k, n in counts.items() if n >= SIBLING_NEVER_FIRES_MIN and k not in fired}


def _row_sym(row: dict[str, Any]) -> str:
    return str(row.get("sym") or row.get("symbol") or "")


def saturation_head(rows: list[dict[str, Any]], n: int) -> dict[str, Any]:
    """What the judge's first `n` rows hold under the saturation law: strong duplicates, quality
    challengers and the mean breadth value -- the evidence that the order moved."""
    head = rows[:max(int(n), 0)]
    vals = [float(r["_sat"]) for r in head if "_sat" in r]
    return {"rows": len(head), "strong_duplicates": sum(1 for r in head if r.get("_dup")),
            "quality_rows": sum(1 for r in head if r.get("_satq")),
            "mean_breadth_value": round(sum(vals) / len(vals), 6) if vals else None}


def order_docket(rows: list[dict[str, Any]], *, publish: bool = True,
                 now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """THE INTAKE CALL. Return the docket re-ordered for coverage, and the table it implies.

    `merge_hypotheses` calls this as the last thing it does before writing the file the sealed
    gauntlet reads, so the order the judge receives IS the allocation measured here -- the report
    describes the docket that actually shipped, not a plan for one. The rows are returned WHOLE:
    the same candidates, all of them, in an order where every prefix carries every family holding
    backlog. A failure here returns the rows untouched, because an ordering organ must never be
    able to cost the desk a docket (L1.28a).
    """
    try:
        doc = build(rows, now=now)
        if not doc.get("families"):
            return rows, doc
        quota = {str(k): int(v) for k, v in (doc.get("quota") or {}).items()}
        banned = banned_from_capital()
        judged_cells, _, _ = judged_index(now=now)
        ids: set[str] = set()
        for row in rows:
            cid = row.get("_cell") or _cell_id(row)
            if cid and cid not in judged_cells:
                ids.add(str(cid))
        # THE UNRUNNABLE FILTER, at the one funnel every producer flows through (the principal,
        # 2026-09-23: "unrunnable specs back to the compiler's filter so they never reach the
        # docket again"). A cell the judge PROVED it cannot rule on is not re-submitted while
        # its symbol's history is unchanged; the moment those bars grow it is re-admitted
        # automatically. Nothing is deleted -- the bank keeps every row with its named reason.
        bank = unrunnable_bank()
        blocked = [r for r in rows if str(r.get("_cell") or "") in bank]
        rows = [r for r in rows if str(r.get("_cell") or "") not in bank]
        judgeable = [r for r in rows if str(r.get("family") or "") not in banned]
        study = [r for r in rows if str(r.get("family") or "") in banned]
        # CHARGE VARIANTS AGAINST THEIR PARENT. The split marks the rows; the two orders below
        # differ ONLY in whether that mark is read, so the difference in unseen mechanisms
        # inside the judge's measured capacity is exactly what the demotion freed. Nothing is
        # dropped in either order: both hold every row.
        split = variant_split(judgeable, ids)
        cap = int((doc.get("totals") or {}).get("capacity_measured") or 0)
        before = coverage_order(judgeable, quota, ids, demote_variants=False, use_keff=False,
                                use_occupancy=False, use_saturation=False)
        ordered_j = coverage_order(judgeable, quota, ids)
        # NEVER-FIRING GROUND TO THE TAIL (2026-09-30). Order only; every row stays.
        dead = never_fire_pairs(bank, fired_pairs())
        if dead:
            _live = [r for r in ordered_j
                     if (str(r.get("family") or ""), _row_sym(r)) not in dead]
            _tail = [r for r in ordered_j
                     if (str(r.get("family") or ""), _row_sym(r)) in dead]
            ordered_j = _live + _tail
            doc["never_fire_ground"] = {
                "pairs": len(dead), "rows_to_tail": len(_tail),
                "min_never_fires": SIBLING_NEVER_FIRES_MIN,
                "rule": ("a (family, symbol) with this many parked never-firing cells and no "
                         "verdict with a named gate ranks after every other row; nothing dropped")}
        ordered = ordered_j + study
        was, now_ = _unseen_in_prefix(before, cap), _unseen_in_prefix(ordered_j, cap)
        # THE ORDERING EVIDENCE: what the judge's measured capacity head holds under the shipped
        # order against the legacy one (no variant demotion, no k_eff term). Same rows, same
        # quotas -- the difference is only which cells the hour reaches first.
        keff = doc.get("_keff_detail") or {}
        dk = _docket_keff()
        if keff.get("status") == "MEASURED" and dk is not None:
            terms = keff.get("_terms") or {}
            keff["head"] = {"capacity": cap,
                            "shipped": dk.head_census(ordered_j, cap, terms),
                            "legacy": dk.head_census(before, cap, terms)}
            doc["keff_order"] = _keff_summary(keff)
        occ = doc.get("occupancy_order") or {}
        om = _occupancy_map()
        if occ.get("status") == "MEASURED" and om is not None:
            occ["head"] = {"capacity": cap, "shipped": om.head_census(ordered_j, cap),
                           "legacy": om.head_census(before, cap)}
        doc["variant_demotion"] = {
            **split, "capacity": cap,
            "unseen_in_capacity_before": was, "unseen_in_capacity_after": now_,
            "slots_freed": now_ - was,
            "rule": ("a parameter variant of a rule already queued on the same family, symbol "
                     "and horizon ranks below an unseen mechanism inside its own family stream. "
                     "The queue is uncapped and no row is dropped; only the order changes"),
        }
        sat = doc.get("saturation_order") or {}
        if sat.get("status") == "MEASURED":
            legacy_sat = coverage_order(judgeable, quota, ids, use_saturation=False)
            sat["head"] = {"capacity": cap, "shipped": saturation_head(ordered_j, cap),
                           "without_saturation": saturation_head(legacy_sat, cap)}
        doc["unrunnable_filtered_from_docket"] = len(blocked)
        for _b in blocked:
            for _k in ("_cell", "_keff", "_occ", "_orth", *_SAT_KEYS):
                _b.pop(_k, None)
        # `orthogonality` (the published per-row score) is KEPT on the row; the ordering terms go.
        for row in ordered:
            for _k in ("_cell", "_variant", "_keff", "_occ", "_orth", *_SAT_KEYS):
                row.pop(_k, None)
        if publish:
            write(doc)
        return ordered, doc
    except Exception as exc:                                             # pragma: no cover
        return rows, {"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


def write(doc: dict[str, Any], *, report: Path | None = None,
          ratchet: Path | None = None) -> None:
    """Publish the table and advance the ratchet. A ratchet write is the NEXT reading's baseline."""
    target = report or REPORT
    target.parent.mkdir(parents=True, exist_ok=True)
    sat = doc.pop("_saturation_detail", None)
    if isinstance(sat, dict) and sat.get("status") == "MEASURED" and report is None:
        cs = _saturation()
        if cs is not None:
            try:
                cs.write_feedback(sat)
            except OSError as exc:
                doc.setdefault("saturation_order", {})["feedback_error"] = type(exc).__name__
    keff = doc.pop("_keff_detail", None)
    if isinstance(keff, dict) and keff.get("status") == "MEASURED" and report is None:
        dk = _docket_keff()
        if dk is not None:
            try:
                dk.publish(keff)
            except OSError as exc:
                doc.setdefault("keff_order", {})["publish_error"] = f"{type(exc).__name__}"
    target.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    fams = doc.get("families") or {}
    state = {
        "at": doc.get("at"),
        "families": {f: {"unjudged": int(r.get("unjudged") or 0),
                         "queued": int(r.get("queued") or 0),
                         "oldest_unjudged_age_h": r.get("oldest_unjudged_age_h")}
                     for f, r in fams.items()},
        "unjudged_total": (doc.get("totals") or {}).get("unjudged_total"),
        "unknown_share": (doc.get("totals") or {}).get("unknown_share"),
        "unknown_share_basis": (doc.get("totals") or {}).get("unknown_share_basis"),
        "prewarm_fail_share": (doc.get("totals") or {}).get("prewarm_fail_share"),
        "drain_status": (doc.get("totals") or {}).get("drain_status"),
        "priors_cursor": (doc.get("priors_learned") or {}).get("cursor") or "",
        "why": ("the baseline the carried-cohort ratchet is measured against: rows already in "
                "this backlog and still unjudged at the next reading were STARVED, because a "
                "cell leaves a cohort exactly one way -- by being judged"),
    }
    rt = ratchet or RATCHET
    rt.parent.mkdir(parents=True, exist_ok=True)
    rt.write_text(json.dumps(state, indent=1, default=str), "utf-8")


def render(doc: dict[str, Any]) -> list[str]:
    t = doc.get("totals") or {}
    lines = [f"judge coverage: {doc.get('verdict')} -- {doc.get('why')}",
             f"  families mined {t.get('families_mined')} / with backlog "
             f"{t.get('families_with_backlog')} / queued this hour {t.get('families_queued')}; "
             f"unjudged {t.get('unjudged_total')} on capacity {t.get('capacity_measured')}"]
    if t.get("unknown_share") is not None:
        _u = doc.get("unknown_reasons") or {}
        _w = t.get("unknown_share_7d")
        lines.append(f"  UNKNOWN {t.get('unknown_total')} of {_u.get('judged_verdicts')} judged "
                     f"({float(t.get('unknown_share') or 0):.1%}; "
                     f"{'n/a' if _w is None else f'{float(_w):.1%}'} over 7d), of which "
                     f"{t.get('never_fires_cells')} never fired at all; parked "
                     f"{(doc.get('unrunnable') or {}).get('parked_this_pass')}")
    lines.append(f"  value at risk {t.get('value_at_risk'):.3e} of which "
                 f"{t.get('value_deferred'):.3e} deferred; forgone "
                 f"{t.get('value_forgone_per_hour'):.3e}/h; drain "
                 f"{t.get('hours_to_drain')}h"
                 + ("  CAPACITY SHORT" if t.get("capacity_short") else ""))
    for row in (doc.get("value_ranking") or [])[:5]:
        lines.append(f"  #{row['rank']} {row['family']}: ev/judge-s "
                     f"{row['ev_per_judge_second']:.3e}"
                     f" p*={row['p_optimistic']:.3f} ({row['prior_status']}) quota {row['quota']}"
                     f" (floor {row['floor']} + {row['remainder']})")
    for row in (doc.get("worst_backlog") or [])[:5]:
        lines.append(f"  {row['family']}: mined {row['mined']} unjudged {row['unjudged']} "
                     f"queued {row['queued']} oldest {row['oldest_unjudged_age_h']}h")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="judge coverage by unjudged backlog, per family")
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's mode)")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true", help="measure without advancing the ratchet")
    args = ap.parse_args(argv)
    t0 = time.time()
    doc = build()
    doc["elapsed_s"] = round(time.time() - t0, 2)
    doc["budget_s"] = args.budget_s
    if not args.no_write:
        write(doc)
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        for line in render(doc):
            print(line)
    return 0


__all__ = [
    "allocate",
    "banned_from_capital",
    "build",
    "coverage_order",
    "family_breadth",
    "family_priors",
    "family_value",
    "grid_cell",
    "judge_seconds_per_cell",
    "judged_index",
    "learn_priors",
    "live_families",
    "main",
    "measured_capacity",
    "name_unknowns",
    "order_docket",
    "rank_by_value",
    "render",
    "unknown_breakdown",
    "unrunnable_bank",
    "update_unrunnable_bank",
    "variant_split",
    "write",
]


if __name__ == "__main__":                                              # pragma: no cover
    sys.exit(main())

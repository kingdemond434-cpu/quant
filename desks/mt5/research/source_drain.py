"""THE DRAIN GUARANTEE -- every registered source collected, chained and converted, or named.

THE PRINCIPAL, 2026-09-23: *"make sure they are always collected, 100% exploited and converted."*
`source_evig` prices the queue; pricing ORDERS a backlog and never drains one, and a source that is
never fetched has an information gain of exactly zero however well it is ranked. On the first
priced pass 147 of 155 sources had never been collected.

WHAT THIS ORGAN GUARANTEES, and each clause is a number it publishes.

  1. THE BACKLOG FALLS EVERY PASS. The top of the EVIG ranking that has never been collected is
     handed to `asia_collector --id ...` this cycle, until the backlog is empty. `n_uncollected`,
     the OLDEST never-collected source and the measured drain rate (sources per pass, and the
     passes remaining at that rate) are published every pass.
  2. UNREACHABLE IS RECORDED, NEVER SILENT. A source that genuinely cannot be fetched lands in
     `not_reached` with the url tried, the status the collector recorded and the attempt count.
     Absence of a row is the one thing this organ does not allow.
  3. A CHAIN, NOT A FETCH. Per source: COLLECTED (bytes in the vault) -> INGESTED (a series with
     a PIT vintage and availability stamp) -> REPRESENTED (rows in that series) -> CELLS_EMITTED
     (candidates the registry credits to it) -> CELLS_JUDGED (those the one gauntlet judged). A
     source that stops at bytes is as useless as one never fetched, and the stage it stopped at
     is the published reason.
  4. TWO RATCHETS THAT ONLY FALL, in `data/source_drain_ratchet.json`: `uncollected` and
     `collected_but_unconverted`. `scripts/check_source_drain.py` fails when either RISES above
     its own best, or when the oldest never-collected source ages past its own cadence window.
  5. IT REPAIRS, IT DOES NOT FILE TASKS (LAWS 7, "a report is not a remedy"). A source stopped at
     bytes is handed to the desk's OWN generic reader -- `asia_parser.parse_all(only=...)`, which
     already dispatches HTML, JSON, CSV, XML, XLSX, PDF and ZIP -- highest EVIG first, every
     pass. A source that is represented and has never emitted a cell is enqueued through the
     canonical registry door (`libs.moat.registry.record_discovery` / `enqueue_candidate`) so the
     one gauntlet can judge it on its own clock. A task row survives only where the repair
     genuinely needs NEW CODE, and `needs_code` is a third ratchet that must keep falling.

  6. THE NUMBER TO MAXIMISE is CELLS REACHING THE GAUNTLET PER SOURCE. A source that is collected
     and represented and still emits nothing gets its reason named and a task: REBUILD (the
     representation exists to be fixed) or RETIRE (nothing to represent), appended to
     `data/source_rebuild_tasks.jsonl`. Never a quiet zero.

NOTHING HERE IS A CAP. It only ever causes MORE collection and MORE conversion; no source is
throttled, no fetch is refused, and the fence fails on a RISING backlog, never on a growing one
that is being worked.

    python desks/mt5/research/source_drain.py --once --budget-s 300 [--no-fetch]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = DESK / "data" / "asia_sources.json"
STATE = DESK / "data" / "lake" / "collector_state.json"
VAULT = DESK / "data" / "lake" / "vault"
SERIES = DESK / "data" / "lake" / "series"
SOURCE_REGISTRY = DESK / "reports" / "SOURCE_REGISTRY.json"
EVIG = DESK / "reports" / "SOURCE_EVIG.json"
RATCHET = DESK / "data" / "source_drain_ratchet.json"
TASKS = DESK / "data" / "source_rebuild_tasks.jsonl"
CHAIN_STATE = DESK / "data" / "source_chain_state.json"
OUT = DESK / "reports" / "SOURCE_DRAIN.json"

COLLECTOR = DESK / "research" / "asia_collector.py"
REPAIR_BATCH = 8           # sources re-parsed per pass, highest EVIG at zero cells first
STALL_WINDOW_H = 168.0     # the unconverted ratchet must FALL within a week or the fence fails
#: Bumped whenever a ratchet's DEFINITION changes. A best recorded under an older definition is
#: not comparable, so the bests re-seed at today's numbers and fall from there (the principal,
#: 2026-09-23: "seed it at today's number and let each pass lower it"). Never bump it to escape
#: a breach -- the git history of this constant is the audit trail for exactly that.
METRIC_VERSION = 2
BATCH = 12                 # sources handed to the collector per pass; raised by budget, never cut
OK_STATUSES = ("COLLECTED", "UNCHANGED", "NOT_MODIFIED")
STAGES = ("collected", "ingested", "represented", "cells_emitted", "cells_judged")
#: Declared cadence -> the hours a source may go uncollected before the fence calls it stale.
#: Three times its own publication cadence: a monthly release missing for a quarter is a defect.
WINDOW_H: dict[str, float] = {"realtime": 3.0, "intraday": 18.0, "daily": 144.0,
                              "weekly": 1_008.0, "monthly": 4_320.0, "quarterly": 12_960.0,
                              "irregular": 6_480.0}


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def _sources() -> list[dict[str, Any]]:
    reg = _read(REGISTRY, {}) or {}
    rows = reg.get("sources") if isinstance(reg, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("id")
            and str(r.get("role") or "mechanism") != "transport"]


def _credited() -> tuple[dict[str, dict[str, int]], str]:
    """Cells the source registry credits to a source id, by exact or namespaced match."""
    doc = _read(SOURCE_REGISTRY, {}) or {}
    rows: list[dict[str, Any]] = []
    for key in ("top_by_roi", "top_by_reputation", "sources", "rows"):
        v = doc.get(key)
        if isinstance(v, list):
            rows.extend(r for r in v if isinstance(r, dict))
    if not rows:
        return {}, "no reports/SOURCE_REGISTRY.json rows on this host"
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        sid = str(r.get("source_id") or r.get("id") or "")
        if not sid:
            continue
        out[sid.split(":")[-1]] = {"leads": int(r.get("n_leads") or 0),
                                   "testable": int(r.get("n_testable") or 0),
                                   "judged": int(r.get("n_certified") or 0)}
    return out, ""


def _registry_cells() -> tuple[dict[str, dict[str, int]], str]:
    """Discoveries and candidates the CANONICAL registry holds per source id.

    The source registry's credit report is rebuilt on its own clock, so a discovery enqueued by
    this organ's repair would be invisible here for an hour and the conversion number would lie
    in the pessimistic direction. This counts the registry itself, which is the record both the
    gauntlet and the compiler read."""
    try:
        from libs.moat.registry import connect
        conn = connect()
    except Exception as exc:
        return {}, f"registry unavailable: {type(exc).__name__}: {exc}"
    out: dict[str, dict[str, int]] = {}
    try:
        for sid, n in conn.execute(
                "SELECT source_id, COUNT(*) FROM discoveries GROUP BY source_id"):
            out.setdefault(str(sid), {"leads": 0, "testable": 0, "judged": 0})["testable"] = int(n)
        for sid, n in conn.execute(
                "SELECT source_id, COUNT(*) FROM discoveries WHERE state NOT IN "
                "('UNPROCESSED','REJECTED') GROUP BY source_id"):
            out.setdefault(str(sid), {"leads": 0, "testable": 0, "judged": 0})["judged"] = int(n)
    except Exception as exc:
        return out, f"registry query failed: {type(exc).__name__}: {exc}"
    finally:
        with contextlib.suppress(Exception):
            conn.close()
    return out, ""


def chain_for(src: dict[str, Any], state: dict[str, Any],
              credited: dict[str, dict[str, int]]) -> dict[str, Any]:
    """Where this source stands in the whole chain, one row, every stage measured."""
    sid = str(src.get("id"))
    _row = state.get(sid)
    row: dict[str, Any] = dict(_row) if isinstance(_row, dict) else {}
    status = str(row.get("last_status") or "")
    vault_hit = (VAULT / sid).exists()
    collected = bool(status in OK_STATUSES or vault_hit)
    series = next((p for p in (SERIES / f"{sid}.parquet", SERIES / f"{sid}.json",
                               SERIES / f"{sid}.csv") if p.exists()), None)
    pit = SERIES / f"{sid}.pit.json"
    pit_doc = _read(pit, {}) if pit.exists() else {}
    frames = (pit_doc.get("frames") if isinstance(pit_doc, dict) else None) or []
    stamped = [f for f in frames if isinstance(f, dict) and str(f.get("status")) == "STAMPED"]
    unstamped_why = next((str(f.get("why")) for f in frames
                          if isinstance(f, dict) and str(f.get("status")) != "STAMPED"), "")
    # INGESTED IS A FRAME ON DISK; STAMPED IS A SEPARATE FACT. `cfets_fixing.pit.json` exists
    # with every frame UNSTAMPED behind a tokenizer error -- that IS an ingestion whose PIT stamp
    # failed, and collapsing it into "never ingested" hid which of the two was broken. Both are
    # published: `ingested`, `pit_stamped`, and the stamper's own reason.
    ingested = bool(series is not None and (pit.exists() or stamped))
    pit_stamped = bool(stamped)
    n_rows = 0
    if isinstance(pit_doc, dict):
        for k in ("n_rows", "rows", "n"):
            try:
                n_rows = int(pit_doc.get(k))  # type: ignore[arg-type]
                break
            except (TypeError, ValueError):
                continue
    if not n_rows and series is not None:
        try:
            n_rows = 1 if series.stat().st_size > 64 else 0
        except OSError:
            n_rows = 0
    represented = bool(ingested and n_rows > 0)
    cells = credited.get(sid) or {}
    emitted = int(cells.get("testable") or cells.get("leads") or 0)
    judged = int(cells.get("judged") or 0)
    reached = "none"
    for stage, ok in (("collected", collected), ("ingested", ingested),
                      ("represented", represented), ("cells_emitted", emitted > 0),
                      ("cells_judged", judged > 0)):
        if not ok:
            break
        reached = stage
    if reached == "none":
        stops_at: str | None = STAGES[0]
    elif reached == STAGES[-1]:
        stops_at = None
    else:
        stops_at = STAGES[STAGES.index(reached) + 1]
    return {
        "id": sid, "cadence": src.get("cadence"), "url": src.get("url"),
        "targets": src.get("targets") or [],
        "collected": collected, "ingested": ingested, "represented": represented,
        "n_rows": n_rows,
        "cells_emitted": emitted, "cells_judged": judged,
        "cells_basis": ("SOURCE_REGISTRY credit" if cells else "no registry credit row"),
        "parse_error": unstamped_why or None, "pit_stamped": pit_stamped,
        "stage_reached": reached, "stops_at": stops_at,
        "last_status": status or None,
        "last_attempt_epoch": row.get("last_attempt_epoch"),
        "why": (
            "never collected: no vault blob and no successful collector status" if not collected
            else ("collected but never ingested: bytes landed and no series frame was written"
                  + (f" ({unstamped_why})" if unstamped_why else ""))
            if not ingested
            else ("ingested but empty: the series exists and carries no rows"
                  + (f"; PIT stamp failed: {unstamped_why}" if unstamped_why else ""))
            if not represented
            else "represented and no cell was ever credited to it" if emitted <= 0
            else "cells emitted and none judged by the gauntlet" if judged <= 0
            else "converted: cells reached the one gauntlet"),
    }


def _window_h(src: dict[str, Any]) -> float:
    return WINDOW_H.get(str(src.get("cadence") or "irregular").lower(), 6_480.0)


def _evig_order(ids: list[str]) -> list[str]:
    try:
        from research.source_evig import fetch_order
        return [i for i in fetch_order(ids) if i in set(ids)]
    except Exception:
        return list(ids)


def drain(pending: list[str], budget_s: float, *, fetch: bool = True,
          oldest_first: list[str] | None = None) -> dict[str, Any]:
    """Hand the top of the ranking to the collector, this pass, and record what answered."""
    if not pending:
        return {"attempted": [], "n_attempted": 0, "seconds": 0.0,
                "why": "backlog empty: every registered source has been collected"}
    if not fetch:
        return {"attempted": [], "n_attempted": 0, "seconds": 0.0,
                "why": "--no-fetch: the queue was priced and nothing was requested"}
    oldest_first = oldest_first or []
    # HALF BY PRICE, HALF BY AGE, so the tail can never starve. A pure top-of-ranking batch
    # re-requests the same twelve sources every hour -- the same truncated-prefix defect that
    # cost this desk eighty-four forward clocks -- and a source that fails twice would then be
    # retried forever while one never attempted at all waits behind it. `pending` arrives in
    # EVIG order and `oldest_first` is the least-recently-attempted half, so every uncollected
    # source is reached within ceil(backlog / (BATCH/2)) passes whatever its price.
    head = pending[: max(1, BATCH // 2)]
    tail = [sid for sid in oldest_first if sid not in head][: BATCH - len(head)]
    batch = [*head, *tail]
    args: list[str] = [sys.executable, str(COLLECTOR)]
    for sid in batch:
        args += ["--id", sid]
    args += ["--budget", str(max(30.0, budget_s)), "--timeout", "20"]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=max(60.0, budget_s + 60.0), check=False, cwd=str(DESK))
        tail = (proc.stdout or "").strip().splitlines()[-6:]
        rc: int | None = proc.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        tail, rc = [f"{type(exc).__name__}: {exc}"], None
    return {"attempted": batch, "n_attempted": len(batch), "returncode": rc,
            "seconds": round(time.monotonic() - t0, 2), "collector_tail": tail,
            "why": ("half the batch by EVIG and half by staleness, so the tail of the "
                    "backlog cannot starve behind a source that fails every hour")}


def repair(rows: list[dict[str, Any]], order: list[str], *,
           budget_s: float = 120.0) -> dict[str, Any]:
    """CLOSE THE GAP, do not describe it. Two repairs, both through doors the desk already owns.

    PARSE    a source with bytes and no stamped series is handed to `asia_parser.parse_all`,
             highest EVIG first. That module already dispatches every shape this registry
             returns, so "needs a parser" is true only where ITS dispatch fails -- and then the
             failure text is the task row, not a guess.
    ENQUEUE  a source that IS represented and has never emitted a cell is recorded through the
             canonical registry door as a discovery keyed by the source, so the one gauntlet
             reaches it on its own clock. Nothing here judges anything.
    """
    t0 = time.monotonic()
    rank = {sid: i for i, sid in enumerate(order)}
    to_parse = sorted([r["id"] for r in rows if r["collected"] and not r["represented"]],
                      key=lambda sid: rank.get(sid, 10**6))[:REPAIR_BATCH]
    parsed: dict[str, Any] = {}
    if to_parse:
        try:
            from research import asia_parser
            parsed = asia_parser.parse_all(only=to_parse) or {}
        except Exception as exc:                       # a parser defect never stops the drain
            parsed = {"error": f"{type(exc).__name__}: {exc}"}
    enqueued: list[dict[str, Any]] = []
    for r in sorted([r for r in rows if r["represented"] and r["cells_emitted"] <= 0],
                    key=lambda r: rank.get(r["id"], 10**6))[:REPAIR_BATCH]:
        if time.monotonic() - t0 > budget_s:
            break
        try:
            from libs.moat.registry import record_discovery
            did, created = record_discovery(
                source_id=str(r["id"]), source_type="asia_plane",
                mechanism=(f"asia source {r['id']} conditions "
                           f"{', '.join(r['targets'][:4]) or 'the MT5 universe'}"),
                origin="source_drain", generator="source_drain",
                assets=list(r["targets"])[:8],
                exact_rule_if_known="",
                note="represented series with no cell; queued for the one gauntlet")
            enqueued.append({"id": r["id"], "discovery_id": did, "created": bool(created)})
        except Exception as exc:                       # registry absent on a research container
            enqueued.append({"id": r["id"], "error": f"{type(exc).__name__}: {exc}"})
    return {"parsed_attempted": to_parse, "parse_result": parsed,
            "enqueued": enqueued, "seconds": round(time.monotonic() - t0, 2),
            "rule": ("repairs run every pass, highest expected-information-gain source at zero "
                     "cells first; a task row survives only where the desk's own reader failed "
                     "and the failure text is the task")}


def _tasks(rows: list[dict[str, Any]], now: str) -> list[dict[str, Any]]:
    """A named task per collected-but-unconverted source. Never a quiet zero."""
    out: list[dict[str, Any]] = []
    for r in rows:
        if not r["collected"] or r["cells_judged"] > 0:
            continue
        kind = ("REBUILD" if r["ingested"] or r["represented"] else
                ("REBUILD" if r["collected"] else "RETIRE"))
        if r["collected"] and not r["ingested"]:
            kind = "REBUILD"          # bytes exist: the parser is what is missing
        if r["represented"] and r["cells_emitted"] <= 0:
            kind = "REBUILD"          # rows exist: a family or a mapping is what is missing
        needs_code = bool(r["collected"] and not r["represented"] and r.get("parse_error"))
        out.append({"at": now, "id": r["id"], "task": kind, "stops_at": r["stops_at"],
                    "needs_code": needs_code, "parse_error": r.get("parse_error"),
                    "why": r["why"], "url": r["url"], "targets": r["targets"]})
    return out


def chain_state() -> dict[str, Any]:
    """THE BIRTH FENCE'S DOOR. Per-source chain state keyed by the registry's own ids, so a fence
    checking that a newly registered source inherits the obligation reads this instead of
    re-deriving it. Empty when the organ has not run here -- UNMEASURED, never a pass."""
    doc = _read(CHAIN_STATE, {}) or {}
    by_source = doc.get("by_source") if isinstance(doc, dict) else None
    return dict(by_source) if isinstance(by_source, dict) else {}


def build(budget_s: float = 300.0, *, fetch: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    srcs = _sources()
    state = _read(STATE, {}) or {}
    credited, credit_why = _credited()
    reg_cells, reg_why = _registry_cells()
    for sid, counts in reg_cells.items():                 # the registry is the live record
        base = credited.setdefault(sid, {"leads": 0, "testable": 0, "judged": 0})
        base["testable"] = max(int(base.get("testable") or 0), int(counts.get("testable") or 0))
        base["judged"] = max(int(base.get("judged") or 0), int(counts.get("judged") or 0))
    rows = [chain_for(s, state if isinstance(state, dict) else {}, credited) for s in srcs]
    by_id = {r["id"]: r for r in rows}
    ratchet = _read(RATCHET, {}) or {}
    first_seen: dict[str, str] = dict(ratchet.get("first_seen") or {})

    uncollected_before = [r["id"] for r in rows if not r["collected"]]
    for sid in uncollected_before:
        first_seen.setdefault(sid, now)
    ages = []
    for sid in uncollected_before:
        try:
            seen = datetime.fromisoformat(str(first_seen[sid]).replace("Z", "+00:00"))
            ages.append((sid, (datetime.now(tz=UTC) - seen).total_seconds() / 3600.0))
        except ValueError:
            continue
    oldest = max(ages, key=lambda kv: kv[1], default=(None, 0.0))
    windows = {str(s.get("id")): _window_h(s) for s in srcs}

    pending = _evig_order(uncollected_before)
    # The least-recently-attempted never-collected sources, for the anti-starvation half.
    def _last_attempt(sid: str) -> float:
        row = state.get(sid) if isinstance(state, dict) else None
        try:
            return float(row.get("last_attempt_epoch"))  # type: ignore[union-attr]
        except (TypeError, ValueError, AttributeError):
            return 0.0

    oldest_first = sorted(uncollected_before, key=_last_attempt)
    result = drain(pending, min(budget_s * 0.7, 180.0), fetch=fetch,
                   oldest_first=oldest_first)

    state_mid = _read(STATE, {}) or {}
    rows_mid = [chain_for(s, state_mid if isinstance(state_mid, dict) else {}, credited)
                for s in srcs]
    # REPAIR, THEN RE-MEASURE. The organ closes what it can close on its own clock (LAWS 7: a
    # report is not a remedy), so every number below is POST-repair -- what is still broken after
    # this pass tried, which is the only honest denominator for a ratchet.
    repairs = repair(rows_mid, _evig_order([r["id"] for r in rows_mid]),
                     budget_s=min(budget_s * 0.3, 120.0))
    state_after = _read(STATE, {}) or {}
    credited, credit_why = _credited()
    reg_after, reg_why = _registry_cells()
    for sid, counts in reg_after.items():
        base = credited.setdefault(sid, {"leads": 0, "testable": 0, "judged": 0})
        base["testable"] = max(int(base.get("testable") or 0), int(counts.get("testable") or 0))
        base["judged"] = max(int(base.get("judged") or 0), int(counts.get("judged") or 0))
    rows_after = [chain_for(s, state_after if isinstance(state_after, dict) else {}, credited)
                  for s in srcs]
    by_id_after = {r["id"]: r for r in rows_after}
    uncollected_after = [r["id"] for r in rows_after if not r["collected"]]
    drained = [sid for sid in result.get("attempted") or []
               if by_id_after.get(sid, {}).get("collected")]
    def _status_of(sid: str) -> Any:
        row_after = state_after.get(sid) if isinstance(state_after, dict) else None
        return row_after.get("last_status") if isinstance(row_after, dict) else None

    not_reached = [{"id": sid, "url": by_id.get(sid, {}).get("url"),
                    "collector_status": _status_of(sid),
                    "attempted_at": now,
                    "why": "requested this pass and still uncollected; it leads the next pass"}
                   for sid in (result.get("attempted") or []) if sid not in drained]

    collected_after = [r for r in rows_after if r["collected"]]
    unconverted = [r for r in collected_after if r["cells_judged"] <= 0]
    tasks = _tasks(rows_after, now)
    if tasks:
        TASKS.parent.mkdir(parents=True, exist_ok=True)
        with TASKS.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(t, default=str) for t in tasks) + "\n")

    history = list(ratchet.get("history") or [])[-49:]
    history.append({"at": now, "uncollected": len(uncollected_after),
                    "unconverted": len(unconverted), "drained": len(drained)})
    rate = 0.0
    if len(history) >= 2:
        span = history[0]["uncollected"] - history[-1]["uncollected"]
        rate = round(span / max(len(history) - 1, 1), 3)
    needs_code = [row_["id"] for row_ in tasks if row_.get("needs_code")]
    # A NEW COLLECTION IS BORN UNCONVERTED, and punishing that would make the fence an argument
    # for collecting less -- the exact timidity the principal forbids. So the ratchet is measured
    # on the backlog NET of sources collected since the last best: `unconverted_net`. Convert one
    # and the net falls; collect one and it does not rise.
    drained_now = len(drained)
    since_best = int(ratchet.get("collected_since_best", 0)) + drained_now
    net_unconverted = max(len(unconverted) - since_best, 0)
    if int(ratchet.get("metric_version", 0)) != METRIC_VERSION:
        ratchet = {"first_seen": first_seen, "history": history,
                   "reseeded_at": now, "reseeded_why": (
                       f"metric_version {ratchet.get('metric_version', 0)} -> {METRIC_VERSION}: "
                       f"the unconverted ratchet is now measured NET of sources collected since "
                       f"the last best, and a best recorded under the old definition is not "
                       f"comparable")}
        since_best = 0
        net_unconverted = len(unconverted)
    prev_best_conv = int(ratchet.get("best_unconverted", 10**9))
    best_conv = min(prev_best_conv, net_unconverted)
    if best_conv < prev_best_conv:
        since_best = 0                                    # a new best re-bases the allowance
    best_unc = min(int(ratchet.get("best_uncollected", 10**9)), len(uncollected_after))
    best_code = min(int(ratchet.get("best_needs_code", 10**9)), len(needs_code))
    # THE STALL CLOCK. A ratchet that only falls says nothing about a count that never moves, so
    # the moment each count last FELL is recorded and the fence fails when a non-zero count has
    # not fallen inside STALL_WINDOW_H. Without it a backlog could sit at today's number forever
    # while every pass reported OK.
    fell_conv = (now if net_unconverted < int(ratchet.get("unconverted_net", 10**9))
                 else str(ratchet.get("unconverted_last_fell_at") or now))
    fell_code = (now if len(needs_code) < int(ratchet.get("needs_code", 10**9))
                 else str(ratchet.get("needs_code_last_fell_at") or now))
    _write(RATCHET, {"at": now, "metric_version": METRIC_VERSION,
                     "reseeded_at": ratchet.get("reseeded_at"),
                     "reseeded_why": ratchet.get("reseeded_why"),
                     "best_uncollected": best_unc, "best_unconverted": best_conv,
                     "best_needs_code": best_code,
                     "uncollected": len(uncollected_after), "unconverted": len(unconverted),
                     "unconverted_net": net_unconverted,
                     "collected_since_best": since_best,
                     "needs_code": len(needs_code),
                     "unconverted_last_fell_at": fell_conv,
                     "needs_code_last_fell_at": fell_code,
                     "stall_window_h": STALL_WINDOW_H,
                     "oldest_never_collected": oldest[0],
                     "oldest_age_h": round(oldest[1], 2),
                     "oldest_window_h": windows.get(str(oldest[0]), 6_480.0),
                     "first_seen": first_seen, "history": history,
                     "rule": ("three counts are RATCHETS and each carries the moment it last "
                              "fell: check_source_drain.py fails when one rises above its own "
                              "best, when a non-zero count has not fallen inside the stall "
                              "window, or when the oldest never-collected source ages past its "
                              "own cadence window")})
    # THE CHAIN STATE, FOR ANY FENCE THAT WANTS IT. The birth fence checks the same axis for a
    # source registered tomorrow, so this publishes the per-source stage rather than making it
    # re-derive one. The SET is the registry's own rows, read every pass -- a source added to
    # data/asia_sources.json inherits the whole obligation with no list to maintain anywhere.
    _write(CHAIN_STATE, {"at": now, "stages": list(STAGES),
                         "derived_from": "desks/mt5/data/asia_sources.json, read every pass",
                         "by_source": {r["id"]: {k: r[k] for k in
                                                 ("stage_reached", "stops_at", "collected",
                                                  "ingested", "represented", "cells_emitted",
                                                  "cells_judged", "parse_error", "why")}
                                       for r in rows_after}})

    stages: dict[str, int] = {}
    for r in rows_after:
        stages[str(r["stage_reached"])] = stages.get(str(r["stage_reached"]), 0) + 1
    zero_cell_top = [
        {"id": r["id"], "evig_rank": pending.index(r["id"]) if r["id"] in pending else None,
         "stage_reached": r["stage_reached"], "why": r["why"]}
        for r in sorted(rows_after, key=lambda r: (r["cells_judged"], r["cells_emitted"]))
        if r["cells_emitted"] <= 0][:5]

    return {
        "at": now,
        "status": "OK" if rows_after else "UNMEASURED",
        "n_sources": len(rows_after),
        "uncollected_before": len(uncollected_before),
        "uncollected_after": len(uncollected_after),
        "n_drained_this_pass": len(drained), "drained": drained,
        "drain_rate_per_pass": rate,
        "passes_to_empty": (round(len(uncollected_after) / rate, 1) if rate > 0 else None),
        "oldest_never_collected": {"id": oldest[0], "age_h": round(oldest[1], 2),
                                   "window_h": windows.get(str(oldest[0]), 6_480.0)},
        "not_reached": not_reached,
        "chain": {"stages": STAGES, "census": stages},
        "n_collected": len(collected_after),
        "n_collected_but_unconverted": len(unconverted),
        "n_unconverted_net_of_new_collections": net_unconverted,
        "n_cells_judged_total": sum(int(r["cells_judged"]) for r in rows_after),
        "cells_credit_basis": (credit_why or "SOURCE_REGISTRY per-source credit")
        + ("; " + reg_why if reg_why else "; canonical registry discovery counts"),
        "highest_evig_at_zero_cells": zero_cell_top,
        "tasks_appended": len(tasks), "n_needs_code": len(needs_code),
        "needs_code": needs_code[:20],
        "repairs": repairs,
        "first_source_with_a_judged_cell": next(
            (r["id"] for r in sorted(rows_after, key=lambda r: -int(r["cells_judged"]))
             if int(r["cells_judged"]) > 0), None),
        "cells_judged_by_source": {r["id"]: int(r["cells_judged"]) for r in rows_after
                                   if int(r["cells_judged"]) > 0},
        "chain_state": str(CHAIN_STATE),
        "rows": rows_after,
        "collector": result,
        "consumers": [
            "scripts/check_source_drain.py -> the two ratchets and the oldest-source window; the "
            "law gate fails when a backlog RISES",
            "desks/mt5/data/source_rebuild_tasks.jsonl -> one named REBUILD/RETIRE task per "
            "collected-but-unconverted source, re-read by this organ each pass",
            "desks/mt5/research/asia_collector.py -> the sources this pass requested by id",
        ],
        "boundary": (
            "THIS ONLY EVER CAUSES MORE COLLECTION. No source is throttled, disabled or refused; "
            "the fence fails on a RISING backlog, never on a large one that is being worked."),
        "seconds": round(time.monotonic() - t0, 2),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--no-fetch", action="store_true",
                    help="measure the chain and the ratchets without requesting a collection")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, fetch=not a.no_fetch)
    try:
        _write(OUT, doc)
    except OSError as exc:
        print(f"source drain: could not write {OUT}: {exc}")
        return 1
    print(f"source drain: uncollected {doc['uncollected_before']} -> "
          f"{doc['uncollected_after']} ({doc['n_drained_this_pass']} drained this pass, rate "
          f"{doc['drain_rate_per_pass']}/pass, {doc['passes_to_empty']} passes to empty)")
    o = doc["oldest_never_collected"]
    print(f"  oldest never collected: {o['id']} at {o['age_h']}h of a {o['window_h']}h window")
    print(f"  chain census: {doc['chain']['census']}")
    rp = doc["repairs"]
    print(f"  repaired this pass: {len(rp.get('parsed_attempted') or [])} re-parsed, "
          f"{len(rp.get('enqueued') or [])} enqueued to the registry; "
          f"{doc['n_needs_code']} row(s) genuinely need new code")
    print(f"  first source with a judged cell: {doc['first_source_with_a_judged_cell']}")
    print(f"  collected {doc['n_collected']}, of which {doc['n_collected_but_unconverted']} "
          f"unconverted; {doc['n_cells_judged_total']} cell(s) judged in total; "
          f"{doc['tasks_appended']} task(s) appended")
    for r in doc["highest_evig_at_zero_cells"]:
        print(f"   ZERO CELLS {str(r['id'])[:32]:<32} rank={r['evig_rank']} "
              f"stage={r['stage_reached']} -- {r['why'][:60]}")
    for r in doc["not_reached"][:6]:
        print(f"   NOT_REACHED {str(r['id'])[:30]:<30} status={r['collector_status']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""CONSUMPTION-TIME FRESHNESS FENCE (L1.44) -- which live decisions are consuming frozen inputs
RIGHT NOW.

Joins {artifact age x consumer contract x recent read events} from the self-building registry
that libs.ops.fresh.read_fresh maintains (data/freshness_contracts.jsonl). Producer-side fences
already ask "did the producer run?"; this is the other half nobody had -- "is anything STEERING
on its corpse?" -- and it is the half that carries the severity, because a dead producer whose
output nobody reads is an idle seat while a dead producer whose output the executor reads is the
money path running on a memory.

PER-CONTRACT VERDICTS:
  FRESH           artifact within the consumer's declared tolerance.
  STALE-CONSUMED  artifact older than the contract AND the consumer read it since it went stale
                  (a stale_read/unreadable_read event in the last 26h) -- the smoking gun, with
                  the caller named. This is what fails the fence.
  STALE-UNREAD    older than the contract, no recent read -- the producer-side fences own chasing
                  the dead producer; reported here for the blast-radius join, never double-fired.
  MISSING         the contracted artifact does not exist at all.
  FOREIGN         an absolute path outside the repo leaked into the registry (test hygiene
                  guard) -- skipped from verdicts, reported so the leak is visible.

FENCE STATUS (exit 2 on the first four -- a gate, not a report):
  STALE-CONSUMED  any contract in that state.
  UNWIRED         a declared decision-path read site no longer references its contract -- the
                  wiring-regression check, so deleting a call site is loud.
  UNMEASURED      zero contracts recorded. An empty registry must never read OK (L1.28a):
                  it means the helper is unwired or no consumer has ticked since deploy.
  MISSING         a consumer declared a contract for an artifact THAT DOES NOT EXIST. Until
                  2026-08-12 (R0398) this was folded into STALE-UNREAD and exited 0, which is
                  the wrong reading in both directions: STALE-UNREAD says "a producer ran once
                  and has since died, and the producer-side fences own chasing it", but nothing
                  produces this path at all, so no producer-side fence has a row to fire on --
                  the artifact is invisible to EVERY fence on the desk while a decision-path
                  consumer reads it. That is the L1.55 fabrication precondition (a consumer
                  reading a file with no producer takes its default and publishes the result as
                  a measurement), and ABSENT and STALE demand opposite repairs: build or
                  schedule the producer vs revive the one that stopped.
  STALE-UNREAD    stale artifacts exist but nothing consumed them -- reported, exit 0.
  OK              every contract fresh.

kind='state' contracts are judged by their GUARDIAN's age (a valid-until-changed file is
legitimately old; the fence must not cry wolf on healthy state -- L1.43).

    python scripts/check_freshness.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: TTL-cached, pages-but-does-not-block; a governance fault never silences
# the organ that reports on the money path's inputs.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fresh import REGISTRY_REL, _age_of  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: WIRING-REGRESSION CHECK. These call sites are the decision-path reads whose contracts must
#: not silently disappear; if a token vanishes from its file the contract was deleted, and that
#: must fail the fence rather than silently return the read site to uncontracted blindness.
#: Checked against the REPO the fence lives in (law surface), never the state root (state
#: surface) -- the same law/state split that keeps state fences out of commit gates.
#:
#: WIDENED 2026-08-12 (R0398) from the two bootstrap sites to every non-test decision-path
#: caller of `read_fresh`. Two entries was the migration's beachhead, not a scope: it made the
#: regression check cover the executor and the pager while the conviction trader's cost gate and
#: the lending-haircut base rates -- both of which steer money -- could have their contracts
#: deleted with the fence still green. The tokens name the CONTRACT, not just the helper, so
#: re-pointing a read at a different artifact is a regression too.
_WIRED: tuple[tuple[str, str], ...] = (
    ("scripts/run_cashcarry_executor.py", "read_fresh"),
    ("scripts/run_alerts.py", "live_guard_dead"),
    ("scripts/run_conviction_trader.py", 'read_fresh("data/cost_hunt.json"'),
    ("libs/research/lending_haircut.py", "read_fresh(BASE_RATES_PATH"),
)

_CONSUMED_WINDOW_H = 26.0     # a stale read within this window counts as "consumed while stale"


def _parse_registry(
        reg: Path) -> tuple[dict[tuple[str, str], dict], dict[tuple[str, str], str], int]:
    """(latest contract per (caller, path), latest stale/unreadable event ts, lines dropped).

    A corrupt line loses one record, never the fence -- but the drop is COUNTED and published
    (L1.60). "Counted by the caller via the returned dicts staying sparse", as this said before
    2026-08-12, is not a count: a registry whose lines all fail to parse and a registry that was
    never written produce the same sparse dicts, and only one of them is a corrupt writer.
    """
    contracts: dict[tuple[str, str], dict] = {}
    events: dict[tuple[str, str], str] = {}
    dropped = 0
    try:
        lines = reg.read_text("utf-8").splitlines()
    except OSError:
        return {}, {}, 0
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            dropped += 1
            continue
        key = (str(r.get("caller", "")), str(r.get("path", "")))
        if r.get("event") == "contract":
            contracts[key] = r
        elif r.get("event") in ("stale_read", "unreadable_read"):
            events[key] = str(r.get("ts", ""))
    return contracts, events, dropped


def _recent(ts: str, now: datetime) -> bool:
    try:
        at = datetime.fromisoformat(ts)
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        return (now - at).total_seconds() / 3600.0 <= _CONSUMED_WINDOW_H
    except ValueError:
        return False


def _verdict(root: Path, c: dict, ev_ts: str | None, now: datetime) -> dict[str, Any]:
    path, caller = str(c.get("path", "")), str(c.get("caller", ""))
    kind = str(c.get("kind", "measurement"))
    max_age_h = float(c.get("max_age_h", 0.0) or 0.0)
    p = Path(path)
    if p.is_absolute() and not str(p).startswith(str(root)):
        return {"caller": caller, "path": path, "verdict": "FOREIGN",
                "detail": "absolute path outside the root leaked into the registry"}
    target = p if p.is_absolute() else root / p
    if kind == "state" and c.get("guardian"):
        g = Path(str(c["guardian"]))
        target = g if g.is_absolute() else root / g
    age, source, _data = _age_of(target)
    out: dict[str, Any] = {"caller": caller, "path": path, "kind": kind,
                           "max_age_h": max_age_h, "age_h": None if age is None else
                           round(age, 2), "age_source": source}
    if age is None:
        out["verdict"] = ("STALE-CONSUMED" if ev_ts and _recent(ev_ts, now) else "MISSING")
        out["detail"] = f"contracted artifact unreadable ({source})"
    elif age <= max_age_h:
        out["verdict"] = "FRESH"
    else:
        consumed = bool(ev_ts and _recent(ev_ts, now))
        out["verdict"] = "STALE-CONSUMED" if consumed else "STALE-UNREAD"
        out["detail"] = (f"{age:.1f}h old vs {max_age_h}h contract"
                         + (f"; consumed while stale (last stale read {ev_ts})" if consumed
                            else "; no read observed since it went stale"))
    return out


def _unwired(repo: Path) -> list[str]:
    bad = []
    for rel, token in _WIRED:
        try:
            src = (repo / rel).read_text("utf-8", errors="ignore")
        except OSError:
            bad.append(f"{rel}: unreadable -- wiring unverifiable counts as UNWIRED, never OK")
            continue
        if token not in src:
            bad.append(f"{rel}: token '{token}' absent -- the freshness contract was removed")
    return bad


def build_report(root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    contracts, events, dropped_lines = _parse_registry(root / REGISTRY_REL)
    rows = [_verdict(root, c, events.get(k), now) for k, c in sorted(contracts.items())]
    unwired = _unwired(_ROOT)

    n_by = {v: sum(1 for r in rows if r["verdict"] == v)
            for v in ("FRESH", "STALE-CONSUMED", "STALE-UNREAD", "MISSING", "FOREIGN")}
    judged = [r for r in rows if r["verdict"] != "FOREIGN"]
    if n_by["STALE-CONSUMED"]:
        status = "STALE-CONSUMED"
    elif unwired:
        status = "UNWIRED"
    elif not judged:
        status = "UNMEASURED"
    elif n_by["MISSING"]:
        # R0398. MISSING ranks ABOVE STALE-UNREAD and fails the fence. It used to be folded into
        # STALE-UNREAD, whose whole justification for exiting 0 is that "the producer-side
        # fences own chasing the dead producer" -- true of a stale artifact, false of an absent
        # one, because a path nothing has ever written appears in no producer-side registry and
        # therefore has no owner anywhere on the desk.
        status = "MISSING"
    elif n_by["STALE-UNREAD"]:
        status = "STALE-UNREAD"
    else:
        status = "OK"
    fresh_fraction = (round(n_by["FRESH"] / len(judged), 3) if judged else None)
    offenders = [f"{r['caller']} <- {r['path']} ({r.get('detail', '')})"
                 for r in rows if r["verdict"] == "STALE-CONSUMED"]
    return {
        "generated": now.isoformat(),
        "law": "L1.44 -- a decision is only as live as its inputs: every decision-path read "
               "declares its max tolerated age at the read site, and a live decision consuming "
               "a frozen input is a fence failure, with the caller named",
        "status": status,
        "n_contracts": len(judged), "by_verdict": n_by,
        "fresh_fraction": fresh_fraction,
        "n_registry_lines_dropped": dropped_lines,   # L1.60: a skip that is counted, not hidden
        "unwired": unwired,
        "missing": [f"{r['caller']} <- {r['path']}" for r in rows if r["verdict"] == "MISSING"],
        "contracts": rows,
        "detail": (f"{len(judged)} contract(s): " + ", ".join(f"{k}={v}" for k, v in
                   n_by.items() if v) if judged else
                   "ZERO contracts recorded -- helper unwired or no consumer has ticked; an "
                   "empty registry must never read OK (L1.28a)")
                  + ("; UNWIRED: " + "; ".join(unwired) if unwired else ""),
        "stale_consumed": offenders,
        "next_action": ("revive the dead producer or re-wire the caller through "
                        "libs.ops.fresh.read_fresh; the offender list names both ends of every "
                        "stale edge" if offenders or unwired else
                        "BUILD OR SCHEDULE THE PRODUCER -- a contracted artifact that has never "
                        "existed has no producer-side fence to chase it, and its consumer is "
                        "steering on a default right now (L1.55)" if n_by["MISSING"] else
                        "extend contracts to the next uncontracted decision-path read"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/freshness_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"freshness (L1.44): {rep['status']} -- {rep['detail']}")
        for line in rep["stale_consumed"]:
            print(f"  STALE-CONSUMED: {line}")
        for line in rep["unwired"]:
            print(f"  UNWIRED: {line}")
        for line in rep["missing"]:
            print(f"  MISSING: {line}")
        if rep["n_registry_lines_dropped"]:
            print(f"  registry: {rep['n_registry_lines_dropped']} unparseable line(s) dropped")
    if args.report_only:
        return 0
    return 2 if rep["status"] in ("STALE-CONSUMED", "UNWIRED", "UNMEASURED", "MISSING") else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""THE HEALTH BOARD -- one artifact that says, for every organ, how fresh it is, what it last
concluded and whether it is failing.

The desk measures its own health in five places that never meet:

    docs/research/runtime_state.json         runtime_attestation: per organ, LIVE / STALE /
                                             MISSING / NEVER / UNMEASURED by artifact age
    desks/mt5/data/events.jsonl              the event log: every leg's LEG_DONE / LEG_FAILED
    desks/mt5/reports/acceptance_properties.json   AP1..AP5, MET / PARTIAL / MISSING
    desks/mt5/data/stall_watch.json          the box's watchdog: failing and missing tasks, memory
    desks/mt5/reports/{BUILD_FAILURE_BANK,TRADE_PATHOLOGY,EXPERIMENT_CONTRACTS}.json
                                             the three hourly readers built beside this board

This joins them on the organ's name and publishes ONE verdict per organ:

    GREEN        artifact fresh (LIVE) AND its last leg run did not fail
    RED          the last run FAILED, or the artifact is STALE / MISSING while the organ runs
    AMBER        fresh but its last reading is a failure verdict, or stale with no run record
    UNMEASURED   nothing on this host proves it either way -- NEVER GREEN (L1.28a)

and a desk-level verdict that can only be GREEN when every source was read and no organ is RED.
A source that is absent or older than its lease makes the board UNMEASURED on that axis, with the
reason, rather than silently shrinking what it judges.

`desks/mt5/reports/HEALTH_BOARD.json` + `HEALTH_BOARD.md`, hourly (leg `health_board`, after
`acceptance`, so it reads this pass's properties). Report only: it repairs, restarts and vetoes
nothing -- the control plane and the clock fixer own repair.

    python desks/mt5/research/health_board.py --once
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
RUNTIME = ROOT / "docs" / "research" / "runtime_state.json"
EVENTS = DESK / "data" / "events.jsonl"
ACCEPTANCE = DESK / "reports" / "acceptance_properties.json"
STALL = DESK / "data" / "stall_watch.json"
READERS = {
    "build_failure_bank": DESK / "reports" / "BUILD_FAILURE_BANK.json",
    "trade_pathology": DESK / "reports" / "TRADE_PATHOLOGY.json",
    "experiment_contracts": DESK / "reports" / "EXPERIMENT_CONTRACTS.json",
    # CRO D35: the 24/7 GitHub resident miner (federation_ops' delta scan); RAN or UNMEASURED.
    "github_resident_miner": DESK / "reports" / "GITHUB_RESIDENT_MINER.json",
    # ROMAN-0832: who excites whom (bar events per symbol, Treasury -> USD -> gold), hourly.
    "cross_excitation": DESK / "reports" / "CROSS_EXCITATION.json",
}
OUT = DESK / "reports" / "HEALTH_BOARD.json"
OUT_MD = DESK / "reports" / "HEALTH_BOARD.md"

SCHEMA = "health-board/1"
GREEN, AMBER, RED, UNMEASURED = "GREEN", "AMBER", "RED", "UNMEASURED"
#: A source older than this is a statement about a desk that no longer exists.
SOURCE_LEASE_H = {"runtime_attestation": 3.0, "events": 3.0, "acceptance": 3.0,
                  "stall_watch": 1.0}
EVENT_TAIL_BYTES = 4 * 1024 * 1024
#: Words that mark an artifact's own last reading as a failure.
_FAIL_WORDS = ("FAIL", "BREACH", "RED", "ERROR", "BROKEN", "FALSIFIED", "REJECTED")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00")[:32])
    except ValueError:
        try:
            t = datetime.fromisoformat(str(x).replace("Z", "+00:00")[:25])
        except ValueError:
            return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _age_h(t: datetime | None) -> float | None:
    return None if t is None else round((_now() - t).total_seconds() / 3600.0, 3)


def _source(name: str, at: datetime | None, present: bool, why: str = "") -> dict[str, Any]:
    age = _age_h(at)
    lease = SOURCE_LEASE_H.get(name)
    if not present:
        state = UNMEASURED
        why = why or "absent on this host"
    elif age is None:
        state, why = UNMEASURED, why or "no timestamp in the source"
    elif lease is not None and age > lease:
        state, why = "STALE", f"{age:.1f}h old against a {lease:.0f}h lease"
    else:
        state, why = "FRESH", why or f"{age:.2f}h old"
    return {"state": state, "age_h": age, "why": why}


def read_events(path: Path) -> tuple[dict[str, dict[str, Any]], datetime | None, bool]:
    """leg -> its LAST LEG_DONE / LEG_FAILED row (tail of the log only)."""
    last: dict[str, dict[str, Any]] = {}
    newest: datetime | None = None
    try:
        with path.open("rb") as fh:
            size = os.fstat(fh.fileno()).st_size
            if size > EVENT_TAIL_BYTES:
                fh.seek(size - EVENT_TAIL_BYTES, os.SEEK_SET)
                fh.readline()
            raw = fh.read().decode("utf-8", "replace")
    except OSError:
        return {}, None, False
    for line in raw.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        t = _ts(r.get("at"))
        if t is not None and (newest is None or t > newest):
            newest = t
        if r.get("kind") in ("LEG_DONE", "LEG_FAILED") and r.get("leg"):
            last[str(r["leg"])] = r
    return last, newest, True


def _organ_leg(organ: str) -> str | None:
    kind, _, name = organ.partition(":")
    return name if kind == "leg" else None


def _last_reading(artifact: Path | None) -> str | None:
    """The artifact's own verdict field, if it carries one."""
    if artifact is None:
        return None
    d = _json(artifact)
    if not isinstance(d, dict):
        return None
    for k in ("status", "verdict", "state", "result", "ok"):
        if k in d and not isinstance(d[k], (dict, list)):
            return str(d[k])
    return None


def judge(organ: dict[str, Any], event: dict[str, Any] | None) -> tuple[str, str]:
    state = str(organ.get("state") or UNMEASURED)
    ev_kind = (event or {}).get("kind")
    if ev_kind == "LEG_FAILED":
        return RED, f"last run FAILED at {event.get('at')} ({event.get('outcome') or 'no outcome'})"
    if state == "LIVE":
        last = str(organ.get("last_reading") or "")
        if last and any(w in last.upper() for w in _FAIL_WORDS):
            return AMBER, f"fresh, but its own last reading is {last!r}"
        if event is None and str(organ.get("kind")) == "leg":
            return AMBER, "fresh artifact, but no LEG_DONE in the event log's tail"
        return GREEN, str(organ.get("why") or "artifact inside its cadence")
    if state in ("STALE", "MISSING"):
        if ev_kind == "LEG_DONE":
            return RED, f"{state}: the leg reports done ({event.get('at')}) yet its artifact is " \
                        f"{'old' if state == 'STALE' else 'absent'}"
        return (RED if state == "MISSING" else AMBER), str(organ.get("why") or state)
    return UNMEASURED, str(organ.get("why") or f"{state}: nothing on this host proves it")


def build(runtime: Path | None = None, events: Path | None = None,
          acceptance: Path | None = None, stall: Path | None = None,
          readers: dict[str, Path] | None = None) -> dict[str, Any]:
    rt = _json(runtime or RUNTIME)
    ev_last, ev_newest, ev_present = read_events(events or EVENTS)
    acc = _json(acceptance or ACCEPTANCE)
    sw = _json(stall or STALL)
    sources = {
        "runtime_attestation": _source("runtime_attestation",
                                       _ts((rt or {}).get("generated_at")), isinstance(rt, dict)),
        "events": _source("events", ev_newest, ev_present),
        "acceptance": _source("acceptance", _ts((acc or {}).get("at")), isinstance(acc, dict)),
        "stall_watch": _source("stall_watch", _ts((sw or {}).get("checked_at")),
                               isinstance(sw, dict)),
    }
    organs: list[dict[str, Any]] = []
    for o in ((rt or {}).get("organs") or []):
        if not isinstance(o, dict) or not o.get("organ"):
            continue
        leg = _organ_leg(str(o["organ"]))
        art = str(o.get("artifact") or "")
        art_p = ROOT / art if art and art != UNMEASURED else None
        row = {"organ": o["organ"], "kind": o.get("kind"), "clock": o.get("clock"),
               "state": o.get("state"), "why": o.get("why"),
               "artifact": art or None, "artifact_age_s": o.get("artifact_age_s"),
               "last_reading": (_last_reading(art_p)
                                if o.get("state") == "LIVE" and art_p is not None else None)}
        ev = ev_last.get(leg) if leg else None
        verdict, why = judge(row, ev)
        row.update({"verdict": verdict, "verdict_why": why,
                    "last_event": ({k: ev.get(k) for k in ("at", "kind", "outcome")}
                                   if ev else None)})
        organs.append(row)
    for name, p in (READERS if readers is None else readers).items():
        d = _json(p)
        st = str((d or {}).get("status") or "")
        organs.append({
            "organ": f"reader:{name}", "kind": "reader", "artifact": str(p.relative_to(ROOT))
            if p.is_relative_to(ROOT) else str(p),
            "state": "LIVE" if isinstance(d, dict) else "NEVER",
            "last_reading": st or None,
            "verdict": (UNMEASURED if not isinstance(d, dict) or st == UNMEASURED else GREEN),
            "verdict_why": (f"{p.name} absent on this host" if not isinstance(d, dict)
                            else f"its own status is {st or 'unstated'}")})
    counts = Counter(o["verdict"] for o in organs)
    reported_failing = [a for a in ((sw or {}).get("actions") or [])
                        if isinstance(a, str) and a.upper().startswith(("FAILING", "TASK MISSING",
                                                                        "STACKED", "HUNG"))]
    # A watchdog reading past its lease is a claim about an older box: it is shown, never counted
    # as a failure now (and the stale source itself already keeps the desk off GREEN).
    sw_fresh = sources["stall_watch"]["state"] == "FRESH"
    failing_tasks = reported_failing if sw_fresh else []
    acc_props = {k: {"status": (v or {}).get("status"), "measured": (v or {}).get("measured")}
                 for k, v in ((acc or {}).get("properties") or {}).items()}
    unmeasured_sources = [k for k, s in sources.items() if s["state"] != "FRESH"]
    if counts.get(RED) or failing_tasks:
        desk = RED
    elif unmeasured_sources or not organs:
        desk = UNMEASURED
    elif counts.get(AMBER) or counts.get(UNMEASURED):
        desk = AMBER
    else:
        desk = GREEN
    worst = sorted((o for o in organs if o["verdict"] in (RED, AMBER)),
                   key=lambda o: (o["verdict"] != RED, str(o["organ"])))
    return {
        "schema": SCHEMA, "at": _now().isoformat(timespec="seconds"),
        "desk_verdict": desk,
        "desk_verdict_why": (
            f"{counts.get(RED, 0)} RED organ(s), {len(failing_tasks)} failing box task(s)"
            if desk == RED else
            f"sources not fresh: {', '.join(unmeasured_sources)}" if unmeasured_sources else
            "no organ rows to judge" if not organs else
            f"{counts.get(AMBER, 0)} AMBER, {counts.get(UNMEASURED, 0)} UNMEASURED"
            if desk == AMBER else "every source fresh, no organ RED or AMBER"),
        "counts": {v: counts.get(v, 0) for v in (GREEN, AMBER, RED, UNMEASURED)},
        "n_organs": len(organs),
        "sources": sources,
        "box_tasks": {"failing": failing_tasks,
                      "stale_claims": [] if sw_fresh else reported_failing,
                      "free_phys_mb": ((sw or {}).get("memory") or {}).get("free_phys_mb"),
                      "total_phys_mb": ((sw or {}).get("memory") or {}).get("total_phys_mb")}
        if isinstance(sw, dict) else {"status": UNMEASURED, "why": "stall_watch.json absent"},
        "acceptance": acc_props or {"status": UNMEASURED,
                                    "why": "acceptance_properties.json absent on this host"},
        "attention": [{k: o.get(k) for k in ("organ", "verdict", "verdict_why", "artifact")}
                      for o in worst[:60]],
        "organs": organs,
        "rule": ("UNMEASURED is a verdict and never GREEN. Report only: the control plane and "
                 "the clock fixer own repair; nothing here restarts, retires or vetoes."),
    }


def render_md(doc: dict[str, Any]) -> str:
    c = doc["counts"]
    lines = [f"# Health board ({doc['at']})", "",
             f"**Desk verdict: {doc['desk_verdict']}** -- {doc['desk_verdict_why']}", "",
             f"Organs: {doc['n_organs']} | GREEN {c['GREEN']} | AMBER {c['AMBER']} | "
             f"RED {c['RED']} | UNMEASURED {c['UNMEASURED']}", "",
             "Derived hourly by `desks/mt5/research/health_board.py`. Never edit by hand.", "",
             "## Sources", "", "| source | state | age h | why |", "|---|---|---|---|"]
    for k, s in doc["sources"].items():
        lines.append(f"| {k} | {s['state']} | {s['age_h']} | {s['why']} |")
    lines += ["", "## Box tasks", ""]
    bt = doc.get("box_tasks") or {}
    for a in bt.get("failing") or []:
        lines.append(f"- {a}")
    for a in bt.get("stale_claims") or []:
        lines.append(f"- (stale watchdog reading, not counted) {a}")
    if not bt.get("failing") and not bt.get("stale_claims"):
        lines.append(f"- {bt.get('why') or 'none failing'}")
    lines += ["", "## Acceptance properties", ""]
    acc = doc.get("acceptance") or {}
    if "status" in acc and isinstance(acc.get("status"), str):
        lines.append(f"- UNMEASURED: {acc.get('why')}")
    else:
        for k, v in acc.items():
            lines.append(f"- {k}: {v.get('status')} ({'measured' if v.get('measured') else 'UNMEASURED'})")
    lines += ["", "## Needs attention (RED first)", "", "| organ | verdict | why |", "|---|---|---|"]
    for o in doc.get("attention") or []:
        lines.append(f"| {o['organ']} | {o['verdict']} | {str(o['verdict_why'])[:160]} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=60.0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    tmp.replace(a.out)
    (OUT_MD if a.out == OUT else a.out.with_suffix(".md")).write_text(render_md(doc), "utf-8")
    c = doc["counts"]
    print(f"health_board: {doc['desk_verdict']} organs={doc['n_organs']} GREEN {c['GREEN']} "
          f"AMBER {c['AMBER']} RED {c['RED']} UNMEASURED {c['UNMEASURED']} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

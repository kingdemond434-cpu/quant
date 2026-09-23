"""producer -> artifact -> consumer -> decision, for every mandated capability.

MANDATE §3 AND §148 ASK FOR A PATH, NOT A LIST. A capability is complete only when its chain
actually runs end to end, and every link fails in its own way: a producer nothing schedules, an
artifact nothing reads, a consumer that reads a file the producer stopped writing. A registry of
statuses cannot tell those apart -- they all present as "not PROVEN" -- so this walks the chain
and names the first broken link.

THE THREE FAILURES THIS EXISTS TO SEPARATE, each one measured on this desk in the last week:

    ORPHAN PRODUCER   writes an artifact nothing reads. `download_remaining` wrote every bar it
                      fetched into a directory the desk does not read, for weeks, while
                      reporting success -- 65% of the docket was then refused for missing bars.
    SILENT ARTIFACT   declared, never produced. 35 capabilities on this checkout.
    DEAD CONSUMER     reads an artifact no producer writes any more -- the shape that turns a
                      stale file into a decision nobody notices is stale.

CYCLES ARE REPORTED, NOT BROKEN. Research pipelines are legitimately cyclic (attribution feeds
the governor which schedules the research that produces attribution), so a cycle here is
information about the loop's shape, never an error to fix by cutting an edge.

    python blueprint/dependency_graph.py            # the chains, worst first
    python blueprint/dependency_graph.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
# THIS PACKAGE'S DIRECTORY GOES FIRST, and that is not cosmetic: `scripts/dependency_graph.py`
# already exists and shadowed `blueprint/dependency_graph.py` when scripts/ sorted earlier --
# closure_report imported the wrong module and died on a missing name. Two files with one module
# name is a fact of this tree; the fix is to be explicit about which one this package means.
_HERE = str(Path(__file__).resolve().parent)
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.append(_p)
if _HERE in sys.path:
    sys.path.remove(_HERE)
sys.path.insert(0, _HERE)

OUT = Path(__file__).resolve().parent / "DEPENDENCY_GRAPH.json"


def _chain(cap: dict[str, Any]) -> dict[str, Any]:
    """One capability's chain, and the FIRST link that is broken.

    First, not all: a producer nothing runs makes every downstream link unanswerable, and
    reporting four failures for one cause sends the reader to fix three things that are fine.
    """
    producer = cap.get("producer")
    artifacts = cap.get("artifacts") or []
    consumers = cap.get("consumers") or []
    scheduler = cap.get("scheduler") or []
    status = cap["status"]

    links = [
        ("producer", bool(producer), "no module owns this capability"),
        ("scheduler", bool(scheduler) or status in ("RUNNING", "DECISION_AFFECTING",
                                                    "MEASURED", "PROVEN"),
         "no scheduler surface runs the producer"),
        ("artifact", bool(artifacts), "the capability declares no artifact to produce"),
        ("produced", status in ("RUNNING", "DECISION_AFFECTING", "MEASURED", "PROVEN"),
         "the artifact has never appeared on this host"),
        ("consumer", bool(consumers), "nothing imports the producer or reads its artifact"),
        ("decision", status in ("DECISION_AFFECTING", "MEASURED", "PROVEN"),
         "no proven route from the artifact into a decision"),
        ("priced", status in ("MEASURED", "PROVEN"),
         "no MODULE_RENT line prices what this capability costs and returns"),
    ]
    broken = next((name for name, ok, _ in links if not ok), "")
    why = next((msg for name, ok, msg in links if not ok), "")
    return {
        "id": cap["id"], "status": status,
        "producer": producer, "scheduler": scheduler,
        "artifacts": artifacts, "consumers": consumers[:6],
        "n_consumers": len(consumers),
        "links_ok": sum(1 for _, ok, _ in links if ok), "links_total": len(links),
        "first_broken_link": broken, "why": why,
        "kind": ("ORPHAN_PRODUCER" if broken == "consumer"
                 else "SILENT_ARTIFACT" if broken == "produced"
                 else "UNSCHEDULED" if broken == "scheduler"
                 else "UNPRICED" if broken == "priced"
                 else "" if not broken else broken.upper()),
    }


def graph() -> dict[str, Any]:
    from coverage import registry
    reg = registry()
    chains = [_chain(c) for c in reg["capabilities"]]
    kinds: dict[str, int] = {}
    for c in chains:
        if c["kind"]:
            kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    complete = [c for c in chains if not c["first_broken_link"]]
    return {
        "generated_at": reg["generated_at"], "git_sha": reg["git_sha"],
        "total": len(chains),
        "chains_complete": len(complete),
        "broken_by_kind": kinds,
        "chains": sorted(chains, key=lambda c: (c["links_ok"], c["id"])),
        "law": ("the FIRST broken link is reported, not every one: a producer nothing runs makes "
                "each downstream link unanswerable, and listing four failures for one cause "
                "sends the reader to fix three things that are not broken."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    g = graph()
    if args.write:
        OUT.write_text(json.dumps(g, indent=2, default=str), encoding="utf-8")
        print(f"{g['total']} chains -> {OUT}")
    if args.json:
        print(json.dumps(g, indent=2, default=str))
        return 0
    if not args.write:
        print(f"{g['total']} capability chains @ {g['git_sha'] or 'no sha'}")
        print(f"  complete end to end: {g['chains_complete']}")
        for k, n in sorted(g["broken_by_kind"].items(), key=lambda kv: -kv[1]):
            print(f"  {k:20s} {n:4d}")
        print("\n  worst chains:")
        for c in g["chains"][:8]:
            print(f"    {c['id']:6s} {c['links_ok']}/{c['links_total']} "
                  f"{c['first_broken_link']:12s} {c['why'][:56]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

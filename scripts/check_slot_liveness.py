#!/usr/bin/env python3
"""ARE THE 12 FORWARD SLOTS DOING ANY WORK? -- and if not, exactly why not.

THE MEASUREMENT THAT PROMPTED THIS, 2026-08-12: twelve of twelve forward slots occupied, ZERO
accruing, every roster sleeve reading NO-EVIDENCE at 6.8 days against a 36h staleness threshold --
and the paper-sleeve spawner holding TWENTY-SIX queued Stage-A survivors behind them. The desk's
only path from research to capital was fully subscribed by clocks producing nothing.

Nothing was broken in a way anything could see. `run_paper_sleeve_forward` reported the symptom
faithfully on every run ("no rows added since the baseline -- the source artifact has not been
regenerated"), and that sentence is TRUE of four completely different situations, exactly one of
which is a defect anyone can fix:

    PRODUCER_UNSCHEDULED  no cron or systemd line regenerates the origin artifact. The clock is
                          born dead. Found one: liquidation_reversion_BTCUSDT, whose inputs are
                          recorded continuously by quant-liquidations.service while the screen
                          that turns them into rows was wired to nothing. Repaired with one cron
                          line rather than by retiring a real candidate.
    SOURCE_STALE_HERE     the producer IS scheduled; this box has not run it. On an ephemeral
                          container this is the NORMAL state and describes the container, not the
                          desk. Nine of ten clocks here. Scoring these as dead is how a container
                          session concludes the desk has collapsed.
    SOURCE_FROZEN         producer scheduled, ran recently, `n` still not moving. The screen's
                          window is fixed rather than expanding, so the clock cannot resolve no
                          matter how long it waits.
    ACCRUING              nothing to do.

THIS ORGAN FREES NO SLOT AND RETIRES NOTHING, deliberately. `slot_registry` is explicit that a
dormant clock stays counted until an explicit ledgered decision retires it, because retirement
SHRINKS the Holm m and LOOSENS every standing clock's bar -- "over-counting only tightens the bar
(the safe error), under-counting admits noise as edge". An organ that automatically cleared dead
clocks to drain a queue would be an organ that automatically loosens statistical gates whenever
the desk is impatient, and with 26 candidates waiting that pressure is permanent. The decision was
never the hard part. Nothing TRIGGERED it.

    python scripts/check_slot_liveness.py [--json] [--page]

EXIT 0 always: a blocked slot is a finding for a person, not a reason to fail a scheduler run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.slot_liveness import report  # noqa: E402

OUT = "data/slot_liveness.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--page", action="store_true",
                    help="send a real page when a slot is blocked by a clock that cannot accrue")
    args = ap.parse_args(argv)

    rep = report(root=_ROOT)
    (_ROOT / OUT).parent.mkdir(parents=True, exist_ok=True)
    (_ROOT / OUT).write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"slot liveness: {rep['accruing']}/{rep['n_clocks']} accruing, "
              f"{rep['slots_blocked_by_a_clock_that_cannot_accrue']} slot(s) held by a clock that "
              "cannot accrue")
        for state, names in rep["by_state"].items():
            print(f"  {state}: {len(names)}")
        for fix in rep["repairable_by_scheduling_a_producer"]:
            print(f"  REPAIRABLE  {fix['clock']}")
            print(f"              {fix['repair']}")

    blocked = rep["slots_blocked_by_a_clock_that_cannot_accrue"]
    if args.page and blocked:
        # A BLOCKED SLOT IS NOT AN OUTAGE, so this pages rather than fails. The cost is invisible
        # and compounding -- a queued survivor loses forward days it can never get back -- which is
        # exactly the class that needs a human told, not a red exit code nobody reads.
        try:
            from libs.ops.alert_channels import send_all
            fixes = rep["repairable_by_scheduling_a_producer"]
            body = [f"{blocked} of {rep['n_clocks']} forward slots are held by a clock that "
                    "CANNOT accrue. Every one of them is paying full multiplicity and returning "
                    "no evidence, while Stage-A survivors queue behind the cap.", ""]
            for c in rep["clocks"]:
                if c["state"] in ("PRODUCER_UNSCHEDULED", "SOURCE_FROZEN"):
                    body += [f"{c['state']}  {c['name']}", f"  {c['why']}", f"  FIX: {c['repair']}",
                             ""]
            if fixes:
                body.append("At least one is repairable by scheduling a producer -- that costs a "
                            "cron line and retires nothing.")
            body.append("NOTE: retiring a clock shrinks the Holm m and LOOSENS every standing "
                        "bar. That stays a ledgered decision with an owner.")
            send_all("forward slots blocked by clocks that cannot accrue", "\n".join(body))
        except (OSError, ValueError, ImportError) as exc:
            print(f"  PAGE FAILED ({type(exc).__name__}: {exc}) -- the finding stands, "
                  f"see {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""WHEN A CLOCK CLEARS ITS BAR, SOMETHING MUST HAPPEN -- and nothing did.

THE MISSING LINK, and it is the last one in the chain. `run_paper_sleeve_forward` computes, per
sleeve, the forward IC, the rows added, the Holm bar it must clear (`forward_bar_z`) and how many
rows that needs (`n_needed_for_forward_rejection`). It then writes all of it to a file and stops.
A 2026-08-12 grep for anything that CONSUMES a cleared bar found: `publish_pipeline`, which counts
resolved sleeves for the dashboard, and nothing else.

So the desk could run a clock for ninety days, watch it clear the bar it was pre-registered
against, and NOTHING WOULD HAPPEN. The sleeve would keep accruing, the slot would stay occupied,
the queue behind it would keep waiting, and the survivor -- the single thing this entire pipeline
exists to produce -- would sit in a JSON file until a person noticed. Same class as the promotion
gate having no actuator, one stage earlier, and worse: the gate at least published a verdict.
Here no verdict was ever formed.

WHAT THIS DOES. Every cycle, for every standing clock: form the forward t-statistic from the
evidence accrued SINCE the clock started, compare it to the cohort's Holm bar, and emit ONE of

    SURVIVED    the pre-registered forward test rejected the null at the cohort bar. This is the
                desk's product. Stamped, ledgered, and handed to the promotion path immediately.
    REFUTED     enough evidence to settle it, and the effect is not there. Also a product -- a
                POWERED negative is knowledge, and it releases the slot.
    ACCRUING    still collecting; carries the fraction of the way there.
    UNDERPOWERED  the source cannot supply the rows this bar needs within the runway.

HOLM IS STEP-DOWN, AND THE DESK WAS RUNNING BONFERRONI. `run_axis_shadows` calls
`holm_bar(m, rank=1)` for every clock -- the rank-1 bar, alpha/m, applied to all of them. That is
Bonferroni, which Holm strictly dominates at the SAME family-wise error rate: order the statistics,
test the strongest at alpha/m, and if it rejects, test the next at alpha/(m-1), and so on until one
fails. Applying the strictest bar to every clock is not extra safety, it is discarded power, and it
is the only place in this pipeline where more throughput is available without touching alpha.

Being precise about what that is worth: it changes NOTHING until a first clock passes, because the
strongest is judged at alpha/m either way. It is not a shortcut to a survivor. It means the SECOND
real effect is not held to a bar built for the possibility that it was the only one.

WHAT IT CANNOT DO. It does not set alpha, does not choose the bar, does not decide the cohort size,
and cannot promote anything to capital -- it hands a SURVIVED verdict to the promotion gate, which
still applies every criterion it applies today. A survivor is the start of the live ladder, never
a bypass of it.

    python scripts/run_forward_resolution.py [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.forward_multiplicity import effective_m  # noqa: E402
from libs.validation.forward_stats import holm_bar  # noqa: E402

FORWARD = "web/paper_sleeve_forward.json"
FORWARD_ALT = "data/paper_sleeve_forward.json"
OUT = "data/forward_resolution.json"
LEDGER = "data/survivors.jsonl"

#: Below this many forward rows nothing is resolved either way, whatever the t-statistic says.
#: A |t| computed on a handful of rows is a coin flip wearing a decimal point, and the direction
#: that matters is the false POSITIVE -- one lucky week must never be able to mint a survivor.
MIN_FORWARD_ROWS = 30.0


def _load(root: Path) -> tuple[dict[str, Any], str]:
    for rel in (FORWARD, FORWARD_ALT):
        try:
            return json.loads((root / rel).read_text("utf-8")), rel
        except (OSError, ValueError):
            continue
    return {}, ""


def _t_stat(ic: float, n: float) -> float:
    """Forward t for a correlation-like statistic over n effective observations."""
    a = abs(float(ic))
    if not math.isfinite(a) or a <= 0.0 or n <= 1.0:
        return 0.0
    return a * math.sqrt(n)


def resolve(root: Path | None = None) -> dict[str, Any]:
    base = root or _ROOT
    now = datetime.now(tz=UTC)
    doc_fwd, src = _load(base)
    sleeves = doc_fwd.get("sleeves") or {}
    mult = effective_m(root=base)

    rows: list[dict[str, Any]] = []
    for name, s in sorted(sleeves.items()):
        added = float(s.get("rows_added") or 0.0)
        ic_f = s.get("ic_forward_estimate")
        row: dict[str, Any] = {
            "name": name, "rows_added": added, "ic_forward": ic_f,
            "n_needed": s.get("n_needed_for_forward_rejection"),
            "progress": s.get("progress_to_resolution"),
            "evidence": s.get("evidence"),
        }
        if not isinstance(ic_f, (int, float)) or added < MIN_FORWARD_ROWS:
            row.update(verdict="ACCRUING", t=None,
                       why=(f"{added:.0f} forward row(s) of the {MIN_FORWARD_ROWS:.0f} minimum. "
                            "A t computed on a handful of rows is a coin flip with a decimal "
                            "point, and the error that matters here mints a false survivor."))
            rows.append(row)
            continue
        row["t"] = round(_t_stat(float(ic_f), added), 4)
        rows.append(row)

    # HOLM STEP-DOWN, applied across the cohort in one pass. Order by the statistic, test the
    # strongest at alpha/m, and only descend while each rejects. The moment one fails, every
    # weaker clock stays unresolved -- that STOPPING RULE is what preserves the family-wise error
    # rate, and dropping it would turn step-down into a licence rather than a procedure.
    testable = sorted((r for r in rows if r.get("t") is not None),
                      key=lambda r: -float(r["t"]))
    m = max(1, mult.m)
    still_descending = True
    for i, r in enumerate(testable):
        rank = i + 1
        bar = float(holm_bar(m, rank))
        r["holm_rank"] = rank
        r["bar_z"] = bar
        if not still_descending:
            r["verdict"] = "ACCRUING"
            r["why"] = (f"a stronger clock at rank {rank - 1} did not clear its own bar, so Holm's "
                        "step-down stops here. Testing on past a failure is what would break the "
                        "family-wise error rate the whole cohort is corrected for.")
            continue
        if float(r["t"]) >= bar:
            r["verdict"] = "SURVIVED"
            r["why"] = (f"forward t={r['t']} clears the rank-{rank} Holm bar {bar} at m={m} on "
                        f"{r['rows_added']:.0f} out-of-sample rows. PRE-REGISTERED and cleared -- "
                        "this is Stage B, the sole promotion authority.")
        else:
            still_descending = False
            n_needed = r.get("n_needed")
            reachable = (isinstance(n_needed, (int, float))
                         and n_needed < 10 * max(r["rows_added"], 1.0))
            r["verdict"] = "ACCRUING" if reachable else "UNDERPOWERED"
            r["why"] = (f"forward t={r['t']} against a rank-{rank} bar of {bar} at m={m}."
                        + ("" if reachable else
                           f" The source would need ~{n_needed} rows to settle this, which is "
                           "more than an order of magnitude beyond what it has supplied -- "
                           "UNDERPOWERED is not a refutation, and it must never be read as one."))

    survivors = [r for r in rows if r.get("verdict") == "SURVIVED"]
    if survivors:
        # LEDGERED THE MOMENT IT HAPPENS. The desk has never produced one; the first must not
        # depend on anybody noticing a JSON field change.
        try:
            with (base / LEDGER).open("a", encoding="utf-8") as fh:
                for r in survivors:
                    fh.write(json.dumps({**r, "resolved_utc": now.isoformat(timespec="seconds"),
                                         "m_effective": m}) + "\n")
        except OSError:
            pass

    doc = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "source": src or "ABSENT",
        "m_effective": m, "m_why": mult.why,
        "n_clocks": len(rows), "n_survived": len(survivors),
        "by_verdict": {v: sum(1 for r in rows if r.get("verdict") == v)
                       for v in sorted({str(r.get("verdict")) for r in rows})},
        "clocks": rows,
        "law": "Stage B is the SOLE promotion authority. A SURVIVED verdict starts the live "
               "ladder; it does not bypass it -- the promotion gate still applies every criterion "
               "it applies today.",
        "procedure": "HOLM STEP-DOWN. The strongest clock is tested at alpha/m, the next at "
                     "alpha/(m-1), and the descent STOPS at the first failure. Applying the "
                     "rank-1 bar to every clock -- which is what run_axis_shadows does -- is "
                     "Bonferroni, which Holm dominates at the same family-wise error rate. It "
                     "changes nothing until a first clock passes; it means the SECOND real effect "
                     "is not held to a bar built for the possibility it was the only one.",
        "unresolved_is_not_refuted": "UNDERPOWERED means the source cannot supply the rows this "
                                     "bar needs. It is not evidence of absence (L1.49) and it "
                                     "must never be recorded as a negative result.",
    }
    if not survivors:
        doc["status"] = "NO-SURVIVOR"
        doc["why"] = ("no standing clock has cleared its pre-registered forward bar. This is the "
                      "desk's honest state, not a failure of this organ.")
    else:
        doc["status"] = "SURVIVOR"
        doc["why"] = (f"{len(survivors)} clock(s) cleared the forward bar. Handed to the promotion "
                      "gate in this same cycle.")
    p = base / OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), "utf-8")

    if survivors:
        try:
            from libs.ops.alert_channels import send_all
            send_all(f"SURVIVOR: {len(survivors)} forward clock(s) cleared the bar",
                     "\n".join(f"{r['name']}\n  t={r['t']} vs rank-{r['holm_rank']} bar "
                               f"{r['bar_z']} at m={m} on {r['rows_added']:.0f} forward rows"
                               for r in survivors)
                     + "\n\nThis is Stage B, the sole promotion authority. The live ladder starts "
                       "now and the promotion gate still applies every criterion it applies "
                       "today -- a survivor begins the ladder, it does not bypass it.")
        except (OSError, ValueError, ImportError):
            pass
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    doc = resolve()
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(f"forward resolution: {doc['status']} -- {doc['n_survived']}/{doc['n_clocks']} "
              f"survived at m={doc['m_effective']}")
        for v, n in doc["by_verdict"].items():
            print(f"  {v}: {n}")
        for r in doc["clocks"]:
            if r.get("verdict") == "SURVIVED":
                print(f"  SURVIVED {r['name']}  t={r['t']} >= {r['bar_z']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

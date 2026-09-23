"""Independent reproduction: re-run a certificate's gates COLD and compare to the record.

WHY THIS EXISTS, IN THIS DESK'S OWN EVIDENCE. The dominant defect here is not a wrong answer, it
is a PLAUSIBLE one: code that runs, exits 0, returns a number, and means nothing. Measured
2026-09-03 alone -- the authority ratchet's revocation test scanned only the first 20,000
characters of the artifact it guarded; the precommit guard re-implemented that same truncation;
the research-health fence made it a third time; the seat meter counted completed no-ops as
crashes; a frontier rule read a numerator that made it unfireable; a healer's backfill sat behind
an early return; that healer's family lookup could not see the desk's most numerous family; a lock
read was eaten by cmd.exe quoting. Eight instances in one day. Every one passed lint, types and
its own exit code. The only thing that ever caught them was re-deriving the number independently.

A certificate is the most expensive artifact this desk produces and the least re-derived. It is
minted once, inside a sweep of thousands, by code that has changed since -- and nothing ever asks
it the same question twice.

WHAT "INDEPENDENT" MEANS HERE, AND WHAT IT DOES NOT. It means a SEPARATE PROCESS, started cold,
told only which cell to judge, that never reads the recorded verdict until it has produced its
own. It does NOT mean a second implementation of the gates: the reproducer runs
`external_gauntlet.py --only <cell>`, the same canonical validator, because a second implementation
would prove only that two programs agree -- and "one canonical validator" exists precisely to stop
the desk owning two answers to one question. The independence is in the PROCESS and the ORDER, not
in the arithmetic.

WHAT A DISAGREEMENT MEANS. Not automatically that the certificate is wrong. Costs are corrected,
bars arrive, universes change -- a drifted metric can be honest. What it means is that the
certificate can no longer be re-derived from what the desk holds today, and a claim that cannot
be re-derived is not evidence the desk may cash (L1.49). The verdict is reported, never enforced:
this script writes no certificate and revokes nothing, which is the same firewall the gauntlet's
own `--only` mode is built on.

    python3 desks/mt5/scripts/reproduce_certificate.py --cert "<key>"        # one
    python3 desks/mt5/scripts/reproduce_certificate.py --sample 3            # random three
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
AUTHORITY = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
OUT = DESK / "reports" / "reproduction_verdicts.json"
GAUNTLET = DESK / "scripts" / "external_gauntlet.py"

#: Metrics compared between the record and the re-run. Chosen because each is a GATE INPUT --
#: a drift here changes a verdict, unlike a cosmetic count.
COMPARED = ("sharpe", "dsr", "sr0", "n_trials", "n", "exp_r")

#: Relative tolerance. Bars accrue and costs are re-derived every run, so bit-equality is the
#: wrong bar; an order-of-magnitude move is not.
TOLERANCE = 0.15


def cell_key_for(cert: dict) -> str | None:
    """The gauntlet docket key for this certificate, or None if it cannot be addressed.

    UNMEASURED IS A REAL ANSWER. A certificate whose cell cannot be named is not reproduced and
    is reported as such -- never quietly counted as agreeing.
    """
    spec = cert.get("shadow_spec") or {}
    sym = str(spec.get("symbol") or cert.get("sym") or "")
    fam = str(spec.get("family") or "")
    if not sym or not fam:
        return None
    return f"{sym}.{fam}."


def recorded_metrics(cert: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for gate in (cert.get("gates") or {}).values():
        if not isinstance(gate, dict):
            continue
        for k in COMPARED:
            if k in gate and isinstance(gate[k], (int, float)):
                out.setdefault(k, float(gate[k]))
    return out


def rerun(cell: str, report_to: Path) -> dict:
    """Run the canonical gauntlet cold on one cell. Never sees the recorded verdict."""
    proc = subprocess.run(
        [sys.executable, str(GAUNTLET), "--only", cell, "--report-to", str(report_to)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=3600, check=False)
    if not report_to.exists():
        return {"error": f"no report written (rc={proc.returncode})",
                "tail": (proc.stdout or proc.stderr or "")[-400:]}
    return json.loads(report_to.read_text("utf-8"))


def fresh_metrics(report: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    stack = [report.get("result")]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                if k in COMPARED and isinstance(v, (int, float)):
                    out.setdefault(k, float(v))
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(node, list):
            stack.extend(node)
    return out


def compare(rec: dict[str, float], got: dict[str, float]) -> tuple[str, list[str]]:
    """PASS / DRIFT / UNMEASURED, with the reason. Never silently 'fine'."""
    shared = [k for k in COMPARED if k in rec and k in got]
    if not shared:
        return "UNMEASURED", ["no comparable metric appeared in both the record and the re-run"]
    notes = []
    for k in shared:
        a, b = rec[k], got[k]
        scale = max(abs(a), abs(b), 1e-9)
        if abs(a - b) / scale > TOLERANCE:
            notes.append(f"{k}: recorded {a:.4g} vs reproduced {b:.4g}")
    return ("DRIFT" if notes else "PASS"), notes or [f"agreed on {', '.join(shared)}"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cert", default=None, help="certificate key to reproduce")
    ap.add_argument("--sample", type=int, default=0, help="reproduce N random certificates")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    doc = json.loads(AUTHORITY.read_text("utf-8"))
    certs = doc.get("survivors") or {}
    if args.cert:
        chosen = {args.cert: certs[args.cert]} if args.cert in certs else {}
        if not chosen:
            print(f"no certificate named {args.cert!r}")
            return 2
    elif args.sample:
        keys = random.sample(sorted(certs), min(args.sample, len(certs)))
        chosen = {k: certs[k] for k in keys}
    else:
        print("nothing to do: pass --cert or --sample")
        return 2

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    verdicts = {}
    for key, cert in chosen.items():
        cell = cell_key_for(cert)
        if cell is None:
            verdicts[key] = {"verdict": "UNMEASURED",
                             "why": ["certificate carries no addressable (symbol, family)"]}
            print(f"  UNMEASURED  {key[:60]}")
            continue
        tmp = DESK / "reports" / f"reproduction_{stamp}_{abs(hash(key)) % 10**8}.json"
        report = rerun(cell, tmp)
        if "error" in report:
            verdicts[key] = {"verdict": "UNMEASURED", "why": [report["error"]],
                             "tail": report.get("tail", "")}
            print(f"  UNMEASURED  {key[:60]}  {report['error']}")
            continue
        rec, got = recorded_metrics(cert), fresh_metrics(report)
        verdict, why = compare(rec, got)
        verdicts[key] = {"verdict": verdict, "why": why, "cell": cell,
                         "recorded": rec, "reproduced": got}
        print(f"  {verdict:11s} {key[:60]}  {why[0]}")

    payload = {
        "reproduced_at": datetime.now(UTC).isoformat(),
        "n": len(verdicts),
        "tolerance": TOLERANCE,
        "verdicts": verdicts,
        "note": ("Independent re-run of the CANONICAL gates in a cold process, compared to the "
                 "recorded certificate. Reports only: writes no certificate and revokes nothing."),
    }
    Path(args.out).write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    counts: dict[str, int] = {}
    for v in verdicts.values():
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    print(f"reproduction: {counts} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

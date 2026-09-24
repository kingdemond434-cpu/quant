"""Start a candidate's forward clock the day it is PROPOSED, not the day it is certified.

THE BOTTLENECK THIS REMOVES. Promotion needs n>=50 AND >=14 days of forward evidence. Today a
candidate serves that wait TWICE: once sitting in the docket waiting to be judged, then again
from zero after it certifies. Measured 2026-09-14: zero of 228 forward clocks qualified for
promotion and the median had taken no trades at all, while the docket held 22,965 candidates.
Running the two in parallel means a variant that certifies in nine days already has nine days
banked and needs five more, instead of starting over.

WHAT THIS IS NOT. It grants nothing. Every row is written with
`gate_admission: PRE_CERTIFICATION_SHADOW`, `promotion_authority: false` and
`order_authority: false`, into a SEPARATE ledger that `shadow_admission` does not read. A
pre-certification row cannot be promoted, cannot be sized, and cannot reach the gateway. It
records what a candidate WOULD have done and nothing else. The ten gates still decide.

THE SEPARATE LEDGER IS THE POINT, not tidiness. A forward number on an ungated cell looks exactly
like a forward number on a certified one, and this desk's recurring failure is precisely that --
a live organ and a dead one rendering identically, `live: 0` meaning "I could not read it", a
routing decision reported as thirteen lost candidates. Mixing these rows into `shadow_state.json`
would put an unjudged cell one join away from every consumer that trusts that file.

AND THE EVIDENCE MUST STILL BE OUT OF SAMPLE, which is the one thing that could make this
dishonest. The gauntlet judges on history up to its own data cutoff. If a clock's window overlaps
that history, its "forward" record is the same data the gate already saw -- the exact
contamination `forward_start` exists to prevent (RESEARCH 6d: a clock counted from the first trade
ever taken lets selection-era evidence pose as forward evidence). So every row carries
`forward_start` stamped at PROPOSAL, and `effective_forward_start` is the later of that and the
certificate's data cutoff once one exists. The promoter must count from the effective start. In
practice the two are days apart, so most of the speed-up survives and none of the honesty is
spent.

    python desks/mt5/research/precert_shadow.py            # report what it would enrol
    python desks/mt5/research/precert_shadow.py --apply    # enrol and evaluate
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"
SHADOW = BASE / "reports" / "shadow"
LEDGER = "precert_shadow_state.json"
OUT = BASE / "reports" / "PRECERT_SHADOW.json"

#: The admission string every row here carries. `pipeline/promote.py` branches on this field and
#: knows nothing about this value, so a pre-certification row is refused by construction rather
#: than by a check someone has to remember to write.
ADMISSION = "PRE_CERTIFICATION_SHADOW"

#: Producers whose candidates are worth a clock before they are judged.
#:
#: NOT THE WHOLE DOCKET. 22,965 candidates evaluated every pass is not a research lane, it is a
#: denial of service against the box that also runs the gateway. These are variants of mechanisms
#: that ALREADY hold certificates -- the families behind them return 105.6 survivors per 1,000
#: ruled cells against `discovered`'s 2.0 -- so they are the candidates most likely to certify,
#: which is exactly the set for which a pre-started clock pays off.
SEED_PRODUCERS = ("session_chart_equivalents.py",)

#: Rows to carry. Each one costs a bar fetch and a replay every pass, on the machine that trades.
MAX_ROWS = 400


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _docket_rows() -> list[dict[str, Any]]:
    d = _read(DOCKET, [])
    rows = d.get("survivors", []) if isinstance(d, dict) else d
    return [r for r in rows
            if isinstance(r, dict) and str(r.get("producer") or "") in SEED_PRODUCERS]


def build_rows() -> tuple[list[tuple[Any, ...]], list[dict[str, Any]]]:
    """(engine rows, provenance) for the candidates this lane should clock."""
    sys.path.insert(0, str(BASE))
    from research.shadow_forward import _runnable_side

    out: list[tuple[Any, ...]] = []
    prov: list[dict[str, Any]] = []
    for r in _docket_rows()[:MAX_ROWS]:
        sym = str(r.get("symbol") or "").upper()
        fam = str(r.get("family") or "")
        params = dict(r.get("params") or {})
        if not sym or not fam:
            continue
        try:
            side = _runnable_side({"symbol": sym, "family": fam, "params": params}, fam)
        except Exception:
            side = None
        if side is None:
            # A family whose side cannot be resolved is not clockable, and saying so beats
            # guessing LONG -- a wrong side produces a real-looking record of the wrong strategy.
            continue
        win = str(params.get("selector") or r.get("selector") or "asia")
        out.append((sym, win, params, fam, side, ADMISSION, (), False))
        prov.append({"symbol": sym, "family": fam, "params": params,
                     "parent_certificate": r.get("parent_certificate"),
                     "variant_of": r.get("variant_of")})
    return out, prov


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="evaluate the rows and write the pre-certification ledger")
    args = ap.parse_args(argv)

    rows, prov = build_rows()
    now = datetime.now(UTC).isoformat(timespec="seconds")
    doc = {
        "generated_utc": now,
        "authority": (f"{ADMISSION}: no promotion authority, no order authority, no capital. "
                      f"Ledger {LEDGER} is not read by shadow_admission."),
        "n_rows": len(rows),
        "ledger": LEDGER,
        "seed_producers": list(SEED_PRODUCERS),
        "max_rows": MAX_ROWS,
        "rule": ("forward_start is stamped at PROPOSAL; the promoter must count from "
                 "max(forward_start, certificate data cutoff) so the window is out of sample"),
        "rows": prov[:50],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"pre-certification shadow: {len(rows)} candidate(s) eligible for an early clock")
    if not args.apply:
        print("  report only; re-run with --apply to enrol and evaluate")
        return 0

    if not rows:
        print("  nothing to enrol")
        return 0
    sys.path.insert(0, str(BASE))
    from research.shadow_forward import main as forward_main
    forward_main(rows=rows, ledger=LEDGER)
    state = _read(SHADOW / LEDGER, {})
    clocked = sum(1 for v in state.values() if isinstance(v, dict) and "n" in v)
    print(f"  {clocked} pre-certification clock(s) in {LEDGER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

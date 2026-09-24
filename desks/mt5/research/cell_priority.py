"""WHICH CELL THE JUDGE REACHES FIRST. This module ORDERS; it never rejects.

THE ARITHMETIC THAT MAKES ORDER THE BINDING DECISION
----------------------------------------------------
The judge can evaluate on the order of 36,000 cells a day against a docket of a quarter of a
million, with a never-judged frontier of 265,120 behind it. At that ratio the docket does not get
tested this week -- a SLICE of it does -- and which slice is decided by order alone. Every cell
stays in the queue; ordering chooses what goes FIRST, never what goes at all.

That distinction is not a nicety. An ordering that dropped a cell would be a SECOND JUDGE, and the
ten gates in `desks/mt5/policy/gate_spec.yaml` are the only thing on this desk that may certify or
refuse. `order()` therefore returns a PERMUTATION of its input, and `test_cell_priority.py` pins
exactly that: same length, same multiset of cell identities, for every input including the ones
this module scores worst. A cell this module ranks last is still judged; it is judged later.

WHAT "MOST LIKELY TO PASS" IS MEASURED FROM, RATHER THAN GUESSED
----------------------------------------------------------------
Three artifacts the desk already writes, read as counts and never as opinions:

  * `data/hypotheses/gate_verdict_ledger.jsonl` -- every verdict this desk has recorded, with the
    cell, its family and whether it passed. The DENOMINATOR: how many cells of this shape have
    been judged at all.
  * `reports/POWER_CURE_CANDIDATES.json` -- cells that cleared all five VALIDITY gates and missed
    only on POWER gates. Under `gate_spec.yaml` those five power gates carry
    `cure_by_forward: true`, so such a cell is on the desk's SECOND route to a certificate: real
    forward evidence, 50 trades and 14 days of it. This is the numerator that matters most right
    now, because the last exact ten-gate run tested 3,110 cells and passed zero.
  * `reports/UNIVERSAL_SURVIVORS.json` -- the 10/10 passes. The numerator that matters most in
    principle, and is near-zero in practice; it is weighted highest and contributes almost
    nothing, which is the honest reading of the evidence rather than a thumb on the scale.

Rates are smoothed toward the HOUSE rate (Laplace, `PRIOR_STRENGTH` pseudo-counts), so a family
with four judged cells is neither crowned by one lucky hit nor buried by one miss. A family with
NO measurement gets the house rate -- not zero. UNMEASURED is a real answer (L1.28a) and the
anti-timid reading of it is "unknown ground, go and look", never "assume barren".

AMONG NEAR-TIES, THE CELL THAT COVERS GROUND NOTHING ELSE COVERS
-----------------------------------------------------------------
`novelty()` reads how much of the docket's judged history already sits on this cell's family, its
chart and its symbol, and prefers the thinnest. Its weight is deliberately an order of magnitude
below the pass terms (`W_NOVELTY` against `W_CURE`), so it decides between cells whose measured
prospects are close and never overrules a cell that is measurably more likely to certify. That is
what "among near-ties" means arithmetically.

WHAT THIS MODULE IS NOT
-----------------------
It sets no threshold, moves no bar, reads no gate result into a decision and writes nothing the
judge reads. It is consumed by `scripts/warm_gauntlet_cache.py`, which decides which cells are
CHEAP for the next sweep -- an uncached cell costs the sweep ~22s of its build budget and a cached
one costs it nothing, so warmth is the real lever on which cells a bounded sweep reaches.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
DESK = BASE / "desks" / "mt5"
HYP = DESK / "data" / "hypotheses"
REPORTS = DESK / "reports"

#: Pseudo-counts pulling a thin family's rate toward the house rate. 25 means a family needs
#: ~25 judged cells before its own record outweighs the desk's average, which is the point at
#: which one hit stops being noise.
PRIOR_STRENGTH = float(os.environ.get("CELL_PRIORITY_PRIOR_STRENGTH", "25"))

#: A ten-gate pass is the product; a forward-cure candidate is a route to one that still owes 14
#: days and 50 trades of genuine out-of-sample evidence. Both are real, and they are not equal.
W_PASS = float(os.environ.get("CELL_PRIORITY_W_PASS", "1.0"))
W_CURE = float(os.environ.get("CELL_PRIORITY_W_CURE", "0.25"))
#: An order of magnitude below W_CURE so it breaks NEAR-ties and never overrules a measured edge.
W_NOVELTY = float(os.environ.get("CELL_PRIORITY_W_NOVELTY", "0.02"))

#: Ledger rows to read. The whole file is the honest answer; this bounds a pathological growth
#: case so the warmer's parent never stalls on it. Rows are read newest-last, so a cap keeps the
#: OLDEST rows -- deliberately, because the denominator is what the cap protects.
MAX_LEDGER_ROWS = int(os.environ.get("CELL_PRIORITY_MAX_LEDGER_ROWS", "2000000"))


def timeframe_from_cell(cell: str) -> str:
    """The chart encoded in a cell id: `GBPJPY@M15.family.p=...` -> `M15`, bare sym -> `H1`.

    This reads an identity the gauntlet already MINTED; it does not re-derive one from params.
    Two builders for one identity is the defect this desk has been bitten by repeatedly, so the
    only other producer of a timeframe here is `external_gauntlet.timeframe_of`, and the caller
    supplies that one for live specs (see `warm_gauntlet_cache`).
    """
    head = str(cell or "").split(".", 1)[0]
    return head.split("@", 1)[1].upper() if "@" in head else "H1"


def family_from_cell(cell: str) -> str:
    """The family segment of a cell id, or "" when the id does not carry one."""
    parts = str(cell or "").split(".")
    return parts[1] if len(parts) >= 2 else ""


def symbol_from_cell(cell: str) -> str:
    head = str(cell or "").split(".", 1)[0]
    return head.split("@", 1)[0]


@dataclass
class Priors:
    """Measured counts, and the rates derived from them. Every field is a count or a ratio of
    counts from an artifact on disk; nothing here is asserted."""

    judged: dict[tuple[str, str], int] = field(default_factory=dict)
    cured: dict[tuple[str, str], int] = field(default_factory=dict)
    passed: dict[tuple[str, str], int] = field(default_factory=dict)
    judged_family: dict[str, int] = field(default_factory=dict)
    judged_tf: dict[str, int] = field(default_factory=dict)
    judged_symbol: dict[str, int] = field(default_factory=dict)
    n_judged: int = 0
    n_cured: int = 0
    n_passed: int = 0
    sources: dict[str, object] = field(default_factory=dict)

    @property
    def house_cure(self) -> float:
        return (self.n_cured / self.n_judged) if self.n_judged else 0.0

    @property
    def house_pass(self) -> float:
        return (self.n_passed / self.n_judged) if self.n_judged else 0.0

    def rate(self, table: dict[tuple[str, str], int], key: tuple[str, str],
             house: float) -> float:
        """A Laplace-smoothed rate. An unmeasured key returns the house rate exactly, which is
        the only honest answer for ground the desk has never judged."""
        n = self.judged.get(key, 0)
        c = table.get(key, 0)
        return (c + PRIOR_STRENGTH * house) / (n + PRIOR_STRENGTH)

    def novelty(self, family: str, tf: str, sym: str) -> float:
        """0..1, higher where the desk's judged history is THINNEST on this cell's ground.

        Three axes, averaged: family, chart and symbol. A cell on a family nobody has judged, at a
        chart nobody has judged, on a symbol nobody has judged scores 1.0; a cell in the most
        crowded corner of all three scores near 0. Counts, not opinions.
        """
        def thin(table: dict[str, int], key: str) -> float:
            n = float(table.get(key, 0))
            worst = float(max(table.values())) if table else 0.0
            if worst <= 0:
                return 1.0
            return 1.0 - min(1.0, n / worst)

        return (thin(self.judged_family, family)
                + thin(self.judged_tf, tf)
                + thin(self.judged_symbol, sym)) / 3.0


def _read_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return None


def measure_priors(base: Path | None = None) -> Priors:
    """Read the three artifacts and count. A missing artifact leaves its numerator at zero and is
    NAMED in `sources`, so an absent input reads as UNMEASURED rather than as a verdict."""
    root = Path(base) if base is not None else BASE
    hyp = root / "desks" / "mt5" / "data" / "hypotheses"
    reports = root / "desks" / "mt5" / "reports"
    p = Priors()

    ledger = hyp / "gate_verdict_ledger.jsonl"
    rows = 0
    if ledger.exists():
        with ledger.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if rows >= MAX_LEDGER_ROWS:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                rows += 1
                cell = str(r.get("cell") or "")
                fam = str(r.get("family") or "") or family_from_cell(cell)
                tf = timeframe_from_cell(cell)
                sym = str(r.get("sym") or "") or symbol_from_cell(cell)
                p.judged[(fam, tf)] = p.judged.get((fam, tf), 0) + 1
                p.judged_family[fam] = p.judged_family.get(fam, 0) + 1
                p.judged_tf[tf] = p.judged_tf.get(tf, 0) + 1
                p.judged_symbol[sym] = p.judged_symbol.get(sym, 0) + 1
        p.sources["gate_verdict_ledger.jsonl"] = rows
    else:
        p.sources["gate_verdict_ledger.jsonl"] = "MISSING (UNMEASURED)"
    p.n_judged = rows

    cure = _read_json(reports / "POWER_CURE_CANDIDATES.json")
    if isinstance(cure, dict) and isinstance(cure.get("candidates"), dict):
        for row in cure["candidates"].values():
            if not isinstance(row, dict):
                continue
            cell = str(row.get("cell") or "")
            fam = str((row.get("shadow_spec") or {}).get("family") or "") or family_from_cell(cell)
            key = (fam, timeframe_from_cell(cell))
            p.cured[key] = p.cured.get(key, 0) + 1
            p.n_cured += 1
        p.sources["POWER_CURE_CANDIDATES.json"] = p.n_cured
    else:
        p.sources["POWER_CURE_CANDIDATES.json"] = "MISSING (UNMEASURED)"

    surv = _read_json(reports / "UNIVERSAL_SURVIVORS.json")
    if isinstance(surv, dict) and isinstance(surv.get("survivors"), dict):
        for name, row in surv["survivors"].items():
            cell = str((row or {}).get("cell") or name) if isinstance(row, dict) else str(name)
            fam = family_from_cell(cell)
            if isinstance(row, dict):
                fam = str((row.get("shadow_spec") or {}).get("family") or "") or fam
            key = (fam, timeframe_from_cell(cell))
            p.passed[key] = p.passed.get(key, 0) + 1
            p.n_passed += 1
        p.sources["UNIVERSAL_SURVIVORS.json"] = p.n_passed
    else:
        p.sources["UNIVERSAL_SURVIVORS.json"] = "MISSING (UNMEASURED)"
    return p


def score(spec: dict, priors: Priors) -> float:
    """This cell's measured prospect of reaching a certificate by EITHER route, plus a small
    novelty term that only separates near-ties. Higher goes first."""
    fam = str(spec.get("family") or "")
    tf = str(spec.get("tf") or "H1").upper()
    sym = str(spec.get("sym") or spec.get("symbol") or "")
    key = (fam, tf)
    p_pass = priors.rate(priors.passed, key, priors.house_pass)
    p_cure = priors.rate(priors.cured, key, priors.house_cure)
    return (W_PASS * p_pass
            + W_CURE * p_cure
            + W_NOVELTY * priors.novelty(fam, tf, sym))


def cell_key(spec: dict) -> str:
    """A stable identity for tie-breaking and for the permutation test. Not the gauntlet's
    `cell_id` -- this never leaves this module and never addresses a cache entry."""
    return (f"{spec.get('sym') or spec.get('symbol') or ''}@{str(spec.get('tf') or 'H1').upper()}"
            f".{spec.get('family') or ''}."
            f"{json.dumps(spec.get('params') or {}, sort_keys=True, default=str)}")


def order(specs: list[dict], priors: Priors) -> list[dict]:
    """Return the SAME cells, most-promising first. A PERMUTATION -- never a filter.

    Ties break on `cell_key` so the order is reproducible across passes and two runs of the
    warmer on the same docket agree about what comes first.
    """
    return sorted(specs, key=lambda sp: (-score(sp, priors), cell_key(sp)))


def publish(specs: list[dict], ordered: list[dict], priors: Priors,
            base: Path | None = None, extra: dict | None = None) -> Path:
    """Write the order and the counts behind it, so the ranking can be argued with."""
    root = Path(base) if base is not None else BASE
    out = root / "desks" / "mt5" / "reports" / "GAUNTLET_CELL_PRIORITY.json"
    top = [{"sym": sp.get("sym"), "family": sp.get("family"), "tf": sp.get("tf"),
            "score": round(score(sp, priors), 6)} for sp in ordered[:200]]
    doc = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "rule": ("ORDERS, NEVER REJECTS: the output is a permutation of the input. Rank is "
                 "W_PASS*P(ten-gate pass | family,chart) + W_CURE*P(validity-clear, i.e. on the "
                 "forward-cure route) + W_NOVELTY*(thinnest judged ground), all Laplace-smoothed "
                 "toward the house rate so an unmeasured family gets the house rate, never zero."),
        "weights": {"pass": W_PASS, "cure": W_CURE, "novelty": W_NOVELTY,
                    "prior_strength": PRIOR_STRENGTH},
        "n_in": len(specs), "n_out": len(ordered),
        "is_permutation": len(specs) == len(ordered),
        "measured_from": priors.sources,
        "house_rates": {"cure": round(priors.house_cure, 6),
                        "pass": round(priors.house_pass, 6)},
        "n_judged": priors.n_judged, "n_cure_eligible": priors.n_cured,
        "n_ten_gate_passes": priors.n_passed,
        "top_200": top,
    }
    if extra:
        doc.update(extra)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return out

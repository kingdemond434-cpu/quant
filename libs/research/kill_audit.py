"""KILL AUDIT — a validator's rejections are evidence requiring interpretation, not verdicts.

THE RUN THAT PRODUCED THIS. 2026-08-08, first complete sweep of the declared universe:

    898,560 evaluated · 687,215 measurable · 762 cleared screen
    FORMULA 9 | FAMILY 3 | INDEPENDENT MECHANISM 2 | PORTFOLIO-CONTRIBUTING unmeasured
    F3 WALK-FORWARD SIGN 750 · F6 LEAKAGE 18 · F5 SAMPLE FLOOR 3

**750 CELLS DYING AT ONE GATE IS ITSELF A MEASUREMENT, AND IT POINTS AT THE GATE AS READILY AS AT
THE CELLS.** Both readings are available and the desk cannot tell them apart from a counter. The
danger runs in both directions and they are not symmetric in how they fail:

    validator too harsh  -> real alpha destroyed at scale, SILENTLY, with every gate green
    validator too loose  -> false discoveries reach capital, loudly, and the rails catch them

The first has no alarm. That is why the audit exists, and why it may never become a route to
lowering a bar: this module classifies, it never promotes. A SOFT_KILL is still a kill.

NINE STATES, because "FAILED F3" is one label over at least nine different situations, each with a
different action and several with opposite ones::

    HARD_KILL            strong evidence the candidate is invalid
    SOFT_KILL            fails, but the evidence against it is weak
    INSUFFICIENT_EVIDENCE  cannot separate no-edge from no-power
    REGIME_CONDITIONAL   arms disagree in a way a conditional mechanism would produce
    DATA_LIMITED         history/resolution prevents judgement
    EXECUTION_LIMITED    gross edge exists; cost destroys it
    VALIDATOR_SUSPECT    the verdict flips under a reasonable perturbation
    LEAKAGE_CONFIRMED    the collapse under lag is decisive
    LEAKAGE_SUSPECT      the lag probe fired but is not conclusive

THE F3 RULE THIS AUDITS, read from the code rather than the docs: a cell dies unless BOTH arms are
positive. That is a strong requirement, and it is deliberately strong -- two negative arms "share a
sign" and would pass a naive sign test. But it also means a genuinely REGIME-CONDITIONAL mechanism
-- positive in one half, absent in the other -- is indistinguishable from noise at this gate, and
that is a false-negative class rather than a bug. Naming it is the whole contribution here.

NOTHING IN THIS MODULE RE-RUNS AN EXPERIMENT ON THE SAME DATA. Re-partitioning until a cell passes
is post-hoc selection wearing a lab coat; every classification is computed from statistics the
sweep already recorded, and every rescue is a PREREGISTERED experiment on evidence the selection
has not seen.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

__all__ = [
    "STATES",
    "KillRecord",
    "audit",
    "classify",
    "summarise",
]

STATES: tuple[str, ...] = (
    "HARD_KILL", "SOFT_KILL", "INSUFFICIENT_EVIDENCE", "REGIME_CONDITIONAL", "DATA_LIMITED",
    "EXECUTION_LIMITED", "VALIDATOR_SUSPECT", "LEAKAGE_CONFIRMED", "LEAKAGE_SUSPECT",
)

#: Observations below which an arm cannot support a sign claim. A walk-forward split halves the
#: sample twice over (arm x regime), so an arm can be far thinner than the headline `n` suggests.
THIN_ARM: int = 250

#: How close to zero an arm's net must be for its SIGN to be an artifact of noise rather than a
#: statement. Below this the F3 sign test is reading a coin flip, and the kill is not evidence.
SIGN_NOISE_BP: float = 0.05

#: Fraction of the surviving arm's magnitude the failing arm must reach before the split looks
#: like a CONDITIONAL mechanism rather than an absent one. Well above zero on purpose: a mechanism
#: that is merely absent in one arm is not evidence of a regime, it is evidence of nothing.
CONDITIONAL_FLOOR: float = 0.25


@dataclass(frozen=True)
class KillRecord:
    """One killed cell, from the sweep's retained statistics. `None` means UNMEASURED."""

    key: str
    kill: str
    t: float | None = None
    hurdle: float | None = None
    n: int | None = None
    net_bps: float | None = None
    gross_bps: float | None = None
    cost_bps: float | None = None
    is_net_bps: float | None = None
    oos_net_bps: float | None = None
    is_n: int | None = None
    oos_n: int | None = None
    leak_net_bps: float | None = None
    regime: str = ""
    horizon: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def gate(self) -> str:
        """The criterion prefix -- F3, F5, F6 -- without the live numbers in the message."""
        return self.kill.split(":", 1)[0].strip().split()[0] if self.kill else ""


def _thin(rec: KillRecord) -> bool:
    return any(x is not None and x < THIN_ARM for x in (rec.is_n, rec.oos_n))


def classify(rec: KillRecord) -> tuple[str, str]:
    """(state, why). ORDER OF CHECKS IS THE LOGIC AND IT RUNS FROM CHEAPEST-TO-DISPROVE UPWARD.

    Power is tested BEFORE validity, because a gate that fired on a thin arm has not shown the
    candidate is wrong -- it has shown the desk cannot tell. Ruling that HARD_KILL would convert
    an absence of evidence into a verdict, which is this desk's most-repeated defect aimed at the
    one place it is least visible.
    """
    gate = rec.gate

    if gate == "F5":
        return "INSUFFICIENT_EVIDENCE", (
            "a split arm was UNMEASURED. This is a SPAN problem and no harness change creates "
            "observations -- re-test when the tape is longer, and until then the cell is neither "
            "alive nor dead")

    if gate == "F6":
        if rec.leak_net_bps is None:
            return "LEAKAGE_SUSPECT", (
                "the lag probe could not be measured, so the collapse is UNVERIFIED. A leakage "
                "verdict on an unmeasured probe is an assertion")
        if rec.net_bps is not None and abs(rec.net_bps) < SIGN_NOISE_BP:
            return "VALIDATOR_SUSPECT", (
                f"net {rec.net_bps:+.4f}bp is inside the noise band, so 'collapses under lag' is "
                "a statement about a number that was never distinguishable from zero")
        if rec.net_bps is not None and rec.leak_net_bps * rec.net_bps < 0:
            return "LEAKAGE_CONFIRMED", (
                f"net {rec.net_bps:+.4f} -> {rec.leak_net_bps:+.4f}bp on ONE extra bar of lag: a "
                "sign flip from a single bar is a timing violation, not decay")
        return "LEAKAGE_SUSPECT", (
            f"net falls {rec.net_bps} -> {rec.leak_net_bps} without flipping sign. That is "
            "consistent with leakage AND with a genuinely short-lived contemporaneous effect; "
            "one-bar sensitivity alone does not establish that the information was unavailable at "
            "decision time. Reconstruct the timestamp chain before calling it leakage")

    if gate in {"F3", "F4"}:
        a, b = rec.is_net_bps, rec.oos_net_bps
        if a is None or b is None:
            return "INSUFFICIENT_EVIDENCE", ("an arm is unmeasured; the sign test had "
                                             "nothing to compare")
        if _thin(rec):
            return "INSUFFICIENT_EVIDENCE", (
                f"an arm holds fewer than {THIN_ARM} observations "
                f"(is={rec.is_n}, oos={rec.oos_n}). "
                "The gate fired on a sample too thin to establish a sign, which shows the desk "
                "cannot tell rather than that the cell is wrong")
        if abs(a) < SIGN_NOISE_BP or abs(b) < SIGN_NOISE_BP:
            return "VALIDATOR_SUSPECT", (
                f"an arm ({a:+.4f} / {b:+.4f} bp) sits inside the {SIGN_NOISE_BP}bp noise band, so "
                "the SIGN that decided this kill is a coin flip. The verdict would plausibly "
                "reverse on a different but equally reasonable split")
        if a > 0 and b > 0:
            return "SOFT_KILL", (
                f"both arms positive ({a:+.4f} / {b:+.4f}) -- this died on F4 MAGNITUDE, not on "
                "sign. The mechanism held out of sample and shrank, which is what an honest "
                "decaying-but-real edge looks like as well as what an overfit one does")
        if a * b < 0 and abs(min(a, b)) >= CONDITIONAL_FLOOR * abs(max(a, b)):
            return "REGIME_CONDITIONAL", (
                f"arms disagree with comparable magnitude ({a:+.4f} vs {b:+.4f}) -- the shape a "
                "CONDITIONAL mechanism produces, and one F3 cannot distinguish from noise because "
                "it requires both arms positive. The missing variable is the research object, not "
                "the cell")
        if (rec.gross_bps is not None and rec.net_bps is not None
                and rec.gross_bps > 0 >= rec.net_bps):
            return "EXECUTION_LIMITED", (
                f"gross {rec.gross_bps:+.4f}bp survives and net {rec.net_bps:+.4f}bp does not: the "
                "round trip eats the edge. Attack cost and holding period before the expression")
        return "HARD_KILL", (
            f"arms disagree decisively ({a:+.4f} vs {b:+.4f}) on adequate samples with both "
            "magnitudes outside the noise band -- the cell does not hold out of sample")

    return "SOFT_KILL", (
        f"unrecognised gate {gate!r}: classified conservatively as a weak kill rather than "
        "guessed at. An unknown criterion is a gap in THIS module, not evidence about the cell")


def audit(records: list[KillRecord]) -> list[dict[str, object]]:
    """Classify every kill and rank so the states that indicate a VALIDATOR problem lead."""
    order = {s: i for i, s in enumerate((
        "VALIDATOR_SUSPECT", "REGIME_CONDITIONAL", "EXECUTION_LIMITED", "INSUFFICIENT_EVIDENCE",
        "LEAKAGE_SUSPECT", "SOFT_KILL", "DATA_LIMITED", "LEAKAGE_CONFIRMED", "HARD_KILL"))}
    rows: list[dict[str, object]] = []
    for r in records:
        state, why = classify(r)
        rows.append({"key": r.key, "gate": r.gate, "state": state, "why": why,
                     "t": r.t, "net_bps": r.net_bps, "is_net_bps": r.is_net_bps,
                     "oos_net_bps": r.oos_net_bps, "is_n": r.is_n, "oos_n": r.oos_n,
                     "regime": r.regime, "horizon": r.horizon})
    rows.sort(key=lambda d: order.get(str(d["state"]), 99))
    return rows


def summarise(records: list[KillRecord]) -> dict[str, object]:
    """THE HEADLINE IS THE FALSE-KILL EXPOSURE, not the kill count.

    `false_kill_exposure` is the share of kills that are NOT hard: verdicts the desk should not
    treat as settled. It is an upper bound on how much real alpha the gate may be destroying and
    deliberately NOT an estimate of how much it is -- calling it an estimate would invite the
    number to be used as a reason to lower a bar, which is the one thing this module must never
    become.
    """
    if not records:
        return {"kills": 0, "headline": (
            "no killed cells retained -- the sweep reported counts only, so its rejections are "
            "UNAUDITABLE. A validator whose kills cannot be examined is unfalsifiable"),
            "tally": {}, "false_kill_exposure": None, "rows": []}
    rows = audit(records)
    tally = Counter(str(r["state"]) for r in rows)
    hard = tally["HARD_KILL"] + tally["LEAKAGE_CONFIRMED"]
    exposure = 1.0 - hard / len(rows)
    suspect = tally["VALIDATOR_SUSPECT"]
    return {
        "kills": len(records), "tally": dict(tally),
        "false_kill_exposure": round(exposure, 4),
        "headline": (
            f"{suspect} kill(s) VALIDATOR_SUSPECT and {tally['REGIME_CONDITIONAL']} "
            f"REGIME_CONDITIONAL of {len(rows)}: {exposure:.0%} of rejections are not settled"
            if exposure > 0 else
            f"all {len(rows)} rejections are decisive on the retained statistics"),
        "rows": rows[:200],
        "note": ("EXPOSURE IS AN UPPER BOUND, never an estimate of alpha destroyed, and it may "
                 "never be cited as a reason to lower a bar. A SOFT_KILL is still a kill; these "
                 "states buy a PREREGISTERED re-test on evidence the selection has not seen, "
                 "never a promotion. Re-partitioning until a cell passes is post-hoc selection."),
    }

"""EQUIVALENT-MUTANT REGISTER -- the one honest reason a mutant may go unkilled.

An equivalent mutant is a source change that CANNOT alter observable behaviour, so no test can
kill it. They are unavoidable, and they are also the single easiest way to destroy the value of
mutation testing: "that one's equivalent" is available for every inconvenient survivor, costs
nothing to say, and is almost never checked. So this register makes the claim expensive:

  * EVERY entry carries a WRITTEN JUSTIFICATION -- the specific argument for why no caller can
    observe the difference. Not "cosmetic", not "n/a": the predicate and both values.
  * EVERY entry is PINNED TO THE SOURCE LINE TEXT as it read when the claim was made. If that line
    is edited in any way, the claim LAPSES and the mutant counts against the score again. This is
    the property that stops the register rotting into a permanent exemption list: the argument was
    made about a specific line of code, so it expires when that code changes.
  * The raw score is ALWAYS reported alongside the adjusted one. Nothing here hides a number.

WHY IT EXISTS AT ALL, rather than just tolerating a red metric. `libs/execution/staging.py` scores
83.3% against a 90% bar, and all 7 survivors are provably equivalent (verified predicate by
predicate: every one mutates a `.get(key, default)` fail-closed default from one refusing value to
a different refusing value -- 1.0 -> 2.0 against `<= 0.10`, 0 -> 1 against `>= 10`, and so on).
The module is therefore at 35/35 on real mutants and can NEVER reach 90% on the raw number.

A metric that is permanently red for a reason nobody can fix is worse than no metric: it trains
the desk to ignore the one number that measures whether its money-path tests actually constrain
anything. That is the same false-red failure that let gate.py sit at a phantom 23.5% -- and a
false red is not a safe conservative error, it is an unreadable one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Equivalence:
    target: str
    kind: str
    mutation: str
    line_text: str       # the stripped source line AS CLAIMED -- the claim's expiry condition
    justification: str


# Each entry below was verified by evaluating the ORIGINAL and MUTATED value against the actual
# predicate and confirming both land on the same side. The verification is reproducible:
#   float(1.0) <= 0.10  is False;  float(2.0) <= 0.10  is False.  -> no caller can tell them apart.
_REGISTER: tuple[Equivalence, ...] = (
    Equivalence(
        "libs/execution/staging.py", "num_const", "2 -> 3",
        '_STATE.write_text(json.dumps(state, indent=2), "utf-8")',
        "JSON indentation. Changes whitespace in the state file and nothing that is parsed: "
        "json.loads is indifferent to indent, and no caller reads the raw text. Purely cosmetic."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "1.0 -> 2.0",
        '"capital_fraction_le_010": float(evidence.get("capital_fraction", 1.0)) <= 0.10,',
        "Fail-closed DEFAULT for a missing capital_fraction. Predicate is `<= 0.10`; both 1.0 and "
        "2.0 are False, so an absent value refuses identically either way. The value never leaves "
        "the function -- only the boolean does."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "0 -> 1",
        '"symbol_count_4_5": 4 <= int(evidence.get("symbol_count", 0)) <= 5,',
        "Fail-closed DEFAULT for a missing symbol_count. Predicate is `4 <= v <= 5`; both 0 and 1 "
        "are outside it, so an absent count refuses identically."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "0.0 -> 1.0",
        '"live_weeks_ge_8": float(evidence.get("live_weeks", 0.0)) >= 8.0,',
        "Fail-closed DEFAULT for missing live_weeks. Predicate is `>= 8.0`; both 0.0 and 1.0 are "
        "below it."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "0 -> 1",
        '"calibration_rows_ge_10": int(evidence.get("calibration_rows", 0)) >= 10,',
        "Fail-closed DEFAULT for missing calibration_rows. Predicate is `>= 10`; both 0 and 1 are "
        "below it."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "1 -> 2",
        '"critical_drill_failures_eq_0": int(evidence.get("critical_drill_failures", -1)) == 0,',
        "The -1 SENTINEL, which the AST sees as USub(1) so the mutant is -2. Predicate is `== 0`; "
        "both -1 and -2 are False, so 'no drill record' refuses either way. NOTE: the sentinel "
        "itself is load-bearing (this defaulted to 0 and passed the S2 gate on missing evidence -- "
        "found by mutation testing twice). Its VALUE being -1 versus -2 is what is equivalent, not "
        "its being negative."),
    Equivalence(
        "libs/execution/staging.py", "num_const", "999.0 -> 1000.0",
        '"realized_cost_le_1_25x": float(evidence.get("cost_ratio", 999.0)) <= 1.25,',
        "Fail-closed DEFAULT for a missing cost_ratio. Predicate is `<= 1.25`; both 999.0 and "
        "1000.0 are above it."),
)


def _line_text(target: str, lineno: int) -> str:
    try:
        lines = (_ROOT / target).read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    return lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""


def classify(target: str, survivor: dict[str, object]) -> Equivalence | None:
    """Return the live equivalence claim for this survivor, or None.

    A claim applies only when kind and mutation match AND the source line still reads exactly as
    it did when the argument was written. Any edit to that line lapses the claim -- the argument
    was about that code, so it does not survive the code changing.
    """
    kind, mutation = str(survivor.get("kind", "")), str(survivor.get("mutation", ""))
    try:
        lineno = int(survivor.get("line", 0))
    except (TypeError, ValueError):
        return None
    actual = _line_text(target, lineno)
    for e in _REGISTER:
        if (e.target == target and e.kind == kind and e.mutation == mutation
                and e.line_text == actual):
            return e
    return None


def adjust(target: str, survivors: list[dict[str, object]], killed: int,
           total: int) -> dict[str, object]:
    """Raw and adjusted kill rates, plus every claim applied and every claim that has LAPSED.

    Lapsed claims are surfaced rather than dropped: a claim whose line moved is a prompt to
    re-argue it against the new code, not permission to keep the exemption.
    """
    equivalents = [(s, e) for s in survivors if (e := classify(target, s)) is not None]
    n_eq = len(equivalents)
    real_total = max(total - n_eq, 0)
    claimed_here = [e for e in _REGISTER if e.target == target]
    lapsed = [e.mutation for e in claimed_here
              if not any(e is m for _, m in equivalents)]
    return {
        "raw_kill_rate": round(killed / total, 4) if total else 0.0,
        "equivalent_mutants": n_eq,
        "adjusted_kill_rate": round(killed / real_total, 4) if real_total else 0.0,
        "equivalences_applied": [
            {"line": s.get("line"), "kind": e.kind, "mutation": e.mutation,
             "justification": e.justification} for s, e in equivalents],
        "equivalences_lapsed": lapsed,
        "real_survivors": [s for s in survivors if classify(target, s) is None],
    }

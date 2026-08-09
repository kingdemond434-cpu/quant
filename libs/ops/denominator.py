"""THE DENOMINATOR OF A VERDICT (L1.57) -- a fence that scanned nothing has not passed.

WHAT THIS ASKS THAT ``fence_exit`` CANNOT. L1.28a/L1.43 gave the desk ``libs/ops/fence_exit.py``:
name the PASSING statuses, fail everything else. It closed the "a BLIND status fell down the
``else 0`` branch" defect (R0237) and it closed it properly. But it can only judge the status it
is HANDED, and the whole class below produces a status that is honestly, correctly ``OK``:

    files = list(root.rglob("*.py"))          # returns [] -- wrong root, moved dir, bad glob
    violations = [f for f in files if bad(f)] # [] , necessarily
    status = "OK" if not violations else "DIRTY"
    return fence_exit(status, {"OK"})         # 0. Correct, given the input. The input is the lie.

Nothing here is a bug in ``fence_exit``. The status genuinely is OK: zero violations were found.
The defect is one level up, in the DENOMINATOR -- how many things were examined to earn that
verdict -- and no instrument on this desk read it. ``all([])`` is ``True``, ``0 < 0/2`` is
``False``, ``min(survivors)`` hides every absent sibling, and each of those renders as health.

THE LAW WAS ALREADY WRITTEN, AND HAD ONE INSTRUMENT FOR ONE RATIO. L1.53(4), 2026-08-05:
"whenever a gauge can be improved by doing less of the thing it exists to encourage, its
denominator is a first-class measurement and is fenced separately." That was written about the
conversion ratio, fenced for the conversion ratio, and generalised in its own text to "every
ratio the desk reports". It was never carried to the place the same arithmetic does the most
damage: a fence's own verdict. A DUTY WITH NO INSTRUMENT IS A WISH (L1.46). This is the
instrument, and the generalisation is from RATIOS to VERDICTS.

THE MEASURED STATE OF THE DESK WHEN THIS WAS WRITTEN (2026-08-05, 40 fences read by hand across
two independent sweeps): **18 of 40 fences pass vacuously** -- an empty scan set yields a passing
status and exit 0. A further **10 publish an ``n_*`` key that looks like a denominator and is
``len()`` of a hardcoded module-level literal**, which counts what the author wrote down, never
what the run found. Only THREE fences published a measured count of what they actually examined.

WHY THE CONSTANT-DENOMINATOR CASE IS THE NASTIER HALF. ``n_organs``, ``n_fences``, ``n_governed``
and ``n_criteria`` all read as measurements in an artifact and in a report line. They cannot fall
when the thing they count disappears, because they never counted it -- so the one event they
exist to reveal is the one event they cannot show. ``check_exploration`` is the proving instance
and it is live: ``n = len(_FAMILY)`` over a dict that is MUTATED AT IMPORT by
``_FAMILY.pop(_k)``, from a module loaded under ``except: _secondary = {}``. Empty that dict and
``len(fresh) < n / 2`` becomes ``0 < 0.0`` -- False -- so the L1.32 exploration-family fence
reports ``status: OK`` with ``n_organs: 0`` and exits 0. The desk would read "the unknown-unknown
organs are healthy" from a fence that had just been told there are no organs.

THE MECHANISM -- ONE KWARG AT THE EXIT SITE, WHICH IS THE ONLY PLACE THAT KNOWS BOTH HALVES::

    from libs.ops.fence_exit import fence_exit
    n = len(discovered)                      # whatever the run actually found
    return fence_exit(rep["status"], _PASSING, scanned=n, of="scripts/check_*.py")

``fence_exit`` records the (fence, of, n, passed) row to the self-building registry and REFUSES
a passing status whose denominator is zero. The registry is what lets a meta-fence measure
coverage without a hand-maintained list of fences -- the same substrate argument as L1.44's
``freshness_contracts.jsonl``, and for the same reason: the desk's hand lists rot.

THIS CAN ONLY EVER MAKE A FENCE FAIL ON MORE INPUTS. There is no vocabulary here for turning a
failure into a pass: ``scanned`` is consulted ONLY when the status was already going to pass.
An undeclared denominator (``scanned=None``) leaves the exit code exactly as it was -- deliberate,
because a fence that goes red on the day it is built gets switched off (L1.43), and an
UNDECLARED fence is instead counted against a COVERAGE RATCHET whose gap is the work queue (L1.0).

ANTI-TIMIDITY READING (L1.28, required of every restraint clause). This is a MEASUREMENT duty and
a SCOPE EXPANSION: it lifts nothing, sizes nothing, and loosens no statistical bar. Its entire
effect is to make "I checked 900 files and found nothing" distinguishable from "I checked nothing"
-- two claims that are currently byte-identical on this desk, and only one of which is evidence.
The direction of the error it catches is always the same and always toward false comfort.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

#: The self-building registry: one append per fence exit that declared a denominator. JSONL
#: (not a keyed JSON map) because fences run concurrently under cron and an append of one short
#: line is race-safe where a read-modify-write of a shared map is not. Readers take the LAST row
#: per fence. Same argument, same shape as libs/ops/fresh.py's freshness_contracts.jsonl.
REGISTRY_REL = "data/denominator_contracts.jsonl"

#: Rows older than this are ignored by readers: a fence that stopped declaring should decay out
#: of coverage rather than count forever from a row written months ago. 30d is generous against
#: the slowest declared fence cadence (weekly) and short enough that a deleted fence disappears.
MAX_ROW_AGE_S = 30 * 86400.0


def _root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def is_vacuous(n_scanned: object, passed: bool) -> bool:
    """True when a PASSING verdict rests on an empty or unusable scan count.

    ``n_scanned`` is typed ``object`` on purpose. A fence that failed to discover its own scope
    can hand us ``None``, a float, or a string; none of those is a positive count of things
    examined, so none of them earns a pass. Only a genuine integer >= 1 does.
    """
    if not passed:
        return False                      # a failing verdict is never vacuous, whatever n is
    if isinstance(n_scanned, bool) or not isinstance(n_scanned, int):
        return True                       # bool is an int subclass; True is not a count
    return n_scanned < 1


def record(fence: str, of: str, n_scanned: object, passed: bool,
           *, root: Path | None = None) -> None:
    """Append one row to the registry. Never raises: a fence must not die over telemetry.

    The row records the OUTCOME, not merely the intent, because the vacuity question needs both
    halves at once and the exit site is the only place that holds them together.
    """
    try:
        r = root or _root()
        p = r / REGISTRY_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        row = {"at": time.time(), "fence": fence, "of": of,
               "n_scanned": n_scanned if isinstance(n_scanned, int) else None,
               "passed": bool(passed), "vacuous": is_vacuous(n_scanned, passed)}
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        pass


def load(root: Path | None = None, *, now: float | None = None) -> dict[str, dict[str, Any]]:
    """Last non-stale row per fence. Malformed lines are skipped, never fatal.

    Returns ``{}`` when the registry is absent or unreadable -- and every caller must treat that
    as UNMEASURED rather than clean (L1.28a). Absence of evidence is not evidence of coverage.
    """
    r = root or _root()
    p = r / REGISTRY_REL
    t = time.time() if now is None else now
    out: dict[str, dict[str, Any]] = {}
    try:
        text = p.read_text("utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(row, dict) or not isinstance(row.get("fence"), str):
            continue
        at = row.get("at")
        if not isinstance(at, (int, float)) or (t - float(at)) > MAX_ROW_AGE_S:
            continue
        out[row["fence"]] = row
    return out


def caller_name(default: str = "unknown") -> str:
    """Best-effort name of the running fence, for callers that do not pass one explicitly."""
    try:
        import __main__
        f = getattr(__main__, "__file__", None)
        if isinstance(f, str) and f:
            return os.path.basename(f)
    except Exception:
        pass
    return default


def governed_fences(root: Path | None = None) -> list[str]:
    """The scope: every ``scripts/check_*.py`` present on disk.

    DISCOVERED, never enumerated. A meta-fence about hardcoded denominators that carried a
    hardcoded list of the fences it governs would be the very defect it exists to detect, and
    would go quietly stale the first time someone added a fence.
    """
    r = root or _root()
    try:
        return sorted(p.name for p in (r / "scripts").glob("check_*.py") if p.is_file())
    except OSError:
        return []


def summarise(root: Path | None = None, *, now: float | None = None,
              scope: Iterable[str] | None = None) -> dict[str, Any]:
    """Coverage and vacuity across the governed fence set. Shared by the fence and its tests."""
    fences = sorted(scope) if scope is not None else governed_fences(root)
    rows = load(root, now=now)
    declared, undeclared, vacuous = [], [], []
    for name in fences:
        row = rows.get(name)
        if row is None:
            undeclared.append(name)
        elif row.get("vacuous"):
            vacuous.append({"fence": name, "of": row.get("of"),
                            "n_scanned": row.get("n_scanned")})
        else:
            declared.append({"fence": name, "of": row.get("of"),
                             "n_scanned": row.get("n_scanned")})
    n = len(fences)
    return {
        "n_fences": n,
        "n_declared": len(declared) + len(vacuous),
        "coverage": None if n == 0 else round((len(declared) + len(vacuous)) / n, 4),
        "declared": declared,
        "undeclared": undeclared,
        "vacuous": vacuous,
    }

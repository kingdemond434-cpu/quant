#!/usr/bin/env python3
"""Ratcheting branch-coverage floor for the MT5 MONEY PATH -- the files that move capital.

    pytest desks/mt5/tests -q -p no:randomly --timeout=600 \\
           --cov=desks/mt5/mt5desk --cov=desks/mt5/research --cov-branch \\
           --cov-report=term:skip-covered --cov-report=json:mt5cov.json
    python scripts/check_mt5_coverage_floor.py --report mt5cov.json          # the gate
    python scripts/check_mt5_coverage_floor.py --report mt5cov.json --init   # seal the baseline, once

WHY A SEPARATE FLOOR. The repo's headline coverage measures `libs`, and its "money path" list
names the retired crypto executor. The MT5 gateway, sizing, promoter and allocator bridge --
the code that actually places orders -- were outside every coverage number the CI reported. A
green gate that measures the wrong heart is worse than no gate, because it is believed.

THE FLOOR RATCHETS. Per money-path file, the highest branch coverage ever recorded is stored and
a run may not fall more than TOLERANCE below it. Nothing here sets a target by fiat; the target
is what the desk has already achieved, and the only direction allowed is up.

THE BASELINE IS COMMITTED, OR THERE IS NO RATCHET (audit 2026-09-05). Until this date the
high-water file was never committed and a missing file was read as `{}` -- so every fresh CI
runner compared the measurement against ZERO, wrote a high-water mark that evaporated with the
runner, and reported green. A ratchet whose memory lives on a disposable host starts from nothing
every time, which is to say it is not a ratchet. Now a missing or unreadable baseline is a FAILURE
that names the file and the one command that creates it, and creating it is an explicit `--init`
that refuses to overwrite: the first measurement is a deliberate act with a date, a report hash
and the suite command on it, and every later rise is recorded on top of that.

ABSENT IS A FAILURE, NOT A LINE OF OUTPUT. The same audit found that a money-path module missing
from the report printed `absent` and moved on. A module leaves the report when its test file is
deleted, when it is renamed, or when the run dies before importing it -- exactly the cases a
coverage floor exists to catch -- and the capital-moving code needs the strongest proof, not the
weakest. The one honest exception is declared in UNMEASURABLE_HERE with its reason, and that
allowlist is itself ratcheted: the first time an allowlisted module DOES appear in the report its
number is recorded in the baseline, its absence is never again excused, and the now-dead entry is
reported on every run until somebody deletes it.

MEASURED AT SEALING, 2026-09-05 (1352 passed, 3 skipped, coverage.py 7.16.0, branch mode). The
gateway was expected to be the excused absence -- it imports MetaTrader5 at module scope and that
package is Windows-only. It was NOT absent: coverage.py lists every file under a `--cov` source
directory whether or not anything imported it, so `gateway.py` is in the report at 0.60% -- ten
prelude lines (21-33, up to the `import MetaTrader5 as mt5` that raises), 0 of 438 branches. The
excuse was written for an absence the report did not have, so the seal retired it and floored the
file at 0.6%, and the reason it was written for is kept beside that number in the baseline. That
is the truer statement: the order-placing file is effectively unexecuted on this host and the
floor says so in a number rather than behind an excuse. The exit is unchanged -- split the
portable decision core out of the terminal-bound shell so it can be executed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HIGH_WATER = ROOT / "desks" / "mt5" / "data" / "coverage_high_water.json"
#: Slack below the high-water mark, as a fraction of 1. Branch coverage moves a little with test
#: ordering and optional-dependency skips; a floor that fires on noise gets deleted, which is
#: worse than a floor two points low. A fall past this is a regression and fails the run.
TOLERANCE = 0.02

#: The invocation the baseline is sealed from -- verbatim from ci.yml's mt5-money-path job, so
#: the number in the committed file and the number CI measures come from the same command.
SUITE_COMMAND = (
    "pytest desks/mt5/tests -q -p no:randomly --timeout=600 "
    "--cov=desks/mt5/mt5desk --cov=desks/mt5/research --cov-branch "
    "--cov-report=term:skip-covered --cov-report=json:mt5cov.json"
)
INIT_COMMAND = "python scripts/check_mt5_coverage_floor.py --report mt5cov.json --init"

#: The MT5 money path, by file. Every one either places an order, sizes one, decides what may
#: trade, or feeds a number the sizer trusts.
MONEY_PATH = (
    "desks/mt5/mt5desk/gateway.py",
    # THE DECISIONS THEMSELVES (added 2026-09-05, the split this file's docstring names as the
    # exit). `gateway.py` is the venue adapter and is measured at ~0.6% here for a structural
    # reason -- MetaTrader5 is Windows-only, so the runner executes ten prelude lines and stops.
    # Every decision it used to hold -- the sizing laws, the heat cap, the allocator readers,
    # roster admission, the state gate, the bracket arithmetic, the retcode diagnosis, the
    # session deadline, the execution context, the release gate, both lanes' steps -- now lives
    # in `decision_core.py`, which imports on any host and IS executed by the desk's suite. This
    # entry is what makes that a measurement rather than a claim: the money path's proof is now
    # a number that can fall, and this file is where it is caught when it does.
    "desks/mt5/mt5desk/decision_core.py",
    "desks/mt5/mt5desk/engine.py",
    "desks/mt5/mt5desk/independence.py",
    "desks/mt5/mt5desk/markout.py",
    "desks/mt5/research/pf_allocator.py",
    "desks/mt5/research/promoter.py",
    "desks/mt5/research/state_admission_run.py",
    "desks/mt5/research/session_phase.py",
    "desks/mt5/research/allocator_attribution.py",
)

#: Money-path modules whose ABSENCE from the report is excused, path -> the structural reason.
#:
#: This is the only way a money-path file may be missing from the report without failing the
#: gate, and an entry is an interim, not a settlement: it is written with its reason so that
#: absent-and-known and absent-and-broken cannot render alike (L1.28a), and it is expected to be
#: outgrown.
#:
#: RATCHETED. An entry here is honoured only while the baseline has never measured the file. The
#: first run that finds the file in the report records its number, stamps `allowlist_retired` in
#: the baseline (reason kept), and from then on the file is held to its floor like every other --
#: this constant no longer excuses it. The stale entry is reported on every run until it is
#: deleted, and tests/scripts/test_check_mt5_coverage_floor.py fences the committed baseline
#: against carrying a retired entry that is still listed here.
#:
#: EMPTY SINCE THE SEAL. The one entry this was written for --
#:     "desks/mt5/mt5desk/gateway.py":
#:         "MetaTrader5 not importable on Linux; portable decision core pending split"
#: -- was retired by the seal on 2026-09-05: the report covered the gateway (0.6%, the import
#: prelude), so the ratchet floored it and the entry became dead code. The reason lives on in the
#: baseline's `allowlist_retired`. The next money-path file the host genuinely cannot measure goes
#: here with its reason, and leaves the same way.
UNMEASURABLE_HERE: dict[str, str] = {}


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def _branch_pct(entry: dict[str, Any]) -> float | None:
    s = entry.get("summary") or {}
    if "percent_covered" in s:
        return float(s["percent_covered"]) / 100.0
    return None


def measure(report: dict[str, Any]) -> dict[str, float | None]:
    """Per money-path file, the covered fraction from a coverage.py JSON report, or None when the
    file is not in the report at all (or is there without a summary, which is the same absence).

    Keys are matched by suffix so the Windows box's backslashed absolute paths and the runner's
    relative ones both resolve to the same money-path entry.
    """
    raw = report.get("files") or {}
    files = {_norm(str(k)): v for k, v in raw.items()} if isinstance(raw, dict) else {}
    out: dict[str, float | None] = {}
    for rel in MONEY_PATH:
        entry = next((v for k, v in files.items() if k.endswith(rel)), None)
        out[rel] = _branch_pct(entry) if isinstance(entry, dict) else None
    return out


def report_meta(report: dict[str, Any]) -> dict[str, Any]:
    meta = report.get("meta")
    return dict(meta) if isinstance(meta, dict) else {}


def is_branch_report(report: dict[str, Any]) -> bool:
    """A branch floor sealed from, or checked against, a line-only report is an inflated number:
    line coverage is always at least branch coverage. coverage.py stamps the report with the mode
    it ran in, and this refuses to read a report that does not say `branch_coverage: true`."""
    return bool(report_meta(report).get("branch_coverage"))


def read_baseline(path: Path) -> dict[str, Any]:
    """The committed high-water record. Raises rather than defaulting: FileNotFoundError when it
    is absent, ValueError when it is not a JSON object with a `high_water` mapping. Neither is
    ever read as `{}` again -- that was the audit's finding (a)."""
    doc = json.loads(path.read_text("utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("high_water"), dict):
        raise ValueError(f"{path} is not a high-water record (no `high_water` mapping)")
    return doc


def evaluate(
    now: dict[str, float | None],
    baseline: dict[str, Any],
    tolerance: float = TOLERANCE,
    *,
    stamp: str | None = None,
) -> dict[str, Any]:
    """The verdict, pure so the tests can drive it.

    Returns `lines` (the per-file table), `notices` (reported, never fatal), `failures` (fatal),
    `high_water` (the marks to persist; only ever higher than the input) and `allowlist_retired`
    (allowlisted files the report has now measured, with when and at what).
    """
    hw: dict[str, float] = {k: float(v) for k, v in baseline["high_water"].items()}
    retired: dict[str, dict[str, Any]] = {
        k: dict(v) for k, v in (baseline.get("allowlist_retired") or {}).items()
    }
    when = stamp or datetime.now(tz=UTC).isoformat()
    new_hw = dict(hw)
    lines: list[str] = []
    notices: list[str] = []
    failures: list[str] = []

    for rel in MONEY_PATH:
        pct = now.get(rel)
        prev = hw.get(rel)
        excused = rel in UNMEASURABLE_HERE and prev is None and rel not in retired
        if pct is None:
            if excused:
                lines.append(f"{rel:52s} {'absent':>7s} {'-':>7s}   excused: "
                             f"{UNMEASURABLE_HERE[rel]}")
                continue
            if prev is not None or rel in retired:
                seen = retired.get(rel, {})
                known = prev if prev is not None else float(seen.get("pct") or 0.0)
                since = f" on {seen['measured_at']}" if seen.get("measured_at") else ""
                failures.append(
                    f"{rel}: ABSENT from the coverage report. Its absence is not excused -- it "
                    f"has been measured before (high-water {known:.1%}{since}), so a report "
                    "without it is a report with a hole where the money path was."
                )
            else:
                failures.append(
                    f"{rel}: ABSENT from the coverage report and not declared in "
                    "UNMEASURABLE_HERE. A money-path module that stops being measured has lost "
                    "its test file, moved, or never imported -- name the reason in the allowlist "
                    "or restore the measurement; the gate does not score silence."
                )
            lines.append(f"{rel:52s} {'absent':>7s} {'-':>7s}   <-- FAIL")
            continue

        if rel in UNMEASURABLE_HERE:
            if rel not in retired:
                retired[rel] = {"measured_at": when, "pct": round(pct, 4),
                                "was_excused_as": UNMEASURABLE_HERE[rel]}
                notices.append(
                    f"ALLOWLIST RATCHETED: {rel} appeared in the report at {pct:.1%}. Its "
                    "absence is no longer excused; the baseline now holds it to a floor. Delete "
                    "its UNMEASURABLE_HERE entry -- the ratchet has retired it."
                )
            else:
                notices.append(
                    f"STALE ALLOWLIST ENTRY: {rel} was measured on "
                    f"{retired[rel].get('measured_at', '?')} and is floored; the "
                    "UNMEASURABLE_HERE entry is dead code and should be deleted."
                )

        flag = ""
        mark = round(pct, 4)
        if prev is None:
            new_hw[rel] = mark
            flag = "   first measurement -- floored here"
            shown_prev = "-"
        else:
            shown_prev = f"{prev:7.1%}"
            if pct + 1e-9 < prev - tolerance:
                failures.append(
                    f"{rel}: {pct:.1%} fell more than {tolerance:.0%} below its high-water "
                    f"{prev:.1%}"
                )
                flag = "   <-- REGRESSION"
            elif mark > prev:
                new_hw[rel] = mark
                flag = "   raised"
        lines.append(f"{rel:52s} {pct:7.1%} {shown_prev:>7s}{flag}")

    for rel in sorted(set(hw) - set(MONEY_PATH)):
        notices.append(
            f"baseline carries {rel} at {hw[rel]:.1%} but it is no longer in MONEY_PATH; the "
            "number is kept (deleting a mark is the denominator trick) and not compared."
        )
    return {
        "lines": lines,
        "notices": notices,
        "failures": failures,
        "high_water": new_hw,
        "allowlist_retired": retired,
    }


def seal(
    now: dict[str, float | None],
    *,
    report_path: str,
    report_sha256: str,
    meta: dict[str, Any],
    stamp: str | None = None,
) -> dict[str, Any]:
    """The first baseline: every measured money-path file at its measured value, every excused
    file with its reason, and the provenance of the report the numbers came from.

    An allowlisted file that the sealing report DOES cover is retired at the seal, reason kept:
    the excuse was never needed on this host and the record says so from day one."""
    when = stamp or datetime.now(tz=UTC).isoformat()
    return {
        "_": (
            "HIGH-WATER MARKS for MT5 money-path branch coverage, per file, as fractions of 1. "
            "Sealed once by --init, raised by the gate whenever a run measures higher, NEVER "
            "lowered by code: nothing lowers a mark but a human editing this file with a reason. "
            "A missing file is a CI failure, not a zero -- a ratchet with no memory is not one."
        ),
        "sealed_at": when,
        "measured_at": when,
        "suite_command": SUITE_COMMAND,
        "report": report_path,
        "report_sha256": report_sha256,
        "report_meta": meta,
        "tolerance": TOLERANCE,
        "money_path_files": list(MONEY_PATH),
        "high_water": {rel: round(pct, 4) for rel, pct in now.items() if pct is not None},
        "unmeasurable_here": {
            rel: UNMEASURABLE_HERE[rel]
            for rel, pct in now.items()
            if pct is None and rel in UNMEASURABLE_HERE
        },
        "allowlist_retired": {
            rel: {"measured_at": when, "pct": round(pct, 4),
                  "was_excused_as": UNMEASURABLE_HERE[rel]}
            for rel, pct in now.items()
            if pct is not None and rel in UNMEASURABLE_HERE
        },
    }


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n", "utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", default="mt5cov.json", help="coverage.py JSON report")
    ap.add_argument("--tolerance", type=float, default=TOLERANCE)
    ap.add_argument("--baseline", default=None,
                    help=f"high-water record (default {HIGH_WATER.relative_to(ROOT)})")
    ap.add_argument("--init", action="store_true",
                    help="SEAL the baseline from this report. Refuses if one exists.")
    a = ap.parse_args(argv)
    baseline_path = Path(a.baseline) if a.baseline else HIGH_WATER

    report_file = Path(a.report)
    try:
        raw = report_file.read_bytes()
        report = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"coverage report unreadable: {a.report} ({exc}). Produce it first:\n"
              f"  {SUITE_COMMAND}")
        return 1
    if not isinstance(report, dict) or not is_branch_report(report):
        print(f"{a.report} was not produced with --cov-branch (meta.branch_coverage is not true). "
              "This is a BRANCH floor; a line-only report would inflate every number in it.")
        return 1
    sha = hashlib.sha256(raw).hexdigest()
    now = measure(report)

    if a.init:
        if baseline_path.exists():
            print(f"REFUSING --init: {baseline_path} already exists. The gate raises it by itself "
                  "on every higher measurement; the only way down is a human editing the file "
                  "with a reason, never a re-seal.")
            return 1
        unexcused = [rel for rel, pct in now.items()
                     if pct is None and rel not in UNMEASURABLE_HERE]
        if unexcused:
            print("REFUSING --init: the report does not cover every money-path module, and a "
                  "baseline sealed over a partial population is a permanent error. Absent and not "
                  f"in UNMEASURABLE_HERE: {', '.join(unexcused)}")
            return 1
        doc = seal(now, report_path=a.report, report_sha256=sha, meta=report_meta(report))
        _write(baseline_path, doc)
        print(f"sealed {baseline_path} from {a.report} (sha256 {sha[:12]}...):")
        for rel, pct in doc["high_water"].items():
            print(f"  {rel:52s} {pct:7.1%}")
        for rel, why in doc["unmeasurable_here"].items():
            print(f"  {rel:52s} {'absent':>7s}   excused: {why}")
        print("  commit this file: it is the ratchet's memory and a runner has none.")
        return 0

    try:
        baseline = read_baseline(baseline_path)
    except FileNotFoundError:
        print(f"NO BASELINE: {baseline_path} is absent. A ratchet with nothing to ratchet against "
              "is not a ratchet, and a zero floor is not a floor -- this used to pass silently. "
              f"Seal one deliberately from a measured report and commit it:\n  {SUITE_COMMAND}\n"
              f"  {INIT_COMMAND}")
        return 1
    except (OSError, ValueError) as exc:
        print(f"BASELINE UNREADABLE: {baseline_path} ({exc}). Not defaulting to zero; repair the "
              "file by hand from git history rather than re-sealing.")
        return 1

    verdict = evaluate(now, baseline, a.tolerance)
    print(f"{'file':52s} {'now':>7s} {'high':>7s}   "
          f"(baseline sealed {baseline.get('sealed_at', '?')})")
    for line in verdict["lines"]:
        print(line)
    for note in verdict["notices"]:
        print(f"  {note}")

    changed = (verdict["high_water"] != baseline["high_water"]
               or verdict["allowlist_retired"] != (baseline.get("allowlist_retired") or {}))
    if changed:
        # THE MARK ONLY RISES. `evaluate` never returns a lower value, so this write is monotone by
        # construction; the provenance fields move with it so the file always names the report
        # that earned its numbers.
        doc = dict(baseline)
        doc["high_water"] = verdict["high_water"]
        doc["allowlist_retired"] = verdict["allowlist_retired"]
        doc["measured_at"] = datetime.now(tz=UTC).isoformat()
        doc["report"] = a.report
        doc["report_sha256"] = sha
        doc["report_meta"] = report_meta(report)
        doc["money_path_files"] = list(MONEY_PATH)
        _write(baseline_path, doc)
        print(f"  high-water raised -> {baseline_path} (commit it; a runner's copy evaporates)")

    if verdict["failures"]:
        for f in verdict["failures"]:
            print(f"  FAIL: {f}")
        print(f"{len(verdict['failures'])} money-path failure(s). Floors ratchet: restore the "
              "coverage, or edit the record by hand with a reason.")
        return 1
    print("money-path floor held")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""ATOMIC CANON PUBLICATION: the judge republishes, and until now nothing carried that forward.

MEASURED ON THE TRADING BOX 2026-09-24, and this is the whole reason the file exists:

    desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json   swept_at 2026-09-03T08:45:17   n=28
    desks/mt5/reports/UNIVERSAL_SURVIVORS.json      swept_at 2026-09-23T05:42      n=28
    desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl   146,359 verdicts, latest 2026-09-23

The SEALED CANON -- the file `libs/research/memory.py`, `alpha_breadth`, `alpha_genome`,
`certificate_hygiene`, `clock_certificate`, `conversion_ledger`, `attribution_reconcile`,
`scripts/sync_research_ledger.py`, `scripts/check_dig_roi.py` and `scripts/run_desk_integrity.py`
all read as the desk's certificate store -- carried a sweep stamp TWENTY-ONE DAYS OLD while the
judge ran and appended verdicts the whole time. Its mtime was recent, which is worse than stale:
`certificate_truth` HEALS it and the retirement scripts PRUNE it, so the file kept moving while
its sweep stamp stood still. A reader checking freshness by mtime saw a live file.

WHY IT WENT STALE. `external_gauntlet.py` is SEALED and IS a faithful republisher: at the end of
every completed sweep it rewrites `reports/UNIVERSAL_SURVIVORS.json` with a fresh `swept_at`
(:3444-3457). Nothing on any clock copies that into the sealed canon. `recertify_canon` sounds
like the step that would and is not: it re-JUDGES the standing library under the current cost
model, writes `reports/recertification_audit.json`, and the hourly cycle only claims it when the
queue holds a `recertify` task -- which a fresh certificate does not raise. So the publication
path had a missing last link and every organ reading the seal was reading 2026-09-03.

WHAT THIS ORGAN DOES, AND THE FOUR THINGS IT REFUSES TO DO:

    IT MINTS NOTHING. A row reaches the seal only if it is already in the judge's report AND
    `gate_policy.all_ten_pass` holds on its own gates record. There is no path here that creates
    a certificate, and no threshold anywhere in the file.
    IT NEVER SHRINKS. The union of the seal's rows and the report's rows is written, never the
    report alone -- the never-shrink law of 2026-08-26 (the certifier wipe), restated at the
    second pen rather than assumed.
    IT NEVER REVIVES A RETIREMENT. A key in `retired_certificates` stays out, whatever the report
    says. Retirement is the retirers' call and this organ does not overturn it.
    IT NEVER WRITES A HALF FILE. tempfile + fsync + os.replace, in the destination directory, so
    a reader either sees the old seal or the new one and never the middle of a 137 KB write.

WHEN THE JUDGE DID NOT REPUBLISH -- killed at its cycle budget, halted on an empty docket, or
refusing a shrink -- the seal is LEFT ALONE and a DERIVED view is published instead, to
`reports/UNIVERSAL_SURVIVORS_DERIVED.json`, built from `gate_verdict_ledger.jsonl` and labelled
derived on every level: `derived: true`, `promotion_authority: false`, and a note saying in words
that its rows are PASSING CELL IDENTITIES and not certificates. The ledger records `passed` and
the terminal gate; it does not record a gates object, so nothing downstream can mistake a derived
row for something `all_ten_pass` would admit. A derived view that could be promoted from would be
a second certificate authority, which is the one thing this desk has never allowed.

RECOVERY: THE GATES ARE EVALUATED, THEN THROWN AWAY (added 2026-09-24, and this is the whole
point of the second half of this file).

    reports/universal_gates_external.json   swept_at 2026-09-23T05:42:42   88,366,334 bytes
                                            76,749 verdicts, survivors_passing_all: 7
    reports/UNIVERSAL_SURVIVORS.json        three minutes later, still swept_at 2026-09-16

The sealed judge writes its 88 MB gate output at `external_gauntlet.py:3123` and only THEN builds
survivor rows, annotates them, merges the scalp lane, rebuilds the power-cure file, purges,
restores and writes `UNIVERSAL_SURVIVORS.json` at :3452. Everything between those two writes is
minutes of work on a docket this size, and `_run_tree` SIGKILLs the leg at its cycle budget.
Measured on the box, `external_gauntlet` recorded ZERO successful outcomes on 18, 19, 20, 22, 23
and 24 September -- TIMEOUT at 1,100 s and 4,581 s, `exit_code=4294967295`, once a Windows paging
failure -- and across that window 65 cells passed all ten gates and not one reached the seal.

A KILL BETWEEN THE TWO WRITES MUST COST AN HOUR, NOT EVERYTHING. The gate output on disk is a
COMPLETE record of the evaluation: each verdict carries the same per-gate `stages` object the
sealed judge copies into `row["gates"]`. So `recover_from_gate_output` reads it, takes the
verdicts the judge already passed, and rebuilds exactly the row the judge was killed before
writing -- WITHOUT RE-RUNNING A SINGLE GATE and without softening one.

FOUR REFUSALS MAKE THAT SAFE, and every one of them is counted by name in the artifact rather
than taken silently:

    A SUPERSEDED CHARGE IS NOT THIS POLICY'S VERDICT. The gate output records the
    `trial_count_basis` and `n_trials` it was judged under. If either differs from the spec in
    force now, the rows are REFUSED -- sealing them would stamp the current attestation onto a
    verdict reached under a different bar, which `gate_policy`'s own comment says that field
    exists to prevent. (Measured today: the surviving gate output was judged at
    `fixed_campaign_trials(597)` and the spec now reads `effective_campaign_trials(109)`.)
    THE TEN GATES, JUDGED BY THE SAME PREDICATE. `gate_policy.all_ten_pass` on the verdict's own
    `stages`, unchanged and uncopied. Nothing here has a threshold.
    PARAMS ARE NEVER GUESSED. The gate output carries a cell ID, not the parameterisation behind
    its digest, so the params are recovered from the docket by recomputing `cell_id` -- and a cell
    whose params cannot be found is REFUSED, never sealed with `{}`. Enrolling a guessed
    parameterisation forward-tests a different strategy than the one certified, which is the
    two-stage law's exact prohibition (`survivor_publication.unrunnable_reason`).
    IT MINTS NOTHING. A verdict the judge did not mark `passed` cannot enter by this door, and
    the retirement, eviction and unrunnable refusals above apply to a recovered row exactly as to
    a republished one.

    python desks/mt5/research/canon_publication.py [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from collections import Counter
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SEAL = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
DERIVED = DESK / "reports" / "UNIVERSAL_SURVIVORS_DERIVED.json"
OUT = DESK / "reports" / "CANON_PUBLICATION.json"
#: The admission screen's census, READ here so the whole funnel reads in one artifact: raw intake
#: -> admissible -> judged -> certified -> sealed. The two halves were published in different
#: files by different organs and nothing ever put them beside each other, which is how a 244,275
#: row bank came to be read as a 244,275 cell backlog against a 28 row certificate store.
ADMISSION = DESK / "reports" / "ADMISSION_SCREEN.json"

#: Keys the seal carries that are NOT the survivor set and must survive a republication. Every one
#: is another organ's record -- the retirers', the healer's, the hygiene pass's -- and dropping it
#: would erase their work under the banner of publishing the judge's.
CARRIED: tuple[str, ...] = ("retired_certificates", "revoked_at", "unrunnable_evicted",
                            "unrunnable_note", "healed_at", "healed_by")

#: A derived view is bounded so a 33 MB ledger can never become an hour of IO on the box that
#: holds the live terminal. It is a fallback view, not an index.
DERIVED_MAX_ROWS = 200_000

#: THE JUDGE'S COMPLETED EVALUATION, written before the survivor rows it was killed before
#: writing. See the "RECOVERY" section of the module docstring.
GATE_OUTPUT = DESK / "reports" / "universal_gates_external.json"
#: The docket the judge built its cells from -- the only place a cell's params survive, because
#: the gate output records the cell's ID (a digest of the params) and not the params.
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
#: The docket is 440 MB on the trading box. It is STREAMED, one top-level object at a time, and
#: only when there is something to recover; this bounds the pass on a box that holds a live
#: terminal. A scan that runs out of budget recovers nothing THIS pass and says so -- the gate
#: output is still on disk, so the next pass tries again. Losing an hour is the whole design.
RECOVERY_BUDGET_SEC = 240.0
#: 4 MB reads: large enough that a 440 MB file is ~110 reads, small enough that the buffer never
#: becomes the memory problem the streaming exists to avoid.
_DOCKET_CHUNK = 1 << 22

#: The ONE forward engine's windows, spelled exactly as `scripts/external_gauntlet.py`'s `main()`
#: spells them. That file is SEALED and this map is a local inside its `main()`, so it cannot be
#: imported; `desks/mt5/tests/test_canon_recovers_a_killed_sweep.py` asserts this copy against the
#: sealed source, so the two can never drift without the suite saying so.
WINDOWS_KNOWN: dict[str, dict[str, int]] = {
    "asia": {"range_start": 7},
    "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13},
    "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14},
    "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17},
}


def _atomic_json(path: Path, value: dict[str, Any], *, indent: int = 2) -> None:
    """Write-and-rename, fsynced, in the destination directory.

    THE DIRECTORY MATTERS: `os.replace` is atomic only within one filesystem, and a temp file in
    the system temp dir is on a different volume on this box. Writing beside the target keeps the
    rename atomic, which is the property the whole function exists for.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=indent, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
    except OSError:
        return None


def _age_hours(stamp: Any, now: datetime) -> float | None:
    try:
        then = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    return round((now - then).total_seconds() / 3600.0, 2)


def _funnel(admission: Path = ADMISSION) -> dict[str, Any]:
    """Raw intake and the admissible population, from the admission screen's own census.

    ABSENT IS UNMEASURED, NEVER ZERO (L1.28a). A missing screen artifact says the screen has not
    run on this box yet; it does not say the bank is empty, and reporting 0 here would make the
    funnel read as "nothing to judge" when the truth is "nobody has counted".
    """
    doc = _read(admission)
    if not doc:
        return {"status": "UNMEASURED",
                "why": f"{admission.name} absent or unreadable -- the admission screen has not "
                       f"run here yet. That is not a claim that the docket is empty."}
    return {"status": doc.get("status"), "measured_at": doc.get("measured_at"),
            "raw_cells": doc.get("raw_cells"), "admissible_cells": doc.get("admissible_cells"),
            "refused_cells": doc.get("refused_cells"),
            "refused_by_reason": doc.get("refused_by_reason"),
            "source": str(admission)}


def derive_from_ledger(ledger: Path = GATE_LEDGER,
                       *, max_rows: int = DERIVED_MAX_ROWS) -> dict[str, Any]:
    """The DERIVED view: which cells the judge's ledger says passed. Not certificates.

    The ledger row is `{at, cell, sym, family, graph_id, passed, terminal_gate,
    downstream_status}`. There is no gates object in it, so this view can state WHICH cells passed
    and WHEN, and it can never state that they hold a ten-gate certificate. That limit is the
    point: it is what makes the fallback safe to publish while the seal is untouched.
    """
    now = datetime.now(UTC)
    passing: dict[str, dict[str, Any]] = {}
    rows = 0
    terminal: Counter[str] = Counter()
    if not ledger.exists():
        return {"derived": True, "status": "UNMEASURED", "n": 0, "cells": {},
                "why": f"{ledger} does not exist", "derived_at": now.isoformat()}
    with ledger.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows += 1
            if rows > max_rows:
                break
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            terminal[str(row.get("terminal_gate"))] += 1
            if row.get("passed") is not True:
                continue
            cell = str(row.get("cell") or "")
            if cell:
                passing[cell] = {"cell": cell, "sym": row.get("sym"),
                                 "family": row.get("family"), "at": row.get("at"),
                                 "graph_id": row.get("graph_id")}
    return {
        "derived": True,
        "status": "MEASURED",
        "promotion_authority": False,
        "note": ("DERIVED VIEW, NOT A CERTIFICATE STORE. These are cell identities the sealed "
                 "judge's verdict ledger records as having passed; the ledger carries no gates "
                 "object, so no row here can satisfy gate_policy.all_ten_pass and nothing may be "
                 "promoted, enrolled or funded from this file. It exists so a session can see "
                 "what the judge found while the canonical seal is waiting on a completed sweep."),
        "source": str(ledger),
        "derived_at": now.isoformat(),
        "ledger_rows_read": rows,
        "terminal_gates": dict(terminal.most_common()),
        "n": len(passing),
        "cells": passing,
    }


def _selector(params: dict[str, Any]) -> str | None:
    """Map a cell's params to the forward engine's window name -- or None, visibly.

    The sealed judge's own `_selector`, rule for rule: the default family session
    (`range_start=7`, or no window keys at all) IS "asia", a named window wins outright, and a
    parameterisation matching no known window returns None so that no shadow_spec is built for
    it. A certificate whose selector cannot be named cannot be enrolled, and guessing one is the
    NO-SPEC defect the refusal below exists to stop.
    """
    if params.get("window") in WINDOWS_KNOWN:
        return str(params["window"])
    keys = {k: params[k] for k in ("range_start", "range_end", "signal_at") if k in params}
    if not keys or keys == {"range_start": 7}:
        return "asia"
    for name, w in WINDOWS_KNOWN.items():
        if all(w.get(k) == v for k, v in keys.items()):
            return name
    return None


def _identity_rules() -> tuple[Any, Any] | None:
    """(`frontier_identity.cell_id`, `external_gauntlet.timeframe_of`), or None when unreachable.

    IMPORTED, NEVER RE-IMPLEMENTED, and this one is not a style preference. The identity is a
    sha256 over the params dict and `timeframe_of` consults a per-family PINNED map inside the
    sealed judge, so a second copy that disagreed about ONE family would match no cell at all and
    report the entire recovery as `params_unrecoverable` -- a wrong answer wearing a
    measurement's clothes. None is UNMEASURED and recovers nothing (L1.28a).

    The import is LAZY because it pulls numpy, pandas and `mt5desk` behind it: an ordinary pass,
    where the judge republished and there is nothing stranded, must not pay for it.
    """
    for path in (DESK / "research", DESK / "scripts", DESK, ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    try:
        from frontier_identity import cell_id
    except ImportError:                                  # pragma: no cover - import-context dep
        try:
            from research.frontier_identity import cell_id  # type: ignore[no-redef]
        except ImportError:
            return None
    try:
        import external_gauntlet as _eg  # type: ignore[import-not-found]
    except Exception:                                    # pragma: no cover - heavy optional dep
        return None
    tf = getattr(_eg, "timeframe_of", None)
    return (cell_id, tf) if callable(tf) else None


def _docket_cell(row: dict[str, Any], cell_id: Any, timeframe_of: Any) -> tuple[str, dict] | None:
    """(cell id, params) for one docket row, normalised EXACTLY as the sealed judge normalises it.

    `external_gauntlet.main` groups the docket by `(sym, chart, family, params)` and the chart is
    folded into `params` when the row carries it and it is not H1. Getting this wrong is silent:
    the digest simply does not match and the cell reads as unrecoverable. The rule is pinned
    against the sealed source by `test_canon_recovers_a_killed_sweep`.
    """
    sym = row.get("symbol")
    fam = row.get("family")
    if not sym or not fam:
        return None
    params = dict(row.get("params") or {})
    row_tf = str(row.get("timeframe") or "").upper()
    if row_tf and row_tf != "H1" and "timeframe" not in params:
        params["timeframe"] = row_tf
    cell = {"sym": sym, "family": fam, "params": params,
            "timeframe": timeframe_of(params, str(fam))}
    return str(cell_id(cell)), params


def docket_params(wanted: set[str], docket: Path = DOCKET,
                  budget_s: float = RECOVERY_BUDGET_SEC) -> tuple[dict[str, dict[str, Any]], str]:
    """({cell id: params}, status) for `wanted`, streamed out of the docket.

    WHY STREAMED. `external_survivors.json` is a 440 MB JSON array on the trading box and this
    organ runs on the box that holds the live terminal; `json.loads` on it would be gigabytes of
    Python objects inside a leg with a four-minute cap. `raw_decode` at an OFFSET into a sliding
    buffer reads one top-level object at a time, so the resident cost is one candidate plus the
    chunk, whatever the file's size.

    THE OFFSET IS NOT A MICRO-OPTIMISATION. The obvious spelling, `buf = buf[end:]`, copies the
    whole remaining buffer once per object: measured on the box, 583,398 rows took 905 seconds
    that way and the scan was quadratic in the chunk size, not linear in the file. The same walk
    with an index is bounded by the parse itself.

    It stops the instant every wanted cell is found -- a killed sweep's passing set is single
    digits -- and on exhausting `budget_s` it returns what it has with status BUDGET_EXHAUSTED.
    That is a partial answer, and the caller REFUSES the cells it could not price rather than
    sealing them with guessed params.
    """
    found: dict[str, dict[str, Any]] = {}
    if not wanted:
        return found, "NOTHING_WANTED"
    if not docket.exists():
        return found, "NO_DOCKET"
    rules = _identity_rules()
    if rules is None:
        return found, "NO_IDENTITY_RULE"
    cell_id, timeframe_of = rules
    deadline = time.monotonic() + max(0.0, float(budget_s))
    decoder = json.JSONDecoder()
    buf = ""
    pos = 0
    rows = 0
    try:
        with docket.open("r", encoding="utf-8", errors="replace") as handle:
            ch = handle.read(1)
            while ch and ch.isspace():
                ch = handle.read(1)
            if ch != "[":
                return found, "DOCKET_NOT_AN_ARRAY"
            while True:
                if rows % 256 == 0 and time.monotonic() > deadline:
                    return found, "BUDGET_EXHAUSTED"
                while pos < len(buf) and (buf[pos].isspace() or buf[pos] == ","):
                    pos += 1
                if pos >= len(buf) or buf[pos] == "]":
                    if pos < len(buf):
                        return found, "EXHAUSTED_DOCKET"
                    chunk = handle.read(_DOCKET_CHUNK)
                    if not chunk:
                        return found, "EXHAUSTED_DOCKET"
                    buf, pos = buf[pos:] + chunk, 0
                    continue
                try:
                    obj, end = decoder.raw_decode(buf, pos)
                except ValueError:
                    chunk = handle.read(_DOCKET_CHUNK)
                    if not chunk:
                        return found, "EXHAUSTED_DOCKET"
                    buf, pos = buf[pos:] + chunk, 0
                    continue
                pos = end
                rows += 1
                if isinstance(obj, dict):
                    try:
                        hit = _docket_cell(obj, cell_id, timeframe_of)
                    except Exception:
                        hit = None
                    if hit is not None and hit[0] in wanted and hit[0] not in found:
                        found[hit[0]] = hit[1]
                        if len(found) == len(wanted):
                            return found, "ALL_FOUND"
    except OSError as exc:
        return found, f"UNREADABLE ({type(exc).__name__})"


def recover_from_gate_output(gates: Path = GATE_OUTPUT, report: Path = REPORT,
                             seal: Path = SEAL, docket: Path = DOCKET,
                             budget_s: float = RECOVERY_BUDGET_SEC) -> dict[str, Any]:
    """Rows the judge EVALUATED and was killed before writing. Never a gate, never a threshold.

    Returns the recovery record; `rows` holds candidate survivor rows for `publish` to merge under
    exactly the refusals a republished row faces. Every verdict the judge passed is accounted for
    by name in `refused`, so an empty recovery states WHY rather than reading as "nothing passed".
    """
    try:
        from gate_policy import ATTESTATION, all_ten_pass
    except ImportError:                                  # pragma: no cover - import-context dep
        from research.gate_policy import ATTESTATION, all_ten_pass  # type: ignore[no-redef]

    now = datetime.now(UTC)
    out: dict[str, Any] = {"gate_output": str(gates), "rows": {},
                           "refused": {}, "recovered_at": now.isoformat()}
    if not gates.exists():
        out.update(status="NO_GATE_OUTPUT",
                   why=f"{gates.name} is absent: this box has no completed gate evaluation to "
                       f"recover from. That is not a claim that nothing passed.")
        return out

    # THE CHEAP QUESTION FIRST. The gate output is 88 MB on the box and `json.loads` on it is a
    # gigabyte of objects and most of a minute -- worth paying to rescue a sweep, and pure waste
    # on an hour where the judge finished. A report whose sweep stamp is LATER than the moment
    # the gate file was written is positive evidence that the judge got past it, so the parse is
    # skipped. Only positive evidence skips: an unreadable stamp, an unreadable mtime or a report
    # older than the file all fall through and read it (L1.28a).
    gate_mtime = _mtime(gates)
    out["gate_mtime"] = gate_mtime
    doc_report_head = _read(report)
    if gate_mtime and str(doc_report_head.get("swept_at") or "") > str(gate_mtime):
        out.update(status="JUDGE_REPUBLISHED", report_swept_at=doc_report_head.get("swept_at"),
                   why=f"the survivor report's sweep stamp ({doc_report_head.get('swept_at')}) is "
                       f"later than the moment {gates.name} was written ({gate_mtime}), so the "
                       f"judge got past its own gate write and nothing is stranded")
        return out

    doc = _read(gates)
    if not doc:
        out.update(status="UNREADABLE_GATE_OUTPUT",
                   why=f"{gates.name} exists ({gates.stat().st_size} bytes) but does not parse; a "
                       f"half-written 88 MB report is exactly what a kill mid-write leaves")
        return out

    swept = doc.get("swept_at")
    out.update(gate_swept_at=swept,
               gate_survivors_passing_all=doc.get("survivors_passing_all"),
               gate_n_judged=doc.get("n_judged"), gate_n_cells=doc.get("n_cells"))
    doc_report = doc_report_head
    report_swept = doc_report.get("swept_at")
    out["report_swept_at"] = report_swept
    # THE JUDGE FINISHED. Its own write is the authority and there is nothing stranded; running
    # a 440 MB docket scan on an ordinary pass would be the cost with none of the benefit.
    if report_swept and swept and str(report_swept) >= str(swept):
        out.update(status="JUDGE_REPUBLISHED", why="the survivor report is at least as new as the "
                                                   "gate output, so no evaluation is stranded")
        return out

    # A SUPERSEDED CHARGE IS NOT THIS POLICY'S VERDICT. See the module docstring.
    #
    # THE CENSUS IS TAKEN FIRST AND THE REFUSAL IS APPLIED AFTER, and the order is the point. An
    # early return here would publish "REFUSED_SUPERSEDED_CHARGE" and NOTHING ELSE -- so the
    # measurement that the sealed judge has been stamping an ELEVENTH stage (`swap_cost`, added
    # 2026-09-14) onto every verdict, which `all_ten_pass` refuses as an exact tuple match, would
    # sit behind a different refusal and never be counted. A blocker hidden behind another
    # blocker is the shape this whole file exists to end. So: everything is measured, and the
    # charge decides only whether a measured row may be SEALED.
    spec_basis = str(ATTESTATION.get("trial_count_basis") or "")
    gate_basis = str(doc.get("trial_count_basis") or "")
    out["gate_trial_basis"] = gate_basis
    out["spec_trial_basis"] = spec_basis
    out["gate_n_trials"] = doc.get("n_trials")
    superseded = bool(not gate_basis or gate_basis != spec_basis)

    seal_doc = _read(seal)
    standing = seal_doc.get("survivors")
    standing = standing if isinstance(standing, dict) else {}
    retired = seal_doc.get("retired_certificates")
    retired = retired if isinstance(retired, dict) else {}
    _ev = seal_doc.get("unrunnable_evicted")
    evicted = set(_ev) if isinstance(_ev, list) else set()

    refused: Counter[str] = Counter()
    extra_gates: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    for v in doc.get("verdicts") or []:
        if not isinstance(v, dict) or v.get("passed") is not True:
            continue
        key = f"external.{v.get('cell')}"
        if key in standing:
            refused["already_sealed"] += 1
            continue
        if key in retired:
            refused["retired"] += 1
            continue
        if key in evicted:
            refused["unrunnable_evicted"] += 1
            continue
        stages = v.get("stages")
        if not all_ten_pass(stages):
            # NAME THE MISMATCH. A verdict the judge passed but `all_ten_pass` refuses is either
            # a partial record or one carrying a stage the policy does not list, and the two are
            # different problems. Counting them together is how a silent blackout looks healthy.
            if isinstance(stages, dict):
                try:
                    from gate_policy import GATES
                except ImportError:                      # pragma: no cover - import-context dep
                    from research.gate_policy import GATES  # type: ignore[no-redef]
                for name in stages:
                    if name not in GATES:
                        extra_gates[str(name)] += 1
                refused["extra_gate_not_in_policy" if any(n not in GATES for n in stages)
                        else "not_all_ten_pass"] += 1
            else:
                refused["no_stages_record"] += 1
            continue
        candidates.append(v)

    out["gate_passed_rows"] = sum(1 for v in doc.get("verdicts") or []
                                  if isinstance(v, dict) and v.get("passed") is True)
    out["extra_gates_seen"] = dict(extra_gates.most_common())
    out["refused"] = dict(refused)
    if superseded:
        refused["superseded_charge"] += len(candidates)
        out.update(status="REFUSED_SUPERSEDED_CHARGE", rows={}, refused=dict(refused),
                   why=(f"the gate output was judged under trial basis {gate_basis!r} and the "
                        f"spec in force now reads {spec_basis!r}. Sealing those verdicts would "
                        f"stamp the current attestation onto rows judged under a different bar. "
                        f"They are not lost: the next completed sweep re-judges them under the "
                        f"policy that is actually in force. The census above is unaffected and "
                        f"names every OTHER blocker in the same artifact."))
        return out
    if not candidates:
        out.update(status="NOTHING_TO_RECOVER", refused=dict(refused),
                   why="every verdict the judge passed is already sealed, already retired, or "
                       "does not carry the canonical ten-gate record")
        return out

    wanted = {str(v.get("cell")) for v in candidates}
    t0 = time.monotonic()
    params_by_cell, scan = docket_params(wanted, docket, budget_s)
    out["docket_scan"] = {"status": scan, "wanted": len(wanted), "found": len(params_by_cell),
                          "seconds": round(time.monotonic() - t0, 2), "docket": str(docket)}

    rows: dict[str, dict[str, Any]] = {}
    for v in candidates:
        cell = str(v.get("cell"))
        key = f"external.{cell}"
        if cell not in params_by_cell:
            # NEVER `{}` AS A STAND-IN. See the module docstring's third refusal.
            refused["params_unrecoverable"] += 1
            continue
        params = dict(params_by_cell[cell])
        sel = _selector(params)
        if sel is None:
            refused["no_selector"] += 1
            continue
        row: dict[str, Any] = {
            "hunt": "external_discoveries",
            "cell": cell,
            "sym": v.get("sym"),
            "days": v.get("days"),
            "gates": v.get("stages"),
            "gated_at": swept,
            "shadow_spec": {"symbol": v.get("sym"), "selector": sel,
                            "family": v.get("family", "session_range_breakout"),
                            "is_universe": True, "hunt": "external_discoveries",
                            "condition": None, "params": params},
            # THE ROUND TRIP IS VISIBLE OR IT DID NOT HAPPEN. A row that entered the canon by any
            # door but the judge's own write says so, on the row, for ever.
            "recovered_from_gate_output": {
                "gate_output": str(gates.relative_to(DESK)) if gates.is_relative_to(DESK)
                else str(gates),
                "gate_swept_at": swept,
                "why": ("the sealed judge evaluated all ten gates and was killed before it wrote "
                        "UNIVERSAL_SURVIVORS.json; no gate was re-run and none was softened"),
                "recovered_at": now.isoformat(),
                "recovered_by": "research/canon_publication.py",
            },
        }
        rows[key] = row

    out.update(status="RECOVERED" if rows else "NOTHING_RECOVERABLE", rows=rows,
               refused=dict(refused), n_recovered=len(rows),
               attestation_source="gate_policy.ATTESTATION (the spec the verdicts were judged "
                                  "under, checked equal above)")
    if not rows:
        out["why"] = ("the judge's evaluation is on disk and every passing verdict in it was "
                      "refused for a named reason above -- none was dropped silently")
    return out


def publish(report: Path = REPORT, seal: Path = SEAL,
            recovered: dict[str, Any] | None = None) -> dict[str, Any]:
    """Seal the judge's latest completed sweep into the canonical store, atomically.

    Returns the publication record. The seal is written only when the report carries the exact
    ten-gate attestation; anything else leaves it untouched and says why, because a canonical
    store overwritten from an unattested source is the certifier wipe with a different cause.
    """
    try:
        from gate_policy import ATTESTATION, all_ten_pass, is_exact_policy
        from survivor_publication import unrunnable_reason
    except ImportError:                                  # pragma: no cover - import-context dep
        from research.gate_policy import (  # type: ignore[no-redef]
            ATTESTATION,
            all_ten_pass,
            is_exact_policy,
        )
        from research.survivor_publication import unrunnable_reason  # type: ignore[no-redef]

    now = datetime.now(UTC)
    doc_report = _read(report)
    doc_seal = _read(seal)
    seal_before = doc_seal.get("survivors")
    seal_before = dict(seal_before) if isinstance(seal_before, dict) else {}
    retired = doc_seal.get("retired_certificates")
    retired = retired if isinstance(retired, dict) else {}
    # THE EVICTION RECORD. `certificate_hygiene` moves rows the enrolment engine can never run to
    # reports/UNIVERSAL_SURVIVORS_UNRUNNABLE.json and lists their keys here. They still stand in
    # the judge's report -- eviction is not revocation -- so without this the seal re-admits every
    # one of them on every publication.
    _ev = doc_seal.get("unrunnable_evicted")
    evicted = set(_ev) if isinstance(_ev, list) else set()

    record: dict[str, Any] = {
        "published_at": now.isoformat(),
        "publisher": "desks/mt5/research/canon_publication.py",
        "judge": "desks/mt5/scripts/external_gauntlet.py (sealed; never edited)",
        "report": str(report),
        "report_swept_at": doc_report.get("swept_at"),
        "report_mtime": _mtime(report),
        "report_n": doc_report.get("n"),
        "seal": str(seal),
        "seal_swept_at_before": doc_seal.get("swept_at"),
        "seal_n_before": len(seal_before),
        "seal_lag_hours_before": _age_hours(doc_seal.get("swept_at"), now),
        "run_lag_hours": _age_hours(doc_report.get("swept_at"), now),
        "funnel": _funnel(),
    }

    # THE RECOVERED ROWS ARE A SECOND SOURCE, NOT A SECOND AUTHORITY. They come from the sealed
    # judge's own completed gate evaluation (see `recover_from_gate_output`) and they face EVERY
    # refusal below that a republished row faces -- retirement, eviction, all_ten_pass, the
    # unrunnable predicate -- through the same loop rather than a parallel one.
    recovered = dict(recovered or {})
    record["recovered_offered"] = len(recovered)
    attested_report = bool(doc_report) and bool(is_exact_policy(doc_report.get("gate_policy")))
    if not doc_report and not recovered:
        record.update(status="NO_REPORT", sealed=False, admitted=0,
                      why=(f"{report} is absent or unreadable. The judge has not republished; the "
                           "seal is left exactly as it stands and a derived view is published "
                           "instead."))
        return record
    if not attested_report and not recovered:
        record.update(status="UNATTESTED_REPORT", sealed=False, admitted=0,
                      why=("the judge's report does not carry the exact ten-gate attestation, so "
                           "nothing in it may enter the canonical store. The seal is untouched."))
        return record

    survivors = doc_report.get("survivors") if attested_report else {}
    survivors = survivors if isinstance(survivors, dict) else {}
    merged = dict(seal_before)
    admitted: list[str] = []
    admitted_recovered: list[str] = []
    refused_rows: Counter[str] = Counter()
    for key, row in {**survivors, **recovered}.items():
        if not isinstance(row, dict):
            refused_rows["not_a_row"] += 1
            continue
        if key in retired:
            # RETIREMENT IS NOT OVERTURNED BY A REPUBLICATION. The retirers own that record and
            # the judge's own restore loop is the only thing that may bring a row back.
            refused_rows["retired"] += 1
            continue
        if key in evicted:
            # NEITHER IS AN EVICTION, AND THIS ONE WAS MEASURED THE FIRST TIME THIS ORGAN RAN.
            # Six keys were admitted on the first pass and ALL SIX were rows `certificate_hygiene`
            # had already moved to reports/UNIVERSAL_SURVIVORS_UNRUNNABLE.json: they pass all ten
            # gates and cannot be enrolled, which is precisely why counting them inflated the
            # desk's belief about its own edge. A republisher that re-admits them is a second pen
            # undoing the first one every hour, quietly, while reporting +6 certificates.
            refused_rows["unrunnable_evicted"] += 1
            continue
        if not all_ten_pass(row.get("gates")):
            refused_rows["not_all_ten_pass"] += 1
            continue
        why_unrunnable = unrunnable_reason(row)
        if why_unrunnable:
            # THE SHARED JUDGE, NOT A LIST LOOKUP. `unrunnable_evicted` is the RECORD of past
            # evictions; this is the RULE, and it is the one all four certificate pens already
            # use (research/survivor_publication.unrunnable_reason). Without it a row that became
            # unenrollable AFTER the last hygiene pass would enter the seal and wait an hour to
            # be evicted again.
            refused_rows["unrunnable_spec"] += 1
            continue
        if key not in merged:
            admitted.append(key)
            if key in recovered:
                admitted_recovered.append(key)
        merged[key] = row

    # THE REFUSAL CENSUS IS A MEASUREMENT AND IS NEVER WITHHELD BY AN EARLY RETURN. A publication
    # that refused every row and says only "REFUSED_EMPTY" is the shape that hides a judge quietly
    # emitting rows the seal cannot take -- the count, by named reason, is the thing that says so.
    record["refused_rows"] = dict(refused_rows)
    if len(merged) < len(seal_before):
        # Unreachable by construction (merged starts as a copy of the seal) and asserted anyway:
        # the never-shrink law is the one this desk has actually lost certificates to.
        record.update(status="REFUSED_SHRINK", sealed=False, admitted=0,
                      why=f"merge would shrink the seal {len(seal_before)} -> {len(merged)}")
        return record
    if not merged:
        record.update(status="REFUSED_EMPTY", sealed=False, admitted=0,
                      why="an empty canon is never published; an empty docket does not revoke "
                          "past verdicts")
        return record

    # THE STAMP FOLLOWS THE EVIDENCE, AND NEVER GOES BACKWARD. A recovered row was evaluated at
    # the gate output's `swept_at`, which is NEWER than the report the killed sweep left behind --
    # that is the entire point of recovering it, so the seal must say so.
    stamps = [str(doc_report.get("swept_at") or "")] if attested_report else []
    stamps += [str((row.get("recovered_from_gate_output") or {}).get("gate_swept_at") or "")
               for key, row in merged.items() if key in recovered]
    stamps.append(str(doc_seal.get("swept_at") or ""))
    swept_at = max(s for s in stamps) if any(stamps) else doc_report.get("swept_at")

    doc_new = dict(doc_seal)
    for key in CARRIED:
        if key in doc_seal:
            doc_new[key] = doc_seal[key]
    doc_new.update({
        "n": len(merged),
        "survivors": merged,
        # THE ATTESTATION OF THE POLICY THE ROWS WERE JUDGED UNDER. The report's when it carries
        # one; otherwise the current spec's, which recovery has already checked the gate output's
        # own trial basis equal to -- it refuses outright when they differ.
        "gate_policy": doc_report.get("gate_policy") if attested_report else ATTESTATION,
        "note": "UNIVERSAL 10-GATE PASS ONLY.",
        # THE TIME OF THE RUN THAT PRODUCED IT, which is the judge's stamp and not this organ's.
        # `published_at` says when the seal was written; `swept_at` says when the evidence in it
        # was gathered, and conflating the two is how a stale store looked fresh by mtime.
        "swept_at": swept_at,
        "published_at": now.isoformat(),
        "published_by": "research/canon_publication.py",
        "published_from": str(report.relative_to(DESK)) if report.is_relative_to(DESK)
        else str(report),
    })
    _atomic_json(seal, doc_new)
    record.update(status="SEALED", sealed=True, admitted=len(admitted),
                  admitted_keys=admitted[:24], refused_rows=dict(refused_rows),
                  admitted_recovered=len(admitted_recovered),
                  admitted_recovered_keys=admitted_recovered[:24],
                  seal_n_after=len(merged), seal_swept_at_after=swept_at,
                  atomic="tempfile + fsync + os.replace in the destination directory")
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--seal", type=Path, default=SEAL)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--gates", type=Path, default=GATE_OUTPUT)
    ap.add_argument("--docket", type=Path, default=DOCKET)
    ap.add_argument("--recovery-budget-s", type=float, default=RECOVERY_BUDGET_SEC)
    ap.add_argument("--no-recovery", action="store_true",
                    help="publish from the judge's report alone; do not read the gate output")
    args = ap.parse_args(argv)

    # RECOVERY RUNS FIRST because its output is an INPUT to the one merge. A second write would
    # be a second pen on the canonical store, which is the defect this whole file was written to
    # end -- so the stranded rows go through `publish`'s refusals with everything else.
    if args.no_recovery:
        recovery: dict[str, Any] = {"status": "SKIPPED", "rows": {},
                                    "why": "--no-recovery was passed"}
    else:
        recovery = recover_from_gate_output(args.gates, args.report, args.seal, args.docket,
                                            args.recovery_budget_s)
    record = publish(args.report, args.seal, recovered=recovery.get("rows") or {})
    record["recovery"] = {k: v for k, v in recovery.items() if k != "rows"}
    if not record.get("sealed"):
        # THE JUDGE DID NOT REPUBLISH. Say so precisely and publish the derived view, which is
        # labelled derived on every level and carries no promotion authority.
        view = derive_from_ledger()
        _atomic_json(DERIVED, view)
        record["derived_view"] = {"path": str(DERIVED), "n": view.get("n"),
                                  "status": view.get("status"),
                                  "why": ("the sealed judge did not republish this pass, so the "
                                          "canonical seal stands and this view is what the "
                                          "verdict ledger shows instead")}
    _atomic_json(args.out, record)
    before = record.get("seal_n_before")
    after = record.get("seal_n_after", before)
    print(f"canon publication: {record['status']} seal {before} -> {after} "
          f"(+{record.get('admitted', 0)}); report swept_at {record.get('report_swept_at')}; "
          f"seal lag before {record.get('seal_lag_hours_before')}h -> {args.out.name}")
    print(f"  recovery from the gate output: {recovery.get('status')} -- "
          f"{recovery.get('gate_passed_rows', 0)} verdict(s) the judge passed, "
          f"{len(recovery.get('rows') or {})} rebuilt, "
          f"{record.get('admitted_recovered', 0)} sealed; "
          f"refused {recovery.get('refused') or {}}"
          + (f"; {recovery.get('why')}" if recovery.get("why") else ""))
    if args.json:
        print(json.dumps(record, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

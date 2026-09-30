"""The rejection ledger: every kill carries a reason code, and the codes are the headline metric.

MT5_GLOBAL_MINING_V1 measures REJECTION, not cell count. A pipeline that reports how many cells
it mined rewards volume; one that reports why each cell died says where the edge is not, which
is the only thing a mining machine learns from.

A rejection without a code cannot be written: `RejectionLedger.reject` raises on an unknown
code, so "rejected, reason unknown" is not a state this ledger can hold. Codes from other lanes
(the Asia-gap thread's rejection-throughput work) are accepted through `EXTERNAL_ALIASES`, which
maps them onto these nine rather than growing a second vocabulary.
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any


class Reason(StrEnum):
    LEAKAGE_LOOKAHEAD = "LEAKAGE_LOOKAHEAD"
    LEAKAGE_REVISION = "LEAKAGE_REVISION"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    DUPLICATE_MECHANISM = "DUPLICATE_MECHANISM"
    NO_ECONOMIC_MECHANISM = "NO_ECONOMIC_MECHANISM"
    COST_EXCEEDS_EDGE = "COST_EXCEEDS_EDGE"
    REGIME_FRAGILE = "REGIME_FRAGILE"
    FAILS_PREREG = "FAILS_PREREG"
    EVALUATOR_REJECT = "EVALUATOR_REJECT"


REASON_CODES: tuple[str, ...] = tuple(r.value for r in Reason)

#: Pipeline stages, in order. A rejection names the stage that made it.
STAGES: tuple[str, ...] = ("fetch", "pit", "extract", "dedup", "compile", "preregister",
                           "gauntlet")

#: Stages whose kills count toward `rejection_rate = rejected / evaluated`. Earlier kills are
#: reported by reason too, but they never reached the evaluator, so folding them into the rate
#: would flatter the screen.
EVALUATION_STAGES: frozenset[str] = frozenset({"preregister", "gauntlet"})

#: Other lanes' codes -> ours. Seeded with the gauntlet's own vocabulary and the obvious
#: synonyms; the Asia-gap thread's codes are added here when its ledger lands.
EXTERNAL_ALIASES: dict[str, Reason] = {
    "LOOKAHEAD": Reason.LEAKAGE_LOOKAHEAD,
    "PIT_VIOLATION": Reason.LEAKAGE_LOOKAHEAD,
    "REVISION_LEAK": Reason.LEAKAGE_REVISION,
    "TOO_FEW_TRADES": Reason.INSUFFICIENT_SAMPLE,
    "DATA_MISSING": Reason.INSUFFICIENT_SAMPLE,
    "DUPLICATE": Reason.DUPLICATE_MECHANISM,
    "NO_MECHANISM": Reason.NO_ECONOMIC_MECHANISM,
    "NO_ECONOMIC_PRIOR": Reason.NO_ECONOMIC_MECHANISM,
    "COST": Reason.COST_EXCEEDS_EDGE,
    "FRAGILE": Reason.REGIME_FRAGILE,
    "PREREG_MISMATCH": Reason.FAILS_PREREG,
}

#: The sealed gauntlet's terminal gates -> reason. Every gate it can name maps somewhere; a gate
#: missing here maps to EVALUATOR_REJECT (the evaluator said no) rather than to nothing.
GATE_REASON: dict[str, Reason] = {
    "economic_prior": Reason.NO_ECONOMIC_MECHANISM,
    "symbol_eligibility": Reason.EVALUATOR_REJECT,
    "stress_costs": Reason.COST_EXCEEDS_EDGE,
    "swap_cost": Reason.INSUFFICIENT_SAMPLE,      # fail-closed: no swap schedule to charge
    "expected_value": Reason.COST_EXCEEDS_EDGE,
    "walk_forward": Reason.REGIME_FRAGILE,
    "cpcv": Reason.REGIME_FRAGILE,
    "pbo": Reason.REGIME_FRAGILE,
    "deflated_sharpe": Reason.EVALUATOR_REJECT,
    "reality_check_spa": Reason.EVALUATOR_REJECT,
    "in_sample_screen": Reason.EVALUATOR_REJECT,
    "lockbox": Reason.INSUFFICIENT_SAMPLE,        # fail-closed: the evidence is missing
    "observations": Reason.INSUFFICIENT_SAMPLE,
    "lookahead": Reason.LEAKAGE_LOOKAHEAD,
}

#: The Asia-gap thread's kill classes (`rejection_throughput.py`, #120), keyed by terminal gate.
#: Only `confident_kill` counts toward kills per day; `fail_closed` means evidence was missing,
#: `screen_reject` is a pre-test screen, and anything else is `unconfident`. The class rides on
#: each gauntlet rejection row beside the reason code, so both lanes read one ledger.
KILL_CLASS: dict[str, str] = {
    **dict.fromkeys(("in_sample_screen", "deflated_sharpe", "pbo", "reality_check_spa", "cpcv",
                     "walk_forward", "stress_costs", "expected_value"), "confident_kill"),
    **dict.fromkeys(("lockbox", "swap_cost"), "fail_closed"),
    **dict.fromkeys(("economic_prior", "symbol_eligibility"), "screen_reject"),
}
KILL_CLASSES: tuple[str, ...] = ("confident_kill", "fail_closed", "screen_reject", "unconfident")


def kill_class(gate: str) -> str:
    return KILL_CLASS.get(str(gate or ""), "unconfident")


#: Downstream statuses the gauntlet writes for cells it did NOT judge. Only the data-missing one
#: is a verdict about the cell; the others are deferrals and leave the cell EVALUATING.
_NOT_RUN_REASON: dict[str, Reason] = {
    "NOT_RUN_DATA_MISSING": Reason.INSUFFICIENT_SAMPLE,
    "NOT_RUN_UNTRADEABLE_SYMBOL": Reason.EVALUATOR_REJECT,
    "NOT_RUN_TERMINAL_GATE_1_REJECT": Reason.NO_ECONOMIC_MECHANISM,
}


class UnknownReasonError(ValueError):
    """A rejection was attempted with a code outside the ledger's vocabulary."""


def normalise(code: str) -> Reason:
    """Our code, or an aliased external one. Anything else raises: no uncoded rejections."""
    c = str(code or "").strip().upper()
    if c in REASON_CODES:
        return Reason(c)
    if c in EXTERNAL_ALIASES:
        return EXTERNAL_ALIASES[c]
    raise UnknownReasonError(f"unknown rejection reason {code!r}; allowed: {REASON_CODES}")


def reason_for_verdict(verdict: Mapping[str, Any]) -> tuple[Reason | None, str]:
    """Map one gauntlet verdict row to (reason, gate). (None, gate) means survived or deferred.

    `passed` is a survivor. A named terminal gate is a kill with that gate's reason. A NOT_RUN
    status that is not a verdict (budget deferral, modifier) returns (None, "DEFERRED")."""
    if verdict.get("passed"):
        return None, "PASSED"
    gate = str(verdict.get("terminal_gate") or "")
    status = str(verdict.get("downstream_status") or "")
    if status in _NOT_RUN_REASON and (not gate or gate == "UNKNOWN"):
        return _NOT_RUN_REASON[status], status
    if not gate or gate in ("UNKNOWN", "PASSED"):
        return None, "DEFERRED"
    return GATE_REASON.get(gate, Reason.EVALUATOR_REJECT), gate


@dataclass(frozen=True)
class Rejection:
    subject_id: str            # cell_id, or record_id for a record killed before it held a cell
    subject_kind: str          # "cell" | "record"
    reason: str
    stage: str
    at: str
    detail: str = ""
    source_id: str = ""
    duplicate_of: str = ""
    kill_class: str = ""       # gauntlet rows only: see KILL_CLASS


class RejectionLedger:
    """Append-only JSONL. One row per kill; `counts` reads it back by reason and stage."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def reject(self, subject_id: str, reason: str, stage: str, *, detail: str = "",
               subject_kind: str = "cell", source_id: str = "", duplicate_of: str = "",
               kill_class: str = "", now: datetime | None = None) -> Rejection:
        code = normalise(reason)
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; allowed: {STAGES}")
        if not subject_id:
            raise ValueError("a rejection needs the id of what it rejected")
        row = Rejection(subject_id=subject_id, subject_kind=subject_kind, reason=code.value,
                        stage=stage, at=(now or datetime.now(tz=UTC)).isoformat(),
                        detail=detail[:500], source_id=source_id, duplicate_of=duplicate_of,
                        kill_class=kill_class)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return row

    def rows(self) -> Iterable[dict[str, Any]]:
        try:
            with self.path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict):
                        yield row
        except OSError:
            return

    def counts(self, since: datetime | None = None, *, stages: Iterable[str] | None = None
               ) -> dict[str, int]:
        """Rejections by reason (every code present, zero included) since `since`."""
        want = set(stages) if stages is not None else None
        out = dict.fromkeys(REASON_CODES, 0)
        for r in self.rows():
            if want is not None and r.get("stage") not in want:
                continue
            if since is not None and not _after(str(r.get("at") or ""), since):
                continue
            code = str(r.get("reason") or "")
            if code in out:
                out[code] += 1
        return out

    def kill_classes(self, since: datetime | None = None) -> dict[str, int]:
        """Gauntlet rejections by the Asia lane's kill class (every class present)."""
        out = dict.fromkeys(KILL_CLASSES, 0)
        for r in self.rows():
            if r.get("stage") != "gauntlet":
                continue
            if since is not None and not _after(str(r.get("at") or ""), since):
                continue
            k = str(r.get("kill_class") or "unconfident")
            out[k if k in out else "unconfident"] += 1
        return out

    def daily_report(self, now: datetime | None = None) -> dict[str, Any]:
        t = now or datetime.now(tz=UTC)
        since = t - timedelta(hours=24)
        return {"window": "24h", "since": since.isoformat(),
                "by_reason_all_stages": self.counts(since),
                "by_reason_evaluation": self.counts(since, stages=EVALUATION_STAGES)}


def _after(iso: str, since: datetime) -> bool:
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return t >= since

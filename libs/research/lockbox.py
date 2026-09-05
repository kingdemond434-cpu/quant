"""A lockbox the researcher cannot read, and a reviewer that has never heard of the candidate.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

    "Researcher: cannot read lockbox dataset, cannot query it, cannot request statistics from it.
     Only PromotionService can execute a frozen candidate against it."

A lockbox that the search can query is not a lockbox. It becomes another training set the moment
anyone is allowed to ask it a question and then change something in response -- and the change
does not have to be deliberate. A researcher who learns that lockbox performance is weak and goes
back to adjust a parameter has trained on the holdout as surely as if they had fitted to it.

SO THE ONLY OPERATION IS EVALUATE-ONCE. `LockboxService.evaluate` runs a FROZEN artifact and
returns a fixed, predetermined metric set. There is no read, no sample, no summary statistic, no
"just tell me the Sharpe". A second evaluation of the same fingerprint returns the FIRST result
and records the repeat, because re-running after a change is exactly how a holdout is consumed --
and the desk would otherwise have no way of noticing it happened.

THE REVIEWER GETS FROZEN FACTS AND NO STORY. It never sees "this is our best candidate", who
built it, how long it took, or what anyone hopes. It receives the artifact's technical content and
one instruction: find a fatal defect. It may return PASS, FAIL or NEEDS_MORE_EVIDENCE, and it
may not modify the candidate, lower a threshold, widen a drawdown allowance, or delete a failed
test. A reviewer able to change the bar is not a reviewer; it is a second researcher.

WHY THE REVIEWER MUST BE STRUCTURALLY BLIND rather than merely instructed to be fair: this desk
spent today finding four defects that had survived for weeks precisely because whoever wrote the
component also judged whether it worked. `strip_advocacy` removes the persuasive content
mechanically, so blindness does not depend on anybody's discipline.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: The ONLY metrics a lockbox evaluation may return. Predetermined so nobody can go fishing for
#: the one number that flatters a candidate, and fixed in code so widening the set is a visible
#: diff rather than an argument in a meeting.
PERMITTED_METRICS = ("verdict", "n_trades", "exp_r", "max_dd_r", "sharpe", "t_stat")

#: Verdicts a reviewer may return. There is deliberately no "PASS WITH CHANGES".
REVIEW_VERDICTS = ("PASS", "FAIL", "NEEDS_MORE_EVIDENCE")

#: Phrases that carry advocacy rather than fact. Removed before a reviewer sees anything --
#: mechanical blindness rather than instructed fairness.
_ADVOCACY = re.compile(
    r"\b(best|excellent|amazing|promising|exciting|strong(est)?|our top|flagship|breakthrough|"
    r"we (believe|think|hope|expect)|should work|looks great|confident)\b", re.I)

#: Fields a reviewer is allowed to see. Anything naming an author, a duration, or an expectation
#: is withheld: none of it is evidence, and all of it is persuasion.
_REVIEWABLE_FIELDS = (
    "artifact_id", "hypothesis_id", "semantic_coordinate", "mechanism", "payer",
    "economic_rationale", "falsifiers", "point_in_time_contract", "data_requirements",
    "code_hash", "ast_hash", "config_hash", "data_snapshot", "trial_count_at_birth",
    "stage_results", "failure_class",
)


class LockboxViolation(RuntimeError):
    """An attempt to read, query, or re-evaluate the holdout. Raised, never warned."""


@dataclass
class LockboxService:
    """Owns the holdout. Nothing else may touch the underlying data.

    `data_path` is stored, never returned, and never opened by any method other than the
    evaluator this service calls internally.
    """

    data_path: Path
    ledger_path: Path
    _results: dict[str, dict[str, Any]] = field(default_factory=dict)
    _repeats: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.ledger_path.exists():
            try:
                blob = json.loads(self.ledger_path.read_text("utf-8"))
                self._results = blob.get("results", {})
                self._repeats = blob.get("repeats", [])
            except (OSError, json.JSONDecodeError):
                # A ledger that cannot be read means the desk cannot know what has already been
                # spent against the holdout. Refusing is the only safe answer.
                raise LockboxViolation(
                    f"{self.ledger_path} exists but is unreadable. Without it there is no record "
                    f"of which candidates have already consumed the holdout, and evaluating "
                    f"blindly would silently re-use it.") from None

    def read(self, *_a: Any, **_kw: Any) -> None:
        raise LockboxViolation(
            "the lockbox cannot be read. A holdout anyone can inspect is a training set: knowing "
            "how a candidate scored is enough to change the next one, whether or not that was "
            "the intention. `evaluate` is the only operation.")

    query = sample = describe = statistics = read

    def evaluate(self, artifact: Any, evaluator: Callable[[Any, Path], dict[str, Any]],
                 *, reason: str) -> dict[str, Any]:
        """Run a FROZEN artifact against the holdout, once, returning permitted metrics only.

        A repeat evaluation of the same fingerprint returns the ORIGINAL result and records the
        attempt. That is not a convenience: re-running after an adjustment is precisely how a
        holdout gets consumed, and silently allowing it would leave the desk unable to tell a
        clean lockbox pass from the third attempt at one.
        """
        if not reason or not reason.strip():
            raise LockboxViolation("every lockbox evaluation must cite why it was spent")
        fp = artifact.fingerprint() if hasattr(artifact, "fingerprint") else str(artifact)

        if fp in self._results:
            self._repeats.append({
                "fingerprint": fp, "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "reason": reason,
                "note": ("REPEAT: this fingerprint already consumed the holdout. The original "
                         "result is returned unchanged. If the candidate genuinely changed, its "
                         "fingerprint would differ -- an identical fingerprint means the same "
                         "candidate is being asked twice.")})
            self._flush()
            return {**self._results[fp], "repeat": True}

        raw = evaluator(artifact, self.data_path)
        result = {k: raw.get(k) for k in PERMITTED_METRICS}
        result["evaluated_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
        result["reason"] = reason
        result["repeat"] = False
        withheld = sorted(set(raw) - set(PERMITTED_METRICS))
        if withheld:
            result["withheld_metrics"] = withheld
        self._results[fp] = result
        self._flush()
        return result

    def _flush(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.write_text(json.dumps(
            {"results": self._results, "repeats": self._repeats,
             "note": "append-only record of every holdout evaluation and every repeat attempt"},
            indent=1), "utf-8")

    def integrity(self) -> dict[str, Any]:
        return {"evaluations": len(self._results), "repeat_attempts": len(self._repeats),
                "verdict": "CLEAN" if not self._repeats else "HOLDOUT REUSED",
                "why": ("a repeat means a candidate was asked twice; each one erodes the "
                        "holdout's independence whether or not anything changed in between")}


def strip_advocacy(text: str) -> str:
    """Remove persuasion so the reviewer sees claims, not enthusiasm."""
    return _ADVOCACY.sub("[REDACTED-ADVOCACY]", text or "")


def review_packet(artifact: Any) -> dict[str, Any]:
    """What a fresh-context reviewer is allowed to see: frozen technical facts, no story.

    Authorship, elapsed effort and expectation are withheld -- none of them is evidence, and all
    of them bias a verdict. The reviewer is told what to look for and nothing about who is hoping
    for which answer.
    """
    packet: dict[str, Any] = {}
    for f in _REVIEWABLE_FIELDS:
        v = getattr(artifact, f, None)
        if isinstance(v, str):
            v = strip_advocacy(v)
        elif isinstance(v, (list, tuple)):
            v = [strip_advocacy(x) if isinstance(x, str) else x for x in v]
        packet[f] = v
    packet["_instruction"] = (
        "Find one fatal defect. Attempt to reproduce the result. Construct the strongest placebo "
        "you can. Search for leakage, selection bias, incorrect execution assumptions, "
        "mechanism/code mismatch and hidden redundancy with an existing strategy. You may return "
        "PASS, FAIL or NEEDS_MORE_EVIDENCE. You may NOT modify the candidate, lower a threshold, "
        "widen a drawdown allowance, or remove a failed test.")
    packet["_withheld"] = ("author, elapsed effort, prior expectations, and any statement of how "
                           "promising this is -- none of it is evidence")
    return packet


@dataclass(frozen=True)
class Review:
    verdict: str
    defect: str
    reproduced: bool
    notes: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in REVIEW_VERDICTS:
            raise ValueError(
                f"verdict {self.verdict!r} is not one of {REVIEW_VERDICTS}. There is deliberately "
                f"no 'PASS WITH CHANGES': a reviewer that can negotiate the bar is a second "
                f"researcher, not an independent check.")


def apply_review(artifact: Any, review: Review) -> tuple[bool, str]:
    """Does this review permit the candidate to proceed? Never modifies the candidate.

    NEEDS_MORE_EVIDENCE blocks, exactly like FAIL. It is a different FINDING -- the candidate may
    return with more evidence -- but it is the same DECISION today, and treating it as a soft pass
    would make it the verdict every uncertain reviewer reaches for.
    """
    if review.verdict == "PASS":
        if not review.reproduced:
            return False, ("PASS is refused when the reviewer could not reproduce the result. An "
                           "unreproduced pass certifies that nobody checked, not that it works.")
        return True, "independent reviewer reproduced the result and found no fatal defect"
    if review.verdict == "FAIL":
        return False, f"reviewer found a fatal defect: {review.defect}"
    return False, (f"NEEDS_MORE_EVIDENCE blocks today exactly as FAIL does: {review.defect}. The "
                   f"candidate may return with more evidence; it may not proceed without it.")

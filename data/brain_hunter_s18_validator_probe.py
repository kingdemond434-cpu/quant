"""BRAIN HUNTER s18 -- controlled probe of zhutoutoutousan/worldquant-miner
`generation_two/core/template_validator.py` (Apache-2.0, sha 6a0c9433).

Four measurements, each a claim someone could refute by re-running this file against a
shallow clone of the repo at that sha:

 1. FIXED-POINT of the two deterministic repair functions that the refeed loop arms with
    `max_attempts = 999` ("retry until successful"). If they converge in one pass, the
    remaining 998 attempts recompute an identical string and the loop cannot progress.
 2. COVERAGE of `_aggressive_event_input_fix` over the operators the repo's OWN
    `compiler_knowledge.json` declares event-incompatible.
 3. REACHABILITY of `_classify_error_from_message`: which of the error classes the repo
    builds dedicated fixers for can the classifier actually name? Its output is stored as
    `error_type` metadata on every learned pattern, so an unreachable class is a label
    collapse in the learning loop, not a cosmetic gap.
 4. The `use_ast` default at the repo's only instantiation site (read, not executed here).

Run:  .venv/bin/python data/brain_hunter_s18_validator_probe.py <path-to-clone>
"""
from __future__ import annotations

import json
import logging
import sys
import tempfile
from pathlib import Path

CASES_EVENT = [
    ("rank(close)", "Operator rank does not support event inputs"),
    ("add(anl4_estimate_eps, anl4_actual_eps)", "Operator add does not support event inputs"),
    ("ts_rank(close, 20)", "Operator ts_rank does not support event inputs"),
    # named event-incompatible by the repo's own compiler_knowledge.json rules, absent from
    # the replacement table:
    ("group_rank(close, sector)", "Operator group_rank does not support event inputs"),
    ("winsorize(close, 4)", "Operator winsorize does not support event inputs"),
    ("zscore(close)", "Operator zscore does not support event inputs"),
]
CASES_COUNT = [
    ("ts_corr(close, open, 20)", "Invalid number of inputs : 3, should be exactly 2 input(s)"),
    ("rank(close)", "Invalid number of inputs : 1, should be at least 2 input(s)"),
    ("ts_mean(close, 20)", "Invalid number of inputs : 2, should be exactly 1 input(s)"),
]
# One message per error class the repo ships a dedicated fixer or retry arm for.
CASES_CLASSIFY = [
    "Unknown variable: foo",
    "Invalid field xyz",
    "Syntax error near )",
    "Type mismatch",
    "Operator add does not support event inputs",
    "Invalid number of inputs : 2, should be exactly 1 input(s)",
    "Unexpected character ',' at position 12",
    "Operator ts_mean requires a lookback window",
]


def _fixed_point(fn, start: str, passes: int = 6) -> tuple[list[str], int]:
    """Apply `fn` repeatedly; return the sequence and the first pass at which it stops moving."""
    seq = [start]
    for _ in range(passes):
        seq.append(fn(seq[-1]))
    at = next(i for i in range(1, len(seq)) if seq[i] == seq[i - 1])
    return seq, at


def main(clone: str) -> dict:
    sys.path.insert(0, clone)
    logging.disable(logging.CRITICAL)
    from generation_two.core.template_validator import TemplateValidator

    db = Path(tempfile.gettempdir()) / "brain_s18_absent.db"
    v = TemplateValidator(operators=[], data_fields=[], ollama_manager=None,
                          db_path=str(db), use_ast=False)

    event = []
    for t, e in CASES_EVENT:
        seq, at = _fixed_point(lambda s, _e=e: v._aggressive_event_input_fix(s, _e, "USA"), t)
        event.append({"input": t, "after_pass_1": seq[1], "fixed_point_at_pass": at,
                      "changed_at_all": seq[1] != t})

    count = []
    for t, e in CASES_COUNT:
        seq, at = _fixed_point(lambda s, _e=e: v._fix_input_count_error(s, _e)[0], t)
        count.append({"input": t, "error": e, "after_pass_1": seq[1],
                      "fixed_point_at_pass": at, "changed_at_all": seq[1] != t})

    classify = {m: v._classify_error_from_message(m) for m in CASES_CLASSIFY}
    return {
        "repo": "zhutoutoutousan/worldquant-miner",
        "sha": "6a0c9433d888c792b9fcaa80ba8e82c0c9aa6e87",
        "licence": "Apache-2.0",
        "aggressive_event_input_fix": event,
        "fix_input_count_error": count,
        "classify_error_from_message": classify,
        "unclassifiable_classes": sorted(m for m, c in classify.items() if c == "unknown_error"),
    }


if __name__ == "__main__":
    default = str(Path(tempfile.gettempdir()) / "wqmc")
    print(json.dumps(main(sys.argv[1] if len(sys.argv) > 1 else default), indent=1))

"""ONE atomic replace for every desk writer: `os.replace`, retried while Windows refuses it.

THE CLASS (measured 2026-10-29). On Windows `os.replace` onto a file another process holds open
raises PermissionError ([WinError 5] access denied, or [WinError 32] sharing violation): Python
opens files without FILE_SHARE_DELETE, so any reader mid-`json.load` blocks the rename. POSIX
never refuses, so every test on the build box passed. On the trading box it cost:

  * MergeDocket: `merge_hypotheses._write_docket_atomically` died on the replace of the
    1.55M-row `external_survivors.json` on 10-27 and the docket never shipped again -- the judge
    kept judging a two-day-old docket and JUDGE_COVERAGE_REUSE refused every pass after.
  * #462's class on the read side: six of fifteen build shards died on universe parquets
    rewritten in place.

Every module grew its own retry (sleeve_registry, judge_coverage, judging_rate_attempt), each
with a different budget, and the writers that did not grow one were the ones that died. This is
the one definition; `tests/ops/test_atomic_replace_wiring.py` fails on a bare `os.replace` in the
judge/merge/compiler writers it names, so the class cannot come back in them.

Never swallows: an error that outlasts `max_wait_s`, and any error that is not a refusal,
raises exactly as `os.replace` would. The temp file is the caller's to clean up.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

__all__ = ["DEFAULT_MAX_WAIT_S", "replace_with_retry"]

#: Long enough for a reader to finish loading a ~1.6M-row JSON docket on a busy box. A refused
#: replace that outlasts it is raised, never turned into a silent skip.
DEFAULT_MAX_WAIT_S = 300.0
FIRST_WAIT_S = 0.1
MAX_STEP_S = 5.0


def replace_with_retry(src: str | os.PathLike[str], dst: str | os.PathLike[str], *,
                       max_wait_s: float = DEFAULT_MAX_WAIT_S,
                       sleep: Callable[[float], Any] | None = None,
                       on_retry: Callable[[int, float, BaseException], Any] | None = None
                       ) -> int:
    """`os.replace(src, dst)`, retried with capped exponential backoff on PermissionError until
    `max_wait_s` of waiting is spent. Returns the number of retries it took (0 = first try)."""
    nap = time.sleep if sleep is None else sleep
    waited = 0.0
    step = FIRST_WAIT_S
    retries = 0
    while True:
        try:
            os.replace(src, dst)
            return retries
        except PermissionError as exc:
            if waited >= max_wait_s:
                raise
            pause = min(step, MAX_STEP_S, max(0.0, max_wait_s - waited)) or FIRST_WAIT_S
            if on_retry is not None:
                on_retry(retries + 1, pause, exc)
            nap(pause)
            waited += pause
            step *= 2.0
            retries += 1

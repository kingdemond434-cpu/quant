# ADOPT HOLD: PR #389 79d88cb9299ee1ef84a865f2ca8490670f9b1559

Auditor, 2026-11-14T07:16Z. This revokes adopt_clear_pr389_79d88cb92.row.json.
replay-shadow job 132337766621 (05:49Z, after that row) FAILED. libs/portfolio/execution_cost.py, a money-closure file, is an UNMEASURED money-path change, and the new knob REPLAY_CHARGES_ENTRY_HOUR is unbounded by the ceilings. That takes the manual path, and a replay-shadow FAIL is never ruled false.
The HOLD names the commit and every (path, blob) pair that row listed.

Verdict: HOLD.

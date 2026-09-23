---
id: L0072
cost: blind
tags: ["security", "ci"]
---

# L0072

A gate that must EXECUTE an artifact to judge it is not a trust boundary -- it is the artifact's first execution path. Ordering (gate a copy, apply only on green) protects everything DOWNSTREAM of the live tree; only verifying provenance BEFORE running anything protects the box itself. Never let a review step's existence be counted as the control against hostile input.

## Evidence

2026-08-05 R0246: deploy/pull_deploy.sh merged FETCH_HEAD then ran run_ci.py FROM the merged tree, on cron every 10min, on the box owning data/secrets/binance_live.json -- the named safety gate was the payload trigger. Fixed 8c851e0 (worktree gate, merge on green); the execution half stayed OPEN as R0411 because %G? is N on every commit and gating requires running the code.

## Tags

#security #ci

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]

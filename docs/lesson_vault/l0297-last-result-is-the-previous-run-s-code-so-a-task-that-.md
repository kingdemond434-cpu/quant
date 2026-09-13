---
id: L0297
cost: blind
tags: ["ops", "monitoring"]
---

# L0297

`Last Result` is the PREVIOUS run's code, so a task that is RUNNING NOW is not failing now. A board that conflates the two sends the operator chasing ghosts. Read the live state column first and report a past failure as history.

## Evidence

2026-09-12: six tasks reported FAILING off stale result codes while every one was mid-sweep and healthy. Separating RUNNING from FAILING took the board from 9 needing attention to 3.

## Tags

#ops #monitoring

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0068-to-prove-a-failing-test-is-environment-rather-than-you]]

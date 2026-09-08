---
id: L0237
cost: near-miss
tags: ["sizing", "risk"]
---

# L0237

A lot floor and a risk base are different quantities. Raising the smallest position the desk will send is not the same as raising the fraction of equity every sleeve starts at, and implementing one as the other silently re-bases the whole book.

## Evidence

Principal: '0.02 lots each trade' then 'its base floor minimum of minimum but not risk floor base where all promoted sleeves start of with that only'. Implemented as max(policy_lot, 0.02) in venue units after sizing, leaving clamp_risk_frac's 3% base and authority_ramp untouched. A test asserts the ramp still separates a 1-trade sleeve from a 300-trade one and that no risk-fraction function mentions the floor.

## Tags

#sizing #risk

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]

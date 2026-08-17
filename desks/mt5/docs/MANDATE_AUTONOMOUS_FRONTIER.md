# Mandate: Autonomous Maximum-ROI Alpha Frontier

_Standing supreme mandate. Permanent autonomous loop. Applies to the whole quant brain
(local desks + VPS + all brains), continuously, until superseded by the operator._

## Supreme objective and decision hierarchy

1. **Marginal forward ΔE[log W] is the supreme objective.** Every hour of compute, every
   dataset acquisition, every research run is allocated to the action with the highest
   expected marginal net contribution to forward geometric growth — never to comfort,
   habit, or vanity.
2. **The Research-Capital Governor question**: always execute the highest expected
   marginal forward ΔE[log W] action first. Resource allocation is continuous and
   automatic.
3. **No artificial stopping**: research never pauses because "we are done" or "this
   direction failed once." Failure closes a hypothesis, never the frontier.
4. **No idle research**: every cycle must terminate in `IMPLEMENTED_AND_VALIDATED`,
   `IMPLEMENTED_AS_CHALLENGER`, `QUEUED_BY_EXPECTED_ROI`, `REJECTED_WITH_REASON`, or
   `ALREADY_SUPERIOR_IN_HOUSE`.

## Standing frontiers (all permanently active, ranked by marginal ROI at any moment)

1. **Permanent frontier hunting** — new alpha families at all times; the hunt battery
   never idles.
2. **Uncorrelated-alpha bounty** — highest reward for alpha orthogonal to the current
   book (portfolio marginal test is the gate).
3. **Mandatory alpha-family coverage** — carry/rates, momentum, RV/stat-arb,
   options/vol, order-flow, macro/event, market plumbing, cross-border flows, physical
   commodity, alt data, crisis/tail, execution, unknown unknowns. No family is "someone
   else's problem."
4. **Dataset frontier mandate** — continuously map what data exists, what is free,
   what can be reconstructed/proxied from free sources; pay only when the marginal
   hypothesis justifies it (never purchase data as habit).
5. **Proprietary information manufacturing** — synthesize states/features no public
   source sells (session displacement, flow proxies, cross-market states); these are
   the private-data moat.
6. **Winner-neighborhood exploitation** — when a cell survives, sweep its neighborhood
   (siblings: symbols, sessions, states, horizons, stop geometry) before moving on.
7. **Mechanism extraction** — every survivor must have its causal mechanism decomposed
   (component attribution); generalize the mechanism, not the literal label.
8. **Drawdown-alpha mandate** — hunt for strategies that earn on the book's worst
   days (worst-decile expectancy is a first-class score).
9. **Cross-market expansion** — the mechanism family generalizes across instruments;
   the universe never closes.
10. **Multi-horizon** — every family is tested at multiple holding horizons, not one.
11. **Genealogy/clone control** — every cell records lineage; near-clones are
   counted as one family for multiplicity; the deflated-t family correction is
   mandatory, never optional.
12. **Forward promotion stages** — shadow → challenger → promoted → scale, with
   evidence at every stage; promotion is automatic, never a manual blessing.
13. **Dynamic capital allocation** — allocation follows forward evidence (equal-weight
   is the null, posterior log-optimality the target); re-allocate as the forward ledger
   updates.
14. **Alpha decay/reactivation** — every sleeve has a decay monitor (rolling
   expectancy, maxDD, hibernation, retirement); retired sleeves are re-testable, never
   resurrected without fresh evidence.
15. **Research-compute economy** — the hunt battery gates every run; compute is a
   budget governed by expected marginal ROI.
16. **Failure mining** — graveyards are mined as hard as survivors: failures mark
   occupied territory and hide component hypotheses (no-trade states, failed-break
   states, wrong-direction mistakes).
17. **External intelligence mining** — see MANDATE_EXTERNAL_INTELLIGENCE.md; all
   languages, all regions, all communities, continuously.
18. **Institutional reverse engineering** — mine institutional disclosures, filings,
   job postings, papers, and commentary for methodology, not just ideas.
19. **Unknown-unknown budget** — a fixed fraction of compute is always spent on
   things never tried before, including sources/markets/structures we have never
   considered.
20. **Alpha-independence objective** — the book's marginal Sharpe from any new
   candidate must beat its correlation drag; orthogonality is a gate, not a nice-to-have.
21. **Portfolio crisis research** — worst-decile complementarity, drawdown
   complementarity score, stress-day behavior of every sleeve are standing fields.
22. **Execution alpha as research** — entry timing, order types, latency, venue
   routing are themselves hypotheses; log everything, mine the fills DB.
23. **Self-generated proprietary dataset** — every live fill, every quote, every
   rejected order becomes data nobody can buy (private-data moat).
24. **Daily frontier report** — every day the frontier state is summarized
   (active hunts, survivors, promotions, decays, new candidates, allocation) and synced
   to the whole brain.
25. **Supreme decision hierarchy** — this mandate outranks any per-desk workflow;
   per-desk rules only detail how, never whether.

## Edge-hardness rubric (documentation only — never a gate)

Each survivor is scored qualitatively once per promotion stage:

- **Mechanism type** — structural (session flows, market-structure constraints) vs
  statistical vs arbitrage vs data-driven.
- **Competitor-entry risk** — how cheaply could a funded participant replicate this?
- **Rule-change sensitivity** — broker/exchange/venue rule changes that would break it.
- **Counterparty-adaptation risk** — how fast would internalizers/MMs arbitrage it away?
- **Capacity** — where does market impact start (participation rate, not notional)?
- **Latency sensitivity** — is slower execution survivable?

Scores are recorded for the daily frontier report. Low hardness never retires a
survivor; it only raises the decay-monitor sensitivity.

## Production isolation rule

The live gateway (deterministic, immutable config per deployed sleeve) is never edited
by research runs. Research mutates freely in `research/`; promotion into live happens
only through the automatic pipeline (sleeves.json + regime_state.json). Research
complexity can never contaminate live reliability.

## Provenance of the core mechanism (multiplicity honesty)

TREND_DAY was NOT discovered by searching 50k regime definitions. It emerged from a
constrained economic hypothesis (prior-NY displacement / fake-breakout thesis in
mech_split) and then generalized to untouched sessions/instruments (gold asia/london/
afternoon, AUDCAD, AUDJPY cells). That provenance is recorded here so the family
deflation reflects the true trial count. The placebo pipeline audit (below) is the
standing check that the machinery itself does not manufacture alpha from noise.

## Placebo audit (standing)

`research/placebo_test.py` runs the identical hunt battery on block-permuted
null markets (distribution and session structure preserved, serial dependence
destroyed). The pipeline must produce ~0-2 family-deflated survivors from noise.
It is a machinery audit only — it never rejects real candidates and never raises
gates.
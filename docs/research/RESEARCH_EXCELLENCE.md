# CONTINUOUS RESEARCH EXCELLENCE DIRECTIVE

**Principal, 2026-07-28. Binds the data, research and exploration layers. Read with
[OPERATING_DOCTRINE.md](OPERATING_DOCTRINE.md) — that one governs *what to build*, this one governs
*how to research*.**

> The objective is no longer to generate more hypotheses. The objective is to maximise
> **validated alpha discovered per unit of research time.**

---

## 0. The holy combination

Aggression and discipline are not in tension; each is what makes the other safe.

| | |
|---|---|
| **Aggressive in** | exploration, data acquisition, hypothesis generation, killing ideas, replacing decaying edges |
| **Ruthless in** | validation, measurement integrity, cost realism, rejecting the unsourced |
| **Selective in** | deployment, capital allocation, what earns a permanent slot |

Survival is not the enemy of aggression — survival is what lets aggression compound.

---

## 1. Data engineering first

Data quality **is** the competitive advantage, not a precondition to it.

Every collector continuously reports: freshness · latency · completeness · schema stability ·
heartbeat · provenance · confidence · historical continuity.

**A degraded collector automatically reduces the Information Advantage Score of every dependent
hypothesis until repaired.** `dependency_graph.py` propagates this; severity tracks what actually
depends on the source, so a stall is DEGRADED until a live decision rests on it, then POISONED.

**Repairing information quality always outranks generating hypotheses from degraded data.**
Evidence: 53% of 45-day refutations were measurement failures (`E_DATA_QUALITY` 61 +
`B_WRONG_MEASUREMENT` 46), independently corroborated at 64% by the single-day autopsy.

## 2. Maximise the information universe

Never assume current datasets suffice. Every cycle asks:

> **What measurable information exists today that this desk cannot observe?**

**No hardcoded target list.** A fixed roster of sources, papers or repositories is a map of where
everyone already looks. The hunter generates its own vectors, records what it has covered, and is
**forbidden from repeating a vector until the space is exhausted or a trigger reopens it**. A
hunter with a permanent checklist is a scavenger.

Standing exclusions are the inverse of a target list — they name what is *too crowded to be worth
hunting*, never what to hunt.

## 3. Information fusion first

Individual datasets are rarely the edge. Weak independent signals are automatically tested in
combination; nonlinear interaction is prioritised over isolated prediction.

## 4. Automatic feature discovery

Do not rely on manually designed features. Generate candidates mechanically — ratios, spreads,
interactions, lags, rolling transforms, volatility conditioning, cross-asset and cross-source
relations — and let validation decide. `feature_library.py` enumerates the construction space and
reports **coverage as a percentage**, so "we tested microstructure" becomes "we tested 1 of 270".

**Coverage is not progress.** Testing every cell is mass multiple-hypothesis testing. Candidates
enter Stage-A screening only, ranked by *distinguishability from known nulls*.

## 5. Mechanism before prediction

Every hypothesis answers: who creates the inefficiency · why it exists · why competition has not
removed it · what measures it · when it should fail · what would falsify it.

Predictions without mechanisms receive lower priority. A dataset for a dead mechanism is not a new
hypothesis.

## 6. Research measurement everywhere

No component exists without measurable economic value. Tracked: collector health · dataset
contribution · feature contribution · hypothesis quality · validation rate · forward survival ·
deployment rate · capital contribution · alpha decay · calibration · experiment velocity.

`module_justification.py` asks the harder question of anything already built — *if this vanished
tonight, what breaks and would anyone notice?* Current answer: **90 of 243 modules are INERT**.

## 7. Research compression

The output of research is not knowledge. It is **experiments, validated mechanisms, deployable
alpha.** Compress papers, repositories and datasets into the smallest set of high-value
experiments.

## 8. Ruthless prioritisation

Every research hour is capital.

```
Expected Research Value =
    P(edge) × magnitude × persistence × information_advantage × capacity ÷ research_cost
```

Always ask: **is this the highest expected-value use of the next research hour?**

## 9. Continuous self-improvement

Every completed experiment updates dataset rankings, collector priorities, the mechanism library,
failure patterns, Information Advantage Scores, the Blind-Spot Map, the Alpha Genome, anomaly
memory and research calibration.

## 10. North star

**Validated Alpha Discovery Rate** — statistically validated, economically plausible,
forward-tested, deployable mechanisms promoted per unit of research time.

Everything else is a supporting metric. Vanity metrics explicitly not tracked: hypotheses
generated, agents run, datasets collected, papers read, scripts written.

**Current value: 0.00.** 382 experiments · 168 decided · 15 survived *screening* · **0 forward-
tested · 0 deployed.** Screening survival is not the north star — a screen carries zero promotion
authority.

---

## The verification standard that governs all ten

Six defects on 2026-07-27–28 were wrong in ways **no amount of re-reading the diff would have
caught**, and every one surfaced by asserting a *value*: a chunker silently disabled by a wrong
helper name · a fix applied to the mainnet module while the desk trades testnet · a guard placed
on the fallback path while the default path ran unguarded · a selftest scoring 6/6 against a rule
that does not exist in production · a filter defeated by deleting one word · a healthy new
collector scored DEAD because cadence needs three timestamps.

> **Verify by measuring the thing. Never by inspecting the change.**

A number that disagrees with reality is the only reliable tell.

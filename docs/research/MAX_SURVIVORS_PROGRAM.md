# MAXIMUM SURVIVORS PROGRAM — the honest max-ROI directive for validated alpha

North star: **survivors, not discoveries.** The KPI is validated independent edges reaching the
portfolio + Sharpe/Sortino/drawdown improvement — NEVER ideas generated, datasets collected, or
agents run. A system that finds 10,000 ideas and deploys 0 is worthless; one that finds 5 durable
independent alphas is gold. Discovery rate is explicitly NOT a metric. More survivors come from
*converting the candidates you already have*, plus a few genuinely-new orthogonal axes — never from
a volume firehose (the verification bottleneck + cumulative-trial DSR deflation make volume negative,
proven by the 420→0 record and the generation-ROI harness).

## PART 1 — The real survivor levers (do these FIRST; they convert candidates you already have)

1. **RECONSTRUCTED-HISTORY BACKFILL — highest ROI.** Your best candidates (OI, LS, liquidations,
   kimchi) sit at ~25/40 forward days *waiting*. Don't wait — reconstruct their history from archives
   (AWS public blockchain data, venue archives, on-chain reconstruction), diff-verify vs ground
   truth, and run the full gauntlet on that reconstructed out-of-sample NOW. A candidate that
   survives on 200 reconstructed days validates today instead of in weeks. This collapses the clock
   — the single biggest survivor multiplier, using data you can get today.
2. **GATE-CALIBRATION AUDIT — recover wrongly-rejected edges.** (a) *Effective-trial-count*: DSR
   deflates by the number of INDEPENDENT trials, not raw count — cluster the trial ledger by
   mechanism and recompute `n_trials` as the effective count; over-counting variations as full trials
   makes the bar artificially unclearable and kills real edges. (b) *Rejection audit*: shadow-track a
   sample of rejects forward; if a slice would have been profitable, the gate is over-strict and you
   are leaking survivors. Either outcome is pure gain, no new data.
3. **CONSTRUCTION QUALITY / DEPTH per axis.** A real edge mis-constructed reads as noise and gets
   rejected (kimchi was nearly lost to a USDT-vs-FX construction bug). Get the mechanism and signal
   construction EXACTLY right; log every construction tried (no garden-of-forking-paths). Depth on
   one axis beats shallow screens of ten.
4. **MORE OBSERVATIONS.** Cross-sectional breadth (screening universe at 150) + finer archive
   sampling (venue 5m–1h OI/LS/taker) = faster statistical power on every candidate.

## PART 2 — Genuinely-new axes/techniques to ADD (vetted from the QRIS plan; existing gates only)

5. **CROSS-DOMAIN DATA AXES — the one real new-axis family.** Developer-ecosystem package downloads
   (npm / PyPI / Docker pulls for blockchain SDKs) as a leading ecosystem-adoption indicator; macro
   / liquidity (dollar, rates — extend the FRED feed) as regime inputs. Each is ONE forward-clocked
   axis with a stated mechanism, verify-don't-trust, screened same-run, DSR-counted. NOT a "division".
6. **INTERSECTION / COMBINATION SEARCH — turn weak signals into a survivor.** Systematically test
   conjunctions of weak-but-INDEPENDENT signals (e.g. dev↑ + capital↑ + flow↑ = ecosystem-transition
   composite) — a legitimate route to a survivor when singles are marginal. Hard rules: every
   interaction is a TRIAL counted in the DSR ledger; only combine signals that are actually
   orthogonal; the composite must beat its own parts out-of-sample. Wire the harness, but it earns
   real investment only once ≥2 validated base signals exist.
7. **EDGE-DECAY LIFECYCLE.** Formal per-alpha half-life tracking (discovery date, initial vs current
   Sharpe, crowding, correlation drift) → retire on PERSISTENT decay, not noise. Extends the existing
   decay/crowding/capacity monitors + the carry-bleed alarm.

## PART 3 — Sharper analyst rotation (prompt-level upgrade to existing diggers — NOT new agents)

8. Rotate the daily fresh-context cycle through explicit missions, each writing to `research_memory`
   / the decision ledger with a hypothesis ID + economic logic + EV score: **Data-Scout** (new axes),
   **Quant-Scientist** (untested relationships in owned data), **Red-Team** (attack for leakage /
   survivorship / crowding / regime-dependency — sharpen the existing external panel), **Cross-Domain**
   (transfer from network science / epidemiology / information theory), **Portfolio-Doctor** (what
   information would most improve the CURRENT Sharpe / fix the current weakness — often higher value
   than another return predictor). Fresh context per cycle breaks assumption lock-in.

## HARD DISCIPLINE (non-negotiable — this is what stops it becoming a garbage machine)

- **Survivors are the KPI.** Discovery/dataset/agent/idea counts are NOT metrics and are never
  optimised for.
- Every hypothesis: **mechanism-first**, an **ID**, **novelty-gated** against the graveyard,
  **EV-scored**, **screened same-run**, **DSR-deflation-counted**.
- **LLMs propose, the gates dispose.** No LLM decides a trade or "adopts" a dataset; it surfaces
  sources/hypotheses that the quant gates then test.
- **Verify-don't-trust** every source (diff vs ground truth); **legitimacy gate** (clean public
  data only). **Log every negative** — no silent drops.
- **NO swarm / NO volume.** Do NOT "run 50 LLMs → 5000 ideas → test them." Quality of axis + speed
  of validation, never quantity of ideas.

## The coda you cannot optimise away

Even fully maxed, survivor rate is bounded by the market's actual edge density and the calendar
clock — no amount of research machinery manufactures edge that isn't there. And a validated edge you
cannot deploy produces **zero realised survivors**: the parallel highest-ROI move remains **Gate 0**
— proving the execution half on real money — because the desk is not a research artifact, it is a
trading operation. Max survivors = max CONVERSION (Parts 1–3) **and** go live.

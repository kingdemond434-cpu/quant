# GAP_ANALYSIS.md — Institutional Gap Analysis & Ranked Roadmap

Current repo vs. a Renaissance/Citadel/Two-Sigma/DE-Shaw/AQR-style platform. The dominant finding:
**most institutional components already exist (orphaned); the gap is INTEGRATION, not invention.**
True "build from scratch" items are few.

**2026-07-09 weekly architecture review (superseding note, do not delete history below):** written
2026-06-25, before 11 price/derivative mechanisms were actually tested (10 rejected — see
`docs/institutional_knowledge.md`). Ranks 1–5 below (risk facade, alpha registry, meta-portfolio,
factor model, tournament wiring) were **substantially completed** in lighter form as flat JSON state
files (`research_state.json`, `web/*.json`, `data/decision_ledger.json`, `data/executive_kpis.json`)
rather than by wiring the heavier orphaned `libs/alpha`, `libs/portfolio/hrp`, `signal_engine/*`
modules — correct call at this scale (1 solo operator, 2 deployed sleeves): the lighter path shipped
faster and is easier to audit. Those heavier modules stay orphaned; do not resurrect them until
sleeve count genuinely demands a real registry (>5-10 validated survivors).
**Rank 6 (Discovery Factory) is now DOWN-PRIORITIZED, not up-next as originally ranked.** The premise
("wire an automated hypothesis generator to grow breadth") assumed breadth was a search problem.
Evidence since says otherwise: the price/derivative surface is exhausted (10/11 rejected — momentum,
reversal, low-vol, VRP, dispersion, etc.), and the meta-learning is `price_only` × 0.30 in the EV
gate. An automated generator pointed at the SAME data sources would mostly re-discover already-
graveyarded failure modes at real compute cost. The binding constraint is **new free DATA axes**
(on-chain, stablecoin flows, OI/LS/liquidations — already being pursued via forward clocks), not more
hypothesis-generation compute over old data. Revisit Discovery Factory only once 2+ genuinely new
data axes are ingested and the current price/derivative-adjacent backlog is exhausted again.
No migration executed this review — expected lifetime-utility gain did not clear the effort+risk cost
of moving off flat JSON state at current scale.

## Coverage by architecture

| Capability | Exists? | Where | Status |
|---|---|---|---|
| Probabilistic regimes (HMM/GMM/Bayesian) | ✅ built | `libs/regime/` | **LIVE** (this session) |
| Vol/trend/stress/correlation regimes | ◑ partial | regime engine + `risk/correlation,crisis` | wire |
| Validation gauntlet (CPCV/DSR/PBO/RC/WF/bootstrap/SPA) | ✅ exists | `libs/validation/*` | ORPHANED (thin wrapper live) |
| Alpha registry + lifecycle | ✅ exists | `libs/alpha/*`, `signal_engine/*` | ORPHANED |
| Alpha competition / tournament | ✅ exists | `signal_engine/alpha_competition_engine` + `portfolio/construction` | ORPHANED + LIVE |
| Decay / crowding / capacity monitors | ✅ exists | `signal_engine/{decay,crowding,capacity}` | ORPHANED |
| Discovery factory (hypothesis gen) | ✅ exists | `alpha_factory/*`, `discovery/*`, `autodiscovery/*` | ORPHANED (needs crypto adapter) |
| Meta-portfolio (HRP/ERC/factor/optimizer) | ✅ exists | `portfolio/{hrp,optimize,factor_model,covariance,risk_parity}` | ORPHANED + partial LIVE |
| Kelly / fractional / drawdown-aware sizing | ✅ exists | `risk/kelly,growth_leverage,vol_target` | ORPHANED (ladder LIVE) |
| Risk engine (heat/ES/CVaR/tail/stress) | ✅ exists | `libs/risk/*` | ORPHANED |
| Kill switch / loss limits / circuit breakers | ◑ partial | executor (kill+daily-loss+DD throttle) + `risk/gate` | extend |
| Research OS (experiment/feature/model registries) | ✅ exists | `store/*`, `features/*`, `monitoring/*` | ORPHANED |
| Performance/risk/alpha attribution | ✅ exists | `signal_engine/attribution`, `portfolio/analytics` | ORPHANED |
| **Alpha breadth (100s–1000s)** | ❌ true gap | ~7 sleeves only | **the real constraint** |
| **Validated forward edge** | ❌ true gap | 0 survivors (all fail DSR) | **the real constraint** |

## The two true gaps (everything else is wiring)
1. **Breadth** — 7 mostly funding-correlated sleeves vs. the hundreds elite firms run. Only the
   discovery factory (Phase 2) attacks this.
2. **Validated edge** — nothing survives the gauntlet forward yet. No amount of architecture creates
   edge; it only allocates/risk-manages it. This must stay front-of-mind.

## Ranked roadmap (ROI = expected Σgrowth × research-productivity × P(success) / cost)

| Rank | Work | Maps to | Reuse | Effort | Why |
|---|---|---|---|---|---|
| 1 | **Risk engine facade** (heat/ES/CVaR/tail/stress → executor) | Phase 6 | `libs/risk/*` | M | Survival dominates; highest institutional priority; ~all code exists |
| 2 | **Alpha Registry** (single source of truth + lifecycle) | Phase 4 (#4) | `libs/alpha/*` | M | Spine for tournament/meta-portfolio/decay |
| 3 | **Meta-portfolio** (HRP/ERC/factor + Σgrowth objective) | Phase 5 (#7) | `portfolio/{hrp,optimize,covariance,factor_model}` | M | Portfolio construction dominates signals |
| 4 | **Factor Risk Model** (shrinkage cov + factor exposures) | Phase 5/6 (#8) | `portfolio/factor_model` | S | Feeds meta-portfolio + risk |
| 5 | **Alpha Tournament wiring** (competition → dynamic capital) | Phase 4/5 (#6) | `signal_engine/alpha_competition` + `construction` | S | Mostly built |
| 6 | **Discovery Factory** (crypto adapter → 100s hypotheses → gauntlet) | Phase 2 (#5) | `autodiscovery/orchestrator` + `discovery/*` | L | Attacks breadth — the real gap; hardest (adapter) |
| 7 | **Full validation gauntlet** entrypoint (anchored WF + purged K-fold + MC + SPA) | Phase 3 | `validation/gauntlet` | S | Strengthen the bar before promotion |
| 8 | **Research OS** (experiment/feature/model registry + reproducibility) | Phase 7 | `store/*`, `features/*` | M | Two-Sigma research productivity |

## Honest sequencing note
Ranks 1–5 are integration of existing, tested code — fast and safe. Rank 6 (discovery factory) is the
only large build and the only one that grows breadth, so it is the highest-value *and* highest-effort.
Ranks 1–5 build the institutional skeleton; rank 6 supplies the fuel; validation (rank 7) is the gate.
Per the mandate: none of this is allowed to deploy unvalidated alpha to live capital — it operates in
shadow until the gauntlet passes forward.

## Implementation order this campaign
#4 Alpha Registry → #8 Factor Model → #7 Meta-Portfolio → #6 Tournament → #1 Risk facade →
#5 Discovery Factory → #3/#7 validation + research OS. Each lands as one tested, wired module.

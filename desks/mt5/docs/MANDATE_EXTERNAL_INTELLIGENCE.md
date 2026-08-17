# Mandate: External Intelligence Steal-and-Improve

_Standing mandate. Continuous. No waiting for operator instruction._

## Core question

For every external source encountered (Reddit, X/Twitter, YouTube, podcasts, blogs,
GitHub, MQL5, Myfxbook, Darwinex, papers, patents, conference talks, broker/exchange
research, quant forums, newsletters, codebases, institutional commentary, job postings,
vendor docs, transcripts, unknown sources, all languages/regions):

> What does this person/system/process do measurably better than us, and can we legally
> convert that advantage into code, data, research methodology, validation, execution,
> portfolio construction, infrastructure, or alpha?

Never merely summarize or save links.

## Conversion pipeline

Every useful discovery becomes:

`SOURCE → CLAIM → ECONOMIC/ENGINEERING MECHANISM → OUR GAP → IMPLEMENTABLE CHANGE → TEST
→ EXPECTED ΔE[log W] → VALIDATION → IMPLEMENT/REJECT`

Terminal states only:

- `IMPLEMENTED_AND_VALIDATED`
- `IMPLEMENTED_AS_CHALLENGER`
- `QUEUED_BY_EXPECTED_ROI`
- `REJECTED_WITH_REASON`
- `ALREADY_SUPERIOR_IN_HOUSE`

## Dimensions to decompose every external system into

`ALPHA` `DATA` `VALIDATION` `EXECUTION` `PORTFOLIO` `CAPACITY` `LIVE OPERATIONS`
`INFRASTRUCTURE` `TESTING` `AI/AGENT DESIGN` `RESEARCH SPEED` `EDGE DURABILITY`
`UNKNOWN-UNKNOWN DISCOVERY`.

For each: are they better than us? If yes, improvement ticket immediately. A weaker
overall system may contain one superior component — extract the valuable part.

## Standing rules

1. **Anti-complacency**: assume every serious external system may contain at least one
   local optimum superior to ours until checked. Never "we are more advanced, nothing to
   learn."
2. **No-copy-without-proof**: popularity, reported P&L, credentials, branding, complexity
   do not constitute evidence. Imported ideas receive no exemption from: leakage checks,
   realistic costs, point-in-time integrity, OOS/WF, multiple-testing controls, execution
   realism, portfolio marginal-value testing, forward confirmation.
3. **Implementation-not-summary**: a research cycle that ends in "interesting idea" is
   incomplete. Every useful discovery terminates in action or explicit economic rejection.
4. **No additions that reject edges**: never add validation harshness that throws away
   small or big good edges. Add only controls that audit the machinery itself (e.g.
   placebo/null-data pipeline) or cheap diagnostics that cannot veto candidates.

## Source breadth

Continuously search all languages (incl. Chinese, Japanese, Korean, Russian, Arabic,
Portuguese, Spanish, Turkish, French, German, Hindi), all regions, all trading
communities, all asset classes, all public institutional sources, all open-source
projects, all credible practitioner discussions. Mine adjacent fields when transferable:
statistics, ML, causal inference, optimization, control theory, signal processing,
distributed systems, databases, cybersecurity, reliability engineering, microstructure,
auction theory, game theory, operations research, information theory.

## Known absorbed additions (provenance registry)

| Source | Idea | Status |
|---|---|---|
| Adderalin (r/algotrading) | Edge Hardness / competitive-entry / rule-change / counterparty-adaptation scoring; capacity as market-impact; replacement-edge inventory | DOCUMENTED (rubric in frontier mandate); scoring optional, never a gate |
| FrameFar (r/algotrading) | Tick/L2 execution truth, latency model, intrabar-order correctness, signal-at-N/executable-at-N+1, unit tests | ALREADY_SUPERIOR_IN_HOUSE (engine.py next-bar-open + intrabar triggers + costs; gold-desk fidelity/execution_cost + 68 tests) |
| GreyMatter AI | Fail-closed architecture, deterministic execution path, information walls, frozen/blind experiments, fast tests | Partially in house (gateway/replay/regime separation); keep as design principle |
| 1,000-strategy researcher | Separate long/short organisms; ensemble not monolith | gold-desk direction_audit/direction_program cover discipline; mt5 desk: side diagnostics only if evidence of asymmetry |
| ML specialist | Economically weighted failure labels; specialist models | gold-desk reference_labeling/user_twin; future ML families only |
| Production builders | Immutable live champions vs mutating research | In house (gateway deterministic loop; hunts isolated) |
| Placebo/null pipeline | Machinery audit: same hunt machine on noise must produce ~0-2 survivors | IMPLEMENTED (research/placebo_test.py) |

## Permanent objective

Turn the entire public and legally accessible global trading/quant ecosystem into a
continuously mined competitive-intelligence feed. The quant becomes progressively harder
to outperform because every useful idea discovered externally becomes another candidate
upgrade internally.
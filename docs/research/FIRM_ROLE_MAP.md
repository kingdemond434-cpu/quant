# Firm role map: every research role of a top quant shop, as an always-on AI lane

zuck, 2026-11-18: replicate hundreds of RenTech-style researchers across every role, widened to
Two Sigma, D. E. Shaw, Citadel's pod discipline, the Chinese quant shops (High-Flyer, Ubiquant,
Minghong, Lingjun) and Asian retail communities in every country.

**Template.** RenTech Medallion: many weak, independent signals combined into one book and
compounded on own capital. From Citadel and Millennium we borrow only the pod discipline: each
strategy has its own hard drawdown stop and a fast cut, sized inside the prop firms' limits.

**Data:** `libs/research/firm_lanes_roster.json` (the roster), `libs/research/firm_lanes.py`
(logic) and `desks/mt5/research/firm_lanes.py` (hourly leg `firm_lanes`, intel department,
information layer). Live verdicts are in `desks/mt5/reports/FIRM_LANES.json`. The roster's
`status` field only says where the code lives; the hourly verdict is measured from the tree and
the artifacts.

| Lane | Real role | Borrowed from | Where |
|---|---|---|---|
| data_acquisition | Data sourcing | RenTech, Two Sigma | acquire_datasets, axis_ingest, alt_data_yield |
| data_cleaning_pit | Cleaning, point in time | RenTech, D. E. Shaw | bitemporal, pit_audit |
| global_alt_data | Alt and global data | Two Sigma, Point72 | world_macro_proposer, cb_tone_screen |
| asset_horizon_grid | Researchers per asset class x horizon | RenTech, High-Flyer, Ubiquant | **NEW** |
| factor_mining | Formula alpha factory | WorldQuant, High-Flyer, Ubiquant | expression_factory, alpha_evolution |
| trend_carry | Trend, carry, macro factors | Man AHL, Winton, AQR | trend_core, carry_state |
| relative_value | Stat arb, relative value | RenTech, D. E. Shaw | alpha_recombination, causal_lab |
| event_text | Events, earnings, text | D. E. Shaw, Two Sigma | earnings_miner |
| llm_research_lab | LLM assistants (propose only) | Two Sigma, Man | **open PRs only** (#332, #501-504) |
| paperclip_company | AI research company (converters, reviver, red team, triage) | Two Sigma, RenTech | **open PR only** (#1301) |
| asian_retail_forest | Asian retail and small quant communities | JoinQuant, RiceQuant, vn.py, JP/KR/TW/HK/IN/SEA forums | deep_forest_miner (580 grounds) |
| careers_scout | Competitor intel from job ads | all target firms | **NEW** |
| execution_cost | Execution and cost models | RenTech, Citadel | execution_science, cost_surfaces |
| signal_combiner | One book from many signals | RenTech | **open PRs only** (#618, #644, #1072) |
| portfolio_risk | Sizing by E[log W] | RenTech, AQR | pf_allocator, constrained_elog |
| pod_stops | Per-strategy drawdown stops | Citadel, Millennium | **NEW, shadow** |
| adversarial_review | Kills overfit | RenTech, D. E. Shaw | adversary, red_queen, traps, null_lab |
| multiple_testing | One lifetime FDR budget | RenTech, AQR | online_fdr, replayed by firm_lanes |
| decay_monitor | Live decay | RenTech, Two Sigma | decay_monitor |
| research_allocation | Compute to what produces | RenTech, Two Sigma | researcher_market, cro_role |
| infrastructure | Clocks and artifacts | RenTech, Citadel | hourly_cycle, leg_rotation |

## What the new lanes do

- **Shared signal library** (`data/firm_lanes/signal_library.jsonl`): every rule any lane sent
  or the judge certified, by (family, symbol, params) identity. A lane never queues a rule
  already there, so no rule pays the multiple-testing charge twice.
- **Queue per lane** (`data/firm_lanes/queues/<lane>.jsonl`): deduplicated, drained 24 rows per
  lane per pass through `proposer_common.donate`, which stamps, blinds, preregisters and charges
  every row as a trial. The sealed judge decides; nothing here decides.
- **Asset x horizon grid**: eight asset buckets (equities excluded, they are event-lane only)
  times intraday, daily and weekly/monthly. The emptiest squares are filled first.
  Origin-priority (JP to FX, CN to commodities, metals, energy and softs, KR/TW/HK/IN to
  indices) only sets the order, never filters.
- **Multiple testing**: every certified survivor's SPA p-value is replayed through LORD++ and
  e-LOND in gating order. `over_budget_share` is the share of certificates the lifetime budget
  would not have admitted.
- **Pod stops, SHADOW**: per-sleeve drawdown in R from `live_ledger.jsonl`. The hard stop is
  half the tightest prop drawdown (E8, 8%) at 0.5% risk, split by sqrt(pods), with a 3R floor;
  CUT_HALF at half the stop. Wiring it into orders is money-path work and needs its normal
  checks plus a Rule 1 proof (GROWTH_GOVERNANCE) that it raises forward E[log W].
- **Careers scout, weekly**: the firms' own careers pages only, through the robots gate and the
  refused-host list (never LinkedIn). New or growing themes go to `data/firm_lanes/lane_topics.jsonl`.

## Rules kept

LLMs propose only and never size. Nothing in firm_lanes is imported by the gateway, the
allocator or the promoter. Every queued rule is a charged trial.

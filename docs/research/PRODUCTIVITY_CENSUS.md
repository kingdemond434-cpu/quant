# RESEARCH PRODUCTIVITY CENSUS

_Derived by `desks/mt5/research/productivity_census.py` at 2026-09-23T18:06:46+00:00; DO NOT EDIT -- regenerate._

**1573 producers** | productive **87** | compute-with-zero-cells **23** | certificates **58** (unattributed 33) | forward 2 | live 40

**Dedup (three identities, all measured):** 18201 raw cells -> 18201 distinct `content_hash` (1.0x -- the door, 1.00 means it works) -> **2844 distinct `grid_cell` (6.3998x)** -> 583 distinct `mechanism` (31.2196x). The last two are the duplication a reader was asking about; the first cannot show it.
**UNMEASURED `canonical_mechanisms`:** registry table `mechanisms` holds 0 rows on this host: no organ has written a canonicalised mechanism, so this stage is UNMEASURED and not zero -- the fallback below counts DISTINCT mechanism_id stamped on discoveries instead
**UNMEASURED `cheap_survivors`:** no research_candidates row carries a judge stamp (`judged_at` null on all 18201 rows, `terminal_gate` likewise), so `survived = 0` everywhere is the column's DEFAULT and not a verdict: the cheap stage is UNMEASURED, not zero. Proxy published as `yield_survivors` from generator_yield/source_yield, which the producers write themselves
**Compute caveat:** UNMEASURED: the compute ledger holds 3 priced run(s) in the last 7 days and NONE of them names a roster producer (cost_by_run keys on the leg name), so every ledger hour here is 0.0 and all compute in this census comes from generator_yield/source_yield compute_s, which the producers charge themselves. Certificates-per-compute-hour is a registry ratio on this host, not a wall-clock one.
**33 of 58 certificates are UNATTRIBUTED** -- no name and no family lineage reaches a producer. That is a lineage-stamping gap, not a zero for any organ.

## By region

| region | prod | sources | docs | raw cells | uniq | submitted | surv | certs | cpu h | cells/src | surv/src | certs/h |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Japan | 37 | 27 | 0 | 40 | 37 | 8 | 0 | 0 | 0.03 | 1.3704 | 0.0 | 0.0 |
| Korea | 2 | 0 | 0 | 5 | 3 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| China | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| SEA | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| Russia/CIS | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| India | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| Europe | 1 | 1973 | 92 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0 | 0.0 | UNMEASURED |
| North America | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| LatAm | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| Oceania | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| MENA | 10 | 0 | 0 | 14 | 14 | 2 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| Africa | 8 | 0 | 0 | 38 | 38 | 12 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| Global/institutional | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| unattributed | 1498 | 17 | 0 | 18104 | 3558 | 10381 | 0 | 25 | 0.44 | 209.2941 | 0.0 | 56.3317 |

## Top producers by certificates

| producer | certs | unique cells | cpu h | region |
|---|--:|--:|--:|---|
| `net_edge` | 24 | 22 | 0.0 | unattributed |
| `mechanism_genome` | 1 | 24 | 0.0 | unattributed |
| `discovery_compiler:interaction` | 0 | 930 | 0.0 | unattributed |
| `discovery_compiler:regime` | 0 | 470 | 0.0 | unattributed |
| `discovery_compiler:cross_asset` | 0 | 441 | 0.0 | unattributed |
| `discovery_compiler:session` | 0 | 298 | 0.0 | unattributed |
| `discovery_compiler:execution` | 0 | 175 | 0.0 | unattributed |
| `discovery_compiler:asset_transfer` | 0 | 167 | 0.0 | unattributed |
| `discovery_compiler:residual` | 0 | 159 | 0.0 | unattributed |
| `discovery_compiler:horizon` | 0 | 115 | 0.0 | unattributed |

## Compute spent, no unique cell -- THE LIST TO ACT ON

| producer | cpu h | ledger h | registry h | sources | clock | region |
|---|--:|--:|--:|--:|---|---|
| `math:symbolic_regression` | 0.0157 | 0.0 | 0.0157 | UNMEASURED | - | unattributed |
| `math:reservoir_computing` | 0.0121 | 0.0 | 0.0121 | UNMEASURED | - | unattributed |
| `math:combinatorics` | 0.0061 | 0.0 | 0.0061 | UNMEASURED | - | unattributed |
| `japan:japanfixingminer` | 0.0058 | 0.0 | 0.0058 | UNMEASURED | - | Japan |
| `japan:japansqminer` | 0.0052 | 0.0 | 0.0052 | UNMEASURED | - | Japan |
| `japan:japangotobiminer` | 0.0047 | 0.0 | 0.0047 | UNMEASURED | - | Japan |
| `math:recurrence_quantification` | 0.0042 | 0.0 | 0.0042 | UNMEASURED | - | unattributed |
| `japan:japanfiscalcalendarminer` | 0.0041 | 0.0 | 0.0041 | UNMEASURED | - | Japan |
| `japan:japanholidayminer` | 0.0039 | 0.0 | 0.0039 | UNMEASURED | - | Japan |
| `math:linear_response` | 0.0031 | 0.0 | 0.0031 | UNMEASURED | - | unattributed |
| `math:sequential_pattern_mining` | 0.0024 | 0.0 | 0.0024 | UNMEASURED | - | unattributed |
| `math:sindy` | 0.0004 | 0.0 | 0.0004 | UNMEASURED | - | unattributed |
| `math:statistical_mechanics` | 0.0004 | 0.0 | 0.0004 | UNMEASURED | - | unattributed |
| `math:survival_hazard` | 0.0003 | 0.0 | 0.0003 | UNMEASURED | - | unattributed |
| `japan:japanresidualminer` | 0.0002 | 0.0 | 0.0002 | UNMEASURED | - | Japan |
| `japan:japanacademicscout` | 0.0001 | 0.0 | 0.0001 | UNMEASURED | - | Japan |
| `japan:japanbojminer` | 0.0001 | 0.0 | 0.0001 | UNMEASURED | - | Japan |
| `japan:japancrossassetminer` | 0.0001 | 0.0 | 0.0001 | UNMEASURED | - | Japan |
| `japan:japandatascout` | 0.0001 | 0.0 | 0.0001 | UNMEASURED | - | Japan |
| `japan:japannativewebscout` | 0.0001 | 0.0 | 0.0001 | UNMEASURED | - | Japan |
| `japan:japantransferminer` | 0.0001 | 0.0 | 0.0001 | UNMEASURED | - | Japan |
| `math:criticality` | 0.0001 | 0.0 | 0.0001 | UNMEASURED | - | unattributed |
| `math:koopman_dmd` | 0.0001 | 0.0 | 0.0001 | UNMEASURED | - | unattributed |

## Where each number comes from

- `roster` <- reports/PRODUCER_CENSUS.json + reports/COMPONENT_REGISTRY.json
- `sources_visited` <- data/alpha_registry.sqlite: sources GROUP BY discovered_via
- `documents_retained` <- data/alpha_registry.sqlite: count(distinct claims.doc_id)
- `raw_mechanism_claims` <- data/alpha_registry.sqlite: count(claims) per source
- `canonical_mechanisms` <- data/alpha_registry.sqlite: mechanisms (empty -> UNMEASURED, proxy = distinct discoveries.mechanism_id)
- `raw_cells` <- data/alpha_registry.sqlite: count(research_candidates) per generator
- `unique_cells` <- data/alpha_registry.sqlite: count(distinct content_hash)
- `gauntlet_submitted` <- research_candidates where donated_cell not null or status in (donated, claimed, retired, judged)
- `cheap_survivors` <- research_candidates where survived = 1
- `certificates` <- desks/mt5/reports/UNIVERSAL_SURVIVORS.json survivors map
- `forward_enrolled` <- desks/mt5/data/sleeve_registry.json
- `live_contribution` <- desks/mt5/data/sleeves.json rows with status LIVE
- `compute_hours` <- libs/ops/compute_ledger.cost_by_run + registry generator_yield/source_yield compute_s
- `region` <- desks/mt5/data/deep_forest_sources.json region codes, mapped by REGION_OF_CODE in this file; producers fall back to sources.country

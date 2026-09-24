# RESEARCH PRODUCTIVITY CENSUS

_Derived by `desks/mt5/research/productivity_census.py` at 2026-09-24T00:09:48+00:00; DO NOT EDIT -- regenerate._

**1653 producers** | productive **115** | compute-with-zero-cells **23** | certificates **58** (unattributed 1) | forward 2 | live 40

**Dedup (three identities, all measured):** 43587 raw cells -> 43042 distinct `content_hash` (1.0127x -- the door, 1.00 means it works) -> **8752 distinct `grid_cell` (4.9802x)** -> 4104 distinct `mechanism` (10.6206x). The last two are the duplication a reader was asking about; the first cannot show it.
**UNMEASURED `canonical_mechanisms`:** registry table `mechanisms` holds 0 rows on this host: no organ has written a canonicalised mechanism, so this stage is UNMEASURED and not zero -- the fallback below counts DISTINCT mechanism_id stamped on discoveries instead
**Compute ledger:** UNMEASURED: the compute ledger holds 4 priced run(s) in the last 7 days and NONE of them names a roster producer (cost_by_run keys on the leg name), so every ledger hour here is 0.0 and all compute in this census comes from generator_yield/source_yield compute_s, which the producers charge themselves. Certificates-per-compute-hour is a registry ratio on this host, not a wall-clock one.
**1 of 58 certificates are UNATTRIBUTED** -- no name and no family lineage reaches a producer. That is a lineage-stamping gap, not a zero for any organ.


## Per-producer measurement coverage -- THE RATCHET

_Denominator is **1653 producers** and travels with every ratio: coverage improved by dropping producers is a regression wearing an improvement's number (L1.50)._

| column | measured | of | coverage | non-zero |
|---|--:|--:|--:|--:|
| `cells` | 1653 | 1653 | 1.0 | 115 |
| `unique_cells` | 1653 | 1653 | 1.0 | 115 |
| `cells_judged` | 1653 | 1653 | 1.0 | 32 |
| `certificates` | 1653 | 1653 | 1.0 | 1 |
| `orthogonality_added` | 1620 | 1653 | 0.98 | 68 |
| `compute_hours` | 1653 | 1653 | 1.0 | 61 |

**Region:** 100 regional + 1522 NOT_REGIONAL = 0.9812 of 1653; 31 still `unattributed`. Routes: roster_kind 1409, name 74, birth_stamp_registry 64, method_or_desk_organ 54, none 31, birth_stamp_census 10, namespace 5, ground 5, sources 1

## By region

| region | prod | sources | docs | raw cells | uniq | submitted | judged | surv | certs | cpu h | cells/src | surv/src | certs/h |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Japan | 53 | 27 | 0 | 13211 | 1877 | 9258 | 49 | 0 | 0 | 0.03 | 69.5185 | 0.0 | 0.0 |
| Korea | 2 | 0 | 0 | 111 | 38 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| China | 3 | 0 | 0 | 18 | 18 | 15 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| SEA | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| Russia/CIS | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| India | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| Europe | 2 | 2215 | 110 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0 | 0.0 | UNMEASURED |
| North America | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| LatAm | 14 | 0 | 0 | 190 | 99 | 0 | 4 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| Oceania | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| MENA | 10 | 0 | 0 | 158 | 115 | 2 | 1 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| Africa | 8 | 0 | 0 | 573 | 330 | 12 | 1 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| Global/institutional | 7 | 0 | 0 | 6 | 6 | 6 | 0 | 0 | 0 | 0.00 | UNMEASURED | UNMEASURED | UNMEASURED |
| NOT_REGIONAL | 1522 | 0 | 0 | 26545 | 4910 | 10973 | 96 | 0 | 0 | 0.69 | UNMEASURED | UNMEASURED | 0.0 |
| unattributed | 31 | 17 | 0 | 2775 | 2583 | 2647 | 74 | 0 | 57 | 0.00 | 151.9412 | 0.0 | UNMEASURED |

## Top producers by certificates

| producer | certs | unique cells | cpu h | region |
|---|--:|--:|--:|---|
| `external` | 57 | 2554 | 0.0 | unattributed |
| `seat:discovery_compiler` | 0 | 1445 | 0.0 | Japan |
| `independence_intake` | 0 | 873 | 0.0 | NOT_REGIONAL |
| `pack_cells.world` | 0 | 845 | 0.0 | NOT_REGIONAL |
| `timeframe_fanout` | 0 | 460 | 0.0 | NOT_REGIONAL |
| `seat:moat_factory` | 0 | 395 | 0.0 | NOT_REGIONAL |
| `sandbox_runner` | 0 | 339 | 0.0 | NOT_REGIONAL |
| `africa:fx_regime_capital_control_sensor` | 0 | 168 | 0.0 | Africa |
| `execution_alpha_miner` | 0 | 159 | 0.0749 | NOT_REGIONAL |
| `sandbox:alpha101` | 0 | 159 | 0.0 | NOT_REGIONAL |

## Compute spent, no unique cell -- THE LIST TO ACT ON

| producer | cpu h | ledger h | registry h | sources | clock | region |
|---|--:|--:|--:|--:|---|---|
| `math:symbolic_regression` | 0.0157 | 0.0 | 0.0157 | 0 | - | NOT_REGIONAL |
| `math:reservoir_computing` | 0.0121 | 0.0 | 0.0121 | 0 | - | NOT_REGIONAL |
| `math:combinatorics` | 0.0061 | 0.0 | 0.0061 | 0 | - | NOT_REGIONAL |
| `japan:japanfixingminer` | 0.0058 | 0.0 | 0.0058 | 0 | - | Japan |
| `japan:japansqminer` | 0.0052 | 0.0 | 0.0052 | 0 | - | Japan |
| `japan:japangotobiminer` | 0.0047 | 0.0 | 0.0047 | 0 | - | Japan |
| `math:recurrence_quantification` | 0.0042 | 0.0 | 0.0042 | 0 | - | NOT_REGIONAL |
| `japan:japanfiscalcalendarminer` | 0.0041 | 0.0 | 0.0041 | 0 | - | Japan |
| `japan:japanholidayminer` | 0.0039 | 0.0 | 0.0039 | 0 | - | Japan |
| `math:linear_response` | 0.0031 | 0.0 | 0.0031 | 0 | - | NOT_REGIONAL |
| `math:sequential_pattern_mining` | 0.0024 | 0.0 | 0.0024 | 0 | - | NOT_REGIONAL |
| `math:sindy` | 0.0004 | 0.0 | 0.0004 | 0 | - | NOT_REGIONAL |
| `math:statistical_mechanics` | 0.0004 | 0.0 | 0.0004 | 0 | - | NOT_REGIONAL |
| `math:survival_hazard` | 0.0003 | 0.0 | 0.0003 | 0 | - | NOT_REGIONAL |
| `japan:japanresidualminer` | 0.0002 | 0.0 | 0.0002 | 0 | - | Japan |
| `japan:japanacademicscout` | 0.0001 | 0.0 | 0.0001 | 0 | - | Japan |
| `japan:japanbojminer` | 0.0001 | 0.0 | 0.0001 | 0 | - | Japan |
| `japan:japancrossassetminer` | 0.0001 | 0.0 | 0.0001 | 0 | - | Japan |
| `japan:japandatascout` | 0.0001 | 0.0 | 0.0001 | 0 | - | Japan |
| `japan:japannativewebscout` | 0.0001 | 0.0 | 0.0001 | 0 | - | Japan |
| `japan:japantransferminer` | 0.0001 | 0.0 | 0.0001 | 0 | - | Japan |
| `math:criticality` | 0.0001 | 0.0 | 0.0001 | 0 | - | NOT_REGIONAL |
| `math:koopman_dmd` | 0.0001 | 0.0 | 0.0001 | 0 | - | NOT_REGIONAL |

## Where each number comes from

- `roster` <- reports/PRODUCER_CENSUS.json + reports/COMPONENT_REGISTRY.json
- `sources_visited` <- data/alpha_registry.sqlite: sources GROUP BY discovered_via
- `documents_retained` <- data/alpha_registry.sqlite: count(distinct claims.doc_id)
- `raw_mechanism_claims` <- data/alpha_registry.sqlite: count(claims) per source
- `canonical_mechanisms` <- data/alpha_registry.sqlite: mechanisms (empty -> UNMEASURED, proxy = distinct discoveries.mechanism_id)
- `raw_cells` <- data/alpha_registry.sqlite: count(research_candidates) per producer, credited through discoveries.discovery_id so the compiler that stamped a cell is never credited with the producer that caused it (the same rule scripts/check_producer_yield._window_cells already applies)
- `raw_cells_stamped_on_candidate` <- the same count read off research_candidates.generator alone, published so the pass-through share stays visible
- `unique_cells` <- count(distinct coalesce(grid_cell, content_hash)) per producer
- `gauntlet_submitted` <- research_candidates where donated_cell not null or status in (donated, claimed, retired, judged) -- the judge's DOOR
- `cells_judged` <- research_candidates carrying a verdict stamp (judged_at non-empty or terminal_gate non-empty) -- what came back OUT of that door
- `cheap_survivors` <- research_candidates where survived = 1
- `certificates` <- desks/mt5/reports/UNIVERSAL_SURVIVORS.json survivors map
- `forward_enrolled` <- desks/mt5/data/sleeve_registry.json
- `live_contribution` <- desks/mt5/data/sleeves.json rows with status LIVE
- `orthogonality_added` <- desks/mt5/reports/PRODUCER_YIELD.json cells_owed.producers[].orthogonality_added -- marginal effective rank from libs.research.sandbox_rotation.breadth, READ and never re-derived here
- `compute_hours` <- libs/ops/compute_ledger.cost_by_run + registry generator_yield/source_yield compute_s
- `region` <- libs/research/attribution.py, delegated in full: producer name -> colon namespace segment -> modal sources.country -> the producer's own declared ground -> the birth stamp on its registry rows -> NOT_REGIONAL for a method, desk organ or declared execution kind. `region_route` on each row names which of those answered.
- `measured_zero` <- when the registry opened, every per-producer GROUP BY ran over the whole table, so a producer absent from a result has a MEASURED zero. When it did not open, every registry stage is UNMEASURED.

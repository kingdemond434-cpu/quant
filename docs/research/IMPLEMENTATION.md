# Implementation lane

DERIVED FILE -- rendered from `desks/mt5/reports/IMPLEMENTER.json` by `desks/mt5/research/implementer.py`. Edit the organ or the ledger, never this page.

Measured 2026-09-23T02:50:19.898101+00:00 · leg `hourly_cycle:implementer` · cadence 3h

- OPEN before this pass: **219** -> after: **216**
- rows moved: **226** blocked 216, implemented 3, rejected 6, scheduled 1
- intake: 7 new row(s); 0 proposal(s) NOT re-proposed because the desk already settled them
- open rows with no owner and no next action: **0** (the defect this organ exists to remove; it must be 0)
- largest blocker class: **needs_specification**
- OPEN ratchet floor: 216 (0 recorded rise(s))

Oldest OPEN row: **R0495** raised 2026-08-12T17:09:22.730103+00:00 (993.7h) · owner `hourly_cycle:implementer`

> THE OWED-WORK WORKER IS HANDED DEFECT LISTS THAT ARE ALREADY STALE, and it cannot tell without re-running the audit. Measured 2026-08-12: of 4 defects handed to

Next action: BT-3941c691df -- hourly_cycle:implementer turns this into a cited spec (file + clock + artifact)

| blocker class | open rows |
|---|---|
| needs_specification | 104 |
| needs_code | 51 |
| needs_clock | 44 |
| needs_change | 14 |
| needs_principal | 3 |

## Build tasks opened this pass

A recommendation that asks for code gets a task, never speculative code.

| task | target | owner | recommendation |
|---|---|---|---|
| BT-539f760e31 | `libs/research/mine_conversion.py` | hourly_cycle:fence_battery | R0525 |
| BT-17cc7255e8 | `libs/validation/dsr.py` | MT5-Gauntlet | R0566 |
| BT-55c1812f03 | `unspecified` | hourly_cycle:mine | R0514 |
| BT-eda2853239 | `tests/execution/test_carry_entry_gate.py` | MT5-Gateway | R0564 |
| BT-f3ee7d4539 | `scripts/model_upgrade.py` | MT5-Gauntlet | R0515 |
| BT-4bf349f4a5 | `run_deadman_switch.py` | principal | R0516 |
| BT-98d9870f5a | `scripts/run_llm_trader.py` | hourly_cycle:implementer | R0534 |
| BT-512a76bbc6 | `unspecified` | MT5-Hourly:promoter | R0517 |
| BT-6e104f0157 | `tests/research/test_unlock_supply_series.py` | hourly_cycle:implementer | R0533 |
| BT-24bc8ac819 | `unspecified` | hourly_cycle:shadow_forward | R0664 |
| BT-82813c61d9 | `unspecified` | hourly_cycle:mine | R0519 |
| BT-233d5bca99 | `unspecified` | hourly_cycle:mine | R0518 |
| BT-fc42020c19 | `unspecified` | hourly_cycle:fence_battery | R0555 |
| BT-356df08192 | `data/audit_coverage.json` | hourly_cycle:fence_battery | R0583 |
| BT-b25a9afaa4 | `data/forward_slots.json` | MT5-Hourly:promoter | R0601 |
| BT-e45bf226b0 | `data/liquidations.parquet` | hourly_cycle:mine | R0612 |
| BT-87487fcc43 | `scripts/check_organ_liveness.py` | timer:crontab.manifest | R0535 |
| BT-315ebb5c33 | `data/sor_crypto.sqlite` | hourly_cycle:implementer | R0586 |
| BT-bc23db6be4 | `unspecified` | hourly_cycle:implementer | R0526 |
| BT-390d9da5ea | `unspecified` | hourly_cycle:mine | R0584 |
| BT-602639361f | `libs/validation/brain_calibration.py` | MT5-Hourly:promoter | R0602 |
| BT-a788a84c20 | `scripts/run_moat_campaign.py` | MT5-Gauntlet | R0567 |
| BT-553158d8f9 | `unspecified` | hourly_cycle:implementer | R0585 |
| BT-150c27b29a | `data/cot_btc_panel.json` | hourly_cycle:mine | R0613 |
| BT-a27bf4e341 | `data/trade_forensics.json` | MT5-Hourly:refresh_bars | R0496 |

## UNMEASURED sources

An absent source is a real answer (L1.28a) and is named rather than skipped:

- desks/mt5/reports/UNKNOWN_UNKNOWNS.json: ABSENT
- desks/mt5/reports/NEGATIVE_KNOWLEDGE.json: ABSENT
- desks/mt5/reports/FRONTIER_MAP.json: ABSENT
- desks/mt5/reports/PIT_AUDIT.json: ABSENT
- desks/mt5/reports/BOOK_FORENSICS.json: ABSENT
- desks/mt5/reports/QUANTBENCH.json: ABSENT
- desks/mt5/reports/FORMAL_INVARIANTS.json: ABSENT
- data/findings_docket.json: ABSENT

# TIER-1 PROCESS BENCHMARK — the standing gap register the desk hunts WITHOUT being told

*(principal order 2026-07-31: "the quant should always maximise itself every day and any time it
sees gaps, I shouldn't have to manually tell — close every single gap left to tier-1 processes,
except something which can't be changed except by time.")*

Scale: **T1** = RenTech/Citadel/DE-Shaw-class process · **T2** = mid-tier fund / serious prop ·
**T3** = advanced independent · **T4** = retail. Rated on PROCESS, not capital.
`run_max_push.py` parses the table below every refresh: every row not at T1 whose `time_bound`
is `no` enters the daily max-push queue automatically. Editing this file IS re-benchmarking —
add rows when a new layer exists, re-grade when evidence moves a tier, and NEVER delete a
below-T1 row without landing it at T1 (the parser treats a vanished row as a silent cap).
Rows whose only closer is calendar time carry `time_bound: yes` and are listed, not queued —
they are walls, not work.

| layer | tier_now | closer_to_t1 | time_bound |
|---|---|---|---|
| validation_methodology | T1 | hold: certification-triggered FDR decider (R0077) keeps it honest | no |
| research_governance | T1 | hold: matrix zero-orphans is the standing bar | no |
| self_audit_layer | T1 | hold: 9-seat sweep + planted controls + recursive meta | no |
| llm_native_automation | T1 | operational maturity: zero scheduler incidents 30d, quota referee alive | no |
| risk_rails | T2 | R0071 money-path cluster + one clean live cycle | no |
| data_moat | T2 | backups/moat replicas live (run_moat_backup) + Storage-Box/R2 for bulk L2 (principal EUR-4/mo) + second venue | no |
| data_engineering | T2 | bronze owner + 132-symbol backfill (R0081) + write-rate fences + lineage on every appender | no |
| alpha_generation_process | T2 | horizon-honest power gate (R0030/O1) + positive-control battery + resurrection consumer + fusion axes earned | no |
| alpha_generation_throughput | T4 | unfreeze generator post-R0077; L1.25a forbids idle generation; feed 12/12 forward slots daily | no |
| knowledge_reuse_read_side | T4 | phantom-DB repoint x4 (R0079) + one consumer per composed store, born-fenced | no |
| monitoring_observability | T2 | pager delivery ratchet off 0% (ntfy topic confirmed on principal's phone) + alert canary green 7d | no |
| execution | T3 | R0071 stops/guards + TCA fields on all open paths (R0084) + maker-first routing measured | no |
| portfolio_construction | T3 | multi-sleeve risk model + correlation-budgeted allocation once n_sleeves >= 3 (R0101) | no |
| security_opsec | T3 | PAT to fine-grained read-only (principal) + ports bound localhost (R0072) + token rotation (principal) | no |
| conversion_repair | T2 | L1.28b fence flow: dispositions >= arrivals for 30 consecutive days | no |
| capital_scale | T4 | compounding through capacity bands | **yes** |
| forward_history_depth | — | T=310d bar; 8h panels accrue sqrt(3)x; otherwise one day per day | **yes** |
| track_record | — | Gate-0 -> first clean live year | **yes** |

**Grading map used by the parser** (declared, arguable, in one place): T1=1.00, T2=0.66,
T3=0.40, T4=0.15. A layer graded `—` in tier_now is time_bound by definition.

**Standing rule:** the deep sweep's synthesis (A) ceiling table and this register must agree —
where they diverge, the sweep re-grades this file in the same session (ledger-first, R0056
pattern), so the benchmark can never fossilize into flattery.

# Gold loss and exit recheck — 2026-09-29

Scope: read-only production reports/logs and local source/tests. No order, sizing,
exit policy, terminal ownership or promotion change was deployed in this review.

## Measured findings

- Fusion `live_ledger.jsonl`, September 25: gold_asia short -56.18 EUR,
  gold_london_am short -47.21 EUR; subsequent opposite-direction closes -8.30
  and -11.43 EUR. Total of those four closes: -123.12 EUR.
- E8 `reports/E8_LOSS_2026-09-24.json`: three gold shorts total -1135.20 USD.
  The report reconciles these to the account guard. It attributes one loss to
  delayed protection and an already-crossed stop modification; the other two
  trades reached only 0.17R/0.20R favorable excursion. These are historical
  findings, not proof that every current loss shares the same cause.
- E8's latest read in the preceding check, 00:33:25 UTC September 29, reported
  equity 97831.11148564 USD and gold-manager status OK. A successful pass does
  not establish uninterrupted management: the gold log also contains repeated
  terminal IPC failures that night.
- Fusion gateway logs previously inspected show IPC failures, delayed/missed
  valid entry levels, margin refusals and release-identity refusals. Those
  refusals must not be bypassed to manufacture more trading activity.

## Existing early-invalidation screen (not new validation)

Production `reports/exit_study.json`, inspected September 29:

| Window | Eligible trades | Four tested variants: change in expectancy R/trade |
| --- | ---: | --- |
| Asia | 68 | -0.0668, -0.0915, -0.1285, -0.0697 |
| London AM | 57 | -0.0685, -0.1609, -0.1543, -0.0566 |
| Afternoon | 50 | +0.0204, +0.0191, +0.0455, +0.0134 |

All are marked SCREEN_ONLY_NOT_PROMOTED. This screen does not establish
out-of-sample net log-growth improvement or an optimal threshold. Do not deploy
the best selected afternoon variant merely because it won this comparison.

## Evidence defect repaired locally

`gateway._position_entry` retrieved the opening fill but discarded its timestamp
and direction. `record_trades` recorded observation time and the closing deal's
side. The exit reader requires opening time, and a closing BUY describes a SHORT
position. New rows now retain explicit entry time/side and execution exit time,
with broker-deal-epoch provenance. Legacy `time`/`side` fields remain unchanged.
The exit reader prefers explicit entry side when available.

This does not backfill historical rows, normalize broker clocks into true UTC,
or complete the missing live-excursion consumer. Production EXIT_ACCOUNTS at
00:35:08 UTC still reported 239 live rows without joinable entry evidence. That
backfill must use actual broker history and account/position/deal identities;
never manufacture timestamps or use shadow excursions as live evidence.

## Remaining acceptance work

1. Resolve terminal ownership through approved maintenance; verify uninterrupted
   management on both venues without creating competing terminal sessions.
2. Backfill actual historical entry/exit identity and timestamps; reconcile fees,
   partial fills and opening risk before evaluating net growth.
3. Join live trade paths using explicit account/basis/position identities and
   matching clock conventions; reject ambiguous joins.
4. Validate early-invalidation challengers chronologically after venue-specific
   costs, with search accounting and untouched prospective evidence.
5. Prove both venue adapters consume the same approved decision version while
   preserving broker-specific costs, execution constraints and account rules.

Status: concrete telemetry repair tested locally; no optimality certification,
no all-blueprints-complete claim, and no deployment claim.

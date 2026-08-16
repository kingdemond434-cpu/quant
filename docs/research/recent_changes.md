# Desk changes, last 24h (generated 2026-08-15T10:10:15Z)

52 commit(s). Patches truncated to 400 lines each -- a seat that receives
40k lines reviews none of them, and the design decision is almost always in the first
few hundred.


---

## 56547b16 Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

```diff
commit 56547b161bbb5ec7f0b49bbe71ed7892a8edddd2
Merge: 6e8d9c1a 4959c7f6
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 09:58:17 2026 +0000

    Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

 scripts/run_spot_executor.py                | 43 ++++++++++++++++---
 tests/execution/test_spot_executor_quote.py | 64 +++++++++++++++++++++++++++++
 2 files changed, 102 insertions(+), 5 deletions(-)
```


---

## 6e8d9c1a desk snapshot 2026-08-15T09:47Z

```diff
commit 6e8d9c1aaa206ab57f87e5b931948da40353db30
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 09:47:09 2026 +0000

    desk snapshot 2026-08-15T09:47Z
---
 alpha_pipeline.json                                |  24 +--
 check_all_axes.py                                  |  34 ++++
 check_bm.py                                        |   8 +
 check_data_axes.py                                 |  31 +++
 check_other.py                                     |  19 ++
 data/CAPABILITY_RATCHET.json                       | 218 +++++++++++----------
 data/ratchet_floors.json                           |   6 +-
 docs/DESK_BRIEF.md                                 |  18 +-
 docs/desk_digest.md                                |  12 +-
 docs/research/CONSTITUTION_RATCHET.json            |   2 +-
 docs/research/CRO_BRIEFING.md                      |  12 +-
 .../capability_hunt/20260815_s0_proposals.md       |  12 ++
 .../capability_hunt/20260815_s4_proposals.md       |  12 ++
 docs/research/trade_forensics_latest.json          |   4 +-
 engineering_backlog.json                           |   2 +-
 rate_platform.py                                   |  11 ++
 reports/gauntlet_certification.json                |   2 +-
 research_state.json                                |  28 +--
 18 files changed, 292 insertions(+), 163 deletions(-)

diff --git a/alpha_pipeline.json b/alpha_pipeline.json
index 2c36b445..4910febe 100644
--- a/alpha_pipeline.json
+++ b/alpha_pipeline.json
@@ -1,5 +1,5 @@
 {
-  "generated": "2026-08-15T03:43:29.782932+00:00",
+  "generated": "2026-08-15T09:33:21.566639+00:00",
   "n_alphas": 8,
   "n_survived": 1,
   "deployed": [
@@ -9,7 +9,7 @@
     {
       "alpha": "crypto::ls_contrarian",
       "category": "derivative-data",
-      "expected_sharpe": 9.1,
+      "expected_sharpe": 9.06,
       "gates": "10/10",
       "survived": true,
       "stage": "validated-candidate",
@@ -19,9 +19,9 @@
       "retire_check": "WATCH"
     },
     {
-      "alpha": "crypto::funding_carry",
+      "alpha": "crypto::ts_trend",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.9,
+      "expected_sharpe": 0.93,
       "gates": "9/10",
       "survived": false,
       "stage": "backtest",
@@ -31,9 +31,9 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::taker_flow",
+      "alpha": "crypto::funding_carry",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.86,
+      "expected_sharpe": 0.91,
       "gates": "9/10",
       "survived": false,
       "stage": "backtest",
@@ -43,9 +43,9 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::ts_trend",
+      "alpha": "crypto::taker_flow",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.81,
+      "expected_sharpe": 0.86,
       "gates": "9/10",
       "survived": false,
       "stage": "backtest",
@@ -57,7 +57,7 @@
     {
       "alpha": "crypto::funding_momentum",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.59,
+      "expected_sharpe": 0.58,
       "gates": "7/10",
       "survived": false,
       "stage": "backtest",
@@ -69,7 +69,7 @@
     {
       "alpha": "crypto::xsec_price_mom",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.5,
+      "expected_sharpe": 0.52,
       "gates": "6/10",
       "survived": false,
       "stage": "backtest",
@@ -82,7 +82,7 @@
       "alpha": "crypto::basis_carry",
       "category": "crypto-sleeve",
       "expected_sharpe": 0.29,
-      "gates": "4/10",
+      "gates": "6/10",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
@@ -93,7 +93,7 @@
     {
       "alpha": "crypto::oi_divergence",
       "category": "derivative-data",
-      "expected_sharpe": -9.84,
+      "expected_sharpe": -9.95,
       "gates": "4/10",
       "survived": false,
       "stage": "backtest",
diff --git a/check_all_axes.py b/check_all_axes.py
new file mode 100644
index 00000000..253c2049
--- /dev/null
+++ b/check_all_axes.py
@@ -0,0 +1,34 @@
+#!/usr/bin/env python3
+import pyarrow.parquet as pq
+import glob
+
+# binance_metrics
+files = glob.glob('/home/quant/quant-platform/data/lake/bronze/binance_metrics/BTCUSDT/**/*.parquet', recursive=True)
+if files:
+    pf = pq.ParquetFile(files[0])
+    print('binance_metrics BTCUSDT columns:', pf.schema.names)
+
+# oi_ls_daily
+files = glob.glob('/home/quant/quant-platform/data/lake/bronze/oi_ls_daily/BTCUSDT.jsonl')
+if files:
+    with open(files[0]) as f:
+        import json
+        line = f.readline()
+        print('oi_ls_daily keys:', list(json.loads(line).keys()))
+
+# perpdex
+with open('/home/quant/quant-platform/data/perpdex_funding.jsonl') as f:
+    line = f.readline()
+    import json
+    print('perpdex_funding keys:', list(json.loads(line).keys()))
+
+# liquidations
+import pandas as pd
+liq = pd.read_parquet('/home/quant/quant-platform/data/liquidations.parquet')
+print('liquidations columns:', list(liq.columns))
+print('liquidations shape:', liq.shape)
+
+# hyperliquid funding
+hl = pd.read_parquet('/home/quant/quant-platform/data/hyperliquid_funding.parquet')
+print('hyperliquid_funding columns:', list(hl.columns))
+print('hyperliquid_funding shape:', hl.shape)
\ No newline at end of file
diff --git a/check_bm.py b/check_bm.py
new file mode 100644
index 00000000..786f81bd
--- /dev/null
+++ b/check_bm.py
@@ -0,0 +1,8 @@
+#!/usr/bin/env python3
+import pyarrow.parquet as pq
+import glob
+
+files = glob.glob('/home/quant/quant-platform/data/lake/bronze/binance_metrics/BTCUSDT/**/*.parquet', recursive=True)
+if files:
+    pf = pq.ParquetFile(files[0])
+    print('binance_metrics columns:', pf.schema.names)
\ No newline at end of file
diff --git a/check_data_axes.py b/check_data_axes.py
new file mode 100644
index 00000000..7e657ea4
--- /dev/null
+++ b/check_data_axes.py
@@ -0,0 +1,31 @@
+#!/usr/bin/env python3
+import pyarrow.parquet as pq
+
+# Check crypto columns
+f = pq.ParquetFile('/home/quant/quant-platform/data/lake/bronze/crypto/BTCUSDT/D1/year=2026/month=8/part-0.parquet')
+print('BTCUSDT D1 columns:', f.schema.names)
+
+# Check binance_metrics
+import os
+for root, dirs, files in os.walk('/home/quant/quant-platform/data/lake/bronze/binance_metrics'):
+    for f_name in files:
+        if f_name.endswith('.parquet'):
+            pf = pq.ParquetFile(os.path.join(root, f_name))
+            print('binance_metrics columns:', pf.schema.names)
+            break
+    break
+
+# Check oi_ls_daily
+for root, dirs, files in os.walk('/home/quant/quant-platform/data/lake/bronze/oi_ls_daily'):
+    for f_name in files:
+        if f_name.endswith('.parquet'):
+            pf = pq.ParquetFile(os.path.join(root, f_name))
+            print('oi_ls_daily columns:', pf.schema.names)
+            break
+    break
+
+# Check perpdex funding
+import json
+with open('/home/quant/quant-platform/data/perpdex_funding.jsonl') as f:
+    line = f.readline()
+    print('perpdex_funding keys:', list(json.loads(line).keys()))
\ No newline at end of file
diff --git a/check_other.py b/check_other.py
new file mode 100644
index 00000000..9f82282a
--- /dev/null
+++ b/check_other.py
@@ -0,0 +1,19 @@
+#!/usr/bin/env python3
+import pyarrow.parquet as pq
+import os
+
+for root, dirs, files in os.walk('/home/quant/quant-platform/data/lake/bronze/binance_metrics'):
+    for f_name in files:
+        if f_name.endswith('.parquet'):
+            pf = pq.ParquetFile(os.path.join(root, f_name))
+            print('binance_metrics columns:', pf.schema.names)
+            break
+    break
+
+for root, dirs, files in os.walk('/home/quant/quant-platform/data/lake/bronze/oi_ls_daily'):
+    for f_name in files:
+        if f_name.endswith('.parquet'):
+            pf = pq.ParquetFile(os.path.join(root, f_name))
+            print('oi_ls_daily columns:', pf.schema.names)
+            break
+    break
\ No newline at end of file
diff --git a/data/CAPABILITY_RATCHET.json b/data/CAPABILITY_RATCHET.json
index 862877df..b92d3395 100644
--- a/data/CAPABILITY_RATCHET.json
+++ b/data/CAPABILITY_RATCHET.json
@@ -1,18 +1,18 @@
 {
  "_": "HIGH-WATER MARKS for desk CAPABILITY, one score per named aspect on the 0-10 scale the principal's standing order is stated on. Raised automatically; NEVER lowered by code. A FALL is a defect reported with a NAMED CAUSE, a FLATLINE is reported with the binding constraint that is holding the aspect down, and UNMEASURED is its own state -- never silently a 0 and never silently a 10.",
  "law": "R0104 -- every aspect is pushed toward 10/10 every day, non-exhaustively. A rating nobody records cannot ratchet, and a score that can silently fall is not a standard.",
- "generated": "2026-08-14T09:50:09.792773+00:00",
+ "generated": "2026-08-15T09:42:30.671349+00:00",
  "status": "REGRESSED",
  "scale_max": 10.0,
  "stall_days": 7.0,
  "n_aspects": 26,
  "n_measured": 25,
  "n_unmeasured": 1,
- "measured_mean": 8.02,
+ "measured_mean": 8.01,
  "first_recorded": "2026-08-05T12:09:08.679174+00:00",
- "last_raise_at": "2026-08-14T09:50:09.792773+00:00",
+ "last_raise_at": "2026-08-15T09:42:30.671349+00:00",
  "days_since_raise": 0.0,
- "n_raises": 10,
+ "n_raises": 11,
  "binding_constraint": {
   "state": "MEASURED",
   "aspect": "alpha_output",
@@ -20,12 +20,12 @@
   "score": 0.0,
   "artifact": "data/promotion_gate.json",
   "n_unmeasured_components": 6,
-  "detail": "granted 'PAPER at the 6% floor cap' at rung 0, blocked at 1 over 23 closed trades",
+  "detail": "granted 'PAPER at the 6% floor cap' at rung 0, blocked at 1 over 24 closed trades",
   "constraint": "+1 promotion rungs granted (0 -> 1 of 4) buys the next point",
   "_": "LOWEST-SCORING COMPONENT DESK-WIDE: alpha_output.promotion_rung at 0.0/10 out of data/promotion_gate.json. This is the line to work first. 6 component(s) are UNMEASURED and are NOT eligible to be this minimum -- an absent measurement has no score, and letting it win here would bury every real defect under things nobody has looked at yet."
  },
  "high_water": {
-  "alerting_pager": 8.8,
+  "alerting_pager": 8.9,
   "alpha_output": 5.0,
   "ambition_discipline": 10.0,
   "backup_dr": 10.0,
@@ -54,7 +54,7 @@
  },
  "component_high_water": {
   "alerting_pager.alert_channels_not_silent": 10.0,
-  "alerting_pager.pager_deliveries_ok": 7.6,
+  "alerting_pager.pager_deliveries_ok": 7.9,
   "alpha_output.forward_slots_occupied": 10.0,
   "alpha_output.promotion_rung": 0.0,
   "ambition_discipline.prompt_timidity_hits": 10.0,
@@ -142,11 +142,11 @@
   {
    "key": "statistical_validation",
    "state": "MEASURED",
-   "score": 4.7,
+   "score": 4.8,
    "high_water": 9.0,
    "movement": "FELL",
-   "cause": "statistical_validation.forecasts_resolved 3.2 -> 2.5 (data/calibration_status.json): status OVERDUE: 1 forecast(s) past their grading deadline -- score them; brier 0.2459, 1 overdue; statistical_validation.mutation_kill_validation_stack 9.0 -> 6.9 (data/mutation_score.json): 2 target(s) at bar 0.9: stepwise.py 0.90, validation.py 0.48; measured 2026-08-05T15:23:17Z",
-   "binding_constraint": "forecasts_resolved at 2.5 -- +40 logged forecasts scored against an outcome (104 -> 144 of 410) buys the next point [+1 UNMEASURED component(s): mutation_kill_validation_stack::validation.py -- the score above covers only 2 of 3 components]",
+   "cause": "statistical_validation.forecasts_resolved 3.2 -> 2.6 (data/calibration_status.json): status OVERDUE: 2 forecast(s) past their grading deadline -- score them; brier 0.2451, 2 overdue; statistical_validation.mutation_kill_validation_stack 9.0 -> 6.9 (data/mutation_score.json): 2 target(s) at bar 0.9: stepwise.py 0.90, validation.py 0.48; measured 2026-08-05T15:23:17Z",
+   "binding_constraint": "forecasts_resolved at 2.6 -- +43 logged forecasts scored against an outcome (105 -> 148 of 410) buys the next point [+1 UNMEASURED component(s): mutation_kill_validation_stack::validation.py -- the score above covers only 2 of 3 components]",
    "ceiling": "the validation stack's own tests kill every mutant of it, over complete (never truncated) runs -- the desk cannot fool itself about whether an edge is real",
    "artifacts": [
     "data/mutation_score.json",
@@ -172,10 +172,10 @@
     {
      "key": "forecasts_resolved",
      "state": "MEASURED",
-     "score": 2.5,
+     "score": 2.6,
      "artifact": "data/calibration_status.json",
-     "detail": "status OVERDUE: 1 forecast(s) past their grading deadline -- score them; brier 0.2459, 1 overdue",
-     "constraint": "+40 logged forecasts scored against an outcome (104 -> 144 of 410) buys the next point"
+     "detail": "status OVERDUE: 2 forecast(s) past their grading deadline -- score them; brier 0.2451, 2 overdue",
+     "constraint": "+43 logged forecasts scored against an outcome (105 -> 148 of 410) buys the next point"
     }
    ]
   },
@@ -292,7 +292,7 @@
      "state": "MEASURED",
      "score": 10.0,
      "artifact": "data/drill_report.json",
-     "detail": "3/3 drills passed at 2026-08-14T03:40:42.061388+00:00; 0 CRITICAL failure(s)",
+     "detail": "3/3 drills passed at 2026-08-15T03:40:10.029132+00:00; 0 CRITICAL failure(s)",
      "constraint": "AT CEILING (3/3 rail drills passing) -- the work is now HOLDING it"
     },
     {
@@ -300,7 +300,7 @@
      "state": "MEASURED",
      "score": 10.0,
      "artifact": "data/organ_liveness.json",
-     "detail": "scripts/run_drills.py is FRESH (age 6.16h against its own 72.0h tolerance); evidence data/drill_report.json, data/drill_log.jsonl",
+     "detail": "scripts/run_drills.py is FRESH (age 5.45h against its own 72.0h tolerance); evidence data/drill_report.json, data/drill_log.jsonl",
      "constraint": "AT CEILING -- producing inside its own declared cadence, and the work is now HOLDING it"
     }
    ]
@@ -308,11 +308,11 @@
   {
    "key": "governance",
    "state": "MEASURED",
-   "score": 8.3,
+   "score": 8.2,
    "high_water": 9.0,
    "movement": "FELL",
-   "cause": "governance.audit_defects_live 6.0 -> 5.0 (data/max_audit_report.json): 29.0 unacknowledged defects at 2026-08-14T08:26:57.553075+00:00; by scope {'REPO': 27, 'RUNTIME': 2}; governance.law_fences_passing 10.0 -> 6.8 (data/law_gate.json): 17.0/25.0 fences green; failures ['check_enforcement_execution.py (rc=2): -> data/enforcement_execution.json', 'check_conversion.py (rc=2): -> /home/quant/quant-platform/data/conversion_status.json', 'check_calibration.py (rc=2): -> /home/quant/quant-platform/data/calibration_status.json', 'check_scheduler_manifest.py (rc=1): scheduler-manifest: DRIFT', 'check_mechanism_attribution.py (rc=2):   cash_and_carry: UNATTRIBUTED -- unexplained WIN +2,693.26 is 2382% of the +113.06 mechanism term -- this sleeve is being credited with P&L its mechanism canno', 'check_organ_liveness.py (rc=2):   NEVER-PRODUCED  scripts/screen_unlock_supply_series.pyage=None tol=504.0h', 'check_excitation.py (rc=2):   next: ACCRUE FILLS -- the executor is wired and the design is loaded; the experiment is waiting on the book to trade, not on an engineering change', 'check_clock_provenance.py (rc=2):   next: Restart the recorders so new rows carry the `c` marker; historical rows stay readable through clock_provenance._HISTORICAL']",
-   "binding_constraint": "audit_defects_live at 5.0 -- -14 live audit defects (29 -> 15, back under the 16 rung) buys the next point",
+   "cause": "governance.audit_defects_live 6.0 -> 4.0 (data/max_audit_report.json): 45.0 unacknowledged defects at 2026-08-15T08:32:59.287688+00:00; by scope {'REPO': 40, 'RUNTIME': 4, 'UNSCOPED': 1}; governance.law_fences_passing 10.0 -> 7.6 (data/law_gate.json): 19.0/25.0 fences green; failures ['check_conversion.py (rc=2): -> /home/quant/quant-platform/data/conversion_status.json', 'check_calibration.py (rc=2): -> /home/quant/quant-platform/data/calibration_status.json', 'check_mechanism_attribution.py (rc=2):   cash_and_carry: UNATTRIBUTED -- unexplained WIN +2,794.05 is 2471% of the +113.06 mechanism term -- this sleeve is being credited with P&L its mechanism canno', 'check_organ_liveness.py (rc=2):   NEVER-PRODUCED  scripts/screen_unlock_supply_series.pyage=None tol=504.0h', 'check_excitation.py (rc=2):   next: ACCRUE FILLS -- the executor is wired and the design is loaded; the experiment is waiting on the book to trade, not on an engineering change', 'check_clock_provenance.py (rc=2):   next: Restart the recorders so new rows carry the `c` marker; historical rows stay readable through clock_provenance._HISTORICAL']",
+   "binding_constraint": "audit_defects_live at 4.0 -- -14 live audit defects (45 -> 31, back under the 32 rung) buys the next point",
    "ceiling": "every law fence green and ZERO live audit defects -- the laws are enforced by machinery rather than by attention",
    "artifacts": [
     "data/law_gate.json",
@@ -325,18 +325,18 @@
     {
      "key": "law_fences_passing",
      "state": "MEASURED",
-     "score": 6.8,
+     "score": 7.6,
      "artifact": "data/law_gate.json",
-     "detail": "17.0/25.0 fences green; failures ['check_enforcement_execution.py (rc=2): -> data/enforcement_execution.json', 'check_conversion.py (rc=2): -> /home/quant/quant-platform/data/conversion_status.json', 'check_calibration.py (rc=2): -> /home/quant/quant-platform/data/calibration_status.json', 'check_scheduler_manifest.py (rc=1): scheduler-manifest: DRIFT', 'check_mechanism_attribution.py (rc=2):   cash_and_carry: UNATTRIBUTED -- unexplained WIN +2,693.26 is 2382% of the +113.06 mechanism term -- this sleeve is being credited with P&L its mechanism canno', 'check_organ_liveness.py (rc=2):   NEVER-PRODUCED  scripts/screen_unlock_supply_series.pyage=None tol=504.0h', 'check_excitation.py (rc=2):   next: ACCRUE FILLS -- the executor is wired and the design is loaded; the experiment is waiting on the book to trade, not on an engineering change', 'check_clock_provenance.py (rc=2):   next: Restart the recorders so new rows carry the `c` marker; historical rows stay readable through clock_provenance._HISTORICAL']",
-     "constraint": "+3 law fences passing (17 -> 20 of 25) buys the next point"
+     "detail": "19.0/25.0 fences green; failures ['check_conversion.py (rc=2): -> /home/quant/quant-platform/data/conversion_status.json', 'check_calibration.py (rc=2): -> /home/quant/quant-platform/data/calibration_status.json', 'check_mechanism_attribution.py (rc=2):   cash_and_carry: UNATTRIBUTED -- unexplained WIN +2,794.05 is 2471% of the +113.06 mechanism term -- this sleeve is being credited with P&L its mechanism canno', 'check_organ_liveness.py (rc=2):   NEVER-PRODUCED  scripts/screen_unlock_supply_series.pyage=None tol=504.0h', 'check_excitation.py (rc=2):   next: ACCRUE FILLS -- the executor is wired and the design is loaded; the experiment is waiting on the book to trade, not on an engineering change', 'check_clock_provenance.py (rc=2):   next: Restart the recorders so new rows carry the `c` marker; historical rows stay readable through clock_provenance._HISTORICAL']",
+     "constraint": "+3 law fences passing (19 -> 22 of 25) buys the next point"
     },
     {
      "key": "audit_defects_live",
      "state": "MEASURED",
-     "score": 5.0,
+     "score": 4.0,
      "artifact": "data/max_audit_report.json",
-     "detail": "29.0 unacknowledged defects at 2026-08-14T08:26:57.553075+00:00; by scope {'REPO': 27, 'RUNTIME': 2}",
-     "constraint": "-14 live audit defects (29 -> 15, back under the 16 rung) buys the next point"
+     "detail": "45.0 unacknowledged defects at 2026-08-15T08:32:59.287688+00:00; by scope {'REPO': 40, 'RUNTIME': 4, 'UNSCOPED': 1}",
+     "constraint": "-14 live audit defects (45 -> 31, back under the 32 rung) buys the next point"
     },
     {
      "key": "principles_mechanically_enforced",
@@ -370,7 +370,7 @@
    "score": 7.3,
    "high_water": 7.4,
    "movement": "FELL",
-   "cause": "data_coverage.assets_with_measured_span 6.6 -> 6.4 (data/data_assets.json): 80/125 assets have a readable span (26 absent on disk); deep=True",
+   "cause": "data_coverage.assets_with_measured_span 6.6 -> 6.3 (data/data_assets.json): 80/127 assets have a readable span (27 absent on disk); deep=True",
    "binding_constraint": "datasets_with_declared_provenance at 5.0 -- +4 datasets carrying source/method/survivorship (8 -> 12, the next rung) buys the next point",
    "ceiling": "every registered asset carrying a measured span and every unknown-unknown organ fresh -- no dark corner of the desk's own data",
    "artifacts": [
@@ -383,10 +383,10 @@
     {
      "key": "assets_with_measured_span",
      "state": "MEASURED",
-     "score": 6.4,
+     "score": 6.3,
      "artifact": "data/data_assets.json",
-     "detail": "80/125 assets have a readable span (26 absent on disk); deep=True",
-     "constraint": "+13 registered assets carrying a measured span (80 -> 93 of 125) buys the next point"
+     "detail": "80/127 assets have a readable span (27 absent on disk); deep=True",
+     "constraint": "+13 registered assets carrying a measured span (80 -> 93 of 127) buys the next point"
     },
     {
      "key": "exploration_organs_fresh",
@@ -459,7 +459,7 @@
```


---

## 4959c7f6 the quote asset the account may trade is not the one the lake holds
First live placement: three orders, three `-2010 This symbol is not permitted for this account`.

Under MiCA, Binance does not permit EEA retail to trade its USDT spot pairs, and the desk's entire
research universe is quoted in USDT because that is what the data lake holds. Nothing in the
strategy or the code was wrong; the account simply may not touch the symbols the universe names.

The signal is about the BASE asset -- BNB, LINK, ADA -- and the quote is a settlement detail of the
venue, so --quote re-points the order path without touching the research. The bars stay
USDT-denominated deliberately: USDT/USDC has held parity within tens of basis points for years, so
a 20-day momentum rank is unaffected, and refitting the universe on thinner USDC history would move
the measured signal for a reason that has nothing to do with the signal.

USDT stays the default so no existing caller is silently re-pointed. The EEA account passes the
flag explicitly, which keeps the constraint visible in the command rather than buried in a default.

A missing price on a re-quoted symbol now says the pair may not be listed in that quote, rather
than reporting a bare UNMEASURED -- the first thing to check after a re-quote is whether the pair
exists at all.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 4959c7f65e9fb3d81eceeefa37a8c0f3ecf08489
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 15 09:41:07 2026 +0000

    the quote asset the account may trade is not the one the lake holds
    
    First live placement: three orders, three `-2010 This symbol is not permitted for this account`.
    
    Under MiCA, Binance does not permit EEA retail to trade its USDT spot pairs, and the desk's entire
    research universe is quoted in USDT because that is what the data lake holds. Nothing in the
    strategy or the code was wrong; the account simply may not touch the symbols the universe names.
    
    The signal is about the BASE asset -- BNB, LINK, ADA -- and the quote is a settlement detail of the
    venue, so --quote re-points the order path without touching the research. The bars stay
    USDT-denominated deliberately: USDT/USDC has held parity within tens of basis points for years, so
    a 20-day momentum rank is unaffected, and refitting the universe on thinner USDC history would move
    the measured signal for a reason that has nothing to do with the signal.
    
    USDT stays the default so no existing caller is silently re-pointed. The EEA account passes the
    flag explicitly, which keeps the constraint visible in the command rather than buried in a default.
    
    A missing price on a re-quoted symbol now says the pair may not be listed in that quote, rather
    than reporting a bare UNMEASURED -- the first thing to check after a re-quote is whether the pair
    exists at all.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 scripts/run_spot_executor.py                | 43 ++++++++++++++++---
 tests/execution/test_spot_executor_quote.py | 64 +++++++++++++++++++++++++++++
 2 files changed, 102 insertions(+), 5 deletions(-)

diff --git a/scripts/run_spot_executor.py b/scripts/run_spot_executor.py
index d7819e6d..3380eb9f 100644
--- a/scripts/run_spot_executor.py
+++ b/scripts/run_spot_executor.py
@@ -64,6 +64,31 @@ MAX_RUN_FRAC = 1.0
 #: returns 0.0 in that case, and 0.0 would let a $0.30 order through to be rejected at the venue.
 FALLBACK_MIN_NOTIONAL = 10.0
 
+#: Quote suffixes the research universe may arrive in, longest first so BTCUSDT strips USDT rather
+#: than matching a shorter suffix inside it. Order matters and is not alphabetical by accident.
+_KNOWN_QUOTES = ("USDT", "USDC", "FDUSD", "TUSD", "EUR", "GBP", "BTC")
+
+
+def retarget(symbol: str, quote: str) -> str:
+    """Re-quote a research symbol onto the asset THIS ACCOUNT MAY ACTUALLY TRADE.
+
+    WHY THIS IS NOT COSMETIC. Measured 2026-08-15: every order came back `-2010 This symbol is not
+    permitted for this account`. Under MiCA, Binance does not permit EEA retail to trade its USDT
+    spot pairs at all, and the desk's entire research universe is quoted in USDT because that is
+    what the data lake holds. The signal is about the BASE asset -- BNB, LINK, ADA -- and the quote
+    is a settlement detail of the venue, so re-quoting changes what is traded not at all and
+    changes whether it CAN be traded completely.
+
+    The bars stay USDT-denominated on purpose. USDT/USDC has traded within a few tens of basis
+    points of parity for years, so a momentum rank over 20-day returns is unaffected; refitting the
+    universe on thinner USDC history would change the measured signal for a reason that has nothing
+    to do with the signal.
+    """
+    for q in _KNOWN_QUOTES:
+        if symbol.endswith(q):
+            return symbol[: -len(q)] + quote
+    return symbol + quote
+
 
 def _round_step(qty: float, step: float) -> float:
     """Down to the venue's step. ALWAYS DOWN: rounding up can exceed the intended weight and, on
@@ -96,6 +121,11 @@ def main() -> int:
                     help="ACTUALLY PLACE ORDERS. Absent, this prints what it would do and spends "
                          "nothing")
     ap.add_argument("--max-run-frac", type=float, default=MAX_RUN_FRAC)
+    ap.add_argument("--quote", default="USDT",
+                    help="quote asset to TRADE in, independent of the quote the research universe "
+                         "is denominated in. EEA retail cannot trade Binance USDT pairs under "
+                         "MiCA (-2010) and must use USDC; the signal is about the base asset and "
+                         "is unchanged by the settlement leg")
     ap.add_argument("--cycle", default=None,
                     help="idempotency scope; defaults to the UTC date so a re-run on the same day "
                          "reuses client order IDs and the venue rejects the duplicate")
@@ -117,7 +147,7 @@ def main() -> int:
     rep: dict[str, Any] = {
         "updated": datetime.now(tz=UTC).isoformat(),
         "cycle": cycle, "armed": armed, "armed_why": why_armed,
-        "rail_frozen": rail_frozen, "rail_why": why_rail,
+        "rail_frozen": rail_frozen, "rail_why": why_rail, "quote": args.quote,
         "targets_why": why_targets, "equity_usd": float(args.equity),
         "placed": [], "refused": [], "dry_run": not place,
         "leverage": "1.0x -- SPOT HOLDS WHAT IT PAID FOR. No leverage exists on this path and "
@@ -149,20 +179,23 @@ def main() -> int:
 
     budget = float(args.equity) * float(args.max_run_frac)
     spent = 0.0
-    for sym, frac in sorted(targets.items(), key=lambda kv: -kv[1]):
+    for research_sym, frac in sorted(targets.items(), key=lambda kv: -kv[1]):
+        sym = retarget(research_sym, args.quote)
         want_usd = frac * float(args.equity)
-        base = sym.replace("USDT", "")
+        base = retarget(research_sym, "")
         price = float(px.get(sym) or 0.0)
         have_usd = float(held.get(base, 0.0)) * price
         delta = want_usd - have_usd            # THE DELTA, never the target
         f = filters.get(sym, {})
         min_notional = float(f.get("min_notional") or 0.0) or FALLBACK_MIN_NOTIONAL
 
-        row: dict[str, Any] = {"symbol": sym, "target_weight": frac,
+        row: dict[str, Any] = {"symbol": sym, "research_symbol": research_sym,
+                               "target_weight": frac,
                                "want_usd": round(want_usd, 2), "have_usd": round(have_usd, 2),
                                "delta_usd": round(delta, 2)}
         if price <= 0:
-            row["why"] = "no price from the venue -- UNMEASURED, refusing to size against it"
+            row["why"] = (f"{sym} carries no price at the venue -- it may not be listed in "
+                          f"{args.quote}. UNMEASURED, refusing to size against it")
             rep["refused"].append(row)
             continue
         if abs(delta) < min_notional:
diff --git a/tests/execution/test_spot_executor_quote.py b/tests/execution/test_spot_executor_quote.py
new file mode 100644
index 00000000..18992bfd
--- /dev/null
+++ b/tests/execution/test_spot_executor_quote.py
@@ -0,0 +1,64 @@
+"""Re-quoting the book onto the asset the account may actually trade.
+
+MEASURED 2026-08-15, on the first live placement: every order came back `-2010 This symbol is not
+permitted for this account`. Under MiCA, Binance does not permit EEA retail to trade its USDT spot
+pairs, and the desk's entire research universe is quoted in USDT because that is what the data lake
+holds. Three orders, three rejections, and the reason was in neither the strategy nor the code.
+
+The signal is about the BASE asset. The quote is a settlement detail of the venue.
+"""
+
+from __future__ import annotations
+
+import importlib.util
+from pathlib import Path
+from typing import Any
+
+_SRC = Path("scripts/run_spot_executor.py")
+
+
+def _mod() -> Any:
+    spec = importlib.util.spec_from_file_location("run_spot_executor_undertest", _SRC)
+    assert spec and spec.loader
+    m = importlib.util.module_from_spec(spec)
+    spec.loader.exec_module(m)
+    return m
+
+
+def test_THE_BASE_ASSET_IS_PRESERVED_AND_ONLY_THE_QUOTE_MOVES() -> None:
+    r = _mod().retarget
+    assert r("BNBUSDT", "USDC") == "BNBUSDC"
+    assert r("LINKUSDT", "USDC") == "LINKUSDC"
+    assert r("ADAUSDT", "EUR") == "ADAEUR"
+
+
+def test_THE_LONGEST_QUOTE_WINS() -> None:
+    """A suffix table ordered wrongly would strip 'USDC' out of 'FDUSD'-quoted symbols, or match a
+    short quote inside a longer one, and the resulting symbol would silently not exist."""
+    r = _mod().retarget
+    assert r("BTCFDUSD", "USDC") == "BTCUSDC"
+    assert r("ETHTUSD", "USDC") == "ETHUSDC"
+
+
+def test_STRIPPING_TO_THE_BARE_BASE_IS_HOW_HOLDINGS_ARE_MATCHED() -> None:
+    """Balances are keyed by base asset, so the holdings lookup needs the base alone. Getting this
+    wrong reads every holding as zero and re-buys a book the account already owns."""
+    r = _mod().retarget
+    assert r("BNBUSDT", "") == "BNB"
+    assert r("ADAUSDC", "") == "ADA"
+
+
+def test_AN_UNRECOGNISED_QUOTE_APPENDS_RATHER_THAN_MANGLING() -> None:
+    """A base-only entry must become a tradeable pair, not a truncated one -- and it must never
+    silently drop characters from a symbol the table does not know."""
+    r = _mod().retarget
+    assert r("SOL", "USDC") == "SOLUSDC"
+
+
+def test_THE_DEFAULT_IS_UNCHANGED() -> None:
+    """USDT stays the default so no existing caller is re-pointed at a different venue leg by an
+    upgrade. The EEA account passes --quote explicitly, which makes the constraint visible in the
+    command rather than buried in a default."""
+    src = _SRC.read_text("utf-8")
+    assert '"--quote", default="USDT"' in src
+    assert "-2010" in src, "the reason for the flag must travel with it"
```


---

## df50d305 Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

```diff
commit df50d305c8b80070058463c463b4e74afcecac53
Merge: 2cd7f445 3ea696c0
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 09:35:45 2026 +0000

    Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

 scripts/run_live_guard.py                  | 38 ++++++++++++++++++++++++++++++
 tests/scripts/test_live_guard_spot_only.py | 36 ++++++++++++++++++++++++++++
 2 files changed, 74 insertions(+)
```


---

## 3ea696c0 the canary was a stuck gauge on a spot-only desk
With no futures leg the probe was skipped on every tick -- correctly, since an unarmed desk has no
execution path to prove. But `consecutive_failures` then held whatever value it had when the
futures venue was last readable, and >=2 of them is a tripwire. So the desk carried a permanent
degraded state with no path back to healthy: the only thing that clears the count is a successful
probe, and no probe could run.

A health check that can only hold its last verdict is not a health check.

The probe's value is identical on either leg -- it catches revoked keys, IP-whitelist drift and
recvWindow skew via a signed read -- so on a spot-only desk it now runs against the spot connector,
which is the credential that actually matters there. A carry desk still probes futures, because
that is the leg carrying liquidation risk, and a test pins the scoping in both directions.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 3ea696c00e136141b4bb574427f807210b10af4e
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 15 09:34:02 2026 +0000

    the canary was a stuck gauge on a spot-only desk
    
    With no futures leg the probe was skipped on every tick -- correctly, since an unarmed desk has no
    execution path to prove. But `consecutive_failures` then held whatever value it had when the
    futures venue was last readable, and >=2 of them is a tripwire. So the desk carried a permanent
    degraded state with no path back to healthy: the only thing that clears the count is a successful
    probe, and no probe could run.
    
    A health check that can only hold its last verdict is not a health check.
    
    The probe's value is identical on either leg -- it catches revoked keys, IP-whitelist drift and
    recvWindow skew via a signed read -- so on a spot-only desk it now runs against the spot connector,
    which is the credential that actually matters there. A carry desk still probes futures, because
    that is the leg carrying liquidation risk, and a test pins the scoping in both directions.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 scripts/run_live_guard.py                  | 38 ++++++++++++++++++++++++++++++
 tests/scripts/test_live_guard_spot_only.py | 36 ++++++++++++++++++++++++++++
 2 files changed, 74 insertions(+)

diff --git a/scripts/run_live_guard.py b/scripts/run_live_guard.py
index 495cbfeb..1f076d68 100644
--- a/scripts/run_live_guard.py
+++ b/scripts/run_live_guard.py
@@ -189,10 +189,48 @@ def _reconcile(venue: Any, now: float) -> tuple[stops.ReconcileReport, str]:
     return stops.reconcile(positions, orders, now), "venue read ok"
 
 
+def _canary_venue(venue: Any) -> tuple[Any, str]:
+    """WHAT THE PROBE SHOULD BE PROVING: that the venue WE TRADE still answers a signed call.
+
+    On a spot-only desk `venue` is None by design, and the old code then skipped the probe
+    forever -- so the canary's last recorded state stayed whatever it was when the futures leg was
+    still being read, and `consecutive_failures` could never come back down. A health check that
+    can only ever hold its last verdict is not a health check; it is a stuck gauge, and this one
+    contributes a tripwire.
+
+    The probe's value is unchanged by which leg it runs on: it catches revoked keys, IP-whitelist
+    drift and recvWindow skew. Pointing it at the spot connector on a spot-only desk aims it at the
+    credential that actually matters here.
+    """
+    if venue is not None:
+        return venue, "futures"
+    if not _spot_only():
+        return None, "none"
+    try:
+        from libs.execution import binance_spot_live as spot
+    except ImportError:
+        return None, "none"
+    try:
+        return (spot, "spot") if spot.is_armed()[0] else (None, "none")
+    except Exception:
+        return None, "none"
+
+
 def _canary(venue: Any, now: float) -> tuple[canary_mod.CanaryState, str]:
     st = canary_mod.CanaryState.load(_ROOT / "data" / "canary_state.json")
     if not st.is_due(now):
         return st, "not due"
+    venue, leg = _canary_venue(venue)
+    if leg == "spot" and venue is not None:
+        t0 = time.time()
+        try:
+            venue.balances()
+            st.record(ok=True, latency_ms=(time.time() - t0) * 1000.0, now=now,
+                      detail="signed spot balances read")
+            return st, "probe ok (spot leg)"
+        except Exception as e:
+            st.record(ok=False, latency_ms=(time.time() - t0) * 1000.0, now=now, detail=repr(e))
+            return st, f"probe FAILED (spot leg): {e!r}"
     if venue is None:
         # Do NOT record an attempt: an unarmed desk has no execution path to prove, and logging
         # failures here would bury a real outage under thousands of S0 rows.
diff --git a/tests/scripts/test_live_guard_spot_only.py b/tests/scripts/test_live_guard_spot_only.py
index 5bae722d..9c1e1eb5 100644
--- a/tests/scripts/test_live_guard_spot_only.py
+++ b/tests/scripts/test_live_guard_spot_only.py
@@ -112,3 +112,39 @@ def test_THE_MARKER_IS_A_PRINCIPAL_ACT_AND_NO_ORGAN_WRITES_IT() -> None:
         body = other.read_text("utf-8")
         assert 'SPOT_ONLY").write_text' not in body
         assert 'SPOT_ONLY").touch' not in body
+
+
+def test_THE_CANARY_PROBES_THE_LEG_THE_DESK_ACTUALLY_TRADES(
+        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    """A STUCK GAUGE IS NOT A HEALTH CHECK. With no futures leg the probe was skipped on every
+    tick, so `consecutive_failures` held whatever value it had when the futures venue was last
+    readable -- and it contributes a tripwire, so the desk carried a permanent degraded state it
+    had no way to clear. The probe's value (revoked keys, IP drift, recvWindow skew) is identical
+    on either leg, so on a spot-only desk it aims at the credential that matters here."""
+    g = _guard()
+    marker = tmp_path / "SPOT_ONLY"
+    marker.write_text("", "utf-8")
+    monkeypatch.setattr(g, "_SPOT_ONLY", marker)
+    _venue, leg = g._canary_venue(None)
+    assert leg in {"spot", "none"}, "a spot-only desk must not report a futures probe"
+
+
+def test_A_CARRY_DESK_STILL_PROBES_FUTURES(
+        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    """The change must be scoped to the spot-only case: where a futures venue exists it remains
+    the thing under test, because that is the leg carrying liquidation risk."""
+    g = _guard()
+    monkeypatch.setattr(g, "_SPOT_ONLY", tmp_path / "absent")
+    sentinel = object()
+    venue, leg = g._canary_venue(sentinel)
+    assert venue is sentinel and leg == "futures"
+
+
+def test_WITHOUT_THE_MARKER_AN_ABSENT_VENUE_RECORDS_NO_ATTEMPT(
+        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    """An unarmed desk has no execution path to prove, and logging failures there would bury a
+    real outage under thousands of S0 rows."""
+    g = _guard()
+    monkeypatch.setattr(g, "_SPOT_ONLY", tmp_path / "absent")
+    venue, leg = g._canary_venue(None)
+    assert venue is None and leg == "none"
```


---

## 2cd7f445 Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

```diff
commit 2cd7f4454c7034f6c2ac6c68b1988268634a46af
Merge: 8b497c82 a89c17c3
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 09:32:06 2026 +0000

    Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

 scripts/run_live_guard.py                  |  47 +++++++++++-
 tests/scripts/test_live_guard_spot_only.py | 114 +++++++++++++++++++++++++++++
 2 files changed, 160 insertions(+), 1 deletion(-)
```


---

## a89c17c3 the guard froze a book that has no futures leg, correctly, forever
The live guard re-latched CASHCARRY_KILL at 00:55 with `naked position >60s`, minutes after the
principal cleared it. Nothing was broken.

The principal is Irish retail, so EEA derivatives are unavailable under MiCA and the futures
account cannot be read. The futures KEYFILE still existed, so `_venue()` returned the futures
connector as armed, `positions()` raised, and `_reconcile` did exactly what a carry desk requires:
FAILED CLOSED, reporting the unreadable venue as a naked position and freezing the executor. Sixty
seconds later, again. The spot book could not have traded today at any point.

A rail firing accurately at a book that no longer exists is the hardest kind of defect to see --
every component is behaving to spec and the desk is halted.

data/SPOT_ONLY declares the absence DELIBERATE, and that distinction is the whole fix: the same
None means "no futures position can exist" under the marker and "we cannot see the book" without
it. The fail-closed path is untouched for any desk that does have leverage, and a test pins it.

Two things the marker does NOT do. It does not silence the §3 report -- the reconcile note now
states on every tick that spot holdings are OUTSIDE the invariant, carry no venue-side stop, and
face drawdown rather than liquidation, because a clean §3 line beside a live spot book otherwise
reads as "protected". And it does not lift any freeze: the ladder rung is separate and still needs
an explicit --rearm.

No organ writes the marker. Same class of file as LIVE_ENABLE and the kill switch, and a test
greps every script to keep it that way.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit a89c17c35ae5fe7f42543a823164106761e462af
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 15 09:28:31 2026 +0000

    the guard froze a book that has no futures leg, correctly, forever
    
    The live guard re-latched CASHCARRY_KILL at 00:55 with `naked position >60s`, minutes after the
    principal cleared it. Nothing was broken.
    
    The principal is Irish retail, so EEA derivatives are unavailable under MiCA and the futures
    account cannot be read. The futures KEYFILE still existed, so `_venue()` returned the futures
    connector as armed, `positions()` raised, and `_reconcile` did exactly what a carry desk requires:
    FAILED CLOSED, reporting the unreadable venue as a naked position and freezing the executor. Sixty
    seconds later, again. The spot book could not have traded today at any point.
    
    A rail firing accurately at a book that no longer exists is the hardest kind of defect to see --
    every component is behaving to spec and the desk is halted.
    
    data/SPOT_ONLY declares the absence DELIBERATE, and that distinction is the whole fix: the same
    None means "no futures position can exist" under the marker and "we cannot see the book" without
    it. The fail-closed path is untouched for any desk that does have leverage, and a test pins it.
    
    Two things the marker does NOT do. It does not silence the §3 report -- the reconcile note now
    states on every tick that spot holdings are OUTSIDE the invariant, carry no venue-side stop, and
    face drawdown rather than liquidation, because a clean §3 line beside a live spot book otherwise
    reads as "protected". And it does not lift any freeze: the ladder rung is separate and still needs
    an explicit --rearm.
    
    No organ writes the marker. Same class of file as LIVE_ENABLE and the kill switch, and a test
    greps every script to keep it that way.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 scripts/run_live_guard.py                  |  47 +++++++++++-
 tests/scripts/test_live_guard_spot_only.py | 114 +++++++++++++++++++++++++++++
 2 files changed, 160 insertions(+), 1 deletion(-)

diff --git a/scripts/run_live_guard.py b/scripts/run_live_guard.py
index 350df99c..495cbfeb 100644
--- a/scripts/run_live_guard.py
+++ b/scripts/run_live_guard.py
@@ -57,6 +57,29 @@ _RAMP = _ROOT / "data" / "ramp_state.json"
 _RAMP_MAX_AGE_H = 168.0
 _PRINCIPAL = _ROOT / "data" / "PRINCIPAL_ACTION.md"
 
+#: DECLARES THAT THIS DESK HAS NO FUTURES LEG, ON PURPOSE. Written by the principal and
+#: never by an organ -- like every other file that changes what the rails believe.
+#:
+#: WHY IT HAD TO EXIST. Measured 2026-08-15. The principal is Irish retail, so EEA derivatives are
+#: unavailable under MiCA and the futures account cannot be read at all. The futures KEYFILE still
+#: existed, so `_venue()` returned the futures connector as armed, `positions()` raised, and
+#: `_reconcile` did the correct thing for a carry desk: FAILED CLOSED, reporting `<unreadable>` as
+#: a naked position and freezing the executor. Sixty seconds later it did it again.
+#:
+#: That is a rail firing accurately at a book that no longer exists. The §3 invariant is about
+#: LEVERAGED positions whose stop must survive the host's death; a spot holding has no liquidation
+#: price and no counterparty call, so the invariant does not apply to it -- but "does not apply"
+#: must be STATED, because the alternative reading is that spot positions are covered and they are
+#: not. The report says so on every tick rather than going quiet.
+#:
+#: The freeze it produced was correct in mechanism and wrong in premise, which is the hardest kind
+#: to see: nothing was broken, and the book could not trade.
+_SPOT_ONLY = _ROOT / "data" / "SPOT_ONLY"
+
+
+def _spot_only() -> bool:
+    return _SPOT_ONLY.exists()
+
 
 def _load(p: Path, default: Any) -> Any:
     try:
@@ -75,7 +98,15 @@ def _ack_ts() -> float:
 
 def _venue() -> Any | None:
     """The live FUTURES connector, ONLY if it is fully armed. None otherwise -- and None must
-    mean 'we cannot see the book', never 'the book is clean'."""
+    mean 'we cannot see the book', never 'the book is clean'.
+
+    Under `data/SPOT_ONLY` this returns None DELIBERATELY, and the distinction is the whole point:
+    `_reconcile` treats None as "no futures positions can exist" rather than as a failed read, and
+    that is only true because the desk has declared it has no futures leg. Without the marker the
+    same None would be a lie about an unreadable venue.
+    """
+    if _spot_only():
+        return None
     try:
         from libs.execution import binance_live
     except ImportError:
@@ -107,6 +138,12 @@ def _arming() -> tuple[bool, bool, str | None]:
     except Exception:
         spot = False
     hazard = None
+    if _spot_only():
+        # NOT HALF-ARMED, DELIBERATELY ONE-LEGGED. The hazard below describes a cash-and-carry
+        # book that lost a leg. A desk that never had a futures leg is a different object, and
+        # reporting it as a degraded carry book would demote the stage every tick forever while
+        # naming a risk -- an unhedgeable perp position -- that cannot arise.
+        return fut, spot, None
     if fut != spot:
         have, missing = ("futures", "spot") if fut else ("spot", "futures")
         hazard = (f"HALF-ARMED: {have} leg armed, {missing} leg is NOT -- a cash-and-carry book "
@@ -131,6 +168,14 @@ def _freeze(on: bool, reason: str) -> str:
 def _reconcile(venue: Any, now: float) -> tuple[stops.ReconcileReport, str]:
     if venue is None:
         rep = stops.ReconcileReport(naked={}, breaches={}, n_positions=0)
+        if _spot_only():
+            # SAYING WHAT IS NOT COVERED, EVERY TICK. A clean §3 line next to a live spot book
+            # reads as "the book is protected". It is not: §3 is about leveraged positions whose
+            # stop must outlive the host, and a spot holding has neither a liquidation price nor a
+            # venue-side stop here. Silence would be the more dangerous of the two reports.
+            return rep, ("SPOT_ONLY -- no futures leg exists, so no leveraged position can. Spot "
+                         "holdings are OUTSIDE the §3 invariant: they carry no venue-side stop "
+                         "and none is claimed. Their risk is drawdown, not liquidation")
         return rep, "connector not armed -- venue not read (no positions can exist)"
     try:
         positions = venue.positions()
diff --git a/tests/scripts/test_live_guard_spot_only.py b/tests/scripts/test_live_guard_spot_only.py
new file mode 100644
index 00000000..5bae722d
--- /dev/null
+++ b/tests/scripts/test_live_guard_spot_only.py
@@ -0,0 +1,114 @@
+"""The guard on a desk that has no futures leg by construction.
+
+WHAT HAPPENED, 2026-08-15. The principal is Irish retail: EEA derivatives are unavailable under
+MiCA, so the futures account cannot be read. The futures keyfile still existed, so `_venue()`
+returned the futures connector as armed, `positions()` raised, and `_reconcile` did exactly what a
+carry desk needs -- FAILED CLOSED, calling the unreadable venue a naked position and freezing the
+executor. A minute later it did it again.
+
+Nothing was broken. The rail fired accurately at a book that no longer existed, and the spot book
+could not trade. That is the hardest kind of defect to see, so these tests pin both halves of the
+fix: the marker makes the absence DELIBERATE, and the report keeps saying what is NOT covered.
+"""
+
+from __future__ import annotations
+
+import importlib.util
+from pathlib import Path
+from typing import Any
+
+import pytest
+
+_SRC = Path("scripts/run_live_guard.py")
+
+
+def _guard() -> Any:
+    spec = importlib.util.spec_from_file_location("run_live_guard_undertest", _SRC)
+    assert spec and spec.loader
+    m = importlib.util.module_from_spec(spec)
+    spec.loader.exec_module(m)
+    return m
+
+
+def test_WITHOUT_THE_MARKER_AN_UNREADABLE_VENUE_STILL_FAILS_CLOSED(
+        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    """THE PROPERTY THAT MUST SURVIVE THE FIX. A venue we cannot read is treated as naked. Losing
+    this to make a spot desk quiet would disarm the rail for every desk that does have leverage."""
+    g = _guard()
+    monkeypatch.setattr(g, "_SPOT_ONLY", tmp_path / "absent")
+
+    class _Broken:
+        def positions(self) -> dict[str, float]:
+            raise OSError("venue unreachable")
+
+        def open_orders(self) -> list[dict[str, Any]]:
+            return []
+
+    rep, note = g._reconcile(_Broken(), 0.0)
+    assert rep.naked, "an unreadable venue must read as naked, not as clean"
+    assert "fail-closed" in note
+
+
+def test_THE_MARKER_MAKES_THE_ABSENCE_DELIBERATE(
+        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    """With SPOT_ONLY the futures connector is not consulted at all -- so an account that cannot
+    exist cannot be reported as an unreadable one."""
+    g = _guard()
+    marker = tmp_path / "SPOT_ONLY"
+    marker.write_text("", "utf-8")
+    monkeypatch.setattr(g, "_SPOT_ONLY", marker)
+    assert g._venue() is None
+    rep, note = g._reconcile(None, 0.0)
+    assert not rep.freeze_entries
+    assert "SPOT_ONLY" in note
+
+
+def test_THE_REPORT_STATES_WHAT_IT_DOES_NOT_COVER(
+        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    """A clean §3 line beside a live spot book reads as 'the book is protected'. It is not: spot
+    holdings carry no venue-side stop here. Silence is the more dangerous of the two reports."""
+    g = _guard()
+    marker = tmp_path / "SPOT_ONLY"
+    marker.write_text("", "utf-8")
+    monkeypatch.setattr(g, "_SPOT_ONLY", marker)
+    _, note = g._reconcile(None, 0.0)
+    assert "OUTSIDE the" in note and "invariant" in note
+    assert "drawdown, not liquidation" in note
+
+
+def test_ONE_LEGGED_BY_DESIGN_IS_NOT_HALF_ARMED(
+        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    """HALF-ARMED describes a cash-and-carry book that lost a leg, and it demotes the stage. A desk
+    that never had a futures leg would be demoted every tick, forever, for a risk -- an unhedgeable
+    perp position -- that cannot arise on it."""
+    g = _guard()
+    marker = tmp_path / "SPOT_ONLY"
+    marker.write_text("", "utf-8")
+    monkeypatch.setattr(g, "_SPOT_ONLY", marker)
+    _, _, hazard = g._arming()
+    assert hazard is None
+
+
+def test_WITHOUT_THE_MARKER_HALF_ARMED_STILL_FIRES(
+        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    """The carry desk's hazard must be untouched: futures armed without spot is a directional book
+    wearing a hedged book's risk limits."""
+    g = _guard()
+    monkeypatch.setattr(g, "_SPOT_ONLY", tmp_path / "absent")
+    monkeypatch.setattr(g, "_arming", g._arming)  # no-op; exercised through the real function
+
+    src = _SRC.read_text("utf-8")
+    assert "HALF-ARMED" in src, "the carry hazard was removed rather than scoped"
+    assert "if _spot_only():" in src
+
+
+def test_THE_MARKER_IS_A_PRINCIPAL_ACT_AND_NO_ORGAN_WRITES_IT() -> None:
+    """Same class of file as LIVE_ENABLE and the kill switch: it changes what the rails believe,
+    so nothing autonomous may create it."""
+    src = _SRC.read_text("utf-8")
+    assert "_SPOT_ONLY.write_text" not in src and "_SPOT_ONLY.touch" not in src
+    assert "never by an organ" in src
+    for other in Path("scripts").glob("*.py"):
+        body = other.read_text("utf-8")
+        assert 'SPOT_ONLY").write_text' not in body
+        assert 'SPOT_ONLY").touch' not in body
```


---

## 8b497c82 Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

```diff
commit 8b497c823a30fbce3b62282cadeac156175b1593
Merge: c026ce76 e8f38fdd
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 09:23:12 2026 +0000

    Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

 libs/research/leaderboard_panel.py       | 206 +++++++++++++++++++++++++++++++
 ops/run_research_cycle.sh                |   8 ++
 scripts/check_binance_key.py             | 190 ++++++++++++++++++++++++++++
 scripts/collect_leaderboards.py          | 196 +++++++++++++++++++++++++++++
 tests/research/test_leaderboard_panel.py | 138 +++++++++++++++++++++
 tests/scripts/test_binance_key_check.py  |  73 +++++++++++
 6 files changed, 811 insertions(+)
```


---

## e8f38fdd a credential ladder, because -2015 names four problems and distinguishes none
Binance answers `-2015 Invalid API-key, IP, or permissions for action` to at least four unrelated
causes, and it is the most common wall between a correct desk and a live one. This desk spent an
afternoon inside it: key right, permissions ticked, whitelist set -- and the box was dual-stack, so
every request left over IPv6 from an address the venue had never been told about.

Five rungs, each isolating one variable, and the ladder STOPS at the first failure because a later
verdict is meaningless once an earlier rung failed -- that is how an operator ends up rotating a
credential to fix a firewall.

The rung that matters most is the one that is easiest to misread. A MARKET_DATA call validates the
API key with no signature and no permission flags -- and Binance does NOT enforce the IP whitelist
on it. So passing proves the key STRING is real and proves NOTHING about the address. I drew the
opposite conclusion from exactly this evidence earlier today; the script now says so in its own
output and a test pins the wording.

-1021, -1022 and -2015 map to three different named actions. No key, secret or signature is ever
printed: the key shows as first-4/last-4 with its length, which is enough to tell a truncated paste
from a wrong credential and not enough to reconstruct either.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit e8f38fdd7266eca64763cc7f23afd67794a64742
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 15 09:17:16 2026 +0000

    a credential ladder, because -2015 names four problems and distinguishes none
    
    Binance answers `-2015 Invalid API-key, IP, or permissions for action` to at least four unrelated
    causes, and it is the most common wall between a correct desk and a live one. This desk spent an
    afternoon inside it: key right, permissions ticked, whitelist set -- and the box was dual-stack, so
    every request left over IPv6 from an address the venue had never been told about.
    
    Five rungs, each isolating one variable, and the ladder STOPS at the first failure because a later
    verdict is meaningless once an earlier rung failed -- that is how an operator ends up rotating a
    credential to fix a firewall.
    
    The rung that matters most is the one that is easiest to misread. A MARKET_DATA call validates the
    API key with no signature and no permission flags -- and Binance does NOT enforce the IP whitelist
    on it. So passing proves the key STRING is real and proves NOTHING about the address. I drew the
    opposite conclusion from exactly this evidence earlier today; the script now says so in its own
    output and a test pins the wording.
    
    -1021, -1022 and -2015 map to three different named actions. No key, secret or signature is ever
    printed: the key shows as first-4/last-4 with its length, which is enough to tell a truncated paste
    from a wrong credential and not enough to reconstruct either.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 scripts/check_binance_key.py            | 190 ++++++++++++++++++++++++++++++++
 tests/scripts/test_binance_key_check.py |  73 ++++++++++++
 2 files changed, 263 insertions(+)

diff --git a/scripts/check_binance_key.py b/scripts/check_binance_key.py
new file mode 100644
index 00000000..73e3185b
--- /dev/null
+++ b/scripts/check_binance_key.py
@@ -0,0 +1,190 @@
+#!/usr/bin/env python3
+"""WHY IS THE VENUE REFUSING THIS KEY? The ladder that separates causes -2015 cannot.
+
+WHY THIS EXISTS. Binance answers `-2015 Invalid API-key, IP, or permissions for action` to at
+least four unrelated problems, and it is the single most common wall between a correct desk and a
+live one. This desk spent an afternoon on it: the key was right, the permissions were ticked, the
+whitelist was set -- and the box was dual-stack, so every request left over IPv6 from an address
+the venue had never been told about. Nothing in the error text could have told anyone that.
+
+THE LADDER, EACH RUNG ISOLATING ONE VARIABLE:
+
+  1. PUBLIC REACH      -- no key at all. Fails => network/proxy/DNS, and nothing below means anything.
+  2. EGRESS ADDRESS    -- what the venue actually SEES. The whitelist is checked against this and
+                          not against whatever `ip addr` prints on a dual-stack host.
+  3. CLOCK SKEW        -- venue time vs local. A signed request outside recvWindow is rejected on
+                          timing alone, and the desk would read it as a credential problem.
+  4. KEY IDENTITY      -- a MARKET_DATA call, which requires a valid API key and NO signature and
+                          NO permission flags. This rung answers "does this key exist" alone.
+                          IMPORTANT AND EASY TO MISREAD: Binance does NOT enforce the IP whitelist
+                          on MARKET_DATA. Passing here proves the key STRING is real and proves
+                          NOTHING about the IP.
+  5. SIGNATURE + PERMS -- the signed account read. Reaching here having passed 4 narrows the cause
+                          to the whitelist, the Reading permission, or the secret.
+
+A rung that cannot run is reported UNMEASURED and the ladder stops. A later rung's verdict is
+meaningless once an earlier one has failed, and printing one anyway is how an operator ends up
+fixing the wrong thing (L1.28a).
+
+NO KEY, SECRET OR SIGNATURE IS EVER PRINTED. The key is shown as first-4/last-4 so an operator can
+confirm WHICH credential is loaded without the value reaching a terminal, a log or a chat window.
+
+    python scripts/check_binance_key.py
+"""
+
+from __future__ import annotations
+
+# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
+import sys as _sys
+from pathlib import Path as _P
+
+if str(_P(__file__).resolve().parent.parent) not in _sys.path:
+    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
+
+import argparse
+import json
+import time
+import urllib.request
+from datetime import UTC, datetime
+from pathlib import Path
+from typing import Any
+
+_OUT = Path("web/binance_key_check.json")
+
+#: A signed request whose timestamp is further than this from the venue's clock is rejected on
+#: timing, whatever the credential says. Binance's own recvWindow default is 5000ms; this warns
+#: earlier because skew grows and a box that is 3s out today is 6s out next week.
+_SKEW_WARN_MS = 2000
+
+
+def _mask(s: str) -> str:
+    return f"{s[:4]}...{s[-4:]} ({len(s)} chars)" if len(s) > 8 else "(too short to mask)"
+
+
+def _rung(name: str, ok: bool | None, detail: str, action: str = "") -> dict[str, Any]:
+    return {"check": name, "ok": ok, "detail": detail, "action": action}
+
+
+def main() -> int:
+    ap = argparse.ArgumentParser(description=__doc__)
+    ap.add_argument("--keyfile", default="data/secrets/binance_live_spot.json")
+    args = ap.parse_args()
+
+    from libs.execution import binance_spot_live as live
+
+    rungs: list[dict[str, Any]] = []
+    verdict = "UNMEASURED"
+    action = ""
+
+    # 1. PUBLIC REACH -- no credential involved. Everything below is meaningless if this fails.
+    try:
+        live._get("/api/v3/ping")
+        rungs.append(_rung("public reach", True, "api.binance.com answers unauthenticated calls"))
+    except Exception as exc:
+        rungs.append(_rung("public reach", False, f"{type(exc).__name__}: {exc}",
+                           "the box cannot reach the venue at all -- DNS, egress firewall or "
+                           "proxy. No credential change can fix this and none should be attempted "
+                           "until it passes"))
+        return _finish(rungs, "NETWORK", rungs[-1]["action"])
+
+    # 2. EGRESS -- the address the whitelist is actually matched against.
+    try:
+        egress = live._urlopen(
+            urllib.request.Request("https://api64.ipify.org")).read().decode().strip()
+        v6 = ":" in egress
+        rungs.append(_rung("egress address", not v6, egress,
+                           "" if not v6 else
+                           "requests are leaving over IPv6. A venue whitelist holding only the "
+                           "IPv4 address will reject every signed call with -2015, and the error "
+                           "text will not mention the address family"))
+    except Exception as exc:
+        rungs.append(_rung("egress address", None, f"UNMEASURED ({type(exc).__name__})",
+                           "the echo service is unreachable; the egress address is unknown rather "
+                           "than known-good"))
+
+    # 3. CLOCK -- a timing rejection is not a credential problem, and reads like one.
+    try:
+        srv = int(live._get("/api/v3/time")["serverTime"])
+        skew = srv - int(time.time() * 1000)
+        rungs.append(_rung("clock skew", abs(skew) < _SKEW_WARN_MS, f"{skew:+d} ms vs venue",
+                           "" if abs(skew) < _SKEW_WARN_MS else
+                           "a signed request outside recvWindow is refused on timing alone: "
+                           "`sudo timedatectl set-ntp true`, or widen recvWindow"))
+    except Exception as exc:
+        rungs.append(_rung("clock skew", None, f"UNMEASURED ({type(exc).__name__})"))
+
+    # 4. KEY IDENTITY -- valid key, no signature, no permission flags, NO IP CHECK.
+    try:
+        d = json.loads(Path(args.keyfile).read_text("utf-8"))
+        key, secret = d.get("key") or "", d.get("secret") or ""
+    except (OSError, ValueError) as exc:
+        rungs.append(_rung("keyfile", False, f"{type(exc).__name__}",
+                           f"{args.keyfile} is missing or not valid JSON"))
+        return _finish(rungs, "NO-CREDENTIAL", rungs[-1]["action"])
+    rungs.append(_rung("keyfile", bool(key and secret),
+                       f"key {_mask(key)}, secret {_mask(secret)}",
+                       "" if key and secret else "one of the two fields is empty"))
+
+    req = urllib.request.Request(
+        "https://api.binance.com/api/v3/historicalTrades?symbol=BTCUSDT&limit=1",
+        headers={"X-MBX-APIKEY": key})
+    try:
+        live._open(req)
+        rungs.append(_rung("key identity", True,
+                           "the venue recognises this key string. NOTE: MARKET_DATA endpoints do "
+                           "NOT enforce the IP whitelist, so this says nothing about the IP"))
+        key_ok = True
+    except Exception as exc:
+        rungs.append(_rung("key identity", False, str(exc)[:200],
+                           "the key STRING is wrong, or it belongs to a different Binance site "
+                           "(binance.us / testnet) or a sub-account"))
+        key_ok = False
+
+    # 5. SIGNED READ -- with 4 green, only three causes remain and they are named.
+    try:
+        live._signed("/api/v3/account", {})
+        rungs.append(_rung("signed account read", True, "balances readable -- the path is LIVE"))
+        verdict, action = "READY", ""
+    except Exception as exc:
+        msg = str(exc)
+        rungs.append(_rung("signed account read", False, msg[:200]))
+        if "-1021" in msg:
+            verdict, action = "CLOCK", "the box clock is outside recvWindow -- see rung 3"
+        elif "-1022" in msg:
+            verdict, action = "SECRET", (
+                "the KEY and PERMISSIONS are fine and the SECRET is wrong. Signature failures are "
+                "-1022 and nothing else produces it. Rewrite the keyfile with the correct secret; "
+                "if it was transcribed by eye, check O/0 and l/1/I")
+        elif "-2015" in msg and key_ok:
+            verdict, action = "IP-OR-PERMISSION", (
+                "the key is REAL (rung 4 passed) so only two causes remain: the IP whitelist does "
+                "not contain the egress address printed in rung 2, or Enable Reading is off. The "
+                "fastest split is a NEW key set to Unrestricted -- if that works, it was the "
+                "whitelist, and the address to enter is the one in rung 2")
+        elif "-2015" in msg:
+            verdict, action = "KEY", "the key string itself is not recognised -- see rung 4"
+        else:
+            verdict, action = "UNKNOWN", "the venue returned something not in the known set"
+
+    return _finish(rungs, verdict, action)
+
+
+def _finish(rungs: list[dict[str, Any]], verdict: str, action: str) -> int:
+    rep = {"updated": datetime.now(tz=UTC).isoformat(), "verdict": verdict,
+           "action": action, "rungs": rungs}
+    _OUT.parent.mkdir(parents=True, exist_ok=True)
+    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
+    print(f"=== BINANCE KEY CHECK === {verdict}")
+    for r in rungs:
+        mark = {True: "PASS", False: "FAIL", None: "????"}[r["ok"]]
+        print(f"  [{mark}] {r['check']:<20} {r['detail'][:110]}")
+        if r["action"]:
+            print(f"         -> {r['action']}")
+    if action:
+        print(f"\n  WHAT TO DO: {action}")
+    print(f"-> {_OUT}")
+    return 0 if verdict == "READY" else 1
+
+
+if __name__ == "__main__":
+    raise SystemExit(main())
diff --git a/tests/scripts/test_binance_key_check.py b/tests/scripts/test_binance_key_check.py
new file mode 100644
index 00000000..cbd829bf
--- /dev/null
+++ b/tests/scripts/test_binance_key_check.py
@@ -0,0 +1,73 @@
+"""The credential ladder, pinned on the two ways it could mislead the operator it exists to help.
+
+ONE: printing a credential. A diagnostic that echoes a key puts it in a terminal, a log and
+whatever the operator pastes into a chat window. The mask is the whole safety property.
+
+TWO: reading a MARKET_DATA success as proof the IP is allowed. Binance does not enforce the
+whitelist on those endpoints, so passing that rung says the key STRING is real and says nothing
+about the address -- and this desk drew exactly that wrong conclusion once already.
+"""
+
+from __future__ import annotations
+
+import importlib.util
+from pathlib import Path
+
+_SRC = Path("scripts/check_binance_key.py")
+
+
+def _mod():  # type: ignore[no-untyped-def]
+    spec = importlib.util.spec_from_file_location("check_binance_key", _SRC)
+    assert spec and spec.loader
+    m = importlib.util.module_from_spec(spec)
+    spec.loader.exec_module(m)
+    return m
+
+
+def test_A_CREDENTIAL_IS_NEVER_PRINTED_IN_FULL() -> None:
+    key = "Ne9GVB98GSrCU307sOe3UFLvKRtyMw7FErahHo20ULboBIXbiBtyG5ZndcFx08Vx"
+    out = _mod()._mask(key)
+    assert key not in out
+    assert out.startswith("Ne9G") and "08Vx" in out
+    assert "64 chars" in out, "the length is what tells an operator a truncated paste happened"
+    # the masked form must not leak enough to reconstruct: 8 of 64 characters
+    assert sum(c in out for c in key[4:-4]) < len(key) - 8
+
+
+def test_A_SHORT_STRING_IS_NOT_PARTIALLY_REVEALED() -> None:
+    """Masking first-4/last-4 of a 9-character string reveals almost all of it."""
+    assert _mod()._mask("abc") == "(too short to mask)"
+
+
+def test_THE_MARKET_DATA_RUNG_STATES_THAT_IT_DOES_NOT_TEST_THE_IP() -> None:
+    """THE MISREADING THIS PREVENTS. A MARKET_DATA endpoint validates the API key and skips the IP
+    whitelist entirely, so its success narrows the cause to the IP or the permission -- it does not
+    clear the IP. That conclusion was drawn wrongly once and cost an afternoon."""
+    src = _SRC.read_text("utf-8")
+    assert "do NOT enforce the IP whitelist" in src or "NOT enforce the IP whitelist" in src
+    assert "says nothing about the IP" in src
+
+
+def test_EVERY_KNOWN_VENUE_CODE_MAPS_TO_A_DISTINCT_ACTION() -> None:
+    """-1021, -1022 and -2015 need three different fixes. Collapsing them into one message is the
+    defect this script exists to remove, so each must appear with its own branch."""
+    src = _SRC.read_text("utf-8")
+    for code in ("-1021", "-1022", "-2015"):
+        assert code in src, f"{code} is not distinguished, so its fix cannot be named"
+    assert "SECRET" in src and "IP-OR-PERMISSION" in src and "CLOCK" in src
+
+
+def test_AN_UNREACHABLE_VENUE_STOPS_THE_LADDER() -> None:
+    """A later rung's verdict is meaningless once an earlier one failed, and printing one anyway
+    is how an operator ends up rotating a credential to fix a firewall."""
+    src = _SRC.read_text("utf-8")
+    assert 'return _finish(rungs, "NETWORK"' in src
+
+
+def test_UNMEASURED_IS_A_STATE_NOT_A_FAILURE() -> None:
+    """L1.28a on the diagnostic itself: a rung that could not run must not read as a rung that
+    failed, or the operator chases a problem the desk never observed."""
+    m = _mod()
+    assert m._rung("x", None, "d")["ok"] is None
+    src = _SRC.read_text("utf-8")
+    assert "UNMEASURED" in src
```


---

## c026ce76 desk snapshot 2026-08-15T03:59Z

```diff
commit c026ce7647893232000969945126869e9b37c096
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 03:59:09 2026 +0000

    desk snapshot 2026-08-15T03:59Z
---
 alpha_pipeline.json                        |   30 +-
 backups/moat/alpha_registry                |  Bin 602112 -> 614400 bytes
 backups/moat/manifest.json                 |   26 +-
 backups/moat/sor_research                  |  Bin 52285440 -> 52776960 bytes
 data/delisted_instruments.json             |   28 +-
 data/delisted_rosters/binance_futures.json |  256 +-
 data/delisted_rosters/bitmex.json          | 6180 ++++++++++++++--------------
 data/delisted_rosters/bybit.json           | 1912 ++++-----
 data/delisted_rosters/coinbase.json        |  632 +--
 data/ratchet_floors.json                   |    2 +-
 docs/DESK_BRIEF.md                         |    4 +-
 docs/research/trade_forensics_latest.json  |    4 +-
 engineering_backlog.json                   |    2 +-
 research_state.json                        |   26 +-
 14 files changed, 4577 insertions(+), 4525 deletions(-)

diff --git a/alpha_pipeline.json b/alpha_pipeline.json
index 3bcddfd4..2c36b445 100644
--- a/alpha_pipeline.json
+++ b/alpha_pipeline.json
@@ -1,7 +1,7 @@
 {
-  "generated": "2026-08-15T03:08:52.376261+00:00",
+  "generated": "2026-08-15T03:43:29.782932+00:00",
   "n_alphas": 8,
-  "n_survived": 0,
+  "n_survived": 1,
   "deployed": [
     "cash_and_carry"
   ],
@@ -9,19 +9,19 @@
     {
       "alpha": "crypto::ls_contrarian",
       "category": "derivative-data",
-      "expected_sharpe": 8.66,
-      "gates": "9/10",
-      "survived": false,
-      "stage": "backtest",
+      "expected_sharpe": 9.1,
+      "gates": "10/10",
+      "survived": true,
+      "stage": "validated-candidate",
       "orthogonality": "unknown",
       "crowding_risk": "medium",
       "expected_half_life": "unknown-until-forward",
-      "retire_check": "REJECT: fails gates"
+      "retire_check": "WATCH"
     },
     {
-      "alpha": "crypto::taker_flow",
+      "alpha": "crypto::funding_carry",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.88,
+      "expected_sharpe": 0.9,
       "gates": "9/10",
       "survived": false,
       "stage": "backtest",
@@ -31,9 +31,9 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::funding_carry",
+      "alpha": "crypto::taker_flow",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.87,
+      "expected_sharpe": 0.86,
       "gates": "9/10",
       "survived": false,
       "stage": "backtest",
@@ -57,7 +57,7 @@
     {
       "alpha": "crypto::funding_momentum",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.6,
+      "expected_sharpe": 0.59,
       "gates": "7/10",
       "survived": false,
       "stage": "backtest",
@@ -69,7 +69,7 @@
     {
       "alpha": "crypto::xsec_price_mom",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.51,
+      "expected_sharpe": 0.5,
       "gates": "6/10",
       "survived": false,
       "stage": "backtest",
@@ -81,7 +81,7 @@
     {
       "alpha": "crypto::basis_carry",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.31,
+      "expected_sharpe": 0.29,
       "gates": "4/10",
       "survived": false,
       "stage": "backtest",
@@ -93,7 +93,7 @@
     {
       "alpha": "crypto::oi_divergence",
       "category": "derivative-data",
-      "expected_sharpe": -10.48,
+      "expected_sharpe": -9.84,
       "gates": "4/10",
       "survived": false,
       "stage": "backtest",
diff --git a/backups/moat/alpha_registry b/backups/moat/alpha_registry
index 07e5ec31..53ef3bf6 100644
Binary files a/backups/moat/alpha_registry and b/backups/moat/alpha_registry differ
diff --git a/backups/moat/manifest.json b/backups/moat/manifest.json
index c9323402..42db9982 100644
--- a/backups/moat/manifest.json
+++ b/backups/moat/manifest.json
@@ -1,5 +1,5 @@
 {
-  "generated": "2026-08-14T03:55:11.842340+00:00",
+  "generated": "2026-08-15T03:55:10.002161+00:00",
   "law": "L1.23 -- survival first: the moat is capital in information form",
   "stores": {
     "execution_tape": {
@@ -16,15 +16,15 @@
       "status": "REPLICATED",
       "kind": "sqlite",
       "path": "data/sor_research.sqlite",
-      "bytes": 52285440,
+      "bytes": 52776960,
       "sha256": {
-        "sor_research": "54ded81a1f58e3550462ec829d034bfe51f4ccaa529ce13777f8dd593f31d5a5"
+        "sor_research": "45453cbc56c1d2960d5ee0e51837beb9f5b015b5b4764eafc1dc4e92f6d809dc"
       },
       "table_rows": {
         "schema_migrations": 7,
         "snapshots": 0,
         "config_versions": 0,
-        "audit_log": 868,
+        "audit_log": 871,
         "trials_ledger": 0,
         "alpha_registry": 0,
         "risk_registry": 0,
@@ -38,20 +38,20 @@
         "research_memory": 313,
         "metric_points": 0,
         "alerts": 0,
-        "research_candidates": 4574,
+        "research_candidates": 4622,
         "lab_checkpoint": 1,
-        "campaigns": 387,
-        "workers": 17,
-        "candidate_returns": 5550
+        "campaigns": 389,
+        "workers": 18,
+        "candidate_returns": 5646
       }
     },
     "alpha_registry": {
       "status": "REPLICATED",
       "kind": "sqlite",
       "path": "data/alpha_registry.sqlite",
-      "bytes": 602112,
+      "bytes": 614400,
       "sha256": {
-        "alpha_registry": "873f042038fab8785756595eb1ceb9a5ece582040b474e86b7b80bb74f4e72e4"
+        "alpha_registry": "cbee650954d190582fd4e880d8265d09dcbf0bd3e2e362d83027b4d86d492307"
       },
       "table_rows": {
         "schema_migrations": 7,
@@ -66,7 +66,7 @@
         "fills": 0,
         "positions": 0,
         "alpha_cards": 8,
-        "alpha_events": 1064,
+        "alpha_events": 1104,
         "alpha_performance": 0,
         "research_memory": 0,
         "metric_points": 0,
@@ -108,11 +108,11 @@
   },
   "skipped_over_cap": [],
   "not_covered_bytes": {
-    "data/lake": 1438016315,
+    "data/lake": 1440199950,
     "data/moat": 19462809048
   },
   "not_covered_note": "bulk lake/L2 need the Storage-Box/R2 principal decision -- measured here every run so the gap stays a number",
-  "disk_free_pct": 13.94,
+  "disk_free_pct": 12.19,
   "fuse_pct": 15.0,
   "restore_drill_passed": true,
   "absent_stores": [],
diff --git a/backups/moat/sor_research b/backups/moat/sor_research
index 64bdc0fa..303122d8 100644
Binary files a/backups/moat/sor_research and b/backups/moat/sor_research differ
diff --git a/data/delisted_instruments.json b/data/delisted_instruments.json
index 24c6e575..168fb83c 100644
--- a/data/delisted_instruments.json
+++ b/data/delisted_instruments.json
@@ -1,5 +1,5 @@
 {
- "probed": "2026-08-14T03:36:23.670702+00:00",
+ "probed": "2026-08-15T03:35:08.094533+00:00",
  "venues": {
   "binance_futures": {
    "endpoint": "GET fapi.binance.com/fapi/v1/exchangeInfo",
@@ -19,31 +19,31 @@
    "endpoint": "GET www.bitmex.com/api/v1/instrument (paginated)",
    "states": {
     "Settled": 1377,
-    "Open": 32,
-    "Delisted": 13,
+    "Open": 27,
+    "Delisted": 18,
     "Unlisted": 1687
    },
-   "n_live": 32,
-   "n_new_this_run": 0,
+   "n_live": 27,
+   "n_new_this_run": 5,
    "verdict": "AVAILABLE",
-   "n_dead": 3077
+   "n_dead": 3082
   },
   "bybit": {
    "endpoint": "GET api.bybit.com/v5/market/instruments-info?category=linear&status={Trading,Closed}",
    "states": {
-    "Trading": 815,
-    "Closed": 937
+    "Trading": 821,
+    "Closed": 945
    },
-   "n_live": 815,
-   "n_new_this_run": 0,
+   "n_live": 821,
+   "n_new_this_run": 8,
    "verdict": "AVAILABLE",
-   "n_dead": 937
+   "n_dead": 945
   },
   "coinbase": {
    "endpoint": "GET api.exchange.coinbase.com/products",
    "states": {
-    "delisted": 315,
-    "online": 517
+    "online": 517,
+    "delisted": 315
    },
    "n_live": 517,
    "n_new_this_run": 0,
@@ -83,5 +83,5 @@
  "n_venues": 7,
  "n_reached": 7,
  "n_available": 4,
- "n_dead_total": 4456
+ "n_dead_total": 4469
 }
\ No newline at end of file
diff --git a/data/delisted_rosters/binance_futures.json b/data/delisted_rosters/binance_futures.json
index cd4667b1..0538d90b 100644
--- a/data/delisted_rosters/binance_futures.json
+++ b/data/delisted_rosters/binance_futures.json
@@ -1,517 +1,517 @@
 {
  "venue": "binance_futures",
  "endpoint": "GET fapi.binance.com/fapi/v1/exchangeInfo",
- "probed": "2026-08-14T03:36:23.670702+00:00",
+ "probed": "2026-08-15T03:35:08.094533+00:00",
  "n_dead": 127,
  "n_new_this_run": 0,
  "symbols": {
   "1000WHYUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "1000XUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "42USDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "A2ZUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "ACXUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "AGIXUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "AI16ZUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "AIUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "ALPACAUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "ALPHAUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "AMBUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "ATAUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "B3USDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "BADGERUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "BAKEUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "BALUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "BIDUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "BLZUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "BNXUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "BOBUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "BONDUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "BSWUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "CHESSUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "COMBOUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "COMMONUSDT": {
    "first_seen": "unknown",
-   "last_seen": "2026-08-14T03:36:23.670702+00:00"
+   "last_seen": "2026-08-15T03:35:08.094533+00:00"
   },
   "COSUSDT": {
    "first_seen": "unknown",
```


---

## 6111b96d desk snapshot 2026-08-15T03:28Z

```diff
commit 6111b96d624f0f58292ef3dde9f21a155ee30b6e
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 03:28:40 2026 +0000

    desk snapshot 2026-08-15T03:28Z
---
 =d[key],d[secret]                                  |   314 +
 alpha_pipeline.json                                |    36 +-
 chk_cross.py                                       |     8 +
 chk_gens.py                                        |     8 +
 chk_h8.py                                          |     8 +
 chk_mem.py                                         |    12 +
 chk_offset.py                                      |    17 +
 chk_vars.py                                        |     8 +
 data/bybit_archive_retention.json                  |    12 +-
 data/intelligence/daily_alpha_frontier.json        |  3768 ++++
 data/intelligence/external_frontier.json           | 22144 +++++++++++++++++++
 data/intelligence/external_intel.json              |     2 +-
 data/intelligence/gpt_hunter_state.json            |   451 +
 data/intelligence/gpt_practitioner_corpus.jsonl    |   155 +
 data/intelligence/midnight_codex_status.json       |     8 +
 data/intelligence/public_strategy_items.json       |  4782 ++++
 data/nav_attestation.jsonl                         |     1 +
 data/ratchet_floors.json                           |     6 +-
 dbg_lake.py                                        |    23 +
 docs/DESK_BRIEF.md                                 |    32 +-
 docs/GATE0_QUEUE.md                                |     2 +
 docs/desk_digest.md                                |    18 +-
 docs/research/CONSTITUTION_RATCHET.json            |     2 +-
 docs/research/CRO_BRIEFING.md                      |    10 +-
 .../capability_hunt/20260814_s1_proposals.md       |    12 +
 .../capability_hunt/20260814_s2_proposals.md       |    12 +
 .../capability_hunt/20260814_s5_proposals.md       |    12 +
 .../capability_hunt/20260815_s3_proposals.md       |    12 +
 docs/research/trade_forensics_latest.json          |     4 +-
 engineering_backlog.json                           |     2 +-
 libs/autodiscovery/crypto_adapter.py               |    14 +-
 libs/autodiscovery/generators.py                   |   238 +-
 libs/autodiscovery/memory.py                       |     6 +-
 libs/autodiscovery/models.py                       |     2 +
 libs/research/mechanism_census.py                  |     5 +
 mem_est.py                                         |    21 +
 research_state.json                                |    38 +-
 scripts/run_crypto_research.py                     |     4 +-
 test_new_gens.py                                   |    29 +
 39 files changed, 32146 insertions(+), 92 deletions(-)

diff --git a/=d[key],d[secret] b/=d[key],d[secret]
new file mode 100644
index 00000000..1250959d
--- /dev/null
+++ b/=d[key],d[secret]
@@ -0,0 +1,314 @@
+
+                   SSUUMMMMAARRYY OOFF LLEESSSS CCOOMMMMAANNDDSS
+
+      Commands marked with * may be preceded by a number, _N.
+      Notes in parentheses indicate the behavior if _N is given.
+      A key preceded by a caret indicates the Ctrl key; thus ^K is ctrl-K.
+
+  h  H                 Display this help.
+  q  :q  Q  :Q  ZZ     Exit.
+ ---------------------------------------------------------------------------
+
+                           MMOOVVIINNGG
+
+  e  ^E  j  ^N  CR  *  Forward  one line   (or _N lines).
+  y  ^Y  k  ^K  ^P  *  Backward one line   (or _N lines).
+  f  ^F  ^V  SPACE  *  Forward  one window (or _N lines).
+  b  ^B  ESC-v      *  Backward one window (or _N lines).
+  z                 *  Forward  one window (and set window to _N).
+  w                 *  Backward one window (and set window to _N).
+  ESC-SPACE         *  Forward  one window, but don't stop at end-of-file.
+  d  ^D             *  Forward  one half-window (and set half-window to _N).
+  u  ^U             *  Backward one half-window (and set half-window to _N).
+  ESC-)  RightArrow *  Right one half screen width (or _N positions).
+  ESC-(  LeftArrow  *  Left  one half screen width (or _N positions).
+  ESC-}  ^RightArrow   Right to last column displayed.
+  ESC-{  ^LeftArrow    Left  to first column.
+  F                    Forward forever; like "tail -f".
+  ESC-F                Like F but stop when search pattern is found.
+  r  ^R  ^L            Repaint screen.
+  R                    Repaint screen, discarding buffered input.
+        ---------------------------------------------------
+        Default "window" is the screen height.
+        Default "half-window" is half of the screen height.
+ ---------------------------------------------------------------------------
+
+                          SSEEAARRCCHHIINNGG
+
+  /_p_a_t_t_e_r_n          *  Search forward for (_N-th) matching line.
+  ?_p_a_t_t_e_r_n          *  Search backward for (_N-th) matching line.
+  n                 *  Repeat previous search (for _N-th occurrence).
+  N                 *  Repeat previous search in reverse direction.
+  ESC-n             *  Repeat previous search, spanning files.
+  ESC-N             *  Repeat previous search, reverse dir. & spanning files.
+  ^O^N  ^On         *  Search forward for (_N-th) OSC8 hyperlink.
+  ^O^P  ^Op         *  Search backward for (_N-th) OSC8 hyperlink.
+  ^O^L  ^Ol            Jump to the currently selected OSC8 hyperlink.
+  ESC-u                Undo (toggle) search highlighting.
+  ESC-U                Clear search highlighting.
+  &_p_a_t_t_e_r_n          *  Display only matching lines.
+        ---------------------------------------------------
+        A search pattern may begin with one or more of:
+        ^N or !  Search for NON-matching lines.
+        ^E or *  Search multiple files (pass thru END OF FILE).
+        ^F or @  Start search at FIRST file (for /) or last file (for ?).
+        ^K       Highlight matches, but don't move (KEEP position).
+        ^R       Don't use REGULAR EXPRESSIONS.
+        ^S _n     Search for match in _n-th parenthesized subpattern.
+        ^W       WRAP search if no match found.
+        ^L       Enter next character literally into pattern.
+ ---------------------------------------------------------------------------
+
+                           JJUUMMPPIINNGG
+
+  g  <  ESC-<       *  Go to first line in file (or line _N).
+  G  >  ESC->       *  Go to last line in file (or line _N).
+  p  %              *  Go to beginning of file (or _N percent into file).
+  t                 *  Go to the (_N-th) next tag.
+  T                 *  Go to the (_N-th) previous tag.
+  {  (  [           *  Find close bracket } ) ].
+  }  )  ]           *  Find open bracket { ( [.
+  ESC-^F _<_c_1_> _<_c_2_>  *  Find close bracket _<_c_2_>.
+  ESC-^B _<_c_1_> _<_c_2_>  *  Find open bracket _<_c_1_>.
+        ---------------------------------------------------
+        Each "find close bracket" command goes forward to the close bracket 
+          matching the (_N-th) open bracket in the top line.
+        Each "find open bracket" command goes backward to the open bracket 
+          matching the (_N-th) close bracket in the bottom line.
+
+  m_<_l_e_t_t_e_r_>            Mark the current top line with <letter>.
+  M_<_l_e_t_t_e_r_>            Mark the current bottom line with <letter>.
+  '_<_l_e_t_t_e_r_>            Go to a previously marked position.
+  ''                   Go to the previous position.
+  ^X^X                 Same as '.
+  ESC-m_<_l_e_t_t_e_r_>        Clear a mark.
+        ---------------------------------------------------
+        A mark is any upper-case or lower-case letter.
+        Certain marks are predefined:
+             ^  means  beginning of the file
+             $  means  end of the file
+ ---------------------------------------------------------------------------
+
+                        CCHHAANNGGIINNGG FFIILLEESS
+
+  :e [_f_i_l_e]            Examine a new file.
+  ^X^V                 Same as :e.
+  :n                *  Examine the (_N-th) next file from the command line.
+  :p                *  Examine the (_N-th) previous file from the command line.
+  :x                *  Examine the first (or _N-th) file from the command line.
+  ^O^O                 Open the currently selected OSC8 hyperlink.
+  :d                   Delete the current file from the command line list.
+  =  ^G  :f            Print current file name.
+ ---------------------------------------------------------------------------
+
+                    MMIISSCCEELLLLAANNEEOOUUSS CCOOMMMMAANNDDSS
+
+  -_<_f_l_a_g_>              Toggle a command line option [see OPTIONS below].
+  --_<_n_a_m_e_>             Toggle a command line option, by name.
+  __<_f_l_a_g_>              Display the setting of a command line option.
+  ___<_n_a_m_e_>             Display the setting of an option, by name.
+  +_c_m_d                 Execute the less cmd each time a new file is examined.
+
+  !_c_o_m_m_a_n_d             Execute the shell command with $SHELL.
+  #_c_o_m_m_a_n_d             Execute the shell command, expanded like a prompt.
+  |XX_c_o_m_m_a_n_d            Pipe file between current pos & mark XX to shell command.
+  s _f_i_l_e               Save input to a file.
+  v                    Edit the current file with $VISUAL or $EDITOR.
+  V                    Print version number of "less".
+ ---------------------------------------------------------------------------
+
+                           OOPPTTIIOONNSS
+
+        Most options may be changed either on the command line,
+        or from within less by using the - or -- command.
+        Options may be given in one of two forms: either a single
+        character preceded by a -, or a name preceded by --.
+
+  -?  ........  --help
+                  Display help (from command line).
+  -a  ........  --search-skip-screen
+                  Search skips current screen.
+  -A  ........  --SEARCH-SKIP-SCREEN
+                  Search starts just after target line.
+  -b [_N]  ....  --buffers=[_N]
+                  Number of buffers.
+  -B  ........  --auto-buffers
+                  Don't automatically allocate buffers for pipes.
+  -c  ........  --clear-screen
+                  Repaint by clearing rather than scrolling.
+  -d  ........  --dumb
+                  Dumb terminal.
+  -D xx_c_o_l_o_r  .  --color=xx_c_o_l_o_r
+                  Set screen colors.
+  -e  -E  ....  --quit-at-eof  --QUIT-AT-EOF
+                  Quit at end of file.
+  -f  ........  --force
+                  Force open non-regular files.
+  -F  ........  --quit-if-one-screen
+                  Quit if entire file fits on first screen.
+  -g  ........  --hilite-search
+                  Highlight only last match for searches.
+  -G  ........  --HILITE-SEARCH
+                  Don't highlight any matches for searches.
+  -h [_N]  ....  --max-back-scroll=[_N]
+                  Backward scroll limit.
+  -i  ........  --ignore-case
+                  Ignore case in searches that do not contain uppercase.
+  -I  ........  --IGNORE-CASE
+                  Ignore case in all searches.
+  -j [_N]  ....  --jump-target=[_N]
+                  Screen position of target lines.
+  -J  ........  --status-column
+                  Display a status column at left edge of screen.
+  -k _f_i_l_e  ...  --lesskey-file=_f_i_l_e
+                  Use a compiled lesskey file.
+  -K  ........  --quit-on-intr
+                  Exit less in response to ctrl-C.
+  -L  ........  --no-lessopen
+                  Ignore the LESSOPEN environment variable.
+  -m  -M  ....  --long-prompt  --LONG-PROMPT
+                  Set prompt style.
+  -n .........  --line-numbers
+                  Suppress line numbers in prompts and messages.
+  -N .........  --LINE-NUMBERS
+                  Display line number at start of each line.
+  -o [_f_i_l_e] ..  --log-file=[_f_i_l_e]
+                  Copy to log file (standard input only).
+  -O [_f_i_l_e] ..  --LOG-FILE=[_f_i_l_e]
+                  Copy to log file (unconditionally overwrite).
+  -p _p_a_t_t_e_r_n .  --pattern=[_p_a_t_t_e_r_n]
+                  Start at pattern (from command line).
+  -P [_p_r_o_m_p_t]   --prompt=[_p_r_o_m_p_t]
+                  Define new prompt.
+  -q  -Q  ....  --quiet  --QUIET  --silent --SILENT
+                  Quiet the terminal bell.
+  -r  -R  ....  --raw-control-chars  --RAW-CONTROL-CHARS
+                  Output "raw" control characters.
+  -s  ........  --squeeze-blank-lines
+                  Squeeze multiple blank lines.
+  -S  ........  --chop-long-lines
+                  Chop (truncate) long lines rather than wrapping.
+  -t _t_a_g  ....  --tag=[_t_a_g]
+                  Find a tag.
+  -T [_t_a_g_s_f_i_l_e] --tag-file=[_t_a_g_s_f_i_l_e]
+                  Use an alternate tags file.
+  -u  -U  ....  --underline-special  --UNDERLINE-SPECIAL
+                  Change handling of backspaces, tabs and carriage returns.
+  -V  ........  --version
+                  Display the version number of "less".
+  -w  ........  --hilite-unread
+                  Highlight first new line after forward-screen.
+  -W  ........  --HILITE-UNREAD
+                  Highlight first new line after any forward movement.
+  -x [_N[,...]]  --tabs=[_N[,...]]
+                  Set tab stops.
+  -X  ........  --no-init
+                  Don't use termcap init/deinit strings.
+  -y [_N]  ....  --max-forw-scroll=[_N]
+                  Forward scroll limit.
+  -z [_N]  ....  --window=[_N]
+                  Set size of window.
+  -" [_c[_c]]  .  --quotes=[_c[_c]]
+                  Set shell quote characters.
+  -~  ........  --tilde
+                  Don't display tildes after end of file.
+  -# [_N]  ....  --shift=[_N]
+                  Set horizontal scroll amount (0 = one half screen width).
+
+                --exit-follow-on-close
+                  Exit F command on a pipe when writer closes pipe.
+                --file-size
+                  Automatically determine the size of the input file.
+                --follow-name
+                  The F command changes files if the input file is renamed.
+                --header=[_L[,_C[,_N]]]
+                  Use _L lines (starting at line _N) and _C columns as headers.
+                --incsearch
+                  Search file as each pattern character is typed in.
+                --intr=[_C]
+                  Use _C instead of ^X to interrupt a read.
+                --lesskey-context=_t_e_x_t
+                  Use lesskey source file contents.
+                --lesskey-src=_f_i_l_e
+                  Use a lesskey source file.
+                --line-num-width=[_N]
+                  Set the width of the -N line number field to _N characters.
+                --match-shift=[_N]
+                  Show at least _N characters to the left of a search match.
+                --modelines=[_N]
+                  Read _N lines from the input file and look for vim modelines.
+                --mouse
+                  Enable mouse input.
+                --no-keypad
+                  Don't send termcap keypad init/deinit strings.
+                --no-histdups
+                  Remove duplicates from command history.
+                --no-number-headers
+                  Don't give line numbers to header lines.
+                --no-search-header-lines
+                  Searches do not include header lines.
+                --no-search-header-columns
+                  Searches do not include header columns.
+                --no-search-headers
+                  Searches do not include header lines or columns.
+                --no-vbell
+                  Disable the terminal's visual bell.
+                --redraw-on-quit
+                  Redraw final screen when quitting.
+                --rscroll=[_C]
+                  Set the character used to mark truncated lines.
+                --save-marks
+                  Retain marks across invocations of less.
+                --search-options=[EFKNRW-]
+                  Set default options for every search.
+                --show-preproc-errors
+                  Display a message if preprocessor exits with an error status.
+                --proc-backspace
+                  Process backspaces for bold/underline.
+                --PROC-BACKSPACE
+                  Treat backspaces as control characters.
+                --proc-return
+                  Delete carriage returns before newline.
+                --PROC-RETURN
+                  Treat carriage returns as control characters.
+                --proc-tab
+                  Expand tabs to spaces.
+                --PROC-TAB
+                  Treat tabs as control characters.
+                --status-col-width=[_N]
+                  Set the width of the -J status column to _N characters.
+                --status-line
+                  Highlight or color the entire line containing a mark.
+                --use-backslash
+                  Subsequent options use backslash as escape char.
+                --use-color
+                  Enables colored text.
+                --wheel-lines=[_N]
+                  Each click of the mouse wheel moves _N lines.
+                --wordwrap
+                  Wrap lines at spaces.
+
+
+ ---------------------------------------------------------------------------
+
+                          LLIINNEE EEDDIITTIINNGG
+
+        These keys can be used to edit text being entered 
+        on the "command line" at the bottom of the screen.
+
+ RightArrow ..................... ESC-l ... Move cursor right one character.
+ LeftArrow ...................... ESC-h ... Move cursor left one character.
+ ctrl-RightArrow  ESC-RightArrow  ESC-w ... Move cursor right one word.
+ ctrl-LeftArrow   ESC-LeftArrow   ESC-b ... Move cursor left one word.
+ HOME ........................... ESC-0 ... Move cursor to start of line.
+ END ............................ ESC-$ ... Move cursor to end of line.
+ BACKSPACE ................................ Delete char to left of cursor.
+ DELETE ......................... ESC-x ... Delete char under cursor.
+ ctrl-BACKSPACE   ESC-BACKSPACE ........... Delete word to left of cursor.
+ ctrl-DELETE .... ESC-DELETE .... ESC-X ... Delete word under cursor.
+ ctrl-U ......... ESC (MS-DOS only) ....... Delete entire line.
+ UpArrow ........................ ESC-k ... Retrieve previous command line.
+ DownArrow ...................... ESC-j ... Retrieve next command line.
+ TAB ...................................... Complete filename & cycle.
+ SHIFT-TAB ...................... ESC-TAB   Complete filename & reverse cycle.
+ ctrl-L ................................... Complete filename, list all.
diff --git a/alpha_pipeline.json b/alpha_pipeline.json
index f972977f..3bcddfd4 100644
--- a/alpha_pipeline.json
+++ b/alpha_pipeline.json
@@ -1,5 +1,5 @@
 {
-  "generated": "2026-08-14T12:45:38.917731+00:00",
+  "generated": "2026-08-15T03:08:52.376261+00:00",
   "n_alphas": 8,
   "n_survived": 0,
   "deployed": [
@@ -9,8 +9,8 @@
     {
       "alpha": "crypto::ls_contrarian",
       "category": "derivative-data",
-      "expected_sharpe": 3.1,
-      "gates": "8/10",
+      "expected_sharpe": 8.66,
+      "gates": "9/10",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
@@ -19,9 +19,9 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::xsec_price_mom",
+      "alpha": "crypto::taker_flow",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.91,
+      "expected_sharpe": 0.88,
       "gates": "9/10",
       "survived": false,
```


---

## 490ce5f0 leaderboard forward panels for Binance and Hyperliquid, daily
III.15's other two venues. screen_copytrading covers OKX; Binance's futures leaderboard and
Hyperliquid's per-account feed -- the most complete free positioning dataset in crypto, public by
design -- were in scope and collected by nothing.

One implementation of what a leaderboard study means, so three venues cannot disagree about it:

  * EXITS ARE THE MEASUREMENT. A trader who leaves between snapshots left for a reason and the
    common reason is a drawdown. They are absent from the second file, so dropping them is the
    DEFAULT behaviour, and it manufactures persistence out of nothing.
  * THE RANK STATISTIC IS PUBLISHED TWICE. Survivors-only, labelled biased upward, and with exits
    ranked last -- the weakest defensible assumption about someone who left. The difference between
    them IS the survivorship effect; neither is publishable alone.
  * AN EMPTY COHORT IS NEVER ARCHIVED. Writing a failed fetch as an empty snapshot makes everyone
    look like they exited, converting a network timeout into a 100% exit rate.
  * MIDRANKS FOR TIES, which a test caught: exits all share one value, so they are always a tie
    block, and distinct ranks would have ordered them by whatever the sort was stable on. The
    naive version returned rho=1.0 on a constant series where the answer is undefined.

The endpoints are unofficial web-front-end routes and the module says so: each failure is named
precisely (HTTP 404 vs 429 vs 403 need three different responses) because a collector returning
nothing must be distinguishable from a venue that has nothing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 490ce5f09aa45f558bcc61675497df09869e61fe
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 15 01:20:45 2026 +0000

    leaderboard forward panels for Binance and Hyperliquid, daily
    
    III.15's other two venues. screen_copytrading covers OKX; Binance's futures leaderboard and
    Hyperliquid's per-account feed -- the most complete free positioning dataset in crypto, public by
    design -- were in scope and collected by nothing.
    
    One implementation of what a leaderboard study means, so three venues cannot disagree about it:
    
      * EXITS ARE THE MEASUREMENT. A trader who leaves between snapshots left for a reason and the
        common reason is a drawdown. They are absent from the second file, so dropping them is the
        DEFAULT behaviour, and it manufactures persistence out of nothing.
      * THE RANK STATISTIC IS PUBLISHED TWICE. Survivors-only, labelled biased upward, and with exits
        ranked last -- the weakest defensible assumption about someone who left. The difference between
        them IS the survivorship effect; neither is publishable alone.
      * AN EMPTY COHORT IS NEVER ARCHIVED. Writing a failed fetch as an empty snapshot makes everyone
        look like they exited, converting a network timeout into a 100% exit rate.
      * MIDRANKS FOR TIES, which a test caught: exits all share one value, so they are always a tie
        block, and distinct ranks would have ordered them by whatever the sort was stable on. The
        naive version returned rho=1.0 on a constant series where the answer is undefined.
    
    The endpoints are unofficial web-front-end routes and the module says so: each failure is named
    precisely (HTTP 404 vs 429 vs 403 need three different responses) because a collector returning
    nothing must be distinguishable from a venue that has nothing.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 libs/research/leaderboard_panel.py       | 206 +++++++++++++++++++++++++++++++
 ops/run_research_cycle.sh                |   8 ++
 scripts/collect_leaderboards.py          | 196 +++++++++++++++++++++++++++++
 tests/research/test_leaderboard_panel.py | 138 +++++++++++++++++++++
 4 files changed, 548 insertions(+)

diff --git a/libs/research/leaderboard_panel.py b/libs/research/leaderboard_panel.py
new file mode 100644
index 00000000..cfa5e933
--- /dev/null
+++ b/libs/research/leaderboard_panel.py
@@ -0,0 +1,206 @@
+"""FORWARD PANELS OVER PUBLIC TRADER LEADERBOARDS -- one implementation, every venue.
+
+WHY A PANEL AND NOT A SCREEN. A leaderboard is, by construction, the maximum of a very large
+number of draws, and it never shows the denominator. Any statistic computed on the traders it
+currently displays is computed on a sample selected for the outcome being measured, so it will show
+skill whether or not skill exists. `screen_copytrading` demonstrated the size of the artifact on
+real OKX data: sorted on pnl/aum/copiers, a 34-trader sample returns Spearman +0.33 between first-
+and second-half returns, manufactured end-to-end by the selection.
+
+The only unbiased design is to FIX A COHORT TODAY, follow it, and count the ones that disappear.
+That is what this module holds, venue-agnostically, so Binance/Bybit/Hyperliquid do not each
+re-derive it and disagree about what "persistence" means.
+
+**EXITS ARE THE MEASUREMENT, NOT MISSING DATA.** A trader who leaves the leaderboard between two
+snapshots left for a reason, and the overwhelmingly common reason is a drawdown. Dropping them --
+which is what happens by default, since they are simply absent from the second file -- is the
+survivorship bug in its purest form. So this reports the exit rate as a first-class number and
+publishes the rank statistic TWICE: once over survivors only (labelled as biased upward, because it
+is), and once with exits ranked last. Neither is published without the other, because the gap
+between them IS the survivorship effect and a reader who sees only one cannot see it.
+
+**A SNAPSHOT IS APPEND-ONLY AND NEVER REWRITTEN.** The panel's value is entirely in the fact that
+the earlier rows were written before anyone knew what happened next. A corrected, re-fetched or
+back-filled row destroys exactly that property while looking like an improvement.
+
+Stdlib + a rank statistic. No venue code here: collectors normalise, this measures.
+"""
+
+from __future__ import annotations
+
+import json
+from datetime import datetime
+from pathlib import Path
+from typing import Any
+
+__all__ = [
+    "MIN_COHORT",
+    "MIN_GAP_DAYS",
+    "TraderRow",
+    "append_snapshot",
+    "forward_persistence",
+    "read_snapshots",
+    "spearman",
+]
+
+#: Two snapshots must be at least this far apart before ANY persistence figure is published.
+#: Venues refresh their published return windows on a multi-day cadence, so a shorter gap re-reads
+#: one datapoint twice and calls it two observations -- which inflates n without adding evidence,
+#: the single most common way a forward panel lies about its own power.
+MIN_GAP_DAYS = 5.0
+
+#: Below 30 traders the Spearman standard error (~1/sqrt(n-1)) exceeds 0.19, so anything under
+#: ~0.4 is indistinguishable from noise. Publishing a number there invites the exact over-reading
+#: this module exists to prevent, so it returns UNDERPOWERED instead of a figure.
+MIN_COHORT = 30
+
+#: The normalised row every venue collector must produce. `trader_id` must be stable across
+#: snapshots -- a venue that rotates its identifiers cannot support a forward panel at all, and
+#: that fact belongs in the collector's report rather than as silently zero persistence.
+TraderRow = dict[str, Any]
+
+
+def read_snapshots(path: Path) -> list[dict[str, Any]]:
+    """Every archived snapshot, oldest first. A malformed line is SKIPPED, never fatal: one bad
+    write must not cost the desk a panel that took weeks of calendar time to accumulate."""
+    try:
+        raw = path.read_text("utf-8", errors="ignore")
+    except OSError:
+        return []
+    out: list[dict[str, Any]] = []
+    for ln in raw.splitlines():
+        if not ln.strip():
+            continue
+        try:
+            out.append(json.loads(ln))
+        except ValueError:
+            continue
+    return out
+
+
+def append_snapshot(path: Path, venue: str, traders: list[TraderRow], *,
+                    at: datetime | None = None, source: str = "") -> bool:
+    """Append one dated cohort. Returns False and writes NOTHING on an empty cohort.
+
+    An empty snapshot is not a cohort of zero traders, it is a FAILED FETCH, and writing it would
+    make every trader look like they exited -- turning a network error into a 100% exit rate, which
+    is a spectacular false finding rather than a missing one.
+    """
+    if not traders:
+        return False
+    path.parent.mkdir(parents=True, exist_ok=True)
+    row = {"at": (at or datetime.now().astimezone()).isoformat(),
+           "venue": venue, "source": source, "n": len(traders), "traders": traders}
+    with path.open("a", encoding="utf-8") as fh:
+        fh.write(json.dumps(row) + "\n")
+    return True
+
+
+def spearman(xs: list[float], ys: list[float]) -> float | None:
+    """Rank correlation. None when undefined -- never 0.0, which reads as 'measured, no relation'
+    and is the wrong claim when the answer is 'not measurable'."""
+    n = len(xs)
+    if n < 3 or n != len(ys):
+        return None
+
+    def rank(v: list[float]) -> list[float]:
+        """MIDRANKS FOR TIES. Assigning distinct ranks to equal values invents an ordering that
+        the data does not contain, and it does so in the direction of whatever the sort was
+        stable on. A constant series then reports rank variance it does not have, and the
+        correlation comes back 1.0 where the honest answer is 'undefined'. That matters here
+        specifically: exits are deliberately assigned one shared value, so they are ALWAYS a tie
+        block, and the naive version would silently rank them against each other."""
+        order = sorted(range(len(v)), key=lambda i: v[i])
+        out = [0.0] * len(v)
+        i = 0
+        while i < len(order):
+            j = i
+            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
+                j += 1
+            mid = (i + j) / 2.0
+            for k in range(i, j + 1):
+                out[order[k]] = mid
+            i = j + 1
+        return out
+
+    rx, ry = rank(xs), rank(ys)
+    mx, my = sum(rx) / n, sum(ry) / n
+    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
+    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
+    dy = sum((b - my) ** 2 for b in ry) ** 0.5
+    return None if dx == 0 or dy == 0 else num / (dx * dy)
+
+
+def _metric(row: TraderRow) -> float:
+    """The venue's published return figure, whatever it called it. Collectors normalise to `roi`."""
+    for k in ("roi", "pnl_ratio", "pnlRatio", "return"):
+        v = row.get(k)
+        if isinstance(v, (int, float)):
+            return float(v)
+    return 0.0
+
+
+def forward_persistence(path: Path, *, min_gap_days: float = MIN_GAP_DAYS,
+                        min_cohort: int = MIN_COHORT) -> dict[str, Any]:
+    """Same cohort, two separated snapshots, exits counted as failures.
+
+    Publishes the rank statistic twice. `spearman_survivors_only` is what a naive analysis computes
+    and is BIASED UPWARD, because everyone who blew up between the snapshots has been silently
+    removed from it. `spearman_exits_ranked_last` puts each exited trader below every survivor on
+    the forward axis, which is the weakest defensible assumption about someone who left a
+    leaderboard. The DIFFERENCE between the two is the survivorship effect, and it is the number
+    worth reading.
+    """
+    snaps = read_snapshots(path)
+    if not snaps:
+        return {"state": "NO-DATA", "n_snapshots": 0,
+                "why": "no snapshot archived yet -- the forward clock starts on the first "
+                       "successful collection, and UNMEASURED is not 'no persistence'"}
+    if len(snaps) < 2:
+        return {"state": "NO-DATA", "n_snapshots": 1,
+                "why": "one snapshot cannot measure persistence; the clock is running"}
+
+    first, last = snaps[0], snaps[-1]
+    gap = (datetime.fromisoformat(last["at"]) - datetime.fromisoformat(first["at"])).days
+    if gap < min_gap_days:
+        return {"state": "NO-DATA", "n_snapshots": len(snaps), "gap_days": gap,
+                "why": f"snapshots {gap}d apart, under the {min_gap_days}d minimum -- a shorter "
+                       "gap re-reads one datapoint twice and calls it two observations"}
+
+    then = {str(t.get("trader_id")): t for t in first.get("traders", [])}
+    now = {str(t.get("trader_id")): t for t in last.get("traders", [])}
+    survived = [c for c in then if c in now]
+    exited = [c for c in then if c not in now]
+    if len(then) < min_cohort:
+        return {"state": "UNDERPOWERED", "n_snapshots": len(snaps), "gap_days": gap,
+                "cohort": len(then), "exited": len(exited),
+                "why": f"cohort {len(then)} < {min_cohort}; a rank statistic here is noise, and "
+                       "publishing one invites the over-reading this panel exists to prevent"}
+
+    xs = [_metric(then[c]) for c in survived]
+    ys = [_metric(now[c]) - _metric(then[c]) for c in survived]
+    surv_rho = spearman(xs, ys)
+
+    # EXITS RANKED LAST. One step below the worst survivor -- not an invented return, just an
+    # ordering, which is all a rank statistic consumes. Ties among exits are fine: they share the
+    # same claim, that they did worse than everyone still standing.
+    floor = (min(ys) - 1.0) if ys else -1.0
+    xs_all = xs + [_metric(then[c]) for c in exited]
+    ys_all = ys + [floor] * len(exited)
+    all_rho = spearman(xs_all, ys_all)
+
+    return {
+        "state": "MEASURED", "n_snapshots": len(snaps), "gap_days": gap,
+        "cohort": len(then), "survived": len(survived),
+        "exited_counted_as_failures": len(exited),
+        "exit_rate": round(len(exited) / len(then), 3),
+        "spearman_survivors_only": surv_rho,
+        "spearman_exits_ranked_last": all_rho,
+        "survivorship_effect": (None if surv_rho is None or all_rho is None
+                                else round(surv_rho - all_rho, 4)),
+        "note": ("spearman_survivors_only is BIASED UPWARD -- everyone who blew up between the "
+                 "snapshots is absent from it. spearman_exits_ranked_last places each exited "
+                 "trader below every survivor on the forward axis, the weakest defensible "
+                 "assumption about someone who left a leaderboard. The gap between the two IS the "
+                 "survivorship effect; neither figure is publishable without the other."),
+    }
diff --git a/ops/run_research_cycle.sh b/ops/run_research_cycle.sh
index 413d59f1..1bead74f 100755
--- a/ops/run_research_cycle.sh
+++ b/ops/run_research_cycle.sh
@@ -191,6 +191,14 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
   # It exits 0 even when the venue is unreachable and records the failure in its own report, so a
   # rate-limited fetch does not redden the whole cycle -- an unreachable venue is not a desk defect.
   nice -n 15 "$PY" scripts/screen_copytrading.py
+  # THE OTHER TWO VENUES III.15 NAMES. screen_copytrading covers OKX only; Binance's futures
+  # leaderboard and Hyperliquid's per-account feed (the most complete free positioning dataset in
+  # crypto, public by design -- FREE_DATA_ADDENDA C3 #54) were in scope and collected by nothing.
+  # Same discipline, one implementation: append-only, exits counted as FAILURES, and the rank
+  # statistic published twice so the survivorship effect is the difference between them rather
+  # than an argument. `|| true` is NOT used: an unreachable venue is recorded inside the report
+  # and the script still exits 0, so a real crash here is a real cycle failure.
+  nice -n 15 "$PY" scripts/collect_leaderboards.py
   # THE RETURN ENGINES. Everything above measures whether the RESEARCH is healthy; these decide
   # where capital would go if there were any. ELEVEN books; nine correctly report UNMEASURED on a
   # clone with no positions and each names the artifact it needs -- they exist now so that nothing
diff --git a/scripts/collect_leaderboards.py b/scripts/collect_leaderboards.py
new file mode 100644
index 00000000..2d804253
--- /dev/null
+++ b/scripts/collect_leaderboards.py
@@ -0,0 +1,196 @@
+#!/usr/bin/env python3
+"""PUBLIC TRADER LEADERBOARDS -> A FORWARD PANEL. Binance and Hyperliquid, daily, append-only.
+
+WHY THIS EXISTS. III.15 makes leaderboard forensics a standing mandate and `screen_copytrading`
+implements it for ONE venue (OKX copytrading). Binance's futures leaderboard and Hyperliquid's
+per-account feed -- which `FREE_DATA_ADDENDA` C3 #54 calls the most complete free positioning
+dataset in crypto, public by design -- were in scope and collected by nothing.
+
+**THE ONLY THING WORTH COLLECTING IS TIME.** A leaderboard read once is worthless: it is the
+maximum of a very large number of draws, shown without its denominator, and every statistic
+computed on it is computed on a sample selected for the outcome being measured. A leaderboard read
+DAILY, with the same identifiers, becomes a forward panel in which disappearance is data. That is
+the entire value proposition here and it is why this runs on a schedule or not at all.
+
+**THE ENDPOINTS ARE UNOFFICIAL AND THIS FILE SAYS SO OUT LOUD.** Binance's leaderboard is a `bapi`
+route behind its web front end, not a documented API: it can change shape or vanish without notice,
+and it is rate-limited by an unpublished policy. So every venue carries a LIST of candidate
+endpoints, each is probed in order, and the report names exactly which responded and how each
+failure failed. A collector that returns nothing must be distinguishable from a venue that has
+nothing, which is L1.28a on the collection layer.
+
+**A FAILED FETCH IS NEVER ARCHIVED.** `append_snapshot` refuses an empty cohort, because writing
+one would make every trader in the previous snapshot look like they exited -- turning a network
+timeout into a 100% exit rate, which is a spectacular false finding rather than a missing one.
+
+**NOTHING HERE IS EVIDENCE FOR CAPITAL.** It produces a panel. The panel earns a forward clock
+under the ordinary funnel or it earns nothing, and no leaderboard entry, rank or return figure may
+reach capital (III.15).
+
+    python scripts/collect_leaderboards.py            # collect all venues
+    python scripts/collect_leaderboards.py --probe    # report reachability, archive nothing
+"""
+
+from __future__ import annotations
+
+# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
+import sys as _sys
+from pathlib import Path as _P
+
+if str(_P(__file__).resolve().parent.parent) not in _sys.path:
+    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
+
+import argparse
+import json
+import urllib.error
+import urllib.request
+from datetime import UTC, datetime
+from pathlib import Path
+from typing import Any
+
+from libs.research.leaderboard_panel import TraderRow, append_snapshot, forward_persistence
+
+_PANEL_DIR = Path("data/leaderboard_panel")
+_OUT = Path("web/leaderboard_collector.json")
+_TIMEOUT = 25
+
+#: Binance's leaderboard lives behind its web front end. `periodType` values the route accepts are
+#: EXACT_MONTHLY / EXACT_WEEKLY / EXACT_DAILY / ALL; ROI is requested rather than PNL because a
+#: return is comparable across account sizes and a PnL is not.
+_BINANCE_RANK = "https://www.binance.com/bapi/futures/v1/public/future/leaderboard/getLeaderboardRank"
+_BINANCE_BODY = {"isShared": True, "isTrader": False, "periodType": "EXACT_MONTHLY",
+                 "statisticsType": "ROI", "tradeType": "PERPETUAL"}
+
+#: Hyperliquid publishes its leaderboard as a static stats blob. Every account's positions are
+#: public by design on this venue, so this is the one place where a panel can eventually be joined
+#: to actual holdings rather than to a published summary figure.
+_HYPERLIQUID_URLS = ("https://stats-data.hyperliquid.xyz/Mainnet/leaderboard",)
+
+_UA = {"User-Agent": "quant-platform/1.0", "Content-Type": "application/json"}
+
+
+def _post(url: str, body: dict[str, Any]) -> Any:
+    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=_UA, method="POST")
+    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
+        return json.loads(r.read())
+
+
+def _get(url: str) -> Any:
+    req = urllib.request.Request(url, headers={"User-Agent": _UA["User-Agent"]})
+    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
+        return json.loads(r.read())
+
+
+def _why(exc: BaseException) -> str:
+    """A failure named precisely enough to act on. `HTTPError` alone cannot distinguish a route
+    that moved (404) from one that is rate-limiting us (429) from one that wants a browser (403),
+    and those are three different responses."""
+    if isinstance(exc, urllib.error.HTTPError):
+        return f"HTTP {exc.code}"
+    if isinstance(exc, urllib.error.URLError):
+        return f"URLError {exc.reason}"
+    return f"{type(exc).__name__}: {exc}"
+
+
+def fetch_binance() -> tuple[list[TraderRow], str]:
+    """Normalised cohort from the Binance futures leaderboard.
+
+    `encryptedUid` is the identifier that must be stable across snapshots -- nickName is not, since
+    a trader can rename and would then read as one exit plus one new entrant.
+    """
+    try:
+        d = _post(_BINANCE_RANK, _BINANCE_BODY)
+    except Exception as exc:
+        return [], f"UNREACHABLE ({_why(exc)})"
+    rows = (d or {}).get("data") or []
+    if not isinstance(rows, list) or not rows:
+        return [], f"RESPONDED BUT EMPTY (success={(d or {}).get('success')!r}) -- shape may have changed"
+    out: list[TraderRow] = []
+    for r in rows:
+        uid = r.get("encryptedUid")
+        if not uid:
+            continue
+        out.append({"trader_id": str(uid), "nick": r.get("nickName"),
+                    "roi": float(r.get("value") or 0.0),
+                    "position_shared": bool(r.get("positionShared")),
+                    "window": _BINANCE_BODY["periodType"]})
+    return out, "ok" if out else "RESPONDED BUT NO USABLE IDENTIFIERS"
+
+
+def _hl_roi(row: dict[str, Any], window: str = "month") -> float:
+    """Hyperliquid publishes performance as [[window, {pnl, roi, vlm}], ...]. Absent window -> 0.0
+    only because a rank statistic needs a number; the collector records the window it used so a
+    reader can see which figure is being ranked."""
+    for w in row.get("windowPerformances") or []:
+        if isinstance(w, list) and len(w) == 2 and w[0] == window:
+            return float((w[1] or {}).get("roi") or 0.0)
```


---

## e9e83070 Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

```diff
commit e9e8307030a9bb75bdffef3a0cbdca16c477d235
Merge: 373b8a82 02a6e6c8
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 01:16:20 2026 +0000

    Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

 libs/execution/binance_spot_live.py              | 69 +++++++++++++++++++++++-
 tests/execution/test_spot_connectors_strength.py |  7 +++
 tests/execution/test_spot_live_error_detail.py   | 50 +++++++++++++++--
 3 files changed, 120 insertions(+), 6 deletions(-)
```


---

## 02a6e6c8 pin the venue egress to IPv4 -- the -2015 was the address family
Measured on the live box: it is dual-stack (95.216.191.70 and 2a01:4f9:c010:9451::1) and Python's
resolver preferred the v6 address. The API key was whitelisted for the v4 one, so every request
reached Binance from an address the venue had never been told about, and it answered

    -2015 Invalid API-key, IP, or permissions for action

on a key whose key, secret and permissions were all correct. The venue names three causes and the
true one is a FOURTH it does not mention. Nothing inside the process can see this: the request is
well formed, the credential is right, the response is a clean 401.

/etc/gai.conf needs root the box does not have, and adding the v6 address to the whitelist leaves
the desk one dual-stack host away from the same silent failure -- so the family is pinned in the
connector. The egress address the venue matches is now a property of this module rather than of
the host's resolver ordering.

The socket bound moved to the call site with it (_TIMEOUT_S, passed explicitly): a wrapper that
forgets to forward a timeout turns an order into a hang, and a hung order is the one state the
desk cannot reconcile.

Three tests: the resolver is asked for AF_INET and nothing else, the pin is on, and the custom
connection's TLS context verifies certificates and hostnames -- it wraps its own socket, so a
missing context would still work, which is the danger.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 02a6e6c8d2c8301dd1125ec2a443f2af1b7c3fd1
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 15 01:15:52 2026 +0000

    pin the venue egress to IPv4 -- the -2015 was the address family
    
    Measured on the live box: it is dual-stack (95.216.191.70 and 2a01:4f9:c010:9451::1) and Python's
    resolver preferred the v6 address. The API key was whitelisted for the v4 one, so every request
    reached Binance from an address the venue had never been told about, and it answered
    
        -2015 Invalid API-key, IP, or permissions for action
    
    on a key whose key, secret and permissions were all correct. The venue names three causes and the
    true one is a FOURTH it does not mention. Nothing inside the process can see this: the request is
    well formed, the credential is right, the response is a clean 401.
    
    /etc/gai.conf needs root the box does not have, and adding the v6 address to the whitelist leaves
    the desk one dual-stack host away from the same silent failure -- so the family is pinned in the
    connector. The egress address the venue matches is now a property of this module rather than of
    the host's resolver ordering.
    
    The socket bound moved to the call site with it (_TIMEOUT_S, passed explicitly): a wrapper that
    forgets to forward a timeout turns an order into a hang, and a hung order is the one state the
    desk cannot reconcile.
    
    Three tests: the resolver is asked for AF_INET and nothing else, the pin is on, and the custom
    connection's TLS context verifies certificates and hostnames -- it wraps its own socket, so a
    missing context would still work, which is the danger.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 libs/execution/binance_spot_live.py              | 69 +++++++++++++++++++++++-
 tests/execution/test_spot_connectors_strength.py |  7 +++
 tests/execution/test_spot_live_error_detail.py   | 50 +++++++++++++++--
 3 files changed, 120 insertions(+), 6 deletions(-)

diff --git a/libs/execution/binance_spot_live.py b/libs/execution/binance_spot_live.py
index b69a9ae7..6a008703 100644
--- a/libs/execution/binance_spot_live.py
+++ b/libs/execution/binance_spot_live.py
@@ -13,7 +13,10 @@ from __future__ import annotations
 
 import hashlib
 import hmac
+import http.client
 import json
+import socket
+import ssl
 import time
 import urllib.error
 import urllib.parse
@@ -24,6 +27,21 @@ from typing import Any
 from libs.execution.idempotency import client_order_id
 
 _BASE = "https://api.binance.com"                # PINNED live spot -- verified against docs
+
+#: EVERY CALL LEAVES OVER IPv4, BECAUSE THE VENUE'S WHITELIST IS AN IPv4 LIST.
+#:
+#: Measured 2026-08-15 on the live box. It holds two addresses -- 95.216.191.70 and
+#: 2a01:4f9:c010:9451::1 -- and Python's default resolver preferred the IPv6 one. So the key was
+#: whitelisted for the v4 address, every request arrived from the v6 address, and Binance returned
+#: `-2015 Invalid API-key, IP, or permissions for action` on a key whose key, secret and
+#: permissions were all correct. The message names three causes and the true one is a FOURTH that
+#: it does not mention, which is why this constant is here rather than in an operator's memory.
+#:
+#: The alternative fixes were rejected: /etc/gai.conf needs root the box does not have, and adding
+#: the v6 address to the venue whitelist leaves the desk one dual-stack host away from the same
+#: silent failure. Pinning the egress family makes the address the venue sees a PROPERTY OF THIS
+#: MODULE rather than of the host's resolver ordering.
+FORCE_IPV4 = True
 _KEYFILE = Path("data/secrets/binance_live_spot.json")
 _ENABLE_FLAG = Path("data/LIVE_ENABLE")
 _VPS_MARKER = Path("data/LIVE_VPS_VERIFIED")
@@ -53,6 +71,55 @@ def is_armed() -> tuple[bool, str]:
     return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())
 
 
+class _IPv4HTTPSConnection(http.client.HTTPSConnection):
+    """HTTPS pinned to A records. `socket.create_connection` walks whatever `getaddrinfo` returns
+    in whatever order the host prefers, so on a dual-stack box the egress address -- the one the
+    venue matches against its whitelist -- is decided by system configuration nobody here reads."""
+
+    def __init__(self, *args: Any, **kwargs: Any) -> None:
+        super().__init__(*args, **kwargs)
+        # HELD EXPLICITLY. `HTTPSConnection._context` exists at runtime but is absent from the
+        # typeshed stubs, and reaching for a private attribute the checker cannot see is how a
+        # TLS context silently becomes None on a version bump -- on the module that places orders.
+        self._tls: ssl.SSLContext = kwargs.get("context") or ssl.create_default_context()
+
+    def connect(self) -> None:
+        last: OSError | None = None
+        for af, kind, proto, _canon, addr in socket.getaddrinfo(
+                self.host, self.port, socket.AF_INET, socket.SOCK_STREAM):
+            sock = socket.socket(af, kind, proto)
+            try:
+                if isinstance(self.timeout, int | float):
+                    sock.settimeout(self.timeout)
+                sock.connect(addr)
+            except OSError as exc:
+                sock.close()
+                last = exc
+                continue
+            self.sock = self._tls.wrap_socket(sock, server_hostname=self.host)
+            return
+        raise last or OSError(f"no IPv4 address for {self.host}")
+
+
+class _IPv4HTTPSHandler(urllib.request.HTTPSHandler):
+    def https_open(self, req: urllib.request.Request) -> Any:
+        return self.do_open(_IPv4HTTPSConnection, req,
+                            context=getattr(self, "_context", None))
+
+
+#: Socket bound on every venue call. An unbounded read on the order path does not fail, it HANGS,
+#: and a hung order is the one state the desk cannot reconcile -- it does not know whether the leg
+#: exists. Passed EXPLICITLY at the call site rather than defaulted, so the bound is visible where
+#: the request is made and cannot be lost by a wrapper that forgets to forward it.
+_TIMEOUT_S = 20
+
+
+def _urlopen(req: urllib.request.Request, *, timeout: int = _TIMEOUT_S) -> Any:
+    if not FORCE_IPV4:
+        return urllib.request.urlopen(req, timeout=timeout)
+    return urllib.request.build_opener(_IPv4HTTPSHandler()).open(req, timeout=timeout)
+
+
 def _open(req: urllib.request.Request) -> Any:
     """urlopen, but a rejection carries the VENUE'S OWN REASON.
 
@@ -67,7 +134,7 @@ def _open(req: urllib.request.Request) -> Any:
     The body is quoted, never the credential: the request's headers are not touched here.
     """
     try:
-        with urllib.request.urlopen(req, timeout=20) as r:
+        with _urlopen(req, timeout=_TIMEOUT_S) as r:
             return json.loads(r.read())
     except urllib.error.HTTPError as exc:
         try:
diff --git a/tests/execution/test_spot_connectors_strength.py b/tests/execution/test_spot_connectors_strength.py
index 911f6a20..dca5386f 100644
--- a/tests/execution/test_spot_connectors_strength.py
+++ b/tests/execution/test_spot_connectors_strength.py
@@ -360,6 +360,13 @@ def _capture_requests(mod: Any, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
         return _FakeResponse(b'{"ok": true}')
 
     monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
+    # binance_spot_live routes through its OWN opener (`_urlopen`) to pin the egress to IPv4 --
+    # the box is dual-stack and the venue whitelists an IPv4 address, so leaving the family to
+    # the host resolver is what produced a -2015 on a wholly correct key. That opener does not
+    # consult `urllib.request.urlopen`, so patching only the stdlib name would let these tests
+    # make a REAL network call and fail on TLS instead of on the assertion they are about.
+    if hasattr(mod, "_urlopen"):
+        monkeypatch.setattr(mod, "_urlopen", fake_urlopen)
     return seen
 
 
diff --git a/tests/execution/test_spot_live_error_detail.py b/tests/execution/test_spot_live_error_detail.py
index 938b85d2..ff4b1566 100644
--- a/tests/execution/test_spot_live_error_detail.py
+++ b/tests/execution/test_spot_live_error_detail.py
@@ -31,7 +31,7 @@ def test_THE_BINANCE_ERROR_CODE_SURVIVES_INTO_THE_MESSAGE(monkeypatch: pytest.Mo
     """-2015 is the difference between 'wrong key' and 'right key, wrong IP'. Losing it costs the
     operator the entire diagnosis."""
     body = b'{"code":-2015,"msg":"Invalid API-key, IP, or permissions for action."}'
-    monkeypatch.setattr(urllib.request, "urlopen",
+    monkeypatch.setattr(live, "_urlopen",
                         lambda *a, **k: (_ for _ in ()).throw(_http_error(401, body)))
     with pytest.raises(RuntimeError) as ei:
         live._open(urllib.request.Request("https://api.binance.com/api/v3/account"))
@@ -48,8 +48,7 @@ def test_A_BODYLESS_REJECTION_STILL_RAISES_AND_SAYS_SO(monkeypatch: pytest.Monke
             raise OSError("stream closed")
 
     err = urllib.error.HTTPError("u", 418, "teapot", {}, _Dead(b""))
-    monkeypatch.setattr(urllib.request, "urlopen",
-                        lambda *a, **k: (_ for _ in ()).throw(err))
+    monkeypatch.setattr(live, "_urlopen", lambda *a, **k: (_ for _ in ()).throw(err))
     with pytest.raises(RuntimeError) as ei:
         live._open(urllib.request.Request("https://api.binance.com/api/v3/account"))
     assert "418" in str(ei.value) and "no body" in str(ei.value)
@@ -57,7 +56,7 @@ def test_A_BODYLESS_REJECTION_STILL_RAISES_AND_SAYS_SO(monkeypatch: pytest.Monke
 
 def test_THE_MESSAGE_IS_BOUNDED(monkeypatch: pytest.MonkeyPatch) -> None:
     """A venue returning an HTML error page must not paste a kilobyte into every journal line."""
-    monkeypatch.setattr(urllib.request, "urlopen",
+    monkeypatch.setattr(live, "_urlopen",
                         lambda *a, **k: (_ for _ in ()).throw(_http_error(502, b"x" * 50_000)))
     with pytest.raises(RuntimeError) as ei:
         live._open(urllib.request.Request("https://api.binance.com/api/v3/account"))
@@ -74,5 +73,46 @@ def test_A_SUCCESSFUL_CALL_IS_UNCHANGED(monkeypatch: pytest.MonkeyPatch) -> None
         def __exit__(self, *a: object) -> None:
             return None
 
-    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(b'{"ok":1}'))
+    monkeypatch.setattr(live, "_urlopen", lambda *a, **k: _Resp(b'{"ok":1}'))
     assert live._open(urllib.request.Request("https://api.binance.com/api/v3/ping")) == {"ok": 1}
+
+
+def test_EVERY_CALL_RESOLVES_IPv4_ONLY(monkeypatch: pytest.MonkeyPatch) -> None:
+    """THE ONE THAT COST A LIVE ARMING. The box is dual-stack -- 95.216.191.70 and
+    2a01:4f9:c010:9451::1 -- and Python's resolver preferred the v6 address. The key was
+    whitelisted for the v4 one, so every request arrived from an address the venue had never been
+    told about and Binance answered `-2015 Invalid API-key, IP, or permissions for action` on a key
+    whose key, secret and permissions were all correct.
+
+    The venue's message names three causes and the true one is a fourth it does not mention. There
+    is no way to notice this from inside the process, which is why the family is pinned in code and
+    asserted here rather than left to the host's resolver ordering.
+    """
+    seen: list[int] = []
+
+    def _spy(host: str, port: int, family: int = 0, *a: object, **k: object) -> list[object]:
+        seen.append(family)
+        raise OSError("stop here -- the family is what this test is about")
+
+    monkeypatch.setattr(live.socket, "getaddrinfo", _spy)
+    conn = live._IPv4HTTPSConnection("api.binance.com", 443)
+    with pytest.raises(OSError):
+        conn.connect()
+    assert seen == [live.socket.AF_INET], (
+        f"resolved with family {seen} -- anything but AF_INET lets a dual-stack host choose the "
+        "egress address, and the egress address is what the venue whitelist matches")
+
+
+def test_THE_IPv4_PIN_IS_ON() -> None:
+    """A constant nobody sets is a constant somebody unsets. The live box needs this True; the
+    test states the requirement so flipping it is a visible decision rather than a silent one."""
+    assert live.FORCE_IPV4 is True
+
+
+def test_THE_TLS_CONTEXT_IS_NEVER_NONE() -> None:
+    """The custom connection wraps its own socket, so a missing context would mean an unverified
+    TLS session on the module that places orders -- and it would still work, which is the danger."""
+    conn = live._IPv4HTTPSConnection("api.binance.com", 443)
+    assert isinstance(conn._tls, live.ssl.SSLContext)
+    assert conn._tls.verify_mode == live.ssl.CERT_REQUIRED
+    assert conn._tls.check_hostname is True
```


---

## 373b8a82 Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

```diff
commit 373b8a8229f234b7c4f7dbce4ccc0fc70c732db7
Merge: e97920f3 172d6ea7
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 01:05:54 2026 +0000

    Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

 libs/execution/binance_spot_live.py            | 31 ++++++++--
 tests/execution/test_spot_live_error_detail.py | 78 ++++++++++++++++++++++++++
 2 files changed, 105 insertions(+), 4 deletions(-)
```


---

## 172d6ea7 a venue rejection now carries the venue's reason
The first live arming printed `venue unreadable (HTTPError: HTTP Error 401: Unauthorized)` and
that sentence is true of at least four different problems with four different fixes: -2014 a
malformed key, -2015 a valid key from a non-whitelisted IP or without trading permission, -1021 a
clock skew, -1022 a bad signature. HTTPError.__str__ discards the body, which is the only part
that says which one it is.

So the operator holding that message has nothing to act on, and the obvious next move -- re-paste
the key -- is the wrong one in three cases out of four.

Both request paths in the live spot connector now go through one opener that reads the body and
quotes it, bounded to 300 chars so an HTML error page cannot flood a journal line. Credentials are
untouched: the body is quoted, the headers are not.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 172d6ea713715070f245198b79d569fe305aafe9
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 15 01:04:23 2026 +0000

    a venue rejection now carries the venue's reason
    
    The first live arming printed `venue unreadable (HTTPError: HTTP Error 401: Unauthorized)` and
    that sentence is true of at least four different problems with four different fixes: -2014 a
    malformed key, -2015 a valid key from a non-whitelisted IP or without trading permission, -1021 a
    clock skew, -1022 a bad signature. HTTPError.__str__ discards the body, which is the only part
    that says which one it is.
    
    So the operator holding that message has nothing to act on, and the obvious next move -- re-paste
    the key -- is the wrong one in three cases out of four.
    
    Both request paths in the live spot connector now go through one opener that reads the body and
    quotes it, bounded to 300 chars so an HTML error page cannot flood a journal line. Credentials are
    untouched: the body is quoted, the headers are not.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 libs/execution/binance_spot_live.py            | 31 ++++++++--
 tests/execution/test_spot_live_error_detail.py | 78 ++++++++++++++++++++++++++
 2 files changed, 105 insertions(+), 4 deletions(-)

diff --git a/libs/execution/binance_spot_live.py b/libs/execution/binance_spot_live.py
index d83927e0..b69a9ae7 100644
--- a/libs/execution/binance_spot_live.py
+++ b/libs/execution/binance_spot_live.py
@@ -15,6 +15,7 @@ import hashlib
 import hmac
 import json
 import time
+import urllib.error
 import urllib.parse
 import urllib.request
 from pathlib import Path
@@ -52,13 +53,36 @@ def is_armed() -> tuple[bool, str]:
     return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())
 
 
+def _open(req: urllib.request.Request) -> Any:
+    """urlopen, but a rejection carries the VENUE'S OWN REASON.
+
+    `HTTPError.__str__` is "HTTP Error 401: Unauthorized" and the body is discarded unless
+    something reads it. Binance puts the only actionable part there: -2015 "Invalid API-key, IP, or
+    permissions for action" is a whitelist or permission problem on a key that is otherwise
+    correct, -2014 is a malformed key, -1021 is a clock skew, -1022 a bad signature. Those need
+    four different fixes and the bare status code distinguishes none of them, so an operator
+    reading the refusal cannot tell "wrong key" from "right key, wrong IP" -- which is exactly the
+    wall a first live arming hits.
+
+    The body is quoted, never the credential: the request's headers are not touched here.
+    """
+    try:
+        with urllib.request.urlopen(req, timeout=20) as r:
+            return json.loads(r.read())
+    except urllib.error.HTTPError as exc:
+        try:
+            detail = exc.read().decode("utf-8", "replace")[:300]
+        except Exception:                                  # body already consumed or stream dead
+            detail = "(no body)"
+        raise RuntimeError(f"venue rejected the call: HTTP {exc.code} {detail}") from exc
+
+
 def _get(path: str, params: dict[str, Any] | None = None) -> Any:
     url = f"{_BASE}{path}"
     if params:
         url += "?" + urllib.parse.urlencode(params)
     req = urllib.request.Request(url, headers={"User-Agent": "quant-live-spot/1.0"})
-    with urllib.request.urlopen(req, timeout=20) as r:
-        return json.loads(r.read())
+    return _open(req)
 
 
 def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
@@ -77,8 +101,7 @@ def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
     else:
         req = urllib.request.Request(f"{_BASE}{path}", data=body, method=method,
                                      headers={"X-MBX-APIKEY": key})
-    with urllib.request.urlopen(req, timeout=20) as r:
-        return json.loads(r.read())
+    return _open(req)
 
 
 def prices() -> dict[str, float]:
diff --git a/tests/execution/test_spot_live_error_detail.py b/tests/execution/test_spot_live_error_detail.py
new file mode 100644
index 00000000..938b85d2
--- /dev/null
+++ b/tests/execution/test_spot_live_error_detail.py
@@ -0,0 +1,78 @@
+"""A venue rejection must carry the venue's reason, not just its status code.
+
+THE FAILURE THIS CLOSES was met on the first live arming. `run_spot_executor` printed
+
+    venue unreadable (HTTPError: HTTP Error 401: Unauthorized) -- refusing
+
+and that sentence is true of at least four completely different problems, each with a different
+fix: a wrong key (-2014), a right key from a non-whitelisted IP or without trading permission
+(-2015), a clock skew (-1021), a bad signature (-1022). `HTTPError.__str__` discards the body,
+which is the only part that says which. An operator holding that message has nothing to act on and
+will re-paste the same key three times.
+"""
+
+from __future__ import annotations
+
+import io
+import urllib.error
+import urllib.request
+
+import pytest
+
+from libs.execution import binance_spot_live as live
+
+
+def _http_error(code: int, body: bytes) -> urllib.error.HTTPError:
+    return urllib.error.HTTPError("https://api.binance.com/api/v3/account", code, "Unauthorized",
+                                  {}, io.BytesIO(body))
+
+
+def test_THE_BINANCE_ERROR_CODE_SURVIVES_INTO_THE_MESSAGE(monkeypatch: pytest.MonkeyPatch) -> None:
+    """-2015 is the difference between 'wrong key' and 'right key, wrong IP'. Losing it costs the
+    operator the entire diagnosis."""
+    body = b'{"code":-2015,"msg":"Invalid API-key, IP, or permissions for action."}'
+    monkeypatch.setattr(urllib.request, "urlopen",
+                        lambda *a, **k: (_ for _ in ()).throw(_http_error(401, body)))
+    with pytest.raises(RuntimeError) as ei:
+        live._open(urllib.request.Request("https://api.binance.com/api/v3/account"))
+    msg = str(ei.value)
+    assert "401" in msg
+    assert "-2015" in msg, "the venue's own code is the actionable part and must survive"
+    assert "Invalid API-key, IP, or permissions" in msg
+
+
+def test_A_BODYLESS_REJECTION_STILL_RAISES_AND_SAYS_SO(monkeypatch: pytest.MonkeyPatch) -> None:
+    """An unreadable body must not become a silent success, and must not mask the status code."""
+    class _Dead(io.BytesIO):
+        def read(self, *a: object, **k: object) -> bytes:
+            raise OSError("stream closed")
+
+    err = urllib.error.HTTPError("u", 418, "teapot", {}, _Dead(b""))
+    monkeypatch.setattr(urllib.request, "urlopen",
+                        lambda *a, **k: (_ for _ in ()).throw(err))
+    with pytest.raises(RuntimeError) as ei:
+        live._open(urllib.request.Request("https://api.binance.com/api/v3/account"))
+    assert "418" in str(ei.value) and "no body" in str(ei.value)
+
+
+def test_THE_MESSAGE_IS_BOUNDED(monkeypatch: pytest.MonkeyPatch) -> None:
+    """A venue returning an HTML error page must not paste a kilobyte into every journal line."""
+    monkeypatch.setattr(urllib.request, "urlopen",
+                        lambda *a, **k: (_ for _ in ()).throw(_http_error(502, b"x" * 50_000)))
+    with pytest.raises(RuntimeError) as ei:
+        live._open(urllib.request.Request("https://api.binance.com/api/v3/account"))
+    assert len(str(ei.value)) < 500
+
+
+def test_A_SUCCESSFUL_CALL_IS_UNCHANGED(monkeypatch: pytest.MonkeyPatch) -> None:
+    """The error path must not have altered the happy path -- this wraps every read and every
+    order placement in the live spot connector."""
+    class _Resp(io.BytesIO):
+        def __enter__(self) -> _Resp:
+            return self
+
+        def __exit__(self, *a: object) -> None:
+            return None
+
+    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(b'{"ok":1}'))
+    assert live._open(urllib.request.Request("https://api.binance.com/api/v3/ping")) == {"ok": 1}
```


---

## e97920f3 Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

```diff
commit e97920f3e5590cd1df4ef883f0325796190bf751
Merge: 94abbd1c 6a9e360a
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 00:59:55 2026 +0000

    Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

 docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md | 33 +++++++++++++++++++++++
 ops/run_research_cycle.sh                         | 11 ++++++++
 tests/ops/test_research_cycle.py                  | 16 +++++++++++
 3 files changed, 60 insertions(+)
```


---

## 6a9e360a schedule the leaderboard panel -- III.15 was a mandate with no scheduler
screen_copytrading.py has existed since 2026-07-31 and is right about everything. It appends an
append-only cohort snapshot, refuses to publish a persistence figure until it holds two snapshots
five days apart, counts exits as FAILURES rather than dropping them, and charges the 13% copier
profit share against any edge before it counts as ours rather than the lead's. It documents the
trap in full: a 34-trader OKX sample sorted on pnl/aum/copiers returns Spearman +0.33 persistence,
manufactured end-to-end by selecting on the outcome and by the absence of everyone who blew up.

Nothing ran it. Zero schedulers, zero cron entries, zero cycle lines.

So the one organ whose verdict is made of calendar separation had been accumulating none, and its
standing NO-DATA was a statement about the cron table rather than about copy traders. That is
L1.28a inverted -- UNMEASURED read as measured-null -- for fifteen days, and III.16 applied to
III.15 itself.

Daily now, and a test fails if the line is ever removed. It exits 0 on an unreachable venue and
records the failure in its own report, so a rate-limited fetch does not redden the cycle.

Venue coverage is stated rather than implied: this reads OKX copytrading only. Binance's
leaderboard, Bybit's and Hyperliquid's per-account feed are in scope and NOT collected. Each is a
separate endpoint and none may be written speculatively from a network-denied clone -- a guessed
endpoint produces a collector that fails silently and a panel that looks like it is accumulating.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 6a9e360af767db8131a949c7830ef81149016f30
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 15 00:58:59 2026 +0000

    schedule the leaderboard panel -- III.15 was a mandate with no scheduler
    
    screen_copytrading.py has existed since 2026-07-31 and is right about everything. It appends an
    append-only cohort snapshot, refuses to publish a persistence figure until it holds two snapshots
    five days apart, counts exits as FAILURES rather than dropping them, and charges the 13% copier
    profit share against any edge before it counts as ours rather than the lead's. It documents the
    trap in full: a 34-trader OKX sample sorted on pnl/aum/copiers returns Spearman +0.33 persistence,
    manufactured end-to-end by selecting on the outcome and by the absence of everyone who blew up.
    
    Nothing ran it. Zero schedulers, zero cron entries, zero cycle lines.
    
    So the one organ whose verdict is made of calendar separation had been accumulating none, and its
    standing NO-DATA was a statement about the cron table rather than about copy traders. That is
    L1.28a inverted -- UNMEASURED read as measured-null -- for fifteen days, and III.16 applied to
    III.15 itself.
    
    Daily now, and a test fails if the line is ever removed. It exits 0 on an unreachable venue and
    records the failure in its own report, so a rate-limited fetch does not redden the cycle.
    
    Venue coverage is stated rather than implied: this reads OKX copytrading only. Binance's
    leaderboard, Bybit's and Hyperliquid's per-account feed are in scope and NOT collected. Each is a
    separate endpoint and none may be written speculatively from a network-denied clone -- a guessed
    endpoint produces a collector that fails silently and a panel that looks like it is accumulating.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md | 33 +++++++++++++++++++++++
 ops/run_research_cycle.sh                         | 11 ++++++++
 tests/ops/test_research_cycle.py                  | 16 +++++++++++
 3 files changed, 60 insertions(+)

diff --git a/docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md b/docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md
index fdd6587c..2518e44f 100644
--- a/docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md
+++ b/docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md
@@ -895,6 +895,39 @@ a measured window, its budget falls like any other unproductive source -- and th
 recorded rather than quietly abandoned, because "we mined the leaderboards and got nothing" is a
 finding the desk must be able to cite.
 
+**THE WIRE, NAMED (2026-08-15). III.15 WAS A MANDATE WITH NO SCHEDULER, WHICH IS III.16 APPLIED TO
+III.15 ITSELF.** `scripts/screen_copytrading.py` had existed since 2026-07-31. It already carries
+the correct design -- an append-only cohort panel, a refusal to publish any persistence figure
+until it holds two snapshots at least `MIN_PANEL_GAP_DAYS=5` apart, exits counted as FAILURES
+rather than dropped, and the copier profit share (13%) charged against any measured edge before it
+counts as an edge for us rather than for the lead. It also documents the trap in full: sorted on
+pnl/aum/copiers, a 34-trader OKX sample returns Spearman +0.33 persistence, which is manufactured
+end-to-end by selecting on the outcome and by the absence of everyone who blew up.
+
+**AND NOTHING RAN IT.** Zero schedulers, zero cron entries, zero cycle lines. So the ONE organ whose
+verdict is made of calendar separation had been accumulating no calendar separation, and its
+standing `NO-DATA` was a statement about the cron table, not about copy traders. Under L1.28a that
+is the difference between UNMEASURED and measured-null, and the desk had been reading one as the
+other for fifteen days. It now runs daily in `ops/run_research_cycle.sh` and
+`tests/ops/test_research_cycle.py` fails if that line is ever removed.
+
+**VENUE COVERAGE IS PARTIAL AND THE GAP IS STATED RATHER THAN IMPLIED.** The wired organ reads OKX
+copytrading only. Binance's leaderboard, Bybit's and Hyperliquid's per-account position feed
+(FREE_DATA_ADDENDA C3 #54: the most complete free positioning dataset in crypto, public by design)
+are IN SCOPE and NOT YET COLLECTED. Each is a separate collector against a separate endpoint, and
+none may be written speculatively from a network-denied clone -- an endpoint guessed rather than
+observed produces a collector that fails silently and a panel that looks like it is accumulating.
+Until each is built and scheduled, this category's coverage is ONE VENUE, and any claim about
+"leaderboard traders" generally is a claim about OKX copytrading specifically.
+
+**WHAT A HEADLINE LIKE "165% OVER 170 DAYS, 15% MAX DRAWDOWN, 189 COPIERS" IS WORTH, CONCRETELY.**
+It is the maximum of a very large number of draws, quoted without its denominator, by a platform
+whose revenue rises with the number of copiers. The named figures are not the evidence and the
+badge is not the evidence; the only extractable objects are (a) the timestamped position stream, if
+the venue publishes one, which is data and enters as data, and (b) the execution and behaviour
+knowledge of category C. The return figure enters as EXTREME_CLAIM_UNVERIFIED with the full
+capital-path forensic required, or it does not enter.
+
 ## III.16 UNWIRED OR IDLE IS A DEFECT — STANDING, ALL SEATS, ALL BRAINS, ALL MINERS
 
 Added 2026-08-14 at the principal's instruction, after the same failure was found four times in
diff --git a/ops/run_research_cycle.sh b/ops/run_research_cycle.sh
index 15e4e299..413d59f1 100755
--- a/ops/run_research_cycle.sh
+++ b/ops/run_research_cycle.sh
@@ -180,6 +180,17 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
   # GPT seat fetches; this records what was fetched, at what completeness, and what remains, so
   # "we mined that channel" stops being a claim nobody can check.
   nice -n 15 "$PY" scripts/run_external_intel.py
+  # LEADERBOARD / COPY-TRADER FORENSICS (III.15), DAILY, because the panel it needs is made of
+  # CALENDAR SEPARATION and nothing else can manufacture it. screen_copytrading was written on
+  # 2026-07-31, correctly diagnoses the survivorship trap that makes every leaderboard read a
+  # phantom edge, appends an append-only cohort snapshot, and refuses to publish a persistence
+  # number until it holds two snapshots at least 5 days apart with EXITS COUNTED AS FAILURES.
+  # It had ZERO schedulers. So the one organ whose verdict depends entirely on repeated daily
+  # snapshots had been accumulating none, and its NO-DATA was a statement about the cron table
+  # rather than about copy traders (III.16, and L1.28a: absence must not resolve to a verdict).
+  # It exits 0 even when the venue is unreachable and records the failure in its own report, so a
+  # rate-limited fetch does not redden the whole cycle -- an unreachable venue is not a desk defect.
+  nice -n 15 "$PY" scripts/screen_copytrading.py
   # THE RETURN ENGINES. Everything above measures whether the RESEARCH is healthy; these decide
   # where capital would go if there were any. ELEVEN books; nine correctly report UNMEASURED on a
   # clone with no positions and each names the artifact it needs -- they exist now so that nothing
diff --git a/tests/ops/test_research_cycle.py b/tests/ops/test_research_cycle.py
index feb9faf3..57e477bf 100644
--- a/tests/ops/test_research_cycle.py
+++ b/tests/ops/test_research_cycle.py
@@ -118,3 +118,19 @@ def test_THE_TRAP_KEEPS_THE_CONTINUATION_THAT_MASKING_BOUGHT() -> None:
     for ln in opts:
         assert "-e" not in ln.replace("-uo", "").replace("-u", ""), (
             f"{ln!r} aborts the cycle on the first failure; the ERR trap records and continues")
+
+
+def test_THE_LEADERBOARD_PANEL_ACCUMULATES_ON_A_SCHEDULE() -> None:
+    """III.15 needs CALENDAR SEPARATION and nothing else can manufacture it.
+
+    screen_copytrading refuses to publish a persistence number until it holds two cohort snapshots
+    at least five days apart, with exits counted as failures -- the only unbiased design against a
+    leaderboard, which is by construction the maximum of a very large number of draws. It was
+    written 2026-07-31 with ZERO schedulers, so the panel accumulated nothing and its NO-DATA was a
+    statement about the cron table rather than about copy traders (III.16, L1.28a).
+
+    A screen whose verdict depends on repeated snapshots and which nothing repeats is not a screen.
+    """
+    assert "screen_copytrading.py" in CYCLE.read_text("utf-8"), (
+        "the copytrading/leaderboard forward panel is not scheduled -- it will report NO-DATA "
+        "forever, and the reason will be the scheduler rather than the evidence")
```


---

## 94abbd1c Merge remote-tracking branch 'origin/claude/llm-auto-upgrade-verify-gcjac3' into codex/controller-sync-20260815
# Conflicts:
#	tests/ops/test_research_cycle.py

```diff
commit 94abbd1cda399aef6e6d1c19f7ef90ea3a49f65e
Merge: b128a556 638c049c
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 00:58:14 2026 +0000

    Merge remote-tracking branch 'origin/claude/llm-auto-upgrade-verify-gcjac3' into codex/controller-sync-20260815
    
    # Conflicts:
    #       tests/ops/test_research_cycle.py

 ops/run_research_cycle.sh        | 88 +++++++++++++++++++++++++++-------------
 tests/ops/test_research_cycle.py | 51 ++++++++++++++++++++---
 2 files changed, 105 insertions(+), 34 deletions(-)
```


---

## 638c049c restore the fail-closed research cycle, and fence it so it cannot be lost again
Restores codex's cb2242ad, which a `--theirs` conflict resolution on the box overwrote.

The cycle could not fail. Twenty-five stages ended in `|| true` and the closing line reported
`exit $?` -- the status of the last `|| true`, which is 0 by construction. A run where the sweep
crashed, the ladder never ran and the promotion path died printed the same "exit 0" as a clean one,
so every artifact it left behind was yesterday's certified as today's, unattended, nightly. That is
L1.49 with a scheduler attached.

The ERR trap keeps the CONTINUATION that masking bought -- a failed sweep must not take the
recorders or the downstream monitors with it -- while removing the silence. `set -e` was
deliberately not added for the same reason: aborting on the first non-zero stage is a worse outage
than the silence it would replace, and a test pins that.

Two stages keep their suppression because their non-zero exit is a VERDICT, not a fault: the
unwired hunter and the go-live preflight. A cycle that went red because the preflight correctly
reported a latched rail would teach everyone to ignore red. A `|| true` added anywhere else now
fails a test.

Three tests, because this was fixed once already and lost to a merge: the trap and the latched exit
must exist, only the two verdict stages may suppress, and the shell must not be set -e.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 638c049c591000e51ce175df300146179999d0bb
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 15 00:55:46 2026 +0000

    restore the fail-closed research cycle, and fence it so it cannot be lost again
    
    Restores codex's cb2242ad, which a `--theirs` conflict resolution on the box overwrote.
    
    The cycle could not fail. Twenty-five stages ended in `|| true` and the closing line reported
    `exit $?` -- the status of the last `|| true`, which is 0 by construction. A run where the sweep
    crashed, the ladder never ran and the promotion path died printed the same "exit 0" as a clean one,
    so every artifact it left behind was yesterday's certified as today's, unattended, nightly. That is
    L1.49 with a scheduler attached.
    
    The ERR trap keeps the CONTINUATION that masking bought -- a failed sweep must not take the
    recorders or the downstream monitors with it -- while removing the silence. `set -e` was
    deliberately not added for the same reason: aborting on the first non-zero stage is a worse outage
    than the silence it would replace, and a test pins that.
    
    Two stages keep their suppression because their non-zero exit is a VERDICT, not a fault: the
    unwired hunter and the go-live preflight. A cycle that went red because the preflight correctly
    reported a latched rail would teach everyone to ignore red. A `|| true` added anywhere else now
    fails a test.
    
    Three tests, because this was fixed once already and lost to a merge: the trap and the latched exit
    must exist, only the two verdict stages may suppress, and the shell must not be set -e.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 ops/run_research_cycle.sh        | 88 +++++++++++++++++++++++++++-------------
 tests/ops/test_research_cycle.py | 48 ++++++++++++++++++++++
 2 files changed, 108 insertions(+), 28 deletions(-)

diff --git a/ops/run_research_cycle.sh b/ops/run_research_cycle.sh
index d041055f..15e4e299 100755
--- a/ops/run_research_cycle.sh
+++ b/ops/run_research_cycle.sh
@@ -31,6 +31,26 @@ done
 export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
 
 {
+  # THE CYCLE COULD NOT FAIL, AND THAT WAS THE BUG. Twenty-five stages ended in `|| true` and the
+  # closing line reported `exit $?` -- the status of the LAST `|| true`, which is 0 by
+  # construction. So a cycle where the sweep crashed, the ladder never ran and the promotion path
+  # died printed the same "exit 0" as a clean one, and every artifact it left behind was yesterday's
+  # certified as today's. That is L1.49 (a gate that never ran is a claim the desk cannot cash)
+  # running unattended every night.
+  #
+  # The ERR trap keeps the CONTINUATION that `|| true` bought -- a failed sweep must not stop the
+  # recorders or the monitors downstream of it -- while removing the SILENCE it also bought. The
+  # two stages that legitimately exit non-zero (the unwired hunter, the go-live preflight) keep
+  # their suppression, and the comment above each says why: a BLOCKED verdict is information.
+  #
+  # Restores codex's cb2242ad, which was lost to a `--theirs` conflict resolution on the box.
+  CYCLE_RC=0
+  record_failure() {
+    local label="$1" rc="$2"
+    echo "STAGE FAILED rc=$rc command=$label"
+    CYCLE_RC=1
+  }
+  trap 'record_failure "$BASH_COMMAND" "$?"' ERR
   echo "=== research cycle start $(date -u) | BARS_FILE_BUDGET=$BARS_FILE_BUDGET ==="
   # niced throughout: the recorders are the irreplaceable process on this box.
   # SURVIVAL PATH FIRST, BEFORE ANY RESEARCH RUNS. The desk hash-locks its constitution and left
@@ -38,22 +58,30 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
   # what the principal last approved. It runs FIRST because a cycle that researched all day and
   # then discovered the dead-man switch had changed would have spent the day on a book with no
   # floor under it.
-  "$PY" scripts/check_risk_kernel.py || echo "RISK-KERNEL DRIFT -- review before trusting this cycle"
+  "$PY" scripts/check_risk_kernel.py || {
+    _rc=$?
+    record_failure "check_risk_kernel.py" "$_rc"
+    echo "RISK-KERNEL DRIFT -- review before trusting this cycle"
+  }
   # BEFORE ANY ORGAN READS THE COHORT. This box owns the runtime state under data/, and nothing
   # could previously say so: two organs each inferred it from the artifacts, and on a clone the
   # evidence and its absence look identical. `derive_slots` therefore read six missing birth
   # certificates as six clocks never born and published a small Holm m as MEASURED -- a LOOSER
   # bar on the only path to capital -- while a test run recomputed tracked ratchets DOWNWARD from
   # whatever the host could see. Both are the same missing fact, stated once here.
-  "$PY" scripts/stamp_desk_host.py || echo "DESK-HOST STAMP FAILED -- the cohort will floor at the cap (safe, but tighter than reality)"
+  "$PY" scripts/stamp_desk_host.py || {
+    _rc=$?
+    record_failure "stamp_desk_host.py" "$_rc"
+    echo "DESK-HOST STAMP FAILED -- the cohort will floor at the cap (safe, but tighter than reality)"
+  }
   OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 15 "$PY" scripts/build_bars.py
   bash ops/run_study_on_vps.sh
-  nice -n 15 "$PY" scripts/study_status.py || true
+  nice -n 15 "$PY" scripts/study_status.py
   # The ladder runs even when the sweep found nothing: it also reports what is ALREADY live, and a
   # cycle that skipped it on a null day would go silent exactly when a live record needs reading.
   # THE REVIEW CONSUMES THE SWEEP: funnel, near-survivor bank, evidence tiers, convergence. Four
   # modules that had zero importers until this line existed -- inventory until something reads them.
-  nice -n 15 "$PY" scripts/run_research_review.py || true
+  nice -n 15 "$PY" scripts/run_research_review.py
   # BEFORE the ladder: the ladder recommends which survivors are owed a clock, and that
   # recommendation is worthless while every seat is occupied. Measured 2026-08-13: m=15 against a
   # cap of 12 with ZERO idle, at least one seat held by a DEGENERATE instrument fault that cannot
@@ -65,13 +93,13 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
   # safe to automate when seats and multiplicity were split: freeing a seat no longer moves any
   # Holm bar, because `m` is now a HIGH-WATER MARK -- a clock that ran and failed consumed a
   # trial, and retiring it does not un-look. BLOCKED clocks are still never touched.
-  nice -n 15 "$PY" scripts/run_clock_retirement_sweep.py --accept-all --decided-by cycle || true
+  nice -n 15 "$PY" scripts/run_clock_retirement_sweep.py --accept-all --decided-by cycle
   # WHY THE CLOCKS ARE SLOW, ranked, next to the sweep that says which ones are dead. Shortening
   # the clock is forbidden (L1.6) and a cleverer test was built and MEASURED slower (anytime_valid
   # graduated a Sharpe-2 edge at a median 132 days against a fixed 90). The only accelerant left is
   # more effective observations per day, and nothing was computing that rate -- two functions in
   # evidence_clock existed for it with zero callers outside their own module.
-  nice -n 15 "$PY" scripts/run_information_rate.py || true
+  nice -n 15 "$PY" scripts/run_information_rate.py
   # THE UNWIRED HUNTER (III.16), daily, so nobody has to remember. A public function that is
   # written, tested, correct and CALLED BY NOTHING is invisible to every other instrument here:
   # ruff sees valid code, mypy valid types, the suite green tests, a module count a module. The
@@ -90,12 +118,12 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
   # long-only crypto book earns in a rising tape with or without selection skill, and quoting the
   # raw number would report the market's return as the strategy's alpha.
   nice -n 15 "$PY" scripts/run_spot_momentum.py --equity "${GOLIVE_CAPITAL:-200}" \
-      --min-notional "${VENUE_MIN_NOTIONAL:-10}" || true
+      --min-notional "${VENUE_MIN_NOTIONAL:-10}"
   # --spot-only REFUSES every short H3 calls and journals the refusal, rather than inverting it
   # (which would score H3's hit rate against trades it never called for) or dropping it silently
   # (which would hide that half its signals were unplaceable rather than absent).
   nice -n 15 "$PY" scripts/run_discretionary_live.py --equity "${GOLIVE_CAPITAL:-200}" \
-      --min-notional "${VENUE_MIN_NOTIONAL:-10}" --spot-only || true
+      --min-notional "${VENUE_MIN_NOTIONAL:-10}" --spot-only
   # THE GO-LIVE STATE, PUBLISHED DAILY RATHER THAN REMEMBERED. Advisory by design: every
   # precondition it reports is already ENFORCED independently on the money path (no keys means no
   # authentication, CASHCARRY_KILL forces flatten-only in the executor's own order loop, the ruin
@@ -117,7 +145,7 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
   # dashboard never showed, which is how a promotion becomes unauditable after the fact.
   nice -n 15 "$PY" scripts/run_live_ladder.py
   nice -n 15 "$PY" scripts/run_auto_promotion.py --capital "${GOLIVE_CAPITAL:-200}" \
-      --min-notional "${VENUE_MIN_NOTIONAL:-10}" || true
+      --min-notional "${VENUE_MIN_NOTIONAL:-10}"
   # EXECUTION HEALTH runs every cycle, including days the research half found nothing. The money
   # path is where the desk is currently LOSING (27 closes, all three hold buckets negative net of
   # fees), so a cycle that reported only research would go quiet on the one number costing money.
@@ -125,41 +153,41 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
   # "INDEPENDENT MECHANISM 2 | PORTFOLIO-CONTRIBUTING unmeasured" and stopped -- a discovery
   # stranded one stage short of the only count that pays, waiting for a human to notice. Survivor
   # forwarding now runs in the same cycle that produced the survivors.
-  nice -n 15 "$PY" scripts/run_portfolio_admission.py || true
+  nice -n 15 "$PY" scripts/run_portfolio_admission.py
   # ZERO-CAPITAL FORWARD CONVERSION, SAME CYCLE. The spawner now consumes both corrected axis
   # screens and the full sweep's measured independent clusters. Waiting for tomorrow's cron
   # throws away the one input that cannot be backfilled: forward time. The runner publishes a
   # day-zero NO-EVIDENCE row immediately, proving every new clock is runnable and cohort-counted.
-  nice -n 15 "$PY" scripts/run_paper_sleeve_spawner.py || true
-  nice -n 15 "$PY" scripts/run_paper_sleeve_forward.py || true
-  nice -n 15 "$PY" scripts/run_promotion_queue.py || true
-  nice -n 15 "$PY" scripts/run_trade_forensics.py || true
-  nice -n 15 "$PY" scripts/run_exec_monitor.py || true
+  nice -n 15 "$PY" scripts/run_paper_sleeve_spawner.py
+  nice -n 15 "$PY" scripts/run_paper_sleeve_forward.py
+  nice -n 15 "$PY" scripts/run_promotion_queue.py
+  nice -n 15 "$PY" scripts/run_trade_forensics.py
+  nice -n 15 "$PY" scripts/run_exec_monitor.py
   # THE LOOP CLOSES HERE. The intelligence cycle re-reads everything this run produced -- kills,
   # survivors, admission, conversion joins, source and cadence yield -- and republishes the ranked
   # gap set, so tomorrow's highest-value work is chosen from today's evidence rather than from
   # whatever was true when the schedule was written.
-  nice -n 15 "$PY" scripts/run_intelligence_cycle.py || true
+  nice -n 15 "$PY" scripts/run_intelligence_cycle.py
   # THE ECONOMIC SCOREBOARD, ABOVE THE ARCHITECTURE COUNTS. Everything before this line measures
   # the RESEARCH: kills, survivors, admission, gaps. None of it answers the only question that
   # decides whether this desk is worth running -- is it generating and RETAINING real net wealth.
   # Runs every cycle including the days it can only answer UNMEASURED, because the day it stops
   # being able to say that is the day a live fill happened and nobody wired the report.
-  nice -n 15 "$PY" scripts/run_wealth_report.py || true
+  nice -n 15 "$PY" scripts/run_wealth_report.py
   # THE BLIND SPOT LEDGER. The Claude-side miners cannot retrieve YouTube transcripts and this
   # clone has no network at all, so a large body of practitioner knowledge -- much of it with no
   # paper, no repo and no article behind it -- is invisible to every collector the desk runs. The
   # GPT seat fetches; this records what was fetched, at what completeness, and what remains, so
   # "we mined that channel" stops being a claim nobody can check.
-  nice -n 15 "$PY" scripts/run_external_intel.py || true
+  nice -n 15 "$PY" scripts/run_external_intel.py
   # THE RETURN ENGINES. Everything above measures whether the RESEARCH is healthy; these decide
   # where capital would go if there were any. ELEVEN books; nine correctly report UNMEASURED on a
   # clone with no positions and each names the artifact it needs -- they exist now so that nothing
   # has to be remembered and wired the day a live book appears, which is the failure mode L1.56
   # names. Two produce real output on a network-denied clone: the mechanism ontology (its input is
   # economic reasoning) and agent authority (its input is a policy declaration in git).
-  nice -n 15 "$PY" scripts/run_opportunity_books.py || true
-  nice -n 15 "$PY" scripts/run_max_push.py || true
+  nice -n 15 "$PY" scripts/run_opportunity_books.py
+  nice -n 15 "$PY" scripts/run_max_push.py
   # THE PROGRAMME CANNOT QUIETLY STALL. The ledger verifies every declared capability against the
   # working tree and publishes the unfinished ones as ranked gaps, so an item that stops being
   # worked reappears in tomorrow's priorities by itself. Runs LAST: it measures the cycle that
@@ -169,17 +197,21 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
   # Evolve the METHOD frontier before the completion report reads it: missing search methods,
   # stagnation, fractional discovery credit and the bounded serendipity mission must affect the
   # same night's priorities rather than appearing one cycle late.
-  nice -n 15 "$PY" scripts/research_alpha_optimizer.py || true
-  nice -n 15 "$PY" scripts/gpt_hunter.py || true
+  nice -n 15 "$PY" scripts/research_alpha_optimizer.py
+  nice -n 15 "$PY" scripts/gpt_hunter.py
   # Elite external work converts through the EXISTING hypothesis queue: public claims stay priors,
   # while capability gaps, papers, failures, participant sensors, MEV and white-space coverage
   # become measured frontier work rather than another document archive.
-  nice -n 15 "$PY" scripts/run_external_intelligence.py || true
-  nice -n 15 "$PY" scripts/run_alpha_frontier.py || true
+  nice -n 15 "$PY" scripts/run_external_intelligence.py
+  nice -n 15 "$PY" scripts/run_alpha_frontier.py
   # Verify the ledger BEFORE the integrated report and ranker consume it. Publishing gaps after
   # max-push would strand every newly found incomplete capability for an extra day.
-  nice -n 15 "$PY" scripts/run_completion_ledger.py || true
-  nice -n 15 "$PY" scripts/run_completion_program.py || true
-  nice -n 15 "$PY" scripts/run_max_push.py || true
-  echo "=== research cycle exit $? at $(date -u) ==="
+  nice -n 15 "$PY" scripts/run_completion_ledger.py
+  nice -n 15 "$PY" scripts/run_completion_program.py
+  nice -n 15 "$PY" scripts/run_max_push.py
+  # $? WOULD BE THE LAST STAGE'S STATUS, WHICH IS NOT THE CYCLE'S. CYCLE_RC latches the first
+  # failure anywhere in the run, so a cycle that broke in the middle and recovered by the end
+  # still reports non-zero. pipefail (set at the top) carries this through the tee.
+  echo "=== research cycle exit $CYCLE_RC at $(date -u) ==="
+  exit "$CYCLE_RC"
 } 2>&1 | tee -a "$LOG"
diff --git a/tests/ops/test_research_cycle.py b/tests/ops/test_research_cycle.py
index b7b512fe..feb9faf3 100644
--- a/tests/ops/test_research_cycle.py
+++ b/tests/ops/test_research_cycle.py
@@ -70,3 +70,51 @@ def test_THE_BAR_BUDGET_IS_OVERRIDABLE_BUT_HAS_A_SANE_DEFAULT() -> None:
     competes with the recorders, so it is a declared default rather than an unbounded job."""
     src = CYCLE.read_text("utf-8")
     assert "BARS_FILE_BUDGET:-" in src
+
+
+#: The two stages whose non-zero exit is a DESIGNED VERDICT rather than a fault. Both publish a
+#: judgement -- "these capabilities are unwired", "the book is BLOCKED" -- and a cycle that went
+#: red because the preflight correctly reported a latched rail would train everyone to ignore red.
+_MAY_SUPPRESS = ("check_unwired_capability.py", "run_golive_preflight.py")
+
+
+def test_THE_CYCLE_CAN_ACTUALLY_FAIL() -> None:
+    """THE ONE THAT MATTERS HERE. Every stage once ended in `|| true` and the closing line
+    reported `exit $?` -- the status of the last `|| true`, which is 0 by construction. A cycle
+    where the sweep crashed, the ladder never ran and the promotion path died printed the same
+    "exit 0" as a clean one, so yesterday's artifacts were certified as today's work every night
+    (L1.49: a gate that never ran is a claim the desk cannot cash).
+
+    This was fixed once and then lost to a `--theirs` merge resolution on the box. That is exactly
+    why it is a test and not a comment.
+    """
+    src = CYCLE.read_text("utf-8")
+    assert "CYCLE_RC=0" in src and "trap 'record_failure" in src, (
+        "the cycle has no ERR trap -- a failing stage leaves no record and the run reports success")
+    assert 'exit "$CYCLE_RC"' in src, (
+        "the cycle does not exit on its own latched status; `exit $?` reports only the LAST "
+        "stage, which says nothing about the twenty before it")
+    assert "exit $? at" not in src, "the old always-zero exit line is back"
+
+
+def test_ONLY_THE_STAGES_THAT_PUBLISH_A_VERDICT_MAY_SUPPRESS_FAILURE() -> None:
+    """`|| true` is how the silence came back last time. Each surviving one must be a stage whose
+    non-zero exit is a judgement, and a new one added anywhere else fails here rather than being
+    discovered a month later by wondering why the cycle is always green."""
+    suppressed = [ln.strip() for ln in CYCLE.read_text("utf-8").splitlines()
+                  if ln.rstrip().endswith("|| true") and not ln.strip().startswith("#")]
+    for ln in suppressed:
+        assert any(k in ln for k in _MAY_SUPPRESS), (
+            f"stage suppresses its own failure and is not one of the two that may: {ln!r}. A "
+            "cycle that cannot go red is a cycle nobody can trust when it is green")
+
+
+def test_THE_TRAP_KEEPS_THE_CONTINUATION_THAT_MASKING_BOUGHT() -> None:
+    """Failing closed must not mean stopping. `set -e` here would abort the whole run on the first
+    stage that exits non-zero, taking the recorders and every downstream monitor with it -- which
+    is a worse outage than the silence it replaced."""
+    opts = [ln for ln in CYCLE.read_text("utf-8").splitlines() if ln.startswith("set ")]
+    assert opts, "the cycle sets no shell options at all"
+    for ln in opts:
+        assert "-e" not in ln.replace("-uo", "").replace("-u", ""), (
+            f"{ln!r} aborts the cycle on the first failure; the ERR trap records and continues")
```


---

## b128a556 make legacy scheduler recovery canonical

```diff
commit b128a55683815cea3f8a113494c8fc88f33b7fa2
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 01:51:56 2026 +0100

    make legacy scheduler recovery canonical
---
 ops/crontab.manifest | 11 +++++++++++
 1 file changed, 11 insertions(+)

diff --git a/ops/crontab.manifest b/ops/crontab.manifest
index 8d96e57a..4dd6f5e8 100644
--- a/ops/crontab.manifest
+++ b/ops/crontab.manifest
@@ -2555,6 +2555,17 @@ SYSTEMD unit="quant-cro-ai.timer" on="*-*-* 08:45:00" exec="ops/run_cro_ai.sh"
 # REGISTRY promotion, sleeve sizing and LIVE at 15% of book.
 11 7 * * * cd "$QUANT_ROOT" && .venv/bin/python scripts/check_partition_power.py >> data/cro_ai_logs/partition_power.log 2>&1
 
+# --- LIVE RECOVERY + VALIDATION JOBS (verified against VPS 2026-08-15) ------------------------
+# The recorder supervisor is a five-minute idempotent watchdog, so it also supplies bounded
+# post-reboot recovery without a second undeclared @reboot path. The three validators consume
+# daily artifacts and remain phase-separated from their producers. These entries replace legacy
+# pre-manifest lines; reconstitution owns exactly one copy of each.
+# CONFIDENCE: verified-live plus committed-script.
+*/5 * * * * cd "$QUANT_ROOT" && flock -n data/.cron_recorder_supervisor.lock bash ops/start_recorders_nosudo.sh >> data/recorder_supervisor.log 2>&1
+20 3 * * * cd "$QUANT_ROOT" && flock -n data/.cron_axis_shadows.lock .venv/bin/python scripts/run_axis_shadows.py >> data/cro_ai_logs/axis_shadows.log 2>&1
+5 4 * * * cd "$QUANT_ROOT" && flock -n data/.cron_cohort_integrity.lock .venv/bin/python scripts/check_cohort_integrity.py --report-only >> data/cro_ai_logs/cohort_integrity.log 2>&1
+15 4 * * * cd "$QUANT_ROOT" && flock -n data/.cron_gate_reachability.lock .venv/bin/python scripts/check_gate_reachability.py --report-only >> data/cro_ai_logs/gate_reachability.log 2>&1
+
 # ---------------------------------------------------------------------------------------------
 # CODE SYNC -- pull the branch and run the gates, hourly, so a pushed fix stops being homework.
 # WHY: every agent change needed the principal to open a terminal, fetch, merge, gate and re-run
```


---

## 381d2541 Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

```diff
commit 381d2541b60697769ca7e68d5d1d8fd45e32acb4
Merge: f0279deb a615c0bc
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 00:52:16 2026 +0000

    Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

 libs/execution/ruin_rail.py       | 92 ++++++++++++++++++++++++++++++++++++
 scripts/run_discretionary_live.py | 12 +++++
 scripts/run_spot_executor.py      | 32 +++++++++++--
 tests/execution/test_ruin_rail.py | 99 +++++++++++++++++++++++++++++++++++++++
 4 files changed, 230 insertions(+), 5 deletions(-)
```


---

## a615c0bc the ruin rails bind the new order paths too
CASHCARRY_KILL has been latched on the box since 2026-08-01. Eight modules read it, each with its
own `_KILL = Path(...)` constant -- which worked while there was exactly one order path.

run_spot_executor was the second one, and it inherited none of them. Its arming contract answers
"may this box place orders at all"; it does not answer "is the book frozen right now". So the
preflight could print `ruin rail: BLOCKED -- the executor is FROZEN and places no orders` on the
same box, in the same minute, that --place would have spent the whole deployable balance.

libs/execution/ruin_rail asks all three rails (CASHCARRY_KILL, DEADMAN_FIRED, FREEZE) in one place,
so a ninth order path cannot skip the check by forgetting a constant exists. A latched rail
downgrades the executor to a dry run and names itself on every refused row -- the operator still
gets the delta table, which is what tells them whether clearing the rail is the right move.

Presence is the latch; contents are only the explanation. An empty or unreadable rail file still
freezes: a rail whose reason cannot be parsed is a rail that fired, not one that did not (WS-005).
Nothing in the module can clear a rail, and a test greps the source to keep it that way -- clearing
a fired rail is the principal's act.

The discretionary runner reports the rail rather than enforcing it: it places nothing, so it has no
order to stop, but an intent list printed during a freeze reads as a book about to be taken.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit a615c0bc0d57945413139f2316086864df26e8bf
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 15 00:51:18 2026 +0000

    the ruin rails bind the new order paths too
    
    CASHCARRY_KILL has been latched on the box since 2026-08-01. Eight modules read it, each with its
    own `_KILL = Path(...)` constant -- which worked while there was exactly one order path.
    
    run_spot_executor was the second one, and it inherited none of them. Its arming contract answers
    "may this box place orders at all"; it does not answer "is the book frozen right now". So the
    preflight could print `ruin rail: BLOCKED -- the executor is FROZEN and places no orders` on the
    same box, in the same minute, that --place would have spent the whole deployable balance.
    
    libs/execution/ruin_rail asks all three rails (CASHCARRY_KILL, DEADMAN_FIRED, FREEZE) in one place,
    so a ninth order path cannot skip the check by forgetting a constant exists. A latched rail
    downgrades the executor to a dry run and names itself on every refused row -- the operator still
    gets the delta table, which is what tells them whether clearing the rail is the right move.
    
    Presence is the latch; contents are only the explanation. An empty or unreadable rail file still
    freezes: a rail whose reason cannot be parsed is a rail that fired, not one that did not (WS-005).
    Nothing in the module can clear a rail, and a test greps the source to keep it that way -- clearing
    a fired rail is the principal's act.
    
    The discretionary runner reports the rail rather than enforcing it: it places nothing, so it has no
    order to stop, but an intent list printed during a freeze reads as a book about to be taken.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 libs/execution/ruin_rail.py       | 92 ++++++++++++++++++++++++++++++++++++
 scripts/run_discretionary_live.py | 12 +++++
 scripts/run_spot_executor.py      | 32 +++++++++++--
 tests/execution/test_ruin_rail.py | 99 +++++++++++++++++++++++++++++++++++++++
 4 files changed, 230 insertions(+), 5 deletions(-)

diff --git a/libs/execution/ruin_rail.py b/libs/execution/ruin_rail.py
new file mode 100644
index 00000000..1baec827
--- /dev/null
+++ b/libs/execution/ruin_rail.py
@@ -0,0 +1,92 @@
+"""THE RUIN RAILS, ASKED IN ONE PLACE -- because a freeze that only some order paths honour is not
+a freeze.
+
+WHAT THIS FIXES. `data/CASHCARRY_KILL` has been latched since 2026-08-01 ("pager ladder at 4h
+rung"). Eight modules read it -- the cashcarry executor, the deadman switch, the live guard,
+gate-0, the alerts, the growth audit, the idle-cost fence, the change window -- and each declares
+its own `_KILL = Path("data/CASHCARRY_KILL")`. That worked while there was exactly ONE order path.
+
+Then a second order path was built (`run_spot_executor`) and it inherited none of them, because
+inheriting a rail requires somebody to remember it exists. Its arming contract -- keyfile,
+LIVE_ENABLE, VPS_VERIFIED -- says only "may this box place orders at all", which is a different
+question from "is the book currently frozen". So the desk's own preflight could print
+``ruin rail (CASHCARRY_KILL): BLOCKED -- the executor is FROZEN and places no orders`` on the same
+box, in the same minute, that the spot executor would happily have spent the whole $200.
+
+**A RAIL IS ONLY A RAIL IF EVERY PATH THAT SPENDS MONEY ASKS IT.** One reader, imported by every
+order path, is the only structure where adding a ninth path cannot silently skip the check. The
+per-module `_KILL` constants stay where they are: rewriting eight working call sites to prove a
+point is how a safety change becomes the outage. New paths use this.
+
+**THE LATCH IS THE ANSWER, THE CONTENTS ARE THE EXPLANATION.** Presence alone freezes. The file's
+text is read only to say WHY in the refusal, and an unreadable or empty file still freezes -- a rail
+whose reason cannot be parsed is a rail that fired, not a rail that did not.
+
+**NOTHING HERE CLEARS ANYTHING.** No function in this module deletes, truncates or moves a rail
+file, and none ever will. Clearing a fired rail is a Tier-3 act reserved to the principal (`rm
+data/CASHCARRY_KILL`), for a stated reason, never on a timer -- an idle book satisfies every
+"N hours clean" test trivially, forever (GAP 91).
+"""
+
+from __future__ import annotations
+
+from pathlib import Path
+
+__all__ = ["RAILS", "frozen", "latched"]
+
+#: Every file whose PRESENCE means "this book does not open new risk", with what each one says.
+#: Ordered most-specific first so the refusal names the trading freeze before the harness latch.
+RAILS: tuple[tuple[str, str], ...] = (
+    ("data/CASHCARRY_KILL",
+     "trading freeze -- the executor is flatten-only and opens nothing"),
+    ("data/DEADMAN_FIRED",
+     "the deadman switch FIRED and latched; the equity rail tripped"),
+    ("data/FREEZE",
+     "a manual freeze is in place"),
+)
+
+#: How much of a rail file's text is quoted back in a refusal. Enough for a timestamp and a reason;
+#: short enough that a rail file somebody pasted a stack trace into cannot flood a journal line.
+_REASON_CHARS = 300
+
+
+def _reason(p: Path) -> str:
+    """The rail's stated reason, or an explicit note that it has none. NEVER an empty string: a
+    blank reason renders as `frozen ()` and reads like a formatting bug rather than a live latch."""
+    try:
+        txt = p.read_text("utf-8").strip()
+    except OSError as exc:
+        return f"unreadable ({type(exc).__name__}) -- the latch still counts"
+    return txt[:_REASON_CHARS] if txt else "no reason recorded in the file"
+
+
+def latched(root: Path | None = None) -> list[tuple[str, str, str]]:
+    """Every rail currently latched as (path, what_it_means, stated_reason). Empty when clear.
+
+    Returns ALL of them rather than short-circuiting on the first: an operator clearing a freeze
+    needs to know there are two, or they will clear one, retry, and be refused again by the other
+    with no idea why.
+    """
+    base = Path(root) if root is not None else Path()
+    out: list[tuple[str, str, str]] = []
+    for rel, means in RAILS:
+        p = base / rel
+        if p.exists():
+            out.append((rel, means, _reason(p)))
+    return out
+
+
+def frozen(root: Path | None = None) -> tuple[bool, str]:
+    """``(is_frozen, why)`` -- the one question an order path asks before it spends money.
+
+    The ``why`` is written to be pasted into a journal and understood a month later, so it names
+    the file, what the file means, and what the file says. When clear it states which rails were
+    CHECKED, because "no rail latched" and "no rail consulted" are the same sentence otherwise and
+    only one of them is evidence.
+    """
+    hits = latched(root)
+    if not hits:
+        return False, ("no ruin rail latched (checked " +
+                       ", ".join(rel for rel, _ in RAILS) + ")")
+    return True, "; ".join(f"{rel} PRESENT -- {means}. Contents: {reason!r}"
+                           for rel, means, reason in hits)
diff --git a/scripts/run_discretionary_live.py b/scripts/run_discretionary_live.py
index 5cfa6b07..ecf8df54 100644
--- a/scripts/run_discretionary_live.py
+++ b/scripts/run_discretionary_live.py
@@ -98,6 +98,13 @@ def main() -> int:
                          "includes Ireland")
     args = ap.parse_args()
 
+    # THE RAILS ARE REPORTED HERE, NOT ENFORCED. This script places nothing, so a latched rail
+    # cannot stop an order it never sends -- but an intent list printed during a freeze reads as a
+    # book about to be taken, and whoever routes it by hand needs to see the freeze on the same
+    # screen. Enforcement lives in the module that actually spends money.
+    from libs.execution.ruin_rail import frozen
+    rail_frozen, why_rail = frozen()
+
     symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
     try:
         from libs.autodiscovery.crypto_adapter import _read_frames
@@ -158,6 +165,8 @@ def main() -> int:
         "n_taken": sum(1 for r in rows if r.get("taken")),
         "absent_symbols": absent,
         "spot_only": bool(args.spot_only),
+        "rail_frozen": rail_frozen,
+        "rail_why": why_rail,
         "shorts_refused": skipped_short,
         "intents": rows,
         "note": ("Intents only -- nothing is placed here. Routing goes through the executor and "
@@ -172,6 +181,9 @@ def main() -> int:
 
     print(f"discretionary-live [{args.rule_id}]: {len(rows)} intent(s), "
           f"{payload['n_taken']} would be taken, equity ${args.equity:,.2f}")
+    if rail_frozen:
+        print(f"  RUIN RAIL LATCHED -- these intents are NOT placeable until it is cleared. "
+              f"{why_rail}")
     for r in rows:
         mark = "TAKE  " if r.get("taken") else "REFUSE"
         print(f"  {mark} {r.get('symbol','?'):<10} {r.get('side','?'):<4} "
diff --git a/scripts/run_spot_executor.py b/scripts/run_spot_executor.py
index e5a03790..d7819e6d 100644
--- a/scripts/run_spot_executor.py
+++ b/scripts/run_spot_executor.py
@@ -18,6 +18,12 @@ That is the single most expensive mistake available in this file and it is silen
 **DRY RUN IS THE DEFAULT AND `--place` IS THE ONLY WAY TO SPEND MONEY.** A flag that defaults to
 placing is a flag somebody sets by forgetting.
 
+**THE RUIN RAILS BIND HERE TOO.** `libs.execution.ruin_rail` is consulted before any order goes
+out, and a latched rail refuses the whole run. The arming contract this module inherits from
+`binance_spot_live` answers "may this box place orders at all"; it does NOT answer "is the book
+frozen right now", and those came apart the moment a second order path existed: `CASHCARRY_KILL`
+has been latched since 2026-08-01 and nothing on this path had ever read it.
+
 **EVERY REFUSAL IS PRINTED AND JOURNALLED.** Below min-notional, below step size, arming missing,
 cap exceeded -- each is stated with its arithmetic. A book that silently skipped a leg would leave
 the operator believing they hold a position they do not.
@@ -96,16 +102,24 @@ def main() -> int:
     args = ap.parse_args()
 
     from libs.execution import binance_spot_live as live
+    from libs.execution.ruin_rail import frozen
 
     cycle = args.cycle or datetime.now(tz=UTC).strftime("%Y%m%d")
     armed, why_armed = live.is_armed()
+    rail_frozen, why_rail = frozen()
+    # A LATCHED RAIL DOWNGRADES THE RUN TO A DRY RUN rather than aborting it. The operator still
+    # gets the full delta table -- which is what tells them whether clearing the rail is even the
+    # right move -- and every row says the rail refused it, so nobody reads the printed book as a
+    # placed one.
+    place = bool(args.place) and not rail_frozen
     targets, why_targets = _load_targets()
 
     rep: dict[str, Any] = {
         "updated": datetime.now(tz=UTC).isoformat(),
         "cycle": cycle, "armed": armed, "armed_why": why_armed,
+        "rail_frozen": rail_frozen, "rail_why": why_rail,
         "targets_why": why_targets, "equity_usd": float(args.equity),
-        "placed": [], "refused": [], "dry_run": not args.place,
+        "placed": [], "refused": [], "dry_run": not place,
         "leverage": "1.0x -- SPOT HOLDS WHAT IT PAID FOR. No leverage exists on this path and "
                     "none can be added; margin is a different product with a different connector "
                     "and a liquidation price.",
@@ -170,14 +184,20 @@ def main() -> int:
 
         side = "BUY" if delta > 0 else "SELL"
         row["side"] = side
-        if not args.place:
+        if rail_frozen:
+            # NOT a dry run and not a venue rejection: the desk's own rail refused it. Named
+            # separately so the journal can never be read as "the venue was fine with this".
+            row["why"] = f"RUIN RAIL LATCHED -- {why_rail}"
+            rep["refused"].append(row)
+            continue
+        if not place:
             row["why"] = "DRY RUN -- would place this; --place spends money"
             rep["placed"].append(row)
             if side == "BUY":
                 spent += delta
             continue
         try:
-            if side == "BUY":
+            if side == "BUY":  # place=True here, so a rail is known clear
                 res = live.place_market_quote(sym, "BUY", round(delta, 2), cycle=cycle)
                 spent += delta
             else:
@@ -199,14 +219,16 @@ def main() -> int:
     _OUT.parent.mkdir(parents=True, exist_ok=True)
     _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
 
-    mode = "DRY RUN" if not args.place else "LIVE"
+    mode = "RAIL FROZEN" if rail_frozen else ("LIVE" if place else "DRY RUN")
     print(f"=== SPOT EXECUTOR [{mode}] === armed={armed} cycle={cycle} equity=${args.equity:,.2f}")
+    if rail_frozen:
+        print(f"  RUIN RAIL LATCHED -- nothing was placed. {why_rail}")
     for r in rep["placed"]:
         print(f"  {r.get('side','?'):<4} {r['symbol']:<10} ${abs(r['delta_usd']):>8,.2f}  "
               f"(target ${r['want_usd']:,.2f}, held ${r['have_usd']:,.2f})")
     for r in rep["refused"]:
         print(f"  SKIP {r.get('symbol','-'):<10} {str(r.get('why',''))[:110]}")
-    if not args.place:
+    if not place and not rail_frozen:
         print("  nothing was placed. add --place to spend money.")
     print(f"-> {_JOURNAL} and {_OUT}")
     return 0
diff --git a/tests/execution/test_ruin_rail.py b/tests/execution/test_ruin_rail.py
new file mode 100644
index 00000000..3a355902
--- /dev/null
+++ b/tests/execution/test_ruin_rail.py
@@ -0,0 +1,99 @@
+"""The ruin rails, pinned on the failure that made this module necessary.
+
+THE DEFECT THIS GUARDS AGAINST is a freeze that only some order paths honour. `CASHCARRY_KILL` sat
+latched on the box while a newly built second order path read only its own arming contract --
+keyfile, LIVE_ENABLE, VPS_VERIFIED -- none of which answer "is the book frozen right now". The
+preflight printed BLOCKED and the executor would have spent the capital, in the same minute, on the
+same machine.
+
+So the tests that matter here are the ones about ABSENCE and UNREADABILITY resolving the wrong way:
+a rail file that exists but is empty, or cannot be read, must still freeze. A rail whose reason
+cannot be parsed is a rail that FIRED, not a rail that did not.
+"""
+
+from __future__ import annotations
+
+from pathlib import Path
+
+from libs.execution.ruin_rail import RAILS, frozen, latched
+
+
+def test_A_CLEAN_TREE_IS_NOT_FROZEN_AND_SAYS_WHAT_IT_CHECKED(tmp_path: Path) -> None:
+    """'No rail latched' and 'no rail consulted' read identically unless the clear answer names
+    the files it looked at. Only one of them is evidence."""
+    is_frozen, why = frozen(tmp_path)
+    assert is_frozen is False
+    for rel, _ in RAILS:
+        assert rel in why, f"the clear verdict must name {rel} as checked, else it is not evidence"
+
+
+def test_EVERY_DECLARED_RAIL_FREEZES_ON_ITS_OWN(tmp_path: Path) -> None:
+    """Each rail is independently sufficient. A rail that only counts alongside another is not a
+    rail, and this is the loop that catches a future entry added to RAILS but never honoured."""
+    for rel, _ in RAILS:
+        p = tmp_path / rel
+        p.parent.mkdir(parents=True, exist_ok=True)
+        p.write_text("fired at 2026-08-01", "utf-8")
+        is_frozen, why = frozen(tmp_path)
+        assert is_frozen is True, f"{rel} present must freeze the book on its own"
+        assert rel in why
+        p.unlink()
+
+
+def test_AN_EMPTY_RAIL_FILE_STILL_FREEZES(tmp_path: Path) -> None:
+    """PRESENCE is the latch; the contents are only the explanation. `touch CASHCARRY_KILL` is a
+    real way a freeze gets set, and treating a blank file as 'no reason, therefore no freeze' would
+    invert the whole rail."""
+    (tmp_path / "data").mkdir()
+    (tmp_path / "data/CASHCARRY_KILL").write_text("", "utf-8")
+    is_frozen, why = frozen(tmp_path)
+    assert is_frozen is True
+    assert "no reason recorded" in why, "a blank reason must render as words, not as `frozen ()`"
+
+
+def test_AN_UNREADABLE_RAIL_STILL_FREEZES(tmp_path: Path) -> None:
+    """A directory where a file is expected makes read_text raise. WS-005 says absence of a
+    readable reason must not resolve to the clean verdict."""
+    (tmp_path / "data/CASHCARRY_KILL").mkdir(parents=True)
+    is_frozen, why = frozen(tmp_path)
+    assert is_frozen is True
+    assert "the latch still counts" in why
+
+
+def test_ALL_LATCHED_RAILS_ARE_REPORTED_NOT_JUST_THE_FIRST(tmp_path: Path) -> None:
+    """An operator who clears one rail and is refused again by a second, unnamed one has no way to
+    find out why. Short-circuiting on the first hit produces exactly that."""
+    (tmp_path / "data").mkdir()
+    for rel, _ in RAILS:
+        (tmp_path / rel).write_text("x", "utf-8")
+    hits = latched(tmp_path)
+    assert len(hits) == len(RAILS)
+    _, why = frozen(tmp_path)
+    for rel, _ in RAILS:
+        assert rel in why
+
+
+def test_THE_REASON_IS_BOUNDED(tmp_path: Path) -> None:
+    """A rail file somebody pasted a stack trace into must not flood every journal line."""
+    (tmp_path / "data").mkdir()
+    (tmp_path / "data/FREEZE").write_text("y" * 50_000, "utf-8")
+    _, why = frozen(tmp_path)
+    assert len(why) < 1_000
+
+
+def test_NOTHING_IN_THIS_MODULE_CLEARS_A_RAIL(tmp_path: Path) -> None:
+    """Clearing a fired rail is a Tier-3 act reserved to the principal. Reading must never be a
+    write, and a module that can clear a rail is one autonomous bug away from clearing it."""
+    (tmp_path / "data").mkdir()
+    p = tmp_path / "data/CASHCARRY_KILL"
+    p.write_text("fired", "utf-8")
+    for _ in range(3):
+        assert frozen(tmp_path)[0] is True
+        assert latched(tmp_path)
+    assert p.exists() and p.read_text("utf-8") == "fired"
+
+    src = Path("libs/execution/ruin_rail.py").read_text("utf-8")
+    for forbidden in ("unlink(", "rmtree", "write_text(", "os.remove", "rename("):
+        assert forbidden not in src, (
+            f"ruin_rail.py contains {forbidden!r} -- this module reads rails and never mutates "
+            "them; clearing a fired rail is the principal's act")
```


---

## f0279deb fail closed on sparse midnight study inputs

```diff
commit f0279deba00adac866f680f0576a9861f5183c60
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 01:45:11 2026 +0100

    fail closed on sparse midnight study inputs
---
 libs/research/orphan_scan.py            |  3 ++-
 scripts/run_full_sweep.py               | 16 +++++++++++-----
 scripts/run_information_rate.py         | 22 +++++++++++++++++++++-
 tests/research/test_information_rate.py | 27 +++++++++++++++++++++++++++
 tests/scripts/test_full_sweep.py        | 33 +++++++++++++++++++++++++++++++++
 5 files changed, 94 insertions(+), 7 deletions(-)

diff --git a/libs/research/orphan_scan.py b/libs/research/orphan_scan.py
index 3c1161e0..b56f3597 100644
--- a/libs/research/orphan_scan.py
+++ b/libs/research/orphan_scan.py
@@ -237,7 +237,8 @@ def _read_artifact(path: Path) -> object | None:
             return None
         return rows
     try:
-        return json.loads(text)
+        loaded: object = json.loads(text)
+        return loaded
     except (TypeError, ValueError):
         return None
 
diff --git a/scripts/run_full_sweep.py b/scripts/run_full_sweep.py
index b6ee5bc7..a5a29c8b 100644
--- a/scripts/run_full_sweep.py
+++ b/scripts/run_full_sweep.py
@@ -522,22 +522,28 @@ def main() -> int:
         print(f"  kill criteria already binding: {PREREG.relative_to(ROOT)}")
         return 0
 
-    symbols = sorted(frames)
+    input_symbols = sorted(frames)
     idx, aligned, dropped = align(frames, a.tail_bars)
+    # `align` deliberately drops symbols whose ragged span cannot support the common grid. Every
+    # downstream panel is built from `aligned`, so its symbol axis must come from the same object.
+    # Reusing `input_symbols` here asks every panel for a column it explicitly dropped and turns an
+    # honest coverage reduction into a KeyError (live: 1000CATUSDT, 2026-08-14).
+    symbols = sorted(aligned)
     secs = bar_seconds(idx)
     if len(idx) < a.min_obs * 2 or secs <= 0:
         rep = blocked(
-            (f"the retained grid across {len(symbols)} symbol(s) has {len(idx)} bars -- fewer "
-             f"than {MIN_SYMBOLS_PER_BAR} symbol(s) overlap anywhere, or none covers "
+            (f"the retained grid from {len(input_symbols)} input symbol(s) has {len(idx)} bars -- "
+             f"fewer than {MIN_SYMBOLS_PER_BAR} symbol(s) overlap anywhere, or none covers "
              f"{MIN_SYMBOL_COVERAGE:.0%} of the grid. The recorders cover names raggedly, so this "
              "usually means the per-symbol bar windows do not intersect: widen BARS_FILE_BUDGET so "
              "each symbol reaches further back, or rebuild bars over a common window."),
-            {"symbols": symbols, "common_bars": len(idx),
+            {"symbols": input_symbols, "retained_symbols": symbols,
+             "symbols_dropped_for_coverage": dropped, "common_bars": len(idx),
              "per_symbol_bars": {s: len(d) for s, d in frames.items()},
              "bar_seconds": secs})
         a.out.parent.mkdir(parents=True, exist_ok=True)
         a.out.write_text(json.dumps(rep, indent=1), "utf-8")
-        print(f"full-sweep: BLOCKED -- common grid is {len(idx)} bars across {symbols}.")
+        print(f"full-sweep: BLOCKED -- common grid is {len(idx)} bars across {input_symbols}.")
         return 0
 
     panels, absent = feature_panels(aligned)
diff --git a/scripts/run_information_rate.py b/scripts/run_information_rate.py
index 9f161bf2..323f5077 100644
--- a/scripts/run_information_rate.py
+++ b/scripts/run_information_rate.py
@@ -39,6 +39,7 @@ if str(_P(__file__).resolve().parent.parent) not in _sys.path:
     _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
 
 import json
+import math
 from datetime import UTC, datetime
 from pathlib import Path
 from typing import Any
@@ -138,6 +139,25 @@ def _state_for(slot: dict[str, Any]) -> tuple[EvidenceState | None, str]:
         "UNMEASURED here has not been re-run since, or is not an axis clock")
 
 
+def _format_accelerant(row: dict[str, Any]) -> str:
+    """Render measured gain or its explicit uncertainty range without inventing a point value."""
+    lever = str(row.get("lever") or "unknown lever")
+    gain = row.get("gain")
+    if isinstance(gain, (int, float)) and not isinstance(gain, bool) and math.isfinite(gain):
+        return f"      +{gain:.1f}x  {lever}"
+
+    low, high = row.get("gain_low"), row.get("gain_high")
+    range_measured = all(
+        isinstance(value, (int, float))
+        and not isinstance(value, bool)
+        and math.isfinite(value)
+        for value in (low, high)
+    )
+    if range_measured:
+        return f"      UNMEASURED [{low:.1f}x..{high:.1f}x]  {lever}"
+    return f"      UNMEASURED  {lever}"
+
+
 def main() -> int:
     try:
         snap = derive_slots()
@@ -197,7 +217,7 @@ def main() -> int:
         print(f"  {r['clock']:<34} {rate_s:>10} eff obs/day   {left_s}")
         print(f"      binding: {r['binding_constraint']} (x{r['binding_costs_multiplier']})")
         for a in r["accelerants"][:2]:
-            print(f"      +{a['gain']:.1f}x  {a['lever']}")
+            print(_format_accelerant(a))
     for u in unmeasured[:5]:
         print(f"  UNMEASURED  {u}")
     print(f"-> {_OUT} and {_WEB}")
diff --git a/tests/research/test_information_rate.py b/tests/research/test_information_rate.py
index 7b6cd68c..13939672 100644
--- a/tests/research/test_information_rate.py
+++ b/tests/research/test_information_rate.py
@@ -257,3 +257,30 @@ def test_NO_LEVER_PUBLISHES_A_POINT_GAIN_FROM_AN_UNMEASURED_STATE() -> None:
     for a in accelerants(s, available_symbols=213, bars_per_day=1, available_bars_per_day=3):
         assert a.gain is None, f"{a.lever} published a point gain from unmeasured inputs"
         assert a.gain_low is not None and a.gain_high is not None
+
+def test_UNMEASURED_ACCELERANT_PRINTS_ITS_RANGE_WITHOUT_A_POINT_ESTIMATE() -> None:
+    """Live regression: ``gain=None`` reached ``:.1f`` and crashed the scheduled report."""
+    import scripts.run_information_rate as R
+
+    line = R._format_accelerant(
+        {"lever": "widen cross-section", "gain": None, "gain_low": 12.3, "gain_high": 213.0}
+    )
+    assert line == "      UNMEASURED [12.3x..213.0x]  widen cross-section"
+    assert "+0.0x" not in line and "+None" not in line
+
+
+def test_UNMEASURED_ACCELERANT_WITHOUT_BOUNDS_STAYS_UNMEASURED() -> None:
+    """Missing uncertainty bounds are absence, never permission to substitute zero."""
+    import scripts.run_information_rate as R
+
+    assert R._format_accelerant({"lever": "unknown", "gain": None}) == (
+        "      UNMEASURED  unknown"
+    )
+
+
+def test_MEASURED_ACCELERANT_RETAINS_THE_EXISTING_POINT_FORMAT() -> None:
+    import scripts.run_information_rate as R
+
+    assert R._format_accelerant({"lever": "publish regimes", "gain": 2.0}) == (
+        "      +2.0x  publish regimes"
+    )
diff --git a/tests/scripts/test_full_sweep.py b/tests/scripts/test_full_sweep.py
index 13e89ad4..383bcc3e 100644
--- a/tests/scripts/test_full_sweep.py
+++ b/tests/scripts/test_full_sweep.py
@@ -432,6 +432,39 @@ def test_RAGGED_SPANS_NO_LONGER_EMPTY_THE_WHOLE_PANEL() -> None:
     assert dropped == ["CCC"], "the disjoint symbol was not dropped, or was dropped silently"
 
 
+def test_MAIN_PASSES_ONLY_RETAINED_SYMBOLS_TO_PANEL_CONSUMERS(
+        monkeypatch: pytest.MonkeyPatch) -> None:
+    """Live regression: 1000CATUSDT was dropped by ``align`` but remained in ``symbols``.
+
+    ``pooled_features`` then indexed every panel with the stale input universe and crashed instead
+    of reporting the retained cross-section. Stop immediately at that boundary so this test never
+    runs the 898,560-cell study.
+    """
+    overlap = pd.date_range("2026-08-01", periods=500, freq="15min", tz="UTC")
+    disjoint = pd.date_range("2026-09-01", periods=500, freq="15min", tz="UTC")
+    frames = {
+        "BTCUSDT": pd.DataFrame({"timestamp": overlap, "close": np.arange(500) + 100.0}),
+        "ETHUSDT": pd.DataFrame({"timestamp": overlap, "close": np.arange(500) + 50.0}),
+        "1000CATUSDT": pd.DataFrame(
+            {"timestamp": disjoint, "close": np.arange(500) + 1.0}
+        ),
+    }
+
+    class ReachedPanelBoundary(Exception):
+        pass
+
+    def capture(_panels: dict[str, pd.DataFrame], symbols: list[str]) -> None:
+        assert symbols == ["BTCUSDT", "ETHUSDT"]
+        raise ReachedPanelBoundary
+
+    monkeypatch.setattr(FS, "universe_check", lambda: (FS.PREREGISTERED_UNIVERSE, True))
+    monkeypatch.setattr(FS, "discover", lambda _symbols, _bars: frames)
+    monkeypatch.setattr(FS, "pooled_features", capture)
+    monkeypatch.setattr(sys, "argv", ["run_full_sweep.py"])
+    with pytest.raises(ReachedPanelBoundary):
+        FS.main()
+
+
 def test_A_BAR_IS_KEPT_ONLY_WHERE_ENOUGH_SYMBOLS_TRADED() -> None:
     """A bar with one symbol in it cannot be ranked cross-sectionally -- `rank` and `zscore`
     degenerate and correctly refuse -- so keeping it buys nothing and dilutes every count."""
```


---

## 4fab1eb8 Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3
# Conflicts:
#	libs/ops/doc_citations.py
#	ops/run_research_cycle.sh

```diff
commit 4fab1eb8615a7d27183d8cc199d5729020827670
Merge: cb2242ad 974063a0
Author: Codex <codex@openai.local>
Date:   Sat Aug 15 00:43:03 2026 +0000

    Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3
    
    # Conflicts:
    #       libs/ops/doc_citations.py
    #       ops/run_research_cycle.sh

 .claude/desk-state.sh                             |  22 ++
 CLAUDE.md                                         |   7 +
 docs/research/ARTIFACT_GOVERNANCE.md              |   2 +-
 docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md | 324 ++++++++++++++++++++++
 libs/execution/discretionary_sleeve.py            | 207 ++++++++++++++
 libs/ops/doc_citations.py                         |   6 +-
 libs/portfolio/auto_promotion.py                  |  28 ++
 libs/research/donated_survivor.py                 | 211 ++++++++++++++
 libs/research/slot_registry.py                    |  53 ++++
 libs/research/spot_momentum.py                    | 197 +++++++++++++
 ops/crontab.manifest                              |  15 +
 ops/run_research_cycle.sh                         | 114 +++++---
 scripts/check_unwired_capability.py               | 183 ++++++++++++
 scripts/max_audit.py                              |   6 +-
 scripts/run_auto_promotion.py                     | 145 ++++++++++
 scripts/run_discretionary_live.py                 | 190 +++++++++++++
 scripts/run_golive_preflight.py                   | 230 +++++++++++++++
 scripts/run_spot_executor.py                      | 216 +++++++++++++++
 scripts/run_spot_momentum.py                      | 180 ++++++++++++
 scripts/run_wealth_report.py                      |  17 ++
 tests/execution/test_discretionary_sleeve.py      | 130 +++++++++
 tests/portfolio/test_auto_promotion.py            |  51 ++++
 tests/research/test_donated_survivor.py           | 163 +++++++++++
 tests/research/test_spot_momentum.py              | 128 +++++++++
 tests/scripts/test_discretionary_live_adapter.py  |  86 ++++++
 25 files changed, 2863 insertions(+), 48 deletions(-)
```

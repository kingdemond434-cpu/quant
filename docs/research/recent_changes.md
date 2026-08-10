# Desk changes, last 24h (generated 2026-08-10T10:10:07Z)

12 commit(s). Patches truncated to 400 lines each -- a seat that receives
40k lines reviews none of them, and the design decision is almost always in the first
few hundred.


---

## 2cac413 desk snapshot 2026-08-10T02:57Z

```diff
commit 2cac413e7eb3705ac422f34a4ac23e668467e716
Author: Codex <codex@openai.local>
Date:   Mon Aug 10 02:57:45 2026 +0000

    desk snapshot 2026-08-10T02:57Z
---
 alpha_pipeline.json                                |    34 +-
 data/decision_ledger.json                          |    34 +-
 data/nav_attestation.jsonl                         |     1 +
 data/ratchet_floors.json                           |   206 +-
 docs/DESK_BRIEF.md                                 |    76 +-
 docs/GATE0_QUEUE.md                                |     2 +
 docs/desk_digest.md                                |   229 +-
 docs/research/CONSTITUTION_RATCHET.json            |   122 +-
 docs/research/CRO_BRIEFING.md                      |    14 +-
 .../capability_hunt/20260809_s0_proposals.md       |    12 +
 .../capability_hunt/20260809_s1_proposals.md       |    12 +
 .../capability_hunt/20260809_s2_proposals.md       |    12 +
 .../capability_hunt/20260809_s5_proposals.md       |    12 +
 .../capability_hunt/20260810_s3_proposals.md       |    12 +
 docs/research/feed_inbox.md                        |     8 +
 docs/research/micro_audit_inbox.md                 |     2 +-
 docs/research/recent_changes.md                    | 13132 ++++++++-----------
 docs/research/trade_forensics_latest.json          |    44 +-
 engineering_backlog.json                           |   169 +-
 ops/crontab.manifest                               |     2 +
 ops/principal_doctrine.txt                         |    10 -
 research_state.json                                |   368 +-
 22 files changed, 6103 insertions(+), 8410 deletions(-)

diff --git a/alpha_pipeline.json b/alpha_pipeline.json
index ae71d7e..86b4044 100644
--- a/alpha_pipeline.json
+++ b/alpha_pipeline.json
@@ -1,5 +1,5 @@
 {
-  "generated": "2026-08-07T03:16:04.757254+00:00",
+  "generated": "2026-08-10T02:51:26.697431+00:00",
   "n_alphas": 8,
   "n_survived": 0,
   "deployed": [
@@ -9,8 +9,8 @@
     {
       "alpha": "crypto::ls_contrarian",
       "category": "derivative-data",
-      "expected_sharpe": 3.4,
-      "gates": "7/10",
+      "expected_sharpe": 2.2,
+      "gates": "5/9",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
@@ -19,9 +19,9 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::funding_carry",
+      "alpha": "crypto::taker_flow",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.94,
+      "expected_sharpe": 0.93,
       "gates": "9/10",
       "survived": false,
       "stage": "backtest",
@@ -33,7 +33,7 @@
     {
       "alpha": "crypto::ts_trend",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.79,
+      "expected_sharpe": 0.89,
       "gates": "9/10",
       "survived": false,
       "stage": "backtest",
@@ -43,10 +43,10 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::taker_flow",
+      "alpha": "crypto::xsec_price_mom",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.49,
-      "gates": "6/10",
+      "expected_sharpe": 0.7,
+      "gates": "9/10",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
@@ -55,10 +55,10 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::xsec_price_mom",
+      "alpha": "crypto::funding_carry",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.47,
-      "gates": "6/10",
+      "expected_sharpe": 0.56,
+      "gates": "7/10",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
@@ -69,7 +69,7 @@
     {
       "alpha": "crypto::basis_carry",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.45,
+      "expected_sharpe": 0.27,
       "gates": "6/10",
       "survived": false,
       "stage": "backtest",
@@ -81,8 +81,8 @@
     {
       "alpha": "crypto::funding_momentum",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.32,
-      "gates": "5/10",
+      "expected_sharpe": -0.19,
+      "gates": "4/10",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
@@ -93,8 +93,8 @@
     {
       "alpha": "crypto::oi_divergence",
       "category": "derivative-data",
-      "expected_sharpe": -10.08,
-      "gates": "4/10",
+      "expected_sharpe": -9.74,
+      "gates": "3/9",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
diff --git a/data/decision_ledger.json b/data/decision_ledger.json
index 37b8a4b..bffc61d 100644
--- a/data/decision_ledger.json
+++ b/data/decision_ledger.json
@@ -2947,7 +2947,9 @@
    "success_metric": "cadence completes inside its budget and persists stamps (MEASURED 443.3s, 29 fired, 3 new stamps); max_audit reports scheduled-script-missing until the tree is resynced (MEASURED 75/133); desk_brief/contributor_score stop reporting false in cro_cycle_log.",
    "reversal_condition": "If deferring the panel measurably delays a finding that would have changed a decision, move it back and instead raise the parent budget. If the wall-clock gate skips the panel on runs that had ample budget, the reserve (780s) is mis-set -- lower it rather than remove it.",
    "neighbours": "daily_research_cycle._run now exports QUANT_STEP_BUDGET_S to ALL ~52 steps (ignored by every step that does not read it) and splits argv -- so desk_brief and contributor_score begin EXECUTING for the first time and will start writing docs/DESK_BRIEF.md and the contributor artifact, which is a new write path, not a no-op. In run_cadence, _funding_restored() and the model-upgrade duty now observe a funding-restored edge one run later (30d cadence, negligible); the closing status line reports panel-due-in computed before the panel runs. max_audit gains defect id scheduled-script-missing, which is REPO-scoped and will therefore escalate to the principal page after 48h -- intended, since the tree is genuinely broken.",
-   "flagged_gap": "branch-fork-75-missing-scheduled-scripts"
+   "flagged_gap": "branch-fork-75-missing-scheduled-scripts",
+   "review_due": "2026-09-03",
+   "review_due_source": "default"
   },
   {
    "id": "2026-08-04-carryover-37-disposition-tooling-absent",
@@ -2962,7 +2964,9 @@
    "success_metric": "After the merge, these items either close or produce a real result; if they still stall, the tooling explanation was wrong and the original skipped-verdict stands.",
    "reversal_condition": "If any of the five is found reachable by another path in this tree, that item returns to genuinely-owed immediately.",
    "neighbours": "Touches no code. It does change how \u00a737 output should be read: max_audit's carryover-skipped message asserts wilful carrying, and that assertion is now known to be unreliable while the tree is forked -- the carry-over brief should stat an item's tooling before calling it skipped. Rowed as the follow-up rather than patched here, since the brief lives on master.",
-   "flagged_gap": "carryover-brief-cannot-distinguish-skipped-from-impossible"
+   "flagged_gap": "carryover-brief-cannot-distinguish-skipped-from-impossible",
+   "review_due": "2026-09-03",
+   "review_due_source": "default"
   },
   {
    "id": "2026-08-04-scheduled-organ-outage-and-stale-code-daemons",
@@ -2976,7 +2980,9 @@
    "reversal_condition": "Checkpoint 20260804T213624_merge-master-restore-75-organs restores the prior tree exactly. If a restored organ proves harmful, delete that script and its crontab line rather than reverting all 113. If the stricter lint config blocks work, the per-file waivers each carry a stated falsifier.",
    "neighbours": "(1) cron + systemd: 75 organs now execute rather than exiting instantly, consuming real resources and writing artifacts for the first time; (2) max_audit: scheduled-script-missing closes and exploration-rate-unmeasured is expected to harden into the honest under-exploration finding now that the rate is measurable; (3) the CI lint leg now enforces DTZ + bandit repo-wide; (4) the executor, 3 recorders and moat miner are all new PIDs; (5) forward clocks reading stablecoin supply now key on UTC days, not local.",
    "flagged_gap": "Still forked: 419 commits behind, ~88 master-only test files, 256 conflicted paths. pyproject proved reunification must be a per-file UNION, not take-theirs. Rowed R0023 + GAP #88c.",
-   "push_record": "L1.37 --no-verify push, sanctioned, 4th instance -- AND THE CLASS HAS CHANGED, which is the point. The previous three were ENOENT: the hook exec'd scripts/run_law_gate.py, which did not exist here, so the gate failed on ABSENCE. The prior record (cb207f2) set its own retirement condition as 'once the merge lands and the hook can actually execute'. That half is now met: the gate RUNS, and this push restored 5 more fences it was missing (check_build_standard, check_mypy_ratchet, check_return_targeting, check_scheduler_manifest, check_sizing_derivation) -- two of which PASS immediately, so they were never breaches, only absences. WHY --no-verify IS STILL JUSTIFIED, verified rather than asserted: the 6 remaining breaches are pre-existing desk-wide states, not my diff. I diffed each fence's output against my own 147 changed paths: check_law_families, check_enforcement_execution, check_timidity_language and check_build_standard name NONE of my files. check_scheduler_manifest names one (ops/run_commit_audit.sh) and reading its detail shows the finding is a crontab DUPE -- the line is scheduled twice live vs once in the manifest -- which is a schedule defect that predates me; I restored the script, never the schedule. check_law_families has moreover never passed on this branch in its life, because until today the file was absent. SO: nothing that exists in this checkout was bypassed on its merits. The leash is now SHORTER, not longer -- from here --no-verify requires showing the breaches are not yours, and the next cycle inherits 6 named, substantive breaches to close (gap #88c / R0023)."
+   "push_record": "L1.37 --no-verify push, sanctioned, 4th instance -- AND THE CLASS HAS CHANGED, which is the point. The previous three were ENOENT: the hook exec'd scripts/run_law_gate.py, which did not exist here, so the gate failed on ABSENCE. The prior record (cb207f2) set its own retirement condition as 'once the merge lands and the hook can actually execute'. That half is now met: the gate RUNS, and this push restored 5 more fences it was missing (check_build_standard, check_mypy_ratchet, check_return_targeting, check_scheduler_manifest, check_sizing_derivation) -- two of which PASS immediately, so they were never breaches, only absences. WHY --no-verify IS STILL JUSTIFIED, verified rather than asserted: the 6 remaining breaches are pre-existing desk-wide states, not my diff. I diffed each fence's output against my own 147 changed paths: check_law_families, check_enforcement_execution, check_timidity_language and check_build_standard name NONE of my files. check_scheduler_manifest names one (ops/run_commit_audit.sh) and reading its detail shows the finding is a crontab DUPE -- the line is scheduled twice live vs once in the manifest -- which is a schedule defect that predates me; I restored the script, never the schedule. check_law_families has moreover never passed on this branch in its life, because until today the file was absent. SO: nothing that exists in this checkout was bypassed on its merits. The leash is now SHORTER, not longer -- from here --no-verify requires showing the breaches are not yours, and the next cycle inherits 6 named, substantive breaches to close (gap #88c / R0023).",
+   "review_due": "2026-09-03",
+   "review_due_source": "default"
   },
   {
    "id": "2026-08-05-severed-reply-channel-and-amnesiac-denylist",
@@ -3002,7 +3008,9 @@
     "run_trade_forensics.py flags -> run_alerts trade_class_bleeding page: the flag text changed (4 opens vs 2, 'below the floor' vs 'at baseline'), which will fire ONE new page under the 24h dedupe. Intended: the count was wrong."
    ],
    "flagged_gap": "The fork is the root cause of the pager regressions and is NOT fixed by this entry: the tree is 419 commits behind master and 108 ahead, and master silently held capabilities this box lacked. Ledgered as R0030.",
-   "push_record": "pending -- committed and pushed at end of cycle"
+   "push_record": "pending -- committed and pushed at end of cycle",
+   "review_due": "2026-09-04",
+   "review_due_source": "default"
   },
   {
    "id": "2026-08-05-l137-no-verify-push-record-5th",
@@ -3023,7 +3031,9 @@
     "ops/principal_doctrine.txt -- untouched, and it is the root cause of breaches 2 and 4 (35 laws absent from it)"
    ],
    "flagged_gap": "ROOT CAUSE, unfixed and now the top governance item: 21 orphan fences and 35 laws absent from the doctrine text mean the enforcement matrix reports laws as fenced that are not. This cycle found the sharpest instance -- check_book_absorbing_state was MAPPED to L1.23 and had never been written, so the desk believed it was guarded against the exact lock that has held the book flat. A registered-but-absent check is worse than an unregistered one: it stops anyone looking. Audit all 21 orphans and every mapping for existence, not just for presence.",
-   "push_record": "--no-verify, 5th instance, this entry is the record"
+   "push_record": "--no-verify, 5th instance, this entry is the record",
+   "review_due": "2026-09-04",
+   "review_due_source": "default"
   },
   {
    "id": "2026-08-05-generation-three-execution-hypotheses-and-a-miscalibrated-ev-gate",
@@ -3044,7 +3054,9 @@
     "data/shadow_sleeves.json / slot_registry -- 11 of 12 forward slots occupied, so at most ONE of these could ever take a clock; Stage A has zero promotion authority so generating all three costs no multiplicity"
    ],
    "flagged_gap": "THE EV GATE IS MIS-CALIBRATED FOR THIS DESK AND IT SILENTLY SHAPES EVERY RESEARCH DECISION. capacity_f = min(capacity_usd/1e6, 5)**0.25, so at our real ~$50k book capacity_f=0.473 and, against _EV_THRESHOLD=0.05, effort_h is the only free variable: a Sharpe-3.0 idea taking 6h scores 0.0462 and REJECTS while the same idea at 0.5h clears. Measured over a 320-cell grid: 4.4% clears at our capital vs 17.5% at $1M. It asks 'would this matter at a big fund', not 'does this raise OUR log-growth', and it penalises execution/cost work hardest -- which the constitution ranks equal to alpha. NOT self-applied: the gate has ZERO promotion authority, so its cost is invisible triage loss rather than risk, and recalibration deserves its own pre-registered acceptance-rate target instead of a threshold nudge. F0023 / R0038.",
-   "push_record": "pending -- pushed at end of cycle"
+   "push_record": "pending -- pushed at end of cycle",
+   "review_due": "2026-09-04",
+   "review_due_source": "default"
   },
   {
    "id": "2026-08-05-l137-no-verify-push-record-6th",
@@ -3072,7 +3084,9 @@
     "gate_state": "14 breaches, all attributed, none owned by this session",
     "owned_and_fixed_first": "check_constitution_core (f35df7e)",
     "verified_on_remote": true
-   }
+   },
+   "review_due": "2026-09-04",
+   "review_due_source": "default"
   },
   {
    "id": "2026-07-28-carry-churn-loop-root-cause-and-fix",
@@ -3610,7 +3624,9 @@
    "expected_cost": "~$200/month reported; split across seats UNMEASURED",
    "success_metric": "the ORIGINAL entry's metric stands and is half-met: '>=1 QUEUE-or-better finding' PASSED (~3); 'provider hit-rate measurable by month 2' FAILED (never computed)",
    "reversal_condition": "unchanged from the original entry: two consecutive panels with zero surviving findings -> drop to biweekly. On the evidence above it has arguably already fired and could not be observed",
-   "ts": "2026-08-09T10:54:30.050491+00:00"
+   "ts": "2026-08-09T10:54:30.050491+00:00",
+   "review_due": "2026-09-08",
+   "review_due_source": "default"
   }
  ]
-}
+}
\ No newline at end of file
diff --git a/data/nav_attestation.jsonl b/data/nav_attestation.jsonl
index 1a6e751..9388d43 100644
--- a/data/nav_attestation.jsonl
+++ b/data/nav_attestation.jsonl
@@ -17,3 +17,4 @@
 {"date":"2026-08-05","ts":"2026-08-05T03:03:23.305660+00:00","molded_curve_usd":13151.52,"equity_marked":13151.52,"_note":"molded_curve_usd is a MOLDED/SIMULATED curve, not venue truth and not a track record; venue truth is the dead-man's combined_equity","deployed_notional":0,"n_carries":0,"realized_spot_pnl":2921.35,"start_futures_equity":10547.78,"mode":"PAPER (testnet) -- pre-Gate-0","prev_sha256":"aa382bc1d859466440a260b58cf02b04e9367495442e91dfa979571f3ab7f2df"}
 {"date":"2026-08-06","ts":"2026-08-06T03:10:55.322164+00:00","molded_curve_usd":17906.66,"equity_marked":17906.66,"_note":"molded_curve_usd is a MOLDED/SIMULATED curve, not venue truth and not a track record; venue truth is the dead-man's combined_equity","deployed_notional":0,"n_carries":0,"realized_spot_pnl":2921.35,"start_futures_equity":10547.78,"mode":"PAPER (testnet) -- pre-Gate-0","prev_sha256":"84f12c75c5ba3bc28ea7dd4924a6ead2fa319c8b3dcaf8ff3fbe56fd34e1f562"}
 {"date":"2026-08-07","ts":"2026-08-07T03:01:03.786819+00:00","molded_curve_usd":17919.22,"equity_marked":17919.22,"_note":"molded_curve_usd is a MOLDED/SIMULATED curve, not venue truth and not a track record; venue truth is the dead-man's combined_equity","deployed_notional":0,"n_carries":0,"realized_spot_pnl":2921.35,"start_futures_equity":10547.78,"mode":"PAPER (testnet) -- pre-Gate-0","prev_sha256":"3d90e734d53885815b31ed90c6858d295182b9fb4fd8f8aba9471c814feaf1cc"}
+{"date":"2026-08-10","ts":"2026-08-10T02:46:44.732713+00:00","molded_curve_usd":17947.69,"equity_marked":17947.69,"_note":"molded_curve_usd is a MOLDED/SIMULATED curve, not venue truth and not a track record; venue truth is the dead-man's combined_equity","deployed_notional":0,"n_carries":0,"realized_spot_pnl":2921.35,"start_futures_equity":10547.78,"mode":"PAPER (testnet) -- pre-Gate-0","prev_sha256":"02939e4f678c396ac8049d614942337123d74e84657c9b58b09cf29b2feceefc"}
diff --git a/data/ratchet_floors.json b/data/ratchet_floors.json
index 8842fe4..9c21096 100644
--- a/data/ratchet_floors.json
+++ b/data/ratchet_floors.json
@@ -1,104 +1,104 @@
 {
-    "findings_coverage":  {
-                              "artifact":  "docs/research/findings_coverage_record.json",
-                              "proving_command":  "python scripts/max_audit.py (check_findings_tracked)",
-                              "recorded":  "2026-07-30T07:19:13Z",
-                              "value":  1
-                          },
-    "miner_seats_productive":  {
-                                   "artifact":  "data/miner_runway.json",
-                                   "proving_command":  "python scripts/check_miner_runway.py --json --report-only",
-                                   "recorded":  "2026-08-01T07:07:02Z",
-                                   "value":  0.090909
-                               },
-    "pager_delivered_24h":  {
-                                "artifact":  "data/alert_delivery.jsonl",
-                                "proving_command":  "python scripts/run_alert_canary.py",
-                                "recorded":  "2026-07-31T07:07:01Z",
-                                "value":  1
-                            },
-    "scripts_mypy_clean":  {
-                               "artifact":  "data/mypy_ratchet.json",
-                               "proving_command":  "python scripts/check_mypy_ratchet.py",
-                               "recorded":  "2026-08-07T03:21:06Z",
-                               "value":  0.406844
-                           },
-    "test_strength::libs/execution/staging.py":  {
-                                                     "artifact":  "data/mutation_score.json",
-                                                     "proving_command":  "python scripts/run_mutation.py --target libs/execution/staging.py",
-                                                     "recorded":  "2026-07-30T23:45:27Z",
-                                                     "value":  1
-                                                 },
-    "test_strength::libs/risk/gate.py":  {
-                                             "artifact":  "data/mutation_score.json",
-                                             "proving_command":  "python scripts/run_mutation.py --target libs/risk/gate.py",
-                                             "recorded":  "2026-07-30T23:45:27Z",
-                                             "value":  1
-                                         },
-    "test_strength::libs/risk/sizing.py":  {
-                                               "artifact":  "data/mutation_score.json",
-                                               "proving_command":  "python scripts/run_mutation.py --target libs/risk/sizing.py",
-                                               "recorded":  "2026-07-30T23:45:27Z",
-                                               "value":  0.8621
-                                           },
-    "test_strength::libs/validation/stepwise.py":  {
-                                                       "artifact":  "data/mutation_score.json",
-                                                       "proving_command":  "python scripts/run_mutation.py --target libs/validation/stepwise.py",
-                                                       "recorded":  "2026-07-30T07:40:54Z",
-                                                       "value":  0.9
-                                                   },
-    "test_strength_min_kill_rate":  {
-                                        "artifact":  "data/mutation_score.json",
-                                        "proving_command":  "python scripts/run_mutation.py",
-                                        "recorded":  "2026-07-30T07:19:13Z",
-                                        "value":  0.9
-                                    },
-    "test_strength_targets_at_bar":  {
-                                         "artifact":  "data/mutation_score.json",
-                                         "proving_command":  "python scripts/run_mutation.py",
-                                         "recorded":  "2026-07-30T23:45:27Z",
-                                         "value":  0.75
-                                     },
-    "campaign_obs_retained":  {
-                                  "artifact":  "data/campaign_retention.json",
-                                  "proving_command":  "python scripts/check_campaign_retention.py",
-                                  "recorded":  "2026-08-06T07:07:01Z",
-                                  "value":  1.0
-                              },
-    "capability_wired":  {
-                             "artifact":  "data/utilisation.json",
-                             "proving_command":  "python scripts/check_utilisation.py",
-                             "recorded":  "2026-08-06T03:15:53Z",
-                             "value":  0.83
-                         },
-    "test_strength::libs/autodiscovery/validation.py":  {
-                                                            "artifact":  "data/mutation_score.json",
-                                                            "proving_command":  "python scripts/run_mutation.py --target libs/autodiscovery/validation.py",
-                                                            "recorded":  "2026-08-06T01:13:49Z",
-                                                            "value":  0.4764
-                                                        },
-    "test_strength::libs/execution/binance_live.py":  {
-                                                          "artifact":  "data/mutation_score.json",
-                                                          "proving_command":  "python scripts/run_mutation.py --target libs/execution/binance_live.py",
-                                                          "recorded":  "2026-08-06T01:13:49Z",
-                                                          "value":  0.5467
-                                                      },
-    "test_strength::libs/execution/binance_spot_live.py":  {
-                                                               "artifact":  "data/mutation_score.json",
-                                                               "proving_command":  "python scripts/run_mutation.py --target libs/execution/binance_spot_live.py",
-                                                               "recorded":  "2026-08-06T01:13:49Z",
-                                                               "value":  0.8721
-                                                           },
-    "test_strength::libs/execution/binance_spot_testnet.py":  {
-                                                                  "artifact":  "data/mutation_score.json",
-                                                                  "proving_command":  "python scripts/run_mutation.py --target libs/execution/binance_spot_testnet.py",
-                                                                  "recorded":  "2026-08-06T01:13:49Z",
-                                                                  "value":  0.8444
-                                                              },
-    "test_strength::libs/execution/binance_testnet.py":  {
-                                                             "artifact":  "data/mutation_score.json",
-                                                             "proving_command":  "python scripts/run_mutation.py --target libs/execution/binance_testnet.py",
-                                                             "recorded":  "2026-08-06T01:13:49Z",
-                                                             "value":  0.6558
-                                                         }
-}
+  "campaign_obs_retained": {
+    "artifact": "data/campaign_retention.json",
+    "proving_command": "python scripts/check_campaign_retention.py",
+    "recorded": "2026-08-06T07:07:01Z",
+    "value": 1.0
+  },
+  "capability_wired": {
+    "artifact": "data/utilisation.json",
+    "proving_command": "python scripts/check_utilisation.py",
+    "recorded": "2026-08-10T02:49:53Z",
+    "value": 0.834
+  },
+  "findings_coverage": {
+    "artifact": "docs/research/findings_coverage_record.json",
+    "proving_command": "python scripts/max_audit.py (check_findings_tracked)",
+    "recorded": "2026-07-30T07:19:13Z",
+    "value": 1
+  },
+  "miner_seats_productive": {
+    "artifact": "data/miner_runway.json",
+    "proving_command": "python scripts/check_miner_runway.py --json --report-only",
+    "recorded": "2026-08-01T07:07:02Z",
+    "value": 0.090909
+  },
+  "pager_delivered_24h": {
+    "artifact": "data/alert_delivery.jsonl",
+    "proving_command": "python scripts/run_alert_canary.py",
+    "recorded": "2026-07-31T07:07:01Z",
+    "value": 1
+  },
+  "scripts_mypy_clean": {
+    "artifact": "data/mypy_ratchet.json",
+    "proving_command": "python scripts/check_mypy_ratchet.py",
+    "recorded": "2026-08-10T02:54:32Z",
+    "value": 0.406844
+  },
+  "test_strength::libs/autodiscovery/validation.py": {
+    "artifact": "data/mutation_score.json",
+    "proving_command": "python scripts/run_mutation.py --target libs/autodiscovery/validation.py",
+    "recorded": "2026-08-06T01:13:49Z",
+    "value": 0.4764
+  },
+  "test_strength::libs/execution/binance_live.py": {
+    "artifact": "data/mutation_score.json",
+    "proving_command": "python scripts/run_mutation.py --target libs/execution/binance_live.py",
+    "recorded": "2026-08-06T01:13:49Z",
+    "value": 0.5467
+  },
+  "test_strength::libs/execution/binance_spot_live.py": {
+    "artifact": "data/mutation_score.json",
+    "proving_command": "python scripts/run_mutation.py --target libs/execution/binance_spot_live.py",
+    "recorded": "2026-08-06T01:13:49Z",
+    "value": 0.8721
+  },
+  "test_strength::libs/execution/binance_spot_testnet.py": {
+    "artifact": "data/mutation_score.json",
```


---

## 3c9eacd merge unified checkpoint from GitHub into VPS state

```diff
commit 3c9eacd5c938f1a31c4eb020b5c153f8c9b4358e
Merge: c6db9fa 8b981a5
Author: Codex <codex@openai.local>
Date:   Sun Aug 9 11:58:26 2026 +0000

    merge unified checkpoint from GitHub into VPS state

 .gitignore                                         |   25 +
 data/agent_authority.json                          |  127 +
 data/decision_ledger.json                          | 7217 ++++++++++----------
 data/intelligence/external_intel.json              |  927 +++
 data/intelligence/extreme_return_claims.json       |   78 +
 data/intelligence/practitioner_corpus.json         |   97 +
 data/intelligence/video_channel_coverage.json      |   31 +
 docs/CONSTITUTION.md                               |   80 +
 docs/GAP_REGISTER.md                               |    6 +
 docs/research/ARTIFACT_GOVERNANCE.md               |    7 +-
 docs/research/COMPETITOR_COVERAGE.json             |  429 ++
 docs/research/COMPLETION_LEDGER.json               | 4628 +++++++------
 docs/research/COVERAGE_RATCHET.json                |    5 +-
 docs/research/SURVIVOR_YIELD_AUDIT.md              |   53 +
 docs/research/test_suite_record.json               |    7 +-
 libs/autodiscovery/orchestrator.py                 |    2 +-
 libs/data/render_fetch.py                          |    4 +-
 libs/execution/binance_spot_testnet.py             |  480 +-
 libs/execution/opportunity_surface.py              |  230 +
 libs/ops/agent_authority.py                        |  263 +
 libs/portfolio/alpha_reserve_bank.py               |  357 +
 libs/portfolio/capital_recycling.py                |  268 +
 libs/portfolio/portfolio_monte_carlo.py            |  344 +
 libs/portfolio/return_engines.py                   |  262 +
 libs/portfolio/strategy_pool.py                    |  263 +
 libs/portfolio/wealth_retention.py                 |  363 +
 libs/research/alpha_retention.py                   |  228 +
 libs/research/axis_screen.py                       |   97 +-
 libs/research/clock_registry.py                    |  109 +
 libs/research/competitor_coverage.py               |  219 +
 libs/research/completion_ledger.py                 |  220 +-
 libs/research/conversion_velocity.py               |  239 +
 libs/research/crowding_hazard.py                   |  204 +
 libs/research/decision_ledger.py                   |  221 +
 libs/research/drawdown_rebound.py                  |  314 +
 libs/research/evidence_clock.py                    |   81 +
 libs/research/external_benchmark.py                |  318 +
 libs/research/frontier.py                          |  418 ++
 libs/research/hunt_frontier.py                     |  316 +
 libs/research/market_breadth.py                    |  253 +
 libs/research/mechanism_ontology.py                |  335 +
 libs/research/paper_sleeves.py                     |    4 +-
 libs/research/participant_phenotype.py             |  202 +
 libs/research/payoff_selection.py                  |  232 +
 libs/research/practitioner_corpus.py               |  351 +
 libs/research/return_claims.py                     |  266 +
 libs/research/video_intelligence.py                |  284 +
 libs/self_improvement/capability_regression.py     |  225 +
 libs/validation/effective_sample.py                |  242 +
 libs/validation/state_conditional.py               |  370 +
 ops/gpt_video_hunter_prompt.txt                    |  277 +
 ops/run_research_cycle.sh                          |   24 +
 scripts/backfill_oi_ls_oos.py                      |   12 +
 scripts/build_enforcement_matrix.py                |   10 +
 scripts/kimi_hunter.py                             |   98 +-
 scripts/max_audit.py                               |    4 +
 scripts/research_allocator.py                      |   97 +-
 scripts/rollback_guard.py                          |   12 +
 scripts/run_axis_shadows.py                        |   49 +-
 scripts/run_cadence.py                             |   10 +
 scripts/run_ci.py                                  |   12 +
 scripts/run_crypto_research.py                     |   12 +
 scripts/run_external_intel.py                      |  241 +
 scripts/run_intelligence_cycle.py                  |   42 +
 scripts/run_live_ladder.py                         |   28 +-
 scripts/run_max_push.py                            |  292 +-
 scripts/run_opportunity_books.py                   |  299 +
 scripts/run_paper_sleeve_forward.py                |   12 +-
 scripts/run_promotion_queue.py                     |    7 +
 scripts/run_trade_forensics.py                     |   12 +
 scripts/run_wealth_report.py                       |  525 ++
 tests/autodiscovery/test_candidate_returns.py      |    2 +-
 tests/autodiscovery/test_novelty_gate.py           |    8 +-
 tests/ops/test_agent_authority.py                  |  204 +
 tests/portfolio/test_alpha_reserve_bank.py         |  271 +
 tests/portfolio/test_portfolio_monte_carlo.py      |  236 +
 tests/portfolio/test_return_engines.py             |  158 +
 tests/portfolio/test_wealth_retention.py           |  232 +
 tests/research/test_alpha_retention.py             |  147 +
 tests/research/test_candidate_store_wiring.py      |    2 +-
 tests/research/test_clock_registry.py              |  156 +
 tests/research/test_cohort_integrity.py            |   24 +-
 tests/research/test_conversion_velocity.py         |  130 +
 tests/research/test_decision_ledger.py             |  124 +
 tests/research/test_external_benchmark.py          |  172 +
 tests/research/test_external_intel_ledgers.py      |  339 +
 tests/research/test_frontier.py                    |  274 +
 tests/research/test_hunt_frontier.py               |  204 +
 tests/research/test_market_breadth.py              |  183 +
 tests/research/test_opportunity_books.py           |  415 ++
 tests/research/test_opportunity_books_paths.py     |  547 ++
 tests/research/test_paper_sleeves.py               |    3 +-
 tests/research/test_payoff_selection.py            |  122 +
 tests/research/test_practitioner_corpus.py         |  232 +
 tests/scripts/test_cycle_scripts_are_runnable.py   |  138 +
 tests/scripts/test_portfolio_admission.py          |    2 +-
 tests/scripts/test_research_allocator_semantics.py |  157 +
 tests/scripts/test_wealth_report.py                |  170 +
 .../self_improvement/test_capability_regression.py |  156 +
 tests/validation/test_effective_sample.py          |  149 +
 tests/validation/test_state_conditional.py         |  203 +
 web/research.html                                  |  100 +-
 102 files changed, 23663 insertions(+), 5973 deletions(-)
```


---

## 8b981a5 merge codex/unified-frontier-20260809: one lineage, and three modules that could not import
Resolves the two-remote split: 1052 commits from the Codex unified frontier
(incl. the VPS desk history) and 11 from this branch, neither containing the
other. 18 conflicts, resolved by rule where a rule applied and by review where
one did not.

COVERAGE RATCHET -- MAX OF EACH FIELD INDEPENDENTLY, never "take a side". Repo
93.23 (claude) vs 93.24 (codex) -> 93.24; money path 81.55 vs 89.44 -> 89.44.
L1.50 says floors ratchet UP only and a merge is not a measurement, so picking
one side wholesale would have silently lowered whichever floor that side was
behind on. Codex raised money-path coverage +7.89pp, which was the named top
residual on this branch. Same rule for test_suite_record: 362 vs 523 -> 523.

APPEND-ONLY FILES UNIONED, never chosen between: .gitignore, CONSTITUTION.md,
GAP_REGISTER.md, ARTIFACT_GOVERNANCE.md, decision_ledger (206+229 -> 230 by
id), COMPLETION_LEDGER (92 + 24 new -> 116), max_audit exemptions,
build_enforcement_matrix law rows, run_research_cycle stages. Dropping either
side would have deleted a law, a gap row or a governance claim.

CODE, REVIEWED RATHER THAN RULED. kimi_hunter and run_axis_shadows were taken
from Codex as the base and this branch's work re-applied on top, because their
versions carried real improvements worth keeping -- per-wave coverage
persistence (a late failure was discarding the territory memory of waves that
HAD succeeded), multi-model fallback, and the fix to a chr(34) obfuscation that
made the depth readout print zero unconditionally. research_allocator kept this
branch's survivor-leak fix plus their EXHAUSTION note. completion_ledger kept
ours, which strictly extends theirs. run_max_push kept both sides' readers.
Both branches had independently created test_external_intelligence.py testing
DIFFERENT modules; both survive, one renamed to test_external_intel_ledgers.

THE MERGE FOUND A LIVE BREAK, AND IT IS NOT MINE. libs/research/event_density,
libs/research/crowding and libs/risk/vol_headroom import MIN_OBS / MIN_T /
Sufficiency / sufficient from evidence_clock. Those names do not exist -- the
evidence-clock rewrite (1118781, which is in BOTH branches' history) replaced
them. Verified by import, not inferred: all three raise ImportError today on
the unified frontier. The merged mypy config type-checks 618 files against
505 before, which is why it surfaced now.

RESTORED THE OLD API VERBATIM rather than migrating the callers. sufficiency()
and sufficient() are not the same statistic -- one tests an effective n
deflated for autocorrelation against a caller-supplied requirement, the other
tests a t against min_t. Rewriting three callers onto the new clock during a
merge would silently change what they compute, and a wrong answer that runs is
worse than an ImportError that does not. The old block returns unchanged and
clearly labelled; migrating the three is owed work with its own review.

Four other real defects fixed to get the tree green: a dict|None that mypy
could not narrow through reassignment in paper_sleeves, an optional playwright
import, and two lint items.

ruff clean, mypy clean over 618 files.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 8b981a50f3c0c354555b9310bb37d4faeb0c00a1
Merge: 1186236 40c0777
Author: Claude <noreply@anthropic.com>
Date:   Sun Aug 9 11:54:01 2026 +0000

    merge codex/unified-frontier-20260809: one lineage, and three modules that could not import
    
    Resolves the two-remote split: 1052 commits from the Codex unified frontier
    (incl. the VPS desk history) and 11 from this branch, neither containing the
    other. 18 conflicts, resolved by rule where a rule applied and by review where
    one did not.
    
    COVERAGE RATCHET -- MAX OF EACH FIELD INDEPENDENTLY, never "take a side". Repo
    93.23 (claude) vs 93.24 (codex) -> 93.24; money path 81.55 vs 89.44 -> 89.44.
    L1.50 says floors ratchet UP only and a merge is not a measurement, so picking
    one side wholesale would have silently lowered whichever floor that side was
    behind on. Codex raised money-path coverage +7.89pp, which was the named top
    residual on this branch. Same rule for test_suite_record: 362 vs 523 -> 523.
    
    APPEND-ONLY FILES UNIONED, never chosen between: .gitignore, CONSTITUTION.md,
    GAP_REGISTER.md, ARTIFACT_GOVERNANCE.md, decision_ledger (206+229 -> 230 by
    id), COMPLETION_LEDGER (92 + 24 new -> 116), max_audit exemptions,
    build_enforcement_matrix law rows, run_research_cycle stages. Dropping either
    side would have deleted a law, a gap row or a governance claim.
    
    CODE, REVIEWED RATHER THAN RULED. kimi_hunter and run_axis_shadows were taken
    from Codex as the base and this branch's work re-applied on top, because their
    versions carried real improvements worth keeping -- per-wave coverage
    persistence (a late failure was discarding the territory memory of waves that
    HAD succeeded), multi-model fallback, and the fix to a chr(34) obfuscation that
    made the depth readout print zero unconditionally. research_allocator kept this
    branch's survivor-leak fix plus their EXHAUSTION note. completion_ledger kept
    ours, which strictly extends theirs. run_max_push kept both sides' readers.
    Both branches had independently created test_external_intelligence.py testing
    DIFFERENT modules; both survive, one renamed to test_external_intel_ledgers.
    
    THE MERGE FOUND A LIVE BREAK, AND IT IS NOT MINE. libs/research/event_density,
    libs/research/crowding and libs/risk/vol_headroom import MIN_OBS / MIN_T /
    Sufficiency / sufficient from evidence_clock. Those names do not exist -- the
    evidence-clock rewrite (1118781, which is in BOTH branches' history) replaced
    them. Verified by import, not inferred: all three raise ImportError today on
    the unified frontier. The merged mypy config type-checks 618 files against
    505 before, which is why it surfaced now.
    
    RESTORED THE OLD API VERBATIM rather than migrating the callers. sufficiency()
    and sufficient() are not the same statistic -- one tests an effective n
    deflated for autocorrelation against a caller-supplied requirement, the other
    tests a t against min_t. Rewriting three callers onto the new clock during a
    merge would silently change what they compute, and a wrong answer that runs is
    worse than an ImportError that does not. The old block returns unchanged and
    clearly labelled; migrating the three is owed work with its own review.
    
    Four other real defects fixed to get the tree green: a dict|None that mypy
    could not narrow through reassignment in paper_sleeves, an optional playwright
    import, and two lint items.
    
    ruff clean, mypy clean over 618 files.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

 .github/workflows/ci.yml                           |    12 +
 .gitignore                                         |    77 +-
 .../sor_research.sqlite                            |     0
 .../sor_research.sqlite                            |     0
 .../test_cycle_skips_redundant_hyp0/sor.sqlite     |   Bin 0 -> 303104 bytes
 .../sor_research.sqlite                            |     0
 .../test_niche_hunt_is_silent0/sor_research.sqlite |     0
 .../sor_research.sqlite                            |     0
 .../sor_research.sqlite                            |     0
 .../test_cycle_skips_redundant_hyp0/sor.sqlite     |   Bin 0 -> 303104 bytes
 .../test_cycle_without_a_gate_is_u0/sor.sqlite     |   Bin 0 -> 303104 bytes
 .../test_every_suppression_is_name0/sor.sqlite     |   Bin 0 -> 303104 bytes
 .../sor_research.sqlite                            |     0
 .../sor_research.sqlite                            |     0
 .../sor_research.sqlite                            |     0
 .../sor_research.sqlite                            |     0
 .../test_niche_hunt_is_silent0/sor_research.sqlite |     0
 .../sor_research.sqlite                            |     0
 .../sor_research.sqlite                            |     0
 AGENTS.md                                          |    31 +
 alpha_pipeline.json                                |    42 +-
 backups/moat/alpha_registry                        |   Bin 0 -> 561152 bytes
 backups/moat/capital_events                        |     1 +
 backups/moat/cost_model                            |  4245 ++++++
 backups/moat/execution_tape/cashcarry_trades.jsonl |   531 +
 backups/moat/graveyard                             |   434 +
 backups/moat/manifest.json                         |   119 +
 backups/moat/sor_research                          |   Bin 0 -> 2744320 bytes
 config/desk_costs.yaml                             |    30 +
 data/CAPABILITY_RATCHET.json                       |  1471 ++
 data/bybit_archive_retention.json                  |    34 +
 data/cashcarry_config.json                         |    10 +-
 data/cot_screen_summary.json                       |   233 +
 data/decision_ledger.json                          |  1679 ++-
 data/event_calendar.json                           |   141 +
 data/mutation_score.json                           |  3641 ++++-
 data/nav_attestation.jsonl                         |    10 +
 data/ratchet_floors.json                           |   164 +-
 data/unlock_event_screen.json                      |   319 +
 deploy/README.md                                   |    35 +
 deploy/finish_setup.sh                             |   106 +
 deploy/git_hooks/pre-push                          |    16 +
 deploy/privilege_separation/install.sh             |    40 +
 deploy/privilege_separation/permission_matrix.json |    14 +
 .../privilege_separation/quant-risk-kernel.service |    29 +
 deploy/pull_deploy.sh                              |   155 +-
 deploy/reconstitute_cron.sh                        |   145 +
 docs/CONSTITUTION.md                               |   590 +
 docs/CYCLE_20260729_CLOSURE.md                     |   115 +
 docs/DESK_BRIEF.md                                 |    83 +-
 docs/DIGGING_CHARTER.md                            |   147 +-
 docs/EXECUTION_QUEUE.md                            |   228 +
 docs/GAP_REGISTER.md                               |   513 +-
 docs/GATE0_QUEUE.md                                |    16 +
 docs/LIVE_CONNECTOR_SPEC.md                        |    28 +
 docs/POST_GATE0_MANIFEST.md                        |    28 +-
 docs/PRINCIPAL_ACTION.md                           |     3 +
 docs/WEEKLY_MAX_CYCLE.md                           |    44 +
 .../binance_spot_testnet.py.bak-20260716           |   169 +
 .../binance_testnet.py.bak-20260716                |   273 +
 .../daily_research_cycle.py.bak-20260716           |   106 +
 .../run_alerts.py.bak-20260716                     |   120 +
 .../run_cashcarry_executor.py.bak-20260716         |   634 +
 docs/desk_digest.md                                |   235 +-
 docs/desk_lessons.jsonl                            |    93 +
 docs/graveyard.md                                  |   268 +-
 docs/institutional_knowledge.md                    |   304 +-
 docs/research/ADVERSARIAL_REVIEW_RUBRIC.md         |    97 +
 docs/research/ARTIFACT_GOVERNANCE.md               |     5 +
 docs/research/AXIS_PREREGISTRATIONS.md             |    46 +
 docs/research/BITMEX_DECADE_INGEST_SPEC.md         |    80 +
 docs/research/COMPLETION_LEDGER.json               |  1614 ++-
 docs/research/CONSTITUTION_RATCHET.json            |   122 +-
 docs/research/COT_SCREEN_RESULT.md                 |   129 +
 docs/research/COVERAGE_RATCHET.json                |    17 +-
 docs/research/CRO_BRIEFING.md                      |   193 +
 docs/research/DATA_UNIVERSE_TAXONOMY.md            |   102 +
 .../DISCRETIONARY_PLAYBOOK_PREREGISTRATION.md      |    69 +
 docs/research/GPT_HUNTER_SOURCES.json              |   250 +
 docs/research/HYPOTHESIS_MAX_SPEC.md               |    53 +
 docs/research/INTRADAY_ROTATION_PREREGISTRATION.md |    66 +
 docs/research/INTRADAY_ROTATION_RESULT.md          |    79 +
 docs/research/MECHANISM_GRAPH.md                   |    94 +
 docs/research/MUTATION_BASELINE.md                 |   133 +
 .../NEW_FAMILY_GENERATORS_PREREGISTRATION.md       |   105 +
 docs/research/OPERATING_DOCTRINE.md                |    15 +
 docs/research/OVERNIGHT_FRONTIER_CONTRACT.json     |   163 +
 docs/research/PERMUTATION_NULL_RESULT.md           |   191 +
 docs/research/PREMORTEM_20260805.md                |   235 +
 docs/research/PROMPT_RATCHET.json                  |   523 +
 docs/research/PROMPT_RATCHET_WAIVERS.json          |    12 +
 docs/research/PROSPECTOR_SPEC.md                   |    20 +-
 docs/research/REALITY_CHECK_POWER.md               |   135 +
 docs/research/SUBSYSTEM_TRIAGE.md                  |     2 +-
 docs/research/TIER1_CONTROLLER_MANDATE.md          |  1407 ++
 docs/research/TRIAGE_20260729_PRINCIPAL_BATCH.md   |    64 +
 docs/research/TRIAGE_ADDENDUM.md                   |     2 +-
 docs/research/VPS_STATE_20260805.md                |    80 +
 docs/research/absorbing_kelly_study.json           |   297 +
 docs/research/alpha_hunt_20260731.md               |   122 +
 docs/research/axis_generation_20260805.md          |    94 +
 docs/research/blind_rediscovery_log.md             |   776 +
 docs/research/cadence_duties.md                    |    11 +-
 docs/research/capability_hunt/20260731_prompts.txt |    77 +
 .../capability_hunt/20260731_s1_prompts.txt        |    87 +
 .../capability_hunt/20260731_s2_proposals.md       |    12 +
 docs/research/capability_hunt/20260731_s5_hunt.md  |   130 +
 .../capability_hunt/20260731_s5_proposals.md       |    83 +
 docs/research/capability_hunt/20260801_s0_hunt.md  |   215 +
 .../capability_hunt/20260801_s0_proposals.md       |   119 +
 docs/research/capability_hunt/20260801_s1_hunt.md  |   140 +
 .../capability_hunt/20260801_s1_proposals.md       |    89 +
 .../capability_hunt/20260801_s2_proposals.md       |    12 +
 docs/research/capability_hunt/20260801_s3_hunt.md  |   185 +
 .../capability_hunt/20260801_s3_proposals.md       |    44 +
 docs/research/capability_hunt/20260801_s4_hunt.md  |   225 +
 .../capability_hunt/20260801_s4_proposals.md       |    97 +
 .../capability_hunt/20260801_s5_proposals.md       |    95 +
 .../capability_hunt/20260802_s3_proposals.md       |    12 +
 .../capability_hunt/20260802_s4_proposals.md       |    12 +
 docs/research/capability_hunt/20260805_s1_hunt.md  |   290 +
 .../capability_hunt/20260805_s1_proposals.md       |   106 +
 docs/research/capability_hunt/20260805_s2_hunt.md  |   162 +
 .../capability_hunt/20260805_s2_proposals.md       |    81 +
 .../capability_hunt/20260805_s4_proposals.md       |    12 +
 docs/research/capability_hunt/20260805_s5_hunt.md  |   201 +
 .../capability_hunt/20260805_s5_proposals.md       |    47 +
 .../capability_hunt/20260806_s0_proposals.md       |    12 +
 .../capability_hunt/20260806_s1_proposals.md       |    12 +
 .../capability_hunt/20260806_s2_proposals.md       |    12 +
 .../capability_hunt/20260806_s3_proposals.md       |   107 +
 .../capability_hunt/20260806_s4_proposals.md       |    12 +
 .../capability_hunt/20260806_s5_proposals.md       |    12 +
 .../capability_hunt/20260807_s3_proposals.md       |    12 +
 .../capability_hunt/20260808_s1_proposals.md       |    12 +
 .../capability_hunt/20260808_s2_proposals.md       |    12 +
 .../capability_hunt/20260808_s3_proposals.md       |    12 +
 .../capability_hunt/20260808_s5_proposals.md       |    12 +
 .../capability_hunt/20260809_s3_proposals.md       |    12 +
 .../capability_hunt/20260809_s4_proposals.md       |    12 +
 docs/research/cn_oss_extraction_20260731.md        |   115 +
 docs/research/conversion_record.json               |    12 +-
 docs/research/data_axis_watchlist.md               |   680 +
 docs/research/deep_review_inbox.md                 |  2577 ++++
 .../deep_sweep/20260728_alpha-discovery.md         |   577 +
 .../deep_sweep/20260728_data-intelligence.md       |   315 +
 docs/research/deep_sweep/20260728_data-moat.md     |    57 +
 .../deep_sweep/20260728_execution-growth.md        |    10 +
 .../research/deep_sweep/20260728_infrastructure.md |    10 +
 .../deep_sweep/20260728_meta-and-blindspots.md     |    10 +
 .../deep_sweep/20260728_research-engine.md         |    10 +
 .../deep_sweep/20260728_validation-stats.md        |    10 +
 docs/research/deep_sweep/20260729_SYNTHESIS.md     |   113 +
 .../deep_sweep/20260729_alpha-discovery.md         |   479 +
 .../deep_sweep/20260729_data-intelligence.md       |   344 +
 docs/research/deep_sweep/20260729_data-moat.md     |   449 +
 .../deep_sweep/20260729_execution-growth.md        |    57 +
 .../research/deep_sweep/20260729_infrastructure.md |   351 +
 .../deep_sweep/20260729_meta-and-blindspots.md     |   348 +
 .../deep_sweep/20260729_research-engine.md         |    74 +
 .../deep_sweep/20260729_validation-stats.md        |   444 +
 docs/research/deep_sweep/20260730_SYNTHESIS.md     |   559 +
 .../deep_sweep/20260730_alpha-discovery.md         |    54 +
 .../deep_sweep/20260730_data-intelligence.md       |  1681 +++
 docs/research/deep_sweep/20260730_data-moat.md     |   828 ++
 .../deep_sweep/20260730_execution-growth.md        |   686 +
 .../research/deep_sweep/20260730_infrastructure.md |  1630 +++
 .../deep_sweep/20260730_meta-and-blindspots.md     |   236 +
 .../deep_sweep/20260730_research-engine.md         |  1831 +++
 .../deep_sweep/20260730_validation-stats.md        |    64 +
 docs/research/deep_sweep/20260731_SYNTHESIS.md     |   389 +
 .../deep_sweep/20260731_alpha-discovery.md         |   589 +
 .../deep_sweep/20260731_data-intelligence.md       |   455 +
 docs/research/deep_sweep/20260731_data-moat.md     |   628 +
 .../deep_sweep/20260731_execution-growth.md        |   390 +
 .../research/deep_sweep/20260731_infrastructure.md |   154 +
 .../deep_sweep/20260731_launch-readiness.md        |   209 +
 .../deep_sweep/20260731_litC_ai_methods.md         |   276 +
 docs/research/deep_sweep/20260731_litE_buyside.md  |   503 +
 .../deep_sweep/20260731_litE_official_sector.md    |   418 +
 .../deep_sweep/20260731_meta-and-blindspots.md     |   444 +
 .../deep_sweep/20260731_research-engine.md         |   320 +
 .../deep_sweep/20260731_validation-stats.md        |   602 +
 docs/research/deep_sweep/20260801_SYNTHESIS.md     |   566 +
 .../deep_sweep/20260801_alpha-discovery.md         |  1239 ++
 .../deep_sweep/20260801_data-intelligence.md       |  1410 ++
 docs/research/deep_sweep/20260801_data-moat.md     |   980 ++
 .../deep_sweep/20260801_execution-growth.md        |   965 ++
 .../research/deep_sweep/20260801_infrastructure.md |  1624 +++
 .../deep_sweep/20260801_launch-readiness.md        |  1373 ++
 .../deep_sweep/20260801_meta-and-blindspots.md     |  1049 ++
 .../deep_sweep/20260801_research-engine.md         |   993 ++
 .../deep_sweep/20260801_validation-stats.md        |  1573 ++
 .../research/deep_sweep/20260805_LIT_ai_methods.md |    51 +
 .../deep_sweep/20260805_LIT_arxiv_qfin_sweep.md    |    58 +
 .../20260805_LIT_backlog_verification.md           |   113 +
 .../deep_sweep/20260805_LIT_theses_layer.md        |    95 +
 .../deep_sweep/LIT_a_failed_replication.md         |    27 +-
 .../research/deep_sweep/LIT_d_nonenglish_theses.md |    23 +
 docs/research/deep_sweep/T1a_kaiko_verification.md |     2 +-
 docs/research/discovery_hypotheses.md              |   131 +
 docs/research/feed_inbox.md                        |   123 +-
 docs/research/findings_coverage_record.json        |    12 +-
 docs/research/gate_power_audit.md                  |   214 +
 docs/research/generation_due.md                    |    18 +
 docs/research/holdings_record.json                 |     4 +-
 docs/research/improvement_inbox.md                 |   575 +
 docs/research/literature_coverage.md               |   220 +-
 docs/research/micro_audit_inbox.md                 |    97 +-
 docs/research/mining_record.json                   |    10 +-
 docs/research/negative_knowledge.md                |    32 +-
 docs/research/next_law_number.txt                  |     3 +
 docs/research/openmarket_corpus.json               |    59 +
 docs/research/paid_dataset_targets.md              |     6 +-
 docs/research/panel_inbox.md                       |   152 +-
 docs/research/panel_rulings.md                     |     1 +
 docs/research/prospector_coverage.md               |  2261 +++
 docs/research/prospector_watchlist.md              |    97 +
 docs/research/recent_changes.md                    | 14162 +++++++++++--------
 docs/research/recommendation_ledger.json           |  6291 ++++++--
 docs/research/search_operator_library.md           |   599 +-
 docs/research/self_interrogation_patterns.md       |    54 +
 docs/research/test_suite_record.json               |     9 +-
 docs/research/trade_forensics_latest.json          |    99 +
 docs/research/weak_signal_registry.md              |     5 +
 docs/research_conversions.jsonl                    |    14 +
 engineering_backlog.json                           |   160 +-
 libs/alpha_factory/__init__.py                     |     2 -
 libs/alpha_factory/alpha_factory_controller.py     |    96 +-
 libs/alpha_factory/capacity_intelligence.py        |    23 +-
 libs/autodiscovery/capacity_screen.py              |   158 +
 libs/autodiscovery/crypto_adapter.py               |    77 +-
 libs/autodiscovery/generators.py                   |   412 +-
 libs/autodiscovery/memory.py                       |   554 +-
 libs/autodiscovery/models.py                       |    11 +
 libs/autodiscovery/orchestrator.py                 |   345 +-
 libs/autodiscovery/reports.py                      |     6 +-
 libs/autodiscovery/research_roi.py                 |     5 +-
 libs/autodiscovery/validation.py                   |   832 +-
 libs/core/coerce.py                                |    42 +
 libs/core/secrets.py                               |     2 +-
 libs/data/asymmetry.py                             |   289 +-
 libs/data/bilibili.py                              |   250 +
 libs/data/cn_sources.py                            |   258 +
 libs/data/crypto_source.py                         |    67 +-
 libs/data/duckdb_client.py                         |     6 +-
 libs/data/foreign_sources.py                       |   826 ++
 libs/data/funding_caps.py                          |   175 +
 libs/data/lake.py                                  |    10 +-
 libs/data/multiexchange.py                         |    18 +-
 libs/data/papers.py                                |   280 +
 libs/data/paywall.py                               |   232 +
 libs/data/render_fetch.py                          |   223 +
 libs/data/source_promotion.py                      |   233 +
 libs/data/venue_http.py                            |    81 +
 libs/discovery/__init__.py                         |    99 +-
 libs/discovery/monte_carlo_survival.py             |    26 +
 libs/discovery/objective.py                        |    21 +-
 libs/doctrine/prompt_ratchet.py                    |   756 +
 libs/execution/binance_live.py                     |    67 +-
 libs/execution/binance_spot_live.py                |    17 +-
 libs/execution/binance_spot_testnet.py             |   480 +-
 libs/execution/binance_testnet.py                  |    55 +-
 libs/execution/carry_accounting.py                 |   138 +-
 libs/execution/collateral.py                       |    14 +
 libs/execution/economics.py                        |   937 ++
 libs/execution/event_guard.py                      |   117 +
 libs/execution/execution_tape.py                   |    14 +-
 libs/execution/leg_modes.py                        |    75 +
 libs/execution/passive_impact.py                   |   416 +
 libs/execution/staging.py                          |    24 +-
 libs/execution/sub_accounts.py                     |   172 +
 libs/llm/second_opinion.py                         |    77 +
 libs/ops/carryover.py                              |   263 +-
 libs/ops/controller_continuity.py                  |   290 +
 libs/ops/denominator.py                            |   205 +
 libs/ops/deploy_plan.py                            |   256 +
 libs/ops/fence_exit.py                             |    90 +
 libs/ops/fresh.py                                  |    85 +-
 libs/ops/host_resources.py                         |   109 +
 libs/ops/input_provenance.py                       |   261 +
 libs/ops/law_police.py                             |   293 +
 libs/ops/llm_route.py                              |   123 +
 libs/ops/llm_seat.py                               |   558 +
 libs/ops/principal_page.py                         |    86 +
 libs/ops/production_contract.py                    |   418 +
 libs/ops/repair_mode.py                            |   259 +
 libs/ops/research_daemon.py                        |    12 +-
 libs/portfolio/concentration.py                    |   420 +
 libs/portfolio/decision_intelligence.py            |   702 +
 libs/portfolio/live_book.py                        |     5 +
 libs/regime/engine.py                              |    20 +-
 libs/research/alpha_economics.py                   |   181 +-
 libs/research/alpha_frontier.py                    |   391 +
 libs/research/alpha_frontier_gaps.py               |    59 +
 libs/research/announcement_diffusion.py            |   825 ++
 libs/research/campaign_retention.py                |   194 +
 libs/research/capability_ratchet.py                |  2531 ++++
 libs/research/capacity_policy.py                   |    39 +-
 libs/research/cohort_independence.py               |   151 +
 libs/research/completion_program_gaps.py           |    96 +
 libs/research/conversion_ledger.py                 |   188 +
 libs/research/conversion_max.py                    |   394 +
 libs/research/cro_role.py                          |   851 ++
 libs/research/crowding.py                          |   189 +
 libs/research/data_registry.py                     |   579 +-
 libs/research/decision_review.py                   |   225 +
 libs/research/decline_value.py                     |   222 +
 libs/research/desk_coverage.py                     |   318 +
 libs/research/desk_economics.py                    |   155 +
 libs/research/desk_memory.py                       |   370 +
 libs/research/dip_ladder.py                        |   171 +
 libs/research/dist_shift.py                        |   121 +
 libs/research/earnability.py                       |   239 +
 libs/research/event_density.py                     |   257 +
 libs/research/evidence_clock.py                    |    81 +
 libs/research/external_intelligence.py             |   801 ++
 libs/research/finding_registry.py                  |    44 +
 libs/research/funnel.py                            |   361 +-
 libs/research/idle_yield.py                        |   395 +
 libs/research/intermarket.py                       |   199 +
 libs/research/intraday_rotation.py                 |   372 +
 libs/research/liq_heatmap.py                       |   242 +
 libs/research/liquidation_brief.py                 |   166 +
 libs/research/listing_events.py                    |   200 +
 libs/research/mechanism_census.py                  |  1704 +++
 libs/research/mine_conversion.py                   |   169 +-
 libs/research/moat_utilisation.py                  |  1506 ++
 libs/research/natural_experiment.py                |   377 +
 libs/research/operators.py                         |   570 +
 libs/research/orderbook_state.py                   |   386 +
 libs/research/overlays.py                          |   240 +
 libs/research/panel_diversity.py                   |   199 +
 libs/research/paper_sleeves.py                     |   492 +
 libs/research/positioning.py                       |   186 +
 libs/research/pre_filter.py                        |   157 +
 libs/research/primary_market_flow.py               |   551 +
 libs/research/promotion_history.py                 |   136 +
 libs/research/public_strategy_hunter.py            |   453 +
```


---

## 1186236 dashboard: the promotion funnel, and stop the card pointing at nothing
libs/research/promotion_latency.py, scripts/run_promotion_queue.py and
libs/research/conversion_velocity.py all existed and measured the
discovery -> shadow -> live path. The dashboard showed NONE of it: grep for
promotion/conversion/funnel in web/research.html returned 0.

New card renders the queue, forward-slot occupancy, and the latency split that
is the whole point -- EVIDENCE_BOUND in green (the forward clock, which is
evidence accruing and must never be compressed) against PROCESS_BOUND in red
(queue wait and decision lag, the dead time nobody chose and the only kind
worth attacking). An empty queue renders amber as UNMEASURED, not as a clean
queue, because on a box where the sweep has not run those are different facts.

AND THE CARD WOULD HAVE BEEN DECORATIVE. The dashboard fetches relative URLs
out of web/; run_promotion_queue writes data/promotion_queue.json. The panel
would have read "not found" forever. Mirrored to web/ rather than moved --
scripts/check_replacement_rate.py reads the data/ path and stays authoritative.

Found while smoke-testing: run_promotion_queue raises ImportError on
`capacity_race` from libs.autodiscovery.validation. It is cron-scheduled every
6h, so that job has been failing on every fire. Not fixed here -- the unified
frontier branch may already resolve it and I am about to merge.

ruff and mypy clean over 505 files.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 118623616ab3c44c762621b86deaf6dbb0a2dab2
Author: Claude <noreply@anthropic.com>
Date:   Sun Aug 9 11:41:25 2026 +0000

    dashboard: the promotion funnel, and stop the card pointing at nothing
    
    libs/research/promotion_latency.py, scripts/run_promotion_queue.py and
    libs/research/conversion_velocity.py all existed and measured the
    discovery -> shadow -> live path. The dashboard showed NONE of it: grep for
    promotion/conversion/funnel in web/research.html returned 0.
    
    New card renders the queue, forward-slot occupancy, and the latency split that
    is the whole point -- EVIDENCE_BOUND in green (the forward clock, which is
    evidence accruing and must never be compressed) against PROCESS_BOUND in red
    (queue wait and decision lag, the dead time nobody chose and the only kind
    worth attacking). An empty queue renders amber as UNMEASURED, not as a clean
    queue, because on a box where the sweep has not run those are different facts.
    
    AND THE CARD WOULD HAVE BEEN DECORATIVE. The dashboard fetches relative URLs
    out of web/; run_promotion_queue writes data/promotion_queue.json. The panel
    would have read "not found" forever. Mirrored to web/ rather than moved --
    scripts/check_replacement_rate.py reads the data/ path and stays authoritative.
    
    Found while smoke-testing: run_promotion_queue raises ImportError on
    `capacity_race` from libs.autodiscovery.validation. It is cron-scheduled every
    6h, so that job has been failing on every fire. Not fixed here -- the unified
    frontier branch may already resolve it and I am about to merge.
    
    ruff and mypy clean over 505 files.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 scripts/run_promotion_queue.py |  7 +++++++
 web/research.html              | 43 ++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 50 insertions(+)

diff --git a/scripts/run_promotion_queue.py b/scripts/run_promotion_queue.py
index ad3dda3..49fff70 100644
--- a/scripts/run_promotion_queue.py
+++ b/scripts/run_promotion_queue.py
@@ -44,6 +44,7 @@ if str(_ROOT) not in sys.path:
     sys.path.insert(0, str(_ROOT))
 
 _OUT = _ROOT / "data/promotion_queue.json"
+_WEB = _ROOT / "web/promotion_queue.json"
 #: The lab candidate store. Was `data/research_memory.db` until 2026-08-01 (R0079) -- a path
 #: NOTHING in this repo has ever written. `_DB.exists()` was therefore always False, this returned
 #: [], and the queue reported a structural `n_candidates: 0` on every 6-hourly run while looking
@@ -151,6 +152,12 @@ def main() -> int:
     rep = build(equity_usd=args.equity, growth=args.growth)
     _OUT.parent.mkdir(parents=True, exist_ok=True)
     _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
+    # MIRRORED TO web/ BECAUSE THE DASHBOARD FETCHES RELATIVE URLS. data/ stays authoritative --
+    # scripts/check_replacement_rate.py reads it -- so this is a copy, not a move. Without it the
+    # funnel card renders "not found" forever, which is the decorative-capability failure this
+    # desk keeps finding: a panel wired to an artifact that is never where it looks.
+    _WEB.parent.mkdir(parents=True, exist_ok=True)
+    _WEB.write_text(json.dumps(rep, indent=2), "utf-8")
     if args.json:
         print(json.dumps(rep, indent=2))
         return 0
diff --git a/web/research.html b/web/research.html
index 5ecabcd..8d7470f 100644
--- a/web/research.html
+++ b/web/research.html
@@ -57,6 +57,16 @@ svg text{fill:var(--dim);font-size:9px}
     <table id="xaweights"><thead><tr><th>Instrument</th><th>Target weight</th></tr></thead><tbody></tbody></table>
     <div class="note" id="xaverdict"></div></div>
 
+  <div class="card"><div class="ph">Promotion funnel · discovery -> shadow -> live (and where the DEAD time is)</div>
+    <div class="k" id="pqk"></div>
+    <div style="padding:10px 14px">
+      <table id="pqtab" style="width:100%;border-collapse:collapse;font-size:13px">
+        <thead><tr style="text-align:left;opacity:.7"><th>candidate</th><th>admission</th>
+          <th>slot action</th><th>runway</th></tr></thead><tbody></tbody></table>
+      <div id="pqlat" style="margin-top:10px;font-size:13px"></div>
+      <div id="pqnote" style="opacity:.65;margin-top:8px;font-size:12px"></div></div>
+  </div>
+
   <div class="card"><div class="ph">Loss forensics · WHERE the money went and WHY (daily)</div>
     <div class="k" id="fxk"></div>
     <div style="padding:10px 14px">
@@ -148,6 +158,39 @@ async function load(){
     }).join("");
     document.getElementById("levnote").textContent=L.note||"";
   }catch(e){document.getElementById("levnote").textContent="leverage.json not found — run run_mt5_portfolio.py";}
+  try{
+    const Q=await (await fetch("promotion_queue.json",{cache:"no-store"})).json();
+    const sl=Q.slots||{};
+    document.getElementById("pqk").innerHTML=
+      [["Candidates",Q.n_candidates],["Forward slots",`${sl.occupied||0}/${sl.cap||0} used, ${sl.free||0} free`],
+       ["Queued to admit",(Q.queue||[]).length],["Excluded",(Q.excluded||[]).length]]
+      .map(([l,v])=>`<div><span style="opacity:.6">${l}</span><br><b>${v===null||v===undefined?"—":v}</b></div>`).join("");
+    const qb=document.querySelector("#pqtab tbody"); qb.innerHTML="";
+    (Q.queue||[]).slice(0,15).forEach(r=>{
+      const now=String(r.slot_action||"").startsWith("ADMIT");
+      qb.innerHTML+=`<tr><td>${r.name||r.candidate||r.key||"—"}</td>`+
+        `<td>${r.admission||"—"}</td>`+
+        `<td style="color:${now?"#7ee787":"#e3b341"}">${r.slot_action||"—"}</td>`+
+        `<td>${r.runway_days===undefined?"—":fmt(r.runway_days)+"d"}</td></tr>`;
+    });
+    if(!(Q.queue||[]).length){
+      qb.innerHTML=`<tr><td colspan="4" style="color:#e3b341">no candidate is queued for admission — UNMEASURED if the sweep has not run, which is a fact about the box and not a clean queue</td></tr>`;
+    }
+    // EVIDENCE-BOUND vs PROCESS-BOUND is the whole point of this card. A forward clock is
+    // evidence accruing and cannot be compressed without destroying what it measures. Queue wait
+    // and decision lag are DEAD TIME -- latency nobody chose, and the only kind worth attacking.
+    const L=Q.latency||{};
+    const rows=Object.entries(L).filter(([,v])=>v&&typeof v==="object"&&("days" in v));
+    document.getElementById("pqlat").innerHTML = Q.latency_is_measured===false
+      ? `<span style="color:#e3b341">latency UNMEASURED — components missing, so total time-to-live is unknown rather than short</span>`
+      : (rows.length
+          ? `<b>Time to live:</b> `+rows.map(([k,v])=>{
+              const dead=/queue|decision|lag|wait/i.test(k);
+              return `<span style="color:${dead?"#ff7b72":"#7ee787"}" title="${dead?"DEAD TIME — nobody chose this":"evidence accruing — cannot be compressed"}">${k} ${fmt(v.days)}d</span>`;
+            }).join(" · ")+`<br><span style="opacity:.6">red = dead time (queue/decision lag) · green = evidence accruing (the forward clock, which must not be shortened)</span>`
+          : "");
+    document.getElementById("pqnote").textContent=`generated ${(Q.generated||"").slice(0,16)} · ${Q.law||""}`;
+  }catch(e){document.getElementById("pqnote").textContent="promotion_queue.json not found — run scripts/run_promotion_queue.py";}
   try{
     const F=await (await fetch("trade_forensics.json",{cache:"no-store"})).json();
     const mk=(F.maker_fill||{}), tp=(F.execution_tape||{});
```


---

## dc49989 wire the ladder to the clock registry: 9 stranded survivors become visible
Measured on the live box, and printing in every cycle before this:

    LADDER : 9 survivor(s) owed a shadow start; 0 record(s) laddered

run_live_ladder computes which Stage-A survivors are owed a forward clock and
then correctly declares `authority: NONE -- recommendations only`. It must not
start clocks. run_axis_shadows, which does start them, read a hardcoded _AXES
dict and could not see the list. One organ noticed and could not act; the other
could act and could not see. Nine survivors sat in the gap.

The cost is the one input this desk cannot buy later. A survivor waiting on a
clock is not idle -- it is losing forward days permanently, and the loss
printed as a tidy status line.

libs/research/clock_registry.register_owed writes the debt into the same
data/axis_clock_registry.json that stage_a_screen already writes and
run_axis_shadows already reads, so the survivors reach Stage-B and the
dashboard with no code edit.

REGISTERING IS NOT PROMOTING. An entry earns a Stage-B row and a dashboard row;
no capital, no eligibility, no evidence. They list as UNTRACKED because a sweep
survivor key is not an axis -- no collector JSONL, no target symbol -- and
`sign: 0` means UNKNOWN direction, never neutral. Inventing a target so the row
looked complete would score a candidate against the wrong asset, which is worse
than not scoring it. First-write-wins, so a later run with real inputs fills it
in without this one having guessed.

owed_since is deliberately NOT restamped on re-registration. The ladder runs
every cycle; restamping would reset the age of the debt daily and erase the
only number that shows how long a clock has been owed.

CAUGHT BEFORE IT BIT: the ladder's tests drive main() with tmp sweep/records/
out paths, and register_owed defaulted to the REAL registry -- so every suite
run would have written fixture survivors into live state. That is the same
shape that polluted web/axis_shadows.json and reddened a cohort fence earlier
today. The path is now a --registry argument, with a test asserting the live
file is untouched by a test run.

11 tests including the end-to-end path (ladder writes -> Stage-B reads ->
survivor appears as UNTRACKED) and that curated _AXES entries still win a name
collision, so a re-registration can never redirect a live clock's target.

Nine Stage-A survivors is not nine edges: 0 admitted, 0 portfolio-contributing,
0 confirmed. Stage-A carries zero promotion authority. What this changes is
that they now accrue forward days instead of being re-counted as owed.

ruff and mypy clean over 505 files.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit dc499896d793c4b82920e96be918bf6aa160e626
Author: Claude <noreply@anthropic.com>
Date:   Sun Aug 9 11:37:41 2026 +0000

    wire the ladder to the clock registry: 9 stranded survivors become visible
    
    Measured on the live box, and printing in every cycle before this:
    
        LADDER : 9 survivor(s) owed a shadow start; 0 record(s) laddered
    
    run_live_ladder computes which Stage-A survivors are owed a forward clock and
    then correctly declares `authority: NONE -- recommendations only`. It must not
    start clocks. run_axis_shadows, which does start them, read a hardcoded _AXES
    dict and could not see the list. One organ noticed and could not act; the other
    could act and could not see. Nine survivors sat in the gap.
    
    The cost is the one input this desk cannot buy later. A survivor waiting on a
    clock is not idle -- it is losing forward days permanently, and the loss
    printed as a tidy status line.
    
    libs/research/clock_registry.register_owed writes the debt into the same
    data/axis_clock_registry.json that stage_a_screen already writes and
    run_axis_shadows already reads, so the survivors reach Stage-B and the
    dashboard with no code edit.
    
    REGISTERING IS NOT PROMOTING. An entry earns a Stage-B row and a dashboard row;
    no capital, no eligibility, no evidence. They list as UNTRACKED because a sweep
    survivor key is not an axis -- no collector JSONL, no target symbol -- and
    `sign: 0` means UNKNOWN direction, never neutral. Inventing a target so the row
    looked complete would score a candidate against the wrong asset, which is worse
    than not scoring it. First-write-wins, so a later run with real inputs fills it
    in without this one having guessed.
    
    owed_since is deliberately NOT restamped on re-registration. The ladder runs
    every cycle; restamping would reset the age of the debt daily and erase the
    only number that shows how long a clock has been owed.
    
    CAUGHT BEFORE IT BIT: the ladder's tests drive main() with tmp sweep/records/
    out paths, and register_owed defaulted to the REAL registry -- so every suite
    run would have written fixture survivors into live state. That is the same
    shape that polluted web/axis_shadows.json and reddened a cohort fence earlier
    today. The path is now a --registry argument, with a test asserting the live
    file is untouched by a test run.
    
    11 tests including the end-to-end path (ladder writes -> Stage-B reads ->
    survivor appears as UNTRACKED) and that curated _AXES entries still win a name
    collision, so a re-registration can never redirect a live clock's target.
    
    Nine Stage-A survivors is not nine edges: 0 admitted, 0 portfolio-contributing,
    0 confirmed. Stage-A carries zero promotion authority. What this changes is
    that they now accrue forward days instead of being re-counted as owed.
    
    ruff and mypy clean over 505 files.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/research/test_suite_record.json  |   4 +-
 libs/research/clock_registry.py       | 109 ++++++++++++++++++++++++
 scripts/run_live_ladder.py            |  28 +++++-
 tests/research/test_clock_registry.py | 156 ++++++++++++++++++++++++++++++++++
 4 files changed, 294 insertions(+), 3 deletions(-)

diff --git a/docs/research/test_suite_record.json b/docs/research/test_suite_record.json
index 7d41b7e..94f1885 100644
--- a/docs/research/test_suite_record.json
+++ b/docs/research/test_suite_record.json
@@ -1,5 +1,5 @@
 {
- "max_collected": 360,
- "at": "2026-08-09T10:48:45.135363+00:00",
+ "max_collected": 362,
+ "at": "2026-08-09T11:36:20.175075+00:00",
  "note": "high-water mark of COLLECTABLE test modules; ratchets UP only. A suite may never quietly shrink -- deleting a test is a decision, not a side effect."
 }
\ No newline at end of file
diff --git a/libs/research/clock_registry.py b/libs/research/clock_registry.py
new file mode 100644
index 0000000..b0ad1c6
--- /dev/null
+++ b/libs/research/clock_registry.py
@@ -0,0 +1,109 @@
+"""THE CLOCK REGISTRY — the wire between an organ that notices and an organ that can act.
+
+THE GAP THIS CLOSES, measured on the live box 2026-08-09 and printing in every cycle before that:
+
+    LADDER : 9 survivor(s) owed a shadow start; 0 record(s) laddered
+
+`scripts/run_live_ladder.py` computes which Stage-A survivors are owed a forward clock, and then
+correctly declares `authority: NONE -- recommendations only`. It must not start clocks; that is
+`scripts/run_axis_shadows.py`'s job. But that script read a HARDCODED `_AXES` dict, so it could not
+see the list. One organ noticed and could not act; the other could act and could not see.
+
+**THE COST IS THE ONE THING THIS DESK CANNOT BUY LATER.** A survivor waiting on a clock is not
+idle, it is losing forward days that will never be recovered. Nine survivors x every day the wire
+was missing is the largest silent loss in the pipeline, and it printed as a tidy status line.
+
+**REGISTERING IS NOT STARTING A CLOCK, AND IT IS NOT A PROMOTION.** An entry here earns exactly two
+things: a row in Stage-B's report and a row on the dashboard. It earns no capital, no eligibility
+and no evidence. What it removes is invisibility -- the difference between an owed clock and a
+forgotten one.
+
+**AND IT REGISTERS THEM AS UNTRACKED, ON PURPOSE.** A sweep survivor key is not an axis: it has no
+collector JSONL and no target symbol, so Stage-B cannot score it. The honest state is *owed and
+unscoreable*, which `run_axis_shadows` already renders as UNTRACKED. Inventing a target so the row
+looked complete would score a candidate against the wrong asset, which is worse than not scoring
+it -- and `first registration wins`, so a later run with real inputs can fill it in without this
+one having guessed first.
+"""
+
+from __future__ import annotations
+
+import json
+from datetime import UTC, datetime
+from pathlib import Path
+from typing import Any
+
+__all__ = ["REGISTRY", "register_owed"]
+
+#: Shared with libs/research/axis_screen.py and scripts/run_axis_shadows.py. One file, so an organ
+#: and the tracker can never disagree about which clocks are owed.
+REGISTRY = Path("data/axis_clock_registry.json")
+
+
+def register_owed(names: list[str], *, source: str, registry: Path | str = REGISTRY,
+                  ) -> tuple[int, str]:
+    """Record survivors owed a forward clock. Returns (newly registered, why).
+
+    IDEMPOTENT AND FIRST-WRITE-WINS. The ladder runs every cycle and would otherwise restamp the
+    same nine names daily, resetting `owed_since` and erasing the very number that makes the debt
+    legible -- how long it has been owed.
+    """
+    if not names:
+        return 0, ("no survivor is owed a shadow start. On a clone with no sweep artifact this is "
+                   "UNMEASURED rather than a clean queue: the sweep is gitignored and lives on "
+                   "the box")
+    reg = Path(registry)
+    try:
+        blob = json.loads(reg.read_text("utf-8")) if reg.exists() else {}
+    except (OSError, ValueError):
+        blob = {}
+    raw = blob.get("axes")
+    axes: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
+
+    now = datetime.now(tz=UTC).isoformat()
+    added, already = 0, 0
+    for name in names:
+        key = str(name).strip()
+        if not key:
+            continue
+        if key in axes:
+            already += 1
+            continue
+        axes[key] = {
+            "clock": "",
+            "target_symbol": "",
+            "method": "z20",
+            "sign": 0,
+            "registered_at": now,
+            "owed_since": now,
+            "registered_by": source,
+            "tracked": False,
+            "note": ("Stage-A survivor OWED a forward clock. Registered so Stage-B and the "
+                     "dashboard can see the debt; this is not a promotion and starts no clock. "
+                     "It carries no collector JSONL and no target symbol, so it lists as "
+                     "UNTRACKED until one is supplied -- deliberately, because inventing a target "
+                     "would score it against the wrong asset, which is worse than not scoring it. "
+                     "`sign: 0` means UNKNOWN direction and must never be read as neutral."),
+        }
+        added += 1
+
+    if added:
+        reg.parent.mkdir(parents=True, exist_ok=True)
+        blob["axes"] = axes
+        blob["updated"] = now
+        blob.setdefault("note", (
+            "Forward clocks owed or started. Written by stage_a_screen when a screen earns a "
+            "clock, and by run_live_ladder when a Stage-A survivor is owed one. Read by "
+            "run_axis_shadows so a candidate reaches Stage-B and the dashboard WITHOUT a code "
+            "edit -- the absence of that path stranded 9 survivors indefinitely."))
+        reg.write_text(json.dumps(blob, indent=1), "utf-8")
+
+    return added, (
+        f"{added} survivor(s) newly registered as owed a forward clock, {already} already known "
+        f"(source: {source}). They list as UNTRACKED until a collector and target symbol exist, "
+        "which is the honest state -- owed and unscoreable is not the same as absent, and it is "
+        "the difference between an owed clock and a forgotten one"
+        if added else
+        f"all {already} owed survivor(s) were already registered (source: {source}); "
+        "`owed_since` deliberately NOT restamped, because how long a clock has been owed is the "
+        "number that makes the debt legible")
diff --git a/scripts/run_live_ladder.py b/scripts/run_live_ladder.py
index 1a7a424..f6f21f5 100644
--- a/scripts/run_live_ladder.py
+++ b/scripts/run_live_ladder.py
@@ -45,6 +45,8 @@ if str(ROOT) not in sys.path:
 
 from libs.portfolio import capital_competition  # noqa: E402
 from libs.research import alpha_state, evidence_clock  # noqa: E402
+from libs.research.clock_registry import REGISTRY as CLOCK_REGISTRY  # noqa: E402
+from libs.research.clock_registry import register_owed  # noqa: E402
 from libs.research.live_ladder import (  # noqa: E402
     MIN_OBS_FOR_A_VERDICT,
     LiveRecord,
@@ -230,6 +232,9 @@ def main() -> int:
     ap = argparse.ArgumentParser(description=__doc__)
     ap.add_argument("--records", type=Path, default=RECORDS)
     ap.add_argument("--sweep", type=Path, default=SWEEP)
+    ap.add_argument("--registry", type=Path, default=CLOCK_REGISTRY,
+                    help="where owed forward clocks are recorded so Stage-B and the dashboard "
+                         "can see them; overridable so tests never write the real one")
     ap.add_argument("--out", type=Path, default=OUT)
     a = ap.parse_args()
 
@@ -245,6 +250,24 @@ def main() -> int:
     # the only thing that cannot be bought later.
     to_shadow = [s for s in survivors if s not in named]
 
+    # THE WIRE THAT WAS MISSING, and its absence was silent. This script computes `to_shadow` and
+    # then declares `authority: NONE -- recommendations only`, which is correct: it must not start
+    # clocks. But run_axis_shadows.py -- the organ that DOES start them -- read a hardcoded _AXES
+    # dict and could not see this list. So a Stage-A survivor sat between an organ that noticed it
+    # and could not act, and an organ that could act and could not see it. Measured 2026-08-09:
+    # "9 survivor(s) owed a shadow start; 0 record(s) laddered", every cycle, for as long as the
+    # sweep has been producing survivors.
+    #
+    # Registering is NOT starting a clock and NOT a promotion. It makes the debt VISIBLE to
+    # Stage-B and to the dashboard, which is the whole difference between an owed clock and a
+    # forgotten one. Forward time is the single input this desk cannot buy later.
+    # REGISTRY PATH IS AN ARGUMENT, NOT A CONSTANT. The tests drive main() with tmp sweep/records/
+    # out paths; a hardcoded default here would write their fixture survivors into the REAL
+    # data/axis_clock_registry.json on every test run. That is not hypothetical -- the same shape
+    # polluted web/axis_shadows.json earlier today and turned a cohort fence red.
+    owed_registered, owed_why = register_owed(to_shadow, source="run_live_ladder",
+                                              registry=a.registry)
+
     verdicts = [decide(r) for r in live]
     competition = competing_allocation(live, verdicts)
 
@@ -272,6 +295,8 @@ def main() -> int:
         "live_records": len(live),
         "stage_a_survivors": len(survivors),
         "to_shadow": to_shadow[:100],
+        "owed_registered": owed_registered,
+        "owed_registration_note": owed_why,
         "governance_ladder": ladder_states[:100],
         "capital_competition": competition,
         "evidence_clock": [
@@ -301,7 +326,8 @@ def main() -> int:
             "Both are gitignored and live on the collecting box; the sweep has not run (GAP #91) "
             "and nothing has traded (Gate-0 0/17). This is UNMEASURED, not an empty ladder.")
     else:
-        rep["verdict"] = (f"{len(to_shadow)} survivor(s) owed a shadow start; "
+        rep["verdict"] = (f"{len(to_shadow)} survivor(s) owed a shadow start "
+                          f"({owed_registered} newly registered for Stage-B); "
                           f"{len(live)} record(s) laddered")
 
     a.out.parent.mkdir(parents=True, exist_ok=True)
diff --git a/tests/research/test_clock_registry.py b/tests/research/test_clock_registry.py
new file mode 100644
index 0000000..7e7a124
--- /dev/null
+++ b/tests/research/test_clock_registry.py
@@ -0,0 +1,156 @@
+"""THE WIRE BETWEEN AN ORGAN THAT NOTICES AND AN ORGAN THAT CAN ACT.
+
+Measured on the live box, printing every cycle:
+
+    LADDER : 9 survivor(s) owed a shadow start; 0 record(s) laddered
+
+`run_live_ladder` computed the debt and correctly refused to act on it (`authority: NONE`).
+`run_axis_shadows` could act and read a hardcoded `_AXES` dict that could not see the list. Nine
+Stage-A survivors sat between them, and the loss compounds daily in the one currency this desk
+cannot buy later -- forward days.
+
+The tests that matter here are the two that stop the wire becoming a lie:
+
+  `test_OWED_SINCE_IS_NEVER_RESTAMPED` -- the ladder runs every cycle; restamping would reset the
+      age of the debt and erase the number that makes it legible.
+  `test_A_TARGET_IS_NEVER_INVENTED`    -- a survivor scored against the wrong asset is worse than
+      one not scored at all, so an unscoreable entry must stay unscoreable.
+"""
+
+from __future__ import annotations
+
+import json
+from pathlib import Path
+
+from libs.research.clock_registry import register_owed
+
+
+class TestRegistersTheDebt:
+    def test_survivors_become_visible_to_stage_b(self, tmp_path: Path) -> None:
+        reg = tmp_path / "reg.json"
+        n, why = register_owed(["m1|btc|z20", "m2|eth|z20"], source="test", registry=reg)
+        assert n == 2
+        assert "newly registered" in why
+        axes = json.loads(reg.read_text("utf-8"))["axes"]
+        assert set(axes) == {"m1|btc|z20", "m2|eth|z20"}
+
+    def test_A_TARGET_IS_NEVER_INVENTED(self, tmp_path: Path) -> None:
+        """A sweep survivor key is not an axis. Fabricating a target so the row looked complete
+        would score the candidate against the wrong asset."""
+        reg = tmp_path / "reg.json"
+        register_owed(["survivor|key"], source="test", registry=reg)
+        rec = json.loads(reg.read_text("utf-8"))["axes"]["survivor|key"]
+        assert rec["target_symbol"] == ""
+        assert rec["clock"] == ""
+        assert rec["tracked"] is False
+        assert rec["sign"] == 0, "0 means UNKNOWN direction; +1 would silently pick momentum"
+        assert "worse than not scoring it" in rec["note"]
+
+    def test_OWED_SINCE_IS_NEVER_RESTAMPED(self, tmp_path: Path) -> None:
+        """The ladder runs every cycle. Restamping would reset the age of the debt daily and
+        destroy the only number that shows how long a clock has been owed."""
+        reg = tmp_path / "reg.json"
+        register_owed(["a"], source="first", registry=reg)
+        first = json.loads(reg.read_text("utf-8"))["axes"]["a"]["owed_since"]
+
+        n, why = register_owed(["a"], source="second", registry=reg)
+        assert n == 0
+        assert "already registered" in why
+        assert "NOT restamped" in why
+        after = json.loads(reg.read_text("utf-8"))["axes"]["a"]
+        assert after["owed_since"] == first
+        assert after["registered_by"] == "first", "first write wins; a re-run must not reassign it"
+
+    def test_a_partial_overlap_adds_only_the_new_ones(self, tmp_path: Path) -> None:
+        reg = tmp_path / "reg.json"
+        register_owed(["a", "b"], source="t", registry=reg)
+        n, _ = register_owed(["b", "c"], source="t", registry=reg)
+        assert n == 1
+        assert set(json.loads(reg.read_text("utf-8"))["axes"]) == {"a", "b", "c"}
+
+
+class TestRefusals:
+    def test_an_empty_list_is_UNMEASURED_not_a_clean_queue(self, tmp_path: Path) -> None:
+        reg = tmp_path / "reg.json"
+        n, why = register_owed([], source="t", registry=reg)
+        assert n == 0
+        assert "UNMEASURED rather than a clean queue" in why
+        assert not reg.exists(), "nothing owed must not create a file implying it was checked"
+
+    def test_blank_names_are_skipped(self, tmp_path: Path) -> None:
+        reg = tmp_path / "reg.json"
+        n, _ = register_owed(["", "   ", "real"], source="t", registry=reg)
+        assert n == 1
+        assert list(json.loads(reg.read_text("utf-8"))["axes"]) == ["real"]
+
+    def test_a_corrupt_registry_does_not_lose_the_new_entries(self, tmp_path: Path) -> None:
+        """Failing closed here would drop the debt silently, which is the state being fixed."""
+        reg = tmp_path / "reg.json"
+        reg.write_text("{not json", "utf-8")
+        n, _ = register_owed(["a"], source="t", registry=reg)
+        assert n == 1
+        assert "a" in json.loads(reg.read_text("utf-8"))["axes"]
+
+
+class TestTheLadderNeverWritesTheRealRegistry:
+    def test_the_path_is_an_argument(self) -> None:
+        """A hardcoded default here would write test fixtures into the live registry on every
+        suite run -- the same shape that polluted web/axis_shadows.json and reddened a fence."""
+        import scripts.run_live_ladder as RL
+        src = Path(RL.__file__).read_text("utf-8")
+        assert "registry=a.registry" in src, "the ladder must pass the CLI path, not the default"
+        assert '"--registry"' in src
+
+    def test_driving_main_with_a_tmp_registry_leaves_the_real_one_alone(
+            self, tmp_path: Path, monkeypatch) -> None:
+        import sys
+
+        import scripts.run_live_ladder as RL
+        real = Path("data/axis_clock_registry.json")
+        before = real.read_text("utf-8") if real.exists() else None
+
+        sweep = tmp_path / "sweep.json"
+        sweep.write_text(json.dumps({"survivors": [{"key": ["fixture", "only"]}]}), "utf-8")
+        reg = tmp_path / "reg.json"
+        monkeypatch.setattr(sys, "argv", [
+            "run_live_ladder.py", "--sweep", str(sweep),
+            "--records", str(tmp_path / "none.json"), "--out", str(tmp_path / "rep.json"),
+            "--registry", str(reg)])
+        assert RL.main() == 0
+
+        assert "fixture|only" in json.loads(reg.read_text("utf-8"))["axes"]
+        after = real.read_text("utf-8") if real.exists() else None
+        assert after == before, "the live registry must be untouched by a test run"
+
+
+class TestItReachesStageB:
+    def test_a_registered_survivor_lists_as_UNTRACKED_rather_than_vanishing(
+            self, tmp_path: Path, monkeypatch) -> None:
+        """END TO END, and the point of the whole wire: the ladder writes, Stage-B reads, and the
+        survivor appears -- unscoreable but VISIBLE, which is the difference between an owed clock
+        and a forgotten one."""
+        import scripts.run_axis_shadows as ras
+
+        reg = tmp_path / "reg.json"
+        register_owed(["stranded|survivor"], source="run_live_ladder", registry=reg)
+        monkeypatch.setattr(ras, "_REGISTRY", reg)
```


---

## c6db9fa bind displacement seats to their exact challenger

```diff
commit c6db9faffeaddcf367e2d4beb8caba4e4a9912aa
Author: Codex <codex@openai.local>
Date:   Sun Aug 9 12:34:46 2026 +0100

    bind displacement seats to their exact challenger
---
 scripts/run_paper_sleeve_spawner.py | 14 ++++++++++++++
 1 file changed, 14 insertions(+)

diff --git a/scripts/run_paper_sleeve_spawner.py b/scripts/run_paper_sleeve_spawner.py
index 90310e8..9297b31 100644
--- a/scripts/run_paper_sleeve_spawner.py
+++ b/scripts/run_paper_sleeve_spawner.py
@@ -330,6 +330,20 @@ def run(root: Path, cohort: dict[str, Any] | None = None,
                 else virtual.get("m_concurrent") or 0))
 
     decision = decide(parsed["candidates"], standing, virtual, book_usd)
+    # A virtual displacement may only fund ITS OWN challenger. Otherwise a higher-ranked,
+    # unrelated candidate can consume the virtual seat while the outgoing clock remains live.
+    actual = decide(parsed["candidates"], standing, cohort, book_usd)
+    real_free = int(actual["free_slots"])
+    lawful_spawn = []
+    for candidate in decision["spawn"]:
+        if real_free > 0:
+            lawful_spawn.append(candidate)
+            real_free -= 1
+        elif candidate.name in by_candidate:
+            lawful_spawn.append(candidate)
+        else:
+            decision["queue"].append(candidate)
+    decision["spawn"] = lawful_spawn
     out["free_slots"], out["why_free"] = decision["free_slots"], decision["why_free"]
     out["duplicates"] = decision["duplicates"]
     out["order_law"] = decision["order_law"]
```


---

## 70cb8b5 kimi hunter: naming a territory is not hunting it
kimi_hunter stamped EVERY territory its model named into hunt_coverage.json,
then excluded everything in that file for 45 days as "ALREADY HUNTED -- do NOT
return, they are picked over".

Its Wave 1 is mapping only. `if w == 1: continue` -- findings are not even
permitted on that wave. So the ground the mapping wave had just judged most
interesting was locked out for 45 days BEFORE ANY HUNT RAN AGAINST IT, and the
coverage file recorded that as progress. Anything paywalled, rate-limited or
without a transcript was written identically to something mined out: "we could
not get in" and "there is nothing left here" were the same mark.

libs/research/hunt_frontier.py keeps four states apart:

    YIELDED     hunted, produced findings          -> picked over, exclude
    EMPTY       hunted, nothing there              -> picked over, exclude
                                                      (real negative knowledge)
    NAMED_ONLY  named by mapping, never hunted     -> FRONTIER, chase first
    BLOCKED     attempted, could not complete      -> FRONTIER, retry after 10d

The prompt now LEADS with "HUNT THESE FIRST -- known frontier, already
identified and never mined", ahead of anything new. A blocker is a fact about a
moment, not about a territory, so BLOCKED resurfaces rather than expiring into
silence -- nothing else was ever going back for it.

THE FREE GATE. should_hunt() reads local state and decides whether to fire with
NO model call, skipping only when every territory is genuinely mined and
nothing is blocked or unhunted. An empty file always hunts, so run #1 still
bootstraps -- a gate that refused on no evidence would guarantee the file
stayed empty forever. That is where the spend goes: a hunter on a 3-hourly
clock pays a full 16k reasoning pass to discover the world has not changed,
when a file on disk already knew.

MIGRATION IS THE LOAD-BEARING PART. The existing coverage file carries only
`first_seen` -- no outcome, because outcomes were never tracked -- so legacy
records migrate as NAMED_ONLY, never as covered. Reading them as mined would
carry the bug forward across the whole history while looking like a clean
upgrade. Practical effect: on the next run every territory kimi has ever named
becomes priority frontier, so expect the first runs to be busy rather than
cheap. That is a backlog being worked, not a regression.

Caught the same conflation in my own output and fixed it: a territory blocked
ten minutes ago was landing in the "ALREADY MINED" list. Blocked-and-cooling
now gets its own section saying "skip THIS run only, they are not mined" --
the prompt is where a wrong label actually changes behaviour.

Removed _load_coverage and _exclusion_text rather than leaving them dead; the
old logic sitting next to the fix is how the bug returns.

gpt_hunter is UNTOUCHED, per instruction. It is also Codex's file on the VPS
branch, so this change carries no merge coupling.

20 tests. ruff and mypy clean over 504 files. The only tests exercising the
changed code are the new ones; the two other files mentioning kimi_hunter scan
ops/ prompt text and not this script. Full suite running at commit time.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 70cb8b53cf1e63be3e3261e741734b12ea1aa550
Author: Claude <noreply@anthropic.com>
Date:   Sun Aug 9 11:31:02 2026 +0000

    kimi hunter: naming a territory is not hunting it
    
    kimi_hunter stamped EVERY territory its model named into hunt_coverage.json,
    then excluded everything in that file for 45 days as "ALREADY HUNTED -- do NOT
    return, they are picked over".
    
    Its Wave 1 is mapping only. `if w == 1: continue` -- findings are not even
    permitted on that wave. So the ground the mapping wave had just judged most
    interesting was locked out for 45 days BEFORE ANY HUNT RAN AGAINST IT, and the
    coverage file recorded that as progress. Anything paywalled, rate-limited or
    without a transcript was written identically to something mined out: "we could
    not get in" and "there is nothing left here" were the same mark.
    
    libs/research/hunt_frontier.py keeps four states apart:
    
        YIELDED     hunted, produced findings          -> picked over, exclude
        EMPTY       hunted, nothing there              -> picked over, exclude
                                                          (real negative knowledge)
        NAMED_ONLY  named by mapping, never hunted     -> FRONTIER, chase first
        BLOCKED     attempted, could not complete      -> FRONTIER, retry after 10d
    
    The prompt now LEADS with "HUNT THESE FIRST -- known frontier, already
    identified and never mined", ahead of anything new. A blocker is a fact about a
    moment, not about a territory, so BLOCKED resurfaces rather than expiring into
    silence -- nothing else was ever going back for it.
    
    THE FREE GATE. should_hunt() reads local state and decides whether to fire with
    NO model call, skipping only when every territory is genuinely mined and
    nothing is blocked or unhunted. An empty file always hunts, so run #1 still
    bootstraps -- a gate that refused on no evidence would guarantee the file
    stayed empty forever. That is where the spend goes: a hunter on a 3-hourly
    clock pays a full 16k reasoning pass to discover the world has not changed,
    when a file on disk already knew.
    
    MIGRATION IS THE LOAD-BEARING PART. The existing coverage file carries only
    `first_seen` -- no outcome, because outcomes were never tracked -- so legacy
    records migrate as NAMED_ONLY, never as covered. Reading them as mined would
    carry the bug forward across the whole history while looking like a clean
    upgrade. Practical effect: on the next run every territory kimi has ever named
    becomes priority frontier, so expect the first runs to be busy rather than
    cheap. That is a backlog being worked, not a regression.
    
    Caught the same conflation in my own output and fixed it: a territory blocked
    ten minutes ago was landing in the "ALREADY MINED" list. Blocked-and-cooling
    now gets its own section saying "skip THIS run only, they are not mined" --
    the prompt is where a wrong label actually changes behaviour.
    
    Removed _load_coverage and _exclusion_text rather than leaving them dead; the
    old logic sitting next to the fix is how the bug returns.
    
    gpt_hunter is UNTOUCHED, per instruction. It is also Codex's file on the VPS
    branch, so this change carries no merge coupling.
    
    20 tests. ruff and mypy clean over 504 files. The only tests exercising the
    changed code are the new ones; the two other files mentioning kimi_hunter scan
    ops/ prompt text and not this script. Full suite running at commit time.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 libs/research/hunt_frontier.py       | 316 +++++++++++++++++++++++++++++++++++
 scripts/kimi_hunter.py               |  93 ++++++-----
 tests/research/test_hunt_frontier.py | 204 ++++++++++++++++++++++
 3 files changed, 569 insertions(+), 44 deletions(-)

diff --git a/libs/research/hunt_frontier.py b/libs/research/hunt_frontier.py
new file mode 100644
index 0000000..804265d
--- /dev/null
+++ b/libs/research/hunt_frontier.py
@@ -0,0 +1,316 @@
+"""HUNT FRONTIER — what has actually been mined, what was only NAMED, and what was MISSED.
+
+THE DEFECT THIS REMOVES, and it is the expensive kind because it looks like discipline.
+`kimi_hunter` recorded every territory its model NAMED into a coverage file, then excluded
+everything in that file from the next 45 days of hunting. The exclusion text is emphatic --
+*"ALREADY HUNTED -- do NOT return to these, they are picked over"* -- and for a territory that was
+genuinely mined, it is right.
+
+But three different things were all being stamped with the same mark:
+
+    YIELDED       hunted, and it produced findings. Genuinely picked over.
+    EMPTY         hunted, and there was nothing there. Real negative knowledge; also done.
+    NAMED_ONLY    the mapping wave named it and no hunt ever ran. NOT hunted.
+    BLOCKED       a hunt was attempted and could not complete -- paywall, no transcript, dead
+                  link, rate limit. NOT hunted, and the reason may not last.
+
+`kimi_hunter`'s Wave 1 is mapping only (`if w == 1: continue` -- findings are not even permitted),
+so **every territory the mapping wave identified was locked out for 45 days before it was ever
+hunted.** The organ was systematically excluded from exactly the ground it had just judged most
+interesting, and the coverage file recorded that as progress.
+
+**THE FRONTIER IS THE INVERSE OF COVERAGE, AND IT IS THE THING WORTH SPENDING ON.** A hunt that
+returns to picked-over ground wastes a reasoning pass; a hunt that never returns to BLOCKED ground
+loses the finding permanently, because nothing else will ever go back for it. So NAMED_ONLY and
+BLOCKED are not exclusions -- they are the priority queue, surfaced ahead of anything new.
+
+**AND IT ANSWERS "SHOULD WE RUN AT ALL" FOR FREE.** `should_hunt` reads local state and decides
+whether frontier exists, with no model call. That is the whole saving: a hunter firing every three
+hours pays a full reasoning pass to discover that the world has not changed, when a file on disk
+already knew.
+
+Pure state accounting. Calls nothing, fetches nothing, and never decides what a hunter concludes.
+"""
+
+from __future__ import annotations
+
+import json
+from dataclasses import dataclass, field
+from datetime import UTC, datetime
+from pathlib import Path
+from typing import Any
+
+__all__ = [
+    "BLOCKED_RETRY_D",
+    "OUTCOMES",
+    "Vector",
+    "VectorState",
+    "frontier",
+    "load",
+    "prompt_sections",
+    "record",
+    "save",
+    "should_hunt",
+    "summarise",
+]
+
+#: What a hunt against one territory actually achieved. Ordered least to most conclusive.
+OUTCOMES: tuple[str, ...] = (
+    "NAMED_ONLY",   # a mapping wave named it; no hunt has run. NOT covered.
+    "BLOCKED",      # hunted and could not complete. NOT covered, and the blocker may lift.
+    "EMPTY",        # hunted, nothing there. Covered -- this is real negative knowledge.
+    "YIELDED",      # hunted, produced findings. Covered.
+)
+
+#: A blocker is a fact about a moment, not about a territory. Paywalls lapse, transcripts appear,
+#: rate limits reset. Long enough not to thrash, short enough that a lifted blocker is noticed.
+BLOCKED_RETRY_D: int = 10
+
+#: Default cooldown for genuinely covered ground. Callers pass their own; kimi_hunter uses 45.
+COVERED_COOLDOWN_D: int = 45
+
+
+@dataclass(frozen=True)
+class Vector:
+    """One named territory and everything known about hunting it."""
+
+    name: str
+    outcome: str = "NAMED_ONLY"
+    first_seen: str = ""
+    last_attempt: str = ""
+    attempts: int = 0
+    findings: int = 0
+    blocker: str = ""
+
+    def __post_init__(self) -> None:
+        if self.outcome not in OUTCOMES:
+            raise ValueError(f"unknown outcome {self.outcome!r}; expected one of {OUTCOMES}")
+
+    @property
+    def covered(self) -> bool:
+        """Only a completed hunt covers ground. Naming it does not; failing to reach it does not."""
+        return self.outcome in ("YIELDED", "EMPTY")
+
+    def _age_days(self, stamp: str, now: datetime) -> float | None:
+        if not stamp:
+            return None
+        try:
+            return (now - datetime.fromisoformat(stamp)).total_seconds() / 86400.0
+        except ValueError:
+            return None
+
+    def huntable(self, now: datetime, *, cooldown_d: int = COVERED_COOLDOWN_D) -> tuple[bool, str]:
+        """(may hunt now, why). UNKNOWN AGES ARE HUNTABLE, deliberately.
+
+        An unparseable timestamp means the record is damaged, and the safe direction for damaged
+        coverage is to allow the hunt: re-hunting known ground costs one pass, while wrongly
+        excluding live frontier costs the finding permanently and silently.
+        """
+        if self.outcome == "NAMED_ONLY":
+            return True, f"{self.name}: NAMED but never hunted -- this is frontier, not coverage"
+        if self.outcome == "BLOCKED":
+            age = self._age_days(self.last_attempt, now)
+            if age is None or age >= BLOCKED_RETRY_D:
+                return True, (f"{self.name}: BLOCKED"
+                              + (f" ({self.blocker})" if self.blocker else "")
+                              + f", last tried {'unknown' if age is None else f'{age:.0f}d'} ago "
+                                "-- a blocker is a fact about a moment, not about the territory")
+            return False, (f"{self.name}: BLOCKED {age:.0f}d ago, retry at {BLOCKED_RETRY_D}d")
+        age = self._age_days(self.last_attempt or self.first_seen, now)
+        if age is None:
+            return True, (f"{self.name}: timestamp unreadable -- allowing the hunt. Re-hunting "
+                          "known ground costs one pass; wrongly excluding live frontier costs "
+                          "the finding permanently and silently")
+        if age >= cooldown_d:
+            return True, (f"{self.name}: {self.outcome} {age:.0f}d ago, past the "
+                          f"{cooldown_d}d cooldown")
+        return False, f"{self.name}: {self.outcome} {age:.0f}d ago -- picked over"
+
+
+@dataclass
+class VectorState:
+    """The whole coverage file, migrated and outcome-aware."""
+
+    vectors: dict[str, Vector] = field(default_factory=dict)
+    note: str = ""
+
+    def upsert(self, v: Vector) -> None:
+        self.vectors[v.name] = v
+
+
+def load(path: Path | str) -> VectorState:
+    """Read coverage, MIGRATING the legacy `{name: {first_seen}}` shape.
+
+    Legacy records carry no outcome, and the honest reading of "somebody wrote this name down and
+    recorded nothing else" is NAMED_ONLY -- not YIELDED. Migrating them as covered would preserve
+    the exact bug this module exists to remove, on the entire existing history.
+    """
+    p = Path(path)
+    try:
+        blob = json.loads(p.read_text("utf-8"))
+    except (OSError, ValueError):
+        return VectorState()
+    out = VectorState(note=str(blob.get("note", "")))
+    for name, rec in (blob.get("vectors") or {}).items():
+        if not isinstance(rec, dict):
+            continue
+        out.upsert(Vector(
+            name=str(name),
+            outcome=str(rec.get("outcome") or "NAMED_ONLY"),
+            first_seen=str(rec.get("first_seen") or ""),
+            last_attempt=str(rec.get("last_attempt") or ""),
+            attempts=int(rec.get("attempts") or 0),
+            findings=int(rec.get("findings") or 0),
+            blocker=str(rec.get("blocker") or ""),
+        ))
+    return out
+
+
+def save(state: VectorState, path: Path | str) -> None:
+    p = Path(path)
+    p.parent.mkdir(parents=True, exist_ok=True)
+    p.write_text(json.dumps({
+        "updated": datetime.now(tz=UTC).isoformat(),
+        "vectors": {n: {"outcome": v.outcome, "first_seen": v.first_seen,
+                        "last_attempt": v.last_attempt, "attempts": v.attempts,
+                        "findings": v.findings, "blocker": v.blocker}
+                    for n, v in sorted(state.vectors.items())},
+        "note": ("NAMED_ONLY and BLOCKED are FRONTIER, not coverage -- they are surfaced to the "
+                 "hunter as priority targets, never as exclusions. Only YIELDED and EMPTY are "
+                 "picked-over ground. A mapping wave that names a territory has not hunted it."),
+    }, indent=1), "utf-8")
+
+
+def record(state: VectorState, name: str, *, outcome: str, findings: int = 0,
+           blocker: str = "") -> Vector:
+    """Record the RESULT of a hunt, not merely that a name was uttered."""
+    now = datetime.now(tz=UTC).isoformat()
+    prev = state.vectors.get(name)
+    v = Vector(
+        name=name, outcome=outcome,
+        first_seen=(prev.first_seen if prev and prev.first_seen else now),
+        last_attempt=(now if outcome != "NAMED_ONLY" else (prev.last_attempt if prev else "")),
+        attempts=(prev.attempts if prev else 0) + (0 if outcome == "NAMED_ONLY" else 1),
+        findings=(prev.findings if prev else 0) + max(0, findings),
+        blocker=blocker,
+    )
+    state.upsert(v)
+    return v
+
+
+def frontier(state: VectorState, *, now: datetime | None = None,
+             cooldown_d: int = COVERED_COOLDOWN_D) -> dict[str, list[Vector]]:
+    """Split the world into what is worth hunting and what is not."""
+    n = now or datetime.now(tz=UTC)
+    unhunted, blocked, ready, picked = [], [], [], []
+    for v in state.vectors.values():
+        ok, _ = v.huntable(n, cooldown_d=cooldown_d)
+        if not ok:
+            picked.append(v)
+        elif v.outcome == "NAMED_ONLY":
+            unhunted.append(v)
+        elif v.outcome == "BLOCKED":
+            blocked.append(v)
+        else:
+            ready.append(v)
+    return {"unhunted": unhunted, "blocked": blocked, "ready": ready, "picked_over": picked}
+
+
+def should_hunt(state: VectorState, *, now: datetime | None = None,
+                cooldown_d: int = COVERED_COOLDOWN_D,
+                min_frontier: int = 1) -> tuple[bool, str]:
+    """THE FREE GATE. Decide whether an expensive pass is worth firing, with no model call.
+
+    AN EMPTY COVERAGE FILE ALWAYS HUNTS. Run #1 has no history and must bootstrap; a gate that
+    refused on no evidence would ensure it never acquired any.
+
+    Returns False only when every known territory is genuinely picked over AND nothing is blocked
+    or unhunted -- the one state where a reasoning pass can be predicted to rediscover what the
+    desk already has.
+    """
+    n = now or datetime.now(tz=UTC)
+    if not state.vectors:
+        return True, ("no hunt history -- run #1 bootstraps. A gate that refused here would "
+                      "guarantee the file stayed empty forever")
+    f = frontier(state, now=n, cooldown_d=cooldown_d)
+    live = len(f["unhunted"]) + len(f["blocked"]) + len(f["ready"])
+    if live >= min_frontier:
+        return True, (
+            f"{live} territory/territories open: {len(f['unhunted'])} NAMED-but-never-hunted, "
+            f"{len(f['blocked'])} BLOCKED past retry, {len(f['ready'])} off cooldown. "
+            f"{len(f['picked_over'])} genuinely picked over")
+    soonest = None
+    for v in f["picked_over"]:
+        age = v._age_days(v.last_attempt or v.first_seen, n)
+        if age is not None:
+            d = cooldown_d - age
+            soonest = d if soonest is None else min(soonest, d)
+    return False, (
+        f"all {len(f['picked_over'])} known territory/territories are picked over and nothing is "
+        "blocked or unhunted -- a reasoning pass now would rediscover what the desk already has"
+        + (f". Next opens in {soonest:.0f}d" if soonest is not None else ""))
+
+
+def prompt_sections(state: VectorState, *, now: datetime | None = None,
+                    cooldown_d: int = COVERED_COOLDOWN_D, limit: int = 40) -> dict[str, str]:
+    """Text for the hunter: what to CHASE first, and what to avoid.
+
+    The priority block is the change that matters. Previously every named territory became an
+    exclusion, so ground the mapping wave had just flagged as interesting was buried for the full
+    cooldown. Now it is the first thing the hunter is pointed at.
+    """
+    n = now or datetime.now(tz=UTC)
+    f = frontier(state, now=n, cooldown_d=cooldown_d)
+    chase: list[str] = []
+    for v in f["unhunted"][:limit]:
+        chase.append(f"{v.name} -- NAMED by a previous mapping wave and NEVER hunted")
+    for v in f["blocked"][:limit]:
+        chase.append(f"{v.name} -- BLOCKED previously"
+                     + (f" ({v.blocker})" if v.blocker else "")
+                     + f", {v.attempts} attempt(s); the blocker may have lifted")
+    # A BLOCKED TERRITORY IS NOT PICKED OVER, EVEN INSIDE ITS RETRY WINDOW. Telling the model it
+    # is "already mined" is the same conflation this module removes, just relocated into the
+    # prompt -- and prompts are where a wrong label actually changes behaviour.
+    mined = [f"{v.name} ({v.outcome.lower()}, {v.findings} finding(s))"
+             for v in f["picked_over"] if v.covered]
+    cooling = [f"{v.name} (blocked{': ' + v.blocker if v.blocker else ''}, retry pending)"
+               for v in f["picked_over"] if not v.covered]
+    avoid = mined
+    priority = ("HUNT THESE FIRST -- known frontier, already identified and never mined:\n  "
+                + "\n  ".join(chase)
+                + "\n\nThese are not suggestions to consider; they are ground this desk has "
+                  "already judged interesting and never reached. Exhaust them before generating "
+                  "new vectors."
+                if chase else
+                "No known unhunted or blocked territory. Generate NEW vectors -- name the "
+                "territories yourself and say why the herd cannot see them.")
+    exclude = ("ALREADY MINED -- do NOT return, they are picked over:\n  " + "\n  ".join(avoid)
+               if avoid else "")
+    if cooling:
+        exclude += (("\n\n" if exclude else "")
+                    + "BLOCKED AND RETRIED RECENTLY -- skip THIS run only, they are not mined:\n  "
+                    + "\n  ".join(cooling))
+    return {"priority": priority, "exclude": exclude,
+            "counts": (f"{len(f['unhunted'])} unhunted, {len(f['blocked'])} blocked, "
+                       f"{len(f['ready'])} off-cooldown, {len(f['picked_over'])} picked over")}
+
+
+def summarise(state: VectorState, *, cooldown_d: int = COVERED_COOLDOWN_D) -> dict[str, Any]:
+    """Report shape."""
+    f = frontier(state, cooldown_d=cooldown_d)
+    go, why = should_hunt(state, cooldown_d=cooldown_d)
+    yielded = [v for v in state.vectors.values() if v.outcome == "YIELDED"]
+    return {
+        "vectors": len(state.vectors),
+        "unhunted": len(f["unhunted"]), "blocked": len(f["blocked"]),
+        "off_cooldown": len(f["ready"]), "picked_over": len(f["picked_over"]),
+        "total_findings": sum(v.findings for v in state.vectors.values()),
+        "yield_rate": (round(len(yielded) / len(state.vectors), 3) if state.vectors else None),
+        "should_hunt": go, "why": why,
+        "headline": (
+            f"{len(f['unhunted'])} territory/territories NAMED and never hunted, "
+            f"{len(f['blocked'])} blocked past retry. {why}"),
+        "note": ("Naming a territory is not hunting it and failing to reach one is not covering "
+                 "it. Only YIELDED and EMPTY are picked-over ground; NAMED_ONLY and BLOCKED are "
+                 "the priority queue, because nothing else will ever go back for them."),
+    }
diff --git a/scripts/kimi_hunter.py b/scripts/kimi_hunter.py
index 275f4dc..afdd47b 100644
--- a/scripts/kimi_hunter.py
+++ b/scripts/kimi_hunter.py
@@ -41,6 +41,7 @@ if str(ROOT) not in sys.path:
     sys.path.insert(0, str(ROOT))
 
 from libs.llm.effort import reasoning_payload  # noqa: E402
+from libs.research import hunt_frontier as hf  # noqa: E402
```


---

## 40c0777 unify frontier research and wire truthful shadow evidence

```diff
commit 40c0777bf557a1ec6f3701ff4866a5ccc2ca35a0
Merge: 447bc61 51e4c84
Author: Codex <codex@openai.local>
Date:   Sun Aug 9 12:29:46 2026 +0100

    unify frontier research and wire truthful shadow evidence

 .github/workflows/ci.yml                           |    7 +
 .gitignore                                         |   84 +-
 .../sor_research.sqlite                            |    0
 .../sor_research.sqlite                            |    0
 .../test_cycle_skips_redundant_hyp0/sor.sqlite     |  Bin 0 -> 303104 bytes
 .../sor_research.sqlite                            |    0
 .../test_niche_hunt_is_silent0/sor_research.sqlite |    0
 .../sor_research.sqlite                            |    0
 .../sor_research.sqlite                            |    0
 .../test_cycle_skips_redundant_hyp0/sor.sqlite     |  Bin 0 -> 303104 bytes
 .../test_cycle_without_a_gate_is_u0/sor.sqlite     |  Bin 0 -> 303104 bytes
 .../test_every_suppression_is_name0/sor.sqlite     |  Bin 0 -> 303104 bytes
 .../sor_research.sqlite                            |    0
 .../sor_research.sqlite                            |    0
 .../sor_research.sqlite                            |    0
 .../sor_research.sqlite                            |    0
 .../test_niche_hunt_is_silent0/sor_research.sqlite |    0
 .../sor_research.sqlite                            |    0
 .../sor_research.sqlite                            |    0
 alpha_pipeline.json                                |   42 +-
 config/desk_costs.yaml                             |   30 +
 data/CAPABILITY_RATCHET.json                       | 1471 +++++
 data/bybit_archive_retention.json                  |   34 +
 data/cashcarry_config.json                         |   10 +-
 data/cot_screen_summary.json                       |  233 +
 data/decision_ledger.json                          | 6487 +++++++++++---------
 data/event_calendar.json                           |  141 +
 data/mutation_score.json                           | 3641 +++++++++--
 data/nav_attestation.jsonl                         |    8 +
 data/ratchet_floors.json                           |  164 +-
 data/unlock_event_screen.json                      |  319 +
 deploy/README.md                                   |   35 +
 deploy/finish_setup.sh                             |  106 +
 deploy/git_hooks/pre-push                          |   30 +-
 deploy/pull_deploy.sh                              |  155 +-
 deploy/reconstitute_cron.sh                        |  145 +
 docs/CONSTITUTION.md                               |  590 ++
 docs/CYCLE_20260729_CLOSURE.md                     |  115 +
 docs/DESK_BRIEF.md                                 |   40 +-
 docs/DIGGING_CHARTER.md                            |  147 +-
 docs/EXECUTION_QUEUE.md                            |  228 +
 docs/GAP_REGISTER.md                               |  513 +-
 docs/GATE0_QUEUE.md                                |   12 +
 docs/LIVE_CONNECTOR_SPEC.md                        |   28 +
 docs/POST_GATE0_MANIFEST.md                        |   28 +-
 docs/PRINCIPAL_ACTION.md                           |    3 +
 docs/WEEKLY_MAX_CYCLE.md                           |   44 +
 .../binance_spot_testnet.py.bak-20260716           |  169 +
 .../binance_testnet.py.bak-20260716                |  273 +
 .../daily_research_cycle.py.bak-20260716           |  106 +
 .../run_alerts.py.bak-20260716                     |  120 +
 .../run_cashcarry_executor.py.bak-20260716         |  634 ++
 docs/desk_digest.md                                |  216 +-
 docs/desk_lessons.jsonl                            |   93 +
 docs/graveyard.md                                  |  268 +-
 docs/institutional_knowledge.md                    |  304 +-
 docs/research/ADVERSARIAL_REVIEW_RUBRIC.md         |   97 +
 docs/research/AXIS_PREREGISTRATIONS.md             |   46 +
 docs/research/BITMEX_DECADE_INGEST_SPEC.md         |   80 +
 docs/research/CONSTITUTION_RATCHET.json            |  122 +-
 docs/research/COT_SCREEN_RESULT.md                 |  129 +
 docs/research/CRO_BRIEFING.md                      |  193 +
 docs/research/DATA_UNIVERSE_TAXONOMY.md            |  102 +
 .../DISCRETIONARY_PLAYBOOK_PREREGISTRATION.md      |   69 +
 docs/research/HYPOTHESIS_MAX_SPEC.md               |   53 +
 docs/research/INTRADAY_ROTATION_PREREGISTRATION.md |   66 +
 docs/research/INTRADAY_ROTATION_RESULT.md          |   79 +
 docs/research/MECHANISM_GRAPH.md                   |   94 +
 docs/research/MUTATION_BASELINE.md                 |  133 +
 .../NEW_FAMILY_GENERATORS_PREREGISTRATION.md       |  105 +
 docs/research/OPERATING_DOCTRINE.md                |   15 +
 docs/research/PERMUTATION_NULL_RESULT.md           |  191 +
 docs/research/PREMORTEM_20260805.md                |  235 +
 docs/research/PROMPT_RATCHET.json                  |  523 ++
 docs/research/PROMPT_RATCHET_WAIVERS.json          |   12 +
 docs/research/PROSPECTOR_SPEC.md                   |   20 +-
 docs/research/REALITY_CHECK_POWER.md               |  135 +
 docs/research/SUBSYSTEM_TRIAGE.md                  |    2 +-
 docs/research/TRIAGE_20260729_PRINCIPAL_BATCH.md   |   64 +
 docs/research/TRIAGE_ADDENDUM.md                   |    2 +-
 docs/research/VPS_STATE_20260805.md                |   80 +
 docs/research/absorbing_kelly_study.json           |  297 +
 docs/research/alpha_hunt_20260731.md               |  122 +
 docs/research/axis_generation_20260805.md          |   94 +
 docs/research/blind_rediscovery_log.md             |  776 +++
 docs/research/cadence_duties.md                    |    5 +
 docs/research/capability_hunt/20260731_prompts.txt |   77 +
 .../capability_hunt/20260731_s1_prompts.txt        |   87 +
 .../capability_hunt/20260731_s2_proposals.md       |   12 +
 docs/research/capability_hunt/20260731_s5_hunt.md  |  130 +
 .../capability_hunt/20260731_s5_proposals.md       |   83 +
 docs/research/capability_hunt/20260801_s0_hunt.md  |  215 +
 .../capability_hunt/20260801_s0_proposals.md       |  119 +
 docs/research/capability_hunt/20260801_s1_hunt.md  |  140 +
 .../capability_hunt/20260801_s1_proposals.md       |   89 +
 .../capability_hunt/20260801_s2_proposals.md       |   12 +
 docs/research/capability_hunt/20260801_s3_hunt.md  |  185 +
 .../capability_hunt/20260801_s3_proposals.md       |   44 +
 docs/research/capability_hunt/20260801_s4_hunt.md  |  225 +
 .../capability_hunt/20260801_s4_proposals.md       |   97 +
 .../capability_hunt/20260801_s5_proposals.md       |   95 +
 .../capability_hunt/20260802_s3_proposals.md       |   12 +
 .../capability_hunt/20260802_s4_proposals.md       |   12 +
 docs/research/capability_hunt/20260805_s1_hunt.md  |  290 +
 .../capability_hunt/20260805_s1_proposals.md       |  106 +
 docs/research/capability_hunt/20260805_s2_hunt.md  |  162 +
 .../capability_hunt/20260805_s2_proposals.md       |   81 +
 .../capability_hunt/20260805_s4_proposals.md       |   12 +
 docs/research/capability_hunt/20260805_s5_hunt.md  |  201 +
 .../capability_hunt/20260805_s5_proposals.md       |   47 +
 .../capability_hunt/20260806_s0_proposals.md       |   12 +
 .../capability_hunt/20260806_s1_proposals.md       |   12 +
 .../capability_hunt/20260806_s2_proposals.md       |   12 +
 .../capability_hunt/20260806_s3_proposals.md       |  107 +
 .../capability_hunt/20260806_s4_proposals.md       |   12 +
 .../capability_hunt/20260806_s5_proposals.md       |   12 +
 .../capability_hunt/20260807_s3_proposals.md       |   12 +
 docs/research/cn_oss_extraction_20260731.md        |  115 +
 docs/research/conversion_record.json               |   12 +-
 docs/research/data_axis_watchlist.md               |  680 ++
 docs/research/deep_review_inbox.md                 | 2577 ++++++++
 .../deep_sweep/20260728_alpha-discovery.md         |  577 ++
 .../deep_sweep/20260728_data-intelligence.md       |  315 +
 docs/research/deep_sweep/20260728_data-moat.md     |   57 +
 .../deep_sweep/20260728_execution-growth.md        |   10 +
 .../research/deep_sweep/20260728_infrastructure.md |   10 +
 .../deep_sweep/20260728_meta-and-blindspots.md     |   10 +
 .../deep_sweep/20260728_research-engine.md         |   10 +
 .../deep_sweep/20260728_validation-stats.md        |   10 +
 docs/research/deep_sweep/20260729_SYNTHESIS.md     |  113 +
 .../deep_sweep/20260729_alpha-discovery.md         |  479 ++
 .../deep_sweep/20260729_data-intelligence.md       |  344 ++
 docs/research/deep_sweep/20260729_data-moat.md     |  449 ++
 .../deep_sweep/20260729_execution-growth.md        |   57 +
 .../research/deep_sweep/20260729_infrastructure.md |  351 ++
 .../deep_sweep/20260729_meta-and-blindspots.md     |  348 ++
 .../deep_sweep/20260729_research-engine.md         |   74 +
 .../deep_sweep/20260729_validation-stats.md        |  444 ++
 docs/research/deep_sweep/20260730_SYNTHESIS.md     |  559 ++
 .../deep_sweep/20260730_alpha-discovery.md         |   54 +
 .../deep_sweep/20260730_data-intelligence.md       | 1681 +++++
 docs/research/deep_sweep/20260730_data-moat.md     |  828 +++
 .../deep_sweep/20260730_execution-growth.md        |  686 +++
 .../research/deep_sweep/20260730_infrastructure.md | 1630 +++++
 .../deep_sweep/20260730_meta-and-blindspots.md     |  236 +
 .../deep_sweep/20260730_research-engine.md         | 1831 ++++++
 .../deep_sweep/20260730_validation-stats.md        |   64 +
 docs/research/deep_sweep/20260731_SYNTHESIS.md     |  389 ++
 .../deep_sweep/20260731_alpha-discovery.md         |  589 ++
 .../deep_sweep/20260731_data-intelligence.md       |  455 ++
 docs/research/deep_sweep/20260731_data-moat.md     |  628 ++
 .../deep_sweep/20260731_execution-growth.md        |  390 ++
 .../research/deep_sweep/20260731_infrastructure.md |  154 +
 .../deep_sweep/20260731_launch-readiness.md        |  209 +
 .../deep_sweep/20260731_litC_ai_methods.md         |  276 +
 docs/research/deep_sweep/20260731_litE_buyside.md  |  503 ++
 .../deep_sweep/20260731_litE_official_sector.md    |  418 ++
 .../deep_sweep/20260731_meta-and-blindspots.md     |  444 ++
 .../deep_sweep/20260731_research-engine.md         |  320 +
 .../deep_sweep/20260731_validation-stats.md        |  602 ++
 docs/research/deep_sweep/20260801_SYNTHESIS.md     |  566 ++
 .../deep_sweep/20260801_alpha-discovery.md         | 1239 ++++
 .../deep_sweep/20260801_data-intelligence.md       | 1410 +++++
 docs/research/deep_sweep/20260801_data-moat.md     |  980 +++
 .../deep_sweep/20260801_execution-growth.md        |  965 +++
 .../research/deep_sweep/20260801_infrastructure.md | 1624 +++++
 .../deep_sweep/20260801_launch-readiness.md        | 1373 +++++
 .../deep_sweep/20260801_meta-and-blindspots.md     | 1049 ++++
 .../deep_sweep/20260801_research-engine.md         |  993 +++
 .../deep_sweep/20260801_validation-stats.md        | 1573 +++++
 .../research/deep_sweep/20260805_LIT_ai_methods.md |   51 +
 .../deep_sweep/20260805_LIT_arxiv_qfin_sweep.md    |   58 +
 .../20260805_LIT_backlog_verification.md           |  113 +
 .../deep_sweep/20260805_LIT_theses_layer.md        |   95 +
 .../deep_sweep/LIT_a_failed_replication.md         |   27 +-
 .../research/deep_sweep/LIT_d_nonenglish_theses.md |   23 +
 docs/research/deep_sweep/T1a_kaiko_verification.md |    2 +-
 docs/research/discovery_hypotheses.md              |  131 +
 docs/research/feed_inbox.md                        |   79 +-
 docs/research/findings_coverage_record.json        |   12 +-
 docs/research/gate_power_audit.md                  |  214 +
 docs/research/generation_due.md                    |   18 +
 docs/research/holdings_record.json                 |    4 +-
 docs/research/improvement_inbox.md                 |  575 ++
 docs/research/literature_coverage.md               |  220 +-
 docs/research/micro_audit_inbox.md                 |   97 +-
 docs/research/mining_record.json                   |   10 +-
 docs/research/negative_knowledge.md                |   32 +-
 docs/research/next_law_number.txt                  |    3 +
 docs/research/openmarket_corpus.json               |   59 +
 docs/research/paid_dataset_targets.md              |    6 +-
 docs/research/panel_inbox.md                       |  152 +-
 docs/research/panel_rulings.md                     |    1 +
 docs/research/prospector_coverage.md               | 2261 +++++++
 docs/research/prospector_watchlist.md              |   97 +
 docs/research/recommendation_ledger.json           | 6291 ++++++++++++++++---
 docs/research/search_operator_library.md           |  599 +-
 docs/research/self_interrogation_patterns.md       |   54 +
 docs/research/test_suite_record.json               |    4 +-
 docs/research/trade_forensics_latest.json          |   99 +
 docs/research/weak_signal_registry.md              |    5 +
 docs/research_conversions.jsonl                    |   14 +
 engineering_backlog.json                           |  160 +-
 libs/alpha_factory/__init__.py                     |    2 -
 libs/alpha_factory/alpha_factory_controller.py     |   96 +-
 libs/alpha_factory/capacity_intelligence.py        |   23 +-
 libs/autodiscovery/capacity_screen.py              |  158 +
 libs/autodiscovery/crypto_adapter.py               |   77 +-
 libs/autodiscovery/generators.py                   |  412 +-
 libs/autodiscovery/memory.py                       |  554 +-
 libs/autodiscovery/models.py                       |   11 +
 libs/autodiscovery/orchestrator.py                 |  347 +-
 libs/autodiscovery/reports.py                      |    6 +-
 libs/autodiscovery/research_roi.py                 |    5 +-
 libs/autodiscovery/validation.py                   |  832 ++-
 libs/core/secrets.py                               |    2 +-
 libs/data/bilibili.py                              |  250 +
 libs/data/cn_sources.py                            |  258 +
 libs/data/crypto_source.py                         |   67 +-
 libs/data/duckdb_client.py                         |    6 +-
 libs/data/foreign_sources.py                       |  826 +++
 libs/data/funding_caps.py                          |  175 +
 libs/data/lake.py                                  |   10 +-
 libs/data/multiexchange.py                         |   18 +-
 libs/data/papers.py                                |  280 +
 libs/data/paywall.py                               |  232 +
 libs/data/render_fetch.py                          |  223 +
 libs/data/source_promotion.py                      |  233 +
 libs/data/venue_http.py                            |   81 +
 libs/discovery/__init__.py                         |   99 +-
 libs/discovery/monte_carlo_survival.py             |   26 +
 libs/discovery/objective.py                        |   21 +-
 libs/doctrine/prompt_ratchet.py                    |  756 +++
 libs/execution/binance_live.py                     |   67 +-
 libs/execution/binance_spot_live.py                |   17 +-
 libs/execution/binance_testnet.py                  |   55 +-
 libs/execution/carry_accounting.py                 |  138 +-
 libs/execution/collateral.py                       |   14 +
 libs/execution/economics.py                        |  937 +++
 libs/execution/event_guard.py                      |  117 +
 libs/execution/execution_tape.py                   |   14 +-
 libs/execution/leg_modes.py                        |   75 +
 libs/execution/passive_impact.py                   |  416 ++
 libs/execution/staging.py                          |   24 +-
 libs/execution/sub_accounts.py                     |  172 +
 libs/llm/second_opinion.py                         |   77 +
 libs/ops/carryover.py                              |  263 +-
 libs/ops/denominator.py                            |  205 +
 libs/ops/deploy_plan.py                            |  256 +
 libs/ops/fence_exit.py                             |   90 +
 libs/ops/fresh.py                                  |   85 +-
 libs/ops/host_resources.py                         |  109 +
 libs/ops/input_provenance.py                       |  261 +
 libs/ops/law_police.py                             |  293 +
 libs/ops/llm_route.py                              |  123 +
 libs/ops/llm_seat.py                               |  558 ++
 libs/ops/principal_page.py                         |   86 +
 libs/ops/repair_mode.py                            |  259 +
 libs/ops/research_daemon.py                        |   12 +-
 libs/portfolio/concentration.py                    |  420 ++
 libs/portfolio/live_book.py                        |    5 +
 libs/regime/engine.py                              |   20 +-
 libs/research/alpha_economics.py                   |  181 +-
 libs/research/announcement_diffusion.py            |  825 +++
 libs/research/campaign_retention.py                |  194 +
 libs/research/capability_ratchet.py                | 2531 ++++++++
 libs/research/capacity_policy.py                   |   39 +-
 libs/research/cohort_independence.py               |  151 +
 libs/research/conversion_ledger.py                 |  188 +
 libs/research/conversion_max.py                    |  394 ++
 libs/research/cro_role.py                          |  851 +++
 libs/research/crowding.py                          |  189 +
 libs/research/data_registry.py                     |  579 +-
 libs/research/decision_review.py                   |  225 +
 libs/research/decline_value.py                     |  222 +
 libs/research/desk_coverage.py                     |  318 +
 libs/research/desk_economics.py                    |  155 +
 libs/research/desk_memory.py                       |  370 ++
 libs/research/dip_ladder.py                        |  171 +
 libs/research/dist_shift.py                        |  121 +
 libs/research/earnability.py                       |  239 +
 libs/research/event_density.py                     |  257 +
 libs/research/finding_registry.py                  |   44 +
 libs/research/idle_yield.py                        |  395 ++
 libs/research/intermarket.py                       |  199 +
 libs/research/intraday_rotation.py                 |  372 ++
 libs/research/liq_heatmap.py                       |  242 +
 libs/research/liquidation_brief.py                 |  166 +
 libs/research/listing_events.py                    |  200 +
 libs/research/mechanism_census.py                  | 1704 +++++
 libs/research/mine_conversion.py                   |  169 +-
 libs/research/moat_utilisation.py                  | 1506 +++++
 libs/research/natural_experiment.py                |  377 ++
 libs/research/operators.py                         |  570 ++
 libs/research/orderbook_state.py                   |  386 ++
 libs/research/overlays.py                          |  240 +
 libs/research/panel_diversity.py                   |  199 +
 libs/research/paper_sleeves.py                     |  492 ++
 libs/research/positioning.py                       |  186 +
 libs/research/pre_filter.py                        |  157 +
 libs/research/primary_market_flow.py               |  551 ++
 libs/research/promotion_history.py                 |  136 +
 libs/research/recommendation_forecast.py           |  168 +
 libs/research/regime_trend.py                      |  257 +
 libs/research/review_rubric.py                     |  144 +
 libs/research/screen_conversion.py                 |  515 ++
 libs/research/slot_admission.py                    |  259 +
 libs/research/slot_displacement.py                 |  261 +
 libs/research/slot_registry.py                     |  225 +-
 libs/research/source_alternatives.py               |  779 +++
 libs/research/source_health.py                     |  725 +++
 libs/research/survivor_panel.py                    |  410 ++
 libs/research/tail_funding.py                      |  164 +
 libs/research/transcript_candidates.py             |  322 +
 libs/research/unlock_supply_series.py              |  729 +++
 libs/research/upbit_data.py                        |  114 +
 libs/research/venue_subsidy.py                     |  559 ++
 libs/research/video_triage.py                      |  173 +
 libs/research/vol_risk_premium.py                  |  638 ++
 libs/research/volatility_signals.py                |  270 +
 libs/risk/capital_events.py                        |  122 +
 libs/risk/gate.py                                  |   16 +
 libs/risk/growth_leverage.py                       |    4 +-
 libs/risk/risk_controls.py                         |  488 +-
 libs/risk/sizing.py                                |   16 +-
 libs/risk/sleeve_allocation.py                     |  327 +
 libs/risk/vol_headroom.py                          |  205 +
 libs/self_improvement/adaptive_thresholds.py       |   32 +
 libs/self_improvement/forecast_calibration.py      |  286 +-
 libs/testing/__init__.py                           |    0
 libs/testing/equivalent_mutants.py                 |  144 +
 libs/validation/admission_power.py                 |  253 +
 libs/validation/bar_permutation.py                 |  258 +
 libs/validation/brain_calibration.py               |  560 ++
 libs/validation/campaign_design.py                 |  325 +
 libs/validation/campaign_window.py                 |  333 +
 libs/validation/drawdown_metrics.py                |  148 +
 libs/validation/ensemble_gate.py                   |  726 +++
 libs/validation/event_study.py                     |  187 +
 libs/validation/forward_stats.py                   |   24 +-
 libs/validation/lookahead_audit.py                 |  207 +
 libs/validation/near_miss.py                       |  679 ++
 libs/validation/pbo.py                             |  137 +-
 libs/validation/random_baseline.py                 |  201 +
 libs/validation/reject_rescore.py                  |   17 +-
 libs/validation/revalidation.py                    |   32 +
 libs/validation/robustness_filters.py              |  165 +
 libs/validation/screen_admission.py                |  369 ++
 libs/validation/screen_select.py                   |  176 +
 libs/validation/stepwise.py                        |  224 +
 libs/validation/type2_cost.py                      |  718 +++
 migrations/__init__.py                             |    2 +
 migrations/m0007_candidate_returns.py              |   75 +
 ops/CRO_CONSTITUTION.md                            |    2 +-
 ops/blindrediscovery_dig_prompt.txt                |    1 +
 ops/brain_env.sh                                   |  150 +-
 ops/crontab.manifest                               |  969 ++-
 ops/crontab.research.manifest                      |   83 +
 ops/deploy_vps.sh                                  |   89 +-
 ops/memory/MEMORY.md                               |   14 +-
 ops/memory/institutional-constitution.md           |   15 +
 ops/principal_doctrine.txt                         |  262 +-
 ops/quant-frontier.service                         |   12 +
 ops/run_blindrediscovery_dig.sh                    |    1 +
 ops/run_cro_ai.sh                                  |    3 +-
 ops/run_dataaxis_dig.sh                            |    1 +
 ops/run_deep_sweep.sh                              |    1 +
 ops/run_frontier_miner.sh                          |   13 +-
 ops/run_litminer_dig.sh                            |    1 +
 ops/run_prospector_dig.sh                          |    1 +
 ops/run_recommendation_worker.sh                   |    9 +-
 ops/run_research_cycle.sh                          |    7 +
 prompts/external_panel_prompt.txt                  |   63 +
 prompts/panel_missions/audit.txt                   |   35 +-
 prompts/panel_missions/benchmark.txt               |   30 +-
 prompts/panel_missions/commit_audit.txt            |   58 +
 prompts/panel_missions/data.txt                    |   35 +-
 prompts/panel_missions/generate.txt                |   35 +-
 prompts/panel_missions/maximization.txt            |   14 +
 prompts/panel_missions/micro.txt                   |   30 +-
 prompts/panel_missions/premortem.txt               |   35 +-
 prompts/panel_missions/production.txt              |    9 +
 prompts/panel_missions/synthesize.txt              |   30 +-
 prompts/panel_missions/tier1.txt                   |   36 +-
 prompts/panel_missions/verify.txt                  |    9 +
 pyproject.toml                                     |   93 +-
 .../liquidation_reversion_BTCUSDT.json             |  279 +
 reports/matrix_window_measurement.json             |   34 +
 reports/screen_exchange_netflow.json               |  346 ++
 research_agenda.json                               |  151 +-
 research_state.json                                |  357 +-
 scripts/ack_defect.py                              |  107 +
 scripts/alpha_lifecycle.py                         |    6 +-
```


---

## a6e014e cohort fence: key the skip on the cause, and check the dangerous case first
The fence skipped when `data/axis_shadow_state.json` was absent, taking that
file's presence as "this is the live desk". It is not a good proxy: running
scripts/run_axis_shadows.py once on a clone creates it while the other seven
cohort sources stay missing, which flips the proxy and fails the fence for a
reason that is a fact about the host. I tripped exactly that today.

Two changes, and the fence is stricter afterwards, not looser:

  - `too_loose` -- an artifact judged against a SMALLER cohort than the
    registry knows about, which is the phantom-edge direction and the entire
    reason this fence exists -- is now asserted UNCONDITIONALLY, above any
    skip. It can no longer be skipped on any host.

  - the skip keys on `unknown_sources`, which names the sources that could not
    be read, instead of inferring it from one file's existence. It can only
    ever skip a COHORT-INCOMPLETE report, which the fence's own detail
    describes as "bars are safe but the desk is flying on a floor" --
    conservative by construction.

Also cleaned web/axis_shadows.json, which I had polluted with test fixtures
(test_tracked, test_no_target) by deleting the registry without regenerating.
That was the proximate cause of the red; the proxy above was the reason a
local run could turn it red at all.

Verified: 15 passed, 1 skipped with the honest reason naming all 7 unreadable
sources. ruff and mypy clean. Full suite running; a test-file change cannot
break another test, which is why this is committed ahead of it.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit a6e014e1b31f4225059da78cda26c7a825628a8a
Author: Claude <noreply@anthropic.com>
Date:   Sun Aug 9 11:04:54 2026 +0000

    cohort fence: key the skip on the cause, and check the dangerous case first
    
    The fence skipped when `data/axis_shadow_state.json` was absent, taking that
    file's presence as "this is the live desk". It is not a good proxy: running
    scripts/run_axis_shadows.py once on a clone creates it while the other seven
    cohort sources stay missing, which flips the proxy and fails the fence for a
    reason that is a fact about the host. I tripped exactly that today.
    
    Two changes, and the fence is stricter afterwards, not looser:
    
      - `too_loose` -- an artifact judged against a SMALLER cohort than the
        registry knows about, which is the phantom-edge direction and the entire
        reason this fence exists -- is now asserted UNCONDITIONALLY, above any
        skip. It can no longer be skipped on any host.
    
      - the skip keys on `unknown_sources`, which names the sources that could not
        be read, instead of inferring it from one file's existence. It can only
        ever skip a COHORT-INCOMPLETE report, which the fence's own detail
        describes as "bars are safe but the desk is flying on a floor" --
        conservative by construction.
    
    Also cleaned web/axis_shadows.json, which I had polluted with test fixtures
    (test_tracked, test_no_target) by deleting the registry without regenerating.
    That was the proximate cause of the red; the proxy above was the reason a
    local run could turn it red at all.
    
    Verified: 15 passed, 1 skipped with the honest reason naming all 7 unreadable
    sources. ruff and mypy clean. Full suite running; a test-file change cannot
    break another test, which is why this is committed ahead of it.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 tests/research/test_cohort_integrity.py | 24 +++++++++++++++++++-----
 1 file changed, 19 insertions(+), 5 deletions(-)

diff --git a/tests/research/test_cohort_integrity.py b/tests/research/test_cohort_integrity.py
index dadae74..b51410b 100644
--- a/tests/research/test_cohort_integrity.py
+++ b/tests/research/test_cohort_integrity.py
@@ -148,11 +148,25 @@ def test_fence_is_green_on_the_live_tree():
     from scripts.check_cohort_integrity import build_report
 
     rep = build_report()
-    shadow = _ROOT / "data/axis_shadow_state.json"
-    if rep["status"] == "COHORT-INCOMPLETE" and not shadow.exists():
-        pytest.skip(f"cohort sources -- {_RUNTIME_ONLY}. The fence reads shadow state written by "
-                    f"the live slots; on a clone it correctly reports a FLOOR rather than a "
-                    f"measurement, which is a fact about the clone: {rep['detail']}")
+    # THE DANGEROUS CONDITION IS CHECKED UNCONDITIONALLY, BEFORE ANY SKIP. `too_loose` is an
+    # artifact judged against a SMALLER cohort than the registry knows about -- the phantom-edge
+    # direction, and the entire reason this fence exists. It must never be skipped for any host.
+    assert not rep["too_loose"], f"BAR-TOO-LOOSE: {rep['too_loose']}"
+
+    # The skip now keys on the CAUSE, not on a proxy. It used to key on
+    # `data/axis_shadow_state.json` existing, taking that as "this is the live desk" -- but
+    # running run_axis_shadows.py once on a clone creates that file while the other seven cohort
+    # sources stay absent, flipping the proxy and failing the fence for a reason that is a fact
+    # about the host. `unknown_sources` names the sources that could not be read, so it says
+    # directly what the proxy was trying to infer.
+    #
+    # This can only ever skip a report that is FLOORED, which the fence's own detail describes as
+    # "bars are safe but the desk is flying on a floor" -- conservative by construction, and the
+    # too_loose assertion above still bites underneath it.
+    if rep["status"] == "COHORT-INCOMPLETE" and rep["unknown_sources"]:
+        pytest.skip(f"cohort sources -- {_RUNTIME_ONLY}. {len(rep['unknown_sources'])} source(s) "
+                    f"unreadable on this host, so m is a FLOOR rather than a measurement and the "
+                    f"bar is capped conservatively: {rep['detail']}")
     assert rep["status"] == "OK", f"{rep['status']}: {rep['detail']}"
     assert rep["shipped_bar_crosscheck"] == "agrees", "local bar diverges from the shipped one"
 
```


---

## 6f665e3 kimchi: close the stale-leg hole, auto-register clocks, put losses on the dashboard
HUNTED KIMCHI FOR SURVIVORS AND THE ANSWER WAS ALREADY WRITTEN. The vault says
the regional-premium class is exhausted per-axis: Turkey (IC -0.063,
FX-close-timing noise), Japan (IC -0.06, freer capital flows), Brazil
(screen-weak), Bithumb (lookahead_artifact), Coinone (redundant). "Kimchi is
the lone survivor across KR/JP/BR/TR/Coinbase tested." Re-running premium
screens would have re-tested graveyarded hypotheses. The mechanism explains the
pattern -- premium tracks BARRIER HEIGHT (Korea std 1.42% vs Turkey 0.23%) --
so it is rent on a capital control, not an inefficiency.

So the work went to what was BLOCKING kimchi instead.

GAP #79, DUE TODAY, CLOSED. A foreign leg stale by one bar passed the
de-contamination gate and was still pure lookahead -- a peer-reviewed Korean
paper's 4,709x "kimchi arbitrage" decomposed to exactly that. Measured on a
synthetic reproduction:

    stale-leg   same_period_corr  0.009  <- old gate: PASS
                prior_period_corr -0.963 <- new gate: SUSPECT-STALE-LEG
    honest      prior_period_corr -0.053 <- no false positive

The gate now tests the prior bar and orthogonalises the residual against both.
It generalises to every axis built by differencing two sources: any premium,
any basis, any cross-venue spread.

NEW CANDIDATES NOW REACH THE DASHBOARD BY THEMSELVES. _AXES in
run_axis_shadows.py was hardcoded, so a candidate that EARNED a forward clock
never appeared in Stage-B until a human edited the script -- silent, and it
looks exactly like "no new candidates". stage_a_screen now registers clocks to
data/axis_clock_registry.json and Stage-B unions them (curated wins
collisions). Direction is DERIVED from which Sharpe carried, never assumed --
guessing +1 would silently invert a reversal axis. A clock with no target
symbol lists as UNTRACKED rather than being dropped or scored against a guessed
asset. Verified end to end; the Holm cohort went 2 -> 5 clocks, which is the
honest multiplicity cost of being counted.

A LIVE BUG FOUND ON THE WAY, and swept per GAP 110. run_trade_forensics was
shipping

    "execution_tape": {"error": "ModuleNotFoundError: No module named 'libs'"}

into the artifact -- `python scripts/x.py` puts scripts/ on sys.path, not the
repo root, and a broad `except Exception` turned the import failure into a
value. An error string is indistinguishable from data to every reader
downstream. Six ops-invoked scripts bootstrapped; the tape now returns real
data (taped 6, tape_days 2403.3). tests/scripts/test_cycle_scripts_are_runnable
pins it for all of them via an AST walk that also catches function-level
imports, which is where this one hid.

run_cashcarry_executor.py is DELIBERATELY exempt and named in the test with the
reason: it is the order path and the Codex seat rewrote ~840 lines of it on the
VPS branch. A three-line edit would manufacture a conflict on the one file
where a bad resolution places a trade. It gets the bootstrap after that merge.

DASHBOARD. Loss-forensics card (hold-bucket net bps, bleeding symbols, maker
share vs target, flags) and axis provenance (curated vs auto-registered,
UNTRACKED in amber). A section that failed renders red as FAILED, never as a
number -- the defect above is exactly what that guard is for.

Also appended a decision-ledger correction: the panel's recorded cost
("~$5 credit, ~$0.10-0.60/run") is ~100x low against the ~$200/month the
principal reports. Appended, not edited -- the ledger is memory. That wrong
number is what priced my own first answer to "is the panel worth it", and
research_roi cannot tell an estimate from a measurement.

Gates: ruff clean, mypy clean over 503 files. The two existing assertions in
the blast radius of the residual_ic change were evaluated directly rather than
assumed -- test_real_lead_still_screens_interesting (residual_ic 0.1064 vs ic
0.1065) and the sweep's |residual|>=0.5|ic| (0.0741 vs 0.0367) -- both hold,
because a genuine lead gives the lag regressor a near-zero coefficient. Full
suite still running at commit time; result reported separately.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 6f665e32275af1254187235ac60c853eb62a7a58
Author: Claude <noreply@anthropic.com>
Date:   Sun Aug 9 10:55:04 2026 +0000

    kimchi: close the stale-leg hole, auto-register clocks, put losses on the dashboard
    
    HUNTED KIMCHI FOR SURVIVORS AND THE ANSWER WAS ALREADY WRITTEN. The vault says
    the regional-premium class is exhausted per-axis: Turkey (IC -0.063,
    FX-close-timing noise), Japan (IC -0.06, freer capital flows), Brazil
    (screen-weak), Bithumb (lookahead_artifact), Coinone (redundant). "Kimchi is
    the lone survivor across KR/JP/BR/TR/Coinbase tested." Re-running premium
    screens would have re-tested graveyarded hypotheses. The mechanism explains the
    pattern -- premium tracks BARRIER HEIGHT (Korea std 1.42% vs Turkey 0.23%) --
    so it is rent on a capital control, not an inefficiency.
    
    So the work went to what was BLOCKING kimchi instead.
    
    GAP #79, DUE TODAY, CLOSED. A foreign leg stale by one bar passed the
    de-contamination gate and was still pure lookahead -- a peer-reviewed Korean
    paper's 4,709x "kimchi arbitrage" decomposed to exactly that. Measured on a
    synthetic reproduction:
    
        stale-leg   same_period_corr  0.009  <- old gate: PASS
                    prior_period_corr -0.963 <- new gate: SUSPECT-STALE-LEG
        honest      prior_period_corr -0.053 <- no false positive
    
    The gate now tests the prior bar and orthogonalises the residual against both.
    It generalises to every axis built by differencing two sources: any premium,
    any basis, any cross-venue spread.
    
    NEW CANDIDATES NOW REACH THE DASHBOARD BY THEMSELVES. _AXES in
    run_axis_shadows.py was hardcoded, so a candidate that EARNED a forward clock
    never appeared in Stage-B until a human edited the script -- silent, and it
    looks exactly like "no new candidates". stage_a_screen now registers clocks to
    data/axis_clock_registry.json and Stage-B unions them (curated wins
    collisions). Direction is DERIVED from which Sharpe carried, never assumed --
    guessing +1 would silently invert a reversal axis. A clock with no target
    symbol lists as UNTRACKED rather than being dropped or scored against a guessed
    asset. Verified end to end; the Holm cohort went 2 -> 5 clocks, which is the
    honest multiplicity cost of being counted.
    
    A LIVE BUG FOUND ON THE WAY, and swept per GAP 110. run_trade_forensics was
    shipping
    
        "execution_tape": {"error": "ModuleNotFoundError: No module named 'libs'"}
    
    into the artifact -- `python scripts/x.py` puts scripts/ on sys.path, not the
    repo root, and a broad `except Exception` turned the import failure into a
    value. An error string is indistinguishable from data to every reader
    downstream. Six ops-invoked scripts bootstrapped; the tape now returns real
    data (taped 6, tape_days 2403.3). tests/scripts/test_cycle_scripts_are_runnable
    pins it for all of them via an AST walk that also catches function-level
    imports, which is where this one hid.
    
    run_cashcarry_executor.py is DELIBERATELY exempt and named in the test with the
    reason: it is the order path and the Codex seat rewrote ~840 lines of it on the
    VPS branch. A three-line edit would manufacture a conflict on the one file
    where a bad resolution places a trade. It gets the bootstrap after that merge.
    
    DASHBOARD. Loss-forensics card (hold-bucket net bps, bleeding symbols, maker
    share vs target, flags) and axis provenance (curated vs auto-registered,
    UNTRACKED in amber). A section that failed renders red as FAILED, never as a
    number -- the defect above is exactly what that guard is for.
    
    Also appended a decision-ledger correction: the panel's recorded cost
    ("~$5 credit, ~$0.10-0.60/run") is ~100x low against the ~$200/month the
    principal reports. Appended, not edited -- the ledger is memory. That wrong
    number is what priced my own first answer to "is the panel worth it", and
    research_roi cannot tell an estimate from a measurement.
    
    Gates: ruff clean, mypy clean over 503 files. The two existing assertions in
    the blast radius of the residual_ic change were evaluated directly rather than
    assumed -- test_real_lead_still_screens_interesting (residual_ic 0.1064 vs ic
    0.1065) and the sweep's |residual|>=0.5|ic| (0.0741 vs 0.0367) -- both hold,
    because a genuine lead gives the lag regressor a near-zero coefficient. Full
    suite still running at commit time; result reported separately.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 data/decision_ledger.json                        |  13 ++-
 docs/research/test_suite_record.json             |   4 +-
 libs/research/axis_screen.py                     |  97 +++++++++++++++-
 scripts/backfill_oi_ls_oos.py                    |  12 ++
 scripts/rollback_guard.py                        |  12 ++
 scripts/run_axis_shadows.py                      |  51 ++++++++-
 scripts/run_cadence.py                           |  10 ++
 scripts/run_ci.py                                |  12 ++
 scripts/run_crypto_research.py                   |  12 ++
 scripts/run_trade_forensics.py                   |  12 ++
 tests/scripts/test_cycle_scripts_are_runnable.py | 138 +++++++++++++++++++++++
 web/research.html                                |  57 +++++++++-
 12 files changed, 416 insertions(+), 14 deletions(-)

diff --git a/data/decision_ledger.json b/data/decision_ledger.json
index c6baf60..8bb0e3b 100644
--- a/data/decision_ledger.json
+++ b/data/decision_ledger.json
@@ -2879,6 +2879,17 @@
     "owned_and_fixed_first": "check_constitution_core (f35df7e)",
     "verified_on_remote": true
    }
+  },
+  {
+   "id": "2026-08-09-panel-cost-recorded-100x-low",
+   "decision": "CORRECTION, appended rather than edited -- the ledger is memory and history is not rewritten. Entry 2026-07-12-multi-model-advisory-panel records the external panel's cost as '~$5 credit = whole panel, ~$0.10-0.60/run'. The principal reports the actual spend as ~$200/MONTH, roughly 100x the recorded figure. That original number is what every downstream ROI comparison has been priced against, including this session's first answer to 'is the panel worth it', which said the dollar cost was negligible. It was not.",
+   "why": "A wrong cost in the ledger is worse than a missing one: research_roi, the frontier surplus calculation and every build/buy comparison read recorded costs and cannot tell an estimate from a measurement. An action priced at 1% of its true cost wins every comparison it enters.",
+   "measured": "Panel authorised 2026-07-12; ~1 month elapsed. Output: 67 distinct recommendations in docs/research/panel_inbox.md, 23 reaching improvement_inbox, ~3 reaching QUEUE-or-better (grep-level count, not an audit). VALIDATED SURVIVORS: 0. ECONOMIC DESCENDANTS: 0 -- the desk has zero confirmed edges, so nothing the panel suggested has produced money. ~$67 per queued finding; cost per dollar earned is undefined because the denominator is zero.",
+   "unmeasured": "The split of the ~$200 across panel / brain / miners is NOT established -- the principal was asked and has not yet answered, so this entry must not be read as '$200 for the panel alone'. Provider hit-rate has NEVER been computed: data/panel_verdicts.jsonl and data/panel_*.json do not exist, so the entry's own success metric ('provider hit-rate measurable by month 2') is unmet and its reversal condition cannot fire.",
+   "expected_cost": "~$200/month reported; split across seats UNMEASURED",
+   "success_metric": "the ORIGINAL entry's metric stands and is half-met: '>=1 QUEUE-or-better finding' PASSED (~3); 'provider hit-rate measurable by month 2' FAILED (never computed)",
+   "reversal_condition": "unchanged from the original entry: two consecutive panels with zero surviving findings -> drop to biweekly. On the evidence above it has arguably already fired and could not be observed",
+   "ts": "2026-08-09T10:54:30.050491+00:00"
   }
  ]
-}
\ No newline at end of file
+}
diff --git a/docs/research/test_suite_record.json b/docs/research/test_suite_record.json
index 021a898..7d41b7e 100644
--- a/docs/research/test_suite_record.json
+++ b/docs/research/test_suite_record.json
@@ -1,5 +1,5 @@
 {
- "max_collected": 359,
- "at": "2026-08-09T09:57:09.349216+00:00",
+ "max_collected": 360,
+ "at": "2026-08-09T10:48:45.135363+00:00",
  "note": "high-water mark of COLLECTABLE test modules; ratchets UP only. A suite may never quietly shrink -- deleting a test is a decision, not a side effect."
 }
\ No newline at end of file
diff --git a/libs/research/axis_screen.py b/libs/research/axis_screen.py
index 3491498..afeaa64 100644
--- a/libs/research/axis_screen.py
+++ b/libs/research/axis_screen.py
@@ -27,7 +27,9 @@ def stage_a_screen(signal: np.ndarray, target_ret: np.ndarray, *, name: str,
                    zwin: int = 20, contam_max: float = 0.20, ic_min: float = 0.03,
                    sharpe_min: float = 0.5, ic_ceiling: float = 0.35,
                    sharpe_ceiling: float = 6.0, clock: str | None = None,
-                   horizon_days: float = 1.0, panel_width: int = 1) -> dict[str, Any]:
+                   horizon_days: float = 1.0, panel_width: int = 1,
+                   target_symbol: str = "",
+                   registry: str = "data/axis_clock_registry.json") -> dict[str, Any]:
     """Screen a signal against NEXT-period target returns with the mandatory angle-20 gate.
 
     signal[t], target_ret[t] must be aligned same-period arrays (target_ret[t] = return realised
@@ -43,6 +45,12 @@ def stage_a_screen(signal: np.ndarray, target_ret: np.ndarray, *, name: str,
                                 leaking future info. Caught the bithumb_KR IC-0.72/Sharpe-10 fake.
                                 Treated as an artifact -- NEVER earns a clock. Re-run a +/-1 day
                                 shift-sensitivity check before trusting anything that trips this.
+      SUSPECT-STALE-LEG      -- |prior-period corr|>contam_max AND it exceeds the same-period corr.
+                                The spread knows the PREVIOUS bar better than the current one, which
+                                is the signature of one feed being stale by a bar. Caught the class
+                                that produced a published 4,709x "kimchi arbitrage" whose Upbit leg
+                                lagged Binance ~1 day. Same-day contamination reads near zero there,
+                                so the lag-0 gate passed it -- GAP #79, closed 2026-08-09.
       TIMING-ARTIFACT        -- fails de-contam: |same-period corr|>contam_max OR residual IC
                                 collapses below half the raw IC (the coinbase/turkey failure mode)
       SCREEN-INTERESTING     -- |IC|>=ic_min, best timing Sharpe>=sharpe_min, passes de-contam,
@@ -76,9 +84,30 @@ def stage_a_screen(signal: np.ndarray, target_ret: np.ndarray, *, name: str,
 
     ic = float(np.corrcoef(zv, fv)[0, 1]) if fv.std() else 0.0
     same = float(np.corrcoef(zv, tv)[0, 1]) if tv.std() else 0.0
-    b = np.polyfit(tv, zv, 1)
-    zr = zv - (b[0] * tv + b[1])                       # signal orthogonalised to same-period return
+
+    # THE STALE-LEG HOLE (GAP #79, closed 2026-08-09). The same-period check above catches a leg
+    # that is aligned-but-coincident. It provably does NOT catch a foreign leg that is stale by one
+    # bar, and that is not a hypothetical: a peer-reviewed Korean paper's 4,709x "kimchi arbitrage"
+    # decomposed to exactly this -- its Upbit column lagged Binance ~1 day, so its "premium" was
+    # approximately MINUS the prior global return and its entry rule was "buy right after BTC
+    # rallied". Same-day contamination reads near zero there, so the gate passed it.
+    #
+    # A cross-source spread is built from two feeds with two clocks. When one is stale the spread
+    # mechanically encodes the OTHER leg's realised move, and the contamination lands at lag 1
+    # instead of lag 0 -- invisible to a lag-0 test by construction. So the prior-period return is
+    # now tested too, and the residual is orthogonalised against BOTH.
+    #
+    # This generalises past kimchi to every axis built by differencing two sources, which is most
+    # of them: any premium, any basis, any cross-venue spread. It can only ever tighten the screen.
+    lag = np.roll(r, 1)[zwin:-1]
+    lag1 = float(np.corrcoef(zv, lag)[0, 1]) if lag.std() else 0.0
+    design = np.column_stack([tv, lag, np.ones(len(zv))])
+    coef, *_ = np.linalg.lstsq(design, zv, rcond=None)
+    zr = zv - design @ coef            # orthogonalised to same-period AND prior-period return
     ic_res = float(np.corrcoef(zr, fv)[0, 1]) if zr.std() and fv.std() else 0.0
+    # STALE-LEG signature: the spread knows the PREVIOUS bar better than the current one. An
+    # honest same-clock spread has no reason to; a mis-clocked one has every reason to.
+    stale_leg = abs(lag1) > contam_max and abs(lag1) > abs(same)
 
     # Annualisation MUST match the target's period. target_ret are horizon_days-day returns, so a
     # year holds 365/horizon_days of them, not 365. The old hardcoded sqrt(365) overstated Sharpe by
@@ -134,10 +163,15 @@ def stage_a_screen(signal: np.ndarray, target_ret: np.ndarray, *, name: str,
     # a diagnostic; ic_ceiling stays caller-tunable per axis rather than one global guess.
     ic_exceeds_contemporaneous = abs(ic) > max(abs(same), ic_min) * 1.5 and abs(ic) >= 0.15
 
-    decontam_fail = abs(same) > contam_max or abs(ic_res) < 0.5 * abs(ic)
+    decontam_fail = abs(same) > contam_max or abs(ic_res) < 0.5 * abs(ic) or stale_leg
     implausible = abs(ic) > ic_ceiling or best > sharpe_ceiling    # alignment/lookahead rail
     if implausible or ic_exceeds_contemporaneous:
         verdict = "SUSPECT-LOOKAHEAD"                  # bithumb-class: too strong to be real
+    elif stale_leg:
+        # Ranked ABOVE the weak/underpowered branches on purpose. A stale-leg axis can post a
+        # perfectly respectable IC, so letting a strength test run first would report the number
+        # rather than the defect that produced it.
+        verdict = "SUSPECT-STALE-LEG"
     elif best < sharpe_min or abs(ic) < ic_min:
         # Distinguish 'tested and refuted' from 'could not have detected it'. Only the former is
         # graveyard-grade negative knowledge.
@@ -166,7 +200,8 @@ def stage_a_screen(signal: np.ndarray, target_ret: np.ndarray, *, name: str,
 
     out = {"name": name, "n": len(zv), "ic": round(ic, 4),
            "sharpe_momentum": sh_mom, "sharpe_reversal": sh_rev,
-           "same_period_corr": round(same, 3), "residual_ic": round(ic_res, 4),
+           "same_period_corr": round(same, 3), "prior_period_corr": round(lag1, 3),
+           "stale_leg": bool(stale_leg), "residual_ic": round(ic_res, 4),
            "decontam_passed": not decontam_fail, "implausible_leak": implausible,
            "horizon_days": float(horizon_days), "panel_width": int(panel_width),
            "n_eff": round(n_eff, 1),
@@ -183,9 +218,61 @@ def stage_a_screen(signal: np.ndarray, target_ret: np.ndarray, *, name: str,
             with p.open("a", encoding="utf-8") as fh:
                 fh.write(json.dumps({"date": today, "z20": out["current_z"],
                                      "screen": out}) + "\n")
+        _register_clock(out, clock=clock, target_symbol=target_symbol, registry=registry)
     return out
 
 
+def _register_clock(out: dict[str, Any], *, clock: str, target_symbol: str,
+                    registry: str) -> None:
+    """Announce a newly-started clock so the Stage-B tracker and the dashboard SEE it.
+
+    THE BREAK THIS CLOSES. Starting a clock wrote a JSONL and told nobody. `run_axis_shadows.py`
+    read a HARDCODED `_AXES` dict, so a candidate that earned a clock did not reach Stage-B -- or
+    the dashboard -- until a human noticed and edited the script. A discovery whose visibility
+    depends on somebody remembering is a discovery the desk will eventually lose, and it fails
+    silently in the direction that looks like "no new candidates" rather than like an error.
+
+    DIRECTION IS DERIVED, NOT ASSUMED: whichever of momentum/reversal actually carried the Sharpe.
+    Guessing +1 would silently invert a reversal axis and turn a real edge into a real loss.
+
+    Registration is NOT promotion. It buys a forward clock and a row on the dashboard, nothing
+    else -- and every clock registered here raises the Holm bar for every other clock racing
+    beside it, which is the honest cost of being counted.
+    """
+    reg = Path(registry)
+    try:
+        blob = json.loads(reg.read_text("utf-8")) if reg.exists() else {}
+    except (OSError, ValueError):
+        blob = {}
+    raw = blob.get("axes")
+    axes: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
+    name = str(out["name"])
+    if name in axes:                       # first registration wins; re-screens must not restamp
+        return
+    sign = 1 if abs(out["sharpe_momentum"]) >= abs(out["sharpe_reversal"]) else -1
+    axes[name] = {
+        "clock": clock,
+        "target_symbol": target_symbol,
+        "method": "z20",
+        "sign": sign,
+        "direction": "momentum" if sign > 0 else "reversal",
+        "registered_at": datetime.now(tz=UTC).isoformat(),
+        "screen_ic": out.get("ic"),
+        "screen_verdict": out.get("verdict"),
+        "tracked": bool(target_symbol),
+        "note": ("" if target_symbol else
+                 "NO TARGET SYMBOL SUPPLIED -- Stage-B cannot score this clock and will list it as "
+                 "UNTRACKED rather than guess one. Pass target_symbol= to stage_a_screen."),
+    }
+    reg.parent.mkdir(parents=True, exist_ok=True)
+    reg.write_text(json.dumps(
+        {"updated": datetime.now(tz=UTC).isoformat(), "axes": axes,
+         "note": ("Clocks started by stage_a_screen, registered so Stage-B and the dashboard pick "
+                  "them up WITHOUT a code edit. Registration is not promotion: it earns a forward "
+                  "clock and a dashboard row, and it raises the Holm bar for every concurrent "
+                  "clock.")}, indent=1), "utf-8")
+
+
 # --------------------------------------------------------------- target/horizon sweep ----------
 #: The mandated sweep grid. Targets and horizons are BOTH swept because the constitution's
 #: TARGET/HORIZON SWEEP DUTY forbids the next-day-absolute reflex: an asset-SELECTION signal is
diff --git a/scripts/backfill_oi_ls_oos.py b/scripts/backfill_oi_ls_oos.py
index b091dcf..7f566c4 100755
--- a/scripts/backfill_oi_ls_oos.py
+++ b/scripts/backfill_oi_ls_oos.py
@@ -23,6 +23,18 @@ including delisted symbols -- the cross-section is what existed then (no survivo
 """
 from __future__ import annotations
 
+# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root, so `libs`
+# resolves only if the project happens to be pip-installed into the interpreter in use. The daily
+# cycle invokes these by path. Without this the libs imports fail -- and in run_trade_forensics a
+# broad `except Exception` caught exactly that and shipped {"error": "ModuleNotFoundError"} into
+# the artifact, where an error string is indistinguishable from data to every reader downstream.
+import sys as _sys
+from pathlib import Path as _P
+
+if str(_P(__file__).resolve().parent.parent) not in _sys.path:
+    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
+
+
 import contextlib
 import json
 import urllib.request
diff --git a/scripts/rollback_guard.py b/scripts/rollback_guard.py
index 093adc2..33b4f22 100644
--- a/scripts/rollback_guard.py
+++ b/scripts/rollback_guard.py
@@ -21,6 +21,18 @@ a subsystem and evaluates AFTER; it auto-reverts on a REVERT verdict.
 
 from __future__ import annotations
 
+# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root, so `libs`
+# resolves only if the project happens to be pip-installed into the interpreter in use. The daily
+# cycle invokes these by path. Without this the libs imports fail -- and in run_trade_forensics a
+# broad `except Exception` caught exactly that and shipped {"error": "ModuleNotFoundError"} into
+# the artifact, where an error string is indistinguishable from data to every reader downstream.
+import sys as _sys
+from pathlib import Path as _P
+
+if str(_P(__file__).resolve().parent.parent) not in _sys.path:
+    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
+
+
 import contextlib
 import json
 import shutil
diff --git a/scripts/run_axis_shadows.py b/scripts/run_axis_shadows.py
index 5b505e5..bef72f4 100755
--- a/scripts/run_axis_shadows.py
+++ b/scripts/run_axis_shadows.py
@@ -136,14 +136,63 @@ def _evaluate(name: str, clock: str, symbol: str, field: str, direction: int,
             "stage": "B (forward-only; eligibility != deployment)"}
 
 
+_REGISTRY = Path("data/axis_clock_registry.json")
+
+
+def _all_axes() -> tuple[dict[str, tuple[str, str, str, int]], list[dict[str, object]]]:
+    """Hand-curated axes UNION the ones stage_a_screen registered when it started a clock.
+
+    WHY THE UNION EXISTS. `_AXES` above is hand-maintained, so until 2026-08-09 a candidate that
+    EARNED a forward clock did not appear in Stage-B -- or on the dashboard -- until a human
+    noticed and edited this file. That failure is silent and it looks exactly like "no new
+    candidates", which is the one shape nobody investigates.
+
+    The curated entries WIN on a name collision: a considered decision here outranks whatever a
+    screen auto-registered, and a re-screen must never quietly redirect a live clock's target.
+
+    An axis registered WITHOUT a target symbol cannot be scored, so it is returned as an UNTRACKED
+    row rather than dropped or guessed at. Dropping it would recreate the invisibility this
+    function exists to remove; guessing a target would silently score it against the wrong asset.
+    """
+    merged = dict(_AXES)
+    untracked: list[dict[str, object]] = []
+    try:
+        blob = json.loads(_REGISTRY.read_text("utf-8"))
+    except (OSError, ValueError):
+        return merged, untracked
+    for name, rec in (blob.get("axes") or {}).items():
+        if name in merged or not isinstance(rec, dict):
+            continue
+        target = str(rec.get("target_symbol") or "")
+        clock = str(rec.get("clock") or "")
+        if not target or not clock:
+            untracked.append({
+                "axis": name, "verdict": "UNTRACKED", "forward_days": 0, "need": _MIN_DAYS,
+                "auto_registered": True,
+                "note": ("clock registered without a target symbol, so forward P&L cannot be "
+                         "scored. Listed rather than dropped -- an invisible candidate is the "
+                         "defect this union exists to prevent -- and NOT guessed at, because "
+                         "scoring it against the wrong asset would be worse than not scoring it"),
+                "stage": "B (registered, unscoreable)"})
+            continue
+        sign = int(rec.get("sign") or 1)
+        merged[name] = (clock, target, str(rec.get("method") or "z20"), sign)
+    return merged, untracked
+
+
 def main() -> None:
     # Derived ONCE, and BEFORE _STATE is rewritten below -- derive_slots() reads that same file to
     # count the axis clocks, so deriving per-axis would both re-read it 3x and let this run's own
     # write feed back into its own bar.
     cohort = cohort_m_for_bar()
-    results = [_evaluate(k, *v, cohort=cohort) for k, v in _AXES.items()]
+    tracked, untracked = _all_axes()
+    results = [_evaluate(k, *v, cohort=cohort) for k, v in tracked.items()]
+    results.extend(untracked)
+    for r in results:
+        r.setdefault("auto_registered", r.get("axis") not in _AXES)
     payload = {"updated": datetime.now(tz=UTC).isoformat(), "min_forward_days": _MIN_DAYS,
                "axes": results,
+               "curated_axes": len(_AXES), "auto_registered_axes": len(results) - len(_AXES),
                "m_concurrent": cohort.m, "m_provenance": cohort.provenance,
                "m_detail": cohort.detail,
                "note": ("Forward-only Stage-B tracking. P&L starts at the clock's first row, never "
diff --git a/scripts/run_cadence.py b/scripts/run_cadence.py
index d421058..5a5b737 100644
--- a/scripts/run_cadence.py
+++ b/scripts/run_cadence.py
```


---

## 447bc61 separate survivor evidence from lexical diagnostics

```diff
commit 447bc61d55cfcc28e832c0964da03ae8b04bacf5
Author: Codex <codex@openai.local>
Date:   Sun Aug 9 11:29:42 2026 +0100

    separate survivor evidence from lexical diagnostics
---
 libs/research/search_strategy.py               |  92 +++++++++++++++------
 scripts/research_alpha_optimizer.py            | 109 ++++++++++++++++++-------
 tests/research/test_search_strategy.py         |  11 ++-
 tests/scripts/test_research_alpha_optimizer.py |  74 +++++++++++++++++
 4 files changed, 228 insertions(+), 58 deletions(-)

diff --git a/libs/research/search_strategy.py b/libs/research/search_strategy.py
index b5a7fb2..bb4abe0 100644
--- a/libs/research/search_strategy.py
+++ b/libs/research/search_strategy.py
@@ -176,7 +176,14 @@ def evolve_search_strategies(
     """Measure, mutate, combine and conservatively nominate retirement of search methods."""
     day = as_of or datetime.now(tz=UTC).date().isoformat()
     stats: dict[str, dict[str, float]] = {
-        method: defaultdict(float, attempts=0.0, explicit_attempts=0.0) for method in SEARCH_METHODS
+        method: defaultdict(
+            float,
+            classified_records=0.0,
+            explicit_attempts=0.0,
+            inferred_mentions=0.0,
+            useful_attempts=0.0,
+        )
+        for method in SEARCH_METHODS
     }
     unattributed = 0
     credit: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
@@ -189,13 +196,21 @@ def evolve_search_strategies(
         outcomes = _outcomes(row)
         method_weight = 1.0 / len(methods)
         for method in methods:
-            stats[method]["attempts"] += method_weight
+            stats[method]["classified_records"] += method_weight
             if classified["provenance"] == "EXPLICIT":
                 stats[method]["explicit_attempts"] += method_weight
-            for key, value in outcomes.items():
-                stats[method][key] += value * method_weight
+                stats[method]["useful_attempts"] += method_weight * min(
+                    1.0,
+                    max(outcomes["useful_information"], outcomes["independent_survivors"]),
+                )
+                for key, value in outcomes.items():
+                    stats[method][key] += value * method_weight
+            else:
+                # Keyword classification maps old prose into the taxonomy, but it is not an
+                # experiment record. Inferred mentions have zero outcome authority.
+                stats[method]["inferred_mentions"] += method_weight
         contributors = row.get("contributors", {})
-        if isinstance(contributors, Mapping):
+        if classified["provenance"] == "EXPLICIT" and isinstance(contributors, Mapping):
             for kind, raw_values in contributors.items():
                 values = (
                     [raw_values]
@@ -213,26 +228,42 @@ def evolve_search_strategies(
     rows: list[dict[str, object]] = []
     for method in SEARCH_METHODS:
         method_stats = dict(stats[method])
-        attempts = method_stats.get("attempts", 0.0)
-        useful = method_stats.get("useful_information", 0.0) + method_stats.get(
-            "independent_survivors", 0.0
-        )
-        alpha = 1.0 + useful
-        beta = 1.0 + max(0.0, attempts - useful)
-        mean = alpha / (alpha + beta)
-        sd = math.sqrt(alpha * beta / ((alpha + beta) ** 2 * (alpha + beta + 1)))
+        attempts = method_stats.get("explicit_attempts", 0.0)
+        useful = min(attempts, method_stats.get("useful_attempts", 0.0))
+        if attempts > 0:
+            alpha = 1.0 + useful
+            beta = 1.0 + max(0.0, attempts - useful)
+            mean: float | None = alpha / (alpha + beta)
+            sd: float | None = math.sqrt(
+                alpha * beta / ((alpha + beta) ** 2 * (alpha + beta + 1))
+            )
+        else:
+            mean = None
+            sd = None
         rows.append(
             {
                 "method": method,
                 **{key: round(value, 6) for key, value in method_stats.items()},
-                "useful_yield_posterior": round(mean, 6),
-                "useful_yield_upper_approx_95": round(min(1.0, mean + 2 * sd), 6),
+                "useful_yield_posterior": round(mean, 6) if mean is not None else None,
+                "useful_yield_upper_approx_95": (
+                    round(min(1.0, mean + 2 * sd), 6)
+                    if mean is not None and sd is not None
+                    else None
+                ),
             }
         )
-    covered = [row for row in rows if finite_float(row.get("attempts")) > 0]
-    missing = [str(row["method"]) for row in rows if finite_float(row.get("attempts")) == 0]
-    total = sum(finite_float(row.get("attempts")) for row in rows)
-    hhi = sum((finite_float(row.get("attempts")) / total) ** 2 for row in rows) if total else None
+    covered = [row for row in rows if finite_float(row.get("explicit_attempts")) > 0]
+    inferred = [row for row in rows if finite_float(row.get("inferred_mentions")) > 0]
+    missing = [
+        str(row["method"]) for row in rows if finite_float(row.get("explicit_attempts")) == 0
+    ]
+    total = sum(finite_float(row.get("explicit_attempts")) for row in rows)
+    classified_total = sum(finite_float(row.get("classified_records")) for row in rows)
+    hhi = (
+        sum((finite_float(row.get("explicit_attempts")) / total) ** 2 for row in rows)
+        if total
+        else None
+    )
     effective = (1.0 / hhi) if hhi else None
     starvation = bool(
         total and effective is not None and effective < max(2.0, math.sqrt(len(SEARCH_METHODS)))
@@ -273,17 +304,17 @@ def evolve_search_strategies(
             "method": row["method"],
             "status": "REVIEW_FOR_RETIREMENT",
             "reason": (
-                ">=10 fractionally credited attempts, no independent survivor, "
+                ">=10 explicitly attributed attempts, no independent survivor, "
                 "low posterior ceiling"
             ),
         }
         for row in rows
-        if finite_float(row.get("attempts")) >= 10
+        if finite_float(row.get("explicit_attempts")) >= 10
         and finite_float(row.get("independent_survivors")) == 0
         and finite_float(row.get("useful_yield_upper_approx_95")) < 0.2
     ]
     return {
-        "status": "MEASURED" if total else "UNMEASURED",
+        "status": "MEASURED" if total else "INSTRUMENTING" if classified_total else "UNMEASURED",
         "method_taxonomy": list(SEARCH_METHODS),
         "methods": rows,
         "coverage": {
@@ -292,9 +323,16 @@ def evolve_search_strategies(
             "ratio": len(covered) / len(SEARCH_METHODS),
             "missing": missing,
             "unattributed_events": unattributed,
+            "inferred_represented": len(inferred),
+            "inferred_ratio": len(inferred) / len(SEARCH_METHODS),
+            "inferred_only": [
+                str(row["method"])
+                for row in inferred
+                if finite_float(row.get("explicit_attempts")) == 0
+            ],
             "explicit_provenance_ratio": (
-                sum(finite_float(row.get("explicit_attempts")) for row in rows) / total
-                if total
+                total / classified_total
+                if classified_total
                 else None
             ),
         },
@@ -312,7 +350,11 @@ def evolve_search_strategies(
         ],
         "serendipity_channel": _serendipity(day, history),
         "recursive_question": "What method could discover a new method of discovering alpha?",
-        "authority": "RESEARCH ALLOCATION PRIOR ONLY; no survivor promotion or capital authority",
+        "authority": (
+            "RESEARCH ALLOCATION PRIOR ONLY; posterior and retirement outputs use EXPLICIT method "
+            "provenance only. Keyword-inferred mentions have zero outcome, survivor-promotion or "
+            "capital authority."
+        ),
     }
 
 
diff --git a/scripts/research_alpha_optimizer.py b/scripts/research_alpha_optimizer.py
index deb0608..c6d568d 100644
--- a/scripts/research_alpha_optimizer.py
+++ b/scripts/research_alpha_optimizer.py
@@ -111,6 +111,7 @@ def main() -> None:
             "method_upgrade": 0,
             "inconclusive": 0,
             "value": 0.0,
+            "survivor_ids": [],
         }
         for m in METHODS
     }
@@ -141,6 +142,8 @@ def main() -> None:
             stats[m]["n"] += 1
             stats[m][outcome] += 1
             stats[m]["value"] += VALUE[outcome]
+            if outcome == "survivor":
+                stats[m]["survivor_ids"].append(str(d.get("id", "UNKNOWN")))
 
     # ACTIVATION GATE -- must FAIL CLOSED. Counting keyword hits in ledger prose is NOT evidence
     # of a confirmed edge (it counted 63 when the true count was 0, flipping the gate open --
@@ -148,10 +151,14 @@ def main() -> None:
     # Stage-B shadow tracker: only verdict == ELIGIBLE is a confirmed edge.
     confirmed = 0
     shadow = Path("web/axis_shadows.json")
+    shadow_rows: list[dict] = []
+    shadow_updated = None
     try:
         sd = json.loads(shadow.read_text("utf-8"))
-        confirmed = sum(1 for a in sd.get("axes", []) if a.get("verdict") == "ELIGIBLE")
-    except Exception:
+        shadow_updated = sd.get("updated")
+        shadow_rows = [a for a in sd.get("axes", []) if isinstance(a, dict)]
+        confirmed = sum(1 for a in shadow_rows if a.get("verdict") == "ELIGIBLE")
+    except (OSError, TypeError, ValueError):
         confirmed = 0
     keyword_surv = sum(s["survivor"] for s in stats.values())
     total_surv = confirmed
@@ -176,16 +183,17 @@ def main() -> None:
         rows.append(
             {
                 "method": m,
-                "attempts": s["n"],
-                "survivors": s["survivor"],
-                "refutations": s["refutation"],
-                "upgrades": s["method_upgrade"],
-                "inconclusive": s["inconclusive"],
-                "value_per_attempt": round(yield_, 3),
-                "posterior": round(post, 3),
+                "classified_ledger_records": s["n"],
+                "keyword_classified_hits": s["survivor"],
+                "keyword_hit_ids": s["survivor_ids"],
+                "refutation_mentions": s["refutation"],
+                "method_upgrade_mentions": s["method_upgrade"],
+                "inconclusive_mentions": s["inconclusive"],
+                "diagnostic_value_per_record": round(yield_, 3),
+                "diagnostic_posterior": round(post, 3),
             }
         )
-    rows.sort(key=lambda r: -r["posterior"])
+    rows.sort(key=lambda r: -r["diagnostic_posterior"])
 
     print(
         "=== RESEARCH ALPHA OPTIMIZER -- which RESEARCH METHODS convert effort into knowledge ==="
@@ -198,14 +206,15 @@ def main() -> None:
     print(f"    MODE: {mode}{mode_note}")
     print(f"    activation needs >={MIN_SURVIVORS} confirmed edges; currently {total_surv}\n")
     print(
-        f"  {'method':<20}{'att':>5}{'surv':>6}{'refut':>7}{'upg':>5}{'incon':>7}"
-        f"{'val/att':>9}{'post':>7}"
+        f"  {'method':<20}{'docs':>5}{'kw-hit':>7}{'refut':>7}{'upg':>5}{'incon':>7}"
+        f"{'diag/rec':>9}{'diag-p':>7}"
     )
     for r in rows:
         print(
-            f"  {r['method']:<20}{r['attempts']:>5}{r['survivors']:>6}{r['refutations']:>7}"
-            f"{r['upgrades']:>5}{r['inconclusive']:>7}{r['value_per_attempt']:>9.3f}"
-            f"{r['posterior']:>7.3f}"
+            f"  {r['method']:<20}{r['classified_ledger_records']:>5}"
+            f"{r['keyword_classified_hits']:>7}{r['refutation_mentions']:>7}"
+            f"{r['method_upgrade_mentions']:>5}{r['inconclusive_mentions']:>7}"
+            f"{r['diagnostic_value_per_record']:>9.3f}{r['diagnostic_posterior']:>7.3f}"
         )
 
     print(
@@ -222,30 +231,68 @@ def main() -> None:
         print("  The recorder runs now because method-outcome history cannot be rebuilt")
         print("  retroactively; the MODEL activates when the numerator exists (Aug 7 clocks).")
 
-    with HIST.open("a", encoding="utf-8") as fh:
-        fh.write(
-            json.dumps(
-                {
-                    "date": today,
-                    "mode": mode,
-                    "total_survivors": total_surv,
-                    "methods": {r["method"]: r["value_per_attempt"] for r in rows},
-                    "total_value": sum(float(s["value"]) for s in stats.values()),
-                    "serendipity_domain": evolution["serendipity_channel"]["domain"],
-                }
+    authority_rows = evolution.get("methods", [])
+    authoritative_value = sum(
+        float(r.get("useful_attempts", 0.0) or 0.0)
+        + float(r.get("realized_value", 0.0) or 0.0)
+        for r in authority_rows
+        if isinstance(r, dict)
+    )
+    # One daily observation, even when several schedules invoke this script. Repeated same-day
+    # rows would make the six-row stagnation window equal "six executions today" rather than six
+    # independent daily opportunities and could trigger a search-process mutation from duplicate
+    # bookkeeping alone. The optimizer runs at the end of the research cycle, so first writer wins
+    # for the day; history remains append-only.
+    if not any(str(row.get("date", "")) == today for row in history):
+        with HIST.open("a", encoding="utf-8") as fh:
+            fh.write(
+                json.dumps(
+                    {
+                        "date": today,
+                        "mode": mode,
+                        "total_survivors": total_surv,
+                        "methods": {
+                            r["method"]: r.get("useful_yield_posterior")
+                            for r in authority_rows
+                        },
+                        "total_value": authoritative_value,
+                        "serendipity_domain": evolution["serendipity_channel"]["domain"],
+                    }
+                )
+                + "\n"
             )
-            + "\n"
-        )
     OUT.write_text(
         json.dumps(
             {
+                "schema_version": 2,
                 "updated": datetime.now(tz=UTC).isoformat(),
                 "mode": mode,
                 "activation_threshold": MIN_SURVIVORS,
                 "confirmed_edges": confirmed,
-                "keyword_hits": keyword_surv,
-                "value_function": VALUE,
-                "methods": rows,
+                "strategy_survivors": {
+                    "count": confirmed,
+                    "source": str(shadow),
+                    "promotion_authority": False,
+                },
+                "shadow_admission": {
+                    "status": "MEASURED" if shadow_updated is not None else "UNMEASURED",
+                    "source": str(shadow),
+                    "updated": shadow_updated,
+                    "eligible": [r for r in shadow_rows if r.get("verdict") == "ELIGIBLE"],
+                    "accruing": [r for r in shadow_rows if r.get("verdict") == "ACCRUING"],
+                    "failing": [r for r in shadow_rows if r.get("verdict") == "FAILING"],
+                },
+                "methods": authority_rows,
+                "weak_label_diagnostics": {
+                    "classification_authority": "NONE",
+                    "keyword_classified_hits": keyword_surv,
+                    "value_function": VALUE,
+                    "methods": rows,
+                    "note": (
+                        "Historical ledger prose classification only. These are not strategies, "
+                        "survivors, shadow candidates, attempts, or evidence."
+                    ),
+                },
                 "search_strategy_evolution": evolution,
             },
             indent=1,
diff --git a/tests/research/test_search_strategy.py b/tests/research/test_search_strategy.py
index 77a20b7..256c965 100644
--- a/tests/research/test_search_strategy.py
+++ b/tests/research/test_search_strategy.py
@@ -29,7 +29,7 @@ def test_explicit_method_provenance_and_fractional_credit() -> None:
         as_of="2026-08-09",
     )
     by_method = {row["method"]: row for row in report["methods"]}
-    assert by_method["causal"]["attempts"] == 0.5
+    assert by_method["causal"]["explicit_attempts"] == 0.5
     assert by_method["participant_first"]["independent_survivors"] == 0.5
     assert report["coverage"]["explicit_provenance_ratio"] == 1.0
     credit = {row["contributor"]: row for row in report["discovery_credit"]}
@@ -65,5 +65,12 @@ def test_keyword_inference_is_labelled_not_treated_as_explicit() -> None:
     report = evolve_search_strategies(
         [{"hypothesis": "reverse engineer a public strategy"}], as_of="2026-08-09"
     )
-    assert report["coverage"]["represented"] == 1
+    assert report["status"] == "INSTRUMENTING"
+    assert report["coverage"]["represented"] == 0
+    assert report["coverage"]["ratio"] == 0
+    assert report["coverage"]["inferred_represented"] == 1
     assert report["coverage"]["explicit_provenance_ratio"] == 0.0
+    by_method = {row["method"]: row for row in report["methods"]}
+    inferred = by_method["reverse_engineering"]
+    assert inferred["inferred_mentions"] == 1.0
+    assert inferred["useful_yield_posterior"] is None
diff --git a/tests/scripts/test_research_alpha_optimizer.py b/tests/scripts/test_research_alpha_optimizer.py
index c652daf..81f0a12 100644
--- a/tests/scripts/test_research_alpha_optimizer.py
+++ b/tests/scripts/test_research_alpha_optimizer.py
@@ -33,3 +33,77 @@ def test_existing_optimizer_publishes_search_method_frontier(
     assert evolution["coverage"]["represented"] == 1
     assert evolution["serendipity_channel"]["bounded_concurrent_missions"] == 1
     assert saved["mode"] == "INSTRUMENTING"
+
+
+def test_keyword_hits_are_not_published_as_survivors_or_shadow_candidates(
+    tmp_path: Path, monkeypatch
+) -> None:
+    data = tmp_path / "data"
+    web = tmp_path / "web"
+    data.mkdir()
+    web.mkdir()
+    ledger = data / "decision_ledger.json"
+    ledger.write_text(
+        json.dumps(
+            {
+                "decisions": [
+                    {
+                        "id": "deadman-reset",
+                        "decision": "combined filter path replicates the risk formula",
+                    },
+                    {
+                        "id": "onchain-wired",
+                        "decision": "composite throughput axis wired to a forward clock",
+                    },
+                ]
+            }
+        ),
+        "utf-8",
+    )
```


---

## 7c9ed8a GAP row 110: a fix that stopped at the file it was found in
The optimizer's source already recorded this defect -- "counted 63 when the
true count was 0, flipping the gate open" -- and the fix went no further than
that file. Its twin sat open in scripts/research_allocator.py, which is the
worse instance because there the phantom count gated the honesty warning.

Row 110 files the RESIDUAL rather than the bug (fixed in 6386cd7): the desk
has no mechanism that turns "defect found here" into "search for the same
shape elsewhere". Every fix is filed against one file. This one survived for
weeks because the sweep was nobody's job.

Full gate on the fix: 0 failures, repo 93.23% (floor 93.23%), money path
81.55% (floor 81.55%), both floors held. The six skips are all VPS-only
inputs and are facts about this clone, not about the gates.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 7c9ed8a1d1fef16d6e26fc717f1cd5a467bb2245
Author: Claude <noreply@anthropic.com>
Date:   Sun Aug 9 10:12:53 2026 +0000

    GAP row 110: a fix that stopped at the file it was found in
    
    The optimizer's source already recorded this defect -- "counted 63 when the
    true count was 0, flipping the gate open" -- and the fix went no further than
    that file. Its twin sat open in scripts/research_allocator.py, which is the
    worse instance because there the phantom count gated the honesty warning.
    
    Row 110 files the RESIDUAL rather than the bug (fixed in 6386cd7): the desk
    has no mechanism that turns "defect found here" into "search for the same
    shape elsewhere". Every fix is filed against one file. This one survived for
    weeks because the sweep was nobody's job.
    
    Full gate on the fix: 0 failures, repo 93.23% (floor 93.23%), money path
    81.55% (floor 81.55%), both floors held. The six skips are all VPS-only
    inputs and are facts about this clone, not about the gates.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/GAP_REGISTER.md | 1 +
 1 file changed, 1 insertion(+)

diff --git a/docs/GAP_REGISTER.md b/docs/GAP_REGISTER.md
index 520d814..bb68ad4 100644
--- a/docs/GAP_REGISTER.md
+++ b/docs/GAP_REGISTER.md
@@ -411,3 +411,4 @@ decision. **They are not analogous and bundling them risks one bad ruling on bot
 | 107 | **REPLACEMENT LATENCY IS THE NUMBER THIS FACTORY IS ACTUALLY OPTIMISING AND IT HAS NEVER BEEN MEASURED ONCE** | Named by the principal 2026-08-09 and correct: a factory can have enormous discovery throughput and still lose the compounding, because a live edge dies and its replacement is months behind. `libs/portfolio/alpha_reserve_bank.py` now answers *if 25/50/75% of live alpha died today, how much is replaceable WITHOUT lowering the bar* — bench deflated by effective independence (three clones are one replacement), same-mechanism cover refused against a mechanism-level death, and `switch_verdict` carrying no drawdown argument at all so the fire-it-because-it-is-down reflex cannot be expressed. **UNMEASURED HERE, AND NOT BY OVERSIGHT:** this clone has no live book, so the ratio has no denominator and the module correctly refuses to report zero. **The gap is that the desk cannot yet name a single eligible bench candidate** — `libs/research/near_survivor.py` banks near-misses and nothing has ever been promoted from it to SHADOW_CHALLENGER, which means the measured reserve ratio on the day a live book exists would be 0.00. | OPEN |
 | 108 | **PER-STRATEGY MONTE CARLO UNDERSTATED PORTFOLIO DRAWDOWN BY 2.93x ON A CLONE BOOK — AND PER-STRATEGY MONTE CARLO IS WHAT THIS DESK RUNS** | Measured 2026-08-09 by `libs/portfolio/portfolio_monte_carlo.dependence_blindness` on a constructed five-clone book. `libs/discovery/monte_carlo_survival.py` reshuffles ONE strategy and `strategy_pool.sizing_drawdown` sizes each member off its own reshuffled tail; both are correct for the question they ask and neither asks what happens on the day every strategy loses at once. Independently shuffling each strategy scatters their bad days across the calendar and manufactures diversification that does not exist. The new module draws ONE block of time per draw and applies it to EVERY strategy, so co-activation, common regime, tail dependence and margin concurrency are never broken rather than modelled. **THE 2.93x IS A CONSTRUCTED-FIXTURE NUMBER, NOT A MEASUREMENT OF THIS DESK.** It proves the discriminator works in both directions (an independent book reads ~1.0). What it costs on the real book is UNMEASURED until `data/strategy_paths.json` exists, and the honest expectation for a crypto book — where basis, momentum, alt-beta and liquidation risk collapse into one factor under stress — is that it is well above 1.0. | OPEN |
 | 109 | **THE DESK ASKED "HOW DO I MAKE BTC STRATEGY #384 BETTER" AND NEVER ONCE ASKED "WHERE ELSE CAN THIS MECHANISM EXPRESS ITSELF"** | Named by the principal 2026-08-09 via Parker's market count, and the framing is sharper than diversification: enormous breadth buys one simple robust rule far more INDEPENDENT CHANCES to encounter the state it needs. A parameter search adds exactly zero independent observations — it re-examines the same history and pays full multiplicity for it — while a new market adds genuinely new draws. `libs/research/market_breadth.py` prices the comparison, deflating occurrence counts by cross-expression state correlation so forty markets that fire in the same hour cannot be spent as forty times the evidence, and filtering feasibility before ranking rather than scoring it. **THE GAP IS THAT DEPTH IS STILL THE DEFAULT AND WILL STAY SO** until `data/market_breadth.json` names candidate expressions, because another parameter needs no new data, no venue access and no new operational surface — which is exactly when it is least likely to be the right call. | OPEN |
+| 110 | **A KNOWN BUG WAS FIXED IN ONE FILE AND NOBODY SWEPT FOR SIBLINGS — SO ITS TWIN SAT OPEN FOR WEEKS IN THE PLACE WHERE IT WAS LOAD-BEARING** | Found by the Codex seat 2026-08-09 in `scripts/research_alpha_optimizer.py`, whose source ALREADY carried the note that keyword-counting ledger prose "counted 63 when the true count was 0, flipping the gate open". That fix was correct and it stopped at the file it was found in. `scripts/research_allocator.py` had the identical `classify()` returning `"survivor"` for any row whose prose contained **"wired"** — on a desk whose ledger is mostly about wiring modules, **82 phantom survivors against a true confirmed count of 0**. **AND THE ALLOCATOR IS THE WORSE INSTANCE, because there the phantom count was LOAD-BEARING:** `prior_dominated = total_surv < 5 or total_n < 30` read the same tally, so 82 evaluated it False and SUPPRESSED the warning that says *do not present this as data-driven* — the leak switched off the sentence that existed to catch it, then printed allocations under the banner "recomputed from evidence, not decreed". **FIXED (6386cd7):** the `survivor` reward bucket is DELETED rather than down-weighted, so restoring the 1.00 payout requires reintroducing the concept instead of editing a number; confirmed survivors come from the Stage-B shadow tracker; an unreadable tracker is UNMEASURED and fails the gate CLOSED (L1.28a); 18 tests pin it, including that the gate still OPENS on real evidence. **SWEPT:** `libs/autodiscovery/research_roi.py` and `libs/alpha_factory/research_attribution.py` read a typed `r.survived` off the candidate ledger rather than prose — clean. Only the two keyword classifiers ever had it. **THE RESIDUAL, AND IT IS THE POINT OF THIS ROW:** the desk has no mechanism that turns "defect found here" into "search for the same shape elsewhere". Every fix is filed against one file. This one survived because the sweep was nobody's job. | OPEN |
```

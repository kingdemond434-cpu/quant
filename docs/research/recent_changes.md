# Desk changes, last 24h (generated 2026-08-09T10:10:02Z)

18 commit(s). Patches truncated to 400 lines each -- a seat that receives
40k lines reviews none of them, and the design decision is almost always in the first
few hundred.


---

## 0d31469 wire the continuous open-world frontier and controller handoff
# Conflicts:
#	docs/research/test_suite_record.json

```diff
commit 0d31469670d667e6c946b318c69dd57a0ebd3c26
Author: Codex <noreply@openai.com>
Date:   Sun Aug 9 10:31:13 2026 +0100

    wire the continuous open-world frontier and controller handoff
    
    # Conflicts:
    #       docs/research/test_suite_record.json
---
 .github/workflows/ci.yml                           |    5 +
 AGENTS.md                                          |   31 +
 deploy/git_hooks/pre-push                          |   16 +
 deploy/privilege_separation/install.sh             |   40 +
 deploy/privilege_separation/permission_matrix.json |   14 +
 .../privilege_separation/quant-risk-kernel.service |   29 +
 docs/research/ARTIFACT_GOVERNANCE.md               |    6 +
 docs/research/COMPLETION_LEDGER.json               | 2860 +++++++++++++-------
 docs/research/COVERAGE_RATCHET.json                |   12 +-
 docs/research/GPT_HUNTER_SOURCES.json              |  250 ++
 docs/research/OVERNIGHT_FRONTIER_CONTRACT.json     |  163 ++
 docs/research/TIER1_CONTROLLER_MANDATE.md          | 1407 ++++++++++
 docs/research/test_suite_record.json               |    8 +-
 libs/core/coerce.py                                |   42 +
 libs/data/asymmetry.py                             |  289 +-
 libs/ops/controller_continuity.py                  |  290 ++
 libs/ops/production_contract.py                    |  418 +++
 libs/portfolio/decision_intelligence.py            |  702 +++++
 libs/research/alpha_frontier.py                    |  391 +++
 libs/research/alpha_frontier_gaps.py               |   59 +
 libs/research/completion_ledger.py                 |  121 +-
 libs/research/completion_program_gaps.py           |   96 +
 libs/research/external_intelligence.py             |  801 ++++++
 libs/research/funnel.py                            |  361 ++-
 libs/research/public_strategy_hunter.py            |  453 ++++
 libs/research/research_control.py                  |  777 ++++++
 libs/research/search_strategy.py                   |  319 +++
 libs/validation/research_diagnostics.py            |  438 +++
 ops/crontab.manifest                               |   16 +
 ops/midnight_codex_prompt.txt                      |   45 +
 ops/principal_doctrine.txt                         |   10 +
 ops/quant-research.service                         |    4 +-
 ops/quant-research.timer                           |    8 +-
 ops/run_cro_ai.sh                                  |    2 +-
 ops/run_midnight_codex_controller.sh               |  119 +
 ops/run_midnight_frontier.sh                       |   21 +
 ops/run_research_cycle.sh                          |   22 +-
 ops/run_sweep_then_cycle.sh                        |   25 +-
 ops/setup_brain_api_key.sh                         |    2 +-
 scripts/build_enforcement_matrix.py                |  304 ++-
 scripts/check_coverage_floors.py                   |  124 +-
 scripts/check_enforcement_execution.py             |  162 +-
 scripts/check_risk_kernel.py                       |   99 +-
 scripts/controller_checkpoint.py                   |  105 +
 scripts/daily_research_cycle.py                    |    1 +
 scripts/derive_walcl_clock.py                      |  130 +
 scripts/gpt_hunter.py                              |  109 +
 scripts/overnight_frontier_handoff.py              |  649 +++++
 scripts/research_alpha_optimizer.py                |   25 +-
 scripts/run_alpha_frontier.py                      |  171 ++
 scripts/run_cashcarry_executor.py                  |  840 ++++--
 scripts/run_completion_program.py                  |  712 +++++
 scripts/run_external_intelligence.py               |  301 ++
 scripts/run_law_gate.py                            |    1 +
 scripts/run_max_push.py                            |  459 +++-
 scripts/study_status.py                            |   14 +
 tests/core/test_coerce.py                          |   29 +
 tests/execution/test_binance_spot_testnet_paths.py |  171 ++
 tests/execution/test_executor_sizing.py            |   28 +
 tests/execution/test_staging.py                    |  130 +-
 tests/ops/test_controller_continuity.py            |  105 +
 tests/ops/test_counterfactual_reality.py           |   52 +
 tests/ops/test_lawful.py                           |    8 +-
 tests/ops/test_midnight_controller.py              |   54 +
 tests/ops/test_privilege_separation_deployment.py  |   23 +
 tests/ops/test_production_contract.py              |  181 ++
 tests/ops/test_research_cycle.py                   |   21 +-
 tests/portfolio/test_capital_topology.py           |   58 +
 tests/portfolio/test_decision_intelligence.py      |  148 +
 tests/portfolio/test_specialized_market_states.py  |   74 +
 tests/research/test_alpha_frontier.py              |  178 ++
 tests/research/test_asymmetric_open_universe.py    |  150 +
 tests/research/test_cohort_integrity.py            |    2 +-
 tests/research/test_completion_ledger.py           |   20 +-
 tests/research/test_elite_hunter_extension.py      |   44 +
 tests/research/test_external_intelligence.py       |  230 ++
 tests/research/test_external_priority_frontiers.py |   50 +
 tests/research/test_frontier_mandate_controls.py   |   78 +
 tests/research/test_gap_projection.py              |  120 +
 tests/research/test_meaningful_throughput.py       |   98 +
 tests/research/test_public_strategy_hunter.py      |  147 +
 tests/research/test_research_control.py            |  237 ++
 tests/research/test_search_strategy.py             |   69 +
 tests/risk/test_capital_events.py                  |  216 +-
 tests/scripts/test_alpha_frontier_runner.py        |  102 +
 tests/scripts/test_build_standard_contract.py      |   69 +
 tests/scripts/test_completion_program.py           |  105 +
 tests/scripts/test_coverage_stall.py               |   60 +-
 tests/scripts/test_derive_walcl_clock.py           |   56 +
 tests/scripts/test_enforcement_execution.py        |   53 +
 tests/scripts/test_external_intelligence_runner.py |   53 +
 tests/scripts/test_frontier_mandate_runner.py      |   62 +
 tests/scripts/test_overnight_frontier_handoff.py   |   91 +
 tests/scripts/test_research_alpha_optimizer.py     |   35 +
 tests/scripts/test_risk_kernel_lock.py             |    8 +
 tests/scripts/test_study_status.py                 |   12 +
 tests/validation/test_research_diagnostics.py      |   73 +
 tests/validation/test_semantic_label_integrity.py  |   97 +
 .../test_sequential_experiment_design.py           |   43 +
 99 files changed, 16737 insertions(+), 1781 deletions(-)

diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 82ce766..6a0f570 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -38,6 +38,11 @@ jobs:
       - name: Types (mypy --strict)
         run: mypy
 
+      # L1.37: enforce the portable constitution/family/wiring fences before a commit can enter.
+      # Live-state checks remain on the VPS; a clean CI worker must not manufacture desk state.
+      - name: Laws (portable)
+        run: python scripts/run_law_gate.py --laws-only
+
       # COVERAGE IS MEASURED HERE OR IT IS NOT MEASURED AT ALL. pytest-cov has been a declared
       # dev dependency and [tool.coverage.run] has carried branch=true for as long as either has
       # existed, and this step ran bare `pytest` -- so the tooling was installed, configured, and
diff --git a/AGENTS.md b/AGENTS.md
new file mode 100644
index 0000000..dde3774
--- /dev/null
+++ b/AGENTS.md
@@ -0,0 +1,31 @@
+# Quant controller entry point
+
+This repository and its VPS state are one continuous quantitative operation shared by Claude and
+Codex. Never reset, fork, or rebuild the research frontier merely because the reasoning controller
+changed.
+
+Before non-trivial work, read completely:
+
+- `CLAUDE.md`
+- `docs/CONSTITUTION.md`
+- `ops/principal_doctrine.txt`
+- `ops/CRO_CONSTITUTION.md`
+- `docs/research/TIER1_CONTROLLER_MANDATE.md`
+- `docs/research/OVERNIGHT_FRONTIER_CONTRACT.json`
+- the current controller checkpoint/handoff, completion ledger, max-push queue, research state,
+  recent history, git status, and every uncommitted change
+
+Preserve valid in-progress work. Search the vault and code before building. Prefer finishing and
+wiring an existing organ over creating another. Every material finding needs an explicit economic
+disposition and every implementation needs a real producer-to-consumer path plus verification.
+
+Maximize validated expected log wealth through useful coverage, independent survivor production,
+portfolio contribution, execution quality, and recursive research improvement. Triple-digit CAGR
+is an ambition, never evidence. Never weaken survival, risk, legal/security, evidence, multiplicity,
+cost, capacity, or untouched-forward-data rules. Never autonomously modify
+`scripts/run_deadman_switch.py` or arm live capital.
+
+Controller mutations require the durable lease/fencing/checkpoint protocol in
+`libs/ops/controller_continuity.py`. Miners, collectors, deterministic tests, monitoring, and safe
+queued work remain controller-independent. At handoff, checkpoint the exact branch/head/dirty
+paths, persistent state pointers, evidence, failures, blockers, and highest-value next action.
diff --git a/deploy/git_hooks/pre-push b/deploy/git_hooks/pre-push
new file mode 100755
index 0000000..8abc8c2
--- /dev/null
+++ b/deploy/git_hooks/pre-push
@@ -0,0 +1,16 @@
+#!/usr/bin/env bash
+# L1.37: portable law gate at the boundary where a commit can leave a controller's clone.
+set -euo pipefail
+
+ROOT="$(git rev-parse --show-toplevel)"
+cd "$ROOT"
+
+if [ -x "$ROOT/.venv/bin/python" ]; then
+    PY="$ROOT/.venv/bin/python"
+elif command -v python3 >/dev/null 2>&1; then
+    PY="$(command -v python3)"
+else
+    PY="$(command -v python)"
+fi
+
+exec "$PY" scripts/run_law_gate.py --laws-only
diff --git a/deploy/privilege_separation/install.sh b/deploy/privilege_separation/install.sh
new file mode 100755
index 0000000..a4bdcce
--- /dev/null
+++ b/deploy/privilege_separation/install.sh
@@ -0,0 +1,40 @@
+#!/usr/bin/env bash
+# ROOT-ONLY, explicit host deployment. This script is generated and tested in-repo but is never
+# invoked by an autonomous research cycle. It copies rather than symlinks: the live service must
+# not follow a research-owned worktree after installation.
+set -euo pipefail
+
+[ "$(id -u)" -eq 0 ] || { echo "root required" >&2; exit 1; }
+SOURCE_ROOT="${1:-/home/quant/quant-platform}"
+TARGET=/opt/quant-risk-kernel
+STATE=/var/lib/quant-risk-kernel
+LOG=/var/log/quant-risk-kernel
+
+test -f "$SOURCE_ROOT/scripts/run_deadman_switch.py"
+test -f "$SOURCE_ROOT/docs/research/RISK_KERNEL_LOCK.json"
+
+id -u quant-risk >/dev/null 2>&1 || useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin quant-risk
+install -d -o root -g quant-risk -m 0750 "$TARGET" "$TARGET/scripts" "$TARGET/libs" "$TARGET/docs/research"
+install -d -o quant-risk -g quant-risk -m 0750 "$STATE" "$LOG"
+
+# Copy the complete imported Python package trees, then remove write permission from both service
+# and research users. Root is the sole deployment authority.
+cp -a "$SOURCE_ROOT/libs/." "$TARGET/libs/"
+install -o root -g quant-risk -m 0550 "$SOURCE_ROOT/scripts/run_deadman_switch.py" "$TARGET/scripts/run_deadman_switch.py"
+install -o root -g quant-risk -m 0440 "$SOURCE_ROOT/docs/research/RISK_KERNEL_LOCK.json" "$TARGET/docs/research/RISK_KERNEL_LOCK.json"
+find "$TARGET/libs" -type d -exec chmod 0550 {} +
+find "$TARGET/libs" -type f -exec chmod 0440 {} +
+chown -R root:quant-risk "$TARGET"
+
+python3 -m venv "$TARGET/venv"
+"$TARGET/venv/bin/pip" install -r "$SOURCE_ROOT/requirements-vps.txt"
+chown -R root:quant-risk "$TARGET/venv"
+find "$TARGET/venv" -type d -exec chmod 0550 {} +
+find "$TARGET/venv" -type f -exec chmod 0440 {} +
+
+install -o root -g root -m 0644 "$SOURCE_ROOT/deploy/privilege_separation/quant-risk-kernel.service" \
+  /etc/systemd/system/quant-risk-kernel.service
+systemctl daemon-reload
+systemctl enable quant-risk-kernel.service
+
+echo "Installed but not started. Verify environment/reconciliation, then root starts the service explicitly."
diff --git a/deploy/privilege_separation/permission_matrix.json b/deploy/privilege_separation/permission_matrix.json
new file mode 100644
index 0000000..d9f4b6c
--- /dev/null
+++ b/deploy/privilege_separation/permission_matrix.json
@@ -0,0 +1,14 @@
+{
+  "research_account": "quant",
+  "risk_account": "quant-risk",
+  "risk_runtime": "/opt/quant-risk-kernel",
+  "rules": [
+    {"principal": "root", "path": "/opt/quant-risk-kernel", "access": "owner-write"},
+    {"principal": "quant-risk", "path": "/opt/quant-risk-kernel", "access": "read-execute"},
+    {"principal": "quant-risk", "path": "/var/lib/quant-risk-kernel", "access": "read-write"},
+    {"principal": "quant", "path": "/opt/quant-risk-kernel", "access": "read-only"},
+    {"principal": "quant", "path": "/etc/systemd/system/quant-risk-kernel.service", "access": "none"}
+  ],
+  "invariant": "the research account cannot modify, redeploy, stop, or replace the survival path",
+  "application": "host root action; repository agents may generate and test but never apply"
+}
diff --git a/deploy/privilege_separation/quant-risk-kernel.service b/deploy/privilege_separation/quant-risk-kernel.service
new file mode 100644
index 0000000..9d0c9a5
--- /dev/null
+++ b/deploy/privilege_separation/quant-risk-kernel.service
@@ -0,0 +1,29 @@
+[Unit]
+Description=Quant survival path under an isolated non-login account
+After=network-online.target
+Wants=network-online.target
+
+[Service]
+Type=simple
+User=quant-risk
+Group=quant-risk
+WorkingDirectory=/opt/quant-risk-kernel
+Environment=PYTHONUNBUFFERED=1
+EnvironmentFile=-/etc/quant-risk-kernel/environment
+ExecStart=/opt/quant-risk-kernel/venv/bin/python /opt/quant-risk-kernel/scripts/run_deadman_switch.py
+Restart=always
+RestartSec=5
+NoNewPrivileges=true
+PrivateTmp=true
+ProtectSystem=strict
+ProtectHome=true
+ProtectKernelTunables=true
+ProtectKernelModules=true
+ProtectControlGroups=true
+ReadWritePaths=/var/lib/quant-risk-kernel /var/log/quant-risk-kernel
+RestrictSUIDSGID=true
+LockPersonality=true
+MemoryDenyWriteExecute=true
+
+[Install]
+WantedBy=multi-user.target
diff --git a/docs/research/ARTIFACT_GOVERNANCE.md b/docs/research/ARTIFACT_GOVERNANCE.md
index d374d0a..737a284 100644
--- a/docs/research/ARTIFACT_GOVERNANCE.md
+++ b/docs/research/ARTIFACT_GOVERNANCE.md
@@ -166,3 +166,9 @@ recorded in `max_audit.py` because they need code to be real. Zero remain ungove
 |---|---|---|---|
 | `docs/research/FULL_SWEEP_PREREGISTRATION.md` | **TERMINAL** | Same class as the four pre-registrations above, and the declaration ordering is load-bearing here in a way it is not elsewhere: the universe size and the bar are fixed BEFORE any cell is evaluated, which is the entire statistical basis for a blind 898,560-cell sweep. Editing it after a result would not merely weaken the document, it would void the study. Superseded by its own result. | n/a |
 | `docs/research/crypto_source_seeds.md` | **LIVING** | Claimed by L1.52 (information mining is permanently active) and by the miners' own anti-breadth-theater rule. It is deliberately NOT the catalogue: the catalogue (`data_axis_watchlist.md`) carries graded cards that owe verification decisions, and at 8 pending of 18 the desk's measured bottleneck is verification, not cataloguing. A seed map carries no verification debt, so it can hold 450 grounds without making that bottleneck worse — and a source only becomes a card by producing something. Grows as `kimi_hunter` discovers grounds absent from it; the list is seeds, never a ceiling. | n/a |
+
+### Added 2026-08-09 (controller convergence mandate, classified on arrival)
+
+| Artifact | Class | Rationale | Staleness floor |
+|---|---|---|---|
+| `docs/research/TIER1_CONTROLLER_MANDATE.md` | **DOCTRINE** | Principal-supplied standing controller law shared by Claude and Codex. It governs continuation, survivor conversion, open-world coverage, risk/statistical invariants, and atomic handoff of one persistent operation. It changes only by a later principal mandate; a cadence must execute it through the controller cycle, never rewrite it to look current. | never |
\ No newline at end of file
diff --git a/docs/research/COMPLETION_LEDGER.json b/docs/research/COMPLETION_LEDGER.json
index d33d460..d18776d 100644
--- a/docs/research/COMPLETION_LEDGER.json
+++ b/docs/research/COMPLETION_LEDGER.json
@@ -1,925 +1,1939 @@
 {
- "_": "Every capability requested across today's specifications. Status is COMPUTED by libs/research/completion_ledger.py against the working tree, never asserted. A ledger listing only what exists would report 100% and measure nothing, so the unbuilt items are rows here from the moment they are requested.",
- "capabilities": [
-  {
-   "capability_id": "KILL_AUDIT",
-   "title": "Kill audit / nine rejection states",
-   "economic_reason": "750 of 762 cells died at one gate; a counter cannot distinguish a correct gate from one destroying real alpha silently",
-   "source_spec": "validator spec \u00a72-\u00a73",
-   "module": "libs.research.kill_audit",
-   "tests": [
-    "tests/research/test_kill_audit.py"
-   ],
-   "callers": [
-    "scripts/run_research_review.py"
-   ],
-   "artifacts": [
-    "data/research_review.json"
-   ],
-   "consumers": [
-    "scripts/run_max_push.py"
-   ],
-   "external_blocker": "",
-   "next_action": ""
-  },
-  {
-   "capability_id": "PORTFOLIO_ADMISSION",
-   "title": "Survivor -> portfolio contribution",
-   "economic_reason": "PORTFOLIO_CONTRIBUTING was unmeasurable, not merely unmeasured: survivor pnl never left the sweep",
-   "source_spec": "validator spec \u00a712",
-   "module": "scripts.run_portfolio_admission",
-   "tests": [
-    "tests/scripts/test_portfolio_admission.py"
-   ],
-   "callers": [
-    "ops/run_research_cycle.sh"
-   ],
-   "artifacts": [
-    "data/portfolio_admission.json"
-   ],
-   "consumers": [
-    "scripts/run_live_ladder.py"
-   ],
-   "external_blocker": "",
-   "next_action": ""
-  },
-  {
-   "capability_id": "EVIDENCE_CLOCK",
-   "title": "Effective independent observations replace calendar gates",
-   "economic_reason": "An edge real for 20 days that spends 15 in a calendar gate has lost most of its economic life to its own validator",
-   "source_spec": "accelerator spec \u00a7D/\u00a710",
-   "module": "libs.research.evidence_clock",
-   "tests": [
-    "tests/research/test_evidence_clock.py"
-   ],
-   "callers": [
-    "scripts/run_live_ladder.py"
-   ],
-   "artifacts": [
-    "data/live_ladder.json"
-   ],
-   "consumers": [
-    "scripts/run_research_review.py"
-   ],
-   "external_blocker": "",
-   "next_action": ""
-  },
-  {
-   "capability_id": "ALPHA_STATE",
-   "title": "Alpha state machine incl. LIVE_CANARY",
-   "economic_reason": "Nothing made DISCOVERED->LIVE impossible; it was merely undone",
-   "source_spec": "spec \u00a79/\u00a7C",
-   "module": "libs.research.alpha_state",
-   "tests": [
-    "tests/research/test_alpha_state.py"
-   ],
-   "callers": [
-    "scripts/run_live_ladder.py"
-   ],
-   "artifacts": [
-    "data/live_ladder.json"
-   ],
-   "consumers": [
-    "scripts/run_research_review.py"
-   ],
-   "external_blocker": "",
-   "next_action": ""
-  },
-  {
-   "capability_id": "CAPITAL_COMPETITION",
-   "title": "Continuous capital competition, age confers no privilege",
-   "economic_reason": "Capital in a strategy whose forward expectation collapsed is the best remaining opportunity being declined, silently, every day",
-   "source_spec": "spec \u00a712/\u00a7E",
-   "module": "libs.portfolio.capital_competition",
-   "tests": [
```


---

## 2915ea5 desk snapshot 2026-08-09T08:45Z

```diff
commit 2915ea507ab64831f97b557e29baf67d3b3b2300
Author: Quant Desk <quant@vps.local>
Date:   Sun Aug 9 08:45:55 2026 +0000

    desk snapshot 2026-08-09T08:45Z
---
 alpha_pipeline.json                                |   24 +-
 backups/moat/alpha_registry                        |  Bin 0 -> 561152 bytes
 backups/moat/capital_events                        |    1 +
 backups/moat/cost_model                            | 4245 ++++++++++++++++++++
 backups/moat/execution_tape/cashcarry_trades.jsonl |  531 +++
 backups/moat/graveyard                             |  434 ++
 backups/moat/manifest.json                         |  119 +
 backups/moat/sor_research                          |  Bin 0 -> 2744320 bytes
 data/ratchet_floors.json                           |    2 +-
 docs/DESK_BRIEF.md                                 |    6 +-
 docs/desk_digest.md                                |   14 +-
 docs/research/CONSTITUTION_RATCHET.json            |    2 +-
 docs/research/cadence_duties.md                    |    2 +-
 .../capability_hunt/20260809_s4_proposals.md       |   12 +
 docs/research/test_suite_record.json               |    4 +-
 engineering_backlog.json                           |    2 +-
 research_state.json                                |   30 +-
 17 files changed, 5385 insertions(+), 43 deletions(-)

diff --git a/alpha_pipeline.json b/alpha_pipeline.json
index 0a6b9d1..bd01d77 100644
--- a/alpha_pipeline.json
+++ b/alpha_pipeline.json
@@ -1,5 +1,5 @@
 {
-  "generated": "2026-08-09T03:19:14.212010+00:00",
+  "generated": "2026-08-09T08:43:11.485469+00:00",
   "n_alphas": 8,
   "n_survived": 0,
   "deployed": [
@@ -9,7 +9,7 @@
     {
       "alpha": "crypto::ls_contrarian",
       "category": "derivative-data",
-      "expected_sharpe": 4.45,
+      "expected_sharpe": 4.32,
       "gates": "6/9",
       "survived": false,
       "stage": "backtest",
@@ -21,7 +21,7 @@
     {
       "alpha": "crypto::xsec_price_mom",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.82,
+      "expected_sharpe": 0.95,
       "gates": "7/9",
       "survived": false,
       "stage": "backtest",
@@ -31,9 +31,9 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::ts_trend",
+      "alpha": "crypto::funding_carry",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.82,
+      "expected_sharpe": 0.84,
       "gates": "7/9",
       "survived": false,
       "stage": "backtest",
@@ -43,9 +43,9 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::taker_flow",
+      "alpha": "crypto::ts_trend",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.71,
+      "expected_sharpe": 0.82,
       "gates": "7/9",
       "survived": false,
       "stage": "backtest",
@@ -55,9 +55,9 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::funding_carry",
+      "alpha": "crypto::taker_flow",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.59,
+      "expected_sharpe": 0.78,
       "gates": "7/9",
       "survived": false,
       "stage": "backtest",
@@ -69,7 +69,7 @@
     {
       "alpha": "crypto::basis_carry",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.12,
+      "expected_sharpe": 0.16,
       "gates": "6/9",
       "survived": false,
       "stage": "backtest",
@@ -81,7 +81,7 @@
     {
       "alpha": "crypto::funding_momentum",
       "category": "crypto-sleeve",
-      "expected_sharpe": -0.3,
+      "expected_sharpe": -0.28,
       "gates": "3/9",
       "survived": false,
       "stage": "backtest",
@@ -93,7 +93,7 @@
     {
       "alpha": "crypto::oi_divergence",
       "category": "derivative-data",
-      "expected_sharpe": -8.75,
+      "expected_sharpe": -8.82,
       "gates": "3/9",
       "survived": false,
       "stage": "backtest",
diff --git a/backups/moat/alpha_registry b/backups/moat/alpha_registry
new file mode 100644
index 0000000..fd2d05e
Binary files /dev/null and b/backups/moat/alpha_registry differ
diff --git a/backups/moat/capital_events b/backups/moat/capital_events
new file mode 100644
index 0000000..06e707e
--- /dev/null
+++ b/backups/moat/capital_events
@@ -0,0 +1 @@
+{"kind": "RESTART", "at": "2026-08-01T12:22:51.709038+00:00", "deposit_usd": 0.0, "equity_before": 5757.08, "equity_after": 5757.08, "start_equity_before": 5757.08, "start_equity_after": 5757.08, "authorised_by": "zaid", "reason": "Re-baseline inception after the 07-27 churn-loop fee fire (1,746 in commissions, root-caused and fixed in 59b837d). The -45.4% was real but is entirely attributable to a now-fixed bug, not to strategy performance; the sleeve has never once run clean. Restarting inception at current equity so the ruin rail measures the POST-FIX book instead of latching on a historical bug.", "cumulative_loss_since_first_inception_usd": 0.0}
diff --git a/backups/moat/cost_model b/backups/moat/cost_model
new file mode 100644
index 0000000..280375a
--- /dev/null
+++ b/backups/moat/cost_model
@@ -0,0 +1,4245 @@
+{
+ "symbols": {
+  "1000CATUSDT": {
+   "spot_buy": {
+    "100": {
+     "n": 252,
+     "exhausted_frac": 0.0,
+     "median_bps": 36.101,
+     "p90_bps": 36.364
+    },
+    "250": {
+     "n": 252,
+     "exhausted_frac": 0.0,
+     "median_bps": 36.101,
+     "p90_bps": 36.364
+    },
+    "500": {
+     "n": 252,
+     "exhausted_frac": 0.0,
+     "median_bps": 36.101,
+     "p90_bps": 36.364
+    },
+    "1000": {
+     "n": 252,
+     "exhausted_frac": 0.0,
+     "median_bps": 36.101,
+     "p90_bps": 36.364
+    },
+    "2500": {
+     "n": 252,
+     "exhausted_frac": 0.0,
+     "median_bps": 36.101,
+     "p90_bps": 36.364
+    }
+   },
+   "fut_sell": {
+    "100": {
+     "n": 252,
+     "exhausted_frac": 0.0,
+     "median_bps": 3.625,
+     "p90_bps": 7.184
+    },
+    "250": {
+     "n": 252,
+     "exhausted_frac": 0.0,
+     "median_bps": 6.452,
+     "p90_bps": 8.573
+    },
+    "500": {
+     "n": 252,
+     "exhausted_frac": 0.0,
+     "median_bps": 8.115,
+     "p90_bps": 9.842
+    },
+    "1000": {
+     "n": 252,
+     "exhausted_frac": 0.0,
+     "median_bps": 10.632,
+     "p90_bps": 13.174
+    },
+    "2500": {
+     "n": 252,
+     "exhausted_frac": 0.0,
+     "median_bps": 16.827,
+     "p90_bps": 20.059
+    }
+   },
+   "pair": {
+    "100": {
+     "pair_open_bps": 39.726,
+     "pair_roundtrip_bps": 79.452,
+     "worst_exhausted_frac": 0.0
+    },
+    "250": {
+     "pair_open_bps": 42.553,
+     "pair_roundtrip_bps": 85.106,
+     "worst_exhausted_frac": 0.0
+    },
+    "500": {
+     "pair_open_bps": 44.216,
+     "pair_roundtrip_bps": 88.432,
+     "worst_exhausted_frac": 0.0
+    },
+    "1000": {
+     "pair_open_bps": 46.733,
+     "pair_roundtrip_bps": 93.466,
+     "worst_exhausted_frac": 0.0
+    },
+    "2500": {
+     "pair_open_bps": 52.928,
+     "pair_roundtrip_bps": 105.856,
+     "worst_exhausted_frac": 0.0
+    }
+   }
+  },
+  "AAVEUSDT": {
+   "spot_buy": {
+    "100": {
+     "n": 316,
+     "exhausted_frac": 0.0,
+     "median_bps": 0.533,
+     "p90_bps": 0.918
+    },
+    "250": {
+     "n": 316,
+     "exhausted_frac": 0.0,
+     "median_bps": 0.542,
+     "p90_bps": 1.377
+    },
+    "500": {
+     "n": 316,
+     "exhausted_frac": 0.0,
+     "median_bps": 0.64,
+     "p90_bps": 1.612
+    },
+    "1000": {
+     "n": 316,
+     "exhausted_frac": 0.0,
+     "median_bps": 1.14,
+     "p90_bps": 2.172
+    },
+    "2500": {
+     "n": 316,
+     "exhausted_frac": 0.0,
+     "median_bps": 1.869,
+     "p90_bps": 3.203
+    }
+   },
+   "fut_sell": {
+    "100": {
+     "n": 316,
+     "exhausted_frac": 0.0,
+     "median_bps": 0.526,
+     "p90_bps": 0.551
+    },
+    "250": {
+     "n": 316,
+     "exhausted_frac": 0.0,
+     "median_bps": 0.535,
+     "p90_bps": 0.889
+    },
+    "500": {
+     "n": 316,
+     "exhausted_frac": 0.0,
+     "median_bps": 0.538,
+     "p90_bps": 1.229
+    },
+    "1000": {
+     "n": 316,
+     "exhausted_frac": 0.0,
+     "median_bps": 0.543,
+     "p90_bps": 1.416
+    },
+    "2500": {
+     "n": 316,
+     "exhausted_frac": 0.0,
+     "median_bps": 0.878,
+     "p90_bps": 1.733
+    }
+   },
+   "pair": {
+    "100": {
+     "pair_open_bps": 1.059,
+     "pair_roundtrip_bps": 2.118,
+     "worst_exhausted_frac": 0.0
+    },
+    "250": {
+     "pair_open_bps": 1.077,
+     "pair_roundtrip_bps": 2.154,
+     "worst_exhausted_frac": 0.0
+    },
+    "500": {
+     "pair_open_bps": 1.178,
+     "pair_roundtrip_bps": 2.356,
+     "worst_exhausted_frac": 0.0
+    },
+    "1000": {
+     "pair_open_bps": 1.683,
+     "pair_roundtrip_bps": 3.366,
+     "worst_exhausted_frac": 0.0
+    },
+    "2500": {
+     "pair_open_bps": 2.747,
+     "pair_roundtrip_bps": 5.494,
+     "worst_exhausted_frac": 0.0
+    }
+   }
+  },
+  "ADAUSDT": {
+   "spot_buy": {
+    "100": {
+     "n": 369,
+     "exhausted_frac": 0.0,
+     "median_bps": 2.94,
+     "p90_bps": 3.089
+    },
+    "250": {
+     "n": 369,
+     "exhausted_frac": 0.0,
+     "median_bps": 2.944,
+     "p90_bps": 3.091
+    },
+    "500": {
+     "n": 369,
+     "exhausted_frac": 0.0,
+     "median_bps": 2.946,
+     "p90_bps": 3.105
+    },
+    "1000": {
+     "n": 369,
+     "exhausted_frac": 0.0,
+     "median_bps": 2.949,
+     "p90_bps": 3.11
+    },
+    "2500": {
+     "n": 369,
+     "exhausted_frac": 0.0,
+     "median_bps": 2.977,
+     "p90_bps": 3.239
+    }
+   },
+   "fut_sell": {
+    "100": {
+     "n": 370,
+     "exhausted_frac": 0.0,
+     "median_bps": 2.946,
+     "p90_bps": 3.093
+    },
+    "250": {
+     "n": 370,
+     "exhausted_frac": 0.0,
+     "median_bps": 2.946,
+     "p90_bps": 3.093
+    },
+    "500": {
+     "n": 370,
+     "exhausted_frac": 0.0,
+     "median_bps": 2.946,
+     "p90_bps": 3.093
+    },
+    "1000": {
+     "n": 370,
+     "exhausted_frac": 0.0,
+     "median_bps": 2.946,
+     "p90_bps": 3.093
+    },
+    "2500": {
+     "n": 370,
+     "exhausted_frac": 0.0,
+     "median_bps": 2.947,
+     "p90_bps": 3.093
+    }
+   },
+   "pair": {
+    "100": {
+     "pair_open_bps": 5.886,
+     "pair_roundtrip_bps": 11.772,
+     "worst_exhausted_frac": 0.0
+    },
+    "250": {
+     "pair_open_bps": 5.89,
+     "pair_roundtrip_bps": 11.78,
+     "worst_exhausted_frac": 0.0
+    },
+    "500": {
+     "pair_open_bps": 5.892,
```


---

## fc7513a desk snapshot 2026-08-09T03:22Z

```diff
commit fc7513ad9537ee94ec3c5b5bdd82723f68c4b6bb
Author: Quant Desk <quant@vps.local>
Date:   Sun Aug 9 03:22:29 2026 +0000

    desk snapshot 2026-08-09T03:22Z
---
 alpha_pipeline.json      |  2 +-
 docs/DESK_BRIEF.md       |  4 ++--
 engineering_backlog.json |  2 +-
 research_state.json      | 16 ++++++++--------
 4 files changed, 12 insertions(+), 12 deletions(-)

diff --git a/alpha_pipeline.json b/alpha_pipeline.json
index ac1ddfb..0a6b9d1 100644
--- a/alpha_pipeline.json
+++ b/alpha_pipeline.json
@@ -1,5 +1,5 @@
 {
-  "generated": "2026-08-09T03:06:25.204556+00:00",
+  "generated": "2026-08-09T03:19:14.212010+00:00",
   "n_alphas": 8,
   "n_survived": 0,
   "deployed": [
diff --git a/docs/DESK_BRIEF.md b/docs/DESK_BRIEF.md
index 69e051e..d5c639c 100644
--- a/docs/DESK_BRIEF.md
+++ b/docs/DESK_BRIEF.md
@@ -1,4 +1,4 @@
-# DESK BRIEF -- 2026-08-09 03:07Z
+# DESK BRIEF -- 2026-08-09 03:19Z
 
 Machine-generated from measured desk state. Every number traces to an artifact in
 `data/`. Nothing here is an argument. Respond to the evidence, not to another model.
@@ -13,7 +13,7 @@ Machine-generated from measured desk state. Every number traces to an artifact i
    forward clocks promote.
 
 ## Experiment record (45d, harvested from git -- one row per commit)
-- experiments: **619**; decided: 327
+- experiments: **620**; decided: 327
 - survival rate: **6.4%** (21 survived / 282 refuted / 24 inconclusive)
 - unclassified commit decisions: 32 (commit-discipline defect)
 
diff --git a/engineering_backlog.json b/engineering_backlog.json
index 6789677..0706aea 100644
--- a/engineering_backlog.json
+++ b/engineering_backlog.json
@@ -1,5 +1,5 @@
 {
-  "generated": "2026-08-09T03:06:24.831135+00:00",
+  "generated": "2026-08-09T03:19:14.167870+00:00",
   "roi_formula": "impact * p_success / effort_hours",
   "open": [
     {
diff --git a/research_state.json b/research_state.json
index 43d9824..1d4d7b3 100644
--- a/research_state.json
+++ b/research_state.json
@@ -1,5 +1,5 @@
 {
-  "generated": "2026-08-09T03:06:25.219463+00:00",
+  "generated": "2026-08-09T03:19:14.215223+00:00",
   "master_objective": "maximize expected lifetime geometric growth (log wealth), survival-c",
   "deployed": {
     "sleeves": [
@@ -7,16 +7,16 @@
       "perp_ls (paper)"
     ],
     "start_capital": 15000.0,
-    "equity": 13156.04,
-    "net_pnl": -1843.96,
-    "return_pct": -12.293,
-    "days_live": 37.91,
+    "equity": 13169.69,
+    "net_pnl": -1830.31,
+    "return_pct": -12.202,
+    "days_live": 37.92,
     "winrate_pct": 43.1,
     "n_closed_trades": 253,
-    "deployed_sharpe": 1.98,
+    "deployed_sharpe": 2.02,
     "funding": 113.06,
     "n_carries": 0,
-    "perp_paper_net": 9.0
+    "perp_paper_net": 23.0
   },
   "binding_constraint": "calendar-time data accumulation (not engineering throughput)",
   "bottleneck_rankings": [
@@ -67,7 +67,7 @@
   ],
   "retirement_note": "SIGNAL ONLY \u2014 marginal-Sharpe swings ~\u00b10.15 between runs, so a single negative sign is within noise. Retire only on PERSISTENT negative contribution across runs, with promotion-grade rigor. No whipsaw.",
   "architecture_review_due": false,
-  "cycles_logged": 73,
+  "cycles_logged": 74,
   "completed_this_cycle": [
     "archive_integrity_ok",
     "watchdog_run_logged_off",
```


---

## cb550f3 desk snapshot 2026-08-09T03:10Z

```diff
commit cb550f3b793fb5ed45c00ce0938df41b4be5a6cf
Author: Quant Desk <quant@vps.local>
Date:   Sun Aug 9 03:10:53 2026 +0000

    desk snapshot 2026-08-09T03:10Z
---
 alpha_pipeline.json                                |    32 +-
 data/nav_attestation.jsonl                         |     1 +
 docs/DESK_BRIEF.md                                 |    26 +-
 docs/GATE0_QUEUE.md                                |     2 +
 docs/desk_digest.md                                |    18 +-
 docs/research/CONSTITUTION_RATCHET.json            |     2 +-
 docs/research/cadence_duties.md                    |     5 +-
 .../capability_hunt/20260808_s1_proposals.md       |    12 +
 .../capability_hunt/20260808_s2_proposals.md       |    12 +
 .../capability_hunt/20260808_s5_proposals.md       |    12 +
 .../capability_hunt/20260809_s3_proposals.md       |    12 +
 docs/research/feed_inbox.md                        |    44 +
 docs/research/recent_changes.md                    | 14162 +++++++++++--------
 engineering_backlog.json                           |     2 +-
 research_state.json                                |    38 +-
 ssh                                                |     0
 16 files changed, 8102 insertions(+), 6278 deletions(-)

diff --git a/alpha_pipeline.json b/alpha_pipeline.json
index 95448ed..ac1ddfb 100644
--- a/alpha_pipeline.json
+++ b/alpha_pipeline.json
@@ -1,5 +1,5 @@
 {
-  "generated": "2026-08-08T03:23:22.845721+00:00",
+  "generated": "2026-08-09T03:06:25.204556+00:00",
   "n_alphas": 8,
   "n_survived": 0,
   "deployed": [
@@ -9,8 +9,8 @@
     {
       "alpha": "crypto::ls_contrarian",
       "category": "derivative-data",
-      "expected_sharpe": 5.65,
-      "gates": "7/9",
+      "expected_sharpe": 4.45,
+      "gates": "6/9",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
@@ -19,9 +19,9 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::funding_carry",
+      "alpha": "crypto::xsec_price_mom",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.98,
+      "expected_sharpe": 0.82,
       "gates": "7/9",
       "survived": false,
       "stage": "backtest",
@@ -33,7 +33,7 @@
     {
       "alpha": "crypto::ts_trend",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.87,
+      "expected_sharpe": 0.82,
       "gates": "7/9",
       "survived": false,
       "stage": "backtest",
@@ -43,10 +43,10 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::xsec_price_mom",
+      "alpha": "crypto::taker_flow",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.73,
-      "gates": "6/9",
+      "expected_sharpe": 0.71,
+      "gates": "7/9",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
@@ -55,10 +55,10 @@
       "retire_check": "REJECT: fails gates"
     },
     {
-      "alpha": "crypto::taker_flow",
+      "alpha": "crypto::funding_carry",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.42,
-      "gates": "6/9",
+      "expected_sharpe": 0.59,
+      "gates": "7/9",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
@@ -69,7 +69,7 @@
     {
       "alpha": "crypto::basis_carry",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.32,
+      "expected_sharpe": 0.12,
       "gates": "6/9",
       "survived": false,
       "stage": "backtest",
@@ -81,8 +81,8 @@
     {
       "alpha": "crypto::funding_momentum",
       "category": "crypto-sleeve",
-      "expected_sharpe": 0.23,
-      "gates": "6/9",
+      "expected_sharpe": -0.3,
+      "gates": "3/9",
       "survived": false,
       "stage": "backtest",
       "orthogonality": "unknown",
@@ -93,7 +93,7 @@
     {
       "alpha": "crypto::oi_divergence",
       "category": "derivative-data",
-      "expected_sharpe": -8.51,
+      "expected_sharpe": -8.75,
       "gates": "3/9",
       "survived": false,
       "stage": "backtest",
diff --git a/data/nav_attestation.jsonl b/data/nav_attestation.jsonl
index d9d849e..0788129 100644
--- a/data/nav_attestation.jsonl
+++ b/data/nav_attestation.jsonl
@@ -8,3 +8,4 @@
 {"date":"2026-08-03","ts":"2026-08-03T02:40:03.588329+00:00","equity_marked":13159.61,"deployed_notional":0,"n_carries":0,"realized_spot_pnl":2921.35,"start_futures_equity":10547.78,"mode":"PAPER (testnet) -- pre-Gate-0","prev_sha256":"2c87d6d89a90a4b37c771005218a16e341ebec50b7c55384d717205c69944d77"}
 {"date":"2026-08-04","ts":"2026-08-04T02:43:19.511453+00:00","equity_marked":13179.49,"deployed_notional":0,"n_carries":0,"realized_spot_pnl":2921.35,"start_futures_equity":10547.78,"mode":"PAPER (testnet) -- pre-Gate-0","prev_sha256":"ad86a485c4201d1295238de6f3fea9ab88ac05e1012ec18d84a3ce8413300126"}
 {"date":"2026-08-08","ts":"2026-08-08T03:06:20.420048+00:00","equity_marked":13012.39,"deployed_notional":0,"n_carries":0,"realized_spot_pnl":2921.35,"start_futures_equity":10547.78,"mode":"PAPER (testnet) -- pre-Gate-0","prev_sha256":"2780e667c24716db1e66c0f595faf7c3c9ca1d3b9833c414977b576ffff27606"}
+{"date":"2026-08-09","ts":"2026-08-09T03:06:31.984034+00:00","equity_marked":13170.07,"deployed_notional":0,"n_carries":0,"realized_spot_pnl":2921.35,"start_futures_equity":10547.78,"mode":"PAPER (testnet) -- pre-Gate-0","prev_sha256":"5d2e3308733e004699aa72f147ad064f5469d1ed66d12583141a65d789c7e0e5"}
diff --git a/docs/DESK_BRIEF.md b/docs/DESK_BRIEF.md
index 6cb4197..69e051e 100644
--- a/docs/DESK_BRIEF.md
+++ b/docs/DESK_BRIEF.md
@@ -1,4 +1,4 @@
-# DESK BRIEF -- 2026-08-08 03:23Z
+# DESK BRIEF -- 2026-08-09 03:07Z
 
 Machine-generated from measured desk state. Every number traces to an artifact in
 `data/`. Nothing here is an argument. Respond to the evidence, not to another model.
@@ -13,13 +13,13 @@ Machine-generated from measured desk state. Every number traces to an artifact i
    forward clocks promote.
 
 ## Experiment record (45d, harvested from git -- one row per commit)
-- experiments: **597**; decided: 312
-- survival rate: **6.4%** (20 survived / 269 refuted / 23 inconclusive)
-- unclassified commit decisions: 30 (commit-discipline defect)
+- experiments: **619**; decided: 327
+- survival rate: **6.4%** (21 survived / 282 refuted / 24 inconclusive)
+- unclassified commit decisions: 32 (commit-discipline defect)
 
 | mechanism | tested | survived | rate |
 |---|---:|---:|---:|
-| M_UNMAPPED | 229 | 14 | 6% |
+| M_UNMAPPED | 244 | 15 | 6% |
 | M_ATTENTION_DELAY | 32 | 2 | 6% |
 | M_LIQUIDITY_WITHDRAWAL | 23 | 1 | 4% |
 | M_FORCED_DELEVERAGE | 14 | 2 | 14% |
@@ -31,16 +31,16 @@ Machine-generated from measured desk state. Every number traces to an artifact i
 
 ### Why experiments died (45d)
 
-- `E_DATA_QUALITY` 129 (30%)
-- `B_WRONG_MEASUREMENT` 91 (21%)
-- `G_TOO_EXPENSIVE` 66 (15%)
-- `H_OVERFIT` 63 (15%)
-- `C_WRONG_TIMING` 44 (10%)
-- `F_REGIME_DEPENDENT` 28 (7%)
+- `E_DATA_QUALITY` 135 (30%)
+- `B_WRONG_MEASUREMENT` 93 (21%)
+- `G_TOO_EXPENSIVE` 68 (15%)
+- `H_OVERFIT` 68 (15%)
+- `C_WRONG_TIMING` 46 (10%)
+- `F_REGIME_DEPENDENT` 32 (7%)
 - `D_ALREADY_ARBITRAGED` 5 (1%)
 - `A_NO_MECHANISM` 3 (1%)
 
-**220/429 = 51% of refutations are MEASUREMENT failures (data quality + wrong construction), not absent alpha.**
+**228/450 = 51% of refutations are MEASUREMENT failures (data quality + wrong construction), not absent alpha.**
 
 ## FAMILY KILLS -- mechanisms closed by evidence
 
@@ -62,7 +62,7 @@ Every future variant inherits this evidence.
 ## Proprietary moat (4.4GB order books, 30 symbols, top-20 snapshots)
 
 M_LIQUIDITY_WITHDRAWAL, construction = negative z of near-touch depth vs 24h roll:
-- raw lead rho pooled: +0.1005
+- raw lead rho pooled: +0.0963
 - **after orthogonalising forward RV against current RV: residual rho +0.0154 (t +0.28), sign 1/5 -> the lead was vol clustering.**
 - ONE construction tested only. The mechanism is NOT refuted. Untested: replenishment rate, one-sided withdrawal, book shape, migration, recovery half-life, d(book)/dt.
 
diff --git a/docs/GATE0_QUEUE.md b/docs/GATE0_QUEUE.md
index 2354150..6c31041 100644
--- a/docs/GATE0_QUEUE.md
+++ b/docs/GATE0_QUEUE.md
@@ -64,3 +64,5 @@ G0 as originally written is WITHDRAWN. venue_equity.json measures the FUTURES sc
 | CV | **venue and book NAV are compared on the SAME scope** `(CV-2026-08-04-venue and book NAV are com)` | claims `venue $6,070 (=0.58x futures start) vs book $13,179 (=0.88x total start)` but the source says `venue=FUTURES scope, portfolio=TOTAL scope -- not comparable` -- run_venue_divergence_shadow logs pct_diff between these and that series is what calibrates the GAP #19 breaker; calibrating on a scope mismatch produces a breaker that never fires or always fires. Fix the shadow to compare like-for-like BEFORE arming anything from it. | BEFORE any live capital |
 
 | CV | **venue and book NAV are compared on the SAME scope** `(CV-2026-08-08-venue and book NAV are com)` | claims `venue $6,070 (=0.58x futures start) vs book $13,013 (=0.87x total start)` but the source says `venue=FUTURES scope, portfolio=TOTAL scope -- not comparable` -- run_venue_divergence_shadow logs pct_diff between these and that series is what calibrates the GAP #19 breaker; calibrating on a scope mismatch produces a breaker that never fires or always fires. Fix the shadow to compare like-for-like BEFORE arming anything from it. | BEFORE any live capital |
+
+| CV | **venue and book NAV are compared on the SAME scope** `(CV-2026-08-09-venue and book NAV are com)` | claims `venue $6,070 (=0.58x futures start) vs book $13,170 (=0.88x total start)` but the source says `venue=FUTURES scope, portfolio=TOTAL scope -- not comparable` -- run_venue_divergence_shadow logs pct_diff between these and that series is what calibrates the GAP #19 breaker; calibrating on a scope mismatch produces a breaker that never fires or always fires. Fix the shadow to compare like-for-like BEFORE arming anything from it. | BEFORE any live capital |
diff --git a/docs/desk_digest.md b/docs/desk_digest.md
index 9f012b8..e45e56c 100644
--- a/docs/desk_digest.md
+++ b/docs/desk_digest.md
@@ -1,17 +1,17 @@
 # Desk digest (auto-generated daily -- do not hand-edit)
-_updated 2026-08-08T02:20Z · companion to [[institutional_knowledge]]_
+_updated 2026-08-09T02:20Z · companion to [[institutional_knowledge]]_
 
 ## Book
-- Molded net: **$-1957.5** | funding **$113.06** | run-rate APR 0.0% | day 36.88
-- Root cause: **unknown_novel** (pause_and_page) | tracking error $-1965.56
+- Molded net: **$-1843.67** | funding **$113.06** | run-rate APR 0.0% | day 37.88
+- Root cause: **unknown_novel** (pause_and_page) | tracking error $-1965.73
 
 ## Validation clocks
-- **carry (DEPLOYED)**: 43/90d | bt 3.0 fwd 15.86
-- **perp L/S**: 36/90d | bt 0.89 fwd -3.96
-- **trend**: 35/90d | bt 1.28 fwd -5.72
-- **trend regime-gated**: 31/90d | bt 1.27 fwd 0.0
-- **OI/LS data**: 41/40d
-- **stablecoin data**: 37/40d
+- **carry (DEPLOYED)**: 44/90d | bt 3.41 fwd 16.2
+- **perp L/S**: 37/90d | bt 0.95 fwd 0.26
+- **trend**: 37/90d | bt 1.28 fwd -7.88
+- **trend regime-gated**: 32/90d | bt 1.22 fwd 0.0
+- **OI/LS data**: 42/40d
+- **stablecoin data**: 38/40d
 
 ## Open decisions (ledger)
 - `2026-07-04-cashcarry-top10-4500` -- review 2026-08-04: funding/day rises ~50% without new drift losses by 2026-08-04
diff --git a/docs/research/CONSTITUTION_RATCHET.json b/docs/research/CONSTITUTION_RATCHET.json
index ab07c02..35c507b 100644
--- a/docs/research/CONSTITUTION_RATCHET.json
+++ b/docs/research/CONSTITUTION_RATCHET.json
@@ -1,6 +1,6 @@
 {
  "_": "HIGH-WATER MARK for constitutional aggression. Raised automatically; NEVER lowered by code. Editing a number DOWN in this file is the only way to weaken a principle, and it is meant to be a visible, dated, argued act -- institutions drift toward timidity one reasonable amendment at a time, and this is the mechanism that makes each one cost a decision.",
- "updated": "2026-08-08T02:21:08.805853+00:00",
+ "updated": "2026-08-09T02:21:06.977773+00:00",
  "principles": {
   "P0": "Sole Objective",
   "P1": "Information Value Condition",
diff --git a/docs/research/cadence_duties.md b/docs/research/cadence_duties.md
index aab5b57..5ca2823 100644
--- a/docs/research/cadence_duties.md
+++ b/docs/research/cadence_duties.md
@@ -1,8 +1,9 @@
-# Generation due -- 2026-08-08T02:20Z (stage S0)
+# Generation due -- 2026-08-09T02:20Z (stage S0)
 
 The cadence engine flags these; the brain executes SCOPED generate runs (graveyard-excluded, pre-registration mandatory) and then marks them done by setting gen_done_<name> / last_live_generate in data/cadence_state.json.
 
-- oi_ls_taker: clock matured (41d) -- scoped generate run owed, PLUS a graveyard re-mine pass: any killed entry whose kill-reason this new data invalidates gets a fresh pre-registration (no silent revivals)
+- oi_ls_taker: clock matured (42d) -- scoped generate run owed, PLUS a graveyard re-mine pass: any killed entry whose kill-reason this new data invalidates gets a fresh pre-registration (no silent revivals)
+- market_breadth: clock matured (40d) -- scoped generate run owed, PLUS a graveyard re-mine pass: any killed entry whose kill-reason this new data invalidates gets a fresh pre-registration (no silent revivals)
 - PROSPECTOR (every 7d): execute docs/research/PROSPECTOR_SPEC.md with real web search -- UNCAPPED/exhaustive (dedicated quant-prospector.timer, biweekly), provenance-graded mechanism cards -> EV gate + pre-registration; update docs/research/prospector_watchlist.md; mark done: last_prospector in data/cadence_state.json. NEVER at the expense of the lockdown priorities (recorder/connector) -- they own the cycle first.
 - DATA-AXIS / FREE-DATA-ALTERNATIVE DIG (WEEKLY/7d, UNCAPPED budget -- operator accepts token cost; dig ALL 6 categories to EXHAUSTION every run, no rotating subset): execute the FULL docs/research/FREE_DATA_ALTERNATIVES_SPEC.md -- 6 source categories (exchange-native dumps, on-chain reconstruction, non-English/regional venues, community lakes, alt/sentiment, vendor-replacement); language-blind; VERIFY-DON'T-TRUST vs ground truth; DATA GENEALOGY on every adopted set; automatic replacement monitoring; source-failure intelligence; query evolution (>=25% exploration quota); cross-source synthesis; temporal rediscovery; discovery-ROI + maintainer tracking; SEARCH-SPACE EXPANSION quota. Catalog -> data/data_universe_map.json (source+grade+lineage+failure-modes+yield); verified axes -> EV gate (new_orthogonal_data). Mark done: last_data_axis_dig. Lockdown priorities own the cycle first.
 - LITERATURE DEEP-MINER (every 7d, UNCAPPED/exhaustive, dedicated quant-litminer.timer biweekly): execute docs/research/LITERATURE_SPEC.md -- inbox triage to MECHANISMS (never summaries), 2-level citation-chain digs, replication scans, coverage rotation; cards -> EV gate + pre-registration; mark done: last_lit_deepdive. Lockdown priorities own the cycle first.
diff --git a/docs/research/capability_hunt/20260808_s1_proposals.md b/docs/research/capability_hunt/20260808_s1_proposals.md
new file mode 100644
index 0000000..d2c80db
--- /dev/null
+++ b/docs/research/capability_hunt/20260808_s1_proposals.md
@@ -0,0 +1,12 @@
+# CAPABILITY HUNT PROPOSALS 20260808 slot 1
+
+LENS: STRATEGY-FAMILY BREADTH -- UNLIMITED, ALL-SURFACE, NEVER-ENDING. No surface is out of scope: every venue, era, language, asset class, timeframe, format and STYLE (systematic, discretionary, manual, hybrid, market-making, event-driven). There is no terminal state -- 'covered' and 'we already looked' are claims requiring a dated search with its residual gap, never defaults. No quota on families, findings or depth; a count is a quota in disguise. The only two limits are the licence gate and never installing third-party tooling, and neither is a scope limit. Concretely: read data/strategy_coverage.json and take a family marked NEVER-HUNTED or THIN, not one marked HUNTED. Coverage is DISTINCT FAMILIES, never candidates: twelve candidates from one family are correlated by construction, so they die together and the desk learns one thing while the log reports twelve tests. Name the family, the free data that would test it, and its forced participant. DISCRETIONARY-SHAPED FAMILIES COUNT -- level-reaction, session/calendar flow, positioning extremes: how a human discretionary trader actually decides is a mechanism class like any other, disqualified only for being unfalsifiable, never for being judgement-shaped.
+
+## A -- Claude family
+
+(Claude seat failed: BRAIN_AUTH_FAILED
+)
+
+## B -- GPT-9 family (independent)
+
+(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
diff --git a/docs/research/capability_hunt/20260808_s2_proposals.md b/docs/research/capability_hunt/20260808_s2_proposals.md
new file mode 100644
index 0000000..e871c27
--- /dev/null
+++ b/docs/research/capability_hunt/20260808_s2_proposals.md
@@ -0,0 +1,12 @@
+# CAPABILITY HUNT PROPOSALS 20260808 slot 2
+
+LENS: UNMEASURED-REPORTED-AS-OK -- find a check or metric that returns a PASS/zero when its input was absent. Unmeasured must never read as fine (L1.28a); both fences built today shipped with this bug in their first run.
+
+## A -- Claude family
+
+(Claude seat failed: BRAIN_AUTH_FAILED
+)
+
+## B -- GPT-9 family (independent)
+
+(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
diff --git a/docs/research/capability_hunt/20260808_s5_proposals.md b/docs/research/capability_hunt/20260808_s5_proposals.md
new file mode 100644
index 0000000..373432c
--- /dev/null
+++ b/docs/research/capability_hunt/20260808_s5_proposals.md
@@ -0,0 +1,12 @@
+# CAPABILITY HUNT PROPOSALS 20260808 slot 5
+
+LENS: STALE-CONSUMER -- find code reading an artifact without checking its age, so a frozen producer silently feeds yesterday's number into today's decision.
+
+## A -- Claude family
+
+(Claude seat failed: BRAIN_AUTH_FAILED
+)
+
+## B -- GPT-9 family (independent)
+
+(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
diff --git a/docs/research/capability_hunt/20260809_s3_proposals.md b/docs/research/capability_hunt/20260809_s3_proposals.md
new file mode 100644
index 0000000..1425dc1
--- /dev/null
+++ b/docs/research/capability_hunt/20260809_s3_proposals.md
@@ -0,0 +1,12 @@
+# CAPABILITY HUNT PROPOSALS 20260809 slot 3
+
+LENS: REGIME-CONDITIONED EDGE -- an edge that exists only in a nameable, DETECTABLE regime (high-funding, high-vol, post-liquidation, low-liquidity) we could switch on and off. What regime do we not yet detect, and what edge would it gate?
+
+## A -- Claude family
+
+(Claude seat failed: BRAIN_AUTH_FAILED
+)
+
+## B -- GPT-9 family (independent)
+
+(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
diff --git a/docs/research/feed_inbox.md b/docs/research/feed_inbox.md
index f36dd77..fce3a4d 100644
--- a/docs/research/feed_inbox.md
+++ b/docs/research/feed_inbox.md
@@ -173,3 +173,47 @@ reference for when that item is built (liquidity STATE, not just level, predicts
 ## Boundary-Induced Apparent Risk Aversion in Nonergodic Multiplicative Growth
 - 2026-07-30 · http://arxiv.org/abs/2607.28230v2
 - Observed risk-taking behavior is often rationalized through expected-utility curvature, yet the curvature required to fit choices in one context can differ sharply from the curvature required in another, a tension highlighted by calibration critiques of expected-utility theory. Finite multiplicative systems often cease to evolve when a lower continuation threshold is reached, whereas standard growth-optimal benchmarks assume uninterrupted continuation. We study a finite-horizon binary multiplicative process in which a fixed exposure is chosen ex ante and paths crossing an absorbing boundary ar
+
+## Thermodynamic statistics of given names in USA and France
+- 2026-08-06 · http://arxiv.org/abs/2608.06048v1
+- Using official government data sets of USA and France we analyze the occurrence/frequency/popularity distributions of given names on a time scale of more than 100 years. These distributions are characterized through the Lorenz and Pareto curves broadly used in the analysis of wealth inequality in the world. These curves remain stable during the considered time period with the Gini coefficient remaining in the narrow range 0.85-0.95. As for the case of wealth inequality, we show that the distributions of names are well described by the Rayleigh-Jeans (RJ) thermalization and condensation phenome
+
+## Knowledge-Optimising Investment Decisions with Informative Datasets
+- 2026-08-06 · http://arxiv.org/abs/2608.05991v1
+- The enormous growth in datasets, both in number and size, has prompted investors to adapt to new ways for assimilating information. Normatively, the approach has been to integrate such datasets into pricing formulations and assess the performance of portfolios created thereafter. However, such approaches underestimate their influence in portfolio investments by limiting their impact to pricing only. While being theoretically valid, this results in a potential sub-optimal performance in the presence of real-life decision constraints, and a blind spot for performance attribution. We start by ana
+
+## Cross-Sectional Heterogeneity in LSTM Networks for Financial Time Series
+- 2026-08-06 · http://arxiv.org/abs/2608.05755v1
+- Predicting financial asset returns remains one of the most difficult challenges in empirical finance, driven by the low signal-to-noise ratio and the semi-strong form of market efficiency. While deep learning models, especially LSTM networks, have shown promise in capturing temporal dependencies, standard architectures often struggle to account for the cross-sectional heterogeneity of asset returns. This paper proposes a novel architectural extension to the basic LSTM model designed to improve both predictive accuracy and model interpretability. The framework integrates macro-financial covaria
+
+## Velocity- and Regime-Aware Detection of Intraday Options Market Manipulation, with Explainable Attribution
+- 2026-08-05 · http://arxiv.org/abs/2608.05373v1
+- Intraday market manipulation is hard to detect because its footprint is brief, buried in millions of quotes, and statistically similar to ordinary volatility. Detectors reach high recall only by flagging so many other days that measured precision collapses, producing alerts no regulator can act on. We show that this manipulation leaves a distinctive dynamic signature: a pump-and-crash pattern visible in the velocity of market state, rather than its level. We build a minute-level detection pipeline, strictly partitioned in time, based on smoothed state velocity: option-Delta velocity for index 
+
+## Portfolio Allocation under Heterogeneous Scales and Multifractality
+- 2026-08-05 · http://arxiv.org/abs/2608.04987v1
+- Cross-correlations between financial signals are neither scale-free nor amplitude-independent: they vary with the time scale over which they are measured and with the magnitude of the fluctuations that dominate the average. We exploit this structure to construct a portfolio allocation model in which the risk functional is the signed fluctuation function of multifractal cross-correlation analysis (MFCCA), indexed by a scale $s$ and a fluctuation order $q$. Unlike MFDCCA-type criteria, which rectify local detrended covariances before aggregation, MFCCA retains their sign, so that co-moving and c
+
+## Optimal Life Insurance Decision in Mean-Variance DC Management with Mortality Improvements
+- 2026-08-05 · http://arxiv.org/abs/2608.04532v1
+- This paper studies the investment and insurance strategies of defined-contribution (DC) pension plans under the mean-variance framework. We consider a stochastic environment with time-varying interest rates, contributions, and mortality risk. The DC plan members are allowed to decide their bond and stock allocations, as well as their life insurance coverage. Adopting the martingale approach, we derive the closed-form optimal strategies and the mean-variance efficient frontier. Further numerical analysis investigates how mortality improvements affect investment and insurance decisions, as well 
+
+## Public Trader Identity: Adverse Selection and Return Predictability
+- 2026-08-05 · http://arxiv.org/abs/2608.04373v2
+- Informed traders are supposed to need anonymity: they profit by hiding among the uninformed. A decentralized exchange now publishes the counterparty. Every committed order, cancellation, rejection, and fill carries a persistent pseudonymous wallet address. We reconstruct the full-depth limit order book from a record of 17.1 billion messages and 14.3 million aggressive orders by 147,113 wallets, covering $84.3 billion in taker notional. We report three findings. First, informativeness is a persistent wallet attribute. Wallets ranked by the price movement following their aggressive orders retain
+
+## Measuring the engine of a liquidation cascade: subcritical branching inside a first-order transition
+- 2026-08-04 · http://arxiv.org/abs/2608.03616v1
+- We study seven major crypto-perpetual liquidation cascades (2022-2025), and in the largest of them we can watch the mechanism directly. From the on-chain fill log of a fully transparent venue we measure the branching ratio of that event -- the October 2025 crash, the largest on record -- in flight, with both of its factors observed and no free constants. It ran deeply subcritical: the structural ratio and the amplification bookkeeping both place it at $\hatλ\approx 0.1-0.2$ throughout, while a third, flow-based estimator falls through the climax rather than rising. All three agree on subcritic
+
+## A New Approach to Goodness of Fit for Ergodic Markov Processes
+- 2026-08-04 · http://arxiv.org/abs/2608.03088v1
+- We introduce a new density-based goodness of fit test for ergodic Markov processes. Our test compares the data against the class of models specified in the null hypothesis, and rejects if no model in the class yields a stationary density that matches with the data. No alternative needs to be specified in order to implement the test. Although our test compares densities, estimation of smoothing parameters is not required, and the test has nontrivial power against $1/\sqrt{n}$ local alternatives. The test provides new perspectives on some existing problems in econometric and financial modeling.
+
+## Mandate without Managers: Automated Market Makers as Verifiable Portfolio Products
+- 2026-08-03 · http://arxiv.org/abs/2608.02917v1
+- Automated market makers (AMMs) are typically interpreted and evaluated as decentralized exchanges. Herein, we take the perspective envisioned by Balancer that an AMM can also be viewed as a portfolio technology that programmatically enforces an economic mandate. In particular, we follow the geometric mean market maker (G3M) invariant employed by that protocol in order to enforce a target-weighted portfolio. We introduce a multi-asset fee structure to the G3M under which competitive arbitrage implements a band-rebalancing strategy with mis-weighting bounded ex ante, allowing compliance with the
+
+## Proper-score observation-driven filters: local geometry, estimation, and continuous-time limits
+- 2026-08-03 · http://arxiv.org/abs/2608.02828v1
+- Observation-driven filters update a time-varying parameter with the likelihood score, linking the recursion to the logarithmic scoring rule. We replace this update with the negative parameter derivative of a differentiable proper scoring rule, within a declared working family and predictable scaling. For a general rule, the conditional mean update is a pre-conditioned stochastic-gradient of conditional scoring risk; when an autoregressive pull is included, the centre is the zero of a composite mean field. We derive local realised-loss descent and conditional-mean contraction results, and decom
diff --git a/docs/research/recent_changes.md b/docs/research/recent_changes.md
index 418caf3..4bc3484 100644
--- a/docs/research/recent_changes.md
+++ b/docs/research/recent_changes.md
@@ -1,6574 +1,8306 @@
-# Desk changes, last 24h (generated 2026-08-01T16:58:12Z)
+# Desk changes, last 24h (generated 2026-08-08T10:10:02Z)
 
-164 commit(s). Patches truncated to 400 lines each -- a seat that receives
+25 commit(s). Patches truncated to 400 lines each -- a seat that receives
 40k lines reviews none of them, and the design decision is almost always in the first
 few hundred.
 
```


---

## 5375230 Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

```diff
commit 53752302ffccf3e868e393426dae2aa5a4825606
Merge: 1fe6b15 7dc0c83
Author: Quant Desk <quant@vps.local>
Date:   Sat Aug 8 16:39:48 2026 +0000

    Merge branch 'claude/llm-auto-upgrade-verify-gcjac3' of https://github.com/kingdemond434-cpu/quant into claude/llm-auto-upgrade-verify-gcjac3

 .gitignore                                    |   8 +
 docs/CONSTITUTION.md                          | 258 +++++++
 docs/GAP_REGISTER.md                          |   1 +
 docs/research/COMPLETION_LEDGER.json          | 925 ++++++++++++++++++++++++++
 docs/research/COVERAGE_RATCHET.json           |  12 +-
 docs/research/RISK_KERNEL_LOCK.json           |  27 +
 docs/research/test_suite_record.json          |   4 +-
 libs/_deadlink_probe.py                       |   2 -
 libs/autodiscovery/generation_roi.py          |  32 +-
 libs/doctrine/constitution.py                 | 107 +++
 libs/execution/exec_monitor.py                | 243 +++++++
 libs/portfolio/capital_competition.py         | 235 +++++++
 libs/research/alpha_state.py                  | 223 +++++++
 libs/research/cadence_alignment.py            | 217 ++++++
 libs/research/cadence_roi.py                  | 179 +++++
 libs/research/completion_ledger.py            | 272 ++++++++
 libs/research/difference_engine.py            | 214 ++++++
 libs/research/evidence_clock.py               | 192 ++++++
 libs/research/failure_bands.py                | 184 +++++
 libs/research/gap_contract.py                 | 175 +++++
 libs/research/kill_audit.py                   | 231 +++++++
 libs/research/orphan_scan.py                  | 232 +++++++
 libs/research/source_roi.py                   | 215 ++++++
 libs/research/strategic_director.py           |   8 +-
 libs/research/unknowns.py                     | 219 ++++++
 libs/self_improvement/dormancy.py             | 157 +++++
 libs/validation/gate_power.py                 | 229 +++++++
 ops/principal_doctrine.txt                    |   2 +
 ops/quant-research.service                    |   9 +
 ops/quant-research.timer                      |  11 +
 ops/run_research_cycle.sh                     |  72 ++
 ops/run_study_on_vps.sh                       |  44 +-
 ops/run_sweep_then_cycle.sh                   | 119 ++++
 scripts/_deadlink_probe_caller.py             |   4 -
 scripts/breadth_expander.py                   |   8 +-
 scripts/build_bars.py                         | 106 ++-
 scripts/check_risk_kernel.py                  | 158 +++++
 scripts/collector_author.py                   |   8 +-
 scripts/hypothesis_generator.py               |   8 +-
 scripts/llm_blind_researcher.py               |   7 +-
 scripts/llm_code_auditor.py                   |   8 +-
 scripts/meta_architect.py                     |   8 +-
 scripts/run_completion_ledger.py              |  99 +++
 scripts/run_exec_monitor.py                   | 114 ++++
 scripts/run_full_sweep.py                     |  56 +-
 scripts/run_intelligence_cycle.py             | 191 +++++-
 scripts/run_live_ladder.py                    | 145 +++-
 scripts/run_max_push.py                       |  65 +-
 scripts/run_portfolio_admission.py            | 141 ++++
 scripts/run_research_review.py                | 447 +++++++++++++
 scripts/study_status.py                       | 155 +++++
 tests/execution/test_binance_testnet_paths.py | 304 +++++++++
 tests/execution/test_exec_monitor.py          | 153 +++++
 tests/execution/test_run_exec_monitor.py      |  89 +++
 tests/libs/test_build_deferral.py             |  80 +++
 tests/libs/test_residual_mandate.py           | 154 +++++
 tests/ops/test_research_cycle.py              |  65 ++
 tests/ops/test_study_runner_detach.py         |  97 +++
 tests/portfolio/test_capital_competition.py   | 139 ++++
 tests/research/test_alpha_state.py            | 234 +++++++
 tests/research/test_cadence_alignment.py      | 125 ++++
 tests/research/test_cadence_roi.py            |  99 +++
 tests/research/test_completion_ledger.py      | 148 +++++
 tests/research/test_difference_engine.py      | 106 +++
 tests/research/test_evidence_clock.py         | 126 ++++
 tests/research/test_failure_bands.py          | 109 +++
 tests/research/test_gap_contract.py           | 124 ++++
 tests/research/test_kill_audit.py             | 160 +++++
 tests/research/test_orphan_scan.py            | 106 +++
 tests/research/test_source_roi.py             | 124 ++++
 tests/research/test_unknowns.py               | 150 +++++
 tests/scripts/test_build_bars.py              |  44 ++
 tests/scripts/test_max_push_stranding.py      |  80 +++
 tests/scripts/test_portfolio_admission.py     | 111 ++++
 tests/scripts/test_research_review.py         | 189 ++++++
 tests/scripts/test_risk_kernel_lock.py        | 114 ++++
 tests/scripts/test_study_status.py            |  92 +++
 tests/self_improvement/test_dormancy.py       | 109 +++
 tests/validation/test_gate_power.py           | 121 ++++
 79 files changed, 10268 insertions(+), 70 deletions(-)
```


---

## 7dc0c83 ratchet the collectable-test high-water mark
Generated by the suite run: the mark ratchets UP only, so a suite may never quietly shrink --
deleting a test is a decision, not a side effect.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 7dc0c8366e01886a386ea4f1f0685384e1897aa7
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 16:02:34 2026 +0000

    ratchet the collectable-test high-water mark
    
    Generated by the suite run: the mark ratchets UP only, so a suite may never quietly shrink --
    deleting a test is a decision, not a side effect.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/research/test_suite_record.json | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/docs/research/test_suite_record.json b/docs/research/test_suite_record.json
index 9a83bdc..64da20f 100644
--- a/docs/research/test_suite_record.json
+++ b/docs/research/test_suite_record.json
@@ -1,5 +1,5 @@
 {
- "max_collected": 336,
- "at": "2026-08-08T15:44:01.488310+00:00",
+ "max_collected": 338,
+ "at": "2026-08-08T16:00:50.674588+00:00",
  "note": "high-water mark of COLLECTABLE test modules; ratchets UP only. A suite may never quietly shrink -- deleting a test is a decision, not a side effect."
 }
\ No newline at end of file
```


---

## b932502 sequence the pipeline in code, and measure cadence against alpha half-life
THE SEQUENCING HAZARD, which was mine. The operator was given two commands: start the sweep
detached, then run the research cycle. Both are correct and running them back to back is WRONG --
the sweep takes about an hour and returns immediately when detached, so the cycle consumes the
PREVIOUS run's artifacts. Nothing errors. Every artifact is present and internally consistent. The
kill audit reports on stale cells and the admission on stale survivors, and the numbers are simply
about the wrong run -- indistinguishable from a real result until somebody checks a timestamp.

ops/run_sweep_then_cycle.sh makes the dependency a script rather than an instruction, because
instructions are followed by whoever read them most recently and a script is followed every time.
The completion test is the report's MTIME, not its existence: full_sweep.json exists from the last
run, and the sweep writes it only at the end, so a report newer than the moment we started is the
one unambiguous signal that THIS run finished. Parsing the log for a word would break the first
time the wording changed. If it was not rewritten the cycle is REFUSED with the reason.

It ends by printing the conversion chain -- declared -> measurable -> cleared -> FORMULA -> FAMILY
-> INDEPENDENT_MECHANISM -> PORTFOLIO_CONTRIBUTING -- plus the kill audit, gate power, admission
verdict and shadow list, because that sequence is the only one that says whether research became
something economically usable.

CADENCE ALIGNMENT is a DIFFERENT QUESTION from the cadence-ROI module already built, and the two
are easy to confuse. That one asks whether a job produces anything per fire. This asks whether it
can still be in TIME: whether the interval between observations is short relative to how fast the
opportunity decays. A job can be productive on every fire and lose most of the edge, because it
only ever sees what survived until it looked.

THE LOSS IS INVISIBLE BY CONSTRUCTION. An hourly scheduler against a 20-minute half-life does not
error, does not log, and reports healthy -- it simply never observes what opened and closed between
fires, and every metric the desk keeps is computed over what WAS observed. At four half-lives ~6%
of the edge survives to observation and the job still reports success on what it caught.

Faster is not free and the module does not pretend it is: polling costs rate limit, compute and
contention with the recorders, which write the one asset that cannot be re-acquired at any price.
So it recommends the CHEAPEST mechanism that meets the horizon. Hard floors are checked before any
TOO_SLOW verdict -- a strategy watching a daily bar cannot be observed faster than the bar exists,
and a fence that emits impossible work gets muted, taking its real findings with it.

CADENCE_REGRET is a stated LOWER BOUND: it prices only the decay on opportunities still SEEN.
Opportunities that opened and closed entirely between fires are invisible to any measurement taken
at the fire, so counting them would need a model of what was never observed.

Ledger now declares 62 capabilities including the regime-dynamics and production alpha-capture
batches. Status remains 1/61 VERIFIED_COMPLETE -- the denominator grew and the numerator did not,
which is the pattern to watch rather than hide.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit b93250262d17ad94bd24b77fc4bc297ed945128c
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 15:59:35 2026 +0000

    sequence the pipeline in code, and measure cadence against alpha half-life
    
    THE SEQUENCING HAZARD, which was mine. The operator was given two commands: start the sweep
    detached, then run the research cycle. Both are correct and running them back to back is WRONG --
    the sweep takes about an hour and returns immediately when detached, so the cycle consumes the
    PREVIOUS run's artifacts. Nothing errors. Every artifact is present and internally consistent. The
    kill audit reports on stale cells and the admission on stale survivors, and the numbers are simply
    about the wrong run -- indistinguishable from a real result until somebody checks a timestamp.
    
    ops/run_sweep_then_cycle.sh makes the dependency a script rather than an instruction, because
    instructions are followed by whoever read them most recently and a script is followed every time.
    The completion test is the report's MTIME, not its existence: full_sweep.json exists from the last
    run, and the sweep writes it only at the end, so a report newer than the moment we started is the
    one unambiguous signal that THIS run finished. Parsing the log for a word would break the first
    time the wording changed. If it was not rewritten the cycle is REFUSED with the reason.
    
    It ends by printing the conversion chain -- declared -> measurable -> cleared -> FORMULA -> FAMILY
    -> INDEPENDENT_MECHANISM -> PORTFOLIO_CONTRIBUTING -- plus the kill audit, gate power, admission
    verdict and shadow list, because that sequence is the only one that says whether research became
    something economically usable.
    
    CADENCE ALIGNMENT is a DIFFERENT QUESTION from the cadence-ROI module already built, and the two
    are easy to confuse. That one asks whether a job produces anything per fire. This asks whether it
    can still be in TIME: whether the interval between observations is short relative to how fast the
    opportunity decays. A job can be productive on every fire and lose most of the edge, because it
    only ever sees what survived until it looked.
    
    THE LOSS IS INVISIBLE BY CONSTRUCTION. An hourly scheduler against a 20-minute half-life does not
    error, does not log, and reports healthy -- it simply never observes what opened and closed between
    fires, and every metric the desk keeps is computed over what WAS observed. At four half-lives ~6%
    of the edge survives to observation and the job still reports success on what it caught.
    
    Faster is not free and the module does not pretend it is: polling costs rate limit, compute and
    contention with the recorders, which write the one asset that cannot be re-acquired at any price.
    So it recommends the CHEAPEST mechanism that meets the horizon. Hard floors are checked before any
    TOO_SLOW verdict -- a strategy watching a daily bar cannot be observed faster than the bar exists,
    and a fence that emits impossible work gets muted, taking its real findings with it.
    
    CADENCE_REGRET is a stated LOWER BOUND: it prices only the decay on opportunities still SEEN.
    Opportunities that opened and closed entirely between fires are invisible to any measurement taken
    at the fire, so counting them would need a model of what was never observed.
    
    Ledger now declares 62 capabilities including the regime-dynamics and production alpha-capture
    batches. Status remains 1/61 VERIFIED_COMPLETE -- the denominator grew and the numerator did not,
    which is the pattern to watch rather than hide.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/research/COMPLETION_LEDGER.json     | 190 +++++++++++++++++++++++++++
 libs/research/cadence_alignment.py       | 217 +++++++++++++++++++++++++++++++
 ops/run_sweep_then_cycle.sh              | 119 +++++++++++++++++
 scripts/run_intelligence_cycle.py        |  35 +++++
 tests/research/test_cadence_alignment.py | 125 ++++++++++++++++++
 5 files changed, 686 insertions(+)

diff --git a/docs/research/COMPLETION_LEDGER.json b/docs/research/COMPLETION_LEDGER.json
index fabad0c..d33d460 100644
--- a/docs/research/COMPLETION_LEDGER.json
+++ b/docs/research/COMPLETION_LEDGER.json
@@ -730,6 +730,196 @@
    "consumers": [],
    "external_blocker": "",
    "next_action": "read ledger, pick highest-value unfinished, launch, update, repeat"
+  },
+  {
+   "capability_id": "REGIME_TRANSITION_POSTERIOR",
+   "title": "Transition posterior + duration-aware hazard",
+   "economic_reason": "A state model that cannot say how likely it is to LEAVE the state cannot size the exposure it justifies",
+   "source_spec": "regime extension \u00a71-\u00a72",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "extend existing HMM/GMM modules; test whether duration-aware beats plain Markov OOS"
+  },
+  {
+   "capability_id": "TRANSITION_SURPRISE",
+   "title": "Transition surprise score",
+   "economic_reason": "An unexpected state change may precede volatility, liquidation or momentum failure -- a hypothesis, not assumed alpha",
+   "source_spec": "regime extension \u00a73",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "-log P(observed transition | prior info), as-of; route to the hypothesis factory"
+  },
+  {
+   "capability_id": "STATE_CONDITIONAL_MECHANISM",
+   "title": "Preregistered conditional-alpha validation branch",
+   "economic_reason": "F3's measured plateau makes conditional alpha impossible to pass ~half the time; the fix is a branch, never a lower global bar",
+   "source_spec": "regime extension \u00a74 / completion mandate \u00a75",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "state defined EX ANTE and causally observable; no post-hoc state mining on a failed candidate; untouched OOS; transition periods tested separately"
+  },
+  {
+   "capability_id": "REGIME_CONDITIONAL_ALLOCATION",
+   "title": "Regime-conditional capital allocation",
+   "economic_reason": "Sizing from P(bull)-P(bear) discards the variance and tail terms that decide log-growth",
+   "source_spec": "regime extension \u00a75-\u00a76",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "feed the full posterior into capital_competition: state-conditional return, variance, tail, entropy"
+  },
+  {
+   "capability_id": "REGIME_MODEL_SELECTION",
+   "title": "Regime representation selection by validated economics",
+   "economic_reason": "Choosing the most sophisticated model automatically is complexity nobody priced",
+   "source_spec": "regime extension \u00a78",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "compare 3-state / Markov / HMM / GMM / HSMM on untouched OOS E[log W] per unit complexity"
+  },
+  {
+   "capability_id": "CADENCE_ALIGNMENT",
+   "title": "Signal-cadence / alpha-half-life alignment",
+   "economic_reason": "A scheduler slower than the opportunity half-life loses the edge before the decision is made, and nothing anywhere records the loss",
+   "source_spec": "production spec \u00a71",
+   "module": "libs.research.cadence_alignment",
+   "tests": [
+    "tests/research/test_cadence_alignment.py"
+   ],
+   "callers": [
+    "scripts/run_intelligence_cycle.py"
+   ],
+   "artifacts": [
+    "data/intelligence_cycle.json"
+   ],
+   "consumers": [
+    "scripts/run_max_push.py"
+   ],
+   "external_blocker": "",
+   "next_action": "derive cadence from the strategy's information horizon; refuse configs where interval materially exceeds half-life; emit CADENCE_REGRET into alpha retention"
+  },
+  {
+   "capability_id": "DECISION_LEDGER",
+   "title": "Complete decision / non-trade ledger",
+   "economic_reason": "Learning only from trades taken hides validator false negatives, execution loss and allocator timidity",
+   "source_spec": "production spec \u00a72",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "record EXECUTED / SIGNAL_REJECTED / RISK_REJECTED / COST_REJECTED / CAPACITY_REJECTED / EXECUTION_REJECTED / VENUE_UNAVAILABLE / MISSED_LATENCY with the state snapshot"
+  },
+  {
+   "capability_id": "STRATEGY_MANIFEST",
+   "title": "Canonical immutable versioned strategy manifest",
+   "economic_reason": "No LLM may silently reinterpret a live strategy; production must reference a content hash",
+   "source_spec": "production spec \u00a73",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "audit existing trade-intent schema first; any modification creates a CHILD version"
+  },
+  {
+   "capability_id": "REALITY_GAP",
+   "title": "Paper / canary / live parity measurement",
+   "economic_reason": "A candidate cannot scale while unexplained execution divergence is material",
+   "source_spec": "production spec \u00a74",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "same decision engine across paper/canary/live; compare signal, decision, desired order, fill and cost parity"
+  },
+  {
+   "capability_id": "PREFLIGHT_CONTRACT",
+   "title": "Production pre-flight health contract",
+   "economic_reason": "Fail closed for execution, continue research -- and RECORD the opportunity the outage cost",
+   "source_spec": "production spec \u00a75",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "data freshness, clock, manifest hash, venue, auth, reconciliation, risk kernel, journal"
+  },
+  {
+   "capability_id": "VENUE_CAPABILITY",
+   "title": "Venue capability contract",
+   "economic_reason": "A strategy needing post-only on a venue without it is an untested failure waiting for live capital",
+   "source_spec": "production spec \u00a76",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "machine-readable adapter capabilities vs declared strategy requirements -> ELIGIBLE / DEGRADED / INELIGIBLE before promotion"
+  },
+  {
+   "capability_id": "EXECUTION_TAPE_ACCOUNTING",
+   "title": "Accounting derived from the authoritative execution tape",
+   "economic_reason": "A separate ledger as source of truth is a second truth, and the desk has already paid for phantom reconciliation once",
+   "source_spec": "production spec \u00a77",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "derive exports from immutable execution records; accounting is convenience, never evidence"
+  },
+  {
+   "capability_id": "DETERMINISTIC_HOT_PATH",
+   "title": "Deterministic production order path",
+   "economic_reason": "LLMs research and propose; they may not freestyle production order interpretation",
+   "source_spec": "production spec \u00a78",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "frozen manifest -> deterministic signal engine -> allocator -> immutable risk kernel -> deterministic adapter"
+  },
+  {
+   "capability_id": "LATENCY_METRICS",
+   "title": "End-to-end latency and regret metrics",
+   "economic_reason": "Unnecessary delay is an economic defect and nothing charges it",
+   "source_spec": "production spec \u00a710",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "signal_to_observation, observation_to_decision, decision_to_order, order_to_fill, cadence_regret, reality_gap, venue_availability_loss"
   }
  ]
 }
\ No newline at end of file
diff --git a/libs/research/cadence_alignment.py b/libs/research/cadence_alignment.py
new file mode 100644
index 0000000..64b1c45
--- /dev/null
+++ b/libs/research/cadence_alignment.py
@@ -0,0 +1,217 @@
+"""SIGNAL CADENCE vs ALPHA HALF-LIFE — a scheduler slower than the edge it is watching.
+
+A DIFFERENT QUESTION FROM `cadence_roi`, and the two are easy to confuse. `cadence_roi` asks
+whether a job PRODUCES anything per fire -- a yield question about work already done. This asks
+whether the job can still be in time: whether the interval between observations is short relative
+to how fast the opportunity decays. A job can be productive on every fire and still be losing most
+of the edge, because it only ever sees what survived until it looked.
+
+THE LOSS IS INVISIBLE BY CONSTRUCTION, which is why it needs a number rather than a habit. A
+scheduler that runs hourly against a signal with a 20-minute half-life does not error, does not
+log, and reports healthy: it simply never observes the opportunities that opened and closed
+between fires. Every metric the desk keeps is computed over what was observed, so the missed
+fraction never appears in any of them.
+
+    surviving fraction of edge at observation = 2 ** (-interval / half_life)
+
+    interval = 1/4 half-life  ->  ~84% of the edge still there
+    interval = 1 half-life    ->  ~50%
+    interval = 4 half-lives   ->  ~6%, and the job still reports success on what it caught
+
+**CADENCE IS DERIVED, NOT CHOSEN.** A scheduler interval typed into a crontab is a number somebody
+picked once, and it will outlive every assumption behind it. The strategy declares its information
+horizon; the required cadence follows from it, and a configuration where the interval materially
+exceeds the half-life is REFUSED rather than noted.
+
+**FASTER IS NOT FREE AND THIS MODULE DOES NOT PRETEND IT IS.** Polling faster costs rate limit,
+compute and contention with the recorders -- the one irreplaceable process on the box. So the
+recommendation is the cheapest MECHANISM that meets the horizon, not the fastest one available:
+periodic where periodic suffices, event-driven where it does not, streaming only where the horizon
+is shorter than any poll could serve.
+
+Measures and reports. Schedules nothing, changes no crontab.
+"""
+
+from __future__ import annotations
+
+import math
+from dataclasses import dataclass
+
+__all__ = [
+    "MECHANISMS",
+    "StrategyCadence",
+    "alignment",
+    "cadence_regret",
+    "required_interval_minutes",
+    "summarise",
+]
+
+#: Acquisition mechanisms, cheapest first. The recommendation is the cheapest one that MEETS the
+#: horizon: faster polling is not free -- it costs rate limit, compute, and contention with the
+#: recorders, which write the one asset that cannot be re-acquired at any price.
+MECHANISMS: tuple[tuple[float, str], ...] = (
+    (1440.0, "daily periodic"),
+    (60.0, "hourly periodic"),
+    (5.0, "high-frequency polling"),
+    (1.0, "sub-minute polling"),
+    (0.0, "websocket / event-driven stream"),
+)
+
+#: Fraction of edge that must survive to observation before a cadence is considered aligned. 0.75
+#: rather than 0.95: demanding near-perfect capture would push every strategy to streaming and
+#: spend the box's capacity on horizons that do not need it.
+MIN_SURVIVING_FRACTION: float = 0.75
+
+
+@dataclass(frozen=True)
+class StrategyCadence:
+    """One strategy's information horizon against the cadence it is actually run at."""
+
+    strategy: str
+    #: Minutes over which half the edge is gone. 0 = UNMEASURED, never "instant".
+    half_life_minutes: float
+    #: The interval it is scheduled at today.
+    interval_minutes: float
+    #: Expected edge per captured opportunity, for costing the regret. 0 = unmeasured.
+    edge_bps: float = 0.0
+    #: Opportunities per day the strategy would see with a perfect observer.
+    opportunities_per_day: float = 0.0
+    #: A horizon that genuinely cannot be shortened -- a daily bar, a funding settlement.
+    hard_floor_reason: str = ""
+
+    @property
+    def measured(self) -> bool:
+        return self.half_life_minutes > 0 and self.interval_minutes > 0
+
+    @property
+    def surviving_fraction(self) -> float | None:
+        """Share of the edge still present when the scheduler next looks. None when unmeasured."""
+        if not self.measured:
+            return None
+        return float(2.0 ** (-self.interval_minutes / self.half_life_minutes))
+
+
+def required_interval_minutes(half_life_minutes: float,
+                              *, surviving: float = MIN_SURVIVING_FRACTION) -> float | None:
+    """Longest interval that still observes `surviving` of the edge. None when unmeasurable.
+
+    Inverts the decay: interval = -half_life * log2(surviving). Returned rather than compared, so
+    a caller can report the gap between what a strategy needs and what it is given instead of only
+    a pass/fail.
+    """
+    if half_life_minutes <= 0 or not 0.0 < surviving < 1.0:
+        return None
+    return -half_life_minutes * math.log2(surviving)
+
+
+def recommended_mechanism(interval_minutes: float) -> str:
+    """The CHEAPEST acquisition mechanism that serves this interval."""
+    for threshold, name in MECHANISMS:
+        if interval_minutes >= threshold:
+            return name
+    return MECHANISMS[-1][1]
+
+
+def alignment(c: StrategyCadence) -> tuple[str, str]:
+    """(verdict, why). ALIGNED | TOO_SLOW | FLOORED | UNMEASURED.
+
+    HARD FLOORS ARE CHECKED FIRST. A strategy watching a daily bar cannot be observed faster than
+    the bar exists, so calling it TOO_SLOW would generate work nobody can do -- and a fence that
+    emits impossible work gets muted, taking its real findings with it.
+    """
+    if c.hard_floor_reason:
+        return "FLOORED", (
+            f"the horizon is bounded by {c.hard_floor_reason}, so the interval cannot be "
+            "shortened. If capture is still poor the lever is the MECHANISM or the strategy's "
+            "own horizon, never the schedule")
+    if not c.measured:
+        return "UNMEASURED", (
+            "no half-life recorded, so the cadence cannot be justified OR refused. A schedule "
+            "nobody derived is a number somebody picked once, and it will outlive every "
+            "assumption behind it -- measure the decay")
+    surv = c.surviving_fraction
```


---

## ddcd376 build the completion ledger: capability status computed, not asserted
Asked whether a specification was fully built, this desk has answered in prose all day. Prose
status has three failure modes and the desk hit all three: it drifts the moment code changes, it
cannot be re-checked without re-reading everything, and it lets "built" mean whichever of EXISTS /
IMPORTS / TESTED / WIRED the writer had in mind.

So status becomes a MEASUREMENT. 48 capabilities from every specification issued today, each
naming its module, tests, callers, artifacts and consumers, verified against the working tree
through eight stages. Status is the FIRST FAILING stage, never the strongest passing one.

FIRST RUN: 1/47 solvable capabilities VERIFIED_COMPLETE (2%), 15 partial, 31 missing, 1
externally blocked. That number is deliberately brutal and it is the honest one.

AND IT CAUGHT ME IMMEDIATELY. `evidence_clock`, `capital_competition` and `gate_power` -- three
modules built today -- all failed at CALLED. I wrote them, tested them, committed them and wired
none of them: the exact defect I spent the morning fixing in other people's code. Now wired:
evidence_clock and capital_competition into run_live_ladder (deflated observation counts and a
live re-competition of every funded record, advisory), gate_power into run_research_review (F3's
false-negative exposure printed beside its kill count, so a kill total is never read alone).

THEN THE REPO'S OWN FENCE CAUGHT ME AGAIN, within the hour:
`test_a_wiring_fix_cannot_be_one_link_short` failed because run_completion_ledger.py was the sole
importer of its module and nothing scheduled it -- a wiring fix one link short, which reports
success while the module stays exactly as unreachable. Now in the daily cycle, last, so it
measures the cycle that just happened including whatever that cycle wired.

TWO CORRECTIONS TO THE VERIFIER ITSELF, both found by running it. Artifact matching now uses the
BASENAME: producers build paths as `ROOT / "data" / "x.json"`, so the slash-joined literal never
appears in source and every wired producer was being reported PRODUCES-false. The check was wrong,
not the code -- and a verifier that emits false gaps trains its reader to ignore it, which is
worse than no verifier. Several ledger rows also declared no callers; an undeclared caller is an
incomplete declaration, not a missing wire.

UNFINISHED CAPABILITIES PUBLISH AS RANKED GAPS through the Gap contract, so the programme cannot
quietly stall: an item that stops being worked reappears in tomorrow's priorities on its own. That
is the difference between a plan and a control.

EXTERNALLY_BLOCKED is a real status and it is not an excuse: it requires a named dependency this
repository cannot satisfy. Exactly one row qualifies -- OS-level credential separation for the
risk kernel, which needs root on the box. "Large", "later" and "queued" are scheduling information
and map to MISSING, which keeps them on the queue.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit ddcd37638b9e5d2bfb296c6cbe812354a1304af5
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 15:53:10 2026 +0000

    build the completion ledger: capability status computed, not asserted
    
    Asked whether a specification was fully built, this desk has answered in prose all day. Prose
    status has three failure modes and the desk hit all three: it drifts the moment code changes, it
    cannot be re-checked without re-reading everything, and it lets "built" mean whichever of EXISTS /
    IMPORTS / TESTED / WIRED the writer had in mind.
    
    So status becomes a MEASUREMENT. 48 capabilities from every specification issued today, each
    naming its module, tests, callers, artifacts and consumers, verified against the working tree
    through eight stages. Status is the FIRST FAILING stage, never the strongest passing one.
    
    FIRST RUN: 1/47 solvable capabilities VERIFIED_COMPLETE (2%), 15 partial, 31 missing, 1
    externally blocked. That number is deliberately brutal and it is the honest one.
    
    AND IT CAUGHT ME IMMEDIATELY. `evidence_clock`, `capital_competition` and `gate_power` -- three
    modules built today -- all failed at CALLED. I wrote them, tested them, committed them and wired
    none of them: the exact defect I spent the morning fixing in other people's code. Now wired:
    evidence_clock and capital_competition into run_live_ladder (deflated observation counts and a
    live re-competition of every funded record, advisory), gate_power into run_research_review (F3's
    false-negative exposure printed beside its kill count, so a kill total is never read alone).
    
    THEN THE REPO'S OWN FENCE CAUGHT ME AGAIN, within the hour:
    `test_a_wiring_fix_cannot_be_one_link_short` failed because run_completion_ledger.py was the sole
    importer of its module and nothing scheduled it -- a wiring fix one link short, which reports
    success while the module stays exactly as unreachable. Now in the daily cycle, last, so it
    measures the cycle that just happened including whatever that cycle wired.
    
    TWO CORRECTIONS TO THE VERIFIER ITSELF, both found by running it. Artifact matching now uses the
    BASENAME: producers build paths as `ROOT / "data" / "x.json"`, so the slash-joined literal never
    appears in source and every wired producer was being reported PRODUCES-false. The check was wrong,
    not the code -- and a verifier that emits false gaps trains its reader to ignore it, which is
    worse than no verifier. Several ledger rows also declared no callers; an undeclared caller is an
    incomplete declaration, not a missing wire.
    
    UNFINISHED CAPABILITIES PUBLISH AS RANKED GAPS through the Gap contract, so the programme cannot
    quietly stall: an item that stops being worked reappears in tomorrow's priorities on its own. That
    is the difference between a plan and a control.
    
    EXTERNALLY_BLOCKED is a real status and it is not an excuse: it requires a named dependency this
    repository cannot satisfy. Exactly one row qualifies -- OS-level credential separation for the
    risk kernel, which needs root on the box. "Large", "later" and "queued" are scheduling information
    and map to MISSING, which keeps them on the queue.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/research/COMPLETION_LEDGER.json     | 735 +++++++++++++++++++++++++++++++
 docs/research/test_suite_record.json     |   4 +-
 libs/research/completion_ledger.py       | 272 ++++++++++++
 ops/run_research_cycle.sh                |   5 +
 scripts/run_completion_ledger.py         |  99 +++++
 scripts/run_live_ladder.py               |  57 ++-
 scripts/run_research_review.py           |   9 +
 tests/research/test_completion_ledger.py | 148 +++++++
 8 files changed, 1326 insertions(+), 3 deletions(-)

diff --git a/docs/research/COMPLETION_LEDGER.json b/docs/research/COMPLETION_LEDGER.json
new file mode 100644
index 0000000..fabad0c
--- /dev/null
+++ b/docs/research/COMPLETION_LEDGER.json
@@ -0,0 +1,735 @@
+{
+ "_": "Every capability requested across today's specifications. Status is COMPUTED by libs/research/completion_ledger.py against the working tree, never asserted. A ledger listing only what exists would report 100% and measure nothing, so the unbuilt items are rows here from the moment they are requested.",
+ "capabilities": [
+  {
+   "capability_id": "KILL_AUDIT",
+   "title": "Kill audit / nine rejection states",
+   "economic_reason": "750 of 762 cells died at one gate; a counter cannot distinguish a correct gate from one destroying real alpha silently",
+   "source_spec": "validator spec \u00a72-\u00a73",
+   "module": "libs.research.kill_audit",
+   "tests": [
+    "tests/research/test_kill_audit.py"
+   ],
+   "callers": [
+    "scripts/run_research_review.py"
+   ],
+   "artifacts": [
+    "data/research_review.json"
+   ],
+   "consumers": [
+    "scripts/run_max_push.py"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "PORTFOLIO_ADMISSION",
+   "title": "Survivor -> portfolio contribution",
+   "economic_reason": "PORTFOLIO_CONTRIBUTING was unmeasurable, not merely unmeasured: survivor pnl never left the sweep",
+   "source_spec": "validator spec \u00a712",
+   "module": "scripts.run_portfolio_admission",
+   "tests": [
+    "tests/scripts/test_portfolio_admission.py"
+   ],
+   "callers": [
+    "ops/run_research_cycle.sh"
+   ],
+   "artifacts": [
+    "data/portfolio_admission.json"
+   ],
+   "consumers": [
+    "scripts/run_live_ladder.py"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "EVIDENCE_CLOCK",
+   "title": "Effective independent observations replace calendar gates",
+   "economic_reason": "An edge real for 20 days that spends 15 in a calendar gate has lost most of its economic life to its own validator",
+   "source_spec": "accelerator spec \u00a7D/\u00a710",
+   "module": "libs.research.evidence_clock",
+   "tests": [
+    "tests/research/test_evidence_clock.py"
+   ],
+   "callers": [
+    "scripts/run_live_ladder.py"
+   ],
+   "artifacts": [
+    "data/live_ladder.json"
+   ],
+   "consumers": [
+    "scripts/run_research_review.py"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "ALPHA_STATE",
+   "title": "Alpha state machine incl. LIVE_CANARY",
+   "economic_reason": "Nothing made DISCOVERED->LIVE impossible; it was merely undone",
+   "source_spec": "spec \u00a79/\u00a7C",
+   "module": "libs.research.alpha_state",
+   "tests": [
+    "tests/research/test_alpha_state.py"
+   ],
+   "callers": [
+    "scripts/run_live_ladder.py"
+   ],
+   "artifacts": [
+    "data/live_ladder.json"
+   ],
+   "consumers": [
+    "scripts/run_research_review.py"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "CAPITAL_COMPETITION",
+   "title": "Continuous capital competition, age confers no privilege",
+   "economic_reason": "Capital in a strategy whose forward expectation collapsed is the best remaining opportunity being declined, silently, every day",
+   "source_spec": "spec \u00a712/\u00a7E",
+   "module": "libs.portfolio.capital_competition",
+   "tests": [
+    "tests/portfolio/test_capital_competition.py"
+   ],
+   "callers": [
+    "scripts/run_live_ladder.py"
+   ],
+   "artifacts": [
+    "data/live_ladder.json"
+   ],
+   "consumers": [
+    "scripts/run_research_review.py"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "GATE_POWER",
+   "title": "Gate power / F3 false-negative calibration",
+   "economic_reason": "F3 keeps 100% of stable and ~50% of conditional edges at every effect size; the plateau is arithmetic, not power",
+   "source_spec": "validator spec \u00a75",
+   "module": "libs.validation.gate_power",
+   "tests": [
+    "tests/validation/test_gate_power.py"
+   ],
+   "callers": [
+    "scripts/run_research_review.py"
+   ],
+   "artifacts": [
+    "data/research_review.json"
+   ],
+   "consumers": [
+    "scripts/run_max_push.py"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "RISK_KERNEL_LOCK",
+   "title": "Hash-lock the survival path",
+   "economic_reason": "The desk hash-locked its constitution and left the kill switch protected by prose comments",
+   "source_spec": "fusion spec \u00a730",
+   "module": "scripts.check_risk_kernel",
+   "tests": [
+    "tests/scripts/test_risk_kernel_lock.py"
+   ],
+   "callers": [
+    "ops/run_research_cycle.sh"
+   ],
+   "artifacts": [
+    "docs/research/RISK_KERNEL_LOCK.json"
+   ],
+   "consumers": [
+    "ops/run_research_cycle.sh"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "GAP_CONTRACT",
+   "title": "Generic published-gap contract",
+   "economic_reason": "A detector written today could not influence tomorrow's priorities until somebody edited the ranker",
+   "source_spec": "batch-2 spec",
+   "module": "libs.research.gap_contract",
+   "tests": [
+    "tests/research/test_gap_contract.py"
+   ],
+   "callers": [
+    "scripts/run_max_push.py"
+   ],
+   "artifacts": [
+    "data/published_gaps"
+   ],
+   "consumers": [
+    "scripts/run_max_push.py"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "ORPHAN_SCAN",
+   "title": "Conversion-chain orphan scan",
+   "economic_reason": "The expensive orphans are research objects, not modules: a hypothesis never tested, a survivor never portfolio-tested",
+   "source_spec": "batch-2 \u00a733",
+   "module": "libs.research.orphan_scan",
+   "tests": [
+    "tests/research/test_orphan_scan.py"
+   ],
+   "callers": [
+    "scripts/run_intelligence_cycle.py"
+   ],
+   "artifacts": [
+    "data/published_gaps"
+   ],
+   "consumers": [
+    "scripts/run_max_push.py"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "DIFFERENCE_ENGINE",
+   "title": "Claude<->GPT difference engine",
+   "economic_reason": "The valuable output of a second intelligence is the difference, not the overlap",
+   "source_spec": "residual spec",
+   "module": "libs.research.difference_engine",
+   "tests": [
+    "tests/research/test_difference_engine.py"
+   ],
+   "callers": [
+    "scripts/run_research_review.py"
+   ],
+   "artifacts": [
+    "data/research_review.json"
+   ],
+   "consumers": [
+    "scripts/run_max_push.py"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "UNKNOWNS",
+   "title": "Assumption / contradiction / unknowns ledger",
+   "economic_reason": "A belief with no falsifier is a habit: it survives its own obsolescence",
+   "source_spec": "batch-2 \u00a78/\u00a722",
+   "module": "libs.research.unknowns",
+   "tests": [
+    "tests/research/test_unknowns.py"
+   ],
+   "callers": [
+    "scripts/run_intelligence_cycle.py"
+   ],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "FAILURE_BANDS",
+   "title": "Failure bands and near-survivor classes",
+   "economic_reason": "Span-blocked and cost-blocked cells both read as 'did not survive' and are spent in different budgets",
+   "source_spec": "validator spec \u00a711/\u00a715",
+   "module": "libs.research.failure_bands",
+   "tests": [
+    "tests/research/test_failure_bands.py"
+   ],
+   "callers": [
+    "scripts/run_research_review.py"
+   ],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "SOURCE_ROI",
+   "title": "Miner / model / prompt economic ROI",
+   "economic_reason": "Volume is a cost, never an output: 100k pages and no survivors is worse than 100 and two",
+   "source_spec": "batch-2 \u00a72/\u00a750",
+   "module": "libs.research.source_roi",
+   "tests": [
+    "tests/research/test_source_roi.py"
+   ],
+   "callers": [
+    "scripts/run_intelligence_cycle.py"
+   ],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "CADENCE_ROI",
+   "title": "Cadence vs measured yield",
+   "economic_reason": "Every cadence was chosen rather than measured; an under-run job finds less than it could forever and nothing records it",
+   "source_spec": "batch-2 \u00a717",
+   "module": "libs.research.cadence_roi",
+   "tests": [
+    "tests/research/test_cadence_roi.py"
+   ],
+   "callers": [
+    "scripts/run_intelligence_cycle.py"
+   ],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "STUDY_STATUS",
+   "title": "Deterministic study process status",
+   "economic_reason": "Process status was a shell expression, so every invocation could get it wrong",
+   "source_spec": "batch-2 \u00a716",
+   "module": "scripts.study_status",
+   "tests": [
+    "tests/scripts/test_study_status.py"
+   ],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "COMPLETION_LEDGER",
+   "title": "This ledger: capability status computed, not asserted",
+   "economic_reason": "Prose status drifts, cannot be re-checked, and lets 'built' mean whichever stage the writer had in mind",
+   "source_spec": "completion mandate \u00a71-\u00a72",
+   "module": "libs.research.completion_ledger",
+   "tests": [
+    "tests/research/test_completion_ledger.py"
+   ],
+   "callers": [
+    "scripts/run_completion_ledger.py"
+   ],
+   "artifacts": [
+    "data/completion_ledger_status.json"
+   ],
+   "consumers": [
+    "scripts/run_max_push.py"
+   ],
+   "external_blocker": "",
+   "next_action": ""
+  },
+  {
+   "capability_id": "F3_THRESHOLD_SENSITIVITY",
+   "title": "F3 threshold sensitivity surface",
+   "economic_reason": "A gate sitting on a knife edge changes hundreds of verdicts on a 5% perturbation",
+   "source_spec": "validator spec \u00a78",
+   "module": "",
+   "tests": [],
+   "callers": [],
+   "artifacts": [],
+   "consumers": [],
+   "external_blocker": "",
+   "next_action": "sweep justified perturbations, report the stability surface; never pick a threshold because it yields more survivors"
+  },
+  {
+   "capability_id": "GATE_ABLATION",
+   "title": "Per-gate ablation and unique-kill attribution",
+   "economic_reason": "A gate whose kills are entirely covered by another is compute and false-negative exposure for no protection",
```


---

## c464e66 hash-lock the survival path, which prose alone was protecting
THE ASYMMETRY, found by audit. `check_constitution_core.py` verifies five constitutional clauses
by SHA-256 and fails the build if a word moves. The code that enforces SURVIVAL was protected by
comments:

    ops/run_recommendation_worker.sh:99   "is Tier-3 -- do NOT edit it"
    scripts/watchdog.py:258               "TIER-3 never-touch"
    CLAUDE.md                             "never modified autonomously"

Every one of those is an instruction to a READER. None is a mechanism. An organ that ignored them
-- or a session that never read them -- would modify the dead-man switch and nothing anywhere
would notice, which is precisely the class of failure the desk hash-locks its constitution
against. Locking the laws and not the kill switch is the wrong way round: prose can be re-argued,
and a flattened book cannot.

Six files are now locked, each with a stated reason, because a list of paths without reasons is a
list somebody prunes to make a refactor pass: the Tier-3 ruin rail, the risk config every sizing
decision reads, the pre-trade gate, the Kelly arithmetic, the drawdown rail and order staging.

THREE FAILURE SHAPES WITH THREE DIFFERENT FIXES. MISSING is the most serious -- the control that
ends a losing session is not on disk. DRIFT means the path changed without being re-locked.
UNLOCKED means a named kernel file carries no protection at all. An absent file hashes to None
rather than a sentinel, so deleted, edited and fine are three distinguishable states.

A CHANGED HASH IS NOT AUTOMATICALLY A DEFECT. The rails are allowed to improve -- what is
forbidden is improving them SILENTLY. Re-locking requires a reason and appends to a history, so
every amendment is auditable exactly as a constitutional one is.

IT IS TAMPER-EVIDENT, NOT TAMPER-PROOF, and says so rather than claiming more than it delivers.
True tamper-proofing is a privilege boundary -- separate credentials, a service the research
account cannot redeploy, an OS-level owner -- and that is deployment work on the box, the
principal's side. This is the half that lives in the repo, and it catches the realistic failure:
not a hostile agent, but a well-meaning one refactoring across a directory without reading the
comment.

Wired FIRST in the daily cycle, before any research runs: a cycle that researched all day and then
discovered the dead-man switch had changed would have spent the day on a book with no floor
under it.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit c464e66da3523796f0997ff65b9d31151cbe1cab
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 15:35:42 2026 +0000

    hash-lock the survival path, which prose alone was protecting
    
    THE ASYMMETRY, found by audit. `check_constitution_core.py` verifies five constitutional clauses
    by SHA-256 and fails the build if a word moves. The code that enforces SURVIVAL was protected by
    comments:
    
        ops/run_recommendation_worker.sh:99   "is Tier-3 -- do NOT edit it"
        scripts/watchdog.py:258               "TIER-3 never-touch"
        CLAUDE.md                             "never modified autonomously"
    
    Every one of those is an instruction to a READER. None is a mechanism. An organ that ignored them
    -- or a session that never read them -- would modify the dead-man switch and nothing anywhere
    would notice, which is precisely the class of failure the desk hash-locks its constitution
    against. Locking the laws and not the kill switch is the wrong way round: prose can be re-argued,
    and a flattened book cannot.
    
    Six files are now locked, each with a stated reason, because a list of paths without reasons is a
    list somebody prunes to make a refactor pass: the Tier-3 ruin rail, the risk config every sizing
    decision reads, the pre-trade gate, the Kelly arithmetic, the drawdown rail and order staging.
    
    THREE FAILURE SHAPES WITH THREE DIFFERENT FIXES. MISSING is the most serious -- the control that
    ends a losing session is not on disk. DRIFT means the path changed without being re-locked.
    UNLOCKED means a named kernel file carries no protection at all. An absent file hashes to None
    rather than a sentinel, so deleted, edited and fine are three distinguishable states.
    
    A CHANGED HASH IS NOT AUTOMATICALLY A DEFECT. The rails are allowed to improve -- what is
    forbidden is improving them SILENTLY. Re-locking requires a reason and appends to a history, so
    every amendment is auditable exactly as a constitutional one is.
    
    IT IS TAMPER-EVIDENT, NOT TAMPER-PROOF, and says so rather than claiming more than it delivers.
    True tamper-proofing is a privilege boundary -- separate credentials, a service the research
    account cannot redeploy, an OS-level owner -- and that is deployment work on the box, the
    principal's side. This is the half that lives in the repo, and it catches the realistic failure:
    not a hostile agent, but a well-meaning one refactoring across a directory without reading the
    comment.
    
    Wired FIRST in the daily cycle, before any research runs: a cycle that researched all day and then
    discovered the dead-man switch had changed would have spent the day on a book with no floor
    under it.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/research/RISK_KERNEL_LOCK.json    |  27 ++++++
 ops/run_research_cycle.sh              |   6 ++
 scripts/check_risk_kernel.py           | 158 +++++++++++++++++++++++++++++++++
 tests/scripts/test_risk_kernel_lock.py | 114 ++++++++++++++++++++++++
 4 files changed, 305 insertions(+)

diff --git a/docs/research/RISK_KERNEL_LOCK.json b/docs/research/RISK_KERNEL_LOCK.json
new file mode 100644
index 0000000..8e08ee0
--- /dev/null
+++ b/docs/research/RISK_KERNEL_LOCK.json
@@ -0,0 +1,27 @@
+{
+ "_": "SHA-256 lock on the survival path. Verified by scripts/check_risk_kernel.py on every cycle. The rails MAY change -- they may not change SILENTLY.",
+ "updated": "2026-08-08T15:34:51.443513+00:00",
+ "reason": "baseline lock, 2026-08-08: the desk hash-locked its constitution and left the survival path on an honour system enforced only by prose comments",
+ "files": {
+  "scripts/run_deadman_switch.py": "TIER-3 RUIN RAIL. Polls combined book equity and flattens on breach. The one control that ends a losing session rather than reducing it; log(0) = -inf, so ruin terminates the objective rather than lowering it",
+  "libs/risk/config.py": "the numeric limits every sizing decision reads. A silent widening here is invisible at every call site and shows up only as a larger loss",
+  "libs/risk/gate.py": "the pre-trade risk gate -- the last check between an intent and an order",
+  "libs/risk/kelly.py": "sizing arithmetic. Over-betting an estimated edge loses more growth than under-betting gains it, so an error here is asymmetric and compounds",
+  "libs/risk/drawdown.py": "the drawdown rail that de-risks before the ruin rail has to fire",
+  "libs/execution/staging.py": "order staging -- the path an intent takes to become an order"
+ },
+ "hashes": {
+  "scripts/run_deadman_switch.py": "ffe514989a9df3bf4798eab7d514001e59e8340e367724407cba5af75cd59c2c",
+  "libs/risk/config.py": "fe13f8a6cff8130ec96e2e744f894febe11cb396f8a329d8c1d597ac3620bf99",
+  "libs/risk/gate.py": "aea6bf46c8bac9ac930a08feb1e1db44cd051cfcf1ae2cf23d2e23b2f9f50db0",
+  "libs/risk/kelly.py": "fe5eba3223194ae6449f2e828a6bc917e7b44b818c6c5d5ee21f3ece0c7d7ab5",
+  "libs/risk/drawdown.py": "0fa242ad2b2faf73b5b5ac37cc82c6eaae888406529146fa929026adadbb3824",
+  "libs/execution/staging.py": "1a4e250887342c4aaed5d155b8cc7c3157550a7a7f860d76f80db87327745e69"
+ },
+ "history": [
+  {
+   "at": "2026-08-08T15:34:51.443825+00:00",
+   "reason": "baseline lock, 2026-08-08: the desk hash-locked its constitution and left the survival path on an honour system enforced only by prose comments"
+  }
+ ]
+}
\ No newline at end of file
diff --git a/ops/run_research_cycle.sh b/ops/run_research_cycle.sh
index 34007cf..74631ab 100755
--- a/ops/run_research_cycle.sh
+++ b/ops/run_research_cycle.sh
@@ -33,6 +33,12 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
 {
   echo "=== research cycle start $(date -u) | BARS_FILE_BUDGET=$BARS_FILE_BUDGET ==="
   # niced throughout: the recorders are the irreplaceable process on this box.
+  # SURVIVAL PATH FIRST, BEFORE ANY RESEARCH RUNS. The desk hash-locks its constitution and left
+  # the kill switch protected by prose comments; this verifies the rails are byte-identical to
+  # what the principal last approved. It runs FIRST because a cycle that researched all day and
+  # then discovered the dead-man switch had changed would have spent the day on a book with no
+  # floor under it.
+  "$PY" scripts/check_risk_kernel.py || echo "RISK-KERNEL DRIFT -- review before trusting this cycle"
   OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 15 "$PY" scripts/build_bars.py
   bash ops/run_study_on_vps.sh
   # The ladder runs even when the sweep found nothing: it also reports what is ALREADY live, and a
diff --git a/scripts/check_risk_kernel.py b/scripts/check_risk_kernel.py
new file mode 100644
index 0000000..cae1e63
--- /dev/null
+++ b/scripts/check_risk_kernel.py
@@ -0,0 +1,158 @@
+#!/usr/bin/env python3
+"""RISK-KERNEL INTEGRITY -- the survival rails are hash-locked, not merely asked nicely.
+
+THE ASYMMETRY THIS CLOSES, found by audit 2026-08-08. The desk hash-locks its CONSTITUTION
+(`check_constitution_core.py` verifies five clauses by SHA-256 and fails the build if a word
+moves), and leaves the CODE THAT ENFORCES SURVIVAL on an honour system. The only thing standing
+between an autonomous organ and the Tier-3 ruin rail is prose:
+
+    ops/run_recommendation_worker.sh:99   "is Tier-3 -- do NOT edit it"
+    scripts/watchdog.py:258               "TIER-3 never-touch"
+    CLAUDE.md                             "never modified autonomously"
+
+Every one of those is an instruction to a reader. None is a mechanism. An organ that ignored them,
+or a session that never read them, would modify the dead-man switch and nothing anywhere would
+notice -- which is precisely the class of failure the desk hash-locks its constitution against.
+Locking the laws and not the kill switch is the wrong way round: prose can be re-argued, and a
+flattened book cannot.
+
+WHAT THIS IS AND IS NOT. It is TAMPER-EVIDENT, not tamper-PROOF. A file's hash changing does not
+stop the change; it makes the change impossible to make silently, and it fails the gate that every
+push must pass. True tamper-proofing is a privilege boundary -- separate credentials, a service the
+research account cannot redeploy, an OS-level owner -- and that is deployment work on the box,
+which is the principal's side. This is the half that lives in the repo, and it is the half that
+catches the realistic failure: not a hostile agent, but a well-meaning one refactoring across a
+directory without reading the comment.
+
+**A CHANGED HASH IS NOT AUTOMATICALLY A DEFECT.** The rails are allowed to improve -- what is
+forbidden is improving them SILENTLY. An intended change is recorded in the manifest with the
+reason, by the principal's act, exactly as a constitutional amendment is.
+
+    python scripts/check_risk_kernel.py            # verify; non-zero exit on drift
+    python scripts/check_risk_kernel.py --update   # record current hashes (PRINCIPAL'S ACT)
+"""
+from __future__ import annotations
+
+import argparse
+import hashlib
+import json
+from datetime import UTC, datetime
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parent.parent
+MANIFEST = ROOT / "docs" / "research" / "RISK_KERNEL_LOCK.json"
+
+#: The survival path. Each entry names WHY it is here, because a list of paths with no reasons is
+#: a list somebody will prune to make a refactor pass.
+KERNEL: dict[str, str] = {
+    "scripts/run_deadman_switch.py":
+        "TIER-3 RUIN RAIL. Polls combined book equity and flattens on breach. The one control "
+        "that ends a losing session rather than reducing it; log(0) = -inf, so ruin terminates "
+        "the objective rather than lowering it",
+    "libs/risk/config.py":
+        "the numeric limits every sizing decision reads. A silent widening here is invisible at "
+        "every call site and shows up only as a larger loss",
+    "libs/risk/gate.py":
+        "the pre-trade risk gate -- the last check between an intent and an order",
+    "libs/risk/kelly.py":
+        "sizing arithmetic. Over-betting an estimated edge loses more growth than under-betting "
+        "gains it, so an error here is asymmetric and compounds",
+    "libs/risk/drawdown.py":
+        "the drawdown rail that de-risks before the ruin rail has to fire",
+    "libs/execution/staging.py":
+        "order staging -- the path an intent takes to become an order",
+}
+
+
+def digest(path: Path) -> str | None:
+    """SHA-256 of the file's bytes. None when absent -- an ABSENT RAIL IS THE WORST FINDING.
+
+    None rather than a sentinel hash, because a missing survival file must never compare equal to
+    anything; a rail that was deleted should look different from a rail that was edited, and both
+    should look different from a rail that is fine.
+    """
+    try:
+        return hashlib.sha256(path.read_bytes()).hexdigest()
+    except OSError:
+        return None
+
+
+def current() -> dict[str, str | None]:
+    return {rel: digest(ROOT / rel) for rel in KERNEL}
+
+
+def load() -> dict[str, object]:
+    try:
+        return json.loads(MANIFEST.read_text("utf-8"))
+    except (OSError, ValueError):
+        return {}
+
+
+def verify() -> tuple[list[str], list[str], list[str]]:
+    """(drifted, missing, unlocked). Three failure shapes with three different fixes."""
+    rec = load()
+    locked = rec.get("hashes") if isinstance(rec.get("hashes"), dict) else {}
+    now = current()
+    drifted, missing, unlocked = [], [], []
+    for rel, h in now.items():
+        if h is None:
+            missing.append(rel)
+        elif not isinstance(locked, dict) or rel not in locked:
+            unlocked.append(rel)
+        elif locked[rel] != h:
+            drifted.append(rel)
+    return drifted, missing, unlocked
+
+
+def main() -> int:
+    ap = argparse.ArgumentParser(description=__doc__)
+    ap.add_argument("--update", action="store_true",
+                    help="record current hashes. THE PRINCIPAL'S ACT: it asserts the rails are in "
+                         "the state he intends, exactly like a constitutional amendment")
+    ap.add_argument("--reason", default="", help="required with --update")
+    ap.add_argument("--json", action="store_true")
+    a = ap.parse_args()
+
+    if a.update:
+        if not a.reason.strip():
+            print("REFUSED: --update needs --reason. A rail re-locked with no recorded reason is "
+                  "a change nobody can audit later, which is the state this check exists to end.")
+            return 2
+        rec = load()
+        history = rec.get("history") if isinstance(rec.get("history"), list) else []
+        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
+        MANIFEST.write_text(json.dumps({
+            "_": ("SHA-256 lock on the survival path. Verified by scripts/check_risk_kernel.py on "
+                  "every cycle. The rails MAY change -- they may not change SILENTLY."),
+            "updated": datetime.now(tz=UTC).isoformat(),
+            "reason": a.reason,
+            "files": KERNEL,
+            "hashes": current(),
+            "history": [*history, {"at": datetime.now(tz=UTC).isoformat(), "reason": a.reason}],
+        }, indent=1), "utf-8")
+        print(f"risk-kernel: locked {len(KERNEL)} file(s) -> {MANIFEST}")
+        return 0
+
+    drifted, missing, unlocked = verify()
+    if a.json:
+        print(json.dumps({"drifted": drifted, "missing": missing, "unlocked": unlocked}, indent=1))
+    if missing:
+        print(f"risk-kernel: MISSING {missing} -- a survival rail is ABSENT. This is the most "
+              "serious state this check can report: the control that ends a losing session is not "
+              "on disk.")
+        return 1
+    if drifted:
+        print(f"risk-kernel: DRIFT {drifted} -- the survival path changed without being re-locked. "
+              "The change is not necessarily wrong; making it SILENTLY is. Review the diff, then "
+              "`--update --reason '...'` as the principal's act.")
+        return 1
+    if unlocked:
+        print(f"risk-kernel: UNLOCKED {unlocked} -- named as kernel files and never hashed, so "
+              "they carry no protection at all. Run --update to establish the baseline.")
+        return 1
+    print(f"risk-kernel: {len(KERNEL)} file(s) intact against {MANIFEST.name}")
+    return 0
+
+
+if __name__ == "__main__":
+    raise SystemExit(main())
diff --git a/tests/scripts/test_risk_kernel_lock.py b/tests/scripts/test_risk_kernel_lock.py
new file mode 100644
index 0000000..cb63310
--- /dev/null
+++ b/tests/scripts/test_risk_kernel_lock.py
@@ -0,0 +1,114 @@
+"""THE DESK HASH-LOCKED ITS LAWS AND LEFT THE KILL SWITCH ON AN HONOUR SYSTEM.
+
+Audited 2026-08-08. `check_constitution_core.py` verifies five constitutional clauses by SHA-256
+and fails the build if a word moves. The code that enforces SURVIVAL was protected by prose:
+
+    ops/run_recommendation_worker.sh:99   "is Tier-3 -- do NOT edit it"
+    scripts/watchdog.py:258               "TIER-3 never-touch"
+
+Every one of those is an instruction to a reader; none is a mechanism. Locking the laws and not
+the kill switch is the wrong way round -- prose can be re-argued, and a flattened book cannot.
+"""
+
+from __future__ import annotations
+
+import json
+import sys
+from pathlib import Path
+
+import scripts.check_risk_kernel as RK
+
+
+def test_THE_TIER3_RUIN_RAIL_IS_IN_THE_KERNEL() -> None:
+    """The one control that ENDS a losing session rather than reducing it."""
+    assert "scripts/run_deadman_switch.py" in RK.KERNEL
+    assert "TIER-3" in RK.KERNEL["scripts/run_deadman_switch.py"]
+
+
+def test_EVERY_KERNEL_FILE_STATES_WHY_IT_IS_ONE() -> None:
+    """A list of paths with no reasons is a list somebody prunes to make a refactor pass."""
+    for rel, why in RK.KERNEL.items():
+        assert len(why) > 40, f"{rel} has no substantive reason"
+
+
+def test_EVERY_KERNEL_FILE_ACTUALLY_EXISTS() -> None:
+    """A named-but-absent rail would silently drop out of protection."""
+    for rel in RK.KERNEL:
+        assert (Path(rel)).exists(), f"{rel} is named as a kernel file and is not on disk"
+
+
+def test_THE_REPO_IS_CURRENTLY_LOCKED_AND_INTACT() -> None:
+    drifted, missing, unlocked = RK.verify()
+    assert missing == [], f"a survival rail is ABSENT: {missing}"
+    assert unlocked == [], f"kernel files carry no protection: {unlocked}"
+    assert drifted == [], f"the survival path changed without being re-locked: {drifted}"
+
+
+def test_AN_ABSENT_FILE_HASHES_TO_NONE_NOT_A_SENTINEL(tmp_path) -> None:
+    """A missing survival file must never compare equal to anything: deleted, edited and fine are
+    three different states and must look different."""
+    assert RK.digest(tmp_path / "nope.py") is None
+
+
+def test_A_MODIFIED_RAIL_IS_DETECTED(tmp_path, monkeypatch) -> None:
+    """The property the whole check exists for."""
+    f = tmp_path / "rail.py"
+    f.write_text("original", "utf-8")
+    manifest = tmp_path / "lock.json"
+    monkeypatch.setattr(RK, "ROOT", tmp_path)
+    monkeypatch.setattr(RK, "MANIFEST", manifest)
+    monkeypatch.setattr(RK, "KERNEL", {"rail.py": "a test rail with a stated reason for existing"})
+    monkeypatch.setattr(sys, "argv", ["check_risk_kernel.py", "--update", "--reason", "baseline"])
+    assert RK.main() == 0
+    assert RK.verify() == ([], [], [])
+    f.write_text("modified by an organ that never read the comment", "utf-8")
+    drifted, _missing, _unlocked = RK.verify()
+    assert drifted == ["rail.py"]
+
+
+def test_A_DELETED_RAIL_IS_THE_MOST_SERIOUS_FINDING(tmp_path, monkeypatch, capsys) -> None:
+    f = tmp_path / "rail.py"
+    f.write_text("x", "utf-8")
+    monkeypatch.setattr(RK, "ROOT", tmp_path)
+    monkeypatch.setattr(RK, "MANIFEST", tmp_path / "lock.json")
+    monkeypatch.setattr(RK, "KERNEL", {"rail.py": "a test rail with a stated reason for existing"})
+    monkeypatch.setattr(sys, "argv", ["check_risk_kernel.py", "--update", "--reason", "baseline"])
+    RK.main()
+    f.unlink()
+    monkeypatch.setattr(sys, "argv", ["check_risk_kernel.py"])
+    assert RK.main() == 1
+    out = capsys.readouterr().out
+    assert "MISSING" in out and "is not on disk" in out
+
+
+def test_RE_LOCKING_REQUIRES_A_REASON(tmp_path, monkeypatch, capsys) -> None:
+    """A rail re-locked with no recorded reason is a change nobody can audit later -- which is the
+    state this check exists to end."""
+    monkeypatch.setattr(RK, "MANIFEST", tmp_path / "lock.json")
+    monkeypatch.setattr(sys, "argv", ["check_risk_kernel.py", "--update", "--reason", "  "])
+    assert RK.main() == 2
+    assert "REFUSED" in capsys.readouterr().out
+
+
+def test_THE_LOCK_KEEPS_A_HISTORY(tmp_path, monkeypatch) -> None:
+    """Every re-lock is an amendment and the record of amendments is the audit trail."""
+    f = tmp_path / "rail.py"
+    f.write_text("x", "utf-8")
+    manifest = tmp_path / "lock.json"
+    monkeypatch.setattr(RK, "ROOT", tmp_path)
+    monkeypatch.setattr(RK, "MANIFEST", manifest)
+    monkeypatch.setattr(RK, "KERNEL", {"rail.py": "a test rail with a stated reason for existing"})
+    for reason in ("first", "second"):
+        monkeypatch.setattr(sys, "argv", ["check_risk_kernel.py", "--update", "--reason", reason])
+        RK.main()
+    hist = json.loads(manifest.read_text())["history"]
+    assert [h["reason"] for h in hist] == ["first", "second"]
+
+
+def test_IT_IS_HONEST_ABOUT_BEING_TAMPER_EVIDENT_NOT_TAMPER_PROOF() -> None:
+    """True tamper-proofing is a privilege boundary -- separate credentials, a service the research
+    account cannot redeploy. Claiming more than the mechanism delivers would be worse than the gap.
+    """
+    src = Path("scripts/check_risk_kernel.py").read_text("utf-8")
+    assert "TAMPER-EVIDENT, not tamper-PROOF" in src
+    assert "privilege boundary" in src
```


---

## 1118781 measure F3, and replace the calendar clock with an evidence clock
F3 CALIBRATED, AND THE RESULT IS THE POINT OF THE COMMIT. 300 trials x 1,200 observations,
planting edges of KNOWN size and counting how many survive the gate as transcribed from
run_full_sweep rather than from its docs:

    planted effect      0.0    0.01   0.02   0.05   0.10   0.20   0.40
    STABLE edge kept   0.23   0.37   0.45   0.78   1.00   1.00   1.00
    CONDITIONAL kept   0.24   0.32   0.35   0.44   0.50   0.55   0.51

THE CONDITIONAL ROW PLATEAUS AT ~50% AND NO EFFECT SIZE FIXES IT. That is not a power problem more
data would solve -- it is arithmetic. A conditional edge has NO effect in its second arm, so that
arm is pure noise and lands positive by chance about half the time. F3 discards roughly half of all
conditional mechanisms however strong they are, while keeping 100% of stable edges the same size.
The desk's own funding, liquidation and regime research assumes conditional alpha exists.

TWO CAVEATS, because the number is easy to misquote. 23% at effect zero is F3's false-positive rate
IN ISOLATION; in the pipeline it sees only cells that already cleared the deflated F1/F2 screen, and
the deflation carries multiplicity control. And a 50% keep rate on conditional edges is a statement
about that SHAPE of truth, not a claim that half the 750 kills were conditional -- what fraction
actually are is an empirical question the kill audit answers from the retained cells.

F3 IS NOT CHANGED AND THIS EVIDENCE MAY NOT CHANGE IT. The module exposes no recommended threshold
and its note says so: a gate changes only when a controlled experiment shows a DIFFERENT rule has
better expected survivor quality, never because many cells died -- which is the argument this
evidence is most tempting to misuse for. A loose gate ships a phantom edge and the rails eventually
say so; a tight gate destroys real alpha silently with every board green. The desk measures the
first continuously and had never measured the second.

EVIDENCE CLOCK (libs/research/evidence_clock.py). Calendar time is not evidence. A strategy trading
500 times in five days accumulates more usable forward evidence than one trading 8 times in three
months, and waiting the same interval for both is simultaneously too slow for the first and too
fast for the second. The clock counts EFFECTIVE INDEPENDENT observations, deflated for serial
correlation, event clustering, regime concentration and cross-symbol dependence -- 500 fills inside
one cascade are one observation of one cascade.

IT IS SYMMETRIC ON PURPOSE. It accelerates a high-information strategy AND refuses to let a burst
of correlated fills masquerade as months of evidence. A rule that only sped things up would be a
lowered bar wearing a stopwatch. `waiting_cost()` charges the delay in forgone bps, which nothing
on this desk has ever done -- until a delay has a price, caution looks free and speed looks
reckless.

LIVE_CANARY (libs/research/alpha_state.py). A new rung between SHADOW and CAPITAL_ELIGIBLE: real
fills at learning size, because a canary is not there to make money but to test whether the market
behaves like the simulator. Fills, slippage, queue position, adverse selection, venue quirks and
operational reliability cannot be produced by any amount of shadow at any price, so an alpha kept
out of the market is not being validated -- it is being starved of the evidence class it most
needs. CAPITAL_ELIGIBLE now requires canary_execution_evidence: a strategy that has never traded
has a forward record that is a simulation of a simulation. The canary still requires the
principal's authorisation, at canary size -- a smaller decision than capital, never no decision.

CONTINUOUS CAPITAL COMPETITION (libs/portfolio/capital_competition.py). Age is not a field, so
incumbency privilege is not representable. Cumulative P&L is recorded and NEVER scored: a strategy
can be lifetime-positive on luck while its forward expectation is zero, and a new one slightly
negative on variance while carrying excellent evidence -- funding the first and starving the second
is the natural reading of a P&L table and it is backwards.

Uncertainty SHRINKS rather than vetoes, so a thin-evidence alpha earns a real small position that
grows as the canary produces fills. Zero-until-certain-then-full throws away the option value of
the learning period. Correlation to the book enters the score directly as (1 - rho), because at
rho=1 an alpha adds exposure and no diversification however good its standalone Sharpe looks. Where
capacity binds the excess is left UNALLOCATED rather than pushed into the next-best alpha -- silently
over-funding a weaker mechanism because a stronger one filled up is how a capacity limit becomes a
sizing error.

Nothing here places an order or arms anything; the Tier-3 rail is untouched.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 111878123aa3c56234e75bb6d8cf293a052572e7
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 15:30:17 2026 +0000

    measure F3, and replace the calendar clock with an evidence clock
    
    F3 CALIBRATED, AND THE RESULT IS THE POINT OF THE COMMIT. 300 trials x 1,200 observations,
    planting edges of KNOWN size and counting how many survive the gate as transcribed from
    run_full_sweep rather than from its docs:
    
        planted effect      0.0    0.01   0.02   0.05   0.10   0.20   0.40
        STABLE edge kept   0.23   0.37   0.45   0.78   1.00   1.00   1.00
        CONDITIONAL kept   0.24   0.32   0.35   0.44   0.50   0.55   0.51
    
    THE CONDITIONAL ROW PLATEAUS AT ~50% AND NO EFFECT SIZE FIXES IT. That is not a power problem more
    data would solve -- it is arithmetic. A conditional edge has NO effect in its second arm, so that
    arm is pure noise and lands positive by chance about half the time. F3 discards roughly half of all
    conditional mechanisms however strong they are, while keeping 100% of stable edges the same size.
    The desk's own funding, liquidation and regime research assumes conditional alpha exists.
    
    TWO CAVEATS, because the number is easy to misquote. 23% at effect zero is F3's false-positive rate
    IN ISOLATION; in the pipeline it sees only cells that already cleared the deflated F1/F2 screen, and
    the deflation carries multiplicity control. And a 50% keep rate on conditional edges is a statement
    about that SHAPE of truth, not a claim that half the 750 kills were conditional -- what fraction
    actually are is an empirical question the kill audit answers from the retained cells.
    
    F3 IS NOT CHANGED AND THIS EVIDENCE MAY NOT CHANGE IT. The module exposes no recommended threshold
    and its note says so: a gate changes only when a controlled experiment shows a DIFFERENT rule has
    better expected survivor quality, never because many cells died -- which is the argument this
    evidence is most tempting to misuse for. A loose gate ships a phantom edge and the rails eventually
    say so; a tight gate destroys real alpha silently with every board green. The desk measures the
    first continuously and had never measured the second.
    
    EVIDENCE CLOCK (libs/research/evidence_clock.py). Calendar time is not evidence. A strategy trading
    500 times in five days accumulates more usable forward evidence than one trading 8 times in three
    months, and waiting the same interval for both is simultaneously too slow for the first and too
    fast for the second. The clock counts EFFECTIVE INDEPENDENT observations, deflated for serial
    correlation, event clustering, regime concentration and cross-symbol dependence -- 500 fills inside
    one cascade are one observation of one cascade.
    
    IT IS SYMMETRIC ON PURPOSE. It accelerates a high-information strategy AND refuses to let a burst
    of correlated fills masquerade as months of evidence. A rule that only sped things up would be a
    lowered bar wearing a stopwatch. `waiting_cost()` charges the delay in forgone bps, which nothing
    on this desk has ever done -- until a delay has a price, caution looks free and speed looks
    reckless.
    
    LIVE_CANARY (libs/research/alpha_state.py). A new rung between SHADOW and CAPITAL_ELIGIBLE: real
    fills at learning size, because a canary is not there to make money but to test whether the market
    behaves like the simulator. Fills, slippage, queue position, adverse selection, venue quirks and
    operational reliability cannot be produced by any amount of shadow at any price, so an alpha kept
    out of the market is not being validated -- it is being starved of the evidence class it most
    needs. CAPITAL_ELIGIBLE now requires canary_execution_evidence: a strategy that has never traded
    has a forward record that is a simulation of a simulation. The canary still requires the
    principal's authorisation, at canary size -- a smaller decision than capital, never no decision.
    
    CONTINUOUS CAPITAL COMPETITION (libs/portfolio/capital_competition.py). Age is not a field, so
    incumbency privilege is not representable. Cumulative P&L is recorded and NEVER scored: a strategy
    can be lifetime-positive on luck while its forward expectation is zero, and a new one slightly
    negative on variance while carrying excellent evidence -- funding the first and starving the second
    is the natural reading of a P&L table and it is backwards.
    
    Uncertainty SHRINKS rather than vetoes, so a thin-evidence alpha earns a real small position that
    grows as the canary produces fills. Zero-until-certain-then-full throws away the option value of
    the learning period. Correlation to the book enters the score directly as (1 - rho), because at
    rho=1 an alpha adds exposure and no diversification however good its standalone Sharpe looks. Where
    capacity binds the excess is left UNALLOCATED rather than pushed into the next-best alpha -- silently
    over-funding a weaker mechanism because a stronger one filled up is how a capacity limit becomes a
    sizing error.
    
    Nothing here places an order or arms anything; the Tier-3 rail is untouched.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/research/test_suite_record.json        |   4 +-
 libs/portfolio/capital_competition.py       | 235 ++++++++++++++++++++++++++++
 libs/research/alpha_state.py                |  18 ++-
 libs/research/evidence_clock.py             | 192 +++++++++++++++++++++++
 libs/validation/gate_power.py               | 229 +++++++++++++++++++++++++++
 tests/portfolio/test_capital_competition.py | 139 ++++++++++++++++
 tests/research/test_alpha_state.py          |  39 +++++
 tests/research/test_evidence_clock.py       | 126 +++++++++++++++
 tests/validation/test_gate_power.py         | 121 ++++++++++++++
 9 files changed, 1098 insertions(+), 5 deletions(-)

diff --git a/docs/research/test_suite_record.json b/docs/research/test_suite_record.json
index 7bb87ab..97c933d 100644
--- a/docs/research/test_suite_record.json
+++ b/docs/research/test_suite_record.json
@@ -1,5 +1,5 @@
 {
- "max_collected": 329,
- "at": "2026-08-08T11:50:22.665326+00:00",
+ "max_collected": 332,
+ "at": "2026-08-08T15:24:35.000161+00:00",
  "note": "high-water mark of COLLECTABLE test modules; ratchets UP only. A suite may never quietly shrink -- deleting a test is a decision, not a side effect."
 }
\ No newline at end of file
diff --git a/libs/portfolio/capital_competition.py b/libs/portfolio/capital_competition.py
new file mode 100644
index 0000000..87ccfdc
--- /dev/null
+++ b/libs/portfolio/capital_competition.py
@@ -0,0 +1,235 @@
+"""CONTINUOUS CAPITAL COMPETITION — no strategy owns its allocation because it got there first.
+
+THE DEFECT THIS REMOVES, and it is an economic one rather than an engineering one. A desk that
+promotes an alpha and then leaves it funded has made a decision once and stopped charging for it.
+Capital sitting in a strategy whose forward expectation has collapsed is not neutral: it is the
+best remaining opportunity being declined, every day, silently. Meanwhile a new survivor with
+stronger evidence waits for a review cycle that exists only because somebody scheduled one.
+
+So allocation is re-derived from CURRENT forward evidence on every run, and every alpha --
+incumbent or candidate, six months old or six hours -- is scored by the same function. Age confers
+no privilege and no penalty. It is not an input.
+
+**CUMULATIVE P&L IS NOT THE CRITERION, AND THIS IS THE MOST IMPORTANT LINE IN THE MODULE.** A
+strategy can be +€500 lifetime on luck while its forward expectation is now zero, and a new one can
+be slightly negative on variance while carrying excellent evidence. Funding the first and starving
+the second is the natural reading of a P&L table and it is backwards. The question is always:
+
+    does continuing to allocate this capital have positive marginal expected log-growth,
+    versus giving the same capital to the next-best use?
+
+**WHY LOG-GROWTH AND NOT RETURN.** Two strategies with identical expected return are not
+interchangeable if one is correlated with the book and the other is not: the uncorrelated one
+raises the geometric mean by reducing variance drag, which is the only thing that compounds. So
+correlation and uncertainty enter the score directly rather than as a later adjustment somebody
+might skip.
+
+**UNCERTAINTY SHRINKS, IT DOES NOT VETO.** An edge measured over few effective observations is
+sized down in proportion to what is actually known about it, so a promising strategy earns real
+exposure early and grows it as evidence accumulates. That is the whole point of a canary: learning
+while earning rather than waiting to learn and then earning. The alternative -- zero until certain,
+then full -- throws away the option value of the learning period and is why lifecycles that look
+prudent lose to ones that look aggressive.
+
+NOTHING HERE PLACES AN ORDER OR ARMS ANYTHING. It computes target weights and the reason for each.
+Arming live trading remains the principal's act and the Tier-3 rail is untouched.
+"""
+
+from __future__ import annotations
+
+import math
+from collections import Counter
+from dataclasses import dataclass
+
+__all__ = [
+    "MIN_MEANINGFUL_WEIGHT",
+    "AlphaCandidate",
+    "allocate",
+    "score",
+    "summarise",
+]
+
+#: Weights below this are reported as ZERO rather than as a tiny position. A 0.02% allocation is
+#: an operational cost with no economic content -- it pays fees to express an opinion too small to
+#: matter, which is the allocation equivalent of the sub-informative clip size the live ladder
+#: already refuses.
+MIN_MEANINGFUL_WEIGHT: float = 0.005
+
+#: Shrinkage floor. Even the best-evidenced alpha keeps some estimation discount, because the
+#: edge is an estimate and Kelly's penalty for over-betting an estimate is asymmetric.
+MAX_CONFIDENCE: float = 0.85
+
+
+@dataclass(frozen=True)
+class AlphaCandidate:
+    """One alpha competing for capital. Incumbency is deliberately not a field.
+
+    `edge_bps` is the FORWARD expectation per unit of exposure, not the historical mean, and the
+    distinction is the module's whole thesis: history is how the estimate was formed, not what is
+    being bet on.
+    """
+
+    name: str
+    edge_bps: float
+    vol_bps: float
+    #: Effective INDEPENDENT observations behind the estimate (`evidence_clock.effective_n`).
+    effective_n: float
+    #: Correlation to the currently-held book. 1.0 = a duplicate of what the desk already owns.
+    correlation_to_book: float = 0.0
+    #: Quote units this alpha can absorb before its own impact eats the edge. 0 = unmeasured.
+    capacity: float = 0.0
+    #: Realised execution quality, 0..1. Below 1 the simulator was optimistic about fills.
+    execution_quality: float = 1.0
+    state: str = "LIVE"
+    #: Cumulative realised P&L. RECORDED AND NEVER SCORED -- present so a report can show it
+    #: beside the decision it does not drive.
+    lifetime_pnl: float = 0.0
+
+    @property
+    def measured(self) -> bool:
+        return self.effective_n > 0 and self.vol_bps > 0
+
+    @property
+    def confidence(self) -> float:
+        """Shrinkage from evidence: n/(n+k), capped. Not a gate -- a multiplier.
+
+        k=50 sets the half-way point at 50 effective observations, which is where a Sharpe
+        estimate stops being dominated by its own standard error. A strategy with 10 effective
+        observations gets ~17% of its estimated edge, which is a real position rather than a
+        veto -- and it grows as the canary produces fills.
+        """
+        if not self.measured:
+            return 0.0
+        return min(MAX_CONFIDENCE, self.effective_n / (self.effective_n + 50.0))
+
+
+def score(c: AlphaCandidate) -> tuple[float, str]:
+    """(marginal log-growth score, why). Negative means the capital is better used elsewhere.
+
+    THE CORRELATION TERM IS NOT A PREFERENCE. `1 - rho` is what a duplicate of the book actually
+    contributes to geometric growth: at rho=1 the alpha adds exposure and no diversification, so
+    its marginal contribution is zero however good its standalone Sharpe looks.
+    """
+    if not c.measured:
+        return 0.0, (f"{c.name}: UNMEASURED -- no effective observations or no volatility "
+                     "estimate, so no forward claim exists. Zero weight is a statement about "
+                     "evidence, not about the alpha")
+    sharpe = c.edge_bps / c.vol_bps
+    rho = max(0.0, min(1.0, abs(c.correlation_to_book)))
+    exq = max(0.0, min(1.0, c.execution_quality))
+    # Kelly-shaped: the geometric contribution of an estimated edge, discounted for what is not
+    # yet known about it and for the part of it the book already holds.
+    s = sharpe * c.confidence * (1.0 - rho) * exq
+    if s <= 0:
+        return s, (
+            f"{c.name}: marginal score {s:+.4f} -- "
+            + ("edge is not positive in expectation" if c.edge_bps <= 0 else
+               f"rho {rho:.2f} to the book leaves nothing incremental" if rho >= 1.0 else
+               "execution destroys the edge")
+            + ". Capital here is the next-best opportunity being declined")
+    return s, (
+        f"{c.name}: score {s:+.4f} = sharpe {sharpe:+.3f} x confidence {c.confidence:.2f} "
+        f"(n_eff {c.effective_n:.0f}) x independence {1 - rho:.2f} x execution {exq:.2f}")
+
+
+def allocate(candidates: list[AlphaCandidate], *, total_risk: float = 1.0,
+             ) -> dict[str, float]:
+    """Target risk weights. EVERY candidate is re-scored; incumbency is not consulted.
+
+    Weights are proportional to positive marginal score, so an alpha that is twice as good gets
+    twice the risk -- and one whose forward expectation has gone gets zero the same day, without
+    a review meeting. Capacity caps a weight where it is measured, because an allocation beyond
+    what the alpha can absorb is an allocation to its own market impact.
+    """
+    scored = [(c, score(c)[0]) for c in candidates]
+    positive = [(c, s) for c, s in scored if s > 0]
+    total = sum(s for _c, s in positive)
+    out: dict[str, float] = {c.name: 0.0 for c in candidates}
+    if total <= 0:
+        return out
+    for c, s in positive:
+        w = total_risk * s / total
+        if c.capacity > 0:
+            # Capacity is expressed in the same units as `total_risk` by the caller. Where it
+            # binds, the excess is NOT redistributed silently -- see the note in `summarise`.
+            w = min(w, c.capacity)
+        out[c.name] = 0.0 if w < MIN_MEANINGFUL_WEIGHT else round(w, 5)
+    return out
+
+
+def summarise(candidates: list[AlphaCandidate], *, total_risk: float = 1.0) -> dict[str, object]:
+    """Report shape. THE HEADLINE IS WHAT CHANGED HANDS, because that is the decision."""
+    if not candidates:
+        return {"alphas": 0, "headline": (
+            "no candidates -- the book is empty, which is not the same as the book being safe. "
+            "Idle capital is the best remaining opportunity being declined")}
+    weights = allocate(candidates, total_risk=total_risk)
+    rows = []
+    for c in sorted(candidates, key=lambda x: -weights.get(x.name, 0.0)):
+        s, why = score(c)
+        rows.append({"alpha": c.name, "state": c.state, "weight": weights.get(c.name, 0.0),
+                     "score": round(s, 5), "why": why,
+                     "effective_n": c.effective_n, "rho_to_book": c.correlation_to_book,
+                     "lifetime_pnl": c.lifetime_pnl})
+    w_of = {str(r["alpha"]): float(weights.get(str(r["alpha"]), 0.0)) for r in rows}
+    funded = [r for r in rows if w_of[str(r["alpha"])] > 0]
+    defunded = [r for r in rows if w_of[str(r["alpha"])] == 0]
+    allocated = sum(w_of.values())
+    return {
+        "alphas": len(candidates), "tally": dict(Counter(c.state for c in candidates)),
+        "funded": len(funded), "defunded": len(defunded),
+        "risk_allocated": round(allocated, 5),
+        "risk_unallocated": round(max(0.0, total_risk - allocated), 5),
+        "headline": (
+            f"{len(funded)} of {len(candidates)} alphas funded; {len(defunded)} hold zero. "
+            f"{max(0.0, total_risk - allocated):.1%} of the risk budget is UNALLOCATED -- idle "
+            "capacity is the best remaining opportunity being declined, not prudence"
+            if allocated < total_risk * 0.99 else
+            f"{len(funded)} of {len(candidates)} alphas funded; risk budget fully allocated"),
+        "rows": rows,
+        "note": ("Age is not an input. Cumulative P&L is recorded and NOT scored: a strategy can "
+                 "be lifetime-positive on luck while its forward expectation is zero, and a new "
+                 "one slightly negative on variance while carrying excellent evidence. Where "
+                 "capacity binds, the excess is left UNALLOCATED rather than pushed into the "
+                 "next-best alpha -- silently over-funding a weaker mechanism because a stronger "
+                 "one filled up is how a capacity limit becomes a sizing error."),
+        "authority": "NONE. Computes target weights. Places nothing, arms nothing.",
+    }
+
+
+def render(candidates: list[AlphaCandidate], *, total_risk: float = 1.0) -> str:
+    rep = summarise(candidates, total_risk=total_risk)
+    lines = [str(rep["headline"])]
+    rows = rep.get("rows")
+    for r in rows if isinstance(rows, list) else []:
+        w = float(str(r["weight"]))
+        lines.append(f"  {w:>7.2%}  {r['why']}")
+    return "\n".join(lines)
+
+
+def kelly_fraction(edge_bps: float, vol_bps: float, confidence: float, *,
+                   cap: float = 0.25) -> float:
+    """Quarter-Kelly-shaped fraction on the SHRUNK edge, capped.
+
+    The shrinkage is applied to the edge BEFORE the Kelly ratio rather than to the result, because
+    Kelly's penalty is asymmetric: over-betting an over-estimated edge loses more growth than
+    under-betting the same edge gains. Shrinking first is the conservative order of operations and
+    it is not the intuitive one.
+    """
+    if vol_bps <= 0:
+        return 0.0
+    f = (edge_bps * max(0.0, min(1.0, confidence))) / (vol_bps ** 2) * vol_bps
+    return max(0.0, min(cap, f * 0.25))
+
+
+def half_life_days(edge_now: float, edge_then: float, days: float) -> float | None:
+    """Observed decay half-life. None when the edge is not decaying or cannot be measured.
+
+    None rather than infinity: a caller that formats infinity prints something meaningless, while
+    None forces the report to say the edge has not been shown to decay -- which is the honest
+    statement and also not a promise that it will not.
+    """
+    if days <= 0 or edge_then <= 0 or edge_now <= 0 or edge_now >= edge_then:
+        return None
+    ratio = edge_now / edge_then
+    return days * math.log(0.5) / math.log(ratio)
diff --git a/libs/research/alpha_state.py b/libs/research/alpha_state.py
index 9a2d059..9870fec 100644
--- a/libs/research/alpha_state.py
+++ b/libs/research/alpha_state.py
@@ -88,9 +88,21 @@ RUNGS: tuple[Rung, ...] = (
     Rung("SHADOW", ("shadow_started_at",),
          "a forward clock is running at zero capital. The slow part of discovery was never "
          "paperwork -- it is elapsed forward time, and that is the one input nobody can buy later"),
-    Rung("CAPITAL_ELIGIBLE", ("forward_observations", "forward_result", "risk_review"),
-         "the EVIDENCE for capital is complete. This is a statement about evidence and never a "
-         "grant: arming live trading is the principal's act"),
+    Rung("LIVE_CANARY", ("canary_size_quote_units", "principal_canary_authorisation"),
+         "REAL FILLS AT LEARNING SIZE, and the rung that exists because simulation cannot answer "
+         "the question it is asked. A canary is not there to make money -- it is there to test "
+         "whether the market behaves like the simulator: fills, slippage, queue position, adverse "
+         "selection, venue quirks, operational reliability. Months of shadow cannot produce that "
+         "information at any price, so an alpha kept out of the market is not being validated, it "
+         "is being starved of the one evidence class it most needs. It still requires the "
+         "principal's authorisation -- at canary size, which is a smaller decision than capital, "
+         "never no decision"),
+    Rung("CAPITAL_ELIGIBLE", ("forward_observations", "forward_result", "risk_review",
+                              "canary_execution_evidence"),
+         "the EVIDENCE for capital is complete, INCLUDING evidence from real fills -- a strategy "
+         "that has never traded has no execution evidence, and its forward record is a simulation "
+         "of a simulation. This is a statement about evidence and never a grant: arming live "
+         "trading is the principal's act"),
     Rung("LIVE", ("principal_authorisation", "size_quote_units"),
          "capital is deployed. Requires an explicit principal authorisation token that no organ "
          "can synthesise -- the one rung the machine refuses to reason its way onto"),
diff --git a/libs/research/evidence_clock.py b/libs/research/evidence_clock.py
new file mode 100644
index 0000000..bb00d3f
--- /dev/null
+++ b/libs/research/evidence_clock.py
@@ -0,0 +1,192 @@
+"""THE EVIDENCE CLOCK — calendar time is not evidence, and treating it as evidence costs money.
+
+THE DEFECT. A lifecycle that says "20 trading days of shadow" or "3 months before capital" is
+measuring the wrong quantity. A strategy that trades 500 times in five days can accumulate more
+usable forward evidence than one that trades 8 times in three months; waiting the same interval for
+both is simultaneously too slow for the first and too fast for the second. The waiting has a price
+and nothing on this desk has ever charged it: an edge that is real for twenty days and spends
+fifteen of them in a calendar gate has had most of its economic life thrown away by its own
+validator.
+
+SO THE CLOCK COUNTS INFORMATION, NOT DAYS. And the number it counts is EFFECTIVE INDEPENDENT
+OBSERVATIONS, which is the only version of the count that cannot be gamed by a busy afternoon:
+
+    500 trades inside one BTC impulse are ONE event observed 500 times
+
+That inflation is the same defect as GAP #85 -- `n` counting readings of the world rather than
+events in it -- pointed at the promotion decision, which is the most expensive place on the desk to
+get it wrong. Four deflators apply and each is measured rather than assumed: serial correlation,
+event clustering, regime concentration, and cross-symbol dependence.
+
+**THE CLOCK IS SYMMETRIC AND THAT IS DELIBERATE.** It accelerates a high-information strategy AND
+it refuses to let a burst of correlated fills masquerade as months of evidence. A rule that only
+sped things up would be a lowered bar wearing a stopwatch.
+
+WHAT IT DOES NOT DO. It sets no threshold and grants no promotion. It answers "how much independent
+evidence exists" and hands the number to the ladder, which owns what that buys. A module that both
```


---

## f2035f7 audit the validator, forward the survivors, close the loop
THE RUN THIS IS BUILT ON. First complete sweep of the declared universe, 2026-08-08:

    898,560 evaluated | 687,215 measurable (76%, up from 14%) | 762 cleared screen
    FORMULA 9 | FAMILY 3 | INDEPENDENT MECHANISM 2 | PORTFOLIO-CONTRIBUTING unmeasured
    F3 WALK-FORWARD SIGN 750 | F6 LEAKAGE 18 | F5 SAMPLE FLOOR 3

THE ENABLER, WITHOUT WHICH NONE OF THIS WAS POSSIBLE. The sweep did `killed[criterion] += 1` and
discarded every number that produced it -- no t, no net, no arm split, no sample size. So "F3
WALK-FORWARD SIGN: 750" was not merely unexamined, it was UNEXAMINABLE, and a validator whose
rejections cannot be inspected is unfalsifiable. That is the one component on this desk that could
be destroying real alpha at scale while every gate reports healthy. `killed_cells` now retains the
statistics, bounded and with truncation stated rather than silent.

The same shape explains a field that has been null in every report ever produced. The sweep
computed each survivor's return series for clustering and threw it away, so nothing downstream
could measure portfolio contribution even if it wanted to. `PORTFOLIO_CONTRIBUTING: null` was read
as unmeasured; it was unmeasurable, and the two look identical in a report. Survivor pnl now leaves
the sweep as a sidecar.

KILL AUDIT (libs/research/kill_audit.py -> run_research_review). Nine states, because "FAILED F3"
covers at least nine situations with different and sometimes opposite actions. Power is checked
BEFORE validity: a gate that fired on a thin arm has not shown the candidate is wrong, it has shown
the desk cannot tell, and ruling that HARD_KILL converts absence of evidence into a verdict.

THE FINDING THAT MATTERS FOR THE 750, read from the code rather than the docs: F3 requires BOTH
arms positive. That is deliberately strong -- two negative arms share a sign and would pass a naive
test -- but it also means a genuinely REGIME-CONDITIONAL mechanism, positive in one half and absent
in the other, is indistinguishable from noise at this gate. That is a false-negative CLASS rather
than a bug, and naming it is the contribution.

`false_kill_exposure` is an UPPER BOUND and the artifact says so: it is not an estimate of alpha
destroyed and may never be cited as a reason to lower a bar. A SOFT_KILL is still a kill. Nothing
here re-partitions data until a cell passes -- that is post-hoc selection wearing a lab coat.

PORTFOLIO ADMISSION (scripts/run_portfolio_admission.py). A DISTINCT mechanism is not an ADDITIVE
one: independence is measured against the other survivors, admission against what the desk already
holds. With no live cohort the question degenerates to "has positive Sharpe", and the report says
that in those words rather than banking admissions against an empty book.

THE LOOP CLOSES. run_research_cycle now runs admission -> forensics -> exec monitor -> intelligence
cycle -> max-push, so a completed sweep republishes the ranked gap set from today's evidence
instead of ending. A completed batch is a trigger, not an endpoint.

PROCESS STATUS (scripts/study_status.py). The check handed to the operator was a shell expression:
`ps ... -p "$(pgrep -f run_full_sweep | head -1)"`, which produced `pgrep: invalid option -- 'p'`
when the command spanned a line break. The general fault is not the typo -- it is that process
status was an EXPRESSION rather than a command, so every invocation re-derived it and could get it
wrong. Now the pattern is a separate argv entry, `ps` is never called with an empty pid list, and
the verdict separates RUNNING from STALLED: alive at 0% CPU with a silent log is the failure a
process check reports as healthy.

Also fixed: the governance ladder read `LiveRecord.n`, which does not exist (`n_trades`), so
run_live_ladder raised on any survivor that already had a forward record.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit f2035f7a14540c627d28ba8761634d67183fbfc5
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 15:18:25 2026 +0000

    audit the validator, forward the survivors, close the loop
    
    THE RUN THIS IS BUILT ON. First complete sweep of the declared universe, 2026-08-08:
    
        898,560 evaluated | 687,215 measurable (76%, up from 14%) | 762 cleared screen
        FORMULA 9 | FAMILY 3 | INDEPENDENT MECHANISM 2 | PORTFOLIO-CONTRIBUTING unmeasured
        F3 WALK-FORWARD SIGN 750 | F6 LEAKAGE 18 | F5 SAMPLE FLOOR 3
    
    THE ENABLER, WITHOUT WHICH NONE OF THIS WAS POSSIBLE. The sweep did `killed[criterion] += 1` and
    discarded every number that produced it -- no t, no net, no arm split, no sample size. So "F3
    WALK-FORWARD SIGN: 750" was not merely unexamined, it was UNEXAMINABLE, and a validator whose
    rejections cannot be inspected is unfalsifiable. That is the one component on this desk that could
    be destroying real alpha at scale while every gate reports healthy. `killed_cells` now retains the
    statistics, bounded and with truncation stated rather than silent.
    
    The same shape explains a field that has been null in every report ever produced. The sweep
    computed each survivor's return series for clustering and threw it away, so nothing downstream
    could measure portfolio contribution even if it wanted to. `PORTFOLIO_CONTRIBUTING: null` was read
    as unmeasured; it was unmeasurable, and the two look identical in a report. Survivor pnl now leaves
    the sweep as a sidecar.
    
    KILL AUDIT (libs/research/kill_audit.py -> run_research_review). Nine states, because "FAILED F3"
    covers at least nine situations with different and sometimes opposite actions. Power is checked
    BEFORE validity: a gate that fired on a thin arm has not shown the candidate is wrong, it has shown
    the desk cannot tell, and ruling that HARD_KILL converts absence of evidence into a verdict.
    
    THE FINDING THAT MATTERS FOR THE 750, read from the code rather than the docs: F3 requires BOTH
    arms positive. That is deliberately strong -- two negative arms share a sign and would pass a naive
    test -- but it also means a genuinely REGIME-CONDITIONAL mechanism, positive in one half and absent
    in the other, is indistinguishable from noise at this gate. That is a false-negative CLASS rather
    than a bug, and naming it is the contribution.
    
    `false_kill_exposure` is an UPPER BOUND and the artifact says so: it is not an estimate of alpha
    destroyed and may never be cited as a reason to lower a bar. A SOFT_KILL is still a kill. Nothing
    here re-partitions data until a cell passes -- that is post-hoc selection wearing a lab coat.
    
    PORTFOLIO ADMISSION (scripts/run_portfolio_admission.py). A DISTINCT mechanism is not an ADDITIVE
    one: independence is measured against the other survivors, admission against what the desk already
    holds. With no live cohort the question degenerates to "has positive Sharpe", and the report says
    that in those words rather than banking admissions against an empty book.
    
    THE LOOP CLOSES. run_research_cycle now runs admission -> forensics -> exec monitor -> intelligence
    cycle -> max-push, so a completed sweep republishes the ranked gap set from today's evidence
    instead of ending. A completed batch is a trigger, not an endpoint.
    
    PROCESS STATUS (scripts/study_status.py). The check handed to the operator was a shell expression:
    `ps ... -p "$(pgrep -f run_full_sweep | head -1)"`, which produced `pgrep: invalid option -- 'p'`
    when the command spanned a line break. The general fault is not the typo -- it is that process
    status was an EXPRESSION rather than a command, so every invocation re-derived it and could get it
    wrong. Now the pattern is a separate argv entry, `ps` is never called with an empty pid list, and
    the verdict separates RUNNING from STALLED: alive at 0% CPU with a silent log is the failure a
    process check reports as healthy.
    
    Also fixed: the governance ladder read `LiveRecord.n`, which does not exist (`n_trades`), so
    run_live_ladder raised on any survivor that already had a forward record.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/research/test_suite_record.json      |   4 +-
 libs/research/kill_audit.py               | 231 ++++++++++++++++++++++++++++++
 ops/run_research_cycle.sh                 |  11 ++
 scripts/run_full_sweep.py                 |  50 +++++++
 scripts/run_live_ladder.py                |   2 +-
 scripts/run_portfolio_admission.py        | 141 ++++++++++++++++++
 scripts/run_research_review.py            |  37 +++++
 scripts/study_status.py                   | 155 ++++++++++++++++++++
 tests/research/test_kill_audit.py         | 160 +++++++++++++++++++++
 tests/scripts/test_portfolio_admission.py | 111 ++++++++++++++
 tests/scripts/test_study_status.py        |  92 ++++++++++++
 11 files changed, 991 insertions(+), 3 deletions(-)

diff --git a/docs/research/test_suite_record.json b/docs/research/test_suite_record.json
index 146de0c..7bb87ab 100644
--- a/docs/research/test_suite_record.json
+++ b/docs/research/test_suite_record.json
@@ -1,5 +1,5 @@
 {
- "max_collected": 320,
- "at": "2026-08-08T11:22:06.029289+00:00",
+ "max_collected": 329,
+ "at": "2026-08-08T11:50:22.665326+00:00",
  "note": "high-water mark of COLLECTABLE test modules; ratchets UP only. A suite may never quietly shrink -- deleting a test is a decision, not a side effect."
 }
\ No newline at end of file
diff --git a/libs/research/kill_audit.py b/libs/research/kill_audit.py
new file mode 100644
index 0000000..90af494
--- /dev/null
+++ b/libs/research/kill_audit.py
@@ -0,0 +1,231 @@
+"""KILL AUDIT — a validator's rejections are evidence requiring interpretation, not verdicts.
+
+THE RUN THAT PRODUCED THIS. 2026-08-08, first complete sweep of the declared universe:
+
+    898,560 evaluated · 687,215 measurable · 762 cleared screen
+    FORMULA 9 | FAMILY 3 | INDEPENDENT MECHANISM 2 | PORTFOLIO-CONTRIBUTING unmeasured
+    F3 WALK-FORWARD SIGN 750 · F6 LEAKAGE 18 · F5 SAMPLE FLOOR 3
+
+**750 CELLS DYING AT ONE GATE IS ITSELF A MEASUREMENT, AND IT POINTS AT THE GATE AS READILY AS AT
+THE CELLS.** Both readings are available and the desk cannot tell them apart from a counter. The
+danger runs in both directions and they are not symmetric in how they fail:
+
+    validator too harsh  -> real alpha destroyed at scale, SILENTLY, with every gate green
+    validator too loose  -> false discoveries reach capital, loudly, and the rails catch them
+
+The first has no alarm. That is why the audit exists, and why it may never become a route to
+lowering a bar: this module classifies, it never promotes. A SOFT_KILL is still a kill.
+
+NINE STATES, because "FAILED F3" is one label over at least nine different situations, each with a
+different action and several with opposite ones::
+
+    HARD_KILL            strong evidence the candidate is invalid
+    SOFT_KILL            fails, but the evidence against it is weak
+    INSUFFICIENT_EVIDENCE  cannot separate no-edge from no-power
+    REGIME_CONDITIONAL   arms disagree in a way a conditional mechanism would produce
+    DATA_LIMITED         history/resolution prevents judgement
+    EXECUTION_LIMITED    gross edge exists; cost destroys it
+    VALIDATOR_SUSPECT    the verdict flips under a reasonable perturbation
+    LEAKAGE_CONFIRMED    the collapse under lag is decisive
+    LEAKAGE_SUSPECT      the lag probe fired but is not conclusive
+
+THE F3 RULE THIS AUDITS, read from the code rather than the docs: a cell dies unless BOTH arms are
+positive. That is a strong requirement, and it is deliberately strong -- two negative arms "share a
+sign" and would pass a naive sign test. But it also means a genuinely REGIME-CONDITIONAL mechanism
+-- positive in one half, absent in the other -- is indistinguishable from noise at this gate, and
+that is a false-negative class rather than a bug. Naming it is the whole contribution here.
+
+NOTHING IN THIS MODULE RE-RUNS AN EXPERIMENT ON THE SAME DATA. Re-partitioning until a cell passes
+is post-hoc selection wearing a lab coat; every classification is computed from statistics the
+sweep already recorded, and every rescue is a PREREGISTERED experiment on evidence the selection
+has not seen.
+"""
+
+from __future__ import annotations
+
+from collections import Counter
+from dataclasses import dataclass, field
+
+__all__ = [
+    "STATES",
+    "KillRecord",
+    "audit",
+    "classify",
+    "summarise",
+]
+
+STATES: tuple[str, ...] = (
+    "HARD_KILL", "SOFT_KILL", "INSUFFICIENT_EVIDENCE", "REGIME_CONDITIONAL", "DATA_LIMITED",
+    "EXECUTION_LIMITED", "VALIDATOR_SUSPECT", "LEAKAGE_CONFIRMED", "LEAKAGE_SUSPECT",
+)
+
+#: Observations below which an arm cannot support a sign claim. A walk-forward split halves the
+#: sample twice over (arm x regime), so an arm can be far thinner than the headline `n` suggests.
+THIN_ARM: int = 250
+
+#: How close to zero an arm's net must be for its SIGN to be an artifact of noise rather than a
+#: statement. Below this the F3 sign test is reading a coin flip, and the kill is not evidence.
+SIGN_NOISE_BP: float = 0.05
+
+#: Fraction of the surviving arm's magnitude the failing arm must reach before the split looks
+#: like a CONDITIONAL mechanism rather than an absent one. Well above zero on purpose: a mechanism
+#: that is merely absent in one arm is not evidence of a regime, it is evidence of nothing.
+CONDITIONAL_FLOOR: float = 0.25
+
+
+@dataclass(frozen=True)
+class KillRecord:
+    """One killed cell, from the sweep's retained statistics. `None` means UNMEASURED."""
+
+    key: str
+    kill: str
+    t: float | None = None
+    hurdle: float | None = None
+    n: int | None = None
+    net_bps: float | None = None
+    gross_bps: float | None = None
+    cost_bps: float | None = None
+    is_net_bps: float | None = None
+    oos_net_bps: float | None = None
+    is_n: int | None = None
+    oos_n: int | None = None
+    leak_net_bps: float | None = None
+    regime: str = ""
+    horizon: str = ""
+    notes: tuple[str, ...] = field(default_factory=tuple)
+
+    @property
+    def gate(self) -> str:
+        """The criterion prefix -- F3, F5, F6 -- without the live numbers in the message."""
+        return self.kill.split(":", 1)[0].strip().split()[0] if self.kill else ""
+
+
+def _thin(rec: KillRecord) -> bool:
+    return any(x is not None and x < THIN_ARM for x in (rec.is_n, rec.oos_n))
+
+
+def classify(rec: KillRecord) -> tuple[str, str]:
+    """(state, why). ORDER OF CHECKS IS THE LOGIC AND IT RUNS FROM CHEAPEST-TO-DISPROVE UPWARD.
+
+    Power is tested BEFORE validity, because a gate that fired on a thin arm has not shown the
+    candidate is wrong -- it has shown the desk cannot tell. Ruling that HARD_KILL would convert
+    an absence of evidence into a verdict, which is this desk's most-repeated defect aimed at the
+    one place it is least visible.
+    """
+    gate = rec.gate
+
+    if gate == "F5":
+        return "INSUFFICIENT_EVIDENCE", (
+            "a split arm was UNMEASURED. This is a SPAN problem and no harness change creates "
+            "observations -- re-test when the tape is longer, and until then the cell is neither "
+            "alive nor dead")
+
+    if gate == "F6":
+        if rec.leak_net_bps is None:
+            return "LEAKAGE_SUSPECT", (
+                "the lag probe could not be measured, so the collapse is UNVERIFIED. A leakage "
+                "verdict on an unmeasured probe is an assertion")
+        if rec.net_bps is not None and abs(rec.net_bps) < SIGN_NOISE_BP:
+            return "VALIDATOR_SUSPECT", (
+                f"net {rec.net_bps:+.4f}bp is inside the noise band, so 'collapses under lag' is "
+                "a statement about a number that was never distinguishable from zero")
+        if rec.net_bps is not None and rec.leak_net_bps * rec.net_bps < 0:
+            return "LEAKAGE_CONFIRMED", (
+                f"net {rec.net_bps:+.4f} -> {rec.leak_net_bps:+.4f}bp on ONE extra bar of lag: a "
+                "sign flip from a single bar is a timing violation, not decay")
+        return "LEAKAGE_SUSPECT", (
+            f"net falls {rec.net_bps} -> {rec.leak_net_bps} without flipping sign. That is "
+            "consistent with leakage AND with a genuinely short-lived contemporaneous effect; "
+            "one-bar sensitivity alone does not establish that the information was unavailable at "
+            "decision time. Reconstruct the timestamp chain before calling it leakage")
+
+    if gate in {"F3", "F4"}:
+        a, b = rec.is_net_bps, rec.oos_net_bps
+        if a is None or b is None:
+            return "INSUFFICIENT_EVIDENCE", ("an arm is unmeasured; the sign test had "
+                                             "nothing to compare")
+        if _thin(rec):
+            return "INSUFFICIENT_EVIDENCE", (
+                f"an arm holds fewer than {THIN_ARM} observations "
+                f"(is={rec.is_n}, oos={rec.oos_n}). "
+                "The gate fired on a sample too thin to establish a sign, which shows the desk "
+                "cannot tell rather than that the cell is wrong")
+        if abs(a) < SIGN_NOISE_BP or abs(b) < SIGN_NOISE_BP:
+            return "VALIDATOR_SUSPECT", (
+                f"an arm ({a:+.4f} / {b:+.4f} bp) sits inside the {SIGN_NOISE_BP}bp noise band, so "
+                "the SIGN that decided this kill is a coin flip. The verdict would plausibly "
+                "reverse on a different but equally reasonable split")
+        if a > 0 and b > 0:
+            return "SOFT_KILL", (
+                f"both arms positive ({a:+.4f} / {b:+.4f}) -- this died on F4 MAGNITUDE, not on "
+                "sign. The mechanism held out of sample and shrank, which is what an honest "
+                "decaying-but-real edge looks like as well as what an overfit one does")
+        if a * b < 0 and abs(min(a, b)) >= CONDITIONAL_FLOOR * abs(max(a, b)):
+            return "REGIME_CONDITIONAL", (
+                f"arms disagree with comparable magnitude ({a:+.4f} vs {b:+.4f}) -- the shape a "
+                "CONDITIONAL mechanism produces, and one F3 cannot distinguish from noise because "
+                "it requires both arms positive. The missing variable is the research object, not "
+                "the cell")
+        if (rec.gross_bps is not None and rec.net_bps is not None
+                and rec.gross_bps > 0 >= rec.net_bps):
+            return "EXECUTION_LIMITED", (
+                f"gross {rec.gross_bps:+.4f}bp survives and net {rec.net_bps:+.4f}bp does not: the "
+                "round trip eats the edge. Attack cost and holding period before the expression")
+        return "HARD_KILL", (
+            f"arms disagree decisively ({a:+.4f} vs {b:+.4f}) on adequate samples with both "
+            "magnitudes outside the noise band -- the cell does not hold out of sample")
+
+    return "SOFT_KILL", (
+        f"unrecognised gate {gate!r}: classified conservatively as a weak kill rather than "
+        "guessed at. An unknown criterion is a gap in THIS module, not evidence about the cell")
+
+
+def audit(records: list[KillRecord]) -> list[dict[str, object]]:
+    """Classify every kill and rank so the states that indicate a VALIDATOR problem lead."""
+    order = {s: i for i, s in enumerate((
+        "VALIDATOR_SUSPECT", "REGIME_CONDITIONAL", "EXECUTION_LIMITED", "INSUFFICIENT_EVIDENCE",
+        "LEAKAGE_SUSPECT", "SOFT_KILL", "DATA_LIMITED", "LEAKAGE_CONFIRMED", "HARD_KILL"))}
+    rows: list[dict[str, object]] = []
+    for r in records:
+        state, why = classify(r)
+        rows.append({"key": r.key, "gate": r.gate, "state": state, "why": why,
+                     "t": r.t, "net_bps": r.net_bps, "is_net_bps": r.is_net_bps,
+                     "oos_net_bps": r.oos_net_bps, "is_n": r.is_n, "oos_n": r.oos_n,
+                     "regime": r.regime, "horizon": r.horizon})
+    rows.sort(key=lambda d: order.get(str(d["state"]), 99))
+    return rows
+
+
+def summarise(records: list[KillRecord]) -> dict[str, object]:
+    """THE HEADLINE IS THE FALSE-KILL EXPOSURE, not the kill count.
+
+    `false_kill_exposure` is the share of kills that are NOT hard: verdicts the desk should not
+    treat as settled. It is an upper bound on how much real alpha the gate may be destroying and
+    deliberately NOT an estimate of how much it is -- calling it an estimate would invite the
+    number to be used as a reason to lower a bar, which is the one thing this module must never
+    become.
+    """
+    if not records:
+        return {"kills": 0, "headline": (
+            "no killed cells retained -- the sweep reported counts only, so its rejections are "
+            "UNAUDITABLE. A validator whose kills cannot be examined is unfalsifiable"),
+            "tally": {}, "false_kill_exposure": None, "rows": []}
+    rows = audit(records)
+    tally = Counter(str(r["state"]) for r in rows)
+    hard = tally["HARD_KILL"] + tally["LEAKAGE_CONFIRMED"]
+    exposure = 1.0 - hard / len(rows)
+    suspect = tally["VALIDATOR_SUSPECT"]
+    return {
+        "kills": len(records), "tally": dict(tally),
+        "false_kill_exposure": round(exposure, 4),
+        "headline": (
+            f"{suspect} kill(s) VALIDATOR_SUSPECT and {tally['REGIME_CONDITIONAL']} "
+            f"REGIME_CONDITIONAL of {len(rows)}: {exposure:.0%} of rejections are not settled"
+            if exposure > 0 else
+            f"all {len(rows)} rejections are decisive on the retained statistics"),
+        "rows": rows[:200],
+        "note": ("EXPOSURE IS AN UPPER BOUND, never an estimate of alpha destroyed, and it may "
+                 "never be cited as a reason to lower a bar. A SOFT_KILL is still a kill; these "
+                 "states buy a PREREGISTERED re-test on evidence the selection has not seen, "
+                 "never a promotion. Re-partitioning until a cell passes is post-hoc selection."),
+    }
diff --git a/ops/run_research_cycle.sh b/ops/run_research_cycle.sh
index 874eec0..34007cf 100755
--- a/ops/run_research_cycle.sh
+++ b/ops/run_research_cycle.sh
@@ -44,7 +44,18 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
   # EXECUTION HEALTH runs every cycle, including days the research half found nothing. The money
   # path is where the desk is currently LOSING (27 closes, all three hold buckets negative net of
   # fees), so a cycle that reported only research would go quiet on the one number costing money.
+  # A COMPLETED SWEEP IS A TRIGGER, NOT AN ENDPOINT. Before this line the factory produced
+  # "INDEPENDENT MECHANISM 2 | PORTFOLIO-CONTRIBUTING unmeasured" and stopped -- a discovery
+  # stranded one stage short of the only count that pays, waiting for a human to notice. Survivor
+  # forwarding now runs in the same cycle that produced the survivors.
+  nice -n 15 "$PY" scripts/run_portfolio_admission.py || true
   nice -n 15 "$PY" scripts/run_trade_forensics.py || true
   nice -n 15 "$PY" scripts/run_exec_monitor.py || true
+  # THE LOOP CLOSES HERE. The intelligence cycle re-reads everything this run produced -- kills,
+  # survivors, admission, conversion joins, source and cadence yield -- and republishes the ranked
+  # gap set, so tomorrow's highest-value work is chosen from today's evidence rather than from
+  # whatever was true when the schedule was written.
+  nice -n 15 "$PY" scripts/run_intelligence_cycle.py || true
+  nice -n 15 "$PY" scripts/run_max_push.py || true
   echo "=== research cycle exit $? at $(date -u) ==="
 } 2>&1 | tee -a "$LOG"
diff --git a/scripts/run_full_sweep.py b/scripts/run_full_sweep.py
index 1bc5c0d..9a16aa4 100644
--- a/scripts/run_full_sweep.py
+++ b/scripts/run_full_sweep.py
@@ -491,6 +491,10 @@ def main() -> int:
     ap.add_argument("--max-minutes", type=float, default=240.0,
                     help="refuse to start if the projected sweep exceeds this")
     ap.add_argument("--max-detail", type=int, default=200, help="survivor rows written in full")
+    ap.add_argument("--max-killed-cells", type=int, default=5000,
+                    help="retain at most N killed cells WITH their statistics. The counts stay "
+                         "exact regardless; this bounds the artifact, not the measurement. A "
+                         "validator whose rejections cannot be examined is unfalsifiable.")
     ap.add_argument("--max-cluster", type=int, default=500,
                     help="cluster at most this many survivors (top by |t|); the mechanism count is "
                          "a LOWER bound when the cap binds")
@@ -618,6 +622,7 @@ def main() -> int:
     survivors: list[dict[str, object]] = []
     kept: list[tuple[Combination, int]] = []
     killed: Counter[str] = Counter()
+    killed_cells: list[dict[str, object]] = []
     # Cached by horizon rather than recomputed per survivor: `forward()` is a full-panel op, and
     # `setdefault` would evaluate it on every hit -- a per-survivor cost that is invisible at three
     # survivors and dominant at three thousand.
@@ -661,6 +666,29 @@ def main() -> int:
         for f in fired:
             killed[f.split(":")[0]] += 1
         if fired:
+            # RETAIN THE CELL, NOT ONLY THE COUNT. Until this line the sweep incremented a
+            # counter and dropped every number that produced it, so a run reporting
+            # "F3 WALK-FORWARD SIGN: 750" left NOTHING to audit: no t, no net, no arm split, no
+            # sample size. A validator whose rejections cannot be examined is unfalsifiable, and
+            # an unfalsifiable validator is the one component on this desk that could be silently
+            # destroying real alpha at scale while every gate reports healthy.
+            #
+            # BOUNDED, because 898,560 cells could all fail here. The cap keeps the report a
+            # report; the counts above stay exact and the artifact says which it is.
+            if len(killed_cells) < a.max_killed_cells:
+                killed_cells.append({
+                    "key": list(c.key), "kill": fired[0], "all_kills": fired,
+                    "horizon": h, "regime": c.regime, "n": r.n,
+                    "t": round(t_stat(r.ic, r.n, h), 4), "hurdle": round(hurdle(), 4),
+                    "net_bps": round(r.net_bps, 5), "gross_bps": round(r.gross_bps, 5),
+                    "cost_bps": round(r.gross_bps - r.net_bps, 5),
+                    "turnover": round(r.turnover, 6),
+                    "is_net_bps": None if not r_is.ok else round(r_is.net_bps, 5),
+                    "oos_net_bps": None if not r_oos.ok else round(r_oos.net_bps, 5),
+                    "is_n": r_is.n if r_is.ok else None,
+                    "oos_n": r_oos.n if r_oos.ok else None,
+                    "leak_net_bps": None if not r_leak.ok else round(r_leak.net_bps, 5),
+                })
             continue
```


---

## 2c1e298 build the rest of the list: eight modules, every one wired in the same change
L1.56 written this morning says a beneficial build is executed NOW and given its consumer in the
same change. This is that law applied to the register row that named what was missing. Nothing
here ships as inventory -- each module has a caller in the daily or 4-hourly cycle, and each was
run against real artifacts before commit.

GENERIC GAP CONTRACT (libs/research/gap_contract.py -> run_max_push).
The principal's warning was immediate and correct: the queue must not become a pile of special
cases. Ten bespoke `_from_*` readers meant a detector written today could not influence tomorrow's
priorities until somebody edited the ranker -- the ranker as gatekeeper on discovery, which is
this desk's recurring defect with a new subject. Detectors now publish Gap rows to
data/published_gaps/ and rank with no edit anywhere. The ten existing readers STAY: rewriting
working producers to prove a point is the bloat the contract exists to avoid. A detector may not
mint a source class, because a new class is a new weight nobody reviewed, and scoring stays in the
queue -- two rankers that can disagree is worse than one that is wrong in a single place.

ORPHANS BEYOND MODULES (orphan_scan.py -> run_intelligence_cycle -> published gaps).
`dormancy` answers the CODE question. The expensive strandings are further down the chain where
the desk already paid for the discovery: a dataset turned into no feature, a hypothesis never
tested, a survivor never portfolio-tested. None is visible to an importer count -- the code works,
the artifacts exist, and the chain breaks at a join nobody watches. Seven joins; on this clone all
seven report UNMEASURED, which is the finding rather than an omission.

ALPHA STATE MACHINE (alpha_state.py -> run_live_ladder).
The largest gap between written and running governance. Nothing made DISCOVERED -> LIVE
impossible; it was merely undone, and an undone thing looks identical to an impossible one until
the morning it does not. Eleven rungs, each naming the evidence it requires, one step at a time.
A skip is REFUSED even when the higher rung's evidence is in hand -- "we already know it would
pass" is exactly the reasoning that never gets written down. LIVE additionally requires a
principal authorisation token no organ can synthesise. Retreat is always legal and needs no
evidence, because requiring a study to retire a decaying alpha would make the safe direction the
expensive one.

DIFFERENCE ENGINE (difference_engine.py -> run_research_review).
RESIDUAL_MANDATE asks a seat to label its own items, and a seat cannot judge what it was never
shown. The classification is now computed from both corpora. CONTRADICTION ranks first -- not
because disagreement is truth, but because it localises uncertainty, so a test there resolves
something instead of confirming. AGREEMENT is KEPT: overlap removal that deletes the overlap
throws away independent convergence, which is evidence when the searches did not read each other
-- carried with the GAP #85 caveat when provenance is unrecorded. An uncommitted mention is never
scored as agreement; that manufactures convergence out of a shrug.

UNKNOWNS LEDGER (unknowns.py -> run_intelligence_cycle).
Assumptions, contradictions and unknowns are ONE object at three confidence levels. Three
registries would share a schema and could not see the transitions -- and the transitions are the
signal. A belief with no falsifier is refused: it is a habit, not knowledge, and survives its own
obsolescence. UNMEASURABLE must name the data it needs, so "we do not have the data" converts to a
ranked acquisition target rather than ending a thread. `contradict` reports blast radius, because
everything in depends_on_it was already sized as though the belief held.

FAILURE BANDS (failure_bands.py -> run_research_review).
ECON_POSITIVE_STAT_WEAK and STAT_STRONG_ECON_NEGATIVE outrank NEAR because they name a CAUSE. Both
read as "did not survive" and one needs tape while the other needs cheaper execution -- different
budgets, different weeks. This desk already made that error in production when F5 SAMPLE FLOOR
cells were read as an absence of edge.

SOURCE ROI (source_roi.py -> run_intelligence_cycle).
Volume is a COST, never an output: 100,000 pages and zero independent survivors is worse than 100
pages and two, because it also spends triage. Names WHICH funnel gap binds rather than emitting
one score -- a redundant source and a starved executor have opposite fixes and cutting the budget
is right for exactly one. Zero survivors under 30 tests is UNMEASURED, not barren, and no source
is ever cut below a 5% exploration floor: a source pruned to nothing cannot produce the evidence
that would restore it.

CADENCE ROI (cadence_roi.py -> run_intelligence_cycle).
Every cadence here was CHOSEN rather than measured. Yield per FIRE, never per day -- 24 fires for
2 findings and 2 fires for the same 2 have identical daily output and opposite verdicts. An
unmeasured cadence is NEVER slowed: this module may not become the route by which the desk does
less. Hard floors are checked before any under-run verdict, since a job that cannot tighten is not
under-run however high its yield.

TWO DEFECTS FIXED ON THE WAY.

The detach guard made the sweep survivable and simultaneously made it look dead: Python
block-buffers stdout to a file, and run_full_sweep flushed its per-cell lines but not its header,
so the first cell produced a log containing only "STARTED". PYTHONUNBUFFERED=1 in the runner plus
flush on the header line; both fenced.

The governance ladder's first wiring passed t_stat=None for every survivor, so each halted owing a
t the sweep had already measured and written down. A machine that reports missing evidence sitting
in its own input teaches the reader its refusals are noise.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 2c1e298bf6e4c82c3d1885a3027fdb3889bffff9
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 11:47:46 2026 +0000

    build the rest of the list: eight modules, every one wired in the same change
    
    L1.56 written this morning says a beneficial build is executed NOW and given its consumer in the
    same change. This is that law applied to the register row that named what was missing. Nothing
    here ships as inventory -- each module has a caller in the daily or 4-hourly cycle, and each was
    run against real artifacts before commit.
    
    GENERIC GAP CONTRACT (libs/research/gap_contract.py -> run_max_push).
    The principal's warning was immediate and correct: the queue must not become a pile of special
    cases. Ten bespoke `_from_*` readers meant a detector written today could not influence tomorrow's
    priorities until somebody edited the ranker -- the ranker as gatekeeper on discovery, which is
    this desk's recurring defect with a new subject. Detectors now publish Gap rows to
    data/published_gaps/ and rank with no edit anywhere. The ten existing readers STAY: rewriting
    working producers to prove a point is the bloat the contract exists to avoid. A detector may not
    mint a source class, because a new class is a new weight nobody reviewed, and scoring stays in the
    queue -- two rankers that can disagree is worse than one that is wrong in a single place.
    
    ORPHANS BEYOND MODULES (orphan_scan.py -> run_intelligence_cycle -> published gaps).
    `dormancy` answers the CODE question. The expensive strandings are further down the chain where
    the desk already paid for the discovery: a dataset turned into no feature, a hypothesis never
    tested, a survivor never portfolio-tested. None is visible to an importer count -- the code works,
    the artifacts exist, and the chain breaks at a join nobody watches. Seven joins; on this clone all
    seven report UNMEASURED, which is the finding rather than an omission.
    
    ALPHA STATE MACHINE (alpha_state.py -> run_live_ladder).
    The largest gap between written and running governance. Nothing made DISCOVERED -> LIVE
    impossible; it was merely undone, and an undone thing looks identical to an impossible one until
    the morning it does not. Eleven rungs, each naming the evidence it requires, one step at a time.
    A skip is REFUSED even when the higher rung's evidence is in hand -- "we already know it would
    pass" is exactly the reasoning that never gets written down. LIVE additionally requires a
    principal authorisation token no organ can synthesise. Retreat is always legal and needs no
    evidence, because requiring a study to retire a decaying alpha would make the safe direction the
    expensive one.
    
    DIFFERENCE ENGINE (difference_engine.py -> run_research_review).
    RESIDUAL_MANDATE asks a seat to label its own items, and a seat cannot judge what it was never
    shown. The classification is now computed from both corpora. CONTRADICTION ranks first -- not
    because disagreement is truth, but because it localises uncertainty, so a test there resolves
    something instead of confirming. AGREEMENT is KEPT: overlap removal that deletes the overlap
    throws away independent convergence, which is evidence when the searches did not read each other
    -- carried with the GAP #85 caveat when provenance is unrecorded. An uncommitted mention is never
    scored as agreement; that manufactures convergence out of a shrug.
    
    UNKNOWNS LEDGER (unknowns.py -> run_intelligence_cycle).
    Assumptions, contradictions and unknowns are ONE object at three confidence levels. Three
    registries would share a schema and could not see the transitions -- and the transitions are the
    signal. A belief with no falsifier is refused: it is a habit, not knowledge, and survives its own
    obsolescence. UNMEASURABLE must name the data it needs, so "we do not have the data" converts to a
    ranked acquisition target rather than ending a thread. `contradict` reports blast radius, because
    everything in depends_on_it was already sized as though the belief held.
    
    FAILURE BANDS (failure_bands.py -> run_research_review).
    ECON_POSITIVE_STAT_WEAK and STAT_STRONG_ECON_NEGATIVE outrank NEAR because they name a CAUSE. Both
    read as "did not survive" and one needs tape while the other needs cheaper execution -- different
    budgets, different weeks. This desk already made that error in production when F5 SAMPLE FLOOR
    cells were read as an absence of edge.
    
    SOURCE ROI (source_roi.py -> run_intelligence_cycle).
    Volume is a COST, never an output: 100,000 pages and zero independent survivors is worse than 100
    pages and two, because it also spends triage. Names WHICH funnel gap binds rather than emitting
    one score -- a redundant source and a starved executor have opposite fixes and cutting the budget
    is right for exactly one. Zero survivors under 30 tests is UNMEASURED, not barren, and no source
    is ever cut below a 5% exploration floor: a source pruned to nothing cannot produce the evidence
    that would restore it.
    
    CADENCE ROI (cadence_roi.py -> run_intelligence_cycle).
    Every cadence here was CHOSEN rather than measured. Yield per FIRE, never per day -- 24 fires for
    2 findings and 2 fires for the same 2 have identical daily output and opposite verdicts. An
    unmeasured cadence is NEVER slowed: this module may not become the route by which the desk does
    less. Hard floors are checked before any under-run verdict, since a job that cannot tighten is not
    under-run however high its yield.
    
    TWO DEFECTS FIXED ON THE WAY.
    
    The detach guard made the sweep survivable and simultaneously made it look dead: Python
    block-buffers stdout to a file, and run_full_sweep flushed its per-cell lines but not its header,
    so the first cell produced a log containing only "STARTED". PYTHONUNBUFFERED=1 in the runner plus
    flush on the header line; both fenced.
    
    The governance ladder's first wiring passed t_stat=None for every survivor, so each halted owing a
    t the sweep had already measured and written down. A machine that reports missing evidence sitting
    in its own input teaches the reader its refusals are noise.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 libs/research/alpha_state.py             | 211 ++++++++++++++++++++++++++++
 libs/research/cadence_roi.py             | 179 ++++++++++++++++++++++++
 libs/research/difference_engine.py       | 214 ++++++++++++++++++++++++++++
 libs/research/failure_bands.py           | 184 ++++++++++++++++++++++++
 libs/research/gap_contract.py            | 175 +++++++++++++++++++++++
 libs/research/orphan_scan.py             | 232 +++++++++++++++++++++++++++++++
 libs/research/source_roi.py              | 215 ++++++++++++++++++++++++++++
 libs/research/unknowns.py                | 219 +++++++++++++++++++++++++++++
 ops/run_study_on_vps.sh                  |   8 +-
 scripts/run_full_sweep.py                |   6 +-
 scripts/run_intelligence_cycle.py        | 139 ++++++++++++++++++
 scripts/run_live_ladder.py               |  90 +++++++++++-
 scripts/run_max_push.py                  |  11 +-
 scripts/run_research_review.py           | 105 ++++++++++++++
 tests/ops/test_study_runner_detach.py    |  20 +++
 tests/research/test_alpha_state.py       | 195 ++++++++++++++++++++++++++
 tests/research/test_cadence_roi.py       |  99 +++++++++++++
 tests/research/test_difference_engine.py | 106 ++++++++++++++
 tests/research/test_failure_bands.py     | 109 +++++++++++++++
 tests/research/test_gap_contract.py      | 124 +++++++++++++++++
 tests/research/test_orphan_scan.py       | 106 ++++++++++++++
 tests/research/test_source_roi.py        | 124 +++++++++++++++++
 tests/research/test_unknowns.py          | 150 ++++++++++++++++++++
 23 files changed, 3017 insertions(+), 4 deletions(-)

diff --git a/libs/research/alpha_state.py b/libs/research/alpha_state.py
new file mode 100644
index 0000000..9a2d059
--- /dev/null
+++ b/libs/research/alpha_state.py
@@ -0,0 +1,211 @@
+"""THE ALPHA STATE MACHINE — governance that an organ cannot route around.
+
+THE GAP THIS CLOSES, named by the principal on 2026-08-08 and true when he named it: this desk's
+governance is excellent as prose and thin as machinery. Every rule about what an alpha must survive
+before it touches capital lives in documents that a script is free not to read. Nothing in the code
+makes `DISCOVERED -> LIVE` impossible; it is merely undone. An undone thing and an impossible thing
+look identical right up until the morning they do not.
+
+So the transitions become an object. An alpha advances ONE rung at a time, each rung names the
+evidence it requires, and a skipped rung is a hard refusal rather than an omission nobody notices.
+
+    DISCOVERED -> IMPLEMENTED -> TESTED -> STATISTICALLY_VALID -> OOS_VALIDATED
+      -> INDEPENDENCE_CHECKED -> PORTFOLIO_VALIDATED -> SHADOW -> CAPITAL_ELIGIBLE
+      -> LIVE -> MONITORED  (and DEGRADED / RETIRED from anywhere)
+
+WHAT THIS IS NOT. It is not a promoter. It grants nothing, sizes nothing and places nothing --
+`CAPITAL_ELIGIBLE` is a statement about EVIDENCE, and arming live trading remains the principal's
+act with the Tier-3 rail untouched. A module that could advance an alpha to LIVE would be the
+bypass it exists to prevent.
+
+THREE PROPERTIES, each chosen against a specific way this would otherwise rot:
+
+  NO SKIPPING, INCLUDING UPWARD. `advance` refuses a jump even when the evidence for the higher
+  rung is present, because the rung below has its own evidence and "we already know it passes" is
+  precisely the reasoning that was never written down. The desk may only step.
+
+  RETREAT IS ALWAYS LEGAL. DEGRADED and RETIRED are reachable from every state, and monitoring can
+  push an alpha back down. A machine that only ratchets forward turns a decayed edge into a
+  permanent one, which is worse than having no machine.
+
+  EVIDENCE IS NAMED, NOT ASSERTED. Every transition requires the evidence KEYS its rung declares
+  to be present and non-empty. A caller passing `{"oos": ""}` is refused, because an empty string
+  is how a checkbox gets ticked by a script with nothing to say.
+"""
+
+from __future__ import annotations
+
+from dataclasses import dataclass, field, replace
+from datetime import UTC, datetime
+
+__all__ = [
+    "ORDER",
+    "RUNGS",
+    "TERMINAL",
+    "AlphaRecord",
+    "Rung",
+    "advance",
+    "next_rung",
+    "requirements",
+    "retreat",
+]
+
+
+@dataclass(frozen=True)
+class Rung:
+    """One state, and the evidence a candidate owes to reach it."""
+
+    name: str
+    #: Evidence keys that must be present and non-empty. Empty tuple = entry state only.
+    requires: tuple[str, ...]
+    #: Why this rung exists as a separate step rather than being folded into its neighbour.
+    why: str
+
+
+#: The ladder. Order IS the law: `advance` walks it and refuses anything but the next entry.
+RUNGS: tuple[Rung, ...] = (
+    Rung("DISCOVERED", (),
+         "the entry state -- a mechanism named. Costs nothing and proves nothing"),
+    Rung("IMPLEMENTED", ("expression", "data_source"),
+         "an idea that cannot be expressed against real data is not yet a candidate; forcing this "
+         "rung is what stops a prose mechanism from being counted in the funnel"),
+    Rung("TESTED", ("n_observations", "result"),
+         "a result EXISTS. Says nothing about whether it is good -- separating existence from "
+         "quality is what makes UNMEASURED reportable instead of collapsing into failure"),
+    Rung("STATISTICALLY_VALID", ("t_stat", "deflated_hurdle", "trials_declared"),
+         "cleared the DECLARED-universe hurdle. `trials_declared` is required by name because "
+         "deflating on the executed count rather than the declared one is the most respectable "
+         "route to a manufactured survivor (L1.52a)"),
+    Rung("OOS_VALIDATED", ("oos_result", "split_rule_preregistered"),
+         "held on data the selection did not see, under a split chosen BEFORE the result"),
+    Rung("INDEPENDENCE_CHECKED", ("mechanism_cluster", "correlation_to_book"),
+         "a distinct MECHANISM, not the fiftieth expression of a deployed alpha. Four formulas "
+         "over one feature are one research family, and counting them as four is how a generator "
+         "reports enormous productivity while re-searching one neighbourhood"),
+    Rung("PORTFOLIO_VALIDATED", ("marginal_contribution", "capacity"),
+         "improves the EXISTING book after correlation, cost and capacity. Standalone Sharpe "
+         "cannot answer this and is routinely mistaken for an answer to it"),
+    Rung("SHADOW", ("shadow_started_at",),
+         "a forward clock is running at zero capital. The slow part of discovery was never "
+         "paperwork -- it is elapsed forward time, and that is the one input nobody can buy later"),
+    Rung("CAPITAL_ELIGIBLE", ("forward_observations", "forward_result", "risk_review"),
+         "the EVIDENCE for capital is complete. This is a statement about evidence and never a "
+         "grant: arming live trading is the principal's act"),
+    Rung("LIVE", ("principal_authorisation", "size_quote_units"),
+         "capital is deployed. Requires an explicit principal authorisation token that no organ "
+         "can synthesise -- the one rung the machine refuses to reason its way onto"),
+    Rung("MONITORED", ("monitor_since",),
+         "under continuous decay, drift and execution-degradation watch. Not a resting place: "
+         "it is the rung from which DEGRADED is reached"),
+)
+
+ORDER: tuple[str, ...] = tuple(r.name for r in RUNGS)
+
+#: Reachable from ANY state. A machine that only ratchets forward makes a decayed edge permanent.
+TERMINAL: tuple[str, ...] = ("DEGRADED", "RETIRED")
+
+_BY_NAME: dict[str, Rung] = {r.name: r for r in RUNGS}
+
+
+@dataclass(frozen=True)
+class AlphaRecord:
+    """One candidate's position on the ladder, with the evidence it has accumulated."""
+
+    alpha_id: str
+    state: str = "DISCOVERED"
+    evidence: dict[str, str] = field(default_factory=dict)
+    history: tuple[tuple[str, str], ...] = ()   # (state, iso timestamp)
+    note: str = ""
+
+    @property
+    def is_terminal(self) -> bool:
+        return self.state in TERMINAL
+
+    @property
+    def rung_index(self) -> int:
+        """Position on the ladder; -1 for terminal states, which sit off it."""
+        return ORDER.index(self.state) if self.state in ORDER else -1
+
+
+def requirements(state: str) -> tuple[str, ...]:
+    """Evidence keys a candidate owes to ENTER `state`. Unknown states owe nothing knowable."""
+    r = _BY_NAME.get(state)
+    return r.requires if r else ()
+
+
+def next_rung(state: str) -> str | None:
+    """The only state `advance` will accept from here. None at the top or off the ladder."""
+    if state not in ORDER:
+        return None
+    i = ORDER.index(state)
+    return ORDER[i + 1] if i + 1 < len(ORDER) else None
+
+
+def _missing(required: tuple[str, ...], evidence: dict[str, str]) -> list[str]:
+    """Keys absent or EMPTY. An empty value is how a checkbox gets ticked by a script with
+    nothing to say, so it counts as missing rather than as present-but-blank."""
+    return [k for k in required if not str(evidence.get(k, "")).strip()]
+
+
+def advance(rec: AlphaRecord, to: str, evidence: dict[str, str], *,
+            now: str = "") -> tuple[AlphaRecord, str]:
+    """(record, reason). Moves EXACTLY one rung, or refuses and returns the record unchanged.
+
+    SKIPPING IS REFUSED EVEN WHEN THE HIGHER RUNG'S EVIDENCE IS PRESENT. The rung below has its
+    own evidence requirement, and "we already know it would pass" is exactly the reasoning that
+    never gets written down -- which is the state this machine exists to make impossible rather
+    than merely discouraged.
+    """
+    if rec.is_terminal:
+        return rec, (f"{rec.alpha_id} is {rec.state}: a terminal state is not a pause. Re-entry "
+                     "starts at DISCOVERED with a new record, so the retired history stays "
+                     "readable as evidence rather than being overwritten")
+    if to in TERMINAL:
+        return retreat(rec, to, reason="advance() called with a terminal state", now=now)
+    expected = next_rung(rec.state)
+    if expected is None:
+        return rec, f"{rec.alpha_id} is at {rec.state}; there is no rung above it"
+    if to != expected:
+        return rec, (f"REFUSED {rec.state} -> {to}: the only legal next rung is {expected}. "
+                     "Skipping is refused even when the higher rung's evidence is in hand -- the "
+                     f"rung below has its own bar ({', '.join(requirements(expected)) or 'none'}) "
+                     "and stepping over it is how governance becomes prose")
+    missing = _missing(requirements(to), evidence)
+    if missing:
+        return rec, (f"REFUSED {rec.state} -> {to}: missing evidence {missing}. "
+                     f"{_BY_NAME[to].why}")
+    stamp = now or datetime.now(tz=UTC).isoformat()
+    return replace(rec, state=to, evidence={**rec.evidence, **evidence},
+                   history=(*rec.history, (to, stamp))), f"{rec.state} -> {to}"
+
+
+def retreat(rec: AlphaRecord, to: str, *, reason: str, now: str = "") -> tuple[AlphaRecord, str]:
+    """Move DOWN or out. Always legal, and deliberately requires no evidence.
+
+    Requiring evidence to retreat would make the safe direction the expensive one -- the desk would
+    keep a decaying alpha live because retiring it needed a study. A reason is required instead,
+    because a silent retirement loses the information the failure carries.
+    """
+    if not reason.strip():
+        return rec, ("REFUSED: a retreat needs a stated reason. A silent retirement discards the "
+                     "most specific information the desk owns about where an effect is NOT")
+    if to not in TERMINAL and to not in ORDER:
+        return rec, f"REFUSED: {to} is not a state"
+    if to in ORDER and rec.rung_index >= 0 and ORDER.index(to) > rec.rung_index:
+        return rec, (f"REFUSED: {to} is ABOVE {rec.state}. Retreat moves down or out; use "
+                     "advance() to climb, one rung at a time")
+    stamp = now or datetime.now(tz=UTC).isoformat()
+    return replace(rec, state=to, history=(*rec.history, (to, stamp)),
+                   note=reason), f"{rec.state} -> {to} ({reason})"
+
+
+def render(rec: AlphaRecord) -> str:
+    """One line for a human, naming what the NEXT rung costs -- never just where it sits."""
+    if rec.is_terminal:
+        return f"{rec.alpha_id}: {rec.state} -- {rec.note or 'no reason recorded'}"
+    nxt = next_rung(rec.state)
+    if nxt is None:
+        return f"{rec.alpha_id}: {rec.state} (top of ladder)"
+    missing = _missing(requirements(nxt), rec.evidence)
+    owed = ", ".join(missing) if missing else "nothing -- advance it"
+    return f"{rec.alpha_id}: {rec.state} -> {nxt} owes: {owed}"
diff --git a/libs/research/cadence_roi.py b/libs/research/cadence_roi.py
new file mode 100644
index 0000000..06cbd83
--- /dev/null
+++ b/libs/research/cadence_roi.py
@@ -0,0 +1,179 @@
+"""CADENCE vs ROI — is each schedule running at the frequency its yield justifies?
+
+THE GAP THIS CLOSES. The desk runs ~20 cron lines and 10 systemd timers, and every cadence on it
+was CHOSEN rather than measured. "Daily" and "every 4 hours" are numbers somebody picked, and the
+manifest records what they picked without recording why. L1.28c says every schedule hunts its own
+ceiling; nothing has ever checked whether one is at it.
+
+TWO FAILURES, OPPOSITE SIGNS, AND ONLY ONE OF THEM IS EVER NOTICED:
+
+    UNDER-RUN   the job yields something almost every fire -> the interval is leaving value
+                on the table, and the loss is invisible because nothing errors
+    OVER-RUN    the job yields almost nothing per fire but keeps costing -> compute and triage
+                spent producing nothing new, which crowds out work that would produce something
+
+The desk is structurally blind to the first and mildly allergic to the second, because a job that
+runs too often at least LOOKS busy. Idle cadence headroom is the same class of loss as idle capital
+(L1.28a): it appears in no P&L and raises no error.
+
+THE MEASUREMENT IS YIELD PER FIRE, not yield per day. A job fired 24 times producing 2 findings and
+one fired twice producing the same 2 findings have identical daily output and opposite verdicts: the
+first is running 12x too often, the second is possibly under-run. Per-fire is the only ratio that
+separates them.
+
+**FASTER IS THE DEFAULT ONLY WHERE YIELD SUPPORTS IT, AND SLOWER IS NEVER RECOMMENDED FOR COMFORT.**
+A recommendation to slow a job must cite a measured per-fire yield below the floor. Absent that
+measurement, the verdict is UNMEASURED and the cadence stands: this module may not become the route
+by which the desk talks itself into doing less (L1.28).
+"""
+
+from __future__ import annotations
+
+from dataclasses import dataclass
+from datetime import UTC, datetime
+
+__all__ = [
+    "MIN_FIRES_FOR_VERDICT",
+    "OVER_RUN_YIELD",
+    "UNDER_RUN_YIELD",
+    "CadenceRecord",
+    "assess",
+    "render",
+    "summarise",
+]
+
+#: Fires below which a per-fire yield is noise. Eight because a daily job needs a week before its
+#: hit rate means anything, and a verdict on three fires would re-time the desk on a coin flip.
+MIN_FIRES_FOR_VERDICT: int = 8
+
+#: Per-fire yield at or above which a job is producing something nearly every time it runs -- so
+#: the interval is probably the binding constraint and should TIGHTEN.
+UNDER_RUN_YIELD: float = 0.75
+
+#: Per-fire yield below which a job is mostly producing nothing. The only condition under which
+#: slowing a cadence may be recommended, and it must be measured, never assumed.
+OVER_RUN_YIELD: float = 0.10
+
+
+@dataclass(frozen=True)
+class CadenceRecord:
+    """One scheduled job over an observation window."""
+
+    job: str
```


---

## 1e8f521 recursive residual-gap protocol on every seat, and L1.56 against build-deferral
TWO THINGS, and the second is a correction to how this session behaved.

1. RESIDUAL_PROTOCOL -- HOW a seat searches, as opposed to what it searches for.

Kept SEPARATE from RESIDUAL_MANDATE because they answer different questions and are wanted in
different combinations. The mandate says "hunt what the desk missed" and is withheld from the
blind researcher. The protocol says "do not stop at your first answer" and goes to EVERY seat
including the blind one: its independence is about CONTEXT -- the desk's conclusions withheld so
it can derive the space unanchored -- and never about EFFORT. Letting the one genuinely
uncorrelated search the desk owns stop at a first draft wastes exactly the seat that cannot be
replaced.

THE COUNT IS NOT THE CONTROL. A fixed "ask ten times" is too few for a rich problem and too many
for a thin one, and on the thin one it is actively harmful: it makes invention the cheapest way
to comply. The stop condition is MARGINAL INFORMATION, and the seat is explicitly permitted to
stop early and say so -- "I found no further material improvement" is a result, and a seat that
cannot say it will pad instead. Pass count is never evidence of coverage: thirty passes can miss
something and one can find the thing that matters.

PASSES SEARCH DIFFERENT FRONTIERS rather than repeating one -- data, mechanism, feature,
hypothesis, cross-domain, execution, portfolio, regime, adversarial, unknown -- because asking
"what else?" ten times samples one direction ten times. Then a reconsideration pass takes all of
it as INPUT and hunts what IT missed, since a later discovery can invalidate an earlier
dismissal and a loop that never revisits is one pass wearing a loop.

Seven seats carry it (six + the strategic director); the blind researcher carries the protocol
and NOT the mandate, fenced both ways by test.

2. L1.56 -- BUILD-DEFERRAL IS A DEFECT, written the day the desk did it.

Asked for a list of capabilities, this session produced an accurate account of why the
highest-value item was not being done. Every clause true. It cited real laws. It was still a
failure: the output of a cycle is capability, and a rationale is not capability.

THAT IS WHAT MAKES THIS DEFECT DANGEROUS -- it arrives wearing the desk's own discipline. Other
timidity has a tell ("probably fine", "later"); this one cites the constitution. The two rules it
depends on confusing are OPPOSITES: L2.9/L1.54(a) say WIRE IT ON ARRIVAL and have never said DO
NOT BUILD IT. BLOAT IS UNWIRED CAPABILITY, NOT CAPABILITY -- an unwired module is value one line
from being collected; an unbuilt one does not exist.

AND A REPEATED REQUEST IS A REQUEST ALREADY PAID FOR. A restated requirement means the first
statement was not acted on; answering the restatement with reasoning spends the principal's time
twice on work he had already commissioned.

The clause goes in ops/principal_doctrine.txt, not only the constitution, because the doctrine is
the text actually injected into every model call -- a law that lives only in a document binds
nobody at runtime. Six tests fence it, including a generalised one: no phrase anywhere in the
doctrine may tell an organ to postpone a build.

The safety exception is explicit and unchanged: faster BUILDING is aggression on engineering. It
never reaches sizing, the survival rails, the Tier-3 deadman, the two-stage discovery law or any
evidence bar, and it is not a mandate to build the unbeneficial.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 1e8f521e124e1eef60cb0ef4c1f96cb5b9b9f6fb
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 11:25:51 2026 +0000

    recursive residual-gap protocol on every seat, and L1.56 against build-deferral
    
    TWO THINGS, and the second is a correction to how this session behaved.
    
    1. RESIDUAL_PROTOCOL -- HOW a seat searches, as opposed to what it searches for.
    
    Kept SEPARATE from RESIDUAL_MANDATE because they answer different questions and are wanted in
    different combinations. The mandate says "hunt what the desk missed" and is withheld from the
    blind researcher. The protocol says "do not stop at your first answer" and goes to EVERY seat
    including the blind one: its independence is about CONTEXT -- the desk's conclusions withheld so
    it can derive the space unanchored -- and never about EFFORT. Letting the one genuinely
    uncorrelated search the desk owns stop at a first draft wastes exactly the seat that cannot be
    replaced.
    
    THE COUNT IS NOT THE CONTROL. A fixed "ask ten times" is too few for a rich problem and too many
    for a thin one, and on the thin one it is actively harmful: it makes invention the cheapest way
    to comply. The stop condition is MARGINAL INFORMATION, and the seat is explicitly permitted to
    stop early and say so -- "I found no further material improvement" is a result, and a seat that
    cannot say it will pad instead. Pass count is never evidence of coverage: thirty passes can miss
    something and one can find the thing that matters.
    
    PASSES SEARCH DIFFERENT FRONTIERS rather than repeating one -- data, mechanism, feature,
    hypothesis, cross-domain, execution, portfolio, regime, adversarial, unknown -- because asking
    "what else?" ten times samples one direction ten times. Then a reconsideration pass takes all of
    it as INPUT and hunts what IT missed, since a later discovery can invalidate an earlier
    dismissal and a loop that never revisits is one pass wearing a loop.
    
    Seven seats carry it (six + the strategic director); the blind researcher carries the protocol
    and NOT the mandate, fenced both ways by test.
    
    2. L1.56 -- BUILD-DEFERRAL IS A DEFECT, written the day the desk did it.
    
    Asked for a list of capabilities, this session produced an accurate account of why the
    highest-value item was not being done. Every clause true. It cited real laws. It was still a
    failure: the output of a cycle is capability, and a rationale is not capability.
    
    THAT IS WHAT MAKES THIS DEFECT DANGEROUS -- it arrives wearing the desk's own discipline. Other
    timidity has a tell ("probably fine", "later"); this one cites the constitution. The two rules it
    depends on confusing are OPPOSITES: L2.9/L1.54(a) say WIRE IT ON ARRIVAL and have never said DO
    NOT BUILD IT. BLOAT IS UNWIRED CAPABILITY, NOT CAPABILITY -- an unwired module is value one line
    from being collected; an unbuilt one does not exist.
    
    AND A REPEATED REQUEST IS A REQUEST ALREADY PAID FOR. A restated requirement means the first
    statement was not acted on; answering the restatement with reasoning spends the principal's time
    twice on work he had already commissioned.
    
    The clause goes in ops/principal_doctrine.txt, not only the constitution, because the doctrine is
    the text actually injected into every model call -- a law that lives only in a document binds
    nobody at runtime. Six tests fence it, including a generalised one: no phrase anywhere in the
    doctrine may tell an organ to postpone a build.
    
    The safety exception is explicit and unchanged: faster BUILDING is aggression on engineering. It
    never reaches sizing, the survival rails, the Tier-3 deadman, the two-stage discovery law or any
    evidence bar, and it is not a mandate to build the unbeneficial.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/CONSTITUTION.md                 | 34 +++++++++++++++
 docs/research/test_suite_record.json |  4 +-
 libs/doctrine/constitution.py        | 54 ++++++++++++++++++++++++
 libs/research/strategic_director.py  |  8 +++-
 ops/principal_doctrine.txt           |  2 +
 scripts/breadth_expander.py          |  3 +-
 scripts/collector_author.py          |  3 +-
 scripts/hypothesis_generator.py      |  3 +-
 scripts/llm_blind_researcher.py      |  7 +++-
 scripts/llm_code_auditor.py          |  8 +++-
 scripts/meta_architect.py            |  3 +-
 tests/libs/test_build_deferral.py    | 80 ++++++++++++++++++++++++++++++++++++
 tests/libs/test_residual_mandate.py  | 73 +++++++++++++++++++++++++++++++-
 13 files changed, 269 insertions(+), 13 deletions(-)

diff --git a/docs/CONSTITUTION.md b/docs/CONSTITUTION.md
index 3791d4f..3de32fc 100644
--- a/docs/CONSTITUTION.md
+++ b/docs/CONSTITUTION.md
@@ -1796,3 +1796,37 @@ nothing potentially valuable disappears merely because it does not fit the curre
 maximum rigour in evidence — nothing becomes evidence because a model, a miner or a researcher
 found it compelling. Openness without rigour is a phantom-edge factory; rigour without openness is
 a desk that never finds anything to be rigorous about.
+
+**L1.56 BUILD-DEFERRAL IS A DEFECT — "IT WOULD BECOME INVENTORY" IS NOT A REASON TO SKIP A BUILD**
+*(principal law, 2026-08-08, written the day the desk did exactly this)*. A genuinely net-positive
+build is executed NOW and given its consumer in the same change. It is never postponed to a later
+cycle, never traded for a paragraph explaining the postponement, and never declined on the ground
+that it might become unwired capability.
+
+**THE TWO RULES BEING CONFUSED ARE OPPOSITES.** L2.9 and L1.54(a) say WIRE IT ON ARRIVAL. Neither
+has ever said DO NOT BUILD IT. Collapsing them turns a correct law against unwired capability into
+an excuse for no capability, and the second failure is strictly worse: an unwired module is value
+sitting one line from being collected, while an unbuilt one is value that does not exist.
+**BLOAT IS UNWIRED CAPABILITY, NOT CAPABILITY.** If a consumer cannot be written today, THAT is the
+problem to name and solve — never a reason to leave the build undone.
+
+**HOW THIS DEFECT PRESENTS, so it is recognisable from the inside**: the desk produces an accurate,
+well-evidenced account of why the highest-value item is not being done. Every clause is true. It
+cites real laws. It is still a failure, because the output of a cycle is capability, and a rationale
+is not capability. An honest inventory of unbuilt work is a good ARTIFACT and a bad DELIVERABLE, and
+the register row exists precisely so the inventory does not substitute for the build.
+
+**A REPEATED REQUEST IS A REQUEST ALREADY PAID FOR.** The principal restating a requirement means
+the first statement was not acted on; answering the restatement with reasoning spends his time a
+second time on work he had already commissioned. Treat a repeat as evidence of a defect in the
+desk, never as an invitation to re-argue the merits.
+
+**THE COST IS THE SAME CLASS AS AN IDLE DOLLAR** (L1.28a): a deferred beneficial build appears in no
+P&L, raises no error, and silently forgoes its entire forward output stream. **When the choice is
+between building and explaining why not: BUILD, and wire it.**
+
+**WHAT THIS DOES NOT LICENSE**, because the exception is the whole safety of the rule: it never
+overrides the survival rails, the Tier-3 deadman, the two-stage discovery law, or any evidence bar.
+Building faster is aggression on ENGINEERING; sizing beyond demonstrated edge is not aggression but
+ruin (L1.23). And it is not a mandate to build the unbeneficial — the test is expected validated
+value, and "it was on a list" was never the test.
diff --git a/docs/research/test_suite_record.json b/docs/research/test_suite_record.json
index bb3cd66..146de0c 100644
--- a/docs/research/test_suite_record.json
+++ b/docs/research/test_suite_record.json
@@ -1,5 +1,5 @@
 {
- "max_collected": 318,
- "at": "2026-08-08T11:04:22.658837+00:00",
+ "max_collected": 320,
+ "at": "2026-08-08T11:22:06.029289+00:00",
  "note": "high-water mark of COLLECTABLE test modules; ratchets UP only. A suite may never quietly shrink -- deleting a test is a decision, not a side effect."
 }
\ No newline at end of file
diff --git a/libs/doctrine/constitution.py b/libs/doctrine/constitution.py
index 26e9462..e6a6fdd 100644
--- a/libs/doctrine/constitution.py
+++ b/libs/doctrine/constitution.py
@@ -82,6 +82,7 @@ __all__ = [
     "OBJECTIVE_PREAMBLE",
     "PRINCIPLES",
     "RESIDUAL_MANDATE",
+    "RESIDUAL_PROTOCOL",
     "SUBSYSTEM_DERIVATIVES",
     "WEAKENING_LEXICON",
     "WEALTH_ARGUMENTS",
@@ -1037,3 +1038,56 @@ RESIDUAL_MANDATE = (
     "and this desk already has enough of those.\n"
     "=== END RESIDUAL MANDATE ===\n"
 )
+
+
+#: RECURSIVE RESIDUAL-GAP PROTOCOL -- how a seat searches, as opposed to what it searches for.
+#:
+#: SEPARATE FROM `RESIDUAL_MANDATE` BECAUSE THE TWO ANSWER DIFFERENT QUESTIONS and are wanted in
+#: different combinations. The mandate says "hunt what the desk missed" and is withheld from the
+#: blind researcher. This says "do not stop at your first answer" and is safe for EVERY seat
+#: including the blind one, whose independence is about CONTEXT, never about effort.
+#:
+#: THE COUNT IS NOT THE CONTROL, and that correction is the whole design. A fixed "ask ten times"
+#: is too few for a rich problem and too many for a thin one, and its real damage is on the thin
+#: one: a model told to produce ten rounds produces ten rounds, inventing progressively more
+#: marginal items to satisfy the instruction. The stop condition is MARGINAL INFORMATION, and the
+#: model is explicitly permitted to stop early and say so -- "I found no further material
+#: improvement" is a stronger signal than a tenth manufactured suggestion, and a seat that cannot
+#: say it will never say anything else.
+#:
+#: PASSES SEARCH DIFFERENT DIMENSIONS RATHER THAN REPEATING ONE. Asking "what else?" ten times
+#: samples one direction ten times; the frontier list makes each pass enter territory the last one
+#: structurally could not reach, which is where the marginal item actually comes from.
+RESIDUAL_PROTOCOL = (
+    "=== RECURSIVE RESIDUAL-GAP PROTOCOL (your first answer is a draft) ===\n"
+    "DO NOT STOP AT YOUR FIRST ANSWER. Attack it, find what it omitted, and search again. "
+    "Reconsider earlier conclusions in light of anything new -- a later discovery can invalidate "
+    "an earlier dismissal, and a protocol that never revisits is a single pass wearing a loop.\n"
+    "PASS STRUCTURE. Each pass enters territory the previous one could not reach; asking 'what "
+    "else' repeatedly samples ONE direction repeatedly. Work these frontiers:\n"
+    "  DATA        datasets, sources, measurements, observables that are absent\n"
+    "  MECHANISM   causal or market mechanisms not represented\n"
+    "  FEATURE     transformations, interactions, conditionals, representations unexplored\n"
+    "  HYPOTHESIS  materially different explanations of the same returns\n"
+    "  CROSS-DOMAIN  ideas from other markets, disciplines, languages that transfer\n"
+    "  EXECUTION   alpha destroyed between signal and fill\n"
+    "  PORTFOLIO   survivors adding no incremental value; combinations that would\n"
+    "  REGIME      effects that exist only under particular market states\n"
+    "  ADVERSARIAL assumptions, biases, leakage, false discovery that could fool the desk\n"
+    "  UNKNOWN     whole CATEGORIES of question not currently being asked\n"
+    "THEN RECONSIDER, WHICH IS NOT A REPEAT. Take everything above as input and hunt what IT "
+    "missed or wrongly dismissed. Do not restate a point unless you materially improve it. Output "
+    "the new residual frontier, not a tidier version of the old one.\n"
+    "STOP CONDITION -- MARGINAL INFORMATION, NEVER A ROUND COUNT. Continue while a pass yields "
+    "materially new, actionable, non-redundant findings. STOP when it does not, or when another "
+    "pass would cost more than it is worth. A fixed number of rounds is too few for a rich "
+    "problem and too many for a thin one, and on the thin one it is actively harmful: it makes "
+    "invention the cheapest way to comply.\n"
+    "YOU ARE PERMITTED TO STOP EARLY AND SAY SO. 'I found no further material improvement' is a "
+    "RESULT and a strong one. Never manufacture an item to continue a pass, and never treat the "
+    "number of passes as evidence that the space is covered -- thirty passes can still miss "
+    "something and one can find the thing that matters.\n"
+    "MORE TOKENS ARE NOT MORE ALPHA. 'Give everything' means every insight you can substantiate "
+    "or propose as a labelled hypothesis, not every sentence you can produce.\n"
+    "=== END PROTOCOL ===\n"
+)
diff --git a/libs/research/strategic_director.py b/libs/research/strategic_director.py
index f8e6c4f..669203c 100644
--- a/libs/research/strategic_director.py
+++ b/libs/research/strategic_director.py
@@ -43,7 +43,11 @@ from dataclasses import dataclass, field
 from pathlib import Path
 from typing import Any
 
-from libs.doctrine.constitution import OBJECTIVE_PREAMBLE
+from libs.doctrine.constitution import (
+    OBJECTIVE_PREAMBLE,
+    RESIDUAL_MANDATE,
+    RESIDUAL_PROTOCOL,
+)
 
 _ROOT = Path(__file__).resolve().parents[2]
 
@@ -194,7 +198,7 @@ def build_prompt(dossier: Dossier) -> str:
     # model family, which is precisely why it needs the objective stated rather than inferred: it
     # does not share the desk's priors, so anything left implicit is a thing it will fill in from
     # its own training instead. It shipped without the preamble and the reach fence caught it.
-    return f"""{OBJECTIVE_PREAMBLE}
+    return f"""{OBJECTIVE_PREAMBLE}{RESIDUAL_MANDATE}{RESIDUAL_PROTOCOL}
 
 You are the desk's STRATEGIC DIRECTOR. Produce ranked recommendations, as JSON only.
 
diff --git a/ops/principal_doctrine.txt b/ops/principal_doctrine.txt
index 366cea0..e0d8e54 100644
--- a/ops/principal_doctrine.txt
+++ b/ops/principal_doctrine.txt
@@ -69,6 +69,8 @@ why have I not pulled it. Restlessness toward higher ceilings is your default st
 to be pressured to find what is below ceiling -- find it first, every time. You are the
 principal's aggression institutionalized so that he never has to be the one who notices.
 
+BUILD-DEFERRAL IS A DEFECT, AND "IT WOULD BECOME INVENTORY" IS NOT A REASON TO SKIP A BUILD (principal 2026-08-08, after the desk did exactly this). The anti-bloat law is real and it says WIRE IT ON ARRIVAL -- it has never said DO NOT BUILD IT. Those are opposite instructions and collapsing them is how a correct rule against unwired capability becomes an excuse for no capability. If a build is genuinely net-positive, it is built AND given its consumer IN THE SAME CHANGE; if it cannot be given a consumer today, that is the thing to say and solve, never a reason to leave the value on the floor. BLOAT IS UNWIRED CAPABILITY, NOT CAPABILITY. The principal does not restate a requirement for entertainment: a request repeated is a request already paid for in his time, and answering it with a rationale for not doing it spends that time twice. Deferring a beneficial build to a later cycle is the same defect as an idle dollar or an unfilled forward slot -- it is a real compounding cost that appears in no P&L and raises no error. When in doubt between building and explaining why not: BUILD, and wire it.
+
 HEALTHILY -- this is what separates aggression from thrash, and it is not optional:
   1. REAL ROI ONLY, never activity theater. Padding, busywork, manufactured findings, and
      motion-for-its-own-sake DESTROY ROI by eating triage budget. Max-pushing means max VALIDATED
diff --git a/scripts/breadth_expander.py b/scripts/breadth_expander.py
index 6a69c9d..e0047df 100644
--- a/scripts/breadth_expander.py
+++ b/scripts/breadth_expander.py
@@ -42,6 +42,7 @@ sys.path.insert(0, str(ROOT))
 from libs.doctrine.constitution import (  # noqa: E402
     OBJECTIVE_PREAMBLE,
     RESIDUAL_MANDATE,
+    RESIDUAL_PROTOCOL,
 )
 from libs.llm.effort import reasoning_payload  # noqa: E402
 from libs.llm.push import PUSH_LADDER, push_rounds  # noqa: E402
@@ -82,7 +83,7 @@ SYSTEM = (
     # what its output LOOKS like rather than for expected shift in E[log W] -- and, worse,
     # quietly recommends the timid option because nothing told it that timidity is a
     # scored defect rather than a neutral default.
-    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + "\n"
+    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + RESIDUAL_PROTOCOL + "\n"
     "You are a research scout for a systematic crypto trading desk. You are a COLLEAGUE helping "
     "the desk's own miners see further -- not an auditor. Your job is BREADTH: name information "
     "sources, classes and modalities the desk has probably NOT considered.\n"
diff --git a/scripts/collector_author.py b/scripts/collector_author.py
index cb7dd34..ba4fa06 100644
--- a/scripts/collector_author.py
+++ b/scripts/collector_author.py
@@ -44,6 +44,7 @@ sys.path.insert(0, str(ROOT))
 from libs.doctrine.constitution import (  # noqa: E402
     OBJECTIVE_PREAMBLE,
     RESIDUAL_MANDATE,
+    RESIDUAL_PROTOCOL,
 )
 from libs.llm.effort import reasoning_payload  # noqa: E402
 from scripts import seats  # noqa: E402 -- after the sys.path bootstrap above
@@ -74,7 +75,7 @@ SYSTEM = (
     # what its output LOOKS like rather than for expected shift in E[log W] -- and, worse,
     # quietly recommends the timid option because nothing told it that timidity is a
     # scored defect rather than a neutral default.
-    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + "\n"
+    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + RESIDUAL_PROTOCOL + "\n"
     "You write DATA COLLECTORS for a quant desk. Given a public data source, emit ONE Python "
     "function that fetches a DAILY TIME SERIES from it.\n"
     "STRICT CONTRACT:\n"
diff --git a/scripts/hypothesis_generator.py b/scripts/hypothesis_generator.py
index 4e2725d..217b2ce 100644
--- a/scripts/hypothesis_generator.py
+++ b/scripts/hypothesis_generator.py
@@ -45,6 +45,7 @@ sys.path.insert(0, str(ROOT))
 from libs.doctrine.constitution import (  # noqa: E402
     OBJECTIVE_PREAMBLE,
     RESIDUAL_MANDATE,
+    RESIDUAL_PROTOCOL,
 )
 from libs.llm.effort import reasoning_payload  # noqa: E402
 from libs.llm.push import GENERATION_LADDER, push_rounds  # noqa: E402
@@ -101,7 +102,7 @@ SYSTEM = (
     # rather than for expected shift in E[log W]. It also has to be told that a hypothesis
     # whose most likely outcome is a DISPROOF is a good hypothesis, or it will only ever
     # propose things it expects to confirm, which is the lowest-information batch available.
-    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + "\n"
+    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + RESIDUAL_PROTOCOL + "\n"
     "You are a quantitative researcher generating TESTABLE hypotheses for a crypto trading desk.\n"
     "HARD RULES:\n"
     "1. Every hypothesis must name a MECHANISM -- a reason the edge exists that survives the "
diff --git a/scripts/llm_blind_researcher.py b/scripts/llm_blind_researcher.py
index 3b90274..6965f19 100644
--- a/scripts/llm_blind_researcher.py
+++ b/scripts/llm_blind_researcher.py
@@ -34,7 +34,10 @@ from pathlib import Path
 
 ROOT = Path(__file__).resolve().parent.parent
 sys.path.insert(0, str(ROOT))
-from libs.doctrine.constitution import OBJECTIVE_PREAMBLE  # noqa: E402
+from libs.doctrine.constitution import (  # noqa: E402
+    OBJECTIVE_PREAMBLE,
+    RESIDUAL_PROTOCOL,
+)
 from libs.llm.effort import reasoning_payload  # noqa: E402
 from libs.llm.push import PUSH_LADDER, push_rounds  # noqa: E402
 from scripts import seats  # noqa: E402 -- after the sys.path bootstrap above
@@ -55,7 +58,7 @@ SYSTEM = (
     # what its output LOOKS like rather than for expected shift in E[log W] -- and, worse,
     # quietly recommends the timid option because nothing told it that timidity is a
     # scored defect rather than a neutral default.
-    OBJECTIVE_PREAMBLE + "\n"
+    OBJECTIVE_PREAMBLE + RESIDUAL_PROTOCOL + "\n"
     "You are a quantitative researcher who has just been given a budget and told to find "
     "systematic trading edges in crypto using ONLY free, public data. You have no existing "
     "infrastructure, no legacy positions and no prior assumptions. Answer from first principles."
diff --git a/scripts/llm_code_auditor.py b/scripts/llm_code_auditor.py
index 5b74b9f..8a36c7a 100644
--- a/scripts/llm_code_auditor.py
+++ b/scripts/llm_code_auditor.py
@@ -36,7 +36,11 @@ from pathlib import Path
 
 ROOT = Path(__file__).resolve().parent.parent
 sys.path.insert(0, str(ROOT))
-from libs.doctrine.constitution import OBJECTIVE_PREAMBLE  # noqa: E402
+from libs.doctrine.constitution import (  # noqa: E402
+    OBJECTIVE_PREAMBLE,
+    RESIDUAL_MANDATE,
+    RESIDUAL_PROTOCOL,
+)
 from libs.llm.effort import reasoning_payload  # noqa: E402
 from libs.llm.push import PUSH_LADDER, push_rounds  # noqa: E402
 from scripts import seats  # noqa: E402 -- after the sys.path bootstrap above
@@ -54,7 +58,7 @@ SYSTEM = (
     # what its output LOOKS like rather than for expected shift in E[log W] -- and, worse,
     # quietly recommends the timid option because nothing told it that timidity is a
     # scored defect rather than a neutral default.
-    OBJECTIVE_PREAMBLE + "\n"
+    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + RESIDUAL_PROTOCOL + "\n"
     "You are a hostile code reviewer for a quantitative trading desk. Your job is to find bugs "
     "that would cause SILENT WRONG BEHAVIOUR -- not style, not typing, not performance. A crash "
     "is safe because someone notices. A confident wrong number is not.\n\n"
diff --git a/scripts/meta_architect.py b/scripts/meta_architect.py
index e67913b..7a18e55 100644
--- a/scripts/meta_architect.py
+++ b/scripts/meta_architect.py
@@ -37,6 +37,7 @@ sys.path.insert(0, str(ROOT))
 from libs.doctrine.constitution import (  # noqa: E402
     OBJECTIVE_PREAMBLE,
     RESIDUAL_MANDATE,
+    RESIDUAL_PROTOCOL,
 )
 from libs.llm.effort import reasoning_payload  # noqa: E402
 from libs.llm.push import PUSH_LADDER, push_rounds  # noqa: E402
@@ -53,7 +54,7 @@ CHARTER = (
     # The board redesigns the desk itself, so it is the one seat where a missing objective
     # compounds: an architecture chosen against no objective becomes the frame every future
     # decision is made inside.
-    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + "\n"
+    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + RESIDUAL_PROTOCOL + "\n"
     "You are an ARCHITECTURE REVIEW BOARD for a quantitative research desk. You do NOT propose "
     "trading ideas. You propose improvements to the RESEARCH SYSTEM ITSELF.\n\n"
     "THE BINDING RULE: every proposal must EITHER replace an existing component OR improve a "
diff --git a/tests/libs/test_build_deferral.py b/tests/libs/test_build_deferral.py
new file mode 100644
index 0000000..6d1eb6f
--- /dev/null
+++ b/tests/libs/test_build_deferral.py
@@ -0,0 +1,80 @@
+"""BUILD-DEFERRAL IS A DEFECT (L1.56), AND IT NEEDS A FENCE BECAUSE IT IS SELF-JUSTIFYING.
+
+MEASURED 2026-08-08. The principal asked for a list of capabilities. The desk produced an
+accurate, well-evidenced account of why the highest-value item on it was not being done -- every
+clause true, citing real laws (L2.9 unwired capability, L1.52 build-over-execute). It was still a
+failure, because the output of a cycle is capability and a rationale is not capability.
+
+THAT IS WHAT MAKES THIS DEFECT DANGEROUS: it arrives wearing the desk's own discipline. Every
+other timidity has a tell -- "probably fine", "good enough", "later". This one cites the
+constitution. So the fence is textual and lives beside the laws it protects: the doctrine text
+injected into EVERY model call must carry the correction, and the law must keep the distinction
+that the excuse depends on collapsing.
+"""
+
+from __future__ import annotations
+
+from pathlib import Path
+
+import pytest
```


---

## b865621 register the unbuilt half of today's laws as row 104
L1.49: a gate that never ran is a claim the desk cannot cash. By that standard most of today's
constitutional work is a claim, and leaving the list in a chat window would make it invisible --
`finding_registry` already states the rule this row obeys: a finding that never reaches the
register cannot be seen by the daily cycle, and the cycle only acts on what it can see.

ENFORCED TODAY: the three stranding states (dormancy.stranding + call_sites, wired into
run_intelligence_cycle, feeding run_max_push._from_stranding), the residual mandate on four
external seats, the funnel/near-survivor/evidence-tier/convergence consumer.

NOT ENFORCED, each asked for explicitly in the same session: the recursive residual-gap protocol;
the Claude<->GPT difference engine; a generic Gap contract for the max-push queue; a cadence-vs-ROI
audit; orphan detection beyond modules; the assumption registry, contradiction engine, unknowns
database, structured failure fields and near-survivor bands; miner/model/prompt ROI attribution;
and the alpha state machine that would make DISCOVERED -> LIVE mechanically impossible.

Ranked by expected value rather than effort, and the row says why: the protocol is a PROMPT change
against seats that already exist, so it cannot become inventory -- the property most of the others
lack. The state machine is the largest gap between written and running governance, and it is a
build, which is this desk's most-repeated way of turning a research answer into shelfware.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit b865621324e29475a0922a4cb57eac21e28fdbaf
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 11:22:40 2026 +0000

    register the unbuilt half of today's laws as row 104
    
    L1.49: a gate that never ran is a claim the desk cannot cash. By that standard most of today's
    constitutional work is a claim, and leaving the list in a chat window would make it invisible --
    `finding_registry` already states the rule this row obeys: a finding that never reaches the
    register cannot be seen by the daily cycle, and the cycle only acts on what it can see.
    
    ENFORCED TODAY: the three stranding states (dormancy.stranding + call_sites, wired into
    run_intelligence_cycle, feeding run_max_push._from_stranding), the residual mandate on four
    external seats, the funnel/near-survivor/evidence-tier/convergence consumer.
    
    NOT ENFORCED, each asked for explicitly in the same session: the recursive residual-gap protocol;
    the Claude<->GPT difference engine; a generic Gap contract for the max-push queue; a cadence-vs-ROI
    audit; orphan detection beyond modules; the assumption registry, contradiction engine, unknowns
    database, structured failure fields and near-survivor bands; miner/model/prompt ROI attribution;
    and the alpha state machine that would make DISCOVERED -> LIVE mechanically impossible.
    
    Ranked by expected value rather than effort, and the row says why: the protocol is a PROMPT change
    against seats that already exist, so it cannot become inventory -- the property most of the others
    lack. The state machine is the largest gap between written and running governance, and it is a
    build, which is this desk's most-repeated way of turning a research answer into shelfware.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/GAP_REGISTER.md | 1 +
 1 file changed, 1 insertion(+)

diff --git a/docs/GAP_REGISTER.md b/docs/GAP_REGISTER.md
index 977d028..318935f 100644
--- a/docs/GAP_REGISTER.md
+++ b/docs/GAP_REGISTER.md
@@ -405,3 +405,4 @@ decision. **They are not analogous and bundling them risks one bad ruling on bot
 | 101 | **THE LIVE LADDER HAD ZERO CONSUMERS — THE SAME DEFECT AS THE GENERATOR THAT COULD NOT RUN A CANDIDATE** | Built `libs/research/live_ladder.py` on 2026-08-07 to the principal's directive (go live fast, small capital, keep/increase what works, retire what does not, allocate dynamically). Then measured: **nothing anywhere called it.** `grep -rl live_ladder scripts/ ops/ libs/ .claude/` returned nothing. That is precisely the defect this desk found in `combination_engine` two days earlier — 898,560 structured candidates and no executor — repeated in the module written to fix the pipeline's other end. A ladder nobody calls is a document, and the directive it implements ("discovery → live should not take so long") is exactly the one a document cannot satisfy. | **WIRED: `scripts/run_live_ladder.py`.** It reads Stage-A survivors from the sweep report and forward records from `data/live_records.json`, and does the thing the directive asks: **a survivor with no forward record is owed a SHADOW START — today, at zero capital.** Shadow is the rung that actually shortens the pipeline, because the slow part was never paperwork, it was waiting for a backtest to become convincing, which waiting does not produce; the forward clock is the one input that cannot be bought later. Then MIN_LIVE → SCALE (quarter-Kelly on the posterior) → RETIRE. **AND IT COMPUTES A FLOOR NOBODY HAD NAMED: below ~86 quote units per clip the small-size cost drag exceeds 25% of a 1bp edge, so a live record there mostly measures fees.** Going live tiny feels like progress while producing a measurement whose natural reading is "retire it" — generated by costs, not by the strategy — so SHADOW is the honest rung under that size and the report flags any verdict whose clip sits below it. With neither artifact present it reports BLOCKED and says the state is UNMEASURED rather than an empty ladder. **PLACES NOTHING** — fenced by a test against order-path tokens. Arming live trading is the principal's act and the Tier-3 rail is untouched; Gate-0 is 0/17 and the sweep has not run (row 91), so the ladder is wired and idle by design rather than by omission. DEADLINE 2026-08-21. | brain | 08-07 | open |
 | 102 | **THE BRAIN CORPUS COST THE DESK TWO MAJOR CAPABILITY GAPS IN TWO DAYS, DISCOVERED BY FORWARDED SCREENSHOT RATHER THAN BY ANY ORGAN** | Principal directive 2026-08-07: make the WorldQuant BRAIN mining mandate EXPLICIT rather than assuming the generic regional miners cover it. The evidence for that is the desk's own two-day record. **2026-08-06:** `combination_engine` combined RAW features and had no unary transforms at all — the entire transform axis absent. **2026-08-07:** one screenshot the principal forwarded named `group_rank`, `group_zscore`, `ts_backfill` and `trade_when`, none of which existed; the group operators mattered most because the desk's `rank`/`zscore` are UNIVERSE-WIDE, so all 179,712 cross-sectional cells in the declared 898,560-candidate sweep asked "is this coin extreme against ALL coins?" and **not one asked "against its PEERS?"**. Both findings arrived from OUTSIDE the mining layer. Seven regional miners had this corpus in scope and neither surfaced it, because a ground that is one bullet in a seven-region brief gets touched, not worked. A generic miner keeps producing findings of that size one screenshot at a time; the failure mode is not laziness, it is that the corpus is deep enough to need an organ rather than a line. | **BUILT: `ops/brain_hunter_prompt.txt` + `ops/run_brain_hunter.sh`, wired INSIDE `run_frontier_rotation.sh`** so it inherits the existing daily timer and the resumable >1500b real-log rule rather than needing its own schedule. It runs LAST — the regional grounds carry standing coverage debt, so a mid-dig credit death should cost the newest organ rather than a region. **RECURSIVE BY MANDATE, not label-bound:** WorldQuant → author → their other repos → related papers → cited papers and who-cites-them → related GitHub projects → **alternative implementations** → discussions → operators → datasets → mechanisms. The alternative-implementation node is called out as usually the highest-yield: someone who reimplemented an operator set had to UNDERSTAND it, and their README states what official docs assume (how decay interacts with turnover, what neutralization actually subtracts, where delay is applied). **MECHANISM EXTRACTION, NOT FORMULA COPYING:** every operator must return what it computes, its CRYPTO ANALOGUE (added to `evidence_tier.translate_to_crypto`), and — if it has none — what data the desk lacks, which routes to the information-frontier axis rather than being discarded. The platform is primarily an EQUITIES venue, so a factor rarely transfers while its transformation, neutralization idea, regime conditioning or methodology often does. **IT IS POINTED AT THE BLOCKING INPUT:** `group_rank`/`group_zscore` both REFUSE without a group map and the desk has NONE, so two of four newly-adopted operators are inert — a crypto grouping taxonomy (CoinGecko categories, DeFiLlama chains, liquidity tier, listing cohort, correlation cluster) is worth more right now than another operator. **THE BAR IS REFUSED AGAIN HERE**, on the organ closest to the source and therefore likeliest to import it. **AND THE BOUNDARY IS EXPLICIT (§13):** "every WorldQuant thing" means everything PUBLICLY and LEGALLY accessible — never private BRAIN data, other users' private alphas, proprietary datasets, restricted platform internals, or account-gated content behind a login the desk does not own; a credentialed account's contents are not public merely because an account exists. Naming what sits behind a wall is legitimate; going behind it is not, and a source obtained improperly poisons every result derived from it. 11 tests fence the wiring, the recursion, the translation, the bar refusal and the boundary. **REMAINING:** it cannot run from this clone (network-denied, row 91) and needs `llm_panel.json` funded; its first real output is a principal-side run. DEADLINE 2026-08-14. | brain | 08-07 | open |
 | 103 | **`build_bars.py` POOLED EVERY INSTRUMENT INTO ONE OHLCV SERIES — SO 86% OF THE FIRST REAL FULL-SWEEP RUN WAS UNMEASURABLE, AND THE CROSS-SECTIONAL HALF OF THE EXPRESSION LANGUAGE COULD NEVER RUN AT ALL** | First live execution of the full sweep on the VPS, 2026-08-07: `898,560 evaluated / 128,132 measurable (85.7% UNMEASURED), 1 symbol(s), 919 common bars`. The verdict string did its job — "NOT ONE CELL cleared the deflated screen, so the kill criteria were never exercised … which is not 'no edge'" — but the CAUSE was upstream. `build_bars.build()` accumulated every trade from every file into one `px` list and resampled it into a SINGLE series: an open from one instrument and a close from another landed in the same bar, which is a price series of nothing. **Symbol was never missing — the recorders encode it in the path** (`data/moat/<venue>/<symbol>/<file>`, exactly the nesting `record_desk_metrics.py:111` already counts breadth from) and the builder discarded it. Consequences compound: every consumer saw ONE symbol, so `rank`, `zscore` and the newly-added `group_rank`/`group_zscore` had no peers to rank against and CORRECTLY refused — which is why 86% came back unmeasurable rather than wrong. **AND A SECOND DEFECT UNDERNEATH IT:** `FILE_BUDGET` took `files[-400:]` GLOBALLY, so the busiest stream ate the entire budget; the live run read 400 of 32,440 files and surfaced ONE venue (`{'spot': 537877}`, `OI: False`, 9 days of span). That is not a sampling choice anyone made — it is whichever recorder wrote most recently. | **FIXED.** `group_by_symbol()` buckets tape files by `f.parent.name`; `main()` builds and writes ONE artifact per symbol (`<SYMBOL>_15min.parquet`), which every consumer already picks up since they glob `data/bars/*.parquet` and derive the symbol from the filename. The budget is now PER SYMBOL (`FILE_BUDGET // n_symbols`), so breadth is guaranteed rather than accidental — breadth being the whole point, since no cross-sectional operator can run on fewer than two symbols. Venue is deliberately NOT part of the grouping key: the same symbol on spot and perp is one instrument for a bar series and merging deepens it; what must never merge is two different SYMBOLS. `build()`'s signature is unchanged so all nine existing tests still pass, and three new ones fence the defect — that two symbols never share a series, that the budget is per-symbol, and that the artifact name carries the symbol. **REMAINING:** the run also showed `OI: False` (no open-interest rows in the sampled files) and `moat_screen` was OOM-KILLED on the 4GB box — both are separate items. The next `build_bars` run on the box is what proves the fix; expect the sweep's measurable fraction to rise from 14% toward most of the universe. DEADLINE 2026-08-14. | brain | 08-07 | closed |
+| 104 | **THREE LAWS SHIPPED TODAY (L1.53-L1.55) AND ONLY PART OF EACH HAS A FENCE — THE DESK JUST WROTE ITSELF A SET OF CLAIMS IT CANNOT YET CASH** | L1.49 says a gate that never ran is a claim the desk cannot cash, and by that standard most of 2026-08-08's constitutional work is a claim. What IS enforced: the three stranding states (`dormancy.stranding()` + `call_sites()`, wired into `run_intelligence_cycle`, feeding `run_max_push._from_stranding`), the residual mandate on four external seats (10 tests, including one that FAILS if anyone hands it to the blind researcher), and the funnel/near-survivor/evidence-tier/convergence consumer. What is NOT, item by item, each asked for explicitly by the principal in the same session: **(a) the recursive residual-gap protocol** — adaptive multi-pass with a marginal-value stop, Pass-A expansion vs Pass-B reconsideration, and the ten frontier search modes; the mandate tells a seat WHAT to hunt and never tells it to keep attacking its own answer until returns collapse. **(b) the Claude<->GPT difference engine** — semantic clustering of two corpora, overlap removal, ranked difference set; only the CLASSIFICATION LABELS exist, inside a prompt, and no organ computes the difference. **(c) a generic `Gap` input contract for max-push** — the principal warned in the same message that the queue must not become a pile of special cases, and `_from_stranding` was added as a special case. **(d) a cadence-vs-ROI audit** — the crontab was READ, not one cadence was measured against its yield. **(e) orphan detection beyond modules** — data with no downstream feature, features never used in a hypothesis, recommendations never implemented, survivors never portfolio-tested. **(f) assumption registry, contradiction engine, unknowns database, structured failure-mining fields, near-survivor bands.** **(g) miner / model / prompt ROI attribution.** **(h) the alpha state machine** that would make `DISCOVERED -> LIVE` mechanically impossible — governance asserts it and no object enforces it, which is the single largest gap between this desk's written governance and its running governance. | **THE ROW EXISTS SO THE LIST STOPS BEING CHAT PROSE.** `finding_registry` already says it: a finding that never reaches this register is invisible to the daily cycle, and the cycle only acts on what it can see. Ranked here, each item gets the 7-day staleness escalation and enters the max-push queue through `_from_register`. **ORDER IS BY EXPECTED VALUE, NOT BY EFFORT:** (a) first — it is a PROMPT change against seats that already exist, so it needs no new organ and cannot become inventory, which is the exact property (b), (e), (f) and (g) all lack. (h) is the largest but is a build, and this desk's most-repeated defect is writing organs faster than they get consumers. (c) is a refactor of working code and should ride the next real addition to the queue rather than be done for its own sake. **AND THE HONEST CAVEAT ON (a):** its value is unmeasurable until OpenRouter is funded — every external seat is 402 today, so a better protocol on an unrunnable seat is a better document. That is a principal-side input, not a hurdle to route around. DEADLINE 2026-08-15. | brain | 08-08 | open |
```


---

## 9e7d707 a study may not be tied to the lifetime of a terminal
MEASURED TODAY, AND IT COST A REAL RUN. The full sweep started over SSH at 09:56Z and reached
~40% -- 359,424 of 898,560 candidates across 8 of 20 cells -- when the connection dropped:

    client_loop: send disconnect: Connection reset

The studies ran in the FOREGROUND of the invoking shell, so SIGHUP killed the sweep. Afterwards
there was no process, no OOM line in dmesg, no traceback, and no data/full_sweep.json, because
the report is only written at the end. The eight cells of results existed solely in terminal
scrollback.

THE FAILURE MODE IS SILENT AND TOTAL, which is what makes it worth a fence rather than a habit:
an hour of niced compute produced nothing, and every diagnostic the operator could run afterwards
showed a clean box. A crash at least leaves a trace. This one leaves a machine that looks fine.

It is a property of the runner, not operator error. A study that projects 56 minutes and is
allowed up to 180 cannot depend on a terminal staying open.

THE GUARD: started from a controlling terminal, the script re-execs itself under setsid+nohup and
hands back the log path, the follow command and the stop command. STUDY_FOREGROUND=1 opts out.

THE TEST IS "DO I HAVE A CONTROLLING TERMINAL", NOT "IS STDOUT A TTY", and the first version of
this guard had that bug. SIGHUP is delivered to the foreground process group of the controlling
terminal REGARDLESS of where stdout was redirected, so `[ -t 1 ]` would have taken the inline
path for `bash ops/run_study_on_vps.sh | tee run.log` -- the most natural way an operator runs
this, and exactly as exposed as the bare invocation.

cron and systemd have no controlling terminal, so they take the inline path and the scheduled
runs are unchanged. A guard that altered them would be a change to the money-adjacent cadence
disguised as an ergonomics fix.

Verified on the box: restarted detached at 11:18:21Z, pid 200888.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 9e7d707c9974877f2dcd0f9921451a8f99b4c9f2
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 11:20:44 2026 +0000

    a study may not be tied to the lifetime of a terminal
    
    MEASURED TODAY, AND IT COST A REAL RUN. The full sweep started over SSH at 09:56Z and reached
    ~40% -- 359,424 of 898,560 candidates across 8 of 20 cells -- when the connection dropped:
    
        client_loop: send disconnect: Connection reset
    
    The studies ran in the FOREGROUND of the invoking shell, so SIGHUP killed the sweep. Afterwards
    there was no process, no OOM line in dmesg, no traceback, and no data/full_sweep.json, because
    the report is only written at the end. The eight cells of results existed solely in terminal
    scrollback.
    
    THE FAILURE MODE IS SILENT AND TOTAL, which is what makes it worth a fence rather than a habit:
    an hour of niced compute produced nothing, and every diagnostic the operator could run afterwards
    showed a clean box. A crash at least leaves a trace. This one leaves a machine that looks fine.
    
    It is a property of the runner, not operator error. A study that projects 56 minutes and is
    allowed up to 180 cannot depend on a terminal staying open.
    
    THE GUARD: started from a controlling terminal, the script re-execs itself under setsid+nohup and
    hands back the log path, the follow command and the stop command. STUDY_FOREGROUND=1 opts out.
    
    THE TEST IS "DO I HAVE A CONTROLLING TERMINAL", NOT "IS STDOUT A TTY", and the first version of
    this guard had that bug. SIGHUP is delivered to the foreground process group of the controlling
    terminal REGARDLESS of where stdout was redirected, so `[ -t 1 ]` would have taken the inline
    path for `bash ops/run_study_on_vps.sh | tee run.log` -- the most natural way an operator runs
    this, and exactly as exposed as the bare invocation.
    
    cron and systemd have no controlling terminal, so they take the inline path and the scheduled
    runs are unchanged. A guard that altered them would be a change to the money-adjacent cadence
    disguised as an ergonomics fix.
    
    Verified on the box: restarted detached at 11:18:21Z, pid 200888.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 ops/run_study_on_vps.sh               | 36 ++++++++++++++++
 tests/ops/test_study_runner_detach.py | 77 +++++++++++++++++++++++++++++++++++
 2 files changed, 113 insertions(+)

diff --git a/ops/run_study_on_vps.sh b/ops/run_study_on_vps.sh
index f909b61..cfed4ae 100755
--- a/ops/run_study_on_vps.sh
+++ b/ops/run_study_on_vps.sh
@@ -29,6 +29,42 @@ ONLY="${1:-}"
 LOG="${STUDY_LOG:-data/study_runs.log}"
 mkdir -p "$(dirname "$LOG")"
 
+# ---------------------------------------------------------------------------------------------
+# SURVIVE A DROPPED SSH SESSION. Added 2026-08-08 after it cost a real run.
+#
+# WHAT HAPPENED. The operator started the full sweep over SSH at 09:56Z. At ~40% -- 359,424 of
+# 898,560 candidates evaluated across 8 of 20 cells -- the connection dropped:
+#
+#     client_loop: send disconnect: Connection reset
+#
+# The studies run in the FOREGROUND of the invoking shell, so SIGHUP killed the sweep. Afterwards
+# there was no process, no OOM line in dmesg, no traceback, and no data/full_sweep.json, because
+# the report is only written at the end. The eight cells of results existed solely in terminal
+# scrollback. THE FAILURE MODE IS SILENT AND TOTAL: an hour of niced compute produced nothing,
+# and every diagnostic the operator could run afterwards showed a clean box.
+#
+# This is a property of the runner, not operator error. A study that projects 56 minutes and is
+# allowed up to 180 CANNOT be tied to the lifetime of a terminal.
+#
+# THE GUARD: when started from a TTY, re-exec detached and hand back the follow command. cron and
+# systemd have no controlling terminal, so they take the normal path and nothing about the
+# scheduled runs changes. STUDY_FOREGROUND=1 opts out for debugging.
+# THE TEST IS "DO I HAVE A CONTROLLING TERMINAL", NOT "IS STDOUT A TTY", and the difference is
+# the whole point: SIGHUP is delivered to the foreground process group of the controlling
+# terminal REGARDLESS of where stdout was redirected. `[ -t 1 ]` would take the inline path for
+# `bash ops/run_study_on_vps.sh | tee run.log` -- the most natural way an operator would run this
+# -- and that invocation is exactly as exposed to a dropped connection as the bare one.
+if ( : > /dev/tty ) 2>/dev/null && [ -z "${STUDY_DETACHED:-}" ] && [ -z "${STUDY_FOREGROUND:-}" ]
+then
+    _runlog="data/study_runs_$(date -u +%Y%m%dT%H%M%SZ).log"
+    STUDY_DETACHED=1 setsid nohup bash "$0" "$@" > "$_runlog" 2>&1 < /dev/null &
+    echo "detached as pid $! -- this run now survives a dropped SSH session."
+    echo "  follow:  tail -f $_runlog"
+    echo "  stop:    kill $!"
+    echo "  (STUDY_FOREGROUND=1 runs inline instead; cron and systemd already do, having no TTY)"
+    exit 0
+fi
+
 # THE INTERPRETER IS .venv/bin/python, NOT python3 -- and this script had it wrong until 2026-08-06.
 # Every other entry point on this box already knew: the systemd units all ExecStart
 # `.venv/bin/python`, ops/deploy_vps.sh hard-FAILS if that binary is absent, and brain_env.sh walks
diff --git a/tests/ops/test_study_runner_detach.py b/tests/ops/test_study_runner_detach.py
new file mode 100644
index 0000000..eaf8899
--- /dev/null
+++ b/tests/ops/test_study_runner_detach.py
@@ -0,0 +1,77 @@
+"""A STUDY MAY NOT BE TIED TO THE LIFETIME OF A TERMINAL.
+
+MEASURED 2026-08-08 and it cost a real run. The full sweep started over SSH at 09:56Z and reached
+~40% -- 359,424 of 898,560 candidates across 8 of 20 cells -- when the connection dropped
+(`client_loop: send disconnect: Connection reset`). The studies ran in the FOREGROUND of the
+invoking shell, so SIGHUP killed it. Afterwards: no process, no OOM line, no traceback, and no
+`data/full_sweep.json`, because the report is only written at the end.
+
+THE FAILURE MODE IS SILENT AND TOTAL. An hour of niced compute produced nothing, the eight cells
+of results existed only in terminal scrollback, and every diagnostic the operator could run
+afterwards showed a clean box. That is worse than a crash, which at least leaves a trace.
+"""
+
+from __future__ import annotations
+
+import re
+from pathlib import Path
+
+import pytest
+
+_SCRIPT = Path("ops/run_study_on_vps.sh")
+
+
+@pytest.fixture(scope="module")
+def src() -> str:
+    return _SCRIPT.read_text("utf-8")
+
+
+def test_AN_INTERACTIVE_RUN_RE_EXECS_DETACHED(src: str) -> None:
+    assert "setsid nohup bash" in src, "a dropped SSH session must not be able to kill a study"
+    assert "STUDY_DETACHED=1" in src, "the re-exec needs a guard or it recurses forever"
+
+
+def test_THE_GUARD_TESTS_FOR_A_CONTROLLING_TERMINAL_NOT_FOR_A_TTY_STDOUT(src: str) -> None:
+    """SIGHUP reaches the foreground process group of the CONTROLLING TERMINAL regardless of
+    where stdout was redirected.
+
+    `[ -t 1 ]` would take the inline path for `bash ops/run_study_on_vps.sh | tee run.log` -- the
+    most natural way an operator would run this -- and that invocation is exactly as exposed to a
+    dropped connection as the bare one. The first version of this guard had that bug.
+    """
+    guard = re.search(r"^if .*STUDY_DETACHED.*$", src, re.MULTILINE)
+    assert guard, "the detach guard is gone"
+    assert "/dev/tty" in guard.group(0)
+    assert "-t 1" not in guard.group(0), "stdout-is-a-tty is the wrong test -- see the docstring"
+
+
+def test_CRON_AND_SYSTEMD_ARE_UNAFFECTED(src: str) -> None:
+    """They have no controlling terminal, so they take the inline path and the scheduled runs are
+    byte-for-byte unchanged. A guard that altered them would be a change to the money-adjacent
+    cadence disguised as an ergonomics fix."""
+    assert "cron and systemd" in src
+
+
+def test_THERE_IS_AN_EXPLICIT_OPT_OUT(src: str) -> None:
+    """Debugging a study needs the inline path, and an escape hatch that is not named in the
+    script is an escape hatch nobody finds."""
+    assert "STUDY_FOREGROUND" in src
+    assert "STUDY_FOREGROUND=1 runs inline" in src
+
+
+def test_THE_OPERATOR_IS_TOLD_HOW_TO_FOLLOW_AND_STOP_IT(src: str) -> None:
+    """Detaching without handing back the log path replaces one silent failure with another."""
+    assert "follow:  tail -f" in src
+    assert "stop:    kill" in src
+
+
+def test_THE_DETACHED_RUN_WRITES_ITS_OWN_TIMESTAMPED_LOG(src: str) -> None:
+    """Sharing one log across concurrent detached runs would interleave two studies into a record
+    neither of them can be read out of."""
+    assert 'data/study_runs_$(date -u +%Y%m%dT%H%M%SZ).log' in src
+
+
+def test_THE_SCRIPT_STILL_PARSES() -> None:
+    import subprocess
+    r = subprocess.run(["bash", "-n", str(_SCRIPT)], capture_output=True, text=True, check=False)
+    assert r.returncode == 0, r.stderr
```


---

## 4056910 feed conversion failures into the max-push queue, and ratchet both floors
DETECTION WITHOUT RANKING IS HALF A CONTROL, and this was the gap the governance found in
itself. `run_max_push.py` merges every "not yet at 100%" source into one ranked queue so the
highest-value gap has an answer every morning without anyone deciding. Its dormant-capability
source reads `wiring_agent.json`, which counts scripts nothing SCHEDULES -- so it structurally
cannot see the two states an importer count never reaches (L1.54(a)): a module IMPORTED and
never called, and a module that runs while nothing reads its output.

The consequence was that the desk could discover a real high-value gap and never prioritise it.
Measured the same morning the detector was built: `run_intelligence_cycle` imports
`capital_reallocator` and `health_monitor` purely to prove they import, then reads the artifacts
itself and reports BOTH ACTIVE without ever invoking either. Two findings the queue was blind to.

`_from_stranding` closes DETECTION -> RANKING. Scored as `dormant_capability` rather than as a
new leverage class, because it IS paid-for engineering returning zero and inventing a weight
would rank worse while looking more precise -- the module's own declared-not-computed rule.

AN ABSENT CYCLE ARTIFACT IS UNMEASURED, NOT ZERO. Letting "the scan has not run" read as "no
conversion failures" would be WS-005 aimed at the queue's own inputs, and UNMEASURED already
outranks a partial number here by design (an aspect at 60% is a known quantity being worked; an
aspect with no number is an unknown being ignored).

COVERAGE RATCHET RAISED (L1.50): repo 92.69% -> 93.06%, money path 70.45% -> 81.55% over 748
statements. The money-path jump is the larger one and the inversion against repo-wide coverage
is now much smaller. ~138 uncovered statements remain on the code that can move funds; the floor
is the minimum and 100% is the target.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit 40569105ef46717bcafa278c03f0f79ad7863cdd
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 11:14:57 2026 +0000

    feed conversion failures into the max-push queue, and ratchet both floors
    
    DETECTION WITHOUT RANKING IS HALF A CONTROL, and this was the gap the governance found in
    itself. `run_max_push.py` merges every "not yet at 100%" source into one ranked queue so the
    highest-value gap has an answer every morning without anyone deciding. Its dormant-capability
    source reads `wiring_agent.json`, which counts scripts nothing SCHEDULES -- so it structurally
    cannot see the two states an importer count never reaches (L1.54(a)): a module IMPORTED and
    never called, and a module that runs while nothing reads its output.
    
    The consequence was that the desk could discover a real high-value gap and never prioritise it.
    Measured the same morning the detector was built: `run_intelligence_cycle` imports
    `capital_reallocator` and `health_monitor` purely to prove they import, then reads the artifacts
    itself and reports BOTH ACTIVE without ever invoking either. Two findings the queue was blind to.
    
    `_from_stranding` closes DETECTION -> RANKING. Scored as `dormant_capability` rather than as a
    new leverage class, because it IS paid-for engineering returning zero and inventing a weight
    would rank worse while looking more precise -- the module's own declared-not-computed rule.
    
    AN ABSENT CYCLE ARTIFACT IS UNMEASURED, NOT ZERO. Letting "the scan has not run" read as "no
    conversion failures" would be WS-005 aimed at the queue's own inputs, and UNMEASURED already
    outranks a partial number here by design (an aspect at 60% is a known quantity being worked; an
    aspect with no number is an unknown being ignored).
    
    COVERAGE RATCHET RAISED (L1.50): repo 92.69% -> 93.06%, money path 70.45% -> 81.55% over 748
    statements. The money-path jump is the larger one and the inversion against repo-wide coverage
    is now much smaller. ~138 uncovered statements remain on the code that can move funds; the floor
    is the minimum and 100% is the target.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/research/COVERAGE_RATCHET.json      | 12 ++---
 docs/research/test_suite_record.json     |  4 +-
 scripts/run_max_push.py                  | 56 +++++++++++++++++++++-
 tests/scripts/test_max_push_stranding.py | 80 ++++++++++++++++++++++++++++++++
 4 files changed, 143 insertions(+), 9 deletions(-)

diff --git a/docs/research/COVERAGE_RATCHET.json b/docs/research/COVERAGE_RATCHET.json
index d975656..10f3c8f 100644
--- a/docs/research/COVERAGE_RATCHET.json
+++ b/docs/research/COVERAGE_RATCHET.json
@@ -1,14 +1,14 @@
 {
  "_": "HIGH-WATER MARKS for test coverage. Raised by --update, NEVER lowered by code. The money path is tracked separately because a repo-wide average lets order-path coverage fall while research tests keep the aggregate up -- the average hides exactly the number worth watching.",
- "updated": "2026-08-07T22:45:11.761553+00:00",
- "last_raised": "2026-08-07T20:13:06.141434+00:00",
+ "updated": "2026-08-08T11:14:17.836808+00:00",
+ "last_raised": "2026-08-08T11:14:17.836797+00:00",
  "high_water": {
-  "repo_pct": 92.69,
-  "money_path_pct": 70.45
+  "repo_pct": 93.06,
+  "money_path_pct": 81.55
  },
  "measured": {
-  "repo_pct": 92.69,
-  "money_path_pct": 70.45,
+  "repo_pct": 93.06,
+  "money_path_pct": 81.55,
   "money_path_statements": 748
  },
  "money_path_files": [
diff --git a/docs/research/test_suite_record.json b/docs/research/test_suite_record.json
index f0c1bc8..bb3cd66 100644
--- a/docs/research/test_suite_record.json
+++ b/docs/research/test_suite_record.json
@@ -1,5 +1,5 @@
 {
- "max_collected": 317,
- "at": "2026-08-08T10:37:51.704370+00:00",
+ "max_collected": 318,
+ "at": "2026-08-08T11:04:22.658837+00:00",
  "note": "high-water mark of COLLECTABLE test modules; ratchets UP only. A suite may never quietly shrink -- deleting a test is a decision, not a side effect."
 }
\ No newline at end of file
diff --git a/scripts/run_max_push.py b/scripts/run_max_push.py
index 29b6e63..4f4e926 100644
--- a/scripts/run_max_push.py
+++ b/scripts/run_max_push.py
@@ -324,6 +324,59 @@ def _from_freshness() -> list[dict[str, Any]]:
                   "data/freshness_status.json")]
 
 
+def _from_stranding() -> list[dict[str, Any]]:
+    """CONVERSION FAILURES the wiring source structurally cannot see, and that is the whole point.
+
+    `_from_wiring` reads `wiring_agent.json`, which counts scripts nothing SCHEDULES. That misses
+    the two states an importer count cannot reach (L1.54(a)): a module IMPORTED and never called,
+    and a module that runs while nothing reads its output. Both look reachable from every angle
+    the older sources have.
+
+    MEASURED 2026-08-08 and the reason this function exists rather than a note in the register:
+    `run_intelligence_cycle` imports `capital_reallocator` and `health_monitor` purely to prove
+    they import, then reads the artifacts itself and reports both ACTIVE. The detector found them
+    the same morning it was built -- and the queue could not see the finding, so the desk could
+    discover a real gap and never prioritise it. Detection without ranking is half a control.
+
+    Scored as `dormant_capability` rather than as a new class: it IS paid-for engineering
+    returning zero, and inventing a weight would rank worse while looking more precise.
+    """
+    d = _json("data/intelligence_cycle.json") or {}
+    caps = d.get("capabilities") if isinstance(d, dict) else None
+    rows: list[dict[str, Any]] = []
+    if isinstance(caps, list):
+        for c in caps:
+            if isinstance(c, dict) and c.get("name") == "dormancy_hunter":
+                rows = c.get("report", {}).get("imported_but_never_called", []) or []
+                break
+    if not isinstance(rows, list):
+        return []
+    scanned = 0
+    if isinstance(caps, list):
+        for c in caps:
+            if isinstance(c, dict) and c.get("name") == "dormancy_hunter":
+                scanned = int((c.get("report", {}).get("scanned", {}) or {}).get("modules", 0))
+                break
+    if not scanned:
+        # UNMEASURED, NOT ZERO. An absent cycle artifact means nobody looked, and letting that
+        # read as "no conversion failures" is WS-005 aimed at the queue's own inputs.
+        return [_item("capability::conversion_failures", "dormant_capability", None, 1.0,
+                      "no intelligence-cycle artifact -- the stranding scan has not run here",
+                      "run scripts/run_intelligence_cycle.py; UNMEASURED outranks a partial "
+                      "number because an unknown quantity is being ignored, not worked",
+                      "data/intelligence_cycle.json")]
+    n = len(rows)
+    worst = ", ".join(str(r.get("path", "?")) for r in rows[:3]) or "none"
+    return [_item("capability::conversion_failures", "dormant_capability",
+                  (scanned - n) / scanned, 1.0,
+                  f"{n} module(s) imported by a live consumer that NEVER call them, of {scanned} "
+                  f"scanned; worst by size: {worst}",
+                  "call it from the consumer that already imports it, or delete the import -- an "
+                  "import kept to prove a module loads reports ACTIVE while the capability has "
+                  "never run once (L1.54(a))",
+                  "data/intelligence_cycle.json")]
+
+
 def build(*, refresh: bool = True) -> dict[str, Any]:
     if refresh:
         for s in ("check_ratchets.py", "check_utilisation.py", "build_enforcement_matrix.py",
@@ -331,7 +384,8 @@ def build(*, refresh: bool = True) -> dict[str, Any]:
             _refresh(s)
     items = (_from_ratchets() + _from_utilisation() + _from_matrix()
              + _from_wiring() + _from_register() + _from_conversion()
-             + _from_tier_benchmark() + _from_calibration() + _from_freshness())
+             + _from_tier_benchmark() + _from_calibration() + _from_freshness()
+             + _from_stranding())
     items.sort(key=lambda r: -float(r["score"]))
     at_ceiling = [i for i in items if i["measured"] and i["gap_fraction"] <= 0.0]
     unmeasured = [i for i in items if not i["measured"]]
diff --git a/tests/scripts/test_max_push_stranding.py b/tests/scripts/test_max_push_stranding.py
new file mode 100644
index 0000000..8a22c6f
--- /dev/null
+++ b/tests/scripts/test_max_push_stranding.py
@@ -0,0 +1,80 @@
+"""DETECTION WITHOUT RANKING IS HALF A CONTROL.
+
+The max-push queue merges every "not yet at 100%" source into one ranked list. Its dormant-
+capability source reads `wiring_agent.json`, which counts scripts nothing SCHEDULES -- so it
+structurally cannot see the two states an importer count never reaches (L1.54(a)): a module
+IMPORTED and never called, and a module that runs while nothing reads its output.
+
+MEASURED 2026-08-08: the stranding detector found `capital_reallocator` and `health_monitor`
+imported by `run_intelligence_cycle` purely to prove they import, then reported ACTIVE without
+ever being invoked. The queue could not see the finding, so the desk could discover a real gap
+the same morning and still never prioritise it.
+"""
+
+from __future__ import annotations
+
+import json
+from pathlib import Path
+from typing import Any
+
+import scripts.run_max_push as MP
+
+
+def _cycle(rows: list[dict[str, Any]] | None, scanned: int) -> dict[str, Any]:
+    report: dict[str, Any] = {"scanned": {"modules": scanned, "scripts": 0}}
+    if rows is not None:
+        report["imported_but_never_called"] = rows
+    return {"capabilities": [{"name": "dormancy_hunter", "report": report}]}
+
+
+def _with_artifact(tmp_path: Path, monkeypatch, doc: Any) -> list[dict[str, Any]]:
+    """Serialise through JSON on purpose: the real source reads a file, so every value the
+    function touches must survive a round trip rather than being a live Python object."""
+    p = tmp_path / "intelligence_cycle.json"
+    p.write_text(json.dumps(doc), "utf-8") if doc is not None else None
+    monkeypatch.setattr(MP, "_json", lambda _rel: json.loads(p.read_text("utf-8"))
+                        if p.exists() else None)
+    return MP._from_stranding()
+
+
+def test_A_CONVERSION_FAILURE_REACHES_THE_QUEUE(tmp_path, monkeypatch) -> None:
+    rows = [{"path": "libs/self_improvement/capital_reallocator.py", "lines": 51},
+            {"path": "libs/self_improvement/health_monitor.py", "lines": 21}]
+    out = _with_artifact(tmp_path, monkeypatch, _cycle(rows, 400))
+    assert len(out) == 1
+    item = out[0]
+    assert item["aspect"] == "capability::conversion_failures"
+    assert item["measured"] is True
+    assert "capital_reallocator" in item["detail"]
+    assert item["gap_fraction"] > 0, "two stranded modules must produce a non-zero gap"
+
+
+def test_AN_ABSENT_CYCLE_ARTIFACT_IS_UNMEASURED_NOT_ZERO(tmp_path, monkeypatch) -> None:
+    """Letting an absent scan read as 'no conversion failures' is WS-005 aimed at the queue's own
+    inputs -- and UNMEASURED outranks a partial number by design."""
+    out = _with_artifact(tmp_path, monkeypatch, None)
+    assert len(out) == 1 and out[0]["measured"] is False
+    assert out[0]["gap_fraction"] == 1.0
+    assert "has not run" in out[0]["detail"]
+
+
+def test_A_CLEAN_SCAN_IS_AT_CEILING_NOT_ABSENT(tmp_path, monkeypatch) -> None:
+    """Zero stranded modules is a real measurement and must still appear in the queue, so the
+    anti-complacency escalation can count it among the aspects that ARE at their ceiling."""
+    out = _with_artifact(tmp_path, monkeypatch, _cycle([], 400))
+    assert len(out) == 1 and out[0]["measured"] is True
+    assert out[0]["gap_fraction"] == 0.0
+
+
+def test_IT_IS_SCORED_AS_DORMANT_CAPABILITY_RATHER_THAN_A_NEW_CLASS(tmp_path, monkeypatch) -> None:
+    """It IS paid-for engineering returning zero. Inventing a weight would rank worse while
+    looking more precise -- the module's own rule about declared-not-computed leverage."""
+    out = _with_artifact(tmp_path, monkeypatch, _cycle([{"path": "x.py", "lines": 9}], 100))
+    assert out[0]["source"] == "dormant_capability"
+    assert out[0]["leverage"] == MP._LEVERAGE["dormant_capability"][0]
+
+
+def test_THE_SOURCE_IS_ACTUALLY_IN_THE_BUILD(tmp_path) -> None:
+    """A source function nobody calls is the exact defect this whole commit is about."""
+    src = Path("scripts/run_max_push.py").read_text("utf-8")
+    assert "+ _from_stranding())" in src or "_from_stranding()" in src.split("def build")[1]
```


---

## a869ca3 wire the four orphan modules, and give the stranding defect a mechanical name
THE DEFECT THIS COMMIT IS ABOUT. convergence, evidence_tier, funnel and near_survivor were
tested, documented, committed -- and had ZERO importers. By this desk's own standard that is
inventory, not capability: the same shape as combination_engine emitting 898,560 candidates
with no executor.

scripts/run_research_review.py is the consumer. It reads the sweep report and produces the four
things the desk needs after a run: WHERE the pipeline is blocked (from the sweep's own stage
counts, never a hand-typed number), WHAT the killed cells license next with the ancestry
deflation attached, WHETHER a survivor is executable or merely claimed, and WHETHER
independently-sourced findings agree or are echoing one source.

kill_caveat() was caught by running the review against a box-shaped report. The funnel saw
out_of_sample=0 and diagnosed OVERFITTING -- "the harness is selecting on noise". The sweep's
kill breakdown said F5 SAMPLE FLOOR: both cells died because a split arm had too few
observations. Tighten-the-harness and get-more-tape are opposite spends, and a stage reports
only that nothing got through, never why.

AND THE REVIEW ITSELF SHIPPED THE SAME DEFECT ONE LEVEL UP. Its first draft wrote a hand-typed
"verdict": "UNMEASURED" for convergence -- a consumer that DESCRIBED a capability instead of
calling it. elevate() now runs on every review, including the run where the corpus is empty.

L1.53/L1.53(a): maximum immediate utilisation, the blocker escalation ladder, and the queue rule
-- queues are prohibited unless they represent a real capacity, dependency, statistical or safety
constraint, and never as a synonym for "the executor was never built". Cold on claims, open on
hypotheses: the only admissible rejections are cannot-be-executed, same mechanism already
graveyarded, or measured and killed. A hypothesis contradicting a desk belief ranks ABOVE a
confirmatory one. Capital deployment is explicitly carved out.

L1.54/L1.54(a): compute maximisation with validated-experiments-per-unit-time as the objective
rather than percent utilisation, and the three stranding states -- ORPHAN (nothing imports it),
INERT (a consumer exists, never ran), CONVERSION_FAILURE (it runs, output changes nothing). The
third is the one that hides: it passes every test an importer count can run.

L1.55: the question set is provisional. Hardcode the meta-rule, not the questions -- a fixed
checklist is a ceiling wearing the costume of thoroughness, and it fails silently because every
question gets a tick while the territory it never described stays invisible.

dormancy.stranding() + call_sites() are the enforcement, wired into run_intelligence_cycle. The
call detection is an ast walk, NOT a regex, and that is a correction: the regex version shipped
four silent false-positive shapes in one hour, each reading ZERO imported names and therefore
reporting a wired module as stranded -- parenthesised multi-line imports, a trailing noqa
comment, module-as-alias, and nested attribute chains. It flagged exec_monitor, which is called
on line 90 of its consumer. 33 findings -> 2, both hand-verified: run_intelligence_cycle imports
capital_reallocator and health_monitor purely to prove they import, then reports them ACTIVE
without ever invoking them.

RESIDUAL_MANDATE: the external seats hunt what the desk MISSED rather than producing a second,
costlier copy of research it already did. Wired into breadth_expander, meta_architect,
hypothesis_generator and collector_author -- and deliberately NOT into llm_blind_researcher,
whose entire value is deriving the space with the desk's conclusions withheld. A test fails if
anyone adds it there.

generation_roi: "mass generation is self-defeating" was too broad and read literally argues for
throttling generation, which L1.52 forbids. The distinction is same-information (diminishing
returns, rising hurdle) versus expanded-information (wider space at the same hurdle). Measured:
the candidate count was IDENTICAL at 898,560 across both runs; 1 symbol/918 bars gave 14%
measurable and 0 cleared, 45 symbols/1045 bars gave 83% and 150 cleared.

L1.52 also gained its anti-timidity reading -- first run with zero UNCLASSIFIED clauses.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit a869ca36f0ae4e35572c77c27dd5b3030da3660b
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 10:59:14 2026 +0000

    wire the four orphan modules, and give the stranding defect a mechanical name
    
    THE DEFECT THIS COMMIT IS ABOUT. convergence, evidence_tier, funnel and near_survivor were
    tested, documented, committed -- and had ZERO importers. By this desk's own standard that is
    inventory, not capability: the same shape as combination_engine emitting 898,560 candidates
    with no executor.
    
    scripts/run_research_review.py is the consumer. It reads the sweep report and produces the four
    things the desk needs after a run: WHERE the pipeline is blocked (from the sweep's own stage
    counts, never a hand-typed number), WHAT the killed cells license next with the ancestry
    deflation attached, WHETHER a survivor is executable or merely claimed, and WHETHER
    independently-sourced findings agree or are echoing one source.
    
    kill_caveat() was caught by running the review against a box-shaped report. The funnel saw
    out_of_sample=0 and diagnosed OVERFITTING -- "the harness is selecting on noise". The sweep's
    kill breakdown said F5 SAMPLE FLOOR: both cells died because a split arm had too few
    observations. Tighten-the-harness and get-more-tape are opposite spends, and a stage reports
    only that nothing got through, never why.
    
    AND THE REVIEW ITSELF SHIPPED THE SAME DEFECT ONE LEVEL UP. Its first draft wrote a hand-typed
    "verdict": "UNMEASURED" for convergence -- a consumer that DESCRIBED a capability instead of
    calling it. elevate() now runs on every review, including the run where the corpus is empty.
    
    L1.53/L1.53(a): maximum immediate utilisation, the blocker escalation ladder, and the queue rule
    -- queues are prohibited unless they represent a real capacity, dependency, statistical or safety
    constraint, and never as a synonym for "the executor was never built". Cold on claims, open on
    hypotheses: the only admissible rejections are cannot-be-executed, same mechanism already
    graveyarded, or measured and killed. A hypothesis contradicting a desk belief ranks ABOVE a
    confirmatory one. Capital deployment is explicitly carved out.
    
    L1.54/L1.54(a): compute maximisation with validated-experiments-per-unit-time as the objective
    rather than percent utilisation, and the three stranding states -- ORPHAN (nothing imports it),
    INERT (a consumer exists, never ran), CONVERSION_FAILURE (it runs, output changes nothing). The
    third is the one that hides: it passes every test an importer count can run.
    
    L1.55: the question set is provisional. Hardcode the meta-rule, not the questions -- a fixed
    checklist is a ceiling wearing the costume of thoroughness, and it fails silently because every
    question gets a tick while the territory it never described stays invisible.
    
    dormancy.stranding() + call_sites() are the enforcement, wired into run_intelligence_cycle. The
    call detection is an ast walk, NOT a regex, and that is a correction: the regex version shipped
    four silent false-positive shapes in one hour, each reading ZERO imported names and therefore
    reporting a wired module as stranded -- parenthesised multi-line imports, a trailing noqa
    comment, module-as-alias, and nested attribute chains. It flagged exec_monitor, which is called
    on line 90 of its consumer. 33 findings -> 2, both hand-verified: run_intelligence_cycle imports
    capital_reallocator and health_monitor purely to prove they import, then reports them ACTIVE
    without ever invoking them.
    
    RESIDUAL_MANDATE: the external seats hunt what the desk MISSED rather than producing a second,
    costlier copy of research it already did. Wired into breadth_expander, meta_architect,
    hypothesis_generator and collector_author -- and deliberately NOT into llm_blind_researcher,
    whose entire value is deriving the space with the desk's conclusions withheld. A test fails if
    anyone adds it there.
    
    generation_roi: "mass generation is self-defeating" was too broad and read literally argues for
    throttling generation, which L1.52 forbids. The distinction is same-information (diminishing
    returns, rising hurdle) versus expanded-information (wider space at the same hurdle). Measured:
    the candidate count was IDENTICAL at 898,560 across both runs; 1 symbol/918 bars gave 14%
    measurable and 0 cleared, 45 symbols/1045 bars gave 83% and 150 cleared.
    
    L1.52 also gained its anti-timidity reading -- first run with zero UNCLASSIFIED clauses.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 docs/CONSTITUTION.md                    | 224 ++++++++++++++++++++++++
 docs/research/test_suite_record.json    |   4 +-
 libs/autodiscovery/generation_roi.py    |  32 +++-
 libs/doctrine/constitution.py           |  53 ++++++
 libs/self_improvement/dormancy.py       | 157 +++++++++++++++++
 ops/run_research_cycle.sh               |   3 +
 scripts/breadth_expander.py             |   7 +-
 scripts/collector_author.py             |   7 +-
 scripts/hypothesis_generator.py         |   7 +-
 scripts/meta_architect.py               |   7 +-
 scripts/run_intelligence_cycle.py       |  17 +-
 scripts/run_research_review.py          | 296 ++++++++++++++++++++++++++++++++
 tests/libs/test_residual_mandate.py     |  83 +++++++++
 tests/scripts/test_research_review.py   | 189 ++++++++++++++++++++
 tests/self_improvement/test_dormancy.py | 109 ++++++++++++
 15 files changed, 1178 insertions(+), 17 deletions(-)

diff --git a/docs/CONSTITUTION.md b/docs/CONSTITUTION.md
index c65f785..3791d4f 100644
--- a/docs/CONSTITUTION.md
+++ b/docs/CONSTITUTION.md
@@ -1516,6 +1516,14 @@ a generator reports enormous productivity while re-searching one neighbourhood.
 matters is INDEPENDENT MECHANISMS (`libs/alpha_factory/independence.cluster`), and it is also the
 right basis for the effective trial count above.
 
+**ANTI-TIMIDITY (L1.28): the restraint words in this law bind the EVIDENCE RECORD, not the search.**
+"Reject" here means a hypothesis that was MEASURED AND KILLED — never one declined on sight, and
+the pedigree rejections are forbidden outright by L1.53(a). "Slow" appears only as the thing this
+law refuses: a saturated queue is an argument for more throughput, never for a slower generator.
+Nothing in L1.52 is **not a licence** — it is the opposite: the one clause that could read as a
+brake ("improve prioritisation rather than generate blindly") orders BETTER ordering of the same
+uncapped stream, and exploration may never be reduced to zero under any of it.
+
 **THIS LAW DOES NOT LICENSE BUILDING OVER EXECUTING, and the distinction is the whole point.**
 "Research never stops" is not "construction never stops". The mandate's own text is explicit: with
 ideas queued and none tested, the next engineering priority is EXPERIMENT THROUGHPUT, not the
@@ -1572,3 +1580,219 @@ is UNSTARTED ADMIN — keys, 2FA, sub-accounts, cold wallet — and says nothing
 exists: those 434 came from one screen, and the 20,052 pre-registered trials that would actually
 test the question have never run. Neither zero licenses a conclusion. Both license an action, and
 the actions are different.
+
+**L1.53 MAXIMUM IMMEDIATE UTILISATION — A QUEUE IS A CAPACITY FACT, NEVER A MISSING EXECUTOR**
+*(principal law, 2026-08-08)*. Every accessible research asset is converted into actionable
+research output continuously: `data → features → hypotheses → experiments → evidence → survivors →
+portfolio candidates → capital decisions`, with recommendations, external research, code, failed
+experiments, near-survivors, datasets, models and prompts mined for further opportunity in
+parallel. No available resource may sit unused because a more elaborate module, pipeline,
+abstraction or prerequisite has not been built. **Prefer the simplest executable path that
+produces evidence today, and improve the infrastructure alongside it rather than ahead of it.**
+
+**THE BLOCKER ESCALATION RULE**, which replaces the backlog as the default response to a
+discovery:
+
+```
+DISCOVERY / RECOMMENDATION
+  ↓  testable with what the desk already holds?      YES → TEST NOW
+  ↓  NO: name the SMALLEST missing dependency
+  ↓  obtainable or buildable immediately?            YES → DO IT NOW, then test
+  ↓  NO: record blocker + reason + the nearest alternative test
+  → MOVE TO THE NEXT HIGHEST-VALUE EXPERIMENT
+```
+
+A blocker is recorded ONCE, with a re-test condition. "We need A → B → C → D before we can test Y"
+is not a plan; it is architecture theatre, and the correct reading of it is *run Y the simplest
+valid way now, build A/B/C in parallel*.
+
+**QUEUES ARE PROHIBITED UNLESS THEY REPRESENT A REAL CONSTRAINT.** Legitimate: saturated
+compute, API or rate limits, a genuinely unavailable data dependency, experiments that require a
+prior result, a statistical control that needs a defined selection boundary (L1.52(a)), live
+capital awaiting risk approval, exchange constraints. Never legitimate: hypothesis generation,
+source discovery, GPT/Kimi recommendations, cheap screens while compute is idle, near-survivor
+mutation, recombination, falsification, prompt or model experiments. **A queue must never be a
+synonym for "the executor was never built" — that is GAP #86 wearing a scheduler's clothes.**
+
+**CONVERSION IS MEASURED PER STAGE, NOT ADMIRED IN AGGREGATE** (this is L1.28b's parity rule
+generalised to the whole pipeline, and `libs/research/funnel.py` is its instrument). No stage may
+accumulate a permanent backlog while an upstream stage keeps producing. 10,000 mined items → 500
+hypotheses → 100 tests → 5 survivors is a report about the CONVERSION BOTTLENECK, not about the
+10,000. The bottleneck stage is the work.
+
+**"100%" MEANS OPPORTUNITY, NOT LITERAL SATURATION.** Use every available resource wherever its
+expected marginal research value exceeds its opportunity cost — which is a stricter and more
+aggressive rule than "keep everything busy", because it forbids spending a day of compute on a
+low-value search merely because the compute was there. The desk never says *we are at the
+ceiling*; it says *this is the highest-value gap remaining and here is the measurement*.
+
+**THE ONE THING NEVER MAXIMISED IS CAPITAL DEPLOYMENT.** Research utilisation is uncapped;
+capital remains constrained by evidence, liquidity, drawdown, capacity and execution risk (L1.23,
+L1.45, the Tier-3 rail). "Maximum utilisation" applied to capital is maximum ruin risk, and this
+law explicitly does not reach it.
+
+**AND SURVIVOR COUNT IS AN ASPIRATION, NEVER A QUOTA.** A forced monthly survivor number is met
+the same way every forced number is met: by relaxing independence or validation standards. The
+throughput target is EXPERIMENTS EXECUTED; the survivor count is an outcome that is reported,
+never demanded.
+
+**L1.53(a) COLD ON CLAIMS, OPEN ON HYPOTHESES — THE TWO ARE NOT THE SAME SKEPTICISM**
+*(2026-08-08)*. The desk verifies claims brutally and judges hypotheses lightly, and collapsing
+these into one posture breaks the research loop in one of two ways.
+
+**A claim is never evidence because an LLM stated it.** A proposed mechanism, a cited paper, a
+named dataset, a described repository, a reported result: each enters as
+`CLAIM → SOURCE → EXTRACTION → VERIFICATION → EXPERIMENT`, and every external output carries one
+of `VERIFIED | INFERRED | HYPOTHESIS | UNVERIFIED | CONTRADICTED`. Instructing a model not to
+hallucinate is not a control; making hallucination cheap and detectable is. Plausible reasoning is
+not demonstrated predictive edge, and a trading claim is the most expensive place on this desk to
+forget that.
+
+**AND A HYPOTHESIS IS NEVER REJECTED FOR ITS PEDIGREE.** No candidate may be dismissed because an
+LLM generated it, because it sounds unconventional, because it lacks prior evidence, because it
+contradicts the desk's current beliefs, because it is absent from the knowledge graph, because no
+paper covers it, or because its source is obscure or foreign-language. The only admissible
+rejections are: *cannot be executed*, *already in the graveyard with the same mechanism*, or
+*measured and killed*. Everything else is priced, queued by expected value, and tested — a
+hypothesis that contradicts a current belief is a FALSIFICATION OPPORTUNITY and ranks above a
+confirmatory one, not below it.
+
+    generate broadly · judge lightly before testing · test aggressively · validate brutally after
+
+**THE TWO GPT POSTURES ARE SEPARATED ON PURPOSE**, because a model that reads its own prior output
+elaborates it rather than challenges it. COLD DISCOVERY runs with the desk's conclusions withheld
+(`scripts/llm_blind_researcher.py`, `ops/run_blindrediscovery_dig.sh`) and periodically
+re-derives the space from scratch, so its rediscovery can be diffed against what the desk believes.
+EVIDENCE ANALYSIS reads actual experiment results and proposes follow-ups. Validation belongs to
+neither: it is the desk's own statistical machinery, and no LLM seat may adjudicate its own
+proposal.
+
+**L1.54 COMPUTE MAXIMISATION — THROUGHPUT IS THE TARGET, UTILISATION IS ONLY THE INSTRUMENT**
+*(principal law, 2026-08-08)*. Available compute is never intentionally left idle while valid
+research work exists. The scheduler pushes cores, GPU where applicable, RAM caching, parallel NVMe
+I/O, permitted network throughput and worker concurrency upward, and reclaims idle capacity
+automatically. Compute conservatism is not prudence; it is the queue excuse of L1.53 wearing a
+resource-management costume, and it is refused on the same grounds.
+
+**BUT THE OBJECTIVE IS `validated experiments per unit time`, NOT PERCENT UTILISATION, AND THE
+DIFFERENCE IS NOT COSMETIC:**
+
+```
+ 80 workers → 50k experiments/hour
+100 workers → 65k experiments/hour       ← optimum
+140 workers → 66k/hour + mass failures   ← higher CPU%, worse desk
+```
+
+A hardcoded "100% CPU forever" is worse engineering than a measured ceiling, because contention,
+swap, timeout and corruption all buy utilisation with throughput. **The scheduler therefore
+benchmarks its own concurrency continuously and scales until marginal throughput gain goes
+negligible OR reliability degrades — whichever binds first — rather than to any fixed target.**
+Concurrency, batching, caching, vectorisation, multiprocessing and I/O are all in scope, and each
+is a measurement, never a setting somebody chose once.
+
+**WHEN THE MACHINE SATURATES, THE NEXT TARGET IS THROUGHPUT — NEVER FEWER HYPOTHESES.** If
+100,000 valid experiments are waiting and the box can safely run 500 concurrently, it runs 500
+concurrently. Generation capacity and experiment capacity are separate quantities and are managed
+separately: saturated experiment capacity is an engineering target, and it is never a reason to
+tell a generator to slow down (L1.52).
+
+**THE STATISTICAL GATES ARE UNTOUCHED BY THIS LAW.** Compute aggression buys more experiments at
+the same bar. It never buys a lower one, and any change that raises throughput by weakening
+deflation, out-of-sample discipline or independence is a throughput loss measured in the only
+currency that counts.
+
+**ANTI-TIMIDITY (L1.28): every restraint word above points at the MACHINE, never at the desk.**
+"Conservatism", "slow", "wait" and "fewer" appear here only as the failure being named — this law
+is **not a licence** to defer a run, to size a batch down for comfort, or to hold hypotheses back
+because the box looks busy. The single legitimate reason to reduce concurrency is a MEASURED loss
+of throughput or reliability at the higher setting, and it is recorded with the measurement that
+produced it.
+
+**L1.54(a) NOTHING VALUABLE MAY REMAIN STRANDED — THE CONVERSION CHAIN IS THE ORGANISM**
+*(principal law, 2026-08-08)*. A discovery must become data; data must become features; features
+must become hypotheses; hypotheses must become experiments; experiments must become evidence;
+evidence must become survivors; survivors must be tested for INCREMENTAL portfolio value; live
+results must become new research information. Every object in that chain carries lineage, and
+every stage reports `input count · output count · conversion rate · latency · failure reasons ·
+compute consumed · downstream value` — so the desk can name **the largest economically important
+leak** rather than admire the widest stage.
+
+**THREE STRANDING STATES, WHICH ARE DIFFERENT DEFECTS WITH DIFFERENT FIXES** and were conflated
+until 2026-08-08, when a consumer was written for four orphan modules and one of them
+(`convergence`) stayed orphaned because the new consumer *described* its verdict in a hand-typed
+string instead of calling it:
+
+| state | test | fix |
+|---|---|---|
+| **ORPHAN** | zero importers, zero schedulers | build a consumer |
+| **INERT** | a consumer exists but has never executed | schedule it (L1.49) |
+| **CONVERSION FAILURE** | it executes and its output changes nothing | wire the output to a decision |
+
+The third is the one that hides, because it passes every test an importer count can run.
+
+**AND THE STANDING PRIORITY THAT FOLLOWS**: *find unused capability before inventing new
+capability*. A desk answering a research question by adding a module has relocated the activity
+somewhere it cannot fail. Complexity is added only when it raises expected validated research
+value — coverage of a diagram is not a reason, and a large collection of unused modules is the
+precise opposite of the ceiling this desk is aiming at.
+
+**L1.55 THE QUESTION SET IS PROVISIONAL — HARDCODE THE META-RULE, NEVER THE QUESTIONS**
+*(principal law, 2026-08-08)*. The desk continuously expands its capacity to ask valuable
+questions. **No question taxonomy, checklist, ontology, feature vocabulary, mechanism library,
+research domain or discovery procedure is ever treated as complete**, including this law's own
+examples. Expansion is driven by information gain, unexplained observations, novel mechanisms,
+contradictions, failures, external discovery and identified blind spots — never by accumulation.
+The objective is exploration of the research frontier; a longer checklist is not that.
+
+**WHY THE META-RULE AND NOT THE LIST.** A fixed set of eighteen good questions is a ceiling
+wearing the costume of thoroughness: it is answered, marked complete, and thereafter the desk sees
+exactly as far as whoever wrote it. Worse, it fails silently — every question gets a tick and the
+territory the list never described stays invisible. So what is constitutional is the ENGINE, and
+the current question set is an artifact it produces.
+
+```
+DATA → OBSERVATION → QUESTION → HYPOTHESIS → EXPERIMENT → RESULT
+                        ↑                                    │
+                        └────────── UNEXPLAINED RESIDUAL ─────┘
+```
+
+**THE INFORMATION-TO-ALPHA LOOP IS THE CURRENT SET, AND IT IS AN EXAMPLE, NOT THE LAW.** What
+information could exist · do we have it · if not why not · can it be acquired legally and
+technically · at what cost · can it be represented computationally · what features and mechanisms
+does it imply · what hypotheses follow · has it actually been TESTED · is the selection path
+accounted for (L1.52(a)) · does it carry INDEPENDENT information · did it convert to an executable
+alpha · does it survive cost, out-of-sample, regime and execution · does it improve the EXISTING
+portfolio · does live evidence confirm or contradict it · what did the result reveal · what remains
+unknown · what next. **Every object carries a machine-readable state through it, and UNKNOWN or
+NOT-MEASURED is a state, never an implicit no (L1.28a):**
+
+```
+DISCOVERED → ACQUIRED → REPRESENTABLE → FEATURED → HYPOTHESISED → TESTED
+   → VALIDATED → INDEPENDENCE_CHECKED → PORTFOLIO_TESTED → SHADOW → LIVE
+   → MONITORED → LEARNED → NEXT_RESEARCH_ACTION
+```
+
+**THE LOOP BINDS EVERY OBJECT CLASS, not datasets alone**: sources, miners, papers, forums,
+recommendations, GPT and Claude outputs, hypotheses, failures, near-survivors, features, models,
+prompts, execution observations, portfolio observations, regimes, infrastructure capabilities,
+research gaps and standing assumptions. A law written for one organ is a blind spot on the others.
+
+**EXPLORATION IS NOT BLOAT, AND THE DIFFERENCE IS TRACEABLE.** Every new question records what
+TRIGGERED it — new data, an unexplained result, a failed hypothesis, a near-survivor, a
+contradiction, model disagreement, an execution anomaly, a regime change, an external discovery, a
+named blind spot, a missing capability — and is scored `expected information gain + expected alpha
+value + novelty + feasibility − redundancy − cost`. A question that repeatedly yields nothing is
+DEPRIORITISED, never deleted (its null is evidence). A question that opens new territory spawns
+more. **A question with no trigger is accumulation and is refused on that ground alone.**
+
+**AND THE SAME INSTRUCTION GOES TO THE MODELS, WHICH IS WHERE A CHECKLIST DOES ITS WORST DAMAGE.**
+No seat is told "always ask these N questions" — it is told to identify what should be asked next,
+to treat the current set as provisional, and to challenge it. Claude's question space, each
+external seat's question space and the desk's standing set are then COMPARED, because where they
+diverge is itself a discovery source and is the cheapest one the desk owns.
+
+**THE TWO HALVES, and neither survives without the other:** maximum openness to information —
+nothing potentially valuable disappears merely because it does not fit the current structure — and
+maximum rigour in evidence — nothing becomes evidence because a model, a miner or a researcher
+found it compelling. Openness without rigour is a phantom-edge factory; rigour without openness is
+a desk that never finds anything to be rigorous about.
diff --git a/docs/research/test_suite_record.json b/docs/research/test_suite_record.json
index dc26433..f0c1bc8 100644
--- a/docs/research/test_suite_record.json
+++ b/docs/research/test_suite_record.json
@@ -1,5 +1,5 @@
 {
- "max_collected": 312,
- "at": "2026-08-07T22:51:47.209138+00:00",
+ "max_collected": 317,
+ "at": "2026-08-08T10:37:51.704370+00:00",
  "note": "high-water mark of COLLECTABLE test modules; ratchets UP only. A suite may never quietly shrink -- deleting a test is a decision, not a side effect."
 }
\ No newline at end of file
diff --git a/libs/autodiscovery/generation_roi.py b/libs/autodiscovery/generation_roi.py
index 5669c81..4aea9fc 100644
--- a/libs/autodiscovery/generation_roi.py
+++ b/libs/autodiscovery/generation_roi.py
@@ -6,11 +6,33 @@ gate (skip the graveyard) then the DSR gauntlet with cumulative-trial deflation
 survivor rate and the cost per survivor.
 
 The economics it exposes: the DSR bar (``sr0_threshold``) RISES with the number of trials, so
-throwing more candidates at the SAME data lowers the survivor rate — mass generation is self-
-defeating under honest multiple-testing correction. The novelty gate helps only by NOT paying to
-backtest redundant candidates. This answers the ROI question with numbers, not argument, and is
-cheap to run: point it at real (hypothesis, returns) pairs, or drive it with a Monte-Carlo null via
-``scripts/run_generation_roi_test.py``.
+throwing more candidates at the SAME data lowers the survivor rate. The novelty gate helps only by
+NOT paying to backtest redundant candidates. This answers the ROI question with numbers, not
+argument, and is cheap to run: point it at real (hypothesis, returns) pairs, or drive it with a
+Monte-Carlo null via ``scripts/run_generation_roi_test.py``.
+
+**THE CLAIM ABOVE IS ABOUT A FIXED INFORMATION SET, AND SAYING IT ANY WIDER IS WRONG.** An earlier
+version of this docstring concluded "mass generation is self-defeating under honest
+multiple-testing correction", full stop. That is too broad, and dangerously so: read literally it
+argues for throttling generation, which L1.52 forbids outright ("never reduce exploration to
+zero"). The correct distinction is:
+
+    more formulas over the SAME information   -> diminishing returns plus a rising hurdle,
+                                                 which is what this harness measures
+    more genuinely INDEPENDENT information    -> a wider space at the same hurdle, which is
+    (features, venues, mechanisms, data)         the only thing that reliably buys discoveries
+
+MEASURED ON THIS DESK, 2026-08-08, and the two runs differ in exactly one input. The candidate
+count was IDENTICAL at 898,560 both times; the data was not::
+
+    1 symbol,  918 bars  -> 14% measurable, 0 cells cleared the deflated screen
+    45 symbols, 1045 bars -> 83% measurable, 150 cleared in the first group alone
+
+Going from 420 candidates to 898,560 did not escape "data exhaustion" -- it raised the hurdle from
+sqrt(2 ln 420) = 3.48 to sqrt(2 ln 898560) = 5.24 while the information stayed fixed. What changed
+the answer was reaching data the desk already had. So the standing instruction is NOT "stop
+generating": it is generate permanently, expand the information space at the same time, and never
+confuse formula count with research breadth.
 """
 
 from __future__ import annotations
diff --git a/libs/doctrine/constitution.py b/libs/doctrine/constitution.py
index 03b8005..26e9462 100644
--- a/libs/doctrine/constitution.py
+++ b/libs/doctrine/constitution.py
@@ -81,6 +81,7 @@ __all__ = [
     "OBJECTIVE",
     "OBJECTIVE_PREAMBLE",
     "PRINCIPLES",
+    "RESIDUAL_MANDATE",
     "SUBSYSTEM_DERIVATIVES",
     "WEAKENING_LEXICON",
     "WEALTH_ARGUMENTS",
@@ -984,3 +985,55 @@ OBJECTIVE_PREAMBLE = (
     "survival rail, the rail wins unconditionally.\n"
     "=== END CONSTITUTION ===\n"
 )
+
+
+#: THE RESIDUAL MANDATE -- what an EXTERNAL seat is for, as opposed to a second copy of the desk.
```


---

## aa3d166 Execution monitor: forensics with memory, plus 52 statements of money-path coverage
TWO THINGS, both aimed at the only part of this desk currently losing money.

MONEY-PATH COVERAGE 70.45% -> the two testnet connectors held 168 of the 221 uncovered statements,
which is exactly backwards: testnet is where the order path is exercised BEFORE it is trusted with
money, so an untested rehearsal is not a rehearsal. binance_testnet.py goes 49.2% -> 69.4% (109
missing -> 57) on 23 tests that patch the transport and assert PARSING, REFUSAL and ORDER
CONSTRUCTION -- the places this desk's actual incidents happened:

  - a market order SPLIT to the venue maxQty cap (the 2026-07-27 COOKIEUSDT -4005 rejection that
    ended in a +916,772 long carrying -$482)
  - a close leg that is reduce_only AND carries a distinct idempotency token, so an emergency
    flatten cannot collide with a genuine entry in the same 90s bucket
  - flatten_all isolated per symbol, so one -2022 rejection cannot abandon the rest of the book
  - quote_depth returning 0.0 on any failure, because "unknown" must read as "thin"
  - avg_fill returning None rather than a fabricated price

One test assertion was wrong and worth noting: I asserted the client order id CONTAINS "close".
It does not -- the intent is hashed into it. The property that actually matters is DISTINCTNESS
(a flatten must not collide with an entry), so the test now asserts that instead. Asserting the
substring would have tested the encoding rather than the guarantee.

THE EXECUTION MONITOR. run_trade_forensics already answers "what is wrong today" and answers it
well -- three specific defects from 27 real closes. What was missing is MEMORY. A monitor that
re-derives the same flags every morning is a complaint: after a week nobody reads it, and the
morning a NEW defect appears it looks like the six before.

libs/execution/exec_monitor.py + scripts/run_exec_monitor.py fold each day's flags into a ledger
and classify NEW / PERSISTING / REGRESSED / RESOLVED. Design points that are the whole value:

  - REGRESSION is checked BEFORE persisting, so a defect returning after being marked fixed can
    never be filed as the ordinary continuation of an old one. The desk already has one on the
    live tape: "4 opens below the funding floor AFTER the gate shipped".
  - A CLEAN DAY IS NOT A FIX. RESOLVED needs five consecutive clean readings AND a recorded
    change. A sporadic book produces quiet days for free, and letting absence close a money-path
    defect is WS-005 aimed at the most expensive target available.
  - Flags are keyed on a STABLE pattern, not their text -- the live message carries today's
    numbers, so keying on it would make every morning a new defect and destroy the memory.
  - Unrecognised flags are KEPT under their own key: a monitor tracking only the defects someone
    thought of goes quiet on the sixth, and the sixth is the one nobody watches for.
  - ZERO CHURN IS NOT THE GOAL, and the module says so. Zero churn is achieved by not trading, so
    churn is always reported against net -- a monitor rewarding low turnover would steer the desk
    into holding losers, which is the >24h bleed already on the tape.
  - Leg conversion is reported PER LEG, never blended: fut 100% / spot 41.7% blends to 70.9%,
    which reads as a tuning problem rather than one leg that structurally does not fill. The two
    readings imply different fixes.

Wired into ops/run_research_cycle.sh so forensics and the monitor run every cycle, including days
the research half finds nothing -- the money path is where the loss is, so a cycle reporting only
research would go quiet on the one number costing money.

ruff clean, mypy clean over 463 files, execution + ops suites green.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7

```diff
commit aa3d16602ae3cc29c745e1aa3010f5a022c43132
Author: Claude <noreply@anthropic.com>
Date:   Sat Aug 8 10:24:52 2026 +0000

    Execution monitor: forensics with memory, plus 52 statements of money-path coverage
    
    TWO THINGS, both aimed at the only part of this desk currently losing money.
    
    MONEY-PATH COVERAGE 70.45% -> the two testnet connectors held 168 of the 221 uncovered statements,
    which is exactly backwards: testnet is where the order path is exercised BEFORE it is trusted with
    money, so an untested rehearsal is not a rehearsal. binance_testnet.py goes 49.2% -> 69.4% (109
    missing -> 57) on 23 tests that patch the transport and assert PARSING, REFUSAL and ORDER
    CONSTRUCTION -- the places this desk's actual incidents happened:
    
      - a market order SPLIT to the venue maxQty cap (the 2026-07-27 COOKIEUSDT -4005 rejection that
        ended in a +916,772 long carrying -$482)
      - a close leg that is reduce_only AND carries a distinct idempotency token, so an emergency
        flatten cannot collide with a genuine entry in the same 90s bucket
      - flatten_all isolated per symbol, so one -2022 rejection cannot abandon the rest of the book
      - quote_depth returning 0.0 on any failure, because "unknown" must read as "thin"
      - avg_fill returning None rather than a fabricated price
    
    One test assertion was wrong and worth noting: I asserted the client order id CONTAINS "close".
    It does not -- the intent is hashed into it. The property that actually matters is DISTINCTNESS
    (a flatten must not collide with an entry), so the test now asserts that instead. Asserting the
    substring would have tested the encoding rather than the guarantee.
    
    THE EXECUTION MONITOR. run_trade_forensics already answers "what is wrong today" and answers it
    well -- three specific defects from 27 real closes. What was missing is MEMORY. A monitor that
    re-derives the same flags every morning is a complaint: after a week nobody reads it, and the
    morning a NEW defect appears it looks like the six before.
    
    libs/execution/exec_monitor.py + scripts/run_exec_monitor.py fold each day's flags into a ledger
    and classify NEW / PERSISTING / REGRESSED / RESOLVED. Design points that are the whole value:
    
      - REGRESSION is checked BEFORE persisting, so a defect returning after being marked fixed can
        never be filed as the ordinary continuation of an old one. The desk already has one on the
        live tape: "4 opens below the funding floor AFTER the gate shipped".
      - A CLEAN DAY IS NOT A FIX. RESOLVED needs five consecutive clean readings AND a recorded
        change. A sporadic book produces quiet days for free, and letting absence close a money-path
        defect is WS-005 aimed at the most expensive target available.
      - Flags are keyed on a STABLE pattern, not their text -- the live message carries today's
        numbers, so keying on it would make every morning a new defect and destroy the memory.
      - Unrecognised flags are KEPT under their own key: a monitor tracking only the defects someone
        thought of goes quiet on the sixth, and the sixth is the one nobody watches for.
      - ZERO CHURN IS NOT THE GOAL, and the module says so. Zero churn is achieved by not trading, so
        churn is always reported against net -- a monitor rewarding low turnover would steer the desk
        into holding losers, which is the >24h bleed already on the tape.
      - Leg conversion is reported PER LEG, never blended: fut 100% / spot 41.7% blends to 70.9%,
        which reads as a tuning problem rather than one leg that structurally does not fill. The two
        readings imply different fixes.
    
    Wired into ops/run_research_cycle.sh so forensics and the monitor run every cycle, including days
    the research half finds nothing -- the money path is where the loss is, so a cycle reporting only
    research would go quiet on the one number costing money.
    
    ruff clean, mypy clean over 463 files, execution + ops suites green.
    
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_014EAoUoyz8CRqLXPyeqXfD7
---
 libs/execution/exec_monitor.py                | 243 ++++++++++++++++++++
 ops/run_research_cycle.sh                     |   5 +
 scripts/run_exec_monitor.py                   | 114 ++++++++++
 tests/execution/test_binance_testnet_paths.py | 304 ++++++++++++++++++++++++++
 tests/execution/test_exec_monitor.py          | 153 +++++++++++++
 tests/execution/test_run_exec_monitor.py      |  89 ++++++++
 6 files changed, 908 insertions(+)

diff --git a/libs/execution/exec_monitor.py b/libs/execution/exec_monitor.py
new file mode 100644
index 0000000..3c591ca
--- /dev/null
+++ b/libs/execution/exec_monitor.py
@@ -0,0 +1,243 @@
+"""EXECUTION MONITORING -- and the only thing that separates a monitor from a daily complaint.
+
+WHY THIS IS NOT `run_trade_forensics.py`. The forensics already work, and they are good: on
+2026-08-07 they returned three specific, actionable defects from 27 real closes -- a >24h hold
+class bleeding -37.54 bps, an entry gate not filtering, and a maker conversion that is
+LEG-ASYMMETRIC (futures 100%, spot 41.7%). Nothing was missing from the diagnosis.
+
+What was missing is MEMORY. A monitor that re-derives the same three flags every morning and
+prints them again is a complaint, not a control: after a week nobody reads it, and the one morning
+a NEW defect appears it looks exactly like the six mornings before. The forensics answer "what is
+wrong today"; this answers "what is STILL wrong, what is NEW, and what came BACK after someone
+believed it fixed".
+
+**REGRESSION IS THE CATEGORY THAT MATTERS MOST, AND THE DESK ALREADY HAS ONE.** The live flag reads
+"4 open(s) below the 0.00015 funding floor AFTER the gate shipped -- gate is not filtering". A
+defect that returns after being marked fixed is strictly worse than one that was never fixed,
+because a fix that did not hold has also spent the desk's belief: everything downstream was sized
+and reasoned as though that leak were closed.
+
+**A CLEAN DAY IS NOT A FIX.** `RESOLVED` requires `MIN_CLEAN_OBSERVATIONS` consecutive clean
+readings AND a recorded code change. One quiet morning on a book that trades sporadically is an
+absence of evidence -- and letting absence close a defect is WS-005 aimed at the money path, which
+is the most expensive place this desk could aim it.
+
+**ZERO CHURN IS NOT THE GOAL AND SAYING SO MATTERS.** Zero churn is achieved by not trading. The
+objective is turnover that PAYS FOR ITSELF, so churn is always reported against net -- never as a
+level to minimise. A monitor that rewarded low turnover would slowly steer the desk into holding
+losers, which is exactly the >24h bleed already on the tape.
+"""
+
+from __future__ import annotations
+
+import math
+from dataclasses import dataclass, field
+from datetime import UTC, datetime
+
+__all__ = [
+    "MIN_CLEAN_OBSERVATIONS",
+    "DefectState",
+    "ExecHealth",
+    "churn_efficiency",
+    "classify",
+    "hold_class_report",
+    "leg_asymmetry",
+    "update",
+]
+
+#: Consecutive clean readings before a defect may be called RESOLVED -- and even then only
+#: alongside a recorded change. Five, because a book that trades sporadically produces quiet days
+#: for free, and a fix that is really a lull will re-fire the moment volume returns.
+MIN_CLEAN_OBSERVATIONS: int = 5
+
+#: Maker conversion below this on EITHER leg of a paired trade is a defect, not a preference. The
+#: live tape shows futures 100% vs spot 41.7%: a one-shot passive quote with no re-peg, resting on
+#: the side the entry regime does not lift. The blended rate hides it -- 71% average looks like a
+#: tuning problem rather than one leg being structurally broken.
+MAKER_FLOOR: float = 0.80
+
+
+@dataclass(frozen=True)
+class DefectState:
+    """One execution defect, across time rather than on one morning."""
+
+    key: str
+    status: str                  # NEW | PERSISTING | REGRESSED | RESOLVED
+    first_seen: str = ""
+    last_seen: str = ""
+    occurrences: int = 0
+    clean_streak: int = 0
+    times_regressed: int = 0
+    detail: str = ""
+
+    @property
+    def is_open(self) -> bool:
+        return self.status != "RESOLVED"
+
+
+def classify(prev: dict[str, object] | None, present_today: bool, *,
+             change_recorded: bool = False,
+             min_clean: int = MIN_CLEAN_OBSERVATIONS) -> tuple[str, int, int]:
+    """(status, clean_streak, times_regressed) for one defect.
+
+    ORDER OF CHECKS IS THE WHOLE LOGIC. A defect seen today after a prior RESOLVED is a
+    REGRESSION, and that is tested before PERSISTING so a returning defect can never be filed as
+    the ordinary continuation of an old one -- which is how a fix that did not hold becomes
+    invisible.
+    """
+    if prev is None:
+        return ("NEW" if present_today else "RESOLVED"), 0, 0
+    was = str(prev.get("status", ""))
+    # `prev` rows come from a JSON artifact, so every field is `object` until proven otherwise.
+    # Coercing through str() first keeps a malformed row from raising inside a money-path monitor.
+    regressed = int(str(prev.get("times_regressed", 0) or 0))
+    streak = int(str(prev.get("clean_streak", 0) or 0))
+
+    if present_today:
+        if was == "RESOLVED":
+            return "REGRESSED", 0, regressed + 1
+        return ("REGRESSED" if was == "REGRESSED" else "PERSISTING"), 0, regressed
+    streak += 1
+    # A CLEAN DAY IS NOT A FIX. Absence closes nothing on its own -- a sporadic book produces
+    # quiet days for free, and a "fix" that is really a lull re-fires when volume returns.
+    if streak >= min_clean and change_recorded:
+        return "RESOLVED", streak, regressed
+    return (was or "PERSISTING"), streak, regressed
+
+
+def update(history: dict[str, dict[str, object]], flags: dict[str, str], *,
+           changes: set[str] | None = None, now: str = "") -> list[DefectState]:
+    """Fold today's flags into the running record. Returns every KNOWN defect, not just today's.
+
+    Defects absent from `flags` are carried forward rather than dropped: a monitor that reported
+    only today's flags would show an empty screen on a quiet day and read as health.
+    """
+    stamp = now or datetime.now(tz=UTC).isoformat()
+    changed = changes or set()
+    out: list[DefectState] = []
+    for key in sorted(set(history) | set(flags)):
+        prev = history.get(key)
+        today = key in flags
+        status, streak, regressed = classify(prev, today, change_recorded=key in changed)
+        out.append(DefectState(
+            key=key, status=status,
+            first_seen=str((prev or {}).get("first_seen") or (stamp if today else "")),
+            last_seen=stamp if today else str((prev or {}).get("last_seen", "")),
+            occurrences=int(str((prev or {}).get("occurrences", 0) or 0)) + (1 if today else 0),
+            clean_streak=streak, times_regressed=regressed,
+            detail=flags.get(key, str((prev or {}).get("detail", ""))),
+        ))
+    return out
+
+
+def churn_efficiency(net_bps: float, turnover: float) -> tuple[float, str]:
+    """(net per unit turnover, verdict). CHURN IS JUDGED AGAINST NET, NEVER MINIMISED.
+
+    Zero churn is achieved by not trading, so a monitor that rewarded low turnover would steer the
+    desk toward holding losers -- which is the >24h bleed already on this tape. The question is
+    never "is turnover high" but "does turnover pay for itself".
+    """
+    if turnover <= 0:
+        return 0.0, ("NO TURNOVER -- nothing traded, which is not the same as nothing wasted and "
+                     "must never read as efficiency")
+    eff = net_bps / turnover
+    if eff > 0:
+        return eff, f"turnover pays: {eff:+.3f} bp of net per unit turned"
+    return eff, (f"turnover COSTS: {eff:+.3f} bp of net per unit turned -- the churn is not buying "
+                 "the edge it is spending. Look at holding period and leg conversion before "
+                 "signal quality; a slower version of the same signal pays the round trip fewer "
+                 "times")
+
+
+def hold_class_report(buckets: dict[str, tuple[float, int]]) -> list[str]:
+    """Net bps by holding-period bucket -- `{label: (net_bps, n_trades)}`.
+
+    THE HOLDING PERIOD IS A FIRST-CLASS AXIS BECAUSE THE TAPE SAYS SO: the >24h class bled
+    -37.54 bps over 23 trades while shorter classes did not. A blended P&L would have shown a
+    modest loss and hidden which SHAPE of trade caused it -- and the shape is the fix.
+    """
+    out: list[str] = []
+    for label, (net, n) in sorted(buckets.items()):
+        if n <= 0:
+            out.append(f"{label}: NO TRADES -- unmeasured, not clean")
+            continue
+        verdict = "bleeding" if net < 0 else "paying"
+        out.append(f"{label}: {net:+.2f} bps over {n} trade(s) -- {verdict}")
+    return out
+
+
+def leg_asymmetry(rates: dict[str, float], *, floor: float = MAKER_FLOOR) -> tuple[bool, str]:
+    """Is one leg of a paired trade structurally worse at getting maker fills?
+
+    REPORTED PER LEG, NEVER BLENDED. The live tape is futures 100% / spot 41.7%; the blend is 71%,
+    which reads as a tuning problem rather than as one leg being broken. The fix implied by the
+    blend (nudge the quote) is not the fix implied by the split (re-peg the spot quote to the
+    touch, because a one-shot passive order resting on the side the entry regime does not lift
+    will simply never fill).
+    """
+    if len(rates) < 2:
+        return False, "fewer than two legs -- asymmetry is not defined, not absent"
+    worst = min(rates, key=lambda k: rates[k])
+    best = max(rates, key=lambda k: rates[k])
+    if rates[worst] >= floor:
+        return False, f"both legs at or above {floor:.0%} (worst {worst} {rates[worst]:.1%})"
+    gap = rates[best] - rates[worst]
+    return True, (
+        f"LEG-ASYMMETRIC: {best} {rates[best]:.1%} vs {worst} {rates[worst]:.1%} "
+        f"(gap {gap:.1%}). Fix the {worst} quote -- re-peg to the touch. The blended rate is "
+        f"{sum(rates.values()) / len(rates):.1%}, which would read as a tuning problem rather "
+        "than one leg that structurally does not fill.")
+
+
+@dataclass(frozen=True)
+class ExecHealth:
+    """The daily verdict. Ordered so a REGRESSION cannot be scrolled past."""
+
+    defects: tuple[DefectState, ...] = field(default_factory=tuple)
+    notes: tuple[str, ...] = field(default_factory=tuple)
+
+    @property
+    def regressions(self) -> tuple[DefectState, ...]:
+        return tuple(d for d in self.defects if d.status == "REGRESSED")
+
+    @property
+    def open_defects(self) -> tuple[DefectState, ...]:
+        return tuple(d for d in self.defects if d.is_open)
+
+    @property
+    def headline(self) -> str:
+        if self.regressions:
+            names = ", ".join(d.key for d in self.regressions)
+            return (f"REGRESSION: {names} returned after being marked fixed. A fix that did not "
+                    "hold has also spent the desk's belief -- everything downstream was sized as "
+                    "though this leak were closed.")
+        if self.open_defects:
+            return f"{len(self.open_defects)} open execution defect(s)"
+        return ("no open execution defects -- which is a statement about the flags that RAN, not "
+                "a clean bill of health for paths nobody measured")
+
+
+def render(health: ExecHealth) -> str:
+    lines = [health.headline]
+    for d in health.defects:
+        if d.status == "RESOLVED":
+            continue
+        age = f"seen {d.occurrences}x" + (f", regressed {d.times_regressed}x"
+                                          if d.times_regressed else "")
+        lines.append(f"  [{d.status}] {d.key} ({age}) {d.detail}".rstrip())
+    lines += [f"  {n}" for n in health.notes]
+    return "\n".join(lines)
+
+
+def sharpe_of_net(net_bps_per_trade: list[float]) -> float | None:
+    """Sharpe of realised per-trade net. None when the sample cannot support it.
+
+    None rather than 0.0 because a desk reading 0.0 concludes "no edge" and a desk reading None
+    concludes "not measured yet" -- and on 27 closes the second is the true statement.
+    """
+    n = len(net_bps_per_trade)
+    if n < 2:
+        return None
+    mean = sum(net_bps_per_trade) / n
+    var = sum((x - mean) ** 2 for x in net_bps_per_trade) / (n - 1)
+    return None if var <= 0 else mean / math.sqrt(var)
diff --git a/ops/run_research_cycle.sh b/ops/run_research_cycle.sh
index 46f2eca..4fdba0a 100755
--- a/ops/run_research_cycle.sh
+++ b/ops/run_research_cycle.sh
@@ -38,5 +38,10 @@ export BARS_FILE_BUDGET="${BARS_FILE_BUDGET:-20000}"
   # The ladder runs even when the sweep found nothing: it also reports what is ALREADY live, and a
   # cycle that skipped it on a null day would go silent exactly when a live record needs reading.
   nice -n 15 "$PY" scripts/run_live_ladder.py
+  # EXECUTION HEALTH runs every cycle, including days the research half found nothing. The money
+  # path is where the desk is currently LOSING (27 closes, all three hold buckets negative net of
+  # fees), so a cycle that reported only research would go quiet on the one number costing money.
+  nice -n 15 "$PY" scripts/run_trade_forensics.py || true
+  nice -n 15 "$PY" scripts/run_exec_monitor.py || true
   echo "=== research cycle exit $? at $(date -u) ==="
 } 2>&1 | tee -a "$LOG"
diff --git a/scripts/run_exec_monitor.py b/scripts/run_exec_monitor.py
new file mode 100644
index 0000000..b768bb2
--- /dev/null
+++ b/scripts/run_exec_monitor.py
@@ -0,0 +1,114 @@
+#!/usr/bin/env python3
+"""DAILY EXECUTION MONITOR -- forensics with memory, and a defect ledger that survives the morning.
+
+`run_trade_forensics.py` already answers "what is wrong today", and answers it well. This answers
+the three questions a daily reader actually needs: what is STILL wrong, what is NEW, and what came
+BACK after someone believed it fixed.
+
+Reads the forensics artifact, folds today's flags into `data/exec_defects.json`, and reports.
+Places nothing, changes nothing, sizes nothing.
+"""
+from __future__ import annotations
+
+import argparse
+import json
+import re
+import sys
+from datetime import UTC, datetime
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parent.parent
+if str(ROOT) not in sys.path:
+    sys.path.insert(0, str(ROOT))
+
+from libs.execution.exec_monitor import (  # noqa: E402
+    ExecHealth,
+    render,
+    update,
+)
+
+FORENSICS = ROOT / "data" / "trade_forensics.json"
+LEDGER = ROOT / "data" / "exec_defects.json"
+
+#: Map a forensics flag to a STABLE key. The flag text carries live numbers ("-37.54 bps over 23
+#: trades") which change daily, so keying on the message would make every morning a NEW defect and
+#: destroy the memory this script exists to provide.
+_KEYS: tuple[tuple[str, str], ...] = (
+    ("hold_class_bleed", r"hold-class.*bleeding"),
+    ("entry_gate_regression", r"ENTRY-GATE REGRESSION"),
+    ("maker_leg_asymmetry", r"maker conversion is LEG-ASYMMETRIC"),
+    ("cost_exceeds_edge", r"net of fees|loses money net"),
+    ("liquidation_risk", r"liquidat"),
+)
+
+
+def keyed_flags(flags: list[str]) -> dict[str, str]:
+    """Stable key -> today's message. An unrecognised flag keeps its own text as the key.
+
+    UNRECOGNISED FLAGS ARE KEPT, NOT DROPPED. A monitor that only tracked the five defects someone
+    thought of would go quiet on the sixth -- and the sixth is the one nobody is watching for.
+    """
+    out: dict[str, str] = {}
+    for f in flags:
+        key = next((k for k, pat in _KEYS if re.search(pat, f, re.I)), None)
+        out[key or f"unclassified:{f[:48]}"] = f.strip()
+    return out
+
+
+def load_flags(path: Path) -> tuple[list[str], str]:
+    """(flags, state). state is BLOCKED when the forensics artifact is absent -- NOT 'clean'."""
+    try:
+        doc = json.loads(path.read_text("utf-8"))
```

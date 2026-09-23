@echo off
rem THE FRONTIER MEASUREMENT LANE (2026-09-12) -- six organs that were built and ran nowhere.
rem
rem III.16: unwired or idle is a defect, and "built" is not a status. Each of these has a main(),
rem writes an artifact and had no caller anywhere in the tree -- measured by grepping every .cmd,
rem .ps1, .sh and .manifest in the repo for their module names and getting nothing back.
rem
rem WHY ONE TASK AND NOT SIX. Every one of them is a pure MEASUREMENT: it reads artifacts the desk
rem already holds, writes a report, and touches no ledger, no sizing and no order. They share a
rem cadence for the same reason -- each answers a question whose truth moves on the scale of a
rem session calendar, not an hour, and re-deriving them hourly would spend the box's parquet IO
rem re-computing the same numbers.
rem
rem ORDER IS DELIBERATE. certificate_hygiene runs FIRST because it is the only one that mutates
rem anything (it evicts unrunnable certificates into their own file), and every organ after it
rem should read the registry it leaves behind rather than the one it found.
rem
rem NONE OF THEM TIGHTENS ANYTHING. forward_calibration states it outright: a high false-admission
rem rate is not licence to raise the bar, because that is a growth cut wearing a statistic. These
rem supply evidence to the CEO docket; the docket decides.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-FrontierAudit.log"
set "PY=C:\Program Files\Python314\python.exe"
cd /d C:\opt\quant
"%PY%" -u "desks\mt5\research\certificate_hygiene.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\book_forensics.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\pit_audit.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\forward_calibration.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\orthogonality.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\unknown_unknowns.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\world_model.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\representation_discovery.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\joint_evolution.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\negative_knowledge.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\frontier_map.py" --apply >>"%LOG%" 2>&1
rem THE THREE-RESOURCE LOOP, IN DEPENDENCY ORDER (F28 + F11/F27, 2026-09-12).
rem scaling_laws fits survivors per compute-hour, which is the ONLY input that gives compute
rem a price; budget_market quotes all three resources; meta_controller spends those prices on
rem nine kinds of action. Run out of order and the controller reads yesterday's prices.
rem scaling_laws returns UNMEASURED until the compute ledger holds seven days -- it held two
rem on the day this was wired, and that is a data limit rather than a defect.
"%PY%" -u -m libs.ops.scaling_laws >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\budget_market.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\market_ecology.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\information_value.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\execution_science.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\subhour_counterfactuals.py" --apply >>"%LOG%" 2>&1
rem BOTH HALVES OF CAPACITY (F21). capacity.py answers the LOWER bound -- the venue's
rem minimum lot forcing more risk per trade than the policy asked for, which its own
rem docstring rightly calls the binding constraint at this account size -- and it had no
rem runner and no contract since the day it was written. capacity_frontier answers the
rem upper bound in the only unit this venue supplies: how many multiples of today's round
rem trip each mechanism survives.
"%PY%" -u "desks\mt5\research\capacity.py" >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\capacity_frontier.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\meta_controller.py" --apply >>"%LOG%" 2>&1
rem RECURSIVE META-R&D (F25), immediately BEFORE the bench and the verifier so it records
rem the arena state as it stood this pass. Its three arenas are the bench, the adversary
rem and the credit record -- which is why it could not be built before them.
"%PY%" -u "desks\mt5\research\meta_rnd.py" --apply >>"%LOG%" 2>&1
rem THE BENCH RUNS LAST (F18), and the order is the point: every probe reads an artifact
rem this lane has just regenerated, so a stale report cannot be mistaken for a returned
rem defect. It reports UNMEASURABLE on an artifact older than the code that produces it.
rem THE EVIDENCE VAULT (F19). Seals each symbol's holdout tier ONCE, counts reveals, and
rem fingerprints the judge, engine, families, cost model and contract terms -- so a
rem verdict minted before any of them changed is visible as such.
"%PY%" -u "desks\mt5\research\evidence_vault.py" --apply >>"%LOG%" 2>&1
rem CAUSAL DISCOVERY (F16). The desk already enumerates rival explanations and has never
rem decided between them. A collider is the one orientation observational data can settle,
rem and the CONFLICT count is a diagnostic on the assumptions rather than noise.
"%PY%" -u "desks\mt5\research\causal_discovery.py" --apply >>"%LOG%" 2>&1
rem CREDIT FLOWS BACK TO THE SCIENTIST (F12). The chain was entirely on disk -- forward
rem clock, sleeve, certificate, docket row, source -- and nobody had walked it, so a
rem miner was rewarded for passing a screen and never asked what its output earned.
"%PY%" -u "desks\mt5\research\credit_assignment.py" --apply >>"%LOG%" 2>&1
rem THE ADVERSARY THAT LEARNS (F17). Each generation is ONE run_gauntlet over the whole
rem population, so two generations cost two dockets of 14 cells -- small against an
rem hourly sweep of thousands. The population PERSISTS, which is what makes it
rem co-evolution: when a gate tightens, the attacks that used to score lose their
rem fitness and the population moves.
"%PY%" -u "desks\mt5\research\adversary_evolution.py" --apply --generations 2 >>"%LOG%" 2>&1
rem GOVERNANCE PRICED (F24). missed_growth walks 22 rails against the growth curve and
rem capital_modifiers scores every applied multiplier; both existed, both were correct,
rem and neither was on a clock. modifier_counterfactuals prices the applied multipliers in
rem E[log W] at CONSTANT average heat, which is the unit F24 asks for.
"%PY%" -u "desks\mt5\research\missed_growth.py" >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\modifier_counterfactuals.py" --apply >>"%LOG%" 2>&1
rem THE STRUCTURAL VERIFIER (F26), beside the bench. The bench asks whether a defect the
rem desk survived has returned; this asks whether a property that must NEVER hold has
rem started holding. Different questions, and a desk needs both.
"%PY%" -u "desks\mt5\research\formal_invariants.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\quantbench.py" --apply >>"%LOG%" 2>&1
exit /b 0

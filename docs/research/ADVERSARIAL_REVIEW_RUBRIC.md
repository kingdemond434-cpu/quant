# Adversarial review rubric — the defect classes this desk actually ships

**Origin:** the "dual-brain" idea (have a second model with different blind spots review the
first's work). Correct in principle: *you cannot mark your own exam*.

**Why the rubric and not the tool.** The reviewing model is interchangeable — Codex, another
Claude, a person. What is not interchangeable is *knowing what to look for on this desk*. Every
class below was found here, in shipped code, usually by measurement after the fact. A generic
"review this code" prompt finds none of them; it finds style.

**On tooling.** OpenAI's Codex CLI is first-party and sandboxes by default (seccomp/Landlock on
Linux, no network, workspace-confined writes), so using it as the second reviewer carries no
supply-chain objection. The objection that stands is narrower and is about *configuration*:
never run any agent with permission checks disabled on a machine holding live exchange keys.
That is a property of the flag, not of the tool.

---

## The classes, each with the real instance that produced it

### 1. Computed but not consumed
A value is calculated every run and never reaches the decision.
- `CampaignGates.screen` — BY-FDR selection computed at `validation.py:379`, never gates.
- `discovery_score` — the whole composite objective, **zero production callers**; ranking is raw
  Sharpe.
- **Test:** for every computed quantity, grep its consumers. Not its definition — its *readers*.

### 2. Gate that fails open
The ambiguous branch permits the action.
- `beats_baselines` returns `True` when no benchmark is supplied, and **no production caller
  supplies one** — measured blocking 0.0% of pure asset-drift candidates.
- **Test:** for each gate, construct the input where it cannot decide. Does it block or allow?

### 3. One correction applied twice
Two mechanisms independently control the same error, compounding into an impassable bar.
- DSR deflated by `n_trials` *on top of* Romano-Wolf FWER over the same 420 candidates. Power at
  true Sharpe 2 was 0%.
- **Test:** list every gate's error model. Two gates controlling family-wise error over one
  family is a defect, not defence in depth.

### 4. Exit code mistaken for production
A process ended; nothing checked it produced.
- `certify_gauntlet.py` had no sys.path bootstrap, died on import under its own manifest line,
  and the BLOCKED artifact it was written to emit was never written either.
- **Test:** assert on the artifact's content and freshness, never on the return code.

### 5. Constant with no producer
A required input nothing computes.
- `parameter_plateau_score`, `half_life_days` — required by `discovery_score`, produced nowhere.
- `libs/discovery/__init__.py` documents `fragility.py`, `half_life.py`, `parameter_stability.py`,
  `correlation_engine.py` — **none of those files exist.**
- **Test:** for every named input and every module named in a docstring, confirm it exists and
  has a writer.

### 6. Objective gameable by partitioning
An optimiser reaches the stated goal by restructuring the problem rather than solving it.
- The strata planner fragmented into 34 minimum-size cohorts because a smaller cohort carries a
  smaller multiplicity deflation — evading the correction, and reporting a fictional 279× gain.
- **Test:** ask what the optimiser would do with an absurd amount of freedom. If the answer is
  degenerate, the objective is underspecified.

### 7. Filter validated at the wrong sample size
A rule of thumb imported without checking it holds at *our* dimensions.
- "OOS may not exceed IS by 30%" rejected 20–40% of genuine alphas at T=310, because a 70/30
  split makes the OOS estimate far noisier than the IS one. Studentising fixed it.
- **Test:** re-derive every borrowed threshold at this desk's actual T and N.

### 8. Dropped candidate scored as a small loss
An objective that treats "not tested" as though it were "tested and failed".
- The first window planner chose 4,000 obs × 16 candidates: 99.9% power, **404 of 420 hypotheses
  never tested at all.** A dropped candidate has *zero* discovery probability.
- **Test:** does the objective count what it excludes?

### 9. Estimator floor reported as a finding
A statistic that is biased by construction at this data shape, read as signal.
- Eigenvalue N_eff reads ~178 of 420 on *perfectly independent* columns when T < N, because the
  correlation matrix has rank ≤ T. Reporting that as "only 178 independent tests" would be an
  artifact dressed as a discovery.
- **Test:** run the estimator on data where the true answer is known. That is the floor.

### 10. Verdict that depends on the machine, not the code
- The law gate ran a consumer before its producer; the matrix was gitignored, so the gate passed
  only on machines that had run it before. Red on CI ten times running.
- **Test:** does it pass in a fresh clone, twice, in either order?

---

## How to run it

Give the reviewer the diff **and this file**, and require a verdict per class — including
"not applicable, because…". A reviewer allowed to return prose returns prose.

Then the desk's own rule applies to the review itself: **a finding is not a finding until it is
measured.** Three of the classes above were caught here by an adversarial pass; two of *those*
were wrong on first inspection and only survived after the measurement agreed. Treat a reviewer's
claim as a hypothesis, not a verdict — including when the reviewer is a different model, and
including when it is confident.

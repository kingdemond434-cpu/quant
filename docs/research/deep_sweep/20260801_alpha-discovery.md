# DEEP COLD AUDIT — ALPHA-DISCOVERY — 2026-08-01

STATUS: COMPLETE

_Auditor: weekly deep cold audit (core doctrine v2). Subsystem: alpha-discovery — hypothesis
diversity, unexplored market behaviours, crowded themes, neglected regimes, cross-asset transfer,
temporal-resolution gaps, feature interactions, regime conditioning, causal-vs-correlational
assumptions, hypothesis redundancy, negative-result reuse, abandoned-idea reassessment,
falsification quality, ignored markets/public information, untestable signals. READ-ONLY. Every
claim carries its proving command. Findings appended incrementally as verified — if this run is cut
off, what is written is the deliverable._

_Predecessor: `docs/research/deep_sweep/20260731_alpha-discovery.md` (F1–F18, O1–O10, T1–T6, the
first completed alpha-discovery audit). This sweep's FIRST duty is REGRESSION: which of yesterday's
findings actually moved, measured from artifacts, not claims. Its SECOND is new ground._

## THE ONE-SENTENCE VERDICT

**The desk's central strategic fact — "420 tested, 0 survivors, the price space is picked clean" —
is now measurably UNINFORMATIVE: the campaign design has ~0.25% power per candidate against a true
annual Sharpe of 2.0, so 0 survivors is the EXPECTED result of that design even in a market full of
world-class edges** — and the module that measures and fixes this was written yesterday, is correct,
and is called by nothing.

## SCORES (subsystem: alpha-discovery)

- **current_capability_pct: 30%** (from 35% yesterday). **The drop is information, not decay** — three
  things genuinely improved (the gate is certified, 348 dead campaigns retired, 12/12 slots filled)
  while three defects that were invisible yesterday were found: the H8 timeframe is structurally
  unreachable (F6), the universe is capped at 10.8% by a default argument (F7), and the resurrection
  feeder selects zero on arithmetic (F8). What genuinely works: falsification *content* (95%
  mechanism-of-death, 97% lessons), the de-contamination gate, pre-registration discipline (13/13
  state kill criteria before compute), and engineering honesty in new modules.
- **practical_ceiling_estimate: 88%** (up from 85%). Raised because F2 reclassifies history depth from
  data poverty to a wiring defect — 1,808 observations per candidate are already on disk. The residual
  12% is genuine crypto market-history shortness and irreducibly slow forward accrual.
- **ceiling_gap: 58 points**, of which the large majority is one-line and one-file work in front of
  already-built, already-tested machinery. Nine of twelve opportunities are wires, not builds.
- **opportunity_cost_1y: the highest on the desk after launch itself.** At 0.25% per-candidate power
  the campaign detects ~1 alpha per 420 tested *even in a market full of Sharpe-2 edges*; at 37.9% it
  detects ~159. A year at the current setting is a year of structurally-zero validated births, which
  under L1.30 is a countdown that reads healthy every single day until the last live edge dies. Add:
  the entire intraday dimension unexpressible, 83.8% of desk data untested, and 24,201 unlock events
  unscreened.
- **confidence: 0.85 on findings** — every claim carries a command run this session, and I
  independently re-verified every load-bearing sub-sweep claim (the timeframe hash, the `limit=30`
  default, the age arithmetic, the slot tuples, the zero-consumer greps) rather than relaying them.
  **0.5 on the scores**, which are judgment over verified parts.
- **unknown_unknown_score: 0.45** (from 0.55). Four independent sub-sweeps converged on ONE shape —
  *built, tested, correct, and called by nothing* — rather than diverging, which is the signal a space
  is nearing exhaustion. It is not lower because F6/F7/F8 were entirely invisible to yesterday's
  audit, so the base rate of hidden one-line blockers is demonstrably above zero.
- **info_gain_if_investigated: ~1.0 for T2** (the real-peer × window certification delta). It
  separates "the gate", "the peers" and "the window" as competing explanations for 420/0 — the desk's
  central strategic question — into a 2×2 where every cell is decisive.
- **expected_alpha_contribution:** direct MEDIUM-HIGH (O8's unlock events is a clean, forced-agent
  mechanism nobody has touched; O2 opens 3,486 candidates plus an entire untested resolution);
  indirect VERY HIGH (O1 changes the detection power of every test the desk will ever run).
- **expected_compounding_contribution: highest on the desk after launch.** O1, O3, O6, O9 and O12 are
  multipliers on every future screen, every novelty check and every recorded experiment.
- **CEILING EXPANSION.** The 88% ceiling is set by a **methodological** assumption — *"a campaign is a
  rectangular matrix of aligned returns"* — and a **organizational** one — *"screens are hand-run."*
  Neither is technological and neither waits on 2–3 year compute. Drop the first and T becomes
  per-candidate (F2); drop the second and Stage-A output stops being a function of whether a session
  happened to run something (F4). With both dropped the ceiling is ~95% and the residual is only the
  true shortness of crypto history.

## 0. REGRESSION — WHAT MOVED SINCE 2026-07-31

Yesterday's audit shipped F1–F18 and O1–O10. Measured from artifacts, not claims.

| item | yesterday | today (2026-08-01) | verdict |
|---|---|---|---|
| **O1** horizon-scaled `ic_min` | proposed | `libs/research/axis_screen.py` untouched since 2026-07-29 | **NOT DONE** |
| **O2/T2** re-score the 420 under fixed gate | proposed | `research_candidates.updated_at` == `created_at` for all 434 | **NOT DONE** |
| **O3** wire the resurrection loop | proposed | `graveyard_resurrection_queue.json` still n=44, updated 07-31T07:24 | **NOT DONE** |
| **O4a** retire the dead v1 campaigns | proposed | **all 348 terminal-marked 2026-07-31 per R0009** | **DONE** |
| **O4b** repoint the phantom-DB refs | proposed | not re-checked this sweep (delegated) | see §2 |
| **O5/T6** positive controls on the gate | never existed | **`reports/gauntlet_certification.json` exists, 2026-08-01T01:35Z, both halves** | **DONE — the single biggest move of the day** |
| **O6** novelty-gate TF-IDF swap | proposed | delegated sub-sweep | see §2 |
| **O7/T4** cross-asset hindsight audit | proposed | no artifact found | **NOT DONE** |
| **O8** intraday dimension | proposed | no 1m ingestion artifact | **NOT DONE** |
| **O9** mechanism tag at experiment time | proposed | delegated sub-sweep | see §2 |
| **O10** untestable-signals registry | proposed | no artifact | **NOT DONE** |

**Score: 2 of 11 moved.** But the two that moved are not equal to the nine that did not — O5 answered
the question the whole subsystem turns on, and it is worth more than the rest combined. That is the
correct reading, and it is also why this report's centre of gravity has shifted from "what should we
hunt" to "can our instrument see anything at all".

Proving commands:

```
$ git log --oneline -3 -- libs/research/axis_screen.py
a7f91a6 desk snapshot 2026-07-29T02:36Z          # last touch: 3 days ago, O1 not implemented

$ .venv/bin/python -c "import sqlite3; c=sqlite3.connect('file:data/sor_crypto.sqlite?mode=ro',uri=True); \
  [print(r) for r in c.execute('select substr(created_at,1,10),substr(updated_at,1,10),count(*) \
   from research_candidates group by 1,2')]"
('2026-07-11', '2026-07-11', 390)
('2026-07-22', '2026-07-22', 30)
('2026-07-30', '2026-07-30', 14)
# updated_at == created_at for every one of the 434 -> nothing has been re-scored. O2 not done.

$ .venv/bin/python -c "import sqlite3; c=sqlite3.connect('file:data/sor_research.sqlite?mode=ro',uri=True); \
  print(c.execute('select count(*) from campaigns').fetchone(), \
        c.execute(\"select error from campaigns limit 1\").fetchone()[0][:80])"
(348,) v1 campaign store frozen since 2026-06-22 (superseded by the v2 sor_crypto factory)
# ...'terminal-marked 2026-07-31 per R0009'. O4a DONE.
```

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**S1 — THE GATE HAS BEEN CERTIFIED, BOTH HALVES, AND IT IS NOT WELDED SHUT.** This is the single
most valuable thing that has happened to alpha-discovery since the subsystem was first audited. The
positive control now runs and produces an artifact.

```
$ .venv/bin/python -c "import json; d=json.load(open('reports/gauntlet_certification.json')); \
  print(d['generated'], d['status']); print('per-candidate:', d['per_candidate_path']); \
  print('legacy:', d['legacy_welded_path'])"
2026-08-01T01:35:36Z COMPLETE-SYNTHETIC
per-candidate: {'pass_rate_by_true_sharpe': {'3': 0.0, '5': 1.0}, 'min_passing_true_sharpe': 5.0,
                'null_false_pass_rate': 0.0, 'certified_admits_good': True}
legacy:        {'pass_rate_by_true_sharpe': {'3': 0.0, '5': 0.0}, 'min_passing_true_sharpe': None,
                'null_false_pass_rate': 0.0, 'certified_admits_good': False}
```

Read it precisely: the **per-candidate path admits a true-Sharpe-5 candidate (100%) and rejects the
null (0% false pass)**. The **legacy path admits nothing at any tested strength** — it is welded, and
it is now proven welded rather than suspected. Both halves of a certification (admits good / rejects
null) are present. Yesterday this instrument did not exist.

**S2 — The 420/0 record's rejections are substantively CORRECT, and I tested this adversarially.**
My working hypothesis on opening was that the multiplicity gates were killing good candidates. They
were not. 84 of 434 candidates (19.4%) were rejected by *nothing but* `{dsr, pbo, reality_check}` —
they passed every economic gate. Their in-sample Sharpe looks excellent and their out-of-sample
Sharpe is nil:

```
$ .venv/bin/python -c "<see §2 F1 for the full script>"
rejected ONLY by multiplicity gates {dsr,pbo,reality_check}: 84 (19.4%)
annual_sharpe (in-sample, annualised) of those 84: median 2.67, p75 3.78, max 6.17, 31 are >=3.0
oos_sharpe    (walk-forward, PER-PERIOD)        : median 0.02, max 0.09
```

`oos_sharpe` is **not** annualised (`libs/validation/revalidation.py:103` — `sharpe_ratio(test)`
raw), so median 0.02/day annualises to ≈0.38 and the best of the 84 reaches ≈1.72. In-sample 2.67 →
out-of-sample 0.38 is an **86% decay**: textbook overfitting, and the gates caught it. *The
multiplicity gates earned their rejections.* Any recommendation to loosen them is refuted by this
table, and I am recording that because it was my own prior going in.

**S3 — `reality_check` is genuinely per-candidate, not a campaign constant in disguise.** I checked
this specifically because a campaign-constant gate was the desk's last big instrument artifact.

```
$ grep -n "reality_value = campaign.stepdown.adjusted_p" libs/autodiscovery/validation.py
471:        pbo_value, reality_value = cand_pbo, campaign.stepdown.adjusted_p[column]
# 13 distinct reality_p values across 434 candidates -- which looks constant-ish but is the
# CORRECT signature of Romano-Wolf step-down: adjusted p is a running maximum, so ties are
# expected by construction. dsr has 398 distinct values across 434. Not welded.
```

**S4 — The daily discovery loop is alive and fresh.** `web/discovery.json` updated
2026-08-01T02:21:53Z, 8 sleeves tested, 5 shadow-eligible (up from 4 yesterday), 3 data-gated
PENDING. The 12 Holm forward slots are full (`data/forward_slots.json`: `idle_slots: 0`,
`m_concurrent: 12`, `complete: true`) — yesterday's F2 idle slot is closed.

**S5 — A horizon-search instrument EXISTS and has run, with the right guards.** Yesterday's F5/F15
implied the horizon dimension was structurally closed. That is too strong: `scripts/horizon_search.py`
sweeps 12 horizons (1→90d) with **Bonferroni α/12 AND an adjacency rule** (a survivor needs ≥2
same-sign neighbours) and Newey-West-style √h deflation for overlap. It ran once:
`data/horizon_discovery.json`, 2026-07-27T12:54Z, `bonferroni_alpha: 0.00417`, on
`wiki_btc_en` (+ defi). Nothing cleared. The defect is not absence of the capability — it is that
the capability is **unscheduled and has been run once on two axes** (see F4).

**S6 — The desk audits its own screens' methodological completeness, daily, and the auditor is
honest.** `data/screen_audit.json`, generated 2026-08-01T02:30:10Z, grades 13 screens against 6
required disciplines and reports `total_missing: 28`. It does **not** grade any screen COMPLETE. An
instrument that refuses to report a clean bill is doing its job (see F5 for what it found).

**S7 — The min-length truncation has been measured, correctly, and the module that fixes it declares
its own precondition instead of pretending to be finished.** `libs/validation/campaign_window.py`
(277 lines + 118 lines of tests, committed `e98b925` at 01:09Z today) states in its own docstring:
*"NOT WIRED INTO ANY CAMPAIGN YET, AND DELIBERATELY SO"*, then names the exact unmet precondition
(per-stratum α must reach the gate or family-wise error becomes 1−(1−0.05)^k). It also rejects its
own first design — maximising per-candidate power chose 16 candidates at 99.9% power and dropped 404
hypotheses — on the grounds that *"a dropped candidate has ZERO probability of discovery, not a small
one."* This is the standard of engineering honesty the rest of the report is measured against.

## 2. WHAT WE DON'T KNOW (ignorance ledger)

### F1 — CRITICAL: 420/0 does not mean the price space is picked clean. It means the instrument cannot see. The design has ~0.25% power per candidate against a true annual Sharpe of 2.0.

This supersedes and finally settles F14/F1 of yesterday's report, and it inverts the desk's standing
narrative on evidence rather than on argument.

The certification's own power curve, at the campaign's recorded shape (T=310 obs, N=420 candidates):

```
$ .venv/bin/python -c "import json; d=json.load(open('reports/gauntlet_certification.json'))['design']; \
  print('hurdle annual Sharpe:', round(d['hurdle_annual_sharpe'],2)); \
  [print(f'  true SR {k:>4}: power {v*100:8.3f}%') for k,v in d['power_by_true_annual_sharpe'].items()]"
hurdle annual Sharpe: 5.04
  true SR    1: power    0.010%
  true SR  1.5: power    0.055%
  true SR    2: power    0.252%
  true SR  2.5: power    0.954%
  true SR    3: power    2.984%
  true SR    4: power   16.812%
  true SR    5: power   48.403%
  true SR    6: power   81.099%
```

**A true annualised Sharpe of 2.0 — a world-class systematic book — has a 0.25% chance of being
detected by this campaign.** Across 420 candidates that is an expectation of ~1 discovery *if every
single candidate were a genuine Sharpe-2 alpha*. The desk observed 0. **0 and 1.06 are not
distinguishable outcomes.** The 420/0 record is consistent with a price space containing hundreds of
excellent edges, and it always was.

This is not the same claim as "the gate is broken". S2 shows the gate's actual rejections were
correct on their merits. The two facts coexist: the gate correctly killed 434 overfit candidates
*and* would have correctly killed almost every genuine edge as well. The record carries almost no
information about the market, which is exactly the condition L1.25 names — *failure to discover alpha
is never evidence alpha does not exist* — and exactly the condition the gate-optimality duty calls a
defect: a gate rejecting ~100% carries zero information until you know its sensitivity.

**The hurdle is set by campaign SHAPE, not by any threshold.** From the same artifact:

```
alternative_shapes (hurdle annual Sharpe):
        N=420   N=100   N=30    N=10    N=5
T=310    5.04    4.53    4.04    3.50    3.08
T=620    3.56    3.20    2.85    2.47    2.18
T=1250   2.51    2.26    2.01    1.74    1.53
T=2500   1.77    1.60    1.42    1.23    1.08
```

Cutting the cohort from 420 to 30 moves the hurdle 5.04→4.04 and buys **nothing** at realistic effect
sizes. Quadrupling history to T=2500 moves it to 1.77 — into the range where real edges live. *History
is the lever; cohort size is not.* And this is not a data-acquisition problem, which is what makes
F2 the most expensive finding in this report.

### F2 — CRITICAL: 82.9% of the observations already on disk are thrown away before a single test runs, by a one-line idiom repeated in six production scripts. The fix is written, measured, tested — and called by nothing.

```
$ .venv/bin/python -c "import pickle,pathlib; d=pickle.loads(pathlib.Path('_audit_prepared.pkl').read_bytes()); \
  lens=[len(r) for *_x,r in d]; print('candidates',len(d),'min',min(lens),'max',max(lens),'mean',sum(lens)//len(lens)); \
  print('obs retained (min-length align):', min(lens)*len(d), ' obs available:', sum(lens))"
candidates 420 min 310 max 4594 mean 1808
obs retained (min-length align): 130200  obs available: 759444
```

One candidate with 310 observations truncates 419 others that have up to 4,594. **629,244
observations — 82.9% — are discarded to keep a matrix rectangular.** Given F1's table, this is the
worst available trade: it spends the only resource that buys power to preserve the one that does not.

The desk's own measurement of the consequence, from `libs/validation/campaign_window.py:20`:

> *"the best candidate's Romano-Wolf adjusted p is **0.522 at the min-length window and 0.089 at the
> max-observation window**. Same candidates, same gate, same threshold."*

A 5.9× improvement in the best p-value from changing nothing but the window. (0.089 still fails at
α=0.05 — the point is not that a survivor was hiding, it is that the campaign is being run 6× away
from its own achievable sensitivity.)

**Expected discoveries** (Σ over strata of cohort × detection power at a REFERENCE true annual Sharpe
of 2.0 — this is a *power* measure, **not** a forecast of 159 real alphas, and must never be quoted as
one): **1.06 under min-length alignment, 159 under stratified windows** at MAX_STRATA=32
(`campaign_window.py:114`). Per candidate that is 0.25% → 37.9%.

The blast radius of the idiom is larger than its own docstring says ("run_campaign.py and its three
siblings"):

```
$ grep -rn "min_len = min(len(" --include=*.py scripts/ libs/ | grep -v test
scripts/run_campaign.py:95           scripts/run_mt5_funding_bridge.py:109
scripts/run_xsec_funding_max.py:68   scripts/run_funding_8h.py:63
scripts/run_mt5_crossasset.py:87     scripts/certify_gauntlet.py:100
# six, not four -- and scripts/run_trend_gauntlet.py:90 + scripts/run_sleeve_alloc.py:85
# carry the same shape as `n = min(len(v) for v in ...)`.
```

**Including `certify_gauntlet.py` itself.** The instrument that certified the gate's sensitivity
floor at true Sharpe 5.0 computed that floor on a min-length-truncated matrix. So *the certified
sensitivity floor is itself a product of the truncation being certified* — S1's number is real but
it is the floor of the **truncated** design, not of the gate.

**The blocker is one keyword argument.** `campaign_window.py` correctly refuses to be wired until the
per-stratum α reaches the gate. That α already exists:

```
$ grep -n "def romano_wolf_stepdown" -A 4 libs/validation/stepwise.py
157:def romano_wolf_stepdown(performance, *, alpha: float = 0.05, n_boot: int = 1000, ...)

$ grep -rn "romano_wolf_stepdown(" --include=*.py libs/ scripts/ | grep -v test
libs/autodiscovery/validation.py:396:        stepdown=romano_wolf_stepdown(matrix),
scripts/audit_gate_power.py:176:                         stepdown=romano_wolf_stepdown(matrix),
scripts/measure_matrix_window.py:81:        res = romano_wolf_stepdown(mat)
# THREE production call sites. NOT ONE passes alpha=. All run at the 0.05 default.
```

Threading `alpha=CAMPAIGN_ALPHA/k` through `campaign_gate_stats` → `romano_wolf_stepdown` is the
entire precondition. This is a ~5-line change standing in front of the largest measured improvement
to discovery power the desk has ever quantified. Under L1.28b that is a found-unfixed defect aging at
its stated ROI; under L1.27 the question "am I protecting capital or avoiding uncertainty?" has an
uncomfortable answer, because the honest engineering reason to wait (error control) is satisfiable
today.

### F3 — CRITICAL: the certifier reports the real-cohort question as BLOCKED while its input sits on disk, loadable, 6.1MB, containing exactly the 420 real candidates.

`reports/gauntlet_certification.json` says `"peers": "SYNTHETIC"` and:

> *"That half stays blocked on a builder for `_audit_prepared.pkl` (3 readers, 0 writers)."*

The file exists and loads:

```
$ ls -la _audit_prepared.pkl
-rw-rw-r-- 1 quant quant 6100907 Jul 26 15:08 _audit_prepared.pkl
$ .venv/bin/python -c "import pickle,pathlib; d=pickle.loads(pathlib.Path('_audit_prepared.pkl').read_bytes()); \
  print(type(d), len(d), [type(v).__name__ for v in d[0]])"
<class 'list'> 420 ['str', 'str', 'str', 'ndarray']
```

The mechanism is a path-resolution asymmetry, and it is exactly reproducible:

```
$ git check-ignore -v _audit_prepared.pkl
.gitignore:33:_audit_prepared.pkl	_audit_prepared.pkl        # UNTRACKED
$ git ls-files --error-unmatch reports/gate_histogram.json
reports/gate_histogram.json                                    # TRACKED
$ grep -n "_PREPARED = \|_HIST = \|_ROOT = " scripts/certify_gauntlet.py
35:_ROOT = Path("/home/quant/quant-platform")
59:_PREPARED = Path("_audit_prepared.pkl")     # relative, and UNTRACKED
61:_HIST = Path("reports/gate_histogram.json") # relative, and TRACKED
```

In any checkout whose CWD is not this exact repo root — a git worktree, CI, a container, an agent
sandbox — the **untracked** pickle is absent while the **tracked** shape file is present. The
`if _PREPARED.exists()` branch at line 98 falls through, `CampaignUnavailable` is never raised
(because `_HIST` supplies the shape), and the run silently degrades to synthetic peers while
reporting the real-cohort question as unanswerable. `git worktree list` shows no live worktree now,
so I cannot name the specific run — but the mechanism is proven by the tracking status alone, and it
is the "no writer" claim that is false: the loader needs a *readable file*, and it has one.

**Consequence, and this is the whole point of the finding:** the one question the desk's entire
search-allocation strategy turns on — *is the real 0/420 informative, or an artifact of its peers?* —
is answerable **right now**, against real peers, with a file already on disk. It is instead recorded
as blocked, and GAP_REGISTER R0040/R0041 are gated behind it.

### F4 — HIGH: the entire Stage-A screening layer is UNSCHEDULED. Every screen is a hand-run one-shot, so discovery output is a function of whether a session happened to run one.

```
$ grep -oP "scripts/\w+\.py" ops/crontab.manifest | sort -u | wc -l
102                                     # of 340 scripts in scripts/
$ grep -nE "horizon_search|reflexivity_m5|fusion_engine|hl_feature|batch_altdata|batch_onchain" \
    ops/crontab.manifest
(no output)
```

**Zero of the 13 screens graded by `data/screen_audit.json` appear anywhere in the scheduler
manifest.** Four differently-named `screen_*.py` scripts ARE scheduled (carry_basis_path,
collateral_allocation, copytrading, funding_spread) plus `run_fusion_search`, `run_autodiscovery`,
`run_generation_diversity` — so the layer is not entirely dark, but the *discovery* screens are.

The observable consequence: the newest artifact in `reports/axis_screens/` is
`kr_perasset_premium.json` at **2026-07-30 22:41** — no new Stage-A axis screen in ~28 hours, under a
standing SCREEN-ON-DISCOVERY duty. `horizon_search.py` — the instrument that re-opens the entire
horizon dimension (S5) — has run **once, ever**, on **two axes**, five days ago.

Under L1.28c every cadence must be a *decided* cadence with its ceiling type named. These have no
cadence at all, which is the unmeasured case, which counts as idle. These are pure-CPU organs reading
data already on disk: their ceiling type is DATA-ARRIVAL, and raising them is nearly free.

### F5 — HIGH: the desk's own screen auditor reports 28 missing methodological disciplines and grades ZERO of 13 screens complete — and the screens run anyway.

```
$ .venv/bin/python -c "import json,collections; d=json.load(open('data/screen_audit.json')); \
  print(d['updated'], 'total_missing', d['total_missing'], 'screens', len(d['screens'])); \
  print(dict(collections.Counter(s['status'] for s in d['screens']))); \
  c=collections.Counter(); [c.update(s['missing']) for s in d['screens']]; print(c.most_common())"
2026-08-01T02:30:10Z total_missing 28 screens 13
{'INCOMPLETE': 10, 'WEAK': 3}
[('multiplicity', 10), ('stability_check', 10), ('lookahead_rail', 4),
 ('net_of_cost', 2), ('gapped_windows', 1), ('decontamination', 1)]
```

**`multiplicity` is missing from 10 of 13 screens.** That is the discipline that stops the
garden-of-forking-paths, and it is absent from the majority of the desk's Stage-A surface — including
`fusion_engine.py`, which searches *combinations* and therefore has the largest implicit trial count
on the desk. `stability_check` is missing from the same 10.

The artifact is generated daily and is fresh (02:30 today, 9 minutes before I read it). Nothing gates
on it. This is the honest-detector/no-consumer shape: the measurement exists, is correct, is current,
and changes no behaviour.

### F6 — CRITICAL: the H8 timeframe is STRUCTURALLY unreachable, because the dedup hash forgot a field. Half the factory has been a no-op since inception.

The generation funnel produced **zero new candidates in the last 48 hours** and 14 in the last 7 days.
Yesterday's F13 is reproduced bit-identically:

```
$ cat data/cro_ai_logs/crypto_factory_cron.log
=== 2026-08-01T01:30:01Z crypto factory harness ===
crypto H8: [cycle] tested=0 survivors=0 rejected=0 promoted_paper=0 skipped_dup=140
crypto D1: [cycle] tested=0 survivors=0 rejected=0 promoted_paper=0 skipped_dup=420
```

The H8 row is the finding. Every H8 hypothesis is skipped as a duplicate because the identity function
cannot see the timeframe:

```
$ sed -n 31,34p libs/autodiscovery/memory.py
def content_hash(hyp: Hypothesis) -> str:
    """Stable identity of a hypothesis (family+subtype+symbol+params) for dedup."""
    payload = [hyp.family.value, hyp.subtype, hyp.symbol, sorted(hyp.params.items())]

$ grep -n "class Hypothesis" -A 11 libs/autodiscovery/models.py
61:class Hypothesis(BaseModel):
66-    family: Family      67-    subtype: str        68-    symbol: str
69-    params: dict        70-    mechanism           71-    edge_source
72-    failure_modes
# NO timeframe field exists. D1 and H8 hypotheses hash IDENTICALLY.
```

Both timeframes run against the same `data/sor_crypto.sqlite`, so every one of the 140 H8
hypotheses collides with its D1 twin and is skipped before it is ever tested. **The 8-hour resolution
has never been tested and cannot be, by construction.** That is the exact resolution the blind
rediscovery run identified as the escape from the daily low-pass filter (vif 3.6 daily vs 1.008 at
8h) — the desk's own named remedy for its own diagnosis, closed by a missing struct field.

### F7 — CRITICAL: "the price space is picked clean" is a claim about 10.8% of the eligible universe. 3,486 candidates sit unused on data already on disk.

```
$ sed -n 120,126p libs/autodiscovery/crypto_adapter.py
def load_universe(timeframe: Timeframe = Timeframe.D1, *, limit: int | None = 30, ...)
# lake symbols D1 = 279, all 279 eligible (>= 250 bars). CAP = 30.
# excluded by the cap: 249 symbols x 14 hypotheses = 3,486 candidates forgone.
```

`434 = 31 symbols × 14 hypotheses` exactly. The pool is not exhausted; it is **capped at 30 symbols
by a default keyword argument**. Acquisition cost of the other 3,486: zero — the bars are in the lake.
Under L1.25a(c) effort must reallocate toward the widest untested space after a null streak; the
widest untested space here is 8× the tested one and requires changing one integer.

The docstring's stated reasons for the cap (bootstrap OOM on a campaign-wide reality check, DSR
deflation drag) are real engineering constraints — but they are **batching** problems, and F1's table
shows that shrinking cohorts buys nothing anyway. The correct response is to run 9 campaigns of 30,
not to leave 89% of the universe untested.

### F8 — CRITICAL: the resurrection feeder — the designated fix for the un-re-scored 420 — selects ZERO every day, on arithmetic, and reports a false reason.

```
$ grep -n "min-age-days" scripts/run_rejection_rescore.py
98:    p.add_argument("--min-age-days", type=float, default=30.0)
$ grep -n "rejection_rescore" ops/crontab.manifest
948:50 6 * * * ... scripts/run_rejection_rescore.py ...     # no --min-age-days override
$ .venv/bin/python -c "<oldest/newest candidate age at 2026-08-01T02:40Z>"
2026-07-11T07:44:31Z  age_days=20.79      <- OLDEST
2026-07-30T02:40:44Z  age_days=2.00       <- newest
```

The oldest rejected candidate is **20.79 days old** against a **30.0-day** eligibility floor. Zero
candidates are eligible and will remain so until **2026-08-10**. The daily cycle's surfaced output
does not say this — it captures the tail of the script, which is the wrong branch:

```
[reject_rescore] {'ok': True, 'rc': 0, 'tail': 'no new forward scores produced (re-eval hook not
wired on this host, or all selected already scored) -- the shadow audit will report unscored, honestly'}
```

The re-eval hook **is** wired (`_forward_score` is fully implemented in that same file). So a daily
green organ reports an infrastructure excuse for what is an age-gate arithmetic block. This is the
mechanism by which yesterday's O2 cannot self-heal, and it explains why nobody noticed: the honest
message is printed first and the misleading one is what gets surfaced.

### F9 — HIGH: the one instrument built to answer "is this 420 candidates or one question asked 420 times?" has never seen a candidate, and its miss is dressed as an honest supply reading.

```
$ grep -n '_DB = ' scripts/run_generation_diversity.py
46:_DB = _ROOT / "data/research_memory.db"
$ ls data/research_memory.db
ls: cannot access 'data/research_memory.db': No such file or directory
$ cat data/cro_ai_logs/gen_diversity.log
generation diversity [UNDER-SAMPLED] over 0 candidates
  NO BATCH -- no research db on this box. That is a supply fact, not a health reading; ...
```

**The statement is false.** 434 candidates are on this box, in `data/sor_crypto.sqlite`. The same
phantom path appears in `run_promotion_queue.py:47`, `run_moat_backup.py:55`, and `max_audit.py`
(×2) — yesterday's F3, unmoved, and now with a measured consequence: the desk's *only* diversity
gauge has produced zero readings while asserting the absence is a fact about the world. A wrong
"nothing to measure" is worse than a crash, because it is quiet and it is reassuring.

Related and same shape: `strategy_breadth` reports `BLIND -- all 14 hunting surfaces carry the
mandate; data/strategy_coverage.json missing`.

### F10 — HIGH: the second research lab has been dead for 42 days behind a green daily cron.

```
$ grep -n "run_autodiscovery" ops/crontab.manifest      # 20 3 * * * daily
$ .venv/bin/python -c "import MetaTrader5"
ModuleNotFoundError: No module named 'MetaTrader5'
$ sqlite3 data/sor_autodiscovery.sqlite "select count(*), max(created_at) from research_candidates"
57 | 2026-06-20T10:15:27Z
```

42 consecutive scheduled runs, zero candidates, no page. Its log is reaped (`ops/run_cro_ai.sh:99`
deletes `*.log` keeping 30 of ~98, 3×/day), so the only surviving evidence is the store's frozen
`max(created_at)` — which is why this survived 42 days of daily audits.

### F11 — THE SHAPE BEHIND F6–F8: three independent refill paths, three unrelated blockers, all silently green, two printing reassuring text.

- the **timeframe** axis is closed by a hash missing a field (F6)
- the **symbol** axis is closed by a `limit=30` default (F7)
- the **resurrection** axis is closed by a `min_age_days=30` no candidate can reach (F8)

None raises an alarm. Two emit text that reads like a considered conclusion. **This is why
`tested=0` has looked like a fact about crypto for nine days.** The generic lesson, which is the part
worth carrying to other subsystems: a null result produced by a *blocked* pipeline is
indistinguishable from a null result produced by an *empty* market, unless something measures the
denominator. Nothing here measured the denominator.

### F12 — MEDIUM-HIGH (L1.25a violation, one day old): a generator encodes its null streak as a standing reason not to widen.

`ops/run_crypto_factory.sh:6-13` ships the text *"the price-family hypothesis space is EXHAUSTED …
It does NOT, by itself, move the 390 number"* as a permanent rationale, and the per-cycle pilot line
re-emits *"0 durable survivors in 1244 trials — the constraint is DATA/MECHANISM, not volume. Do NOT
rent hardware yet"* every run.

The hardware conclusion is defensible — re-running duplicates buys nothing. The defect is that the
same sentence has stood in for **widening the space**, which F6/F7 show costs a struct field and an
integer. L1.25a was enacted 2026-07-31 naming this exact organ as its proving instance; one day later
the behaviour is bit-identical. No other generator gates on past nulls — the rest fail on wiring
(F8/F9/F10), not on pessimism.

### F13 — CRITICAL: the 12 forward slots are 4.56 independent bets. Four of them are the SAME estimator on the SAME instrument.

`m_concurrent: 12` is the Holm cohort size — the number every Stage-B bar is corrected against. It is
booked at 12. The economic reality:

```
$ grep -n "BTCUSDT" scripts/run_axis_shadows.py
80: "defi_utilisation":           ("data/defi_util_axis.jsonl",    "BTCUSDT", "z20", -1)
81: "stablecoin_supply_momentum": ("data/stablecoin_supply.jsonl", "BTCUSDT", "z20", +1)
85: "cny_premium":                ("data/cny_premium.jsonl",       "BTCUSDT", "z20", +1)
95: "walcl_reserve_impulse":      ("data/walcl_impulse.jsonl",     "BTCUSDT", "z20", +1)
```

**Four slots are a 20-day z-score of a scalar series, signed, applied to directional BTCUSDT.** Only
the input series differs. Their P&L is one BTC return stream re-signed four ways; they cannot fail
independently, which is exactly the assumption Holm correction makes about them.

A second block is worse because the desk has already *measured* it: `trend_30d` (TS-momentum, top-15
majors, 30d), `trend_regime` (its own state file calls it *"pre-registered challenger to
trend_30d"*), `crypto_combined` (composition includes `ts_trend`), and `crossasset`
(`trend_basket_returns(100)` + `xsec_momentum_returns(120)`) — four price-momentum slots. The
graveyard killed `tftrailbreakout` and `tfatrexitbreakout` at **`max_corr 0.91` vs the trend book**,
tagged `wrong_orthogonality`/`crowded`. The desk knows trend variants correlate at 0.91 and is
running four concurrently.

Collapsed to economic bet: `PRICE-MOMENTUM 4, LIQUIDITY-z20→BTC 3, CARRY-FUNDING 2, PERP-POSITIONING
2, REGIONAL-PREMIUM 1` → **H = 1.517, effective bets 4.56, top-3 share 75%. A 2.63× overstatement.**

This cuts both ways and both directions matter:
- **Diversity is 2.63× worse than booked** — L1.18's maximum-independent-sources objective is being
  measured against a number that double-counts.
- **The Holm bar is 2.63× too strict** — correcting for m=12 when 4.56 independent tests exist makes
  every forward promotion harder than the evidence requires. This is a *gate-optimality* defect in
  the direction nobody looks for.

Against `MECHANISM_GRAPH.md`: 6/12 slots sit on M1 — the chain the document itself calls *"saturated
— stop adding sensors"*. **4/12 name no mechanism node at all**, violating the graph's own binding
rule (*"a hypothesis that cannot name one is a curve-fit and is rejected before it consumes a forward
slot"*). **0/12 sit on M4 (information diffusion), the one chain the document calls open.** No
pairwise slot-correlation instrument exists anywhere on the desk; the only orthogonality check
(`run_axis_generate.py:41`) is `|corr| to funding_carry > 0.5` — one reference asset, not a cohort
covariance.

And three live slots are *simultaneously in the graveyard resurrection queue*: `trend_regime`
(`regime_artifact`), `ls_contrarian` (`overfit`), `oi_divergence` (`overfit`). A strategy cannot
coherently be both an accruing forward clock and a dead strategy awaiting revival.

### F14 — CRITICAL: the diversity gauge reports PERFECT diversity from ZERO rows, every 6 hours, and the caveat does not survive the hop into the scorecard.

```
$ cat data/gen_diversity.json
{"generated": "2026-08-01T00:23:01Z", "n_in_batch": 0,
 "gen_diversity": {"n": 0, "mechanism_entropy": 1.0, "feature_breadth": 1.0,
                   "semantic_distinctness": 1.0, "cross_generator_dup_rate": 0.0}}
```

`mechanism_entropy: 1.0` and `semantic_distinctness: 1.0` computed over `n: 0`. The stdout is honest
(*"the metrics below would be fabricated if reported as measured"*) but `_append_scorecard()` pushes
the 1.0s into `data/panel_scorecard.json` **where the caveat does not travel**. This is the
UNMEASURED-REPORTED-AS-OK defect class (L1.40) inside the very instrument built to detect
redundancy — and it is the reason F13 went unnoticed: the organ that should have flagged 4.56/12 has
been reporting 1.0 since it was wired.

### F15 — HIGH: the desk's experiment record carries mechanism 0 times in 192 rows, so concentration is not computable from the live store.

```
$ <key census over research_memory.metrics_json, 192 rows, 2026-07-24 -> 07-31>
status_granular: 192   axis: 156   mechanism: 0
```

`research_candidates` *does* have a `mechanism` column — and those crypto rows are the 434 frozen
ones. The MECHANISM_GRAPH rule is binding on paper and enforced in exactly zero places. Yesterday's
O9 (mechanism-tag at experiment time) is unmoved and is now the blocker for the one query generation
most needs: *which mechanisms have we never probed?*

The historical record, where it IS computable (`docs/graveyard.md`), is genuinely good: 48
family-hits across 13 of 14 families, **H=2.345, effective 10.44 families, top-1 18.8%**. The desk
tested ~100 ideas, not one idea 100 ways. **The failure is entirely downstream: the funnel narrows
from 10.4 to 4.56 and nothing watches it narrow.**

### F16 — HIGH: the family-coverage fence has read BLIND every hour since it was wired, and when it first fires it will pass by a margin of exactly zero on double-counted evidence.

```
$ ls -la data/strategy_coverage.json
ls: cannot access 'data/strategy_coverage.json': No such file or directory
$ tail -6 data/cro_ai_logs/strategy_breadth.log      # 6/6 lines: BLIND
```

Five call sites depend on this file, including two **doctrine surfaces** that instruct every hunting
organ to read it: `run_capability_hunt.py:224` and `kimi_hunter.py:158` (*"data/strategy_coverage.json
names every family HUNTED / THIN / NEVER-HUNTED"*). It has never existed. Every miner and hunter
told to consult it has been consulting nothing — including this audit's own charter.

Computed read-only: `7/14 = 0.500` hunted vs `MIN_HUNTED_FRACTION = 0.5` → **OK by zero margin**, and
propped by double-counting: 8 of 40 attributed graveyard names match two families each (1.20×
inflation). Two families sit at exactly `THIN_BELOW=3`; reassigning one shared candidate flips the
verdict to NARROW.

One hit is a plain substring false positive: `'level' in 'cm_mvrv_btc_daily_level'` → True. That is
a Coin Metrics MVRV on-chain ratio, not a support/resistance test. **LEVEL-REACTION has been tested
zero times, not once** — and it is the conviction sleeve's own stop-placement premise. Ledger row
R0211's claim that it was "tested exactly once" is an artifact of the matcher. There are **2
NEVER-HUNTED families** (LEVEL-REACTION, STATISTICAL-ARBITRAGE), not 1.

Cadence defect on top: producer `50 5 * * *` (daily), consumer fence `35 * * * *` (hourly) — the
fence reads a stale file 23 hours out of 24 even after it starts working (L1.44).

### F17 — CRITICAL: the Stage-A harness has no concept of a bar. The temporal search space is locked to three integers by a dict lookup.

```
$ sed -n 55,56p scripts/screen_idle_axes.py
ZWIN = {1: 20, 5: 12, 20: 6}
HORIZONS = (1, 5, 20)
# ZWIN[h] raises KeyError for h in (2, 3, 0.04, ...). _HORIZONS = (1,5,20) is duplicated
# identically in screen_exchange_netflow.py:46 and screen_fred_macro_axis.py:97.
$ sed -n 66p libs/research/axis_screen.py
    fwd = np.roll(r, -1)          # the forecast is ALWAYS exactly one bar ahead
```

`libs/research/axis_screen.py` takes no resolution parameter. Multi-day horizons are faked by the
caller pre-downsampling. A recursive walk of **all 44 screen/backtest artifacts on disk** returns:

```
DISTINCT HORIZON VALUES:    1 (76x), 5 (71x), 20 (69x), 1.0 (42x), 5.0 (14x), 20.0 (11x)
                            + 13 fractional FRED-alignment values
DISTINCT RESOLUTION/BAR VALUES: {"frequency": "12h"}    <- ONE, from options VRP
```

**No screen artifact on this desk records what a bar is.** That is why the intraday dimension is not
"untested" — it is *inexpressible* in the audited harness, which is a strictly worse condition and
explains why the one intraday analysis that exists (`micro_factory.py`) was written outside the
harness with a hand-rolled Spearman.

### F18 — HIGH: 42 screen cells were run on 4-hour bars and stamped `horizon_days=1.0`, understating annualised Sharpe by 2.45×.

```
$ grep -n "PERIOD\|stage_a_screen" scripts/screen_smart_dumb.py
34:PERIOD, LIMIT = "4h", 500
76:  r = stage_a_screen(sig, ret, name=f"{sym}:{name}", zwin=20)     # horizon_days NOT passed
$ .venv/bin/python -c "<walk data/elite_trader_screen.json for horizon_days>"
horizon_days recorded in a 4h-bar screen: {1.0: 20}
```

`axis_screen.py:88` annualises with `sqrt(365/horizon_days)`. For 4h bars the correct factor is
`sqrt(365/0.1667) = 46.8`; the default applied `sqrt(365) = 19.1`. **All 42 cells came back
UNDERPOWERED / TIMING-ARTIFACT — a verdict the mislabel alone is capable of producing.** Six scripts
carry this shape (`screen_smart_dumb`, `hl_dir_flow`, `hl_breadth_flow`, `hl_feature_factory`,
`hl_flow_alpha`, `reflexivity_m5`). Their nulls are uninterpretable and must be re-run, not cited.

### F19 — CRITICAL: 83.8% of the desk's data is a 7.68 GB order-book tape that has carried ONE test, and that test forecast volatility, not return.

```
$ du -sb data/ data/moat data/lake/bronze/cme
9,161,370,012  data/
7,675,071,018  data/moat            = 83.8%
1,107,232,400  data/lake/bronze/cme = 12.1%   (PAID Databento)
$ .venv/bin/python -c "<read data/feature_library.json>"
N FEATURES: 9  STATUS: {'computed_unused': 5, 'tested': 1, 'confirmed': 1, 'forward_clock': 1, 'blocked': 1}
  F001 spread_bps  src=data/moat  computed_unused  tested_constructions=0
  F003 depth10 / F004 imbalance / F005 concentration / F006 slope  -- all computed_unused, 0
```

The tape is L2 depth at **~4.3 s** across 80 symbol-feeds (20,439 files). Its only consumer,
`scripts/micro_factory.py:155`, computes `spearman(wd[m], fwd[m])` where `fwd = np.roll(rv, -1)` —
**realised volatility, never return** — over `SYMS = [BTC, ETH, SOL, XRP, DOGE]`, `N_FILES = 60`,
`"hours": 35`. That is **5 of 80 feeds, 35 observations, wrong target**. The 5.8 GB Bybit tape and
the 535 MB spot tape have never been opened by any analysis. Output is 4.6 days stale behind a daily
cron.

**There has never been a return-predictive test on the largest and only irreplaceable object the desk
owns.** And per the data-moat sweep, the "irreplaceable" premise is itself refuted (free first-party
Bybit archive at 200 levels/100ms vs our 25 levels/4080ms) — so the asset is simultaneously
un-tested and over-valued.

Paid data fares no better: of 1.1 GB of Databento CME, only the 2 MB `ohlcv-1d` file is read by
anything. The 597 MB BTC + 346 MB ETH `statistics` files and the 13 MB `ohlcv-1h` (146,331 rows) have
**zero readers**. And the curve is collapsed: `screen_cme_basis.py:66` does
`bars.sort_values("dte_d").groupby("day").first()` — 8.29 traded contracts/day reduced to 1, so the
only "basis term structure TESTED" claim on the desk rests on a two-point front/next spread.

### F20 — HIGH: 54 catalogued sources, 1 screened. The catalogue reads as coverage and is a wishlist.

```
$ <split data/data_universe_map.json sources by presence of a "screen" field>
DICT-CARDS WITH A "screen" FIELD:  1   (cboe_cfe_crypto_settlements -> all 4 cells UNDERPOWERED)
DICT-CARDS WITH NO "screen" FIELD: 53
$ for t in gdelt pytrends xatu mempool_dumpster flashbots cryptopanic numia bigquery; do
    echo "$t: $(grep -rli "$t" --include=*.py libs/ scripts/ | wc -l)"; done
gdelt: 0  pytrends: 0  xatu: 0  mempool_dumpster: 0  flashbots: 0  cryptopanic: 0  numia: 0  bigquery: 0
```

Attention is monitored by exactly one source: Wikipedia pageviews for **three pages**. `reddit`
appears 4 times, all inside mechanism-tagging keyword dicts — no collector. This is the
catalog-and-stop leak §33 exists to close, at the SOURCE level, at 1/54.

### F21 — HIGH: six of eleven named market behaviours have never carried a test, and three were "killed" by an EV score computed without data.

| behaviour | verdict | proof |
|---|---|---|
| order-book imbalance | code exists, **never run** | `feature_library` F004 `tested_constructions: 0`; `libs/research/microstructure.py` sole importer is its own unit test |
| liquidations / cascades | **never** | `data/liquidations.parquet` 50,317 rows; readers = the writer + a freshness check |
| cross-venue latency / lead-lag | **never** | every `lead.?lag` hit is cross-*asset*; both venue tapes recorded, nothing joins them |
| options gamma / dealer flow | **never** (VRP tested) | 1 grep hit, a wishlist string |
| stablecoin depeg | **never** (supply screened) | appears only as a risk-haircut constant |
| **unlocks / governance** | **never** | `grep -rn "unlock_events" --include=*.py .` → **0 hits**, against `data/unlock_events.json` = **5.2 MB, 24,201 dated events, 174 perp-matched** |
| MEV / priority fees | **never** | 0 hits repo-wide |
| funding **term structure** | **never** | 0 hits across all screen artifacts |
| calendar / session | partial | `session: {tested: 6, survivors: 0}`; DoW / month-end / **expiry** untested |
| basis term structure | tested, 2-point only | F19 |
| correlation regime break | **EV-gated pre-research** | `graveyard.md:76`, EV 0.0003, *"reject before research"* — no returns ever computed |

**The trap worth naming:** `correlation_regime`, `stablecoin_mint_burn`, `crypto_equity_leadlag` and
`liquidation_heatmap_cascade` all sit in `docs/graveyard.md` and read as "killed" to any grep or
novelty check. Their basis is an `est_sharpe` prior, not data. **Three of eleven behaviours are
refuted-by-arithmetic-only** — and the novelty gate will now block anyone from re-proposing them.
That is the graveyard being used to protect ground it never actually walked.

`data/unlock_events.json` is the single sharpest instance: 24,201 dated supply-shock events with 174
already matched to perps, zero code references, and a mechanism (forced holder distribution on a
publicly known schedule) that names exactly who is forced to trade and why they cannot stop.

### F22 — MEDIUM-HIGH: a 5-minute archive was down-sampled to daily, then declared redundant with its own down-sample.

`data/lake/bronze/binance_metrics` is 34 MB of **5-minute** OI / top-trader L/S / taker-flow since
2023 (289 rows/day/symbol). The only screen ever run on it says, in its own `coverage` field:

> *"Despite 435 files this axis is ONE symbol. It is the raw 5-min metrics archive that oi_ls_daily
> was itself built from, so `sum_open_interest`, `count_long_short_ratio` and
> `sum_taker_long_short_vol_ratio` are REDUNDANT with oi_ls_daily and were not re-screened."*

Redundancy was asserted against the desk's own **daily aggregate of the same file**. All
`screen_outputs` carry `horizon_days: 1`. The 288 intraday points per day have never been a
hypothesis — and per F17 they *could not have been*.

### F23 — MEDIUM: the asset registry is blind to 97.6% of the disk and its yield column has never been populated.

```
bytes catalogued in data_assets.json: 217,207,282  = 2.4% of the 9.16 GB on disk
alpha_contribution populated: 0 / 61
assets with zero consumers: 11 / 61      assets whose path does not exist: 8 / 61
```

Unregistered entirely: `lake_cme` (1.1 GB), `lake_fed`, `lake_binance_metrics`, `lake_wikipedia`,
`lake_etf_flows`, `lake_mining`, `lake_crossasset`, and all of `data/moat`. The 8 registered `lake_*`
rows carry `research_value` 70–98 and **zero consumers each**. There is no field anywhere that
measures data→alpha conversion; `alpha_contribution` exists and is `None` 61 times — so the
DATA-TO-ALPHA CONVERSION RATIO the doctrine requires to be *driven up* is not measured at all, and
unmeasured counts as zero.

### F24 — MEDIUM: non-USDT instruments are not under-covered, they are unreachable.

```
$ grep -n "quoteAsset" libs/data/crypto_source.py
114:        and s.get("quoteAsset") == "USDT"
```

Inside `list_perp_symbols()`, the single universe function. Coin-margined (inverse) perps, USDC-quoted
perps and every non-USDT quote are excluded by a hard filter with no override — so basis/funding
differences *between quote currencies*, a genuine structural mechanism, cannot be studied without
editing that line. Recording it as a one-line finding rather than a gap because that is what it is.

### F25 — CRITICAL, and it REFUTES yesterday's O6: the novelty gate's problem is RANKING, not thresholding, and the prescribed fix does not reproduce.

Yesterday's O6 said: swap the novelty gate's Jaccard matcher for the TF-IDF already in
`knowledge_engine.py:80-99`, hours of work. **Measured on the identical task, that prescription
fails.**

```
# 8 paraphrases of real graveyard kills, production prior set (n=48), threshold 0.70
RECALL @ prod threshold = 0/8 = 0.0%   max sim 0.120
NEAREST-NEIGHBOUR WRONG IN 8/8   (the reversal paraphrase's nearest prior is a LIVE SLEEVE)
verbatim recall 6/6   FPR 0/3

# the prescribed replacement, same 8 paraphrases
knowledge_engine TF-IDF, graveyard-only (n=45):  recall@1 1/8 = 12.5%
knowledge_engine TF-IDF, real corpus  (n=399):   recall@1 0/8 =  0.0%
research_erv concept-archaeology:                recall@1 3/8 = 37.5%   <- best available
```

The "J = 0.000 → 0.977 measured on the identical task" figure quoted in
`20260801_research-engine.md:895` is a **same-document self-similarity**, not paraphrase retrieval.
On the 399-document corpus TF-IDF actually runs against (89% experiment-registry noise) it scores
0/8. Because the nearest neighbour is wrong in 8/8 cases, **no threshold exists that fixes this** —
lowering the bar flags everything and still names the wrong prior.

The only approach that beats noise is `research_erv`'s **concept-family** mapping (37.5%), and its
own docstring says why: *"'Twitter sentiment predicts returns' and 'social attention predicts
momentum' share almost no tokens and are the SAME dead idea."* **The working design is concept-family
mapping, not any bag-of-words metric — a different and larger build than a matcher swap.** I am
recording this as a refutation of my predecessor's recommendation, with the measurement, because
shipping O6 as scoped would have consumed a day and moved recall from 0% to 0%.

Worse: the gate is **unreachable in production anyway**. Its three callers (`screen_idle_axes.py`,
`screen_fred_macro_axis.py`, `screen_exchange_netflow.py`) have `cron_lines = 0` each and appear in
no `daily_research_cycle.py`, `ops/*.sh` or `watchdog.py` path. The measured consequence: in 192
research-memory rows, `failure_stage='novelty_gate'` appears **once**.

### F26 — CRITICAL: the desk built resurrection detection TWICE, on two schedules, and wired the output of NEITHER. Ten dead ideas have had their own revival condition fire.

```
$ grep -rn "graveyard_resurrection_queue" --include=*.py --include=*.sh scripts libs ops app api tools
scripts/graveyard_resurrect.py:22:OUT = Path("data/graveyard_resurrection_queue.json")
# ONE hit. It is the producer's own output path. Cron: 40 4 * * 0, weekly, writing to nothing.

$ grep -rn "negative_knowledge.json" --include=*.py scripts libs app api web ops tools
scripts/negative_knowledge.py:31:OUT = ROOT / "data/negative_knowledge.json"
# ONE hit. Writer only. n=45, refreshed 2026-08-01T02:30, records with triggers_met: 10
```

**Ten dead ideas have had their pre-declared revival condition FIRE**, into a file with zero readers,
refreshed four hours ago: `funding_momentum` [cost_model_improved], `oi_divergence`
[oos_available], `ls_contrarian`, `tftrailbreakout`, `tfatrexitbreakout`, `coinone_kr_premium`,
`era_ta_indicator_stack`, `era_grid_ladder_vol_bot`, `lit_bruteforce_ratio_mining`, breadth re-add.

L1.16a exists to make resurrection *narrow but real*. The narrow half is enforced; the real half is
not wired. Two priority-5 PRIME entries (`defi_health`, `multilingual_wikipedia_attention`) carry the
treatment *"killed at DAILY horizon only. Horizon search is the exact remedy"* — **and nothing
external blocks them.** Both axes are already ingested; the remedy is a multi-horizon re-screen the
TARGET/HORIZON SWEEP DUTY already mandates and `horizon_search.py` already implements (S5).

Integrity bug in both stores: two entries are the markdown **table-header rows** (`"Hypothesis"`,
`"Hypothesis (external prior)"`) parsed as hypotheses and assigned priority 2 with treatment
*"UNCLASSIFIED death — tag it before judging."* So `n=44` is really 42.

### F27 — HIGH: L1.16a's re-entry-condition mandate is met by 28% of the graveyard and by 1 of the 3 kills written since the law passed.

```
$ <parse docs/graveyard.md table rows; git blame -w for dates>
table rows parsed: 43
mechanism-of-death present:  41/43 = 95%     <- EXCELLENT, with numbers
re-entry condition present:  12/43 = 28%     <- the L1.16a mandate
  last 7 days (n=16): 44%      older (n=27): 19%      post-L1.16a (n=3): 1/3
```

The trend is real and improving (44% vs 19%). But L1.16a became constitutional on 07-29 and made the
field mandatory *at kill time*; both 07-31 kills (`carry_entry_shorts_widening_basis`,
`lit_crypto_xsec_size_and_volume`) lack one. **Nothing fences the field.** This is one missing
column, not a documentation-culture problem — the mechanism-of-death half is at 95%.

### F28 — HIGH: `research_erv.py` declares the graveyard handle and never reads it; its "concept-level archaeology" is a frozen 8-entry dict, and it has ranked the same 5 fake candidates every day since it was wired.

```
$ grep -n "GRAVE" scripts/research_erv.py
40:GRAVE = ROOT / "docs/graveyard.md"        # declared, ZERO other references in the file
$ sed -n 64,74p scripts/research_erv.py
HISTORY = {"attention": ("DEAD", ...), "developer": ("MOSTLY DEAD", ...), ...}   # 8, frozen
$ ls data/hypothesis_queue.jsonl
ls: cannot access 'data/hypothesis_queue.jsonl': No such file or directory
$ .venv/bin/python -c "import json;print(json.load(open('data/research_erv.json'))['n'])"
5
```

The docstring claims it *"matches at concept level against the graveyard."* It matches a frozen table
no graveyard write updates. Its queue file is absent, so `main()` falls to the hardcoded 5-item demo
slate at lines 158–176. `research_allocator.py:39` carries the identical declared-never-read defect.
This matters beyond the organ: F25 identified concept-family mapping as the *only* approach that
works, and the desk already has one — inert, frozen, and fed a demo.

### F29 — HIGH: 11 of 13 pre-registrations carry a falsifier that was never exercised, and a construction substitution went unrecorded.

All 13 pre-registrations state kill criteria **before** computation — genuinely well done, e.g.
*"Falsify: 40 fwd days NW-t<=0 or sign flips (attention momentum, not fade → graveyard wrong_sign,
do NOT flip-fit)"*, which pre-commits against flip-fitting the result.

**Resolved with a recorded verdict: 2/13.** The COT pair resolved honestly in `COT_SCREEN_RESULT.md`
(*"Pooled lagged Newey-West t = −0.64"*) and cancelled a multi-week data purchase — the system
working exactly as designed.

The other 11 were EV-rejected pre-compute, so their forward falsifiers never ran
(`data/shadow_sleeves.json` = `[]`; none of the 4 accruing axes matches). **And 8 of the 11 were
later tested under a Stage-A screen rather than the pre-registered "40 forward days, NW-t" test**
(research_memory: equity, fed, cme, index, metal, mining, energy, wikipedia — all `result=failure`).
The pre-registration page was never updated with the substitution or the outcome. Because no card
states a resolve **date**, "past due with no verdict" is formally unmeasurable — which is itself the
L1.29 defect: an ungraded prediction is a belief, not a forecast.

### F30 — HIGH: there is no cumulative screen-side multiplicity accounting anywhere on the desk. The gauntlet deflates as if exactly 2 trials had ever been run.

```
$ .venv/bin/python -c "<select count(*) from trials_ledger>"    ->  0
$ grep -rn "Gauntlet(" --include=*.py scripts libs app api      ->  (empty)
```

`libs/validation/gauntlet.py:89-102`:

```python
def _resolve_n_trials(self, candidate, observed_sr) -> int:
    if candidate.n_trials_override is not None: return max(2, candidate.n_trials_override)
    if self.ledger is not None: ... return max(2, ceil(true_count * multiplier))
    return 2                       # <-- the only branch reachable in production
```

`class Gauntlet` and `TrialsLedger` are a tested orphan pair; `n_trials_override` is set in exactly
one place, `tests/validation/test_gauntlet.py:31`. The hash-chained multiplicity spine
(`prev_hash`, `row_hash`) has never held a row.

Where trial counts actually live — three disconnected places, none cumulative:
`reports/axis_screens/_raw_trials.json` (n=48, 6 days stale, `axis: None` on all 48 so trials cannot
be attributed to a family); per-run literals passed straight to `deflated_sharpe_ratio(n_trials=...)`
with observed values `2`, `6`, `120`, `len(variants)`; and the forward side only
(`holm_bar 2.64, m_concurrent 12`), which *is* correctly enforced.

Compounding with F25: redundant hypotheses are not caught before compute, and the trials they burn
are never counted after. Both halves of multiplicity control are open on the screen side.

### F31 — THE ONE THING WORTH PROTECTING: the CONTENT of the negative record is excellent. Only retrieval and consumption are broken.

```
$ <research_memory, 137 failure rows>
failure_cause 121/137 = 88%    failure_stage 109/137 = 80%    lessons 133/137 = 97%
failure_cause hist: counted-trial-no-edge 42, stats 37, economics 5, contemporaneous-not-leading 2
```

And the best hypothesis rows meet the "who is forced, and why can't they stop" bar exactly
(`rm-20260726T010044-641f6b`, verbatim):

> *"MINER ECONOMICS → FORCED SELLING: miners are the only structurally-forced sellers (USD fixed
> costs vs BTC revenue, unhedgeable); when hashprice falls below marginal cash cost that cohort
> liquidates treasury and powers off, and the power-off is visible in hashrate BEFORE price. …
> Pre-registered sign: NEGATIVE IC."*

Against that: **58% of hypothesis rows (32/55) name no forced agent at all** — e.g. *"CNY OTC premium
predicts next-day BTC return (catalogued prior: premium up = inflow = bullish)"*. Those are
correlations with a label. And `predecessor_id` is **0/192**, so the 97 construction rows that
actually consume the trials budget cannot be joined back to the hypothesis row carrying the
mechanism.

The desk's own measured prior, `research_erv.py:24-26`: *"Every survivor on this desk has been a
SPREAD with a HARD constraint… Every FORECAST died."* **58% of what it logs are forecasts.**

## 3. WHAT COULD MATTER MOST (ranked opportunities)

Ranked by expected impact × confidence / (cost × maintenance). Every item names what it displaces
(L1.14). The default displaced by all of them is the current one: **running an exhausted generator
against a locked pool inside a three-cell search box**, which F6/F7/F8 show produces exactly zero.

**A note on the shape of this list.** Nine of the twelve items are one-line or one-file changes in
front of already-built, already-tested machinery. That is not a coincidence — it is the subsystem's
actual condition. Alpha-discovery is not short of ideas, data, or instruments. It is short of
**wires**. Any recommendation to build something new here is displaced by the ones below.

**O1 [HIGHEST — COMPOUNDING MULTIPLIER] — Wire the stratified campaign window (F2, F1).**
Thread `alpha=CAMPAIGN_ALPHA/k` from `campaign_gate_stats` into `romano_wolf_stepdown` (which already
accepts it), then call `plan_strata` from the six `min_len` sites. **Measured effect: expected
discoveries 1.06 → 159 at a reference true Sharpe of 2.0; per-candidate detection power 0.25% →
37.9%; the best candidate's RW adjusted p 0.522 → 0.089 from the window alone.** This is the largest
quantified improvement to discovery power in the desk's record and it operates on data already on
disk. Complexity: low (the planner is written and tested; the precondition is a keyword argument).
Dependencies: none. Failure mode: wiring the plan without the level inflates family-wise error to
1−(1−0.05)^k — which is exactly why the module refuses to be called, so **do not wire it without the
α**. Validation: `test_campaign_window.py` plus a null-cohort FPR check at the new levels.
Monitoring: publish `retained_fraction` per campaign. Retirement: never — this is the instrument.
Time horizon: 1w to land, effect on every campaign thereafter.

**O2 — Unblock the three refill paths (F6, F7, F8). Three one-liners, three different axes.**
(a) add `timeframe` to `Hypothesis` and to `content_hash` → the H8 resolution becomes testable for
the first time, and 8h is the desk's own named remedy for the daily low-pass gate (vif 1.008 vs 3.6);
(b) run the D1 factory in batches over the full 279-symbol lake instead of `limit=30` → 3,486
candidates at zero acquisition cost; (c) either lower `--min-age-days` to ~14 or pass it explicitly
in cron → the resurrection feeder stops selecting zero, instead of waiting until 2026-08-10 for an
arithmetic accident to clear. **All three are currently invisible because two of them print
reassuring text.** Complexity: trivial ×3. Validation: `tested>0` in the factory log — a criterion the
current state fails unambiguously.

**O3 [COMPOUNDING MULTIPLIER] — Teach the Stage-A harness what a bar is (F17), and re-run the 42
mislabelled 4h cells (F18).** `ZWIN = {1:20, 5:12, 20:6}` is the whole temporal negative space in one
line. Until `stage_a_screen` takes a resolution, every intraday test must be written outside the
audited harness — which is why the only one that exists forecasts volatility with a hand-rolled
Spearman. This is the precondition for O7 and for anything the 7.68 GB tape could ever say.
Complexity: low-medium. Failure mode: a resolution parameter that is not threaded into the
annualisation reproduces F18 at a new scale — so land both together, with the six affected scripts
re-run in the same commit.

**O4 — Wire ONE consumer for the two resurrection stores (F26).** Ten dead ideas have had their
pre-declared revival trigger fire into files with zero readers. Both PRIME entries (`defi_health`,
`multilingual_wikipedia_attention`) are unblocked by nothing external — the axes are ingested and
`horizon_search.py` already implements the remedy. Also fix the two-row header-parse bug in both
stores. Complexity: low. This is L1.16a's "real" half, which has never been built while its "narrow"
half is fully enforced.

**O5 — Anchor `_PREPARED` to `_ROOT` and re-run the certification against REAL peers (F3).** One
`Path` change answers the desk's central strategic question — *is the real 0/420 informative?* — with
a 6.1 MB file already on disk, and un-gates GAP_REGISTER R0040/R0041. Complexity: trivial. Note the
result should be read against O1: certifying at the truncated window measures the truncation, not the
gate, so O5's honest form is *"certify at both windows and publish the delta."*

**O6 — Build the slot-correlation instrument and re-derive `m_concurrent` (F13).** 12 booked slots
are 4.56 effective bets. This is two defects in one number: diversity is 2.63× overstated **and** the
Holm bar is 2.63× too strict, so real forward candidates are being held to a bar the evidence does
not require. Compute the pairwise correlation of the 12 slot return streams and publish both the
effective count and the raw one. Complexity: low. This also gives the desk its first honest answer to
"are we running one bet twelve ways?" — which `run_generation_diversity` has been answering `1.0`
from `n=0`.

**O7 — Run ONE return-predictive test on the moat tape (F19).** 83.8% of desk data, one test ever,
and that test forecast volatility. Five features are `computed_unused` with `tested_constructions: 0`.
Depends on O3 for the harness; does not depend on it for a scripted first pass. Note the honest
framing from the data-moat sweep: the tape's "irreplaceable" premise is refuted (free first-party
Bybit archive is deeper and faster), so the case for this is *utilisation of a sunk asset*, not moat
defence.

**O8 — Screen `data/unlock_events.json` (F21). 24,201 dated events, 174 perp-matched, zero code
references.** Token unlocks are the cleanest mechanism available on the desk that nobody has touched:
a publicly scheduled forced-distribution event with a named agent who cannot postpone. It is
event-shaped, so it routes through `libs/validation/event_study.py` (§42), not a daily return series.
Complexity: low. This is the single best ratio of mechanism quality to work remaining in the report.

**O9 — Make `mechanism` and `predecessor_id` required at log time (F15, F31).** 0/192 rows carry
either. Without them the desk cannot compute its own concentration, cannot answer "which mechanisms
have we never probed?", and cannot join a construction back to the hypothesis that motivated it.
Forward flow is the point; backfill is optional. Complexity: trivial. Yesterday's O9, unmoved.

**O10 — Rebuild novelty as concept-family archaeology, and revive `research_erv` properly (F25,
F28).** Measured recall: Jaccard 0%, TF-IDF 0–12.5%, concept-family 37.5%. The concept-family engine
exists, declares the graveyard handle, never reads it, and is fed a hardcoded demo slate.
**Explicitly supersedes yesterday's O6** (TF-IDF swap), which this sweep refuted with a measurement.
Complexity: medium — and it must be scoped as a build, not a swap.

**O11 — Fence the re-entry-condition field on new graveyard rows (F27).** 28% coverage overall, 1/3
since L1.16a made it mandatory. One field, one check. Complexity: trivial. Cheap enough that the
28%→100% ratchet costs less than arguing about it.

**O12 — Give the screen side a cumulative trials ledger (F30).** `trials_ledger` has 0 rows because
`Gauntlet` has 0 production instantiations, so `_resolve_n_trials` returns the literal `2` in every
production path. Complexity: medium (it is a wiring job, not a build — the schema and the hash chain
exist). Interaction with O1: correcting multiplicity *upward* while O1 corrects the window makes the
two changes push in opposite directions on the same bar, which is exactly why both should land with
the certification re-run (O5) as the arbiter.

**Explicitly NOT recommended, with reasons** (L1.27: a reasoned no is a disposition):
- *Loosening any statistical gate.* Refuted by S2 — the 84 multiplicity-only rejects decay 86% out of
  sample. The gates earned their rejections. Every item above raises power by changing DESIGN
  (window, resolution, universe, cohort independence), never by lowering a bar.
- *Yesterday's O1 (horizon-scaled `ic_min`).* Superseded, not rejected: F17 shows the binding
  constraint is that the harness cannot express a bar at all, which is upstream of what `ic_min`
  should be. Do O3 first; re-evaluate `ic_min` against the resulting power surface.
- *Acquiring new data.* The desk has 9.16 GB on disk of which one directory holding 83.8% has carried
  one test, 1.1 GB of paid CME data is 85% unread, and 3,486 candidates are excluded by a default
  argument. Acquisition is not the constraint and buying more would make the conversion ratio worse.

## 4. WHAT WE TEST NEXT (experiments, success criteria, retirement conditions)

**T1 — Stratified-window flip test (executes O1).** Re-run the 420 through the gate at (a) min-length
and (b) stratified windows, with per-stratum α. Success: a verdict table plus the measured FPR on a
null cohort at the new levels. **Kill criterion: if null FPR exceeds 5% at the stratified levels, the
Bonferroni accounting is wrong and the wiring is reverted** — that is the failure mode the module's
own docstring predicts, so it is the one to instrument. Retirement: n/a, becomes the default.

**T2 — Real-peer certification delta (executes O5).** Run `certify_gauntlet.py` with `_PREPARED`
resolved from `_ROOT`, at both windows. Success: `min_passing_true_sharpe` published for
real-vs-synthetic peers and truncated-vs-stratified windows — a 2×2 that finally separates "the gate",
"the peers" and "the window" as explanations for 420/0. Cost: hours of bootstrap. Information gain:
~1.0; every cell is decisive.

**T3 — Factory unblock smoke test (executes O2).** After the three one-liners: does the D1 factory
report `tested > 0`, and does the H8 factory report `tested = 140` rather than `skipped_dup = 140`?
Success: both. This is a pass/fail with no interpretation required, which is the right shape for a
finding that hid for nine days behind reassuring text.

**T4 — Unlock-event study (executes O8).** Pre-register direction, window and threshold as constants
before computing (§42); run both the fixed window and the triple barrier and publish **both**
verdicts; raise `VARIANTS_TRIED` to price the trials considered. Success: a per-window event-study
table either way. A null is a first-class deliverable and buys free multiplicity budget.

**T5 — Effective-slot-count measurement (executes O6).** Correlate the 12 slot return streams;
publish effective m alongside booked m. Success: both numbers exist and are floored per L1.0.
**Decision rule stated in advance: if effective m < 8, the Holm bar is recomputed at the effective
count and the four `z20→BTCUSDT` axes are consolidated or re-aimed** — writing the rule now prevents
the result being read whichever way is convenient later.

**T6 — Moat first-light (executes O7, depends on O3 for the harness).** One return-predictive screen
on `imbalance` and `depth5` at native resolution across ≥20 of the 80 feeds. Success: a screen
artifact that records its bar. Retirement: if three orthogonal microstructure features across 20+
feeds produce nothing at any expressible horizon, that is the first real evidence about the tape and
it goes in the graveyard **with its re-entry condition** (O11).

**T7 — Novelty recall bake-off (executes O10).** Score Jaccard / TF-IDF / concept-family on a
held-out set of ≥20 paraphrased graveyard entries. Success: recall@1 published per method and a
decision recorded. Retirement condition: if concept-family cannot exceed 60% recall@1, the gate is
re-scoped to "flag for human review" rather than "block", because a 37%-recall blocker is worse than
no blocker — it produces false confidence that dead ground is being screened.

---

**REGISTER ROWS OWED (§35 / no-orphaned-recommendation law / L1.39).** This audit ran READ-ONLY and
could not row its own findings. The next live cycle owes one `scripts/recommendations.py add` row per
opportunity **O1–O12** (or a reasoned rejection), and `scripts/track_findings.py` rows for **F1–F31**.
Three items are also **corrections to existing ledger rows** and must be handled as such, not as new
work: yesterday's **O6 is REFUTED** by F25 and should be re-scoped, not implemented as written;
**R0211's claim that LEVEL-REACTION was "tested exactly once" is a matcher artifact** (F16) and the
true count is zero; and the `20260801_research-engine.md:895` **"J = 0.000 → 0.977" figure is a
self-similarity, not paraphrase retrieval** (F25). Per the coverage ratchet, reaching 100% by not
rowing these is the denominator trick; this paragraph exists so the omission cannot be silent.

## APPENDIX A — SIX-PERSPECTIVE COVERAGE LOG

**1. INTERNAL (measured, not configured).** F1 (power curve from the certification artifact), F2
(pickle lengths), F6–F8 (factory log, `content_hash` source, age arithmetic), F13 (slot tuples), F14
(`n:0` with entropy 1.0), F19 (`feature_library` statuses), F30 (`trials_ledger` count). Every
strength in §1 verified from an artifact timestamp or a row count, never a schedule.

**2. EXTERNAL — the motive-similar Tier-1 cohort.** Three transferable practices, and one direct
re-grade:

- **`forward_history_depth` is mis-graded and I am saying so.** `TIER1_BENCHMARK.md:76` records it as
  `T=310d bar … otherwise one day per day | time_bound: **yes**` — i.e. only the calendar can fix it.
  **F2 refutes that.** The mean candidate already holds **1,808** observations and the longest holds
  **4,594**; T=310 is a truncation artifact, not a calendar fact. This row is not time-bound, it is a
  wiring job, and `run_max_push.py` parses that table — so the mis-grade has been actively keeping the
  desk's single highest-leverage fix out of the queue. **Re-grade to `time_bound: no`, closer: O1.**
- **RenTech/Medallion (the ceiling exemplar) and XTX** run enormous numbers of weak, decorrelated
  signals and take their edge from *combination*. `gate_power_audit.md:§7` measures the desk doing the
  opposite: it scores each leg alone against a bar only an assembled portfolio could clear — 5 legs at
  true SR 1.0 make a portfolio SR of 2.24, while P(all five clear individually) is 9e-21. The desk's
  gate is architecturally hostile to the cohort's dominant strategy.
- **Jane Street / Optiver / IMC** would not have a research pipeline where the entire Stage-A screen
  layer is unscheduled (F4). Cadence is a first-class engineering property at those firms; here 0 of
  13 screens have one.
- **Negative exemplars (control group).** Which of our rails would have caught them? *LTCM* — the
  correlation-blindness failure — is the one this subsystem is currently closest to: F13 shows 12
  positions booked as 12 independent bets that are 4.56, with **no pairwise correlation instrument
  anywhere on the desk**. Our rails would NOT have caught LTCM's specific death, and O6 is the fix.
  *Archegos* (concentration) is covered by the capacity/sleeve rails. *Alameda* (commingling) is
  covered by the NAV attestation chain.

**3. FUTURE (2–3 years out).** The binding constraint here is not compute, and that is worth stating
plainly because it is the kind of thing a future-perspective section usually gets wrong. With 2028
compute the desk would still have `ZWIN = {1:20, 5:12, 20:6}`, still hash hypotheses without a
timeframe, and still cap the universe at 30 symbols. What 2–3 years genuinely changes: (a) LLM-native
**concept-family** matching makes O10 cheap and reliable, retiring bag-of-words novelty entirely;
(b) cheap long-context models make the 7.68 GB tape searchable by description rather than by
hand-written feature; (c) synthetic-market generators make F1's power problem partly addressable by
simulation rather than by waiting for history. None of the three helps until the wires in §3 exist.

**4. CONTRARIAN (assumptions actively tested, not assumed).** I opened this audit believing the
multiplicity gates were killing good candidates and **the data refuted me** (S2: 86% out-of-sample
decay on the 84 multiplicity-only rejects). I tested whether `reality_check` was a campaign constant
in disguise and **it is not** (S3: the 13 distinct values are Romano-Wolf step-down ties, which is
correct behaviour). I tested yesterday's prescribed novelty fix and **it does not reproduce** (F25).
The one standing assumption that did fall is the biggest: *"420 tested, 0 survivors"* has been read
as a fact about the market for nine days and is a fact about a 0.25%-power instrument (F1).

**5. GREENFIELD.** Rebuilt today with only validated knowledge, the changes are: (a) the screen
harness takes `(resolution, horizon)` as a first-class pair, not a dict lookup; (b) candidate identity
includes every dimension that makes a test distinct (timeframe above all); (c) one candidate store,
not five — `sor_research` (14), `sor_autodiscovery` (57), `sor_crypto` (434), `alpha_registry` (8
cards), `sor_research_lake*` (2 more) are the same table shape six times, and the diversity gauge
picked a seventh path that never existed; (d) campaigns stratify by available history from day one;
(e) every store has a declared reader before it has a writer. Historical baggage score: **high** —
three of the six stores are frozen, and one live organ points at a seventh that has never existed.

**6. FRONTIER (what became possible recently and is unexploited).** The free first-party Bybit L2
archive (200 levels/100 ms vs our 25/4,080 ms, 345 d vs 10.6 d) was identified by the data-moat sweep
and sits in our own universe map at `status: queued` — it makes O7 both cheaper and better than
running on our own tape. Deribit historical access is verified by actual download, satisfying the
options-VRP kill's own re-entry condition for free (resurrection queue, priority 3, *"starved, not
wrong"*). Neither is blocked by anything.

## APPENDIX B — NEGATIVE-SPACE SWEEP LOG

Questions never asked, data never screened, methods never attempted. **A documented empty seam is a
result** (L1.25a) — the seams below marked GENUINELY EMPTY are recorded as knowledge, not as gaps.

**Never tested at all** (each verified by grep returning zero, or by a `tested_constructions: 0`
field): order-book imbalance (code exists, never run); liquidations/cascades (50,317 rows, readers =
writer + freshness check); cross-venue latency/lead-lag (both tapes recorded, nothing joins them);
options gamma/dealer flow; stablecoin depeg; **token unlocks (24,201 events, 0 code references)**;
MEV/priority fees (0 hits repo-wide); funding *term structure* (0 hits across all screen artifacts);
day-of-week / month-end / **expiry** effects.

**Refuted by arithmetic, never by data — and now protected by the novelty gate.** `correlation_regime`
(EV 0.0003, *"reject before research"*), `stablecoin_mint_burn`, `crypto_equity_leadlag`,
`liquidation_heatmap_cascade`. All four sit in `docs/graveyard.md` and read as "killed" to any grep.
**This is the most dangerous shape in the report**: the graveyard is being used to defend ground it
never walked, and L1.16a's narrow door will now block anyone from re-proposing them.

**Resolutions never expressible:** 1m, 5m, 15m, 30m, 2h, 6h — at any horizon, per F17. Not
"untested": *inexpressible* in the audited harness.

**Data on disk with zero analysis:** `data/moat` 7.68 GB (5 of 80 feeds, 35 obs, wrong target);
`data/lake/bronze/cme` 944 MB of paid Databento statistics + 1h bars (zero readers);
`binance_metrics` 5-minute archive (down-sampled to daily, then declared redundant with its own
down-sample); `deribit_surface.parquet` (78 rows, not in crontab, zero consumers).

**Public information named and never collected** (zero collector code each): GDELT, pytrends, Xatu,
mempool.dumpster, Flashbots, CryptoPanic, Numia, BigQuery public datasets, Reddit. Attention is
monitored by exactly one source: Wikipedia pageviews for **three pages**.

**GENUINELY EMPTY — checked, nothing there, recorded as knowledge:**
- *Non-USD quote pairs / inverse perps.* Not under-covered — **unreachable** behind
  `quoteAsset == "USDT"` in the single universe function (F24).
- *DEX/AMM microstructure.* 2 grep hits, both ticker-string lists. No pool, swap or LP data anywhere.
  Hyperliquid (perp DEX) is the sole genuine exception and *is* probed.
- *Prediction markets.* Genuinely tested — 167 markets, 8 calibration buckets, 3 strategies, all dead
  on `n=167 < 250`. Tested and underpowered, not unlooked-at.
- *Survivorship.* One honest positive: `backfill_oi_ls_oos.py:22` explicitly includes delisted
  symbols. No other screen makes the claim.
- *Regional venues.* KR is the deepest non-US coverage (175-asset × 400d panel, honest null); TR
  screened; CN OTC premium collected. **JP, BR, RU: catalogued only, zero collectors.**

**Failure modes never simulated:** an edge that works only in one funding regime; a venue outage
mid-signal; the desk's own crowding into its own edges as size grows.

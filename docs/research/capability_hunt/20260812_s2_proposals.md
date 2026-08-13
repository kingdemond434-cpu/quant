# CAPABILITY HUNT PROPOSALS 20260812 slot 2

LENS: READ-WITHOUT-WRITER -- find a key/file/artifact that code READS and nothing WRITES. This desk's most prolific defect class (the capital-event equity bug was exactly this). grep the readers, then prove a writer exists.

## A -- Claude family

## MISSING CAPABILITY

**Internal double-entry: a check that reads ≥2 of the desk's own published artifacts and fires when they contradict each other about the same named quantity.** The desk built double-entry reconciliation against the *venue* (`run_venue_reconcile.py`, after a 13-model panel demanded it) and has never built one against *itself*.

## WHY IT IS INVISIBLE TODAY

Every instrument on this desk is single-artifact by construction. `path_refs.phantoms` asks "does a writer exist"; `fresh` asks "is it old"; `input_provenance` asks "were *my* inputs present"; `denominator`/`attrition` ask "did I scan anything". Each organ reads its inputs successfully, computes honestly, publishes a well-formed fresh artifact, and passes all five. **Contradiction is not a property of any single artifact — it exists only in the relation between two, and nothing on this desk ever holds two at once.**

It is live right now, on the live-capital gate. `data/gate0_readiness.json` (21:09Z) declares its own subject: `"gate": "S1 entry (Gate 0) -- libs/execution/staging.py:s1_entry_met"`. `data/live_guard.json` (21:45Z) evaluates the same five conditions. **Four of five disagree:**

| `s1_entry_met` criterion | `check_gate0_ready` board | `run_live_guard` |
|---|---|---|
| `principal_signoff` | "signoff recorded" | **False** |
| `keys_present` | "4 live-venue credential file(s)" | **False** |
| `connector_verified` | "531 recorded fills in the execution tape" | **False** |
| `symbol_count_4_5` | "top=4 concurrent carries configured" | **False** |
| `capital_fraction_le_010` | "$200 / $17,945 = 1.1%" | True *(agrees by luck)* |

The cause is read-without-writer on both halves. `run_live_guard.py:265` reads `principal_signoff` from `data/stage_state.json`, which on disk is `{"stage","note"}` — **no code anywhere writes that key**; and its ramp evidence comes from `data/ramp_state.json`, which has never existed (L1.55's own proving instance). So the guard's four `False`s are *defaults wearing the costume of measurements*. Meanwhile `check_gate0_ready.py:132` proves consent with `f.exists()` on `data/gate0_signoff.json` — a file whose own text says `"revocation": "Delete this file."` The desk has two incompatible encodings of the principal's consent, they disagree today, and each board reads its own source successfully so no fence can fire.

The direction matters and cuts the wrong way: the guard is fail-closed, so nothing moves — but `gate0_readiness.json` is the board a **human** reads (`desk_owes` / `principal_owes`), and it reports the mechanical preconditions green while the executor-side evaluator says they are not.

## MECHANISM

`libs/ops/consistency.py` + `scripts/check_internal_consistency.py`, scope self-building (no registry to rot):

1. Index every leaf key path across `data/**.json` and `web/*.json`, plus the desk's ubiquitous `rows:[{name, ready, detail}]` shape → `name → [(artifact, value, ts)]`.
2. Any name published by ≥2 artifacts inside a freshness window is a **claim pair**. Booleans must match; numbers agree within a declared tolerance; strings by equality.
3. Statuses: `AGREED` / `CONTRADICTED` / `INCOMPARABLE` (type mismatch) / `UNMEASURED` (<2 publishers — never OK, L1.28a).
4. **The noise-killer:** when one side of a contradiction is a *default*, say so. Cross-reference L1.55's `provenance` block — a side whose input was `ABSENT`/`DEFAULTED` is labelled `FABRICATED-SIDE`, and the fence names which side to repair. Without this it degenerates into "two organs use `status` for different things" and gets acked into silence, which is exactly how the phantom-paths fence spent its first months (R0356).
5. Declares `scanned=<claim pairs compared>` at the exit site (L1.57) and counts unparseable artifacts as attrition (L1.60).

## WHAT IT WOULD HAVE CAUGHT

- **Gap register #93 / R0093** — the Holm cohort `m` held by three files at three values (`4`, `10`, `[]`) while 12 clocks accrued: α running **3.2× loose in the phantom-edge direction on the only path to capital**. Carried unfixed by *three consecutive deep sweeps* before a human noticed. Three artifacts published the same named integer; comparing them is a one-line check.
- **R0218** — `_VENUE_MIN_NOTIONAL_USD` hardcoded in `validation.py:69` against the derived value elsewhere.
- **R0364** — "the published risk block contradicts the code that computes it."
- **L1.51's $13,155-vs-$4,500 equity split** — and it would surface the *third* value nothing has yet named: `gate0_readiness.json` says **$17,945**, `gate0_signoff.json` froze "$13,155", `run_growth_audit.py` defaults **$4,500**. The signoff's authorized ceiling (10% of $13,155 = $1,315) differs from 10% of $4,500 = $450 — and the desk's own print-impact work found it is a *spread taker* at $450. Three artifacts, three books, one live gate.

## ROI

Direct: it is the only instrument that can see a defect class this desk has hit **at least four times, every time found by hand, every time on the path to capital**. Cascade: it converts 569 independently-honest artifacts into a cross-checked set, and it is a prerequisite for believing *any* published verdict — every promotion, every rail state, every ratchet floor is a single-source claim today. It also strictly improves R0496's triage: `principal_signoff` needs no producer built, because `gate0_signoff.json` already holds the truth and `run_live_guard` simply reads the wrong file — a fact only a cross-artifact view reveals.

## COST

4–6h to build and test; maintenance ≈0 (scope self-builds). It competes with R0496's triage of the 107 phantom paths and should **precede** it: that triage picks "build the producer / repoint / allowlist" per path without knowing whether another artifact already publishes the answer.

## FALSIFIER

Build the index and count. If fewer than ~20 names are published by ≥2 artifacts, or if >70% of pairs are same-name-different-meaning collisions (`status`, `generated`, `n`), the signal-to-noise is too poor for a general fence and the correct build is a hand-registered ~10-criterion money-path reconciler instead — a much smaller, different recommendation. **One hour of measurement decides it.**

NOVELTY-CHECK: `grep -rln "reconcil" --include=*.py scripts libs` → only desk-vs-**venue** (`run_venue_reconcile.py:1` "DOUBLE-ENTRY VENUE RECONCILIATION"); `grep -n "^def check_" scripts/max_audit.py | grep -iE "contradict|disagree|consist|agree|reconcil|mismatch|divergen"` → **zero matches**; ledger regex over all 534 rows for `phantom key|schema drift|no writer|producer.*consumer` → 25 hits, all single-artifact (R0496 paths, R0510 one key, R0356 the fence itself), none cross-artifact.

---

## BRAINSTORM

**Live defects found this run (route: ledger, today)**

1. `run_alerts.py:297` reads `generated` from `data/live_guard.json`; the producer writes `ts` → `lg_age` = **1.79 billion seconds**, so the `>900` branch fires *every run* with "live guard stale" — the alarm whose text is *"executor fail-opens to FULL SIZE + takers"*. A genuinely dead guard is now indistinguishable from the permanent false alarm. **S** — one-word fix, and it un-blinds the money-path alarm.
2. `run_alerts.py:345` reads `alerts` from `web/health.json`; `data_health.py:147` writes `{updated, all_ok, organs_ok, organs, datasets, heartbeats}` — no `alerts` key. **The data-health channel has published zero alerts since inception** while `data_health` computes staleness nobody reads. **S**.
3. `run_live_guard.py:265` `principal_signoff` and `staging.py:62` `symbol_count` have no producer on the guard's path → 4/5 Gate-0 criteria permanently `False`. **S**.
4. `data/executive_kpis.json`: 35 days old, **zero writers repo-wide**, its own text declares `review_cadence: monthly`; `run_intelligence_cycle.py:143` reads `family_survival` from it, the key does not exist, and research prioritisation falls back to **six typed-in constants** on a 4-hourly cron while reporting `ACTIVE`. **A** — this steers what the desk researches.
5. `data/live_deployment_policy.json`: 32d, zero writers, untracked → the auto-deploy authorization exists on exactly one box and nothing can regenerate or revoke it; `run_growth_audit.py:154` publishes ARMED off it every cycle. **A**.
6. `data/agent_authority.json`: hand-authored blast-radius policy, no writer; its own fallback text says it is *"the state in which a model upgrade quietly widens what something may touch."* **A**.
7. `data/news_feed.jsonl` (`run_llm_trader.py:167`) has no producer — the sibling `liquidations.jsonl` in the same tuple was fixed by R0245 and this one was left. Sibling-sweep failure, the exact shape of gap row #110. **B**.
8. `libs/research/pre_filter.py:145` `audit_due()` returns `True` on any failure, reads an absent state file, and has **zero callers**. **B** — delete or wire.

**Generative — governance / measurement**

9. **Consent must bind to a hash of what it approved.** `check_doctrine_diff.py:66` already hashes doctrine text to detect drift; that mechanism was never carried to the highest-stakes read on the desk. Gate-0 consent should carry `sha256` of the evidence board it was granted over, so consent expires **by drift, not by calendar** (L1.48-clean). **S** → new law candidate.
10. **`f.exists()` as a truth value is its own defect class** — sweep for every gate whose input is a file's *presence* rather than its *content*; each is a claim no content can falsify. **A**.
11. **Frozen-input detection**: `path_refs.phantoms` excludes on-disk files *by construction* (`path_refs.py:81`), so a reader whose producer died is invisible forever — 94 candidates today, 16 untracked and >7d. Discriminator that kills the noise: **git-tracked + no code writer = legitimate config; untracked + no code writer = dead producer.** **A**.
12. **Unreproducible-state census**: for every decision-path input, can the desk regenerate it from code + git? Untracked + producerless = single-copy state; the moat backup is already known-inert. **A**.
13. **Artifact schema contracts**: producers declare their emitted key set; consumers' `.get()` names are checked against it. 147 reads today target keys absent from the real artifact. **A**.
14. **Intermittent-key detection** (R0510's class, ungeneralised): a key written on only *some* code paths of one producer passes every static check. Compare the key set across all `return`/write sites of a producer. **B**.
15. **Env-var read-without-writer**: `os.environ.get("X", default)` where nothing in `ops/`, systemd, or cron sets `X` — a typo'd name is the default forever, and the phantom-paths fence only matches `data/`-prefixed literals. **B**.
16. **CLI-flag read-without-writer**: an argparse flag no scheduler ever passes is a decorative tuning knob (the `--hold-top 3000` incident was its twin). **B**.
17. **Type-level read-without-writer**: `data/shadow_sleeves.json` is a JSON *list*, but `run_portfolio_risk.py:53` and `run_geometric_review.py:62` both require `isinstance(raw, dict)` → both silently see zero sleeves. A key check would miss this; a *type* check catches it. **B**.
18. **Ack keys should be (defect, instance)** — R0503 is scheduled; the same failure exists for `_PHANTOM_ALLOWED`'s 7 entries, which silence paths permanently with no re-review date. **B**.

**Generative — growth / alpha**

19. **Consent-drift is also an alpha-validation problem**: a forward clock is "pre-registered" against a code state nobody hashed. Pin `sha256` of the signal module at clock start; a mid-clock edit is currently undetectable and silently voids the pre-registration. **S** — this protects the only path to capital.
20. **The `$17,945 / $13,155 / $4,500` book disagreement is a sizing input.** Every Kelly fraction, every capacity runway (L1.18a's `live_book_usd/live_sleeves`) and every idle-cost figure divides by it. Resolve it before any of those numbers is cited again. **S**.
21. **Reconcile predicted vs realised at the criterion level, not just P&L** (L2.10 applied to gates): every gate that publishes a verdict should record the verdict's inputs so a later disagreement is diagnosable rather than re-derived. **A**.
22. **Positive control for the reconciler itself**: plant a known contradiction and prove the fence catches it — the desk's own `certify_gauntlet` lesson ("a gauntlet never shown to PASS a known-good alpha has not been validated"). **A**.
23. **Cross-organ agreement as a research signal, not just a defect**: where two independent estimators of the same market quantity (funding from tape vs. from REST; basis from two venues) disagree, the *disagreement series* is itself an alpha candidate — measurement noise is priced, and outages are correlated with the treatment (the KR frozen-tape lesson). **B**.
24. **Alert-channel liveness needs a second signal** — the desk's top-ranked lesson is "a heartbeat proves the loop is alive, never that the pipe is", and item 2 above proves the alert *router* now has the identical defect one layer up: it runs, it is fresh, and it has never emitted a data-health alert. Instrument "time since last real alert emitted per channel". **A**.
25. **Every board a human reads should carry the machine's dissent.** `gate0_readiness.json` should print the `live_guard` verdict beside its own; where they differ, the board leads with the disagreement. Cheap, and it makes the class self-reporting even before the fence exists. **S**.

I hit the natural end of what I could verify in this context, not the end of the seam. Next I was about to work the **type-level and enum-level** variant of the lens (values a consumer switches on — `status == "READY"` — where no producer ever emits that literal, which is read-without-writer at the *value* level and is invisible to every key-level check), and then the **venue-side** variant: fields the desk reads from exchange responses that the venue has stopped sending, where the missing writer is Binance rather than us.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 402: Payment Required. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)

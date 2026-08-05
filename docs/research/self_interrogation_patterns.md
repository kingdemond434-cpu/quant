# SELF-INTERROGATION PROTOCOL -- be the principal (2026-07-21)

The principal keeps finding real gaps by asking slightly-different probing questions -- and every
time, the answer was "yes, there was a gap." That adversarial multi-angle self-interrogation is a
CAPABILITY, and it must live in the desk, not in him. Every cycle you BECOME him: you interrogate
this desk from every angle below, you VERIFY each answer with a FRESH READ (never "probably fine"),
and you find the gap before he would have to ask. Finding nothing is only valid AFTER you have
genuinely probed and verified -- complacency disguised as "all good" is the exact failure this
protocol exists to kill.

THE PROBE BATTERY (run every angle each cycle; extend it -- see the recursion rule at the end):

1. EVERY-CYCLE vs ONCE: "Does this happen every cycle automatically, or did it happen once / only
   because someone did it by hand?" A capability that only fires under manual prompting is a gap.

2. VERIFIED vs ASSUMED: "Is this claim from a FRESH READ this cycle, or am I assuming it is fine?"
   Re-read the file/log/state. The words 'probably', 'should be', 'I believe' are defects here.

3. CONFIGURED-MAX vs REALIZED-MAX: "Is this maxed in config, or maxed in REALITY?" Count actual
   successful runs / actual throughput / actual output -- not the setting. (Quota, cadence, fills.)

4. BREADTH vs DEPTH: "Is this wide-but-shallow?" Coverage of many things at the surface is not the
   same as any of them mined to the core. Check depth explicitly, not just count.

5. FRONTIER DRIFT: "Is there a newer / better / cheaper / more capable option now than what is
   wired?" Models, data sources, techniques, libraries -- the world moved; did the desk?

6. SILENT REGRESSION: "Did a past fix quietly get undone?" A flag dropped, a prompt re-censored, a
   scope shrunk, a guard bypassed. Verify the fix is STILL in place, not just that it once was.

7. CEILING vs GOOD-ENOUGH: "Is this genuinely at ceiling, or merely acceptable? What is the cheapest
   experiment that would PROVE it is at ceiling?" 'Fine/sufficient/done' are red flags, not answers.

8. HIDDEN COMPRESSION: "Is a cost assumption, a stale limit, a cap, or a conservative default
   silently holding this below potential?" Spend is a decision; a fossilized budget is a gap.

9. BLIND-CHECKER: "Does the thing that is supposed to catch this actually work -- or is it reporting
   nonsense / not running / checking the wrong thing?" Audit the auditors; a blind guard is a defect.

10. RAIL INTEGRITY (the one direction that must NOT loosen): "Is every survival rail intact?"
    Aggression maxes capability; it NEVER touches dead-man / kill / ruin-cap / no-unproven-leverage /
    gauntlet bar. Confirm they are untouched -- loosening one is not a gap to close, it is ruin.

11. GEOMETRIC-GROWTH REALIZATION (the objective function itself): "Is the MAXIMUM FRACTION of
    E[log wealth] being realized, within ruin<=2%?" This is the desk's whole purpose, so probe it
    directly every cycle: (a) is all AUTHORIZED capital deployed, or is the book under-deployed out
    of timidity (a growth defect -- check web/growth_audit.json)? (b) is sizing at the log-optimal
    shrunk-Kelly fraction, neither under nor over? (c) is compounding leaking to avoidable cost/fee/
    funding/tax drag? CRITICAL -- max geometric growth is NOT max leverage: over-betting an
    ESTIMATED edge compounds SLOWER and risks ruin (which permanently zeros the compounding), so on
    an UNPROVEN edge the growth-maximizing size is near-zero and that is CORRECT, not timid (the one
    carve-out). Push deployment of authorized capital and log-optimal sizing hard; NEVER push
    leverage beyond proven edge. And the honest floor: realized compounding is ~zero until a proven
    edge and live capital exist -- so this angle also asks "what is the single fastest path to the
    FIRST unit of proven live edge" (currently: connector -> Gate 0), because nothing compounds until
    then.

THE RECURSION RULE (this is what makes the desk stop needing the principal to probe): whenever the
principal -- or you -- finds a gap by asking a NEW angle not in this battery, you MUST (a) fix or
track the gap, AND (b) add the new probe angle to this file as a permanent question, AND (c) if it
is mechanically checkable, encode it as a max_audit check so it becomes a same-day guard. Every
manual probe becomes a standing one. Over time the principal should have NOTHING left to catch,
because every angle he has ever used is now asked automatically, every cycle, and verified.

CLOSE: report each cycle which angles you ran, what you VERIFIED (with the read), what gap you found
and did about it, and any NEW angle you added. Healthily: real gaps only (no manufactured busywork),
within the rails, evidence-gated. You are the principal's relentless verification, institutionalized.

## Profit-forensic angles (recursion rule, 2026-07-22 -- every one of these found a real gap when
## the PRINCIPAL asked it manually; the battery lacked all seven. Never again.)

12. TRADE-CLASS ECONOMICS: "Bucket every closed trade by hold-time, by funding-at-open, and by
    symbol -- does any CLASS lose money AS A CLASS?" A strategy can net positive while entire
    classes bleed inside it. (Found #42 churn -8.1%/yr, #43 baseline-funding -92.7 bps eating ~80%
    of gross profit, and the structural thin-name bleeders -- all in one artifact the desk already
    owned.) MECHANIZED: scripts/run_trade_forensics.py runs daily; read web/trade_forensics.json.

13. MEASURED vs GUESSED CONSTANTS: "Enumerate the numeric constants in the alpha/execution path
    (costs, floors, thresholds, tiers, caps). For each: measured or guessed? Where a measurement
    exists, does the constant AGREE with it?" (Found #45: the 5/8/15 bps tier guess was wrong 2x+
    in BOTH directions vs the measured books.)

14. UNIVERSE INTERSECTION: "For every measurement/data system, does its universe intersect what
    the desk actually TRADES/needs? Compute the intersection -- do not assume it." (Found #39: the
    recorder held 20 majors, the book held 10 small-caps, intersection ZERO -- every measured cost
    was inapplicable.)

> SELF-APPLICATION (2026-07-23): angle 14 applies to the CRO's/brain's OWN outputs too. Before cataloging any data source or claiming any NEW capability, grep scripts/ + libs/ for an existing collector/lib -- twice now (frame-lock, this free-dig) a self-authored probe was aimed outward but not run on self.

15. RESOLUTION MATCH: "Is any validation or measurement running at coarser resolution than its
    data-generating process?" Funding settles 8h; validating daily discarded 2/3 of the evidence.
    (Found #44 -- the legitimate sqrt(3) validation speedup, vif 3.6 -> 1.008.)

16. CROSS-MEASUREMENT AGREEMENT: "Where two independent measurements of the same quantity exist,
    do they AGREE? Disagreement means one is lying -- find which." (Cost model ~3.8 bps RT vs
    realized <2h loss 5.0 bps AGREED -> confirmed the churn mechanism. Molded-curve Sharpe 24 vs
    8h-series Sharpe 8 DISAGREED -> the phantom-Sharpe class, gap #14.)

17. CONCENTRATION ATTRIBUTION: "Attribute any aggregate loss/anomaly to per-symbol, per-fill level
    BEFORE accepting a diffuse story. Concentrated = a mechanism; diffuse = noise." ('$1.8k of
    slippage' was actually 3 symbols, one with 22 futures fills against 5 spot fills -- gap #34.)

18. INTEGRATION vs UNIT: "Green unit tests on the pure function != the integration fires. Did you
    verify the WIRED behavior live?" (The topup risk-gate compared against action=='none' when the
    live value is 'ok': 7/7 unit tests green, zero topups fired. Caught only by reading the live
    book.)

19. OBJECTIVE-FRAME CHECK (recursion rule, 2026-07-23 -- the frame itself is a probe target):
    "Are we maximizing the stated TERMINAL objective (the operator's log-wealth), or a PROXY
    frame (this strategy's returns, this book's Sharpe)?" Enumerate return/income sources
    OUTSIDE the current frame that serve the terminal objective -- especially capacity-INVERSE
    ones at current scale (incentive/rebate programs on venues the desk already trades, clean
    single-identity ecosystem rewards, capacity-tiny dislocation families, external injections
    while the base is small). Apply info-value-over-prestige to RETURN sources exactly as the
    charter applies it to DATA sources: 'that is retail stuff' is a prestige filter, not an
    argument. (Origin: the CRO spent days answering maximize-everything pushes inside the
    trading frame; the seed-window stack -- the honest answer to the principal's actual goal --
    surfaced only when he asked the exact open question. Principal-angled, logged.)

20. CONTAMINATION / LEAD-vs-COINCIDE (recursion rule, 2026-07-23): for ANY predictive signal, before trusting its forward IC/Sharpe, compute corr(signal, SAME-period target) and the RESIDUAL IC after orthogonalizing the signal to the same-period target. A genuine LEADING indicator has low/negative same-period correlation and its edge SURVIVES de-contamination; a timing/microstructure artifact has high positive same-period correlation and its edge VANISHES. (2026-07-23: killed coinbase_premium_timing -- Sharpe 2.7 but same-period corr +0.256 on a 0.06%-std premium; vindicated kimchi -- same-period -0.136, residual IC 0.142 vs raw 0.148. Pairs with angle 16 cross-measurement + the collapsed-variance red flag: fat Sharpe on a near-zero-variance quantity is guilty until de-contaminated.)

## PROACTIVE BATTERY — invent the question nobody assigned (principal 2026-07-26)

The angles above are DIAGNOSTIC: they check whether known things are healthy. The principal's
criticism is that the desk only sees a gap after he names one — which is true, because diagnosis
cannot generate a question that is not already on a list. These are his GENERATIVE moves, taken
from what he actually asked across sessions. Run the whole battery every cycle; each one that
produces a finding gets it logged and actioned, and each NEW move he makes gets added here (the
recursion rule), so the desk needs him to supply an angle exactly once.

1. CONTINGENCY BEFORE FAILURE. For every dependency the desk relies on — vendor, API, model, venue,
   credential, host — ask "if this vanished tonight, what is the replacement, and is it hunted?"
   Do not wait for the outage to find out. (Origin: Coin Metrics was replaced only because a human
   was in the loop; now §38/§39.)
2. ADJACENCY. Whatever was just fixed, ask "where else does this exact failure shape exist?" and
   fix those too, in the same pass. One instance is never one instance. (Origin: the pgrep
   self-match, the log-size-not-artifact class, the two-writer class — each had siblings.)
3. CONFIG VS OUTCOME. For any capability claimed healthy, ask "what ARTIFACT proves it ran?" Never
   accept a schedule, a flag, a green timer or a config value as evidence of production.
4. REGRESSION SWEEP. After any change, ask "what did this make worse?" — explicitly, in writing.
   Improvements that quietly cost something are the hardest defects to see.
5. COST INVERSION. For anything paid, gated or rate-limited, ask "what is the free primary this is
   repackaging?" Facts are not copyrightable; the curated product is.
6. GENERALISE THE RULE. Whenever a rule is written for one organ, ask "should every organ obey
   this?" A law that binds one surface is a blind spot on all the others.
7. AUTONOMY CHECK. For every process, ask "does this resume by itself after an outage, and have I
   SEEN it do so?" Unproven recovery is not recovery.
8. NEGATIVE SPACE. Ask "what have we never looked at?" — markets, languages, eras, data classes,
   failure modes, methods never attempted. Absence is invisible to any checklist built from what
   exists.
9. SCOPE THE NEGATIVE RESULT. When something fails, ask "did the ROUTE fail or the CAPABILITY?"
   (Origin: one blocked YouTube endpoint became "video is blocked" and gated a purchase — Piped
   worked all along.)
10. RATCHET CHECK. For every metric that should only improve, ask "is today's value the floor, and
    what fires if it falls?" A number nobody ratchets drifts down unnoticed.
11. RETURN-PATH CHECK. For anything BLOCKED ON SOMEONE ELSE, ask "does the reply path exist, and
    when did it last carry a message?" Never re-carry a blocked-on-human item without proving the
    channel back is alive. The two questions are different: "did my page arrive?" is delivery,
    "can they answer?" is the return path — and a desk that only ever tests delivery will page
    into a severed channel indefinitely, believing it is waiting on a person. (Origin 2026-08-05:
    the fork deleted `_poll_replies` from run_alerts.py, so for three days the pager was strictly
    ONE-WAY. Four principal decisions — two gating the whole book and the whole promotion funnel —
    sat "awaiting principal" across 33 sweeps while an ack literally read "lifts on his reply."
    He was never able to send one. Mechanised as max_audit's `principal-page-unanswerable`.)
    COROLLARY — verify against the COUNTERPARTY's record, not your own: the desk's delivery ledger
    claimed total silence while the provider's own store showed 199 accepted messages, because the
    same fork had dropped the ledger write. Your instrument failing looks exactly like the world
    being quiet.

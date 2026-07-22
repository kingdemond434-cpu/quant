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

# OPS CHECKLIST -- mandatory before/after any operational action
_Codified 2026-07-21 from this week's actual operator errors (each rule has a incident behind it)._

BEFORE launching any long-running remote job:
- [ ] detached? `setsid -f ... </dev/null` (07-19: cycles died with the SSH session, twice)
- [ ] spend-bearing? check the balance FIRST (07-20: two panels fired into exhausted credits;
      the 'verification run' verified nothing)
- [ ] editing shell-embedded prompt text? run the dollar-audit: count `$<digit>` before/after
      (07-19: unescaped $300 killed every brain cycle silently)

BEFORE claiming any process state:
- [ ] pgrep patterns use the bracket trick `patter[n]` (07-19 AND 07-20: self-matching monitors
      reported a dead cycle as RUNNING for 80 minutes)
- [ ] use UNFILTERED listings before declaring something dead (07-19: grep -v pipes ate live
      processes -> false 'died' diagnosis -> wasted relaunch + lost cycle output)

BEFORE claiming any outcome:
- [ ] fresh read of the artifact (log tail, file size, ledger id) -- never 'the command was
      supposed to' (constitutional verify-then-claim; multiple incidents)
- [ ] deleting latch/state files? ALL of the set or none (07-20: partial dead-man reset
      re-asserted the kill and looked like a fresh fire)

BEFORE reading any secrets file:
- [ ] extract named fields only; NEVER print provider dicts (07-20: OpenRouter key + 07-20:
      Databento key both hit chat; both required rotation)

WHEN a primary data feed is blocked (FRED throttled, CFTC down, a calendar mirror gone):
- [ ] do NOT record the family as "quiet ground" -- three families starved on all 297 sweep
      passes of 08-27 because every producer knew ONE upstream (principal: "data blocked ->
      the fixers always immediately find alternative ecosystem data")
- [ ] fetch through the alternate-route registry, which records WHICH route served each feed
      in data/data_route_provenance.json so provenance travels with the switch:
      `.venv/bin/python scripts/data_alternates.py <feed>` (macro series via DBnomics, market
      series via Stooq; routes needing packages the box lacks report UNAVAILABLE, never
      half-import)
- [ ] a route that served is a producer change owed, not a workaround: name the feed and the
      route in the gap register so the collector learns the alternate permanently

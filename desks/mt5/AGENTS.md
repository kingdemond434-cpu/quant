# Agent instructions (binding)

1. Read `docs/UNIVERSAL_PROMOTION_PROTOCOL.md` before doing anything.
   It is binding on every session: fail closed, absence is never permission,
   and the universal 10-gate pass is the single path to capital.
2. Universal gate is the only survivor gate. Battery numbers are descriptive.
3. Survivors proceed: universal 10-gate → signal gate (INFORMED required,
   else excluded) → allocation → deployment. `reports/SURVIVORS_LEDGER.json`
   is the ledger; count `n` and act on every new survivor.
4. Architecture is frozen (protocol rule 11): new ideas go to
   `data/research_queue.json`, not into the codebase ad hoc.
5. Research pipeline ticks hourly (research_loop); desks are perpetual;
   supervisor respawns anything that dies (logs in local temp dir,
   NOT OneDrive).
6. Hold files `data/HOLD_<target>` pause a supervisor target. Lifting a hold
   resumes it. Do not fake markers.
7. VPS (quant@95.216.191.70, desks/mt5) is the always-on research authority
   when this box is off; changes must be synced (scripts/sync_to_vps.ps1)
   and pushed so every brain sees them.

## CANONICAL LIVE BOX (2026-08-22, standing until superseded here)

**Contabo (`C:\opt\quant`, Windows) is the sole canonical live execution box.**
It runs MT5-Gateway/MT5-Hourly/MT5-Shadow/MT5-ShadowSync/MT5-ResearchSupervisor
against the FUSION LIVE account (server `FusionMarkets-Live`), and its
`reports/shadow/shadow_health.json` (synced to Hetzner every 15 min by
MT5-ShadowSync) is the ONE authoritative shadow-evidence state -- it now also
carries `gateway_armed` and `promoted_live_sleeves` so live-arm state is
visible without a shell on the box.

**The principal's laptop (`C:\Users\dell\mt5-research`) is RETIRED, not idle.**
Its MT5-*, QuantMT5Frontier and MarkerTest scheduled tasks are disabled ON
PURPOSE -- that collector reads a VANTAGE account (`VantageMarkets-Live 14`),
which is why its own `promotion_authority` correctly reads `false`
(`"fusion" in server.casefold()` fails for Vantage; that is the safety check
working, not a defect to fix). It was retired 2026-08-22 because Contabo now
covers this role and running two live collectors risks exactly the shared-
state collision this file already warns about in rule 7. **DO NOT RE-ENABLE
IT** to "restore Fusion bars" or "fix" `promotion_authority=false` -- both
read as broken from the laptop's own vantage point but are the retirement
and the safety check working as intended. If a brain cannot reach Contabo
directly (e.g. SSH host-key mismatch) that is a REACHABILITY problem to
solve on its own terms, never a reason to re-enable the laptop as a stand-in.

Any brain finding this note stale (a new box, the laptop un-retired on
purpose, Contabo decommissioned) should update this section in the same
commit that changes the topology, not leave the next reader to rediscover it
by re-breaking something already fixed once.
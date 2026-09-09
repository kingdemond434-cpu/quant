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
## Growth governance (binding, principal order 2026-09-04)

Two rules, applied everywhere, now and in future. `scripts/check_growth_governance.py` requires
them verbatim on this surface and breaches when they are absent -- which is what happened when a
VPS runtime-state push (c2703fbd) overwrote this file without them, and the fence read red until
2026-09-09. The canonical statement, with what they mean, is `docs/GROWTH_GOVERNANCE.md`.

> **Rule 1.** Every risk reduction mechanism must prove that it increases robust forward E[log W].
>
> **Rule 2.** Every strong opportunity must be allowed to increase capital above normal when the evidence supports it.

Neither rule is a licence to raise leverage by fiat: Rule 2 is permission for EVIDENCE to raise
size, and Rule 1 is the burden of proof any shrink, cap or veto has to discharge first.

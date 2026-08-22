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

## VERIFYING CONTABO WITHOUT A SHELL ON IT

No installer in this repo ever enables an SSH SERVER on Contabo -- every SSH
usage that exists (sync_to_vps.ps1, sync_shadow_to_vps.ps1) is Contabo acting
as the CLIENT, reaching OUT to Hetzner. Nothing sets it up to accept inbound
connections. A brain that tries to SSH INTO Contabo directly is fighting an
undocumented, unsupported path -- and the failure mode observed 2026-08-22
was exactly this: blocked by a host-key mismatch, unable to verify Contabo,
and it substituted the laptop as a stand-in instead. That substitution is
never correct (see above); the right move is a different verification path,
not a different box.

**THE SUPPORTED PATH: read Hetzner's synced copy.** MT5-ShadowSync already
pushes `reports/shadow/shadow_health.json` from Contabo to Hetzner
(`/home/quant/quant-platform/desks/mt5/reports/shadow/`) every 15 minutes.
That file carries `status`, `configured_sleeves`, `sleeves_with_forward_
trades`, `evidence_blocked_sleeves`, `errors`, `gateway_armed` and
`promoted_live_sleeves` -- everything needed to answer "is Contabo healthy
and what is its live-arm state" without ever touching Contabo directly. Any
brain with Hetzner access (`quant@95.216.191.70`) or a synced local checkout
reads that file. This is the DEFAULT verification method. If it looks stale
(older than ~20 minutes), the finding is "the sync pipe may be down," not
"Contabo may be down" -- those are different problems with different fixes.

**IF DIRECT SSH TO CONTABO IS GENUINELY NEEDED** (running a live command,
not just reading state) and it presents a host key that doesn't match a
cached one: DO NOT accept-and-continue, and DO NOT disable host-key checking.
Verify out-of-band first, from a channel a network attacker cannot also
control:
  1. Log into the Contabo customer portal -> the VPS -> its VNC/KVM console
     (not a network SSH/RDP session -- the provider's own screen view).
  2. From that console, in an elevated PowerShell: check whether an SSH
     server is even running (`Get-Service sshd -ErrorAction SilentlyContinue`)
     and if so, its host key fingerprint (`ssh-keygen -lf
     "C:\ProgramData\ssh\ssh_host_ed25519_key.pub"` once OpenSSH Server is
     confirmed installed, or the equivalent Ed25519/RSA key file present).
  3. Compare that fingerprint, read from the console, against what the
     failing SSH client reported. Match -> the earlier key was stale
     (reprovision/reinstall); remove ONLY that one entry from the client's
     known_hosts and reconnect. Mismatch -> stop, do not connect, treat as a
     possible compromise and involve the principal before doing anything
     else.
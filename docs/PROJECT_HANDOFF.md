# PROJECT HANDOFF — Autonomous Solo Crypto Quant Desk

**Purpose:** paste this whole file into a fresh Claude session on a NEW Anthropic account to
continue this project seamlessly, with zero rebuilding. The system does NOT live in any Anthropic
account — it lives on a VPS. Switching accounts changes only *which credential authenticates
Claude*; the desk keeps running untouched. Read this, then read the live state on the VPS, and
continue exactly as the previous session did.

---

## 0. THE ONE THING TO UNDERSTAND FIRST
The entire system — code, data lake, dashboard, trading executor, risk rails, research factory,
memory, constitution — is on a **Hetzner VPS**, running 24/7 under systemd, independent of any
Claude account or laptop. Migrating to a new Anthropic account does **not** move or rebuild
anything. It only changes whose Claude Pro/Max login sits in the VPS's `~/.claude_token.env`.
So: **nothing to rebuild, no millions of tokens. Just re-authenticate and re-read the state.**

## 1. WHAT THIS IS
A fully autonomous, AI-operated systematic crypto trading desk built by one principal (Saqib, 18,
solo, budget-constrained) plus an AI CRO (you). Objective: **maximize E[log wealth] subject to
ruin ≤ 2%**. Deployed edge: delta-neutral funding carry (long spot + short perp on Binance
testnets, harvesting 8-hourly funding). Currently **testnet/paper — zero live capital, zero live
track record.** Governance, validation, and honesty discipline are institutional-grade; the edge
is thin (one near-validated family) and unproven live.

## 2. VPS ACCESS (the live system)
- **Host:** `95.216.191.70` (Hetzner, Ubuntu 26.04, 2 vCPU / 4 GB).
- **SSH:** `ssh -i <path-to-quant_vps-key> quant@95.216.191.70` (user `quant`; the ed25519 key
  was generated on the principal's laptop at `~/.ssh/quant_vps`; on a new machine, generate a new
  key and the principal adds its pubkey via the Hetzner console, or copies the existing key over).
- **Repo:** `/home/quant/quant-platform` (Python 3.12 venv at `.venv/`, editable-installed).
- **Dashboard:** https://dash.quanttt.xyz (stable Cloudflare named tunnel → localhost:8080).
- **Services (systemd):** `quant-cashcarry` (executor), `quant-deadman` (ruin rail),
  `quant-dashboard`, `quant-liquidations`, `quant-tunnel`, `quant-refresh.timer` (3-min feeds),
  `quant-cro.timer` (08:01 UTC python research cycle), `quant-cro-ai.timer` (08:45 UTC headless
  AI CRO — the brain — needs auth to run). Check health: `systemctl is-active quant-*`.

## 3. WHERE THE BRAIN'S MIND LIVES (read these on the VPS to continue)
- **Constitution:** `ops/CRO_CONSTITUTION.md` — the full CRO operating doctrine (6-point cycle
  contract, honesty mandate, sizing/validation/risk policy, multi-model panel protocol, monthly
  governance, meta-overfit + sunset discipline). This IS your operating manual. Read it first.
- **Memory:** `ops/memory/*.md` — MEMORY.md (index) + crypto-desk-state.md (the running project
  log with every incident/decision), institutional-constitution.md, user-profile.md, etc.
- **Decision ledger:** `data/decision_ledger.json` (~27 logged decisions with hypotheses +
  reversal conditions). **Knowledge base / graveyard:** `docs/institutional_knowledge.md`,
  `docs/graveyard.md`. **System review dossier:** `docs/SYSTEM_REVIEW.md`.

## 4. CURRENT STATUS (as of 2026-07-12)
- Desk migrated to VPS, hardened, running. Carry book healthy (10 carries, funding accruing,
  ≈breakeven net, ~20-40% APR run-rate on testnet).
- Dead-man rail: isolated, versioned, pid-stamped (after a false-fire incident 07-11 — see the
  knowledge base; the fix set is the reason it's now single-writer + version-guarded).
- **Multi-model advisory panel** LIVE: 11 frontier models via one OpenRouter key
  (`data/secrets/llm_panel.json`), max-reasoning, weekly mission rotation (audit/generate/data/
  premortem/synthesize) + monthly tier1. Run: `python scripts/run_external_panel.py`.
- **Research-factory pilot** RUNNING (started 07-12): the autodiscovery factory records
  `survivors-per-1,000` to `web/pilot.json` each cycle (`libs/research/information_value.py`).
  30-day measurement to decide whether scaling generation / renting hardware is EV-positive.
  Standing rule: **0 durable survivors → do not scale/rent; the constraint is data, not volume.**

## 5. THE TWO HUMAN STEPS STILL PENDING (do these on the new account)
1. **Authenticate the brain.** On a machine with a terminal, SSH to the VPS and run
   `claude setup-token` (needs the NEW account's Claude login, which you now have). It saves auth
   to `~/.claude/.credentials.json`; the `quant-cro-ai.timer` then runs the daily AI cycle.
   Alternatively put an `ANTHROPIC_API_KEY=...` (from console.anthropic.com, with a spend cap)
   into `~/.claude_token.env` — but the subscription setup-token is far cheaper for daily heavy
   autonomous use. **This single step is what "moving accounts" actually accomplishes: the new
   account's login re-activates the brain. Nothing else migrates.**
2. **Live keys (later).** Only after a 7-day VPS stability gate AND carry validation completes:
   place trade-only, withdrawal-disabled live Binance keys in `data/secrets/binance_live.json` on
   the VPS via SSH. NEVER paste exchange keys into chat.

## 6. SECURITY CONSTRAINTS (HARD STOPS — never autonomous, human-only forever)
Moving funds / deposits / withdrawals / transfers; creating financial obligations; creating or
**rotating API keys**; irreversible infra destruction; removing/disabling any kill switch or
ruin-flatten beyond 45% (Tier-3). Live keys must be trade-only + withdrawal-disabled. Never
fabricate results/Sharpe/validation. Never deploy unvalidated edge to real capital. Never relax
validation gates. The principal can ALWAYS override / pull the plug — the system is never
locked against its owner.

## 7. HOW TO CONTINUE (fresh-session bootstrap)
1. SSH into the VPS; run `systemctl is-active quant-*` and open dash.quanttt.xyz to confirm health.
2. Read `ops/CRO_CONSTITUTION.md` and `ops/memory/crypto-desk-state.md` in full.
3. Skim `data/decision_ledger.json`, `docs/graveyard.md`, `docs/institutional_knowledge.md`.
4. You are now fully caught up — operate as the CRO per the constitution. The daily cycle,
   panel, and factory pilot run on their timers; your job is the reasoning/triage/build layer.

## 8. WHAT NOT TO DO (hard-won lessons — full detail in institutional_knowledge.md)
- Don't build a brute-force "thousands-of-strategies/day" factory or rent hardware BEFORE the
  30-day pilot shows forward-validated survivors — throughput on thin data manufactures false
  positives. The pilot exists to settle this with evidence.
- Don't add anti-overfit machinery reflexively (that's itself overfitting) — restraint + the
  sunset discipline + reversibility are the primary defenses. The pre-live build phase is
  essentially complete; the binding constraint now is LIVE EVIDENCE and TIME, not features.
- Don't chase a CAGR target (targeting a return number corrupts a survival-constrained optimizer
  into over-leverage). Max safe growth; let the number fall out.
- Verify daemon WRITE-SIGNATURE (versioned state + pid heartbeat), not just heartbeat freshness.

*Handoff generated 2026-07-12. The desk is on the VPS; this file is the map. Re-auth, re-read,
continue.*

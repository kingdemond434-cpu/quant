> **DECOMMISSIONED 2026-08-23.** The Hetzner VPS this document brings up (95.216.191.70) is fully
> torn down. The desk migrated to MT5/Fusion (`CLAUDE.md` MT5 UNIVERSAL MANDATE); the live box is
> Contabo (`desks/mt5/AGENTS.md`). Kept as historical record -- do not follow it to bring anything
> back up.

# Bringing the whole desk up on the VPS

`docs/RECORDER_DEPLOY.md` covers the recorders — the data side, and still the thing that unblocks
everything downstream. This document covers **the desk**: the organs that make it run, notice, and
survive. They were the larger gap, and they were invisible for a reason worth stating plainly.

## The gap this closes

Until 2026-08-03 the repository could start recorders, a moat miner, and five credit-blocked
diggers. It could not start the desk. Nothing in it launched:

| organ | what it does | consequence of it not running |
|---|---|---|
| `run_cadence.py` | fires the panel, tier-1, the moat screen, survivor promotion, the forward-clock review — and enforces the never-sleepier floors | every duty owed forever; floors unenforced |
| `run_alerts.py` | the ntfy pager | `data/.last_alerts.json` has a **1.0h floor**, so a fresh install violated it from the first hour and stayed violated |
| `watchdog.py` | supervises the executor, dashboard and liquidation listener | its own header records that when it died on 2026-07-11 the desk ran **11.5 days** with the pager silent and the forward clocks frozen |
| `run_deadman_switch.py` | Tier-3 ruin rail: flattens the book at a 35% drawdown | no automated protection against ruin |

Every one lived exactly as long as somebody remembered to type its name. That is the same failure
that left the moat empty — and it is structural, not careless: unit files are easy to write and
easy to never install. Nothing detected it either, because every check looked at the units that
*exist* rather than at the organs that must *run*.

Closed by: five new unit files, one deploy script, `scripts/verify_deployment.py`, and four tests
that fail if a floor's producer has no launcher, if the deploy script stops installing a required
unit, if it ever arms the ruin rail, or if it stops verifying production.

---

## Install

```bash
cd /home/quant/quant-platform
git pull
bash ops/deploy_vps.sh
```

That is the whole thing. It runs the three CI gates first (a deploy that installs a broken tree is
worse than no deploy — it looks finished), installs every unit, starts them **in dependency
order**, and then verifies.

Order matters and is not cosmetic: recorders first, because everything downstream reads what they
write and a miner reporting 0% coverage against no tape is noise that hides the real signal.

### If `quant` has no sudo

The Hetzner box does not have it. `deploy_vps.sh` detects this, exits 2, and prints the
zero-privilege path — `ops/start_recorders_nosudo.sh` plus two crontab lines that reproduce the one
property of the units that actually matters, `Restart=always`. Worst-case exposure is five minutes
of tape after an unnoticed crash, versus everything after an unsupervised reboot.

---

## Verify — production, not process status

```bash
.venv/bin/python scripts/verify_deployment.py
```

**`systemctl is-active` proves a process is alive and never that it produced.** That is the failure
mode this desk keeps hitting: a panel that exited clean and appended no verdict, a timer firing for
weeks against a crashed script, a watchdog whose death nobody noticed for eleven days while
everything looked scheduled.

So the verifier asks one question of every organ — *when did it last WRITE something* — and returns:

- **RUNNING** — inside its floor
- **STALE** — exists but past its floor: scheduled and not producing, the dangerous middle case
- **MISSING** — never written, or nothing in the repository starts its producer

It exits non-zero if anything is MISSING or STALE, so it gates the deploy rather than decorating
it. `deploy_vps.sh` ends by running it and propagates the code.

---

## The one unit the deploy script will not arm

`quant-deadman.service` is installed and **not started**.

It polls combined book equity once a minute and, after five consecutive readings below 65% of the
high-water mark, writes the executor kill file, market-flattens every futures position reduce-only,
sells spot to USDT, and pages you. It **moves funds**, and its own header makes it Tier-3 —
"explicit principal sign-off only". A deploy script that quietly starts a process which can flatten
the book is exactly the autonomy that tier forbids, so the script prints the command and you type
it.

Before you do, confirm three things:

1. live API keys are present **and have trade permission**
2. the high-water mark in the rail's state reflects the real book, not a test run
3. 65% is the level you intend — a rail armed against a stale high-water mark fires on a book
   that is fine

```bash
sudo systemctl enable --now quant-deadman
```

Until then the desk has no automated protection against a 35% drawdown.

---

## What is still blocked after a clean deploy

A green `verify_deployment` does **not** mean the desk is producing research. Two things remain,
and neither is fixable from this repository:

**OpenRouter credits.** Five digger organs and the external panel are credit-gated. Their timers
fire and the runs exit having produced nothing — which the desk reports honestly rather than
marking the duty done. `scripts/check_organ_readiness.py` confirms all eleven assemble cleanly;
authentication is the only untested step, and it needs a live credential by definition.

**Time.** The moat pipeline is `mine → screen → register → promote → forward-verify`. Once tape
lands, the frontier converges on real cells within hours and the survivor registry starts
accumulating immediately. Promotion needs ≥4 screenings on ≥2 independent cells — days. A forward
clock needs tape recorded *after* a promotion — weeks. No amount of code buys that, and a pipeline
that claimed otherwise would be lying about the only out-of-sample evidence it can produce.

---

## When something is wrong

```bash
# what does the desk itself think?
.venv/bin/python scripts/verify_deployment.py
.venv/bin/python scripts/max_audit.py            # live defects, scoped REPO vs RUNTIME
.venv/bin/python scripts/enforce_constitution.py # constitutional breaches, with fix paths

# one organ
systemctl status quant-cadence.timer
journalctl -u quant-cadence -n 50 --no-pager

# is the tape actually growing? (not just present)
watch -n 30 'du -sh data/moat/*'
```

**`REFUSING TO START: N req/s over self-imposed cap`** — the recorder computes its own rate budget
at boot and refuses to exceed it. Deliberate: on 2026-07-21 an unnoticed weight overrun got this
desk's IP cut off by Binance six hours later, with no traceback. Widen intervals or cut symbols; do
not raise the cap.

**403 / connection refused from a venue** — the box cannot reach the exchange. This is why the
recorders cannot run in the Claude Code web container: `fapi.binance.com`, `api.binance.com` and
`api.bybit.com` all answer 403 to CONNECT there.

**`ProtectSystem=strict` write failures** — the units allow writes only under the repo's `data/`,
`web/` and `docs/`. If you relocate the repo, update `ReadWritePaths` and `WorkingDirectory`
together.

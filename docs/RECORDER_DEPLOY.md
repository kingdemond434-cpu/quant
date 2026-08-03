# Starting the recorders — the one action that unblocks everything downstream

> **This document covers the DATA side only.** For the whole desk — the cadence engine, the pager,
> the process supervisor and the ruin rail, none of which had a launcher until 2026-08-03 — see
> **[VPS_BRINGUP.md](VPS_BRINGUP.md)**, and prefer `bash ops/deploy_vps.sh` over the manual steps
> below. This file remains the reference for what the recorders themselves do and how to debug them.

**Why this document exists.** The desk has a moat miner, an EVIG ranking that prefers owned data
3× on replication cost, a 30% reserved slot floor for moat candidates, and a constitutional law
(P26) making under-exploration a breach. All of it is running. All of it is waiting on data that
does not exist, because **the recorders have never had a systemd unit** — they were started by
hand, and a process started by hand is a process that stops on the next reboot and never comes
back.

That is the whole gap. Not funding, not code, not a decision. Four unit files.

**Why it is urgent rather than merely pending.** Every unrecorded second is permanently unbuyable
at any price. Pre-recorder L2 does not exist free at any venue, so a day not recorded is a day
that can never be bought back with money later. This is the only cost on the desk that money
cannot fix afterwards.

---

## What you are starting

| Unit | What it records | Rate |
|---|---|---|
| `quant-recorder-fut` | Binance USD-M futures L2 depth + aggTrades, 30 symbols | depth 4s, trades 20s |
| `quant-recorder-spot` | Binance spot L2 depth + aggTrades | depth 4s, trades 20s |
| `quant-recorder-bybit` | Bybit linear L2 depth + trades + funding/OI/mark, 20 symbols | depth 1.5s, trades 10s |
| `quant-moat-miner` | *Reads* the above and extracts the seven latent series | continuous |
| `quant-moat-screen` | *Interrogates* the mine: does any of the eleven mechanisms actually predict? | continuous |

All five are **public market data only** — no API keys, no order paths, no ability to touch the
book. Recording is not trading: the *connector* is Gate-0-gated because it moves money; the
*tape* is gated by nothing.

Disk: roughly **40–70 MB/day compressed** for the futures recorder at 5 symbols, scaling with
symbol count. `run_recorder.py` pauses itself at 80% disk automatically.

---

## Install (run on the VPS, as a user with sudo)

```bash
cd /home/quant/quant-platform
git pull

# 1. Install the units
sudo cp ops/quant-recorder-fut.service \
        ops/quant-recorder-spot.service \
        ops/quant-recorder-bybit.service \
        ops/quant-moat-miner.service \
        ops/quant-moat-screen.service \
        /etc/systemd/system/
sudo systemctl daemon-reload

# 2. Start the three recorders FIRST. The miner has nothing to read until these have run.
sudo systemctl enable --now quant-recorder-fut quant-recorder-spot quant-recorder-bybit

# 3. Confirm the tape is actually landing before starting the miner (give it ~2 minutes)
ls -la data/moat/fut/*/ | head
ls -la data/moat/bybit/*/ | head

# 4. Start the dedicated continuous miner AND the continuous survivor hunt
sudo systemctl enable --now quant-moat-miner quant-moat-screen
```

The screen is a separate unit for the same reason the miner is: the miner DESCRIBES the tape and
the screen ASKS it whether anything predicts. Running the first continuously and the second on a
daily cadence meant the desk's one irreplaceable asset was measured around the clock and
interrogated once a day. Both now carry a persisted coverage frontier, so both converge on the
whole archive instead of re-grinding the newest slice.

`enable --now` is deliberate: `enable` survives reboot, `--now` starts it immediately. A recorder
that only starts on the next reboot is a recorder that loses everything until then.

---

## If `quant` has no sudo (it does not, on the Hetzner box)

`sudo: I'm sorry quant. I'm afraid I can't do that` means /etc/systemd/system is unreachable and
the unit files above cannot be installed. That is not a reason to leave the tape unrecorded, so
there is a zero-privilege path that reproduces the one property of the units that actually
matters — `Restart=always`:

```bash
cd /home/quant/quant-platform

# start everything now (idempotent -- safe to run any number of times)
bash ops/start_recorders_nosudo.sh

# keep it alive across crashes AND reboots, using nothing but the user's own crontab
( crontab -l 2>/dev/null | grep -v start_recorders_nosudo
  echo "@reboot cd /home/quant/quant-platform && bash ops/start_recorders_nosudo.sh >> data/recorder_supervisor.log 2>&1"
  echo "*/5 * * * * cd /home/quant/quant-platform && bash ops/start_recorders_nosudo.sh >> data/recorder_supervisor.log 2>&1"
) | crontab -

crontab -l | grep start_recorders    # confirm both lines landed
```

The script is BOTH the starter and the watchdog, which is why the same line serves `@reboot` and
`*/5`: it starts whatever is down and leaves alone whatever is up. That covers the failure a
supervisor loop would miss — the supervisor itself dying — and it needs no root at all.

Worst case exposure is five minutes of tape after an unnoticed crash, versus everything after a
reboot with no supervision. Tighten to `*/1` if that matters; the script costs a few `pgrep`s.

**Why not `systemctl --user`?** It also needs `loginctl enable-linger`, which is usually
root-gated, and a user service that stops when the session closes is worse than cron because it
looks like it is working.

## Verify it is working (not just running)

**An exit code proves a process ended, never that it produced.** The desk has been burned by this
exact class before — a panel exited clean, wrote nothing, and marked its duty done. So check
production, not status:

```bash
# Are files GROWING? (not just present)
watch -n 30 'du -sh data/moat/*'

# Heartbeats fresh?
date -r data/recorder_heartbeat; date -r data/recorder_bybit_heartbeat

# Is the miner converting tape into coverage?
python3 scripts/mine_moat.py && jq '.cumulative_coverage' data/moat_mine.json

# Is the hunt converting coverage into verdicts -- and is IT converging?
jq '{coverage_pct, cells_on_disk, hypotheses, tally}' data/moat_screen.json

# Anything that survived on more than one independent cell? (the only stage-A evidence there is)
jq '.persistent_candidates' data/moat_screen.json

# And did any of it beat the sweep's OWN false-positive rate -- i.e. earn a forward clock?
jq '{stats, promoted: [.promoted[].key], refused: [.refused[].refused]}' data/moat_promotion.json

# Is the constitutional breach clearing?
python3 scripts/enforce_constitution.py
```

The last command is the real acceptance test. Before you start the recorders it reports:

```
constitution: 1 breach(es) ... IN BREACH
  [BLOCKED   ] exploration-blocked-upstream: moat 0% and the blocker is UPSTREAM
```

Once tape is landing and the miner has run, that breach reclassifies from `BLOCKED` (nothing the
desk can do) to `under-exploration` (a gap that must be *closing*), and then clears as coverage
rises. **If it stays at `exploration-blocked-upstream`, the recorders are not writing** — that is
the signal to look at the logs, not at the miner.

---

## If it does not start

```bash
sudo systemctl status quant-recorder-fut
journalctl -u quant-recorder-fut -n 50 --no-pager
tail -50 data/recorder_fut.log
```

**`REFUSING TO START: N req/s over self-imposed cap`** — the recorder computes its own rate
budget at boot and refuses to exceed it. This is deliberate: on 2026-07-21 an unnoticed weight
overrun got the desk's IP cut off by Binance six hours later, with no traceback. Widen the
intervals or cut symbols; do not raise the cap.

**Venue returns 403 / connection refused** — the box cannot reach the exchange. Check egress
policy and any proxy. *This is the exact reason the recorders cannot run in the Claude Code web
container*: `fapi.binance.com`, `api.binance.com` and `api.bybit.com` all answer 403 to CONNECT
there, so this must be deployed on the VPS.

**`ProtectSystem=strict` write failures** — the units allow writes only to
`/home/quant/quant-platform/data`. If you relocate the repo, update `ReadWritePaths` and
`WorkingDirectory` together.

---

## What happens automatically once tape exists

Nothing else needs starting. Everything downstream is already wired and running:

1. **`quant-moat-miner`** mines hole-first — cells nobody has measured before it re-measures
   anything. That ordering is what converges on 100% rather than re-grinding one convenient
   symbol.
2. **`scripts/mine_moat.py`** also fires every cadence cycle as the floor, so coverage advances
   even if the continuous miner is down.
2c. **`promote_moat_survivors.py`** fires every cadence cycle and is the only thing that converts
   persistence into a **forward clock** — never capital. Its bar is *derived*: a candidate must
   beat the sweep's own measured promotion rate under a binomial tail test, on ≥2 independent
   cells, with a stable IC sign. Romano-Wolf controls error *within* a screening pass; across
   thousands of passes only this does.
2b. **`quant-moat-screen`** hunts survivors hole-first over the same grid, so a cell that is mined
   but never screened is a visible hole rather than an invisible one. Survivors persist to
   `data/moat_survivors.json` **with their misses** — Romano-Wolf controls family-wise error
   inside one pass and nothing controls it across thousands, so a one-pass survivor is expected
   noise and only the hit rate over independent cells is evidence.
3. **EVIG** ranks moat-derived candidates ~3× public ones on replication cost, and **30% of the
   ranked head is reserved** for them so public-data volume can never starve them.
4. **`enforce_constitution.py`** checks the coverage gap is *closing* every cycle, and a gap that
   stands still becomes a defect rather than a status.

---

## The next ceiling

100% coverage of the current grid is **not** completion, and P20 does not recognise one. The grid
**grows every second the recorders run**, so 100% is a moving target rather than a finish line.
After that the ceilings are: more mechanisms per cell, finer time buckets, and more venues — the
seven reconstructions in `libs/hypmax/moat_mine.py` are the first seven, not the last.

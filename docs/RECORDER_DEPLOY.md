# Starting the recorders — the one action that unblocks everything downstream

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

All four are **public market data only** — no API keys, no order paths, no ability to touch the
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
        /etc/systemd/system/
sudo systemctl daemon-reload

# 2. Start the three recorders FIRST. The miner has nothing to read until these have run.
sudo systemctl enable --now quant-recorder-fut quant-recorder-spot quant-recorder-bybit

# 3. Confirm the tape is actually landing before starting the miner (give it ~2 minutes)
ls -la data/moat/fut/*/ | head
ls -la data/moat/bybit/*/ | head

# 4. Start the dedicated continuous miner
sudo systemctl enable --now quant-moat-miner
```

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

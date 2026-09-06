> **PARTIALLY DECOMMISSIONED 2026-08-23.** The Hetzner VPS this doc's concrete commands target
> (95.216.191.70) is fully torn down; the specific `cd /home/quant/quant-platform` steps below no
> longer apply anywhere. The general data/research transport PROBLEM this file describes is still
> real for the MT5 desk (`desks/mt5/AGENTS.md`), but its current answer is
> `desks/mt5/scripts/sync_shadow_to_git.ps1` (small state, straight to git) plus box-local
> `data`/`reports` for everything else -- not this VPS-specific mechanism.

# Getting data and research into the same place

**The problem, stated exactly.** `.gitignore` carries `data/*` with the comment *"the journal is
data/, not git"*. Every analysis container is a **fresh clone**. So:

> **research runs where there is no data; data accumulates where there is no research, and nothing
> moves one to the other.**

That is a **transport gap, not a data gap**. The desk holds `moat_depth.jsonl`, `moat_trades.jsonl`
and `funding_history.jsonl`, and the moat miner has been converting tape into coverage for weeks.
It is why every study reports `BLOCKED`, and **it is not fixed by writing more analysis code.**

There are two fixes. They are not alternatives to choose between once — they answer different
questions and the desk wants both.

---

## (a) Run the study where the data is

```bash
# on the VPS
cd /home/quant/quant-platform
bash ops/run_study_on_vps.sh                  # every registered study
bash ops/run_study_on_vps.sh failed_breakout  # just one
```

**What you get.** The full archive, including the **oldest tape** — the part a competitor most
conclusively cannot obtain, because unlike a live feed it cannot be bought or backfilled at any
price. Nothing leaves the machine.

**What it costs.** The study competes for CPU with the recorders. The script therefore runs
`nice -n 15` and single-threaded (`OMP_NUM_THREADS=1`), because the recorders are the irreplaceable
process on that box: a study that starves them costs tape nobody can re-acquire.

**The refusal built into it.** A study whose pre-registration document is missing does not run. Kill
criteria chosen after seeing a result are not kill criteria, so the table maps every study to the
document that binds it and refuses when the file is absent.

**Getting a verdict off the box.** Artifacts land under `data/` and are gitignored. Either read the
verdict there, or **commit the JSON report itself** — reports are small, and a verdict is not a lake.

---

## (b) Ship a snapshot to somewhere a clone can fetch

```bash
# on the VPS
bash ops/snapshot_research_data.sh                    # last 7 days -> data/snapshots/*.tar.zst
SNAPSHOT_DAYS=30 bash ops/snapshot_research_data.sh   # a month instead
PUBLISH_TO=user@host:/srv/snap bash ops/snapshot_research_data.sh   # and scp it

# on the analysis machine
bash ops/restore_research_data.sh research-snapshot-<stamp>.tar.zst --dry-run
bash ops/restore_research_data.sh research-snapshot-<stamp>.tar.zst
python scripts/run_failed_breakout_study.py           # no longer BLOCKED
```

**What you get.** Fast iteration on real shapes, off-box, in a container that can be thrown away.

**What it costs.** A bounded window, not the archive. Any result is therefore a result *about a
window* — so do **not** use path (b) for a verdict on a hypothesis whose whole claim is the length
of the archive. Use (a) for that.

### Three properties of the snapshot worth knowing

**It is an allow-list, not a deny-list.** Files are named explicitly. An allow-list cannot leak a
file class nobody thought of; a deny-list leaks every one added after it was written.

**The secrets fence runs twice.** `data/secrets/**` is outside the allow-list, *and* the staged tree
is scanned for secret-shaped paths before the archive is built, *and* the restore side refuses an
archive containing them even though the snapshot side already excluded them — because the archive
may not have come from the snapshot side. Nothing is encrypted: **treat a snapshot as public.**

**A truncated transfer is the dangerous failure**, not a corrupt one. A short archive unpacks
cleanly and is missing half the tape, and a study run against it reports a *smaller sample* rather
than an error — a number computed on partial data entering the funnel wearing the same vocabulary
as one computed on all of it. So the restore verifies the `.sha256` and then re-hashes every file
against `MANIFEST.json`.

### Making it automatic

```bash
# on the VPS, nightly at 03:30 UTC
30 3 * * * cd /home/quant/quant-platform && SNAPSHOT_DAYS=14 \
  PUBLISH_TO=user@host:/srv/snap bash ops/snapshot_research_data.sh >> data/snapshot.log 2>&1
```

`SNAPSHOT_KEEP` (default 5) prunes old archives. That bound is load-bearing: a nightly job with no
retention fills the disk, and a full disk takes the recorders down — which costs more tape than
every snapshot ever saved.

---

## Which path for which question

| the question | path | why |
|---|---|---|
| does this mechanism exist over the whole archive? | **(a)** | the claim is about span; a window cannot answer it |
| does my harness handle real data shapes? | **(b)** | iteration speed, throwaway container |
| what is the verdict on a pre-registered study? | **(a)** | full data, then commit the JSON report |
| I need to debug why a study says NO-INPUT | **(b)** | the manifest names exactly which input is absent |

---

## Credentials

```bash
python scripts/check_credentials.py            # what is present, what is dark, how to get it
python scripts/check_credentials.py --missing  # a setup checklist
python scripts/check_credentials.py --json     # machine-readable
```

Fourteen credential files are read from fifteen different places, each with its own **silent**
graceful-degradation path — a missing key must never crash an organ. The sum of fifteen silent
degradations is a desk that appears healthy while most of it is switched off, and nothing else
states which parts are currently dark.

The inventory reports **presence and shape only**. It never prints a key and never validates one
against a venue, so its output is safe to paste.

**Present-but-broken ranks worse than absent** and is listed first: a truncated or malformed file
*looks* configured, so nobody checks it again, while every reader treats it as missing.

### The three that matter most, in order

1. **`ntfy.json`** — free, one line, and without it every alert is computed and **delivered
   nowhere**. The desk pages into the void, which is indistinguishable from having nothing to say.
2. **`llm_panel.json`** — the only credential that costs money, and the one that unblocks the most:
   the external panel, code auditor, strategic director, kimi hunter, blind rediscovery, hypothesis
   generator and breadth expander are all returning 402 right now.
3. **`heartbeat_url.json`** — free. A dead box is silent, and silence is what a healthy box also
   looks like. It is also the second pager route, on a different provider and a different network
   path, so one outage cannot take the whole pager down.

Everything else degrades an axis rather than an organ.

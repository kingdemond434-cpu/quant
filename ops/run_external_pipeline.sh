#!/bin/bash
# STAGES 2-3 OF THE SAME-DAY PIPELINE (RESEARCH §6d), chained so a discovery mined today is
# certified today: external hypotheses -> stage-A backtest -> full ten-gate gauntlet -> canon.
# Before 2026-08-26 both stages ran only when a human typed them; today's 15-pass sweep was a
# manual run, and tomorrow's discoveries would have sat unbacktested -- the exact waiting room
# the law forbids.
set -u
cd /home/quant/quant-platform
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; a commit that changes this file's LENGTH while it is running resumes execution inside
# a line. Measured on 63680c05 (ops/run_frontier_rotation.sh): comment text ran as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. Only the exit INSIDE the
# group ends the process before bash reads another byte. Do not unwrap; add nothing after `}`.
{
PY=.venv/bin/python
LOGF=data/cro_ai_logs/external_pipeline_gauntlet.log

# ---------------------------------------------------------------------------------------
# EVERY REMOTE STAGE IS TIME-BOUNDED (2026-08-26). `ssh -o ConnectTimeout=20` bounds the
# HANDSHAKE and nothing else: once connected, a remote command may run forever and this script
# blocks on it. The only backstop was the unit's TimeoutStartSec=2h, and when that fires it
# kills the WHOLE pipeline -- so a single slow remote search silently costs stage 2c (merge),
# stage 3 (the ten-gate gauntlet) and stage 4 (canon sync). That is L1.58's machinery failing
# to complete end-to-end, and it is invisible: the unit just reads `activating` for two hours.
#
# MEASURED: the 11:54 run reached stage 2b at 12:45, pulled the orthogonal artifact, and then
# sat on edge_search until the 2h unit timeout at 13:54. Zero candidates certified that run.
# The 05:36, 06:15 and 09:05 runs died the same way (3x oom-kill, 1x timeout in unit_deaths).
#
# A bound means a hung stage costs ITS OWN stage and the pipeline carries on. The default is a
# first estimate deliberately marked as one: tighten it from measured successful-run durations,
# not from another guess. `timeout` exits 124 on expiry and that is reported distinctly from a
# remote failure, because the two demand different repairs.
REMOTE_STAGE_TIMEOUT="${REMOTE_STAGE_TIMEOUT:-25m}"

# `timeout ... ssh` KILLS THE SSH CLIENT, NOT THE REMOTE PROCESS, and on this desk that is the
# difference between a bounded stage and a box that slowly stops working. MEASURED 2026-09-02:
# the 10:44 gauntlet was reported TIMED OUT at 11:09 and its python was still resident on the
# desk box at 11:41 holding 1.2 GB, beside two more orphans from the same run (570 MB, 778 MB).
# Six python processes held 3.1 GB of the box's 8.4 GB, so `edge_search` -- which needs ~2000 MB
# -- found 891 MB, stood down, and edge_search_results.json went 9.1 hours stale and was
# STALE_SKIPPED by the merge. The desk stopped producing candidates because its timeouts leaked.
#
# Every orphan is one hour's stage that reported failure and kept running. They accumulate, so
# the box degrades monotonically until something restarts it -- which is exactly what "no new
# certificates and no new clocks" looks like from the outside.
reap_remote () {    # reap_remote <pattern> -- kill desk-box pythons whose command line matches
  local pat="$1"
  timeout 90 ssh -o ConnectTimeout=20 contabo-mt5 \
    "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | Where-Object { \$_.CommandLine -like '*${pat}*' } | ForEach-Object { Write-Output ('reaped ' + \$_.ProcessId + ' ' + [math]::Round(\$_.WorkingSetSize/1MB) + 'MB'); Stop-Process -Id \$_.ProcessId -Force }\"" \
    2>>"$LOGF" | tr -d '\r'
}

remote_stage () {   # remote_stage <label> <remote command>
  local label="$1"; shift
  # These searches legitimately keep one SSH session open for 20+ minutes.  The default
  # connection was reset at 23m during a healthy orthogonal run, discarding the artifact just
  # before completion.  Keepalives distinguish a live long computation from a dead socket.
  timeout "$REMOTE_STAGE_TIMEOUT" ssh -o ConnectTimeout=20 \
    -o ServerAliveInterval=15 -o ServerAliveCountMax=20 \
    contabo-mt5 "$@" >> "$LOGF" 2>&1
  local rc=$?
  if [ "$rc" -eq 124 ]; then
    echo "$label TIMED OUT after $REMOTE_STAGE_TIMEOUT on the desk box -- later stages still run"
    # REAP WHAT THE TIMEOUT DID NOT. Matched on the script name inside the remote command so a
    # timed-out gauntlet reaps gauntlets and nothing else -- never a blanket python kill, which
    # would take the MT5 gateway and the forward engine with it.
    local script
    script=$(printf '%s\n' "$@" | grep -oE '[A-Za-z0-9_]+\.py' | head -1)
    if [ -n "$script" ]; then
      echo "$label: reaping orphaned $script on the desk box"
      reap_remote "$script" | sed "s/^/  $label /"
    else
      echo "$label: TIMED OUT and no script name could be matched -- an orphan may remain"
    fi
  elif [ "$rc" -ne 0 ]; then
    echo "$label FAILED with rc=$rc on the desk box -- later stages still run"
  fi
  return "$rc"
}
# ---------------------------------------------------------------------------------------
export QUANT_PIPELINE_STARTED_AT="$(date -u +%FT%TZ)"

# ---------------------------------------------------------------------------------------
# STAGE 0: THE CODE THIS PIPELINE EXECUTES REMOTELY MUST BE THE CODE THAT WAS COMMITTED AND
# GATED HERE. Until 2026-08-26 there was NO path -- `grep -rl contabo-mt5 ops/ scripts/
# deploy/` found four files and not one of them pushed a line of Python. Data went TO the box
# and artifacts came BACK; the modules the box actually runs arrived by some C:-side route
# nobody here controls.
#
# So a fix to the heaviest organ on the desk was INERT the moment it was committed. Measured:
# after committing the edge_search memory fix, `git hash-object` on the box still returned
# 54021b40 -- byte-for-byte the PRE-FIX file -- and that path is not even tracked on the branch
# the box has checked out (claude/llm-auto-upgrade-verify-gcjac3, which has diverged 348/233
# from this one), so no `git pull` there would ever have delivered it.
#
# The VPS repo IS the source of truth for these modules and that is measured, not assumed:
# orthogonal_sweep.py and external_gauntlet.py both hashed IDENTICAL on both boxes.
#
# VERIFIED BY HASH, NEVER BY EXIT CODE. scp exits 0 in cases that did not land, the same way
# `git push` exits 0 on a remote reject -- this desk has been burned by exactly that. The
# comparison is against `git hash-object` run on the box itself.
echo "[$(date -u +%FT%TZ)] stage 0: sync remotely-executed modules to the desk box"
# `families_orthogonal` imports the edge-queue and generic families at module import time.
# They are runtime dependencies of both the remote discovery jobs and the writer-side forward
# engine, so leaving either off this verified bundle makes the whole family registry disappear
# behind an ImportError even while the top-level module hash looks current.
# family_inputs.py is here because its ABSENCE is a measured outage, not a hypothetical:
# shadow_forward.py runs on the desk box and imports mt5desk.family_inputs, and when the
# file was not there it raised ModuleNotFoundError and parked NINE certified sleeves at
# BLOCKED_SLEEVE_ERROR with days=0 of 14 -- a fifth of the forward book accruing nothing
# while every fence read green. Someone put the file on the box by hand on 2026-08-30 and
# the sleeves recovered, but nothing in this list guaranteed it, so a rebuild would have
# silently reproduced the outage.
REMOTE_MODULES="desks/mt5/mt5desk/family_inputs.py desks/mt5/mt5desk/families.py desks/mt5/mt5desk/families_orthogonal.py desks/mt5/mt5desk/families_edge_queue.py desks/mt5/mt5desk/family_generic.py libs/research/bar_span.py desks/mt5/research/job_lock.py desks/mt5/research/orthogonal_sweep.py desks/mt5/research/edge_search.py desks/mt5/scripts/external_gauntlet.py"
# NEVER SHIP A TRAMPLED MODULE (2026-08-27): a replayer reverts working-tree code to ancient
# copies roughly hourly, the moneypath fence heals within 10 minutes -- but this sync fires at
# :05, INSIDE the trample window, and shipped ancient engines to the desk twice tonight. The
# fence call below heals any active trample first (it restores from canon and commits); only a
# tree that passes the marker check is allowed to reach the box that trades.
$PY scripts/check_moneypath_fence.py >/dev/null 2>&1 || $PY scripts/check_moneypath_fence.py >/dev/null 2>&1
if ! $PY scripts/check_moneypath_fence.py >/dev/null 2>&1; then
  echo "code sync SKIPPED: moneypath fence cannot heal the tree; refusing to ship unknown code"
  REMOTE_MODULES=""
fi
for m in $REMOTE_MODULES; do
  scp -q "$m" "contabo-mt5:C:/opt/quant/$m" 2>>"$LOGF" || echo "code sync scp FAILED: $m"
done
# DATA THE REMOTE FAMILIES READ, not just the code that reads it. `orthogonal_sweep` runs HERE on
# the desk box, but `_macro_series` reads `data/fred_macro.json`, which the FRED collector writes on
# the VPS -- so the file existed, was current, and never travelled. Measured 2026-09-04: `macro`
# loaded as None on the box and `macro_conditional` produced zero signals across the whole
# universe, filed as `no-signals (a macro state series)` -- which reads as "the desk has no macro
# data" while 6 series and 848 observations sat on the other machine. Same class as the bars: the
# consumer and the producer were on different boxes and nothing carried the file between them.
#
# Small, dated, read-only inputs only. Bars go the other way (ops/pull_bars.sh) because the
# terminal that makes them lives on the box.
for _d in data/fred_macro.json; do
  [ -f "$_d" ] || continue
  scp -q "$_d" "contabo-mt5:C:/opt/quant/$_d" 2>>"$LOGF" \
    && echo "data sync: $_d -> desk box" \
    || echo "data sync FAILED: $_d"
done

_want=$(git hash-object $REMOTE_MODULES | tr -d '\r')
_have=$(timeout 120 ssh -o ConnectTimeout=20 contabo-mt5 \
          "cd C:\opt\quant && git hash-object $REMOTE_MODULES" 2>/dev/null \
        | grep -E '^[0-9a-f]{40}$' | tr -d '\r')
if [ "$_want" = "$_have" ]; then
  echo "code sync verified: $(echo "$_want" | wc -l) module(s) byte-identical on the desk box"
else
  # LOUD, and the pipeline continues: the box still holds runnable (older) code, so stopping
  # here would trade a stale search for no search at all. But the verdicts of this run were
  # produced by code that is NOT what was gated, and that must never be silent.
  echo "CODE SYNC UNVERIFIED -- the desk box is running code that is NOT this repo's."
  echo "  wanted: $(echo "$_want" | tr '\n' ' ')"
  echo "  found : $(echo "$_have" | tr '\n' ' ')"
fi
# ---------------------------------------------------------------------------------------

echo "[$(date -u +%FT%TZ)] stage 2: external backtest"
$PY desks/mt5/side_channels/run_external_backtest.py || echo "stage 2 FAILED (rc=$?)"

# STAGE 2b: the zero-hardcode search. It runs BEFORE the gauntlet so its diverse candidates are
# judged by the same ten gates as everything else -- and it carries its own trial count so the
# deflation is honest about how wide the search was.
# STAGE 2a: what did the miners and the MOAT point at this week? Mining supplies ATTENTION,
# not hypotheses -- 740 discovery files existed and none had ever reached the ten gates because a
# web artefact is not a (symbol, family, params). This turns them into a ranked search target
# list, hourly, and the moat's own tick tape weighs heaviest because nobody else has it.
# STAGE 1: precompute every number an LLM organ would otherwise count for itself. Python
# counts; the model judges. This runs first so anything downstream -- including the LLM organs on
# their own cadences -- reads current facts rather than deriving them.
echo "[$(date -u +%FT%TZ)] stage 1: research facts pack"
$PY scripts/build_research_facts.py || echo "facts pack FAILED (rc=$?) -- continuing"

echo "[$(date -u +%FT%TZ)] stage 2a: mined ground (miners + moat -> search targets)"
$PY desks/mt5/research/mined_ground.py || echo "mined ground FAILED (rc=$?) -- continuing"
echo "[$(date -u +%FT%TZ)] stage 2a.1: miner evidence -> executable candidates / deepening queue"
$PY desks/mt5/research/miner_candidate_compiler.py \
  || echo "miner candidate compiler FAILED (rc=$?) -- continuing"

# Heavy discovery belongs on the MT5 desk box. Measured 2026-08-26: running edge_search here
# OOM-killed this service after the 28-minute external screen, so neither search output reached
# merge or the gauntlet. The desk box has the same Fusion universe and ~8GB RAM; execute BOTH the
# family-free search and the named orthogonal falsification sweep there, then pull their artifacts
# into the one merge below. Discovery remains hourly; only the compute location changes.
# ORDER IS THE FIX (2026-09-01). This block used to sit AFTER stage 2b, and that is why the
# gauntlet almost never ran. Stage 2b launches TWO heavy remote searches on the desk box --
# orthogonal frontier (~1250MB) and family-free/edge_search (~2000MB) -- and stage 3 then asked
# the SAME 8GB box, which also runs the live terminal, for another ~1200MB. It was last in the
# queue for memory it could never get: measured 2026-08-31, 62 external_gauntlet stand-downs in
# one day, and on 2026-09-01 02:06 the merge announced 22 families and 20,341 discovered
# candidates going to the gauntlet, which then exited rc=75 one second later.
#
# THE ASYMMETRY DECIDES THE ORDER. A gauntlet that stands down means candidates are never
# judged: zero certificates, and the entire hour of mining upstream is wasted. A SEARCH that
# stands down means fewer NEW candidates against a docket already 20,341 deep, and it resumes
# from its per-cell cache on the next trigger by design. One loss is total, the other marginal,
# so the terminal stage goes first and runs while the box is at its quietest.
#
# The docket it judges is `external_survivors.json`, which PERSISTS on disk between runs, so
# running before this cycle's merge costs at most one hour of freshness on the newest rows --
# paid out of a backlog that has not been judged at all for days.
# STAGE 3 RUNS ON THE DESK BOX, NOT HERE. Measured 2026-08-26: a 208-cell gauntlet (100 of them
# discovered edges with ~5,000 signals each) was OOM-killed on this 4GB box -- 25 OOM events in 90
# minutes -- while the desk box sat with 4.1GB free of 8GB and already holds the universe. Heavy
# compute follows the memory and the data; this box coordinates and keeps the canon. Running it
# here would silently truncate the gauntlet to whatever fits, which is worse than not running it:
# a partial gauntlet still writes verdicts.
echo "[$(date -u +%FT%TZ)] stage 3: ten-gate gauntlet (on the desk box)"
# Ship the docket ONLY when it holds candidates -- an empty file here becomes an empty sweep
# there, and an empty sweep once wiped the authority file. Belt to the two braces above.
ROWS=$($PY -c "import json;print(len(json.load(open('desks/mt5/data/hypotheses/external_survivors.json'))))" 2>/dev/null || echo 0)
if [ "$ROWS" -gt 0 ]; then
  scp -q desks/mt5/data/hypotheses/external_survivors.json \
      contabo-mt5:'C:/opt/quant/desks/mt5/data/hypotheses/external_survivors.json' 2>/dev/null
else
  echo "NOT shipping an empty docket ($ROWS rows) to the desk box"
fi
if remote_stage "ten-gate gauntlet" \
     "cd C:\opt\quant\desks\mt5 && py -3 -W ignore scripts\external_gauntlet.py"; then
  scp -q contabo-mt5:'C:/opt/quant/desks/mt5/reports/UNIVERSAL_SURVIVORS.json' \
      desks/mt5/reports/UNIVERSAL_SURVIVORS.json 2>/dev/null
  scp -q contabo-mt5:'C:/opt/quant/desks/mt5/reports/universal_gates_external.json' \
      desks/mt5/reports/universal_gates_external.json 2>/dev/null
  $PY scripts/reconcile_external_queue.py || echo "external queue reconciliation FAILED (rc=$?)"
  echo "gauntlet done on the desk box; certificates pulled back"
else
  echo "stage 3 FAILED on the desk box -- see $LOGF"
fi


echo "[$(date -u +%FT%TZ)] stage 2b: desk-box frontier search (family-free + orthogonal)"
scp -q desks/mt5/data/hypotheses/mined_targets.json \
    contabo-mt5:'C:/opt/quant/desks/mt5/data/hypotheses/mined_targets.json' 2>/dev/null || true
# Small, durable point-in-time axes used by structured miner candidates travel with the run.
scp -q data/cot_zcache.parquet \
    contabo-mt5:'C:/opt/quant/data/cot_zcache.parquet' 2>/dev/null || true

# These are independent discovery methods. Running them behind `A && B` made an OOM in the
# family-free search suppress the much cheaper orthogonal sweep. THE ARTIFACT IS ALWAYS PULLED,
# whatever this cycle's remote invocation did: measured 2026-08-27, the desk finished a 3.9MB
# search at 03:29 AFTER the ssh leg had timed out, and the success-gated pull then left the VPS
# merging a copy 25 hours old for the rest of the day. `scp -p` preserves the artifact's TRUE
# mtime, so merge_hypotheses' freshness contract -- not this script's guess about the run --
# decides whether the content is this cycle's discovery or yesterday's.
# ONE SEARCH PER CYCLE, ALTERNATING -- because the unit is `Type=oneshot` on an hourly timer,
# and systemd SKIPS a trigger whose previous run has not finished. It does not queue it and it
# does not overlap it: the hour is simply dropped. Measured 2026-09-01, the 02:20 cycle was still
# in stage 2b at 03:15, so the 03:05 trigger never fired at all.
#
# Stage 2b was the whole overrun: two remote searches at a 25m timeout each, run back to back,
# is 50 minutes before the merge has started. Running them in parallel is not the fix -- they
# are the two heaviest jobs on an 8GB box that also holds the live terminal, and colliding is
# what produced 162 stand-downs in a day.
#
# So each cycle runs ONE of them, alternating on the hour. Both keep per-cell caches that resume
# rather than restart (see job_lock's refusal text and the gauntlet's FRESH_BUILD_BUDGET), so
# alternating halves the wall clock without losing any work -- a search simply advances every
# other hour instead of every hour, against a docket already 20,000 deep. The gauntlet, which is
# terminal and whose stand-down costs everything, keeps its slot every single cycle.
# RE-VERIFY CODE IDENTITY IMMEDIATELY BEFORE LAUNCHING, NOT ONLY AT STAGE 0. Stage 0 ships and
# hash-verifies the modules, but stages 1, 2, 2a and 2a.1 run between there and here -- fifteen
# minutes and more -- and the box's copy drifts inside that window. MEASURED 2026-09-03: the box
# ran edge_search at 05:20 against a `job_lock.py` of 4,644 bytes while this repo's was 13,703
# (and `orthogonal_sweep.py` at 15,905 against 32,015), so the search executed WITHOUT the
# commit-aware memory guard and the dead-owner lock recovery that were written precisely to keep
# it alive. edge_search_results.json was 27.8 hours stale and orthogonal_candidates.json 15.5,
# with both jobs "running" the whole time -- a producer that runs, is fenced by rules it no
# longer contains, and emits nothing. The drift healer already existed and runs every 13 minutes;
# nothing ordered it against the launch, so it healed the box reliably at every moment except the
# one that mattered. Healing HERE makes the window zero: the code that runs is the code that was
# gated, or this cycle says so out loud.
$PY scripts/check_desk_module_drift.py || echo "module drift heal reported drift (healed above; see data/desk_module_drift.json)"

_HOUR=$(date -u +%H)
if [ $(( 10#$_HOUR % 2 )) -eq 0 ]; then _SEARCH=orthogonal; else _SEARCH=familyfree; fi
echo "stage 2b: running the $_SEARCH frontier this cycle (they alternate hourly; both resume from cache)"

# A search may take the whole slot and still make progress; the gauntlet already had its own.
_SEARCH_TIMEOUT_SAVE="$REMOTE_STAGE_TIMEOUT"
REMOTE_STAGE_TIMEOUT="${SEARCH_STAGE_TIMEOUT:-20m}"

if [ "$_SEARCH" = "orthogonal" ]; then
remote_stage "orthogonal frontier" \
     "cd C:\opt\quant\desks\mt5 && py -3 -W ignore research\orthogonal_sweep.py" \
  || echo "orthogonal frontier run FAILED/timed out on the desk box -- see $LOGF"
fi
scp -p -q contabo-mt5:'C:/opt/quant/desks/mt5/data/hypotheses/orthogonal_candidates.json' \
    desks/mt5/data/hypotheses/orthogonal_candidates.json 2>/dev/null \
  && echo "orthogonal frontier artifact pulled (true mtime preserved)" \
  || echo "orthogonal frontier pull FAILED"

if [ "$_SEARCH" = "familyfree" ]; then
remote_stage "family-free frontier" \
     "cd C:\opt\quant\desks\mt5 && py -3 -W ignore research\edge_search.py" \
  || echo "family-free frontier run FAILED/timed out on the desk box -- see $LOGF"
fi
REMOTE_STAGE_TIMEOUT="$_SEARCH_TIMEOUT_SAVE"
scp -p -q contabo-mt5:'C:/opt/quant/desks/mt5/data/hypotheses/edge_search_results.json' \
    desks/mt5/data/hypotheses/edge_search_results.json 2>/dev/null \
  && echo "family-free frontier artifact pulled (true mtime preserved)" \
  || echo "family-free frontier pull FAILED"

# STAGE 2c: merge every producer into the ONE file the gauntlet reads. Without this the search
# and the sweep write files nothing consumes -- producers with no consumer, which is how the book
# stayed 95% one family while the searcher "ran nightly".
echo "[$(date -u +%FT%TZ)] stage 2c: merge hypothesis sources"
$PY desks/mt5/research/merge_hypotheses.py || echo "merge FAILED (rc=$?)"

# Stage 4: certificates -> canon copy -> desk box. The canon file is what the authority
# ratchet floors and what restores the authority file after a bad writer.
$PY scripts/check_authority_ratchet.py || true
$PY - <<'PYEOF'
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, ".")
from libs.ops.canon_lease import hold
auth = Path("desks/mt5/reports/UNIVERSAL_SURVIVORS.json")
canon = Path("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json")
a = json.loads(auth.read_text("utf-8"))
c = json.loads(canon.read_text("utf-8")) if canon.exists() else {"survivors": {}}
if len(a.get("survivors", {})) >= len(c.get("survivors", {})):
    # UNDER LEASE. Two certifiers wrote this file tonight and the loser was whichever ran first;
    # the lease serialises them and fences a stalled writer out entirely.
    with hold("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json", "external-pipeline") as tok:
        shutil.copyfile(auth, canon)
        print(f"canon updated under lease {str(tok)[:12]}: n={len(a['survivors'])}")
else:
    print(f"canon NOT updated: authority {len(a.get('survivors', {}))} < canon "
          f"{len(c['survivors'])} -- ratchet holds")
PYEOF

scp -q desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json \
    contabo-mt5:'C:/opt/quant/desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json' \
  && echo "canon synced to desk box" || echo "desk-box sync FAILED (will retry next run)"
scp -q desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json \
    contabo-mt5:'C:/opt/quant/desks/mt5/reports/UNIVERSAL_SURVIVORS.json' \
  && echo "canonical authority synced to desk box" \
  || echo "desk-box authority sync FAILED (will retry next run)"

# The hypothesis corpus lives on THIS box (stage 2 writes it here) but the dashboard state is
# built on the desk box, which is the only machine that can read the live account. Without this
# the funnel's first stage reads null -- "discovered" unmeasured -- while every later stage has
# a number, which reads as a broken pipeline rather than a missing file.
scp -q desks/mt5/data/hypotheses/external_backtest_results.json \
    contabo-mt5:'C:/opt/quant/desks/mt5/data/hypotheses/external_backtest_results.json' \
  2>/dev/null && echo "hypothesis corpus synced" || echo "hypothesis sync skipped"
echo "[$(date -u +%FT%TZ)] external pipeline done"

exit $?
}

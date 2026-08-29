#!/bin/bash
# AUTO-PUSH GUARD (principal 2026-08-27: "make sure I don't have to do commands -- all things
# are automatically pushed"). Fences and sync organs COMMIT locally; nothing pushed them, so
# healed canon sat local-only until a session happened to push. Push is safe to attempt any
# time: a reject leaves everything as it was and the next tick retries.
cd /home/quant/quant-platform || exit 0
LOG_TS() { date -u +%FT%TZ; }

# CONCURRENCY LOCK (gap-fixer 2026-08-29). The timer fires every 10 minutes and the gated push
# it starts can take longer than that, so ticks STACKED: measured 2026-08-29, three auto_push
# runs were live at once holding two `pytest --co` collections of 287 MB each. The memory guard
# below cannot see them -- each run checked MemAvailable at its OWN start, before the others had
# allocated. A guard that samples a shared resource without excluding its own siblings measures
# a number that is already stale. `flock -n` makes overlap impossible: a tick that finds a run
# in progress exits 0 immediately and the next tick retries, which is exactly the deferral this
# script already implements for the memory case. In the script, not the unit, so it protects
# EVERY caller (the systemd unit, the crontab row, a human) rather than one of them.
# `-E 99` because plain `flock -n` exits 1 BOTH when the lock is held and when the child exits 1,
# and this script's child legitimately exits non-zero on a failed push. Collapsing those two into
# one code is how a lock starts reporting real failures as contention. NOT `exec`: exec replaces
# the shell, so the `||` branch after it is unreachable and the deferral would never be logged.
LOCK=data/.auto_push.lock
if [ -z "${AUTO_PUSH_LOCKED:-}" ]; then
  export AUTO_PUSH_LOCKED=1
  flock -n -E 99 "$LOCK" "$0" "$@"
  rc=$?
  if [ "$rc" -eq 99 ]; then
    echo "$(LOG_TS) SKIPPED: another auto_push run holds $LOCK; next tick retries."
    exit 0
  fi
  exit "$rc"
fi
ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo 0)
if [ "${ahead:-0}" -gt 0 ]; then
  # MEMORY GUARD (gap-fixer 2026-08-28; THRESHOLD RE-MEASURED 2026-08-29). `git push` fires the
  # pre-push hook, which runs ops/gates.sh -- ruff + compileall + pytest --co + mypy.
  #
  # The 2026-08-28 figure was an AVAILABLE-DELTA (1038MB -> 796MB, so "~242MB"), and that method
  # systematically UNDER-reads a working set: the page cache absorbs part of it, so the delta is
  # smaller than the memory the job actually needs to hold. Re-measured 2026-08-29 the direct
  # way, `/usr/bin/time -v ./ops/gates.sh` -> `Maximum resident set size (kbytes): 428608` =
  # **419 MiB** (pytest --co alone peaks at 415 MiB). The old 400MB floor was BELOW the gate's
  # own requirement, so the guard was clearing pushes it could not fund. 550 is 419 measured
  # plus room for git, bash and the transient.
  #
  # The box is 4GB with ZERO swap, so when another ~290MB organ (the mt5 suite ratchet, a seat,
  # a dig) is resident at the same time, the gate does not fit and the KERNEL picks the victim.
  #
  # WHAT THAT LOOKED LIKE, AND WHY IT WAS INVISIBLE: 15 oom-kills of this unit in 24h. The
  # kill lands mid-gate, so the script dies BEFORE reaching either of its echo lines --
  # data/cro_ai_logs/auto_push.log sat at 0 bytes for 12 hours while a commit stayed local and
  # `systemctl` reported "Finished" for the ticks where `ahead` happened to be 0. A guard whose
  # whole job is proving work left the box was failing in the one way that leaves no evidence.
  #
  # So: refuse to START a gate that cannot fit, and SAY SO. A logged deferral retries in ten
  # minutes and costs nothing; an oom-kill costs the log line that would have explained it.
  # This weakens no gate -- --no-verify is never used here, the hook still runs in full.
  avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 99999)
  if [ "${avail:-99999}" -lt 550 ]; then
    echo "$(LOG_TS) DEFERRED: ${ahead} commit(s) unpushed; ${avail}MB available < 550MB needed for the pre-push gate (419MiB measured peak RSS, 4GB box, no swap). Retrying next tick."
    exit 0
  fi
  # Log the ATTEMPT before the gate runs: a heartbeat proves the loop is alive, never that the
  # pipe is (desk lesson). If the next line in this log is another ATTEMPT rather than a
  # verdict, this unit was killed mid-gate and that is now readable instead of silent.
  echo "$(LOG_TS) ATTEMPT: pushing ${ahead} commit(s) with ${avail}MB available"
  # `git push` EXITS 0 ON A REMOTE REJECT (desk lesson, 3+ instances): the pre-receive hook
  # declines, the transport succeeded, and the exit code reports the transport. Trusting `&&`
  # here made this guard log "pushed N commit(s)" for a push that landed nothing -- a false
  # green on the one organ whose whole job is proving that work left the box. Grep the OUTPUT,
  # which is why 2>&1 replaces the discarded stderr, and confirm from the REMOTE ref afterwards
  # rather than from anything git said.
  out=$(git push 2>&1); rc=$?
  after=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "?")
  # THE VERDICT IS THE REF, NOT THE EXIT CODE (gap-fixer 2026-08-29). This organ already knew
  # `git push` EXITS 0 ON A REMOTE REJECT and its own comment above says to "confirm from the
  # REMOTE ref afterwards rather than from anything git said" -- then ANDed `rc -eq 0` into the
  # verdict anyway, so it still believed the exit code in the other direction.
  #
  # MEASURED 2026-08-29 00:43: rc=1 while `git reflog show origin/desk-sync-clean` recorded
  # `0ea5e033 @{2026-08-29 00:43:49}: update by push`. The commit LANDED and this guard logged
  # "push did NOT land". Both directions of the same mistake now have evidence on this box, and
  # a false negative is not harmless: it tells the desk work is stuck when it is not, which is
  # how a real stuck push gets read as the usual noise.
  #
  # `after` is the honest test and it catches BOTH: git updates the remote-tracking ref only
  # when the ref actually moves, so a reject (exit 0 or not) leaves `after` > 0 and reads as NOT
  # LANDED, while a landed push reads as landed however git chose to exit. rc and any reject
  # text stay in the log as DIAGNOSTICS -- reported, never the verdict.
  if [ "$after" = "0" ]; then
    if [ "$rc" -ne 0 ] || printf '%s' "$out" | grep -qiE 'rejected|denied|error:'; then
      echo "$(date -u +%FT%TZ) pushed ${ahead} commit(s) -- but the remote complained (rc=$rc): $(printf '%s' "$out" | grep -iE 'rejected|denied|error:|remote:' | tr '\n' ' ' | cut -c1-300)"
    else
      echo "$(date -u +%FT%TZ) pushed ${ahead} commit(s)"
    fi
  else
    echo "$(date -u +%FT%TZ) push did NOT land (rc=$rc, still ${after} ahead); leaving for the sync organ: $(printf '%s' "$out" | tr '\n' ' ' | cut -c1-300)"
  fi
fi

#!/bin/bash
# AUTO-PUSH GUARD (principal 2026-08-27: "make sure I don't have to do commands -- all things
# are automatically pushed"). Fences and sync organs COMMIT locally; nothing pushed them, so
# healed canon sat local-only until a session happened to push. Push is safe to attempt any
# time: a reject leaves everything as it was and the next tick retries.
cd /home/quant/quant-platform || exit 0
LOG_TS() { date -u +%FT%TZ; }
ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo 0)
if [ "${ahead:-0}" -gt 0 ]; then
  # MEMORY GUARD (gap-fixer 2026-08-28). `git push` fires the pre-push hook, which runs
  # ops/gates.sh -- ruff + compileall + pytest --co + mypy. MEASURED on this box: that costs
  # ~242MB of headroom (available 1038MB -> 796MB during a real gated push). The box is 4GB
  # with ZERO swap, so when another ~290MB organ (the mt5 suite ratchet, a seat, a dig) is
  # resident at the same time, the gate does not fit and the KERNEL picks the victim.
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
  if [ "${avail:-99999}" -lt 400 ]; then
    echo "$(LOG_TS) DEFERRED: ${ahead} commit(s) unpushed; ${avail}MB available < 400MB needed for the pre-push gate (~242MB measured, 4GB box, no swap). Retrying next tick."
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
  if [ "$rc" -eq 0 ] && [ "$after" = "0" ] && ! printf '%s' "$out" | grep -qiE 'rejected|denied|error:'; then
    echo "$(date -u +%FT%TZ) pushed ${ahead} commit(s)"
  else
    echo "$(date -u +%FT%TZ) push did NOT land (rc=$rc, still ${after} ahead); leaving for the sync organ: $(printf '%s' "$out" | tr '\n' ' ' | cut -c1-300)"
  fi
fi

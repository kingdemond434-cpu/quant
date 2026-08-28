#!/bin/bash
# AUTO-PUSH GUARD (principal 2026-08-27: "make sure I don't have to do commands -- all things
# are automatically pushed"). Fences and sync organs COMMIT locally; nothing pushed them, so
# healed canon sat local-only until a session happened to push. Push is safe to attempt any
# time: a reject leaves everything as it was and the next tick retries.
cd /home/quant/quant-platform || exit 0
ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo 0)
if [ "${ahead:-0}" -gt 0 ]; then
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

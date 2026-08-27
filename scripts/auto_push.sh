#!/bin/bash
# AUTO-PUSH GUARD (principal 2026-08-27: "make sure I don't have to do commands -- all things
# are automatically pushed"). Fences and sync organs COMMIT locally; nothing pushed them, so
# healed canon sat local-only until a session happened to push. Push is safe to attempt any
# time: a reject leaves everything as it was and the next tick retries.
cd /home/quant/quant-platform || exit 0
ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo 0)
if [ "${ahead:-0}" -gt 0 ]; then
  git push --quiet 2>/dev/null && echo "$(date -u +%FT%TZ) pushed ${ahead} commit(s)" \
    || echo "$(date -u +%FT%TZ) push rejected (non-ff); leaving for the sync organ"
fi

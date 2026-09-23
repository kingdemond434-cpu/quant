#!/bin/bash
# A SECOND public URL on a brand-new hostname, alongside the permanent named tunnel.
#
# WHY BOTH. dash.quanttt.xyz serves 200 with real HTML to a browser User-Agent from off-box, and
# still would not open on the principal's laptop or phone. When a hostname answers everywhere you
# can test and nowhere the user is, the hostname itself is the variable: a cached 404 from before
# the tunnel was fixed, a resolver that has the old answer, or a network that filters it. None of
# those are fixable from this side, and all of them are bypassed by a name the client has never
# seen before.
#
# The named tunnel stays primary -- it is permanent and belongs in a bookmark. This is the escape
# hatch for exactly the situation the principal is in, and it prints its URL to a file the
# dashboard link-checker can read.
# SEALED against mid-run rewrite (max_audit launcher-unsealed, 2026-09-03). bash reads this
# file by BYTE OFFSET, and this tree takes ~200 commits/day, so a length change while the
# tunnel is up resumes execution inside a line -- measured on 63680c05, which killed a
# frontier dig. The `exit` must be INSIDE the group: a bare `{ ... }` still lets bash read
# past the closing brace and re-run the whole script.
{
set -uo pipefail
cd /home/quant/quant-platform
URL_FILE=data/desk_quick_url.txt
LOG=data/desk_quick_tunnel.log
: > "$LOG"

/usr/local/bin/cloudflared --no-autoupdate --config /home/quant/.cloudflared/quick.yml \
    --protocol http2 --logfile "$LOG" --loglevel info \
    tunnel --url http://localhost:8788 &
CF_PID=$!

for _ in $(seq 1 45); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | head -1)
  if [ -n "${URL:-}" ]; then
    printf '%s\n' "$URL" > "$URL_FILE"
    echo "quick tunnel up: $URL/desk.html"
    break
  fi
  sleep 2
done
[ -s "$URL_FILE" ] || echo "WARNING: no quick URL captured; see $LOG"
wait $CF_PID

exit $?
}

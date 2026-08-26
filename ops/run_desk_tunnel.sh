#!/bin/bash
# QUICK TUNNEL for the desk dashboard -- a public HTTPS URL with no root, no zone, no DNS.
#
# WHY NOT THE NAMED TUNNEL. `desk.quanttt.xyz` was CNAMEd to this box's own tunnel, but requests
# never reached the connector (its log stayed empty while the edge returned 404): the hostname is
# still bound to the pre-existing `quant-dash` tunnel at Cloudflare's routing layer, and that
# tunnel is driven by a ROOT unit this box's user cannot reload -- `sudo` is refused here by
# design. Rather than leave the dashboard blocked on a restart nobody can perform, this uses a
# quick tunnel: Cloudflare mints its own trycloudflare.com hostname, so there is no hostname to
# contend over and no privilege to acquire.
#
# The URL changes whenever the tunnel reconnects from scratch, so it is written to
# data/desk_url.txt on every start -- read that file, never guess. Access is still gated by the
# dashboard's token (--require-token), which is what actually protects the equity data; the
# tunnel only provides transport and TLS.
set -u
cd /home/quant/quant-platform
URL_FILE=data/desk_url.txt
LOG=data/desk_tunnel.log
: > "$LOG"

# --config IS MANDATORY HERE. cloudflared silently reads ~/.cloudflared/config.yml when no
# config is given, and that file names the PRE-EXISTING tunnel whose ingress serves a different
# hostname. So `--url` was being overridden: the connector registered happily, logged zero
# incoming requests, and every request 404'd at the edge because the hostname belonged to the
# other tunnel. Pointing at an isolated config is what makes --url actually take effect.
/usr/local/bin/cloudflared --no-autoupdate --config /home/quant/.cloudflared/quick.yml \
    tunnel --url http://localhost:8788 --logfile "$LOG" --loglevel info &
CF_PID=$!

for _ in $(seq 1 40); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | head -1)
  if [ -n "${URL:-}" ]; then
    printf '%s\n' "$URL" > "$URL_FILE"
    echo "desk dashboard public at: $URL/desk.html?k=<key from data/secrets/dashboard_token.txt>"
    break
  fi
  sleep 2
done
[ -s "$URL_FILE" ] || echo "WARNING: no URL captured; see $LOG"
wait $CF_PID

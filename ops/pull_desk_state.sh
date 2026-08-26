#!/bin/bash
# PULL LIVE DESK STATE from the trading box to this public box (principal 2026-08-26: dashboard
# on Dell and phone with fresh data; the Contabo dashboard is abandoned).
#
# WHY A PULL AND NOT A PUSH. This box already holds the SSH identity for the desk box (every
# deploy tonight went that way), so a pull needs no new credential, no inbound port on the
# trading box, and no service running there beyond the state builder it already runs. The desk
# box serves nothing to anyone.
#
# WHAT TRAVELS: the built dashboard state and the shadow ledgers it summarises -- read-only
# artifacts. No secrets, no credentials, no order path. If the desk box is unreachable the last
# good copy stays in place and `age_seconds` on the page tells the truth about how old it is.
set -u
cd /home/quant/quant-platform
REMOTE=contabo-mt5
ok=0

scp -q "$REMOTE:C:/opt/quant/web/desk_state.json" web/desk_state.json.tmp 2>/dev/null \
  && mv web/desk_state.json.tmp web/desk_state.json && ok=1

for f in shadow_state.json qquant_shadow_state.json scalp_shadow_state.json; do
  scp -q "$REMOTE:C:/opt/quant/desks/mt5/reports/shadow/$f" \
      "desks/mt5/reports/shadow/$f.tmp" 2>/dev/null \
    && mv "desks/mt5/reports/shadow/$f.tmp" "desks/mt5/reports/shadow/$f"
done
scp -q "$REMOTE:C:/opt/quant/desks/mt5/reports/UNIVERSAL_SURVIVORS.json" \
    desks/mt5/reports/UNIVERSAL_SURVIVORS.json.tmp 2>/dev/null \
  && mv desks/mt5/reports/UNIVERSAL_SURVIVORS.json.tmp desks/mt5/reports/UNIVERSAL_SURVIVORS.json

# The job manifest judges FRESHNESS, so it has to see the trading box's own artifacts rather than
# this box's stale copies -- otherwise it would report a dead organ as healthy, which is the exact
# failure mode it exists to catch.
scp -q "$REMOTE:C:/opt/quant/desks/mt5/reports/execution_quality.json" \
    desks/mt5/reports/execution_quality.json 2>/dev/null || true
for f in sleeve_registry.json decay_live.json forward_reconcile.json daily_cycle_state.json; do
  scp -q "$REMOTE:C:/opt/quant/desks/mt5/data/$f" "desks/mt5/data/$f" 2>/dev/null || true
done

rm -f web/desk_state.json.tmp desks/mt5/reports/shadow/*.tmp desks/mt5/reports/*.tmp 2>/dev/null
if [ "$ok" = "1" ]; then
  echo "$(date -u +%FT%TZ) desk state pulled"
else
  echo "$(date -u +%FT%TZ) PULL FAILED -- serving last good copy; the page's age field shows it"
  exit 1
fi

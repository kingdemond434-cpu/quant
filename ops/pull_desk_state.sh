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
# FRESHNESS MUST BE THE BOX'S, NOT THE PULLER'S (-p, measured 2026-08-27). Without `-p` every
# scp stamps the local copy with NOW, so this script rewrote ~10 artifacts every two minutes and
# each one read FRESH forever -- including `shadow_state.json` (3h limit), `decay_live.json` and
# `forward_reconcile.json` (26h). The desk box had not written `sleeve_registry.json` since
# 03:34 (4.6h, past its own 3h window) and the local copy still showed an age of one minute; only
# the job manifest's separate byte-identical heuristic caught it, and nothing at all would have
# caught a box that simply stopped. That is this desk's oldest lesson wearing new clothes: an
# artifact's mtime proves the COPY happened, never that the producer ran. `-p` carries the
# remote's modification time across, so every staleness gauge downstream measures the box.
set -u
cd /home/quant/quant-platform
REMOTE=contabo-mt5
ok=0

scp -pq "$REMOTE:C:/opt/quant/web/desk_state.json" web/desk_state.json.tmp 2>/dev/null \
  && mv web/desk_state.json.tmp web/desk_state.json && ok=1

# Pull every state producer consumed by the read-only watchdog. Omitting shadow_health meant the
# VPS could have current sleeve ledgers but keep judging yesterday's aggregate health; omitting
# external_shadow_state made newly certified generic frontiers invisible after they enrolled.
for f in shadow_state.json qquant_shadow_state.json scalp_shadow_state.json \
         external_shadow_state.json shadow_health.json; do
  scp -pq "$REMOTE:C:/opt/quant/desks/mt5/reports/shadow/$f" \
      "desks/mt5/reports/shadow/$f.tmp" 2>/dev/null \
    && mv "desks/mt5/reports/shadow/$f.tmp" "desks/mt5/reports/shadow/$f"
done

# THE LEDGERS THEMSELVES, which this script's own header has claimed travel since it was written
# and which never did. MEASURED 2026-08-28: the box held 43 ledgers with 7 `phase: "forward"` rows
# -- one per live clock -- while the VPS copies were frozen at 2026-08-26T11:00 because nothing
# ever fetched them. `portfolio_evidence.daily_series()` reads ONLY `ledger_*.json` and counts
# only forward rows, so it reported "0 sleeve(s) with forward observations" and
# `check_live_readiness` blocked rung 0 on `independence: UNMEASURED`. That verdict reads as "the
# market has not supplied observations yet"; the observations existed, on the other machine. The
# state files crossed and the evidence they summarise did not.
# Staged into a temp directory and moved as a batch: a half-copied ledger read mid-pull is a
# truncated JSON array, and a reader that swallows the parse error counts the sleeve as empty --
# which is the same silent zero this fixes.
_LDIR="desks/mt5/reports/shadow/.ledgers.tmp"
rm -rf "$_LDIR" && mkdir -p "$_LDIR"
if scp -pq "$REMOTE:C:/opt/quant/desks/mt5/reports/shadow/ledger_*.json" "$_LDIR/" 2>/dev/null \
   && [ -n "$(ls -A "$_LDIR" 2>/dev/null)" ]; then
  for _l in "$_LDIR"/ledger_*.json; do
    # A ledger that does not parse is not an update. Never overwrite a good local copy with one.
    if .venv/bin/python -c "import json,sys; json.load(open(sys.argv[1]))" "$_l" 2>/dev/null; then
      mv "$_l" "desks/mt5/reports/shadow/$(basename "$_l")"
    fi
  done
fi
rm -rf "$_LDIR"
scp -pq "$REMOTE:C:/opt/quant/desks/mt5/reports/UNIVERSAL_SURVIVORS.json" \
    desks/mt5/reports/UNIVERSAL_SURVIVORS.json.tmp 2>/dev/null \
  && mv desks/mt5/reports/UNIVERSAL_SURVIVORS.json.tmp desks/mt5/reports/UNIVERSAL_SURVIVORS.json

# THE GATE REPORT ITSELF, which was never pulled at all. Every question worth asking about the
# pipeline -- which gate binds, how many cells were judged versus dropped, what the trial charge
# actually was -- is answered ONLY here, and this box was reading a copy two days older than the
# box that produced it. So the sweep ran hourly while every diagnosis made here described
# Wednesday, and the difference was invisible because the local file's mtime was refreshed by
# everything EXCEPT its own content.
# Measured 2026-08-28: local swept_at 08-26T04:54 (149 verdicts) against 08-28T01:13 (460
# verdicts) on the box. The recertification audit is the same story -- it decides whether a
# standing certificate still holds, and judging that from a stale copy is worse than not judging
# it, because it reports an answer.
for f in universal_gates_external.json recertification_audit.json; do
  scp -pq "$REMOTE:C:/opt/quant/desks/mt5/reports/$f" "desks/mt5/reports/$f.tmp" 2>/dev/null \
    && mv "desks/mt5/reports/$f.tmp" "desks/mt5/reports/$f"
done

# THE DOCKET ITSELF. Every breadth, ROI and backlog judgement made on this box reads
# external_survivors.json, and it was never on the pull list -- it arrived only when a fixer
# happened to scp it as a side effect. So the coverage checks were grading a docket that could be
# hours behind the one the gauntlet actually judges, and tonight a bond backfill that DID land on
# the desk box (6,270 rows, 214 bond candidates) left this box still reporting the class as
# starved from a 6,024-row copy.
for f in external_survivors.json coverage_search_results.json; do
  scp -pq "$REMOTE:C:/opt/quant/desks/mt5/data/hypotheses/$f" \
      "desks/mt5/data/hypotheses/$f.tmp" 2>/dev/null \
    && mv "desks/mt5/data/hypotheses/$f.tmp" "desks/mt5/data/hypotheses/$f"
done

# THE TRADING HALT MARKER. The desk auto-pauses itself when placement passes are rejected, and
# it writes a file saying exactly why. Nothing pulled that file and nothing read it, so the desk
# stopped trading on 2026-08-25 and reported it to no one for three days -- while every research
# organ went on being green, because research WAS healthy. The one number that matters was not
# among the numbers being checked.
# Absence is meaningful here and must be propagated, not merely skipped: a stale local copy would
# announce a halt that has since been cleared, which is the same lie in the other direction. So a
# failed pull DELETES the local marker rather than leaving yesterday's answer in place.
if scp -pq "$REMOTE:C:/opt/quant/desks/mt5/data/GATEWAY_PAUSED" \
        desks/mt5/data/GATEWAY_PAUSED.tmp 2>/dev/null; then
  mv desks/mt5/data/GATEWAY_PAUSED.tmp desks/mt5/data/GATEWAY_PAUSED
else
  rm -f desks/mt5/data/GATEWAY_PAUSED.tmp desks/mt5/data/GATEWAY_PAUSED
fi

# The job manifest judges FRESHNESS, so it has to see the trading box's own artifacts rather than
# this box's stale copies -- otherwise it would report a dead organ as healthy, which is the exact
# failure mode it exists to catch.
scp -pq "$REMOTE:C:/opt/quant/desks/mt5/reports/execution_quality.json" \
    desks/mt5/reports/execution_quality.json 2>/dev/null || true
for f in sleeve_registry.json decay_live.json forward_reconcile.json daily_cycle_state.json moat_coverage.json stall_watch.json; do
  scp -pq "$REMOTE:C:/opt/quant/desks/mt5/data/$f" "desks/mt5/data/$f" 2>/dev/null || true
done

# THE UNIVERSE REGISTRY TRAVELS BACK, NEVER-SHRINKING. Only the desk box can read the terminal,
# so it is the sole producer of tick_value/contract_size for all 251 symbols -- and every
# consumer here (merge, the searchers' symbol list, breadth, costing) reads the VPS copy. Pulled
# to a temp file and installed ONLY when it holds at least as many symbols as the copy in hand:
# the registry ratchets (L1.50) and a truncated or mid-write file must never become the local
# truth (measured 2026-08-27: a rogue writer left a 23-row stump that a sync then propagated).
_UT=desks/mt5/data/universe/universe.json.tmp
if scp -pq "$REMOTE:C:/opt/quant/desks/mt5/data/universe/universe.json" "$_UT" 2>/dev/null; then
  if python3 - "$_UT" desks/mt5/data/universe/universe.json <<'PY'
import json, sys
def n(p):
    try:
        d = json.load(open(p))
        return len(d) if isinstance(d, dict) else 0
    except Exception:
        return 0
new, cur = n(sys.argv[1]), n(sys.argv[2])
print(f"universe pull: desk={new} local={cur}")
sys.exit(0 if new and new >= cur else 1)
PY
  then
    mv "$_UT" desks/mt5/data/universe/universe.json
    echo "universe registry installed from the desk"
  else
    echo "universe pull REFUSED: desk copy is smaller than the local registry -- keeping local"
  fi
fi
rm -f "$_UT" 2>/dev/null || true

rm -f web/desk_state.json.tmp desks/mt5/reports/shadow/*.tmp desks/mt5/reports/*.tmp 2>/dev/null
if [ "$ok" = "1" ]; then
  echo "$(date -u +%FT%TZ) desk state pulled"
else
  echo "$(date -u +%FT%TZ) PULL FAILED -- serving last good copy; the page's age field shows it"
  exit 1
fi

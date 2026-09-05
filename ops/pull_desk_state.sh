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
# newer-only (reports): the VPS runs shadow passes too, and a stale box copy landing on top of a
# fresher local one is how IDENTITY_BROKEN rows and retired clocks keep reappearing after repair.
for f in shadow_state.json qquant_shadow_state.json scalp_shadow_state.json \
         external_shadow_state.json shadow_health.json; do
  _d="desks/mt5/reports/shadow/$f"
  if scp -pq "$REMOTE:C:/opt/quant/desks/mt5/reports/shadow/$f" "$_d.tmp" 2>/dev/null; then
    if [ ! -f "$_d" ] || [ "$_d.tmp" -nt "$_d" ]; then
      mv -f "$_d.tmp" "$_d"
    else
      rm -f "$_d.tmp"
      echo "pull kept local $f: the box copy is not newer"
    fi
  fi
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
# newer-only (reports): BOTH BOXES CERTIFY, so the box copy is not automatically the truth.
# The VPS gauntlet writes this file too. A blind overwrite meant every certificate the VPS sweep
# produced was reverted by the next pull, 90 seconds later: measured 2026-09-05, the canon read
# 66 survivors at 23:42 and 54 at 01:05 with an mtime of 22:45 -- the local sweep certified and
# the pull put the box's older canon back on top, so the desk looked like it was certifying
# nothing while it was certifying and losing it. scp -p preserves the remote mtime, so -nt
# compares the two canons honestly and the older one never wins.
_US=desks/mt5/reports/UNIVERSAL_SURVIVORS.json
if scp -pq "$REMOTE:C:/opt/quant/desks/mt5/reports/UNIVERSAL_SURVIVORS.json" "$_US.tmp" 2>/dev/null; then
  if [ ! -f "$_US" ] || [ "$_US.tmp" -nt "$_US" ]; then
    mv -f "$_US.tmp" "$_US"
  else
    rm -f "$_US.tmp"
    echo "pull kept local UNIVERSAL_SURVIVORS.json: the box canon is not newer"
  fi
fi

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
# NEWER-ONLY, BECAUSE THE VPS PRODUCES SOME OF THESE TOO. A blind overwrite made this pull a
# REVERTER: forward_reconcile.py runs here every 20 minutes and writes
# desks/mt5/data/forward_reconcile.json, and this loop then replaced it with the box's copy --
# 21 hours old on 2026-09-04 -- roughly every 90 seconds. The desk recomputed enrolment three
# times an hour and threw the answer away each time, while every freshness check read the stale
# file and reported the organ dead. scp -p preserves the remote mtime, so `-nt` compares the two
# copies honestly; the older side never wins, whichever box it came from.
for f in sleeve_registry.json decay_live.json forward_reconcile.json daily_cycle_state.json moat_coverage.json stall_watch.json; do
  _dst="desks/mt5/data/$f"
  _tmp="desks/mt5/data/.$f.incoming"
  if scp -pq "$REMOTE:C:/opt/quant/desks/mt5/data/$f" "$_tmp" 2>/dev/null; then
    if [ ! -f "$_dst" ] || [ "$_tmp" -nt "$_dst" ]; then
      mv -f "$_tmp" "$_dst"
    else
      rm -f "$_tmp"
      echo "pull kept local $f: the box copy is not newer"
    fi
  else
    rm -f "$_tmp" 2>/dev/null || true
  fi
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

# NEVER-SHRINKING IN BOTH DIMENSIONS (fields added 2026-08-29). The row-count half of this guard
# came from a 23-row stump that a sync propagated. The COLUMN half comes from the same class one
# level down: on 2026-08-29 a desk copy with all 251 symbols intact -- so it sailed past the row
# count -- had dropped `currency_profit` from every one of them, and this pull reinstalled the
# lossy copy every two minutes, defeating three restores by hand. currency_profit is MetaTrader5's
# OWN answer to what currency a symbol is denominated in, and it is the only correct route for a
# share or index CFD whose name ("3M", "AUS200") carries no denomination to parse; without it
# quote_currency() returns None and every cost downstream becomes UNMEASURED. This desk has
# already paid once for a column silently vanishing from this exact file (tick_value: 0/197
# costable, and a 184x JPY commission undercharge).
#
# The test is deliberately blunt in the safe direction: a field carried by at least a quarter of
# the LOCAL rows and by NONE of the incoming ones is a dropped column, not a schema change. A
# genuinely retired field is retired on the desk box and lands here the moment one row keeps it,
# and a NEW field on the desk copy is not restricted at all -- this can only ever refuse.
def load(p):
    try:
        d = json.load(open(p))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def fields(d):
    out = {}
    for row in d.values():
        if isinstance(row, dict):
            for k in row:
                out[k] = out.get(k, 0) + 1
    return out

new_d, cur_d = load(sys.argv[1]), load(sys.argv[2])
new, cur = len(new_d), len(cur_d)
print(f"universe pull: desk={new} local={cur}")
if not new or new < cur:
    sys.exit(1)
nf, cf = fields(new_d), fields(cur_d)

# ALL-OR-NOTHING MISSED PARTIAL LOSS, WHICH IS THE COMMON CASE. This refused only when a field
# was absent from EVERY incoming row, so a desk copy carrying `currency_profit` on 200 of 251
# symbols and dropping it from the other 51 sailed through -- `nf[k] > 0`, therefore "not
# dropped". Measured 2026-09-03: the local registry went 4,067 fields -> 3,864 through this
# guard, 203 records gone, `currency_profit` among them, and the protected-records fence caught
# it only at commit time. That field is MetaTrader5's own answer to what a symbol is denominated
# in and the only correct route for a share or index CFD whose name carries no denomination.
#
# UNION, NOT REFUSAL, AND IT IS STRICTLY BETTER THAN EITHER PREVIOUS OUTCOME. Refusing kept the
# local copy and threw away every fresh value the desk had just measured; installing kept the
# fresh values and threw away the fields. The union keeps both: the incoming row wins on every
# field it HAS -- it is the newer measurement of the broker's own registry -- and any field the
# local row carries and the incoming one lacks is carried forward. A field can therefore only
# ever be added by a pull, never removed, which is what a ratcheting registry means (L1.50).
#
# A genuine retirement is still possible; it just cannot happen silently through a sync. It is
# done on the file itself, deliberately, and named -- the same standard the certificate ratchet
# holds revocations to.
restored = 0
for sym, row in new_d.items():
    cur_row = cur_d.get(sym)
    if not isinstance(row, dict) or not isinstance(cur_row, dict):
        continue
    for k, v in cur_row.items():
        if k not in row:
            row[k] = v
            restored += 1
for sym, row in cur_d.items():
    if sym not in new_d:
        new_d[sym] = row                 # a symbol the desk stopped reporting is not a deletion
        restored += 1
if restored:
    print(f"universe pull: union kept {restored} record(s) the desk copy omitted")
    json.dump(new_d, open(sys.argv[1], "w"), indent=1, sort_keys=True)
nf2 = fields(new_d)
still = sorted(k for k, c in cf.items() if nf2.get(k, 0) < c)
if still:
    print("universe pull: REFUSING -- union still loses: "
          + ", ".join(f"{k} ({cf[k]} local -> {nf2.get(k, 0)})" for k in still[:6]))
    sys.exit(2)
sys.exit(0)
PY
  then
    mv "$_UT" desks/mt5/data/universe/universe.json
    echo "universe registry installed from the desk"
  else
    echo "universe pull REFUSED: desk copy shrinks the local registry (rows or columns) -- keeping local"
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

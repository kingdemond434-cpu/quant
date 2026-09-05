#!/usr/bin/env bash
# Pull the H1 bar set from the trading box. Nothing else did.
#
# WHY THIS EXISTS (2026-09-04)
#
# Measured: every one of 200 H1 parquets on the VPS was stale -- median 210 hours, ZERO fresher
# than 24h, the freshest 73h -- while the trading box held 299 files written minutes earlier from
# the live terminal. `pull_desk_state.sh` fetches state, reports, ledgers and the universe
# REGISTRY, and has never fetched the bars themselves.
#
# Everything VPS-side that reads bars was therefore reading an eight-day-old market: the research
# loop, the adapter registry, every measurement class, and the bar-coverage fence. None of it
# errored -- stale parquets load perfectly -- so the whole research plane was producing confident
# answers about a week-old world.
#
# STAGE THEN SWAP, per file. A partially written parquet is unreadable, and the forward engine and
# research loop read this directory on a timer, so a mid-transfer read would surface as a corrupt
# bar file rather than as a sync in progress.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
REMOTE="${REMOTE:-contabo-mt5}"
DEST="desks/mt5/data/universe"
STAGE="$DEST/.incoming"
mkdir -p "$STAGE"

# ONE STREAM, NOT 299 ROUND TRIPS. A per-file `scp` of the wildcard took longer than the job's
# own timeout and was killed part-way through, leaving a half-populated staging directory and
# installing nothing -- the first version of this script did exactly that. `tar -cf -` over a
# single ssh moves the whole 221MB set in one connection, and Windows ships tar.exe natively.
#
# tar preserves mtimes, which is what every freshness check downstream reads. Without that an
# eight-day-old file arrives stamped NOW and reports as current -- the exact failure this script
# exists to end, reintroduced by its own transfer.
if ! timeout 900 ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=20 \
      "$REMOTE" 'cd C:\opt\quant\desks\mt5\data\universe && tar -cf - *_H1.parquet' \
      | tar -xf - -C "$STAGE" 2>/dev/null; then
  echo "bar pull: stream failed -- staged files discarded, existing bars untouched"
  rm -rf "$STAGE"
  exit 1
fi

n=0
for f in "$STAGE"/*_H1.parquet; do
  [ -e "$f" ] || continue
  mv -f "$f" "$DEST/$(basename "$f")" && n=$((n + 1))
done
rm -rf "$STAGE"
if [ "$n" -eq 0 ]; then
  echo "bar pull: stream returned no files -- nothing installed"
  exit 1
fi
echo "bar pull: $n H1 file(s) installed from $REMOTE"

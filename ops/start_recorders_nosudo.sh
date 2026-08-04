#!/usr/bin/env bash
# START (AND KEEP ALIVE) THE RECORDERS WITHOUT ROOT.
#
# WHY THIS EXISTS. The `quant` user has no sudo, so /etc/systemd/system is unreachable and the
# unit files cannot be installed. That is not a reason to leave the tape unrecorded: every
# unrecorded second is permanently unbuyable at any price, and this is the only cost on the desk
# that money cannot fix afterwards. So this reproduces the one property of the units that actually
# matters -- Restart=always -- using nothing but a user crontab.
#
# IDEMPOTENT BY DESIGN. It is both the STARTER and the WATCHDOG: run it every few minutes from
# cron and it starts whatever is not running and leaves alone whatever is. That gives the same
# guarantee as Restart=always with zero privileges, and it also covers the case a supervisor loop
# would miss -- the supervisor itself dying.
#
# Public market data only: no keys, no order paths. Recording is not trading.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PY="${QUANT_PY:-.venv/bin/python}"
[ -x "$PY" ] || PY="python3"
mkdir -p data

start_if_down() {
    local name="$1" script="$2"
    # Match on the SCRIPT PATH, not the name: `pgrep -f run_recorder` also matches
    # run_recorder_spot and run_recorder_bybit, so a single loose pattern would report all three
    # alive the moment any one of them started -- and the desk would silently record one venue
    # while believing it recorded three.
    if pgrep -f "[s]cripts/${script}" >/dev/null 2>&1; then
        echo "  ok      ${name} already running"
        return 0
    fi
    nohup "$PY" "scripts/${script}" >> "data/recorder_${name}.log" 2>&1 &
    sleep 1
    if pgrep -f "[s]cripts/${script}" >/dev/null 2>&1; then
        echo "  STARTED ${name} (pid $(pgrep -f "[s]cripts/${script}" | head -1))"
    else
        # A recorder that refuses to start is usually the rate-budget guard, which is deliberate:
        # an unnoticed weight overrun got this desk's IP cut off by Binance for six hours.
        echo "  FAILED  ${name} -- see data/recorder_${name}.log (last line below)"
        tail -1 "data/recorder_${name}.log" 2>/dev/null | sed 's/^/          /'
    fi
}

echo "recorders $(date -u +%FT%TZ):"
start_if_down fut   run_recorder.py
start_if_down spot  run_recorder_spot.py
start_if_down bybit run_recorder_bybit.py

# The miner is started LAST and only if something is recording -- it has nothing to read
# otherwise, and a miner reporting 0% because no tape exists is noise that hides the real signal.
if [ -d data/moat ] && [ -n "$(ls -A data/moat 2>/dev/null)" ]; then
    if pgrep -f "[s]cripts/mine_moat.py --loop" >/dev/null 2>&1; then
        echo "  ok      moat-miner already running"
    else
        MOAT_FILE_BUDGET="${MOAT_FILE_BUDGET:-40}" \
          nohup "$PY" scripts/mine_moat.py --loop --interval 15 \
          >> data/moat_miner.log 2>&1 &
        echo "  STARTED moat-miner (continuous)"
    fi
    # THE HUNT, NOT ONLY THE MINE. The miner DESCRIBES the tape; the screen ASKS it whether any
    # mechanism actually predicts. Running the first continuously and the second on a daily
    # cadence was the asymmetry: an irreplaceable asset measured around the clock and interrogated
    # once a day. Both carry their own persisted coverage frontier, so both converge.
    if pgrep -f "[s]cripts/screen_moat.py --loop" >/dev/null 2>&1; then
        echo "  ok      moat-screen already running"
    else
        nohup "$PY" scripts/screen_moat.py --files "${MOAT_SCREEN_FILES:-24}" \
          --loop --interval "${MOAT_SCREEN_INTERVAL:-30}" \
          >> data/moat_screen.log 2>&1 &
        echo "  STARTED moat-screen (continuous survivor hunt)"
    fi
else
    echo "  wait    moat-miner not started: data/moat is empty, nothing to mine yet"
fi

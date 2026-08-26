#!/usr/bin/env bash
# EARLY-WINDOW SEAT TIMERS (gap-fixer 2026-08-26) -- the arrivals-collapse repair.
#
# MEASURED, not guessed. 101 headless seat launches over the 7 days to 2026-08-26 produced
# only 20 real digs (19.8%); 58 died on `auth unavailable` before launching at all. The
# failure is a clean time-of-day pattern, not randomness:
#
#     00:00-09:00 UTC   14 produced /  7 dead   (67% success)  <- subscription quota available
#     14:00-20:00 UTC    3 produced / 60 dead   ( 5% success)  <- quota exhausted
#
# Whole families sit at zero: dataaxis 0/7 at 14:00, prospector 0/7 at 18:00, litminer 0/8
# at 19:00, all six regional frontier seats 0/26 at 15:00. The desk read this as an arrivals
# collapse and was told to hunt harder; the miners were dying at launch.
#
# ROOT CAUSE: every dig row in ops/crontab.manifest is guarded by
#   `systemctl is-enabled quant-<seat>.timer || <run it>`
# and ROOT systemd timers for those seats exist at 14:00/15:00/18:00/19:00 -- precisely the
# exhausted window. The guard therefore suppresses the manifest's own EARLY slots (03/05/06/07,
# in the productive window) in favour of root timers that fire into a wall and fail. Those root
# units are the `quant-dataaxis/frontier/prospector` failures in `systemctl --failed`, and root
# is the principal's console -- unreachable from here.
#
# THE REPAIR, entirely in userland: re-home the manifest's OWN early slots as user timers, with
# the is-enabled guard dropped (its purpose was to avoid double-scheduling against a root timer
# that WORKS). Nothing is invented -- same scripts, same flocks, same logs, same hours the
# manifest already specifies. The shared /tmp/seat_*.lock keeps a user run and a root run from
# ever overlapping, and every dig is resume-aware, so a successful early run makes the doomed
# afternoon run cheap instead of duplicative.
#
# SLOT CHOICE IS MEASURED, and re-measurable: scripts/check_seat_launch_yield.py publishes the
# per-hour table to data/seat_launch_yield.json and names the productive hours. On the 7 days to
# 2026-08-26 those were 05:00-09:00 UTC (80-100% of launches produced) against 14:00-19:00 UTC
# (0-14%). The rotation keeps a second 03:00 bite because it is resume-safe and costs one ping
# when the earlier slot already produced. Re-run this installer when the fence's productive
# hours move -- the quota window is a fact about the subscription, not a constant.
#
# Idempotent: re-running rewrites the units and re-enables them.
set -euo pipefail
U="$HOME/.config/systemd/user"
mkdir -p "$U"

install_seat() {  # name  oncalendar  command  [success_exit_codes]
    local name="$1" cal="$2" cmd="$3" ok="${4:-0}"
    # A FENCE THAT CORRECTLY REPORTS A BREACH EXITS NONZERO, and without SuccessExitStatus
    # systemd files that under `--failed` and the global death-visibility drop-in writes it to
    # unit_deaths.jsonl -- making a working fence indistinguishable from a crash-looping organ.
    # That is the desk's own silence lesson pointed the other way: the alarm channel gets so
    # noisy that a real death stops standing out. Same convention as quant-sameday-fence.
    cat > "$U/quant-seat-$name.service" <<EOF
[Unit]
Description=Early-window seat: $name (manifest slot re-homed; root timer fires into the exhausted quota window)

[Service]
Type=oneshot
WorkingDirectory=/home/quant/quant-platform
TimeoutStartSec=3h
SuccessExitStatus=$ok
ExecStart=/bin/bash -c '$cmd'
EOF
    cat > "$U/quant-seat-$name.timer" <<EOF
[Unit]
Description=Timer for early-window seat: $name

[Timer]
OnCalendar=$cal
RandomizedDelaySec=180
Persistent=true
Unit=quant-seat-$name.service

[Install]
WantedBy=timers.target
EOF
    systemctl --user enable --now "quant-seat-$name.timer" >/dev/null
    echo "  installed quant-seat-$name.timer  ($cal)"
}

install_seat frontier "*-*-* 08:00:00 UTC" \
  'flock -n /tmp/seat_frontier.lock /bin/bash ops/run_frontier_rotation.sh >> data/cro_ai_logs/seat_frontier.log 2>&1'
install_seat dataaxis "*-*-* 05:00:00 UTC" \
  'flock -n /tmp/seat_dataaxis.lock /bin/bash ops/run_dataaxis_dig.sh >> data/cro_ai_logs/seat_dataaxis.log 2>&1'
install_seat prospector "*-*-* 06:00:00 UTC" \
  'flock -n /tmp/seat_prospector.lock /bin/bash ops/run_prospector_dig.sh >> data/cro_ai_logs/seat_prospector.log 2>&1'
install_seat litminer "*-*-* 07:00:00 UTC" \
  'flock -n /tmp/seat_litminer.lock /bin/bash ops/run_litminer_dig.sh >> data/cro_ai_logs/seat_litminer.log 2>&1'
install_seat frontier2 "*-*-* 03:00:00 UTC" \
  'flock -n /tmp/seat_frontier.lock /bin/bash ops/run_frontier_rotation.sh >> data/cro_ai_logs/seat_frontier.log 2>&1'

# THE FENCE THAT WATCHES THIS REPAIR. Without it the next quota-window shift is invisible again
# and the desk re-learns the lesson by reading "arrivals collapsed" and hunting harder. Daily at
# 10:00 UTC -- after the whole early window has run, so it grades the day it is measuring.
install_seat launch-yield "*-*-* 10:00:00 UTC" \
  '.venv/bin/python scripts/check_seat_launch_yield.py >> data/cro_ai_logs/seat_launch_yield.log 2>&1' \
  '0 2'

systemctl --user daemon-reload
echo "early-window seat timers installed."

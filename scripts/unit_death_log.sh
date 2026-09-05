#!/usr/bin/env bash
# Fleet-wide unit-death visibility (gap-fixer 2026-08-26). Invoked by the global user-scope
# drop-in ops/service.d/10-death-visibility.conf (installed at
# ~/.config/systemd/user/service.d/) as ExecStopPost for EVERY user service, so an oom-kill,
# timeout or crash leaves a durable line even when the unit's own log got nothing.
# Context: 3 gap-wirer seats were OOM-killed silently on 2026-08-26 (zero swap, 4GB box);
# each left a 58-byte log indistinguishable from an auth failure.
# $1 = unit name (%n). systemd sets SERVICE_RESULT / EXIT_CODE / EXIT_STATUS for ExecStopPost.
# Always exits 0: a logging fence must never change a unit's own result.
RESULT="${SERVICE_RESULT:-unknown}"
[ "$RESULT" = "success" ] && exit 0
LOG=/home/quant/quant-platform/data/cro_ai_logs/unit_deaths.jsonl
mkdir -p "$(dirname "$LOG")" 2>/dev/null
printf '{"ts":"%s","unit":"%s","result":"%s","exit_code":"%s","exit_status":"%s"}\n' \
  "$(date -u +%FT%TZ)" "${1:-unknown}" "$RESULT" "${EXIT_CODE:-}" "${EXIT_STATUS:-}" >> "$LOG" 2>/dev/null
exit 0

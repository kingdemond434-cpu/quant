#!/usr/bin/env bash
# ROOT-ONLY, explicit host deployment. This script is generated and tested in-repo but is never
# invoked by an autonomous research cycle. It copies rather than symlinks: the live service must
# not follow a research-owned worktree after installation.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "root required" >&2; exit 1; }
SOURCE_ROOT="${1:-/home/quant/quant-platform}"
TARGET=/opt/quant-risk-kernel
STATE=/var/lib/quant-risk-kernel
LOG=/var/log/quant-risk-kernel

test -f "$SOURCE_ROOT/scripts/run_deadman_switch.py"
test -f "$SOURCE_ROOT/docs/research/RISK_KERNEL_LOCK.json"

id -u quant-risk >/dev/null 2>&1 || useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin quant-risk
install -d -o root -g quant-risk -m 0750 "$TARGET" "$TARGET/scripts" "$TARGET/libs" "$TARGET/docs/research"
install -d -o quant-risk -g quant-risk -m 0750 "$STATE" "$LOG"

# Copy the complete imported Python package trees, then remove write permission from both service
# and research users. Root is the sole deployment authority.
cp -a "$SOURCE_ROOT/libs/." "$TARGET/libs/"
install -o root -g quant-risk -m 0550 "$SOURCE_ROOT/scripts/run_deadman_switch.py" "$TARGET/scripts/run_deadman_switch.py"
install -o root -g quant-risk -m 0440 "$SOURCE_ROOT/docs/research/RISK_KERNEL_LOCK.json" "$TARGET/docs/research/RISK_KERNEL_LOCK.json"
find "$TARGET/libs" -type d -exec chmod 0550 {} +
find "$TARGET/libs" -type f -exec chmod 0440 {} +
chown -R root:quant-risk "$TARGET"

python3 -m venv "$TARGET/venv"
"$TARGET/venv/bin/pip" install -r "$SOURCE_ROOT/requirements-vps.txt"
chown -R root:quant-risk "$TARGET/venv"
find "$TARGET/venv" -type d -exec chmod 0550 {} +
find "$TARGET/venv" -type f -exec chmod 0440 {} +

install -o root -g root -m 0644 "$SOURCE_ROOT/deploy/privilege_separation/quant-risk-kernel.service" \
  /etc/systemd/system/quant-risk-kernel.service
systemctl daemon-reload
systemctl enable quant-risk-kernel.service

echo "Installed but not started. Verify environment/reconciliation, then root starts the service explicitly."

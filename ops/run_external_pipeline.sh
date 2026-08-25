#!/bin/bash
# STAGES 2-3 OF THE SAME-DAY PIPELINE (RESEARCH §6d), chained so a discovery mined today is
# certified today: external hypotheses -> stage-A backtest -> full ten-gate gauntlet -> canon.
# Before 2026-08-26 both stages ran only when a human typed them; today's 15-pass sweep was a
# manual run, and tomorrow's discoveries would have sat unbacktested -- the exact waiting room
# the law forbids.
set -u
cd /home/quant/quant-platform
PY=.venv/bin/python

echo "[$(date -u +%FT%TZ)] stage 2: external backtest"
$PY desks/mt5/side_channels/run_external_backtest.py || echo "stage 2 FAILED (rc=$?)"

echo "[$(date -u +%FT%TZ)] stage 3: ten-gate gauntlet"
$PY desks/mt5/scripts/external_gauntlet.py || { echo "stage 3 FAILED (rc=$?)"; exit 1; }

# Stage 4: certificates -> canon copy -> desk box. The canon file is what the authority
# ratchet floors and what restores the authority file after a bad writer.
$PY - <<'PYEOF'
import json, shutil
from pathlib import Path
auth = Path("desks/mt5/reports/UNIVERSAL_SURVIVORS.json")
canon = Path("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json")
a = json.loads(auth.read_text("utf-8"))
c = json.loads(canon.read_text("utf-8")) if canon.exists() else {"survivors": {}}
if len(a.get("survivors", {})) >= len(c.get("survivors", {})):
    shutil.copyfile(auth, canon)
    print(f"canon updated: n={len(a['survivors'])}")
else:
    print(f"canon NOT updated: authority {len(a.get('survivors', {}))} < canon "
          f"{len(c['survivors'])} -- ratchet holds")
PYEOF

scp -q desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json \
    contabo-mt5:'C:/opt/quant/desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json' \
  && echo "canon synced to desk box" || echo "desk-box sync FAILED (will retry next run)"
echo "[$(date -u +%FT%TZ)] external pipeline done"

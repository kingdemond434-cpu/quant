#!/usr/bin/env python3
"""Fix manifest + timer: SYSTEMD entries instead of cron lines; single OnCalendar."""
from pathlib import Path

# 1) Remove the cron lines I added, keep the comment block, append SYSTEMD entries
mp = Path("/home/quant/quant-platform/ops/crontab.manifest")
src = mp.read_text()

start_marker = "# ---------------------------------------------------------------------------------------------\n# X/TWITTER INTELLIGENCE + COT POSITIONING (added 2026-08-16)"
if start_marker not in src:
    print("Manifest start marker not found")
    raise SystemExit(2)
# find the block: from start_marker to EOF (it was appended at the end)
idx = src.find(start_marker)
src = src[:idx]

systemd_block = """# ---------------------------------------------------------------------------------------------
# X/TWITTER INTELLIGENCE + COT POSITIONING (added 2026-08-16)
# quant-x-collector.timer :05 hourly -> scripts/collect_x_signals.py (x.com SSR fallback)
# quant-x-deepmine.timer  06:15/14:15/22:15 -> scripts/deep_mine_x.py (priority accounts:
#   L1vsun, shmidtqq, antpalkin -- quant research systems mined for mechanisms)
# quant-cot-fetch.timer   Fri 20:30 -> scripts/fetch_cot.py (CFTC COT weekly positioning,
#   feeds cot_positioning_reversal generator via libs/autodiscovery/crypto_adapter.py)
# NOTE: all three run on the USER TIMER PLANE (systemd), like the autodiscovery slices; the
# cron plane is not used for them, so they carry SYSTEMD entries, not cron lines.
SYSTEMD unit="quant-x-collector.timer" on="*:05" exec="scripts/collect_x_signals.py"
SYSTEMD unit="quant-x-deepmine.timer" on="*-*-* 06,14,22:15:00" exec="scripts/deep_mine_x.py"
SYSTEMD unit="quant-cot-fetch.timer" on="Fri *-*-* 20:30:00" exec="scripts/fetch_cot.py"
"""
src = src.rstrip() + "\n\n" + systemd_block
mp.write_text(src)
print("Manifest updated")

# 2) Fix the deepmine timer: single OnCalendar with comma list
tp = Path("/home/quant/quant-platform/ops/quant-x-deepmine.timer")
tsrc = tp.read_text()
old_cal = """[Timer]
OnCalendar=*-*-* 06:15:00
OnCalendar=*-*-* 14:15:00
OnCalendar=*-*-* 22:15:00
Persistent=true"""
new_cal = """[Timer]
OnCalendar=*-*-* 06,14,22:15:00
Persistent=true"""
if old_cal not in tsrc:
    print("Timer calendar pattern not found")
    raise SystemExit(3)
tp.write_text(tsrc.replace(old_cal, new_cal))
print("Timer updated")

# 3) Copy fixed timer to user plane
import shutil
shutil.copy(tp, Path.home() / ".config/systemd/user/quant-x-deepmine.timer")
print("User timer synced")
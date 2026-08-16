#!/usr/bin/env python3
from pathlib import Path

p = Path("/home/quant/quant-platform/ops/crontab.manifest")
src = p.read_text()

block = """# ---------------------------------------------------------------------------------------------
# AUTODISCOVERY SLICES (10 x 30-symbol chunks over the full lake, one pass per hour)
# quant-autodiscovery-slice{0..9}.timer at :00,:10,:20,:30,:40,:50,:03,:13,:23,:33
# -> scripts/run_crypto_research.py --max-symbols 30 --offset {0,30,...,270}
# 30-symbol chunk = the PROVEN memory-safe size on this 3.8GB/2-core box (50-symbol chunks
# OOM-killed: CI pytest + moats hold ~1.2GB RSS, leaving <500MB for candidate series).
# NOTE: user timer plane only, like the x-intel timers -- cron lines would double-run them.
SYSTEMD unit="quant-autodiscovery-slice0.timer" on="*:00" exec="scripts/run_crypto_research.py"
SYSTEMD unit="quant-autodiscovery-slice1.timer" on="*:10" exec="scripts/run_crypto_research.py"
SYSTEMD unit="quant-autodiscovery-slice2.timer" on="*:20" exec="scripts/run_crypto_research.py"
SYSTEMD unit="quant-autodiscovery-slice3.timer" on="*:30" exec="scripts/run_crypto_research.py"
SYSTEMD unit="quant-autodiscovery-slice4.timer" on="*:40" exec="scripts/run_crypto_research.py"
SYSTEMD unit="quant-autodiscovery-slice5.timer" on="*:50" exec="scripts/run_crypto_research.py"
SYSTEMD unit="quant-autodiscovery-slice6.timer" on="*:03" exec="scripts/run_crypto_research.py"
SYSTEMD unit="quant-autodiscovery-slice7.timer" on="*:13" exec="scripts/run_crypto_research.py"
SYSTEMD unit="quant-autodiscovery-slice8.timer" on="*:23" exec="scripts/run_crypto_research.py"
SYSTEMD unit="quant-autodiscovery-slice9.timer" on="*:33" exec="scripts/run_crypto_research.py"
"""
src = src.rstrip() + "\n\n" + block
p.write_text(src)
print("Added 10 slice SYSTEMD entries")
#!/usr/bin/env python3
import sys

sys.path.insert(0, '/home/quant/quant-platform')
from scripts.run_cashcarry_executor import _check_dynamic_leverage_gate, _dynamic_capital

print("imports OK")
gate, details = _check_dynamic_leverage_gate()
print("gate passed:", gate)
print("reason:", details.get('reason'))
print("days_clean:", details.get('days_clean'))
print("checks:", details.get('checks'))
print("operator capital test:", _dynamic_capital(4500.0))

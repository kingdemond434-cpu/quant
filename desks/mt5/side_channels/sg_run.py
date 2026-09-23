import sys, traceback
sys.path.insert(0, r"C:\Users\dell\mt5-research\research")
sys.argv = ["signal_gate.py", "run_hunt18", "reports/hunt18_h18-004.json", "XAUUSD"]
import signal_gate
try:
    sys.exit(signal_gate.main())
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
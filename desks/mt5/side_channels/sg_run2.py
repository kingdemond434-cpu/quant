import sys, time, traceback
sys.path.insert(0, r"C:\Users\dell\mt5-research\research")
sys.argv = ["signal_gate.py", "run_hunt18", "reports/hunt18_h18-004.json"]
import signal_gate
t0 = time.time()
try:
    rc = signal_gate.main()
    print("MAIN RETURNED", rc, "%.1fs" % (time.time() - t0))
    sys.exit(rc)
except BaseException as e:
    traceback.print_exc()
    print("EXC", repr(e), "%.1fs" % (time.time() - t0), flush=True)
    sys.exit(99)
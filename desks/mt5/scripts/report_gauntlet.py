import json
r = json.load(open("/home/quant/quant-platform/desks/mt5/reports/universal_gates_external.json"))
print(f"Matrix: PBO={r['program_level']['pbo']:.4f}, SPA p={r['program_level']['spa_p']:.4f}")
print(f"n_trials={r['n_trials']}, cells={r['n_cells']}")
print(f"\n{r['survivors_passing_all']}/{r['n_cells']} PASS ALL 10 GATES\n")
for v in r["verdicts"]:
    st = "PASS" if v["passed"] else "FAIL"
    sr = v["stages"]["in_sample_screen"].get("sharpe", 0)
    dsr = v["stages"]["deflated_sharpe"].get("dsr", 0)
    wf = v["stages"]["walk_forward"].get("oos_sharpe", 0)
    ev = v["stages"]["expected_value"].get("ev", 0)
    fails = [n for n, s in v["stages"].items() if not s["passed"]]
    extra = f"  FAIL: {', '.join(fails)}" if fails else ""
    print(f"{st} {v['cell']:<55} n={v['days']:<5} SR={sr:.4f} DSR={dsr:.4f} WF={wf:.4f} EV={ev:.4f}{extra}")

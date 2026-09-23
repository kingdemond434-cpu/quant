@echo off
rem EVERY CLOCK IS CERTIFIED OR RETIRED -- nothing squats (principal 2026-08-26).
rem
rem forward_reconcile is called from daily_cycle.py:134, and daily_cycle is NOT SCHEDULED on the
rem trading box -- so on the box that actually trades it had never run. Measured 2026-09-12: 32
rem clocks sat ACTIVE with `promotion_authority: false` and `gate_reason: "missing exact original
rem universal ten-gate pass"`, accruing forward evidence they were structurally barred from ever
rem cashing, and 40 more were orphans no engine enrols. First run took 81 actions and the roster
rem went NO_AUTHORITY 32 -> 0.
rem
rem It fails soft by construction: unreadable enrolment disables retirement for the pass, and
rem retiring only sets a status and a reason -- ledgers, trade lists and day counts are untouched,
rem so a retired row stays auditable and a future certificate can revive it on a FRESH window.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-ForwardReconcile.log"
cd /d C:\opt\quant\desks\mt5
"C:\Program Files\Python314\python.exe" -u research\forward_reconcile.py >>"%LOG%" 2>&1
exit /b 0

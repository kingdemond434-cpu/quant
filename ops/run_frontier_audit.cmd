@echo off
rem THE FRONTIER MEASUREMENT LANE (2026-09-12) -- six organs that were built and ran nowhere.
rem
rem III.16: unwired or idle is a defect, and "built" is not a status. Each of these has a main(),
rem writes an artifact and had no caller anywhere in the tree -- measured by grepping every .cmd,
rem .ps1, .sh and .manifest in the repo for their module names and getting nothing back.
rem
rem WHY ONE TASK AND NOT SIX. Every one of them is a pure MEASUREMENT: it reads artifacts the desk
rem already holds, writes a report, and touches no ledger, no sizing and no order. They share a
rem cadence for the same reason -- each answers a question whose truth moves on the scale of a
rem session calendar, not an hour, and re-deriving them hourly would spend the box's parquet IO
rem re-computing the same numbers.
rem
rem ORDER IS DELIBERATE. certificate_hygiene runs FIRST because it is the only one that mutates
rem anything (it evicts unrunnable certificates into their own file), and every organ after it
rem should read the registry it leaves behind rather than the one it found.
rem
rem NONE OF THEM TIGHTENS ANYTHING. forward_calibration states it outright: a high false-admission
rem rate is not licence to raise the bar, because that is a growth cut wearing a statistic. These
rem supply evidence to the CEO docket; the docket decides.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-FrontierAudit.log"
set "PY=C:\Program Files\Python314\python.exe"
cd /d C:\opt\quant
"%PY%" -u "desks\mt5\research\certificate_hygiene.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\book_forensics.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\pit_audit.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\forward_calibration.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\orthogonality.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\unknown_unknowns.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\world_model.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\representation_discovery.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "desks\mt5\research\joint_evolution.py" --apply >>"%LOG%" 2>&1
exit /b 0

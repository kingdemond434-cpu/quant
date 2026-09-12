@echo off
rem F7 -- THE SCIENTIST TOURNAMENT, RIGHT AFTER THE FREE BUDGET RESETS (2026-09-12).
rem
rem 00:30 UTC, which is 02:30 on this box's clock. The cadence is not a preference: the panel
rem costs twelve requests per subject, and this account's REAL free ceiling -- learned from the
rem provider's own 429 rather than assumed -- was 563 requests on the day this was written. Run
rem at any other hour and the tournament competes with the audit lane, the deepseek cycle and the
rem hypothesis generator for a budget they have already spent, and seats no panel at all.
rem
rem ONE SUBJECT. Twelve calls buys ten independent critics, a reviewer and a meta-reviewer on ONE
rem certificate. Two subjects would buy twenty-four shallower readings, and the product of this
rem organ is the DISAGREEMENT between critics who read different evidence -- which needs the
rem panel complete, not the sample wide.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "QUANT_FREE_TIER=1"
set "SSL_CERT_FILE=C:\Program Files\Python314\Lib\site-packages\certifi\cacert.pem"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-ScientistTournament.log"
cd /d C:\opt\quant
"C:\Program Files\Python314\python.exe" -u "desks\mt5\research\scientist_tournament.py" --apply --subjects 1 >>"%LOG%" 2>&1
exit /b 0

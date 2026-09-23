@echo off
rem F1 OF THE 28: one canonical release, and nothing else touches the money path.
rem
rem libs/ops/release.verify() and libs/ops/release_signing.verify() both existed, were both
rem correct, and neither had a caller outside its own test. Two complete guards standing between
rem an unreviewed process and the files that size real positions, and the box never asked either
rem one a question. This asks, every 15 minutes.
rem
rem Exit 1 means money-path drift, an unsigned release, or an adoption that would overwrite
rem unpushed work. MT5-NeverStale reads the artifact.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-ReleaseAuthority.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\ops\release_authority.py" >>"%LOG%" 2>&1
exit /b 0

# Register MT5-PresserSTT and install its LOCAL speech model (build C row 48, 2026-11-18).
#
# WHAT IT DOES, in order, printing each result:
#   1. Measures free RAM with psutil (never CIM: it has hung on the trading box). Below 6 GB free
#      nothing is installed: the trading terminal keeps its memory.
#   2. pip-installs faster-whisper at a PINNED version into the desk's Python, unless it already
#      imports. Nothing installs at import time anywhere else; desks/mt5/research/presser_stt.py
#      reports UNMEASURED with the reason until this has run.
#   3. Downloads the CTranslate2 "small" weights once into C:\opt\whisper\models\small and sets
#      MACHINE env QUANT_WHISPER_MODEL_DIR to it. The module loads with local_files_only, so no
#      later run touches the network for the model.
#   4. Registers MT5-PresserSTT: `presser_stt.py --watch` every 5 minutes, IgnoreNew, priority 7
#      (BELOW_NORMAL), 2 h limit (a live press conference is at most ~75 minutes). Outside a
#      press-conference window, or when the window's source is not ALLOWED on terms and robots,
#      a run writes reports\PRESSER_STT.json and exits in under a second.
#
# It never touches the gateway, the judge, a sleeve, an allocator fraction or a key. To undo:
#   Unregister-ScheduledTask MT5-PresserSTT -Confirm:$false
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_presser_stt_task.ps1

$ErrorActionPreference = 'Stop'
$TaskName = 'MT5-PresserSTT'
$Python   = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe'
$ModelDir = 'C:\opt\whisper\models\small'
$Pin      = 'faster-whisper==1.1.1'
function Say($m) { Write-Host ("[presser-stt] " + $m) }

$freeGb = [double](& $Python -c "import psutil; print(round(psutil.virtual_memory().available/1024**3,1))")
Say ("free RAM (psutil): {0} GB" -f $freeGb)
if ($freeGb -lt 6) { Say 'below 6 GB free: nothing installed; the module stays UNMEASURED'; exit 2 }

& $Python -c "import faster_whisper" 2>$null
if ($LASTEXITCODE -ne 0) {
    Say "installing $Pin"
    & $Python -m pip install --only-binary=:all: $Pin
    if ($LASTEXITCODE -ne 0) { Say 'pip install failed: the module stays UNMEASURED'; exit 3 }
}

if (-not (Test-Path (Join-Path $ModelDir 'model.bin'))) {
    New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null
    Say "downloading model weights to $ModelDir"
    & $Python -c "from huggingface_hub import snapshot_download as s; s('Systran/faster-whisper-small', local_dir=r'$ModelDir')"
    if ($LASTEXITCODE -ne 0) { Say 'model download failed: the module stays UNMEASURED'; exit 4 }
}
[Environment]::SetEnvironmentVariable('QUANT_WHISPER_MODEL_DIR', $ModelDir, 'Machine')

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant\desks\mt5 && set QUANT_WHISPER_MODEL_DIR=' + $ModelDir + ' && ' +
  '"' + $Python + '" -u -W ignore research\presser_stt.py --watch ' +
  '>> C:\opt\quant\desks\mt5\logs\MT5-PresserSTT.log 2>&1')
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
             -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable -Priority 7
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -User 'Administrator' -RunLevel Highest -Force | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
Say ("$TaskName registered: " + $t.State)

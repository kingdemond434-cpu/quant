# Register MT5-PresserSTT and install its LOCAL speech model (build C row 48, 2026-11-18).
#
# THE DESK'S INTERPRETER IS NEVER CHANGED (audit MF1 on #1351). Everything installs into its own
# venv, C:\opt\whisper\venv, created --system-site-packages so the desk's modules (libs, numpy,
# psutil) still import from it. The installer prints the desk interpreter's `pip freeze` before and
# after and FAILS if the two differ by a single line.
#
# WHAT IT DOES, in order, printing each result:
#   1. Measures free RAM with psutil (never CIM: it has hung on the trading box). Below 6 GB free
#      nothing is installed: the trading terminal keeps its memory.
#   2. Freezes the desk interpreter's package set (before).
#   3. Creates the venv unless it exists, and installs faster-whisper 1.1.1 under a CONSTRAINTS
#      file that pins its transitive set: ctranslate2, onnxruntime, av, tokenizers and
#      huggingface_hub at versions with cp314 Windows wheels (read on PyPI 2026-11-18), and numpy
#      at EXACTLY the version the desk interpreter already has (pyproject: numpy>=2.4.6,<3; the
#      box runs 2.5.3), so the venv reuses the system numpy and installs none of its own.
#      Binary wheels only. Nothing installs at import time anywhere else:
#      desks/mt5/research/presser_stt.py reports UNMEASURED with the reason until this has run.
#   4. Downloads the CTranslate2 "small" weights once into C:\opt\whisper\models\small with the
#      venv's python and sets MACHINE env QUANT_WHISPER_MODEL_DIR. The module loads with
#      local_files_only, so no later run touches the network for the model.
#   5. Freezes the desk interpreter again and diffs: a non-empty diff stops the install, exit 5.
#   6. Registers MT5-PresserSTT on the VENV's python: `presser_stt.py --watch` every 5 minutes,
#      working directory C:\opt\quant (and cd into desks\mt5), IgnoreNew, priority 7
#      (BELOW_NORMAL), 2 h limit (a live press conference is at most ~75 minutes). Each run's first
#      log line is the venv python's version and executable (printed by `--watch` itself). Outside a press-conference window, or when
#      the window's source is not ALLOWED on terms and robots, or below the module's memory floor,
#      a run writes reports\PRESSER_STT.json and exits without loading a model.
#
# It never touches the gateway, the judge, a sleeve, an allocator fraction or a key. To undo:
#   Unregister-ScheduledTask MT5-PresserSTT -Confirm:$false; Remove-Item -Recurse C:\opt\whisper\venv
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_presser_stt_task.ps1

$ErrorActionPreference = 'Stop'
$TaskName = 'MT5-PresserSTT'
$DeskPy   = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe'
$Root     = 'C:\opt\whisper'
$Venv     = Join-Path $Root 'venv'
$VenvPy   = Join-Path $Venv 'Scripts\python.exe'
$ModelDir = Join-Path $Root 'models\small'
$Constr   = Join-Path $Root 'constraints.txt'
$Logs     = 'C:\opt\quant\desks\mt5\logs'
function Say($m) { Write-Host ("[presser-stt] " + $m) }
function Freeze { (& $DeskPy -m pip freeze --all) | Sort-Object }

$freeGb = [double](& $DeskPy -c "import psutil; print(round(psutil.virtual_memory().available/1024**3,1))")
Say ("free RAM (psutil): {0} GB" -f $freeGb)
if ($freeGb -lt 6) { Say 'below 6 GB free: nothing installed; the module stays UNMEASURED'; exit 2 }

$before = @(Freeze)
Say ("desk interpreter pip freeze BEFORE ({0} lines):" -f $before.Count)
$before | ForEach-Object { Write-Host ("  " + $_) }

$numpy = (& $DeskPy -c "import numpy; print(numpy.__version__)").Trim()
if (-not $numpy) { Say 'desk numpy unreadable: refusing to pin blind'; exit 3 }
New-Item -ItemType Directory -Force -Path $Root, $ModelDir | Out-Null
@(
  "faster-whisper==1.1.1",
  "ctranslate2==4.9.0",
  "onnxruntime==1.32.0",
  "av==19.0.2",
  "tokenizers==0.23.3",
  "huggingface_hub==2.4.0",
  "numpy==$numpy"
) | Set-Content -Path $Constr -Encoding ASCII
Say "constraints ($Constr): numpy==$numpy (the desk's own) plus the pinned transitive set"

if (-not (Test-Path $VenvPy)) {
    Say "creating venv $Venv (--system-site-packages)"
    & $DeskPy -m venv --system-site-packages $Venv
    if ($LASTEXITCODE -ne 0) { Say 'venv creation failed: the module stays UNMEASURED'; exit 3 }
}
& $VenvPy -c "import faster_whisper" 2>$null
if ($LASTEXITCODE -ne 0) {
    Say 'installing faster-whisper==1.1.1 into the venv'
    & $VenvPy -m pip install --only-binary=:all: -c $Constr 'faster-whisper==1.1.1'
    if ($LASTEXITCODE -ne 0) { Say 'pip install failed: the module stays UNMEASURED'; exit 3 }
}

if (-not (Test-Path (Join-Path $ModelDir 'model.bin'))) {
    Say "downloading model weights to $ModelDir"
    & $VenvPy -c "from huggingface_hub import snapshot_download as s; s('Systran/faster-whisper-small', local_dir=r'$ModelDir')"
    if ($LASTEXITCODE -ne 0) { Say 'model download failed: the module stays UNMEASURED'; exit 4 }
}

$after = @(Freeze)
Say ("desk interpreter pip freeze AFTER ({0} lines):" -f $after.Count)
$after | ForEach-Object { Write-Host ("  " + $_) }
$diff = @(Compare-Object -ReferenceObject $before -DifferenceObject $after)
Say ("desk interpreter freeze diff: {0} line(s)" -f $diff.Count)
$diff | ForEach-Object { Write-Host ("  {0} {1}" -f $_.SideIndicator, $_.InputObject) }
if ($diff.Count -ne 0) { Say 'the desk interpreter CHANGED: stopping before the task is registered'; exit 5 }

[Environment]::SetEnvironmentVariable('QUANT_WHISPER_MODEL_DIR', $ModelDir, 'Machine')

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -WorkingDirectory 'C:\opt\quant' -Argument (
  '/d /s /c cd /d C:\opt\quant\desks\mt5 && set QUANT_WHISPER_MODEL_DIR=' + $ModelDir + ' && ' +
  '"' + $VenvPy + '" -u -W ignore research\presser_stt.py --watch ' +
  '>> ' + $Logs + '\MT5-PresserSTT.log 2>&1')
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
             -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable -Priority 7
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -User 'Administrator' -RunLevel Highest -Force | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
Say ("$TaskName registered on $VenvPy : " + $t.State)

# Hourly box job: pull sealed transcript bundles from the data branch, open them with the
# box-only private key, and turn them into discovery rows (free OpenRouter models only).
# Unsealed text is untrusted LLM input; the extractor only PROPOSES discovery rows.
# Registers as SYSTEM (ServiceAccount, Highest): the job opens sealed bundles with the box-only
# private key, so it needs a defined principal, never an interactive-only registration that runs
# only while someone is logged on. The adoption run calls it with -IfMissing (Adopt-And-Seal 1b),
# which never touches a task that is already registered.
#   Register once:  powershell -File scripts\run_video_cells_box.ps1 -Install
#   Ensure form:    powershell -File scripts\run_video_cells_box.ps1 -IfMissing
param([string]$Repo = "C:\opt\quant", [string]$Branch = "claude/video-transcripts",
      [int]$MaxVideos = 40, [switch]$Install, [switch]$IfMissing)
$ErrorActionPreference = "Stop"
if ($IfMissing) {
  if (Get-ScheduledTask -TaskName "Quant-VideoCells" -ErrorAction SilentlyContinue) {
    Write-Host "Quant-VideoCells already registered; -IfMissing leaves it untouched"; exit 0
  }
  $Install = $true
}
if ($Install) {
  $me = $MyInvocation.MyCommand.Path
  $a = New-ScheduledTaskAction -Execute "powershell.exe" `
         -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$me`"" -WorkingDirectory $Repo
  # a DAILY trigger repeating hourly for one day (as install_independence_intake_task.ps1), never a
  # long -Once, whose repetition has expired on this box
  $at = (Get-Date).Date.AddMinutes(17)
  $t = New-ScheduledTaskTrigger -Daily -At $at
  $t.Repetition = (New-ScheduledTaskTrigger -Once -At $at -RepetitionInterval (New-TimeSpan -Hours 1) `
                     -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
  $s = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
         -ExecutionTimeLimit (New-TimeSpan -Minutes 55)
  $p = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
  Register-ScheduledTask -TaskName "Quant-VideoCells" -Action $a -Trigger $t -Settings $s -Principal $p `
         -Description "Hourly as SYSTEM: sealed YouTube transcripts -> discovery rows" -Force | Out-Null
  Write-Host "Registered Quant-VideoCells (hourly)"; exit 0
}
Set-Location $Repo
# SYSTEM has no per-user PATH: prefer the repo venv, then the py launcher, then python (as Adopt-And-Seal)
$py = Join-Path $Repo ".venv\Scripts\python.exe"; $pyArgs = @()
if (-not (Test-Path $py)) {
  if (Get-Command py -ErrorAction SilentlyContinue) { $py = "py"; $pyArgs = @("-3") } else { $py = "python" }
}
$vault = Join-Path $Repo "data\video_vault"
$sealed = Join-Path $vault "sealed"; $open = Join-Path $vault "unsealed"
New-Item -ItemType Directory -Force -Path $sealed, $open | Out-Null
# PREFLIGHT, LOUD NOT SILENT: under SYSTEM a package installed with `pip install --user` into an
# Administrator profile is invisible. If the resolved interpreter cannot import what the run needs,
# record it and exit 2 so the scheduler and desk health see the failure.
& $py @pyArgs -c "import cryptography, requests" 2>$null
if ($LASTEXITCODE -ne 0) {
  $why = "the interpreter ($py) cannot import cryptography/requests; install them into it (not --user)"
  @{ ts = (Get-Date).ToUniversalTime().ToString("s") + "Z"; state = "NO_DEPS"; why = $why } |
    ConvertTo-Json | Set-Content -Path (Join-Path $vault "LAST_RUN.json")
  Write-Host "VIDEO CELLS NO_DEPS: $why"; exit 2
}
git fetch --quiet origin $Branch
$files = git ls-tree -r --name-only "origin/$Branch" -- sealed | Where-Object { $_ -match '^sealed/[A-Za-z0-9_.-]+\.vault$' }
foreach ($f in $files) {
  $dest = Join-Path $sealed (Split-Path $f -Leaf)
  if (-not (Test-Path $dest)) {
    # Start-Process redirection writes the blob's raw bytes (no PowerShell re-encoding, no cmd parsing)
    $p = Start-Process -FilePath "git" -ArgumentList @("cat-file", "blob", "origin/${Branch}:$f") `
           -RedirectStandardOutput $dest -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -ne 0) { Remove-Item -Force $dest -ErrorAction SilentlyContinue }
  }
}
& $py @pyArgs scripts\video_transcript_vault.py open --src $sealed --dst $open
& $py @pyArgs scripts\extract_video_cells.py --mined $open --max-videos $MaxVideos
# box-side coverage proof: every enumerated video id and its status, from the PC's own ledger
& $py @pyArgs scripts\mine_channel_transcripts.py --out $open --report-only --report desks\mt5\reports\VIDEO_MINING_COVERAGE.json
$stamp = @{ ts = (Get-Date).ToUniversalTime().ToString("s") + "Z"; bundles = (Get-ChildItem $sealed -Filter *.vault).Count } | ConvertTo-Json
Set-Content -Path (Join-Path $vault "LAST_RUN.json") -Value $stamp

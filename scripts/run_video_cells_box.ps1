# Hourly box job: pull sealed transcript bundles from the data branch, open them with the
# box-only private key, and turn them into discovery rows (free OpenRouter models only).
# Unsealed text is untrusted LLM input; the extractor only PROPOSES discovery rows.
# Run as Administrator, from C:\opt\quant.
#   Register once:  powershell -File scripts\run_video_cells_box.ps1 -Install
param([string]$Repo = "C:\opt\quant", [string]$Branch = "claude/video-transcripts",
      [int]$MaxVideos = 40, [switch]$Install)
$ErrorActionPreference = "Stop"
if ($Install) {
  $me = $MyInvocation.MyCommand.Path
  $a = New-ScheduledTaskAction -Execute "powershell.exe" `
         -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$me`"" -WorkingDirectory $Repo
  $t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Hours 1)
  $s = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
         -ExecutionTimeLimit (New-TimeSpan -Minutes 55)
  Register-ScheduledTask -TaskName "Quant-VideoCells" -Action $a -Trigger $t -Settings $s `
         -Description "Hourly: sealed YouTube transcripts -> discovery rows" -Force | Out-Null
  Write-Host "Registered Quant-VideoCells (hourly)"; exit 0
}
Set-Location $Repo
$vault = Join-Path $Repo "data\video_vault"
$sealed = Join-Path $vault "sealed"; $open = Join-Path $vault "unsealed"
New-Item -ItemType Directory -Force -Path $sealed, $open | Out-Null
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
python scripts\video_transcript_vault.py open --src $sealed --dst $open
python scripts\extract_video_cells.py --mined $open --max-videos $MaxVideos
# box-side coverage proof: every enumerated video id and its status, from the PC's own ledger
python scripts\mine_channel_transcripts.py --out $open --report-only --report desks\mt5\reports\VIDEO_MINING_COVERAGE.json
$stamp = @{ ts = (Get-Date).ToUniversalTime().ToString("s") + "Z"; bundles = (Get-ChildItem $sealed -Filter *.vault).Count } | ConvertTo-Json
Set-Content -Path (Join-Path $vault "LAST_RUN.json") -Value $stamp

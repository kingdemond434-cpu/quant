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
# THE RUN MEASURES ITS OWN EXIT CODES (every git and python step below checks $LASTEXITCODE and
# records it). Under PS 5.1, 'Stop' turns a native command's redirected stderr (the preflight's
# 2>$null, a git warning) into a terminating NativeCommandError that would kill the run before it
# writes its named state, so the run body uses 'Continue'.
$ErrorActionPreference = "Continue"
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
# SYSTEM RUNS GIT ON A TREE OWNED BY BUILTIN\Administrators: plain git refuses with "dubious
# ownership" (rc 128), and a native exit code does not trip $ErrorActionPreference in PS 5.1, so a
# failed fetch used to leave $files empty and still write a healthy-looking LAST_RUN.json.
# GitBoxEnv sets safe.directory = THIS repo and prompts off for this process only (as
# sync_shadow_to_git.ps1), and every git and python step's rc is measured and recorded.
. (Join-Path $Repo "desks\mt5\scripts\GitBoxEnv.ps1")
$gitEnv = Initialize-BoxGitEnv -RepoRoot $Repo
function Write-LastRun([string]$State, [hashtable]$Extra) {
  $doc = @{ ts = (Get-Date).ToUniversalTime().ToString("s") + "Z"; state = $State;
            bundles = (Get-ChildItem $sealed -Filter *.vault -ErrorAction SilentlyContinue).Count;
            safe_directory = $gitEnv.SafeDirectory }
  foreach ($k in $Extra.Keys) { $doc[$k] = $Extra[$k] }
  $doc | ConvertTo-Json | Set-Content -Path (Join-Path $vault "LAST_RUN.json")
}
git fetch --quiet origin $Branch
$fetchRc = $LASTEXITCODE
if ($fetchRc -ne 0) { Write-LastRun "FETCH_FAILED" @{ fetch_rc = $fetchRc }; Write-Host "VIDEO CELLS FETCH_FAILED rc=$fetchRc"; exit 2 }
$listed = @(git ls-tree -r --name-only "origin/$Branch" -- sealed)
$lsRc = $LASTEXITCODE
if ($lsRc -ne 0) { Write-LastRun "LIST_FAILED" @{ fetch_rc = $fetchRc; ls_tree_rc = $lsRc }; Write-Host "VIDEO CELLS LIST_FAILED rc=$lsRc"; exit 2 }
$files = $listed | Where-Object { $_ -match '^sealed/[A-Za-z0-9_.-]+\.vault$' }
$newBundles = 0; $catFailed = 0
foreach ($f in $files) {
  $dest = Join-Path $sealed (Split-Path $f -Leaf)
  if (-not (Test-Path $dest)) {
    # Start-Process redirection writes the blob's raw bytes (no PowerShell re-encoding, no cmd parsing)
    $p = Start-Process -FilePath "git" -ArgumentList @("cat-file", "blob", "origin/${Branch}:$f") `
           -RedirectStandardOutput $dest -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -ne 0) { Remove-Item -Force $dest -ErrorAction SilentlyContinue; $catFailed++ } else { $newBundles++ }
  }
}
& $py @pyArgs scripts\video_transcript_vault.py open --src $sealed --dst $open
$openRc = $LASTEXITCODE
& $py @pyArgs scripts\extract_video_cells.py --mined $open --max-videos $MaxVideos
$extractRc = $LASTEXITCODE
# box-side coverage proof: every enumerated video id and its status, from the PC's own ledger
& $py @pyArgs scripts\mine_channel_transcripts.py --out $open --report-only --report desks\mt5\reports\VIDEO_MINING_COVERAGE.json
$coverageRc = $LASTEXITCODE
$state = if ($openRc -ne 0 -or $extractRc -ne 0 -or $coverageRc -ne 0 -or $catFailed -gt 0) { "STEP_FAILED" } else { "OK" }
Write-LastRun $state @{ fetch_rc = $fetchRc; ls_tree_rc = $lsRc; listed_bundles = @($files).Count;
                        new_bundles = $newBundles; cat_file_failed = $catFailed; open_rc = $openRc;
                        extract_rc = $extractRc; coverage_rc = $coverageRc }
if ($state -ne "OK") { exit 2 }

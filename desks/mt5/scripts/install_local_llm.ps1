# INSTALL THE LAB'S LOCAL MODEL: Ollama, one quantized ~14B model on capped cores, at idle priority
# (2026-10-13; the 14B model, the thread cap and the core pinning 2026-10-14).
#
# WHY. The free cloud rungs run out every day; the local rung never does. `libs/ops/free_chain.py`
# already calls any OpenAI-compatible server named in QUANT_LOCAL_LLM_URLS, and only while the
# box has spare CPU (under 35%); `demote_local_servers` drops the server to the idle class on
# every call. What was missing is the server. This file installs it, once, idempotently.
#
# WHAT IT DOES, in order, printing each result:
#   1. Measures this machine with psutil (never CIM: it has hung on the trading box). Picks the
#      model from MEASURED free RAM: qwen2.5:14b-instruct-q4_K_M (~9 GB) at >= 24 GB free,
#      qwen2.5:7b-instruct-q4_K_M (~4.7 GB) at >= 12 GB, qwen2.5:3b-instruct at >= 6 GB. 70B is
#      not offered: on CPU it is too slow to be worth a call.
#   2. Installs Ollama (winget, else the official installer) unless `ollama` is already on PATH,
#      and stops the tray app so exactly one server runs -- ours.
#   3. Sets MACHINE environment (the desk's tasks run as SYSTEM): OLLAMA_HOST=127.0.0.1:11434
#      (loopback only), OLLAMA_MODELS=C:\opt\ollama\models (shared by the pull and the server),
#      OLLAMA_NUM_PARALLEL=1, OLLAMA_MAX_LOADED_MODELS=1, OLLAMA_KEEP_ALIVE=10m, and
#      QUANT_LOCAL_LLM_URLS=http://127.0.0.1:11434/v1.
#   4. Registers MT5-LocalLLM: `ollama serve` at startup as LOCAL SERVICE, task priority 10 (the lowest
#      the scheduler has), restarted on failure, then starts it.
#   5. Pulls the chosen model, creates `quant-lab` from it with num_thread = cores/4 (min 2), pins
#      the server to the last cores at Idle, sets QUANT_LOCAL_LLM_MODEL=quant-lab (machine), and
#      runs one tiny completion through free_chain and reads llm_seat's local seat.
#
# INTEGRITY (audit must-fix 9, 2026-10-13):
#   * Ollama is installed at a PINNED version. The first run pins winget's current version in
#     C:\opt\ollama\install.lock.json; later runs install exactly that one. Pass -OllamaVersion
#     to choose the pin yourself.
#   * Every binary is checked with Get-AuthenticodeSignature before it runs: the installer
#     fallback before it is started, and ollama.exe after it is installed. A signature that is
#     not Valid, or not signed by Ollama, stops the script.
#   * Each model is pinned by its digest on first pull (the same lock file). A later run whose
#     pull resolves to a different digest stops instead of serving it.
#   * C:\opt\ollama is locked to SYSTEM and Administrators (full), LOCAL SERVICE read+execute on
#     bin and modify on models. The server runs as LOCAL SERVICE, not SYSTEM.
#   * Below 6 GB free RAM nothing is pulled: the trading terminal keeps its memory.
#
# It never touches the gateway, the judge, a sleeve or a key. To undo:
#   Unregister-ScheduledTask MT5-LocalLLM -Confirm:$false; winget uninstall Ollama.Ollama
#   'QUANT_LOCAL_LLM_URLS','QUANT_LOCAL_LLM_MODEL','QUANT_LOCAL_LLM_THREADS' | ForEach-Object {
#       [Environment]::SetEnvironmentVariable($_, $null, 'Machine') }
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_local_llm.ps1

param([string]$OllamaVersion = '')
$ErrorActionPreference = 'Stop'
$TaskName = 'MT5-LocalLLM'
$Repo     = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Models   = 'C:\opt\ollama\models'
$Url      = 'http://127.0.0.1:11434/v1'

function Say($m) { Write-Host ("[local-llm] " + $m) }
$Root = 'C:\opt\ollama'
$Lock = Join-Path $Root 'install.lock.json'
New-Item -ItemType Directory -Force -Path $Root | Out-Null
$lockDoc = @{ ollama_version = ''; models = @{} }
if (Test-Path $Lock) {
    $raw = Get-Content $Lock -Raw | ConvertFrom-Json
    $lockDoc.ollama_version = [string]$raw.ollama_version
    if ($raw.models) { $raw.models.PSObject.Properties | ForEach-Object { $lockDoc.models[$_.Name] = [string]$_.Value } }
}
function Save-Lock { $lockDoc | ConvertTo-Json -Depth 4 | Set-Content -Path $Lock -Encoding UTF8 }
function Assert-Signed($path) {
    $sig = Get-AuthenticodeSignature -FilePath $path
    $who = if ($sig.SignerCertificate) { $sig.SignerCertificate.Subject } else { '' }
    if ($sig.Status -ne 'Valid' -or $who -notmatch 'Ollama') {
        throw "refusing ${path}: signature $($sig.Status), signer '$who' (must be Valid and Ollama)"
    }
    Say "signature ok: $path ($who)"
}

# 1. Measure, never assume (CLAUDE.md: the two boxes differ twelve-fold).
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "python not on PATH: cannot measure memory with psutil" }
$freeGb = [double](& $py -c "import psutil; print(round(psutil.virtual_memory().available / 1024**3, 1))")
$cores  = [int](& $py -c "import psutil; print(psutil.cpu_count(logical=True))")
Say "measured: $freeGb GB free RAM, $cores logical cores"
# A ~14B model at 4-bit is ~9 GB resident; 24 GB free leaves the terminal and the gateway 15.
if ($freeGb -ge 24) {
    $pull = @('qwen2.5:14b-instruct-q4_K_M')
} elseif ($freeGb -ge 12) {
    $pull = @('qwen2.5:7b-instruct-q4_K_M')
} elseif ($freeGb -ge 6) {
    $pull = @('qwen2.5:3b-instruct')
} else {
    Say "only $freeGb GB free: below the 6 GB floor, nothing is installed (the terminal keeps it)"
    exit 0
}
Say ("models chosen from measured RAM: " + ($pull -join ', '))

# 2. Install Ollama once.
$ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
if (-not $ollama) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $ver = if ($OllamaVersion) { $OllamaVersion } elseif ($lockDoc.ollama_version) { $lockDoc.ollama_version } else {
            $show = winget show --id Ollama.Ollama -e --accept-source-agreements | Out-String
            if ($show -match '(?m)^Version:\s*(\S+)') { $Matches[1] } else { throw "winget did not report a version to pin" }
        }
        Say "installing Ollama $ver with winget (pinned)"
        winget install --id Ollama.Ollama -e --version $ver --silent --accept-package-agreements --accept-source-agreements | Out-Host
        $lockDoc.ollama_version = $ver; Save-Lock
    } else {
        Say "installing Ollama from the official installer"
        $exe = Join-Path $env:TEMP 'OllamaSetup.exe'
        Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile $exe -UseBasicParsing
        Assert-Signed $exe
        Start-Process -FilePath $exe -ArgumentList '/VERYSILENT', '/NORESTART' -Wait
    }
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
    $ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollama) {
        $guess = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
        if (Test-Path $guess) { $ollama = $guess } else { throw "ollama.exe not found after install" }
    }
}
Say "ollama: $ollama"
# Copy the binary somewhere SYSTEM can read (a per-user install lives under one user's profile).
$bin = 'C:\opt\ollama\bin'
New-Item -ItemType Directory -Force -Path $bin, $Models | Out-Null
$srcDir = Split-Path $ollama
Copy-Item -Path (Join-Path $srcDir '*') -Destination $bin -Recurse -Force
$ollama = Join-Path $bin 'ollama.exe'
Assert-Signed $ollama
# Lock the tree: only SYSTEM and Administrators may write; the server reads bin and writes models.
& icacls $Root /inheritance:r /grant:r 'SYSTEM:(OI)(CI)F' 'Administrators:(OI)(CI)F' | Out-Null
& icacls $bin /grant:r '*S-1-5-19:(OI)(CI)RX' | Out-Null
& icacls $Models /grant:r '*S-1-5-19:(OI)(CI)M' | Out-Null
Say "ACL locked on $Root (LOCAL SERVICE: read on bin, modify on models)"
Get-Process -Name 'ollama app', 'ollama' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$startup = Join-Path ([Environment]::GetFolderPath('Startup')) 'Ollama.lnk'
if (Test-Path $startup) { Remove-Item $startup -Force; Say "removed the tray app's startup link" }

# 3. Machine environment.
$vars = @{
    'OLLAMA_HOST' = '127.0.0.1:11434'; 'OLLAMA_MODELS' = $Models; 'OLLAMA_NUM_PARALLEL' = '1';
    'OLLAMA_MAX_LOADED_MODELS' = '1'; 'OLLAMA_KEEP_ALIVE' = '10m'; 'QUANT_LOCAL_LLM_URLS' = $Url
}
foreach ($k in $vars.Keys) {
    [Environment]::SetEnvironmentVariable($k, $vars[$k], 'Machine')
    Set-Item -Path "Env:$k" -Value $vars[$k]
    Say "set $k (machine)"
}

# 4. The server task: LOCAL SERVICE (no admin, no user profile), at startup, lowest priority.
$action    = New-ScheduledTaskAction -Execute $ollama -Argument 'serve'
$trigger   = New-ScheduledTaskTrigger -AtStartup
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -Priority 10
$principal = New-ScheduledTaskPrincipal -UserId 'NT AUTHORITY\LOCALSERVICE' -LogonType ServiceAccount -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5
Get-Process -Name 'ollama' -ErrorAction SilentlyContinue | ForEach-Object {
    $_.PriorityClass = 'Idle'; Say ("server pid {0} set to Idle priority" -f $_.Id)
}

# 5. Pull, then serve it as a CAPPED model: `quant-lab` is the pulled weights with num_thread
#    fixed at a quarter of the logical cores (at least 2), so a long generation can never take
#    the cores the terminal, the gateway and the gauntlet need. The server process is also pinned
#    to the LAST $threads cores (its runner children inherit the mask) at Idle priority.
$threads = [Math]::Max(2, [int][Math]::Floor($cores / 4))
$Capped  = 'quant-lab'
foreach ($m in $pull) {
    Say "pulling $m (several GB; this is the slow step)"
    & $ollama pull $m | Out-Host
    $row = (& $ollama list | Select-String -SimpleMatch $m | Select-Object -First 1)
    $digest = if ($row) { ($row.ToString() -split '\s+')[1] } else { '' }
    if (-not $digest) { throw "no digest listed for $m after the pull" }
    $pinned = $lockDoc.models[$m]
    if ($pinned -and $pinned -ne $digest) {
        & $ollama rm $m | Out-Null
        throw "$m resolved to digest $digest, pinned ${pinned}: removed, not served. Delete its lock entry to accept a new build."
    }
    $lockDoc.models[$m] = $digest; Save-Lock
    Say "$m digest $digest (pinned)"
}
$modelfile = Join-Path $Root 'quant-lab.Modelfile'
Set-Content -Path $modelfile -Encoding ASCII -Value @("FROM $($pull[0])", "PARAMETER num_thread $threads")
& $ollama create $Capped -f $modelfile | Out-Host
if (-not (& $ollama list | Select-String -SimpleMatch $Capped)) { throw "ollama create $Capped failed" }
Say "$Capped = $($pull[0]) capped at $threads of $cores threads"
$mask = [long]0
for ($i = $cores - $threads; $i -lt $cores; $i++) { $mask = $mask -bor ([long]1 -shl $i) }
Get-Process -Name 'ollama' -ErrorAction SilentlyContinue | ForEach-Object {
    $_.ProcessorAffinity = [IntPtr]$mask; $_.PriorityClass = 'Idle'
    Say ("server pid {0} pinned to the last {1} cores, Idle" -f $_.Id, $threads)
}
[Environment]::SetEnvironmentVariable('QUANT_LOCAL_LLM_MODEL', $Capped, 'Machine')
$env:QUANT_LOCAL_LLM_MODEL = $Capped
# free_chain re-applies the same pinning to the server before every local call, so it survives a
# reboot (a scheduled task cannot carry an affinity mask itself).
[Environment]::SetEnvironmentVariable('QUANT_LOCAL_LLM_THREADS', [string]$threads, 'Machine')
$env:QUANT_LOCAL_LLM_THREADS = [string]$threads
Say "set QUANT_LOCAL_LLM_MODEL=$Capped (machine): llm_seat and free_chain call only the capped model"
$probe = @'
import json, os, sys
sys.path[:0] = [r"REPO", r"REPO\desks\mt5"]
os.environ["QUANT_LOCAL_LLM_GUARD"] = "0"   # this one probe only; the lab keeps the CPU guard
from libs.ops import free_chain
st = free_chain.status()
print(json.dumps({k: st.get(k) for k in ("verdict", "local_models_that_fit")}, default=str)[:800])
r = free_chain.chat("Reply with the single word ok.", "ok?", max_tokens=5, temperature=0,
                    skip=tuple(p.name for p in free_chain.providers() if p.tier != "local"))
print("local rung answered:", r.provider, r.model, repr(r.text[:20]))
from libs.ops import llm_seat
dark = llm_seat.local_dark()
seat = next((s for s in llm_seat.seats() if llm_seat.is_local(s)), None)
model, err = llm_seat.discover_model(seat) if seat else ("", dark)
print("llm_seat local seat:", f"LIT on {model}" if model else f"DARK: {err}")
'@
$probe = $probe.Replace('REPO', $Repo)
$tmp = Join-Path $env:TEMP 'local_llm_probe.py'
Set-Content -Path $tmp -Value $probe -Encoding UTF8
& $py $tmp
Say "done. The lab leg and the deepening worker pick QUANT_LOCAL_LLM_URLS up on their next start."

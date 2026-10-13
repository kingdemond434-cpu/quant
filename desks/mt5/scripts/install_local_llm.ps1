# INSTALL THE LAB'S LOCAL MODEL: Ollama, one quantized 7-8B model, at idle priority (2026-10-13).
#
# WHY. The free cloud rungs run out every day; the local rung never does. `libs/ops/free_chain.py`
# already calls any OpenAI-compatible server named in QUANT_LOCAL_LLM_URLS, and only while the
# box has spare CPU (under 35%); `demote_local_servers` drops the server to the idle class on
# every call. What was missing is the server. This file installs it, once, idempotently.
#
# WHAT IT DOES, in order, printing each result:
#   1. Measures this machine with psutil (never CIM: it has hung on the trading box). Picks the
#      model from MEASURED free RAM: qwen2.5:7b-instruct-q4_K_M (~4.7 GB) at >= 12 GB free, and
#      llama3.1:8b-instruct-q4_K_M as a second, independent model at >= 24 GB free; below
#      12 GB, qwen2.5:3b-instruct. 70B is not offered: on CPU it is too slow to be worth a call.
#   2. Installs Ollama (winget, else the official installer) unless `ollama` is already on PATH,
#      and stops the tray app so exactly one server runs -- ours.
#   3. Sets MACHINE environment (the desk's tasks run as SYSTEM): OLLAMA_HOST=127.0.0.1:11434
#      (loopback only), OLLAMA_MODELS=C:\opt\ollama\models (shared by the pull and the server),
#      OLLAMA_NUM_PARALLEL=1, OLLAMA_MAX_LOADED_MODELS=1, OLLAMA_KEEP_ALIVE=10m, and
#      QUANT_LOCAL_LLM_URLS=http://127.0.0.1:11434/v1.
#   4. Registers MT5-LocalLLM: `ollama serve` at startup as SYSTEM, task priority 10 (the lowest
#      the scheduler has), restarted on failure, then starts it.
#   5. Pulls the chosen model(s) and runs one tiny completion through free_chain.status().
#
# It never touches the gateway, the judge, a sleeve or a key. To undo:
#   Unregister-ScheduledTask MT5-LocalLLM -Confirm:$false; winget uninstall Ollama.Ollama
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_local_llm.ps1

$ErrorActionPreference = 'Stop'
$TaskName = 'MT5-LocalLLM'
$Repo     = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Models   = 'C:\opt\ollama\models'
$Url      = 'http://127.0.0.1:11434/v1'

function Say($m) { Write-Host ("[local-llm] " + $m) }

# 1. Measure, never assume (CLAUDE.md: the two boxes differ twelve-fold).
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "python not on PATH: cannot measure memory with psutil" }
$freeGb = [double](& $py -c "import psutil; print(round(psutil.virtual_memory().available / 1024**3, 1))")
$cores  = [int](& $py -c "import psutil; print(psutil.cpu_count(logical=True))")
Say "measured: $freeGb GB free RAM, $cores logical cores"
if ($freeGb -ge 24) {
    $pull = @('qwen2.5:7b-instruct-q4_K_M', 'llama3.1:8b-instruct-q4_K_M')
} elseif ($freeGb -ge 12) {
    $pull = @('qwen2.5:7b-instruct-q4_K_M')
} else {
    $pull = @('qwen2.5:3b-instruct')
}
Say ("models chosen from measured RAM: " + ($pull -join ', '))

# 2. Install Ollama once.
$ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
if (-not $ollama) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Say "installing Ollama with winget"
        winget install --id Ollama.Ollama -e --silent --accept-package-agreements --accept-source-agreements | Out-Host
    } else {
        Say "installing Ollama from the official installer"
        $exe = Join-Path $env:TEMP 'OllamaSetup.exe'
        Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile $exe -UseBasicParsing
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

# 4. The server task: SYSTEM, at startup, lowest priority, restarted if it dies.
$action    = New-ScheduledTaskAction -Execute $ollama -Argument 'serve'
$trigger   = New-ScheduledTaskTrigger -AtStartup
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -Priority 10
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5
Get-Process -Name 'ollama' -ErrorAction SilentlyContinue | ForEach-Object {
    $_.PriorityClass = 'Idle'; Say ("server pid {0} set to Idle priority" -f $_.Id)
}

# 5. Pull and prove one completion.
foreach ($m in $pull) {
    Say "pulling $m (several GB; this is the slow step)"
    & $ollama pull $m | Out-Host
}
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
'@
$probe = $probe.Replace('REPO', $Repo)
$tmp = Join-Path $env:TEMP 'local_llm_probe.py'
Set-Content -Path $tmp -Value $probe -Encoding UTF8
& $py $tmp
Say "done. The lab leg and the deepening worker pick QUANT_LOCAL_LLM_URLS up on their next start."

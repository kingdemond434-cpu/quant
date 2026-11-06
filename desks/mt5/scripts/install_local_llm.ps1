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
#   4. Registers MT5-LocalLLM: `ollama serve` at startup as LOCAL SERVICE, task priority 10 (the lowest
#      the scheduler has), restarted on failure, then starts it.
#   5. Pulls the chosen model(s) and runs one tiny completion through free_chain.status().
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
$lockDoc = @{ ollama_version = ''; signer_thumbprint = ''; models = @{} }
if (Test-Path $Lock) {
    $raw = Get-Content $Lock -Raw | ConvertFrom-Json
    $lockDoc.ollama_version = [string]$raw.ollama_version
    $lockDoc.signer_thumbprint = [string]$raw.signer_thumbprint
    if ($raw.models) { $raw.models.PSObject.Properties | ForEach-Object { $lockDoc.models[$_.Name] = [string]$_.Value } }
}
function Save-Lock { $lockDoc | ConvertTo-Json -Depth 4 | Set-Content -Path $Lock -Encoding UTF8 }
function Assert-Signed($path) {
    # The signer is PINNED BY THUMBPRINT (audit of 538cb964, SF6), not matched as a subject
    # substring: any certificate whose subject merely contains "Ollama" used to pass. The first
    # valid signature is recorded in the lock (trust on first use, printed so a human can check
    # it); every later binary must carry exactly that certificate.
    $sig = Get-AuthenticodeSignature -FilePath $path
    $cert = $sig.SignerCertificate
    $who = if ($cert) { $cert.Subject } else { '' }
    $thumb = if ($cert) { $cert.Thumbprint } else { '' }
    if ($sig.Status -ne 'Valid' -or $who -notmatch '(^|,\s*)O=Ollama') {
        throw "refusing ${path}: signature $($sig.Status), signer '$who' (must be Valid, O=Ollama)"
    }
    if ($lockDoc.signer_thumbprint -and $lockDoc.signer_thumbprint -ne $thumb) {
        throw "refusing ${path}: signer thumbprint $thumb, pinned $($lockDoc.signer_thumbprint). Delete signer_thumbprint from $Lock to accept a new certificate."
    }
    if (-not $lockDoc.signer_thumbprint) {
        $lockDoc.signer_thumbprint = $thumb; Save-Lock
        Say "signer pinned on first use: $thumb ($who, issuer $($cert.Issuer))"
    }
    Say "signature ok: $path ($who, $thumb)"
}
function Invoke-Icacls {
    # icacls reports failure only in its exit code; an unchecked failure left the tree writable
    # while the script said "ACL locked" (audit of 538cb964, SF6).
    & icacls @args | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls $($args -join ' ') failed with exit code $LASTEXITCODE" }
}

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
# STOP THE SERVER BEFORE COPYING OVER ITS BINARY (audit of 538cb964, SF5): on a re-run the copy
# hit "file in use" on the running ollama.exe and the script threw half way through.
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
}
Get-Process -Name 'ollama app', 'ollama' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
if ((Resolve-Path $srcDir).Path -ne (Resolve-Path $bin).Path) {
    Copy-Item -Path (Join-Path $srcDir '*') -Destination $bin -Recurse -Force
}
$ollama = Join-Path $bin 'ollama.exe'
Assert-Signed $ollama
# Lock the tree: only SYSTEM and Administrators may write; the server reads bin and writes models.
Invoke-Icacls $Root /inheritance:r /grant:r 'SYSTEM:(OI)(CI)F' 'Administrators:(OI)(CI)F'
Invoke-Icacls $bin /grant:r '*S-1-5-19:(OI)(CI)RX'
Invoke-Icacls $Models /grant:r '*S-1-5-19:(OI)(CI)M'
Say "ACL locked on $Root (LOCAL SERVICE: read on bin, modify on models)"
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
# BOUNDED CORES (audit of 538cb964, SF7): inference would otherwise spread across every core next
# to the live terminal. The server is pinned to the TOP quarter of the logical cores (at least 2;
# QUANT_LOCAL_LLM_CORES overrides), through `start /affinity`, which `/wait` keeps attached so the
# task's restart-on-failure still sees the server exit.
$llmCores = [int]([Environment]::GetEnvironmentVariable('QUANT_LOCAL_LLM_CORES', 'Machine'))
if ($llmCores -le 0) { $llmCores = [Math]::Max(2, [Math]::Floor($cores / 4)) }
$llmCores = [Math]::Min($llmCores, $cores)
$mask = ([int64]1 -shl $llmCores) - 1
$mask = $mask -shl ($cores - $llmCores)
$maskHex = '{0:X}' -f $mask
Say "server pinned to $llmCores of $cores logical cores (affinity 0x$maskHex)"
$action    = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\cmd.exe" `
    -Argument ('/c start "" /wait /low /affinity {0} "{1}" serve' -f $maskHex, $ollama)
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

# 5. Pull and prove one completion.
function Get-Digest($m) {
    $row = (& $ollama list | Select-String -SimpleMatch $m | Select-Object -First 1)
    if ($row) { ($row.ToString() -split '\s+')[1] } else { '' }
}
foreach ($m in $pull) {
    $pinned = $lockDoc.models[$m]
    # A PINNED MODEL ALREADY HERE IS NEVER RE-PULLED (audit of 538cb964, SF5): the pull ran before
    # the digest check, so a tag moved upstream replaced the pinned build and the check then
    # removed the model altogether. Now a present pinned build is kept as it is.
    if ($pinned -and (Get-Digest $m) -eq $pinned) {
        Say "$m digest $pinned already present and pinned: not pulled"
        continue
    }
    Say "pulling $m (several GB; this is the slow step)"
    & $ollama pull $m | Out-Host
    $digest = Get-Digest $m
    if (-not $digest) { throw "no digest listed for $m after the pull" }
    if ($pinned -and $pinned -ne $digest) {
        & $ollama rm $m | Out-Null
        throw "$m resolved to digest $digest, pinned ${pinned}: removed, not served. Delete its lock entry to accept a new build."
    }
    $lockDoc.models[$m] = $digest; Save-Lock
    Say "$m digest $digest (pinned)"
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

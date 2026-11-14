<#
.SYNOPSIS
    Repair a Claude Code settings file that does not parse -- run by a PERSON, never by an AI.

.DESCRIPTION
    THE FAILURE (2026-11-13). The box's C:\Users\Administrator\.claude\settings.json lost its
    leading "{". Claude Code could not parse it, so the permission mode set there never loaded and
    every Remote Control session kept prompting. ops\claude_settings_health.py (read-only, wired
    into ops\process_health.py) now reports such a file as BROKEN with an exact diagnosis.

    WHY A PERSON RUNS THIS. An AI never edits its own permission settings (project hard rule): a
    session that could rewrite the file that limits it would have no limit. So this script refuses
    to run inside a Claude Code session (CLAUDECODE / CLAUDE_CODE_ENTRYPOINT set), in a
    non-interactive process, or in session 0 (a scheduled task), and it asks the person at the
    keyboard to type REPAIR. These checks are a guard rail, not a lock (a process can unset an
    environment variable or pipe the word in); what keeps it a person's tool is that it is
    referenced by no scheduled task, installer or box action, and a test fails if one appears.

    WHAT IT CHANGES. Only the one diagnosed repair, never a key or a value:
        UTF8_BOM                 strip a leading byte-order mark
        MISSING_LEADING_BRACE    put back the "{" at the start
        MISSING_TRAILING_BRACE   put back the "}" at the end
    Anything else is reported and left alone (open the file in Notepad). The original is kept as
    <file>.bak-<UTC stamp>; the result is written as UTF-8 without a BOM and re-parsed before the
    script says it worked. A file that already parses is never touched.

    AFTER IT. A permission mode is fixed when a session starts, so restart Remote Control: in the
    bridge's minimized console press Ctrl+C (the watchdog starts the server again within 10 s),
    or reboot. Then `python ops\claude_settings_health.py` reads OK.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File ops\bridge\Repair-ClaudeSettings.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File ops\bridge\Repair-ClaudeSettings.ps1 -Path C:\Users\Administrator\.claude\settings.json
#>
[CmdletBinding()]
param([string] $Path = (Join-Path $env:USERPROFILE ".claude\settings.json"))

$ErrorActionPreference = "Stop"

# ---- a person, at a keyboard, outside any Claude Code session --------------------------------
if ($env:CLAUDECODE -or $env:CLAUDE_CODE_ENTRYPOINT) {
    Write-Output "REFUSED: this is running inside a Claude Code session. An AI never edits its own permission settings; a person runs this from their own PowerShell window."
    exit 3
}
if (-not [Environment]::UserInteractive -or [System.Diagnostics.Process]::GetCurrentProcess().SessionId -eq 0) {
    Write-Output "REFUSED: not an interactive desktop session (scheduled task or service). A person runs this."
    exit 3
}

# ---- only a Claude Code settings file ----------------------------------------------------------
$full = [IO.Path]::GetFullPath($Path)
$leaf = Split-Path -Leaf $full
$dirLeaf = Split-Path -Leaf (Split-Path -Parent $full)
if ($leaf -notin @("settings.json", "settings.local.json") -or $dirLeaf -ne ".claude") {
    Write-Output "REFUSED: $full is not a .claude\settings.json or .claude\settings.local.json"
    exit 2
}
if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { Write-Output "NOTHING TO DO: $full does not exist"; exit 0 }

function Test-JsonObject([string] $text) {
    try { $o = $text | ConvertFrom-Json -ErrorAction Stop; return ($o -is [System.Management.Automation.PSCustomObject]) }
    catch { return $false }
}

$bytes = [IO.File]::ReadAllBytes($full)
$text = [Text.Encoding]::UTF8.GetString($bytes)
$hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
if ($hasBom) { $text = $text.Substring(1) }

if (-not $hasBom -and (Test-JsonObject $text)) { Write-Output "OK: $full already parses; nothing changed"; exit 0 }

$diagnosis = $null
$fixed = $null
$body = $text.Trim()
if ($hasBom -and (Test-JsonObject $text)) { $diagnosis = "UTF8_BOM"; $fixed = $text }
elseif (-not $body.StartsWith("{") -and (Test-JsonObject ("{" + $body))) { $diagnosis = "MISSING_LEADING_BRACE"; $fixed = "{" + $body + [Environment]::NewLine }
elseif (-not $body.EndsWith("}") -and (Test-JsonObject ($body + "}"))) { $diagnosis = "MISSING_TRAILING_BRACE"; $fixed = $body + [Environment]::NewLine + "}" + [Environment]::NewLine }

if (-not $diagnosis) {
    Write-Output "UNKNOWN: $full does not parse and none of the three exact repairs fixes it. Open it in Notepad (it was not changed)."
    exit 1
}

Write-Output "File:      $full"
Write-Output "Diagnosis: $diagnosis"
Write-Output "Change:    only that; every key and value stays as it is. A backup is kept."
$answer = Read-Host "Type REPAIR to apply"
if ($answer -cne "REPAIR") { Write-Output "Not applied; nothing changed."; exit 1 }

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$backup = "$full.bak-$stamp"
Copy-Item -LiteralPath $full -Destination $backup
[IO.File]::WriteAllText($full, $fixed, (New-Object System.Text.UTF8Encoding($false)))

$check = [IO.File]::ReadAllText($full)
if (-not (Test-JsonObject $check)) {
    Copy-Item -LiteralPath $backup -Destination $full -Force
    Write-Output "FAILED: the repaired file did not parse; the original was put back (backup $backup)."
    exit 1
}
Write-Output "REPAIRED ($diagnosis). Backup: $backup"
Write-Output "Next: restart Remote Control (Ctrl+C in the bridge's console; the watchdog restarts it in ~10 s) so new sessions load the setting."
exit 0

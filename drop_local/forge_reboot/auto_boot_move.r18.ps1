# (r18, 2026-11-26 17:33Z) D is now decided by the current boot's own trust checker: ORDINARY/TIGHTEN move on CLEAR alone,
#   everything else needs $F\owner_approvals\<sha>.txt in an admin-only folder outside the drop (the owner's act; no hour,
#   no silence). See D0/D1 below.
# AUTOMATIC BOOT MOVE (zuck 2026-11-26 12:38Z: "Remove that safety room ... Root ... If it needs me").
# Runs as SYSTEM from C:\ProgramData\QuantBox\forge\auto_boot_move.ps1 (admin-owned; the drop cannot change it),
# task QuantForge-BootMove every 15 min, IgnoreNew. It moves the QuantForge-Loop boot ONLY when ALL hold:
#   A. the drop checkout holds forge_reboot\boot-<name>.bundle + .bundle.sha256 + boot-<name>.verdict.json, the bundle's
#      sha256 matches, the bundle carries exactly one head, and the verdict line is "AUDIT CLEAR <that exact 40-hex sha>";
#   B. no verdict anywhere in the drop says "AUDIT HOLD <that sha>" (a later HOLD always beats a CLEAR);
#   C. the new head is a strict descendant of the current boot (fast-forward only; never sideways or back);
#   D. old..new (--no-renames) touches NO trust-set path (TRUST_SET.json itself, any `files` glob or `symbols` file of T at the old OR
#      the new boot). A change inside T still needs the owner (AUTHORIZE TRUST / his box session), exactly as on the forge;
#   E. the same sha has not failed an attempt in the last 6 h (journal), so a broken candidate cannot end passes in a loop.
#   (r3) A boot that touches T otherwise passes D only via the 1 h silent veto (D2 below); one that could narrow T
#        (TRUST_SET.json, trust_check.py, protect.py, ops/release/authority/*) always needs the owner (D1).
#   (r11) TRUST MODEL, chosen by zuck 2026-11-26 13:38:32Z ("A", project chat message
#        cmsg_012XFUfE12Rvggnu86fDb8prRXEpU4qT6Y8aXwKi6TWAYz, in reply to the coordinator's 13:38:20Z message
#        cmsg_012XFUfE12Rvggnu86fDb8prXEUnUxFVZaHTcXKe1MQHLe, which told him "A means you're trusting Claude to police
#        itself on exactly that code"). He declined any app or step (13:35Z "its fr u to monitor"). So the D2 clock starts
#        on the drop file forge_reboot\announced\<sha>.txt, which the Autonomy seat writes only after the coordinator
#        posted the one-line notice to zuck in project chat. THE BOX CANNOT VERIFY THAT POST: anyone who can push the
#        drop can start the hour on a T change zuck never saw. The safeguard is the coordinator's chat post (Claude
#        discipline), not the box. D1 (anything that could narrow T) still needs the owner.
# (r17, Audit HOLD r16 15:46Z) recovery by stage: verified write stands; started write restores .premove first;
#   boot-src is staging only (back to Old on any non-moved exit); QuantForge-CI restarted if this run stopped it.
# (r16, 11-26 after the 15:41Z failed move) every fallible step before ending a pass; known-path lock check only;
# error line first with position; recovery (boot-src back, loop restarted) on any non-moved exit after an end.
# Then it runs move_boot.r11 steps -1..3 unchanged in substance (end a >30 min old-boot pass, object fetch, byte-exact
# sha-only rewrite of loop.json and run_loop.cmd, 61-ish watched hashes + 3 task definitions unchanged, rollback on any
# mismatch). It never touches the trust dir, ROOT_PIN, signers, tokens, task definitions, AdoptRelease or the live tree.
# Every attempt (moved / refused / rolled back) is one JSON line in C:\ProgramData\QuantBox\forge\boot_moves.jsonl
# plus a full log under C:\opt\quant\data\evidence_backups\forge_reboot_auto_<utc>_<sha9>\move_boot.log.
$ErrorActionPreference = 'Continue'   # selection phase: git stderr must not throw under PS 5.1; 'Stop' from the move on
$F = 'C:\ProgramData\QuantBox\forge'
$Src = "$F\boot-src"
$Journal = "$F\boot_moves.jsonl"
$L1 = [Text.Encoding]::GetEncoding(28591)   # Latin-1: one char per byte, every byte round-trips
$U8 = [Text.UTF8Encoding]::new($false)
$G = @('-c', 'safe.directory=*', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=NUL')   # (r5) no repo-config code path as SYSTEM
function Get-Sha256Hex([string] $p) { (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash }
function Journal([hashtable] $row) {
    $row['at'] = (Get-Date).ToUniversalTime().ToString('o')
    [IO.File]::AppendAllText($Journal, (([pscustomobject]$row) | ConvertTo-Json -Compress -Depth 8) + "`n", $U8)
}
function Recent-Failure([string] $sha) {
    if (-not (Test-Path -LiteralPath $Journal)) { return $false }
    $cut = (Get-Date).ToUniversalTime().AddHours(-6)
    foreach ($ln in [IO.File]::ReadAllLines($Journal, $U8)) {
        try { $r = $ln | ConvertFrom-Json } catch { continue }
        if ($r.new -eq $sha -and $r.result -in @('rolled_back', 'stopped_after_end', 'error') -and [datetimeoffset]::Parse("$($r.at)").UtcDateTime -gt $cut) { return $true }   # (r2) UTC both sides
    }
    return $false
}
$AdminSids = @('S-1-5-32-544', 'S-1-5-18')
function Test-AdminOnly([string] $p) {   # (r7) owner and every ACE Administrators/SYSTEM, none inherited unless the
    try {                                # parent is itself proven (files in the guard dir); any error = not proven
        $acl = Get-Acl -LiteralPath $p
        $own = (New-Object Security.Principal.NTAccount($acl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
        $aces = @($acl.Access)
        return ($AdminSids -contains $own) -and $aces.Count -gt 0 -and -not ($aces | Where-Object {
            $_.IsInherited -or ($AdminSids -notcontains $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value) })
    } catch { return $false }
}
function T-Globs([string] $rev) {
    $raw = & git @G -C $Src show "${rev}:ops/box_git/TRUST_SET.json" 2>$null
    if ($LASTEXITCODE) { return $null }
    $t = ($raw -join "`n") | ConvertFrom-Json
    $sym = @(); if ($t.symbols) { $sym = @($t.symbols.PSObject.Properties.Name) }   # (r2) T's symbol-pinned files too
    return @('ops/box_git/TRUST_SET.json') + @($t.files) + $sym
}

# --- (r3) BOX GUARDIAN HOOK: boot code may carry ops/box_git/box_guardian.ps1 (disk, delivery latency, auto-repairs).
# It runs as SYSTEM, so it runs ONLY when T at the current boot lists it (any change to it is then a ROOT change: the
# veto path above, or the owner). Child process, 10 min cap, its failure never stops the boot move below.
$GuardRel = 'ops/box_git/box_guardian.ps1'
$bootNow = "$((Get-Content -Raw "$F\loop.json" | ConvertFrom-Json).boot)".Trim()
$gNow = T-Globs $bootNow
# (r5, Audit MF2) Never run the boot-src working file: the boot's committed blob is written to an admin-only copy
# and that copy runs (no stat-cache trust, no edit window between check and start).
# (r7, Audit MF 12:58Z) The copy lives in $F\guard, which the installer creates fresh (owner Administrators,
# inheritance removed, Admins/SYSTEM only). $F itself stays writable for Users, so nothing is ever created there.
# Every run proves the dir ACL (like the ledger); after writing, proves the file's owner/ACL and that its sha256
# equals a second fresh `git show` of the same blob, immediately before Start-Process. Any doubt: no guardian run.
$GuardDir = "$F\guard"
$GuardRun = "$GuardDir\guardian.run.ps1"
$GuardChk = "$GuardDir\guardian.check.ps1"
$GitShow = "git -c safe.directory=* -c core.fsmonitor=false -c core.hooksPath=NUL -C `"$Src`" show ${bootNow}:$GuardRel"
$hasGuard = $false
if ($gNow -and ($gNow | Where-Object { $GuardRel -like $_ })) {
    & git @G -C $Src cat-file -e "${bootNow}:$GuardRel" 2>$null
    if (-not $LASTEXITCODE) {
        if (-not ((Test-Path -LiteralPath $GuardDir -PathType Container) -and (Test-AdminOnly $GuardDir))) {
            Journal @{ result = 'guardian_refused'; why = "guard dir $GuardDir missing or not admin-only (installer makes it)" }
        } else {
            foreach ($x in @($GuardRun, $GuardChk)) { if (Test-Path -LiteralPath $x) { Remove-Item -LiteralPath $x -Force } }
            & cmd /c "$GitShow > `"$GuardRun`""
            if (-not $LASTEXITCODE) {
                & "$env:SystemRoot\System32\icacls.exe" $GuardRun /inheritance:r /grant:r '*S-1-5-32-544:F' '*S-1-5-18:F' | Out-Null
                if ($LASTEXITCODE -eq 0 -and (Test-AdminOnly $GuardRun)) {
                    & cmd /c "$GitShow > `"$GuardChk`""
                    if (-not $LASTEXITCODE -and (Get-Sha256Hex $GuardRun) -eq (Get-Sha256Hex $GuardChk)) { $hasGuard = $true }
                    else { Journal @{ result = 'guardian_refused'; why = 'guardian copy sha256 differs from a fresh git show' } }
                    Remove-Item -LiteralPath $GuardChk -Force -ErrorAction SilentlyContinue
                } else { Journal @{ result = 'guardian_refused'; why = 'guardian copy owner/ACL not admin-only' } }
            }
        }
    }
}
if ($hasGuard) {
    $GuardPs = $GuardRun
    try {
        $gp = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -PassThru -WindowStyle Hidden `
            -ArgumentList @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', "`"$GuardPs`"")
        if (-not $gp.WaitForExit(600000)) { $gp.Kill(); Journal @{ result = 'guardian_timeout' } }
        elseif ($gp.ExitCode -ne 0) { Journal @{ result = 'guardian_failed'; code = $gp.ExitCode } }
    } catch { Journal @{ result = 'guardian_error'; why = "$($_.Exception.Message)" } }
}

# --- choose a candidate (read only until a candidate passes A-E) ---
$Cfg = Get-Content -Raw "$F\loop.json" | ConvertFrom-Json
$Old = "$($Cfg.boot)".Trim()
if ($Old -notmatch '^[0-9a-f]{40}$') { Journal @{ result = 'refused'; why = "loop.json boot is not a sha: $Old" }; exit 2 }
$Drop = $Cfg.drop.checkout
$RB = Join-Path $Drop 'forge_reboot'
if (-not (Test-Path -LiteralPath $RB)) { exit 0 }
$holds = @{}
foreach ($v in Get-ChildItem -Recurse -File -Filter '*.json' -LiteralPath $Drop -ErrorAction SilentlyContinue) {
    try { $txt = [IO.File]::ReadAllText($v.FullName, $U8) } catch { continue }
    foreach ($m in [regex]::Matches($txt, 'AUDIT HOLD ([0-9a-f]{40})')) { $holds[$m.Groups[1].Value] = $v.FullName }
}
$cands = @()
foreach ($b in Get-ChildItem -File -Filter 'boot-*.bundle' -LiteralPath $RB) {   # only boot packets
    $shaF = "$($b.FullName).sha256"; $verF = ($b.FullName -replace '\.bundle$', '.verdict.json')
    if (-not ((Test-Path -LiteralPath $shaF) -and (Test-Path -LiteralPath $verF))) { continue }
    try { $ver = [IO.File]::ReadAllText($verF, $U8) | ConvertFrom-Json } catch { continue }
    if ("$($ver.line)" -notmatch '^\s*AUDIT CLEAR ([0-9a-f]{40})\b') { continue }
    $sha = $Matches[1]
    if ($sha -eq $Old) { continue }
    $want = ((Get-Content -Raw -LiteralPath $shaF) -split '\s+')[0].ToUpper()
    if ((Get-Sha256Hex $b.FullName) -ne $want) { Journal @{ result = 'refused'; new = $sha; bundle = $b.Name; why = 'A: sha256 mismatch' }; continue }
    $heads = @(& git @G -C $Src bundle list-heads $b.FullName 2>$null | Where-Object { $_ -match '^[0-9a-f]{40} refs/heads/' })
    if ($heads.Count -ne 1 -or -not $heads[0].StartsWith($sha)) { continue }   # verdict is not for this bundle's head
    $cands += [pscustomobject]@{ Sha = $sha; Bundle = $b.FullName; Ref = ($heads[0] -split ' ')[1]; Verdict = $verF }
}
if (-not $cands) { exit 0 }
# Bring every candidate's objects into boot-src (objects only: FETCH_HEAD, no ref, no checkout yet).
$ok = @()
foreach ($c in $cands) {
    & git @G -C $Src cat-file -e "$($c.Sha)^{commit}" 2>$null
    if ($LASTEXITCODE) { & git @G -C $Src fetch -q $c.Bundle $c.Ref 2>$null }
    & git @G -C $Src cat-file -e "$($c.Sha)^{commit}" 2>$null
    if ($LASTEXITCODE) { continue }
    & git @G -C $Src merge-base --is-ancestor $Old $c.Sha
    if ($LASTEXITCODE) { continue }                                        # C: not a fast-forward of the current boot
    $ok += $c
}
# The newest: a candidate no other candidate descends from.
$pick = $null
foreach ($c in $ok) {
    $beaten = $false
    foreach ($d in $ok) { if ($d.Sha -ne $c.Sha) { & git @G -C $Src merge-base --is-ancestor $c.Sha $d.Sha; if (-not $LASTEXITCODE) { $beaten = $true } } }
    if (-not $beaten) { $pick = $c; break }
}
if (-not $pick) { exit 0 }
$New = $pick.Sha
if ($holds.ContainsKey($New)) { Journal @{ result = 'refused'; old = $Old; new = $New; why = "B: AUDIT HOLD in $($holds[$New])" }; exit 0 }
if (Recent-Failure $New) { exit 0 }
$gOld = T-Globs $Old; $gNew = T-Globs $New
if ($null -eq $gOld -or $null -eq $gNew) { Journal @{ result = 'refused'; old = $Old; new = $New; why = 'D: TRUST_SET.json unreadable at a boot' }; exit 2 }
$changed = @(& git @G -C $Src diff --no-renames --name-only $Old $New)   # (r2) a rename out of T lists both paths
if ($LASTEXITCODE) { Journal @{ result = 'refused'; old = $Old; new = $New; why = 'D: diff failed' }; exit 2 }
$hitT = @($changed | Where-Object { $p = $_; ($gOld + $gNew) | Where-Object { $p -like $_ } })
if ($hitT) {
    # (r18, zuck 2026-11-26 17:33Z "cut every protected change possible all except core"; Audit pre-read items 17-23)
    # D0. The CURRENT boot's own trust checker judges old..new, exactly as the forge does: its trust_check.py and the
    #     TRUST_SET.json beside it are taken from $Old (never from the packet), written to an admin-only copy, re-hashed
    #     against a second fresh `git show`, and run with python -I. ORDINARY or TIGHTEN (a knob, a doc, a test, a
    #     tightening) moves on the Audit CLEAR alone. REFUSE is refused. TRUST, CONTRACT, any error, timeout, unreadable
    #     output or an old checker without --classify: the change needs the OWNER (D1 below).
    $cls = $null; $clsWhy = ''
    $Py = 'C:\Program Files\Python314\python.exe'
    $TcDir = "$GuardDir\tc"
    try {
        if (-not ((Test-Path -LiteralPath $GuardDir -PathType Container) -and (Test-AdminOnly $GuardDir))) { throw "guard dir not admin-only" }
        if (-not (Test-Path -LiteralPath $Py)) { throw "python missing" }
        if (Test-Path -LiteralPath $TcDir) { Remove-Item -LiteralPath $TcDir -Recurse -Force }
        New-Item -ItemType Directory -Path $TcDir | Out-Null
        & "$env:SystemRoot\System32\icacls.exe" $TcDir /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
        foreach ($rel in @('ops/box_git/trust_check.py', 'ops/box_git/TRUST_SET.json')) {
            $dst = Join-Path $TcDir (Split-Path $rel -Leaf)
            $show = "git -c safe.directory=* -c core.fsmonitor=false -c core.hooksPath=NUL -C `"$Src`" show ${Old}:$rel"
            & cmd /c "$show > `"$dst`""
            if ($LASTEXITCODE) { throw "git show $rel failed" }
            & cmd /c "$show > `"$dst.chk`""
            if ($LASTEXITCODE -or (Get-Sha256Hex $dst) -ne (Get-Sha256Hex "$dst.chk")) { throw "checker copy of $rel differs from a fresh git show" }
            Remove-Item -LiteralPath "$dst.chk" -Force
        }
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = $Py
        $psi.Arguments = "-I `"$TcDir\trust_check.py`" --classify `"$Src`" $Old $New"
        $psi.UseShellExecute = $false; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true; $psi.CreateNoWindow = $true
        $p = [Diagnostics.Process]::Start($psi)
        $outT = $p.StandardOutput.ReadToEndAsync(); $errT = $p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit(600000)) { $p.Kill(); throw "checker timed out" }
        if ($p.ExitCode -ne 0) { throw "checker exit $($p.ExitCode): $("$($errT.Result)".Trim() -replace '\s+', ' ' | ForEach-Object { $_.Substring(0, [Math]::Min(200, $_.Length)) })" }
        $res = ("$($outT.Result)".Trim().Split("`n") | Select-Object -Last 1) | ConvertFrom-Json
        if ("$($res.class)" -notin @('ORDINARY', 'TIGHTEN', 'TRUST', 'CONTRACT', 'REFUSE')) { throw "checker printed no class" }
        $cls = "$($res.class)"; $clsWhy = "$($res.why)"
    } catch { $cls = $null; $clsWhy = "$($_.Exception.Message)" }
    if ($cls -eq 'REFUSE') { Journal @{ result = 'refused'; old = $Old; new = $New; why = "D0: checker REFUSE: $clsWhy" }; exit 0 }
    # A VETO <sha> anywhere in the drop still blocks this sha forever (a forged veto can only block, never allow).
    foreach ($v in Get-ChildItem -Recurse -File -LiteralPath $Drop -Include '*.json', '*.txt' -ErrorAction SilentlyContinue) {
        try { if ([IO.File]::ReadAllText($v.FullName, $U8) -match "VETO $New") {
            Journal @{ result = 'refused'; old = $Old; new = $New; why = "D: vetoed in $($v.FullName)" }; exit 0 } } catch {}
    }
    if ($cls -in @('ORDINARY', 'TIGHTEN')) {
        Journal @{ result = 'checker_cleared'; old = $Old; new = $New; class = $cls; why = $clsWhy; paths = @($hitT | Select-Object -First 20) }
    } else {
        # D1. The core (who approves, the money gates, signing and authority, the checker itself) and anything the
        #     checker could not clear: the OWNER's own act only. (Audit r18 MF1) Approvals live OUTSIDE the drop, in
        #     $F\owner_approvals, which the installer creates admin-only and every run re-proves (owner and every ACE
        #     Administrators/SYSTEM, none inherited). The file <sha>.txt counts only when neither it nor the folder is a
        #     reparse point (symlink/junction) and it has exactly one hard link, so no alias of another admin file can
        #     stand in for it. No silence, no clock (zuck 11-26 14:28Z): the owner's file is the approval itself.
        #     AI sessions never write it (standing rule; Audit spot-checks each owner_approved row against a zuck message).
        $OA = "$F\owner_approvals"
        $why1 = $null
        if (-not (Test-Path -LiteralPath $OA -PathType Container)) { $why1 = 'owner_approvals folder missing (installer makes it)' }
        elseif (((Get-Item -LiteralPath $OA -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { $why1 = 'owner_approvals is a reparse point' }
        elseif (-not (Test-AdminOnly $OA)) { $why1 = 'owner_approvals ACL not admin-only' }
        $ann = Join-Path $OA "$New.txt"
        if (-not $why1) {
            if (-not (Test-Path -LiteralPath $ann -PathType Leaf)) { $why1 = 'no owner approval file' }
            elseif (((Get-Item -LiteralPath $ann -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { $why1 = 'approval file is a reparse point' }
            else {
                $links = @(& "$env:SystemRoot\System32\fsutil.exe" hardlink list $ann 2>$null)
                if ($LASTEXITCODE -or $links.Count -ne 1) { $why1 = "approval file has $($links.Count) hard links" }
            }
        }
        if ($why1) {
            Journal @{ result = 'awaiting_owner'; old = $Old; new = $New; class = $cls; why = $clsWhy; owner = $why1; paths = @($hitT | Select-Object -First 20) }
            exit 0
        }
        Journal @{ result = 'owner_approved'; old = $Old; new = $New; class = $cls; why = $clsWhy; file = $ann }
    }
}

# --- candidate passed A-E: move it ---
$ErrorActionPreference = 'Stop'
$Ev = 'C:\opt\quant\data\evidence_backups\forge_reboot_auto_{0:yyyyMMdd_HHmmss}_{1}' -f (Get-Date).ToUniversalTime(), $New.Substring(0, 9)
New-Item -ItemType Directory -Force -Path $Ev | Out-Null
$Ended = $false
$SrcMoved = $false; $CiStopped = $false; $Written = $false; $Verified = $false   # (r17) recovery state
# (r16) After a pass was ended, ANY exit other than 'moved' puts the box back as it was and restarts the loop at once:
# boot-src back to the old boot, QuantForge-Loop started (11-26 15:41Z: r11 ended pass 26732, then threw, and the box
# sat on a half-moved boot-src with no pass until the next 5-min tick).
function Note([string] $m) { try { [IO.File]::AppendAllText("$Ev\move_boot.log", ("{0:u}  {1}`r`n" -f (Get-Date).ToUniversalTime(), $m), $U8) } catch {} }
function Start-Tasks {   # (r17) restart what this run stopped; never anything else
    if (-not $script:Ended) { return }
    try { Start-ScheduledTask -TaskName 'QuantForge-Loop'; Note 'RECOVER: QuantForge-Loop started' } catch { Note "RECOVER: QuantForge-Loop start failed: $($_.Exception.Message)" }
    if ($script:CiStopped) { try { Start-ScheduledTask -TaskName 'QuantForge-CI'; Note 'RECOVER: QuantForge-CI started' } catch { Note "RECOVER: QuantForge-CI start failed: $($_.Exception.Message)" } }
}
# (r17, Audit MF 15:46Z) Recovery depends on how far the move got:
#   verified write  -> the move stands: no revert, only the stopped tasks are started;
#   write started   -> .premove bytes restored first, then boot-src back to Old, then tasks started;
#   no write        -> boot-src back to Old (it is staging only), then tasks started if a pass was ended.
function Recover-AfterEnd {
    $ErrorActionPreference = 'Continue'
    if ($script:Verified) { Start-Tasks; return }
    if ($script:Written) {
        foreach ($p in $Files) {
            try { [IO.File]::WriteAllBytes($p, $before[$p]); $okR = [Convert]::ToBase64String([IO.File]::ReadAllBytes($p)) -eq [Convert]::ToBase64String($before[$p]); Note "RECOVER: $p restored from .premove bytes, verified $okR" }
            catch { Note "RECOVER: RESTORE FAILED $p : $($_.Exception.Message); .premove copy in $Ev" }
        }
    }
    if ($script:SrcMoved -or ("$(& git @G -C $Src rev-parse HEAD 2>&1)".Trim() -ne $Old)) { & git @G -C $Src checkout -q --detach --force $Old 2>&1 | Out-Null; Note "RECOVER: boot-src back to $Old (rc $LASTEXITCODE)" }
    Start-Tasks
}
trap {
    # (r16) the log line FIRST, with where it failed; then the journal; then recovery.
    $where = "$($_.InvocationInfo.PositionMessage)" -replace '\s+', ' '
    try { [IO.File]::AppendAllText("$Ev\move_boot.log", ("{0:u}  ERROR: {1} [{2}] at {3}`r`n" -f (Get-Date).ToUniversalTime(), $_.Exception.Message, $_.Exception.GetType().FullName, $where), $U8) } catch {}
    try { Journal @{ result = 'error'; old = $Old; new = $New; ended_pass = $Ended; why = "$($_.Exception.Message)"; where = $where.Substring(0, [Math]::Min(400, $where.Length)); evidence = $Ev } } catch {}
    if ($script:Verified) {   # (r17) the verified write stands: record it as moved, start the tasks, exit 0
        try { Journal @{ result = 'moved'; old = $Old; new = $New; ended_pass = $Ended; evidence = $Ev; note = 'error after the verified write' } } catch {}
        Start-Tasks; exit 0
    }
    Recover-AfterEnd
    exit 5
}
function Stop-Move([string] $why, [int] $code) {
    Say "STOP: $why"
    Journal @{ result = $(if ($Ended) { 'stopped_after_end' } else { 'deferred' }); old = $Old; new = $New; why = $why; evidence = $Ev }
    Recover-AfterEnd
    exit $code
}
# (r16) Native git never runs under 'Stop' (PS 5.1 turns any stderr line into a terminating error); rc is checked.
function GitRc { $ErrorActionPreference = 'Continue'; & git @G @args 2>&1 | Out-Null; return $LASTEXITCODE }

$Files = @("$F\loop.json", "$F\run_loop.cmd")
$Watch = @('C:\opt\audit_registry\ROOT_PIN.json') +
    (Get-ChildItem -Recurse -File 'C:\ProgramData\QuantBox\trust', "$F\box-tokens", "$F\drop-key",
        "$F\custom\https", "$F\data\jwt" | Where-Object { $_.FullName -notmatch '__pycache__' } |
        ForEach-Object FullName)
function Tasks {   # one scalar string: each task's static definition only (no run state, no last/next run times)
    $parts = foreach ($n in 'QuantForge-Loop', 'QuantForge-CI', 'QuantForge-Pin') {
        $t = Get-ScheduledTask -TaskName $n
        $a = $t.Actions | Select-Object Execute, Arguments, WorkingDirectory | ConvertTo-Json -Compress
        $p = $t.Principal | Select-Object UserId, LogonType, RunLevel, GroupId | ConvertTo-Json -Compress
        $g = @($t.Triggers | ForEach-Object { [pscustomobject]@{ C = $_.CimClass.CimClassName; S = $_.StartBoundary; E = $_.EndBoundary; En = $_.Enabled; I = $_.Repetition.Interval; D = $_.Repetition.Duration; L = $_.ExecutionTimeLimit } }) | ConvertTo-Json -Compress
        $s = $t.Settings | Select-Object ExecutionTimeLimit, MultipleInstances, Priority, StartWhenAvailable, Enabled, Hidden, DisallowStartIfOnBatteries, StopIfGoingOnBatteries, RunOnlyIfIdle, WakeToRun | ConvertTo-Json -Compress
        "$n|$a|$p|$g|$s"
    }
    return [string]($parts -join "`n")
}
function Say([string] $m) { $l = "{0:u}  {1}" -f (Get-Date).ToUniversalTime(), $m; Write-Host $l; Add-Content "$Ev\move_boot.log" $l }
function LoopRunning { (Get-ScheduledTask -TaskName 'QuantForge-Loop').State -eq 'Running' }
# Every byte that differs between $a and $b must lie inside an occurrence of the old sha in $a.
function OnlyShaBytes([byte[]] $a, [byte[]] $b) {
    if ($a.Length -ne $b.Length) { return $false }
    $in = New-Object bool[] $a.Length
    foreach ($m in [regex]::Matches($L1.GetString($a), $Old)) { for ($i = $m.Index; $i -lt $m.Index + $m.Length; $i++) { $in[$i] = $true } }
    for ($i = 0; $i -lt $a.Length; $i++) { if ($a[$i] -ne $b[$i] -and -not $in[$i]) { return $false } }
    return $true
}

# -1. End a pass on the old boot older than 30 min (Audit 19:55Z). Only QuantForge-Loop and QuantForge-CI.
function Procs { @(Get-CimInstance Win32_Process) }
function Tree([object[]] $all, [object[]] $roots) {   # roots + every descendant by parent pid, keyed pid@creation
    $out = @{}; $q = New-Object System.Collections.Queue; foreach ($r in $roots) { $q.Enqueue($r) }
    while ($q.Count) {
        $p = $q.Dequeue(); $k = "{0}@{1:o}" -f $p.ProcessId, $p.CreationDate
        if ($out.ContainsKey($k)) { continue }; $out[$k] = $p
        foreach ($c in $all | Where-Object { $_.ParentProcessId -eq $p.ProcessId -and $_.CreationDate -ge $p.CreationDate }) { $q.Enqueue($c) }
    }
    return $out
}
function Alive([hashtable] $tree) { $now = Procs; @($tree.Values | Where-Object { $t = $_; $now | Where-Object { $_.ProcessId -eq $t.ProcessId -and $_.CreationDate -eq $t.CreationDate } }) }
# -2. boot-src to the new boot (objects already fetched above), detached checkout. Never touches loop-src or the mirror.
if (-not (Test-Path -LiteralPath $Src)) { Stop-Move "$Src does not exist; nothing ended or written" 2 }
if ("$(& git @G -C $Src rev-parse HEAD)".Trim() -ne $New) {
    $script:SrcMoved = $true
    if (GitRc -C $Src checkout -q --detach --force $New) { Stop-Move 'boot-src checkout of the new boot failed' 2 }
    Say "boot-src now at $New (from $($pick.Bundle), sha256 verified, verdict $($pick.Verdict))"
}
# r7: checked before step -1, so a missing or wrong boot-src never ends a pass.
if (-not (Test-Path -LiteralPath $Src)) { Stop-Move "$Src does not exist; nothing ended or written" 2 }
if ("$(& git @G -C $Src rev-parse HEAD)".Trim() -ne $New) { Stop-Move 'boot-src HEAD is not the new boot; nothing ended or written' 2 }
# (r16) EVERY fallible step runs BEFORE a pass is ended (Audit 15:43Z): byte plan, evidence copies, watched hashes,
# task definitions, and the object fetches into loop-src and the forge repo (objects only: harmless to a running pass).
if (GitRc -C $Src merge-base --is-ancestor $Old $New) { Stop-Move 'old boot is not an ancestor' 2 }
$before = @{}; foreach ($p in $Files) { $before[$p] = [IO.File]::ReadAllBytes($p) }
$exp = @{}
foreach ($p in $Files) {
    $t = $L1.GetString($before[$p])
    $n = ([regex]::Matches($t, $Old)).Count
    $want = if ($p -like '*loop.json') { 1 } else { 2 }
    if ($n -ne $want) { Stop-Move "$p holds $n copies of the old boot, expected $want" 2 }
    if ($t.Contains($New)) { Stop-Move "$p already names the new boot" 2 }
    $exp[$p] = $L1.GetBytes($t.Replace($Old, $New))
    if (-not (OnlyShaBytes $before[$p] $exp[$p])) { Stop-Move "planned bytes for $p differ outside the boot sha" 2 }
}
foreach ($p in $Files) { [IO.File]::WriteAllBytes("$Ev\$(Split-Path $p -Leaf).premove", $before[$p]) }
$wh = @{}; foreach ($p in $Watch) { $wh[$p] = Get-Sha256Hex $p }
$tasks0 = Tasks
# 1. Object-only fetch of the new boot into loop-src (FETCH_HEAD only, no ref)
if (GitRc -C "$F\loop-src" cat-file -e "$New^{commit}") {
    if (GitRc -C "$F\loop-src" fetch -q $Src $New) { Stop-Move 'could not fetch the boot object into loop-src' 3 }
    if (GitRc -C "$F\loop-src" cat-file -e "$New^{commit}") { Stop-Move 'object missing in loop-src after fetch' 3 }
}
# (r6) The gate checks the boot out of the forge repo ($Cfg.bare, mirror.git): objects only, no ref.
if (GitRc -C $Cfg.bare cat-file -e "$New^{commit}") {
    if (GitRc -C $Cfg.bare fetch -q --no-tags "$F\loop-src" $New) { Stop-Move "could not fetch the boot object into $($Cfg.bare)" 3 }
    if (GitRc -C $Cfg.bare cat-file -e "$New^{commit}") { Stop-Move "boot object not in the forge repo $($Cfg.bare) after fetch" 3 }
    Say "forge repo $($Cfg.bare) now holds $New (objects only)"
}
Say 'all pre-checks passed: byte plan, evidence copies, watched hashes, task definitions, boot objects in loop-src and the forge repo'

if (LoopRunning) {
    $all = Procs
    $loopRoots = @($all | Where-Object { $_.CommandLine -match 'run_loop\.cmd|box_loop\.py"?\s+--config' } |
        Where-Object { $pp = $_.ParentProcessId; -not ($all | Where-Object { $_.ProcessId -eq $pp -and $_.CommandLine -match 'run_loop\.cmd|box_loop' }) })
    $ciRoots = @($all | Where-Object { $_.CommandLine -match 'box_loop\.py"?\s+--ci-worker' } |
        Where-Object { $pp = $_.ParentProcessId; -not ($all | Where-Object { $_.ProcessId -eq $pp -and $_.CommandLine -match 'box_loop' }) })
    if (-not $loopRoots) { Stop-Move 'QuantForge-Loop is Running but its process was not found; nothing ended' 2 }
    $start = ($loopRoots | Sort-Object CreationDate | Select-Object -First 1).CreationDate
    if (((Get-Date) - $start).TotalMinutes -lt 30) { Stop-Move ("the loop pass started {0:u}, under 30 min ago; retry later" -f $start.ToUniversalTime()) 2 }
    $boot = (& git @G -C "$F\loop-src" rev-parse HEAD).Trim()
    $tree = Tree $all ($loopRoots + $ciRoots)
    Say ("ENDING PASS: loop root pid(s) {0}, started {1:u}, boot {2}; CI worker root pid(s) {3}; {4} processes in the two trees:" -f
        (($loopRoots | ForEach-Object ProcessId) -join ','), $start.ToUniversalTime(), $boot, (($ciRoots | ForEach-Object ProcessId) -join ','), $tree.Count)
    foreach ($p in $tree.Values) { Say ("    pid {0} ppid {1} {2:u} {3}" -f $p.ProcessId, $p.ParentProcessId, $p.CreationDate.ToUniversalTime(), "$($p.CommandLine)".Substring(0, [Math]::Min(200, "$($p.CommandLine)".Length))) }
    # The loop ticks every 5 min (IgnoreNew while running). End just after a tick, so the next one is ~5 min away and
    # cannot start a fresh old-boot pass before the write below.
    $next = (Get-ScheduledTaskInfo -TaskName 'QuantForge-Loop').NextRunTime
    if ($next -and ($next - (Get-Date)).TotalSeconds -lt 180) { Start-Sleep -Seconds ([Math]::Max(0, [int](($next - (Get-Date)).TotalSeconds) + 10)) }
    $script:Ended = $true
    Stop-ScheduledTask -TaskName 'QuantForge-Loop'
    if ((Get-ScheduledTask -TaskName 'QuantForge-CI').State -eq 'Running') { $script:CiStopped = $true; Stop-ScheduledTask -TaskName 'QuantForge-CI' }
    $until = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $until -and ((LoopRunning) -or (Alive $tree).Count)) { Start-Sleep -Seconds 2 }
    $left = Alive $tree
    if ((LoopRunning) -or $left.Count) { Stop-Move ("120 s after Stop-ScheduledTask the loop is Running={0} and {1} process(es) of the pass are alive: {2}; nothing written" -f (LoopRunning), $left.Count, (($left | ForEach-Object ProcessId) -join ',')) 2 }
    Say 'the pass and all its descendants have exited'
    # The dead pass's unclaimed jobs would run on the next worker tick: moved to evidence, never deleted.
    $pend = Join-Path $Cfg.ci_jobs 'pending'
    if (Test-Path $pend) {
        $orph = @(Get-ChildItem -File $pend | Where-Object { $_.LastWriteTime -le (Get-Date) })
        if ($orph) { New-Item -ItemType Directory -Force -Path "$Ev\orphan_jobs" | Out-Null
            foreach ($o in $orph) { Move-Item -LiteralPath $o.FullName -Destination "$Ev\orphan_jobs\" ; Say "    moved unclaimed job $($o.Name) to $Ev\orphan_jobs" } }
    }
    # (r16) Locks a killed git leaves: ONLY the known index.lock paths, never a walk of a live tree (r11 walked forge\work,
    # 28 GB / 215k files, under 'Stop' while the ended pass's worktrees were being removed). Reported, never deleted.
    $lockPaths = @("$F\loop-src\.git\index.lock", (Join-Path $Cfg.bare 'index.lock'))
    try { $lockPaths += @(Get-ChildItem -Directory -LiteralPath (Join-Path $Cfg.bare 'worktrees') -ErrorAction Ignore | ForEach-Object { Join-Path $_.FullName 'index.lock' }) } catch {}
    $locks = @($lockPaths | Where-Object { try { Test-Path -LiteralPath $_ -ErrorAction Ignore } catch { $false } })
    if ($locks) { foreach ($l in $locks) { Say "WARNING: git lock left by the ended pass will block the next pass until removed: $l" } }
    else { Say 'no git index.lock in loop-src, the forge repo or its worktrees: the next pass is not blocked' }
}

# 0. After the end: nothing may have changed under us
if (LoopRunning) { Stop-Move 'QuantForge-Loop is Running; retry between passes' 2 }
if ("$(& git @G -C $Src rev-parse HEAD 2>$null)".Trim() -ne $New) { Stop-Move 'boot-src HEAD is not the new boot' 2 }
foreach ($p in $Files) { if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($p)) -ne [Convert]::ToBase64String($before[$p])) { Stop-Move "$p changed after the pre-checks; nothing written" 2 } }

if (LoopRunning) { Stop-Move 'QuantForge-Loop started; nothing written; retry between passes' 2 }

# 2. Write in place (keeps ACLs), then read back byte for byte; any exception counts as a mismatch
$bad = @()
try {
    $script:Written = $true
    foreach ($p in $Files) { [IO.File]::WriteAllBytes($p, $exp[$p]) }
    foreach ($p in $Files) {
        $got = [IO.File]::ReadAllBytes($p)
        if ([Convert]::ToBase64String($got) -ne [Convert]::ToBase64String($exp[$p])) { $bad += "content $p" }
        if (-not (OnlyShaBytes $before[$p] $got)) { $bad += "bytes outside the boot sha changed in $p" }
        $diff = 0; for ($i = 0; $i -lt [Math]::Min($got.Length, $before[$p].Length); $i++) { if ($got[$i] -ne $before[$p][$i]) { $diff++ } }
        Say ("{0}: {1} bytes differ from before; sha256 {2}" -f $p, $diff, (Get-Sha256Hex $p))
    }
    foreach ($p in $Watch) { if ((Get-Sha256Hex $p) -ne $wh[$p]) { $bad += "hash $p" } }
    $tasks1 = Tasks; if (-not [string]::Equals($tasks1, $tasks0)) { $bad += 'task definition'; Say "task definition before: $tasks0"; Say "task definition after:  $tasks1" }
} catch {
    $bad += "exception: $($_.Exception.Message)"
}

# 3. Rollback on any mismatch or exception
if ($bad) {
    $ok = $true
    foreach ($p in $Files) {
        try { [IO.File]::WriteAllBytes($p, $before[$p]) } catch { $ok = $false; Say "RESTORE WRITE FAILED $p : $($_.Exception.Message)" }
        try { if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($p)) -ne [Convert]::ToBase64String($before[$p])) { $ok = $false } } catch { $ok = $false }
    }
    Say ("ROLLED BACK ({0}); restore verified: {1}; .premove copies in {2}" -f ($bad -join '; '), $ok, $Ev)
    Journal @{ result = 'rolled_back'; old = $Old; new = $New; why = ($bad -join '; '); restore_verified = $ok; evidence = $Ev }; $script:Written = $false; Recover-AfterEnd; exit 4
}
$script:Verified = $true
Say "DONE: boot $Old -> $New in loop.json and run_loop.cmd; $($Watch.Count) watched hashes and 3 task definitions unchanged"
if ($script:CiStopped) { try { Start-ScheduledTask -TaskName 'QuantForge-CI' } catch {} }
Journal @{ result = 'moved'; old = $Old; new = $New; bundle = (Split-Path $pick.Bundle -Leaf); verdict = (Split-Path $pick.Verdict -Leaf); ended_pass = $Ended; evidence = $Ev }
exit 0

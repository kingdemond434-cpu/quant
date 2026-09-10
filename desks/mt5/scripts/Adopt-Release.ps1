<#
.SYNOPSIS
    Land the branch's tree on this box without ever asking the filesystem to
    unlink a file, then record the merge so the ordinary sync resumes.

.DESCRIPTION
    THE FAILURE THIS EXISTS FOR

    A hard power-off (2026-09-07, the disk-full hang) left one tracked path
    with a corrupt NTFS directory entry:

        error: unable to unlink old 'desks/mt5/side_channels/run_external_backtest.py':
        Invalid argument

    No process holds it -- `taskkill` reports no python, `Move-Item` fails the
    same way. The entry itself is damaged, so every operation that goes through
    DeleteFile/MoveFile returns EINVAL. `git merge`, `git checkout <ref> -- .`
    and `git pull` all update a file by unlinking the old one and creating a
    new one, so all three die on that single path and take the WHOLE adoption
    with them: nothing lands, and `Sync-Pull` exits 1 before it publishes.

    That is not a small outage. The box then runs whatever code it happened to
    hold, the dashboard stops updating, and the desk goes silent -- the same
    266-hour silence as before, from a different cause.

    WHY THIS WORKS WHERE GIT DOES NOT

    Opening an existing file with FileMode.Truncate rewrites its CONTENTS in
    place. It never touches the directory entry, so a damaged entry is simply
    not consulted. Every path the incoming tree changes is written that way,
    the paths are staged BY NAME, and the result is committed. Only then is
    the merge recorded with `-s ours` -- which is safe precisely because the
    tree already matches, and the script REFUSES to record it if it does not.

    So the ordering is the safety property, not a convenience:

        write in place -> stage by name -> commit -> VERIFY tree == ref -> record

    A `-s ours` merge run before that verification would silently discard the
    incoming work while reporting success. Run after it, it discards nothing:
    it only writes down a parent that is already true of the tree.

    WHAT IT WILL NOT DO

    A CODE path the incoming tree DELETES still needs a real unlink, and if that
    unlink fails the file stays. The script does not pretend otherwise: it
    counts those, names them, and leaves the exit code non-zero so a caller
    cannot read a partial adoption as a clean one. Nothing is force-removed.

    A STATE path the incoming tree deletes is never unlinked at all (2026-09-08).
    Origin stopped tracking it -- a4bd8663 untracked seventeen console logs and
    three supervisor files under desks/mt5/logs/ that running hunts hold open --
    so it leaves the INDEX only (`git rm --cached`) and stays on disk as the
    box's untracked evidence. Deleting it could only fail (a handle without
    FILE_SHARE_DELETE, or the damaged entry) and refuse the whole adoption on a
    file nothing reads from git; keeping it TRACKED (the old kept-by-box branch)
    re-published it on the next push and re-armed the very unmergeable loop the
    upstream deletion fixed.

    It never runs a bare `git add -A` and never stashes: every path it stages
    was enumerated from a diff or from `git status`, and the box's own
    uncommitted state is committed as itself, not parked.

    THIS DOES NOT REPAIR THE FILESYSTEM. `chkdsk C: /F` (no /R -- the surface
    scan is not what is wrong) plus a reboot is the actual repair, and it stays
    the right thing to do at the next convenient restart. This makes the desk
    whole in the meantime, and costs nothing if the entry is later fixed.

    STATE THE BOX HAS WRITTEN IS THE BOX'S (2026-09-08)

    The first version adopted EVERY path that differed from the target, and on
    a box that had not pushed for a day and a half that meant rewriting its own
    forward ledgers, certificates, hypotheses dockets and stall-watch verdicts
    with origin's older copies -- the box's live evidence rolled back to the
    last thing it had managed to publish. The two adoption attempts of 2026-09-07
    died mid-write (a locked path), left the code half-written and uncommitted,
    and every hourly sync since failed on the merge of that tree; the gateway
    refused new risk on the drift for a day while five sleeves placed nothing.

    A path under a state prefix (the same list `libs.ops.release.STATE_PREFIXES`
    holds, minus docs/, which the box never writes) that THIS BOX has changed
    since it diverged from the target is kept, not adopted: it is evidence, and
    the box is the only place it is measured. A state path only origin changed
    -- a research budget, a measured venue clock, an input a session wrote for
    the box to read -- is adopted like code. Code is always adopted. The merge
    is recorded once every path outside the kept set matches the target, so the
    next sync fast-forwards and the box's own state travels to origin with it.

    The cost of that rule is stated rather than hidden: where BOTH sides changed
    a state path, the box's copy wins and origin's edit is reverted by the box's
    next push. Every such path is named in the output.

.PARAMETER RepoRoot
    Repository root. Defaults to three levels above this script, correct by
    construction.

.PARAMETER Branch
    Branch to adopt. Defaults to the checkout's current branch, which is what
    `sync_shadow_to_git.ps1` pulls -- so this adopts exactly what the sync
    could not.

.PARAMETER NoFetch
    Adopt the FETCH_HEAD already on disk instead of fetching first. For a
    rerun, or a box whose network is the thing that is broken.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File desks\mt5\scripts\Adopt-Release.ps1
#>
[CmdletBinding()]
param(
    [string] $RepoRoot,
    [string] $Branch,
    [switch] $NoFetch
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}
if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    throw "not a repository root: $RepoRoot"
}

function Invoke-Git {
    # Captures stdout as text and THROWS on a non-zero exit, so a failed plumbing
    # call can never be mistaken for an empty result -- which is how a bad diff
    # would otherwise read as "nothing to adopt".
    #
    # NOT named $Args: that is a PowerShell automatic variable, and binding a
    # parameter over it in a non-advanced function silently loses the arguments.
    param([string[]] $GitArgs, [switch] $AllowFail)
    # `2>&1` ON A NATIVE COMMAND UNDER `ErrorActionPreference = Stop` IS A TRAP, and it killed
    # this script on its first real run. PowerShell turns each stderr LINE from an external
    # program into an ErrorRecord, and under `Stop` the first one becomes TERMINATING -- so the
    # script aborts on output that is not an error at all. git writes its ordinary progress to
    # stderr:
    #
    #     git.exe : From https://github.com/<owner>/<repo>
    #     At Adopt-Release.ps1:196 char:9 ... NativeCommandError
    #
    # That is a successful fetch reporting what it fetched. EXIT CODE IS THE TRUTH for a native
    # command, and this function already checks it; the preference is therefore relaxed only
    # around the call and restored immediately, so a real PowerShell error still stops the script.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        # Each record is forced to a string as it arrives: an ErrorRecord that reaches the caller
        # un-stringified fails `-match '\S'` and would silently drop a line of real output.
        $out = & git -C $RepoRoot @GitArgs 2>&1 | ForEach-Object { "$_" }
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($LASTEXITCODE -ne 0 -and -not $AllowFail) {
        throw ("git {0} failed rc={1}: {2}" -f ($GitArgs -join " "), $LASTEXITCODE, ($out -join "`n"))
    }
    return $out
}

function Invoke-GitBytes {
    # BYTE-EXACT, and it has to be. PowerShell 5.1's `>` writes UTF-16 and
    # Out-File writes a BOM; either one changes the content, so the file would
    # not match the ref, the verification below would fail, and the adoption
    # would be refused for a reason that has nothing to do with the tree.
    # Reading the raw stdout stream is the only way to get the exact bytes.
    param([string] $ArgLine)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName               = "git"
    $psi.Arguments              = ('-C "{0}" {1}' -f $RepoRoot, $ArgLine)
    $psi.UseShellExecute        = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.CreateNoWindow         = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    $ms = New-Object System.IO.MemoryStream
    $proc.StandardOutput.BaseStream.CopyTo($ms)
    $err = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    return @{ Bytes = $ms.ToArray(); ExitCode = $proc.ExitCode; Error = $err }
}

function Get-WorktreeBytes {
    # `--filters`, NOT plain `cat-file blob`. The blob is the REPOSITORY form --
    # always LF -- and Git for Windows checks files out through an eol filter, so
    # writing the blob raw puts LF into files this box expects to hold CRLF. For
    # `.cmd` that is not cosmetic: cmd.exe parsing of labels and `goto` is not
    # reliable on LF-only batch files, and four .cmd files are tracked here.
    #
    # `cat-file --filters <rev>:<path>` emits exactly the bytes git itself would
    # write to the working tree, so the adopted file is indistinguishable from a
    # checked-out one. Staging converts back on the way in, so the committed blob
    # still matches the target and the verification below is unaffected either way.
    #
    # Falls back to the raw blob on a git too old for --filters (< 2.11): LF
    # content is still correct for every interpreter used here, and refusing to
    # adopt at all would be the worse failure.
    param([string] $Rev, [string] $Path)
    $r = Invoke-GitBytes ('cat-file --filters "{0}:{1}"' -f $Rev, $Path)
    if ($r.ExitCode -ne 0) {
        $r = Invoke-GitBytes ('cat-file blob "{0}:{1}"' -f $Rev, $Path)
        if ($r.ExitCode -ne 0) {
            throw ("cat-file {0}:{1} failed: {2}" -f $Rev, $Path, $r.Error)
        }
    }
    return $r.Bytes
}

function Write-InPlace {
    # THE WHOLE POINT OF THE SCRIPT IS THIS FUNCTION. Truncate opens the
    # existing entry and rewrites the bytes; it issues no DeleteFile and no
    # MoveFile, so a corrupt directory entry is never consulted. Create is only
    # for a path the incoming tree ADDS, where there is no entry to damage.
    param([string] $Full, [byte[]] $Bytes)
    $dir = Split-Path $Full -Parent
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    if (Test-Path -LiteralPath $Full) {
        $mode = [System.IO.FileMode]::Truncate
        # Clear read-only rather than fail on it: git leaves modes alone, but a
        # restore-from-backup or a rescue-shell copy can set the attribute, and
        # a read-only bit is not a reason to abandon an adoption.
        $item = Get-Item -LiteralPath $Full -Force
        if ($item.Attributes -band [System.IO.FileAttributes]::ReadOnly) {
            $item.Attributes = $item.Attributes -bxor [System.IO.FileAttributes]::ReadOnly
        }
    } else {
        $mode = [System.IO.FileMode]::Create
    }
    # A READER IN THE WAY IS A MOMENT, NOT A VERDICT. Both 2026-09-07 attempts died on a path an
    # organ happened to hold open, and the loop above treated the first sharing violation as the
    # path being corrupt. A python import or a log tail holds a file for milliseconds; three
    # tries two seconds apart outlast that, and a path still locked after six seconds is
    # reported exactly as before.
    $tries = 0
    $unlinked = $false
    while ($true) {
        try {
            $fs = [System.IO.File]::Open($Full, $mode, [System.IO.FileAccess]::Write,
                                         [System.IO.FileShare]::None)
            try { $fs.Write($Bytes, 0, $Bytes.Length) } finally { $fs.Close() }
            return
        } catch [System.IO.IOException] {
            $tries++
            if ($tries -ge 3) { throw }
            Start-Sleep -Seconds 2
        } catch [System.UnauthorizedAccessException] {
            # A DENIED WRITE IS NOT A DENIED PATH (2026-09-09). Ten paths on the box -- eight
            # `data/` files the SYSTEM-run intelligence legs wrote, plus desks/mt5/AGENTS.md and
            # desks/mt5/blueprint/coverage.py -- came to carry an ACL the desk's own account
            # cannot write. Truncate needs WRITE_DATA on the FILE; unlink needs only DELETE_CHILD
            # on its DIRECTORY, which the account plainly has (the same pass created 15,136 files
            # beside them). So the adoption failed, hourly, on ten paths out of 15,146 -- and
            # because Adopt-And-Seal refuses to seal a tree that only half-matches the branch,
            # those ten held the whole box on stale code for a day.
            #
            # THIS IS NOT A RETREAT FROM THE IN-PLACE RULE. Truncate stays the only first move,
            # for exactly the reason the header gives: a corrupt directory entry must never be
            # consulted. The unlink is reached ONLY after the kernel has already refused the
            # in-place write on permission grounds, where the alternative is not "a safer write"
            # but no write at all. It is tried once, it is tried only for a path that already
            # existed, and if the unlink is refused too the ORIGINAL access error is what the
            # caller sees -- so a genuinely unwritable path still reads as [FAIL] and still
            # leaves the exit code non-zero. Nothing is force-removed that was not about to be
            # overwritten with the branch's own bytes in the next statement.
            if ($unlinked -or $mode -ne [System.IO.FileMode]::Truncate) { throw }
            $denied = $_
            try { [System.IO.File]::Delete($Full) } catch { throw $denied }
            $unlinked = $true
            $mode = [System.IO.FileMode]::Create
        }
    }
}

# THE STATE PREFIXES, verbatim from `libs.ops.release.STATE_PREFIXES` minus docs/ (which the box
# never writes, so origin's docs are adopted like code). Kept as a literal because this script
# runs BEFORE the adopted `libs` is on disk; test_adopt_release_keeps_the_box_s_state pins the
# two lists to each other.
$StatePrefixes = @("desks/mt5/data/", "desks/mt5/reports/", "desks/mt5/logs/",
                   "data/", "reports/", "logs/", "web/")

# STATE ARTIFACTS THAT SIT AT THE DESK ROOT INSTEAD OF UNDER data/. Every prefix above ends in a
# directory, so a state file written beside the code reads as CODE -- and this script then treats
# the box's own copy as unexplained drift rather than as the box's evidence.
#
# MEASURED HERE 2026-09-10, on the first adoption that reached the current branch:
#
#     REFUSING to record the merge: 9 path(s) still differ from the target.
#     adopt-and-seal: Adopt-Release exited 1 -- partial adoption; NOT sealing a tree that only
#     half-matches the branch
#
# Seven of those nine were a gateway state file, a regime stamp, a cycle marker and four sweep
# outputs, at the desk root only because they were committed there once (aa90ee81, 2026-08-19).
# The refusal was correct; the classification under it was not. The box rewrites those files, so
# every future adoption would have refused for the same reason -- the seal never recorded, the
# gateway never restarted, and the box stayed on old code indefinitely.
#
# KEPT IN STEP WITH libs/ops/release.STATE_FILES, which is the same list in the language the rest
# of the desk reads it in, and a test fails when the two drift apart.
$StateFiles = @("desks/mt5/gateway_state.json", "desks/mt5/regime_state.json",
                "desks/mt5/sync_marker.json", "desks/mt5/portfolio_projection.json",
                "desks/mt5/hunt11.json", "desks/mt5/mech_battery.json",
                "desks/mt5/mech_split.json")

function Test-StatePath {
    param([string] $Rel)
    $p = ($Rel -replace '\\', '/').TrimStart('.', '/')
    if ($StateFiles -contains $p) { return $true }
    foreach ($prefix in $StatePrefixes) { if ($p.StartsWith($prefix)) { return $true } }
    return $false
}

Write-Host "ADOPT RELEASE"
Write-Host ("  repo   {0}" -f $RepoRoot)

if (-not $Branch) { $Branch = (Invoke-Git @("rev-parse", "--abbrev-ref", "HEAD")).Trim() }
Write-Host ("  branch {0}" -f $Branch)

# FETCH_HEAD, NOT origin/<branch>. A `git fetch origin <branch>` with an explicit
# branch argument does not necessarily update the remote-tracking ref, and this
# box has already produced "unknown revision origin/claude/..." immediately after
# a successful fetch of that same branch. FETCH_HEAD is written by the fetch that
# just ran, every time.
if (-not $NoFetch) {
    $delay = 2
    $ok = $false
    foreach ($attempt in 1..4) {
        # Same trap as `Invoke-Git`, and this is where it actually fired: `git fetch` reports
        # "From https://github.com/<owner>/<repo>" and its ref updates on stderr, which is a
        # SUCCESSFUL fetch describing itself. Under `Stop` that first line terminated the script
        # before a single file had been adopted.
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        # CAPTURED, NOT DISCARDED. This was `2>&1 | Out-Null`, which threw away the one thing
        # worth having. MEASURED ON THE BOX 2026-09-10, the whole output of a failed adoption:
        #
        #     fetch attempt 1 failed -- retrying in 2s
        #     fetch attempt 2 failed -- retrying in 4s
        #     fetch attempt 3 failed -- retrying in 8s
        #     fetch attempt 4 failed -- retrying in 16s
        #     fetch of origin/... failed after 4 attempts
        #
        # Four identical lines and a throw, naming no cause. Credentials, DNS, a proxy, a lock
        # held by another process and a permission fault on .git all look exactly the same, and
        # each has a different remedy. A deployment path that cannot say why it failed is the
        # same defect this desk keeps finding one level up: activity reported, outcome withheld.
        try { $out = & git -C $RepoRoot fetch origin $Branch 2>&1 | Out-String }
        finally { $ErrorActionPreference = $prev }
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
        Write-Host ("  fetch attempt {0} failed (exit {1}) -- retrying in {2}s"    `
                    -f $attempt, $LASTEXITCODE, $delay)
        foreach ($line in ($out -split "`r?`n" | Where-Object { $_ -match '\S' })) {
            Write-Host ("      git: {0}" -f $line)
        }
        Start-Sleep -Seconds $delay
        $delay = $delay * 2
    }
    if (-not $ok) {
        throw ("fetch of origin/$Branch failed after 4 attempts; git's own last words are " +
               "printed above. A permission fault on .git or on the working tree is the most " +
               "common cause on this box -- see docs/BOX_PERMISSIONS.md")
    }
}
$target = (Invoke-Git @("rev-parse", "FETCH_HEAD")).Trim()
$head   = (Invoke-Git @("rev-parse", "HEAD")).Trim()
Write-Host ("  head   {0}" -f $head.Substring(0, 12))
Write-Host ("  target {0}" -f $target.Substring(0, 12))

if ($head -eq $target) { Write-Host "  already at target -- nothing to adopt"; exit 0 }

# ---- 1. THE BOX'S OWN UNCOMMITTED STATE, COMMITTED AS ITSELF -----------------
# The sync commits state every fifteen minutes, so a dirty tree here means a pass
# was interrupted -- which is exactly the situation this script is run in. Those
# edits are the box's measurements and they are not disposable, so they are
# committed rather than parked: `git stash` in a tree another process is writing
# has already lost work on this desk once (R0423), and it stays banned.
# Only TRACKED modifications are staged, each named. Untracked files are left
# untouched -- a bare `git add -A` here would sweep logs, caches and secrets into
# the branch, and no adoption is worth that.
$dirty = @(Invoke-Git @("status", "--porcelain", "--untracked-files=no") |
           Where-Object { "$_" -match '\S' })
if ($dirty.Count -gt 0) {
    # `XY path`, or `R  old -> new` for a rename: the destination is what to stage.
    $dirtyPaths = @($dirty | ForEach-Object {
        $p = "$_".Substring(3)
        if ($p -match ' -> ') { $p = ($p -split ' -> ')[-1] }
        $p.Trim().Trim('"')
    })
    Write-Host ("  committing {0} uncommitted state path(s) first" -f $dirtyPaths.Count)
    foreach ($p in $dirtyPaths) { Invoke-Git @("add", "--", $p) -AllowFail | Out-Null }
    Invoke-Git @("commit", "-m", "Box state captured before release adoption") -AllowFail | Out-Null
}

# ---- 2. WRITE EVERY CHANGED PATH IN PLACE ------------------------------------
# `core.quotePath=false` so paths arrive raw rather than C-quoted, and NOT `-z`:
# PowerShell captures a child process's stdout as text split on newlines, so a
# NUL-delimited stream arrives as one opaque string and the parse depends on NUL
# surviving the marshalling. NTFS forbids control characters in filenames, so on
# this box one record per line is exactly safe.
$records = @(Invoke-Git @("-c", "core.quotePath=false", "diff", "--name-status", "HEAD", $target) |
             ForEach-Object { "$_" } | Where-Object { $_ -match '\S' })

# WHAT THIS BOX HAS WRITTEN SINCE IT DIVERGED. Measured against the merge base, AFTER step 1,
# so the state that was still uncommitted a moment ago counts as the box's. A state path in
# this set is live evidence and is kept; one outside it is an input origin wrote for the box.
# No merge base (unrelated histories) means nothing can be told apart, and the safe reading of
# "cannot tell" is that every state path is the box's.
$boxTouched = @{}
# Paths the box ADDED since the merge base (status A): a state file only this box has ever held.
# Origin cannot have "dropped" what it never tracked, so such a path is never untracked below;
# it falls through to the kept-by-box rule like any other box-written state.
$boxAdded = @{}
$mergeBase = (Invoke-Git @("merge-base", "HEAD", $target) -AllowFail | ForEach-Object { "$_" } |
              Where-Object { $_ -match '\S' } | Select-Object -First 1)
if ($mergeBase) {
    foreach ($rec in @(Invoke-Git @("-c", "core.quotePath=false", "diff", "--name-status", "$mergeBase", "HEAD") |
                       ForEach-Object { "$_" } | Where-Object { $_ -match '\S' })) {
        $cols = $rec -split "`t"
        $p = $cols[-1]
        $boxTouched[$p] = $true
        if ($cols[0] -match '^A') { $boxAdded[$p] = $true }
    }
}
function Test-KeptByBox {
    param([string] $Rel)
    if (-not (Test-StatePath $Rel)) { return $false }
    if (-not $mergeBase) { return $true }
    return $boxTouched.ContainsKey($Rel)
}

$written = 0; $added = 0; $removed = 0; $untracked = 0
$kept      = New-Object System.Collections.ArrayList
$unremoved = New-Object System.Collections.ArrayList
$staged    = New-Object System.Collections.ArrayList

# PROGRESS, BECAUSE SILENCE HERE IS INDISTINGUISHABLE FROM A HANG. Each path costs one
# `git cat-file` process, and on a checkout far behind its branch this loop can run to thousands
# of them -- minutes of no output on a box whose last two problems both presented as "it stopped".
# An operator watching a dead terminal reasonably kills it, and a half-adopted tree is the one
# state this script exists to avoid.
$total = 0
foreach ($rec in $records) { $total += if ($rec -match '^[RC]') { 2 } else { 1 } }
Write-Host ("  adopting {0} path(s) in place..." -f $total)
$seen = 0

foreach ($rec in $records) {
    $cols   = $rec -split "`t"
    $status = $cols[0]
    # R/C carry TWO paths (old, new); every other status carries one.
    if ($status -match '^[RC]') {
        $ops = @(@{ Kind = "D"; Path = $cols[1] }, @{ Kind = "A"; Path = $cols[2] })
    } else {
        $ops = @(@{ Kind = $status.Substring(0, 1); Path = $cols[1] })
    }
    foreach ($op in $ops) {
        $rel  = $op.Path
        $full = Join-Path $RepoRoot ($rel -replace '/', '\')
        if ($op.Kind -eq "D" -and (Test-StatePath $rel) -and -not $boxAdded.ContainsKey($rel)) {
            # ORIGIN STOPPED TRACKING A STATE PATH, so it leaves the INDEX and only the index.
            # a4bd8663 (2026-09-06) untracked desks/mt5/logs/ -- seventeen console logs and the
            # supervisor's pid/state/marker -- because running hunts hold them open and every
            # merge on the box died on `unable to unlink old ... signal_gate_console.txt`. The
            # box's HEAD still tracks them, so they arrive here as D ops, and either old branch
            # was wrong: [System.IO.File]::Delete on an open handle throws, lands the path in
            # $unremoved, shows up as drift and REFUSES the adoption (exit 1, nothing sealed);
            # while a box-modified one was KEPT tracked, `-s ours` recorded the deletion as
            # merged, and the next push re-tracked an ignored log on origin -- the loop the
            # upstream deletion had just closed. `git rm --cached` issues no unlink: the bytes
            # stay on disk as the box's untracked (now ignored) evidence, HEAD stops listing the
            # path exactly as the target does, and the verify gate below sees no difference.
            # Deliberately NOT added to $staged: a later `git add --all -- <path>` would re-add
            # any copy .gitignore does not cover. Code deletions still take the branch below.
            # --ignore-unmatch BECAUSE THE RETRY MUST BE ABLE TO SUCCEED (2026-09-09). Without it
            # this call fatals -- "pathspec did not match any files", rc=128 -- on a path that is
            # ALREADY out of the index, which is precisely what a previous run of this script
            # leaves behind. Measured on the box: the first adoption untracked several hundred
            # desks/mt5/data/intelligence/**/discoveries_*.json, failed later on ten paths whose
            # ACL it could not write, and every retry after that reported those same hundreds as
            # [FAIL] rc=128 and refused to seal -- each attempt failing on exactly the work the
            # attempt before it had completed. The desired end state here is "not in the index",
            # and a path that is already there has reached it. Nothing is swallowed: a path that
            # IS in the index and will not drop still returns non-zero and still lands in
            # $unremoved, which is the case the block below exists for.
            Invoke-Git @("rm", "--cached", "--quiet", "--ignore-unmatch", "--", $rel) -AllowFail |
                Out-Null
            if ($LASTEXITCODE -ne 0) {
                # Not swallowed: an index that will not drop the path (staged content differing
                # from both the file and HEAD) leaves it in HEAD, and the verify gate must see
                # that rather than a count that says it was handled.
                Write-Host ("  [FAIL] {0}: git rm --cached rc={1}" -f $rel, $LASTEXITCODE)
                [void]$unremoved.Add($rel)
                $seen++
                continue
            }
            $untracked++
            $seen++
            continue
        }
        if (Test-KeptByBox $rel) {
            # The box's own measurement. Not written, not deleted, not staged: it stays
            # exactly as the organ that produced it left it, and travels to origin on the
            # next push.
            [void]$kept.Add($rel)
            $seen++
            continue
        }
        if ($op.Kind -eq "D") {
            # The one operation that CANNOT avoid an unlink. If the entry is the
            # damaged one, it stays -- and it is reported, never swallowed.
            try {
                if (Test-Path -LiteralPath $full) { [System.IO.File]::Delete($full) }
                $removed++
            } catch {
                [void]$unremoved.Add($rel)
                continue
            }
        } else {
            try {
                Write-InPlace -Full $full -Bytes (Get-WorktreeBytes -Rev $target -Path $rel)
                if ($op.Kind -eq "A") { $added++ } else { $written++ }
            } catch {
                Write-Host ("  [FAIL] {0}: {1}" -f $rel, $_.Exception.Message)
                [void]$unremoved.Add($rel)
                continue
            }
        }
        [void]$staged.Add($rel)
        $seen++
        if ($seen % 250 -eq 0) {
            Write-Host ("    {0}/{1} ..." -f $seen, $total)
        }
    }
}
Write-Host ("  wrote {0} modified, {1} added, {2} deleted in place; {3} state path(s) origin no longer tracks untracked here (left on disk)" -f $written, $added, $removed, $untracked)
if ($kept.Count -gt 0) {
    Write-Host ("  kept {0} state path(s) this box wrote since it diverged (the box's evidence wins; origin's copy is reverted by the next push):" -f $kept.Count)
    $kept | Select-Object -First 12 | ForEach-Object { Write-Host ("    {0}" -f $_) }
    if ($kept.Count -gt 12) { Write-Host ("    ... and {0} more" -f ($kept.Count - 12)) }
}

# ---- 3. STAGE BY NAME AND COMMIT ---------------------------------------------
# Chunked: a repository-sized pathspec list overruns the Windows command line,
# and the failure mode is a TRUNCATED add that commits part of the tree.
if ($staged.Count -gt 0) {
    for ($c = 0; $c -lt $staged.Count; $c += 200) {
        $chunk = @($staged.GetRange($c, [Math]::Min(200, $staged.Count - $c)))
        $addArgs = @("add", "--all", "--") + $chunk
        Invoke-Git $addArgs | Out-Null
    }
}
# THE COMMIT DOES NOT DEPEND ON $staged. The index also carries the `rm --cached` removals
# above, and an adoption whose only change is untracking state origin dropped has nothing in
# $staged at all -- nested here, those removals were never committed, so the verify below
# still saw the path in HEAD and refused. `diff --cached` lists both kinds.
$pending = @(Invoke-Git @("diff", "--cached", "--name-only") |
             ForEach-Object { "$_" } | Where-Object { $_ -match '\S' })
if ($pending.Count -gt 0) {
    Invoke-Git @("commit", "-m",
        ("Adopt {0} in place; NTFS entry corruption blocks unlink" -f $target.Substring(0, 12))) | Out-Null
    Write-Host ("  committed {0} path(s)" -f $pending.Count)
}

# ---- 4. VERIFY BEFORE RECORDING ----------------------------------------------
# This is the gate that makes step 5 safe. `merge -s ours` writes down a parent
# and keeps THIS tree; if this tree still differs from the target, recording it
# would bury the difference under a commit that claims to contain it. So the
# difference must be empty, or the merge is not recorded at all.
# The kept state paths are the one sanctioned difference: they differ from the
# target BY DESIGN (the box's evidence over origin's older copy), and step 5
# records exactly that -- the next push carries them up, it does not bury them.
$drift = @(Invoke-Git @("-c", "core.quotePath=false", "diff", "--name-only", "HEAD", $target) |
           ForEach-Object { "$_" } | Where-Object { $_ -match '\S' } |
           Where-Object { -not (Test-KeptByBox $_) })
if ($drift.Count -gt 0) {
    Write-Host ""
    Write-Host ("REFUSING to record the merge: {0} path(s) still differ from the target." -f $drift.Count)
    $drift | Select-Object -First 20 | ForEach-Object { Write-Host ("    {0}" -f $_) }
    if ($unremoved.Count -gt 0) {
        Write-Host ""
        Write-Host ("{0} path(s) could not be written or unlinked -- the corrupt entries:" -f $unremoved.Count)
        $unremoved | ForEach-Object { Write-Host ("    {0}" -f $_) }
        Write-Host "Repair with:  chkdsk C: /F   (then reboot), and run this again."
    }
    exit 1
}

# ---- 5. RECORD THE MERGE -----------------------------------------------------
# Without this the branch is adopted but not DESCENDED from the target, so every
# later `Sync-Pull` sees itself behind, tries to merge, and dies on the same
# entry again -- an adoption that has to be repeated every hour is not an
# adoption. `-s ours` touches no file, which is why it survives the corruption.
Invoke-Git @("merge", "-s", "ours", $target, "-m",
             "Record the release merge; tree adopted in place by Adopt-Release") | Out-Null

Write-Host ""
Write-Host ("ADOPTED. HEAD is now {0} and descends from {1}; code == target, {2} state path(s) kept as the box's." -f `
            (Invoke-Git @("rev-parse", "--short", "HEAD")).Trim(), $target.Substring(0, 12), $kept.Count)
Write-Host "The next sync will fast-forward instead of failing on the merge."
Write-Host ""
Write-Host "Next:  python desks\mt5\mt5desk\release_identity.py"
Write-Host "       python desks\mt5\scripts\check_gold_live.py"
exit 0

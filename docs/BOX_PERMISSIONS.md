# The trading box's NTFS permissions, and the two outages they caused

> ANNEX. Not standing orders. This records what was measured on the Contabo box on 2026-09-10 and
> the exact commands that fixed it, because both failures presented as something else entirely
> and the second one cost a second round trip to diagnose.

## What happened

The box had not sealed a release in weeks. Three separate symptoms, one cause underneath:

```
error: cannot open '.git/FETCH_HEAD': Permission denied
```

`FETCH_HEAD` could not be written, so `git rev-parse FETCH_HEAD` returned a STALE commit and
`Adopt-Release.ps1` adopted a target 27 commits behind the branch while reporting success. The
adoption was working perfectly against the wrong target.

```
fetch attempt 1 failed -- retrying in 2s     (x4, then a throw)
```

After the `.git` ACLs were repaired the same fault moved: `git fetch` itself began failing with
no stated reason, because the retry loop discarded git's stderr (`2>&1 | Out-Null`). Fixed in
the same commit as this file -- the loop now prints git's own words on every failed attempt.

```
compute_ledger: row for 'refresh_bars' NOT written
(PermissionError: [Errno 13] Permission denied: 'C:\opt\quant\desks\mt5\data\compute_ledger.jsonl')
```

And this is the one that explains why the first repair was not enough. **The fix was applied to
`.git` only.** The working tree kept the old ACLs, so every organ that writes evidence --
the compute ledger, the sync marker, the intelligence donations, the tape -- was still denied.
A box that can fetch and adopt but cannot write its own records is not a working box; it is a
box whose research output is silently discarded, which reads downstream as "the miners found
nothing".

## The repair, whole

Run in an **elevated** PowerShell (right-click -> Run as administrator). `takeown` on `.git`
alone is the half-fix that produced the third symptom above.

```powershell
takeown /F C:\opt\quant /R /D Y | Out-Null
icacls C:\opt\quant /grant "*S-1-5-32-544:(OI)(CI)F" /T /Q
```

`*S-1-5-32-544` is the well-known SID of the local Administrators group. **Use the SID, not a
name.** `%USERNAME%` is cmd syntax and expands to nothing in PowerShell; `$env:USERNAME` works
but resolves to whatever account happens to be typing, which is not necessarily the account the
scheduled tasks run as. Both produce:

```
No mapping between account names and security IDs was done.
Successfully processed 0 files; Failed processing 1 files
```

which is a failure that prints a success line first.

## Then verify, in this order

```powershell
cd C:\opt\quant
git fetch origin claude/llm-auto-upgrade-verify-gcjac3   # real error, if any, unfiltered
git rev-parse FETCH_HEAD                                  # must equal origin's tip
powershell -ExecutionPolicy Bypass -File desks\mt5\scripts\Adopt-And-Seal.ps1
```

A sealed adoption prints a target equal to the branch tip and does **not** print
`REFUSING to record the merge`.

## Two things that make this worse than it looks

**Only one writer at a time.** `Adopt-And-Seal.ps1` holds the named mutex `Local\MT5-GitWriter`
for its whole pass and `sync_shadow_to_git.ps1` races for `.git/index.lock`. A second terminal
running the hourly cycle, or an editor with the repo open, can hold a lock that presents as a
fetch failure. Close the others before adopting.

**A bare `git fetch` before the script is not harmless.** `Adopt-Release.ps1` fetches itself, with
four retries, INSIDE the mutex. Running `git fetch` first does the same work outside it, and that
is what produced the original `FETCH_HEAD: Permission denied` -- two writers, one file. Run the
script alone.

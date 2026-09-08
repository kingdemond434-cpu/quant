# Box recovery runbook — 2026-09-08

The desk stopped at **02:20 UTC** when C: hit 0.5GB free. Two code fixes are already on
`claude/llm-auto-upgrade-verify-gcjac3` (the branch the box pulls):

* `stall_watch.ps1` — an 8-tier disk ladder that escalates instead of asking for a person
* `desk_self_heal.py` — `check_disk_headroom` + `check_research_cadence` in the noon lane

**Neither can apply itself while the box is wedged**, because a full disk stops the pull and the
scheduled tasks alike. Everything below is run on the box, in an **elevated PowerShell**.

---

## 1 — See what is actually eating the disk

```powershell
Get-PSDrive C | Select-Object @{n='FreeGB';e={[math]::Round($_.Free/1GB,2)}}

Get-ChildItem C:\opt\quant -Directory |
  ForEach-Object { [PSCustomObject]@{ Path=$_.Name
    GB=[math]::Round(((Get-ChildItem $_.FullName -Recurse -File -EA SilentlyContinue |
        Measure-Object Length -Sum).Sum/1GB),2) } } |
  Sort-Object GB -Descending | Select-Object -First 12
```

## 2 — Emergency prune (safe pools only)

Run as one block. **Nothing here touches `data\tape`, `data\universe`, `data\secrets`, or the
RELEASE/manifest chain** — the tick tape is unrecoverable and is worth more than the disk.

```powershell
Get-ChildItem C:\opt\quant -Recurse -Directory -Filter __pycache__ -EA SilentlyContinue |
  Remove-Item -Recurse -Force -EA SilentlyContinue
Remove-Item 'C:\opt\quant\desks\mt5\reports\gauntlet_cache\*' -Recurse -Force -EA SilentlyContinue
Remove-Item 'C:\opt\quant\desks\mt5\data\free_data_cache\*'   -Recurse -Force -EA SilentlyContinue
Remove-Item 'C:\opt\quant\desks\mt5\data\pf_allocator_cache\*' -Recurse -Force -EA SilentlyContinue
Get-ChildItem 'C:\opt\quant\desks\mt5\logs' -File -Recurse -EA SilentlyContinue |
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-3) } | Remove-Item -Force -EA SilentlyContinue
Remove-Item "$env:TEMP\*" -Recurse -Force -EA SilentlyContinue
Get-PSDrive C | Select-Object @{n='FreeGB';e={[math]::Round($_.Free/1GB,2)}}
```

Target is **≥5GB**. If it is still under, step 1's listing says where the growth is; do not
delete anything it names under `data\tape` or `data\universe` — come back and ask instead.

## 3 — Pull the fixes

```powershell
cd C:\opt\quant
git status --short
git fetch origin claude/llm-auto-upgrade-verify-gcjac3
git pull --ff-only origin claude/llm-auto-upgrade-verify-gcjac3
git log --oneline -3
```

You should see `Noon self-heal checks the RESOURCE and the CADENCE` and
`Disk watchdog heals itself`.

**If `git status` shows local changes and the pull refuses: stop and paste the output.**
Do NOT `git stash` — this is a shared tree and a stash here has silently eaten work before.

## 4 — Restart the dead tasks

```powershell
Get-ScheduledTask -TaskName 'MT5-*' | ForEach-Object {
  $i = Get-ScheduledTaskInfo $_
  [PSCustomObject]@{ Task=$_.TaskName; State=$_.State; Last=$i.LastRunTime; Result=$i.LastTaskResult } } |
  Format-Table -AutoSize

Get-ScheduledTask -TaskName 'MT5-*' | Where-Object State -eq 'Disabled' | Enable-ScheduledTask
'MT5-StallWatch','MT5-Hourly','MT5-Gauntlet','MT5-Shadow' |
  ForEach-Object { Start-ScheduledTask -TaskName $_ -EA SilentlyContinue }
```

`Result` is the one to read: `0` is success, `267009` is still running, anything else is a
failing task.

## 5 — Verify the desk is alive again

```powershell
Get-Content C:\opt\quant\desks\mt5\data\stall_watch.json
(Get-Item C:\opt\quant\desks\mt5\data\gateway_state.json).LastWriteTime
python C:\opt\quant\scripts\build_zentech_state.py
```

Then from anywhere:

```bash
curl -sI https://dash.quanttt.xyz/desk_state.json | grep -i last-modified
```

`last-modified` must be within the last hour. Until it is, the desk is still down.

## 6 — Why the gold sleeves are armed but have never filled

The four `XAUUSD.asia` sleeves have been `LIVE` in the registry since **2026-09-04 02:56** and
`LIVE_MANIFEST.jsonl` shows `armed: true, lot: 0.06, n_brackets: 3`. But
`matched_fills: 0`, `open_trades: []`, `margin: 0.0`, and the equity curve is 179 flat samples
at €752.51. **Armed is not filled.**

The lead: that same manifest line records `equity: 21127.01` while the account holds **€752.51**
— a 28× mismatch. If the bracket was sized against €21k, `0.06 lot × 3 brackets` on a €752
account is very likely rejected for margin, which produces exactly this signature.

```powershell
Get-Content C:\opt\quant\desks\mt5\data\gateway_state.json

# what the terminal said when it tried to send
Get-ChildItem "$env:APPDATA\MetaQuotes\Terminal" -Recurse -Filter *.log -EA SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 5 |
  ForEach-Object { Write-Host "`n== $($_.FullName)"; Get-Content $_.FullName -Tail 80 |
    Select-String -Pattern 'reject|no money|invalid volume|not enough|failed|margin' }
```

Paste whatever those lines say — that is the answer to "why has nothing filled", and it is the
one thing that cannot be read from off the box.

## 7 — Not a command: the E8 decision

Buy **$100k, static 10% DD, 10% target, 0.30–0.35% risk per trade**, and confirm before paying
whether it carries a **2% daily profit cap** — the cap costs ~22 points of pass probability
(86.7% → 64.8%) and is worth more than any other setting on the page. Never size past 0.35% on
that account: pass probability falls off a cliff at 0.45% (83% → 30%) when daily risk outgrows
the 2.5% daily loss limit.

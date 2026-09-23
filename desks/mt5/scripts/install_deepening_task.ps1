# INSTALL THE DEEPENING QUEUE'S READER (2026-09-03).
#
# THE GAP, MEASURED. `data/hypotheses/miner_deepening_queue.json` held 705 tasks, every one at
# status None, and its own `consumer` field named who was supposed to work them: "hourly/daily
# research brains must recover a falsifiable rule or reject". A grep for that filename across
# every module on this desk returned exactly ONE hit -- the line in miner_candidate_compiler.py
# that DEFINES the write path. Nothing read it. It was a write-only queue.
#
# WHAT THAT COST, in the compiler's own accounting for a single hour: 1,151 evidence rows in,
# 370 executable candidates out, 705 into this queue. Of 39 miner sources only four converted
# at all (broker_swaps 248/248, forexfactory 44->107, ff_calendar_vintage 114->6, seasonality
# 79->2). The other 35 -- including the entire world crawler, 50 rows and 0 candidates -- put
# everything here. The desk crawls the world hourly and drops most of what it finds into a file
# with no reader.
#
# CADENCE. Hourly, one hour behind nothing in particular: the queue is rebuilt by the compiler
# each hour and this reader is idempotent against it, because a task's identity is a hash of its
# own (source, url, title) rather than its position, and every decision -- including a rejection
# -- is appended to data/hypotheses/deepening_worked.jsonl. A task is therefore paid for ONCE.
# Re-running an hour whose tasks are all decided costs nothing and calls no seat.
#
# WHAT BOUNDS THE SPEND. Three things, and none of them is trust. `libs.ops.llm_seat` carries the
# monthly cap and the spend ledger; --limit caps the tasks per run (25 by default, so the 705
# backlog drains over about a day rather than in one afternoon at the month's expense); and the
# worked-ledger stops any task being billed twice. The ExecutionTimeLimit below is the last stop.
#
# WHAT IT MAY NOT DO. It cannot invent a rule. Every extraction must quote a verbatim span from
# the row's own text, and the quote is CHECKED against that text here rather than trusted -- a
# model that cannot ground its answer is rejected as a fabrication. Recovered fields are written
# onto a copy of the original row and passed back through `compile_row`, so this adds no second
# admission path into the candidate store: it can only cause the existing door to open.
#
# Idempotent: re-running replaces the task rather than erroring. Takes its principal from
# MT5-MoatSilver rather than hardcoding a SID, so the MT5 organs never drift apart in identity.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File install_deepening_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-Deepening'
$Root     = 'C:\opt\quant\desks\mt5'
$Log      = 'C:\opt\quant\desks\mt5\logs\MT5-Deepening.log'

$template = Get-ScheduledTask -TaskName 'MT5-MoatSilver'
$userId   = $template.Principal.UserId

$action = New-ScheduledTaskAction -Execute 'cmd.exe' `
    -Argument ('/d /s /c "cd /d {0} && py -3 research\deepening_worker.py --limit 25 >> {1} 2>&1"' -f $Root, $Log)

# :35 past the hour: the compiler rebuilds the queue near the top of the hour, so this reads a
# queue that has just been refreshed rather than racing it.
$start = [datetime]::Today.AddHours(1).AddMinutes(35)
$trigger = New-ScheduledTaskTrigger -Once -At $start
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Hours 1)).Repetition

$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType S4U -RunLevel Highest

# StartWhenAvailable so an hour lost to a reboot is caught up rather than silently skipped.
# MultipleInstances IgnoreNew because two readers working the same queue would bill the overlap
# twice -- the worked-ledger dedupes across runs, not within a race.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -MultipleInstances IgnoreNew

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Work the miner deepening queue: recover a falsifiable rule from the source text or reject it, then re-compile through compile_row. Installed 2026-09-03: the queue held 705 tasks and had no reader at all, stranding the yield of 35 of 39 miner sources including the whole world crawler.' | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2}" -f $t.TaskName, $t.State, $t.Triggers[0].Repetition.Interval

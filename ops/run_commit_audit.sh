#!/usr/bin/env bash
# COMMIT AUDIT -- point the independent seats at the desk's OWN recent work.
#
# THE GAP THIS CLOSES (principal 2026-08-01): "no independent validation, no second pair of eyes --
# every check was written by the same mind that wrote the code." The desk already owns 13 seats
# across 11 labs (deepseek, google, meituan, minimax, moonshotai, nvidia, openai, qwen,
# thinkingmachines, x-ai, z-ai) -- genuine independence, because a different model family has
# different blind spots, whereas a second checker by the same author inherits the first one's.
# What was MISSING is that nothing ever pointed those seats at the desk's own commits. They
# reviewed research findings and code on rotation; nobody reviewed the changes themselves.
#
# DEGRADES HONESTLY WHEN UNFUNDED. OpenRouter is out of credit, so this will report BLOCKED and
# exit rather than pretending. It is installed now precisely so the whole loop works the moment
# credit lands, with nothing further to wire.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; a commit that changes this file's LENGTH while it is running resumes execution inside
# a line. Measured on 63680c05 (ops/run_frontier_rotation.sh): comment text ran as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. Only the exit INSIDE the
# group ends the process before bash reads another byte. Do not unwrap; add nothing after `}`.
{
mkdir -p data/cro_ai_logs docs/research
LOG="data/cro_ai_logs/commit_audit_$(date -u +%Y%m%dT%H%M).log"
DIFF="docs/research/recent_changes.md"

# Build the payload the mission reads. Patches are truncated per commit: a seat that receives
# 40k lines reviews none of them, and the first ~400 lines of a diff carry the design decision.
.venv/bin/python - "$DIFF" <<'PYEOF'
import subprocess, sys
from datetime import UTC, datetime
from pathlib import Path

out = Path(sys.argv[1])
shas = subprocess.run(["git", "log", "--since=24.hours", "--format=%H"],
                      capture_output=True, text=True).stdout.split()
parts = [f"# Desk changes, last 24h (generated {datetime.now(tz=UTC).isoformat()[:19]}Z)\n",
         f"\n{len(shas)} commit(s). Patches truncated to 400 lines each -- a seat that receives\n"
         "40k lines reviews none of them, and the design decision is almost always in the first\n"
         "few hundred.\n"]
for sha in shas[:25]:
    msg = subprocess.run(["git", "log", "-1", "--format=%h %s%n%b", sha],
                         capture_output=True, text=True).stdout.strip()
    patch = subprocess.run(["git", "show", "--stat", "--patch", sha],
                           capture_output=True, text=True).stdout.splitlines()
    parts.append(f"\n\n---\n\n## {msg}\n\n```diff\n" + "\n".join(patch[:400]) + "\n```\n")
out.write_text("".join(parts), "utf-8")
print(f"commit-audit payload: {len(shas)} commit(s) -> {out}")
PYEOF

if ! brain_auth_check; then
    echo "$(date -u +%FT%TZ) commit-audit: auth unavailable -- next run resumes" >> "$LOG"
    exit 1
fi

echo "=== commit-audit start $(date -u) ===" >> "$LOG"
# INBOX is the panel's ARTIFACT of a real reply: run_external_panel.py writes it only inside
# `if ok:` where ok = seats that returned a response (scripts/run_external_panel.py:419-421).
# Stamp its pre-run mtime so "did any seat actually answer?" is decided by a file that changed,
# never by an exit code.
INBOX="docs/research/panel_inbox.md"
INBOX_BEFORE=$(stat -c %Y "$INBOX" 2>/dev/null || echo 0)

# The panel takes the mission by name and fans it across every funded seat. If OpenRouter has no
# credit each seat 402s and the panel reports it -- BLOCKED, not broken, and it fires on the next
# funded run with no further wiring.
PANEL_MISSION=commit_audit timeout 2400 .venv/bin/python scripts/run_external_panel.py \
    >> "$LOG" 2>&1
RC=$?
echo "=== commit-audit exit $RC at $(date -u) ===" >> "$LOG"

# Every finding becomes a ledger row so the owed-work worker ACTS on it. An independent review
# nobody acts on is theatre -- the same failure the recommendation ledger was built to end.
#
# GATED ON THE ARTIFACT, NOT ON RC (fixed 2026-08-01, first run, by the bug's own output). This
# read `if [ "$RC" = "0" ]`, and run_external_panel.py exits 0 when EVERY SEAT FAILS -- it prints
# "zero responses" and returns cleanly. So the very first run rowed R0341 claiming "independent
# seats reviewed the last 24h of desk commits" after tencent 404'd, cohere and nvidia-nano 400'd
# and nvidia threw KeyError('choices'): 0/4 substantive, no inbox written, nothing reviewed by
# anybody. That is the UNMEASURED-REPORTED-AS-OK class (L1.40) pointed at the conversion queue --
# an organ manufacturing one un-actionable row per day into a backlog already arriving ~4x faster
# than it drains (L1.28b), and each phantom row costs a human triage slot to discover it is empty.
# REFUSAL IS AN OUTCOME WITH ITS OWN VOCABULARY (L1.41 condition 1): no reply => NO-QUORUM, said
# out loud in the log, and NO row. Fail-closed is right here -- a missing row is visible as an
# organ that produced nothing, while a phantom row is invisible until someone spends the slot.
INBOX_AFTER=$(stat -c %Y "$INBOX" 2>/dev/null || echo 0)
SUBST=$(grep -oE 'panel: [0-9]+/[0-9]+ substantive' "$LOG" | tail -1 | grep -oE '[0-9]+/[0-9]+' || true)
if [ "$RC" = "0" ] && [ "$INBOX_AFTER" -gt "$INBOX_BEFORE" ]; then
    .venv/bin/python scripts/recommendations.py add --source panel \
        --summary "COMMIT AUDIT $(date -u +%F): independent seats (${SUBST:-count unparsed} substantive) reviewed the last 24h of desk commits -- triage every finding in $LOG, row the real ones, and reject the rest with reasons" \
        >> "$LOG" 2>&1 || echo "commit-audit: LEDGER WRITE FAILED -- findings exist in $LOG and are UNROWED" >> "$LOG"
else
    echo "commit-audit: NO-QUORUM (rc=$RC, substantive=${SUBST:-unparsed}, inbox unchanged) -- zero seats replied, so there is NOTHING to triage and NO row is owed. This is the honest degraded outcome, not a failure to convert." >> "$LOG"
fi

exit $?
}

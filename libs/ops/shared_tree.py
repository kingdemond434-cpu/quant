"""SHARED-CHECKOUT DETECTOR (R0423) -- two live sessions in one worktree corrupt each other.

THE FAILURE, THREE TIMES RECORDED. A sibling session runs a broad `git commit` between another
session's `git add` and its `git commit`, sweeping the staged files into a commit whose message is
about something else entirely. The CODE survives; the RATIONALE is destroyed -- and under L1.16 an
edge or a repair is only durable if its mechanism is understood, which is what a commit message is
for. The live instance: commit d971a08 is titled "R0261: the composite discovery rank is
log_growth wearing nine other names" and contains libs/execution/carry_accounting.py,
run_cashcarry_executor.py, run_live_combined.py and tests/execution/test_carry_accounting.py --
the $4,807 futures-leg reporting repair. `git blame` on that repair now points a future reader at
an unrelated subject line.

Prior instances in desk memory: "a sibling commit -a swept my staged ledger" and "a sibling
git checkout'd the tree off my branch MID-TASK".

THE PER-INSTANCE FIX WAS ALWAYS "RE-COMMIT", AND IT NEVER GENERALISED. The generalisation is that
concurrent sessions must not share a worktree: each takes `git worktree add -b <branch>` at
session start and merges back. This module is the cheap detector that makes the violation VISIBLE
at the moment the decision is still free -- session start.

DELIBERATELY ADVISORY, NEVER BLOCKING. A governance fault must not stop the desk (L1.37), and a
false positive that refused to let a session start would be far more expensive than the defect it
prevents. It reports; the human or the session decides.

WHY THE BRACKET TRICK. `pgrep -f claude` matches the checker's own argv and any sibling's system
prompt, which is how this desk previously reported a dead cycle as RUNNING for 80 minutes. Every
pattern here is written so it cannot match the process doing the matching.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

#: Bracket-trick patterns for a live agent session. `clau[d]e` cannot match this process's own
#: argv, because the literal string in OUR argv is `claude` and the regex demands the bracket
#: class -- the standard idiom, and the reason a self-match cannot happen here.
_SESSION_PATTERNS = (r"clau[d]e", r"cod[e]x")


def _ppid(pid: int) -> int | None:
    try:
        st = Path(f"/proc/{pid}/stat").read_text("utf-8")
    except OSError:
        return None
    # comm (field 2) can contain spaces and parens, so split after the LAST ')' -- the standard
    # parse, same reason max_audit._proc_start does it this way.
    return int(st[st.rindex(")") + 2:].split()[1])


def _ancestors(pid: int, limit: int = 40) -> set[int]:
    """Ancestry of a LIVE pid, empty for one that does not exist.

    The first version added `pid` before checking it was real, so a vanished pid reported itself
    as its own ancestry -- a non-existent process claiming a lineage. Harmless in today's caller
    and wrong in a way the next caller would inherit.
    """
    out: set[int] = set()
    cur: int | None = pid
    while cur and cur > 1 and len(out) < limit:
        parent = _ppid(cur)
        if parent is None:
            break                         # cur does not exist: it contributes no ancestry
        out.add(cur)
        cur = parent
    return out


def _live_session_pids() -> list[int]:
    """Live agent sessions OTHER THAN THIS ONE'S OWN PROCESS TREE.

    MY OWN SUBAGENTS ARE NOT SIBLINGS, and counting them would make this fire on every session
    that ever spawned a helper -- a detector that cries wolf gets disabled (L1.37/L1.43), which
    would leave the real defect undetected forever. A subagent shares this worktree BY DESIGN and
    does not independently `git commit`; a sibling session is the one that can sweep staged files.
    The test is ancestry, not name: anything descended from a process in my own ancestor chain is
    mine.
    """
    pids: list[int] = []
    for pat in _SESSION_PATTERNS:
        try:
            r = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True, timeout=5)
        except (subprocess.SubprocessError, OSError):
            continue                      # no pgrep, or it died: UNMEASURED, handled by caller
        pids += [int(x) for x in r.stdout.split() if x.isdigit()]
    mine = _ancestors(os.getpid())
    return sorted({p for p in set(pids)
                   if _is_session(p) and not (_ancestors(p) & mine)})


def _is_session(pid: int) -> bool:
    """Is this pid an agent BINARY, rather than something whose cmdline merely says 'claude'?

    `pgrep -f` matches the whole command line, and every Bash tool invocation on this box is
    `/bin/bash -c source /home/quant/.claude/shell-snapshots/...` -- which contains `.claude` in a
    PATH and matched. Measured 2026-08-13: that alone produced 5 phantom "sessions" against 1 real
    one, a 5:1 false-positive rate on the first run. The desk has been here before with pgrep
    self-matching; the answer is the same both times -- match the EXECUTABLE, not the text.
    """
    try:
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except OSError:
        return False
    # Tolerate a wrapper: cron launches these as `timeout 3000 claude --effort max ...`.
    for tok in (t.decode("utf8", "replace") for t in argv[:3] if t):
        if Path(tok).name in ("claude", "codex"):
            return True
    return False


def _cwd_of(pid: int) -> Path | None:
    try:
        return Path(os.readlink(f"/proc/{pid}/cwd"))
    except OSError:
        return None                       # exited, or not ours to read


def _git_common_dir(cwd: Path) -> str | None:
    """The SHARED .git directory, which is what two worktrees of one repo have in common.

    NOT `rev-parse --git-dir`: for a linked worktree that returns the per-worktree
    `.git/worktrees/<name>` path, so two worktrees of the same repo would look like two different
    repos and this detector would report the safe case as safe for the wrong reason -- and, worse,
    would stay silent on the actual shared-checkout case only by accident. --git-common-dir is the
    one that is EQUAL across worktrees and DIFFERENT across repos, which is exactly the question.
    """
    try:
        r = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--git-common-dir"],
                           capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    p = Path(r.stdout.strip())
    return str((cwd / p).resolve() if not p.is_absolute() else p.resolve())


def detect(_pids: list[int] | None = None) -> dict[str, Any]:
    """Are two or more live sessions working in the SAME worktree?

    Returns a report with status SHARED / CLEAR / UNMEASURED. UNMEASURED is a real answer and is
    never collapsed into CLEAR (L1.28a): "no other session is in my tree" and "I could not see
    whether one is" are different facts, and only one of them is safety.
    """
    pids = _live_session_pids() if _pids is None else _pids
    me = _git_common_dir(Path.cwd())
    if me is None:
        return {"status": "UNMEASURED", "n_sessions": len(pids),
                "detail": "this process is not inside a git worktree, or git is unavailable"}
    # A worktree is identified by its ROOT, not its cwd -- two sessions sitting in different
    # subdirectories of one checkout are still sharing that checkout.
    others: list[dict[str, Any]] = []
    unreadable = 0
    for pid in pids:
        cwd = _cwd_of(pid)
        if cwd is None:
            unreadable += 1               # COUNTED, not dropped (L1.60): a pid we cannot read is
            continue                      # not evidence of a clear tree
        common = _git_common_dir(cwd)
        if common == me:
            others.append({"pid": pid, "cwd": str(cwd)})
    # SAME REPO IS NOT SAME WORKTREE, and the difference IS the fix this law recommends. Two
    # sessions in two linked worktrees share a git_common_dir and cannot sweep each other's
    # staged files; that is the safe arrangement, so it must not report as the defect.
    shared = [o for o in others if _same_worktree(Path(o["cwd"]))]
    status = "SHARED" if shared else ("UNMEASURED" if unreadable and not others else "CLEAR")
    return {
        "status": status,
        "git_common_dir": me,
        "n_sessions": len(pids),
        "n_unreadable_pids": unreadable,
        "same_repo": others,
        "same_worktree": shared,
        "detail": (
            f"{len(shared)} other live session(s) are in THIS worktree -- a broad `git commit` in "
            "either will sweep the other's staged files into an unrelated commit and destroy its "
            "rationale (R0423)" if shared else
            f"{len(others)} other session(s) share this repo but work in their own worktrees"
            if others else
            "no other live session detected in this repo"),
        "next_action": (
            "take your own worktree before touching the tree:\n"
            "    git worktree add -b <branch> ../qp-<branch> && cd ../qp-<branch>\n"
            "and merge back when done. NEVER `git stash` and NEVER `git commit -a` in a shared "
            "checkout." if shared else "none"),
    }


def _same_worktree(cwd: Path) -> bool:
    """Is `cwd` inside the SAME worktree as this process (not merely the same repo)?"""
    try:
        a = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
        b = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError):
        return False
    if a.returncode or b.returncode:
        return False
    return Path(a.stdout.strip()).resolve() == Path(b.stdout.strip()).resolve()

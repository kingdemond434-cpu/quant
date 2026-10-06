"""THE TEN VPS SHELL AGENT LANES, EACH ON THE NARROWEST ALLOWLIST ITS BRIEF NEEDS.

THE DEFECT. Ten ops/run_*.sh launchers called `claude -p ... <permission-bypass flag>`, handing
every tool -- any write, any command, any push, crontab, the secrets directory -- to seats whose
briefs say "RESEARCH ONLY (freeze): WRITE only to docs/research/* and data/* catalogs". The brief
was the only fence, and a brief is prose. PR #179 moved the Python organs off the flag and left
these ten on a shrink-only PENDING_SCOPING list in tests/ops/test_no_permission_bypass.py.

WHAT THIS MODULE DOES. It holds each lane's allowlist as DATA, read from that lane's own brief,
and builds the scoped `claude` arguments for it (libs/ops/agent_denials.scoped_claude_args):
stream-json output, `--allowedTools <the lane's rules>`, `--disallowedTools <NEVER_RULES + the
lane-self rules>`, and the allowlist stated at the end of the prompt so the seat knows its fence
before it walks into it. ops/scoped_claude.sh calls it, runs the lane, and pipes the stream through
scripts/record_agent_denials.py, which writes one `UNMEASURED / counts_as MISSED` row per refused
call into the lane's own log and into data/cro_ai_logs/agent_denials.jsonl. A refused step is a
MISSED step with a row; it is never dropped silently and never read as done.

THE THREE SHAPES, from the briefs:

  * RESEARCH DIGS (blindrediscovery, dataaxis, litminer, prospector, frontier, brain_hunter,
    video_hunter). Every brief carries the freeze: "WRITE only to docs/research/* and data/*
    catalogs. NEVER touch scripts/, libs/, the executor, risk rails, live/state files." So they get
    read-only tools, edits on exactly those paths plus docs/graveyard.md (the routing line every
    brief names for debunkings) and data/intelligence/** (the compiler's only intake, CLAUDE.md
    "SEAT OUTPUT GOES THROUGH"), the CLIs the briefs name (fetch_video_transcript, source_backlog_
    next, recommendations.py add, mine_gate), and a plain `git add` / `git commit -m` because the
    §33 lead tells every dig to "act, convert, commit". Web tools are UNRESTRICTED by domain for the
    digs that hunt the web -- their mandate is the whole public web (L1.34/L1.35), and a domain list
    would cut research generation. The blind-rediscovery dig gets NO web at all: its brief says
    "NO external search of any kind".
  * CODE-EDITING WORKERS (gap_wirer, recommendation_worker). Their briefs are repair and
    implementation -- "change the code, add or update a test, run ruff and the relevant pytest
    subset, commit". They get path-scoped edits over the code trees they must edit (scripts, libs,
    tests, ops, desks/mt5, docs, data, prompts and the root controllers), the test/lint/gate
    commands, any `scripts/*` CLI under the venv, and a plain commit. Not acceptEdits: an edit
    outside those trees is refused and recorded. gap_wirer alone also gets the user-unit verbs its
    STEP 0 needs (restart/start/enable a --user unit, daemon-reload) and a plain push, because its
    brief's reality gate is "deploy/wire -> FORCE ONE REAL RUN".
  * THE CRO CYCLE (cro_ai). One full daily research cycle against ops/CRO_CONSTITUTION.md: inbox
    triage, gap-register re-rank, improvement-inbox spec builds, the monthly prompt review (which
    rewrites an ops/*_prompt.txt), memory files, PRINCIPAL_ACTION.md, rollback_guard and run_ci.
    It gets the code-worker edit set, WebSearch/WebFetch (constitution: "WebSearch for NEW
    orthogonal mechanisms"), and the venv `scripts/*` CLIs.

WHAT EVERY LANE IS REFUSED, whatever its allowlist says: NEVER_RULES (secrets, the deadman rail,
the sealed doctrine, forced push/reset/stash/commit -a), blanket `git add -A/./--all`, and
LANE_SELF_RULES -- no lane may edit this module, the shared runner, the recorder, the denial
parser, the fence or its own launcher, because a seat that can rewrite its own allowlist has none.

    python -m libs.ops.vps_lane_scopes argv <lane> [--effort low]  < prompt   # NUL-separated
    python -m libs.ops.vps_lane_scopes rules <lane>                            # one rule per line
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass

from libs.ops.agent_denials import NEVER_RULES, READ_ONLY_RULES, scoped_claude_args, write_rules

#: Where every lane's refusal rows land (beside the lanes' own logs; the log gets the same rows
#: as human lines).
DENIAL_LEDGER = "data/cro_ai_logs/agent_denials.jsonl"

#: Files no lane may edit: the scope machinery itself and the ten launchers. Without this a code
#: lane could widen its own allowlist for its next run.
LAUNCHERS: tuple[str, ...] = (
    "ops/run_blindrediscovery_dig.sh", "ops/run_brain_hunter.sh", "ops/run_cro_ai.sh",
    "ops/run_dataaxis_dig.sh", "ops/run_frontier_miner.sh", "ops/run_gap_wirer.sh",
    "ops/run_litminer_dig.sh", "ops/run_prospector_dig.sh", "ops/run_recommendation_worker.sh",
    "ops/run_video_hunter.sh",
)
LANE_SELF_RULES: tuple[str, ...] = (
    *write_rules(
        "libs/ops/vps_lane_scopes.py", "libs/ops/agent_denials.py", "ops/scoped_claude.sh",
        "scripts/record_agent_denials.py", "tests/ops/test_no_permission_bypass.py",
        "tests/ops/test_vps_shell_agents_scoped.py", *LAUNCHERS,
    ),
    "Bash(git add -A:*)", "Bash(git add .:*)", "Bash(git add --all:*)",
    # gap_wirer may `git push origin <branch>`; NEVER_RULES' force-push prefixes start at
    # `git push --force`, so the forms that put the remote first are refused here too.
    "Bash(git push origin --force:*)", "Bash(git push origin -f:*)",
    "Bash(git push origin --force-with-lease:*)", "Bash(git push --force-with-lease:*)",
    "Bash(git push origin +*)", "Bash(git push origin --delete:*)",
)

LANE_DENIED: tuple[str, ...] = (*NEVER_RULES, *LANE_SELF_RULES)

PY = ".venv/bin/python"
WEB: tuple[str, ...] = ("WebSearch", "WebFetch")

#: The research freeze, verbatim in effect: docs/research/* and data/* catalogs, plus the two
#: routing targets every dig brief names outside docs/research (graveyard, seat intelligence).
DIG_WRITES: tuple[str, ...] = ("docs/research/**", "docs/graveyard.md", "data/*",
                               "data/intelligence/**")
DIG_BASH: tuple[str, ...] = (
    f"Bash({PY} scripts/source_backlog_next.py:*)",     # RESUME, DO NOT RESTART step (1)
    f"Bash({PY} scripts/recommendations.py add:*)",     # hand-off of every surviving card
    f"Bash({PY} scripts/mine_gate.py:*)",               # §33 conversion duty, re-read on demand
    "Bash(git add:*)", "Bash(git commit -m:*)",         # "act, convert, commit" (no push)
)
VIDEO_BASH: tuple[str, ...] = (f"Bash({PY} scripts/fetch_video_transcript.py:*)",)

#: Code trees a repair/implementation worker may edit. Wider than a dig by necessity, and still
#: never the secrets, the deadman rail, the sealed doctrine or the scope machinery (denied).
CODE_WRITES: tuple[str, ...] = (
    "scripts/**", "libs/**", "tests/**", "ops/**", "desks/mt5/**", "docs/**", "data/**",
    "prompts/**", "hourly_controller.py", "hourly_controller_with_discovery.py",
    "research_agenda.json", "research_state.json", "engineering_backlog.json",
)
CODE_BASH: tuple[str, ...] = (
    f"Bash({PY} -m pytest:*)", f"Bash({PY} -m ruff:*)", f"Bash({PY} -m mypy:*)",
    "Bash(.venv/bin/ruff:*)",
    f"Bash({PY} scripts/*)", "Bash(./ops/gates.sh:*)", "Bash(bash ops/gates.sh:*)",
    "Bash(git add:*)", "Bash(git commit -m:*)",
)


@dataclass(frozen=True)
class Lane:
    """One shell agent lane: its launcher, what its brief does, and its exact allowlist."""

    name: str
    launcher: str
    duty: str
    rules: tuple[str, ...]
    edits_code: bool = False


def _dig(name: str, launcher: str, duty: str, *, web: bool = True,
         extra_writes: Iterable[str] = (), extra_bash: Iterable[str] = ()) -> Lane:
    rules = [*READ_ONLY_RULES, *(WEB if web else ()),
             *write_rules(*DIG_WRITES, *extra_writes), *DIG_BASH,
             *(VIDEO_BASH if web else ()), *extra_bash]
    return Lane(name, launcher, duty, tuple(dict.fromkeys(rules)))


LANES: dict[str, Lane] = {lane.name: lane for lane in (
    _dig("blindrediscovery_dig", "ops/run_blindrediscovery_dig.sh",
         "fresh-eyes invention from the desk's OWN artifacts; no external search of any kind",
         web=False),
    _dig("dataaxis_dig", "ops/run_dataaxis_dig.sh",
         "free-data alternatives: data_universe_map.json + data_axis_watchlist.md"),
    _dig("litminer_dig", "ops/run_litminer_dig.sh",
         "literature deep-miner: mechanisms, replications, engine findings"),
    _dig("prospector_dig", "ops/run_prospector_dig.sh",
         "strategy prospector: prospector_watchlist.md + coverage"),
    _dig("frontier_miner", "ops/run_frontier_miner.sh",
         "regional / unified frontier dig (one region per invocation)"),
    _dig("brain_hunter", "ops/run_brain_hunter.sh",
         "WorldQuant BRAIN public corpus: operators, groupings, mechanisms"),
    _dig("video_hunter", "ops/run_video_hunter.sh",
         "video/transcript + extreme-return + practitioner intelligence",
         # The collector reads the YouTube key ITSELF; the seat never reads data/secrets.
         extra_bash=(f"Bash({PY} scripts/collect_youtube_corpus.py:*)",)),
    Lane("gap_wirer", "ops/run_gap_wirer.sh",
         "weekly repair: fix gap-register rows, wire unwired organs, force a real run",
         tuple(dict.fromkeys([
             *READ_ONLY_RULES, *write_rules(*CODE_WRITES), *CODE_BASH,
             "Bash(systemctl --failed:*)", "Bash(systemctl --user --failed:*)",
             "Bash(systemctl --user restart:*)", "Bash(systemctl --user start:*)",
             "Bash(systemctl --user enable:*)", "Bash(systemctl --user daemon-reload)",
             "Bash(git push origin:*)",
         ])), edits_code=True),
    Lane("recommendation_worker", "ops/run_recommendation_worker.sh",
         "owed-work worker: implement / reject / schedule every open ledger row and live defect",
         tuple(dict.fromkeys([*READ_ONLY_RULES, *write_rules(*CODE_WRITES), *CODE_BASH])),
         edits_code=True),
    Lane("cro_ai", "ops/run_cro_ai.sh",
         "the headless daily CRO research cycle against ops/CRO_CONSTITUTION.md",
         tuple(dict.fromkeys([*READ_ONLY_RULES, *WEB, *write_rules(*CODE_WRITES),
                              *CODE_BASH])),
         edits_code=True),
)}


def allowlist_note(lane: Lane) -> str:
    """The allowlist, stated in the prompt so the seat knows its fence before it reaches it."""
    return (f"\n\nTOOL ALLOWLIST FOR THIS LANE ({lane.name}; enforced by the CLI, no permission "
            f"bypass): {', '.join(lane.rules)}. ALWAYS REFUSED: {', '.join(LANE_DENIED)}. Any "
            "other tool or path is refused, and every refused call is recorded as UNMEASURED and "
            "counts as MISSED in this lane's log and in " + DENIAL_LEDGER + ". If a step of your "
            "brief needs something outside this list, do not reach for it: write that step into "
            "your session note as MISSED (needs <tool/path>) so the next run or the principal can "
            "open it, and carry on with every step you CAN do.")


def lane_args(name: str, prompt: str, *, effort: str | None = None) -> list[str]:
    """The arguments after `claude --append-system-prompt "$_DOCTRINE"` for one lane run."""
    lane = LANES[name]
    return scoped_claude_args(prompt + allowlist_note(lane), allowed=lane.rules, effort=effort,
                              denied=LANE_DENIED)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("argv", help="NUL-separated claude args; the prompt is read from stdin")
    a1.add_argument("lane", choices=sorted(LANES))
    a1.add_argument("--effort")
    a2 = sub.add_parser("rules", help="the lane's allowlist, one rule per line")
    a2.add_argument("lane", choices=sorted(LANES))
    a = ap.parse_args(argv)
    if a.cmd == "rules":
        print("\n".join(LANES[a.lane].rules))
        return 0
    prompt = sys.stdin.read()
    if not prompt.strip():
        print(f"vps_lane_scopes: empty prompt for {a.lane}", file=sys.stderr)
        return 2
    sys.stdout.write("\0".join(lane_args(a.lane, prompt, effort=a.effort or None)) + "\0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

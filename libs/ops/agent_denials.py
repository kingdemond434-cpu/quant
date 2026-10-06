"""A REFUSED TOOL CALL IS A MISSED STEP, AND IT MUST LEAVE A ROW.

THE DEFECT. The unattended agent lanes (the noon CRO pass on the box, the model-upgrade probes
on the VPS) run `claude -p`. In print mode a tool outside the allowlist is refused without a
prompt and the pass simply carries on: the step that needed WebFetch, or a plain `ls`, never ran,
and nothing on disk says so. The pass then reports its duties as if every step had been taken.
That is a silent MISSED, the same shape as a gate that never ran (L1.49), and absence must never
resolve to a clean verdict (L1.28a).

WHAT THIS MODULE DOES. It reads the CLI's `--output-format stream-json --verbose` stream and
finds every refused tool call. Three signals are read, measured on Claude Code 2.1.285
(2026-09-30), and unioned by `tool_use_id` so one refusal is one row:

  * a `{"type":"system","subtype":"permission_denied","tool_name":..,"tool_use_id":..}` event;
  * the final `{"type":"result", "permission_denials":[{tool_name, tool_use_id, tool_input}]}`;
  * a `tool_result` with `is_error: true` whose text is the CLI's refusal wording, which is the
    only signal left when the stream was cut off before its result event.

Each refusal becomes one ledger row, `verdict: UNMEASURED, counts_as: MISSED, reason:
permission_denied`, and `apply_to_duties` marks the CRO duty the step served as MISSED in the
pass's own review, so a duty whose step was refused can never read MET.

NOTHING SECRET LEAVES. The row carries a capped input summary with anything under data/secrets and
anything key-shaped replaced before the cap is applied. Never log a raw tool input.

The WebFetch allowlist lives in ONE data file, `ops/agent_webfetch_domains.json`; the box launcher
reads it directly and every Python consumer reads it through `load_webfetch_domains`.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.win_write import write_text_resilient

ROOT = Path(__file__).resolve().parents[2]
DOMAINS_FILE = ROOT / "ops" / "agent_webfetch_domains.json"

#: The input summary cap, in characters, applied AFTER scrubbing.
SUMMARY_CAP = 160

_HOST_RE = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
                      r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")

#: The CLI's own refusal wording in a tool_result. Narrow on purpose: a command that failed with
#: an OS "Permission denied" is a failed step, not a refused one, and must not be relabelled.
_REFUSAL_MARKERS = (
    "requested permissions to use",
    "haven't granted it yet",
    "permission to use",
    "was blocked. for security",
    "denied by your permission settings",
    "permission denied by",
)

_SECRETS_PATH = re.compile(r"[^\s'\"]*data[\\/]+secrets[^\s'\"]*", re.IGNORECASE)
#: (pattern, replacement), applied in order: bearer tokens and JWTs before `name: value`, so
#: `Authorization: Bearer <t>` never redacts only the word Bearer; query parameters keep their `?`.
_KEYISH: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]{8,}"), "Bearer [redacted]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-.]+"), "[redacted]"),
    (re.compile(r"(?i)([?&](?:key|token|apikey|api_key|access_token|servicekey|crtfc_key|"
                r"secret|sig|signature)=)[^&\s'\"]+"), r"\1[redacted]"),
    (re.compile(r"(?i)\b([A-Za-z0-9_]*(?:key|token|secret|passw(?:or)?d|auth|credential)"
                r"[A-Za-z0-9_]*)\s*[=:]\s*(?!\[redacted\])[^\s&'\"]+"), r"\1=[redacted]"),
    (re.compile(r"sk-(?:ant-)?[A-Za-z0-9_\-]{8,}"), "[redacted]"),
    (re.compile(r"\b(?:ghp|gho|ghs|github_pat|xox[abp])_[A-Za-z0-9_]{8,}"), "[redacted]"),
    (re.compile(r"\bAKIA[0-9A-Z]{12,}"), "[redacted]"),
    # Long opaque runs (hex / base64) are credentials far more often than they are useful text.
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), "[redacted]"),
    # Mixed-case-and-digit runs with no path separator, so a long repo path is never eaten.
    (re.compile(r"(?<![\w/.\-])(?=[A-Za-z0-9+_\-]*\d)(?=[A-Za-z0-9+_\-]*[A-Z])"
                r"(?=[A-Za-z0-9+_\-]*[a-z])[A-Za-z0-9+_\-]{32,}={0,2}"), "[redacted]"),
)


# ------------------------------------------------------------------ the one domain list
def load_webfetch_domains(path: Path | None = None) -> list[str]:
    """The WebFetch hosts from the one data file, validated. Raises ValueError on a bad host."""
    doc = json.loads((path or DOMAINS_FILE).read_text("utf-8"))
    out: list[str] = []
    for row in doc.get("domains", []):
        host = str(row.get("domain", "")).strip()
        if not _HOST_RE.match(host):
            raise ValueError(f"not a bare lowercase hostname: {host!r}")
        if not row.get("sources") or not str(row.get("terms", "")).strip():
            raise ValueError(f"{host}: a listed host must name its sources and its terms")
        if host not in out:
            out.append(host)
    return out


def webfetch_rules(path: Path | None = None) -> list[str]:
    """`WebFetch(domain:<host>)` allow rules, one per listed host."""
    return [f"WebFetch(domain:{h})" for h in load_webfetch_domains(path)]


# ------------------------------------------------------------------ scrubbing
def scrub(text: str) -> str:
    """Replace secrets paths and key-shaped substrings. Applied before any cap."""
    s = _SECRETS_PATH.sub("[secrets-path]", text)
    for rx, repl in _KEYISH:
        s = rx.sub(repl, s)
    return s


def summarize_input(tool: str, tool_input: Any, cap: int = SUMMARY_CAP) -> str:
    """A short, scrubbed, capped description of what the refused call tried to do."""
    if isinstance(tool_input, Mapping):
        for k in ("command", "url", "file_path", "path", "pattern", "notebook_path", "query"):
            v = tool_input.get(k)
            if isinstance(v, str) and v.strip():
                raw = v
                break
        else:
            try:
                raw = json.dumps(tool_input, sort_keys=True, default=str)
            except (TypeError, ValueError):
                raw = repr(tool_input)
    elif tool_input is None:
        raw = ""
    else:
        raw = str(tool_input)
    s = scrub(" ".join(raw.split()))
    return s if len(s) <= cap else s[: cap - 3] + "..."


# ------------------------------------------------------------------ the stream
@dataclass
class StreamSummary:
    """What one stream-json run said: its final text, and every refused tool call."""

    result_text: str | None = None
    result_seen: bool = False
    is_error: bool | None = None
    denials: list[dict[str, Any]] = field(default_factory=list)
    lines: int = 0
    malformed: int = 0
    non_json: list[str] = field(default_factory=list)


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(c.get("text", "")) for c in content if isinstance(c, Mapping))
    return ""


def _is_refusal(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _REFUSAL_MARKERS)


def parse_stream(lines: Iterable[str]) -> StreamSummary:
    """Parse a `claude -p --output-format stream-json --verbose` stream. Never raises on bad lines.

    A line that is not JSON is counted (`malformed` when it looked like JSON, `non_json` for the
    CLI's plain stderr) and skipped; one bad line must not hide the refusals around it.
    """
    out = StreamSummary()
    uses: dict[str, tuple[str, Any]] = {}
    found: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    last_text: str | None = None

    def _note(tid: str, **kv: Any) -> None:
        if tid not in found:
            found[tid] = {"tool_use_id": tid, "tool": None, "tool_input": None,
                          "message": None, "signals": []}
            order.append(tid)
        row = found[tid]
        for k, v in kv.items():
            if k == "signal":
                if v not in row["signals"]:
                    row["signals"].append(v)
            elif v is not None and row.get(k) in (None, ""):
                row[k] = v

    for raw in lines:
        line = raw.strip().lstrip("﻿")
        if not line:
            continue
        out.lines += 1
        if not line.startswith(("{", "[")):
            out.non_json.append(line[:300])
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            out.malformed += 1
            continue
        if not isinstance(ev, dict):
            out.malformed += 1
            continue
        kind = ev.get("type")
        if kind == "system" and ev.get("subtype") == "permission_denied":
            tid = str(ev.get("tool_use_id") or f"anon-{out.lines}")
            _note(tid, tool=ev.get("tool_name"), message=ev.get("message"), signal="system")
        elif kind == "result":
            out.result_seen = True
            out.is_error = bool(ev.get("is_error"))
            res = ev.get("result")
            out.result_text = res if isinstance(res, str) else out.result_text
            for d in ev.get("permission_denials") or []:
                if not isinstance(d, Mapping):
                    continue
                tid = str(d.get("tool_use_id") or f"anon-{out.lines}-{len(order)}")
                _note(tid, tool=d.get("tool_name"), tool_input=d.get("tool_input"),
                      signal="result")
        elif kind in ("assistant", "user"):
            msg = ev.get("message")
            content = msg.get("content") if isinstance(msg, Mapping) else None
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, Mapping):
                    continue
                if c.get("type") == "tool_use" and c.get("id"):
                    uses[str(c["id"])] = (str(c.get("name") or ""), c.get("input"))
                elif c.get("type") == "text" and kind == "assistant" and c.get("text"):
                    last_text = str(c["text"])
                elif (c.get("type") == "tool_result" and c.get("is_error")
                      and _is_refusal(_text_of(c.get("content")))):
                    tid = str(c.get("tool_use_id") or f"anon-{out.lines}")
                    _note(tid, message=_text_of(c.get("content")), signal="tool_result")

    if out.result_text is None and last_text is not None:
        out.result_text = last_text
    for tid in order:
        row = found[tid]
        name, inp = uses.get(tid, (None, None))
        if not row["tool"]:
            row["tool"] = name or "UNKNOWN"
        if row["tool_input"] is None:
            row["tool_input"] = inp
        out.denials.append(row)
    return out


# ------------------------------------------------------------------ rows
#: Which CRO duty a refused step served, read from what the step touched. Needles are matched
#: case-insensitively against "<tool> <input summary>". A refusal that matches nothing still
#: counts against D13 ("every item fully completed this pass"): a refused step is a noticed item
#: that was not completed.
DUTY_NEEDLES: dict[str, tuple[str, ...]] = {
    "D1": ("desktop", "git show origin"),
    "D3": ("judging_throughput", "judge_capacity"),
    "D4": ("backlog", "gauntlet_backpressure"),
    "D5": ("certificate", "promoter", "cert_to_clock"),
    "D7": ("webfetch", "ingestion", "alt_platform", "forest"),
    "D8": ("cells_mined", "families_mined", "miner"),
    "D9": ("k_eff", "risk_cluster"),
    "D14": ("producer_breadth",),
    "D15": ("judging_burndown", "judge_coverage"),
    "D16": ("gate_verdict_ledger", "unknown_share"),
    "D17": ("box_state_freshness", "box_state"),
    "D18": ("unfed", "unused_dataset", "data_universe_map"),
    "D19": ("alt_proxies", "paid_substitute", "substitute"),
    "D20": ("cell_culture_index", "culture"),
    "D21": ("live_door",),
    "D22": ("decay_live", "decay_monitor", "markout"),
    "D23": ("confident_kill", "kills_per_day", "kill_class"),
    "D24": ("credential_coverage", "check_credentials"),
    "D25": ("desktop_pass2_status", "pass2"),
    "D26": ("six_event_trace", "six_event"),
}
_WEBFETCH_DUTIES = ("D7", "D19")


def duties_for(tool: str, input_summary: str, domains: Iterable[str] = ()) -> list[str]:
    """The duties a refused call served. Always includes D13."""
    hay = f"{tool} {input_summary}".lower()
    hits = [d for d, needles in DUTY_NEEDLES.items() if any(n in hay for n in needles)]
    if tool == "WebFetch":
        hits += [d for d in _WEBFETCH_DUTIES if d not in hits]
        if any(h in hay for h in domains) and "D19" not in hits:
            hits.append("D19")
    if "D13" not in hits:
        hits.append("D13")
    return sorted(hits, key=lambda d: int(d[1:]))


def denial_rows(summary: StreamSummary, *, surface: str, at: str | None = None,
                **context: Any) -> list[dict[str, Any]]:
    """One ledger row per refused call. Context (lane, agent, date, model...) is copied in."""
    stamp = at or datetime.now(tz=UTC).isoformat()
    try:
        domains = load_webfetch_domains()
    except (OSError, ValueError):
        domains = []
    rows: list[dict[str, Any]] = []
    for d in summary.denials:
        tool = str(d.get("tool") or "UNKNOWN")
        summ = summarize_input(tool, d.get("tool_input"))
        row: dict[str, Any] = {
            "event": "denial", "surface": surface, "at": stamp,
            "verdict": "UNMEASURED", "counts_as": "MISSED", "reason": "permission_denied",
            "tool": tool, "input_summary": summ,
            "tool_use_id": str(d.get("tool_use_id") or ""),
            "signals": list(d.get("signals") or []),
            "duties": duties_for(tool, summ, domains),
        }
        for k, v in context.items():
            if v is not None and k not in row:
                row[k] = v
        rows.append(row)
    return rows


def append_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    """Append rows to a JSONL ledger (utf-8, one compact object per line). Returns the count."""
    rows = list(rows)
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)


# ------------------------------------------------------------------ duty scoring
_CLEARED = {"MISSED", "BLOCKED"}


def apply_to_duties(duties: dict[str, Any], rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Mark every duty a refused step served as MISSED (verdict UNMEASURED). Mutates `duties`.

    A duty the pass itself scored MET, OPTIMAL or UNMEASURED is downgraded, and what it had
    claimed is kept under `status_claimed`. A duty already MISSED or BLOCKED keeps its status
    and gains the refused steps as further evidence. Returns the duty ids that changed status.
    """
    changed: list[str] = []
    by_duty: dict[str, list[Mapping[str, Any]]] = {}
    for r in rows:
        for d in r.get("duties") or ["D13"]:
            by_duty.setdefault(str(d), []).append(r)
    for duty, hits in sorted(by_duty.items(), key=lambda kv: int(kv[0][1:])):
        cur = duties.get(duty)
        entry: dict[str, Any] = dict(cur) if isinstance(cur, Mapping) else {}
        prior = str(entry.get("status") or "")
        steps = [f"{h.get('tool')}: {h.get('input_summary')}" for h in hits]
        entry["denied_steps"] = list(dict.fromkeys(list(entry.get("denied_steps") or []) + steps))
        entry["counts_as"] = "MISSED"
        if prior not in _CLEARED:
            if prior:
                entry["status_claimed"] = prior
            entry["status"] = "MISSED"
            entry["verdict"] = "UNMEASURED"
            entry["reason"] = "permission_denied"
            changed.append(duty)
        duties[duty] = entry
    return changed


def _parse_ts(s: Any) -> datetime | None:
    if not isinstance(s, str) or not s:
        return None
    t = s.strip().replace("Z", "+00:00")
    # Windows' round-trip format carries seven fractional digits; Python accepts at most six.
    t = re.sub(r"(\.\d{6})\d+", r"\1", t)
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def score_review(review_path: Path, rows: list[dict[str, Any]],
                 started_at: str | None) -> dict[str, Any]:
    """Apply this pass's refusals to TIER1_BREADTH_REVIEW.json's `latest.duties`.

    Only a review written BY THIS PASS (latest.at at or after `started_at`) is scored: an older
    review belongs to an earlier pass, and rewriting its history would be the lie this module
    exists to stop. The ledger rows stand on their own either way.
    """
    out: dict[str, Any] = {"review": str(review_path), "applied": False, "changed": []}
    if not rows:
        out["why"] = "no refusals"
        return out
    try:
        doc = json.loads(review_path.read_text("utf-8-sig"))
    except (OSError, ValueError) as e:
        out["why"] = f"review unreadable: {type(e).__name__}"
        return out
    latest = doc.get("latest") if isinstance(doc, dict) else None
    if not isinstance(latest, dict):
        out["why"] = "review has no latest block"
        return out
    start, wrote = _parse_ts(started_at), _parse_ts(latest.get("at"))
    if start is not None and (wrote is None or wrote < start):
        out["why"] = "review predates this pass; not rewritten"
        return out
    duties = latest.get("duties")
    if not isinstance(duties, dict):
        duties = {}
        latest["duties"] = duties
    out["changed"] = apply_to_duties(duties, rows)
    latest["permission_denials"] = {
        "count": len(rows), "counts_as": "MISSED",
        "rows": [{"tool": r["tool"], "input_summary": r["input_summary"],
                  "duties": r["duties"]} for r in rows],
    }
    # Resilient write: on the box other organs read this file while the pass ends (WinError 5
    # / errno 13 on a plain replace); see libs/ops/win_write.py.
    write_text_resilient(review_path, json.dumps(doc, indent=1, ensure_ascii=False))
    out["applied"] = True
    return out


# ------------------------------------------------------------------ scoped VPS agent calls
#: Read-only rules every scoped VPS agent may use to look around. Nothing here writes a file,
#: pushes, or reads a secret; `Read` rules also govern Grep and Glob, so the deny below covers them.
READ_ONLY_RULES: tuple[str, ...] = (
    "Read", "Glob", "Grep",
    "Bash(git log:*)", "Bash(git show:*)", "Bash(git diff:*)", "Bash(git grep:*)",
    "Bash(git status:*)", "Bash(git ls-files:*)", "Bash(git blame:*)", "Bash(git rev-parse:*)",
    "Bash(ls:*)", "Bash(wc:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(grep:*)", "Bash(stat:*)",
    "Bash(du:*)", "Bash(df:*)", "Bash(date:*)", "Bash(jq:*)",
    "Bash(systemctl --user status:*)", "Bash(systemctl --user list-timers:*)",
    "Bash(journalctl --user:*)", "Bash(crontab -l)",
    "Bash(.venv/bin/python scripts/vault_search.py:*)",
    "Bash(.venv/bin/python scripts/lessons.py:*)",
)

#: Refused for every scoped VPS agent, whatever its allowlist says: secrets never leave the box,
#: the Tier-3 deadman rail is never modified autonomously, the sealed doctrine is never edited by
#: an agent, and no history is rewritten.
NEVER_RULES: tuple[str, ...] = (
    "Read(data/secrets/**)", "Edit(data/secrets/**)", "Write(data/secrets/**)",
    "Edit(scripts/run_deadman_switch.py)", "Write(scripts/run_deadman_switch.py)",
    "Edit(ops/principal_doctrine.txt)", "Write(ops/principal_doctrine.txt)",
    "Bash(git push --force:*)", "Bash(git push -f:*)", "Bash(git reset --hard:*)",
    "Bash(git stash:*)", "Bash(git commit -a:*)",
)


def write_rules(*paths: str) -> list[str]:
    """`Edit(p)` and `Write(p)` for each repo-relative path or glob: the agent's own output only."""
    out: list[str] = []
    for p in paths:
        out += [f"Edit({p})", f"Write({p})"]
    return out


def scoped_claude_args(prompt: str, *, allowed: Iterable[str], effort: str | None = None,
                       denied: Iterable[str] = NEVER_RULES,
                       max_turns: int | None = None) -> list[str]:
    """The arguments after `claude` for one scoped, unattended `-p` call.

    stream-json (with the --verbose the CLI requires for it under -p) is the only output that
    names a refused call, so every caller parses it with `parse_stream`. The prompt comes first:
    --allowedTools and --disallowedTools are variadic and would swallow a trailing positional.
    An empty `allowed` becomes `--allowedTools ""`: no tools at all. No permission bypass and no
    acceptEdits are ever emitted here; an edit is allowed only by an explicit path rule.
    """
    rules = [r for r in allowed if r]
    args = ["-p", prompt, "--output-format", "stream-json", "--verbose"]
    if effort:
        args += ["--effort", effort]
    if max_turns is not None:
        args += ["--max-turns", str(max_turns)]
    args += ["--allowedTools", *(rules or [""])]
    deny = list(denied)
    if deny and rules:
        args += ["--disallowedTools", *deny]
    return args


#: The brain wrapper every VPS organ runs claude through: auth + model chain from brain_env.sh,
#: the doctrine as the appended system prompt, then the scoped arguments as "$@". Exit 90 is the
#: organs' own auth sentinel.
BRAIN_WRAPPER = (
    'source ops/brain_env.sh && '
    'brain_auth_check || { echo "BRAIN_AUTH_FAILED: no model in _BRAIN_MODEL_CHAIN answered '
    '-- pool drained or session limit"; exit 90; } && '
    'claude --append-system-prompt "$_DOCTRINE" "$@"'
)


def brain_argv(organ: str, claude_args: list[str]) -> list[str]:
    """`bash -c BRAIN_WRAPPER <organ> <claude args...>` (the organ name lands in $0)."""
    return ["bash", "-c", BRAIN_WRAPPER, organ, *claude_args]


def denial_log_lines(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """One human log line per refused call, in record_agent_denials.py's wording."""
    return [f"PERMISSION DENIED (counts as MISSED; verdict UNMEASURED): "
            f"{r.get('tool')}: {r.get('input_summary')}" for r in rows]

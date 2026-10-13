"""THE COMMAND-LINE FENCE FOR THE TEN VPS SHELL AGENT LANES: NO FORCED PUSH, NO SECRETS READ.

THE DEFECT (audit of PR #199). The lanes' fence was the CLI's `--disallowedTools` list, and those
rules are PREFIX matchers: `Bash(git push --force:*)` refuses `git push --force origin x` and
nothing else. `git push origin x --force`, `git push -uf origin x`, `git push origin +x`,
`git push origin :x`, `git push origin HEAD:<box branch>` all start with the allowed
`git push origin` and sailed through, and `Read(data/secrets/**)` governs the Read tool only, so
`head`, `tail`, `grep`, `jq` or any `scripts/*` CLI handed `data/secrets/<file>` read the key.
A prefix list cannot see a flag that comes after the remote, so a list was the wrong instrument.

WHAT THIS MODULE DOES. It parses the WHOLE command the way a shell would split it (every
`;`/`&&`/`||`/`|` segment, every quoted string that is itself a command) and refuses:

  * any `git push` that forces (`--force`, `--force-with-lease`, `--force-if-includes`, `-f` alone
    or inside combined short flags, a `+` refspec), deletes (`--delete`, `-d`, an empty-source
    `:dst` refspec, `--prune`), mirrors or sweeps every ref (`--mirror`, `--all`, `--branches`),
    swaps the remote's programs (`--receive-pack`, `--exec`), or targets the box branch
    `claude/llm-auto-upgrade-verify-gcjac3` in any spelling (`x`, `HEAD:x`, `refs/heads/x`,
    `src:refs/heads/x`; a bare `git push origin` or `HEAD` refspec is resolved to the checked-out
    branch, and an unresolvable one is refused, never guessed);
  * any command whose arguments reach `data/secrets` -- by path (relative, absolute, `./`, `..`,
    backslashes, doubled slashes), by a glob that can expand into it, by a variable or command
    substitution beside a `data` path, or by a recursive grep over an ancestor of it -- whatever
    the program (`cat`, `head`, `tail`, `grep`, `jq`, `scripts/*`, anything);
  * a non-Bash tool whose path/pattern input reaches `data/secrets`.

It is wired as a PreToolUse hook (`hook_settings`), which sees the full command before the CLI's
own allow/deny lists run: exit 2 blocks the call and the reason goes back to the seat. The wording
begins "Permission denied by the VPS lane guard", which libs/ops/agent_denials._REFUSAL_MARKERS
reads, so every refusal is an UNMEASURED / counts-as-MISSED row like any other refused call.
The hook FAILS CLOSED: any error in the guard itself exits 2 (and the hook command adds
`|| exit 2`, so even a missing interpreter blocks rather than allows).

STDLIB ONLY, and runnable as a file (`python -I libs/ops/lane_guard.py hook`), so the hook needs
nothing importable from the tree it guards. Paths are normalised with posixpath after turning
backslashes into slashes, so a Windows spelling is matched the same way as a POSIX one.
"""
from __future__ import annotations

import fnmatch
import json
import posixpath
import re
import shlex
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

#: The trading box's branch. Only the box (Adopt-And-Seal) and reviewed merges move it.
BOX_BRANCH = "claude/llm-auto-upgrade-verify-gcjac3"
SECRETS = "data/secrets"
#: The secrets directory's absolute path on the VPS, for a recursive walk named from above it.
VPS_SECRETS = "/home/quant/quant-platform/data/secrets"
REFUSAL = "Permission denied by the VPS lane guard"

_OPERATORS = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")", "\n"}
#: git global options that take a separate value (`git -C dir push`).
_GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
                   "--super-prefix", "--config-env"}
#: `git push` options that take a separate value, so the value is not read as a refspec.
_PUSH_VALUE_OPTS = {"-o", "--push-option", "--repo", "--signed"}
_PUSH_REFUSED_LONG = ("--force", "--force-with-lease", "--force-if-includes", "--delete",
                      "--mirror", "--all", "--branches", "--prune", "--receive-pack", "--exec")
_PUSH_REFUSED_SHORT = set("fd")
_GLOB = re.compile(r"[*?\[]")
_EXPANSION = re.compile(r"[$`]|<\(")


# ------------------------------------------------------------------ splitting
def _tokens(command: str) -> list[str] | None:
    """Shell-style tokens with operators as their own tokens; None when it cannot be parsed."""
    lex = shlex.shlex(command.replace("\r", "\n"), posix=True, punctuation_chars=";&|()\n")
    lex.whitespace = " \t"
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:
        return None


def _segments(tokens: Sequence[str]) -> Iterator[list[str]]:
    seg: list[str] = []
    for t in tokens:
        if t in _OPERATORS or (t and set(t) <= set(";&|()\n")):
            if seg:
                yield seg
            seg = []
        else:
            seg.append(t)
    if seg:
        yield seg


def _nested(tokens: Sequence[str]) -> Iterator[str]:
    """Quoted strings that are themselves commands (`bash -c "git push -f"`, `$(...)`)."""
    for t in tokens:
        if (" " in t or "\n" in t or ";" in t) and t.strip():
            yield t
        for m in re.finditer(r"\$\(([^()]*)\)|`([^`]*)`", t):
            yield m.group(1) or m.group(2) or ""


# ------------------------------------------------------------------ git push
def _git_push_args(seg: Sequence[str]) -> list[str] | None:
    """The arguments after `push` when the segment runs `git push`, else None."""
    for i, t in enumerate(seg):
        if t == "git" or t.endswith("/git"):
            j = i + 1
            while j < len(seg) and seg[j].startswith("-"):
                opt = seg[j]
                if opt == "-c" and j + 1 < len(seg) and seg[j + 1].lower().startswith("alias."):
                    return ["--alias-definition"]  # an inline alias can hide any subcommand
                j += 2 if opt in _GIT_VALUE_OPTS else 1
            if j < len(seg) and seg[j] == "push":
                return list(seg[j + 1:])
    return None


def _dst_of(refspec: str, current_branch: str | None) -> str | None:
    """The destination ref a refspec writes, short form; None when it cannot be known."""
    spec = refspec[1:] if refspec.startswith("+") else refspec
    dst = spec.rsplit(":", 1)[1] if ":" in spec else spec
    if dst in ("HEAD", "@", ""):
        return current_branch
    for pre in ("refs/heads/", "heads/"):
        if dst.startswith(pre):
            dst = dst[len(pre):]
    return dst


def push_refusal(command: str, current_branch: str | None = None) -> str | None:
    """Why this command's `git push` is refused, or None when every push in it is allowed.

    `current_branch` is the checked-out branch (what a bare `git push origin` or a `HEAD` refspec
    writes); None means unknown, and a push whose target therefore cannot be read is refused.
    """
    toks = _tokens(command)
    if toks is None:
        return "unparseable command (unbalanced quotes) -- refused rather than guessed"
    for seg in _segments(toks):
        args = _git_push_args(seg)
        if args is None:
            continue
        positional: list[str] = []
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a == "--alias-definition":
                return "git -c alias.* can hide a forced push -- refused"
            if a.startswith("--"):
                name = a.split("=", 1)[0]
                if name in _PUSH_REFUSED_LONG or name.startswith("--force"):
                    return f"git push {name} (forces, deletes or sweeps remote refs) is refused"
                if name in _PUSH_VALUE_OPTS and "=" not in a:
                    skip = True
                continue
            if a.startswith("-") and len(a) > 1:
                bad = _PUSH_REFUSED_SHORT & set(a[1:])
                if bad:
                    return f"git push {a} (short flag -{''.join(sorted(bad))}) is refused"
                if a[-1] == "o":
                    skip = True
                continue
            positional.append(a)
        refspecs = positional[1:]
        for spec in refspecs:
            if spec.startswith("+"):
                return f"git push refspec {spec!r} forces (+) -- refused"
            src = spec.split(":", 1)[0] if ":" in spec else spec
            if ":" in spec and not src:
                return f"git push refspec {spec!r} deletes the remote branch -- refused"
        targets = [_dst_of(s, current_branch) for s in refspecs] or [current_branch]
        for dst in targets:
            if dst is None:
                return ("git push target cannot be resolved (no refspec / HEAD and the "
                        "checked-out branch is unknown) -- refused")
            if dst == BOX_BRANCH:
                return f"git push to the box branch {BOX_BRANCH} is refused"
    for inner in _nested(toks):
        why = push_refusal(inner, current_branch)
        if why:
            return why
    return None


# ------------------------------------------------------------------ data/secrets
def _norm(path: str) -> str:
    p = path.replace("\\", "/")
    while "//" in p:
        p = p.replace("//", "/")
    p = posixpath.normpath(p) if p else p
    return p.lower()


def _glob_reaches_secrets(path: str) -> bool:
    """A glob any of whose expansions is data/secrets or lies under it.

    Every run of consecutive segments is tried as the `data/secrets` pair, so an absolute
    (`/home/quant/quant-platform/data/s*/k`) or relative (`data/*`, `d*/s*/*.json`) glob is read
    the same way. Matching is per segment, as the shell does it: `*` never crosses `/`, so
    `data/*.json` is NOT a match.
    """
    segs = [s for s in path.split("/") if s]
    for i in range(len(segs) - 1):
        if fnmatch.fnmatchcase("data", segs[i]) and fnmatch.fnmatchcase("secrets", segs[i + 1]):
            return True
    return False


def _reaches_secrets(token: str) -> bool:
    raw = token.split("=", 1)[1] if token.startswith("-") and "=" in token else token
    p = _norm(raw)
    if not p or p == ".":
        return False
    if SECRETS in p or ("secret" in p and "/" in p):
        return True
    if _EXPANSION.search(raw) and "data" in p:
        return True  # `data/$X/key`, `data/$(echo secrets)` -- cannot be read statically
    return bool(_GLOB.search(p)) and _glob_reaches_secrets(p)


def _recursive_over_ancestor(seg: Sequence[str]) -> bool:
    """`grep -r pat .` / `grep -R pat data` (or no path at all) walks into data/secrets."""
    prog = posixpath.basename(seg[0]) if seg else ""
    if prog not in ("grep", "egrep", "fgrep", "rg"):
        return False
    recursive = prog == "rg" or any(
        a in ("--recursive", "--dereference-recursive") or
        (a.startswith("-") and not a.startswith("--") and set(a[1:]) & {"r", "R"})
        for a in seg[1:])
    if not recursive:
        return False
    if any(a.startswith(("--exclude-dir=secrets", "--exclude-dir=data/secrets")) for a in seg):
        return False
    paths = [a for a in seg[1:] if not a.startswith("-")][1:]  # first operand is the pattern
    if not paths:
        return True  # recursive grep with no path walks the cwd, i.e. the repo
    for a in paths:
        p = _norm(a.replace("~", "/home/quant", 1) if a.startswith("~") else a)
        if p in (".", "data", "/") or p == ".." or p.startswith("../"):
            return True
        if p.startswith("/") and VPS_SECRETS.startswith(p.rstrip("/") + "/"):
            return True
    return False


def secrets_refusal(command: str) -> str | None:
    """Why this command is refused for reaching data/secrets, or None."""
    toks = _tokens(command)
    if toks is None:
        return "unparseable command (unbalanced quotes) -- refused rather than guessed"
    for seg in _segments(toks):
        for t in seg:
            if _reaches_secrets(t):
                return f"{seg[0]} reaches {SECRETS} ({t!r}) -- secrets never leave the box"
        if _recursive_over_ancestor(seg):
            return (f"recursive {seg[0]} over an ancestor of {SECRETS} -- add "
                    "--exclude-dir=secrets or name the subtree")
    for inner in _nested(toks):
        why = secrets_refusal(inner)
        if why:
            return why
    return None


def refusal(tool: str, tool_input: object, current_branch: str | None = None) -> str | None:
    """The guard's verdict for one tool call: a reason to refuse, or None to let the CLI decide."""
    if not isinstance(tool_input, dict):
        return None
    if tool == "Bash":
        cmd = tool_input.get("command")
        if not isinstance(cmd, str):
            return "Bash call without a command string -- refused"
        return push_refusal(cmd, current_branch) or secrets_refusal(cmd)
    for k in ("file_path", "path", "notebook_path", "pattern"):
        v = tool_input.get(k)
        if isinstance(v, str) and _reaches_secrets(v):
            return f"{tool} {k} reaches {SECRETS} -- secrets never leave the box"
    return None


def current_branch(cwd: str | None) -> str | None:
    """The checked-out branch in cwd, or None when it cannot be read (detached, no git)."""
    try:
        r = subprocess.run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=cwd or None,
                           capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    out = r.stdout.strip()
    return out if r.returncode == 0 and out else None


# ------------------------------------------------------------------ the hook
def hook(stdin_text: str) -> tuple[int, str]:
    """(exit code, stderr) for one PreToolUse payload: 0 lets the CLI decide, 2 blocks."""
    try:
        payload = json.loads(stdin_text)
        tool = str(payload.get("tool_name") or "")
        tool_input = payload.get("tool_input")
        branch = None
        if tool == "Bash" and isinstance(tool_input, dict) and "push" in str(
                tool_input.get("command", "")):
            branch = current_branch(payload.get("cwd"))
        why = refusal(tool, tool_input, branch)
    except Exception as e:  # the guard fails CLOSED on its own error
        return 2, f"{REFUSAL}: guard error ({type(e).__name__}) -- refused, counts as MISSED"
    if why:
        return 2, f"{REFUSAL}: {why}. Counts as MISSED; record the step as MISSED and carry on."
    return 0, ""


def hook_settings(python: str, guard: str | Path | None = None) -> str:
    """The `--settings` JSON that runs this guard as a PreToolUse hook on every tool call."""
    path = str(guard or Path(__file__).resolve())
    cmd = f"{shlex.quote(python)} -I {shlex.quote(path)} hook || exit 2"
    return json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "*", "hooks": [{"type": "command", "command": cmd, "timeout": 30}]}]}},
        separators=(",", ":"))


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["hook"]:
        rc, msg = hook(sys.stdin.read())
        if msg:
            print(msg, file=sys.stderr)
        return rc
    if args[:1] == ["check"] and len(args) == 2:
        why = push_refusal(args[1], current_branch(None)) or secrets_refusal(args[1])
        print(why or "ALLOWED")
        return 2 if why else 0
    print("usage: lane_guard.py hook < payload.json | lane_guard.py check '<command>'",
          file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main())

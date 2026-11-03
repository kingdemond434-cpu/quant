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
    branch, and an unresolvable one is refused, never guessed). Long options are resolved the
    way git resolves them, by unambiguous PREFIX (`--del` is `--delete`, `--mirr` is `--mirror`),
    and any argument the shell would expand first (`$BR`, `${BR}`, `$(...)`, backticks) is
    refused: its option, remote or target cannot be read before the shell runs;
  * any command whose arguments reach `data/secrets` -- by path (relative, absolute, `./`, `..`,
    backslashes, doubled slashes), by a glob that can expand into it, by a variable or command
    substitution beside a `data` path, or by a recursive grep over an ancestor of it (`-r`,
    `-R`, `-d recurse`, `--directories=recurse`, any abbreviation; only an `--exclude-dir` glob
    that matches the base name `secrets` lets it through, never `secretsX`) -- whatever
    the program (`cat`, `head`, `tail`, `grep`, `jq`, `scripts/*`, anything);
  * a non-Bash tool whose path/pattern input reaches `data/secrets`.

EVERY PATH IS READ FROM THE WORKING DIRECTORY IT RUNS IN (audit HOLD on #199, 2026-11-03).
`cd data && grep -r x secrets`, and `cd data`, then `cd secrets`, then `head k` across three
calls, named the directory relatively and passed. Each relative operand is now resolved against
the payload's `cwd` (which carries a `cd` from an earlier call forward), against every `cd`,
`pushd` target earlier in the same command (all are kept: a `cd` in a pipeline or subshell does
not persist) and against a program's own `-C`/`--directory`/`--chdir`. A `cd` into the secrets
directory is refused, every command whose cwd is inside it is refused, and a cwd that cannot be
read (`cd -`, `cd $X`) refuses the operands after it.

WHAT THIS GUARD CANNOT SEE: A STRUCTURAL LIMIT. It judges the command line, not what a program
does. The CODE lanes may write `scripts/**` (and other code) and may also run it, so a lane can
write a script that opens data/secrets and then run it with nothing secrets-shaped on the line;
a symlink planted earlier is the same hole. No command-line parser closes that. The real fence is
the operating system: data/secrets must be unreadable to the user the lanes run as (a separate
owner and mode 0700, or a user the lanes cannot become). Until that is set on the VPS, this guard
narrows the path; it does not seal it.

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
import os
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
#: The tree this guard ships in; a missing payload cwd is read as this one.
ROOT = Path(__file__).resolve().parents[2]
#: Every secrets directory known by absolute path (normalised as `_norm` does).
SECRET_DIRS: tuple[str, ...] = tuple(dict.fromkeys(
    posixpath.normpath(d.replace("\\", "/")).lower()
    for d in (VPS_SECRETS, str(ROOT / "data" / "secrets"))))
#: Programs whose `cd`-like argument moves the cwd for the rest of the command.
_CD = ("cd", "pushd", "chdir")

_OPERATORS = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")", "\n"}
#: git global options that take a separate value (`git -C dir push`).
_GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
                   "--super-prefix", "--config-env"}
#: `git push` options that take a separate value, so the value is not read as a refspec.
_PUSH_VALUE_OPTS = {"-o", "--push-option", "--repo", "--signed"}
_PUSH_REFUSED_LONG = ("--force", "--force-with-lease", "--force-if-includes", "--delete",
                      "--mirror", "--all", "--branches", "--prune", "--receive-pack", "--exec")
_PUSH_REFUSED_SHORT = set("fd")
#: Every long `git push` option git itself accepts, so an abbreviation (git takes any unambiguous
#: prefix: `--del` IS `--delete`, `--mirr` IS `--mirror`) is resolved against the whole table, not
#: matched literally. An abbreviation that is a prefix of a refused option is refused even when git
#: would call it ambiguous: failing closed costs one retry, failing open costs a remote branch.
_PUSH_LONG = ("--all", "--branches", "--mirror", "--delete", "--tags", "--dry-run", "--porcelain",
              "--force", "--force-with-lease", "--force-if-includes", "--prune", "--verbose",
              "--quiet", "--progress", "--no-verify", "--verify", "--set-upstream",
              "--follow-tags", "--signed", "--atomic", "--push-option", "--repo",
              "--receive-pack", "--exec", "--recurse-submodules", "--thin", "--no-thin",
              "--ipv4", "--ipv6", "--no-signed", "--no-atomic", "--no-force-with-lease",
              "--no-force-if-includes", "--no-recurse-submodules", "--no-progress",
              "--no-follow-tags")
_GLOB = re.compile(r"[*?\[]")
_EXPANSION = re.compile(r"[$`]|<\(")
#: A token the shell would expand before git saw it (`$BR`, `${BR}`, `$(...)`, backticks): the
#: tokenizer splits `$(` into `$` and `(`, so a lone `$` is the start of a substitution too.
_SHELL_EXPANDS = re.compile(r"[$`]")


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
            if j < len(seg) and _SHELL_EXPANDS.search(seg[j]):
                return ["--expanded-subcommand"]  # `git $CMD ...` may be a push
    return None


def _long_option(name: str) -> str | None:
    """The `git push` long option an (abbreviated) `--name` denotes; a refused option whenever
    the abbreviation could be one, None when it names nothing git push knows."""
    if name in _PUSH_LONG:
        return name
    cands = [o for o in _PUSH_LONG if o.startswith(name)]
    refused = [o for o in cands if o in _PUSH_REFUSED_LONG]
    if refused:
        return refused[0]
    return cands[0] if len(cands) == 1 else None


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
            if a == "--expanded-subcommand":
                return ("git subcommand is a shell expansion ($VAR / $(...)) and may be a push "
                        "-- refused rather than guessed")
            if _SHELL_EXPANDS.search(a):
                return (f"git push argument {a!r} is a shell expansion: its option, remote or "
                        "target cannot be read before the shell runs -- refused")
            if a == "--":
                continue
            if a.startswith("--"):
                name = a.split("=", 1)[0]
                if name.startswith("--force"):
                    return f"git push {name} (forces, deletes or sweeps remote refs) is refused"
                full = _long_option(name)
                if full in _PUSH_REFUSED_LONG:
                    return (f"git push {name} (= {full}: forces, deletes or sweeps remote refs) "
                            "is refused")
                if full in _PUSH_VALUE_OPTS and "=" not in a:
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


def _abs(path: str, cwd: str | None) -> str | None:
    """`path` as an absolute, normalised, lower-cased path read from `cwd`; None when a relative
    path meets an unknown cwd."""
    p = path.replace("\\", "/")
    if p.startswith("~"):
        p = os.path.expanduser(p).replace("\\", "/")
    if not p.startswith("/"):
        if cwd is None:
            return None
        p = cwd.rstrip("/") + "/" + p
    return _norm(p)


def _inside_secrets(absp: str) -> bool:
    """An absolute path that IS a secrets directory or lies under one: a known one by path, any
    `.../data/secrets/...` pair, or a glob that can expand to either."""
    if any(absp == d or absp.startswith(d + "/") for d in SECRET_DIRS):
        return True
    segs = [x for x in absp.split("/") if x]
    if any(segs[i] == "data" and segs[i + 1] == "secrets" for i in range(len(segs) - 1)):
        return True
    return bool(_GLOB.search(absp)) and _glob_reaches_secrets(absp)


def _ancestor_of_secrets(absp: str) -> bool:
    """A directory a recursive walk from which enters a secrets directory: an ancestor of a
    known one (globs read per segment), or one holding `data/secrets` or `secrets` on disk."""
    if absp == "/" or _inside_secrets(absp):
        return True
    psegs = [x for x in absp.split("/") if x]
    for d in SECRET_DIRS:
        dsegs = [x for x in d.split("/") if x]
        if len(psegs) < len(dsegs) and all(
                fnmatch.fnmatchcase(dsegs[i], psegs[i]) for i in range(len(psegs))):
            return True
    if _GLOB.search(absp):
        return False
    return (os.path.isdir(posixpath.join(absp, "data", "secrets"))
            or (absp.endswith("/data") and os.path.isdir(posixpath.join(absp, "secrets"))))


def _reaches_secrets(token: str, cwds: Sequence[str | None] = (None,)) -> bool:
    """A token (a path operand, or the value of `--opt=value`) that reaches data/secrets, read
    as written AND from every cwd the command may be in (audit HOLD on #199: `cd data && grep
    -r x secrets` named the directory relatively and passed)."""
    raw = token.split("=", 1)[1] if token.startswith("-") and "=" in token else token
    p = _norm(raw)
    if not p or p == ".":
        return any(c is not None and _inside_secrets(_norm(c)) for c in cwds)
    if SECRETS in p or ("secret" in p and "/" in p):
        return True
    if _EXPANSION.search(raw):
        if "data" in p:
            return True  # `data/$X/key`, `data/$(echo secrets)` -- cannot be read statically
        # from inside data/, a bare `$X` may itself be `secrets`
        if any(c is not None and _norm(c).rsplit("/", 1)[-1] == "data" for c in cwds):
            return True
    if bool(_GLOB.search(p)) and _glob_reaches_secrets(p):
        return True
    for c in cwds:
        absp = _abs(raw, c)
        if absp is not None and _inside_secrets(absp):
            return True
    return False


#: GNU grep short options that take a value: the characters after one are its value, not flags.
_GREP_VALUE_SHORT = set("efmABCDd")
#: GNU grep long options that take a value (abbreviations resolved by prefix below).
_GREP_VALUE_LONG = ("--regexp", "--file", "--max-count", "--after-context", "--before-context",
                    "--context", "--devices", "--directories", "--include", "--exclude",
                    "--exclude-dir", "--exclude-from", "--label", "--binary-files", "--color",
                    "--colour", "--group-separator")
_GREP_RECURSIVE_LONG = ("--recursive", "--dereference-recursive")


def _grep_long(name: str) -> str | None:
    """The grep long option an (abbreviated) `--name` denotes. An abbreviation that could be a
    recursion switch is read as one even where grep would call it ambiguous (fails closed)."""
    known = (*_GREP_VALUE_LONG, *_GREP_RECURSIVE_LONG)
    if name in known:
        return name
    cands = [o for o in known if o.startswith(name)]
    rec = [o for o in cands if o in _GREP_RECURSIVE_LONG]
    if rec and len(name) > 3:
        return rec[0]
    if "--directories" in cands and len(name) > 3:
        return "--directories"
    return cands[0] if len(cands) == 1 else None


def _is_recurse(value: str) -> bool:
    """`-d ACTION` / `--directories=ACTION`: grep takes any unambiguous prefix of `recurse`, and
    an expansion (`-d $MODE`) cannot be read, so it counts as recursion."""
    v = value.strip().lower()
    return (bool(v) and "recurse".startswith(v)) or _SHELL_EXPANDS.search(v) is not None


def _excludes_secrets(value: str) -> bool:
    """An `--exclude-dir` glob that matches the secrets directory's BASE NAME, which is all GNU
    grep compares while it recurses. `secretsX` (and `data/secrets`) do NOT exclude it."""
    return fnmatch.fnmatchcase("secrets", value.rstrip("/"))


def _grep_walk(seg: Sequence[str]) -> tuple[bool, bool, list[str]]:
    """(recursive, secrets excluded, path operands) for one grep segment, options parsed the way
    getopt does: combined short flags, attached and separate values, long-option prefixes."""
    recursive = excluded = pattern_given = False
    operands: list[str] = []
    i = 1
    while i < len(seg):
        a = seg[i]
        i += 1
        if a == "--":
            operands.extend(seg[i:])
            break
        if a.startswith("--"):
            name, eq, val = a.partition("=")
            full = _grep_long(name)
            if full in _GREP_RECURSIVE_LONG:
                recursive = True
            elif full in _GREP_VALUE_LONG:
                if not eq:
                    val = seg[i] if i < len(seg) else ""
                    i += 1
                if full == "--directories" and _is_recurse(val):
                    recursive = True
                elif full == "--exclude-dir" and _excludes_secrets(val):
                    excluded = True
                elif full in ("--regexp", "--file"):
                    pattern_given = True
            continue
        if a.startswith("-") and len(a) > 1:
            k = 1
            while k < len(a):
                c = a[k]
                k += 1
                if c in ("r", "R"):
                    recursive = True
                elif c in _GREP_VALUE_SHORT:
                    val = a[k:]
                    if not val:
                        val = seg[i] if i < len(seg) else ""
                        i += 1
                    if c == "d" and _is_recurse(val):
                        recursive = True
                    elif c in ("e", "f"):
                        pattern_given = True
                    break
            continue
        operands.append(a)
    return recursive, excluded, operands if pattern_given else operands[1:]


def _recursive_over_ancestor(seg: Sequence[str], cwds: Sequence[str | None] = (None,)) -> bool:
    """`grep -r pat .` / `grep -d recurse pat data` (or no path at all) walks into data/secrets.
    Every operand is resolved from every cwd the command may be in."""
    prog = posixpath.basename(seg[0]) if seg else ""
    if prog not in ("grep", "egrep", "fgrep", "rg"):
        return False
    if prog == "rg":
        # rg always recurses and has no --exclude-dir: its path operands decide it alone.
        recursive, excluded = True, False
        paths = [a for a in seg[1:] if not a.startswith("-")][1:]
    else:
        recursive, excluded, paths = _grep_walk(seg)
    if not recursive or excluded:
        return False
    for a in paths or ["."]:   # no path walks the cwd
        if _SHELL_EXPANDS.search(a):
            return True  # `grep -r k $DIR`: may expand to an ancestor
        for c in cwds:
            absp = _abs(a, c)
            if absp is None or _ancestor_of_secrets(absp):
                return True
        if _norm(a) in ("data",) or (_GLOB.search(a) and fnmatch.fnmatchcase("data", _norm(a))):
            return True
    return False


def _cd_target(seg: Sequence[str]) -> str | None:
    """The directory a `cd`/`pushd` segment moves to ("~" for a bare `cd`)."""
    args = [a for a in seg[1:] if a not in ("-L", "-P", "-e", "-@", "--")]
    return args[0] if args else "~"


def _dash_c_dirs(seg: Sequence[str]) -> list[str]:
    """Directories a program is told to run from (`tar -C d`, `make -C d`, `git -C d`,
    `env --chdir=d`): its relative operands are read from there too."""
    out: list[str] = []
    for i, a in enumerate(seg[1:], 1):
        if a in ("-C", "--directory", "--chdir", "--cwd") and i + 1 < len(seg):
            out.append(seg[i + 1])
        elif a.startswith(("--directory=", "--chdir=", "--cwd=")):
            out.append(a.split("=", 1)[1])
        elif a.startswith("-C") and len(a) > 2 and not a.startswith("--"):
            out.append(a[2:])
    return out


def _judge_segment(seg: Sequence[str], cwds: Sequence[str | None]) -> str | None:
    """Why one simple command, run from any of `cwds`, reaches data/secrets; or None."""
    if any(c is not None and _inside_secrets(_norm(c)) for c in cwds):
        return (f"the working directory is inside {SECRETS} -- every command there reads it; "
                "cd out of it first")
    seg_cwds = list(cwds)
    for d in _dash_c_dirs(seg):
        seg_cwds += [None] if _EXPANSION.search(d) else [_abs(d, c) for c in cwds]
    if None in seg_cwds and len(seg) > 1:
        return ("the working directory cannot be resolved (`cd -`, `cd $X` or `-C $X`), so "
                f"{seg[0]}'s operands cannot be shown to stay out of {SECRETS} -- refused")
    for t in seg:
        if _reaches_secrets(t, seg_cwds):
            return f"{seg[0]} reaches {SECRETS} ({t!r}) -- secrets never leave the box"
    if _recursive_over_ancestor(seg, seg_cwds):
        return (f"recursive {seg[0]} over an ancestor of {SECRETS} -- add "
                "--exclude-dir=secrets or name the subtree")
    return None


def _secrets_refusal(command: str, start: list[str | None]) -> str | None:
    """THE CWD IS TRACKED THROUGH THE COMMAND (audit HOLD on #199), as the shell moves it:

    * `cd T && x`: x runs only if the cd succeeded, so x is read from T alone; at the next `;`,
      `||` or newline the cd may have FAILED, so the old cwd comes back beside T;
    * `cd T; x` / `cd T || x` / a newline: the cd may have failed, so x is read from both;
    * `cd T | x`, `cd T & x`: a pipeline stage or a background job does not move the shell;
    * `( ... )`: a subshell's cd ends at its `)`.
    Every operand is judged from every cwd it may run in."""
    toks = _tokens(command)
    if toks is None:
        return "unparseable command (unbalanced quotes) -- refused rather than guessed"
    cwds: list[str | None] = list(start)
    fallback: list[str | None] = []   # cwds a failed `cd ... &&` leaves the shell in
    stack: list[tuple[list[str | None], list[str | None]]] = []
    pending: tuple[list[str | None], list[str | None]] | None = None  # (old, new) of the last cd
    seg: list[str] = []
    seen: list[str | None] = list(start)   # every cwd any part of the command may run in

    def union(*lists: list[str | None]) -> list[str | None]:
        return list(dict.fromkeys(c for lst in lists for c in lst))

    def flush() -> str | None:
        nonlocal pending
        if not seg:
            return None
        if posixpath.basename(seg[0]) in _CD:
            target = _cd_target(seg)
            if target == "-" or _EXPANSION.search(target):
                new: list[str | None] = [None]   # cannot be read statically
            else:
                new = [_abs(target, c) for c in cwds]
                for n in new:
                    if n is not None and _inside_secrets(n):
                        return f"cd into {SECRETS} ({target!r}) -- secrets never leave the box"
            pending = (list(cwds), list(dict.fromkeys(new)))
            seen.extend(pending[1])
            return None
        pending = None
        return _judge_segment(seg, cwds)

    for t in [*toks, ";"]:
        if not (t in _OPERATORS or (t and set(t) <= set(";&|()\n"))):
            seg.append(t)
            continue
        why = flush()
        if why:
            return why
        seg = []
        for ch in t:
            if ch == "(":
                stack.append((list(cwds), list(fallback)))
                fallback = []
            elif ch == ")" and stack:
                cwds, fallback = stack.pop()
                pending = None
        op = t.replace("(", "").replace(")", "")
        if pending is not None:
            old, new = pending
            if op == "&&":
                cwds, fallback = new, union(fallback, old)
            elif op in ("|", "&", "|&"):
                cwds = old
            else:   # ; || newline, end
                cwds = union(old, new)
            pending = None
        if op in (";", "||", "\n", ";;", "") and fallback and ")" not in t:
            cwds, fallback = union(cwds, fallback), []
    # A quoted command (`bash -c "..."`, `$(...)`) runs from wherever its segment ran, so it is
    # read from every cwd the outer command reached.
    for inner in _nested(toks):
        why = _secrets_refusal(inner, list(dict.fromkeys(seen)))
        if why:
            return why
    return None


def secrets_refusal(command: str, cwd: str | None = None) -> str | None:
    """Why this command is refused for reaching data/secrets, or None. `cwd` is the directory
    the command starts in -- the hook payload's, which carries a `cd` from an EARLIER call
    forward (`cd data`, then `cd secrets`, then `head k`) -- and defaults to this tree's root."""
    start = str(cwd) if cwd else str(ROOT)
    return _secrets_refusal(command, [start.replace("\\", "/")])


def refusal(tool: str, tool_input: object, current_branch: str | None = None,
            cwd: str | None = None) -> str | None:
    """The guard's verdict for one tool call: a reason to refuse, or None to let the CLI decide."""
    if not isinstance(tool_input, dict):
        return None
    if tool == "Bash":
        cmd = tool_input.get("command")
        if not isinstance(cmd, str):
            return "Bash call without a command string -- refused"
        return push_refusal(cmd, current_branch) or secrets_refusal(cmd, cwd)
    start = (str(cwd) if cwd else str(ROOT)).replace("\\", "/")
    for k in ("file_path", "path", "notebook_path", "pattern"):
        v = tool_input.get(k)
        if isinstance(v, str) and _reaches_secrets(v, [start]):
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
        cwd = payload.get("cwd")
        why = refusal(tool, tool_input, branch, cwd if isinstance(cwd, str) else None)
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
        why = push_refusal(args[1], current_branch(None)) or secrets_refusal(args[1], os.getcwd())
        print(why or "ALLOWED")
        return 2 if why else 0
    print("usage: lane_guard.py hook < payload.json | lane_guard.py check '<command>'",
          file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main())

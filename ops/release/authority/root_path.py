"""THE ROOT PATH (zuck 2026-11-10 23:18Z / 23:19Z: "everything literally everything autonomous",
"never ever need to manually comment paste anything fr merges any type"). SEALED CORE.

After the final sitting, a ROOT PR that changes the box gate (audit_gate.py), the publisher or the
release machinery merges with no owner comment when ALL hold. THE RELEASE AUTHORITY ENFORCES
EVERY CONDITION (authority_verdict), and only once GitHub itself enforces the authority's status
on LIVE (Level 2): a rewritten gate can then merge nothing the authority did not pass, so the gate
is not trusted to keep this path. The gate runs the same rules (gate_verdict) to send the notice,
ask for the one re-run and merge. Both load THIS module from their own pinned checkout, so a PR is
judged by the base's rules, never its own:

  0. Level 2 is enforced, and the sealed re-pin service is installed on the box (REPIN_MARKER);
  1. the newest AUDIT verdict comment is CLEAR for the exact head, AND the Auditor's newest row
     for the PR on the audit-registry ref (AUDIT_REF:AUDIT_FILE, read from git, not from a box
     file) is CLEAR for that head;
  2. every ROOT_JOBS job green on the exact head, counted over ALL attempts (filter=all). A failed
     independent-review or replay-shadow is re-run automatically ONCE, only when its failure cites
     no line and flags nothing; a second failure, or any other failure, blocks. No adjudication;
  3. the BASE's trusted-eval passed on the exact head;
  4. up to date with LIVE; the merge pinned to the head sha;
  5. ROOT_VETO_H (72 h) since a ROOT NOTICE for THIS head was DELIVERED: the gate sends it to
     zuck's alert channel, and only on a receipt (exit 0 AND "delivered N", N > 0) posts the
     anchoring PR comment "ROOT NOTICE <head> delivered: <receipt>", whose GitHub time starts the
     window. Any red check, non-CLEAR verdict, edited trusted comment or DEACTIVATE dated after
     that notice VOIDS it: a new notice, a new 72 h. A new push is a new head;
  6. one at a time: the authority signs nothing while LIVE's root digest is not the pinned one,
     which is true from a ROOT merge until the re-pin service (repin.py) re-pins the released,
     adopted tree; the gate also writes ROOT_INFLIGHT.json BEFORE the merge call.

THE SEALED CORE never takes this path (the project's rule: a pin approved from a phone may never
re-pin its own door): every file of the release authority (ops/release/authority/*, which holds
this module, the policy, the signer, the pin tools, the re-pin service and ROOT_POLICY.json with
the root list, the grow-only lists and the sizing envelope), trusted-eval.yml, the immutable
evaluator check, and the SEALED_VALUES constants. A ROOT PR whose reasons are anything but
"root file X" stays zuck's too. Lifting that is zuck's call alone.

RESIDUAL RISK (stated for the sitting note, Auditor 2026-11-10): every session posts with one
GitHub identity, and the registry ref is landed by a session, so the comment, the row and the
notice comment are records, not independent keys. Against a deliberate forge the 72 h window is
DETECTION, not prevention, until an authenticated Auditor channel exists.

Pure: no I/O here. The callers read GitHub, the box files and the clock, and pass facts in.
"""

from __future__ import annotations

import ast
import fnmatch
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

#: Condition 6: the ROOT veto window, three times the normal 24 h.
ROOT_VETO_H = 72.0
#: Condition 2: the jobs that must be green on the exact head. Kept HERE, not read from
#: audit_gate's GATING_JOBS / AUTO_JOBS, so a ROOT PR that shortens those lists does not shorten
#: what the next ROOT PR needs.
ROOT_JOBS = (
    "quality",
    "mt5-money-path",
    "coverage-floor",
    "risk-invariants",
    "replay-shadow",
    "independent-review",
)
#: Condition 2: the only jobs that get the one automatic re-run, and how many re-runs.
RERUNNABLE = ("independent-review", "replay-shadow")
RERUNS = 1
#: Condition 3.
TRUSTED_EVAL = "trusted-eval"
#: The box command that delivers the veto notice (the gate's own channel).
NOTIFY_ENV = "QUANT_REGISTRY_NOTIFY"
#: Condition 1, second record: read from git by both the authority and the gate.
AUDIT_REF = "refs/heads/audit-registry"
AUDIT_FILE = "REGISTRY_ROWS.jsonl"
#: Condition 0: written by install_repin.ps1 once the sealed re-pin service is installed.
REPIN_MARKER = r"C:\opt\authority\sealed\INSTALLED.sha256"
#: Condition 5: the anchoring PR comment the gate posts after a delivered notice.
NOTICE_PREFIX = "ROOT NOTICE"
_NOTICE = re.compile(r"\AROOT NOTICE ([0-9a-f]{40}) delivered: (\S.*)")
#: The class an attestation carries for this path.
ROOT_CLASS = "ROOT"

#: Files no PR may change through this path (patterns, case-insensitive).
SEALED_CORE = (
    "ops/release/authority/*",
    ".github/workflows/trusted-eval.yml",
    "scripts/check_immutable_evaluator.py",
)
#: Constants in other files that steer where the path's records come from or go to. A PR that
#: changes, removes or re-assigns one is SEALED (an absent constant that a PR adds with exactly
#: this value is not a change of it).
SEALED_VALUES: dict[tuple[str, str], Any] = {
    (".github/scripts/audit_gate.py", "REGISTRY_NOTIFY_ENV"): "QUANT_REGISTRY_NOTIFY",
    (".github/scripts/audit_gate.py", "REGISTRY_HOLD_H"): 24.0,
    (".github/scripts/audit_gate.py", "AUTHORITY_PUBKEY_ENV"): "QUANT_AUTHORITY_PUBKEY",
    (".github/scripts/audit_gate.py", "AUTHORITY_DIR_ENV"): "QUANT_AUTHORITY_ATTESTATIONS",
    (".github/scripts/audit_gate.py", "AUTHORITY_PIN_ENV"): "QUANT_AUTHORITY_ROOT_PIN",
    (".github/scripts/audit_gate.py", "AUTHORITY_KILL"): "DEACTIVATE",
    ("ops/release/auditor_sync.py", "REF"): "refs/heads/audit-registry",
    ("ops/release/auditor_sync.py", "FILE"): "REGISTRY_ROWS.jsonl",
    ("ops/release/auditor_sync.py", "MEMECOIN_FILE"): "MEMECOIN_REGISTRY_ROWS.jsonl",
    (".github/scripts/memecoin_gate.py", "MEMECOIN_REGISTRY_ENV"): "MEMECOIN_AUDIT_REGISTRY",
}
#: Forms that can re-bind a module global without an assignment the AST pin sees. A sealed-value
#: file that uses any of them cannot be pinned down, so a change to it is SEALED.
_REBIND = re.compile(
    r"globals\(\)|vars\(\)|__dict__|sys\.modules|setattr\(|importlib\.reload|\bexec\(|\beval\("
)

_UNREADABLE = object()
_ROOT_REASON = "root file "
#: A failure that names a place: path/file.ext:123.
_CITES_LINE = re.compile(
    r"[\w./\\-]+\.[A-Za-z0-9]{1,8}:\d+|\bline\s+\d+|\blines?\s+\d+\s*-\s*\d+|\bL\d+\b",
    re.IGNORECASE,
)
_CONTROL = re.compile(r"touches_control|control machinery", re.IGNORECASE)
_RISK = re.compile(r"risk_increasing|risk increase", re.IGNORECASE)
#: A model's FAIL vote: its findings stay in the job log (never relayed), so whether they cite a
#: line cannot be read, and a failure that may cite a line is never re-run.
_VOTED = re.compile(r"voted FAIL|findings are in the job log", re.IGNORECASE)
_DELIVERED = re.compile(r"\bdelivered\s+(\d+)\b")


# ----------------------------------------------------------------------------- the sealed core


def _sealed_file(name: str) -> bool:
    low = name.replace("\\", "/").lower()
    return any(fnmatch.fnmatchcase(low, p.lower()) for p in SEALED_CORE)


def _binds(node: ast.AST, name: str) -> bool:
    """Does `node` (re)bind `name` in its own scope?"""
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.For, ast.AsyncFor)):
        targets = [node.target]
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        targets = [i.optional_vars for i in node.items if i.optional_vars is not None]
    elif isinstance(node, ast.Delete):
        targets = list(node.targets)
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        return any((a.asname or a.name.split(".")[0]) == name or a.name == "*" for a in node.names)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler)):
        return node.name == name
    return any(isinstance(n, ast.Name) and n.id == name for t in targets for n in ast.walk(t))


def py_constant(src: str | None, name: str) -> Any:
    """The value of module constant `name` in Python source `src`: None when absent, _UNREADABLE
    when it cannot be pinned down (a parse error, a non-literal value, more than one binding of
    the name anywhere in the module, or a `global` re-binding)."""
    if src is None:
        return None
    if _REBIND.search(src):
        return _UNREADABLE
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return _UNREADABLE
    found: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            return _UNREADABLE
        if _binds(node, name):
            found.append(node)
    if not found:
        return None
    if len(found) > 1:
        return _UNREADABLE
    node = found[0]
    if node not in tree.body or isinstance(node, ast.AugAssign):
        return _UNREADABLE
    value = getattr(node, "value", None)
    if value is None:
        return _UNREADABLE
    try:
        return ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return _UNREADABLE


def sealed_touch(
    files: Iterable[str],
    read_base: Callable[[str], str | None],
    read_head: Callable[[str], str | None],
) -> list[str]:
    """Why this change touches the SEALED CORE (empty: it does not). `files`: every changed path,
    both sides of a rename."""
    changed = {f.replace("\\", "/") for f in files}
    low = {f.lower(): f for f in changed}
    out = [f"sealed core file {f}" for f in sorted(changed) if _sealed_file(f)]
    for (path, name), pinned in SEALED_VALUES.items():
        if path.lower() not in low:
            continue
        path = low[path.lower()]
        hv, bv = py_constant(read_head(path), name), py_constant(read_base(path), name)
        if hv is _UNREADABLE:
            out.append(f"sealed value {path}:{name} cannot be read on the head")
        elif hv != bv and not (bv is None and hv == pinned):
            out.append(f"sealed value {path}:{name} changes ({bv!r} -> {hv!r})")
    return out


def eligible(cls_reasons: Iterable[str]) -> tuple[bool, str]:
    """May a ROOT PR with these classify() reasons take the ROOT path? Only when it is ROOT
    purely because it changes root files: a shrinking grow-only list, a sizing-envelope change or
    a sealed-core change stays zuck's."""
    reasons = list(cls_reasons)
    if not reasons:
        return False, "no ROOT reason given: fail closed"
    other = [r for r in reasons if not r.startswith(_ROOT_REASON)]
    if other:
        return False, "not a root-file-only change, so zuck's path: " + "; ".join(other)
    sealed = [r for r in reasons if _sealed_file(r[len(_ROOT_REASON) :])]
    if sealed:
        return False, "the sealed core never takes the ROOT path: " + "; ".join(sealed)
    return True, "root files only: " + ", ".join(r[len(_ROOT_REASON) :] for r in reasons)


# ----------------------------------------------------------------------------- the checks


def failure_flags(texts: Iterable[str]) -> list[str]:
    """Why a failed job's own annotations rule out the automatic re-run (empty: they do not)."""
    out: list[str] = []
    for t in texts:
        if _CITES_LINE.search(t):
            out.append("its failure cites a line")
        if _CONTROL.search(t):
            out.append("its failure flags control machinery")
        if _RISK.search(t):
            out.append("its failure flags a risk increase")
        if _VOTED.search(t):
            out.append("a reviewer voted FAIL and its findings may cite a line")
    return sorted(set(out))


def jobs(attempts: Mapping[str, list[Mapping[str, Any]]]) -> tuple[str, str, str | None]:
    """("pass" | "pending" | "rerun" | "fail", why, the job to re-run). `attempts[name]`: every
    GENUINE run of that ROOT job on the exact head, oldest first, each {"status",
    "conclusion", "unavailable": the reviewer's UNAVAILABLE mark, "flags": failure_flags(...) or
    None when the annotations were unreadable}."""
    pending: list[str] = []
    rerun: str | None = None
    for name in ROOT_JOBS:
        runs = list(attempts.get(name) or [])
        if not runs:
            pending.append(f"{name} (not started)")
            continue
        last = runs[-1]
        if last.get("status") != "completed":
            pending.append(name)
            continue
        if last.get("conclusion") == "success":
            continue
        if last.get("unavailable"):  # no free reviewer answered: queued, never a pass or a fail
            pending.append(f"{name} (queued: no free reviewer answered)")
            continue
        concl = last.get("conclusion")
        flags = last.get("flags")
        failed = [r for r in runs if r.get("status") == "completed"
                  and r.get("conclusion") != "success" and not r.get("unavailable")]  # fmt: skip
        if name not in RERUNNABLE:
            return "fail", f"{name} {concl}: no re-run on the ROOT path", None
        if len(failed) > RERUNS:
            return "fail", f"{name} {concl} again after {RERUNS} re-run", None
        if flags is None:
            return "fail", f"{name} {concl}: its annotations cannot be read, so no re-run", None
        if flags:
            return "fail", f"{name} {concl}: " + ", ".join(flags), None
        rerun = rerun or name
    if pending:
        return "pending", "waiting on: " + ", ".join(pending), None
    if rerun:
        return "rerun", f"{rerun} failed once and names nothing: one automatic re-run", rerun
    return "pass", f"all {len(ROOT_JOBS)} ROOT jobs green on the exact head", None


def registry_agrees(rows: Iterable[Mapping[str, Any]], pr: int, head: str) -> tuple[bool, str]:
    """Condition 1, second record: the Auditor's newest row for `pr` is CLEAR for `head`."""
    mine = [r for r in rows if r.get("pr") == pr]
    if not mine:
        return False, "no Auditor registry row"
    last = mine[-1]
    if last.get("verdict") != "CLEAR" or last.get("sha") != head:
        return (
            False,
            f"the Auditor's newest row is {last.get('verdict')} {str(last.get('sha'))[:9]}",
        )
    return True, f"Auditor registry CLEAR {head[:9]}"


def comment_clear(found: list[Mapping[str, Any]], head: str) -> tuple[bool, str]:
    """Condition 1, first record: the newest AUDIT verdict comment is CLEAR for `head`."""
    if not found:
        return False, "no AUDIT verdict comment"
    last = found[-1]
    if last.get("verdict") != "CLEAR" or last.get("sha") != head:
        return (
            False,
            f"the newest AUDIT comment is {last.get('verdict')} {str(last.get('sha'))[:9]}",
        )
    return True, f"AUDIT CLEAR {head[:9]}"


# ----------------------------------------------------------------------------- the veto window


def notice(pr: int, head: str, root_files: Iterable[str]) -> tuple[str, str]:
    """(title, body) of the ROOT veto notice, in plain words."""
    files = ", ".join(sorted(root_files)) or "(none listed)"
    title = (
        f"PR #{pr} {head[:9]} CHANGES HOW MERGES ARE APPROVED: auto-merges in "
        f"{ROOT_VETO_H:.0f} h unless vetoed"
    )
    body = (
        f"PR #{pr} at {head} changes the merge machinery itself: {files}. The Auditor CLEARed it "
        f"and every check passed. The box merges it after {ROOT_VETO_H:.0f} h. To stop it: an "
        "AUDIT HOLD on the PR, a HOLD row, DEACTIVATE merges, or a new push."
    )
    return title, body


def receipt(returncode: int, stdout: str) -> str | None:
    """The delivery receipt of one notice send, or None when it was not delivered."""
    if returncode != 0:
        return None
    got = [int(n) for n in _DELIVERED.findall(stdout or "")]
    if not got or max(got) <= 0:
        return None
    return " ".join((stdout or "").split())[:200]


def notice_comment(head: str, got: str) -> str:
    """The anchoring PR comment posted after a DELIVERED notice; its time starts the window."""
    return f"{NOTICE_PREFIX} {head} delivered: {' '.join(got.split())[:200]}"


def _when(text: Any) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo is not None else None


def notices(
    comments: Iterable[Mapping[str, Any]], trusted: Iterable[str]
) -> list[tuple[datetime, str]]:
    """(time, head) of every unedited ROOT NOTICE comment by a trusted author, oldest first."""
    ok = set(trusted)
    out: list[tuple[datetime, str]] = []
    for c in comments:
        if str(c.get("author_association") or "") not in ok:
            continue
        if c.get("updated_at") not in (None, c.get("created_at")):
            continue
        m = _NOTICE.match(str(c.get("body") or ""))
        at = _when(c.get("created_at"))
        if m and at is not None:
            out.append((at, m.group(1)))
    return sorted(out)


def voids(
    verdicts: Iterable[Mapping[str, Any]],
    attempts: Mapping[str, list[Mapping[str, Any]]],
    board: Iterable[Mapping[str, Any]],
    deactivate: str,
    trusted: Iterable[str],
) -> list[datetime]:
    """Every moment that VOIDS a ROOT notice dated before it: a non-CLEAR AUDIT verdict (an edited
    trusted comment is one), a ROOT job attempt that failed, and a DEACTIVATE (or an edited
    trusted comment) on the switch board. An unreadable time counts as the far future."""
    far = datetime.max.replace(tzinfo=UTC)
    ok = set(trusted)
    out: list[datetime] = []
    for v in verdicts:
        if v.get("verdict") != "CLEAR":
            out.append(_when(v.get("at")) or far)
    for runs in attempts.values():
        for r in runs:
            if r.get("status") == "completed" and r.get("conclusion") != "success":
                out.append(_when(r.get("completed_at")) or far)
    for c in board:
        if str(c.get("author_association") or "") not in ok:
            continue
        if c.get("updated_at") not in (None, c.get("created_at")):
            out.append(_when(c.get("updated_at")) or far)
        elif str(c.get("body") or "").strip() == deactivate:
            out.append(_when(c.get("created_at")) or far)
    return out


def window(
    sent: list[tuple[datetime, str]], head: str, now: datetime, void: Iterable[datetime] = ()
) -> tuple[str, str]:
    """("open" | "elapsed" | "none", why) for the ROOT window of `head`: from the newest ROOT
    NOTICE for this head, unless anything in `void` is dated after it (then a new notice is due)."""
    mine = [at for at, h in sent if h == head]
    if not mine:
        return "none", f"no delivered ROOT notice for {head[:9]}"
    at = max(mine)
    if at > now:
        return "none", "the ROOT notice is dated in the future"
    late = [v for v in void if v >= at]
    if late:
        return "none", f"something went red, HOLD or off after the notice ({max(late).isoformat()})"
    age_h = (now - at).total_seconds() / 3600.0
    if age_h < ROOT_VETO_H:
        return "open", f"ROOT veto window {age_h:.1f} of {ROOT_VETO_H:.0f} h"
    return "elapsed", f"ROOT veto window passed ({age_h:.0f} h, no veto)"


# ----------------------------------------------------------------------------- the verdicts


def _common(f: Mapping[str, Any]) -> tuple[str, str] | None:
    """The checks both sides make, in order; None when all of them pass."""
    if f.get("sealed"):
        return "HOLD", "SEALED CORE, zuck's path only: " + "; ".join(f["sealed"])
    ok, why = eligible(f.get("cls_reasons") or [])
    if not ok:
        return "HOLD", f"ROOT: {why}"
    if f.get("hold"):
        return "HOLD", f"an AUDIT HOLD stands: {f['hold']}"
    if f.get("deactivated"):
        return "WAIT", "merges are DEACTIVATED"
    if not f.get("enforced"):
        return "WAIT", "the ROOT path is off until GitHub enforces the authority's status (Level 2)"
    if not f.get("repin_installed"):
        return "WAIT", "the ROOT path is off until the sealed re-pin service is installed"
    for key in ("comment", "registry"):
        good, kwhy = f.get(key) or (False, f"{key} not read")
        if not good:
            return "WAIT", kwhy
    return None


def authority_verdict(f: Mapping[str, Any]) -> tuple[str, list[str]]:
    """The release authority's verdict on a ROOT PR (policy.decide calls this for class ROOT).
    It enforces EVERY condition, the window included, so a CLEAR here (signed as class ROOT, and
    the Level 2 status success) is enough for GitHub to allow the merge. Facts beyond
    policy.decide's: sealed, enforced, repin_installed, comment, registry, root_jobs (jobs()),
    trusted_eval, window (window())."""
    got = _common(f)
    if got is not None:
        return got[0], [got[1]]
    if not f.get("patch_id"):
        return "WAIT", ["the change's patch-id could not be computed"]
    state, jwhy, _ = f.get("root_jobs") or ("pending", "no checks read", None)
    if state == "fail":
        return "FAIL", [f"ROOT path: {jwhy}"]
    if state != "pass":
        return "WAIT", [f"ROOT path: {jwhy}"]
    te, twhy = f.get("trusted_eval") or ("pending", "trusted-eval not read")
    if te == "fail":
        return "FAIL", [f"ROOT path: {twhy}"]
    if te != "pass":
        return "WAIT", [f"ROOT path: {twhy}"]
    if not f.get("fresh"):
        return "WAIT", [f"not up to date: {f.get('fresh_why')}"]
    w, wwhy = f.get("window") or ("none", "no ROOT notice")
    if w != "elapsed":
        return "WAIT", [f"ROOT path: {wwhy}"]
    return "CLEAR", [f"ROOT path: {jwhy}; {twhy}; {wwhy}"]


def gate_verdict(g: Mapping[str, Any]) -> tuple[str, str]:
    """The box gate's action on a ROOT PR: "MERGE" | "NOTIFY" (send the notice now) | "RERUN" |
    "WAIT" | "HOLD", and why. Same facts as authority_verdict, plus in_flight (why an earlier
    ROOT merge is not yet re-pinned, or "") and attested ((bool, why): the authority's class-ROOT
    CLEAR for this head, needed only to merge)."""
    got = _common(g)
    if got is not None:
        return got
    if g.get("in_flight"):
        return "WAIT", f"one ROOT merge at a time: {g['in_flight']}"
    state, jwhy, _ = g.get("root_jobs") or ("pending", "no checks read", None)
    if state == "rerun":
        return "RERUN", jwhy
    if state == "fail":
        return "HOLD", f"ROOT path: {jwhy}"
    if state != "pass":
        return "WAIT", jwhy
    te, twhy = g.get("trusted_eval") or ("pending", "trusted-eval not read")
    if te != "pass":
        return ("HOLD" if te == "fail" else "WAIT"), twhy
    if not g.get("fresh"):
        return "WAIT", f"not up to date: {g.get('fresh_why')}"
    w, wwhy = g.get("window") or ("none", "no ROOT notice")
    if w == "none":
        return "NOTIFY", wwhy
    if w == "open":
        return "WAIT", wwhy
    good, awhy = g.get("attested") or (False, "no authority attestation")
    if not good:
        return "WAIT", f"{wwhy}, but {awhy}"
    return "MERGE", f"ROOT path: {jwhy}; {twhy}; {wwhy}"

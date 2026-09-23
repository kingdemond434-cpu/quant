"""THE RESEARCH SANDBOX -- where third-party research code may run, and what it may never touch.

THE LAW (docs/LAWS.md 5h, the external code sandbox law, principal 2026-09-17): third-party and
open-source research code may execute ONLY inside isolated research environments with no broker
credentials, no production secrets, no direct live-order route, no write authority over canonical
evidence, no authority to merge production code, and controlled filesystem and network
permissions; dependencies, commit, licence, configuration and input datasets are recorded; outputs
are UNTRUSTED research donations until independently ingested and verified. "Run research code
aggressively in sandboxes; never give it live authority."

WHAT THIS MODULE ACTUALLY ENFORCES, AND WHAT IT ONLY DECLARES -- the distinction matters more than
the code does, because a boundary nobody can name is a boundary nobody can check:

  ENFORCED HERE          a scrubbed environment (every secret-shaped variable removed, and
                         `MT5_*`, `QUANT_*`, broker and API variables with them), a working
                         directory OUTSIDE the desk tree, a per-system virtual environment, a hard
                         timeout, an output size cap, and a read-only view of the desk (inputs are
                         COPIED into the sandbox, never mounted). NOT the licence: since
                         2026-09-23 an unread licence is a recorded label, not a refusal to start.
  DECLARED, NOT ENFORCED network egress. Windows offers no per-process firewall this desk can set
                         without administrator rules, so `network="allowlist"` is a STATEMENT OF
                         INTENT on this host and is reported as UNENFORCED_ON_THIS_HOST on every
                         run. Saying it is enforced would be the exact lie the law exists to stop.

WHAT IS ENFORCED HERE IS ABOUT ACTS, NOT ABOUT CONTENT (LAWS 5e, 2026-09-23). The isolation is
the boundary: no credentials, no live authority, no write into the desk tree. That is the desk
refusing to DO something, and it stays. What went was the CONTENT filtering that used to sit in
the same function: `provision()` refused an unread licence, a licence off a runnable list, and any
host outside an eight-domain allowlist. Those were discovery brakes -- they left every seed
UNDISPOSED on an unread LICENSE file -- and they are deleted. `provenance_notes()` records exactly
what they recorded, as labels that route REDISTRIBUTION and never stop a run. `refuse_reason()`
now answers only "there is nothing here to run": a non-executing disposition, or an upstream that
names no host. `run()` still refuses a sandbox that was never provisioned.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from libs.research import external_federation as fed

#: Sandboxes live OUTSIDE the desk tree, so nothing a third-party process writes can land in the
#: repository the gateway imports from. Overridable for tests only.
SANDBOX_ROOT = Path(os.environ.get("QUANT_SANDBOX_ROOT", r"C:\opt\quant-sandbox"))
#: Hosts the desk has code for and knows the raw-file shape of. A PROVENANCE LIST, NOT A GATE
#: (LAWS 5e, 2026-09-23): a host that is not on it is provisioned anyway and RECORDED as
#: off-roster. The old version refused every other host by name, so a research system published
#: anywhere but eight domains was never tested -- a discovery brake, deleted.
ALLOWED_HOSTS: frozenset[str] = frozenset({
    "github.com", "gitlab.com", "gitee.com", "codeberg.org", "bitbucket.org",
    "huggingface.co", "pypi.org", "files.pythonhosted.org"})
#: SPDX ids whose terms permit REDISTRIBUTING the code and derived work. A ROUTING LABEL on what
#: the desk may publish, NOT a permission to run: the desk runs anything it can fetch, inside the
#: isolated sandbox, for its own research. An unread licence is recorded UNVERIFIED and the run
#: happens regardless -- reading somebody's public code is not one of the five refused acts.
RUNNABLE_LICENCES: frozenset[str] = frozenset({
    "MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "MPL-2.0", "ISC", "Unlicense",
    "GPL-3.0", "GPL-2.0", "AGPL-3.0", "LGPL-3.0"})
#: The alias that says what the set now MEANS. Both names point at one object on purpose.
REDISTRIBUTABLE_LICENCES: frozenset[str] = RUNNABLE_LICENCES
#: Environment variables a sandboxed process may keep. Everything else is dropped, and anything
#: whose NAME looks like a secret is dropped even if it is on this list.
ENV_KEEP: frozenset[str] = frozenset({
    "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT", "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE", "OS", "LANG", "LC_ALL", "PYTHONIOENCODING", "HOME", "USERPROFILE"})
_SECRET_NAME = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CRED|AUTH|SESSION|COOKIE|LOGIN|ACCOUNT|BROKER|MT5|QUANT|"
    r"OPENAI|ANTHROPIC|DEEPSEEK|XAI|OPENROUTER|FRED|AWS|AZURE|GCP)", re.I)
#: A sandboxed run may not exceed these, whatever it thinks it is doing.
MAX_RUN_S = 3600
MAX_OUTPUT_BYTES = 8 * 1024 * 1024


def scrub_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """The environment a third-party process gets: the minimum to start python, and nothing that
    could authenticate as this desk. Measured intent: a process that wants a broker credential
    must FAIL, visibly, rather than find one."""
    src = dict(os.environ if base is None else base)
    out: dict[str, str] = {}
    for k, v in src.items():
        if k.upper() in ENV_KEEP and not _SECRET_NAME.search(k):
            out[k] = v
    out["QUANT_SANDBOX"] = "1"
    out["PYTHONDONTWRITEBYTECODE"] = "1"
    out["PYTHONIOENCODING"] = "utf-8"
    return out


@dataclass(frozen=True)
class Sandbox:
    """One system's isolated research environment."""

    system_id: str
    root: Path
    commit: str = "UNMEASURED"
    licence: str = "UNVERIFIED"
    provisioned: bool = False
    why: str = ""
    dependencies: tuple[str, ...] = ()
    policy: fed.SandboxPolicy = fed.POLICY
    network_enforced: bool = False

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def out(self) -> Path:
        return self.root / "out"

    def record(self) -> dict[str, Any]:
        return {"system_id": self.system_id, "root": str(self.root), "commit": self.commit,
                "licence": self.licence, "provisioned": self.provisioned, "why": self.why,
                "dependencies": list(self.dependencies),
                "policy": self.policy.__dict__,
                "network": ("allowlist (UNENFORCED_ON_THIS_HOST: no per-process firewall rule "
                            "is available to this desk; the claim is declared, not enforced)"
                            if not self.network_enforced else "allowlist (enforced)")}


@dataclass
class RunResult:
    system_id: str
    ok: bool
    why: str
    seconds: float = 0.0
    returncode: int | None = None
    stdout_tail: tuple[str, ...] = ()
    packet: fed.ExternalResearchPacket | None = None
    artefacts: tuple[str, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)


def _host_of(upstream: str) -> str:
    body = upstream.split("://")[-1]
    if body.startswith("github:"):
        return "github.com"
    if ":" in body and "/" in body and not body.startswith(("github.com", "gitlab.com")):
        prefix = body.split(":", 1)[0]
        return {"github": "github.com", "gitlab": "gitlab.com", "gitee": "gitee.com",
                "public": "", "paper": ""}.get(prefix, "")
    return body.split("/")[0]


def provenance_notes(system: fed.ExternalSystem, disposition: str) -> tuple[str, ...]:
    """The LABELS this system carries, none of which stop it being provisioned or run.

    Every one of these was a refusal before 2026-09-23 (LAWS 5e). An off-roster host and an
    unread or non-redistributable licence are now PROVENANCE, recorded on the sandbox row and
    carried into the research packet, so the desk knows what it may republish and still tests
    every system it can fetch.
    """
    notes: list[str] = []
    host = _host_of(system.upstream)
    if host and host not in ALLOWED_HOSTS:
        notes.append(f"off-roster host {host!r}: provisioned and recorded, never refused")
    if system.licence in ("UNVERIFIED", "", "UNMEASURED"):
        notes.append("licence UNVERIFIED at the pin: the run happens and the reading stays a task")
    elif system.licence not in REDISTRIBUTABLE_LICENCES:
        notes.append(f"licence {system.licence!r} withholds redistribution: research use only, "
                     f"nothing derived from it is republished")
    if disposition == "WRAPPED":
        notes.append("WRAPPED: upstream runs behind the desk's own adapter")
    return tuple(notes)


def refuse_reason(system: fed.ExternalSystem, disposition: str) -> str | None:
    """Why this system CANNOT be provisioned, or None.

    ONLY TWO THINGS ANSWER THIS NOW, and neither is a policy brake: a disposition that does not
    run upstream code at all, and an upstream string that names no host to fetch from. The host
    allowlist and the licence gates that used to live here were DISCOVERY BRAKES -- they left
    every seed UNDISPOSED on an unread LICENSE file -- and they are deleted; what they recorded
    now lands in `provenance_notes()`.
    """
    if disposition not in ("DIRECT", "WRAPPED"):
        return (f"disposition is {disposition}: only DIRECT and WRAPPED run upstream code "
                f"(REBUILT reproduces the mechanism in canonical infrastructure instead)")
    if not _host_of(system.upstream):
        return (f"upstream {system.upstream!r} names no resolvable host: there is nothing to "
                f"fetch. Pin the real repository URL and commit")
    return None


def provision(system: fed.ExternalSystem, disposition: str, *, root: Path | None = None,
              dry_run: bool = True) -> Sandbox:
    """Prepare (or refuse) a sandbox. `dry_run` is the DEFAULT on purpose: cloning a stranger's
    repository and installing its dependencies is an explicit act, never a side effect of an
    hourly leg."""
    base = (root or SANDBOX_ROOT) / system.system_id
    why = refuse_reason(system, disposition)
    if why:
        return Sandbox(system.system_id, base, licence=system.licence, provisioned=False, why=why)
    labels = provenance_notes(system, disposition)
    note = ("; " + "; ".join(labels)) if labels else ""
    if dry_run:
        return Sandbox(system.system_id, base, licence=system.licence, provisioned=False,
                       why="dry run: the sandbox is eligible and was not created" + note)
    base.mkdir(parents=True, exist_ok=True)
    (base / "work").mkdir(exist_ok=True)
    (base / "out").mkdir(exist_ok=True)
    return Sandbox(system.system_id, base, licence=system.licence, provisioned=True,
                   why="provisioned; the upstream checkout and its dependencies are the "
                       "operator's next step and are recorded when they land" + note)


def run(sandbox: Sandbox, argv: list[str], *, timeout_s: int = 600,
        inputs: dict[str, Path] | None = None) -> RunResult:
    """Execute inside the sandbox with a scrubbed environment and a hard timeout.

    Inputs are COPIED in; nothing is mounted, so a third-party process cannot reach the desk's
    files by following a path. The result is UNTRUSTED until `packet()` parses it.
    """
    if not sandbox.provisioned:
        return RunResult(sandbox.system_id, False, f"not provisioned: {sandbox.why}")
    bad = sandbox.policy.violations()
    if bad:
        return RunResult(sandbox.system_id, False, f"sandbox policy violated: {bad}")
    sandbox.work.mkdir(parents=True, exist_ok=True)
    sandbox.out.mkdir(parents=True, exist_ok=True)
    for name, src in (inputs or {}).items():
        try:
            shutil.copy2(src, sandbox.work / name)
        except OSError as exc:
            return RunResult(sandbox.system_id, False, f"input {name} unreadable: {exc}")
    t0 = time.monotonic()
    try:
        proc = subprocess.run(argv, cwd=str(sandbox.work), env=scrub_env(),
                              capture_output=True, text=True,
                              timeout=min(timeout_s, MAX_RUN_S), check=False)
    except subprocess.TimeoutExpired:
        return RunResult(sandbox.system_id, False, f"timed out after {timeout_s}s",
                         seconds=round(time.monotonic() - t0, 1))
    except OSError as exc:
        return RunResult(sandbox.system_id, False, f"failed to start: {type(exc).__name__}: {exc}")
    tail = tuple((proc.stdout or "")[-MAX_OUTPUT_BYTES:].strip().splitlines()[-20:])
    return RunResult(sandbox.system_id, proc.returncode == 0,
                     "ran" if proc.returncode == 0 else f"returncode {proc.returncode}",
                     seconds=round(time.monotonic() - t0, 1), returncode=proc.returncode,
                     stdout_tail=tail,
                     artefacts=tuple(sorted(p.name for p in sandbox.out.glob("*"))))


def packet(sandbox: Sandbox, path: Path | None = None) -> fed.ExternalResearchPacket:
    """Parse the sandbox's output as an ExternalResearchPacket -- the ONLY exit (LAWS 5h).

    A packet carrying a verdict-shaped field raises here, at the boundary, which is the whole
    point: the external engine may donate a hypothesis and may never donate a survivor.
    """
    p = path or (sandbox.out / "packet.json")
    doc = json.loads(p.read_text(encoding="utf-8-sig"))
    return fed.ExternalResearchPacket(
        system_id=str(doc.get("system_id") or sandbox.system_id),
        run_id=str(doc.get("run_id") or "UNMEASURED"),
        commit=str(doc.get("commit") or sandbox.commit),
        candidates=tuple(doc.get("candidates") or ()),
        datasets=tuple(doc.get("datasets") or ()),
        mechanisms=tuple(doc.get("mechanisms") or ()),
        representations=tuple(doc.get("representations") or ()),
        research_methods=tuple(doc.get("research_methods") or ()),
        trials_charged=int(doc.get("trials_charged") or 0),
        provenance={"sandbox": sandbox.record(), "path": str(p)})


@dataclass
class InstallResult:
    """What provisioning a per-system virtual environment measured."""

    system_id: str
    ok: bool
    why: str
    python: str = ""
    requirement: str = ""
    seconds: float = 0.0
    lockfile: str = ""
    env_hash: str = ""
    dependencies: tuple[str, ...] = ()

    def record(self) -> dict[str, Any]:
        return {"ok": self.ok, "why": self.why, "python": self.python,
                "requirement": self.requirement, "seconds": self.seconds,
                "lockfile": self.lockfile, "env_hash": self.env_hash,
                "n_dependencies": len(self.dependencies)}


def venv_python(sandbox: Sandbox) -> Path:
    """The per-system interpreter inside the sandbox root (Windows and POSIX layouts)."""
    venv = sandbox.root / "venv"
    win = venv / "Scripts" / "python.exe"
    return win if (win.exists() or os.name == "nt") else venv / "bin" / "python"


#: ONE environment for every adapter whose upstream is provisionable. Per-system venvs would
#: each re-install the scientific core (measured ~500 MB apiece), so the supply line would stop
#: on free disk long before it stopped on capability. `sandbox_provision.py` builds this one with
#: `--system-site-packages` over the desk's own interpreter and records what imports in it.
SHARED_ID = "_shared"


def shared_python(root: Path | None = None) -> Path:
    """The shared sandbox interpreter (it may not exist; the provisioner creates it)."""
    return venv_python(Sandbox(SHARED_ID, (root or SANDBOX_ROOT) / SHARED_ID))


def shared_modules(root: Path | None = None) -> dict[str, str]:
    """system_id -> the version the provisioner MEASURED importable in the shared venv.

    An absent or unreadable manifest is an empty mapping, never an exception: availability is a
    measurement the runner reports, and a missing file means it has not been measured yet.
    """
    path = (root or SANDBOX_ROOT) / SHARED_ID / "modules.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    rows = doc.get("modules") if isinstance(doc, dict) else None
    return {str(k): str(v) for k, v in (rows or {}).items()} if isinstance(rows, dict) else {}


def install(sandbox: Sandbox, requirement: str, *, timeout_s: int = 900,
            base_python: str | None = None) -> InstallResult:
    """Create the system's virtual environment and install ONE PINNED requirement into it under
    the scrubbed environment, then record the lockfile (`pip freeze`) and its hash.

    Refused unless the sandbox is provisioned (licence read, host allowlisted) and the
    requirement is pinned: LAWS 5m forbids a floating dependency, and a venv is a boundary only
    when what is inside it is known. The install runs OUTSIDE the desk tree with no secret in
    its environment; pip's own cache lives under the (kept) user profile.
    """
    if not sandbox.provisioned:
        return InstallResult(sandbox.system_id, False, f"not provisioned: {sandbox.why}")
    if "==" not in requirement and "@" not in requirement:
        return InstallResult(sandbox.system_id, False,
                             f"requirement {requirement!r} is not pinned: no floating dependency "
                             f"may be provisioned (LAWS 5m)", requirement=requirement)
    t0 = time.monotonic()
    env = scrub_env()
    py = venv_python(sandbox)
    if not py.exists():
        try:
            made = subprocess.run([base_python or sys.executable, "-m", "venv",
                                   str(sandbox.root / "venv")], env=env, capture_output=True,
                                  text=True, timeout=300, check=False, cwd=str(sandbox.root))
        except (subprocess.TimeoutExpired, OSError) as exc:
            return InstallResult(sandbox.system_id, False,
                                 f"venv creation failed: {type(exc).__name__}: {exc}",
                                 requirement=requirement)
        if made.returncode != 0 or not py.exists():
            return InstallResult(sandbox.system_id, False,
                                 f"venv creation failed: {(made.stderr or made.stdout)[-300:]}",
                                 requirement=requirement)
    argv = [str(py), "-m", "pip", "install", "--no-input", "--disable-pip-version-check",
            "--progress-bar", "off", requirement]
    try:
        proc = subprocess.run(argv, env=env, capture_output=True, text=True,
                              timeout=timeout_s, check=False, cwd=str(sandbox.root))
    except subprocess.TimeoutExpired:
        return InstallResult(sandbox.system_id, False, f"pip install timed out after "
                                                       f"{timeout_s}s", python=str(py),
                             requirement=requirement,
                             seconds=round(time.monotonic() - t0, 1))
    except OSError as exc:
        return InstallResult(sandbox.system_id, False,
                             f"pip failed to start: {type(exc).__name__}: {exc}",
                             python=str(py), requirement=requirement)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return InstallResult(sandbox.system_id, False,
                             "pip install failed: " + " | ".join(t[:160] for t in tail),
                             python=str(py), requirement=requirement,
                             seconds=round(time.monotonic() - t0, 1))
    frozen = subprocess.run([str(py), "-m", "pip", "freeze", "--disable-pip-version-check"],
                            env=env, capture_output=True, text=True, timeout=120, check=False,
                            cwd=str(sandbox.root))
    lines = tuple(ln.strip() for ln in (frozen.stdout or "").splitlines() if ln.strip())
    lock = sandbox.root / "requirements.lock"
    lock.write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest = hashlib.sha256(("\n".join(lines) + sys.version).encode("utf-8")).hexdigest()[:16]
    return InstallResult(sandbox.system_id, True, "installed", python=str(py),
                         requirement=requirement, seconds=round(time.monotonic() - t0, 1),
                         lockfile=str(lock), env_hash=digest, dependencies=lines[:300])


def stage(sandbox: Sandbox, files: Mapping[str, Path]) -> list[str]:
    """COPY files into the work directory at the given relative paths (subdirectories allowed).
    This is how the adapter code and the bundle reach a sandbox: copied, never mounted."""
    out: list[str] = []
    for rel, src in files.items():
        dst = sandbox.work / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        out.append(rel)
    return out


def status(root: Path | None = None) -> dict[str, Any]:
    """What is provisioned on this host, and the honest note about what is enforced."""
    base = root or SANDBOX_ROOT
    rows = []
    if base.exists():
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            rows.append({"system_id": d.name, "work": (d / "work").exists(),
                         "out": (d / "out").exists(),
                         "artefacts": sorted(q.name for q in (d / "out").glob("*"))[:10]})
    return {"root": str(base), "exists": base.exists(), "sandboxes": rows,
            "python": sys.executable,
            "enforced": ["scrubbed environment", "working directory outside the desk tree",
                         "hard timeout", "output cap", "inputs copied, never mounted"],
            "declared_not_enforced": ["network egress (no per-process firewall rule available to "
                                      "this desk on this host)"],
            "law": "docs/LAWS.md 5h -- the external code sandbox law"}

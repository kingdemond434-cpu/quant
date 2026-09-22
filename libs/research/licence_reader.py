"""THE LICENCE READER -- a system's terms, read at a pin from the place that publishes them.

LAWS 5h: DIRECT execution is refused while a licence is UNVERIFIED, and a licence is never
asserted from memory. This module is the only lawful way a roster row's `licence` changes: it
reads the terms at a pin, normalises them to the SPDX ids `sandbox.RUNNABLE_LICENCES` speaks, and
records WHAT it read and WHERE (`basis`, `source`, `pin`, `commit_sha`, `read_at`). When nothing
could be read the reading stays UNVERIFIED and carries the reason -- an unread licence is a task,
never a guess about somebody else's terms.

TWO SOURCES, NO THIRD-PARTY CODE EXECUTED. A PyPI-distributed system is read from the package
METADATA of a WHEEL fetched with `pip download --no-deps --only-binary :all:` into the sandbox
root under the scrubbed environment (a wheel is a zip; reading it runs nothing), with PyPI's JSON
index as the fallback for sdist-only projects (an sdist's metadata would require executing its
build backend, which is exactly what may not happen outside `sandbox.run`). A repository-hosted
system is read from the raw LICENSE at the pinned commit over the allowlisted hosts only; the pin
is resolved once with `git ls-remote` and recorded, so the exact revision is persisted (LAWS 5m).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from libs.research import external_federation as fed
from libs.research import sandbox as sb

Fetch = Callable[[str], bytes]

#: Hosts a licence read may fetch from. `raw.githubusercontent.com` is github.com's raw-file
#: endpoint and is the ONLY host added beyond the provisioning allowlist.
FETCH_HOSTS: frozenset[str] = frozenset({
    "pypi.org", "files.pythonhosted.org", "raw.githubusercontent.com", "gitlab.com",
    "gitee.com", "codeberg.org", "bitbucket.org"})
#: Raw-file URL shapes of the allowlisted code hosts.
RAW_URLS: dict[str, str] = {
    "github.com": "https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{name}",
    "gitlab.com": "https://gitlab.com/{owner}/{repo}/-/raw/{ref}/{name}",
    "gitee.com": "https://gitee.com/{owner}/{repo}/raw/{ref}/{name}",
    "codeberg.org": "https://codeberg.org/{owner}/{repo}/raw/commit/{ref}/{name}",
    "bitbucket.org": "https://bitbucket.org/{owner}/{repo}/raw/{ref}/{name}",
}
LICENCE_FILES: tuple[str, ...] = ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCE", "COPYING",
                                  "LICENSE.rst", "COPYING.txt", "LICENSE-MIT", "LICENSE.MIT")
#: Where a seed that names only `public:<name>` is actually distributed. Only names whose
#: identity is certain: a wrong distribution name would read the wrong project's terms, which is
#: worse than UNVERIFIED. Systems WITH adapters are named in `libs.research.adapters.SPECS`.
PYPI_DISTRIBUTIONS: dict[str, str] = {
    "pymc": "pymc", "neuralforecast": "neuralforecast", "darts": "u8darts", "kats": "kats",
    "merlion": "salesforce-merlion", "aeon": "aeon", "tpot": "TPOT", "openspiel": "open_spiel",
    "pyg_temporal": "torch-geometric-temporal", "ripser": "ripser", "ray": "ray",
    "reservoirpy": "reservoirpy", "kymatio": "kymatio", "sbi": "sbi", "pyribs": "ribs",
    "dspy": "dspy", "arcticdb": "arcticdb", "featuretools": "featuretools",
    "cvxportfolio": "cvxportfolio", "openevolve": "openevolve", "easytpp": "easy-tpp",
    "chronos2": "chronos-forecasting", "timesfm": "timesfm", "moment": "momentfm",
    "tushare": "tushare",
}
#: Repository homes for `public:` seeds whose code lives on an allowlisted host.
REPOSITORIES: dict[str, str] = {
    "idtxl": "github:pwollstadt/IDTxl", "alphagen": "github:RL-MLDM/alphagen",
    "abides": "github:abides-sim/abides", "ai_scientist": "github:SakanaAI/AI-Scientist-v2",
    "dso": "github:dso-org/deep-symbolic-optimization",
    "darwin_godel_machine": "github:jennyzzt/dgm", "kronos": "github:shiyu-coder/Kronos",
}
FETCH_TIMEOUT_S = 30
PIP_TIMEOUT_S = 240

#: SPDX normalisation of the free text PyPI classifiers and `License` fields carry. ORDER IS THE
#: RULE: LGPL/AGPL before GPL, 2-clause before bare BSD, so a specific match wins a generic one.
_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"AGPL|Affero", re.I), "AGPL-3.0"),
    (re.compile(r"LGPL|Lesser General Public", re.I), "LGPL-3.0"),
    (re.compile(r"GPL[- ]?2|GPLv2|General Public License v2", re.I), "GPL-2.0"),
    (re.compile(r"GPL[- ]?3|GPLv3|General Public License v3|\bGPL\b", re.I), "GPL-3.0"),
    (re.compile(r"Apache", re.I), "Apache-2.0"),
    (re.compile(r"\bMIT\b|Expat", re.I), "MIT"),
    (re.compile(r"BSD[- ]?2|Simplified BSD|FreeBSD", re.I), "BSD-2-Clause"),
    (re.compile(r"BSD[- ]?3|New BSD|Modified BSD|Revised BSD", re.I), "BSD-3-Clause"),
    (re.compile(r"\bBSD\b", re.I), "BSD-3-Clause"),
    (re.compile(r"MPL|Mozilla Public", re.I), "MPL-2.0"),
    (re.compile(r"\bISC\b", re.I), "ISC"),
    (re.compile(r"Unlicense", re.I), "Unlicense"),
    (re.compile(r"CC[- ]BY[- ]NC|Non-?Commercial", re.I), "CC-BY-NC-4.0"),
    (re.compile(r"Proprietary|Commercial", re.I), "Proprietary"),
)
#: Signatures of licence BODIES (a LICENSE file, or a `License` field carrying the whole text).
_BODIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Unlicense", re.compile(r"This is free and unencumbered software", re.I)),
    ("ISC", re.compile(r"Permission to use, copy, modify, and/or distribute this software for any "
                       r"purpose with or without fee", re.I)),
    ("MIT", re.compile(r"Permission is hereby granted, free of charge", re.I)),
    ("Apache-2.0", re.compile(r"Apache License[\s,]+Version 2\.0", re.I)),
    ("AGPL-3.0", re.compile(r"GNU AFFERO GENERAL PUBLIC LICENSE", re.I)),
    ("LGPL-3.0", re.compile(r"GNU LESSER GENERAL PUBLIC LICENSE", re.I)),
    ("GPL-2.0", re.compile(r"GNU GENERAL PUBLIC LICENSE\s+Version 2", re.I)),
    ("GPL-3.0", re.compile(r"GNU GENERAL PUBLIC LICENSE\s+Version 3", re.I)),
    ("MPL-2.0", re.compile(r"Mozilla Public License,? (?:Version |v\.? ?)2\.0", re.I)),
    ("BSD", re.compile(r"Redistribution and use in source and binary forms", re.I)),
)
_BSD_THIRD_CLAUSE = re.compile(r"Neither the name", re.I)


@dataclass(frozen=True)
class LicenceReading:
    """What was read, from where, at which pin. UNVERIFIED carries its reason in `why`."""

    system_id: str
    licence: str = "UNVERIFIED"
    basis: str = ""
    source: str = ""
    pin: str = ""
    version: str = ""
    commit_sha: str = ""
    read_at: str = ""
    why: str = ""

    @property
    def read(self) -> bool:
        return self.licence != "UNVERIFIED"

    @property
    def runnable(self) -> bool:
        return self.licence in sb.RUNNABLE_LICENCES

    def record(self) -> dict[str, Any]:
        return {**asdict(self), "runnable": self.runnable}


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def normalise(text: str | None) -> str:
    """Free licence text or a classifier -> the SPDX id the runnable list speaks, or UNVERIFIED.

    A licence BODY is recognised by its signature before any keyword rule runs, so a `License`
    field that carries the whole 2-clause BSD text is BSD-2-Clause and not a bare "BSD" guess.
    """
    if not text or not str(text).strip():
        return "UNVERIFIED"
    body = classify_body(str(text))
    if body != "UNVERIFIED":
        return body
    head = str(text).strip()[:400]
    for rx, spdx in _RULES:
        if rx.search(head):
            return spdx
    return "UNVERIFIED"


def classify_body(text: str) -> str:
    """The SPDX id of a licence BODY by its signature phrases; BSD's clause count from the text."""
    for spdx, rx in _BODIES:
        if rx.search(text):
            if spdx == "BSD":
                return "BSD-3-Clause" if _BSD_THIRD_CLAUSE.search(text) else "BSD-2-Clause"
            return spdx
    return "UNVERIFIED"


def _default_fetch(url: str) -> bytes:
    host = urlparse(url).netloc.lower()
    if host not in FETCH_HOSTS:
        raise PermissionError(f"host {host!r} is not in the licence-read allowlist "
                              f"{sorted(FETCH_HOSTS)}")
    req = Request(url, headers={"User-Agent": "quant-licence-reader/1 (LAWS 5h)",
                                "Accept": "application/json, text/plain, */*"})
    with urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
        return bytes(resp.read(2_000_000))


# --------------------------------------------------------------------------------- PyPI

def _from_metadata(fields: Mapping[str, Any]) -> tuple[str, str]:
    """(spdx, basis) from METADATA-shaped fields: License-Expression first (PEP 639), then the
    classifiers, then the free `License` field; a bare BSD classifier is refined by any licence
    body the metadata carries."""
    expr = str(fields.get("license_expression") or "").strip()
    if expr:
        got = normalise(expr)
        if got != "UNVERIFIED":
            return got, f"License-Expression: {expr}"
    classifiers = [str(c) for c in (fields.get("classifiers") or ())
                   if str(c).startswith("License ::")]
    body = str(fields.get("license") or "")
    for c in classifiers:
        got = normalise(c.split("::")[-1])
        if got != "UNVERIFIED":
            if got == "BSD-3-Clause" and "BSD-3" not in c and "3-Clause" not in c:
                refined = classify_body(body) if body else "UNVERIFIED"
                if refined.startswith("BSD"):
                    return refined, f"classifier {c!r} refined by the licence body"
                return got, f"classifier {c!r} (bare BSD; clause count unread, both are runnable)"
            return got, f"classifier {c!r}"
    if body:
        got = normalise(body)
        if got != "UNVERIFIED":
            return got, f"License field: {body.strip().splitlines()[0][:80]!r}"
    return "UNVERIFIED", ("no License-Expression, no License classifier and no readable License "
                          "field in the package metadata")


def parse_metadata(text: str) -> dict[str, Any]:
    """A wheel's `*.dist-info/METADATA` (RFC 822 headers) -> the fields `_from_metadata` reads."""
    out: dict[str, Any] = {"classifiers": []}
    for line in text.split("\n\n", 1)[0].splitlines():
        key, _, value = line.partition(":")
        k = key.strip().lower()
        if k == "classifier":
            out["classifiers"].append(value.strip())
        elif k in ("license", "license-expression", "version", "name"):
            out[k.replace("-", "_")] = value.strip()
    return out


def read_wheel(path: Path) -> dict[str, Any]:
    """METADATA fields plus any licence body shipped inside the wheel; reading a zip runs
    nothing."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        meta = next((n for n in names if n.endswith(".dist-info/METADATA")), None)
        fields = parse_metadata(zf.read(meta).decode("utf-8", "replace")) if meta else {}
        for n in names:
            low = n.lower()
            if ".dist-info/licenses/" in low or low.rsplit("/", 1)[-1].startswith(
                    ("license", "licence", "copying")):
                with contextlib.suppress(Exception):
                    body = zf.read(n).decode("utf-8", "replace")
                    if classify_body(body) != "UNVERIFIED":
                        fields["license_body"] = body
                        break
    return fields


def pip_download_wheel(requirement: str, dest: Path, *, timeout_s: int = PIP_TIMEOUT_S,
                       python: str | None = None) -> tuple[Path | None, str]:
    """`pip download --no-deps --only-binary :all:` under the scrubbed environment into `dest`.
    A wheel is data; an sdist would execute its build backend, so sdists are refused here."""
    dest.mkdir(parents=True, exist_ok=True)
    argv = [python or sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary",
            ":all:", "--disable-pip-version-check", "--no-input", "-q", "-d", str(dest),
            requirement]
    try:
        proc = subprocess.run(argv, cwd=str(dest), env=sb.scrub_env(), capture_output=True,
                              text=True, timeout=timeout_s, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, f"pip download failed to complete: {type(exc).__name__}: {exc}"
    wheels = sorted(dest.glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if proc.returncode != 0 or not wheels:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
        return None, f"no wheel for {requirement!r} on this interpreter: {tail[0][:200]}"
    return wheels[-1], "wheel downloaded"


def read_pypi(system_id: str, distribution: str, *, version: str = "",
              fetch: Fetch | None = None, root: Path | None = None,
              read_at: str | None = None) -> LicenceReading:
    """Read a PyPI-distributed system's licence at `distribution==version` (latest when unpinned).

    The wheel's METADATA is the primary source when a sandbox root is given; PyPI's JSON index is
    the fallback that also serves sdist-only projects without executing anything. Whatever
    answered is named in `source`; the version read becomes the pin.
    """
    stamp = read_at or now()
    fetch = fetch or _default_fetch
    basis, source, why = "", "", ""
    fields: dict[str, Any] = {}
    digest = ""
    if root is not None:
        req = f"{distribution}=={version}" if version else distribution
        wheel, note = pip_download_wheel(req, root / "_licences" / system_id)
        if wheel is not None:
            with contextlib.suppress(Exception):
                fields = read_wheel(wheel)
                if fields.get("license_body"):
                    fields["license"] = fields["license_body"]
                version = str(fields.get("version") or version)
                digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
                source = f"wheel:{wheel.name}"
        else:
            why = note
    if not fields:
        url = (f"https://pypi.org/pypi/{distribution}/{version}/json" if version
               else f"https://pypi.org/pypi/{distribution}/json")
        try:
            doc = json.loads(fetch(url).decode("utf-8"))
        except Exception as exc:
            return LicenceReading(system_id, why=(f"{why}; " if why else "")
                                  + f"PyPI index unreadable for {distribution!r}: "
                                    f"{type(exc).__name__}: {str(exc)[:160]}", read_at=stamp,
                                  source=f"pypi:{distribution}")
        info = doc.get("info") if isinstance(doc, dict) else None
        if not isinstance(info, Mapping):
            return LicenceReading(system_id, why=f"PyPI index for {distribution!r} carries no "
                                                 f"info block", read_at=stamp,
                                  source=f"pypi:{distribution}")
        fields = {"license": info.get("license"), "license_expression":
                  info.get("license_expression"), "classifiers": info.get("classifiers") or [],
                  "version": info.get("version")}
        version = str(info.get("version") or version)
        source = f"pypi-json:{distribution}"
        for u in (doc.get("urls") or []):
            if isinstance(u, Mapping) and u.get("packagetype") in ("bdist_wheel", "sdist"):
                digest = str(((u.get("digests") or {}).get("sha256")) or "")
                if digest:
                    break
    spdx, basis = _from_metadata(fields)
    pin = f"{distribution}=={version}" if version else distribution
    return LicenceReading(system_id, licence=spdx, basis=basis, source=source, pin=pin,
                          version=version, commit_sha=(f"sha256:{digest}" if digest else ""),
                          read_at=stamp,
                          why=("" if spdx != "UNVERIFIED" else basis))


# --------------------------------------------------------------------------------- repositories

def parse_repository(upstream: str) -> tuple[str, str, str] | None:
    """`github:owner/repo` | `https://gitlab.com/owner/repo(.git)` -> (host, owner, repo)."""
    text = upstream.strip()
    if ":" in text and "://" not in text:
        prefix, _, rest = text.partition(":")
        host = {"github": "github.com", "gitlab": "gitlab.com", "gitee": "gitee.com",
                "codeberg": "codeberg.org", "bitbucket": "bitbucket.org"}.get(prefix.lower())
        if not host:
            return None
        parts = rest.strip("/").split("/")
    else:
        u = urlparse(text)
        host = u.netloc.lower()
        parts = u.path.strip("/").split("/")
    if host not in RAW_URLS or len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    return host, parts[0], parts[1].removesuffix(".git")


def resolve_commit(host: str, owner: str, repo: str, *, timeout_s: int = FETCH_TIMEOUT_S) -> str:
    """The revision HEAD points at right now, via `git ls-remote` (git is not third-party code).
    Empty when it cannot be resolved -- the caller then records the read as UNVERIFIED."""
    git = shutil.which("git")
    if not git:
        return ""
    try:
        proc = subprocess.run([git, "ls-remote", f"https://{host}/{owner}/{repo}.git", "HEAD"],
                              capture_output=True, text=True, timeout=timeout_s, check=False,
                              env={**sb.scrub_env(), "GIT_TERMINAL_PROMPT": "0"})
    except (subprocess.TimeoutExpired, OSError):
        return ""
    for line in (proc.stdout or "").splitlines():
        sha = line.split("\t")[0].strip()
        if len(sha) == 40:
            return sha
    return ""


def read_repository(system_id: str, upstream: str, *, commit: str = "",
                    fetch: Fetch | None = None, read_at: str | None = None) -> LicenceReading:
    """Read the LICENSE at a pinned commit from an allowlisted host; pin HEAD when none is given."""
    stamp = read_at or now()
    fetch = fetch or _default_fetch
    parsed = parse_repository(upstream)
    if parsed is None:
        return LicenceReading(system_id, read_at=stamp, why=(
            f"upstream {upstream!r} names no allowlisted repository host: pin the real "
            f"repository URL (or distribution) before its licence can be read"))
    host, owner, repo = parsed
    sha = commit or resolve_commit(host, owner, repo)
    if not sha:
        return LicenceReading(system_id, read_at=stamp, source=f"{host}/{owner}/{repo}",
                              why=f"could not resolve a commit for {host}/{owner}/{repo}: the "
                                  f"repository is unreachable, private or gone")
    tried: list[str] = []
    for name in LICENCE_FILES:
        url = RAW_URLS[host].format(owner=owner, repo=repo, ref=sha, name=name)
        try:
            body = fetch(url).decode("utf-8", "replace")
        except Exception as exc:
            tried.append(f"{name}: {type(exc).__name__}")
            continue
        spdx = normalise(body)
        pin = f"{host}/{owner}/{repo}@{sha}"
        if spdx == "UNVERIFIED":
            return LicenceReading(system_id, source=f"{host}/{owner}/{repo}", pin=pin,
                                  commit_sha=sha, read_at=stamp,
                                  why=f"{name} at {sha[:12]} was read but matches no known "
                                      f"licence signature: read it by hand and record the id")
        return LicenceReading(system_id, licence=spdx, basis=f"{name} at {sha[:12]}",
                              source=f"{host}/{owner}/{repo}", pin=pin, commit_sha=sha,
                              read_at=stamp)
    return LicenceReading(system_id, source=f"{host}/{owner}/{repo}", commit_sha=sha,
                          read_at=stamp,
                          why=f"no licence file at {sha[:12]} among {list(LICENCE_FILES)}: "
                              f"{'; '.join(tried)[:200]}")


# --------------------------------------------------------------------------------- dispatch

def distribution_of(system: fed.ExternalSystem) -> tuple[str, str]:
    """(distribution, pinned version) for a PyPI-distributed system, or ('', '')."""
    if system.upstream.startswith("pypi:"):
        name, _, ver = system.upstream[5:].partition("==")
        return name, ver
    try:
        from libs.research import adapters
        spec = adapters.SPECS.get(system.system_id)
    except Exception:
        spec = None
    if spec is not None:
        return spec.distribution, spec.version
    return PYPI_DISTRIBUTIONS.get(system.system_id, ""), ""


def read(system: fed.ExternalSystem, *, pin: str = "", fetch: Fetch | None = None,
         root: Path | None = None) -> LicenceReading:
    """Read this system's licence from wherever it is published; UNVERIFIED with the reason when
    nowhere is known. `pin` is a version for PyPI systems and a commit for repositories."""
    dist, version = distribution_of(system)
    if dist:
        return read_pypi(system.system_id, dist, version=pin or version, fetch=fetch, root=root)
    upstream = REPOSITORIES.get(system.system_id, system.upstream)
    if parse_repository(upstream) is not None:
        return read_repository(system.system_id, upstream, commit=pin, fetch=fetch)
    return LicenceReading(system.system_id, read_at=now(), why=(
        f"no distribution or allowlisted repository is known for {system.upstream!r}: name the "
        f"PyPI distribution or the repository and the licence becomes readable"))


def apply(row: dict[str, Any], reading: LicenceReading) -> None:
    """Record a reading on a ledger row. An UNVERIFIED reading records only its attempt."""
    row["licence_read_at"] = reading.read_at
    row["licence_source"] = reading.source or row.get("licence_source") or "UNMEASURED"
    if not reading.read:
        row["licence_why"] = reading.why
        return
    row["licence"] = reading.licence
    row["licence_basis"] = reading.basis
    row["pin"] = reading.pin
    if reading.commit_sha:
        row["commit_sha"] = reading.commit_sha
    row.pop("licence_why", None)


def dispose(system: fed.ExternalSystem, reading: LicenceReading) -> tuple[str, str]:
    """(disposition, why) once the licence is read: the principal's integration mode when the
    terms permit running it, REBUILT with the reason when they do not, UNDISPOSED when unread."""
    if not reading.read:
        return "UNDISPOSED", f"licence unread: {reading.why}"
    if reading.runnable:
        mode = system.integration if system.integration in fed.RUNNING_DISPOSITIONS else "WRAPPED"
        return mode, f"licence {reading.licence} read from {reading.basis} at {reading.pin}"
    return "REBUILT", (f"licence {reading.licence!r} is not on the runnable list "
                       f"{sorted(sb.RUNNABLE_LICENCES)}: REBUILT is the lawful route "
                       f"(read from {reading.basis} at {reading.pin})")

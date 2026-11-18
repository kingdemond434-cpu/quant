"""SUPPLY-CHAIN AUDIT (rea lane Z2d, 2026-11-18).

WHY. The box installs Python packages from this repo's manifests and every workflow runs third-party
GitHub Actions, some of them holding a private key or `contents: write`. A mutable action tag
(`@v1`) or an unpinned package is a door anyone who takes over that upstream can walk through. This
audit names every such door so it can be shut.

WHAT IT FLAGS (severity in brackets; HIGH and MEDIUM fail the run):
  ACTION_NOT_SHA     [HIGH]   a workflow `uses:` an action by tag/branch, not by 40-hex commit SHA
  PY_UNPINNED        [HIGH]   a Python requirement with no version at all
  PY_TYPOSQUAT       [HIGH]   a name one/two edits from a well-known package, not itself one
  PY_NOT_EXACT       [MEDIUM] a requirements file entry that is a range (>=, ~=), not `==`
  PY_NO_HASH         [MEDIUM] a requirements file entry pinned `==` without `--hash=sha256:...`
  PY_DUPLICATE       [LOW]    the same package declared twice in one file
  SCAN_ERROR         [HIGH]   a manifest the audit could not read: FAIL CLOSED, never "no findings"

pyproject.toml declares a LIBRARY, so its ranges are by design: only a bare, unversioned dependency
is flagged there. requirements*.txt files are what gets installed, so they are held to exact pins
with hashes.

NOT A PR CHECK. Run on a schedule by .github/workflows/supply-chain-audit.yml. It never gates a PR
(zuck's standing order: no new gates on non-money work, never fix a gate with a gate).

    python .github/scripts/supply_chain_audit.py [--root .] [--json out.json] [--md out.md]
    python .github/scripts/supply_chain_audit.py --fix-actions   # tags -> SHAs via git ls-remote

Exit: 0 clean (LOW only), 1 findings, 2 the audit itself crashed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

FAIL_SEVERITIES = {"HIGH", "MEDIUM"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USES_RE = re.compile(
    r"^(?P<indent>\s*-?\s*)uses:\s*(?P<q>['\"]?)(?P<ref>[^\s'\"#]+)(?P=q)(?P<rest>.*)$"
)
NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*(.*)$")

# Well-known PyPI names a typosquat imitates. Keep every package the repo depends on in here, so a
# near-miss of our own dependency (e.g. `pandsa`) is caught too.
POPULAR = {
    "numpy",
    "pandas",
    "scipy",
    "requests",
    "urllib3",
    "certifi",
    "idna",
    "charset-normalizer",
    "pyyaml",
    "pydantic",
    "pydantic-settings",
    "pyarrow",
    "duckdb",
    "psutil",
    "websockets",
    "python-dateutil",
    "pytz",
    "tzdata",
    "statsmodels",
    "arch",
    "ruff",
    "mypy",
    "pytest",
    "pytest-cov",
    "pytest-timeout",
    "pytest-xdist",
    "hypothesis",
    "scikit-learn",
    "joblib",
    "threadpoolctl",
    "matplotlib",
    "seaborn",
    "plotly",
    "streamlit",
    "fastapi",
    "uvicorn",
    "starlette",
    "httpx",
    "aiohttp",
    "flask",
    "django",
    "sqlalchemy",
    "cryptography",
    "pyopenssl",
    "setuptools",
    "wheel",
    "pip",
    "six",
    "attrs",
    "click",
    "jinja2",
    "markupsafe",
    "packaging",
    "typing-extensions",
    "boto3",
    "botocore",
    "s3transfer",
    "colorama",
    "tqdm",
    "rich",
    "lxml",
    "beautifulsoup4",
    "openpyxl",
    "xlrd",
    "polars",
    "numba",
    "llvmlite",
    "xgboost",
    "lightgbm",
    "catboost",
    "torch",
    "tensorflow",
    "keras",
    "transformers",
    "openai",
    "anthropic",
    "pre-commit",
    "black",
    "isort",
    "flake8",
    "pylint",
    "coverage",
    "tox",
    "virtualenv",
    "metatrader5",
    "vectorbt",
    "backtrader",
    "akshare",
    "snownlp",
    "youtube-transcript-api",
    "types-pyyaml",
    "yfinance",
    "ccxt",
    "ta-lib",
    "pandas-ta",
    "sympy",
    "networkx",
    "protobuf",
    "grpcio",
    "pillow",
    "opencv-python",
    "selenium",
    "playwright",
    "paramiko",
    "redis",
    "pymongo",
    "psycopg2",
    "psycopg2-binary",
    "pymysql",
    "orjson",
    "ujson",
    "msgpack",
    "zstandard",
}


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    path: str
    line: int
    subject: str
    detail: str
    fix: str = ""


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def distance(a: str, b: str) -> int:
    """Damerau-Levenshtein (optimal string alignment): a swap of two letters counts as one edit."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def typosquat_of(name: str, known: set[str]) -> str | None:
    n = norm(name)
    if n in known:
        return None
    limit = 1 if len(n) < 8 else 2
    best = min(known, key=lambda k: (distance(n, k), k), default=None)
    if best is not None and 0 < distance(n, best) <= limit:
        return best
    return None


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Join backslash continuations (hash lines) into one entry, keeping the first line number."""
    out: list[tuple[int, str]] = []
    buf, start = "", 0
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.split(" #", 1)[0] if not raw.lstrip().startswith("--hash") else raw
        if raw.lstrip().startswith("#"):
            line = ""
        if not buf:
            start = no
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
            continue
        buf += line
        if buf.strip():
            out.append((start, buf.strip()))
        buf = ""
    if buf.strip():
        out.append((start, buf.strip()))
    return out


def parse_requirement(entry: str) -> tuple[str, str, bool] | None:
    """(name, version spec, has_hash), or None for option lines (-r, -e, --index-url, URLs)."""
    if entry.startswith(("-", "git+", "http://", "https://")):
        return None
    has_hash = "--hash=" in entry
    head = entry.split("--hash=", 1)[0].split(";", 1)[0].strip()
    m = NAME_RE.match(head)
    if not m:
        raise ValueError(f"unparseable requirement: {entry!r}")
    return m.group(1), m.group(3).strip(), has_hash


def audit_requirements(path: Path, rel: str, known: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, int] = {}
    for no, entry in _logical_lines(path.read_text(encoding="utf-8")):
        parsed = parse_requirement(entry)
        if parsed is None:
            continue
        name, spec, has_hash = parsed
        key = norm(name)
        if key in seen:
            findings.append(
                Finding("PY_DUPLICATE", "LOW", rel, no, name, f"also declared on line {seen[key]}")
            )
        seen.setdefault(key, no)
        if not spec:
            findings.append(
                Finding(
                    "PY_UNPINNED",
                    "HIGH",
                    rel,
                    no,
                    name,
                    "no version at all",
                    f"pin it: {name}==<tested version>",
                )
            )
        elif not spec.startswith("==") or "*" in spec or "," in spec:
            findings.append(
                Finding(
                    "PY_NOT_EXACT",
                    "MEDIUM",
                    rel,
                    no,
                    name,
                    f"range {spec!r}",
                    "pin the exact tested version with ==",
                )
            )
        elif not has_hash:
            findings.append(
                Finding(
                    "PY_NO_HASH",
                    "MEDIUM",
                    rel,
                    no,
                    name,
                    f"{spec} without --hash",
                    "regenerate with `uv pip compile --generate-hashes` (or pip-compile)",
                )
            )
        squat = typosquat_of(name, known)
        if squat:
            findings.append(
                Finding(
                    "PY_TYPOSQUAT",
                    "HIGH",
                    rel,
                    no,
                    name,
                    f"one edit from {squat!r}",
                    f"confirm the name; did you mean {squat}?",
                )
            )
    return findings


def _pyproject_deps(data: dict[str, Any]) -> list[str]:
    proj = data.get("project", {})
    deps = list(proj.get("dependencies", []))
    for group in proj.get("optional-dependencies", {}).values():
        deps.extend(group)
    return deps


def audit_pyproject(path: Path, rel: str, known: set[str]) -> list[Finding]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    text_lines = path.read_text(encoding="utf-8").splitlines()
    findings: list[Finding] = []
    for dep in _pyproject_deps(data):
        parsed = parse_requirement(dep)
        if parsed is None:
            continue
        name, spec, _ = parsed
        no = next((i for i, ln in enumerate(text_lines, 1) if f'"{dep}"' in ln), 0)
        if not spec:
            findings.append(
                Finding(
                    "PY_UNPINNED",
                    "HIGH",
                    rel,
                    no,
                    name,
                    "no version bound",
                    f"add a floor and a next-major cap, e.g. {name}>=X,<X+1",
                )
            )
        squat = typosquat_of(name, known)
        if squat:
            findings.append(
                Finding(
                    "PY_TYPOSQUAT",
                    "HIGH",
                    rel,
                    no,
                    name,
                    f"one edit from {squat!r}",
                    f"confirm the name; did you mean {squat}?",
                )
            )
    return findings


def audit_workflow(path: Path, rel: str) -> list[Finding]:
    findings: list[Finding] = []
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = USES_RE.match(line)
        if not m:
            continue
        ref = m.group("ref")
        if ref.startswith(("./", "docker://")) or "@" not in ref:
            continue  # local action, or a docker image (digest-pinning is a separate lane)
        action, version = ref.rsplit("@", 1)
        if not SHA_RE.match(version):
            findings.append(
                Finding(
                    "ACTION_NOT_SHA",
                    "HIGH",
                    rel,
                    no,
                    action,
                    f"pinned to mutable ref {version!r}",
                    f"uses: {action}@<40-hex sha> # {version}",
                )
            )
    return findings


def requirement_files(root: Path) -> list[Path]:
    skip = {".git", "node_modules", ".venv", "venv", "dist", "backups", "third_party"}
    out = []
    for p in root.rglob("requirements*.txt"):
        if not skip.intersection(p.relative_to(root).parts):
            out.append(p)
    return sorted(out)


def run_audit(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    known = set(POPULAR)
    req_files = requirement_files(root)
    pyproject = root / "pyproject.toml"

    def guarded(rel: str, fn: Callable[..., list[Finding]], *args: Any) -> None:
        try:
            findings.extend(fn(*args))
        except Exception as exc:  # fail closed
            findings.append(
                Finding("SCAN_ERROR", "HIGH", rel, 0, rel, f"{type(exc).__name__}: {exc}")
            )

    for p in req_files:
        rel = p.relative_to(root).as_posix()
        guarded(rel, audit_requirements, p, rel, known)
    if pyproject.exists():
        guarded("pyproject.toml", audit_pyproject, pyproject, "pyproject.toml", known)
    wf_dir = root / ".github" / "workflows"
    workflows = sorted([*wf_dir.glob("*.yml"), *wf_dir.glob("*.yaml")]) if wf_dir.exists() else []
    if not workflows:
        findings.append(
            Finding(
                "SCAN_ERROR", "HIGH", ".github/workflows", 0, "workflows", "no workflow files found"
            )
        )
    for p in workflows:
        rel = p.relative_to(root).as_posix()
        guarded(rel, audit_workflow, p, rel)
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(findings, key=lambda f: (order[f.severity], f.code, f.path, f.line))


def resolve_sha(action: str, ref: str, token: str | None = None) -> str:
    """The commit a tag/branch points to now, via anonymous `git ls-remote` (no API token, no rate
    limit). An annotated tag is peeled (`^{}`) to its commit."""
    owner_repo = "/".join(action.split("/")[:2])
    out = subprocess.run(
        [
            "git",
            "ls-remote",
            f"https://github.com/{owner_repo}",
            f"refs/tags/{ref}",
            f"refs/tags/{ref}^{{}}",
            f"refs/heads/{ref}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    refs: dict[str, str] = {}
    for line in out.splitlines():
        sha_part, _, name = line.partition("\t")
        if name:
            refs[name] = sha_part
    sha = (
        refs.get(f"refs/tags/{ref}^{{}}")
        or refs.get(f"refs/tags/{ref}")
        or refs.get(f"refs/heads/{ref}", "")
    )
    if not SHA_RE.match(sha):
        raise ValueError(f"{action}@{ref} did not resolve to a commit sha: {sha!r}")
    return sha


def fix_actions(
    root: Path, resolver: Callable[..., str] = resolve_sha, token: str | None = None
) -> list[str]:
    """Mechanical repair: every `uses: a/b@tag` becomes `uses: a/b@<sha> # tag`.

    Returns the changed files."""
    cache: dict[str, str] = {}
    changed = []
    for p in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        dirty = False
        for i, line in enumerate(lines):
            m = USES_RE.match(line.rstrip("\n"))
            if not m or m.group("ref").startswith(("./", "docker://")) or "@" not in m.group("ref"):
                continue
            action, version = m.group("ref").rsplit("@", 1)
            if SHA_RE.match(version):
                continue
            key = f"{action}@{version}"
            if key not in cache:
                cache[key] = resolver(action, version, token)
            nl = "\n" if line.endswith("\n") else ""
            lines[i] = f"{m.group('indent')}uses: {action}@{cache[key]} # {version}{nl}"
            dirty = True
        if dirty:
            p.write_text("".join(lines), encoding="utf-8")
            changed.append(p.relative_to(root).as_posix())
    return changed


def to_markdown(findings: list[Finding]) -> str:
    failing = [f for f in findings if f.severity in FAIL_SEVERITIES]
    head = "FAIL" if failing else "PASS"
    out = [
        f"## Supply-chain audit: {head}",
        "",
        f"{len(failing)} failing finding(s), {len(findings) - len(failing)} low.",
        "",
        "| Severity | Code | Where | Subject | Detail | Fix |",
        "|---|---|---|---|---|---|",
    ]
    for f in findings:
        where = f"`{f.path}:{f.line}`"
        out.append(f"| {f.severity} | {f.code} | {where} | `{f.subject}` | {f.detail} | {f.fix} |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--md", dest="md_out")
    ap.add_argument(
        "--fix-actions", action="store_true", help="rewrite action tags to commit SHAs in place"
    )
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.fix_actions:
            for rel in fix_actions(root):
                print(f"pinned actions in {rel}")
        findings = run_audit(root)
    except Exception as exc:  # the audit itself broke: fail closed
        print(f"SUPPLY-CHAIN AUDIT CRASHED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    md = to_markdown(findings)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps([asdict(f) for f in findings], indent=2), encoding="utf-8"
        )
    if args.md_out:
        Path(args.md_out).write_text(md, encoding="utf-8")
    print(md)
    return 1 if any(f.severity in FAIL_SEVERITIES for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())

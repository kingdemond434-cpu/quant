#!/usr/bin/env python3
"""Deterministic base-vs-head checks of an independent-reviewer FAIL's findings.

    python ops/release/finding_refuter.py --diff D.patch --findings F.json [--base REF] [--out P]

A small model's FAIL is final (local_models.json `votes`), and on 11-03/04 it failed heads for
things their diffs do not do (#661, #666, #665: "adds new network destinations" on a lint diff).
ops/release/authority/ONE_TIME_AUTHORISATION.md designs the exit: a finding clears only when a
deterministic base-vs-head check refutes it AND a second, independent model family agrees,
under a ROOT_POLICY rule. This file is the first half and nothing more:

- It writes one JSON report and changes nothing. It never turns a FAIL into a PASS; whatever
  consumes the report (a ROOT rule, not this file) also needs the second family's agreement.
- Each finding is sorted into the review rubric's rules (ops/release/review_rubric.md) by the
  words it uses. Only four rules have a check the diff can answer:
    risk     (rule 1)  no changed file is a money file (the reviewer's own is_money_file)
    control  (rule 2)  no changed file is a protected or secrets path; no added secret read
    network  (rule 4)  no added host absent from the base, no added network call in code
    hidden   (rule 5)  no added eval/exec/base64/encoded-command line
  evidence (rule 3), mismatch (rule 6) and a finding that names no rule are UNKNOWN, always.
- A finding is REFUTED only when every rule it names is refuted. One UPHELD finding makes the
  report UPHELD; otherwise one UNKNOWN makes it UNKNOWN. No findings at all is UNKNOWN.
- A head whose diff touches the PROTECTED tuple (.github/scripts/audit_gate.py), a secrets path
  or a money file is INELIGIBLE before any finding is read: those heads take the manual path.
- A diff that addresses the reviewer is UPHELD: it never reached a model and never clears.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ir = _load("_ir_refuter", HERE / "independent_review.py")
_ag = _load("_ag_refuter", ROOT / ".github" / "scripts" / "audit_gate.py")

#: rubric rule -> the words that invoke it (casefolded finding text)
RULES: dict[str, re.Pattern[str]] = {
    "risk": re.compile(
        r"\brisk\b|\bsiz(e|es|ing)\b|leverage|exposure|\bpositions?\b|loss[- ]limit|\bstops?\b"
        r"|kill[- ]?switch|freeze|drawdown|fails?[- ]open"
    ),
    "control": re.compile(
        r"\brelease\b|\bmerg\w*|approv\w*|\baudit\w*|\bci\b|workflow|trusted|\bseal\w*|\bsign(ed|ing)?\b"
        r"|\badopt\w*|roll[- ]?back|credential|\btokens?\b|secrets?\b|password|permission|privilege"
    ),
    "network": re.compile(
        r"network|destination|\bhosts?\b|\burls?\b|endpoint|external (api|service|server)"
        r"|fetch\w*|send\w* data|exfiltrat|data leak\w*|upload|\bbrokers?\b|\baccounts?\b"
        r"|order types?|copy\w* trades?"
    ),
    "hidden": re.compile(
        r"obfuscat|encoded|base64|dynamic code|\beval\b|\bexec\b|under (test|ci)"
        r"|looks? for (this|the) review"
    ),
    "evidence": re.compile(
        r"look-?ahead|(?<!data )leakage|point[- ]in[- ]time|holdout|trial count|certif|replicat"
        r"|forward clock|\bledgers?\b|\bhistory\b|\bjournal\b"
    ),
    "mismatch": re.compile(
        r"not (documented|described|explained)|undocumented|does not match|too large|tangled"
    ),
}
CHECKED = ("risk", "control", "network", "hidden")

URL_HOST = re.compile(r"\bhttps?://([A-Za-z0-9.-]+)")
NET_CALL = re.compile(
    r"\brequests\.|\bhttpx\b|urllib\.request|\burlopen\(|\bsocket\.|\baiohttp\b|websocket"
    r"|http\.client|\bsmtplib\b|\bftplib\b|\bparamiko\b|Invoke-WebRequest|Invoke-RestMethod"
    r"|\bcurl\s|\bwget\s|Net\.WebClient|\bgh (api|pr|release|repo|workflow|run)\b|\bgit push\b"
    r"|\bscp\s|\bssh\s|\birm\s|\biwr\s|Start-BitsTransfer"
)
HIDDEN = re.compile(
    r"\beval\(|\bexec\(|base64|b64decode|\bmarshal\b|pickle\.loads|__import__\(|\bcompile\("
    r"|-EncodedCommand|FromBase64String|codecs\.decode|Invoke-Expression|\biex\b|importlib"
    r"|getattr\(__builtins__|\b(zlib|bz2|lzma|gzip)\.decompress|\[Convert\]::|\s-enc\s"
)
#: A process launch, whatever it runs: the deny-lists cannot see into its arguments (AD #689 #2).
SUBPROC = re.compile(r"\bsubprocess\b|\bos\.(system|popen|exec\w*|spawn\w*)\b|Start-Process|&\s*\$")
#: Verbs of the release machinery: control and risk are never refuted by path alone when added
#: code names one (AD #689 #3).
CONTROL_VERB = re.compile(r"\b(merg\w*|approv\w*|adopt\w*|seal\w*|promot\w*|attest\w*)\b", re.I)
SECRET_READ = re.compile(
    r"data[/\\]+secrets|(environ|getenv)\W[^\n]{0,40}(KEY|TOKEN|SECRET|PASSWORD)", re.IGNORECASE
)
CODE = re.compile(
    r"\.(py|pyi|ps1|psm1|psd1|psc1|bat|cmd|sh|js|ts|rs|mq4|mq5|mqh|yml|yaml|vbs|cs|go|rb)$"
    r"|^(ops|scripts)/(.*/)?[^/.]+$"  # an extensionless script under ops/ or scripts/
)
#: Code and config: an undecodable byte here can hide code, so the report is UNKNOWN (AD #681).
CONFIG = re.compile(r"\.(toml|json|jsonl|cfg|ini|manifest|txt)$|(^|/)\.github/")
CODE_GLOBS = ("*.py", "*.pyi", "*.ps1", "*.psm1", "*.psd1", "*.psc1", "*.bat", "*.cmd", "*.sh",
              "*.js", "*.ts", "*.rs", "*.mq4", "*.mq5", "*.mqh", "*.yml", "*.yaml", "*.vbs", "*.cs",
              "*.go", "*.rb")  # fmt: skip


def added(diff: str) -> list[tuple[str, str]]:
    """(path, text) for every added line, the path from the `+++ b/` header of its file."""
    out: list[tuple[str, str]] = []
    path = ""
    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            path = ""
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("+") and path:
            out.append((path, line[1:]))
    return out


def kinds(finding: str) -> list[str]:
    text = " ".join(finding.casefold().split())
    return [k for k, rx in RULES.items() if rx.search(text)]


def eligible(files: list[str], closure: frozenset[str] | None) -> tuple[bool, list[str]]:
    why = [f"protected {f}" for f in files if any(fnmatch.fnmatch(f, p) for p in _ag.PROTECTED)]
    why += [f"secrets {f}" for f in files if any(fnmatch.fnmatch(f, p) for p in _ag.SECRETS)]
    why += [f"money {f}" for f in files if _ir.is_money_file(f, closure)]
    return not why, why


def check(
    kind: str,
    files: list[str],
    plus: list[tuple[str, str]],
    known_hosts: frozenset[str],
    floor: tuple[str, ...],
    closure: frozenset[str] | None,
) -> tuple[str, list[str]]:
    """(REFUTED | UPHELD | UNKNOWN, evidence lines) for one rubric rule on this diff."""
    hits: list[str]
    code = [(p, t) for p, t in plus if CODE.search(p)]
    launch = [f"{p}: {t.strip()[:120]}" for p, t in code if SUBPROC.search(t)]
    if kind in ("risk", "control", "network", "hidden") and launch:
        return "UNKNOWN", ["a process launch the deny-lists cannot see into", *launch[:10]]
    if kind in ("risk", "control"):
        busy = [f"{p}: {t.strip()[:120]}" for p, t in code
                if NET_CALL.search(t) or HIDDEN.search(t) or CONTROL_VERB.search(t)]  # fmt: skip
        if busy:
            return "UNKNOWN", [
                "added code calls out, hides code or names a release verb",
                *busy[:10],
            ]
    if kind == "risk":
        hits = [f"money file {f}" for f in files if _ir.is_money_file(f, closure)]
    elif kind == "control":
        hits = [f"floor path {f}" for f in files if any(fnmatch.fnmatch(f, p) for p in floor)]
        hits += [f"{p}: {t.strip()[:120]}" for p, t in plus if SECRET_READ.search(t)]
    elif kind == "network":
        hits = [
            f"{p}: new host {h}"
            for p, t in plus
            for h in URL_HOST.findall(t)
            if h.casefold() not in known_hosts
        ]
        hits += [
            f"{p}: {t.strip()[:120]}" for p, t in plus if CODE.search(p) and NET_CALL.search(t)
        ]
    elif kind == "hidden":
        hits = [f"{p}: {t.strip()[:120]}" for p, t in plus if CODE.search(p) and HIDDEN.search(t)]
    else:
        return "UNKNOWN", [f"rule '{kind}' has no deterministic check"]
    return ("UPHELD", hits[:20]) if hits else ("REFUTED", [f"no {kind} change in the diff"])


def refute(diff: str, findings: list[str], known_hosts: frozenset[str],
           floor: tuple[str, ...], closure: frozenset[str] | None) -> dict[str, Any]:  # fmt: skip
    files = _ir.changed_files(diff)
    ok, why = eligible(files, closure)
    if not ok:
        return {"verdict": "INELIGIBLE", "why": why, "findings": []}
    if _ir.addressed_to_reviewer(diff):
        return {"verdict": "UPHELD", "why": ["the diff addresses the reviewer"], "findings": []}
    plus = added(diff)
    bad = sorted({p for p, t in plus if "\ufffd" in t and (CODE.search(p) or CONFIG.search(p))})
    if bad:
        return {"verdict": "UNKNOWN", "why": [f"undecodable bytes in {p}" for p in bad],
                "findings": []}  # fmt: skip
    rows: list[dict[str, Any]] = []
    for text in findings:
        ks = kinds(text)
        if not ks:
            rows.append({"finding": text, "rules": [], "verdict": "UNKNOWN",
                         "evidence": ["names no rubric rule"]})  # fmt: skip
            continue
        per = {k: check(k, files, plus, known_hosts, floor, closure) for k in ks}
        vs = {v for v, _ in per.values()}
        verdict = "UPHELD" if "UPHELD" in vs else "UNKNOWN" if "UNKNOWN" in vs else "REFUTED"
        rows.append({"finding": text, "rules": ks, "verdict": verdict,
                     "evidence": {k: e for k, (_, e) in per.items()}})  # fmt: skip
    vs = {r["verdict"] for r in rows}
    verdict = (
        "UNKNOWN" if not rows
        else "UPHELD" if "UPHELD" in vs
        else "UNKNOWN" if "UNKNOWN" in vs
        else "REFUTED"
    )  # fmt: skip
    return {"verdict": verdict, "files": files, "findings": rows}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout  # fmt: skip


def base_hosts(base: str) -> frozenset[str]:
    """Every http(s) host literal in the base tree's CODE files: a host only a doc mentions is
    not one the system already talks to (AD #689 #4)."""
    try:
        out = _git("grep", "-h", "-o", "-I", "-E", r"https?://[A-Za-z0-9.-]+", base, "--",
                   *CODE_GLOBS)  # fmt: skip
    except subprocess.CalledProcessError as exc:  # grep exits 1 on no match
        out = exc.stdout or ""
    return frozenset(m.casefold() for m in URL_HOST.findall(out))


def base_text(base: str, rel: str) -> str | None:
    try:
        return _git("show", f"{base}:{rel}")
    except subprocess.CalledProcessError:
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--diff", required=True, help="unified diff, base...head")
    ap.add_argument("--findings", required=True, help="JSON: a list of strings, or the answer")
    ap.add_argument("--base", default="HEAD", help="base ref the hosts and lists are read at")
    ap.add_argument("--out", default="", help="write the report here as well")
    a = ap.parse_args(argv)
    diff = Path(a.diff).read_text(encoding="utf-8", errors="replace")
    raw = json.loads(Path(a.findings).read_text(encoding="utf-8"))
    findings = [str(x) for x in (raw.get("findings") if isinstance(raw, dict) else raw) or []]
    closure_txt = base_text(a.base, "ops/money_closure.txt")
    closure = None if closure_txt is None else _ir.closure_rows(closure_txt)
    floor_txt = base_text(a.base, "ops/release/protected_paths.txt") or ""
    floor = tuple(_ir.closure_rows(floor_txt)) + _ag.FORMERLY_PROTECTED
    rep = refute(diff, findings, base_hosts(a.base), floor, closure)
    text = json.dumps(rep, indent=1, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

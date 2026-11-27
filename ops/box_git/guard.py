"""THE BOX GUARD -- the verdict pen is deterministic code, never a seat (boot r23).

WHY (zuck 2026-11-27 13:13Z): "AI develops new code. An independent, protected automated checker
validates it ... If it passes, it can deploy automatically within existing authorization ... You
only intervene when the system needs to change its fundamental authority or protected
safeguards." 13:14Z: "is this adding complexity and slowness though". So this module is small and
every check is seconds to minutes; no model, no network, no wait on a person or a seat.

WHO HOLDS THE PEN. This file runs from the boot loop source (moved only by the owner-installed
boot mover) inside QuantForge-Loop as the non-admin `quantgate`. The PR's own code runs only under
`quantci` (the CI worker: non-admin, denied the trust, guard and token folders). The verdict is
written here, by the loop, into GUARD_DIR\\verdicts, which only Administrators, SYSTEM and
quantgate can write. An Auditor seat still reads every packet; its HOLD is honoured (a HOLD at the
head blocks) but its CLEAR is no longer needed.

THE CHECKS (first refusal wins; every one is a measurement, and UNMEASURED refuses):
  1. trust class by the PINNED trust checker: REFUSE refused; TRUST parked for the owner.
  2. static money rules on every changed money-path .py file, or every changed .py outside
     tests/ when the money reading is UNMEASURED (static_problems): no NEW network, model,
     subprocess, ctypes, dynamic-code import or call, and no literal naming a guard, trust, halt
     or token path. Counted base vs head, so code that already had them is not blocked.
  3. ceilings: an unreadable ops/release/ceilings.json fails; a raise is journalled in the
     verdict and never blocks (RISK AUTONOMY, zuck 11-14 and 2026-11-27 13:50Z). The prop firms'
     own caps stay REFUSE in the pinned checker (hard_caps): the one hard bound.
  4. money path only: the pinned risk invariants and risk suites (box_loop.risk_job, from the
     BASE), then the live entry files' import smoke (adopt_guard.smoke) under quantci.
  5. a cap on money-path merges per day (MONEY_MERGES_PER_DAY) and never a head the adopter
     rolled back.
A verdict names the guard's own hash (guard_hash): a verdict written by another guard build does
not count, so changing the guard voids every verdict it gave.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

GUARD_DIR = Path(r"C:\ProgramData\QuantBox\guard")
VERDICTS = "verdicts"
LEDGER = "merges.jsonl"
CONTEXT = "box-guard"
#: (D4) at most this many money-path merges in any 24 h; a busy day waits, it never drops.
MONEY_MERGES_PER_DAY = 48
#: The adopter's record of rolled-back releases (libs/ops/adopt_guard.ROLLBACKS_REL).
ROLLBACKS = Path(r"C:\opt\quant\desks\mt5\reports\ADOPT_ROLLBACKS.jsonl")
CEILINGS = "ops/release/ceilings.json"
SHA40 = re.compile(r"[0-9a-f]{40}")

#: (D2) modules a money-path file may not newly import: network, models, processes, native code,
#: dynamic loading. A new one is the owner's call (TRUST), never the guard's.
BANNED_IMPORTS = frozenset({
    "socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp", "websocket",
    "websockets", "ftplib", "smtplib", "openai", "anthropic", "groq", "cerebras", "litellm",
    "subprocess", "ctypes", "cffi", "importlib", "runpy", "pickle", "marshal", "multiprocessing",
})
#: (D2) calls a money-path file may not newly make.
BANNED_CALLS = frozenset({"exec", "eval", "compile", "__import__", "globals", "setattr",
                          "delattr", "system", "popen", "startfile", "spawnv", "execv"})
#: (D2) a literal naming one of these is a write the guard cannot follow: TRUST.
BANNED_LITERALS = re.compile(r"(?i)QuantBox[\\/]+(guard|trust|tokens|inbox)|new_risk_holds"
                             r"|ADOPT_NEW_RISK_HOLD|data[\\/]+secrets|GUARD_DIR")


@dataclass
class Verdict:
    sha: str
    base: str
    ok: bool
    cls: str            # PASS | TRUST | REFUSE | FAIL
    why: str
    money: bool = False
    checks: list[str] = field(default_factory=list)
    guard: str = ""
    at: str = ""


# ------------------------------------------------------------------------------ the pen
def guard_hash(files: Iterable[Path]) -> str:
    """sha256 over the guard's own bytes (this file, the trust checker, TRUST_SET): a verdict is
    worth only the code that wrote it (Audit D3). An unreadable file hashes as UNREADABLE, so it
    never matches a hash that was written while it could be read."""
    h = hashlib.sha256()
    for f in sorted(Path(p) for p in files):
        h.update(f.name.encode() + b"\0")
        try:
            h.update(f.read_bytes())
        except OSError:
            h.update(b"UNREADABLE")
        h.update(b"\0")
    return h.hexdigest()


def write_verdict(folder: Path, v: Verdict) -> Path:
    d = Path(folder) / VERDICTS
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{v.sha}.json"
    tmp = d / f".{v.sha}.part"
    tmp.write_text(json.dumps(asdict(v), sort_keys=True), encoding="utf-8")
    os.replace(tmp, f)
    return f


def read_verdict(folder: Path, sha: str, guard: str) -> Verdict | None:
    """The PASS verdict for exactly `sha` written by this guard build, or None."""
    if not SHA40.fullmatch(sha or ""):
        return None
    try:
        doc = json.loads((Path(folder) / VERDICTS / f"{sha}.json").read_text(encoding="utf-8"))
        v = Verdict(**{k: doc[k] for k in Verdict.__dataclass_fields__ if k in doc})
    except (OSError, ValueError, TypeError, KeyError):
        return None
    return v if (v.ok and v.cls == "PASS" and v.sha == sha and v.guard == guard) else None


# ------------------------------------------------------------------------------ D2: static
def _uses(src: str) -> tuple[dict[str, int], int] | None:
    """Banned imports/calls counted in one source, and banned literals; None if it won't parse."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    n: dict[str, int] = {}
    lits = 0
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module.split(".")[0]]
        for m in names:
            if m in BANNED_IMPORTS:
                n[f"import {m}"] = n.get(f"import {m}", 0) + 1
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(
                fn, ast.Attribute) else ""
            if name in BANNED_CALLS:
                n[f"call {name}"] = n.get(f"call {name}", 0) + 1
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and \
                BANNED_LITERALS.search(node.value):
            lits += 1
    return n, lits


def static_problems(pairs: Iterable[tuple[str, str | None, str | None]]) -> list[str]:
    """(path, base source or None, head source or None) per changed .py file. A use the head has
    MORE of than the base is a problem; a head file that does not parse is a problem."""
    out: list[str] = []
    for path, base, head in pairs:
        if head is None or not path.endswith(".py"):
            continue
        h = _uses(head)
        if h is None:
            out.append(f"{path}: does not parse")
            continue
        b = _uses(base) if base is not None else ({}, 0)
        b = b or ({}, 0)
        for k, c in sorted(h[0].items()):
            if c > b[0].get(k, 0):
                out.append(f"{path}: new {k} (base {b[0].get(k, 0)} -> head {c})")
        if h[1] > b[1]:
            out.append(f"{path}: new literal naming a guard, trust, halt, token or secret path "
                       f"(base {b[1]} -> head {h[1]})")
    return out


# ------------------------------------------------------------------------------ D4: ceilings
def _numbers(doc: Any, at: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    if isinstance(doc, bool):
        return out
    if isinstance(doc, int | float):
        out[at] = float(doc)
    elif isinstance(doc, Mapping):
        for k, v in doc.items():
            out.update(_numbers(v, f"{at}/{k}"))
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            out.update(_numbers(v, f"{at}[{i}]"))
    return out


def ceiling_raises(base: str | None, head: str | None) -> list[str] | None:
    """Every number in ceilings.json that the head raises (or adds); None if unreadable. A lowering
    or a removed row is not a raise (the checker's hard caps judge the prop firms' rows)."""
    if head is None or head == base:
        return []
    try:
        b = _numbers(json.loads(base)) if base else {}
        h = _numbers(json.loads(head))
    except ValueError:
        return None
    return [f"{k}: {b.get(k)} -> {v}" for k, v in sorted(h.items())
            if k not in b or v > b[k]]


# ------------------------------------------------------------------------------ D4/D3: history
def money_merges_today(folder: Path, now: datetime | None = None) -> int | None:
    now = now or datetime.now(UTC)
    f = Path(folder) / LEDGER
    try:
        lines = f.read_text(encoding="utf-8").splitlines() if f.exists() else []
    except OSError:
        return None
    n = 0
    for ln in lines:
        try:
            row = json.loads(ln)
            at = datetime.fromisoformat(str(row["at"]))
        except (ValueError, KeyError, TypeError):
            return None  # a garbled ledger is unmeasured
        if row.get("money") and now - at < timedelta(hours=24):
            n += 1
    return n


def record_merge(folder: Path, pr: Any, head: str, merged: str, money: bool,
                 now: datetime | None = None) -> None:
    row = {"at": (now or datetime.now(UTC)).isoformat(timespec="seconds"), "pr": pr,
           "head": head, "merge": merged, "money": money}
    with (Path(folder) / LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def rolled_back_heads(folder: Path, rollbacks: Path = ROLLBACKS) -> set[str] | None:
    """PR heads whose merge the adopter rolled back: never merged again (the same bytes failed
    health once). None when either record is unreadable (fail closed)."""
    try:
        bad = set()
        if rollbacks.exists():
            for ln in rollbacks.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    bad.add(str(json.loads(ln).get("bad") or ""))
        heads = set()
        led = Path(folder) / LEDGER
        if led.exists():
            for ln in led.read_text(encoding="utf-8").splitlines():
                row = json.loads(ln)
                if str(row.get("merge") or "") in bad:
                    heads.add(str(row.get("head") or ""))
        return heads
    except (OSError, ValueError, AttributeError):
        return None


# ------------------------------------------------------------------------------ the decision
def decide(sha: str, base: str, *, trust: tuple[bool, str, str], static: Sequence[str],
           raises: Sequence[str] | None, money: list[str] | None,
           risk: tuple[bool, str] | None, smoke: tuple[bool, str] | None,
           merges_today: int | None, rolled_back: set[str] | None, held: bool,
           guard: str) -> Verdict:
    """Pure: the measured answers in, one verdict out. `money` None is UNMEASURED and is treated
    as money; `risk`/`smoke` are None when they did not need to run (not money path)."""
    at = datetime.now(UTC).isoformat(timespec="seconds")
    is_money = money is None or bool(money)

    def v(ok: bool, cls: str, why: str, checks: list[str]) -> Verdict:
        return Verdict(sha, base, ok, cls, why[:400], is_money, checks, guard, at)

    t_ok, t_cls, t_why = trust
    if t_cls == "REFUSE":
        return v(False, "REFUSE", f"trust: {t_why}", ["trust"])
    if not t_ok:
        return v(False, "TRUST", f"needs the owner: {t_cls}: {t_why}", ["trust"])
    if held:
        return v(False, "FAIL", "an Auditor HOLD names this head", ["trust", "hold"])
    if static:
        return v(False, "TRUST", "needs the owner: " + "; ".join(static[:4]), ["trust", "static"])
    if raises is None:
        return v(False, "FAIL", f"{CEILINGS} UNMEASURED", ["trust", "static", "ceilings"])
    # RISK AUTONOMY (zuck 2026-11-14, reconfirmed 2026-11-27 13:50Z): limits move autonomously in
    # either direction; the one hard bound is the firms' own rules, which the pinned checker
    # REFUSEs (hard_caps). A raise is journalled in the verdict, never a block.
    raised = f"; ceilings raised: {'; '.join(raises[:4])}" if raises else ""
    if rolled_back is None:
        return v(False, "FAIL", "rollback record UNMEASURED", ["trust", "static", "ceilings"])
    if sha in rolled_back:
        return v(False, "FAIL", "this head was rolled back once", ["rollback"])
    checks = ["trust", "static", "ceilings", "rollback"]
    if not is_money:
        return v(True, "PASS", f"not money path: trust, static and ceilings pass{raised}", checks)
    if merges_today is None:
        return v(False, "FAIL", "money merge ledger UNMEASURED", checks)
    if merges_today >= MONEY_MERGES_PER_DAY:
        return v(False, "FAIL", f"{merges_today} money merges in 24 h (cap "
                                f"{MONEY_MERGES_PER_DAY}): waits", checks)
    if risk is None or not risk[0]:
        return v(False, "FAIL", f"risk: {risk[1] if risk else 'did not run'}", [*checks, "risk"])
    if smoke is None or not smoke[0]:
        return v(False, "FAIL", f"smoke: {smoke[1] if smoke else 'did not run'}",
                 [*checks, "risk", "smoke"])
    return v(True, "PASS", f"money path: {risk[1]}; {smoke[1]}{raised}",
             [*checks, "risk", "smoke"])

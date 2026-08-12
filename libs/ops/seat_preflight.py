"""OPENROUTER PRE-FLIGHT — prove every dark organ will fire correctly, BEFORE paying for one call.

THE MOMENT THIS EXISTS FOR. The principal is about to fund OpenRouter. Twelve organs are dark
today and every one of them will wake at once when the key lands. The expensive failure is not a
dark organ -- it is an organ that LOOKS wired, wakes with the key, and then discovers it was never
finished: its output goes nowhere, its cron line was never added, it crashes on import, or it
spends without a cap. Finding that out mid-cycle costs both the money and the cycle.

So this checks readiness STATICALLY. It makes ZERO model calls and spends nothing. Every check is
an import, a file read, or a grep over the manifest -- the whole point is to be free.

THE FOUR WAYS AN ORGAN IS "WIRED" AND STILL BROKEN, each checked separately because each fails
independently and a single pass/fail would hide three of them:

  1. IMPORTABLE      it crashes before it reaches the seat. A syntax or import error is invisible
                     while the organ is dark, because nothing runs it.
  2. SEATED          it never actually asks for a seat. An organ that reads no key will stay dark
                     after funding and look like a scheduling problem for a week.
  3. SCHEDULED       nothing fires it. A perfectly built organ with no cron line produces nothing
                     forever, and this desk already carries 26 unwired modules as proof.
  4. CONSUMED        its output artifact is read by nobody. This is the dormancy defect (L2.9):
                     the organ runs, spends real money, writes a file, and the file is never
                     opened. That is the most expensive shape because it looks healthy.

SPEND SAFETY IS CHECKED, NOT ASSUMED. An organ that reaches the seat without a cap check can
empty the budget in one cycle. libs.ops.llm_seat holds a $20 monthly default and a ledger; an
organ that never consults either is flagged UNCAPPED regardless of how well it is wired.

WHAT THIS DELIBERATELY DOES NOT DO: light the seat, call a model, estimate quality, or rank the
organs by value. It answers one question -- if the key arrived right now, what would actually
work -- and it answers it for free.
"""
from __future__ import annotations

import ast
import importlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["DARK_ORGANS", "OrganReadiness", "preflight", "readiness"]

_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "ops/crontab.manifest"
OUT = "docs/research/openrouter_preflight.json"

#: Every organ that goes live the moment OPENROUTER_API_KEY exists, with the artifact it produces.
#: The artifact matters as much as the script: an organ whose output nobody reads is the dormancy
#: defect, and it is invisible until you look for the READER.
#: NON-SPENDING organs. They depend on OpenRouter but never buy inference, so judging them on
#: "does it reach a seat" is a category error my first model made: refresh_panel_roster reads the
#: PUBLIC /models catalogue (verified 2026-08-12: HTTP 200, 664KB, no auth) and uses a key only
#: to copy it forward into the rewritten roster. Demanding a seat of it would have had the desk
#: "fixing" an organ that was correct.
NON_SPENDING: frozenset[str] = frozenset({"refresh_panel_roster"})

DARK_ORGANS: tuple[tuple[str, str], ...] = (
    ("run_cro", "docs/research/CRO_BRIEFING.md"),
    ("run_external_panel", "data/panel_verdicts.jsonl"),
    ("run_strategic_director", "data/strategic_director.json"),
    ("llm_code_auditor", "data/llm_code_audit.json"),
    ("meta_architect", "data/meta_architect.json"),
    ("breadth_expander", "data/breadth_expander.json"),
    ("kimi_hunter", "data/kimi_hunter.json"),
    ("collector_author", "data/collector_author.json"),
    ("deep_review", "data/deep_review.json"),
    ("run_micro_audit", "data/micro_audit.json"),
    ("refresh_panel_roster", "data/panel_roster.json"),
    ("llm_blind_researcher", "data/blind_researcher.json"),
    ("run_deepseek_cycle", "data/deepseek_evidence.jsonl"),
)

#: Modules that ARE the paid-seat machinery. Reaching any of them -- directly or through any
#: number of local hops -- means this organ can spend.
_SEAT_MODULES: frozenset[str] = frozenset({
    "libs.ops.llm_seat", "libs.ops.llm_route", "libs.llm.push", "libs.llm.effort",
    "libs.llm.second_opinion", "libs.llm.market", "scripts.seats",
})

#: Symbols that mean "this organ checks the budget before spending".
_CAP_MARKERS = ("DEFAULT_MONTHLY_CAP_USD", "SPEND_LEDGER", "spend", "cap_usd", "budget")


@dataclass
class OrganReadiness:
    """One organ's answer to: if the key arrived right now, would this work?"""

    organ: str
    artifact: str
    importable: bool = False
    seated: bool = False
    scheduled: bool = False
    consumed: bool = False
    capped: bool = False
    spends: bool = True
    import_error: str = ""
    consumers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        """READY means all four wiring checks pass. `capped` is reported separately because an
        uncapped organ is a SPEND risk rather than a wiring fault -- conflating them would let a
        budget hole hide behind a green wiring tick."""
        return self.importable and self.seated and self.scheduled and self.consumed

    @property
    def verdict(self) -> str:
        if not self.importable:
            return "BROKEN_IMPORT"
        if not self.seated:
            return "NEVER_ASKS_FOR_A_SEAT"
        if not self.scheduled:
            return "UNSCHEDULED"
        if not self.consumed:
            return "OUTPUT_UNREAD"
        if not self.spends:
            return "READY_NON_SPENDING"
        return "READY" if self.capped else "READY_BUT_UNCAPPED"


def _source(script: str) -> str:
    p = _ROOT / "scripts" / f"{script}.py"
    try:
        return p.read_text("utf-8", errors="ignore")
    except OSError:
        return ""


def _importable(script: str) -> tuple[bool, str]:
    """Import WITHOUT executing main(). A module that crashes on import is dark twice over: it
    fails silently today because nothing runs it, and it fails loudly the day it is funded."""
    try:
        importlib.import_module(f"scripts.{script}")
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:160]}"


def _consumers(artifact: str) -> list[str]:
    """WHO READS THIS. An organ whose artifact nobody opens spends real money into a void, and
    that is the most expensive failure here because every other signal looks healthy."""
    if not artifact:
        return []
    name = Path(artifact).name
    hits: list[str] = []
    for d in ("scripts", "libs", "app", "api"):
        base = _ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if p.name == f"{Path(artifact).stem}.py":
                continue                       # the producer is not a consumer
            try:
                if name in p.read_text("utf-8", errors="ignore"):
                    hits.append(p.relative_to(_ROOT).as_posix())
            except OSError:
                continue
    return sorted(hits)


def _local_imports(mod_src: str) -> set[str]:
    """Every libs.* / scripts.* module this source imports, by AST rather than by regex."""
    out: set[str] = set()
    try:
        tree = ast.parse(mod_src)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
            out.update(f"{node.module}.{a.name}" for a in node.names)
    return {m for m in out if m.startswith(("libs.", "scripts."))}


def _reaches_seat(script: str, *, _depth: int = 6) -> bool:
    """TRANSITIVE. Does this organ reach the seat machinery through ANY chain of local imports?

    STRING MARKERS WERE THE WRONG INSTRUMENT AND PRODUCED THREE ROUNDS OF FALSE POSITIVES on the
    first run of this very module: kimi_hunter reaches a model through libs.ops.llm_route, which
    was not on my list, while its only literal mention of "seats" is in a PROSE COMMENT. So a
    marker list both missed real seats and matched English. The import GRAPH cannot be fooled by
    either -- it answers the actual question, which is whether the code can get to a paid call.
    """
    seen: set[str] = set()
    frontier = {f"scripts.{script}"}
    for _ in range(_depth):
        nxt: set[str] = set()
        for mod in frontier - seen:
            seen.add(mod)
            if mod in _SEAT_MODULES or any(mod.startswith(s + ".") for s in _SEAT_MODULES):
                return True
            rel = Path(*mod.split(".")).with_suffix(".py")
            try:
                src = (_ROOT / rel).read_text("utf-8", errors="ignore")
            except OSError:
                continue
            nxt |= _local_imports(src)
        frontier = nxt - seen
        if not frontier:
            break
    return False


#: Env vars that ARE a seat. An organ can be perfectly seated without importing seat machinery --
#: run_deepseek_cycle reads the key directly, because its identity is local and only inference
#: leaves the box. Requiring an import would have called it unseated.
_KEY_TOKENS = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "XAI_API_KEY")


def _reads_a_key(script: str) -> bool:
    """Does this organ (or anything it imports) read a provider key from the environment?"""
    for mod in {f"scripts.{script}"} | _closure(f"scripts.{script}"):
        rel = Path(*mod.split(".")).with_suffix(".py")
        try:
            src = (_ROOT / rel).read_text("utf-8", errors="ignore")
        except OSError:
            continue
        if any(k in src for k in _KEY_TOKENS) and ("environ" in src or "getenv" in src):
            return True
    return False


def _closure(root_mod: str, *, depth: int = 5) -> set[str]:
    seen: set[str] = set()
    frontier = {root_mod}
    for _ in range(depth):
        nxt: set[str] = set()
        for mod in frontier - seen:
            seen.add(mod)
            rel = Path(*mod.split(".")).with_suffix(".py")
            try:
                nxt |= _local_imports((_ROOT / rel).read_text("utf-8", errors="ignore"))
            except OSError:
                continue
        frontier = nxt - seen
        if not frontier:
            break
    return seen


def _invoked_by(script: str) -> list[str]:
    """Scripts that shell out to or import this organ. An organ fired by a SCHEDULED parent is
    scheduled -- reporting it UNSCHEDULED because it has no cron line of its own is a false alarm,
    and run_external_panel and breadth_expander are both fired by daily_research_cycle."""
    out = []
    for pth in (_ROOT / "scripts").rglob("*.py"):
        if pth.stem == script:
            continue
        try:
            src = pth.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        if f"{script}.py" in src or f"scripts.{script}" in src:
            out.append(pth.stem)
    return sorted(out)


def readiness(script: str, artifact: str, *, manifest_text: str = "") -> OrganReadiness:
    src = _source(script)
    r = OrganReadiness(organ=script, artifact=artifact)
    if not src:
        r.import_error = f"scripts/{script}.py does not exist"
        r.notes.append("organ named in the dark list but absent from the repo -- either build it "
                       "or remove the claim that it is waiting on a key")
        return r
    r.importable, r.import_error = _importable(script)
    r.spends = script not in NON_SPENDING
    r.seated = (not r.spends) or _reaches_seat(script) or _reads_a_key(script)
    r.capped = any(m in src for m in _CAP_MARKERS)
    mt = manifest_text or (_ROOT / MANIFEST).read_text("utf-8", errors="ignore")
    direct = bool(re.search(rf"\b{re.escape(script)}\.py\b", mt))
    parents = _invoked_by(script)
    via = [q for q in parents if re.search(rf"\b{re.escape(q)}\.py\b", mt)]
    r.scheduled = direct or bool(via)
    if not direct and via:
        r.notes.append(f"no cron line of its own; fired by scheduled parent(s): {via[:3]}")
    # The producer writes the artifact; a CONSUMER is any other module that names it.
    producer = f"scripts/{script}.py"
    r.consumers = [c for c in _consumers(artifact) if c != producer]
    r.consumed = bool(r.consumers)
    if not r.seated:
        r.notes.append("reaches no seat machinery -- it will stay dark after funding and look "
                       "like a scheduling problem")
    if not r.scheduled:
        r.notes.append("no cron line fires it; a built organ with no schedule produces nothing "
                       "forever")
    if not r.consumed:
        r.notes.append(f"nothing reads {artifact} -- this organ would spend real money writing a "
                       "file nobody opens (L2.9 dormancy)")
    if r.spends and r.seated and not r.capped:
        r.notes.append("reaches a seat with no visible budget check -- one cycle can empty the "
                       "cap")
    return r


def preflight(*, root: Path | None = None, write: bool = True) -> dict[str, Any]:
    """The whole answer, for free. No model is called and no key is required."""
    base = root or _ROOT
    try:
        mt = (base / MANIFEST).read_text("utf-8", errors="ignore")
    except OSError:
        mt = ""
    rows = [readiness(s, a, manifest_text=mt) for s, a in DARK_ORGANS]
    by_verdict: dict[str, list[str]] = {}
    for r in rows:
        by_verdict.setdefault(r.verdict, []).append(r.organ)

    ready = [r for r in rows if r.ready]
    doc = {
        "what": "static readiness of every organ that wakes when OPENROUTER_API_KEY is funded",
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "spend_incurred": "ZERO -- imports, file reads and a manifest grep. No model is called.",
        "n_organs": len(rows),
        "n_ready": len(ready),
        "by_verdict": by_verdict,
        "organs": [
            {"organ": r.organ, "verdict": r.verdict, "artifact": r.artifact,
             "importable": r.importable, "seated": r.seated, "scheduled": r.scheduled,
             "consumed": r.consumed, "capped": r.capped,
             "import_error": r.import_error, "n_consumers": len(r.consumers),
             "consumers": r.consumers[:4], "notes": r.notes}
            for r in rows
        ],
        "law": "READY means importable AND seated AND scheduled AND its output is read. An "
               "uncapped organ is reported separately -- a budget hole must never hide behind a "
               "green wiring tick",
        "authority": "MEASUREMENT ONLY. Lights no seat, calls no model, ranks no organ by value.",
    }
    if write:
        p = base / OUT
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=1, ensure_ascii=False), "utf-8")
        doc["written_to"] = str(p)
    return doc

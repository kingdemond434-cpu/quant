"""EVOLVING MISSIONS -- a forest's prompt and query set, rewritten every pass from what it yielded.

THE PRINCIPAL'S ORDER (2026-11-17 20:32Z): the civilisations' prompts change and constantly
evolve. The federation had no reusable mechanism for that: `forest_runner`'s source scout asks the
same pack terms, polyglot tables and `MANDATE_SEEDS` every pass, and the proposer seat only ADDS
search strings without remembering which ones paid. This module is the small generic piece that
was missing, and it is OPT-IN PER FOREST (`Forest.evolving`): no other forest's behaviour changes.

WHAT EVOLVES. A `Mission` is a mission sentence plus two weighted vocabularies:

* `terms`   -- the query / selection terms the forest reads with (what its scout emits as seeds
               and what its miner ranks items by);
* `sources` -- weights over the forest's already-REVIEWED sources (which to read first and how
               much). Evolution reweights a reviewed roster; it never adds a host, because a
               source enters only through review, never through a model or a yield count.

THE STEP IS DETERMINISTIC (`evolve`). Given the parent and one pass's `Yield`:

* a term or source that produced claims GROWS (x`GROW` plus a log-yield bonus, capped at `W_MAX`);
* one that was TRIED and produced nothing DECAYS (x`DECAY`); a non-seed term that decays below
  `FLOOR` is RETIRED -- moved to `retired` with the pass that retired it, never deleted, so the
  log says what was dropped and when;
* a SEED term never retires: it is held at `FLOOR` (the scout-floor rule applied to vocabulary --
  a mission starved of its own anchor can never earn it back);
* the vocabulary the pass's claims carried (`Yield.harvest`: mechanism classes, instruments,
  quantities) EXPANDS the term set, the `MAX_EXPAND` most frequent new terms entering at
  `EXPAND_W` -- a retired term may re-enter this way, which is the revival path;
* the mission sentence is re-composed from the base mission and the current top terms, so the
  prompt text itself changes as the vocabulary does.

Same parent + same yield + same stamp -> byte-identical child. No clock, no randomness.

EVERY VERSION IS RECORDED, APPEND-ONLY (`append`, `verify_chain`). One JSON row per version in a
per-forest log: its id (a content hash), its PARENT id, the pass stamp, the full mission and the
diff from the parent. `append` refuses a row whose parent is not the log's current head, so the
log is a chain and a rewrite is detectable; `verify_chain` re-walks it. A pass that observed no
yield (nothing tried) produces no new version -- `evolve` returns the parent with `changed=False`
and the caller reports the hold and why, rather than minting a version that says nothing.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DECAY", "EXPAND_W", "FLOOR", "GROW", "MAX_EXPAND", "MAX_TERMS", "W_MAX",
    "Mission", "Yield", "append", "evolve", "head", "load_log", "seed", "verify_chain",
]

GROW = 1.5
DECAY = 0.7
FLOOR = 0.05
W_MAX = 8.0
EXPAND_W = 0.5
MAX_EXPAND = 8
MAX_TERMS = 64
TOP_IN_MISSION = 6


def _r(x: float) -> float:
    return round(float(x), 4)


def _norm(term: Any) -> str:
    return " ".join(str(term or "").strip().lower().split())[:80]


@dataclass(frozen=True)
class Mission:
    """One version of a forest's evolving mission."""

    forest: str
    base: str
    terms: dict[str, float]
    sources: dict[str, float]
    seeds: tuple[str, ...] = ()
    retired: dict[str, str] = field(default_factory=dict)
    parent: str | None = None
    stamp: str = ""
    generation: int = 0

    @property
    def text(self) -> str:
        top = [t for t, _w in sorted(self.terms.items(), key=lambda kv: (-kv[1], kv[0]))]
        focus = ", ".join(top[:TOP_IN_MISSION]) or "the seed vocabulary"
        return f"{self.base} This pass's focus, ranked by what paid: {focus}."

    def content(self) -> dict[str, Any]:
        return {"forest": self.forest, "base": self.base, "parent": self.parent,
                "terms": dict(sorted(self.terms.items())),
                "sources": dict(sorted(self.sources.items())),
                "seeds": list(self.seeds), "retired": dict(sorted(self.retired.items())),
                "generation": self.generation}

    @property
    def version(self) -> str:
        blob = json.dumps(self.content(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def as_row(self, diff: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {"version": self.version, "parent": self.parent, "pass": self.stamp,
                "generation": self.generation, "mission": self.text, **self.content(),
                "diff": dict(diff or {})}

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Mission:
        return cls(forest=str(row.get("forest") or ""), base=str(row.get("base") or ""),
                   terms={str(k): float(v) for k, v in dict(row.get("terms") or {}).items()},
                   sources={str(k): float(v) for k, v in dict(row.get("sources") or {}).items()},
                   seeds=tuple(str(s) for s in row.get("seeds") or ()),
                   retired={str(k): str(v) for k, v in dict(row.get("retired") or {}).items()},
                   parent=row.get("parent"), stamp=str(row.get("pass") or ""),
                   generation=int(row.get("generation") or 0))


@dataclass(frozen=True)
class Yield:
    """What one pass produced, per term and per source, and the vocabulary its claims carried.

    `tried_*` names what the pass actually exercised: only a TRIED term can decay. A term the
    pass never reached (Tor absent, budget out) is not evidence against it.
    """

    terms: Mapping[str, int] = field(default_factory=dict)
    sources: Mapping[str, int] = field(default_factory=dict)
    tried_terms: Iterable[str] = ()
    tried_sources: Iterable[str] = ()
    harvest: Mapping[str, int] = field(default_factory=dict)

    @property
    def observed(self) -> bool:
        return bool(list(self.tried_terms) or list(self.tried_sources) or self.harvest)


def seed(forest: str, base: str, terms: Iterable[str], sources: Iterable[str] = (),
         stamp: str = "") -> Mission:
    """Generation 0: every seed term and source at weight 1.0."""
    ts = [t for t in (_norm(x) for x in terms) if t]
    return Mission(forest=forest, base=base, terms=dict.fromkeys(ts, 1.0),
                   sources={str(s): 1.0 for s in sources}, seeds=tuple(dict.fromkeys(ts)),
                   stamp=stamp)


def _step(w: float, got: int, tried: bool) -> float:
    if got > 0:
        return min(W_MAX, w * GROW + 0.25 * math.log1p(got))
    if tried:
        return w * DECAY
    return w


def evolve(parent: Mission, y: Yield, stamp: str,
           sources: Iterable[str] | None = None) -> tuple[Mission, dict[str, Any], bool]:
    """(child, diff, changed). Deterministic; see the module docstring for the rules.

    `sources`, when given, is the CURRENT reviewed roster: a source no longer on it leaves the
    weights, and a newly reviewed one enters at 1.0 -- the roster decides membership, yield only
    decides weight.
    """
    tried_t = {_norm(t) for t in y.tried_terms}
    tried_s = {str(s) for s in y.tried_sources}
    got_t = {_norm(k): int(v) for k, v in y.terms.items()}
    terms: dict[str, float] = {}
    retired = dict(parent.retired)
    grown, decayed, gone = [], [], []
    seeds = set(parent.seeds)
    for t, w in sorted(parent.terms.items()):
        nw = _step(w, got_t.get(t, 0), t in tried_t)
        if nw > w:
            grown.append(t)
        elif nw < w:
            decayed.append(t)
        if nw < FLOOR:
            if t in seeds:
                nw = FLOOR
            else:
                retired[t] = stamp
                gone.append(t)
                continue
        terms[t] = _r(nw)
    added = []
    harvest = sorted(((_norm(k), int(v)) for k, v in y.harvest.items() if _norm(k)),
                     key=lambda kv: (-kv[1], kv[0]))
    for t, n in harvest:
        if len(added) >= MAX_EXPAND or len(terms) >= MAX_TERMS:
            break
        if n > 0 and t not in terms:
            terms[t] = EXPAND_W
            retired.pop(t, None)
            added.append(t)
    roster = sorted(set(sources)) if sources is not None else sorted(parent.sources)
    srcs: dict[str, float] = {}
    for s in roster:
        w = parent.sources.get(s, 1.0)
        srcs[s] = _r(max(FLOOR, _step(w, int(y.sources.get(s, 0)), s in tried_s)))
    child = Mission(forest=parent.forest, base=parent.base, terms=terms, sources=srcs,
                    seeds=parent.seeds, retired=retired, parent=parent.version, stamp=stamp,
                    generation=parent.generation + 1)
    diff = {"added": added, "retired": gone, "grown": grown, "decayed": decayed,
            "sources_changed": sorted(s for s in srcs if srcs[s] != parent.sources.get(s)),
            "mission_before": parent.text, "mission_after": child.text}
    changed = (child.terms != parent.terms or child.sources != parent.sources
               or child.retired != parent.retired)
    if not changed:
        return parent, {**diff, "held": "no term or source moved this pass"}, False
    return child, diff, True


# ------------------------------------------------------------------------- the append-only log
def load_log(path: Path) -> list[dict[str, Any]]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except ValueError:
                out.append({"_unreadable": ln[:200]})
    return out


def head(path: Path) -> Mission | None:
    rows = [r for r in load_log(path) if "version" in r]
    return Mission.from_row(rows[-1]) if rows else None


def verify_chain(path: Path) -> dict[str, Any]:
    """Re-walk the log: every row's parent is the previous row's version and every version is
    the hash of its own content. A break names the first row that fails."""
    rows = load_log(path)
    prev: str | None = None
    for i, r in enumerate(rows):
        if "version" not in r:
            return {"ok": False, "rows": len(rows), "break_at": i, "why": "unreadable row"}
        if r.get("parent") != prev:
            return {"ok": False, "rows": len(rows), "break_at": i,
                    "why": f"parent {r.get('parent')!r} is not the previous version {prev!r}"}
        if Mission.from_row(r).version != r["version"]:
            return {"ok": False, "rows": len(rows), "break_at": i,
                    "why": "version is not the hash of the row's own content"}
        prev = str(r["version"])
    return {"ok": True, "rows": len(rows), "head": prev}


def append(path: Path, mission: Mission, diff: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Append one version. Refuses (ValueError) a mission whose parent is not the current head:
    the log only ever grows at its end, and it never forks."""
    current = head(path)
    want = current.version if current else None
    if mission.parent != want:
        raise ValueError(f"mission parent {mission.parent!r} is not the log head {want!r}; "
                         f"the version log is append-only")
    row = mission.as_row(diff)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row

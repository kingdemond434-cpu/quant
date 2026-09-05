"""The desk's typed research memory: what it knows, by KIND, readable by any worker at runtime.

WHY A SECOND MEMORY. `desk_memory` carries the lessons the desk PAID for, ranked into a fixed
prompt budget -- a few dozen rows, curated. This is the other thing a research desk needs and did
not have: the long tail of small, typed facts that nothing curates -- twenty thousand buried
parameter regions, sixty-six certificates, the coverage gaps the allocator named yesterday, the
search operators the diggers validated, the governance rules -- indexed so that a deepening worker
handed "EURCHF drawdown reversal, horizon 3" can be told, before it proposes anything, that the
desk buried that region four times and why. A worker that cannot read the graveyard re-proposes
corpses; the graph makes the corpses visible to code, this makes them visible to a PROMPT.

NO EMBEDDINGS, BY DESIGN. Recall is token overlap on a lower-cased, non-word-split tokenisation,
with CJK runs split into character bigrams so the Chinese and Japanese entries the frontier
miners write are searchable by the same mechanism. Overlap is auditable: the reason a memory
surfaced is the words it shares with the query, which a vector similarity cannot say. It is also
free -- no model, no network, no index to rebuild -- which is what lets it run inside an hourly
worker on the box.

APPEND-ONLY, ONE JSONL PER KIND. A memory is never edited; a correction is a new memory naming
the one it `supersedes`, and recall skips the superseded. `remember` dedupes on exact (key, text),
so `build_from_artifacts` can run every cycle and add nothing when nothing changed.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
#: Where the per-kind ledgers live. Overridable (tests, a second desk) by passing `memory_dir`
#: to any call or by rebinding this constant before the call.
MEMORY_DIR = ROOT / "desks" / "mt5" / "data" / "memory"

KINDS: tuple[str, ...] = ("fact", "hypothesis", "failure", "survivor", "execution", "regime",
                          "method")

_WORD = re.compile(r"\w+", re.UNICODE)
#: Hiragana/Katakana, CJK Extension A, CJK Unified, Hangul syllables.
_CJK = re.compile("[぀-ヿ㐀-䶿一-鿿가-힯]+")
#: Function words that would otherwise dominate overlap between any two English sentences.
_STOP: frozenset[str] = frozenset((
    "the", "a", "an", "of", "on", "in", "and", "or", "for", "to", "is", "are", "was", "with",
    "at", "by", "as", "it", "its", "this", "that", "be", "not", "no", "from", "than", "then",
    "if", "so", "we", "our", "their", "has", "have", "had", "but", "into", "over", "per",
))
#: One memory line in a prompt is capped here so a single verbose entry cannot eat the budget.
_LINE_CHARS = 220


def tokenize(text: str) -> set[str]:
    """Lower-cased word tokens; CJK runs become character bigrams (a single char stays itself)."""
    out: set[str] = set()
    for tok in _WORD.findall(text.lower()):
        for run in _CJK.findall(tok):
            if len(run) == 1:
                out.add(run)
            out.update(run[i:i + 2] for i in range(len(run) - 1))
        for piece in _CJK.split(tok):
            if len(piece) >= 2 and piece not in _STOP:
                out.add(piece)
    return out


def _memory_id(kind: str, key: str, text: str) -> str:
    return hashlib.sha256(f"{kind}|{key}|{text}".encode()).hexdigest()[:16]


def _path(kind: str, memory_dir: Path | None) -> Path:
    if kind not in KINDS:
        raise ValueError(f"unknown memory kind {kind!r}; kinds are {KINDS}")
    return (memory_dir or MEMORY_DIR) / f"{kind}.jsonl"


def _as_dict(obj: object) -> dict[str, Any]:
    return {str(k): v for k, v in obj.items()} if isinstance(obj, dict) else {}


def _as_list(obj: object) -> list[Any]:
    return list(obj) if isinstance(obj, list) else []


@dataclass
class _Ledger:
    """One kind's rows, their token sets and an id index, valid while `stamp` matches the file."""
    stamp: tuple[float, int] | None
    rows: list[dict[str, Any]] = field(default_factory=list)
    toks: list[set[str]] = field(default_factory=list)
    ids: dict[str, int] = field(default_factory=dict)

    def add(self, row: dict[str, Any]) -> None:
        self.ids[str(row["id"])] = len(self.rows)
        self.rows.append(row)
        self.toks.append(tokenize(f"{row.get('key', '')} {row.get('text', '')}"))


#: Parsed-and-tokenised ledgers keyed on path, valid while (mtime, size) matches. The failure
#: ledger holds tens of thousands of regions: the deepening worker asks once per task and a
#: build appends once per region, so both re-parsing per question and re-parsing per append
#: would be quadratic. An append by THIS process updates the cache in place; an append by
#: another process changes the stamp and forces a re-read.
_CACHE: dict[str, _Ledger] = {}


def _stamp(path: Path) -> tuple[float, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime, st.st_size)


def _ledger(kind: str, memory_dir: Path | None) -> _Ledger:
    path = _path(kind, memory_dir)
    stamp = _stamp(path)
    if stamp is None:
        _CACHE.pop(str(path), None)
        return _Ledger(stamp=None)
    hit = _CACHE.get(str(path))
    if hit is not None and hit.stamp == stamp:
        return hit
    led = _Ledger(stamp=stamp)
    try:
        for ln in path.read_text("utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                row = _as_dict(json.loads(ln))
            except ValueError:
                continue
            if row.get("id"):
                led.add(row)
    except OSError:
        return _Ledger(stamp=None)
    _CACHE[str(path)] = led
    return led


def _load(kind: str, memory_dir: Path | None) -> tuple[list[dict[str, Any]], list[set[str]]]:
    led = _ledger(kind, memory_dir)
    return led.rows, led.toks


def remember(kind: str, key: str, text: str, *, source: str,
             evidence: dict[str, Any] | None = None, supersedes: str | None = None,
             memory_dir: Path | None = None) -> dict[str, Any]:
    """Append one memory; an exact (key, text) already held is returned unchanged, not re-added.

    The returned row carries `new` so a builder can count what it actually added.
    """
    path = _path(kind, memory_dir)
    key, text = str(key).strip(), " ".join(str(text).split())
    if not key or not text:
        raise ValueError("a memory needs both a key and a text")
    mid = _memory_id(kind, key, text)
    led = _ledger(kind, memory_dir)
    pos = led.ids.get(mid)
    if pos is not None:
        return {**led.rows[pos], "new": False}
    row: dict[str, Any] = {"id": mid, "kind": kind, "key": key, "text": text,
                           "source": str(source), "evidence": dict(evidence or {}),
                           "supersedes": supersedes, "at": datetime.now(tz=UTC).isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
    led.add(row)
    led.stamp = _stamp(path)
    _CACHE[str(path)] = led
    return {**row, "new": True}


def _score(q: set[str], m: set[str]) -> float:
    """Overlap normalised by the memory's own length, so a long entry cannot win by mentioning
    everything. Zero shared tokens is zero, whatever the lengths."""
    if not q or not m:
        return 0.0
    shared = len(q & m)
    return shared / math.sqrt(len(m)) if shared else 0.0


def recall(kind: str | None, query: str, k: int = 8, *,
           memory_dir: Path | None = None) -> list[dict[str, Any]]:
    """The k memories (of one kind, or all) sharing the most tokens with the query.

    Superseded memories never surface. Ties break newest-first, then by id, so two runs on the
    same ledger recall the same rows in the same order.
    """
    q = tokenize(query)
    if not q:
        return []
    kinds: Iterable[str] = (kind,) if kind else KINDS
    scored: list[tuple[float, str, str, dict[str, Any]]] = []
    for kd in kinds:
        rows, toks = _load(kd, memory_dir)
        dead = {str(r.get("supersedes")) for r in rows if r.get("supersedes")}
        for r, m in zip(rows, toks, strict=True):
            if str(r.get("id")) in dead:
                continue
            s = _score(q, m)
            if s > 0:
                scored.append((s, str(r.get("at") or ""), str(r.get("id")), r))
    scored.sort(key=lambda x: (x[1], x[2]), reverse=True)   # newest-first among equal scores
    scored.sort(key=lambda x: -x[0])                        # ... under a stable sort by score
    return [{**r, "score": round(s, 4)} for s, _, _, r in scored[:max(0, int(k))]]


def digest(kind: str, *, memory_dir: Path | None = None) -> dict[str, Any]:
    """Counts, the newest entry and the busiest sources of one kind -- the health line."""
    rows, _ = _load(kind, memory_dir)
    dead = {str(r.get("supersedes")) for r in rows if r.get("supersedes")}
    by_source: dict[str, int] = {}
    for r in rows:
        s = str(r.get("source") or "?")
        by_source[s] = by_source.get(s, 0) + 1
    newest = max(rows, key=lambda r: str(r.get("at") or "")) if rows else None
    return {"kind": kind, "n": len(rows), "n_active": sum(1 for r in rows
                                                            if str(r.get("id")) not in dead),
            "newest": ({"key": newest.get("key"), "at": newest.get("at"),
                        "source": newest.get("source")} if newest else None),
            "top_sources": sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0]))[:5],
            "path": str(_path(kind, memory_dir))}


# ------------------------------------------------------------------------------------------
# Building the memory from what the desk already writes
# ------------------------------------------------------------------------------------------

def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return _as_dict(json.loads(path.read_text("utf-8")))
    except (OSError, ValueError):
        return None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text("utf-8")
    except OSError:
        return None


def _params_text(params: object) -> str:
    return json.dumps(params, sort_keys=True, default=str) if isinstance(params, dict) else "{}"


class _Tally:
    """Counts what a build added versus merely re-saw, per kind, and why an input was skipped."""

    def __init__(self, memory_dir: Path | None) -> None:
        self.memory_dir = memory_dir
        self.added: dict[str, int] = dict.fromkeys(KINDS, 0)
        self.seen: dict[str, int] = dict.fromkeys(KINDS, 0)
        self.inputs: dict[str, str] = {}

    def put(self, kind: str, key: str, text: str, source: str,
            evidence: dict[str, Any] | None = None) -> None:
        row = remember(kind, key, text, source=source, evidence=evidence,
                       memory_dir=self.memory_dir)
        self.seen[kind] += 1
        if row.get("new"):
            self.added[kind] += 1


def _ingest_graph(root: Path, t: _Tally) -> None:
    path = root / "desks" / "mt5" / "data" / "hypothesis_graph.jsonl"
    if not path.exists():
        t.inputs["hypothesis_graph"] = "absent"
        return
    try:
        from libs.research.hypothesis_graph import Graph
        current = Graph(path).current()
    except Exception as exc:
        t.inputs["hypothesis_graph"] = f"unreadable: {type(exc).__name__}: {exc}"
        return
    buried: dict[str, list[dict[str, Any]]] = {}
    n_cert = 0
    for r in current.values():
        fate = str(r.get("fate"))
        if fate in ("FAILED", "BURIED"):
            buried.setdefault(str(r.get("region")), []).append(r)
        elif fate == "CERTIFIED":
            n_cert += 1
            t.put("survivor", f"graph:{r.get('id')}",
                  f"{r.get('family')} on {r.get('symbol')} params {_params_text(r.get('params'))} "
                  f"CERTIFIED {str(r.get('at') or '')[:10]}"
                  + (f"; {r.get('why')}" if r.get("why") else ""),
                  source="hypothesis_graph", evidence={"region": r.get("region")})
    for region, rows in buried.items():
        rows.sort(key=lambda x: str(x.get("at") or ""))
        last = rows[-1]
        whys = [str(x.get("why")) for x in rows if x.get("why")]
        t.put("failure", region,
              f"{last.get('family')} on {last.get('symbol')} params "
              f"{_params_text(last.get('params'))} {last.get('fate')} {len(rows)}x in region "
              f"{region}" + (f"; why: {whys[-1][:200]}" if whys else ""),
              source="hypothesis_graph",
              evidence={"n_failed": len(rows), "last_at": last.get("at"),
                        "sources": sorted({str(x.get('source') or '') for x in rows})[:5]})
    t.inputs["hypothesis_graph"] = f"{len(buried)} buried regions, {n_cert} certified nodes"


def _ingest_canon(root: Path, t: _Tally) -> None:
    path = root / "desks" / "mt5" / "data" / "UNIVERSAL_SURVIVORS.canon.json"
    doc = _read_json(path)
    if doc is None:
        t.inputs["survivors_canon"] = "absent or unreadable"
        return
    survivors = _as_dict(doc.get("survivors"))
    n = 0
    for key, cert_obj in survivors.items():
        cert = _as_dict(cert_obj)
        spec = _as_dict(cert.get("shadow_spec"))
        sym = str(cert.get("sym") or spec.get("symbol") or "?")
        fam = str(spec.get("family") or cert.get("family") or "?")
        gates = _as_dict(cert.get("gates"))
        passed = [g for g, v in gates.items() if isinstance(v, dict) and v.get("passed")]
        text = (f"{fam} on {sym} params {_params_text(spec.get('params'))}"
                f" selector={spec.get('selector')} condition={spec.get('condition')}"
                f" gated {str(cert.get('gated_at') or '')[:10]} passed {len(passed)} gates"
                + (f" status={cert.get('status')}" if cert.get("status") else ""))
        t.put("survivor", f"canon:{key}", text, source="survivors_canon",
              evidence={"hunt": cert.get("hunt"), "days": cert.get("days")})
        n += 1
    t.inputs["survivors_canon"] = f"{n} certificates"


def _scalar_summary(doc: dict[str, Any], limit: int = 12) -> str:
    parts = []
    for k, v in doc.items():
        if isinstance(v, (int, float, str, bool)) and not str(k).startswith("_"):
            parts.append(f"{k}={v}")
        if len(parts) >= limit:
            break
    return "; ".join(parts)


def _ingest_execution(root: Path, t: _Tally) -> None:
    for name in ("FILL_SURFACE", "NETTING"):
        path = root / "desks" / "mt5" / "reports" / f"{name}.json"
        doc = _read_json(path)
        if doc is None:
            t.inputs[name.lower()] = "absent or unreadable"
            continue
        summary = _scalar_summary(doc)
        if not summary:
            t.inputs[name.lower()] = "no scalar fields to summarise"
            continue
        t.put("execution", name.lower(), f"{name}: {summary}", source=f"reports/{name}.json")
        t.inputs[name.lower()] = "summarised"


def _ingest_regime(root: Path, t: _Tally) -> None:
    path = root / "desks" / "mt5" / "reports" / "REGIME_COVERAGE.json"
    doc = _read_json(path)
    if doc is None:
        t.inputs["regime_coverage"] = "absent or unreadable"
        return
    n = 0
    for gap, why in _as_dict(doc.get("gaps")).items():
        t.put("regime", f"gap:{gap}", f"coverage gap {gap}: {why}", source="regime_coverage")
        n += 1
    for bucket in _as_list(doc.get("uncovered")):
        t.put("regime", f"uncovered:{bucket}",
              f"no sleeve covers state {bucket}: a candidate whose cause is specific to it is "
              "worth more than another cell in a covered state", source="regime_coverage")
        n += 1
    t.inputs["regime_coverage"] = f"{n} gaps/uncovered states"


def _sections(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    """(heading, body) for every heading line matching `pattern`, body up to the next heading."""
    out: list[tuple[str, str]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = pattern.match(lines[i])
        if not m:
            i += 1
            continue
        title = m.group(1).strip()
        body: list[str] = []
        i += 1
        while i < len(lines) and not lines[i].startswith("#"):
            body.append(lines[i])
            i += 1
        out.append((title, " ".join(" ".join(body).split())))
    return out


_GRAVE_HEAD = re.compile(r"^##+\s+(.+?)\s*$")
_OP_HEAD = re.compile(r"^###\s+(OP-\d+.*?)\s*$")
_RULE = re.compile(r"^\s*>?\s*\*\*(Rule\s+\d+)\.\*\*\s*(.+?)\s*$")
_BULLET = re.compile(r"^\s*[*-]\s+(.+?)\s*$")


def _ingest_docs(root: Path, t: _Tally) -> None:
    grave = _read_text(root / "docs" / "graveyard.md")
    if grave is None:
        t.inputs["graveyard_md"] = "absent"
    else:
        n = 0
        for title, body in _sections(grave, _GRAVE_HEAD):
            t.put("failure", f"graveyard:{title[:120]}",
                  f"GRAVEYARD {title}" + (f": {body[:240]}" if body else ""),
                  source="docs/graveyard.md")
            n += 1
        t.inputs["graveyard_md"] = f"{n} headings"
    ops = _read_text(root / "docs" / "research" / "search_operator_library.md")
    if ops is None:
        t.inputs["search_operator_library_md"] = "absent"
    else:
        n = 0
        for title, body in _sections(ops, _OP_HEAD):
            t.put("method", title.split()[0], f"{title}: {body[:300]}",
                  source="docs/research/search_operator_library.md")
            n += 1
        t.inputs["search_operator_library_md"] = f"{n} operators"
    gov = _read_text(root / "docs" / "GROWTH_GOVERNANCE.md")
    if gov is None:
        t.inputs["growth_governance_md"] = "absent"
    else:
        n = 0
        section = "preamble"
        for line in gov.splitlines():
            if line.startswith("#"):
                section = line.lstrip("#").strip()[:60]
                continue
            m = _RULE.match(line)
            if m:
                t.put("fact", f"growth_governance:{m.group(1).lower().replace(' ', '_')}",
                      f"GROWTH GOVERNANCE {m.group(1)}: {m.group(2)}",
                      source="docs/GROWTH_GOVERNANCE.md")
                n += 1
                continue
            b = _BULLET.match(line)
            if b and len(b.group(1)) >= 40:
                body = b.group(1).replace("**", "")
                t.put("fact", f"growth_governance:{section}:{n}",
                      f"GROWTH GOVERNANCE ({section}): {body[:300]}",
                      source="docs/GROWTH_GOVERNANCE.md")
                n += 1
        t.inputs["growth_governance_md"] = f"{n} rules"


def build_from_artifacts(root: Path = ROOT, *, memory_dir: Path | None = None) -> dict[str, Any]:
    """Ingest the artifacts the desk already writes. Re-running adds nothing that has not
    changed; every input that could not be read says so in `inputs` rather than vanishing."""
    t = _Tally(memory_dir)
    for step in (_ingest_graph, _ingest_canon, _ingest_execution, _ingest_regime, _ingest_docs):
        try:
            step(root, t)
        except Exception as exc:
            t.inputs[step.__name__.removeprefix("_ingest_")] = (
                f"FAILED: {type(exc).__name__}: {exc}")
    return {"generated_at": datetime.now(tz=UTC).isoformat(), "root": str(root),
            "memory_dir": str(memory_dir or MEMORY_DIR), "added": t.added, "seen": t.seen,
            "inputs": t.inputs}


# ------------------------------------------------------------------------------------------
# Serving a worker
# ------------------------------------------------------------------------------------------

def _params_query(task: dict[str, Any]) -> str:
    """A task that names exact params (a mutation, a revival) pins its region with them."""
    params = task.get("params")
    if not isinstance(params, dict) or not params:
        return ""
    return " ".join(f"{k} {json.dumps(v, default=str)}" for k, v in sorted(params.items()))


def _task_query(task: dict[str, Any]) -> str:
    syms = task.get("symbols")
    sym_text = " ".join(str(s) for s in syms) if isinstance(syms, list) else str(syms or "")
    return " ".join(str(x) for x in (task.get("title") or "", task.get("description") or "",
                                     task.get("family") or "", sym_text, _params_query(task))
                    if x)


def prompt_context(task: dict[str, Any], limit_chars: int = 1500, *,
                   memory_dir: Path | None = None) -> str:
    """The memories a deepening worker should read before it proposes: short "[kind] ..." lines.

    Failures for the task's own (symbol, family) are asked for explicitly and placed first,
    because that is the corpse the worker is most likely to re-propose; the general recall over
    every kind follows. Empty when nothing relevant is remembered -- never a fabricated line.
    """
    query = _task_query(task)
    if not query.strip():
        return ""
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    fam = str(task.get("family") or "")
    syms = task.get("symbols")
    pq = _params_query(task)
    for sym in (syms if isinstance(syms, list) else [])[:3]:
        if not fam:
            break
        for r in recall("failure", f"{sym} {fam} {pq}", k=3, memory_dir=memory_dir):
            if str(r["id"]) not in seen:
                seen.add(str(r["id"]))
                picked.append(r)
    for r in recall(None, query, k=12, memory_dir=memory_dir):
        if str(r["id"]) not in seen:
            seen.add(str(r["id"]))
            picked.append(r)
    lines: list[str] = []
    used = 0
    for r in picked:
        line = f"[{r.get('kind')}] {str(r.get('text') or '')[:_LINE_CHARS]}"
        if used + len(line) + 1 > limit_chars:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="ingest the desk's artifacts")
    ap.add_argument("--recall", default=None, help="query to recall against every kind")
    ap.add_argument("--kind", default=None)
    a = ap.parse_args()
    if a.build:
        d = build_from_artifacts()
        print(f"MEMORY  added={d['added']}  inputs={d['inputs']}")
    if a.recall:
        for r in recall(a.kind, a.recall):
            print(f"  {r['score']:.3f} [{r['kind']}] {r['text'][:160]}")
    for kd in KINDS:
        d = digest(kd)
        print(f"  {kd:10s} n={d['n']:6d} active={d['n_active']:6d} top={d['top_sources'][:2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

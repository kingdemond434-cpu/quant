"""The vault is lexical. THIS IS THE SEMANTIC HOP -- embeddings without a service.

`scripts/vault_search.py` is BM25, and CLAUDE.md says the quiet part out loud: an empty result
means THESE TOKENS are absent, not that the question was never settled. That is the wrong
instrument for the two questions this desk asks after every candidate, because neither is a
token question:

    "what failed that is mechanistically similar to this?"
    "which existing survivor would make this candidate redundant?"

A desk that cannot answer the first re-runs its own dead ends and pays the trial count twice --
and trial count is a SHARED cost here: the deflated-Sharpe charge and the program-level SPA/PBO
divide ONE family-wise error budget across every cell the desk has ever tested. A desk that
cannot answer the second buys the same business twice and calls it diversification; alpha_genome
measures that structurally for CERTIFIED cells only, and most of what this desk knows never
reached a certificate.

WHAT IS INDEXED -- everything the desk has learned that carries words, one document per row:

    lesson         docs/desk_lessons.jsonl                     the corpus never forgotten
    hypothesis     data/hypothesis_graph.jsonl                 born/failed/certified, with `why`
    verdict        data/hypotheses/gate_verdict_ledger.jsonl   which gate a cell died at
    survivor       reports/UNIVERSAL_SURVIVORS.json            ten-gate passes, with shadow_spec
    claim          reports/DEEP_FOREST.json                    mined stories, mechanism class
    llm_hypothesis data/intelligence/**/discoveries_*.json     the seats' donations (newest 2000)
    genome         reports/ALPHA_GENOME.json                   structural fingerprints
    commit         git log --format=%h%x09%s -400              what the desk did to itself
    trade_outcome  data/live_ledger.jsonl                      per sleeve: n deals, sum R

NO SERVICE AND NO NETWORK, by construction: a hashing TF-IDF vectoriser (32,768 buckets, IDF
measured over the corpus, rows L2-normalised, cosine = one dot product) on numpy alone. No model
to download, no key to leak, no endpoint to be down at 04:00 when the promoter wants an answer.
Worse than a sentence transformer at paraphrase, BETTER than BM25 at the thing that matters
here, because the rendered text carries the MECHANISM VOCABULARY -- the family name split on its
underscores, the params keys, the failing stage and the `why` prose all land in the same bucket
space, so `session_range_breakout` and "breaks the Asian session range" overlap.

DETERMINISTIC ON PURPOSE: buckets are blake2b, never Python's `hash()`, which is salted per
process -- an index built by a scheduled leg must score identically when queried here. Ties
break by document order, which is sorted.

UNMEASURED IS A VERDICT (L1.28a). An absent source is skipped AND COUNTED: `manifest["sources"]`
names every source, its path, its status and its rows, so "nothing failed like this" can be read
against "that ledger was not there" -- a different sentence. A `git` that will not run is
UNMEASURED, not zero commits.

CLI: build [--limit-per-kind N] | query TEXT [--k --kinds --symbol --family] | failures TEXT |
     redundant --symbol S --family F | unknown [--axis-a --axis-b]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter, deque
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from functools import lru_cache
from hashlib import blake2b
from itertools import islice
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent                              # repo root

N_BUCKETS = 1 << 15
TOKENISER = "v1:alnum2+cjk1"
KINDS = ("lesson", "hypothesis", "verdict", "survivor", "claim", "llm_hypothesis",
         "genome", "commit", "trade_outcome")
#: A fate meaning the desk already spent this trial and lost it.
DEAD_FATES = frozenset({"FAILED", "BURIED", "KILLED", "REJECTED", "RETIRED"})
LLM_ROW_CAP, COMMIT_CAP = 2000, 400
_TOKEN = re.compile(r"[a-z0-9]{2,}|[一-鿿]")
_STOP_WORDS = """a an and are as at be been but by for from has had have in into is it its of on
or that the their this to was were will with which when where than then there these those not
no only also very over under more most"""
_STOP = frozenset(_STOP_WORDS.split())
#: Family WORD -> mechanism class. Word-based rather than a registry of family names on purpose:
#: a family minted tomorrow still lands in a class, and one that lands in none is reported
#: UNCLASSIFIED rather than guessed into a neighbour.
MECHANISM_WORDS: tuple[tuple[str, str], ...] = (
    ("breakout", "breakout"), ("range", "breakout"), ("session", "breakout"),
    ("momentum", "trend"), ("trend", "trend"), ("reversion", "reversion"),
    ("revert", "reversion"), ("decay", "reversion"), ("gap", "reversion"), ("carry", "carry"),
    ("swap", "carry"), ("residual", "residual"), ("relative", "residual"), ("pca", "residual"),
    ("correlation", "residual"), ("vol", "volatility"), ("liquidity", "microstructure"),
    ("orderflow", "microstructure"), ("spread", "microstructure"), ("calendar", "calendar"),
    ("month", "calendar"), ("dow", "calendar"), ("seasonal", "calendar"), ("event", "event"),
    ("macro", "macro"), ("regime", "regime"), ("cot", "positioning"),
)


# --------------------------------------------------------------------------- paths & records

def _desk() -> Path:
    """The desk root. The env var exists so a CLI can be pointed at a synthetic tree."""
    return Path(os.environ.get("QUANT_SEMANTIC_DESK") or BASE)


def _repo() -> Path:
    return Path(os.environ.get("QUANT_SEMANTIC_REPO") or ROOT)


def home() -> Path:
    """Where the index lives: index.npz + docs.jsonl + manifest.json."""
    return Path(os.environ.get("QUANT_SEMANTIC_HOME") or (_desk() / "data" / "semantic_memory"))


def sources() -> dict[str, Path]:
    """Every corpus source by kind. `commit` has no path -- it is read from git."""
    desk, repo = _desk(), _repo()
    return {"lesson": repo / "docs" / "desk_lessons.jsonl",
            "hypothesis": desk / "data" / "hypothesis_graph.jsonl",
            "verdict": desk / "data" / "hypotheses" / "gate_verdict_ledger.jsonl",
            "survivor": desk / "reports" / "UNIVERSAL_SURVIVORS.json",
            "claim": desk / "reports" / "DEEP_FOREST.json",
            "llm_hypothesis": desk / "data" / "intelligence",
            "genome": desk / "reports" / "ALPHA_GENOME.json",
            "trade_outcome": desk / "data" / "live_ledger.jsonl"}


@dataclass
class Doc:
    doc_id: str
    kind: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Hit:
    doc_id: str
    kind: str
    score: float
    text: str
    meta: dict[str, Any]
    structural: bool = False


@dataclass(frozen=True)
class Manifest:
    at: str
    n_docs: int
    by_kind: dict[str, int]
    vocab_hash: str
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    limit_per_kind: int = 0
    n_buckets: int = N_BUCKETS
    tokeniser: str = TOKENISER

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> Manifest:
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in row.items() if k in names})

    @property
    def absent(self) -> list[str]:
        """Sources NOT read -- the denominator behind every empty answer."""
        return sorted(k for k, r in self.sources.items() if str(r.get("status")) != "READ")


# --------------------------------------------------------------------------- tolerant readers

def _text(*parts: Any) -> str:
    """Render a sentence out of whatever the row happened to carry. Never raises."""
    out: list[str] = []
    for p in parts:
        if p is None or isinstance(p, bool):
            continue
        if isinstance(p, dict):
            out.append(" ".join(str(k) for k in p))
            out.extend(str(v) for v in p.values() if isinstance(v, str))
        elif isinstance(p, list | tuple):
            out.extend(str(v) for v in p if isinstance(v, str | int | float))
        else:
            out.append(str(p))
    return " ".join(s for s in (x.strip() for x in out) if s)


def _rows(path: Path, limit: int) -> list[dict[str, Any]]:
    """The LAST `limit` json objects of a jsonl append-log -- newest is the useful end."""
    keep: deque[dict[str, Any]] = deque(maxlen=limit or None)
    with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                keep.append(row)
    return list(keep)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))


def _failing_stage(gates: Any) -> str:
    if isinstance(gates, dict):
        for name, g in gates.items():
            if isinstance(g, dict) and g.get("passed") is False:
                return str(name)
    return ""


def _report_rows(blob: Any, keys: Iterable[str],
                 limit: int) -> Iterator[tuple[str, dict[str, Any]]]:
    """Rows from a report that may be a list, a dict of rows, or a dict holding either."""
    def numbered(seq: Iterable[Any]) -> Iterator[tuple[str, dict[str, Any]]]:
        for i, r in enumerate(seq):
            if isinstance(r, dict):
                yield str(r.get("cell") or r.get("id") or i), r

    found: Iterator[tuple[str, dict[str, Any]]] = iter(())
    if isinstance(blob, list):
        found = numbered(blob)
    elif isinstance(blob, dict):
        for key in keys:
            inner = blob.get(key)
            if isinstance(inner, dict):
                found = ((str(n), r) for n, r in inner.items() if isinstance(r, dict))
                break
            if isinstance(inner, list):
                found = numbered(inner)
                break
    return islice(found, limit or None)


def _read_lessons(path: Path, limit: int) -> list[Doc]:
    docs = []
    for row in _rows(path, limit):
        lid = str(row.get("id") or row.get("lesson_id") or len(docs))
        tags = [t for t in (row.get("tags") or []) if isinstance(t, str)]
        docs.append(Doc(f"lesson:{lid}", "lesson",
                        _text(row.get("lesson"), row.get("evidence"), tags, row.get("source")),
                        {"lesson_id": lid, "tags": tags, "outcome": "LESSON",
                         "source": str(row.get("source") or ""),
                         "at": str(row.get("learned") or "")}))
    return docs


def _read_hypotheses(path: Path, limit: int) -> list[Doc]:
    docs = []
    for row in _rows(path, limit):
        fate = str(row.get("fate") or "").upper()
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        stage = _failing_stage(row.get("gates"))
        docs.append(Doc(f"hypothesis:{row.get('id') or len(docs)}", "hypothesis",
                        _text(row.get("symbol"), row.get("family"), params, row.get("why"),
                              row.get("source"), fate, stage),
                        {"symbol": str(row.get("symbol") or ""), "fate": fate, "stage": stage,
                         "family": str(row.get("family") or ""), "outcome": fate,
                         "source": str(row.get("source") or ""),
                         "why": str(row.get("why") or ""), "at": str(row.get("at") or "")}))
    return docs


def _read_verdicts(path: Path, limit: int) -> list[Doc]:
    docs = []
    for i, row in enumerate(_rows(path, limit)):
        passed = bool(row.get("passed"))
        verdict = str(row.get("verdict") or ("PASS" if passed else "FAIL")).upper()
        stage = str(row.get("stage") or row.get("terminal_gate") or "")
        cell = str(row.get("cell") or "")
        why = _text(row.get("why"), row.get("message"), row.get("downstream_status"))
        docs.append(Doc(f"verdict:{i}:{cell}", "verdict",
                        _text(row.get("sym") or cell.split(".")[0], row.get("family"), cell,
                              "gate", stage, verdict, why),
                        {"symbol": str(row.get("sym") or ""), "cell": cell, "stage": stage,
                         "family": str(row.get("family") or ""), "verdict": verdict,
                         "outcome": verdict, "passed": passed, "why": why,
                         "at": str(row.get("at") or "")}))
    return docs


def _read_survivors(path: Path, limit: int) -> list[Doc]:
    docs = []
    for name, r in _report_rows(_json(path), ("survivors", "rows", "cells"), limit):
        spec = r.get("shadow_spec") if isinstance(r.get("shadow_spec"), dict) else {}
        sym = str(spec.get("symbol") or r.get("sym") or r.get("symbol") or "")
        fam = str(spec.get("family") or r.get("family") or "")
        docs.append(Doc(f"survivor:{name}", "survivor",
                        _text(sym, fam, spec.get("selector"), spec.get("condition"),
                              r.get("hunt"), r.get("cell"), "survivor certified universal"),
                        {"symbol": sym, "family": fam, "outcome": "SURVIVOR",
                         "selector": str(spec.get("selector") or ""), "days": r.get("days"),
                         "hunt": str(r.get("hunt") or ""),
                         "status": str(r.get("status") or "UNIVERSAL")}))
    return docs


def _read_claims(path: Path, limit: int) -> list[Doc]:
    docs = []
    for name, r in _report_rows(_json(path), ("claims", "top_claims", "rows"), limit):
        syms = [s for s in (r.get("symbols") or []) if isinstance(s, str)]
        mech = str(r.get("mechanism_class") or r.get("mechanism") or "")
        docs.append(Doc(f"claim:{name}", "claim",
                        _text(r.get("title"), r.get("claim"), mech, syms, r.get("channel"),
                              r.get("evidence_grade"), r.get("ground"), r.get("mechanism_key")),
                        {"symbol": syms[0] if syms else "", "symbols": syms, "mechanism": mech,
                         "outcome": "CLAIM", "grade": str(r.get("evidence_grade") or ""),
                         "url": str(r.get("url") or "")}))
    return docs


def _read_genome(path: Path, limit: int) -> list[Doc]:
    docs = []
    for name, r in _report_rows(_json(path), ("genome", "sleeves"), limit):
        docs.append(Doc(f"genome:{name}", "genome",
                        _text(r.get("symbol"), r.get("asset_class"), r.get("family"),
                              r.get("mechanism"), r.get("direction_bias"), r.get("clock"),
                              r.get("legs"), r.get("factor_roles"), r.get("source")),
                        {"symbol": str(r.get("symbol") or ""),
                         "family": str(r.get("family") or ""),
                         "mechanism": str(r.get("mechanism") or ""),
                         "asset_class": str(r.get("asset_class") or ""),
                         "clock": str(r.get("clock") or ""),
                         "outcome": str(r.get("status") or "GENOME")}))
    return docs


def _read_llm(root: Path, limit: int) -> list[Doc]:
    """The seats' donations, NEWEST FILE FIRST and capped -- 8,800 files is a crawl, not a read."""
    cap = min(limit or LLM_ROW_CAP, LLM_ROW_CAP)
    docs: list[Doc] = []
    for path in sorted(root.rglob("discoveries_*.json"),
                       key=lambda p: (-p.stat().st_mtime, str(p))):
        if len(docs) >= cap:
            break
        try:
            blob = _json(path)
        except (OSError, ValueError):
            continue
        rows = blob if isinstance(blob, list) else (
            blob.get("discoveries") or blob.get("rows") if isinstance(blob, dict) else None)
        seat = path.parent.name
        for i, r in enumerate(islice(rows or [], cap - len(docs))):
            if not isinstance(r, dict):
                continue
            syms = [s for s in (r.get("symbols") or []) if isinstance(s, str)]
            docs.append(Doc(f"llm:{seat}:{path.stem}:{i}", "llm_hypothesis",
                            _text(r.get("kind") or r.get("type"), r.get("family"), syms,
                                  r.get("why"), r.get("hypothesis"), r.get("description"),
                                  r.get("title"), r.get("summary"), r.get("source"), seat),
                            {"symbol": syms[0] if syms else "", "symbols": syms, "seat": seat,
                             "family": str(r.get("family") or ""),
                             "outcome": str(r.get("kind") or r.get("type") or "DONATION")}))
    return sorted(docs, key=lambda d: d.doc_id)


def _read_trades(path: Path, limit: int) -> list[Doc]:
    """One document per SLEEVE, not per deal: n and sum R is what redundancy reads."""
    agg: dict[str, dict[str, Any]] = {}
    for row in _rows(path, 0):
        sleeve = str(row.get("sleeve") or "").strip()
        if not sleeve:
            continue
        a = agg.setdefault(sleeve, {"n": 0, "sum_r": 0.0, "pl": 0.0, "symbol": ""})
        a["n"] += 1
        try:
            a["sum_r"] += float(row.get("r_multiple") or 0.0)
            a["pl"] += float(row.get("pl_quote") or 0.0)
        except (TypeError, ValueError):
            pass
        a["symbol"] = a["symbol"] or str(row.get("symbol") or "")
    docs = []
    for sleeve in sorted(agg)[:limit or None]:
        a = agg[sleeve]
        outcome = "PROFITABLE" if a["sum_r"] > 0 else ("LOSING" if a["sum_r"] < 0 else "FLAT")
        docs.append(Doc(f"trade:{sleeve}", "trade_outcome",
                        _text(a["symbol"], sleeve, "live sleeve traded", f"{a['n']} deals",
                              "sum R", f"{a['sum_r']:.3f}", outcome),
                        {"symbol": a["symbol"], "sleeve": sleeve, "n": a["n"], "family": "",
                         "sum_r": round(float(a["sum_r"]), 6),
                         "pl_quote": round(float(a["pl"]), 4), "outcome": outcome}))
    return docs


def _read_commits(repo: Path, limit: int) -> tuple[list[Doc], str]:
    """Commit subjects. A git that will not run is UNMEASURED -- never zero commits."""
    n = min(limit or COMMIT_CAP, COMMIT_CAP)
    cmd = ["git", "-C", str(repo), "log", "--format=%h%x09%s", f"-{n}"]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"UNMEASURED: {type(exc).__name__}"
    if p.returncode != 0:
        return [], f"UNMEASURED: git exit {p.returncode}"
    docs = []
    for line in p.stdout.decode("utf-8", errors="replace").splitlines():
        sha, _, subject = line.partition("\t")
        if sha and subject:
            docs.append(Doc(f"commit:{sha}", "commit", subject,
                            {"sha": sha, "outcome": "COMMIT"}))
    return docs, "READ"


# --------------------------------------------------------------------------- enrichment

def mechanism_of(family: str) -> str:
    """The mechanism class a family name implies, or UNCLASSIFIED -- which is also an answer."""
    fam = str(family or "").lower()
    for word, mech in MECHANISM_WORDS:
        if word in fam:
            return mech
    return "UNCLASSIFIED" if fam else ""


def _asset_classes(desk: Path) -> dict[str, str]:
    """MetaTrader's own registry: the broker's answer, never a guess off the ticker."""
    try:
        reg = _json(desk / "data" / "universe" / "universe.json")
    except (OSError, ValueError):
        return {}
    if not isinstance(reg, dict):
        return {}
    return {str(k).upper(): str(v.get("asset_class") or "")
            for k, v in reg.items() if isinstance(v, dict)}


def _enrich(docs: list[Doc], desk: Path) -> None:
    """Fill mechanism and asset class everywhere, from the corpus's own two registries."""
    klass = _asset_classes(desk)
    fams: dict[str, str] = {}
    for d in docs:
        sym, fam = str(d.meta.get("symbol") or ""), str(d.meta.get("family") or "")
        if sym and d.meta.get("asset_class"):
            klass.setdefault(sym.upper(), str(d.meta["asset_class"]))
        if fam and d.meta.get("mechanism"):
            fams.setdefault(fam, str(d.meta["mechanism"]))
    known = sorted(fams, key=len, reverse=True)
    for d in docs:
        if d.kind == "trade_outcome" and not d.meta.get("family"):
            sleeve = str(d.meta.get("sleeve") or "").lower()
            d.meta["family"] = next((f for f in known if f.lower() in sleeve), "")
        fam = str(d.meta.get("family") or "")
        if not d.meta.get("mechanism"):
            d.meta["mechanism"] = fams.get(fam) or mechanism_of(fam)
        if not d.meta.get("asset_class"):
            d.meta["asset_class"] = klass.get(str(d.meta.get("symbol") or "").upper(), "")
        for key in ("symbol", "family", "outcome"):
            d.meta.setdefault(key, "")
        extra = _text(d.meta.get("mechanism"), d.meta.get("asset_class"))
        if extra:
            d.text = f"{d.text} {extra}".strip()


# --------------------------------------------------------------------------- the vectoriser

@lru_cache(maxsize=1 << 17)
def _bucket(token: str) -> int:
    """blake2b, NOT hash(): str hashing is salted per process and would move every vector."""
    return int.from_bytes(blake2b(token.encode(), digest_size=4).digest(), "big") % N_BUCKETS


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(str(text).lower()) if t not in _STOP]


def _counts(text: str) -> Counter[int]:
    return Counter(_bucket(t) for t in tokens(text))


def _tf(count: int) -> float:
    return 1.0 + math.log(count)


# --------------------------------------------------------------------------- build

def _atomic(path: Path, write: Callable[[Path], Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    write(tmp)
    os.replace(tmp, path)


def _savez(path: Path, **arrays: Any) -> None:
    """Through an open HANDLE, never a name: `savez` appends `.npz` to a name that lacks it,
    so the atomic `index.npz.tmp` would be written as `index.npz.tmp.npz` and the rename
    would then fail on a file that was never there."""
    with path.open("wb") as fh:
        np.savez_compressed(fh, **arrays)


def _collect(limit: int) -> tuple[list[Doc], dict[str, dict[str, Any]]]:
    """Every source read tolerantly; absence and unreadability are RECORDED, never fatal."""
    readers: dict[str, Callable[[Path, int], list[Doc]]] = {
        "lesson": _read_lessons, "hypothesis": _read_hypotheses, "verdict": _read_verdicts,
        "survivor": _read_survivors, "claim": _read_claims, "genome": _read_genome,
        "llm_hypothesis": _read_llm, "trade_outcome": _read_trades}
    docs: list[Doc] = []
    status: dict[str, dict[str, Any]] = {}
    for kind, path in sources().items():
        row: dict[str, Any] = {"path": str(path), "status": "ABSENT", "n": 0}
        if path.exists():
            try:
                got = readers[kind](path, limit)
                docs.extend(got)
                row.update(status="READ", n=len(got))
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                row["status"] = f"UNREADABLE: {type(exc).__name__}: {exc}"
        status[kind] = row
    got, git_status = _read_commits(_repo(), limit)
    docs.extend(got)
    status["commit"] = {"path": f"git log @ {_repo()}", "status": git_status, "n": len(got)}
    _enrich(docs, _desk())
    seen: set[str] = set()
    for d in docs:
        doc_id = d.doc_id
        while doc_id in seen:
            doc_id = f"{d.doc_id}#{len(seen)}"
        seen.add(doc_id)
        d.doc_id = doc_id
    return docs, status


def build(limit_per_kind: int = 5000) -> Manifest:
    """Read every source, render every document, write index.npz + docs.jsonl + manifest.json."""
    docs, status = _collect(limit_per_kind)
    rows_l: list[int] = []
    cols_l: list[int] = []
    raw_l: list[float] = []
    df = np.zeros(N_BUCKETS, dtype=np.int64)
    for i, d in enumerate(docs):
        cnt = _counts(d.text)
        for bucket, n in sorted(cnt.items()):
            rows_l.append(i)
            cols_l.append(bucket)
            raw_l.append(_tf(n))
        if cnt:
            df[list(cnt)] += 1
    n_docs = len(docs)
    idf = (np.log((1.0 + n_docs) / (1.0 + df)) + 1.0).astype(np.float32)
    rows = np.asarray(rows_l, dtype=np.int32)
    cols = np.asarray(cols_l, dtype=np.int32)
    vals = np.asarray(raw_l, dtype=np.float32) * idf[cols] if raw_l else np.zeros(0, np.float32)
    norm = np.sqrt(np.bincount(rows, weights=np.square(vals, dtype=np.float64),
                               minlength=max(n_docs, 1)))
    if len(vals):
        vals = (vals / np.where(norm > 0.0, norm, 1.0)[rows]).astype(np.float32)
    man = Manifest(at=datetime.now(UTC).isoformat(), n_docs=n_docs,
                   by_kind=dict(sorted(Counter(d.kind for d in docs).items())),
                   vocab_hash=blake2b(f"{TOKENISER}|{N_BUCKETS}".encode() + idf.tobytes(),
                                      digest_size=8).hexdigest(),
                   sources=status, limit_per_kind=int(limit_per_kind))
    out = home()
    _atomic(out / "docs.jsonl", lambda p: p.write_text("".join(
        json.dumps({"doc_id": d.doc_id, "kind": d.kind, "text": d.text, "meta": d.meta},
                   ensure_ascii=False, sort_keys=True) + "\n" for d in docs), "utf-8"))
    _atomic(out / "index.npz", lambda p: _savez(
        p, rows=rows, cols=cols, vals=vals, idf=idf, n_docs=np.int64(n_docs),
        manifest=np.array(json.dumps(man.to_dict(), sort_keys=True))))
    _atomic(out / "manifest.json", lambda p: p.write_text(
        json.dumps(man.to_dict(), indent=1, sort_keys=True), "utf-8"))
    return man


def render_candidate(candidate: dict[str, Any]) -> str:
    """A candidate dict as the same kind of sentence the corpus was rendered into."""
    params = candidate.get("params") if isinstance(candidate.get("params"), dict) else {}
    fam = str(candidate.get("family") or "")
    return _text(candidate.get("symbol"), fam, mechanism_of(fam), params,
                 candidate.get("selector"), candidate.get("clock"), candidate.get("why"),
                 candidate.get("mechanism"), candidate.get("text"), candidate.get("asset_class"))


# --------------------------------------------------------------------------- query

class Memory:
    """A built index, loaded: cosine over L2-normalised hashing TF-IDF rows, plus filters."""

    def __init__(self, docs: list[Doc], rows: np.ndarray, cols: np.ndarray, vals: np.ndarray,
                 idf: np.ndarray, manifest: Manifest) -> None:
        self.docs, self.manifest = docs, manifest
        self.rows, self.cols, self.vals, self.idf = rows, cols, vals, idf
        self.n_docs = len(docs)
        self._class = {str(d.meta.get("symbol") or "").upper(): str(d.meta.get("asset_class"))
                       for d in docs if d.meta.get("asset_class")}

    @classmethod
    def load(cls, path: Path | None = None) -> Memory:
        out = Path(path) if path else home()
        with np.load(out / "index.npz", allow_pickle=False) as z:
            rows, cols, vals, idf = z["rows"], z["cols"], z["vals"], z["idf"]
            man = Manifest.from_dict(json.loads(str(z["manifest"].item())))
        docs = [Doc(str(r["doc_id"]), str(r["kind"]), str(r["text"]), dict(r.get("meta") or {}))
                for r in _rows(out / "docs.jsonl", 0)]
        return cls(docs, rows, cols, vals, idf, man)

    def vector(self, text: str) -> np.ndarray:
        """One query as an L2-normalised row in the same bucket space."""
        q = np.zeros(N_BUCKETS, dtype=np.float32)
        for bucket, n in _counts(text).items():
            q[bucket] = _tf(n) * self.idf[bucket]
        norm = float(np.linalg.norm(q))
        return q / norm if norm > 0.0 else q

    def scores(self, text: str) -> np.ndarray:
        if not self.n_docs or not len(self.rows):
            return np.zeros(self.n_docs, dtype=np.float64)
        q = self.vector(text)
        return np.bincount(self.rows, weights=self.vals * q[self.cols], minlength=self.n_docs)

    def _mask(self, kinds: Iterable[str] | None, symbol: str | None = None,
              family: str | None = None,
              keep: Callable[[Doc], bool] | None = None) -> np.ndarray:
        want = {str(k) for k in kinds} if kinds else None
        sym = (symbol or "").strip().upper() or None
        fam = (family or "").strip().lower() or None
        out = np.zeros(self.n_docs, dtype=bool)
        for i, d in enumerate(self.docs):
            ok = (want is None or d.kind in want)
            ok = ok and (sym is None or str(d.meta.get("symbol") or "").upper() == sym)
            ok = ok and (fam is None or str(d.meta.get("family") or "").lower() == fam)
            out[i] = ok and (keep is None or keep(d))
        return out

    def _hits(self, text: str, k: int, mask: np.ndarray) -> list[Hit]:
        sc = np.where(mask, self.scores(text), -1.0)
        order = np.argsort(-sc, kind="stable")[:max(int(k), 0)]
        return [Hit(self.docs[i].doc_id, self.docs[i].kind, round(float(sc[i]), 6),
                    self.docs[i].text, dict(self.docs[i].meta))  # a COPY: a caller that edits
                for i in order if sc[i] > 0.0]                   # a hit must not edit the index

    def query(self, text: str, k: int = 10, kinds: Iterable[str] | None = None,
              symbol: str | None = None, family: str | None = None) -> list[Hit]:
        """Cosine-nearest documents, structurally filtered first."""
        return self._hits(text, k, self._mask(kinds, symbol, family))

    def similar_failures(self, text_or_candidate: str | dict[str, Any], k: int = 10) -> list[Hit]:
        """What failed that is mechanistically similar to this -- and at WHICH gate.

        Restricted to what can BE a failure: a verdict that did not pass, a hypothesis whose fate
        is FAILED/BURIED, and the lesson corpus (a lesson is a recorded failure with a cost).
        Each hit carries `meta["stage"]` wherever the source named the gate it died at.
        """
        text = (text_or_candidate if isinstance(text_or_candidate, str)
                else render_candidate(text_or_candidate))

        def keep(d: Doc) -> bool:
            if d.kind == "verdict":
                return not d.meta.get("passed")
            if d.kind == "hypothesis":
                return str(d.meta.get("fate") or "").upper() in DEAD_FATES
            return d.kind == "lesson"

        return self._hits(text, k, self._mask(("verdict", "hypothesis", "lesson"), keep=keep))

    def redundant_with(self, candidate: dict[str, Any], k: int = 5) -> list[Hit]:
        """Which survivor (or live sleeve) already owns this mechanism.

        Cosine ranks; `structural` is the harder statement -- same family AND same symbol, or
        same family AND same asset class. A structural hit is the same business under another
        name whatever the cosine says, and that is the redundancy the allocator pays for twice.
        """
        fam = str(candidate.get("family") or "").lower()
        sym = str(candidate.get("symbol") or "").upper()
        klass = str(candidate.get("asset_class") or self._class.get(sym, "")).lower()
        out = []
        for h in self._hits(render_candidate(candidate), k,
                            self._mask(("survivor", "trade_outcome"))):
            same_fam = bool(fam) and str(h.meta.get("family") or "").lower() == fam
            same = same_fam and (
                (bool(sym) and str(h.meta.get("symbol") or "").upper() == sym)
                or (bool(klass) and str(h.meta.get("asset_class") or "").lower() == klass))
            out.append(Hit(h.doc_id, h.kind, h.score, h.text, h.meta, structural=same))
        return out

    def unknown_combinations(self, axis_a: str = "mechanism",
                             axis_b: str = "asset_class") -> list[tuple[str, str]]:
        """Pairs the corpus holds NOTHING on. Not tried-and-failed: never tried, by name."""
        drop = {"", "UNCLASSIFIED"}
        a_vals = sorted({str(d.meta.get(axis_a) or "") for d in self.docs} - drop)
        b_vals = sorted({str(d.meta.get(axis_b) or "") for d in self.docs} - drop)
        seen = {(str(d.meta.get(axis_a) or ""), str(d.meta.get(axis_b) or "")) for d in self.docs}
        return [(a, b) for a in a_vals for b in b_vals if (a, b) not in seen]


# --------------------------------------------------------------------------- CLI

def _print(hits: list[Hit]) -> None:
    for h in hits:
        stage = f" stage={h.meta['stage']}" if h.meta.get("stage") else ""
        flag = " STRUCTURAL" if h.structural else ""
        print(f"  {h.score:.4f}  {h.kind:<14} {h.doc_id}{stage}{flag}")
        print(f"          {h.text[:150]}")


# ================================================== THE EXPERIENCE SPLIT (Tier-1 Q17)
#: THE SIX NEGATIVE CLASSES, DERIVED FROM THE GATE A CELL DIED AT -- never from prose. A verdict
#: ledger row names its terminal gate; this maps that name onto the class of MISTAKE it records,
#: so "what kind of thing goes wrong here" is a count rather than an impression. `other` is a
#: real class: a death nothing here recognises must be visible, not filed under the nearest label.
NEGATIVE_CLASSES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("leakage", ("pit", "point_in_time", "lookahead", "leak", "survivorship")),
    ("cost_killed", ("stress_cost", "cost", "net_edge", "spread", "slippage", "impact")),
    ("parameter_fragility", ("pbo", "walk_forward", "cpcv", "stability", "fragility",
                             "deflated_sharpe", "overfit")),
    ("duplicate_family", ("novelty", "orthogonality", "redundan", "correlation", "duplicate")),
    ("regime_failure", ("regime", "invariance", "state_admission", "conditional")),
    ("forward_failure", ("forward", "shadow", "live", "reconcile", "enrol")),
)
#: What `distil` writes. Read by the deepening worker BEFORE it generates (see `experience`).
EXPERIENCE = "experience_memory.json"


def negative_class(stage: str) -> str:
    """The class of mistake a terminal gate name records. `other` when nothing matches."""
    s = str(stage or "").strip().lower()
    if not s:
        return "other"
    for name, needles in NEGATIVE_CLASSES:
        if any(n in s for n in needles):
            return name
    return "other"


def _pos_neg(docs: Sequence[Doc]) -> tuple[list[Doc], list[Doc]]:
    pos: list[Doc] = []
    neg: list[Doc] = []
    for d in docs:
        if d.kind == "survivor":
            pos.append(d)
        elif d.kind == "hypothesis":
            fate = str(d.meta.get("fate") or "").upper()
            if fate in DEAD_FATES:
                neg.append(d)
            elif fate == "CERTIFIED":
                pos.append(d)
        elif d.kind == "verdict":
            (pos if d.meta.get("passed") else neg).append(d)
        elif d.kind == "trade_outcome":
            with contextlib.suppress(TypeError, ValueError):
                (pos if float(d.meta.get("sum_r") or 0.0) > 0.0 else neg).append(d)
        elif d.kind == "lesson":
            neg.append(d)
    return pos, neg


def positive(docs: Sequence[Doc] | None = None) -> list[Doc]:
    """MECHANISMS THAT SURVIVED: certificates, passed gates, certified hypotheses, sleeves whose
    live R is positive. The half of experience a generator should imitate."""
    return _pos_neg(list(docs) if docs is not None else _loaded_docs())[0]


def negative(docs: Sequence[Doc] | None = None) -> list[Doc]:
    """WHAT WENT WRONG: failed gate verdicts, buried hypotheses, the lesson corpus, sleeves whose
    live R is negative. The half a generator should refuse to repeat."""
    return _pos_neg(list(docs) if docs is not None else _loaded_docs())[1]


def _loaded_docs() -> list[Doc]:
    try:
        return list(Memory.load().docs)
    except (OSError, ValueError, KeyError) as exc:
        raise RuntimeError(f"semantic index unreadable: {type(exc).__name__}: {exc}") from exc


def distil(docs: Sequence[Doc] | None = None, *, top: int = 12,
           out: Path | None = None) -> dict[str, Any]:
    """POSITIVE and NEGATIVE experience, distilled to `data/experience_memory.json`.

    FactorMiner's split (Tier-1 Q17): retrieve -> generate -> evaluate -> DISTIL. The index
    answers "what is similar to this"; this answers the two questions a generator asks before it
    has a candidate at all -- what construction has worked here, and what class of mistake keeps
    killing things here. Per negative class: how many cells died that way, and the exemplars with
    the gate they died at. Per positive family: how many survived, in which asset classes, and
    the conditions the certificate declared. An empty class is a MEASURED zero, never a gap.
    """
    rows = list(docs) if docs is not None else _loaded_docs()
    pos, neg = _pos_neg(rows)
    by_class: dict[str, dict[str, Any]] = {name: {"n": 0, "examples": []}
                                           for name, _ in NEGATIVE_CLASSES}
    by_class["other"] = {"n": 0, "examples": []}
    for d in neg:
        stage = str(d.meta.get("stage") or d.meta.get("terminal_gate") or d.kind)
        slot = by_class[negative_class(stage)]
        slot["n"] += 1
        if len(slot["examples"]) < top:
            slot["examples"].append({"doc_id": d.doc_id, "kind": d.kind, "stage": stage,
                                     "symbol": d.meta.get("symbol"),
                                     "family": d.meta.get("family"),
                                     "mechanism": d.meta.get("mechanism"),
                                     "text": d.text[:220]})
    by_family: dict[str, dict[str, Any]] = {}
    for d in pos:
        fam = str(d.meta.get("family") or "UNDECLARED")
        slot = by_family.setdefault(fam, {"n": 0, "asset_classes": {}, "constructions": []})
        slot["n"] += 1
        klass = str(d.meta.get("asset_class") or "UNCLASSIFIED")
        slot["asset_classes"][klass] = int(slot["asset_classes"].get(klass, 0)) + 1
        if len(slot["constructions"]) < top:
            slot["constructions"].append({"doc_id": d.doc_id, "kind": d.kind,
                                          "symbol": d.meta.get("symbol"),
                                          "mechanism": d.meta.get("mechanism"),
                                          "text": d.text[:220]})
    doc = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_docs": len(rows), "n_positive": len(pos), "n_negative": len(neg),
        "status": "MEASURED" if rows else "UNMEASURED",
        "negative": dict(sorted(by_class.items())),
        "positive": dict(sorted(by_family.items(), key=lambda kv: -int(kv[1]["n"]))),
        "negative_classes": [n for n, _ in NEGATIVE_CLASSES] + ["other"],
        "rule": ("POSITIVE = survivors, passed gate verdicts, certified hypotheses, sleeves with "
                 "positive live R. NEGATIVE = failed verdicts, buried hypotheses, the lesson "
                 "corpus, sleeves with negative live R, classed by the GATE they died at. "
                 "Written every `semantic_memory build`; read by the deepening worker before it "
                 "generates (Tier-1 Q17)"),
        "consumer": "desks/mt5/research/deepening_worker.py (retrieval before generation)",
    }
    target = out if out is not None else (_desk() / "data" / EXPERIENCE)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic(target, lambda p: p.write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                                               "utf-8"))
    except OSError as exc:                                    # pragma: no cover - disk
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return doc


def experience(path: Path | None = None) -> dict[str, Any]:
    """The distilled experience, or an UNMEASURED verdict. The retrieval side of Q17."""
    p = path if path is not None else (_desk() / "data" / EXPERIENCE)
    try:
        doc = json.loads(p.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {"status": "UNMEASURED",
                                                  "why": f"{p.name} is not an object"}
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED",
                "why": f"{p.name} unreadable ({type(exc).__name__}); no experience to retrieve"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="semantic institutional memory (local, no service)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").add_argument("--limit-per-kind", type=int, default=5000)
    for name in ("query", "failures"):
        p = sub.add_parser(name)
        p.add_argument("text")
        p.add_argument("--k", type=int, default=10)
        p.add_argument("--kinds", nargs="*", default=None, choices=list(KINDS))
        p.add_argument("--symbol", default=None)
        p.add_argument("--family", default=None)
    r = sub.add_parser("redundant")
    for flag in ("--symbol", "--family", "--asset-class", "--text"):
        r.add_argument(flag, default="")
    r.add_argument("--k", type=int, default=5)
    u = sub.add_parser("unknown")
    u.add_argument("--axis-a", default="mechanism")
    u.add_argument("--axis-b", default="asset_class")
    u.add_argument("--limit", type=int, default=40)
    a = ap.parse_args(argv)

    if a.cmd == "build":
        man = build(a.limit_per_kind)
        # THE EXPERIENCE SPLIT RIDES THE SAME PASS (Tier-1 Q17). Building the index and then
        # leaving the positive/negative views to a second clock is how an organ goes dark; the
        # distillation is cheap beside the vectoriser and lands on every build.
        try:
            exp = distil()
            print(f"  experience: {exp['n_positive']} positive / {exp['n_negative']} negative "
                  f"-> {_desk() / 'data' / EXPERIENCE}")
        except (RuntimeError, OSError, ValueError) as exc:
            print(f"  experience: UNMEASURED ({type(exc).__name__}: {exc})")
        print(f"SEMANTIC MEMORY  {man.n_docs} docs  vocab {man.vocab_hash}  -> {home()}")
        for kind in KINDS:
            print(f"  {kind:<15} {man.by_kind.get(kind, 0):>7}  "
                  f"{man.sources.get(kind, {}).get('status', 'ABSENT')}")
        if man.absent:
            print(f"  NOT READ (skipped, counted): {', '.join(man.absent)}")
        return 0
    mem = Memory.load()
    if a.cmd == "query":
        _print(mem.query(a.text, k=a.k, kinds=a.kinds, symbol=a.symbol, family=a.family))
    elif a.cmd == "failures":
        _print(mem.similar_failures(a.text, k=a.k))
    elif a.cmd == "redundant":
        _print(mem.redundant_with({"symbol": a.symbol, "family": a.family, "why": a.text,
                                   "asset_class": a.asset_class}, k=a.k))
    else:
        pairs = mem.unknown_combinations(a.axis_a, a.axis_b)
        print(f"{len(pairs)} {a.axis_a} x {a.axis_b} combinations with ZERO documents")
        for pa, pb in pairs[:a.limit]:
            print(f"  {pa:<18} {pb}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

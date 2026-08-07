"""VAULT RETRIEVAL -- one hop from a question to the section of docs/ that answers it.

THE PROBLEM, MEASURED: docs/ is 208,409 lines across 118 files, and the whole repo is 565,542
lines. No context window holds that. So every organ that needs to know what the desk already
decided -- an audit, a sweep, a cycle, a fresh session -- either greps blind or proceeds without
knowing, and the second is what actually happens. `CLAUDE.md` fixed orientation and
`.claude/desk-state.sh` fixed live numbers; neither helps with "has this been decided before, and
where".

**THIS IS LEXICAL RETRIEVAL (BM25), NOT SEMANTIC SEARCH, AND THE DISTINCTION IS NOT PEDANTRY.**
No embedding model is reachable from this desk -- the analysis clone is network-policy-denied at
the gateway (GAP row 91) and the LLM panel is unfunded. Shipping BM25 under the word "semantic"
would be exactly the overclaim this repo exists to catch, and the failure mode is specific: a
caller who believes the index understands MEANING will read an empty result as "the desk never
considered this", when it may only mean the query used different words. **An empty result here is
NOT EVIDENCE OF ABSENCE.** It is evidence that these tokens do not appear.

Where lexical is genuinely strong, and why it is the right build rather than a consolation: this
corpus is dense with distinctive technical tokens -- `reduce_only`, `deflation`, `ratchet`,
`L1.50`, `PBO`, `newClientOrderId`. Those are precisely the terms an organ searches for, and BM25
ranks them well. Where it is weak is conceptual paraphrase, and callers are told so.

CHUNKED BY HEADING, NOT BY FIXED WINDOW. A section is the unit of meaning in this vault: a law and
its rationale are one thought, and a 500-token window cuts them apart -- returning the rule without
the reason, which is how a rule gets applied in a case it was never meant for. Every chunk carries
its heading path, so a hit is CITABLE (`docs/CONSTITUTION.md > L1.50 ...`) rather than a blob a
caller has to go find again.

Stdlib only, deliberately: this is on the research path and in an MCP server, and an import there is
a dependency on someone else's release schedule (the same argument libs/execution/idempotency.py
makes for the order path).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Searched by default. `docs/` is the vault; `ops/memory/` holds standing operator notes that are
#: decisions in every sense that matters and were previously reachable only by knowing they existed.
DEFAULT_ROOTS: tuple[str, ...] = ("docs", "ops/memory")

#: EXCLUDED BY DEFAULT, and this is a relevance decision rather than a tidiness one. `docs/audit_
#: shards/` is GENERATED: thirteen near-identical dumps of source code, claimed as a directory class
#: in max_audit._TERMINAL_ARTIFACTS. Measured on the first real query, they took two of the top
#: three hits with IDENTICAL text at the same line number in two different shards -- because the
#: same code appears in all of them. A search surface where generated duplicates outrank the
#: decisions is worse than no search: it is confidently wrong at the top, which is the position a
#: reader trusts most. `recent_changes.md` is excluded for the same reason (an append-only log of
#: diffs, not a decision). Pass `include_generated=True` to search them anyway.
GENERATED: tuple[str, ...] = ("docs/audit_shards/", "docs/research/recent_changes.md")

#: BM25. k1 controls term-frequency saturation, b the length normalisation. Standard values --
#: tuning them against a corpus with no relevance judgements would be fitting noise, and this
#: module has no ground truth to fit against. Left at the defaults with that said out loud.
K1: float = 1.5
B: float = 0.75

_TOKEN = re.compile(r"[a-z0-9_]{2,}")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")

#: A NUMBERED TABLE ROW IS A UNIT OF MEANING HERE, and heading-chunking alone cannot see that.
#: FOUND BY THE TEST, not by reading: `docs/GAP_REGISTER.md` -- the document that ranks what the
#: desk should work on -- is ENTIRELY a markdown table with no internal headings, so every gap row
#: collapsed into one ~390-line chunk. BM25 length normalisation (b=0.75) then crushed it, and a
#: query naming a defect the register describes in detail surfaced VPS_BRINGUP.md instead. The most
#: decision-dense file in the vault was effectively unsearchable, and it looked like it worked.
#: One row = one decision, so each is chunked on its own.
_TABLE_ROW = re.compile(r"^\|\s*(\d+[a-z]?)\s*\|")

#: Tokens carrying no discriminating power in THIS corpus. Deliberately short: an aggressive stop
#: list silently deletes queries. "data", "desk" and "research" appear in nearly every document
#: here, so they cost ranking without adding it.
_STOP = frozenset([
    "the", "an", "and", "or", "of", "to", "in", "is", "it", "be", "as", "at", "by", "for", "on",
    "this", "that", "with", "from", "not", "are", "was", "were", "will", "we", "our", "you",
    "your", "they", "them", "his", "her", "its", "if", "then", "than", "so", "such", "but",
    "no", "nor", "can", "may", "might",
])


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


@dataclass(frozen=True)
class Chunk:
    """One heading-delimited section, kept citable."""

    path: str
    heading: str          # full heading path, e.g. "LEVEL 1 > L1.50 A FLOOR THAT HAS NOT RISEN"
    text: str
    line: int             # 1-indexed line of the heading, so a hit opens at the right place

    @property
    def cite(self) -> str:
        return f"{self.path}:{self.line}" + (f"  §{self.heading}" if self.heading else "")


@dataclass
class VaultIndex:
    """BM25 over heading-delimited chunks. Built in memory; the corpus is small enough that
    persisting it would add a staleness failure mode for no measurable gain."""

    chunks: list[Chunk] = field(default_factory=list)
    _tf: list[Counter[str]] = field(default_factory=list)
    _df: Counter[str] = field(default_factory=Counter)
    _len: list[int] = field(default_factory=list)
    _avg: float = 0.0

    def __len__(self) -> int:
        return len(self.chunks)

    def add(self, chunk: Chunk) -> None:
        toks = _tokens(chunk.heading + "\n" + chunk.text)
        self.chunks.append(chunk)
        tf = Counter(toks)
        self._tf.append(tf)
        self._df.update(tf.keys())
        self._len.append(len(toks))
        self._avg = (sum(self._len) / len(self._len)) if self._len else 0.0

    def search(self, query: str, *, limit: int = 8,
               path_filter: str = "") -> list[tuple[float, Chunk]]:
        """Rank chunks against `query`. Returns (score, chunk), best first, zero-scoring dropped.

        ZERO RESULTS MEANS "THESE TOKENS ARE ABSENT", NOT "THE DESK NEVER CONSIDERED THIS". Callers
        that read it as absence will conclude a decision was never made when it was made in other
        words -- and on this desk, re-deciding something already decided is exactly the waste the
        vault exists to prevent.
        """
        q = _tokens(query)
        if not q or not self.chunks:
            return []
        n = len(self.chunks)
        scored: list[tuple[float, Chunk]] = []
        for i, chunk in enumerate(self.chunks):
            if path_filter and path_filter not in chunk.path:
                continue
            tf, dl = self._tf[i], self._len[i]
            s = 0.0
            for term in q:
                f = tf.get(term, 0)
                if not f:
                    continue
                # BM25 IDF, the +0.5/+0.5 form: bounded below so a term appearing in nearly every
                # chunk cannot go negative and start SUBTRACTING from the score of a document that
                # genuinely contains it.
                idf = math.log(1.0 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                denom = f + K1 * (1.0 - B + B * dl / (self._avg or 1.0))
                s += idf * f * (K1 + 1.0) / denom
            if s > 0.0:
                scored.append((s, chunk))
        scored.sort(key=lambda x: (-x[0], x[1].path, x[1].line))
        return scored[:limit]


def _split(path: Path, rel: str) -> list[Chunk]:
    """Split a markdown file into heading-delimited chunks, carrying the heading PATH.

    Preamble before the first heading becomes its own chunk rather than being discarded -- in this
    vault the text above the first `##` is routinely the document's whole thesis (see
    GAP_REGISTER.md, whose re-rank rationale lives there), and dropping it would make the most
    important paragraph in several documents unsearchable.
    """
    try:
        lines = path.read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    out: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    cur_head, cur_line = "", 1

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body or cur_head:
            out.append(Chunk(path=rel, heading=cur_head, text=body, line=cur_line))

    for i, line in enumerate(lines, 1):
        row = _TABLE_ROW.match(line)
        if row:
            # Emit the row as its own chunk, keeping the heading path so it stays citable and the
            # row id in the heading so "row 91" is itself a searchable token.
            out.append(Chunk(path=rel, heading=f"{cur_head} > row {row.group(1)}".lstrip(" >"),
                             text=line.strip(), line=i))
            continue
        m = _HEADING.match(line)
        if not m:
            buf.append(line)
            continue
        flush()
        depth, title = len(m.group(1)), m.group(2).strip()
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack.append((depth, title))
        cur_head, cur_line, buf = " > ".join(t for _d, t in stack), i, []
    flush()
    return [c for c in out if c.text or c.heading]


def build(roots: tuple[str, ...] = DEFAULT_ROOTS, *, base: Path = ROOT,
          include_generated: bool = False) -> VaultIndex:
    """Index every markdown file under `roots`. Deterministic order, so two builds agree."""
    idx = VaultIndex()
    for r in roots:
        d = base / r
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.md")):
            rel = p.relative_to(base).as_posix()
            if not include_generated and any(rel.startswith(g) or rel == g for g in GENERATED):
                continue
            for chunk in _split(p, rel):
                idx.add(chunk)
    return idx


def format_hits(hits: list[tuple[float, Chunk]], *, width: int = 320) -> str:
    """Render for a terminal or an MCP tool result -- citation first, then enough body to judge.

    The citation leads because the point of this index is to send the reader to the SOURCE. A
    result that is pleasant to read and hard to locate would encourage acting on the excerpt, and
    an excerpt is not the decision.
    """
    if not hits:
        return ("no chunk contains these tokens. NOT EVIDENCE OF ABSENCE -- this index is LEXICAL "
                "(BM25), so a decision recorded in different words will not match. Re-query with "
                "the vocabulary the document would have used, or grep directly.")
    out = []
    for score, c in hits:
        body = " ".join(c.text.split())
        out.append(f"[{score:5.1f}] {c.cite}\n        {body[:width]}"
                   + ("..." if len(body) > width else ""))
    return "\n".join(out)

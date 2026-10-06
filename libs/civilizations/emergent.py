"""THE ONTOLOGY FRONTIER: unknown-unknowns become classes, and classes become new ground.

    zuck, 2026-10-05: "The blueprint is never considered closed ... 'Not listed in this mandate'
    must never mean 'out of scope'. This must continuously autonomously happen and evolve 24/7."

The output ontology (libs.civilizations.ontology) is a fixed bank of named signals. Anything it
does not recognise used to end in NO_VALUE, counted and closed. This module keeps that residue
working:

1. OBSERVE. Every routed item's text is cut into content-word bigrams (and repository topics).
   A term any ontology signal already matches is KNOWN and skipped; the rest are counted by
   document frequency and by distinct source.
2. PROMOTE. A term seen in >= MIN_DF items from >= MIN_SOURCES lanes is a recurring concept the
   desk has no class for: it is born as an emergent class (`emergent_classes.json`), with the
   evidence that bore it. Classes are never deleted, so the ontology only widens.
3. ROUTE. An item the fixed bank calls NO_VALUE but that carries an emergent class's term is
   routed to EMERGENT_CLASS (its own outcome ledger, read by the knowledge graph), not closed.
4. EXPLORE. Each emergent class, and each coverage-tensor mission, becomes a query for the
   frontier GitHub search lane; the repositories it discovers are promoted to mining lanes by the
   resident's frontier promoter. New concepts therefore buy new ground on their own.

Deterministic and bounded: the lexicon keeps at most MAX_TERMS rows (singletons pruned first).
"""
from __future__ import annotations

import functools
import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

from libs.civilizations import ontology as O

MIN_DF = 5
MIN_SOURCES = 2
MAX_TERMS = 20_000
MAX_SOURCES_KEPT = 10
MAX_QUERIES = 30
_WORD = re.compile(r"[a-z][a-z0-9]{2,}")
#: function words and the vocabulary of every code/README page: never a concept
STOP = frozenset(re.findall(r"\w+", """
the and for with that this from are was were has have had not but you your our their they them
its can will would should could may might must into onto over under than then there here when
what which who whom whose why how all any each every some such only also more most less least
very just like use used using uses based about above after again against before being below
between both down during few further once other same too out off own while where http https www
com org net html github readme license licence copyright install pip import return def class
self none true false null var let const function new get set run file files code example
examples data value values type types list dict str int float bool test tests version docs
default config see note todo fixme issue issues pull request main master branch commit update
added fixed remove removed support make makes made one two three first last time times
"""))


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


@functools.lru_cache(maxsize=200_000)
def _known(term: str) -> bool:
    """A term the fixed bank already recognises is not unknown."""
    return any(rx.search(term) for _k, _n, _w, rx in O.SIGNALS)


#: a sentence counts only when it is about markets: a concept is unknown to a TRADING ontology,
#: not merely unknown (otherwise every library name in a README would be born a class)
MARKET = re.compile(r"\b(market|price|pric(e|ing)|trad(e|er|ing)|futures?|stocks?|equit(y|ies)|"
                    r"forex|fx|currenc(y|ies)|commodit(y|ies)|volatility|returns?|alpha|factor|"
                    r"hedg(e|ing)|yields?|spreads?|index|indices|bonds?|rates?|portfolio|"
                    r"liquidity|flows?|carry|momentum|arbitrage|options?|gold|oil|metals?)\b")
_SENT = re.compile(r"[.!?;\n]+")


def terms(text: str, *, topics: Iterable[str] = (), cap_chars: int = 20_000) -> set[str]:
    out: set[str] = set()
    for sent in _SENT.split(str(text or "")[:cap_chars].lower()):
        if not MARKET.search(sent):
            continue
        words = [w for w in _WORD.findall(sent) if w not in STOP]
        out.update(f"{a} {b}" for a, b in pairwise(words) if a != b)
    out.update(str(t).lower().replace("-", " ") for t in topics if t)
    return {t for t in out if not _known(t)}


def _bump(book: dict[str, dict[str, Any]], term: str, *, at: str, df: int = 1,
          source_id: str | None = None, uri: str | None = None,
          sources: Iterable[str] = (), examples: Iterable[str] = ()) -> None:
    row = book.setdefault(term, {"df": 0, "sources": [], "first_seen": at, "examples": []})
    row["df"] += df
    row["first_seen"] = min(str(row["first_seen"]), at)
    for sid in [*sources, *([source_id] if source_id else [])]:
        if sid not in row["sources"] and len(row["sources"]) < MAX_SOURCES_KEPT:
            row["sources"].append(sid)
    for u in [*examples, *([uri] if uri else [])]:
        if len(row["examples"]) < 3 and u not in row["examples"]:
            row["examples"].append(u)


class EmergentLexicon:
    """The residue lexicon and the classes it has given birth to (both durable JSON)."""

    def __init__(self, data_dir: Path, *, exclude: re.Pattern[str] | None = None) -> None:
        self.lex_path = Path(data_dir) / "emergent_lexicon.json"
        self.cls_path = Path(data_dir) / "emergent_classes.json"
        self.exclude = exclude
        self.lex: dict[str, dict[str, Any]] = self._load(self.lex_path)
        self.classes: dict[str, dict[str, Any]] = self._load(self.cls_path)
        self.observed = 0
        # what THIS process observed since its last sync: the resident and the hourly leg each
        # hold a lexicon, so a save merges its delta into the file instead of overwriting it
        self.delta: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _load(p: Path) -> dict[str, dict[str, Any]]:
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            return {}
        return doc if isinstance(doc, dict) else {}

    def observe(self, text: str, *, source_id: str, uri: str,
                topics: Iterable[str] = ()) -> None:
        self.observed += 1
        at = _iso(_now())
        for t in terms(text, topics=topics):
            if self.exclude is not None and self.exclude.search(t):
                continue
            for book in (self.lex, self.delta):
                _bump(book, t, at=at, source_id=source_id, uri=uri)

    def sync(self) -> None:
        """Re-read the files, add this process's delta, keep every class either side holds."""
        disk = self._load(self.lex_path)
        for t, d in self.delta.items():
            _bump(disk, t, at=str(d["first_seen"]), df=int(d["df"]), sources=d["sources"],
                  examples=d["examples"])
        self.lex = disk
        self.classes = {**self.classes, **self._load(self.cls_path)}
        self.delta = {}

    def match(self, text: str) -> list[str]:
        """Emergent classes whose term appears in `text` (the ROUTE step)."""
        if not self.classes:
            return []
        body = " ".join(_WORD.findall(str(text or "")[:60_000].lower()))
        return sorted(t for t in self.classes if f" {t} " in f" {body} ")

    def promote(self) -> list[str]:
        born = []
        at = _iso(_now())
        for t, row in self.lex.items():
            if t in self.classes:
                self.classes[t]["df"] = row["df"]
                self.classes[t]["sources"] = list(row["sources"])
                continue
            if row["df"] >= MIN_DF and len(row["sources"]) >= MIN_SOURCES:
                self.classes[t] = {"born_at": at, "df": row["df"],
                                   "sources": list(row["sources"]),
                                   "examples": list(row["examples"]),
                                   "first_seen": row["first_seen"]}
                born.append(t)
        return born

    def prune(self) -> int:
        if len(self.lex) <= MAX_TERMS:
            return 0
        keep = sorted(self.lex, key=lambda t: (t not in self.classes, -self.lex[t]["df"],
                                               self.lex[t]["first_seen"]))[:MAX_TERMS]
        dropped = len(self.lex) - len(keep)
        self.lex = {t: self.lex[t] for t in keep}
        return dropped

    def save(self) -> None:
        for p, doc in ((self.lex_path, self.lex), (self.cls_path, self.classes)):
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(doc, ensure_ascii=False), "utf-8")
            tmp.replace(p)

    def queries(self, missions: Iterable[Mapping[str, Any]], *, n: int = MAX_QUERIES
                ) -> list[str]:
        """EXPLORE: the frontier search lane's queries, the youngest emergent classes first
        (they are the least explored), then the coverage tensor's missions."""
        young = sorted(self.classes, key=lambda t: (str(self.classes[t].get("born_at")),
                                                   -int(self.classes[t].get("df") or 0)),
                       reverse=True)
        out = [f"{t} trading" for t in young[: n // 2]]
        for m in missions:
            q = str(m.get("query") or "").strip()
            if q and q not in out:
                out.append(q)
            if len(out) >= n:
                break
        return out[:n]

    def report(self, born: list[str], pruned: int) -> dict[str, Any]:
        top = sorted(self.lex.items(), key=lambda kv: -int(kv[1]["df"]))[:50]
        return {"generated_at": _iso(_now()),
                "rule": (f"a term no ontology signal matches, seen in >= {MIN_DF} items from "
                         f">= {MIN_SOURCES} lanes, is born as an EMERGENT_CLASS; classes are "
                         "never deleted; their items are routed to EMERGENT_CLASS instead of "
                         "NO_VALUE and their terms drive the frontier GitHub search"),
                "classes": len(self.classes), "born_this_pass": born,
                "lexicon_terms": len(self.lex), "pruned_this_pass": pruned,
                "observed_this_pass": self.observed,
                "emergent_classes": self.classes,
                "nearest_to_birth": [{"term": t, "df": r["df"], "sources": len(r["sources"])}
                                     for t, r in top if t not in self.classes][:25]}

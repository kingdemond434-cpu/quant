"""THE VOCABULARY PROPOSER: learn the names the desk's intake uses and the desk does not know.

WHY THIS EXISTS (N9 item 12, unknown-unknown engine; classification 2026-11-10)

`unseen_frontier` counts mechanism species per ground, and it refuses to guess: a sighting
whose family, tag or claim class the desk's own vocabulary cannot place is counted as
`sightings_unknown_mechanism` and learnt from by nobody. Measured on the box 2026-11-09 07:01Z:
48,647 such sightings and 57,765 rows naming neither a mechanism nor a feature, against a
mechanism vocabulary of 20 words. Every one of those rows is a miner telling the desk something
in words it cannot read, and the richest pile of unknown unknowns on the desk was a counter.

WHAT IT DOES. One streaming pass over the same four grounds `unseen_frontier` reads (mined
claims, the deep forest's top claims, the seats' `data/intelligence/**/discoveries_*.json`,
`hypothesis_graph.jsonl`), under the same caps. Every LABEL a row carries (its family, each
mechanism tag, its claim class) that the desk cannot place is a candidate word. For each word
it keeps how many rows and how many distinct grounds use it, and two independent readings of
what it means:

  co-label  the mechanisms of the rows where the word appears beside a label the desk DOES
            know (a row tagged `forced_liquidation` and `momentum` says the first word travels
            with trend_persistence);
  kind vote the feature names and parameter kinds the word's rows carry, scored against the
            mechanisms those same kinds carry on rows the desk can place, each kind weighted by
            how specific it is (a kind every mechanism uses votes for none).

A word used on at least MIN_GROUNDS grounds and MIN_ROWS rows becomes:

  ALIAS               both readings agree on one known mechanism (or one is silent and the
                      other is decisive, share >= ALIAS_SHARE): the word is read as that
                      mechanism from the next pass on;
  PROPOSED_MECHANISM  the readings disagree or neither is decisive: the word is its own
                      candidate mechanism, `proposed:<word>`, and is counted as a species of
                      its own instead of vanishing into UNKNOWN.

Below the floor a word is counted, never dropped (`below_floor`).

THE CONSUMER. `data/vocabulary_aliases.json` is read by `unseen_frontier.mechanism_of` as the
last resort after the desk's own family table and claim classes, so the estimate the allocator
and the source registry read stops discarding what the miners keep finding. A proposed
mechanism is labelled as proposed everywhere it appears; it never borrows a known mechanism's
name and it never reaches a bar, a size or an order.

WHAT IT REFUSES. A word that is a number, shorter than MIN_WORD, or one of the generic
labels in STOP_LABELS is not a mechanism and is skipped with a count. Rows naming no label at
all teach nothing about words and are counted as `rows_without_label`.

    python desks/mt5/research/vocabulary_proposer.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
if str(BASE / "research") not in sys.path:
    sys.path.insert(0, str(BASE / "research"))

import unseen_frontier as uf  # noqa: E402

REPORT = BASE / "reports" / "VOCABULARY_PROPOSALS.json"
ALIASES = BASE / "data" / "vocabulary_aliases.json"

#: A word must be used on this many distinct grounds (language|source) ...
MIN_GROUNDS = 3
#: ... and on this many rows before it is read at all. One forum's private jargon is not yet
#: a word the field uses.
MIN_ROWS = 20
#: A reading is decisive when its top mechanism holds this share of its evidence.
ALIAS_SHARE = 0.60
#: The co-label reading needs this many co-labelled rows to speak.
MIN_COLABEL = 10
MIN_WORD = 3
#: Labels that name a data source, a status or a container, never a mechanism.
STOP_LABELS = frozenset({
    "unknown", "none", "null", "other", "misc", "general", "test", "todo", "na", "n_a",
    "strategy", "signal", "alpha", "factor", "hypothesis", "idea", "trade", "trading",
    "market", "price", "returns", "return", "discovery", "claim", "story", "forum", "news",
})
#: Kinds kept per word; the vote reads the most used.
MAX_KINDS_PER_WORD = 64
MAX_GROUNDS_KEPT = 64
MAX_SAMPLE_SYMBOLS = 8
TOP_N = 200


def _word(label: Any) -> str:
    return uf._tok(label)


def _usable(word: str) -> bool:
    return (len(word) >= MIN_WORD and not word.replace("_", "").isdigit()
            and word not in STOP_LABELS)


def known_mechanism(word: str) -> str:
    """The desk's own reading of one label, with no help from this organ."""
    named = uf.classify_family(word)
    if named != uf.UNKNOWN:
        return named
    return uf.CLASS_MECHANISM.get(word, uf.UNKNOWN)


class Row:
    """What one intake row says: its labels, its kinds, its ground and its symbols."""

    __slots__ = ("ground", "kinds", "labels", "symbols")

    def __init__(self, labels: Iterable[Any], kinds: frozenset[str], ground: str,
                 symbols: Any) -> None:
        self.labels = [w for w in (_word(x) for x in labels) if w]
        self.kinds = kinds
        self.ground = ground
        self.symbols = symbols


def _ground(language: Any, source: Any) -> str:
    return f"{_word(language) or uf.UNKNOWN}|{_word(source) or uf.UNKNOWN}"


def _tags(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list | tuple) else []


def rows(note: dict[str, str], stats: Counter[str]) -> Iterator[Row]:
    """The four grounds, read the way `unseen_frontier` reads them and under its caps."""
    for row in uf._iter_jsonl(uf.CLAIMS, note, uf.MAX_JSONL_LINES):
        stats["claim_rows"] += 1
        inst = row.get("instruments")
        yield Row([row.get("mechanism_class")], uf.kind_set(None, row.get("quantities")),
                  _ground(row.get("language") or row.get("lang"), row.get("source")),
                  inst.get("analogues") if isinstance(inst, dict) else None)
    doc = uf._read_json(uf.DEEP_FOREST, note)
    for row in (doc.get("top_claims") or []) if isinstance(doc, dict) else []:
        if isinstance(row, dict):
            stats["deep_forest_rows"] += 1
            yield Row([row.get("mechanism_class")], uf.kind_set(None, row.get("quantities")),
                      _ground(row.get("language") or row.get("lang"),
                              row.get("source") or "deep_forest"), row.get("symbols"))
    files = uf._discovery_files()
    if not files:
        note[uf.INTELLIGENCE.name] = "ABSENT"
    read = 0
    for path in files:
        try:
            body = json.loads(path.read_text("utf-8-sig"))
        except (OSError, ValueError):
            stats["discovery_files_unreadable"] += 1
            continue
        items = body if isinstance(body, list) else body.get("discoveries")
        if not isinstance(items, list):
            continue
        read += 1
        for row in items:
            if not isinstance(row, dict):
                continue
            stats["discovery_rows"] += 1
            yield Row([row.get("family"), *_tags(row.get("mechanism_tags")),
                       row.get("mechanism_class")],
                      uf.kind_set(row.get("params"), row.get("mechanism")),
                      _ground(row.get("lang") or row.get("language"),
                              row.get("source") or path.parent.name), row.get("symbols"))
    if files:
        note[uf.INTELLIGENCE.name] = f"READ({read}/{len(files)})"
    for row in uf._iter_jsonl(uf.GRAPH, note, uf.MAX_JSONL_LINES):
        stats["graph_rows"] += 1
        yield Row([row.get("family")], uf.kind_set(row.get("params")),
                  _ground(row.get("lang") or row.get("language"),
                          str(row.get("source") or "").split(":")[0]), row.get("symbol"))


class Word:
    __slots__ = ("colabel", "grounds", "kinds", "n_rows", "n_unplaced", "symbols")

    def __init__(self) -> None:
        self.n_rows = 0
        self.n_unplaced = 0
        self.grounds: set[str] = set()
        self.colabel: Counter[str] = Counter()
        self.kinds: Counter[str] = Counter()
        self.symbols: list[str] = []


def _symbols(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple):
        return [str(s) for s in value if isinstance(s, str | int)]
    return []


def collect(stream: Iterable[Row], stats: Counter[str]) -> tuple[dict[str, Word],
                                                                  dict[str, Counter[str]]]:
    """One pass: unplaced words with their evidence, and kind -> mechanism on placed rows."""
    words: dict[str, Word] = defaultdict(Word)
    kind_mech: dict[str, Counter[str]] = defaultdict(Counter)
    for row in stream:
        if not row.labels:
            stats["rows_without_label"] += 1
            continue
        placed = {w: known_mechanism(w) for w in row.labels}
        mechs = {m for m in placed.values() if m != uf.UNKNOWN}
        # Only a row the desk places COMPLETELY teaches what a kind means: a row that also
        # carries an unplaced word would let that word vote for itself through its own kinds.
        if mechs and all(m != uf.UNKNOWN or not _usable(w) for w, m in placed.items()):
            for m in mechs:
                for k in row.kinds:
                    kind_mech[k][m] += 1
        for w, m in placed.items():
            if m != uf.UNKNOWN:
                continue
            if not _usable(w):
                stats["labels_refused"] += 1
                continue
            rec = words[w]
            rec.n_rows += 1
            if not mechs:
                rec.n_unplaced += 1
            if len(rec.grounds) < MAX_GROUNDS_KEPT:
                rec.grounds.add(row.ground)
            for m in mechs:
                rec.colabel[m] += 1
            for k in row.kinds:
                if k in rec.kinds or len(rec.kinds) < MAX_KINDS_PER_WORD:
                    rec.kinds[k] += 1
            if len(rec.symbols) < MAX_SAMPLE_SYMBOLS:
                for s in _symbols(row.symbols):
                    if s not in rec.symbols:
                        rec.symbols.append(s)
    stats["placed_kinds"] = len(kind_mech)
    return dict(words), dict(kind_mech)


def kind_vote(kinds: Counter[str], kind_mech: dict[str, Counter[str]]) -> Counter[str]:
    """Score each known mechanism by the kinds this word's rows carry, each kind weighted by how
    few mechanisms share it (log of mechanisms over mechanisms-with-kind). A kind every
    mechanism uses weighs zero."""
    n_mech = len({m for c in kind_mech.values() for m in c}) or 1
    vote: Counter[str] = Counter()
    for k, uses in kinds.items():
        dist = kind_mech.get(k)
        if not dist:
            continue
        idf = math.log(n_mech / len(dist))
        if idf <= 0:
            continue
        total = sum(dist.values())
        for m, c in dist.items():
            vote[m] += uses * idf * c / total
    return vote


def _top(c: Counter[str]) -> tuple[str | None, float, float]:
    total = float(sum(c.values()))
    if total <= 0:
        return None, 0.0, 0.0
    m, v = c.most_common(1)[0]
    return m, v / total, total


def judge(word: str, rec: Word, kind_mech: dict[str, Counter[str]]) -> dict[str, Any]:
    """The verdict on one word, with every number it rests on."""
    co_m, co_share, co_n = _top(rec.colabel)
    kv = kind_vote(rec.kinds, kind_mech)
    kv_m, kv_share, _ = _top(kv)
    co_says = co_m if co_n >= MIN_COLABEL and co_share >= ALIAS_SHARE else None
    kv_says = kv_m if kv_share >= ALIAS_SHARE else None
    if len(rec.grounds) < MIN_GROUNDS or rec.n_rows < MIN_ROWS:
        verdict, mechanism = "BELOW_FLOOR", None
    elif co_says and (kv_says in (None, co_says)):
        verdict, mechanism = "ALIAS", co_says
    elif kv_says and co_n < MIN_COLABEL:
        verdict, mechanism = "ALIAS", kv_says
    else:
        verdict, mechanism = "PROPOSED_MECHANISM", f"proposed:{word}"
    return {
        "word": word, "verdict": verdict, "mechanism": mechanism,
        "n_rows": rec.n_rows, "n_unplaced_rows": rec.n_unplaced,
        "n_grounds": len(rec.grounds), "grounds_sample": sorted(rec.grounds)[:8],
        "colabel": {"top": co_m, "share": round(co_share, 3), "n": int(co_n)},
        "kind_vote": {"top": kv_m, "share": round(kv_share, 3),
                      "kinds_used": len(rec.kinds)},
        "top_kinds": [k for k, _ in rec.kinds.most_common(8)],
        "symbols_sample": rec.symbols,
    }


def build(stream: Iterable[Row] | None = None) -> dict[str, Any]:
    note: dict[str, str] = {}
    stats: Counter[str] = Counter()
    words, kind_mech = collect(rows(note, stats) if stream is None else stream, stats)
    verdicts = [judge(w, r, kind_mech) for w, r in words.items()]
    verdicts.sort(key=lambda v: (-v["n_unplaced_rows"], -v["n_rows"], v["word"]))
    by = Counter(v["verdict"] for v in verdicts)
    aliases = {v["word"]: v["mechanism"] for v in verdicts if v["verdict"] == "ALIAS"}
    proposed = {v["word"]: v["mechanism"] for v in verdicts
                if v["verdict"] == "PROPOSED_MECHANISM"}
    reached = sum(v["n_unplaced_rows"] for v in verdicts if v["verdict"] != "BELOW_FLOOR")
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "inputs": note,
        "rows_read": {k: int(stats[k]) for k in
                      ("claim_rows", "deep_forest_rows", "discovery_rows", "graph_rows")},
        "rows_without_label": int(stats["rows_without_label"]),
        "labels_refused": int(stats["labels_refused"]),
        "words_unplaced": len(verdicts),
        "verdicts": dict(by),
        "unplaced_rows_now_readable": int(reached),
        "aliases": aliases,
        "proposed": proposed,
        "words": verdicts[:TOP_N],
        "floors": {"min_grounds": MIN_GROUNDS, "min_rows": MIN_ROWS,
                   "alias_share": ALIAS_SHARE, "min_colabel": MIN_COLABEL},
        "consumer": ("desks/mt5/research/unseen_frontier.py mechanism_of "
                     "(data/vocabulary_aliases.json)"),
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write(report: dict[str, Any]) -> Path:
    _atomic_write(REPORT, json.dumps(report, indent=1, ensure_ascii=False, default=str))
    _atomic_write(ALIASES, json.dumps({"at": report["at"], "aliases": report["aliases"],
                                       "proposed": report["proposed"]},
                                      indent=1, ensure_ascii=False, sort_keys=True))
    return REPORT


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="learn the intake's unplaced mechanism words")
    ap.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    args = ap.parse_args(argv)
    report = build()
    target = "DRY RUN (nothing written)" if args.dry_run else str(write(report))
    print(f"VOCABULARY PROPOSER {report['at']}  inputs: "
          + ", ".join(f"{k}={v}" for k, v in report["inputs"].items()))
    print(f"  unplaced words {report['words_unplaced']}  verdicts {report['verdicts']}  "
          f"rows now readable {report['unplaced_rows_now_readable']}  "
          f"rows without a label {report['rows_without_label']} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

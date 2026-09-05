"""THE TAXONOMY IS DISCOVERED. There is no enum of event types in this file and there must
never be one.

THE FAILURE THIS PREVENTS, stated as plainly as it deserves. If the event schema carries a closed
list of categories, then the first genuinely novel event class -- the one nobody anticipated,
which is reliably the one that moves markets most -- arrives as "not in the list" and is dropped.
The desk's blindness is then structural and invisible: the ledger shows nothing happened. A
system that can only recognise what it was told about on the day it was written is the hardcoded
table the principal ruled out, wearing a different name.

HOW A CATEGORY COMES INTO EXISTENCE HERE.

    1. Everything is recorded. An item that matches nothing gets `UNCLASSIFIED`, maximum
       novelty, and a place in the unclassified pool. It keeps its credibility score, its
       measured cross-asset reaction and its unpriced fraction, because all of those are
       measurable WITHOUT knowing what kind of event it is. What it does not get is capital
       authority.
    2. Assignment is nearest-centroid over the ledger's own instances, not over a rule. A
       category's centroid IS the mean of the items previously assigned to it, so the meaning of
       a category drifts with the evidence rather than with an author's memory.
    3. Emergence: when the unclassified pool contains at least `MIN_EMERGE` items that mutually
       cluster, a NEW category is minted, labelled from its own distinguishing tokens, status
       EMERGENT. It has no capital authority until it accumulates `ledger.MIN_CATEGORY_N`
       measured reactions and survives replay -- so discovery is cheap and trust is not.

THE SEEDS ARE BOOTSTRAP, NOT TRUTH. `SEED_HINTS` exists only so a cold ledger is not one
undifferentiated pool on day one. Each seed is a handful of words that names a coverage area the
desk knows it wants to see; the moment real instances arrive, the centroid is rebuilt from THEM
and the seed's contribution decays to nothing (`_centroid` weights instances over seeds and drops
the seed entirely past `SEED_RETIRE_N`). A seed that never attracts instances is visible in the
report as exactly that -- a coverage area the desk cannot see -- which is a purchasing decision.

WHY TOKEN HASHING AND NOT AN LLM. The capture path on this desk has a standing rule that no LLM
sits in it (`news_desk.py`), and it is the right rule: a capture path must be deterministic,
replayable to the byte, and cheap enough to run on every item. Hashed token vectors with cosine
similarity are all three. They are also weaker than an embedding model, which is a real cost, and
the honest consequence is a higher UNCLASSIFIED rate rather than a confident wrong label. An
embedding model may be added later as an ADDITIONAL feature block; it may not become the only
one, because the replay must stay reproducible.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ledger import MACRO_DIR, write_json_atomic
from .schema import UNCLASSIFIED, Status, now_iso

#: Feature width. 512 hashed buckets over a vocabulary of a few thousand macro tokens keeps
#: collisions rare enough not to matter and the vector small enough to hold thousands in memory.
DIM = 512

#: Cosine above which an item joins an existing category. Set where a shared topic word alone is
#: NOT enough -- two headlines must share several distinguishing tokens. Raising it costs recall
#: (more UNCLASSIFIED, which is recorded and safe); lowering it costs precision (confident wrong
#: labels, which contaminate every statistic conditioned on the category). The asymmetry is why
#: this number is deliberately on the high side and is never tuned down to reduce UNCLASSIFIED.
ASSIGN_SIM = 0.45

#: Mutual similarity required for two unclassified items to be in the same emergent cluster.
EMERGE_SIM = 0.55

#: Instances required before an emergent cluster becomes a category at all. This is a
#: DISCOVERY floor, not an evidence floor: a new category still needs `MIN_CATEGORY_N` measured
#: reactions before any estimate conditioned on it is reportable.
MIN_EMERGE = 12

#: Once a category has this many real instances, its seed words are dropped from the centroid
#: entirely -- the evidence has replaced the guess.
SEED_RETIRE_N = 25

TAXONOMY_PATH = MACRO_DIR / "taxonomy.json"

_TOKEN_RE = re.compile(r"[a-z][a-z0-9'&-]{1,}")

#: Words that carry no discriminating information in a macro feed.
_STOP = frozenset((
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "that", "this", "these",
    "those", "of", "in", "on", "at", "to", "for", "from", "by", "with", "without", "as",
    "is", "are", "was", "were", "be", "been", "being", "it", "its", "it's", "has", "have",
    "had", "do", "does", "did", "not", "no", "nor", "so", "such", "very", "more", "most",
    "much", "many", "new", "news", "say", "says", "said", "report", "reports", "reported",
    "after", "before", "during", "over", "under", "about", "into", "out", "up", "down",
    "we", "our", "you", "your", "they", "their", "he", "she", "his", "her", "i", "me", "my",
))

#: BOOTSTRAP ONLY. Coverage areas the desk knows it wants to see, so a cold ledger has structure
#: on day one. Emphatically NOT the taxonomy: these are starting centroids that the evidence
#: overwrites, and the discovered categories that matter most are the ones not on this list.
#: Keys are labels; values are seed words. Adding one here is cheap and changes nothing about
#: what the layer CAN see -- coverage is decided by `sources.py`, not by this dict.
SEED_HINTS: dict[str, tuple[str, ...]] = {
    "central_bank_policy": ("rate", "rates", "policy", "committee", "hike", "cut", "hold",
                            "monetary", "meeting", "minutes", "governor", "bank", "basis",
                            "points", "decision", "statement"),
    "inflation_release": ("inflation", "cpi", "ppi", "prices", "consumer", "producer",
                          "deflator", "core", "yoy", "index"),
    "labour_release": ("employment", "payrolls", "unemployment", "jobs", "jobless", "claims",
                       "wages", "earnings", "labour", "labor", "hiring"),
    "growth_release": ("gdp", "growth", "output", "production", "industrial", "pmi", "retail",
                       "sales", "confidence", "sentiment", "activity"),
    "fiscal_political": ("budget", "election", "parliament", "coalition", "government",
                         "minister", "vote", "referendum", "deficit", "spending", "tax"),
    "trade_policy": ("tariff", "tariffs", "sanctions", "export", "import", "quota", "embargo",
                     "controls", "trade", "duties", "restrictions"),
    "conflict_security": ("strike", "strikes", "attack", "military", "conflict", "war",
                          "ceasefire", "escalation", "troops", "missile", "border", "security"),
    "energy_supply": ("opec", "crude", "oil", "barrel", "output", "inventories", "refinery",
                      "pipeline", "gas", "lng", "production", "cuts"),
    "agriculture_supply": ("harvest", "crop", "yield", "drought", "planting", "acreage",
                           "soybean", "soybeans", "corn", "wheat", "sugar", "coffee", "cocoa",
                           "cotton", "export", "exports", "shipments", "usda"),
    "shipping_logistics": ("shipping", "freight", "canal", "strait", "port", "vessel",
                           "chokepoint", "tanker", "blockade", "congestion"),
    "credit_financial_stress": ("default", "downgrade", "rating", "bailout", "insolvency",
                                "liquidity", "bank", "deposit", "spreads", "credit", "bond",
                                "yields", "auction"),
    "fx_intervention": ("intervention", "peg", "devaluation", "revaluation", "currency",
                        "reserves", "verbal", "yen", "franc", "capital", "controls"),
    "corporate_earnings": ("earnings", "guidance", "quarterly", "revenue", "profit", "outlook",
                           "results", "buyback", "dividend", "forecast"),
    "regulatory_exchange": ("regulator", "regulation", "exchange", "listing", "margin",
                            "reconstitution", "rebalance", "index", "rule", "approval"),
    "natural_disaster": ("earthquake", "hurricane", "typhoon", "flood", "wildfire", "storm",
                         "eruption", "disaster", "evacuation", "damage"),
    "volatility_repricing": ("volatility", "vix", "options", "skew", "hedging", "gamma",
                             "implied", "repricing", "selloff", "rally"),
}

__all__ = [
    "ASSIGN_SIM",
    "DIM",
    "EMERGE_SIM",
    "MIN_EMERGE",
    "SEED_HINTS",
    "Assignment",
    "Taxonomy",
    "cosine",
    "tokenise",
    "vectorise",
]


def tokenise(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP and len(t) > 2]


def _bucket(token: str) -> tuple[int, float]:
    """Stable across processes and releases -- Python's `hash` is salted per interpreter, which
    would make a replay unreproducible between runs. blake2b is not."""
    h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    n = int.from_bytes(h, "big")
    return n % DIM, 1.0 if (n >> 20) & 1 else -1.0


def vectorise(text: str) -> dict[int, float]:
    """Signed hashed bag of words, sublinear term frequency, L2-normalised.

    Sublinear tf (1 + log count) stops a headline that repeats one word from becoming a vector
    about that word. Signed buckets make collisions cancel in expectation rather than
    accumulate, which is what keeps 512 buckets usable.
    """
    counts = Counter(tokenise(text))
    vec: dict[int, float] = {}
    for tok, c in counts.items():
        idx, sign = _bucket(tok)
        vec[idx] = vec.get(idx, 0.0) + sign * (1.0 + math.log(c))
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm <= 0:
        return {}
    return {k: v / norm for k, v in vec.items()}


def cosine(a: dict[int, float], b: dict[int, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return float(sum(v * b.get(k, 0.0) for k, v in a.items()))


def _mean(vecs: Sequence[dict[int, float]]) -> dict[int, float]:
    if not vecs:
        return {}
    acc: dict[int, float] = {}
    for v in vecs:
        for k, x in v.items():
            acc[k] = acc.get(k, 0.0) + x
    norm = math.sqrt(sum(x * x for x in acc.values()))
    if norm <= 0:
        return {}
    return {k: x / norm for k, x in acc.items()}


@dataclass(frozen=True)
class Assignment:
    category: str
    similarity: float
    status: str
    novelty: float
    note: str = ""


@dataclass
class Category:
    label: str
    origin: str                      # "seed" | "emergent"
    n_instances: int = 0
    centroid: dict[int, float] = field(default_factory=dict)
    top_tokens: tuple[str, ...] = ()
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "origin": self.origin, "n_instances": self.n_instances,
                "centroid": {str(k): round(v, 6) for k, v in self.centroid.items()},
                "top_tokens": list(self.top_tokens), "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Category:
        return cls(label=str(d.get("label", "")), origin=str(d.get("origin", "emergent")),
                   n_instances=int(d.get("n_instances", 0)),
                   centroid={int(k): float(v) for k, v in (d.get("centroid") or {}).items()},
                   top_tokens=tuple(d.get("top_tokens") or ()),
                   created_at=str(d.get("created_at", "")))


class Taxonomy:
    """The learned category registry. Persisted so a restart does not forget what it discovered.

    `fit(texts)` rebuilds every centroid from the ledger's own instances; `classify(text)` is a
    pure read. The two are separate on purpose: classification during capture must be fast,
    deterministic and side-effect-free so a replay of the same bytes gives the same label.
    """

    def __init__(self, path: Path | str | None = None,
                 seeds: dict[str, tuple[str, ...]] | None = None) -> None:
        self.path = Path(path) if path is not None else TAXONOMY_PATH
        self.seeds = dict(SEED_HINTS if seeds is None else seeds)
        self.categories: dict[str, Category] = {}
        self._instances: dict[str, list[dict[int, float]]] = {}
        self._corpus_df: Counter[str] = Counter()
        self._bootstrap()

    def _bootstrap(self) -> None:
        for label, words in self.seeds.items():
            self.categories[label] = Category(
                label=label, origin="seed", n_instances=0,
                centroid=vectorise(" ".join(words)), top_tokens=tuple(words[:6]),
                created_at="seed")

    # ------------------------------------------------------------------ persist ----
    def load(self) -> Taxonomy:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text("utf-8"))
            except (OSError, ValueError):
                return self
            for d in raw.get("categories", []):
                cat = Category.from_dict(d)
                if cat.label:
                    self.categories[cat.label] = cat
        return self

    def save(self) -> None:
        write_json_atomic(self.path, {
            "at": now_iso(),
            "assign_sim": ASSIGN_SIM, "emerge_sim": EMERGE_SIM, "min_emerge": MIN_EMERGE,
            "note": ("Categories are DISCOVERED from the ledger. Seeds are a cold-start "
                     "bootstrap and are dropped from a centroid once it has "
                     f"{SEED_RETIRE_N} real instances."),
            "categories": [c.to_dict() for c in
                           sorted(self.categories.values(), key=lambda c: c.label)],
        })

    # ------------------------------------------------------------------ fitting ----
    def fit(self, labelled: Iterable[tuple[str, str]]) -> Taxonomy:
        """Rebuild centroids from `(label, text)` pairs -- the ledger's own assigned instances.

        A category whose instances have arrived stops being its seed: past `SEED_RETIRE_N` the
        seed vector is dropped entirely, so the category means what the evidence says it means.
        """
        by_label: dict[str, list[str]] = {}
        for label, text in labelled:
            if label and label != UNCLASSIFIED:
                by_label.setdefault(label, []).append(text)
        for label, texts in by_label.items():
            vecs = [vectorise(t) for t in texts]
            cat = self.categories.get(label)
            seed_vec = vectorise(" ".join(self.seeds.get(label, ())))
            n = len(vecs)
            parts = list(vecs)
            if n < SEED_RETIRE_N and seed_vec:
                parts.append(seed_vec)
            centroid = _mean(parts)
            toks = Counter(t for text in texts for t in tokenise(text))
            self.categories[label] = Category(
                label=label, origin=(cat.origin if cat else "emergent"), n_instances=n,
                centroid=centroid, top_tokens=tuple(w for w, _ in toks.most_common(8)),
                created_at=(cat.created_at if cat and cat.created_at else now_iso()))
            self._instances[label] = vecs
        for text in (t for _, t in labelled if isinstance(t, str)):
            self._corpus_df.update(set(tokenise(text)))
        return self

    # --------------------------------------------------------------- classifying ----
    def classify(self, text: str, *, known_vectors: Sequence[dict[int, float]] = ()) -> Assignment:
        """Label an item, or refuse to. Refusal is a first-class, recorded outcome.

        `novelty` is 1 - the best similarity to anything the desk has seen (categories AND the
        recent-item vectors handed in). An item that matches nothing scores 1.0, which is the
        honest reading: maximum novelty and maximum uncertainty at the same time.
        """
        vec = vectorise(text)
        if not vec:
            return Assignment(UNCLASSIFIED, 0.0, Status.RECORDED_ONLY, 1.0,
                              "no usable tokens")
        best_label, best_sim = UNCLASSIFIED, 0.0
        for label, cat in self.categories.items():
            s = cosine(vec, cat.centroid)
            if s > best_sim:
                best_label, best_sim = label, s
        nearest_seen = max((cosine(vec, v) for v in known_vectors), default=0.0)
        novelty = max(0.0, 1.0 - max(best_sim, nearest_seen))
        if best_sim >= ASSIGN_SIM:
            cat = self.categories[best_label]
            status = Status.MEASURED if cat.n_instances >= MIN_EMERGE else Status.RECORDED_ONLY
            note = "" if status == Status.MEASURED else (
                f"category '{best_label}' has {cat.n_instances} instances "
                f"(< {MIN_EMERGE}); label recorded, no authority")
            return Assignment(best_label, round(best_sim, 4), status, round(novelty, 4), note)
        return Assignment(
            UNCLASSIFIED, round(best_sim, 4), Status.RECORDED_ONLY, round(novelty, 4),
            f"nearest category '{best_label}' at {best_sim:.3f} < ASSIGN_SIM={ASSIGN_SIM}; "
            "RECORDED with no capital authority -- an unknown event is not a dropped event")

    # ---------------------------------------------------------------- emergence ----
    def discover(self, unclassified: Sequence[tuple[str, str]]) -> list[Category]:
        """Mint categories from the unclassified pool. `unclassified` is `(id, text)`.

        Single-linkage over cosine >= EMERGE_SIM, minimum cluster size MIN_EMERGE. Single-linkage
        is chosen because the question here is "is there a coherent new THING", and a chain of
        closely-related reports IS that thing; the cost is chaining, which is bounded by the high
        similarity floor and by the fact that a minted category earns nothing until it has
        measured reactions.
        """
        items = [(i, vectorise(t), t) for i, t in unclassified]
        items = [(i, v, t) for i, v, t in items if v]
        n = len(items)
        if n < MIN_EMERGE:
            return []
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a in range(n):
            for b in range(a + 1, n):
                if cosine(items[a][1], items[b][1]) >= EMERGE_SIM:
                    ra, rb = find(a), find(b)
                    if ra != rb:
                        parent[ra] = rb
        groups: dict[int, list[int]] = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(i)
        minted: list[Category] = []
        for members in groups.values():
            if len(members) < MIN_EMERGE:
                continue
            texts = [items[m][2] for m in members]
            toks = Counter(t for text in texts for t in tokenise(text))
            # Distinguishing tokens: frequent HERE and not merely frequent everywhere. Without
            # the corpus discount every emergent label would be named after the words that are
            # common in all macro text ("market", "said", "percent").
            scored = sorted(
                toks.items(),
                key=lambda kv: -(kv[1] / (1.0 + self._corpus_df.get(kv[0], 0))))
            top = tuple(w for w, _ in scored[:8])
            label = "emergent:" + "_".join(top[:3]) if top else "emergent:unnamed"
            if label in self.categories:
                label = f"{label}_{len(self.categories)}"
            cat = Category(label=label, origin="emergent", n_instances=len(members),
                           centroid=_mean([items[m][1] for m in members]), top_tokens=top,
                           created_at=now_iso())
            self.categories[label] = cat
            minted.append(cat)
        return minted

    def report(self) -> dict[str, Any]:
        seeds_unseen = sorted(c.label for c in self.categories.values()
                              if c.origin == "seed" and c.n_instances == 0)
        return {
            "at": now_iso(),
            "n_categories": len(self.categories),
            "emergent": sorted(c.label for c in self.categories.values()
                               if c.origin == "emergent"),
            "with_instances": {c.label: c.n_instances for c in
                               sorted(self.categories.values(), key=lambda c: -c.n_instances)
                               if c.n_instances},
            # A seed nobody has ever matched is a coverage area the desk cannot currently see.
            # Named rather than quietly carried, because a named blind spot is actionable.
            "seed_areas_never_observed": seeds_unseen,
        }

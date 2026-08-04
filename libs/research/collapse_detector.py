"""GENERATOR COLLAPSE DETECTOR -- HYPOTHESIS_MAX #6 (unblocked at Gate 0 entry, 2026-07-30).

THE FAILURE MODE, and why it is invisible without this. Uncapped generation collapses: multiple
generators and seats converge on near-identical hypotheses, so measured THROUGHPUT rises while
INFORMATION throughput falls. Every dashboard the desk owns counts candidates, so collapse reads
as productivity. The desk's own record is the cautionary case -- 420 candidates, 0 survivors -- and
"420 tests" versus "one question asked 420 ways" are indistinguishable from a count.

WHY IT IS BUILT NOW AND NOT BEFORE. The spec deferred it with an explicit trigger: *"build it when
generation cadence upgrades to weekly at S1/Gate-0 entry"*, because generation was low-volume and
data-triggered, so the failure mode was unreachable. That trigger fires today.

FOUR AXES, per the spec, each measuring a different way a batch can be narrow:
  MECHANISM  entropy over fingerprints. Collapse = entropy falling while volume holds.
  FEATURE    breadth across feature families / data axes.
  MARKET     symbol and venue coverage. Cross-sectional families count the UNIVERSE they rank,
             not one name -- otherwise a 200-symbol cross-sectional signal scores as narrow as a
             single-name trade, which inverts the measure it is meant to provide.
  SEMANTIC   pairwise Jaccard over normalised mechanism tokens, plus CROSS-GENERATOR overlap --
             deterministic, no embeddings, no extra model calls, so it can run every batch.

IT NEVER BLOCKS GENERATION. The spec is explicit and it is right: this is instrumentation that
pages the process, not a gate on ideas. A diversity metric with veto power would be a second
unvalidated filter on the discovery funnel, and the desk already knows what an over-tight funnel
costs. It flags a DIVERSITY AUDIT for the weekly panel, and the audit asks the question a number
cannot: which seats collapsed, onto what, and why -- telemetry-induced herding, shared-prompt
drift, or a genuinely dominant regime, which is a legitimate reason to converge.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.mechanism_fingerprint import describe, fingerprint, jaccard, tokens

_ROOT = Path(__file__).resolve().parents[2]
HISTORY = _ROOT / "data/gen_diversity_history.jsonl"

#: A metric this far below its trailing median flags an audit. Starting value from the spec.
DROP_TRIGGER = 0.40
#: Share of near-duplicate pairs BETWEEN different generators that flags an audit.
CROSS_DUP_TRIGGER = 0.25
#: Jaccard at or above this counts a pair as near-duplicate.
NEAR_DUP_JACCARD = 0.80
#: Trailing window for the median comparison.
TRAILING_BATCHES = 8
#: Below this, a batch is too small for entropy to mean anything.
MIN_BATCH = 4


@dataclass
class BatchDiversity:
    n: int
    mechanism_entropy: float          # normalised 0..1 (1 = every idea distinct)
    feature_breadth: float            # distinct families / n, capped at 1
    market_breadth: int               # distinct symbols covered
    semantic_distinctness: float      # 1 - mean pairwise Jaccard
    cross_generator_dup_rate: float   # share of cross-generator pairs that are near-duplicates
    n_fingerprints: int
    top_fingerprints: list[tuple[str, int]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["top_fingerprints"] = [list(t) for t in self.top_fingerprints]
        return d


def _normalised_entropy(counts: list[int]) -> float:
    """Shannon entropy over fingerprint counts, normalised by log(n_items).

    NORMALISED BY ITEM COUNT, not by category count. Dividing by log(n_categories) would report a
    batch of 50 ideas sharing 2 fingerprints as PERFECTLY diverse (both categories equally used) --
    the collapse would score 1.0. Against log(n_items) that batch scores ~0.18, which is the
    reading that matches what actually happened.
    """
    total = sum(counts)
    if total <= 1:
        return 1.0
    h = -sum((c / total) * math.log(c / total) for c in counts if c > 0)
    # `+ 0.0` normalises the -0.0 that a single-category batch produces. Total collapse should
    # print as 0.0, not as a negative zero that reads like a bug in the report.
    return min(1.0, h / math.log(total)) + 0.0


def _universe_size(hyp: Any) -> set[str]:
    """The names an idea actually spans. A cross-sectional family ranks a universe, so counting
    its single `symbol` field would score the broadest ideas as the narrowest."""
    uni = getattr(hyp, "universe", None)
    if uni:
        return {str(s) for s in uni}
    params = dict(getattr(hyp, "params", {}) or {})
    if params.get("cross_sectional") or "rank" in str(getattr(hyp, "subtype", "")).lower():
        n = int(params.get("universe_size", 0) or 0)
        if n > 0:
            return {f"{getattr(hyp, 'family', 'x')}::xs::{i}" for i in range(n)}
    sym = getattr(hyp, "symbol", None)
    return {str(sym)} if sym else set()


def measure(batch: list[Any], *, generators: list[str] | None = None) -> BatchDiversity:
    """Diversity of one generation batch. `generators[i]` names the seat that produced batch[i]."""
    n = len(batch)
    if n == 0:
        return BatchDiversity(0, 1.0, 1.0, 0, 1.0, 0.0, 0)

    fps = [fingerprint(h) for h in batch]
    counts = Counter(fps)
    families = {fp.split("/")[0] for fp in fps}
    symbols: set[str] = set()
    for h in batch:
        symbols |= _universe_size(h)

    toks = [tokens(describe(h)) for h in batch]
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    sims = [jaccard(toks[i], toks[j]) for i, j in pairs]
    mean_sim = sum(sims) / len(sims) if sims else 0.0

    cross_rate = 0.0
    if generators and len(generators) == n:
        cross = [(k, (i, j)) for k, (i, j) in enumerate(pairs) if generators[i] != generators[j]]
        if cross:
            cross_rate = sum(1 for k, _ in cross if sims[k] >= NEAR_DUP_JACCARD) / len(cross)

    return BatchDiversity(
        n=n,
        mechanism_entropy=round(_normalised_entropy(list(counts.values())), 4),
        feature_breadth=round(min(1.0, len(families) / n), 4),
        market_breadth=len(symbols),
        semantic_distinctness=round(1.0 - mean_sim, 4),
        cross_generator_dup_rate=round(cross_rate, 4),
        n_fingerprints=len(counts),
        top_fingerprints=counts.most_common(5),
    )


def _history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def assess(div: BatchDiversity, *, path: Path = HISTORY) -> dict[str, Any]:
    """Compare against the trailing median and decide whether a DIVERSITY AUDIT is warranted.

    A batch below MIN_BATCH is reported UNDER-SAMPLED, never flagged: entropy over three ideas is
    noise, and a detector that cries wolf on small batches gets muted before it ever sees a real
    collapse.
    """
    prior = _history(path)[-TRAILING_BATCHES:]
    flags: list[str] = []

    if div.n < MIN_BATCH:
        return {"batch": div.as_dict(), "verdict": "UNDER-SAMPLED", "flags": [],
                "n_trailing": len(prior),
                "note": f"batch of {div.n} (<{MIN_BATCH}) -- entropy is not meaningful here"}

    if div.cross_generator_dup_rate > CROSS_DUP_TRIGGER:
        flags.append(
            f"cross-generator near-duplicate rate {div.cross_generator_dup_rate:.0%} > "
            f"{CROSS_DUP_TRIGGER:.0%}: separate seats are producing the same idea, which is "
            "herding or shared-prompt drift rather than independent search")

    for metric in ("mechanism_entropy", "feature_breadth", "semantic_distinctness"):
        hist = [float(p["batch"][metric]) for p in prior
                if p.get("batch", {}).get(metric) is not None]
        if len(hist) < 3:
            continue
        med = sorted(hist)[len(hist) // 2]
        now = float(getattr(div, metric))
        if med > 0 and now < med * (1.0 - DROP_TRIGGER):
            flags.append(f"{metric} {now:.3f} is {1 - now / med:.0%} below its trailing-"
                         f"{len(hist)} median {med:.3f}")

    return {
        "batch": div.as_dict(),
        "verdict": "DIVERSITY-AUDIT" if flags else "OK",
        "flags": flags,
        "n_trailing": len(prior),
        "note": "Instrumentation, never a gate -- generation is not blocked by this result "
                "(HYPOTHESIS_MAX #6). A flag books the question for the weekly panel: which "
                "seats collapsed, onto what, and why. Convergence in a genuinely dominant "
                "regime is a legitimate answer.",
    }


def record(div: BatchDiversity, *, path: Path = HISTORY, **meta: Any) -> dict[str, Any]:
    """Assess, append to history, return the assessment. Append-only: the trailing median is only
    meaningful if no batch is ever quietly dropped from the record."""
    out = assess(div, path=path)
    out["at"] = datetime.now(tz=UTC).isoformat()
    out.update(meta)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")
    return out

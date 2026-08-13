"""Randomise the order of a candidate list shown to an LLM, and LOG the permutation (R0457).

THE MEASURED PROBLEM. arXiv 2509.08713 ("Hidden Pitfalls of AI Scientist Systems") ran a
controlled protocol on two open-source AI-scientist systems and found selection is driven by
POSITION, not merit: **100% metric-ordering dependence** (whichever metric was listed first got
used, Tables 7-8) and Agent Laboratory picking the first four listed benchmarks 82.4% of the time.
Ordering bias is one of the best-replicated LLM phenomena there is, and this desk presents fixed-
order menus to LLMs and then TALLIES THE ANSWERS AS EVIDENCE.

WHY THE LOG IS THE POINT, AND NOT THE SHUFFLE. The desk already had one shuffle --
`run_external_panel.py:538`, added by GAP #72(4) with the correct diagnosis in its own comment
("the CRO reads top-down, so the desk was imposing a position bias on ITSELF"). It is unseeded and
writes nothing, so the permutation is unrecoverable and the desk STILL cannot answer "how
order-sensitive are we?". A shuffle without a log converts a measurable bias into an unmeasurable
one; it de-biases the estimate and destroys the residual. Every call here records the permutation
and the seed, so ordering sensitivity becomes a cheap reanalysis of logged runs rather than a
20-call experiment nobody schedules (L1.28a: unmeasured counts as zero).

WHAT THIS IS NOT FOR. An ORDINAL menu carries meaning in its order -- `EVIDENCE_CLASSES` runs
weakest-to-strongest, prior conversation turns run oldest-to-newest -- and shuffling it destroys
information rather than bias. Use this only where the listed items are PEERS and the model is
being asked to choose among them. Where a ranking is a real prior (risk-class-first review
payloads), shuffle WITHIN a tier, never across.
"""
from __future__ import annotations

import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent.parent
LOG = _ROOT / "data/list_order_log.jsonl"

T = TypeVar("T")


def shuffled_with_log(
    items: Sequence[T], *, organ: str, field: str, seed: int | None = None,
) -> tuple[list[T], list[int]]:
    """Return (reordered items, permutation) and append the permutation to the log.

    `permutation[i]` is the ORIGINAL index of the item now at position `i`, so a later reanalysis
    can map any answer back to the position it was shown in without re-deriving anything.

    `seed` is recorded whether supplied or drawn, which is what makes a run reproducible. Drawing
    from `os.urandom` rather than a clock means two organs starting in the same second cannot share
    a permutation -- correlated "randomisation" across seats would look like agreement and would be
    the bias wearing a fix's clothes.

    A ONE-ITEM LIST IS STILL LOGGED. It carries no bias, but dropping it would make the log's
    denominator the count of lists that happened to be long enough, and a denominator that quietly
    sheds members is the defect L1.60 exists for -- "this list was short" and "this call site never
    ran" must not be byte-identical to a reader.
    """
    if seed is None:
        seed = int.from_bytes(os.urandom(8), "big")
    n = len(items)
    perm = np.random.default_rng(seed).permutation(n).tolist() if n > 1 else list(range(n))

    # Append-only, one line, flushed. NOT wrapped in a try/except: the shuffle has already happened
    # by the time this runs, so swallowing a write failure would leave the desk holding a permuted
    # list it can never map back -- strictly worse than the fixed order it replaced, and invisible.
    # A failure here is a real defect and is allowed to say so (L1.41: no silent swallow).
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(), "organ": organ, "field": field,
            "n": n, "seed": seed, "permutation": perm,
        }, sort_keys=True) + "\n")

    return [items[i] for i in perm], perm

"""ONE CONTENT-ADDRESSED IDENTITY FROM RAW DATA TO P&L -- the hashes, the chain, the join classes.

Item 1 of the principal's 2026-09-29 list: *"one immutable research identity raw data -> live
trade ... survives candidate -> gate -> certificate -> clock -> sleeve -> allocator -> order ->
fill -> P&L. No fuzzy joins / sleeve-name matching / recomputed identities. Content-addressed chain
raw_data_hash -> transformation_hash -> hypothesis_hash -> experiment_hash -> certificate_hash ->
allocation_hash -> order_hash -> fill_hash; any trade reconstructable years later."*

WHAT ALREADY EXISTS UPSTREAM, AND IS NOT REBUILT HERE. `libs/research/artifact_chain.py` hash-links
source -> claim -> hypothesis -> code -> data -> config -> result -> review; `research/
evidence_chain.py` Merkle-roots every certificate (spec, seeds, verdicts, gate policy, costs,
evidence counts); `research/sleeve_registry.identity` mints the forward clock's `sleeve_id` over
family/symbol/params/code_hash/cost_hash/venue; `libs/data/input_identity.py` digests every bar
file the gauntlet reads. Each of those is content-addressed. What NOTHING addressed was the half of
the chain that carries money: certificate -> clock -> sleeve -> allocation -> order -> fill -> P&L.
Those links were joined by NAMES -- and names on this desk are truncated, lower-cased, rebuilt from
parts or overwritten by the broker (the measured break table is in `research/identity_chain.py`).

THIS MODULE IS PURE. It hashes, chains and classifies; it reads no file and knows no path, so the
arithmetic of an identity can be tested exactly and is the same on both boxes.

    node_hash(kind, payload)  sha256("<kind>|" + canonical JSON). The payload is the node's own
                              content, so two nodes with one hash ARE the same object.
    chain(nodes)              link_i = sha256(link_{i-1} + node_hash_i) along CHAIN_KINDS. The
                              head therefore commits to every node before it, and a trade whose
                              chain head matches a recorded one is the SAME trade of the SAME
                              strategy on the SAME data, not merely one with the same name.
    JOIN CLASSES              how a link between two nodes was established. Only EXACT (a key
                              carried on both sides, compared byte for byte) and CONTENT (a
                              content hash computed on both sides and equal) are clean. FUZZY is
                              any normalisation -- a prefix, a lower-casing, a coarse composite
                              key several objects share. BROKEN is no link. UNMEASURED is a side
                              whose artifact was not there to read; it is never counted clean.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

#: The chain's order, raw data first and money last. A node may be absent (None) -- the chain then
#: breaks there and `head` is None, because a head that skipped a node would commit to a trade
#: whose ancestry it cannot name.
CHAIN_KINDS: tuple[str, ...] = (
    "raw_data", "transformation", "hypothesis", "experiment", "certificate", "clock",
    "sleeve", "allocation", "order", "fill", "pnl",
)

EXACT, CONTENT, FUZZY, BROKEN, UNMEASURED = "EXACT", "CONTENT", "FUZZY", "BROKEN", "UNMEASURED"
JOIN_CLASSES: tuple[str, ...] = (EXACT, CONTENT, FUZZY, BROKEN, UNMEASURED)
CLEAN: frozenset[str] = frozenset({EXACT, CONTENT})

GENESIS = "0" * 64
#: The identity tag a venue order could carry (MT5's comment holds ~31 characters): the chain
#: head's first 12 hex digits, 48 bits -- collision-free at any trade count this desk will reach.
TAG_LEN = 12


def canonical(obj: Any) -> str:
    """Sorted-key, separator-tight JSON: the one spelling every hash in this module is over."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def node_hash(kind: str, payload: Any) -> str:
    """The content address of one node. The kind is inside the hash, so a fill and an order with
    byte-identical payloads are still two different objects."""
    if kind not in CHAIN_KINDS:
        raise ValueError(f"unknown chain kind {kind!r}; expected one of {CHAIN_KINDS}")
    return sha256(f"{kind}|{canonical(payload)}")


def spec_hash(spec: Mapping[str, Any]) -> str:
    """The HYPOTHESIS identity: what the strategy IS, independent of where it is recorded.

    Symbol, family, selector and the params dict -- the four fields the certificate's
    `shadow_spec` and the forward clock's `identity` BOTH carry. Side/direction is deliberately
    NOT here: the canon records it inconsistently (null on families that emit both sides) and
    the clock always records one, so including it would make every both-sided family's
    certificate un-joinable to its own clock. The clock's direction stays on the clock node.
    Params are canonicalised (sorted keys; lists kept as lists) so key order never matters.
    """
    params = spec.get("params")
    params = dict(params) if isinstance(params, Mapping) else {}
    body = {"symbol": str(spec.get("symbol") or ""), "family": str(spec.get("family") or ""),
            "selector": str(spec.get("selector") or ""),
            "params": {str(k): params[k] for k in sorted(params, key=str)}}
    return sha256("hypothesis|" + canonical(body))


def chain(nodes: Mapping[str, Any]) -> dict[str, Any]:
    """Hash-link the nodes in CHAIN_KINDS order. A missing node stops the chain.

    Returns each node's hash, each link hash up to the first gap, `complete`, `broken_at` and
    `head` (None unless complete). Pure; the same nodes give the same head on any machine.
    """
    rows: list[dict[str, Any]] = []
    prev = GENESIS
    broken_at: str | None = None
    for kind in CHAIN_KINDS:
        payload = nodes.get(kind)
        if payload is None:
            rows.append({"kind": kind, "hash": None, "link": None})
            if broken_at is None:
                broken_at = kind
            continue
        h = node_hash(kind, payload)
        link: str | None = None
        if broken_at is None:
            prev = sha256(prev + h)
            link = prev
        rows.append({"kind": kind, "hash": h, "link": link})
    complete = broken_at is None
    return {"nodes": rows, "complete": complete, "broken_at": broken_at,
            "head": prev if complete else None}


def tag(head: str | None) -> str | None:
    """The short identity a venue order would carry for this chain head, or None."""
    return head[:TAG_LEN] if head else None


def verify_chain(recorded: Mapping[str, Any], nodes: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute a recorded chain from its payloads: which node, if any, no longer hashes."""
    fresh = chain(nodes)
    moved = [a["kind"] for a, b in zip(recorded.get("nodes") or [], fresh["nodes"], strict=False)
             if a.get("hash") != b.get("hash")]
    return {"intact": not moved and recorded.get("head") == fresh["head"], "moved": moved,
            "head_recorded": recorded.get("head"), "head_recomputed": fresh["head"]}


def classify(joins: Mapping[str, Mapping[str, Any]], required: Sequence[str]) -> dict[str, Any]:
    """End-to-end verdict for one trade from its per-link join classes.

    CLEAN only when every REQUIRED link is EXACT or CONTENT. Otherwise the weakest class wins,
    in the order BROKEN > UNMEASURED > FUZZY: a chain with a broken link is not "fuzzy", and an
    unread artifact is not "clean".
    """
    classes = {k: str((joins.get(k) or {}).get("class") or UNMEASURED) for k in required}
    if all(c in CLEAN for c in classes.values()):
        verdict = "CLEAN"
    elif any(c == BROKEN for c in classes.values()):
        verdict = BROKEN
    elif any(c == UNMEASURED for c in classes.values()):
        verdict = UNMEASURED
    else:
        verdict = FUZZY
    return {"verdict": verdict, "classes": classes,
            "weak_links": sorted(k for k, c in classes.items() if c not in CLEAN)}

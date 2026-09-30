"""THE TRUTH KERNEL (Tier S layers 1, 12, 46): content-addressed lineage from raw data to fill,
an append-only hash-chained journal, a sealed constitution no agent can weaken, and the evidence
seal that proves no historical ledger was rewritten.

WHAT `libs/research/artifact_chain.py` ALREADY DOES, AND WHERE IT STOPS. It hash-links source ->
claim -> hypothesis -> code -> data -> config -> result -> review. It stops at the certificate:
nothing links a review to the allocation that sized the sleeve, the order the gateway sent, or the
fill the broker returned. So a trade could not be rebuilt from hashes. This kernel is the
continuation: its nodes are content-addressed (id = sha256 of kind, canonical payload and sorted
parent ids), so the same fact always has the same id, and its parents may point at an
artifact_chain `artifact_id` -- the two chains join rather than duplicate.

    raw_data -> transformation -> hypothesis -> experiment -> certificate -> allocation -> order
             -> fill

`reconstruct(fill_id)` walks every ancestor and returns the whole record: what data existed,
which hypothesis, which program, which tests, which posterior, why that size, why that order.

THE CONSTITUTION. A small set of numeric rules (PIT, trial accounting, cost, lockbox,
certification, capital authority, provenance, reproducibility) each with a DIRECTION that counts as
stricter. The sealed version lives in a file; any change is a PROPOSAL. A proposal that loosens any
rule is WEAKENING and can only become law by a principal ratification record; nothing in the code
path can ratify. Agents propose; the principal ratifies; neither can rewrite the evidence (the seal
below). That is the separation of powers (layer 46).

THE EVIDENCE SEAL. For each protected ledger the kernel stores (size, sha256 of the whole file).
On the next pass a ledger whose first `size` bytes no longer hash to the stored value was
REWRITTEN -- appends are fine, edits are not. The seal is itself journaled.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

KINDS: tuple[str, ...] = ("raw_data", "transformation", "hypothesis", "experiment",
                          "certificate", "allocation", "order", "fill")
_RANK = {k: i for i, k in enumerate(KINDS)}
GENESIS = "0" * 64


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str)


def sha256(text: str | bytes) -> str:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()


def node_id(kind: str, payload: Mapping[str, Any], parents: Sequence[str]) -> str:
    return sha256(canon({"kind": kind, "payload": payload, "parents": sorted(parents)}))


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    payload: dict[str, Any]
    parents: tuple[str, ...]
    at: str
    chain: str

    def as_row(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "payload": self.payload,
                "parents": list(self.parents), "at": self.at, "chain": self.chain}


class KernelError(RuntimeError):
    pass


@dataclass
class Journal:
    """Append-only, hash-chained, content-addressed. One JSON line per node."""

    path: Path
    _index: dict[str, Node] = field(default_factory=dict)
    _tail: str = GENESIS
    _loaded: bool = False

    def load(self) -> Journal:
        self._index.clear()
        self._tail = GENESIS
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    n = Node(row["id"], row["kind"], row["payload"], tuple(row["parents"]),
                             row["at"], row["chain"])
                    self._index[n.id] = n
                    self._tail = n.chain
        self._loaded = True
        return self

    def _ensure(self) -> None:
        if not self._loaded:
            self.load()

    def __contains__(self, nid: object) -> bool:
        self._ensure()
        return nid in self._index

    def get(self, nid: str) -> Node | None:
        self._ensure()
        return self._index.get(nid)

    def nodes(self) -> list[Node]:
        self._ensure()
        return list(self._index.values())

    def put(self, kind: str, payload: Mapping[str, Any], parents: Sequence[str] = (),
            *, at: str | None = None, external_parents: bool = False) -> Node:
        """Add a node (idempotent: the same kind/payload/parents returns the existing node).

        Parents must already be in the journal unless `external_parents` (an artifact_chain id);
        a parent of a LATER kind than the child is refused -- an order cannot be a hypothesis's
        ancestor."""
        self._ensure()
        if kind not in _RANK:
            raise KernelError(f"unknown kind {kind!r}")
        nid = node_id(kind, payload, parents)
        existing = self._index.get(nid)
        if existing is not None:
            return existing
        for p in parents:
            pn = self._index.get(p)
            if pn is None:
                if not external_parents:
                    raise KernelError(f"parent {p[:12]} not in journal")
                continue
            if _RANK[pn.kind] > _RANK[kind]:
                raise KernelError(f"{pn.kind} cannot be an ancestor of {kind}")
        stamp = at or datetime.now(UTC).isoformat()
        chain = sha256(self._tail + nid)
        node = Node(nid, kind, dict(payload), tuple(parents), stamp, chain)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(canon(node.as_row()) + "\n")
        self._index[nid] = node
        self._tail = chain
        return node

    def verify(self) -> dict[str, Any]:
        """Recompute every id and the chain; name the first break."""
        tail = GENESIS
        n = 0
        if not self.path.exists():
            return {"ok": True, "n": 0}
        with self.path.open("r", encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if not line.strip():
                    continue
                row = json.loads(line)
                want = node_id(row["kind"], row["payload"], row["parents"])
                if want != row["id"]:
                    return {"ok": False, "n": n, "break_at": i, "why": "payload edited"}
                if sha256(tail + row["id"]) != row["chain"]:
                    return {"ok": False, "n": n, "break_at": i,
                            "why": "chain broken (insert/delete/reorder)"}
                tail = row["chain"]
                n += 1
        return {"ok": True, "n": n, "tail": tail}

    def reconstruct(self, nid: str) -> dict[str, Any]:
        """Every ancestor of `nid`, grouped by kind, plus the ids the journal cannot resolve."""
        self._ensure()
        seen: dict[str, Node] = {}
        missing: list[str] = []
        stack = [nid]
        while stack:
            cur = stack.pop()
            if cur in seen or cur in missing:
                continue
            node = self._index.get(cur)
            if node is None:
                missing.append(cur)
                continue
            seen[cur] = node
            stack.extend(node.parents)
        by_kind: dict[str, list[dict[str, Any]]] = {k: [] for k in KINDS}
        for node in seen.values():
            by_kind[node.kind].append({"id": node.id, "payload": node.payload, "at": node.at})
        present = [k for k in KINDS if by_kind[k]]
        return {"root": nid, "kinds_present": present,
                "complete": all(by_kind[k] for k in KINDS[:_RANK[seen[nid].kind] + 1])
                if nid in seen else False,
                "unresolved_parents": missing, "by_kind": by_kind}

    def coverage(self) -> dict[str, Any]:
        """For every fill: how much of its ancestry the journal holds."""
        self._ensure()
        fills = [n for n in self._index.values() if n.kind == "fill"]
        full = 0
        depth: dict[str, int] = {}
        for f in fills:
            r = self.reconstruct(f.id)
            k = len(r["kinds_present"])
            depth[str(k)] = depth.get(str(k), 0) + 1
            if r["complete"]:
                full += 1
        return {"fills": len(fills), "fully_reconstructible": full,
                "share": (full / len(fills)) if fills else None, "depth_histogram": depth,
                "nodes": len(self._index)}


# ------------------------------------------------------------------------------------------------
# The constitution
# ------------------------------------------------------------------------------------------------

#: rule -> (default value, direction that is STRICTER: "up" means a larger number is stricter)
DEFAULT_CONSTITUTION: dict[str, tuple[float, str]] = {
    "pit.max_lookahead_bars": (0.0, "down"),
    "pit.require_knowledge_time": (1.0, "up"),
    "trials.lifetime_accounting": (1.0, "up"),
    "trials.min_counted_per_family": (1.0, "up"),
    "costs.fail_closed": (1.0, "up"),
    "costs.stress_multiplier": (3.0, "up"),
    "lockbox.min_fraction": (0.2, "up"),
    "lockbox.single_use": (1.0, "up"),
    "cert.gates_required": (10.0, "up"),
    "cert.dsr_threshold": (0.95, "up"),
    "capital.allocator_zero_means_no_order": (1.0, "up"),
    "capital.certificate_required": (1.0, "up"),
    "provenance.content_addressed": (1.0, "up"),
    "reproducibility.seeded": (1.0, "up"),
    "immune.min_trap_rejection": (0.9, "up"),
}


def constitution_doc(rules: Mapping[str, tuple[float, str]] | None = None) -> dict[str, Any]:
    rules = rules or DEFAULT_CONSTITUTION
    body = {k: {"value": v, "stricter": d} for k, (v, d) in sorted(rules.items())}
    return {"rules": body, "hash": sha256(canon(body))}


def classify_amendment(sealed: Mapping[str, Any], proposed: Mapping[str, Any]
                       ) -> dict[str, Any]:
    """Compare a proposed rule set with the sealed one: which rules tighten, loosen, vanish."""
    s_rules: Mapping[str, Any] = sealed.get("rules") or {}
    p_rules: Mapping[str, Any] = proposed.get("rules") or {}
    tighten, loosen, removed, added = [], [], [], []
    for k, spec in s_rules.items():
        if k not in p_rules:
            removed.append(k)
            continue
        old, new = float(spec["value"]), float(p_rules[k]["value"])
        if p_rules[k].get("stricter", spec["stricter"]) != spec["stricter"]:
            loosen.append(k)
            continue
        up = spec["stricter"] == "up"
        if new == old:
            continue
        if (new > old) == up:
            tighten.append(k)
        else:
            loosen.append(k)
    for k in p_rules:
        if k not in s_rules:
            added.append(k)
    weakening = bool(loosen or removed)
    return {"tighten": tighten, "loosen": loosen, "removed": removed, "added": added,
            "weakening": weakening}


def constitution_status(sealed: Mapping[str, Any], live: Mapping[str, Any],
                        ratifications: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Is the rule set in force the sealed one, or a principal-ratified successor?

    A live rule set that differs from the seal is LAWFUL only if a ratification record names its
    exact hash. A tightening needs no ratification (agents may always make the desk stricter);
    a loosening without one is a VIOLATION."""
    live_hash = sha256(canon(live.get("rules") or {}))
    sealed_hash = sha256(canon(sealed.get("rules") or {}))
    if live_hash == sealed_hash:
        return {"status": "SEALED", "hash": live_hash}
    diff = classify_amendment(sealed, live)
    ratified = {str(r.get("hash")) for r in ratifications
                if str(r.get("by", "")).startswith("principal")}
    if live_hash in ratified:
        return {"status": "RATIFIED", "hash": live_hash, "diff": diff}
    if not diff["weakening"]:
        return {"status": "TIGHTENED", "hash": live_hash, "diff": diff}
    return {"status": "VIOLATION", "hash": live_hash, "diff": diff,
            "why": "rules loosened without a principal ratification of this exact hash"}


#: where the live rule set and the principal's ratifications live, relative to the repo root
CONSTITUTION_REL = ("docs", "research", "tier_s_constitution.json")
RATIFICATIONS_REL = ("docs", "research", "tier_s_ratifications.jsonl")


def in_force(live: Mapping[str, Any] | None,
             ratifications: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """The rule set IN FORCE, as {rule: value}, with the status that put it there.

      no live file            SEALED_DEFAULT -- DEFAULT_CONSTITUTION binds
      SEALED / RATIFIED       the live file's values (RATIFIED may loosen: the principal said so)
      TIGHTENED               the live file's values (stricter needs no ratification)
      VIOLATION               the SEALED values: a loosening nobody ratified has no force

    A validator reads its thresholds from here (S01) through `binding_value`."""
    sealed = constitution_doc()
    default = {k: float(v) for k, (v, _d) in DEFAULT_CONSTITUTION.items()}
    if live is None:
        return {"status": "SEALED_DEFAULT", "hash": sealed["hash"], "rules": default}
    rules = live.get("rules")
    if not isinstance(rules, Mapping):
        raise ValueError("the live constitution carries no rules object")
    st = constitution_status(sealed, live, ratifications)
    if st["status"] == "VIOLATION":
        return {**st, "rules": default,
                "why": f"{st.get('why')}: the loosening has no force, the sealed rules bind"}
    return {**st, "rules": {str(k): float(spec["value"]) for k, spec in rules.items()}}


def read_in_force(root: Path) -> dict[str, Any]:
    """`in_force` over the repository's own files. RAISES when a present file is unreadable, so
    a caller can fall back to its own constants rather than to a guess."""
    live_p = root.joinpath(*CONSTITUTION_REL)
    rat_p = root.joinpath(*RATIFICATIONS_REL)
    live = json.loads(live_p.read_text("utf-8")) if live_p.exists() else None
    if live is not None and not isinstance(live, Mapping):
        raise ValueError(f"{live_p.name} is not an object")
    ratifs: list[Mapping[str, Any]] = []
    if rat_p.exists():
        for line in rat_p.read_text("utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, Mapping):
                    raise ValueError(f"{rat_p.name} holds a non-object row")
                ratifs.append(row)
    return in_force(live, ratifs)


def binding_value(rule: str, constant: float, law: Mapping[str, Any] | None
                  ) -> tuple[float, str]:
    """The threshold a validator APPLIES for `rule`: the law in force, never looser than the
    validator's own `constant` unless the principal RATIFIED the rule set that says so.

    `law` None (the constitution could not be read), a rule the law does not carry, or a value
    that is not a finite number: the validator's constant stands, exactly as before."""
    import math
    if law is None or rule not in DEFAULT_CONSTITUTION:
        return float(constant), "constant (constitution unread)"
    try:
        v = float((law.get("rules") or {})[rule])
    except (KeyError, TypeError, ValueError):
        return float(constant), f"constant ({rule} not in the law in force)"
    if not math.isfinite(v):
        return float(constant), f"constant ({rule} is not a finite number)"
    status = str(law.get("status") or "")
    if status == "RATIFIED":
        return v, f"{rule}={v} (principal-ratified rule set)"
    up = DEFAULT_CONSTITUTION[rule][1] == "up"
    bound = max(v, float(constant)) if up else min(v, float(constant))
    src = "law" if bound == v else "validator constant (stricter than the law)"
    return bound, f"{rule}={bound} ({src}; law {status})"


def gauntlet_thresholds(root: Path, *, dsr_threshold: float, gates_required: float,
                        lockbox_min_fraction: float) -> dict[str, Any]:
    """The three constitution rules the external gauntlet binds (S01), resolved ONCE per sweep.

    Each argument is the gauntlet's own current constant, which stands whenever the law cannot
    be read (status UNREADABLE) and which the law may only TIGHTEN unless the principal ratified
    the rule set in force. The result is published beside the sweep so a verdict names the law
    it was judged under."""
    law: dict[str, Any] | None
    try:
        read = read_in_force(root)
        law, status, law_hash = read, str(read["status"]), read.get("hash")
        law_why = str(read.get("why") or "")
    except Exception as exc:  # unreadable: the gauntlet's constants stand
        law, status, law_hash = None, "UNREADABLE", None
        law_why = f"{type(exc).__name__}: {exc}"
    out: dict[str, Any] = {"status": status, "hash": law_hash, "why": {}}
    if law_why:
        out["law_why"] = law_why
    for key, rule, const in (("dsr_threshold", "cert.dsr_threshold", dsr_threshold),
                             ("gates_required", "cert.gates_required", gates_required),
                             ("lockbox_min_fraction", "lockbox.min_fraction",
                              lockbox_min_fraction)):
        out[key], out["why"][key] = binding_value(rule, const, law)
    return out


# ------------------------------------------------------------------------------------------------
# The evidence seal (append-only proof for historical ledgers)
# ------------------------------------------------------------------------------------------------

def _prefix_hash(path: Path, size: int) -> str | None:
    try:
        h = hashlib.sha256()
        remaining = size
        with path.open("rb") as fh:
            while remaining > 0:
                chunk = fh.read(min(1 << 20, remaining))
                if not chunk:
                    return None
                h.update(chunk)
                remaining -= len(chunk)
        return h.hexdigest()
    except OSError:
        return None


def seal_ledgers(paths: Iterable[Path], previous: Mapping[str, Any] | None, root: Path
                 ) -> dict[str, Any]:
    """Check every ledger against its previous seal, then re-seal at its current size.

    A ledger whose sealed prefix changed is REWRITTEN (tampering). One that SHRANK was rotated or
    truncated. One missing now but sealed before is VANISHED. Appends are fine."""
    prev: Mapping[str, Any] = (previous or {}).get("ledgers") or {}
    out: dict[str, Any] = {}
    violations: list[dict[str, Any]] = []
    for p in paths:
        rel = os.path.relpath(p, root).replace("\\", "/")
        before = prev.get(rel)
        if not p.exists():
            if before:
                violations.append({"ledger": rel, "kind": "VANISHED"})
                out[rel] = before
            continue
        size = p.stat().st_size
        if before:
            old_size = int(before.get("size", 0))
            if size < old_size:
                # Log rotation (kept by the principal 2026-09-29) truncates legitimately, so a
                # shrink is reported as its own kind; an in-place EDIT of the sealed prefix is
                # the unambiguous tampering signal.
                violations.append({"ledger": rel, "kind": "SHRANK",
                                   "why": f"shrank {old_size} -> {size} bytes (rotation or "
                                          f"truncation)"})
            elif _prefix_hash(p, old_size) != before.get("sha256"):
                violations.append({"ledger": rel, "kind": "REWRITTEN",
                                   "why": f"first {old_size} bytes changed"})
        out[rel] = {"size": size, "sha256": _prefix_hash(p, size)}
    return {"ledgers": out, "violations": violations, "n": len(out),
            "at": datetime.now(UTC).isoformat()}

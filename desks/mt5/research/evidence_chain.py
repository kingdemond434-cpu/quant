"""THE EVIDENCE CHAIN -- one Merkle manifest per certificate, in an append-only hash chain.

THE GAP THE LEDGER NAMED (Tier-1 B19): *"content-addressed blobs and payload hashes exist; no
hash chain over certificates, seeds and verdicts."* `libs/data/pit.py` content-addresses the
PAYLOADS a collector fetched, which proves a file was not edited after it landed. It says nothing
about the object the desk actually risks money on: a certificate is a SPEC, a set of SEEDS and ten
GATE VERDICTS, assembled from artifacts at a moment in time, and nothing in this tree could tell
you whether the certificate you are reading today is the one that was judged.

WHAT IS HASHED, AND WHY EACH LEAF IS THERE.

    spec       symbol, family, params, side, timeframe, selector -- the identity the gauntlet,
               the forward clock and the gateway all key on. A changed spec under an unchanged
               certificate id is the failure this leaf exists to expose.
    seeds      every seed the record carries. A result that cannot name its seed cannot be
               replayed, and a seed that changed silently makes two different experiments look
               like one.
    verdicts   the ten gate verdicts and the gate policy version. The policy version is a leaf
               of its own: the same verdict under a different policy is a different claim.
    costs      the frozen cost model. The desk has already lost twelve clocks to a cost field
               changing underneath a certificate (2026-09-02); a leaf makes that visible in one
               comparison rather than twelve.
    days / n   the evidence counts the certificate asserts.

THE CHAIN. Each pass appends one row per certificate whose manifest root has MOVED, and each row
carries the hash of the row before it: `entry = sha256(prev_entry || canonical(row))`. So the
history cannot be rewritten without rewriting every row after it, and `verify()` recomputes the
whole chain from genesis every pass. The head hash is published, which is the number another
machine can compare against without reading the file.

DIVERGENCE IS THE POINT, not tamper. Tamper is rare and the chain proves it; what actually happens
on a desk is that the EVIDENCE BEHIND a certificate moves -- a gate re-run, a cost corrected, a
param normalised -- and nobody notices which certificates are no longer the ones that were judged.
`divergences` names exactly those, with the leaf that moved.

NO GATE, NO REFUSAL. This organ reads the canon, hashes it and writes its own files. It imports
none of the four sealed files, retires nothing, and a divergence is published rather than acted
on: what a divergence means for capital is the promoter's judgement, and the promoter is sealed.

    python desks/mt5/research/evidence_chain.py --once --budget-s 120
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CERTS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
CHAIN = DESK / "data" / "evidence_chain.jsonl"
OUT = DESK / "reports" / "EVIDENCE_CHAIN.json"
GENESIS = "0" * 64


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _leaf(name: str, obj: Any) -> dict[str, str]:
    return {"leaf": name, "hash": _sha(f"{name}|{_canonical(obj)}")}


def _merkle(leaves: list[dict[str, str]]) -> str:
    """A binary Merkle root over the leaf hashes; an odd node is paired with itself."""
    level = [x["hash"] for x in leaves]
    if not level:
        return GENESIS
    while len(level) > 1:
        nxt: list[str] = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(_sha(a + b))
        level = nxt
    return level[0]


def _seeds(rec: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if "seed" in str(k).lower() and not isinstance(v, (dict, list)):
                    out[f"{path}{k}"] = v
                else:
                    walk(v, f"{path}{k}.")
        elif isinstance(node, list):
            for i, v in enumerate(node[:50]):
                walk(v, f"{path}{i}.")

    walk(rec, "")
    return out


def manifest(cert_id: str, rec: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """The Merkle manifest for one certificate: leaves, their hashes, and the root."""
    spec = rec.get("shadow_spec") or {}
    gates = rec.get("gates") or {}
    verdicts = {k: bool((v or {}).get("passed")) if isinstance(v, dict) else v
                for k, v in gates.items()} if isinstance(gates, dict) else {}
    leaves = [
        _leaf("spec", {k: spec.get(k) for k in
                       ("symbol", "family", "params", "side", "timeframe", "selector")}
              if spec else {k: rec.get(k) for k in ("sym", "cell", "hunt")}),
        _leaf("seeds", _seeds(rec)),
        _leaf("verdicts", verdicts),
        _leaf("gate_policy", {k: policy.get(k) for k in
                              ("version", "gates", "trials_multiplier", "trial_count_basis")}),
        _leaf("costs", rec.get("costs") or rec.get("cost_model") or {}),
        _leaf("evidence_counts", {k: rec.get(k) for k in ("days", "n", "trades", "oos_n")}),
    ]
    return {"cert_id": cert_id, "leaves": leaves, "merkle_root": _merkle(leaves),
            "n_leaves": len(leaves)}


def _certificates() -> tuple[dict[str, dict[str, Any]], dict[str, Any], str]:
    for path in (CERTS, CANON):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows = doc.get("survivors") if isinstance(doc, dict) else None
        if isinstance(rows, dict) and rows:
            return ({str(k): v for k, v in rows.items() if isinstance(v, dict)},
                    doc.get("gate_policy") or {}, str(path))
    return {}, {}, "no readable certificate canon"


def read_chain(path: Path = CHAIN) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            rows.append({"corrupt": line[:120]})
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def entry_hash(prev: str, row: dict[str, Any]) -> str:
    body = {k: v for k, v in row.items() if k != "entry_hash"}
    return _sha(prev + _canonical(body))


def verify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Recompute the whole chain from genesis. A break names the first row that does not hold."""
    prev = GENESIS
    broken: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        if row.get("corrupt"):
            broken.append({"seq": i, "why": "unparseable line"})
            break
        want = entry_hash(prev, row)
        if str(row.get("prev_hash")) != prev:
            broken.append({"seq": i, "why": "prev_hash does not match the row before it",
                           "expected": prev, "found": row.get("prev_hash")})
            break
        if str(row.get("entry_hash")) != want:
            broken.append({"seq": i, "why": "entry hash does not match the row's own content",
                           "expected": want, "found": row.get("entry_hash")})
            break
        prev = str(row.get("entry_hash"))
    return {"verdict": "INTACT" if not broken else "BROKEN", "head": prev,
            "n_rows": len(rows), "breaks": broken}


def chain_status(path: Path = CHAIN) -> dict[str, Any]:
    """THE CONSUMER'S DOOR. `quantbench` case QB007 replays this every hour, so a chain that
    stops verifying is a REGRESSED case in the corpus the suite must beat, not a silent file."""
    return verify(read_chain(path))


def build(budget_s: float = 120.0, chain_path: Path = CHAIN) -> dict[str, Any]:
    t0 = time.monotonic()
    certs, policy, source = _certificates()
    rows = read_chain(chain_path)
    before = verify(rows)
    last_root: dict[str, str] = {}
    for row in rows:
        if row.get("cert_id"):
            last_root[str(row["cert_id"])] = str(row.get("merkle_root"))
    appended: list[dict[str, Any]] = []
    divergences: list[dict[str, Any]] = []
    prev = before["head"] if before["verdict"] == "INTACT" else None
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    if prev is not None:
        with_lines: list[str] = []
        for cid, rec in certs.items():
            if time.monotonic() - t0 > budget_s:
                break
            m = manifest(cid, rec, policy)
            was = last_root.get(cid)
            if was == m["merkle_root"]:
                continue
            if was is not None:
                prior = next((r for r in reversed(rows) if str(r.get("cert_id")) == cid), {})
                moved = [x["leaf"] for x in m["leaves"]
                         if x["hash"] not in {y.get("hash") for y in (prior.get("leaves") or [])}]
                divergences.append({"cert_id": cid, "was": was, "now": m["merkle_root"],
                                    "leaves_moved": moved})
            row = {"seq": len(rows) + len(appended), "at": now, "cert_id": cid,
                   "merkle_root": m["merkle_root"], "leaves": m["leaves"],
                   "source": source, "prev_hash": prev,
                   "kind": ("UPDATE" if was is not None else "FIRST_SEEN")}
            row["entry_hash"] = entry_hash(prev, row)
            prev = row["entry_hash"]
            appended.append(row)
            with_lines.append(json.dumps(row, separators=(",", ":"), default=str))
        if with_lines:
            chain_path.parent.mkdir(parents=True, exist_ok=True)
            with chain_path.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(with_lines) + "\n")
    after = verify(read_chain(chain_path))
    return {
        "at": now,
        "status": ("OK" if after["verdict"] == "INTACT" and certs else
                   ("BROKEN" if after["verdict"] == "BROKEN" else "UNMEASURED")),
        "source": source, "n_certificates": len(certs),
        "n_appended": len(appended), "n_divergent": len(divergences),
        "divergences": divergences[:40],
        "chain": {"path": str(chain_path), "n_rows": after["n_rows"], "head": after["head"],
                  "verdict": after["verdict"], "breaks": after["breaks"]},
        "leaves": ["spec", "seeds", "verdicts", "gate_policy", "costs", "evidence_counts"],
        "rule": ("entry = sha256(prev_entry || canonical(row)); a row is appended only when a "
                 "certificate's Merkle root MOVES, so the chain is the history of what the "
                 "evidence said, not a per-pass copy of it"),
        "consumers": [
            "desks/mt5/research/quantbench.py case QB007 -> chain_status(): a chain that stops "
            "verifying is a REGRESSED case the suite fails on",
            "reports/EVIDENCE_CHAIN.json head hash -> the one number another machine can compare "
            "without reading the chain",
        ],
        "boundary": (
            "PUBLISHED, NEVER ACTED ON. A divergence does not retire a certificate, void a clock "
            "or move capital -- what it means is the promoter's judgement and the promoter is "
            "sealed. No gate, no threshold, no refusal."),
        "seconds": round(time.monotonic() - t0, 3),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--chain", type=Path, default=CHAIN)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, chain_path=a.chain)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"evidence chain: could not write {OUT}: {exc}")
        return 1
    c = doc["chain"]
    print(f"evidence chain: {doc['n_certificates']} certificate(s) manifested, "
          f"{doc['n_appended']} row(s) appended, {doc['n_divergent']} divergence(s); "
          f"chain {c['verdict']} at {c['n_rows']} rows, head {str(c['head'])[:16]}")
    for d in doc["divergences"][:8]:
        print(f"   MOVED {d['cert_id'][:52]:<52} leaves={','.join(d['leaves_moved']) or '-'}")
    for b in c["breaks"]:
        print(f"   BREAK seq={b.get('seq')} {b.get('why')}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

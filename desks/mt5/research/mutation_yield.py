"""Which mutations pay: the certify rate per operator, per source, per generator, from the ledger.

    P(certify | operator)  ~  Beta(1 + certified, 1 + failed)        one posterior per operator
    weight(operator)       =  posterior mean / pooled mean, clipped to [0.25, 4.0]

`survivor_distiller` names every cell it steps with the operator that produced it and the
certificate it stepped from; `alpha_evolution`, the deepening worker and the compilers name
theirs. The hypothesis graph then records what became of each. This module JOINS the two --
a lineage row to its verdict, by node id -- and reports, per operator and per source, how many
were tried, how many certified, how deep the parent chains run and how long a verdict took. The
weights it writes are a BIAS on which parameter the distiller perturbs first; they change no
screen, no gate and no trial count. A weight of 4.0 means "step this one first", not "step this
one past the bar".

WHY THE GRAPH IS NOT ENOUGH ON ITS OWN. `record_candidates` persists a candidate's symbol, family,
params, source and a parent HASH -- not its evidence. The operator and the parent certificate ride
in the discovery contract (`data/intelligence/<source>/discoveries_*.json`, written by
`proposer_common.donate`), so those files are read too and joined to the graph on
`node_id(symbol, family, params)`. Where nothing carries an operator yet, the weights file is
still written, with the reason, so the distiller's reader finds a file that says "uniform" rather
than an absence it cannot distinguish from a crash.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

SOURCE = "mutation_yield"
REPORT = _DESK / "reports" / "MUTATION_YIELD.json"
GRAPH = _DESK / "data" / "hypothesis_graph.jsonl"
CANON = _DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
INTEL = _DESK / "data" / "intelligence"
OPERATOR_WEIGHTS = _DESK / "data" / "mutation_operator_weights.json"
GENERATOR_WEIGHTS = _DESK / "data" / "generator_weights.json"
#: Sources whose rows are mutations or descendants of something, rather than fresh proposals.
LINEAGE_SOURCES: tuple[str, ...] = ("survivor_distiller", "mutation", "deepening",
                                    "alpha_evolution", "weak_signal_compiler", "coevolution")
GENERATORS: tuple[str, ...] = ("random", "gflow", "symreg")
CLIP = (0.25, 4.0)
VERDICTS = ("CERTIFIED", "FAILED", "BURIED")


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _src(source: Any) -> str:
    return str(source or "").removeprefix("miner:").split(":")[0]


def _at(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# ------------------------------------------------------------------------------------------
# Lineage rows: from the graph and from the discovery contract
# ------------------------------------------------------------------------------------------

def _graph_rows(inputs: dict[str, str]) -> list[dict[str, Any]]:
    try:
        from libs.research.hypothesis_graph import Graph
        rows = Graph(GRAPH).rows()
    except Exception as exc:
        inputs["hypothesis_graph"] = f"unreadable: {type(exc).__name__}: {exc}"
        return []
    inputs["hypothesis_graph"] = f"{len(rows)} rows" if rows else f"no rows at {GRAPH}"
    return rows


def _lineage_from_graph(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        params = r.get("params") if isinstance(r.get("params"), dict) else {}
        gates = r.get("gates") if isinstance(r.get("gates"), dict) else {}
        op = params.get("operator") or gates.get("operator")
        gen = params.get("generator") or gates.get("generator")
        if _src(r.get("source")) not in LINEAGE_SOURCES and not (op or gen):
            continue
        nid = str(r["id"])
        row = out.setdefault(nid, {"id": nid, "symbol": r.get("symbol"), "family": r.get("family"),
                                   "params": params, "source": _src(r.get("source")),
                                   "operator": None, "parent": None, "generator": None,
                                   "born_at": None})
        row["operator"] = row["operator"] or (str(op) if op else None)
        row["generator"] = row["generator"] or (str(gen) if gen else None)
        if row["born_at"] is None and r.get("fate") == "BORN":
            row["born_at"] = r.get("at")
    return out


def _lineage_from_discoveries(inputs: dict[str, str]) -> dict[str, dict[str, Any]]:
    from libs.research.hypothesis_graph import node_id

    out: dict[str, dict[str, Any]] = {}
    n_files = 0
    if not INTEL.exists():
        inputs["discoveries"] = f"no intelligence dir at {INTEL}"
        return out
    for src_dir in sorted(p for p in INTEL.iterdir() if p.is_dir()):
        for path in sorted(src_dir.glob("discoveries_*.json")):
            doc = _json(path)
            discs = doc.get("discoveries")
            if not isinstance(discs, list):
                continue
            n_files += 1
            for c in discs:
                if not isinstance(c, dict) or not isinstance(c.get("params"), dict):
                    continue
                ev = c.get("evidence") if isinstance(c.get("evidence"), dict) else {}
                op = ev.get("operator") or c["params"].get("operator")
                parent = ev.get("parent")
                gen = ev.get("generator") or c["params"].get("generator")
                src = _src(c.get("source") or doc.get("source") or src_dir.name)
                if src not in LINEAGE_SOURCES and not (op or parent or gen):
                    continue
                nid = node_id(str(c.get("symbol")), str(c.get("family")), dict(c["params"]))
                row = out.setdefault(nid, {
                    "id": nid, "symbol": c.get("symbol"), "family": c.get("family"),
                    "params": dict(c["params"]), "source": src, "operator": None,
                    "parent": None, "generator": None,
                    "born_at": c.get("available_time") or doc.get("generated_at")})
                row["operator"] = row["operator"] or (str(op) if op else None)
                row["parent"] = row["parent"] or (str(parent) if parent else None)
                row["generator"] = row["generator"] or (str(gen) if gen else None)
    inputs["discoveries"] = f"{n_files} discovery files, {len(out)} lineage rows"
    return out


def lineage_rows(graph_rows: list[dict[str, Any]],
                 inputs: dict[str, str]) -> dict[str, dict[str, Any]]:
    """One row per node id, discovery-contract fields filling what the graph did not keep."""
    rows = _lineage_from_graph(graph_rows)
    for nid, d in _lineage_from_discoveries(inputs).items():
        g = rows.get(nid)
        if g is None:
            rows[nid] = d
            continue
        for k in ("operator", "parent", "generator", "born_at"):
            g[k] = g[k] or d[k]
    return rows


# ------------------------------------------------------------------------------------------
# Verdicts and depth
# ------------------------------------------------------------------------------------------

def verdicts(graph_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per node: the CURRENT fate, and when the FIRST verdict landed (time-to-verdict's end)."""
    out: dict[str, dict[str, Any]] = {}
    for r in graph_rows:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        nid = str(r["id"])
        v = out.setdefault(nid, {"fate": None, "first_verdict_at": None, "born_at": None})
        v["fate"] = r.get("fate")
        if r.get("fate") == "BORN" and v["born_at"] is None:
            v["born_at"] = r.get("at")
        if r.get("fate") in VERDICTS and v["first_verdict_at"] is None:
            v["first_verdict_at"] = r.get("at")
    return out


def _parent_index(canon: dict[str, Any]) -> dict[str, str]:
    """Certificate key -> node id, so a parent named by canon key resolves to a graph node."""
    from libs.research.hypothesis_graph import node_id

    out: dict[str, str] = {}
    for key, cert in (canon.get("survivors") or {}).items():
        if not isinstance(cert, dict):
            continue
        spec = cert.get("shadow_spec") or {}
        params = spec.get("params")
        sym = str(cert.get("sym") or spec.get("symbol") or "").upper()
        fam = str(spec.get("family") or "")
        if sym and fam and isinstance(params, dict):
            out[str(key)] = node_id(sym, fam, params)
    return out


def depth_of(rows: dict[str, dict[str, Any]], cert_index: dict[str, str]) -> dict[str, int]:
    """Generations between a row and its root survivor: 1 for a child of a certificate, 2 for
    a child of a child. A parent that is not itself a lineage row is the root."""
    def resolve(parent: str | None) -> str | None:
        if not parent:
            return None
        if parent.startswith("graph:"):
            return parent[6:]
        return cert_index.get(parent, parent)

    out: dict[str, int] = {}
    for nid in rows:
        depth, cur, seen = 1, nid, {nid}
        while True:
            pid = resolve(rows[cur].get("parent"))
            if pid is None or pid not in rows or pid in seen:
                break
            seen.add(pid)
            depth += 1
            cur = pid
        out[nid] = depth
    return out


# ------------------------------------------------------------------------------------------
# The tallies
# ------------------------------------------------------------------------------------------

def _posterior(cert: int, failed: int) -> dict[str, float]:
    a, b = 1.0 + cert, 1.0 + failed
    return {"alpha": a, "beta": b, "mean": round(a / (a + b), 4)}


def tally(rows: dict[str, dict[str, Any]], verd: dict[str, dict[str, Any]],
          depth: dict[str, int], by: str) -> dict[str, dict[str, Any]]:
    """Per value of `by` (operator / source / generator): trials, fates, posterior, depth,
    time-to-verdict. A row without that field is not in this tally."""
    groups: dict[str, list[str]] = {}
    for nid, r in rows.items():
        key = r.get(by)
        if key:
            groups.setdefault(str(key), []).append(nid)
    out: dict[str, dict[str, Any]] = {}
    for key, ids in sorted(groups.items()):
        fates = Counter(str((verd.get(i) or {}).get("fate") or "PENDING") for i in ids)
        cert = fates.get("CERTIFIED", 0)
        failed = fates.get("FAILED", 0) + fates.get("BURIED", 0)
        hours: list[float] = []
        for i in ids:
            v = verd.get(i) or {}
            born = _at(v.get("born_at") or rows[i].get("born_at"))
            done = _at(v.get("first_verdict_at"))
            if born and done and done >= born:
                hours.append((done - born).total_seconds() / 3600.0)
        depths = [depth.get(i, 1) for i in ids]
        out[key] = {"trials": len(ids), "certified": cert, "failed": failed,
                    "pending": len(ids) - cert - failed, "posterior": _posterior(cert, failed),
                    "depth": {"max": max(depths), "mean": round(statistics.mean(depths), 3),
                              "hist": dict(sorted(Counter(depths).items()))},
                    "time_to_verdict_h": ({"n": len(hours),
                                           "median": round(statistics.median(hours), 2),
                                           "max": round(max(hours), 2)} if hours
                                          else {"n": 0, "median": None, "max": None})}
    return out


def weights_from(groups: dict[str, dict[str, Any]],
                 always: tuple[str, ...] = ()) -> tuple[dict[str, float], float | None, str]:
    """posterior mean / pooled mean per group, clipped. Groups never seen get 1.0."""
    cert = sum(g["certified"] for g in groups.values())
    failed = sum(g["failed"] for g in groups.values())
    judged = cert + failed
    out: dict[str, float] = dict.fromkeys(always, 1.0)
    if judged == 0:
        why = ("no judged rows carry this field: every weight at 1.0"
               if not groups else f"{len(groups)} groups seen but none judged yet: 1.0 each")
        out.update(dict.fromkeys(groups, 1.0))
        return out, None, why
    pooled = _posterior(cert, failed)["mean"]
    for key, g in groups.items():
        w = float(g["posterior"]["mean"]) / pooled
        out[key] = round(min(CLIP[1], max(CLIP[0], w)), 4)
    return out, pooled, f"{len(groups)} groups, {judged} judged, pooled mean {pooled}"


def run(write: bool = True) -> dict[str, Any]:
    inputs: dict[str, str] = {}
    graph_rows = _graph_rows(inputs)
    rows = lineage_rows(graph_rows, inputs)
    verd = verdicts(graph_rows)
    depth = depth_of(rows, _parent_index(_json(CANON)))
    by_operator = tally(rows, verd, depth, "operator")
    by_source = tally(rows, verd, depth, "source")
    by_generator = tally(rows, verd, depth, "generator")
    op_w, op_pooled, op_why = weights_from(by_operator)
    gen_w, gen_pooled, gen_why = weights_from(by_generator, always=GENERATORS)
    now = datetime.now(tz=UTC).isoformat()
    rep: dict[str, Any] = {
        "generated_at": now, "inputs": inputs, "n_lineage_rows": len(rows),
        "n_with_operator": sum(1 for r in rows.values() if r.get("operator")),
        "n_with_generator": sum(1 for r in rows.values() if r.get("generator")),
        "by_operator": by_operator, "by_source": by_source, "by_generator": by_generator,
        "operator_weights": {"weights": op_w, "pooled_mean": op_pooled, "reason": op_why},
        "generator_weights": {"weights": gen_w, "pooled_mean": gen_pooled, "reason": gen_why},
        "clip": list(CLIP)}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
        OPERATOR_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
        OPERATOR_WEIGHTS.write_text(json.dumps(
            {**op_w, "_generated_at": now, "_reason": op_why, "_pooled_mean": op_pooled,
             "_clip": list(CLIP)}, indent=1), "utf-8")
        GENERATOR_WEIGHTS.write_text(json.dumps(
            {**gen_w, "_generated_at": now, "_reason": gen_why, "_pooled_mean": gen_pooled,
             "_clip": list(CLIP)}, indent=1), "utf-8")
    return rep


def main() -> int:
    argparse.ArgumentParser().parse_args()
    r = run()
    print(f"MUTATION YIELD  {r['n_lineage_rows']} lineage rows, "
          f"{r['n_with_operator']} with an operator; {r['operator_weights']['reason']}")
    for op, g in r["by_operator"].items():
        print(f"  {op:28s} trials={g['trials']:4d} cert={g['certified']:3d} "
              f"fail={g['failed']:4d} p={g['posterior']['mean']:.3f} "
              f"depth<={g['depth']['max']} w={r['operator_weights']['weights'].get(op)}")
    for src, g in r["by_source"].items():
        print(f"  source {src:21s} trials={g['trials']:4d} cert={g['certified']:3d} "
              f"fail={g['failed']:4d} p={g['posterior']['mean']:.3f}")
    gw = r["generator_weights"]
    print(f"  generators: {gw['weights']}  ({gw['reason']})")
    print(f"written: {REPORT}, {OPERATOR_WEIGHTS}, {GENERATOR_WEIGHTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

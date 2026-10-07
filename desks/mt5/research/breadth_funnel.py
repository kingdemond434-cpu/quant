"""THE END-TO-END BREADTH FUNNEL, PER CANDIDATE (breadth law, BREADTH-0267..0273).

Breadth credit is provisional when a row is generated and realised only when the book carries an
independent stream. Between the two sit seven stages, and a candidate's credit is only as real as
the last stage it measurably reached:

    generated                      the row is in the docket (external_survivors.json)
    structurally_novel             its persisted `breadth_order.dup` is 0 (not a near-duplicate)
    evaluator_admitted             the judge wrote a verdict for its cell (gate_verdict_ledger)
    survives                       that verdict passed
    forward_enrolled               a forward clock runs it (shadow_state, symbol x session)
    prospective_independence       the forward map reads its sleeve INDEPENDENT of another
                                   (CERTIFICATE_SATURATION.forward_independence)
    promoted_live                  data/sleeves.json carries a LIVE row on its symbol x family

Each stage is MEASURED from its own artifact or UNMEASURED with the reason: a stage whose input
is absent on this host counts nothing and says so -- absence is never a zero (L1.28a), and a later
stage is never credited without the earlier one. Published per stage, per producer, and per
candidate (the most advanced first, capped), hourly from the breadth leg.

Facts only. Nothing here changes an order, a gate, a trial, capital, sizing or promotion.
"""
from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
VERDICTS = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
SHADOW = DESK / "reports" / "shadow" / "shadow_state.json"
SLEEVES = DESK / "data" / "sleeves.json"
SATURATION = DESK / "reports" / "CERTIFICATE_SATURATION.json"
OUT = DESK / "reports" / "BREADTH_FUNNEL.json"
UNMEASURED, MEASURED = "UNMEASURED", "MEASURED"
STAGES = ("generated", "structurally_novel", "evaluator_admitted", "survives",
          "forward_enrolled", "prospective_independence", "promoted_live")
#: The verdict ledger is the box's largest file; its tail is what the window can speak for.
VERDICT_TAIL_BYTES = 64 * 1024 * 1024
MAX_CANDIDATES_PUBLISHED = 2000
FAILURE_EXAMPLES = 8


def _cs() -> Any:
    try:
        from research import certificate_saturation as cs
    except ImportError:                                                  # pragma: no cover
        import certificate_saturation as cs  # type: ignore[import-not-found,no-redef]
    return cs


def _cell_id(spec: Mapping[str, Any]) -> str:
    try:
        from research.frontier_identity import cell_id
    except ImportError:                                                  # pragma: no cover
        from frontier_identity import cell_id  # type: ignore[import-not-found,no-redef]
    return str(cell_id(dict(spec)))


def _params(row: Mapping[str, Any]) -> dict[str, Any]:
    p = row.get("params")
    if isinstance(p, str):
        try:
            p = ast.literal_eval(p)
        except (ValueError, SyntaxError):
            p = None
    return dict(p) if isinstance(p, Mapping) else {}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def verdicts(path: Path | None = None) -> dict[str, Any] | None:
    """{cell: {"passed": ever, "gate": the last failing terminal gate}} from the ledger's tail;
    None when the ledger is absent."""
    p = path or VERDICTS
    try:
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > VERDICT_TAIL_BYTES:
                fh.seek(size - VERDICT_TAIL_BYTES)
                fh.readline()
            raw = fh.read()
    except OSError:
        return None
    out: dict[str, Any] = {}
    for ln in raw.decode("utf-8", errors="replace").splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("cell"):
            v = out.setdefault(str(r["cell"]), {"passed": False, "gate": None})
            if r.get("passed") is True:
                v["passed"] = True
            else:
                v["gate"] = str(r.get("terminal_gate") or "UNKNOWN")
    return out


def _verdict(vm: Mapping[str, Any], cell: str) -> dict[str, Any] | None:
    v = vm.get(cell)
    if v is None:
        return None
    if isinstance(v, Mapping):
        return {"passed": bool(v.get("passed")), "gate": v.get("gate")}
    return {"passed": bool(v), "gate": None if v else "UNKNOWN"}


def _session(row: Mapping[str, Any], params: Mapping[str, Any]) -> str:
    return str(params.get("session") or row.get("selector") or row.get("session") or "").lower()


#: What every generator -- new machinery above all -- must DEMONSTRATE (BREADTH-0606..0609),
#: each read from its own funnel stage: novel outputs, evaluation, conversion (a
#: survivor), independent survivors.
DEMONSTRATIONS = (("novel_outputs", "structurally_novel"), ("evaluation", "evaluator_admitted"),
                  ("conversion", "survives"),
                  ("independent_survivor", "prospective_independence"))


def demonstrations(by_producer: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """{producer: {property: DEMONSTRATED | NOT_DEMONSTRATED | UNMEASURED, ...}}. A stage whose
    input is absent is UNMEASURED, never NOT_DEMONSTRATED (L1.28a). Published, never enforced
    here: what a generator may run is decided elsewhere."""
    out: dict[str, Any] = {}
    for prod, st in by_producer.items():
        rec: dict[str, Any] = {}
        for name, stage in DEMONSTRATIONS:
            n = st.get(stage)
            rec[name] = (UNMEASURED if n is None else
                         "DEMONSTRATED" if n > 0 else "NOT_DEMONSTRATED")
            rec[f"{name}_n"] = n
        rec["all_demonstrated"] = all(rec[n] == "DEMONSTRATED" for n, _ in DEMONSTRATIONS)
        out[prod] = rec
    return out


def build(*, docket: Any = None, verdict_map: Mapping[str, Any] | str | None = "read",
          shadow: Any = None, sleeves: Any = None, saturation: Any = None,
          now: datetime | None = None) -> dict[str, Any]:
    t = now or datetime.now(tz=UTC)
    rows = docket if docket is not None else _read_json(DOCKET)
    if not isinstance(rows, list):
        return {"status": UNMEASURED, "at": t.isoformat(timespec="seconds"),
                "why": "docket absent or unreadable", "stages": dict.fromkeys(STAGES)}
    vm: Mapping[str, Any] | None = (verdicts() if verdict_map == "read" else
                                    verdict_map if isinstance(verdict_map, Mapping) else None)
    sh = shadow if shadow is not None else _read_json(SHADOW)
    sl = sleeves if sleeves is not None else _read_json(SLEEVES)
    sat = saturation if saturation is not None else _read_json(SATURATION)
    why: dict[str, str] = {}
    if vm is None:
        why["evaluator_admitted"] = why["survives"] = "gate_verdict_ledger.jsonl absent"
    enrolled: set[tuple[str, str]] | None = None
    if isinstance(sh, Mapping):
        enrolled = set()
        for k in sh:
            sym, _, sess = str(k).partition(".")
            enrolled.add((sym.upper(), sess.lower()))
    else:
        why["forward_enrolled"] = "shadow_state.json absent"
    live: set[tuple[str, str]] | None = None
    srows = sl.get("sleeves") if isinstance(sl, Mapping) else sl
    if isinstance(srows, list):
        live = {(str(r.get("symbol") or "").upper(), str(r.get("family") or ""))
                for r in srows if isinstance(r, Mapping)
                and str(r.get("status") or "").upper() == "LIVE"}
    else:
        why["promoted_live"] = "data/sleeves.json absent"
    independent: set[tuple[str, str]] | None = None
    fi = (sat or {}).get("forward_independence") if isinstance(sat, Mapping) else None
    if isinstance(fi, Mapping) and fi.get("status") == MEASURED:
        independent = set()
        cs = _cs()
        for p in fi.get("pairs") or []:
            if isinstance(p, Mapping) and p.get("state") == "INDEPENDENT":
                for lab in (p.get("a"), p.get("b")):
                    s, f, _ = cs.sleeve_identity(str(lab))
                    independent.add((s, f))
    else:
        why["prospective_independence"] = "forward independence map unmeasured"
    if vm is None:
        # every later stage requires a passed verdict: with the verdicts unmeasured, so are they
        for s in ("forward_enrolled", "prospective_independence", "promoted_live"):
            why.setdefault(s, "requires `survives`, which is unmeasured on this host")
        enrolled = independent = live = None
    counts: Counter[str] = Counter()
    failures: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_producer: dict[str, Counter[str]] = defaultdict(Counter)
    novel_measured = 0
    cands: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        params = _params(r)
        sym = str(r.get("symbol") or r.get("sym") or "").upper()
        fam = str(r.get("family") or "")
        try:
            cell = _cell_id({"sym": sym, "family": fam, "params": params})
        except Exception:
            cell = f"{sym}.{fam}"
        st: dict[str, bool | None] = {"generated": True}
        bo = r.get("breadth_order")
        if isinstance(bo, Mapping) and "dup" in bo:
            novel_measured += 1
            st["structurally_novel"] = not bo.get("dup")
        ver = None if vm is None else _verdict(vm, cell)
        st["evaluator_admitted"] = None if vm is None else ver is not None
        st["survives"] = None if vm is None else bool(ver and ver["passed"])
        sess = _session(r, params)
        st["forward_enrolled"] = (None if enrolled is None
                                  else bool(st["survives"]) and (sym, sess) in enrolled)
        st["prospective_independence"] = (None if independent is None
                                          else bool(st["forward_enrolled"])
                                          and (sym, fam) in independent)
        st["promoted_live"] = (None if live is None
                               else bool(st["survives"]) and (sym, fam) in live)
        producer = str(r.get("producer") or r.get("source") or "unknown")
        if ver is not None and not ver["passed"]:
            # WHICH FAILED AND WHY (BREADTH-0364/0365): the judge's terminal gate, per producer
            gate = str(ver.get("gate") or "UNKNOWN")
            failures[producer][gate] += 1
            if len(examples[producer]) < FAILURE_EXAMPLES:
                examples[producer].append({"cell": cell, "terminal_gate": gate})
        reached = [s for s in STAGES if st.get(s) is True]
        for s in reached:
            counts[s] += 1
            by_producer[producer][s] += 1
        cands.append({"cell": cell, "producer": producer, "first_seen": r.get("first_seen"),
                      "stage": reached[-1] if reached else None,
                      "depth": len(reached), "stages": st})
    if not novel_measured:
        why["structurally_novel"] = "no docket row carries a persisted breadth_order"
    stages = {s: (counts.get(s, 0) if s not in why else None) for s in STAGES}
    cands.sort(key=lambda c: (-c["depth"], str(c["first_seen"] or "")))
    conv = {}
    for a, b in pairwise(STAGES):
        na, nb = stages.get(a), stages.get(b)
        conv[f"{a}->{b}"] = (round(nb / na, 6) if isinstance(na, int) and isinstance(nb, int)
                             and na > 0 else None)
    bp = {p: {s: (c.get(s, 0) if s not in why else None) for s in STAGES}
          for p, c in sorted(by_producer.items())}
    return {"status": MEASURED, "at": t.isoformat(timespec="seconds"),
            "n_candidates": len(cands), "stages": stages, "unmeasured": why,
            "generator_demonstrations": demonstrations(bp),
            "conversion": conv,
            "by_producer": bp,
            "failures_by_producer": {
                p: {"by_terminal_gate": dict(c.most_common()), "examples": examples[p],
                    "note": ("UNKNOWN is the judge's unmeasured path (too few observations), "
                             "not a rejection")}
                for p, c in sorted(failures.items())},
            "candidates": cands[:MAX_CANDIDATES_PUBLISHED],
            "rule": ("a stage is credited only when its own artifact shows it and every earlier "
                     "stage held; a stage whose input is absent reads None (UNMEASURED), never 0")}


def publish(doc: Mapping[str, Any], path: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(p)
    return p


def main() -> int:
    doc = build()
    p = publish(doc)
    print(f"breadth_funnel: {doc.get('stages')} -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""PAPERCLIP INTAKE: the box end of the narrow donation gateway, one hourly leg, three jobs.

    1. EXPORT the lab's inbox   desks/mt5/data/paperclip/inbox.json -- sanitised material the
                                isolated runner may read: dead/starved producers, stranded
                                datasets, a sample of UNJUDGED cell specs, rejected cells with
                                the gate that stopped them, rule-less corpus rows. Specs and
                                gate names only: no returns, no lockbox, no ledger of money.
    2. INGEST the lab's bundles  every successful `paperclip-lab.yml` run not yet ingested is
                                downloaded with the box's own gh, and EVERY row is re-screened
                                here with the real catalogues (`libs/research/paperclip_lab/
                                contract.py`) -- the runner's screen is never trusted. Survivors:
                                  recipe/hypothesis -> data/intelligence/paperclip/
                                                       discoveries_*.json (the seat door; the
                                                       compiler and the sealed gauntlet take it
                                                       from there)
                                  revival           -> desks/mt5/data/paperclip/
                                                       revival_proposals.jsonl (for the producer's
                                                       owner; never applied here)
                                  triage            -> desks/mt5/data/paperclip/triage_priors.jsonl
                                                       (ADVISORY: nothing reads it as an order until
                                                       the scorecard measures its precision)
    3. SCORE the company       desks/mt5/data/paperclip/scorecard.json -- per role: calls,
                                accepted, compiled, judged, passed; unique survivors per call;
                                the same ratios for the LLM seats it competes with; triage AUC
                                against later verdicts; and the HEALTH of the loop (age of the
                                newest bundle). A loop that stopped is RED and the leg fails.

    python desks/mt5/research/paperclip_intake.py --once
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (ROOT, BASE, BASE / "research"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from libs.research.paperclip_lab import contract, lab  # noqa: E402

PC = BASE / "data" / "paperclip"
INBOX = PC / "inbox.json"
SEEN = PC / "donated_keys.txt"
INGESTED = PC / "ingested_runs.json"
REVIVALS = PC / "revival_proposals.jsonl"
TRIAGE = PC / "triage_priors.jsonl"
DONATED = PC / "donated_cells.jsonl"
SCORECARD = PC / "scorecard.json"
SEAT_DIR = ROOT / "data" / "intelligence" / "paperclip"
HYP = BASE / "data" / "hypotheses"
REPO = os.environ.get("PAPERCLIP_REPO", "kingdemond434-cpu/quant")
WORKFLOW = "paperclip-lab.yml"
ARTIFACT = "paperclip-bundle"
STALE_H = 3.0
#: The seats the company competes with, as `source` on compiled candidates.
RIVALS = ("deepseek", "kimi_k3_deep_forest")


def now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


def _append_jsonl(p: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")


def _tail_jsonl(p: Path, n: int, max_bytes: int = 8_000_000) -> list[dict[str, Any]]:
    try:
        with p.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-n:]:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


# ------------------------------------------------------------------------------ 1. inbox
def export_inbox(limit: int = 400) -> dict[str, Any]:
    reports = BASE / "reports"
    py = _read_json(reports / "PRODUCER_YIELD.json") or {}
    producers = [{"producer": p.get("producer"), "verdict": p.get("verdict"),
                  "why": p.get("why"), "rows_in_window": p.get("rows_in_window"),
                  "replacement": p.get("replacement")}
                 for p in py.get("producers") or [] if p.get("verdict") in ("DEAD", "STARVED")]
    datasets: list[dict[str, Any]] = []
    for path in (reports / "DATA_UTILIZATION_AUDIT.json", ROOT / "reports" /
                 "DATA_UTILIZATION_AUDIT.json"):
        d = _read_json(path)
        rows = (d or {}).get("datasets") if isinstance(d, dict) else None
        if isinstance(rows, dict):
            rows = [dict(v, dataset=k) for k, v in rows.items() if isinstance(v, dict)]
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            state = json.dumps(r, default=str)
            if '"NO"' in state or "STRAND" in state.upper():
                datasets.append({k: r.get(k) for k in ("dataset", "name", "source", "defects",
                                                       "downstream_state") if r.get(k)})
        if datasets:
            break
    queue: list[dict[str, Any]] = []
    try:
        import queue_store
        for r in queue_store.pending(limit):
            spec = r.get("spec") if isinstance(r.get("spec"), dict) else r
            queue.append({"cell": r.get("cell") or r.get("id"),
                          "sym": spec.get("sym") or spec.get("symbol"),
                          "family": spec.get("family"), "params": spec.get("params"),
                          "mechanism": str(spec.get("mechanism") or "")[:300]})
    except Exception as exc:
        queue = []
        queue_err = f"{type(exc).__name__}: {exc}"[:200]
    else:
        queue_err = None
    graveyard = []
    for r in _tail_jsonl(HYP / "gate_verdict_ledger.jsonl", 4000):
        if r.get("passed") is True or str(r.get("terminal_gate") or "") in ("", "UNKNOWN"):
            continue
        graveyard.append({"cell": r.get("cell"), "family": r.get("family"),
                          "sym": r.get("sym"), "failed_gate": r.get("terminal_gate")})
    graveyard = graveyard[-limit:]
    corpus = []
    dq = _read_json(HYP / "miner_deepening_queue.json")
    rows = ((dq.get("tasks") or dq.get("rows") or []) if isinstance(dq, dict)
            else (dq if isinstance(dq, list) else []))
    for r in rows[:limit] if isinstance(rows, list) else []:
        if isinstance(r, dict):
            corpus.append({k: str(r.get(k))[:400] for k in (
                "source", "title", "text", "summary", "disposition", "url") if r.get(k)})
    doc = {"schema": "paperclip_inbox/1", "generated_at": _iso(now()),
           "producers": producers, "datasets": datasets, "queue": [q for q in queue if
                                                                    q.get("cell")],
           "graveyard": graveyard, "corpus": corpus,
           "unmeasured": {k: v for k, v in {"queue": queue_err}.items() if v}}
    _write_json(INBOX, doc)
    return {k: len(v) for k, v in doc.items() if isinstance(v, list)}


# ------------------------------------------------------------------------------ 2. ingest
def _gh() -> str | None:
    for c in (os.environ.get("QUANT_GH"), shutil.which("gh"),
              r"C:\Users\Administrator\tools\gh\bin\gh.exe"):
        if c and Path(c).exists():
            return c
    return shutil.which("gh")


def fetch_bundles(done: set[str]) -> tuple[list[tuple[str, dict[str, Any]]], str | None]:
    gh = _gh()
    if not gh:
        return [], "gh not found"
    try:
        out = subprocess.run([gh, "run", "list", "-R", REPO, "--workflow", WORKFLOW,
                              "--status", "success", "--limit", "24", "--json",
                              "databaseId,createdAt"], capture_output=True, text=True,
                             timeout=90, check=False)
        runs = json.loads(out.stdout or "[]") if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return [], f"gh run list: {type(exc).__name__}"
    if runs is None:
        return [], f"gh run list rc={out.returncode}: {out.stderr.strip()[:160]}"
    bundles: list[tuple[str, dict[str, Any]]] = []
    for run in sorted(runs, key=lambda r: str(r.get("createdAt"))):
        rid = str(run.get("databaseId"))
        if rid in done:
            continue
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run([gh, "run", "download", rid, "-R", REPO, "-n", ARTIFACT,
                                "-D", td], capture_output=True, text=True, timeout=120,
                               check=False)
            doc = _read_json(Path(td) / "paperclip_bundle.json") if r.returncode == 0 else None
        if isinstance(doc, dict) and doc.get("schema") == "paperclip_bundle/1":
            bundles.append((rid, doc))
        else:
            done.add(rid)  # an expired or malformed artifact is skipped once, not forever
    return bundles, None


def _box_catalogues() -> tuple[dict[str, list[str]], list[str], set[str]]:
    fams = lab.family_catalog(ROOT)
    try:
        from miner_candidate_compiler import _registered_family
        fams = {f: p for f, p in fams.items() if _registered_family(f)} or fams
    except Exception:
        pass
    try:
        from family_policy import family_banned
        fams = {f: p for f, p in fams.items() if not family_banned(f)}
    except Exception:
        pass
    uni = lab.universe(ROOT)
    syms = sorted(s for s, c in uni.items() if c in lab.HYPOTHESIS_CLASSES)
    py = _read_json(BASE / "reports" / "PRODUCER_YIELD.json") or {}
    prods = {str(p.get("producer")) for p in py.get("producers") or [] if p.get("producer")}
    return fams, syms, prods


def _seat_row(r: dict[str, Any], generated: str) -> dict[str, Any]:
    """The miner-discovery contract, as `deepseek_cycle._donate` writes it."""
    row = {"source": "paperclip", "kind": r["kind"] if r["kind"] == "hypothesis" else "recipe",
           "title": f"{r['family']} on {','.join(r['symbols'])}: {r['testable_claim'][:120]}",
           "symbols": r["symbols"], "family": r["family"], "mechanism": r["mechanism"],
           "testable_claim": r["testable_claim"], "falsifier": r.get("falsifier"),
           "mechanism_tags": [r["family"]], "origin": r.get("origin"),
           "origin_ref": r.get("origin_ref"), "inputs": r.get("inputs") or [],
           "paperclip_role": r.get("role"), "paperclip_model": r.get("model"),
           "dedup_key": r["dedup_key"],
           "url": f"paperclip://{r.get('role')}/{r['dedup_key']}"}
    if r["kind"] == "recipe":
        row["params"] = dict(r["params"])
        if r.get("timeframe"):
            row["params"].setdefault("timeframe", r["timeframe"])
    if r.get("parent_cell"):
        row["lineage"] = {"root": r["parent_cell"], "operator": "paperclip_descendant"}
    return row


def ingest(bundles: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    fams, syms, prods = _box_catalogues()
    try:
        seen = set(SEEN.read_text("utf-8").split())
    except OSError:
        seen = set()
    generated = _iso(now())
    seat, revivals, triage, keys = [], [], [], []
    stats: dict[str, dict[str, int]] = {}
    refused: dict[str, int] = {}
    for rid, b in bundles:
        for role, c in ((b.get("spend") or {}).get("calls_by_role") or {}).items():
            st = stats.setdefault(role, {})
            st["calls"] = st.get("calls", 0) + int(c)
        for row in b.get("rows") or []:
            if not isinstance(row, dict):
                continue
            role = str(row.get("role") or "?")
            payload = {k: v for k, v in row.items() if k in contract.ALLOWED_KEYS}
            v = contract.screen(payload, families=fams, universe=syms, producers=prods,
                                seen=seen)
            if not v.ok or v.row is None:
                cls = (v.reasons[0].split(":")[0].split(" ")[0] if v.reasons else "?").lower()
                refused[cls] = refused.get(cls, 0) + 1
                continue
            r = dict(v.row, dedup_key=v.key, role=role, model=row.get("model"), run_id=rid)
            keys.append(v.key)
            st = stats.setdefault(role, {})
            st["accepted"] = st.get("accepted", 0) + 1
            if r["kind"] in ("recipe", "hypothesis"):
                seat.append(_seat_row(r, generated))
            elif r["kind"] == "revival":
                revivals.append(dict(r, at=generated, status="PROPOSED_TO_OWNER"))
            else:
                triage.append(dict(r, at=generated))
    path = None
    if seat:
        from libs.data.pit import stamp_or_refuse
        from libs.research.source_provenance import stamp_row
        stamped, pit_refused = stamp_or_refuse(
            [stamp_row(s, ground=f"paperclip:{s['paperclip_role']}", retrieved_at=generated)
             for s in seat], "paperclip")
        refused["pit"] = refused.get("pit", 0) + len(pit_refused)
        if stamped:
            SEAT_DIR.mkdir(parents=True, exist_ok=True)
            path = SEAT_DIR / f"discoveries_{generated.replace(':', '').replace('-', '')[:15]}.json"
            path.write_text(json.dumps({"source": "paperclip", "generated_at": generated,
                                        "discoveries": stamped}, indent=1, default=str),
                            encoding="utf-8")
            _append_jsonl(DONATED, [{"at": generated, "role": s["paperclip_role"],
                                     "dedup_key": s["dedup_key"], "family": s["family"],
                                     "symbols": s["symbols"], "params": s.get("params"),
                                     "kind": s["kind"]} for s in stamped])
    _append_jsonl(REVIVALS, revivals)
    _append_jsonl(TRIAGE, triage)
    if keys:
        with SEEN.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(keys) + "\n")
    return {"bundles": len(bundles), "seat_rows": len(seat), "revivals": len(revivals),
            "triage": len(triage), "refused": refused, "calls": stats,
            "donated_to": str(path) if path else None}


# ------------------------------------------------------------------------------ 3. score
def _cell_ids(rows: list[dict[str, Any]]) -> dict[str, str]:
    """cell id -> role, for every donated cell whose identity the box can compute."""
    try:
        from frontier_identity import cell_id
    except Exception:
        return {}
    out: dict[str, str] = {}
    for r in rows:
        for s in r.get("symbols") or []:
            try:
                out[cell_id({"sym": s, "family": r.get("family"),
                             "params": r.get("params") or {}})] = str(r.get("role"))
            except Exception:
                continue
    return out


def _compiled_by_source() -> dict[str, dict[str, int]]:
    """Compiled candidates per donor (paperclip by role; the rival seats as one row each)."""
    doc = _read_json(HYP / "miner_candidates.json") or {}
    out: dict[str, dict[str, int]] = {}
    cands = doc.get("candidates") if isinstance(doc, dict) else None
    for c in cands or []:
        if not isinstance(c, dict):
            continue
        src = str(c.get("source") or "")
        if src == "miner:paperclip":
            role = str(c.get("source_url") or "").removeprefix("paperclip://").split("/")[0]
            out.setdefault(f"paperclip:{role}", {})["compiled"] = \
                out.setdefault(f"paperclip:{role}", {}).get("compiled", 0) + 1
        for rv in RIVALS:
            if src == f"miner:{rv}":
                out.setdefault(rv, {})["compiled"] = out.setdefault(rv, {}).get("compiled", 0) + 1
    seats = doc.get("seats") if isinstance(doc, dict) else None
    if isinstance(seats, dict):
        for rv in RIVALS:
            if isinstance(seats.get(rv), dict):
                out.setdefault(rv, {})["seat"] = seats[rv]  # type: ignore[assignment]
    return out


def _auc(pairs: list[tuple[float, bool]]) -> float | None:
    pos = [p for p, y in pairs if y]
    neg = [p for p, y in pairs if not y]
    if len(pos) < 3 or len(neg) < 3:
        return None
    wins = sum((1.0 if a > b else 0.5 if a == b else 0.0) for a in pos for b in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def score(last: dict[str, Any], fetch_err: str | None) -> dict[str, Any]:
    prev = _read_json(SCORECARD) or {}
    roles: dict[str, dict[str, Any]] = prev.get("roles") or {}
    for role, s in (last.get("calls") or {}).items():
        r = roles.setdefault(role, {})
        for k in ("calls", "accepted"):
            r[k] = int(r.get(k) or 0) + int(s.get(k) or 0)
    donated = _tail_jsonl(DONATED, 200_000, max_bytes=60_000_000)
    ids = _cell_ids(donated)
    judged: dict[str, int] = {}
    passed: dict[str, int] = {}
    tri = {str(t.get("cell")): float(t.get("prior") or 0) for t in
           _tail_jsonl(TRIAGE, 200_000, max_bytes=40_000_000) if t.get("cell")}
    pairs: list[tuple[float, bool]] = []
    ledger = HYP / "gate_verdict_ledger.jsonl"
    try:
        with ledger.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"cell"' not in line:
                    continue
                try:
                    v = json.loads(line)
                except ValueError:
                    continue
                cell = str(v.get("cell") or "")
                ok = v.get("passed") is True
                if cell in ids:
                    judged[ids[cell]] = judged.get(ids[cell], 0) + 1
                    if ok:
                        passed[ids[cell]] = passed.get(ids[cell], 0) + 1
                if cell in tri and str(v.get("terminal_gate") or "") not in ("", "UNKNOWN"):
                    pairs.append((tri[cell], ok))
    except OSError:
        pass
    comp = _compiled_by_source()
    for role, r in roles.items():
        r["compiled"] = int((comp.get(f"paperclip:{role}") or {}).get("compiled") or 0)
        r["judged"] = judged.get(role, 0)
        r["passed"] = passed.get(role, 0)
        calls = max(1, int(r.get("calls") or 0))
        r["unique_compiled_per_call"] = round(r["compiled"] / calls, 4)
        r["passed_per_100_calls"] = round(100 * r["passed"] / calls, 4)
    tot = {k: sum(int(r.get(k) or 0) for r in roles.values())
           for k in ("calls", "accepted", "compiled", "judged", "passed")}
    newest = prev.get("newest_bundle_at")
    if last.get("bundles"):
        newest = _iso(now())
    age_h = None
    if newest:
        age_h = round((now() - datetime.fromisoformat(newest)).total_seconds() / 3600, 2)
    if not newest:
        health, why = "RED", f"no bundle ever ingested ({fetch_err or 'no successful run'})"
    elif age_h is not None and age_h > STALE_H:
        health, why = "RED", f"newest bundle {age_h}h old (> {STALE_H}h): the loop stopped" + (
            f"; {fetch_err}" if fetch_err else "")
    else:
        health, why = "GREEN", "bundles landing"
    auc = _auc(pairs)
    doc = {"schema": "paperclip_scorecard/1", "at": _iso(now()), "health": health, "why": why,
           "newest_bundle_at": newest, "newest_bundle_age_h": age_h, "totals": tot,
           "usd_spent": 0.0, "roles": roles,
           "rivals": {rv: comp.get(rv) or "UNMEASURED" for rv in RIVALS},
           "triage": {"scored_cells": len(tri), "judged_since": len(pairs), "auc": auc,
                      "weight_earned": bool(auc is not None and auc >= 0.6 and len(pairs) >= 200),
                      "rule": "advisory until AUC >= 0.6 on >= 200 judged scored cells"},
           "last_pass": last}
    _write_json(SCORECARD, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    inbox = export_inbox()
    done = set(map(str, _read_json(INGESTED) or []))
    bundles, err = ([], "fetch disabled") if a.no_fetch else fetch_bundles(done)
    last = ingest(bundles)
    ids = {r for r in done | {rid for rid, _ in bundles} if r.isdigit()}
    _write_json(INGESTED, sorted(ids, key=int)[-2000:])
    doc = score(last, err)
    print(json.dumps({"inbox": inbox, "ingest": {k: v for k, v in last.items() if k != "calls"},
                      "health": doc["health"], "why": doc["why"], "totals": doc["totals"]},
                     default=str))
    return 0 if doc["health"] == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())

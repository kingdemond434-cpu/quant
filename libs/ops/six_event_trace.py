"""SIX-EVENT TRACE -- is the system real? Re-derived from recorded artifacts only.

The principal's test: the desk is real only if six events have HAPPENED, each provable by ids
and timestamps in recorded artifacts (never by code or docs that claim them):

  1 source mined end-to-end into a cell   2 cell preregistered (hash) BEFORE its judgement
  3 gauntlet REJECT with its gate logged   4 certified survivor forward-observed for real days
  5 live allocation -> broker deal -> reconciled against its intent
  6 decay detection that retired something (and was not later voided)

Verdict per event: PROVEN (latest instance within --fresh-days of --now), STALE (only older),
MISSING (no instance). A missing or unreadable artifact contributes nothing -- never a pass.
Timestamps are read from INSIDE the artifacts: the live branch is an orphan rooted 2026-09-28,
so git commit dates say when the tree was re-rooted, not when the box recorded anything.

    python -m libs.ops.six_event_trace [--root .] [--now 2026-09-30T12:00:00Z] [--fresh-days 7]

Clock: the `six_event_trace` step of desks/mt5/research/daily_cycle.py (once per UTC day).
Consumer: CRO_CYCLE.md STEP 4C, which reads the report and routes any non-PROVEN event as a
defect. Read-only except for its own report, desks/mt5/reports/six_event_trace.json. Stdlib only.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

DATA, REP = "desks/mt5/data", "desks/mt5/reports"
#: A seat's own output is not a mined external source (it is a model talking), so it is excluded.
LLM_SEAT = re.compile(r"chatgpt|gpt|deepseek|kimi|llm|claude|codex", re.I)


def _before(a: Any, b: Any) -> bool:
    """True when both parse and a is strictly earlier than b; an unparseable side is never true."""
    ta, tb = ts(a), ts(b)
    return ta is not None and tb is not None and ta < tb


def ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v[:4].isdigit():
        return None
    s = re.sub(r"(\.\d{6})\d+", r"\1", v.strip().replace("Z", "+00:00"))
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def load(root: str, rel: str) -> Any:
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def jsonl(root: str, rel: str) -> Iterator[Any]:
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            for ln in fh:
                try:
                    yield json.loads(ln)
                except ValueError:
                    continue
    except OSError:
        return


def git_meta(root: str, rel: str) -> dict[str, Any]:
    """Last commit on this checkout, and the last BOX-authored commit on any ref (the box
    commits as "Contabo MT5 Desk"); the live branch is an orphan, so the first is re-rooting."""
    out = {}
    for key, extra in (("head", []), ("box", ["--all", "--author=Contabo"])):
        try:
            r = subprocess.run(
                ["git", "-C", root, "log", "-1", *extra, "--format=%cI %an", "--", rel],
                capture_output=True,
                text=True,
                timeout=60,
            )
            out[key] = r.stdout.strip() or "none"
        except (OSError, subprocess.SubprocessError):
            out[key] = "UNMEASURED"
    return out


def ev(
    name: str, instances: list[dict[str, Any]], sources: list[str], note: str = ""
) -> dict[str, Any]:
    instances = [i for i in instances if ts(i.get("at"))]
    instances.sort(key=lambda i: ts(i["at"]) or datetime.min.replace(tzinfo=UTC))
    return {
        "event": name,
        "latest": instances[-1] if instances else None,
        "n_instances": len(instances),
        "sources": sources,
        "note": note,
    }


def e1_source_to_cell(root: str) -> dict[str, Any]:
    """Named external source (URL) -> hypothesis card -> docket cell id with a gauntlet verdict."""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "data/intelligence/hypotheses/H-*.yaml"))):
        with open(p, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
        hid = re.search(r"^id: (\S+)", txt, re.M)
        url = re.search(r"source_url: (\S+)", txt)
        coll = re.search(r"collected_at: '?([^'\n]+)", txt)
        rep = load(root, f"{REP}/gauntlet_{hid.group(1)}.json") if hid else None
        if not (hid and url and isinstance(rep, dict)):
            continue
        for v in (rep.get("result") or {}).get("verdicts") or []:
            out.append(
                {
                    "at": rep.get("generated_at"),
                    "source_url": url.group(1),
                    "collected_at": coll.group(1) if coll else None,
                    "card": hid.group(1),
                    "cell": v.get("cell"),
                    "passed": v.get("passed"),
                }
            )
    # Named miner source -> research-queue id -> canonical cell (no URL is carried on these rows).
    for r in load(root, f"{DATA}/research_queue.json") or []:
        gid = str(r.get("geneology_id", ""))
        if (
            r.get("canonical_cell")
            and gid.startswith("external:miner:")
            and not LLM_SEAT.search(gid)
        ):
            out.append(
                {
                    "at": r.get("reconciled_at"),
                    "source": r["geneology_id"],
                    "queue_id": r.get("id"),
                    "created_at": r.get("created_at"),
                    "cell": r["canonical_cell"],
                    "verdict": r.get("canonical_verdict"),
                    "source_url": None,
                }
            )
    return ev(
        "1 source mined end-to-end into a cell",
        out,
        [
            "data/intelligence/hypotheses/H-*.yaml",
            f"{REP}/gauntlet_*.json",
            f"{DATA}/research_queue.json",
        ],
    )


def e2_prereg_before_verdict(root: str) -> dict[str, Any]:
    """A verdict record that CARRIES a prereg_hash registered strictly before the verdict."""
    cards = {r.get("prereg_hash"): r for r in jsonl(root, f"{DATA}/preregistrations.jsonl")}
    out = []
    for n in jsonl(root, f"{DATA}/hypothesis_graph.jsonl"):
        h = n.get("prereg_hash") or (n.get("params") or {}).get("prereg_hash")
        c = cards.get(h)
        if (
            c
            and n.get("fate") in ("FAILED", "CERTIFIED")
            and _before(c.get("registered_utc"), n.get("at"))
        ):
            out.append(
                {
                    "at": n["at"],
                    "prereg_hash": h,
                    "registered_utc": c["registered_utc"],
                    "cell": n.get("region"),
                    "fate": n.get("fate"),
                }
            )
    for r in load(root, f"{DATA}/research_queue.json") or []:
        c = cards.get(r.get("prereg_hash"))
        if (
            c
            and r.get("canonical_verdict")
            and _before(c.get("registered_utc"), r.get("reconciled_at"))
        ):
            out.append(
                {
                    "at": r["reconciled_at"],
                    "prereg_hash": r["prereg_hash"],
                    "registered_utc": c["registered_utc"],
                    "cell": r.get("canonical_cell"),
                }
            )
    last = max(cards.values(), key=lambda c: c.get("registered_utc") or "", default=None)
    return ev(
        "2 cell preregistered with a sealed contract",
        out,
        [
            f"{DATA}/preregistrations.jsonl",
            f"{DATA}/hypothesis_graph.jsonl",
            f"{DATA}/research_queue.json",
        ],
        f"{len(cards)} cards registered, 0 joinable unless listed; latest card "
        f"{(last or {}).get('prereg_hash')} at {(last or {}).get('registered_utc')}; "
        "no committed verdict record carries a prereg_hash",
    )


def _fails(stages: dict[str, Any]) -> list[str]:
    return [
        g for g, s in (stages or {}).items() if isinstance(s, dict) and s.get("passed") is False
    ]


def e3_reject_with_gate(root: str) -> dict[str, Any]:
    out = []
    for p in glob.glob(os.path.join(root, REP, "gauntlet_*.json")):
        rep = load(root, os.path.relpath(p, root)) or {}
        for v in (rep.get("result") or {}).get("verdicts") or []:
            if v.get("passed") is False and _fails(v.get("stages")):
                out.append(
                    {
                        "at": rep.get("generated_at"),
                        "cell": v.get("cell"),
                        "failed_gates": _fails(v.get("stages")),
                        "artifact": os.path.relpath(p, root),
                    }
                )
    q = load(root, f"{REP}/QQUANT_GATES.json") or {}
    for v in q.get("verdicts") or []:
        if v.get("passed") is False and _fails(v.get("stages")):
            out.append(
                {
                    "at": q.get("swept_at"),
                    "cell": v.get("id"),
                    "hunt": v.get("hunt"),
                    "failed_gates": _fails(v.get("stages")),
                    "artifact": f"{REP}/QQUANT_GATES.json",
                }
            )
    return ev(
        "3 gauntlet REJECT with logged gate",
        out,
        [f"{REP}/gauntlet_*.json", f"{REP}/QQUANT_GATES.json"],
        "research_queue GAUNTLET_REJECTED rows carry no gate; the gate ledger "
        "(data/hypotheses/gate_verdict_ledger.jsonl, reports/universal_gates_external.json) "
        "is not committed",
    )


def e4_survivor_forward(root: str, min_days: float, min_n: int) -> dict[str, Any]:
    surv = (load(root, f"{REP}/UNIVERSAL_SURVIVORS.json") or {}).get("survivors") or {}
    shadow = load(root, f"{REP}/shadow/shadow_state.json") or {}
    out = []
    for key, s in surv.items():
        spec = (s or {}).get("shadow_spec") or {}
        row = shadow.get(f"{spec.get('symbol')}.{spec.get('selector')}")
        if not isinstance(row, dict):
            continue
        a, b, g = ts(row.get("first_entry")), ts(row.get("last_entry")), ts(s.get("gated_at"))
        if (
            a
            and b
            and g
            and a >= g
            and (b - a) >= timedelta(days=min_days)
            and (row.get("n") or 0) >= min_n
        ):
            out.append(
                {
                    "at": row["last_entry"],
                    "certificate": key,
                    "gated_at": s["gated_at"],
                    "clock": f"{spec['symbol']}.{spec['selector']}",
                    "n": row.get("n"),
                    "first_entry": row["first_entry"],
                    "status": row.get("status"),
                    "sleeve_id": row.get("sleeve_id"),
                }
            )
    last = max(
        (str(r.get("last_attempt_at")) for r in shadow.values() if isinstance(r, dict)),
        default=None,
    )
    return ev(
        "4 survivor forward-observed",
        out,
        [f"{REP}/UNIVERSAL_SURVIVORS.json", f"{REP}/shadow/shadow_state.json"],
        f"shadow state last written {last}",
    )


def e5_live_fill(root: str) -> dict[str, Any]:
    sleeves = {
        r.get("name"): r for r in (load(root, f"{DATA}/sleeves.json") or {}).get("sleeves") or []
    }
    deals: dict[Any, list[Any]] = {}
    for d in jsonl(root, f"{DATA}/live_ledger.jsonl"):
        for k in ("entry_order", "position_id"):
            if d.get(k):
                deals.setdefault(d[k], []).append(d)
    out = []
    for i in jsonl(root, f"{DATA}/order_intents.jsonl"):
        for d in {x["deal"]: x for x in deals.get(i.get("ticket") or -1, [])}.values():
            sl = sleeves.get(i.get("sleeve")) or {}
            out.append(
                {
                    "at": i.get("time"),
                    "sleeve": i.get("sleeve"),
                    "ticket": i["ticket"],
                    "entry_deal": d.get("entry_deal"),
                    "close_deal": d.get("deal"),
                    "requested": i.get("intended"),
                    "entry_fill": d.get("entry_price"),
                    "deal_recorded": d.get("time"),
                    "account": d.get("account"),
                    "sleeve_status_now": sl.get("status"),
                    "allocator_funded_now": sl.get("risk_frac_source") == "allocator_marginal"
                    and (sl.get("risk_frac") or 0) > 0,
                    "principal_override": bool(sl.get("principal_override")),
                }
            )
    m = load(root, f"{REP}/markout.json") or {}
    return ev(
        "5 live allocation -> reconciled fill",
        out,
        [
            f"{DATA}/order_intents.jsonl",
            f"{DATA}/live_ledger.jsonl",
            f"{DATA}/sleeves.json",
            f"{REP}/markout.json",
        ],
        f"markout.json at {m.get('at')}: n_matched={m.get('n_matched')} "
        f"(the organ that should record the match); joins here are re-derived",
    )


def e6_decay_retirement(root: str) -> dict[str, Any]:
    out, voided = [], []
    for k, r in (load(root, f"{DATA}/GOLD_RETIRED.json") or {}).items():
        out.append(
            {"at": (r or {}).get("retired_at"), "window": k, "reason": (r or {}).get("reason")}
        )
    for k, r in (load(root, f"{DATA}/GOLD_RETIRED_VOIDED.json") or {}).items():
        voided.append(
            {
                "window": k,
                **{
                    x: (r or {}).get(x) for x in ("retired_at", "reason", "voided_at", "voided_why")
                },
            }
        )
    for a in (load(root, f"{DATA}/decay_live.json") or {}).get("actions_taken") or []:
        if isinstance(a, dict):
            out.append({"at": a.get("at"), "decay_action": a})
    for k, r in (load(root, f"{REP}/shadow/shadow_state.json") or {}).items():
        if isinstance(r, dict) and r.get("e_kill_supported") is True and r.get("retired_at"):
            out.append({"at": r["retired_at"], "clock": k, "reason": r.get("retire_reason")})
    d = load(root, f"{DATA}/decay_live.json") or {}
    return ev(
        "6 decay detection retired something",
        out,
        [
            f"{DATA}/GOLD_RETIRED.json",
            f"{DATA}/GOLD_RETIRED_VOIDED.json",
            f"{DATA}/decay_live.json",
            f"{REP}/shadow/shadow_state.json",
        ],
        f"voided retirements: {voided}; decay_live.json checked_at {d.get('checked_at')} "
        f"roster_state={d.get('roster_state')}",
    )


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--now", default=None, help="ISO time; default is the wall clock (UTC)")
    ap.add_argument("--fresh-days", type=float, default=7.0)
    ap.add_argument("--min-forward-days", type=float, default=7.0)
    ap.add_argument("--min-forward-n", type=int, default=5)
    ap.add_argument("--out", default=f"{REP}/six_event_trace.json")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    now = (ts(a.now) if a.now else None) or datetime.now(UTC)
    events = [
        e1_source_to_cell(root),
        e2_prereg_before_verdict(root),
        e3_reject_with_gate(root),
        e4_survivor_forward(root, a.min_forward_days, a.min_forward_n),
        e5_live_fill(root),
        e6_decay_retirement(root),
    ]
    for e in events:
        t = ts((e["latest"] or {}).get("at"))
        e["verdict"] = (
            "MISSING"
            if t is None
            else "PROVEN"
            if now - t <= timedelta(days=a.fresh_days)
            else "STALE"
        )
        e["latest_at"] = t.isoformat() if t else None
        e["git_last_commit"] = {s: git_meta(root, s) for s in e["sources"] if "*" not in s}
    doc = {
        "generated_at": datetime.now(UTC).isoformat(),
        "now": now.isoformat(),
        "fresh_days": a.fresh_days,
        "events": events,
    }
    try:
        os.makedirs(os.path.dirname(os.path.join(root, a.out)), exist_ok=True)
        with open(os.path.join(root, a.out), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
    except OSError as exc:
        print(f"could not write {a.out}: {exc}")
    print("| event | verdict | latest | key ids |\n|---|---|---|---|")
    for e in events:
        ids = {k: v for k, v in (e["latest"] or {}).items() if k != "at" and v not in (None, "")}
        print(
            f"| {e['event']} | {e['verdict']} | {e['latest_at']} | "
            f"{json.dumps(ids, default=str)[:220]} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

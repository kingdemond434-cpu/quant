"""THE HOURLY PASS, ON THE BOX, 24/7, WITHOUT CLAUDE (principal 2026-11-25 03:11Z).

"abuse hrly pass fr max roi 24 7 without claude limits". The pass that a Claude session ran every
6 hours (reports/hourly_pass/tools/system_board.py + redteam_pick.py + PREVENTION.tsv) is folded
into the guardian, so the box has ONE checker. It reads only local box files (no git, no network)
and publishes desks/mt5/reports/PASS_FINDINGS.json with the 15-minute state push. Claude's pass
then only reviews `needs_claude` and writes fixes.

Every guardian pass (15 min): the board (every task row with its status and prevention class),
invariants I1-I8 (from the guardian's own DESK_SELF_HEAL.json), the prevention census, the fault
diff against the last pass (new / changed / fixed / escalate after 3 passes).
Once an hour: the computed lens answers and a red-team round of mechanical probes on the 3
least-recently inspected components. The ask ledger's sources live in the project files, not on
the box, so `ledger` says OFF_BOX rather than inventing a score.

No LLM is used here at all (ambiguous probes go to `needs_claude`), and nothing here can touch
sizing, orders or the money path: it reads and it writes three files.
"""
from __future__ import annotations

import collections
import contextlib
import json
import os
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
OUT = "desks/mt5/reports/PASS_FINDINGS.json"
STATE = "data/box_pass_state.json"          # box-local diff memory (gitignored)
REDTEAM_LOG = "data/box_pass_redteam.jsonl"  # box-local inspection history
PREVENTION = "ops/pass/PREVENTION.tsv"
BOARD = "desks/mt5/reports/process_health.json"
SELF_HEAL = "desks/mt5/reports/DESK_SELF_HEAL.json"
RELEASE = "desks/mt5/data/release_identity.json"
SLEEVES = "desks/mt5/data/sleeves.json"
ESCALATE_PASSES = 3
HOURLY_MIN = 55.0
REDTEAM_PICKS = 3
#: Exit codes that are not failures: 0, still running (0x41301), not yet run (0x41303).
OK_CODES = (0, 267009, 267011, None)
INTENDED_OFF = {
    "MT5-CycleNoon": 'zuck 11-19 "Remove noon cycle only fr now"',
    "MemecoinAutonomousDevelopment": "old Codex dev worker; dev goes via audited packets",
    "MT5-FTMOFollow": "copy follower retired; FTMO native executor (zuck 11-20 no copy accounts)",
}
MAP = {"OK": "LIVE", "FAILING": "BROKEN", "STALE": "BROKEN", "NO_ARTIFACT": "BROKEN",
       "NOT_SCHEDULED": "NOT_LIVE", "DISABLED": "NOT_LIVE", "UNCONTRACTED": "UNCONTRACTED"}
OWN = [(("gateway", "shadow", "allocator", "terminal", "ftmo", "e8", "promot", "sleeve", "fill",
         "regime", "decay"), "One pipe"),
       (("judge", "frontier", "deepen", "tape", "intel", "cert", "gauntlet", "hunt", "breadth",
         "miner", "compiler", "docket", "paperclip", "llm"), "Research"),
       (("news", "world", "macro", "data", "feed", "forest", "cot", "flow"), "Data"),
       (("memecoin",), "Memecoin")]


def owner(name: str) -> str:
    nl = name.lower()
    return next((o for kws, o in OWN if any(k in nl for k in kws)), "Autonomy")


def _read(root: Path, rel: str) -> Any:
    try:
        return json.loads((root / rel).read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}


def _write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, p)


def _ts(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def load_prevention(root: Path) -> list[tuple[str, re.Pattern[str], str, str, str]]:
    out = []
    with contextlib.suppress(OSError):
        for ln in (root / PREVENTION).read_text("utf-8").splitlines():
            f = ln.split("\t")
            if ln and not ln.startswith("#") and len(f) >= 6:
                with contextlib.suppress(re.error):
                    out.append((f[0], re.compile(f[1]), f[2], f[4], f[5]))
    return out


def board_rows(root: Path) -> list[dict[str, Any]]:
    ph = _read(root, BOARD)
    rows: list[dict[str, Any]] = []
    for p in ph.get("processes", []) if isinstance(ph, dict) else []:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        name, verdict = str(p["name"]), str(p.get("verdict") or "")
        why = str(p.get("why") or "")
        code = p.get("last_result_code")
        if name in INTENDED_OFF and verdict == "DISABLED":
            status, fault = "OFF_BY_DESIGN", INTENDED_OFF[name]
        elif verdict == "UNCONTRACTED" and code not in OK_CODES:
            status, verdict = "BROKEN", "UNCONTRACTED+FAILED"
            fault = f"no artifact contract AND last run failed: {p.get('last_result')} " \
                    f"(code {code})"
        else:
            status, fault = MAP.get(verdict, "BROKEN"), (why if verdict != "OK" else "")
        rows.append({"name": name, "status": status, "verdict": verdict,
                     "last_run": str(p.get("last_run") or ""), "fault": fault[:160],
                     "owner": owner(name), "age_min": p.get("artifact_age_min"),
                     "limit_min": p.get("contract_max_age_min"), "code": code})
    return rows


def invariant_rows(root: Path) -> dict[str, dict[str, Any]]:
    sh = _read(root, SELF_HEAL)
    out: dict[str, dict[str, Any]] = {}
    for r in sh.get("invariants", []) if isinstance(sh, dict) else []:
        if isinstance(r, dict) and r.get("invariant"):
            detail = str(r.get("detail") or "")
            out[str(r["invariant"])] = {"ok": bool(r.get("holds")) and "UNMEASURED" not in detail,
                                        "unmeasured": "UNMEASURED" in detail,
                                        "verdict": detail[:240]}
    for k in ("I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8"):
        out.setdefault(k, {"ok": False, "unmeasured": True,
                           "verdict": "UNMEASURED: the guardian has not reported this invariant"})
    return out


def classify(rows: list[dict[str, Any]], prev: list[tuple[str, re.Pattern[str], str, str, str]]
             ) -> None:
    for r in rows:
        if r["status"] not in ("BROKEN", "NOT_LIVE"):
            continue
        key = f"{r['name']}|{r['verdict']}|{r['fault']}"
        hit = next(((c, st, own) for c, rx, _rule, st, own in prev if rx.search(key)), None)
        r["prevention"], r["prevention_status"] = (hit[0], hit[1]) if hit else (
            "UNCLASSIFIED", "MISSING")


def diff(rows: list[dict[str, Any]], state: dict[str, Any], now: str
         ) -> tuple[dict[str, Any], dict[str, list[str]]]:
    new_state: dict[str, Any] = {}
    d: dict[str, list[str]] = {"new": [], "changed": [], "fixed": [], "escalate": []}
    for r in rows:
        p = state.get(r["name"]) or {}
        bad = r["status"] in ("BROKEN", "NOT_LIVE")
        passes = int(p.get("bad_passes") or 0) + 1 if bad else 0
        new_state[r["name"]] = {"status": r["status"], "verdict": r["verdict"],
                                "first_bad": (p.get("first_bad") or now) if bad else None,
                                "bad_passes": passes}
        if bad and not p:
            d["new"].append(r["name"])
        elif bad and p.get("verdict") != r["verdict"]:
            d["changed"].append(r["name"])
        elif not bad and p.get("status") in ("BROKEN", "NOT_LIVE"):
            d["fixed"].append(r["name"])
        if bad and passes >= ESCALATE_PASSES:
            d["escalate"].append(r["name"])
    return new_state, d


def lens(root: Path, rows: list[dict[str, Any]], inv: dict[str, dict[str, Any]]
         ) -> dict[str, Any]:
    """The computable zuck-lens answers (ZUCK_LENS.md), from box files only."""
    c = collections.Counter(r["status"] for r in rows)
    judged = c["LIVE"] + c["BROKEN"] + c["NOT_LIVE"]
    sl = _read(root, SLEEVES)
    sl = sl.get("sleeves", sl) if isinstance(sl, dict) else sl
    sl = list(sl.values()) if isinstance(sl, dict) else (sl if isinstance(sl, list) else [])
    live = [s for s in sl if isinstance(s, dict) and s.get("status") == "LIVE"]
    by_acct = collections.Counter(str(s.get("account") or s.get("venue") or "unknown")
                                  for s in live)
    hr = _read(root, "desks/mt5/reports/BOX_HEADROOM.json")
    rid = _read(root, RELEASE)
    prev_rows = [r for r in rows if r.get("prevention")]
    return {
        "Q1_live_share": round(c["LIVE"] / judged, 3) if judged else None,
        "Q2_stale_ok": sum(1 for r in rows if r["verdict"] == "STALE" and r["code"] == 0),
        "Q3_prevention_box_share": round(sum(r["prevention_status"] == "BOX" for r in prev_rows)
                                         / len(prev_rows), 3) if prev_rows else None,
        "Q4_headroom": {k: (hr.get(k) or {}).get("why") for k in
                        ("disk", "ram", "cpu", "terminals", "quotas")} if hr else "UNMEASURED",
        "Q5_invariants_holding": sum(v["ok"] for v in inv.values()),
        "Q6_uncontracted": c["UNCONTRACTED"],
        "Q9_release": {"verdict": rid.get("verdict"), "running": str(rid.get("running_sha"))[:9],
                       "allows_new_risk": rid.get("allows_new_risk")} if rid else "UNMEASURED",
        "Q11_live_sleeves_by_account": dict(by_acct) if sl else "UNMEASURED",
    }


def probe(r: dict[str, Any]) -> dict[str, Any]:
    """Mechanical red-team probes on one board component: no judgement, no LLM."""
    checks = {
        "has_contract": r["limit_min"] is not None,
        "artifact_fresh": (r["age_min"] is not None and r["limit_min"] is not None
                           and float(r["age_min"]) <= float(r["limit_min"])),
        "result_ok": r["code"] in OK_CODES,
        "verdict_ok": r["status"] in ("LIVE", "OFF_BY_DESIGN"),
        "verdict_agrees": not (r["status"] == "LIVE" and r["code"] not in OK_CODES),
    }
    failed = [k for k, v in checks.items() if not v]
    verdict = "PASS" if not failed else ("SUSPECT" if failed == ["has_contract"] else "FAIL")
    return {"component": r["name"], "probes": checks, "verdict": verdict,
            "finding": ", ".join(failed) or "all probes pass", "owner": r["owner"]}


def redteam(root: Path, rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    last: dict[str, str] = {}
    with contextlib.suppress(OSError):
        for ln in (root / REDTEAM_LOG).read_text("utf-8").splitlines():
            with contextlib.suppress(ValueError):
                row = json.loads(ln)
                last[str(row.get("component"))] = str(row.get("at"))
    pool = sorted(r["name"] for r in rows)
    random.Random(now.strftime("%Y-%m-%d") + str(len(last))).shuffle(pool)  # noqa: S311
    pool.sort(key=lambda n: last.get(n, ""))
    byname = {r["name"]: r for r in rows}
    out = [probe(byname[n]) for n in pool[:REDTEAM_PICKS]]
    with contextlib.suppress(OSError):
        (root / REDTEAM_LOG).parent.mkdir(parents=True, exist_ok=True)
        with (root / REDTEAM_LOG).open("a", encoding="utf-8") as fh:
            for f in out:
                fh.write(json.dumps({"at": now.isoformat(timespec="seconds"), **f}) + "\n")
    return out


def run(root: Path = ROOT, now: datetime | None = None) -> dict[str, Any]:
    t = now or datetime.now(UTC)
    at = t.isoformat(timespec="seconds")
    rows = board_rows(root)
    classify(rows, load_prevention(root))
    st = _read(root, STATE)
    st = st if isinstance(st, dict) else {}
    board_state, d = diff(rows, st.get("board") or {}, at)
    inv = invariant_rows(root)
    counts = collections.Counter(r["status"] for r in rows)
    pc = collections.Counter(r.get("prevention_status") for r in rows if r.get("prevention"))
    last_h = _ts(st.get("last_hourly"))
    hourly = last_h is None or (t - last_h).total_seconds() / 60 >= HOURLY_MIN
    prev_doc = _read(root, OUT)
    prev_doc = prev_doc if isinstance(prev_doc, dict) else {}
    lens_doc = lens(root, rows, inv) if hourly else prev_doc.get("lens", {})
    red = redteam(root, rows, t) if hourly and rows else prev_doc.get("redteam", [])
    needs = [f"{r['name']}: {r['fault']}" for r in rows
             if r.get("prevention") == "UNCLASSIFIED"][:30]
    needs += [f"redteam {f['component']}: {f['finding']}" for f in red
              if f.get("verdict") == "FAIL"]
    needs += [f"invariant {k}: {v['verdict']}" for k, v in inv.items() if not v["ok"]]
    sh = _read(root, SELF_HEAL)
    doc = {
        "schema": "pass_findings/1", "at": at, "measured": bool(rows),
        "board": {"counts": dict(counts), **d},
        "invariants": inv,
        "prevention": {"BOX": pc.get("BOX", 0), "BUILT": pc.get("BUILT", 0),
                       "SPECCED": pc.get("SPECCED", 0), "MISSING": pc.get("MISSING", 0),
                       "UNCLASSIFIED": sorted(r["name"] for r in rows
                                              if r.get("prevention") == "UNCLASSIFIED")},
        "lens": lens_doc, "lens_at": at if hourly else prev_doc.get("lens_at"),
        "redteam": red,
        "ledger": {"state": "OFF_BOX", "why": "the ask ledger's sources (ZUCK_LEDGER, "
                   "ASKS_SINCE_1118) live in the project files, not on the box"},
        "autofixed": [r for r in (sh.get("repairs") or []) if r.get("ok")]
        if isinstance(sh, dict) else [],
        "needs_claude": needs,
    }
    with contextlib.suppress(OSError):
        _write_atomic(root / OUT, json.dumps(doc, indent=1, default=str) + "\n")
        _write_atomic(root / STATE, json.dumps(
            {"board": board_state, "last_hourly": at if hourly else st.get("last_hourly")}) + "\n")
    return doc


if __name__ == "__main__":
    d = run()
    print(json.dumps({"at": d["at"], "counts": d["board"]["counts"],
                      "escalate": len(d["board"]["escalate"]),
                      "needs_claude": len(d["needs_claude"])}))

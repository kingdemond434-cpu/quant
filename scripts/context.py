#!/usr/bin/env python3
"""THE REPO AS RESEARCH MEMORY: decision journal, per-sleeve rationale, operator digest.

    python scripts/context.py decide --title T --decision D --why W --by WHO [--owner LANE]
                                     [--evidence PATH|sha:SHA|pr:N|url:URL ...] [--supersedes ID]
    python scripts/context.py show [--n 20] [--grep WORD]
    python scripts/context.py verify            # exit 1 on a malformed row or a missing path
    python scripts/context.py rationale --sync  # one file per LIVE/STANDBY sleeve, human text kept
    python scripts/context.py digest [--out P]  # the operator's one-page audit (default
                                                # context/DIGEST.md; the box writes
                                                # desks/mt5/reports/OPERATOR_DIGEST.md)
    python scripts/context.py coverage          # read-only rationale coverage

Protocol and ownership: context/DELEGATION_PROTOCOL.md. Why this exists: research that lives in
chat is lost when the session ends, and an operator who must re-read every agent's work to trust
it has no time left to run the book. So every decision that changes what the desk does is ONE
journal row with pointers to its evidence, `verify` proves the pointers resolve, and the digest
is the single page the operator reads.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CTX = ROOT / "context"
JOURNAL = CTX / "decision_journal.jsonl"
SLEEVES_DIR = CTX / "sleeves"
DIGEST = CTX / "DIGEST.md"
SLEEVES = ROOT / "desks" / "mt5" / "data" / "sleeves.json"
REPORTS = ROOT / "desks" / "mt5" / "reports"
REQUIRED = ("id", "at", "title", "decision", "why", "by", "evidence")
GEN_OPEN, GEN_CLOSE = "<!-- generated: do not edit between these markers -->", "<!-- /generated -->"
UNWRITTEN = "UNWRITTEN"


def read_journal(path: Path = JOURNAL) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                rows.append({"_bad": f"line {i}: {exc}"})
    return rows


def next_id(rows: list[dict[str, Any]], day: str) -> str:
    n = sum(1 for r in rows if str(r.get("id", "")).startswith(f"D-{day}-"))
    return f"D-{day}-{n + 1:03d}"


def decide(a: argparse.Namespace, path: Path = JOURNAL) -> dict[str, Any]:
    rows = read_journal(path)
    now = datetime.now(UTC)
    row = {"id": next_id(rows, now.strftime("%Y%m%d")), "at": now.isoformat(timespec="seconds"),
           "title": a.title, "decision": a.decision, "why": a.why, "by": a.by,
           "owner": a.owner or "", "evidence": list(a.evidence or []),
           "supersedes": a.supersedes or ""}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _check_pointer(p: str) -> str:
    """OK, MISSING, or UNVERIFIABLE (a shallow clone cannot see an old commit; not a lie)."""
    if p.startswith(("url:", "pr:", "http://", "https://", "thread:")):
        return "OK"
    if p.startswith("sha:"):
        sha = p[4:]
        try:
            r = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{sha}^{{commit}}"],
                               capture_output=True, timeout=10)
        except Exception:
            return "UNVERIFIABLE"
        return "OK" if r.returncode == 0 else "UNVERIFIABLE"
    path = p.split("#", 1)[0].split(":", 1)[0] if re.match(r"^[^:]+:\d+", p) else p.split("#", 1)[0]
    if path.startswith("/mnt/project-files/"):
        return "OK" if Path(path).exists() else "UNVERIFIABLE"
    return "OK" if (ROOT / path).exists() else "MISSING"


def verify(path: Path = JOURNAL) -> tuple[bool, list[str]]:
    problems: list[str] = []
    ids: set[str] = set()
    for r in read_journal(path):
        if "_bad" in r:
            problems.append(r["_bad"])
            continue
        rid = str(r.get("id"))
        miss = [k for k in REQUIRED if not r.get(k)]
        if miss:
            problems.append(f"{rid}: missing {miss}")
        if rid in ids:
            problems.append(f"{rid}: duplicate id")
        ids.add(rid)
        if r.get("supersedes") and r["supersedes"] not in ids:
            problems.append(f"{rid}: supersedes unknown or later id {r['supersedes']}")
        for p in r.get("evidence") or []:
            if _check_pointer(str(p)) == "MISSING":
                problems.append(f"{rid}: evidence path does not exist: {p}")
    return (not problems), problems


def _family_mechanism(family: str) -> str:
    try:
        sys.path.insert(0, str(ROOT / "desks" / "mt5"))
        from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES
        fn = ORTHOGONAL_FAMILIES.get(family)
        doc = (fn.__doc__ or "").strip().split("\n\n")[0] if fn else ""
        inputs = FAMILY_INPUTS.get(family, ("", None))[0]
        return " ".join(doc.split()) + (f" Inputs: {inputs}." if inputs else "")
    except Exception:
        return ""


def _generated_block(row: dict[str, Any]) -> str:
    keys = ("status", "symbol", "timeframe", "family", "session", "exec", "risk_frac",
            "risk_frac_source", "lot")
    lines = [GEN_OPEN, "", "| field | value |", "|---|---|"]
    lines += [f"| {k} | {row.get(k)} |" for k in keys if row.get(k) is not None]
    po = row.get("principal_override")
    if isinstance(po, dict) and po.get("why"):
        lines += ["", f"Principal override ({po.get('by', '')}): {po['why']}"]
    lines += ["", "_from desks/mt5/data/sleeves.json (the box's copy is authoritative; re-run "
                  "`rationale --sync` after pulling it)_", GEN_CLOSE]
    return "\n".join(lines)


def _section(text: str, heading: str) -> str:
    """The body under `heading` up to the next level-2 heading, stripped."""
    if heading not in text:
        return ""
    body = text.split(heading, 1)[1].split("\n", 1)[-1]
    return body.split("\n## ", 1)[0].strip()


def rationale_sync(sleeves: Path = SLEEVES, out_dir: Path = SLEEVES_DIR) -> dict[str, Any]:
    """One file per LIVE/STANDBY sleeve. The generated block is refreshed; human text is kept."""
    doc = json.loads(sleeves.read_text(encoding="utf-8")) if sleeves.exists() else {}
    rows = [r for r in (doc.get("sleeves") or []) if isinstance(r, dict)
            and r.get("status") in ("LIVE", "STANDBY") and r.get("name")]
    out_dir.mkdir(parents=True, exist_ok=True)
    created, updated, written = [], 0, 0
    for r in rows:
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", str(r["name"]))
        p = out_dir / f"{name}.md"
        block = _generated_block(r)
        if p.exists():
            text = p.read_text(encoding="utf-8")
            if GEN_OPEN in text and GEN_CLOSE in text:
                head, rest = text.split(GEN_OPEN, 1)
                tail = rest.split(GEN_CLOSE, 1)[1]
                new = head + block + tail
            else:
                new = text.rstrip() + "\n\n" + block + "\n"
            if new != text:
                p.write_text(new, encoding="utf-8")
                updated += 1
        else:
            mech = _family_mechanism(str(r.get("family") or ""))
            p.write_text("\n".join([
                f"# {r['name']}", "", block, "",
                "## Thesis (why this edge exists)", "",
                (f"Family mechanism, from the family's own code: {mech}" if mech
                 else UNWRITTEN), "",
                "## Why it should keep working, and who is on the other side", "", UNWRITTEN, "",
                "## Kill criterion (the falsifier that retires it)", "", UNWRITTEN, "",
                "## Regime notes (control room: vol / trend / liquidity)", "", UNWRITTEN, "",
                "## Log", ""]) + "\n", encoding="utf-8")
            created.append(name)
        if _section(p.read_text(encoding="utf-8"), "## Thesis") not in ("", UNWRITTEN):
            written += 1
    return {"sleeves": len(rows), "created": created, "updated": updated,
            "thesis_written": written,
            "thesis_coverage": round(written / len(rows), 4) if rows else None}


def coverage(sleeves: Path = SLEEVES, out_dir: Path = SLEEVES_DIR) -> dict[str, Any]:
    """READ-ONLY rationale coverage: which LIVE/STANDBY sleeves have a file and a written thesis.

    The daily cycle calls this on the box and must never write under `context/`: that folder is
    CODE to `libs.ops.release` (not a state prefix), so a box-side write would dirty the tree and
    refuse the seal. Rationale files are written by agents on origin (`rationale --sync`).
    """
    doc = json.loads(sleeves.read_text(encoding="utf-8")) if sleeves.exists() else {}
    rows = [r for r in (doc.get("sleeves") or []) if isinstance(r, dict)
            and r.get("status") in ("LIVE", "STANDBY") and r.get("name")]
    missing, unwritten = [], []
    for r in rows:
        p = out_dir / (re.sub(r"[^A-Za-z0-9_.-]", "_", str(r["name"])) + ".md")
        if not p.exists():
            missing.append(str(r["name"]))
        elif _section(p.read_text(encoding="utf-8"), "## Thesis") in ("", UNWRITTEN):
            unwritten.append(str(r["name"]))
    n = len(rows)
    return {"sleeves": n, "live": sum(1 for r in rows if r.get("status") == "LIVE"),
            "missing_file": missing, "thesis_unwritten": unwritten,
            "thesis_written": n - len(missing) - len(unwritten),
            "thesis_coverage": round((n - len(missing) - len(unwritten)) / n, 4) if n else None}


def _report(name: str) -> dict[str, Any] | None:
    p = REPORTS / name
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except Exception:
        return None


def digest(n: int = 20, out: Path = DIGEST) -> str:
    rows = [r for r in read_journal() if "_bad" not in r]
    ok, problems = verify()
    rs = coverage()
    cr = _report("CONTROL_ROOM.json") or {}
    rc = _report("REGIME_ALLOCATION_CONTRACT.json") or {}
    bb = _report("BENCH_BRIDGE.json") or {}
    lines = ["# Operator digest", "",
             f"_generated {datetime.now(UTC).isoformat(timespec='minutes')} by "
             "`python scripts/context.py digest`; derived, never edit by hand_", "",
             "## Control room", ""]
    if cr:
        lines.append(f"- Instruments trending {cr.get('share_trending')}, high-vol "
                     f"{cr.get('share_high_vol')}, thin {cr.get('share_thin')} "
                     f"(`desks/mt5/reports/CONTROL_ROOM.json`)")
    else:
        lines.append("- Control room: UNMEASURED on this host")
    if rc:
        h = rc.get("headline") or {}
        lines.append(f"- Regime-to-allocation contract: **{rc.get('verdict')}**, "
                     f"geo_asset - geo = {h.get('annual')} log/yr, CI90 per day {h.get('ci90')}")
    if bb:
        st = bb.get("stages") or {}
        lines.append("- Bench to capital: " + ", ".join(
            f"{k} {v.get('n')}" for k, v in st.items()) + f"; missed growth "
            f"{len(bb.get('missed_growth') or [])} candidate(s), "
            f"{bb.get('missed_growth_per_year')} log/yr")
    lines += ["", "## Research memory health", "",
              f"- Journal: {len(rows)} decision(s); verify "
              f"{'PASS' if ok else 'FAIL: ' + '; '.join(problems[:5])}",
              f"- Sleeve rationale: {rs.get('sleeves')} live/standby sleeve(s), thesis written for "
              f"{rs.get('thesis_written')} ({rs.get('thesis_coverage')}); no file for "
              f"{len(rs.get('missing_file') or [])} -- run `python scripts/context.py rationale "
              "--sync` on origin", "",
              f"## Last {n} decisions", ""]
    for r in rows[-n:][::-1]:
        ev = ", ".join(f"`{e}`" for e in (r.get("evidence") or [])[:4])
        lines.append(f"- **{r.get('id')}** {r.get('title')} ({r.get('by')}"
                     f"{'; owner ' + r['owner'] if r.get('owner') else ''}): {r.get('decision')}"
                     + (f" Evidence: {ev}" if ev else ""))
    text = "\n".join(lines) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decide")
    for k in ("title", "decision", "why", "by"):
        d.add_argument(f"--{k}", required=True)
    d.add_argument("--owner", default="")
    d.add_argument("--evidence", nargs="*", default=[])
    d.add_argument("--supersedes", default="")
    s = sub.add_parser("show")
    s.add_argument("--n", type=int, default=20)
    s.add_argument("--grep", default="")
    sub.add_parser("verify")
    r = sub.add_parser("rationale")
    r.add_argument("--sync", action="store_true")
    g = sub.add_parser("digest")
    g.add_argument("--n", type=int, default=20)
    g.add_argument("--out", type=Path, default=DIGEST)
    sub.add_parser("coverage")
    a = ap.parse_args(argv)
    if a.cmd == "decide":
        print(json.dumps(decide(a), indent=1))
    elif a.cmd == "show":
        rows = [x for x in read_journal() if not a.grep or a.grep.lower() in json.dumps(x).lower()]
        for x in rows[-a.n:]:
            print(f"{x.get('id')}  {x.get('title')}  -- {x.get('decision')}")
    elif a.cmd == "verify":
        ok, problems = verify()
        print("PASS" if ok else "\n".join(problems))
        return 0 if ok else 1
    elif a.cmd == "rationale":
        print(json.dumps(rationale_sync(), indent=1))
    elif a.cmd == "digest":
        print(digest(a.n, a.out))
    elif a.cmd == "coverage":
        print(json.dumps(coverage(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

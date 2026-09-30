#!/usr/bin/env python3
"""THE TIER S PROGRAMME CANNOT CLAIM WHAT THE REPOSITORY DOES NOT HOLD -- AND NO LAYER SHIPS
WITHOUT A CONTRACT.

`docs/research/tier_s_program.json` lists the 46 layers of the Tier S research institution. The
blueprint is CLOSED (principal, 2026-09-29): no new categories, and a subsystem is admitted only
with a MEASURABLE CONTRACT naming the gain it must show -- more independent-alpha discovery, more
falsification power, more information per compute, a lower false-discovery rate, better
live/backtest calibration, better execution capture, lower operational risk, or measurable
research productivity. This fence is that admission rule, enforced at every law-gate run:

  * status is DONE, PARTIAL, BLOCKED_ON_USER or BLOCKED_ON_BOX, and every status but DONE names
    what is left in `remaining` -- a layer cannot read as finished while its wording is not met;
  * every cited file exists; the clock is one the repository knows (the same clock vocabulary
    as check_tier5_audit.py); the artifact is named;
  * the contract parses (`libs.tiers.contracts.problems`) and its `organ` is a Tier S organ
    (`desks/mt5/research/tier_s.py`) or `report:<FILE>` whose writer is itself a known leg;
  * a DONE layer carries an empty `remaining`: "done, except" is PARTIAL;
  * a DONE layer is ATTESTED BY THE TRADING BOX (verifier, 2026-09-30): its artifact fresh on
    the box and its contract not REJECTED, in the box-written data/tier_s/box_evidence.json
    (`libs/tiers/box_evidence`). Code complete and tested elsewhere is BUILT, never DONE;
  * every hourly leg the programme ADDED (`LEG_CONTRACTED`) carries a parsing contract in
    `leg_contracts`, read from its own report -- a new leg with no contract is refused.

`--render` writes docs/research/TIER_S_PROGRAM.md (the gap map; derived, never hand-edited),
and with `--with-verdicts` joins this host's latest hourly verdicts from
desks/mt5/reports/tier_s/CONTRACTS.json (the committed render carries none: a verdict is the box's).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from check_tier5_audit import clock_known, clocks  # noqa: E402

from libs.tiers import box_evidence, contracts  # noqa: E402

LEDGER = ROOT / "docs" / "research" / "tier_s_program.json"
RENDERED = ROOT / "docs" / "research" / "TIER_S_PROGRAM.md"
VERDICTS = ROOT / "desks" / "mt5" / "reports" / "tier_s" / "CONTRACTS.json"
ORGAN_SRC = ROOT / "desks" / "mt5" / "research" / "tier_s.py"
STATUSES = ("DONE", "BUILT", "PARTIAL", "BLOCKED_ON_USER", "BLOCKED_ON_BOX")
#: the trading box's own attestation, committed by the box's sync (libs/tiers/box_evidence)
BOX_EVIDENCE = ROOT / "desks" / "mt5" / "data" / "tier_s" / "box_evidence.json"
N_LAYERS = 46
#: the hourly legs the Tier S programme added outside the 46 layers: each needs a contract
LEG_CONTRACTED = ("tier_s", "adversary_evolution", "execution_science", "frontier_map",
                  "market_ecology", "research_diversity_archive")


def organs(root: Path) -> set[str]:
    p = root / "desks" / "mt5" / "research" / "tier_s.py"
    if not p.exists():
        return set()
    src = p.read_text("utf-8", errors="replace")
    return set(re.findall(r'\("([a-z_]+)", organ_\w+\)', src)) | set(
        re.findall(r'reports\["([a-z_]+)"\] = _run', src))


def check(ledger: dict[str, Any], root: Path,
          evidence: Any = None) -> tuple[list[str], Counter[str]]:
    problems: list[str] = []
    if evidence is None:
        try:
            evidence = json.loads((root / BOX_EVIDENCE.relative_to(ROOT)).read_text("utf-8"))
        except (OSError, ValueError):
            evidence = {}
    on_box = box_evidence.attested(evidence)
    known = clocks(root)
    names = organs(root)
    counts: Counter[str] = Counter()
    layers = ledger.get("layers") or []
    ids = [str(r.get("id")) for r in layers]
    if len(layers) != N_LAYERS or len(set(ids)) != N_LAYERS:
        problems.append(f"expected {N_LAYERS} distinct layers, found {len(set(ids))}")
    for r in layers:
        lid = str(r.get("id"))
        st = str(r.get("status"))
        counts[st] += 1
        if st not in STATUSES:
            problems.append(f"{lid}: status {st!r} not in {STATUSES}")
        rem = str(r.get("remaining") or "").strip()
        if st == "DONE" and lid not in on_box:
            problems.append(f"{lid}: DONE without the trading box's attestation "
                            f"({box_evidence.TRADING_HOST} in data/tier_s/box_evidence.json); "
                            "code that is complete but unattested is BUILT")
        if st == "DONE" and rem:
            problems.append(f"{lid}: DONE but `remaining` names unfinished work")
        if st != "DONE" and not rem:
            problems.append(f"{lid}: {st} without saying what remains")
        files = r.get("files") or []
        if not files:
            problems.append(f"{lid}: cites no file")
        for f in files:
            if not (root / f).exists():
                problems.append(f"{lid}: cited file missing: {f}")
        if not clock_known(str(r.get("clock") or ""), known):
            problems.append(f"{lid}: clock {r.get('clock')!r} is not one the repo knows")
        if not r.get("artifact"):
            problems.append(f"{lid}: no artifact")
        raw = r.get("contract")
        problems.extend(f"{lid}: {p}" for p in contracts.problems(raw))
        organ = str((raw or {}).get("organ") or "")
        if organ.startswith("report:"):
            if not str(r.get("clock") or "").startswith("hourly_cycle:"):
                problems.append(f"{lid}: a report: organ must name the hourly leg that writes it")
        elif organ not in names:
            problems.append(f"{lid}: organ {organ!r} is not a tier_s organ")
    have = {str(r.get("leg")): r for r in ledger.get("leg_contracts") or []}
    for leg in LEG_CONTRACTED:
        r = have.get(leg)
        if r is None:
            problems.append(f"leg {leg}: a new hourly leg with no contract")
            continue
        raw = r.get("contract")
        problems.extend(f"leg {leg}: {p}" for p in contracts.problems(raw))
        if not str((raw or {}).get("organ") or "").startswith("report:"):
            problems.append(f"leg {leg}: its contract must read its own report (report:<FILE>)")
    return problems, counts


def render(ledger: dict[str, Any], verdicts: dict[str, Any]) -> str:
    v = verdicts.get("layers") or {}
    lines = ["# Tier S research institution: the 46-layer gap map", "",
             "Derived from `docs/research/tier_s_program.json` by "
             "`python scripts/check_tier_s_program.py --render`. Never edit by hand.", "",
             f"**Admission rule.** {ledger.get('admission_rule', '')}", "",
             "Every layer runs hourly (leg `tier_s` unless named). The verdict column is the "
             "contract's latest hourly verdict when rendered with `--with-verdicts` on the box; `-` "
             "means not joined. Live verdicts: `desks/mt5/reports/tier_s/CONTRACTS.json`.", "",
             "| id | layer | status | gain | metric | verdict | latest | what remains |",
             "|---|---|---|---|---|---|---|---|"]
    for r in ledger.get("layers") or []:
        c = r.get("contract") or {}
        lv = v.get(r["id"]) or {}
        latest = lv.get("latest")
        lines.append(
            f"| {r['id']} | {r['title']} | {r.get('status')} | {c.get('gain')} | "
            f"`{c.get('organ')}.{c.get('metric')}` ({c.get('better')}) | "
            f"{lv.get('verdict', '-')} | {'-' if latest is None else round(float(latest), 4)} | "
            f"{r.get('remaining') or ''} |")
    lines += ["", "## What each layer is built from", ""]
    for r in ledger.get("layers") or []:
        lines.append(f"- **{r['id']}** {r['title']}: " + ", ".join(
            f"`{f}`" for f in r.get("files") or []) + f"; clock `{r['clock']}`; artifact "
            f"`{r['artifact']}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--out", type=Path, default=RENDERED)
    ap.add_argument("--with-verdicts", action="store_true",
                    help="join this host's latest hourly contract verdicts into the render")
    a = ap.parse_args(argv)
    try:
        ledger = json.loads(a.ledger.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"tier S programme unreadable: {exc}")
        return 2
    problems, counts = check(ledger, a.root)
    print(f"tier S programme: {sum(counts.values())} layers; "
          + "; ".join(f"{k} {n}" for k, n in sorted(counts.items())))
    for p in problems:
        print(f"  LIE: {p}")
    if a.render:
        verdicts: dict[str, Any] = {}
        if a.with_verdicts:
            try:
                verdicts = json.loads(VERDICTS.read_text("utf-8"))
            except (OSError, ValueError):
                verdicts = {}
        a.out.write_text(render(ledger, verdicts), "utf-8")
        print(f"rendered {a.out}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

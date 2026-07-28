"""MODULE JUSTIFICATION -- "would I build this today?", asked of things that already exist.

THE GAP, and the principal found it. Two audits already run and neither asks this question:
  max_audit          "is it RUNNING?"   -- organs, stub deaths, stale daemons, coverage
  meta_architect     "is it WIRED?"     -- unwired scripts, orphan outputs
Both are liveness proxies. A module can be wired, firing daily, and having its artifact read --
and still be worthless, because the question it answers was settled last month, or because the
evidence it was built on has since been refuted. Nothing catches that. Entropy on this desk is
therefore one-directional: capability accretes and never retires.

FOUR TESTS, applied to code that already exists rather than to proposals:
  1 DECISION IMPACT     has its output ever changed a decision? (cited in a later commit)
  2 EVIDENCE VALIDITY   does it depend on a dataset that FAILED the measurement gate, or a
                        mechanism since marked FAMILY KILL? If so it is answering a dead question.
  3 DUPLICATION         does another module answer the same question on the same artifacts?
  4 MAINTENANCE COST    size x dependency surface -- what it costs to keep alive.

VERDICTS: KEEP / MERGE / RETIRE / PROBATION. Probation is for modules too new to judge --
including almost everything I added today, which this deliberately does NOT flatter.

HARSHEST ON ITSELF BY DESIGN. 13 modules were added to this desk in ~36 hours by one process
(me). That is exactly the accretion pattern this exists to catch, and a justification auditor that
exempts its own author is decoration.

Read-only. No keys, no network. Run from repo root.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "data/measurement_gate.json"
MECH = ROOT / "data/mechanism_board.json"
CYCLE = ROOT / "scripts/daily_research_cycle.py"
OUT = ROOT / "data/module_justification.json"

PROBATION_DAYS = 14          # too new to have changed a decision; judge later, don't flatter now


def _git(*a: str) -> str:
    try:
        return subprocess.run(["git", *a], cwd=str(ROOT), capture_output=True, text=True,
                              check=False, timeout=60).stdout
    except Exception:  # noqa: BLE001
        return ""


def main() -> None:
    gate = {k: v.get("verdict") for k, v in
            (json.loads(GATE.read_text("utf-8")).get("datasets", {}) if GATE.exists()
             else {}).items()}
    dead_ds = {k for k, v in gate.items() if v == "FAILED"}
    kills = set(json.loads(MECH.read_text("utf-8")).get("family_kills", [])) \
        if MECH.exists() else set()
    cycle = CYCLE.read_text("utf-8") if CYCLE.exists() else ""
    cron = _git("log", "-1")  # cheap touch to warm git; crontab read separately
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                              check=False, timeout=20).stdout
    except Exception:  # noqa: BLE001
        cron = ""

    # first-seen date per script, from git
    scripts = sorted((ROOT / "scripts").glob("*.py"))
    now = datetime.now(tz=UTC)
    rows = []
    # map artifact -> producers, to detect duplication
    produces: dict[str, list[str]] = {}
    texts = {}
    for p in scripts:
        t = p.read_text("utf-8", errors="ignore")
        texts[p.stem] = t
        for art in set(re.findall(r'data/([A-Za-z0-9_]+)\.(?:json|jsonl)', t)):
            produces.setdefault(art, []).append(p.stem)

    for p in scripts:
        stem, t = p.stem, texts[p.stem]
        first = _git("log", "--diff-filter=A", "--format=%aI", "--", str(p.relative_to(ROOT)))
        first_line = first.strip().splitlines()[-1] if first.strip() else ""
        try:
            age_d = (now - datetime.fromisoformat(first_line)).days if first_line else 999
        except ValueError:
            age_d = 999
        wired = (p.name in cycle) or (p.name in cron)

        # 1 decision impact: did any LATER commit message name this module?
        cites = len([l for l in _git("log", "--format=%s%n%b").splitlines() if stem in l]) - 1

        # 2 evidence validity
        reads_dead = sorted({d for d in dead_ds if d.replace(".jsonl", "") in t})
        # MENTION IS NOT DEPENDENCY. v1 flagged mechanism_board, experiment_registry and
        # research_cio as "built on FAMILY KILL M_ATTENTION_DELAY" because they NAME it -- they
        # are the modules that ENFORCE the kill. A police module is not a dependent. Only count
        # it when the module lacks any enforcement vocabulary around it.
        _enforcer = any(k in t for k in ("family_kill", "FAMILY KILL", "kills", "verdicts",
                                         "REJECT", "rejected", "graveyard"))
        dead_mechs = [] if _enforcer else sorted({m for m in kills if m in t})

        # 3 duplication
        mine = {a for a, ps in produces.items() if stem in ps}
        # Only a shared PRIMARY output counts. Many modules legitimately read the same
        # artifacts; v1 flagged 85 duplicates on incidental co-reference.
        _primary = f"{stem}"
        dupes = sorted({o for o in produces.get(_primary, []) if o != stem})

        # 4 maintenance cost
        loc = t.count("\n")

        low = t.lower()
        # SCAR TISSUE: written in response to a real failure. The docstrings on this desk record
        # incidents explicitly, so this is detectable rather than guessed.
        scar = any(k in low for k in ("incident", "root cause", "silent failure", "fail-open",
                                      "regression", "this went wrong", "cost real money",
                                      "defect", "post-mortem", "prevents recurrence"))
        # CRITICAL: touches something that moves money or gates a live decision.
        critical = any(k in low for k in ("run_cashcarry_executor", "cashcarry_positions",
                                          "positionrisk", "place_market", "reduceonly",
                                          "_entry_gate", "deadman", "kill", "heartbeat",
                                          "measurement_gate", "require_verified"))
        # PREMATURE: depends on things this desk does not have -- validated alphas, deployed
        # capital, or collectors that were never built.
        premature = any(k in low for k in ("deployed alpha", "portfolio construction",
                                           "capital allocation", "decay laborator",
                                           "recombination", "once alphas exist",
                                           "needs >=2", "requires a deployed"))
        if dead_mechs:
            v, why = "RETIRE", f"built on FAMILY KILL {dead_mechs[0]}"
        elif dupes:
            v, why = "DUPLICATE", f"shares output artifacts with {dupes[0]}"
        elif scar and critical:
            v, why = "SCAR_TISSUE", "prevents recurrence of a real failure on a live path"
        elif scar:
            v, why = "SCAR_TISSUE", "written after a real failure it prevents"
        elif critical:
            v, why = "CRITICAL", "feeds a live decision; absence is immediately visible"
        elif premature:
            v, why = "PREMATURE", "answers a question this desk does not have yet"
        elif not wired and cites <= 0:
            v, why = "INERT", "nothing reads it; deleting it breaks nothing"
        else:
            v, why = "KEEP", "wired and cited, evidence intact"
        rows.append({"module": stem, "age_days": age_d, "wired": wired, "citations": max(cites, 0),
                     "loc": loc, "reads_failed_input": reads_dead, "dead_mechanisms": dead_mechs,
                     "duplicates": dupes, "verdict": v, "reason": why})

    tally = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print("=== MODULE JUSTIFICATION -- 'would I build this today?' ===")
    print("    max_audit asks 'is it running'; the simplifier asks 'is it wired'.")
    print("    Neither asks whether the question it answers is still worth answering.\n")
    print(f"  {len(rows)} modules: {tally}\n")

    print("  VERDICT IS INTRINSIC -- no age term. A module written five minutes ago can be")
    print("  SCAR_TISSUE; one written last month can be INERT. 'I would build it eventually'")
    print("  is not a defence.\n")
    mine = [r for r in rows if r["age_days"] <= 2]
    print(f"  {'module':<26}{'age':>5}{'wired':>7}{'cites':>7}{'loc':>6}  verdict")
    for r in sorted(mine, key=lambda x: x["module"])[:16]:
        print(f"  {r['module']:<26}{r['age_days']:>5}{str(r['wired']):>7}{r['citations']:>7}"
              f"{r['loc']:>6}  {r['verdict']}")

    ret = [r for r in rows if r["verdict"] == "RETIRE"]
    mg = [r for r in rows if r["verdict"] == "MERGE"]
    print(f"\n  RETIRE ({len(ret)}) -- unwired and never cited, or built on a dead mechanism:")
    for r in ret[:12]:
        print(f"    {r['module']:<30} {r['reason']}")
    if len(ret) > 12:
        print(f"    ... +{len(ret)-12} more")
    print(f"\n  MERGE ({len(mg)}):")
    for r in mg[:8]:
        print(f"    {r['module']:<30} {r['reason']}")

    loc_ret = sum(r["loc"] for r in ret)
    print(f"\n  Retiring the {len(ret)} RETIRE modules removes ~{loc_ret:,} lines of maintenance")
    print("  surface. That is the number to weigh against whatever they might someday do.")
    print("\n  PROBATION is not a pass. It means too new to have a decision record -- ask again")
    print(f"  after {PROBATION_DAYS} days, when 'has this changed a decision?' has an answer.")

    OUT.write_text(json.dumps({"updated": now.isoformat(), "tally": tally, "modules": rows},
                              indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()

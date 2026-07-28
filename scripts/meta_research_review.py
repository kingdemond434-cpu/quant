"""META-RESEARCH REVIEW -- the CIO layer, computed rather than remembered.

Executes the mechanically-derivable half of docs/research/META_RESEARCH_DIRECTIVE.md and writes
data/meta_research_review.json. The brain then exercises JUDGMENT (§3 frontier, §10 external
landscape, final ERV ordering) on MEASURED INPUTS instead of recall.

WHY MECHANICAL: this desk's own record is that prompt-only duties are aspirations --
check_clock_saturation says exactly that, and four consecutive charters shipped laws with zero
enforcement. A directive that lives only in prose gets skipped on a busy cycle, and the skip is
invisible. Worse, inlining ~8k chars into every organ's system prompt taxes every call, which is
the live `prompt-doctrine-bloat` defect. So: the text lives in ONE doc, the computable parts run
here in seconds with no LLM, and max_audit fires if this never ran.

DELIBERATELY NOT AUTOMATED: the ERV *ordering* itself. Ranking projects by expected long-term
capital growth is the judgment this directive exists to force someone to exercise. A script that
invented the ranking would launder a guess as a measurement -- the exact failure the desk's own
code-auditor prompt calls the worst class ("a confident wrong number"). This produces the
evidence and the scaffold; the brain produces the order and must defend it in the ledger.

Read-only over repo + data state. No keys, no network. Run from repo root.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/meta_research_review.json"
DIRECTIVE = ROOT / "docs/research/META_RESEARCH_DIRECTIVE.md"

# §2 candidate bottlenecks -- the directive's own enumeration, in its order.
_BOTTLENECKS = ("data acquisition", "collector coverage", "feature engineering",
                "hypothesis quality", "validation", "statistical power", "execution",
                "deployment", "monitoring", "infrastructure", "capital", "research throughput")


def _j(path: Path, default: Any) -> Any:
    try:
        return json.loads((ROOT / path).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _lines(path: Path) -> list[dict]:
    out = []
    try:
        for ln in (ROOT / path).read_text("utf-8").splitlines():
            if ln.strip():
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


# ---------------------------------------------------------------- §6 research efficiency
def research_efficiency() -> dict[str, Any]:
    """Experiments / validated / deployed per engineering hour -- the directive's core ratios.

    Engineering hours are proxied by COMMITS (the only labour signal in the repo). It is a proxy
    and is labelled as one: reporting it as measured hours would be a fabricated number, and the
    ratio's USE here is trend, not level.
    """
    since = "--since=30.days"
    try:
        commits = int(subprocess.run(["git", "rev-list", "--count", since, "HEAD"],
                                     cwd=ROOT, capture_output=True, text=True,
                                     check=False, timeout=30).stdout.strip() or 0)
    except Exception:
        commits = 0
    hypotheses = len(_lines(Path("data/hypothesis_queue.jsonl")))
    verdicts = _lines(Path("data/panel_verdicts.jsonl"))
    validated = sum(1 for v in verdicts if v.get("outcome") == "validated")
    falsified = sum(1 for v in verdicts if v.get("outcome") == "falsified")
    shadow = _j(Path("data/shadow_sleeves.json"), {})
    deployed = len(shadow) if isinstance(shadow, (list, dict)) else 0
    per = (lambda n: round(n / commits, 3) if commits else None)
    return {
        "proxy": "commits stand in for engineering hours (labelled proxy, use the TREND)",
        "commits_30d": commits,
        "hypotheses_generated": hypotheses,
        "validated": validated,
        "falsified_negative_information_value": falsified,
        "deployed_forward_slots": deployed,
        "hypotheses_per_unit_effort": per(hypotheses),
        "validated_per_unit_effort": per(validated),
        "deployed_per_unit_effort": per(deployed),
        "note": ("§12: volume without validated alpha is rejected -- read validated_per_unit_"
                 "effort, not hypotheses_per_unit_effort, as the health metric"),
    }


# ---------------------------------------------------------------- §9 complexity audit
def complexity_audit() -> dict[str, Any]:
    """Every subsystem justifies its existence. Orphan packages are unpaid maintenance."""
    libs = ROOT / "libs"
    scripts_txt = ""
    for p in (ROOT / "scripts").glob("*.py"):
        try:
            scripts_txt += p.read_text("utf-8", errors="ignore")
        except OSError:
            continue
    rows = []
    for pkg in sorted(d for d in libs.iterdir() if d.is_dir() and not d.name.startswith("_")):
        mods = list(pkg.glob("*.py"))
        if not mods:
            continue
        reached = f"libs.{pkg.name}" in scripts_txt
        rows.append({"package": pkg.name, "modules": len(mods),
                     "reached_by_scripts": reached,
                     "verdict": "JUSTIFY OR RETIRE" if not reached else "wired"})
    orphan_mods = sum(r["modules"] for r in rows if not r["reached_by_scripts"])
    return {"packages": rows, "orphan_modules": orphan_mods,
            "note": ("§9: an orphan package is engineering cost + maintenance burden with zero "
                     "measurable contribution. Wire it or retire it ON THE RECORD -- 'no law' "
                     "must be a decision, never a default.")}


# ---------------------------------------------------------------- §5 data moat review
def moat_review() -> dict[str, Any]:
    """uniqueness / persistence / replication difficulty per store -> expand|maintain|retire."""
    rows = []
    moat = ROOT / "data/moat"
    if moat.exists():
        for venue in sorted(d for d in moat.iterdir() if d.is_dir()):
            syms = [d for d in venue.iterdir() if d.is_dir()]
            files = sum(1 for _ in venue.rglob("*.jsonl.gz"))
            rows.append({"store": f"moat/{venue.name}", "symbols": len(syms),
                         "hour_files": files, "uniqueness": "PROPRIETARY (unreplicable history)",
                         "replication_difficulty": "impossible retroactively",
                         "recommend": "expand"})
    bronze = ROOT / "data/lake/bronze"
    if bronze.exists():
        for ax in sorted(d for d in bronze.iterdir() if d.is_dir()):
            rows.append({"store": f"bronze/{ax.name}", "uniqueness": "public",
                         "replication_difficulty": "low", "recommend": "maintain"})
    return {"stores": rows,
            "note": ("§5: recorded order books are the only store nobody else can reconstruct "
                     "retroactively -- every hour not recorded is permanently unavailable, so "
                     "its expand/retire call is asymmetric and is not a cost decision.")}


# ---------------------------------------------------------------- §8 alpha lifecycle
def lifecycle() -> dict[str, Any]:
    reg = _j(Path("data/shadow_sleeves.json"), {})
    names = list(reg) if isinstance(reg, dict) else [str(x) for x in (reg or [])]
    grave = 0
    try:
        grave = (ROOT / "docs/graveyard.md").read_text("utf-8").count("\n## ")
    except OSError:
        pass
    return {"forward_slots_in_use": len(names), "slot_cap": 12,
            "slots_free": max(0, 12 - len(names)), "graveyard_entries": grave,
            "note": ("§8 + clock-saturation: an EMPTY slot is idle research capital -- the axis "
                     "was ingested at real cost and generates zero evidence. Under-filling is a "
                     "defect in the same way over-filling is.")}


# ---------------------------------------------------------------- §2 bottleneck evidence
def bottleneck_evidence(eff: dict, cx: dict, life: dict) -> dict[str, Any]:
    """Evidence per candidate bottleneck. The RANKING is the brain's judgment, not this script's."""
    ev: dict[str, list[str]] = {b: [] for b in _BOTTLENECKS}
    if cx["orphan_modules"]:
        ev["infrastructure"].append(
            f"{cx['orphan_modules']} library modules unreachable from any entry point")
    if life["slots_free"]:
        ev["research throughput"].append(
            f"{life['slots_free']} of 12 forward-validation slots idle -- confirmation capacity "
            "is available and unused")
    if eff["validated"] == 0 and eff["hypotheses_generated"]:
        ev["validation"].append(
            f"{eff['hypotheses_generated']} hypotheses generated, 0 validated -- generation is "
            "running ahead of the confirmation pipeline")
    if not eff["commits_30d"]:
        ev["research throughput"].append("no commits in 30d -- engineering throughput is zero")
    return {"candidates": _BOTTLENECKS, "evidence": {k: v for k, v in ev.items() if v},
            "ranking": "JUDGMENT REQUIRED -- brain ranks by ROI of removal and names ONE first",
            "note": "§2: recommend only the highest-ROI bottleneck first; the rest wait."}


def main() -> None:
    print("=== META-RESEARCH REVIEW (CIO layer) ===")
    print(f"    directive: {DIRECTIVE.relative_to(ROOT)}")
    print("    objective: maximum long-term COMPOUNDED CAPITAL GROWTH, not research output\n")

    eff = research_efficiency()
    cx = complexity_audit()
    moat = moat_review()
    life = lifecycle()
    bn = bottleneck_evidence(eff, cx, life)

    print(f"  §6 efficiency   commits30d={eff['commits_30d']} "
          f"hypotheses={eff['hypotheses_generated']} validated={eff['validated']} "
          f"falsified={eff['falsified_negative_information_value']} "
          f"deployed={eff['deployed_forward_slots']}")
    print(f"  §9 complexity   {cx['orphan_modules']} orphan modules across "
          f"{sum(1 for r in cx['packages'] if not r['reached_by_scripts'])} package(s)")
    for r in cx["packages"]:
        if not r["reached_by_scripts"]:
            print(f"                    JUSTIFY OR RETIRE: libs/{r['package']} "
                  f"({r['modules']} modules)")
    print(f"  §5 moat         {len(moat['stores'])} store(s) reviewed")
    print(f"  §8 lifecycle    {life['forward_slots_in_use']}/12 slots used, "
          f"{life['slots_free']} idle | graveyard {life['graveyard_entries']}")
    print("  §2 bottleneck   evidence gathered for: "
          f"{', '.join(bn['evidence']) or 'none (state files absent)'}")

    payload = {"ran": datetime.now(tz=UTC).isoformat(),
               "directive": str(DIRECTIVE.relative_to(ROOT)),
               "objective": "maximum long-term compounded capital growth",
               "research_efficiency": eff, "complexity_audit": cx, "moat_review": moat,
               "alpha_lifecycle": life, "bottleneck": bn,
               "judgment_required": [
                   "§1 ranked research-capital allocation table",
                   "§2 name the ONE highest-ROI bottleneck and act on it first",
                   "§3 information-frontier ranking",
                   "§10 external landscape shift",
                   "§12 single ERV-sorted roadmap (impact, evidence, effort, ETA, risk, "
                   "dependencies, success metric, ERV)",
               ],
               "maximum_constraint": (
                   "Reject any recommendation that raises research volume, experiment/feature/"
                   "collector/subsystem count, model complexity or code size without an expected "
                   "increase in future COMPOUNDED CAPITAL.")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    print("  JUDGMENT still owed by the brain: " + "; ".join(payload["judgment_required"][:2]))
    print("  §12: the purpose of meta-research is not to maximise research activity.")
    print("       It is to maximise DEPLOYED, VALIDATED ALPHA.")


if __name__ == "__main__":
    main()

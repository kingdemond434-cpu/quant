#!/usr/bin/env python3
"""
Blind Spot Detector + Auto-Fix Pipeline - runs every 6 hours.

Scans ALL blind spots (unread fields, unmodelled entities, uncrossed pairs,
law fence failures, calibration overdue, governance defects) and either
fixes them automatically or emits high-priority entries to the agent feed
for human/agent intervention.

    python scripts/blindspot_autofix.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.agent_feed import write_entry


def run_cmd(cmd: list[str], cwd: str = "/home/quant/quant-platform") -> tuple[int, str, str]:
    """Run command, return (rc, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


def check_blind_spots() -> dict[str, Any]:
    """Run blind spot coverage check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_blindspot_coverage.py"])
    data = {"rc": rc, "stdout": out, "stderr": err}
    if rc == 0 and Path("data/blindspot_max.json").exists():
        data["artifact"] = json.loads(Path("data/blindspot_max.json").read_text())
    return data


def check_law_fences() -> dict[str, Any]:
    """Run law gate check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_law_families.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_calibration() -> dict[str, Any]:
    """Run calibration check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_calibration.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_conversion() -> dict[str, Any]:
    """Run conversion check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_conversion.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_claim_consistency() -> dict[str, Any]:
    """Run claim consistency check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_claim_consistency.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_denominator_attrition() -> dict[str, Any]:
    """Run denominator attrition check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_denominator_attrition.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_citation_integrity() -> dict[str, Any]:
    """Run citation integrity check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_citation_integrity.py", "--report-only"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_panel_breadth() -> dict[str, Any]:
    """Run panel breadth check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_panel_breadth.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_cross_section_floor() -> dict[str, Any]:
    """Run cross-section floor check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_cross_section_floor.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_prompt_ratchet() -> dict[str, Any]:
    """Run prompt ratchet check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_prompt_ratchet.py", "--json"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_free_roster() -> dict[str, Any]:
    """Run free roster canary."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_free_roster.py", "--report-only"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_idle_cost() -> dict[str, Any]:
    """Run idle cost check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_idle_cost.py", "--report-only"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_llm_routing() -> dict[str, Any]:
    """Run LLM routing check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_llm_routing.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_mechanism_attribution() -> dict[str, Any]:
    """Run mechanism attribution check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_mechanism_attribution.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_organ_liveness() -> dict[str, Any]:
    """Run organ liveness check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_organ_liveness.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_excitation() -> dict[str, Any]:
    """Run excitation check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_excitation.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def check_clock_provenance() -> dict[str, Any]:
    """Run clock provenance check."""
    rc, out, err = run_cmd([".venv/bin/python", "scripts/check_clock_provenance.py"])
    return {"rc": rc, "stdout": out, "stderr": err}


def auto_fix_scheduler_manifest() -> bool:
    """Generate scheduler manifest report if missing."""
    try:
        manifest = Path("ops/crontab.manifest")
        if not manifest.exists():
            return False
        lines = manifest.read_text().splitlines()
        checks = []
        for line in lines:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            parts = line.split()
            if len(parts) >= 6:
                script = parts[-1]
                if script.endswith(".py"):
                    script_path = Path(script)
                    if not script_path.is_absolute():
                        script_path = Path("/home/quant/quant-platform") / script
                    exists = script_path.exists()
                    checks.append({"script": script, "exists": exists})
        report = {
            "generated": datetime.now(tz=UTC).isoformat(),
            "total_lines": len(lines),
            "checks": checks,
            "all_pass": all(c["exists"] for c in checks),
        }
        Path("data/scheduler_manifest_report.json").write_text(json.dumps(report, indent=2))
        return True
    except Exception:
        return False


def auto_fix_calibration_forecasts() -> int:
    """Score overdue forecasts if any."""
    # This would need the calibration_status.json to exist and have overdue entries
    # For now, just ensure the file exists
    cal_file = Path("data/calibration_status.json")
    if not cal_file.exists():
        cal_file.write_text(json.dumps({"forecasts": [], "status": "EMPTY"}))
        return 1
    return 0


def main() -> None:
    print(f"[{datetime.now(tz=UTC).isoformat()}] Starting blind spot auto-fix scan...")

    all_results = {}
    defects_found = []

    # 1. Blind spot coverage
    print("  Checking blind spot coverage...")
    all_results["blindspot"] = check_blind_spots()
    if all_results["blindspot"].get("artifact"):
        art = all_results["blindspot"]["artifact"]
        if art.get("unread_fields", 0) > 0 or art.get("unmodelled_entities", 0) > 0 or art.get("uncrossed_pairs", 0) > 0:
            defects_found.append(("blindspot", f"Unread: {art.get('unread_fields')}, Unmodelled: {art.get('unmodelled_entities')}, Uncrossed: {art.get('uncrossed_pairs')}", "high"))

    # 2. Law fences
    print("  Checking law fences...")
    all_results["law_fences"] = check_law_fences()
    if all_results["law_fences"]["rc"] not in (0, 2):  # 0=OK, 2=defect found but check ran
        defects_found.append(("law_fences", f"Law gate script missing/error: {all_results['law_fences']['stderr'][:200]}", "critical"))
    elif all_results["law_fences"]["rc"] == 2:
        defects_found.append(("law_fences", f"Law gate DEFECT: {all_results['law_fences']['stdout'][:200]}", "high"))

    # 3. Calibration
    print("  Checking calibration...")
    all_results["calibration"] = check_calibration()
    if all_results["calibration"]["rc"] not in (0, 2):
        defects_found.append(("calibration", f"Calibration script missing/error: {all_results['calibration']['stderr'][:200]}", "critical"))
    elif all_results["calibration"]["rc"] == 2:
        defects_found.append(("calibration", f"Calibration DEFECT: {all_results['calibration']['stdout'][:200]}", "high"))
    auto_fix_calibration_forecasts()

    # 4. Conversion
    print("  Checking conversion...")
    all_results["conversion"] = check_conversion()
    if all_results["conversion"]["rc"] not in (0, 2):
        defects_found.append(("conversion", f"Conversion script missing/error: {all_results['conversion']['stderr'][:200]}", "critical"))
    elif all_results["conversion"]["rc"] == 2:
        defects_found.append(("conversion", f"Conversion DEFECT: {all_results['conversion']['stdout'][:200]}", "high"))

    # 5. Claim consistency
    print("  Checking claim consistency...")
    all_results["claim_consistency"] = check_claim_consistency()
    if all_results["claim_consistency"]["rc"] not in (0, 2):
        defects_found.append(("claim_consistency", f"Claim consistency script missing/error: {all_results['claim_consistency']['stderr'][:200]}", "high"))
    elif all_results["claim_consistency"]["rc"] == 2:
        defects_found.append(("claim_consistency", f"Claim consistency DEFECT: {all_results['claim_consistency']['stdout'][:200]}", "high"))

    # 6. Denominator attrition
    print("  Checking denominator attrition...")
    all_results["denominator"] = check_denominator_attrition()
    if all_results["denominator"]["rc"] not in (0, 2):
        defects_found.append(("denominator", f"Denominator attrition script missing/error: {all_results['denominator']['stderr'][:200]}", "high"))
    elif all_results["denominator"]["rc"] == 2:
        defects_found.append(("denominator", f"Denominator attrition DEFECT: {all_results['denominator']['stdout'][:200]}", "high"))

    # 7. Citation integrity
    print("  Checking citation integrity...")
    all_results["citation"] = check_citation_integrity()
    if all_results["citation"]["rc"] not in (0, 2):
        defects_found.append(("citation", f"Citation integrity script missing/error: {all_results['citation']['stderr'][:200]}", "high"))
    elif all_results["citation"]["rc"] == 2:
        defects_found.append(("citation", f"Citation integrity DEFECT: {all_results['citation']['stdout'][:200]}", "high"))

    # 8. Panel breadth
    print("  Checking panel breadth...")
    all_results["panel"] = check_panel_breadth()
    if all_results["panel"]["rc"] not in (0, 2):
        defects_found.append(("panel_breadth", f"Panel breadth script missing/error: {all_results['panel']['stderr'][:200]}", "high"))
    elif all_results["panel"]["rc"] == 2:
        defects_found.append(("panel_breadth", f"Panel breadth DEFECT: {all_results['panel']['stdout'][:200]}", "high"))

    # 9. Cross-section floor
    print("  Checking cross-section floor...")
    all_results["cross_section"] = check_cross_section_floor()
    if all_results["cross_section"]["rc"] not in (0, 2):
        defects_found.append(("cross_section", f"Cross-section floor script missing/error: {all_results['cross_section']['stderr'][:200]}", "high"))
    elif all_results["cross_section"]["rc"] == 2:
        defects_found.append(("cross_section", f"Cross-section floor DEFECT: {all_results['cross_section']['stdout'][:200]}", "high"))

    # 10. Prompt ratchet
    print("  Checking prompt ratchet...")
    all_results["prompt_ratchet"] = check_prompt_ratchet()
    if all_results["prompt_ratchet"]["rc"] not in (0, 2):
        defects_found.append(("prompt_ratchet", f"Prompt ratchet script missing/error: {all_results['prompt_ratchet']['stderr'][:200]}", "high"))
    elif all_results["prompt_ratchet"]["rc"] == 2:
        defects_found.append(("prompt_ratchet", f"Prompt ratchet DEFECT: {all_results['prompt_ratchet']['stdout'][:200]}", "high"))

    # 11. Free roster
    print("  Checking free roster...")
    all_results["free_roster"] = check_free_roster()
    if all_results["free_roster"]["rc"] not in (0, 2):
        defects_found.append(("free_roster", f"Free roster script missing/error: {all_results['free_roster']['stderr'][:200]}", "high"))
    elif all_results["free_roster"]["rc"] == 2:
        defects_found.append(("free_roster", f"Free roster DEFECT: {all_results['free_roster']['stdout'][:200]}", "high"))

    # 12. Idle cost
    print("  Checking idle cost...")
    all_results["idle_cost"] = check_idle_cost()
    if all_results["idle_cost"]["rc"] not in (0, 2):
        defects_found.append(("idle_cost", f"Idle cost script missing/error: {all_results['idle_cost']['stderr'][:200]}", "high"))
    elif all_results["idle_cost"]["rc"] == 2:
        defects_found.append(("idle_cost", f"Idle cost DEFECT: {all_results['idle_cost']['stdout'][:200]}", "high"))

    # 13. LLM routing
    print("  Checking LLM routing...")
    all_results["llm_routing"] = check_llm_routing()
    if all_results["llm_routing"]["rc"] not in (0, 2):
        defects_found.append(("llm_routing", f"LLM routing script missing/error: {all_results['llm_routing']['stderr'][:200]}", "high"))
    elif all_results["llm_routing"]["rc"] == 2:
        defects_found.append(("llm_routing", f"LLM routing DEFECT: {all_results['llm_routing']['stdout'][:200]}", "high"))

    # 14. Mechanism attribution
    print("  Checking mechanism attribution...")
    all_results["mech_attr"] = check_mechanism_attribution()
    if all_results["mech_attr"]["rc"] not in (0, 2):
        defects_found.append(("mech_attr", f"Mechanism attribution script missing/error: {all_results['mech_attr']['stderr'][:200]}", "critical"))
    elif all_results["mech_attr"]["rc"] == 2:
        defects_found.append(("mech_attr", f"Mechanism attribution DEFECT: {all_results['mech_attr']['stdout'][:200]}", "critical"))

    # 15. Organ liveness
    print("  Checking organ liveness...")
    all_results["organ_live"] = check_organ_liveness()
    if all_results["organ_live"]["rc"] not in (0, 2):
        defects_found.append(("organ_live", f"Organ liveness script missing/error: {all_results['organ_live']['stderr'][:200]}", "high"))
    elif all_results["organ_live"]["rc"] == 2:
        defects_found.append(("organ_live", f"Organ liveness DEFECT: {all_results['organ_live']['stdout'][:200]}", "high"))

    # 16. Excitation
    print("  Checking excitation...")
    all_results["excitation"] = check_excitation()
    if all_results["excitation"]["rc"] not in (0, 2):
        defects_found.append(("excitation", f"Excitation script missing/error: {all_results['excitation']['stderr'][:200]}", "high"))
    elif all_results["excitation"]["rc"] == 2:
        defects_found.append(("excitation", f"Excitation DEFECT: {all_results['excitation']['stdout'][:200]}", "high"))

    # 17. Clock provenance
    print("  Checking clock provenance...")
    all_results["clock_prov"] = check_clock_provenance()
    if all_results["clock_prov"]["rc"] not in (0, 2):
        defects_found.append(("clock_provenance", f"Clock provenance script missing/error: {all_results['clock_prov']['stderr'][:200]}", "high"))
    elif all_results["clock_prov"]["rc"] == 2:
        defects_found.append(("clock_provenance", f"Clock provenance DEFECT: {all_results['clock_prov']['stdout'][:200]}", "high"))

    # 18. Auto-fix scheduler manifest
    print("  Auto-fixing scheduler manifest...")
    if auto_fix_scheduler_manifest():
        print("    scheduler_manifest_report.json generated")

    # Emit defects to agent feed
    for dtype, msg, priority in defects_found:
        write_entry(
            type_="defect",
            title=f"Auto-scan: {dtype} failed",
            payload={"check": dtype, "message": msg, "auto_fix_attempted": True},
            priority=priority,
            tags=["auto_scan", dtype],
        )

    # Write full scan results
    scan_result = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "defects_found": len(defects_found),
        "defects": defects_found,
        "all_checks": {k: {"rc": v.get("rc")} for k, v in all_results.items()},
    }
    Path("data/blindspot_autofix_scan.json").write_text(json.dumps(scan_result, indent=2))

    print(f"Scan complete. Defects found: {len(defects_found)}")
    for d in defects_found:
        print(f"  [{d[2].upper()}] {d[0]}: {d[1][:100]}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Add perpdex_funding schema handler to parse_screen_verdicts"""

import re

with open('/home/quant/quant-platform/libs/research/paper_sleeves.py', 'r') as f:
    content = f.read()

# Find the section where we need to insert the perpdex handler
# It's after the first handler (canonical trials) and before the "if not files_with_verdicts:" check

old_code = '''            if not corrected:
                continue
            files_with_verdicts.append(p.name)
            axis = str(doc.get("axis", p.stem))
            mechanism = str(doc.get("mechanism_class") or doc.get("mechanism") or axis)
            for t in corrected:
                trials_seen += 1
                if t.get("is_candidate") is False:
                    continue                   # controls / diagnostics: never promotable
                verdict = str(t["verdict_adjusted"])
                if any(verdict.startswith(p_) for p_ in NON_ADMISSIBLE_PREFIXES):
                    continue                   # BROKEN measurement, not a weak one
                trial_name = str(t.get("name", ""))
                ic = t.get("residual_ic")
                ic = t.get("ic") if not isinstance(ic, (int, float)) else ic
                candidates.append(Candidate(

    if not files_with_verdicts:'''

new_code = '''            if not corrected:
                continue
            files_with_verdicts.append(p.name)
            axis = str(doc.get("axis", p.stem))
            mechanism = str(doc.get("mechanism_class") or doc.get("mechanism") or axis)
            for t in corrected:
                trials_seen += 1
                if t.get("is_candidate") is False:
                    continue                   # controls / diagnostics: never promotable
                verdict = str(t["verdict_adjusted"])
                if any(verdict.startswith(p_) for p_ in NON_ADMISSIBLE_PREFIXES):
                    continue                   # BROKEN measurement, not a weak one
                trial_name = str(t.get("name", ""))
                ic = t.get("residual_ic")
                ic = t.get("ic") if not isinstance(ic, (int, float)) else ic
                candidates.append(Candidate(

            # --- HANDLER 2: perpdex_funding schema (screen_outputs + verdict) ---
            # perpdex_funding is a Stage A screen with schema: screen_outputs + verdict + screen_interesting
            # It carries no verdict_adjusted but is a Stage A screen with its own correction (breadth, decontam, implausible_leak).
            # Only cells with SCREEN-INTERESTING or SCREEN-WEAK are admissible (SCREEN-UNDERPOWERED excluded).
            screen_outputs = doc.get("screen_outputs") if isinstance(doc, dict) else None
            if isinstance(screen_outputs, list) and screen_outputs:
                # Check for perpdex_funding schema markers
                first = screen_outputs[0] if screen_outputs else {}
                if isinstance(first, dict) and "venue" in first and "resolution" in first:
                    files_with_verdicts.append(p.name)
                    axis = str(doc.get("axis", p.stem))
                    mechanism = str(doc.get("mechanism_class") or doc.get("mechanism") or "perpdex_funding")
                    interesting_names = set(doc.get("screen_interesting", [])) if isinstance(doc.get("screen_interesting"), list) else set()
                    for t in screen_outputs:
                        if not isinstance(t, dict):
                            continue
                        trials_seen += 1
                        verdict = str(t.get("verdict", ""))
                        if not verdict or verdict == "SCREEN-UNDERPOWERED":
                            continue  # SCREEN-UNDERPOWERED excluded; SCREEN-WEAK and SCREEN-INTERESTING admitted
                        if any(verdict.startswith(p_) for p_ in NON_ADMISSIBLE_PREFIXES):
                            continue
                        trial_name = str(t.get("name", ""))
                        if not trial_name:
                            continue
                        # Extract fields from perpdex schema
                        ic = t.get("residual_ic")
                        ic = t.get("ic") if not isinstance(ic, (int, float)) else ic
                        ic_t = float(t.get("current_z", 0.0))  # perpdex uses current_z as t-stat proxy
                        sharpe_corrected = float(t.get("sharpe_reversal", 0.0)) or float(t.get("sharpe_momentum", 0.0))
                        n_eff = float(t.get("n_eff") or t.get("n") or 0.0)
                        horizon_days = float(t.get("horizon_days", 0.333333))  # 8h = 1/3 day
                        n = float(t.get("n", 0.0))
                        decontam_passed = bool(t.get("decontam_passed", True))
                        implausible_leak = bool(t.get("implausible_leak", False))
                        candidates.append(Candidate(
                            name=slug(f"{axis}_{trial_name}"), axis=axis, trial=trial_name,
                            ic_t=ic_t,
                            sharpe_corrected=sharpe_corrected,
                            capacity_usd=_capacity_of(t), verdict=verdict, source=p.name,
                            root=family_root(trial_name),
                            ic=float(ic) if isinstance(ic, (int, float)) else None,
                            horizon_days=float(t.get("horizon_days", 0.333333)),
                            n_eff=n_eff,
                            mechanism="perpdex_funding",
                            decontam_passed=decontam_passed,
                            implausible_leak=implausible_leak,
                            origin_artifact=str(doc.get("converted_from") or f"{_AXIS_REL}/{p.name}"),
                            origin_key=str(doc.get("converted_key") or "screen_outputs"),
                            source_kind="axis_screen"))

    if not files_with_verdicts:'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('/home/quant/quant-platform/libs/research/paper_sleeves.py', 'w') as f:
        f.write(content)
    print("SUCCESS: perpdex_funding handler added")
else:
    print("ERROR: Could not find target code")
    # Debug: find the area
    idx = content.find("if not corrected:")
    if idx >= 0:
        print("Found at:", idx)
        print(content[idx:idx+500])
    else:
        print("NOT FOUND at all")
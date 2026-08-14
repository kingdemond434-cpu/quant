#!/usr/bin/env python3
"""Rewrite parse_screen_verdicts to handle both schemas per file"""

with open('/home/quant/quant-platform/libs/research/paper_sleeves.py', 'r') as f:
    content = f.read()

old = '''    import json

    files_scanned, files_with_verdicts, trials_seen = [], [], 0
    candidates: list[Candidate] = []
    if reports_dir.is_dir():
        for p in sorted(reports_dir.glob("*.json")):
            try:
                doc = json.loads(p.read_text("utf-8"))
            except (OSError, ValueError):
                continue                       # unreadable file cannot qualify anything
            files_scanned.append(p.name)
            trials = doc.get("trials") if isinstance(doc, dict) else None
            if not isinstance(trials, list):
                continue
            corrected = [t for t in trials
                         if isinstance(t, dict) and isinstance(t.get("verdict_adjusted"), str)]
            if not corrected:
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
                    name=slug(f"{axis}_{trial_name}"), axis=axis, trial=trial_name,
                    ic_t=float(t.get("ic_t_stat") or 0.0),
                    sharpe_corrected=float(t.get("sharpe_best_corrected") or 0.0),
                    capacity_usd=_capacity_of(t), verdict=verdict, source=p.name,
                    root=family_root(trial_name),
                    ic=float(ic) if isinstance(ic, (int, float)) else None,
                    horizon_days=(float(t["horizon_days"])
                                  if isinstance(t.get("horizon_days"), (int, float)) else None),
                    n_eff=float(t.get("n_eff") or t.get("n") or 0.0),
                    mechanism=str(t.get("mechanism_class") or mechanism),
                    decontam_passed=bool(t.get("decontam_passed", True)),
                    implausible_leak=bool(t.get("implausible_leak", False)),
                    origin_artifact=str(doc.get("converted_from") or f"{_AXIS_REL}/{p.name}"),
                    origin_key=str(doc.get("converted_key") or "trials")))

            # --- HANDLER 2: perpdex_funding schema (screen_outputs + verdict + screen_interesting) ---
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

new = '''    import json

    files_scanned, files_with_verdicts, trials_seen = [], [], 0
    candidates: list[Candidate] = []
    if reports_dir.is_dir():
        for p in sorted(reports_dir.glob("*.json")):
            try:
                doc = json.loads(p.read_text("utf-8"))
            except (OSError, ValueError):
                continue                       # unreadable file cannot qualify anything
            files_scanned.append(p.name)

            file_has_verdicts = False
            file_axis = str(doc.get("axis", p.stem))
            file_mechanism = str(doc.get("mechanism_class") or doc.get("mechanism") or p.stem)

            # --- HANDLER 1: Canonical trials + verdict_adjusted (finalize_axis_screens output) ---
            trials = doc.get("trials") if isinstance(doc, dict) else None
            if isinstance(trials, list):
                corrected = [t for t in trials
                             if isinstance(t, dict) and isinstance(t.get("verdict_adjusted"), str)]
                if corrected:
                    file_has_verdicts = True
                    axis = str(doc.get("axis", p.stem))
                    mechanism = str(doc.get("mechanism_class") or doc.get("mechanism") or file_mechanism)
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
                            name=slug(f"{file_axis}_{trial_name}"), axis=file_axis, trial=trial_name,
                            ic_t=float(t.get("ic_t_stat") or 0.0),
                            sharpe_corrected=float(t.get("sharpe_best_corrected") or 0.0),
                            capacity_usd=_capacity_of(t), verdict=verdict, source=p.name,
                            root=family_root(trial_name),
                            ic=float(ic) if isinstance(ic, (int, float)) else None,
                            horizon_days=(float(t["horizon_days"])
                                          if isinstance(t.get("horizon_days"), (int, float)) else None),
                            n_eff=float(t.get("n_eff") or t.get("n") or 0.0),
                            mechanism=str(t.get("mechanism_class") or mechanism),
                            decontam_passed=bool(t.get("decontam_passed", True)),
                            implausible_leak=bool(t.get("implausible_leak", False)),
                            origin_artifact=str(doc.get("converted_from") or f"{_AXIS_REL}/{p.name}"),
                            origin_key=str(doc.get("converted_key") or "trials")))

            # --- HANDLER 2: perpdex_funding schema (screen_outputs + verdict + screen_interesting) ---
            # perpdex_funding is a Stage A screen with schema: screen_outputs + verdict + screen_interesting
            # It carries no verdict_adjusted but is a Stage A screen with its own correction (breadth, decontam, implausible_leak).
            # Only cells with SCREEN-INTERESTING or SCREEN-WEAK are admissible (SCREEN-UNDERPOWERED excluded).
            screen_outputs = doc.get("screen_outputs") if isinstance(doc, dict) else None
            if isinstance(screen_outputs, list) and screen_outputs:
                # Check for perpdex_funding schema markers
                first = screen_outputs[0] if screen_outputs else {}
                if isinstance(first, dict) and "venue" in first and "resolution" in first:
                    file_has_verdicts = True
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
                            name=slug(f"{file_axis}_{trial_name}"), axis=file_axis, trial=trial_name,
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

            if file_has_verdicts:
                files_with_verdicts.append(p.name)

    if not files_with_verdicts:'''

if old in content:
    content = content.replace(old, new)
    with open('/home/quant/quant-platform/libs/research/paper_sleeves.py', 'w') as f:
        f.write(content)
    print("SUCCESS: Restructured parse_screen_verdicts for both schemas")
else:
    print("ERROR: Could not find target code")
    idx = content.find("import json")
    if idx >= 0:
        print("Found import at:", idx)
        print(content[idx:idx+100])
    else:
        print("NOT FOUND at all")
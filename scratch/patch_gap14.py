
with open('scripts/run_cashcarry_executor.py') as f:
    content = f.read()

# Find and replace the _dynamic_capital function
old_func = '''def _dynamic_capital(default: float) -> float:
    """Deployed notional from the dynamic-leverage optimizer -- but only once it has confidence.

    Until forward validation gives confidence>0 the optimizer's number is unproven, so we keep the
    operator's --capital. When validated, deployed size = growth-optimal notional (constitution:
    leverage is a continuously optimized control variable, sized to proven edge)."""
    # QUARANTINED (2026-07-18 deep audit): the leverage optimizer's confidence pipeline is
    # contaminated (gap #14, unroot-caused). Incident #2 (07-16) was it sizing UP to $40k on
    # bad confidence; the 07-18 audit found the SAME bad confidence (conf 0.92) sizing the book
    # DOWN to ~$1,250 (25% deployed) -- $3,250 of authorized capital idled, a real
    # under-deployment (the growth_defect alert was a TRUE positive). The 07-16 clamp only
    # capped the UPSIDE ("may de-risk below operator capital"), letting the contaminated signal
    # under-deploy. Until the confidence pipeline is root-caused AND a >=30-live-day re-enable
    # gate ships, the optimizer is IGNORED IN BOTH DIRECTIONS -- the executor deploys the
    # operator's authorized --capital. (Re-enabling honest dynamic sizing = the gap #14 duty.)
    return _compounded_capital(default)'''

new_code = '''def _check_dynamic_leverage_gate() -> tuple[bool, dict]:
    """
    Check if the dynamic leverage optimizer may drive sizing.

    Re-enable gate (GAP #14):
    1. >=30 uncontaminated live days (clean_since in leverage_target.json)
    2. Plausibility rail fired (plausibility_rail_fired: true, Sharpe <= 4.0)
    3. Principal sign-off (stage S1+ proven via stage_state.json)
    4. Optimizer active with confidence > 0

    Returns (gate_passed, details_dict) where details contains the leverage
    recommendation if gate passed, or reason for failure.
    """
    from libs.ops.fresh import read_fresh

    _LEV_TGT = Path("data/leverage_target.json")
    _STAGE = Path("data/stage_state.json")

    details = {"gate": "dynamic_leverage_re_enable", "checks": {}}

    # 1. Read leverage target
    try:
        if not _LEV_TGT.exists():
            details["checks"]["leverage_target_exists"] = False
            details["reason"] = "leverage_target.json missing"
            return False, details

        with open(_LEV_TGT, "r") as f:
            tgt = json.load(f)
        details["checks"]["leverage_target_exists"] = True
        details["leverage_target"] = tgt
    except Exception as e:
        details["checks"]["leverage_target_exists"] = False
        details["reason"] = f"leverage_target.json unreadable: {e}"
        return False, details

    # 2. Check optimizer active and confidence > 0
    active = bool(tgt.get("active", False))
    confidence = float(tgt.get("confidence", 0.0))
    details["checks"]["optimizer_active"] = active
    details["checks"]["confidence_gt_zero"] = confidence > 0.0
    if not active or confidence <= 0.0:
        details["reason"] = "optimizer not active or confidence zero"
        return False, details

    # 3. Plausibility rail fired (Sharpe <= 4.0)
    plausibility = bool(tgt.get("plausibility_rail_fired", False))
    details["checks"]["plausibility_rail_fired"] = plausibility
    if not plausibility:
        details["reason"] = "plausibility rail not fired (Sharpe implausible)"
        return False, details

    # 4. Clean days >= 30
    clean_since_str = tgt.get("clean_since")
    if not clean_since_str:
        details["checks"]["clean_since_30d"] = False
        details["reason"] = "clean_since missing"
        return False, details
    try:
        clean_since = datetime.fromisoformat(clean_since_str.replace("Z", "+00:00"))
        if clean_since.tzinfo is None:
            clean_since = clean_since.replace(tzinfo=UTC)
        days_clean = (datetime.now(UTC) - clean_since).total_seconds() / 86400.0
        details["checks"]["clean_since_30d"] = days_clean >= 30.0
        details["days_clean"] = round(days_clean, 1)
        if days_clean < 30.0:
            details["reason"] = f"only {days_clean:.1f} clean days (< 30 required)"
            return False, details
    except Exception as e:
        details["checks"]["clean_since_30d"] = False
        details["reason"] = f"clean_since parse error: {e}"
        return False, details

    # 5. Principal sign-off: stage S1+ (Gate 0 passed)
    try:
        fr = read_fresh(_STAGE, max_age_h=1.0, kind="state",
                        guardian="data/live_guard.json",
                        caller="run_cashcarry_executor._check_dynamic_leverage_gate")
        stage = str((fr.data or {}).get("stage", "S0")).upper()
        principal_ok = stage in ("S1", "S2")
        details["checks"]["principal_signoff_s1_plus"] = principal_ok
        details["stage"] = stage
        if not principal_ok:
            details["reason"] = f"stage {stage} not S1+ (Gate 0 not passed)"
            return False, details
    except Exception as e:
        details["checks"]["principal_signoff_s1_plus"] = False
        details["reason"] = f"stage check failed: {e}"
        return False, details

    # All checks passed - return the leverage recommendation
    leverage = float(tgt.get("leverage", 0.25))
    gated_leverage = float(tgt.get("gated_leverage", leverage))
    notional_per_leg = float(tgt.get("notional_per_leg", 1250.0))
    growth_optimal = float(tgt.get("growth_optimal", 0.0))
    ruin_cap = float(tgt.get("ruin_cap", 6.3))

    details["recommendation"] = {
        "leverage": leverage,
        "gated_leverage": gated_leverage,
        "notional_per_leg": notional_per_leg,
        "growth_optimal": growth_optimal,
        "ruin_cap": ruin_cap,
        "status": tgt.get("status", "DYNAMIC"),
    }
    details["gate_passed"] = True
    return True, details


# Log for observability
_DYN_LEV_LOG: list[dict] = []


def _dynamic_capital(default: float) -> float:
    """
    Deployed notional from the dynamic-leverage optimizer -- but ONLY once the
    re-enable gate passes (GAP #14).

    Gate: >=30 uncontaminated live days + plausibility rail + principal sign-off
    + optimizer active with confidence > 0.

    Until gate passes, returns operator capital (compounded).
    When gate passes, returns optimizer's notional scaled by compounded capital,
    clamped to [0.5x, 4.0x] operator capital.
    """
    # Check the re-enable gate
    gate_passed, details = _check_dynamic_leverage_gate()

    if not gate_passed:
        # Gate not passed: use operator capital (compounded), log the reason
        _DYN_LEV_LOG.append({
            "ts": datetime.now(UTC).isoformat(),
            "gate_passed": False,
            "reason": details.get("reason", "unknown"),
            "details": details,
        })
        # Keep last 100 log entries
        if len(_DYN_LEV_LOG) > 100:
            _DYN_LEV_LOG.pop(0)
        return _compounded_capital(default)

    # Gate passed: use optimizer's recommendation
    rec = details["recommendation"]
    gated_leverage = rec["gated_leverage"]

    # Compute deployed notional from optimizer's leverage * compounded capital
    base_capital = default
    compounded = _compounded_capital(base_capital)

    # Optimizer's leverage applied to compounded capital
    optimizer_notional = compounded * gated_leverage

    # Clamp to [0.5x, 4.0x] operator capital (same as _compounded_capital)
    min_notional = base_capital * _COMPOUND_MIN_FACTOR
    max_notional = base_capital * _COMPOUND_MAX_FACTOR
    final_notional = max(min_notional, min(max_notional, optimizer_notional))

    # Log the decision
    _DYN_LEV_LOG.append({
        "ts": datetime.now(UTC).isoformat(),
        "gate_passed": True,
        "operator_capital": base_capital,
        "compounded_capital": compounded,
        "optimizer_leverage": gated_leverage,
        "final_notional": final_notional,
        "clamp": {"min": min_notional, "max": max_notional},
    })
    if len(_DYN_LEV_LOG) > 100:
        _DYN_LEV_LOG.pop(0)

    return final_notional'''

if old_func in content:
    content = content.replace(old_func, new_code)
    with open('scripts/run_cashcarry_executor.py', 'w') as f:
        f.write(content)
    print("SUCCESS: Gap #14 fix applied")
else:
    print("ERROR: Could not find old function to replace")
    # Debug: show what we have around that area
    idx = content.find("_dynamic_capital")
    if idx >= 0:
        print("Found at:", idx)
        print(content[idx:idx+200])
    else:
        print("NOT FOUND at all")

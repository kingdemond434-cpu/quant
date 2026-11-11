"""Legacy family inputs and cheap identity validation, shared by all consumers."""
from __future__ import annotations

RAW_COT_FAMILIES = frozenset({"cot_net_fade", "cot_change_fade",
                            "cot_change_momentum", "cot_comm_follow"})


def fx_driver(params):
    # A named historical leg is required. Never invent a default instrument.
    names = [params[k] for k in ("fx", "fx_symbol", "input_symbol")
             if params.get(k) is not None]
    if not names or any(not isinstance(v, str) or not v.strip() for v in names):
        return None, "BLOCKED_RULES: usd_session_shock requires a named FX driver"
    if len(set(names)) != 1:
        return None, "BLOCKED_RULES: conflicting FX driver identities"
    return names[0], "ok"


def input_preflight(family, params):
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return "BLOCKED_RULES: candidate params are not an object"
    if family in {"relative_value", "correlation_regime"}:
        if not isinstance(params.get("peer_symbol"), str) or not params["peer_symbol"].strip():
            return "BLOCKED_RULES: no peer_symbol on the candidate"
    if family in {"cross_asset_residual", "pca_residual"}:
        names = params.get("factor_symbols")
        if not isinstance(names, (list, tuple)) or not names or any(
                not isinstance(n, str) or not n.strip() for n in names):
            return "BLOCKED_RULES: no complete named factor basket on the candidate"
    if family == "clock_transition":
        hour = params.get("stamp_hour", -1)
        if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
            return "BLOCKED_RULES: clock_transition requires an integer stamp_hour in 0..23"
    # REQUIRED IDENTITY, NAMED BEFORE THE BUILD BUDGET IS SPENT (2026-10-20). Box sweep 23324's
    # pre-warm returned 9,718 NOT_RUN_BUILD_FAILED of 21,112 completions, and 7,266 of them were
    # these two deterministic refusals: 3,898 lead_lag "no driver_symbol on the cell" and 3,368
    # calendar_month TypeError "missing 2 required keyword-only arguments: 'active_month' and
    # 'side_bias'". Each one loaded bars and held a pool worker before failing. A failed build is
    # never stamped seen, so the same cells sat at the head of the never-judged docket and were
    # re-attempted first on every sweep. Refused here they leave in `modifier_preflight` with the
    # same NOT_RUN_BUILD_FAILED status and their reason in the report, never reach a worker, and
    # are re-read every sweep, so a cell whose producer adds the field is judged that sweep.
    # Only what the builder already refuses is refused: an empty driver (`build_cell`'s own test)
    # and an ABSENT calendar key (the TypeError). A present but out-of-range value still goes to
    # the family, which answers it as it always has.
    if family == "lead_lag" and not params.get("driver_symbol"):
        return "BLOCKED_RULES: lead_lag: no driver_symbol on the cell"
    # A TRIANGLE NAMES BOTH LEGS OR IT IS NOT A TRIANGLE (2026-10-22). `build_cell` refuses
    # `if not leg_b_symbol` / `if not leg_c_symbol`, but only AFTER a pool worker has loaded the
    # cell's own bars, so the refusal held a worker and, as a pre-warm failure, came back
    # BUDGET_DEFERRED at the head of every sweep. The box's 2026-10-22 census
    # (UNKNOWN_SHARE_CENSUS.json, 6,000 random docket cells) measured `no_leg_symbol_named` at
    # 7 of 31 build failures. Same test as the builder's, same spelling as the driver refusal.
    if family == "triangle":
        for leg in ("leg_b_symbol", "leg_c_symbol"):
            if not params.get(leg):
                return f"BLOCKED_RULES: triangle: no {leg} on the candidate"
    if family == "calendar_month":
        missing = [k for k in ("active_month", "side_bias") if k not in params]
        if missing:
            return ("BLOCKED_RULES: calendar_month requires a source-specified "
                    + " and ".join(missing) + " on the candidate")
    if family == "usd_session_shock":
        _, why = fx_driver(params)
        if why != "ok":
            return why
    return None


def legacy_inputs(sym, family, params, bars_loader):
    """Return (extra, reason); preserve raw report dates and the family's release lag."""
    params = {} if params is None else params
    why = input_preflight(family, params)
    if why:
        return None, why
    if family == "usd_session_shock":
        driver, _ = fx_driver(params)
        # The family explicitly conditions on H1 FX, even when the traded chart is finer.
        fx = bars_loader(driver, "H1")
        if fx is None or len(fx) < 300:
            return None, f"BLOCKED_DATA: insufficient H1 FX driver bars for {driver}"
        return {"fx": fx}, "ok"
    if family in RAW_COT_FAMILIES:
        source = params.get("input_source")
        if source is not None and source not in {"cftc_legacy", "cot_legacy", "raw_cot"}:
            return None, f"BLOCKED_RULES: raw COT family cannot substitute source {source!r}"
        import numpy as np
        import pandas as pd
        from mt5desk.data import load_cot
        try:
            cot = load_cot(sym)
        except (KeyError, OSError, ValueError) as exc:
            return None, f"BLOCKED_DATA: raw COT for {sym}: {type(exc).__name__}: {exc}"
        prefix = "comm" if family == "cot_comm_follow" else "noncomm"
        required = ["report_date", f"{prefix}_positions_long_all",
                    f"{prefix}_positions_short_all"]
        if cot is None or cot.empty or any(c not in cot.columns for c in required):
            return None, f"BLOCKED_DATA: raw COT needs {required}; normalized net is insufficient"
        if cot["report_date"].isna().any() or cot["report_date"].duplicated().any():
            return None, "BLOCKED_DATA: invalid or duplicate raw COT report dates"
        for col in required[1:]:
            values = pd.to_numeric(cot[col], errors="coerce").to_numpy(dtype=float)
            if not np.isfinite(values).all() or (values < 0).any():
                return None, f"BLOCKED_DATA: invalid raw positioning counts in {col}"
        # Do not replace dates, fabricate publication timestamps, or apply the lag twice.
        return {"cot": cot}, "ok"
    return {}, "ok"

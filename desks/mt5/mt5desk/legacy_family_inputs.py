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

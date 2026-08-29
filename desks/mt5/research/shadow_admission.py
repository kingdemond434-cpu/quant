"""Fail-closed bridge from canonical ten-gate certificates to shadow work."""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

try:  # package import (tests/library callers) versus direct script execution
    from .gate_policy import all_ten_pass, is_exact_policy
except ImportError:  # pragma: no cover - exercised by production script entrypoints
    from gate_policy import all_ten_pass, is_exact_policy

BASE = Path(__file__).resolve().parent.parent


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


#: The qquant report writes its family as the shorthand "breakout"; the executable family on
#: this desk is "session_range_breakout". That translation is why the old literal was there, and
#: it must survive -- emitting the raw token produces a spec no family function matches, so the
#: sleeve is silently unrunnable. What must NOT survive is the EXCLUSION that sat beside it:
#: every other family was dropped entirely. Normalise known aliases, pass everything else
#: through, exclude nothing.
_FAMILY_ALIASES = {"breakout": "session_range_breakout"}


def _exec_family(name: str) -> str:
    return _FAMILY_ALIASES.get(str(name).casefold(), str(name) or "session_range_breakout")


def authorized_specs(base: Path = BASE) -> set[tuple[str, str, str | None, str, bool]]:
    """Return exact executable specs certified under the original policy only.

    Legacy qquant session rows are reconstructible from REAL_SURVIVORS. Newer
    universal survivors must publish an explicit ``shadow_spec``; guessing lost
    parameters from a display cell name is forbidden.
    """
    reports = base / "reports"
    out: set[tuple[str, str, str | None, str, bool]] = set()

    qquant = _read(reports / "QQUANT_GATES.json")
    if is_exact_policy(qquant.get("gate_policy")):
        for row in qquant.get("verdicts", []):
            if not isinstance(row, dict) or row.get("passed") is not True:
                continue
            if not all_ten_pass(row.get("stages")):
                continue
            parts = str(row.get("id") or "").split()
            if len(parts) != 5:
                continue
            symbol, family, side, selector, condition = parts
            # NO FAMILY WHITELIST, and the family is CARRIED rather than asserted. This dropped
            # every certified row whose family was not "breakout", and then wrote the literal
            # "session_range_breakout" into the spec regardless -- so a certificate for any other
            # mechanism was either discarded or relabelled as something it is not. Both are the
            # same defect: a door that only one family can walk through cannot diversify a book,
            # and diversification is the binding constraint here.
            # The guards that matter are unchanged and do the real work: is_exact_policy on the
            # report, and all_ten_pass on the row. Only genuinely certified rows reach this line.
            if side.upper() != "LONG":
                continue
            state = None if condition.upper() in {"NONE", "ALL", "UNCONDITIONED"} else condition
            out.add((symbol, selector, state, _exec_family(family), False))

    # Compatibility rows are accepted only when they carry the same complete
    # policy attestation; they cannot bypass or strengthen the QQUANT authority.
    real = _read(reports / "REAL_SURVIVORS.json")
    for row in real.get("real_survivors", []):
        if not isinstance(row, dict) or row.get("REAL3") is not True:
            continue
        cert = row.get("qquant_gates") or {}
        if not is_exact_policy(cert.get("policy")) or not all_ten_pass(cert.get("stages")):
            continue
        # Normalise the alias, exclude nothing, and CARRY the family into the spec instead of
        # asserting a literal. This dropped every certified compatibility row outside one family
        # and then wrote "session_range_breakout" regardless, so a certificate for any other
        # mechanism was either discarded or relabelled as something it is not.
        family = str(row.get("fam") or "SESSION_RANGE_BREAKOUT")
        if str(row.get("side") or "LONG").upper() != "LONG":
            continue
        state = row.get("state") or None
        out.add((str(row["sym"]), str(row["win"]), state, _exec_family(family), False))

    universal = _read(reports / "UNIVERSAL_SURVIVORS.json")
    if is_exact_policy(universal.get("gate_policy")):
        for row in universal.get("survivors", {}).values():
            if not isinstance(row, dict) or not all_ten_pass(row.get("gates")):
                continue
            spec = row.get("shadow_spec")
            if not isinstance(spec, dict):
                continue
            required = {"symbol", "selector", "family", "is_universe"}
            if not required <= set(spec):
                continue
            out.add((str(spec["symbol"]), str(spec["selector"]),
                     spec.get("condition") or None, str(spec["family"]),
                     spec["is_universe"] is True))
    return out


def partition_work(
    declared: Iterable[tuple[str, str, str | None, str, bool]],
    base: Path = BASE,
) -> tuple[list[tuple[str, str, str | None, str, bool]],
           list[tuple[str, str, str | None, str, bool]]]:
    authority = authorized_specs(base)
    admitted, blocked = [], []
    for spec in declared:
        (admitted if spec in authority else blocked).append(spec)
    return admitted, blocked

def power_cure_specs(base: Path = BASE) -> set[tuple[str, str, str | None, str, bool]]:
    """Specs that failed ONLY power gates -- admissible once forward evidence cures them.

    THE POLICY HAD NO INSTRUMENT (L1.46). gate_spec.yaml states `power_cure_via_forward: true`
    and classifies five gates as POWER (in_sample_screen, deflated_sharpe, cpcv, walk_forward,
    expected_value) versus five as VALIDITY (economic_prior, pbo, reality_check_spa,
    stress_costs, lockbox), with VALIDITY a hard fail. That is the whole reason 36 sleeves sit
    on forward clocks: they cleared every validity gate and missed on deflated Sharpe, which
    forward evidence is explicitly allowed to settle.

    But `authorized_specs` only ever admitted EXACT ten-gate certificates -- so a sleeve could
    complete the cure the policy promised and still be refused at the door, forever. The cure
    was unreachable, which makes it a wish rather than a rule. This function is the missing
    instrument: it returns the power-cure-eligible specs, and the PROMOTER (not this file)
    applies the forward thresholds before anything is promoted.
    """
    from gate_policy import is_exact_policy
    reports = base / "reports"
    out: set[tuple[str, str, str | None, str, bool]] = set()
    # CLASSIFICATIONS FROM THE SPEC, WITH FALLBACKS. The desk box runs a different branch whose
    # gate_policy predates get_validity_gates/get_power_gates, so importing them unconditionally
    # turned a policy improvement into an ImportError that killed the entire promoter run. A
    # capability that works only on one box's revision is not deployed. Read the spec when the
    # helpers are missing, the canonical literal when even the spec cannot be read, and FAIL
    # SOFT: a promoter that cannot classify skips the cure path, never aborts promotion.
    try:
        from gate_policy import get_power_gates, get_validity_gates
        validity, power = get_validity_gates(), get_power_gates()
    except ImportError:
        try:
            import yaml
            spec = yaml.safe_load((base / "policy" / "gate_spec.yaml").read_text("utf-8"))
            cls = spec.get("gate_classifications", {})
            validity = frozenset(cls.get("validity", ()))
            power = frozenset(cls.get("power", ()))
        except Exception:
            validity = frozenset({"economic_prior", "pbo", "reality_check_spa",
                                  "stress_costs", "lockbox"})
            power = frozenset({"in_sample_screen", "deflated_sharpe", "cpcv",
                               "walk_forward", "expected_value"})
    if not validity or not power:
        return out
    qq = _read(reports / "QQUANT_GATES.json")
    if not is_exact_policy(qq.get("gate_policy")):
        return out
    for r in qq.get("verdicts", []):
        stages = r.get("stages") if isinstance(r, dict) else None
        if not isinstance(stages, dict):
            continue
        # VALIDITY IS ABSOLUTE: one validity miss and the cell is DEAD, never cured.
        if not all(isinstance(stages.get(g), dict) and stages[g].get("passed") is True
                   for g in validity):
            continue
        # and it must actually be a POWER failure -- a full pass belongs to authorized_specs.
        failed_power = [g for g in power
                        if not (isinstance(stages.get(g), dict)
                                and stages[g].get("passed") is True)]
        if not failed_power:
            continue
        parts = str(r.get("id") or "").split()
        if len(parts) != 5:
            continue
        symbol, family, _side, selector, condition = parts
        # No whitelist here either -- the cure lane must be open to every mechanism that clears
        # the validity gates, which is the entire point of curing by forward evidence.
        state = None if condition.upper() in {"NONE", "ALL", "UNCONDITIONED"} else condition
        out.add((symbol, selector, state, _exec_family(family), False))

    # THE EXTERNAL LANE, which had no route at all. The qquant report above is one producer; the
    # gauntlet publishes its own validity-pass, power-deficient cells to POWER_CURE_CANDIDATES
    # with an EXACT executable shadow_spec (never a guessed selector). Certificates stay in
    # UNIVERSAL_SURVIVORS; these rows carry no promotion authority, and the promoter still
    # applies the forward cure thresholds before anything is promoted.
    # Measured 2026-08-29 -- 615 candidates across EIGHT families (cross_asset_residual 140,
    # session_range_breakout 96, overnight_gap_decay 79, relative_value 73, carry 72, ...), 598
    # of them failing deflated_sharpe alone. Without this block admission saw 68, all of one
    # family, which is what a cure lane looks like when only one producer can reach it.
    cure = _read(reports / "POWER_CURE_CANDIDATES.json")
    if is_exact_policy(cure.get("gate_policy")):
        for row in (cure.get("candidates") or {}).values():
            if not isinstance(row, dict) or row.get("validity_pass") is not True:
                continue
            if not row.get("failed_power_gates"):
                continue
            spec = row.get("shadow_spec")
            if not isinstance(spec, dict):
                continue
            if not {"symbol", "selector", "family", "is_universe"} <= set(spec):
                continue
            out.add((str(spec["symbol"]), str(spec["selector"]),
                     spec.get("condition") or None, _exec_family(spec["family"]),
                     spec["is_universe"] is True))
    return out


def authorized_runs(base: Path = BASE) -> list[dict]:
    """Exactly-specified RUNNABLE certificates: symbol, selector, family AND certified params.

    WHY THIS EXISTS ALONGSIDE `authorized_specs`. That function answers "is this cell allowed?"
    and its five-tuple deliberately has no params -- every existing consumer depends on that
    shape. This one answers a different question the forward engine actually needs: "what,
    precisely, do I run?" Measured 2026-08-26: 21 certificates collapsed to 6 five-tuples, so
    five separately-gauntleted XAUUSD parameterizations became one clock executing the engine's
    own default (rr=2.0). Four certified strategies were therefore never forward-tested while
    still being counted as certificates.

    A certificate WITHOUT `params` is not returned. It cannot be: running it means guessing the
    parameterization that passed, and `authorized_specs`' own rule is that reconstructing lost
    parameters from a display name is forbidden. Those rows are re-certified with params by the
    next daily gauntlet pass rather than run on a guess.
    """
    universal = _read(base / "reports" / "UNIVERSAL_SURVIVORS.json")
    if not is_exact_policy(universal.get("gate_policy")):
        return []
    runs: list[dict] = []
    for name, row in (universal.get("survivors") or {}).items():
        if not isinstance(row, dict) or not all_ten_pass(row.get("gates")):
            continue
        spec = row.get("shadow_spec")
        if not isinstance(spec, dict):
            continue
        params = spec.get("params")
        if not isinstance(params, dict):
            continue                       # ABSENT params -- unrunnable without guessing
        # {} is NOT "lost parameters": it is the complete parameterization "family defaults",
        # byte-exactly what the gauntlet executed (build_cell with params={}) and what the
        # p=<hash-of-empty> cell identity certifies. Excluding it kept both overnight_gap_decay
        # certificates CERTIFIED-NOT-ENROLLED while the same-day fence flagged them (2026-08-27).
        runs.append({
            "certificate": name,
            "symbol": str(spec["symbol"]), "selector": str(spec["selector"]),
            "family": str(spec.get("family") or "session_range_breakout"),
            "condition": spec.get("condition") or None,
            "params": dict(params),
        })
    return runs


def run_key(run: dict) -> str:
    """Stable per-parameterization clock key: SYMBOL.selector#p1=v1_p2=v2 (sorted, so stable)."""
    sig = "_".join(f"{k}={run['params'][k]}" for k in sorted(run["params"]))
    return f"{run['symbol']}.{run['selector']}#{sig}"

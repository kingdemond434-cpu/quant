"""CERTIFICATE DUPLICATES -- two certificates for one executable rule.

WHY (BR1, box 2026-11-11). The blind reviewer re-ran 14 CHFNOK carry certificates and found
whole groups reproducing one trade set. Most of that was the reviewer dropping `session` (fixed
in blind_reviewer.call_params), but not all of it: `{"timeframe": "M30"}` and
`{"input_symbol": "CHFNOK", "timeframe": "M30"}` hash to different cells (6c593827..., ce4c84b9...)
while naming the same rule -- carry reads its swap from its own symbol by default -- and both
hold a certificate with the same numbers. A duplicate certificate counts the same evidence
twice: the survivor count, the allocator's breadth and the forward roster all see two edges
where there is one.

WHAT THIS DOES. `executable_identity` reduces a cell to what decides its trades:
symbol, chart, family, session (a `family_call.SESSIONS` window, the raw name for any other name,
or the family's own `session` keyword verbatim), side, the family's keyword arguments with the
signature's defaults filled in, and the modifiers `cell_modifiers` would apply. It drops only
what provably changes nothing: an `input_symbol` equal to the cell's own symbol, label keys
(`cell_modifiers.LABEL_KEYS`), a no-op regime, and the fill-surface vintage stamp. Anything it
cannot reduce stays in the identity, so the reduction can miss a duplicate but never invent one.

`sweep` groups the certificates in UNIVERSAL_SURVIVORS.json by identity and writes
reports/CERT_DUPLICATES.json: every group with more than one certificate, the earliest-gated
one named as the original and the rest as its duplicates, counted per family. REPORT ONLY:
nothing here edits a certificate, a clock, a sleeve or a trial count. The judge's refusal to
mint a new duplicate is the sealed side (external_gauntlet) and reads `executable_identity`.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
OUT = BASE / "reports" / "CERT_DUPLICATES.json"
UNMEASURED = "UNMEASURED"
GROUP_SAMPLE = 200

#: Keys that only stamp WHEN or FROM WHICH MAP a cell was selected; no family or filter reads them.
_VINTAGE_KEYS = frozenset({"surface_generated_at"})
_NO_OP_REGIMES = frozenset({"", "unconditional", "all", "any"})


def _norm(v: Any) -> Any:
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        f = float(v)
        return int(f) if f.is_integer() else round(f, 12)
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    return str(v)


def _family_fn(family: str) -> Any:
    try:
        from mt5desk import executables
        return executables.resolve_family(family)
    except Exception:
        return None


def _signature(fn: Any) -> tuple[dict[str, Any], bool] | None:
    try:
        ps = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return None
    varkw = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in ps.values())
    defaults = {k: p.default for k, p in ps.items()
                if p.default is not inspect.Parameter.empty and k not in ("side",)}
    if "session" in ps and "session" not in defaults:
        defaults["session"] = None
    return defaults, varkw


def _session_identity(session: str, raw: Any,
                      sig: tuple[dict[str, Any], bool] | None) -> Any:
    """The session as far as it can be reduced WITHOUT inventing a duplicate.

    Only the names `family_call.SESSIONS` defines map to a window, and only `all` (or no session)
    reduces to None. A family that takes `session` as its own keyword (the joint-window families,
    `family_scalp`) means something else by london/new_york/overlap, so its raw value is kept;
    so is any name the shared table does not define."""
    if sig is not None and ("session" in sig[0]):
        return None if raw is None else ["kwarg", _norm(raw)]
    if session == "all":
        return None
    try:
        from mt5desk.family_call import SESSIONS
    except Exception:
        return ["name", session]
    if session in SESSIONS and SESSIONS[session] is not None:
        return list(SESSIONS[session])  # type: ignore[arg-type]
    return ["name", session]


def executable_identity(symbol: str, family: str, params: dict[str, Any] | None, *,
                        side: Any = None, fn: Any = None) -> str:
    """A canonical JSON string; two cells with the same string trade the same signals."""
    sym = str(symbol or "").upper()
    p = dict(params or {})
    tf = str(p.pop("timeframe", None) or "H1").upper()
    raw_session = p.pop("session", None)
    session = str(raw_session or "all").strip().lower()
    if str(p.get("input_symbol") or "").upper() == sym:
        p.pop("input_symbol")
    for k in _VINTAGE_KEYS:
        p.pop(k, None)
    labels: frozenset[str] = frozenset()
    modifier_keys: frozenset[str] = frozenset()
    try:
        from mt5desk import cell_modifiers
        labels, modifier_keys = cell_modifiers.LABEL_KEYS, cell_modifiers.MODIFIER_KEYS
    except Exception:
        pass
    for k in labels:
        p.pop(k, None)
    if str(p.get("regime") or "").strip().lower() in _NO_OP_REGIMES:
        p.pop("regime", None)
    fn = _family_fn(family) if fn is None else fn
    sig = _signature(fn) if fn is not None else None
    session_key = _session_identity(session, raw_session, sig)
    kwargs: dict[str, Any] = {}
    mods: dict[str, Any] = {}
    other: dict[str, Any] = {}
    if sig is None:
        other = p                               # unresolvable family: nothing reduced
    else:
        defaults, varkw = sig
        kwargs = {**defaults}
        for k, v in p.items():
            if k in defaults or varkw:
                kwargs[k] = v
            elif k in modifier_keys:
                mods[k] = v
            else:
                other[k] = v                    # the judge would refuse it; keep it visible
        kwargs.pop("symbol", None)              # the cell's own symbol is passed by the judge
        kwargs.pop("session", None)             # carried once, in `session`, never twice
    return json.dumps(_norm({"symbol": sym, "chart": tf, "family": str(family),
                             "session": session_key,
                             "side": None if side is None else str(side).upper(),
                             "kwargs": kwargs, "modifiers": mods, "unreduced": other}),
                      sort_keys=True, separators=(",", ":"))


def _spec(row: Any) -> dict[str, Any] | None:
    sp = row.get("shadow_spec") if isinstance(row, dict) else None
    if not isinstance(sp, dict) or not isinstance(sp.get("params"), dict):
        return None
    return sp


def groups(survivors: dict[str, Any]) -> tuple[dict[str, list[str]], list[str]]:
    """identity -> certificate keys (earliest gated first); and the keys with no runnable spec."""
    by_id: dict[str, list[tuple[str, str]]] = {}
    unrunnable: list[str] = []
    fns: dict[str, Any] = {}
    for key, row in survivors.items():
        sp = _spec(row)
        if sp is None:
            unrunnable.append(key)
            continue
        fam = str(sp.get("family") or "")
        if fam not in fns:
            fns[fam] = _family_fn(fam)
        ident = executable_identity(str(sp.get("symbol") or row.get("sym") or ""), fam,
                                    sp.get("params"), side=sp.get("side"), fn=fns[fam])
        by_id.setdefault(ident, []).append((str(row.get("gated_at") or ""), key))
    return ({i: [k for _, k in sorted(v)] for i, v in by_id.items()}, sorted(unrunnable))


def sweep(survivors: Any, now: datetime | None = None) -> dict[str, Any]:
    t = (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
    rows = survivors.get("survivors") if isinstance(survivors, dict) else None
    if not isinstance(rows, dict):
        return {"at": t, "status": UNMEASURED,
                "why": f"{SURVIVORS.name} absent or has no `survivors` mapping"}
    g, unrunnable = groups(rows)
    dup = {i: ks for i, ks in g.items() if len(ks) > 1}
    by_family: Counter[str] = Counter()
    listed: list[dict[str, Any]] = []
    for ident, ks in sorted(dup.items(), key=lambda kv: -len(kv[1])):
        fam = json.loads(ident)["family"]
        by_family[fam] += len(ks) - 1
        if len(listed) < GROUP_SAMPLE:
            listed.append({"original": ks[0], "duplicates": ks[1:], "identity": json.loads(ident)})
    n_dup = sum(len(ks) - 1 for ks in dup.values())
    return {"at": t, "status": "MEASURED", "certificates": len(rows),
            "executable_rules": len(g), "duplicate_groups": len(dup),
            "duplicate_certificates": n_dup, "by_family": dict(by_family.most_common()),
            "unrunnable": {"n": len(unrunnable), "sample": unrunnable[:20],
                           "why": "no shadow_spec.params: identity UNMEASURED, never grouped"},
            "groups": listed, "groups_listed": len(listed),
            "rule": ("identity = symbol, chart, family, session window, side, family kwargs "
                     "with signature defaults, applied modifiers; dropped only: input_symbol "
                     "equal to the symbol, label keys, a no-op regime, the surface vintage. "
                     "Report only: no certificate, clock, sleeve or trial count is changed.")}


def _write_atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    a = ap.parse_args(argv)
    try:
        doc = json.loads(SURVIVORS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = None
    out = sweep(doc)
    if not a.dry_run:
        _write_atomic(OUT, out)
    print(f"cert_duplicates: {out.get('status')} certificates={out.get('certificates')} "
          f"duplicate_certificates={out.get('duplicate_certificates')} "
          f"by_family={out.get('by_family')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

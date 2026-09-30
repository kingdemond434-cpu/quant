"""RESEARCH-LIVE IDENTITY: is the spec the gateway trades the spec research certified?

WHAT ALREADY EXISTED, EACH PROVING ONE LINK AND NONE THE JOIN (surveyed 2026-09-30):

    mt5desk/release_identity.py      the running CODE is the sealed release (commit + money-path
                                     hashes) -- says nothing about which spec a sleeve trades
    libs/data/input_identity.py      the BARS a verdict was measured on are pinned
    research/sleeve_registry.verify  a forward clock's identity has not drifted since it froze --
                                     research's own record against research's own record
    promoter certificate_drift       a qquant candidate's spec is in today's authority set, at
                                     promotion time only, "recorded, blocking nothing"
    libs/tiers/conformance.py        the gateway's send sites implement the model-checked protocol
    libs/tiers/shadow_desk.py        candidate CODE replayed beside the incumbent's

Nothing puts the row the gateway reads (`data/sleeves.json`) beside the certificate research
issued (`UNIVERSAL_SURVIVORS`) and the clock research froze (`sleeve_registry.json`) and asks
whether they are the same strategy. That is the join below. Per LIVE sleeve, five fields:

    family, symbol, selector   the sleeve row against the certificate's `shadow_spec`
    params                     what the gateway will CALL the family with -- the row's own params
                               when it carries a mapping, else recovered from the certificate's
                               cell exactly as `gateway._params_from_certificate` recovers them
                               (the docket join on `frontier_identity.cell_id`, verified by the
                               digest) -- against the certified params
    code                       the code hash of the function the gateway resolves NOW
                               (`executables.resolve_family` -> `sleeve_registry.code_hash`)
                               against the one the forward clock FROZE; a difference whose
                               bytecode (`behaviour_hash`) agrees is prose, not a new strategy

VERDICTS. MATCH -- every field agrees. MISMATCH -- a named defect, with each disagreeing field
and both values. UNMEASURED -- the join could not be made (no certificate cell, a lane that is not
certified through UNIVERSAL_SURVIVORS, a family nothing resolves), with the reason. UNMEASURED is
never counted as a match.

THE CONSEQUENCE lives in `libs/tiers/promotion_authority.review_live`, which lists a LIVE row
whose identity MISMATCHES among the rows the door would withhold (`data/tier_s/live_door.json`);
the promoter's automatic retirement reads that file. Nothing here writes a sleeve.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from typing import Any

MATCH, MISMATCH, UNMEASURED = "MATCH", "MISMATCH", "UNMEASURED"
FIELDS: tuple[str, ...] = ("family", "symbol", "selector", "params", "code")
SIDE_WORDS = (("SHORT", -1), ("SELL", -1), ("LONG", 1), ("BUY", 1))


def _canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, default=str)


def cert_cell(row: Mapping[str, Any]) -> str:
    """The certificate cell a sleeve row names, the two shapes the gateway reads: a dict with a
    `cell`, or a dotted string (a bare word such as `forward_clock` names a lane, not a cell)."""
    cert = row.get("certificate")
    if isinstance(cert, Mapping):
        return str(cert.get("cell") or "")
    if isinstance(cert, str) and "." in cert:
        return cert.strip()
    return ""


def survivor_for(cell: str, survivors: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]] | None:
    """The UNIVERSAL_SURVIVORS row for a certificate cell: by its full key, else by the bare cell
    under any hunt prefix (`external.X` is keyed `external.X`; a row's own `cell` also counts)."""
    if cell in survivors and isinstance(survivors[cell], Mapping):
        return cell, survivors[cell]
    bare = cell.split(".", 1)[1] if cell.startswith("external.") else cell
    for k, v in survivors.items():
        if not isinstance(v, Mapping):
            continue
        if str(v.get("cell") or "") in (cell, bare) or str(k).endswith("." + bare):
            return str(k), v
    return None


def recover_params(row: Mapping[str, Any], docket_index: Mapping[str, Any],
                   docket_by_sym_family: Mapping[tuple[str, str], list[Any]] | None = None
                   ) -> tuple[dict[str, Any] | None, str]:
    """(params the gateway would call the family with, how). None = the gateway refuses the row.

    `gateway._params_from_certificate`'s rule, restated read-only (the gateway imports
    MetaTrader5 and cannot be imported off the box): an explicit params mapping on the row wins;
    else a qquant descriptor yields its side word; else the certificate cell's digest is looked up
    in the docket (`docket_index`: cell_id -> params); a bare name with no parameter field is the
    default parameterisation only when the docket holds exactly one for that symbol and family."""
    if "params" in row and isinstance(row.get("params"), Mapping):
        return dict(row["params"]), "row"
    cell = cert_cell(row)
    if not cell:
        return None, "the row carries no params and its certificate names no cell"
    want = cell.split(".", 1)[1] if cell.startswith("external.") else cell
    if cell.startswith("qquant.") or " " in want:
        words = want.replace(".", " ").split()
        sign = next((v for w in words for k, v in SIDE_WORDS if w.upper() == k), None)
        if sign is not None:
            return {"side": sign}, "qquant_side_word"
    if want in docket_index:
        return dict(docket_index[want] or {}), "docket_digest"
    if "." in want and "p=" not in want and "=" not in want.split(".", 2)[-1]:
        sym, fam = want.split(".", 1)
        cands = (docket_by_sym_family or {}).get((sym, fam)) or []
        uniq = {_canon(p or {}) for p in cands}
        if len(uniq) == 1:
            return json.loads(next(iter(uniq))), "docket_unique_default"
        if not uniq:
            return {}, "bare_name_default"
        return None, (f"bare cell {want!r} with {len(uniq)} docketed parameterisations: the "
                      "gateway refuses to guess")
    return None, f"certified cell {want!r} is not in the docket on this host"


def frozen_for(symbol: str, family: str, selector: str, params: Mapping[str, Any] | None,
               registry: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]] | None:
    """The forward clock research froze for this spec: same family, symbol, selector and (when
    known) params. Rows whose identity names no params match on the other three alone."""
    best: tuple[str, Mapping[str, Any]] | None = None
    for k, v in registry.items():
        idn = (v or {}).get("identity") if isinstance(v, Mapping) else None
        if not isinstance(idn, Mapping):
            continue
        if (str(idn.get("family")), str(idn.get("symbol")), str(idn.get("selector"))) != (
                family, symbol, selector):
            continue
        if params is not None and _canon(dict(idn.get("params") or {})) != _canon(dict(params)):
            continue
        if best is None or str(v.get("status")) == "LIVE":
            best = (str(k), idn)
    return best


def judge_row(row: Mapping[str, Any], *, survivors: Mapping[str, Any],
              registry: Mapping[str, Any], docket_index: Mapping[str, Any],
              docket_by_sym_family: Mapping[tuple[str, str], list[Any]] | None,
              code_of: Callable[[str], tuple[str | None, str | None]]) -> dict[str, Any]:
    name = str(row.get("name") or "")
    out: dict[str, Any] = {"name": name, "exec": row.get("exec")}
    family = str(row.get("family") or "")
    if not family:
        return {**out, "verdict": UNMEASURED,
                "why": "the row names no family (a gold-window lane row); its certificate is the "
                       "window's forward clock, not a UNIVERSAL_SURVIVORS spec"}
    cell = cert_cell(row)
    out["certificate_cell"] = cell or None
    hit = survivor_for(cell, survivors) if cell else None
    if hit is None:
        return {**out, "verdict": UNMEASURED,
                "why": (f"certificate {row.get('certificate')!r} is not a UNIVERSAL_SURVIVORS cell "
                        "on this host" if cell else
                        f"certificate {row.get('certificate')!r} names a lane, not a cell")}
    skey, srow = hit
    spec = srow.get("shadow_spec") or {}
    spec = spec if isinstance(spec, Mapping) else {}
    out["survivor"] = skey
    traded_params, basis = recover_params(row, docket_index, docket_by_sym_family)
    selector = str(row.get("selector") or row.get("session") or "")
    traded = {"family": family, "symbol": str(row.get("symbol") or ""), "selector": selector,
              "params": traded_params}
    c_family = str(spec.get("family") or "")
    c_symbol = str(spec.get("symbol") or srow.get("sym") or "")
    c_selector = str(spec.get("selector") or "")
    c_params: dict[str, Any] | None = (dict(spec["params"]) if isinstance(spec.get("params"),
                                                                          Mapping) else None)
    certified: dict[str, Any] = {"family": c_family, "symbol": c_symbol,
                                 "selector": c_selector, "params": c_params}
    out["params_basis"] = basis
    diffs: dict[str, dict[str, Any]] = {}
    for f in ("family", "symbol", "selector"):
        if traded[f] != certified[f]:
            diffs[f] = {"traded": traded[f], "certified": certified[f]}
    unmeasured: list[str] = []
    if traded_params is None:
        unmeasured.append(f"params: {basis}")
    elif certified["params"] is None:
        unmeasured.append("params: the certificate's shadow_spec carries none")
    elif _canon(traded_params) != _canon(certified["params"]):
        diffs["params"] = {"traded": traded_params, "certified": certified["params"]}
    # THE CODE: the function the gateway resolves NOW against the one the clock FROZE.
    live_code, live_beh = code_of(family)
    frozen = frozen_for(c_symbol, c_family, c_selector, c_params, registry)
    out["code"] = {"live": live_code, "live_behaviour": live_beh}
    if live_code is None:
        unmeasured.append(f"code: nothing resolves family {family!r} on this host")
    elif frozen is None:
        unmeasured.append("code: no forward clock in sleeve_registry froze this spec")
    else:
        fk, fid = frozen
        out["code"].update({"clock": fk, "frozen": fid.get("code_hash"),
                            "frozen_behaviour": fid.get("behaviour_hash")})
        if fid.get("code_hash") != live_code:
            fb = fid.get("behaviour_hash")
            if fb and live_beh and fb == live_beh and not str(fb).startswith("nocode:"):
                out["code"]["prose_only"] = True
            else:
                diffs["code"] = {"traded": live_code, "certified": fid.get("code_hash"),
                                 "traded_behaviour": live_beh, "certified_behaviour": fb}
    out["traded"] = traded
    out["certified"] = certified
    if diffs:
        return {**out, "verdict": MISMATCH, "fields": sorted(diffs), "diff": diffs,
                "unmeasured": unmeasured,
                "why": ("IDENTITY_MISMATCH: the gateway trades a spec research did not certify ("
                        + ", ".join(sorted(diffs)) + ")")}
    if unmeasured:
        return {**out, "verdict": UNMEASURED, "why": "; ".join(unmeasured)}
    return {**out, "verdict": MATCH}


def judge(live_rows: Iterable[Mapping[str, Any]], **kw: Any) -> dict[str, Any]:
    rows = [judge_row(r, **kw) for r in live_rows]
    by = {v: [r["name"] for r in rows if r["verdict"] == v] for v in (MATCH, MISMATCH,
                                                                      UNMEASURED)}
    return {"n_live": len(rows), "counts": {k: len(v) for k, v in by.items()},
            "mismatched": by[MISMATCH], "unmeasured": by[UNMEASURED],
            "defects": [{"name": r["name"], "defect": "IDENTITY_MISMATCH",
                         "fields": r["fields"], "why": r["why"]}
                        for r in rows if r["verdict"] == MISMATCH],
            "rows": rows}


def mismatch_reasons(doc: Mapping[str, Any] | None) -> dict[str, str]:
    """{LIVE sleeve name: reason} for every MISMATCH row of a RESEARCH_LIVE_IDENTITY document."""
    out: dict[str, str] = {}
    rows = doc.get("rows") if isinstance(doc, Mapping) else None
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, Mapping) and r.get("verdict") == MISMATCH and r.get("name"):
            out[str(r["name"])] = str(r.get("why") or "IDENTITY_MISMATCH")
    return out

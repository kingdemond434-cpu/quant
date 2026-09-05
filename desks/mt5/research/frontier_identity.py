"""Exact identity and economic-prior rules shared by discovery and the universal gauntlet."""
from __future__ import annotations

import hashlib
import json

#: The chart every historical cell was hunted on, and the one whose name stays unwritten.
#:
#: THE CORRUPTION THIS PREVENTS (2026-09-05, when the sweep gained the full M1..D1 ladder). Cell
#: identity feeds the gauntlet's content-addressed series cache and the certificate key. If it
#: does not carry the CHART, then the same symbol and family on M5 and on H1 are the SAME CELL:
#: the cache serves one result for the other and a certificate minted on one chart is claimed by
#: the other. Every number in that record is internally consistent, so no gate downstream can see
#: it -- which makes it strictly worse than the H1-only limitation it would arrive with.
#:
#: H1 IS SPELLED BY ITS ABSENCE, and the asymmetry is deliberate rather than untidy -- it is the
#: same rule `shadow_forward.sleeve_key` already applies to direction ("every key ever written by
#: this desk is a long clock"). Every cell id, certificate, forward-clock key and cache entry this
#: desk has ever written is an H1 cell. Writing `@H1` into all of them would rename the entire
#: canon at once and orphan every running clock against its own ledger. So an H1 id is
#: byte-identical to what it has always been, and every other chart is named explicitly.
REFERENCE_TIMEFRAME = "H1"


def timeframe_of(cell: dict) -> str:
    """The chart a cell is hunted on: its own `timeframe`, its params', or H1 by default."""
    for source in (cell, cell.get("params") or {}):
        if isinstance(source, dict) and source.get("timeframe"):
            return str(source["timeframe"]).upper()
    return REFERENCE_TIMEFRAME


def _tf_suffix(cell: dict) -> str:
    tf = timeframe_of(cell)
    return "" if tf == REFERENCE_TIMEFRAME else f"@{tf}"


def cell_id(cell: dict) -> str:
    """Executable identity; arbitrary DSL parameters must never collapse onto rr=?/wb=? IDs."""
    params = dict(cell.get("params") or {})
    # THE LEGACY SHORT FORM IS ONLY SAFE WHEN rr/wait_bars ARE THE WHOLE PARAMETER SET.
    # It used to fire whenever EITHER key was present, so every other parameter collapsed out
    # of the identity -- measured 2026-08-29 on H-20260828-005, where 24 distinct trials
    # (3 symbols x 2 rr x 2 ttl_bars x 2 directions) printed as 8 ids, three cells deep each,
    # with opposite-signed Sharpes under the SAME name. The docstring above already forbade
    # exactly this; the branch predicate did not enforce it. Anything richer than {rr,
    # wait_bars} now takes the digest form, so no historical id whose params were only those
    # two keys changes value.
    # THE CHART IS PART OF THE NAME, not only of the digest. `timeframe` normally rides in
    # `params` and so already changes the digest -- but a cell whose chart is carried on the row
    # instead, and the legacy short form below (which drops params entirely), would both collapse
    # two charts onto one id. Reading it through `timeframe_of` and appending it makes the
    # identity right whichever way the chart was recorded, and leaves it VISIBLE: an operator
    # reading a docket can see that `XAUUSD@M5.carry.p=ab12` is not the H1 cell of that name.
    # It rides on the SYMBOL rather than at the end because every consumer that splits a cell id
    # splits on "." -- `<sym>.<family>.<params>` -- and a fourth dot-separated field would change
    # that arity for every reader at once.
    tf = _tf_suffix(cell)
    if params and set(params) <= {"rr", "wait_bars"}:
        return (f"{cell['sym']}{tf}.{cell['family']}.rr={params.get('rr', '?')}"
                f"_wb={params.get('wait_bars', '?')}")
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{cell['sym']}{tf}.{cell['family']}.p={digest}"


def economic_prior(cell: dict) -> dict:
    """Fail closed for unconstrained statistical finds; named mechanisms remain hypotheses."""
    status = str(cell.get("mechanism_status") or "")
    if not status:
        status = "STATISTICAL_ONLY" if cell.get("family") == "discovered" else "NAMED"
    passed = status == "NAMED"
    return {
        "passed": passed,
        "message": str(cell.get("mechanism_note") or (
            "named registered family" if passed else "statistical discovery has no economic prior"
        )),
        "mechanism_status": status,
    }

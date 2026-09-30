"""Exact identity and economic-prior rules shared by discovery and the universal gauntlet."""
from __future__ import annotations

import hashlib
import json
from typing import Any

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


def timeframe_of(cell: dict[str, Any]) -> str:
    """The chart a cell is hunted on: its own `timeframe`, its params', or H1 by default."""
    for source in (cell, cell.get("params") or {}):
        if isinstance(source, dict) and source.get("timeframe"):
            return str(source["timeframe"]).upper()
    return REFERENCE_TIMEFRAME


def _tf_suffix(cell: dict[str, Any]) -> str:
    tf = timeframe_of(cell)
    return "" if tf == REFERENCE_TIMEFRAME else f"@{tf}"


def cell_id(cell: dict[str, Any]) -> str:
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


def docket_cell(row: dict[str, Any]) -> dict[str, Any]:
    """A DOCKET ROW, normalised into the cell the judge will key its verdict by.

    THE ONE PLACE THE ROW->CELL RULE LIVES, and the reason it has to exist at all. `cell_id`
    answers "what is this cell called"; it cannot answer "which cell is this ROW", because a
    producer may carry the chart in `params["timeframe"]`, on the row's own `timeframe` field, or
    in both. `external_gauntlet.main` groups the docket into cells by folding a non-H1 ROW chart
    into `params` and then naming the cell from `params` alone -- so the chart is inside the
    identity DIGEST. Any reader that instead hands `cell_id` a separate `timeframe` key gets the
    right `@TF` suffix over a digest computed WITHOUT the chart, and lands in a different key
    space that happens to look identical for H1.

    WHAT THAT COST, MEASURED ON THE BOX 2026-09-24/25. `judge_coverage` banks every cell whose
    build failed (88,488 rows) under the judge's own verdict key, and filters the docket by that
    bank under the second key. Overlap of the bank with the 539,462-row docket:

        bank INTERSECT judge_coverage's keys     0
        bank INTERSECT the judge's own keys  78,771

    So the bank held the answer for 78,771 docket rows and removed none of them: the judge
    rebuilt every one of them, every pass, and its pre-warm failure count never moved
    (81,588 -> 88,246 -> 109,792 -> 93,320). 192,757 of 539,462 rows (35.7%) were keyed
    differently by the two sides. The same gap silently told the coverage table that every
    non-H1 cell it had ever judged was still unjudged, because `judged_index` reads the gate
    ledger, which is in the judge's key space too.

    Two shapes diverge, and they diverge in OPPOSITE directions -- which is why a partial
    overlap, rather than none at all, is what a reader saw:

      * chart on the row only  (row `timeframe` M15, absent from params)
          judge: GBPAUD@M15.cross_asset_residual.p=6403309d7977b134   (chart IS in the digest)
          here : GBPAUD@M15.cross_asset_residual.p=a7abf4646a7e6aca   (chart is NOT)
      * chart in params, row says H1 (the orthogonal sweep writes both, row stamped H1)
          judge: UK100@M1.exogenous_conditioner.p=4174b6f6734b5405
          here : UK100.exogenous_conditioner.p=4174b6f6734b5405       (suffix lost entirely)

    `timeframe_of` reads the cell-level field FIRST, so passing `timeframe` beside `params`
    overrides the chart the params themselves name. Returning a cell with NO separate
    `timeframe` key is therefore load-bearing, not tidiness: params alone must decide.
    """
    params = dict(row.get("params") or {})
    row_tf = str(row.get("timeframe") or "").upper()
    if row_tf and row_tf != REFERENCE_TIMEFRAME and "timeframe" not in params:
        params["timeframe"] = row_tf
    return {"sym": row.get("symbol") or row.get("sym"), "family": row.get("family"),
            "params": params}


def docket_cell_id(row: dict[str, Any]) -> str:
    """The judge's identity for a docket ROW. See `docket_cell` for why the row needs its own."""
    return cell_id(docket_cell(row))


def economic_prior(cell: dict[str, Any]) -> dict[str, Any]:
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

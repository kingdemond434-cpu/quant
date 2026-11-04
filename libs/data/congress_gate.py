"""THE CONGRESS ATTEST SWITCH -- congressional disclosures stay OFF until the principal attests.

WHY (auditor ruling, 2026-11-03). The House and Senate periodic transaction reports are filed under
the STOCK Act and published under 5 U.S.C. 13107. Section 13107(c) makes it unlawful to obtain or
use such a report for any commercial purpose other than news and communications media or
dissemination to the general public, and trading is the case it names. Whether this desk's use is
lawful is a judgement for the principal and counsel, never for a session or an organ. So collection
and every use stay OFF by default, and one switch -- this module -- is the only thing that turns
them on.

ONE SWITCH, READ ONE WAY, BY EVERY ORGAN. The switch is ON only when the principal sets

    QUANT_CONGRESS_ATTEST=1

in the environment of the process that reads the data -- exactly "1", nothing else. These are the
semantics `desks/mt5/research/informed_capital.congress_attested()` already uses for the House and
Senate collectors (branch claude/informed-capital-cells, 421a72925c), so the free stack, the
informed-capital organ and every reader below answer to the SAME variable read the SAME way, and
the gate bills under the same rail name (`congress_attestation_gate`) with the same status
(`AWAITING_PRINCIPAL`). Nothing in the repository sets it: it is the principal's act.

WHAT OFF MEANS, everywhere this module is consulted:

  * the fetcher makes NO request and returns an AWAITING_PRINCIPAL verdict carrying its
    missed-growth line (`libs.data.free_stack.fetch_congress`);
  * every reader of congressional output -- the PIT store, the published lake series, the hunter's
    allocation state, the proposer's grid, the conditioner families, the lake PIT door -- treats
    the data as UNMEASURED, INCLUDING DATA COLLECTED BEFORE THE SWITCH WAS READ. Nothing is
    deleted: the files stay on disk for the principal's review, and nothing reads them.

The refusal is a rail in the growth-governance sense, so it carries its `missed_growth_line`. Its
price is UNMEASURED, said, never zero: no congressional cell has ever been judged, so there is no
forward E[log W] to bill. The rail exists for a legal reason, not a risk one, and the line says so.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any

ENV = "QUANT_CONGRESS_ATTEST"
#: The status every fetcher and reader reports while the switch is OFF (informed_capital's word).
HELD = "AWAITING_PRINCIPAL"
#: The missed-growth rail the gate bills under (informed_capital's name, so the ledger has one).
RAIL = "congress_attestation_gate"
LEGAL_BASIS = ("5 U.S.C. 13107(c): congressional periodic transaction reports may not be used "
               "for a commercial purpose; trading is the case it names")

#: The roster `kind` of a congressional source, and the identifiers its data travels under: the
#: roster id (`congress_trades`), its lake series (`fs_congress_trades`), the informed-capital
#: families (`house_ptr`, `senate_ptr`, `congress_agg`) and the transaction mirror.
CONGRESS_KINDS: frozenset[str] = frozenset({"congress", "house_ptr", "senate_ptr"})
_ID_RE = re.compile(r"(congress|house_ptr|senate_ptr|stock_?watcher|ptr_filings)", re.I)


def attest_state(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """{"on": bool, "why": str} -- the switch as read now."""
    e = os.environ if env is None else env
    raw = str(e.get(ENV, "")).strip()
    if raw == "1":
        return {"on": True, "why": f"{ENV}=1 (attested by the principal)"}
    if raw:
        return {"on": False, "why": f"{ENV}={raw!r} is not 1: OFF"}
    return {"on": False, "why": f"{ENV} unset: OFF by default"}


def attested(env: Mapping[str, str] | None = None) -> bool:
    """True only when the principal has attested. Every caller asks this, and nothing else."""
    return bool(attest_state(env)["on"])


def is_congress_source(source: Any) -> bool:
    """A roster row (by `kind` or `id`) or a bare source / series / family identifier that
    carries congressional disclosure data."""
    if isinstance(source, Mapping):
        if str(source.get("kind") or "").lower() in CONGRESS_KINDS:
            return True
        return any(_ID_RE.search(str(source.get(k) or "")) for k in ("id", "source", "family"))
    return bool(_ID_RE.search(str(source or "")))


def refused(source: Any, env: Mapping[str, str] | None = None) -> bool:
    """True when `source` is congressional and the switch is OFF: the caller reads UNMEASURED."""
    return is_congress_source(source) and not attested(env)


def missed_growth_line(source_id: str) -> dict[str, Any]:
    """The growth-governance bill for holding this source. Priced UNMEASURED, never zero."""
    return {"rail": RAIL, "source": str(source_id), "value": None, "status": "UNMEASURED",
            "verdict": "UNMEASURED", "two_sided": True,
            "forgone": ("the congressional disclosure series and every cell it would condition "
                        "or mint (direct, indirect and allocation-state uses)"),
            "why": (f"{source_id} forgone while {ENV} is unset ({LEGAL_BASIS}); the growth given "
                    "up is UNMEASURED because the reports were never read -- set the switch, or "
                    "retire the gate, to price it"),
            "legal_basis": LEGAL_BASIS, "revert": f"the principal sets {ENV}=1"}


def held_verdict(source_id: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """What a fetcher or reader reports in place of data while the switch is OFF."""
    return {"status": HELD, "source": str(source_id), "switch": ENV,
            "switch_read": attest_state(env), "requests": 0, "reading": "UNMEASURED",
            "legal_basis": LEGAL_BASIS, "missed_growth": missed_growth_line(source_id)}

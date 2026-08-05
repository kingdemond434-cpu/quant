#!/usr/bin/env python3
"""L1.54 clause 1, measured: which LLM organs are still ONE model away from producing nothing?

WHY THIS FENCE EXISTS RATHER THAN A REWRITE. Twelve organs read data/secrets/llm_panel.json and
kimi_hunter proved what a single-route organ costs -- scheduled 56 times a week, one unavailable
model string, and it produced literally nothing since it was built: no artifact, no ledger row, no
complaint. Rewriting eleven more files in one pass would be eleven untested changes to the desk's
whole reasoning layer at once. Naming them turns an assumed exposure into a ranked, tracked one
that the conversion queue works down (L1.53), and turns "the LLM side is maxed" from a claim into
a number.

WHAT IT MEASURES. For every script referencing the roster: does it resolve routes through
libs/ops/llm_route (ROUTED), or does it pick one model and stop (SINGLE-ROUTE)? A routed organ's
chain is additionally checked for SOUNDNESS -- depth, family diversity, and a free tail ordered
last -- because a chain of four versions of one vendor's model is one opinion four times, and a
free tier ordered first spends nothing while a paid route that would have answered goes untried.

EXIT 0 ALWAYS. This is a STATE fence, not a LAW fence (L1.37): it reports a conversion backlog
that is real and known, and failing the build on it would block every push until eleven unrelated
organs were rewritten. The artifact is the deliverable; run_max_push ranks it like any other
below-ceiling aspect.

    python scripts/check_llm_routing.py [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.llm_route import chain_is_sound  # noqa: E402

_OUT = _ROOT / "data/llm_routing.json"
#: The roster FILENAME a script must mention to be an LLM organ. Not a credential --
#: S105 fires on the name, not the value, so the marker is renamed rather than
#: blanket-ignored: a real hardcoded secret must still trip this rule here.
_ROSTER_FILENAME = "llm_panel.json"


def _chain_literal(tree: ast.Module) -> list[str] | None:
    """A module-level MODEL_CHAIN tuple/list of plain strings, if one is declared."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "MODEL_CHAIN" not in names or not isinstance(node.value, ast.Tuple | ast.List):
            continue
        vals = [e.value for e in node.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        return vals or None
    return None


def audit(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    organs: list[dict[str, Any]] = []
    for path in sorted((root / "scripts").glob("*.py")):
        try:
            src = path.read_text("utf-8")
        except OSError:
            continue
        if _ROSTER_FILENAME not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        routed = "libs.ops.llm_route" in src or "llm_route import" in src
        chain = _chain_literal(tree)
        row: dict[str, Any] = {
            "script": f"scripts/{path.name}",
            "status": "ROUTED" if routed else "SINGLE-ROUTE",
            "declares_chain": chain is not None,
            "chain_len": len(chain) if chain else 0,
        }
        if chain:
            ok, why = chain_is_sound(chain)
            row["chain_sound"] = ok
            row["chain_note"] = why
        elif not routed:
            row["chain_note"] = ("resolves one model from the roster and stops -- an unavailable "
                                 "model, an exhausted balance or one transport error produces "
                                 "nothing, and on a scheduled organ that is silent")
        organs.append(row)

    routed_n = sum(1 for o in organs if o["status"] == "ROUTED")
    unsound = [o["script"] for o in organs if o.get("chain_sound") is False]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.54 clause 1 -- a chain, never a single name",
        "n_organs": len(organs),
        "n_routed": routed_n,
        "n_single_route": len(organs) - routed_n,
        "routed_fraction": round(routed_n / len(organs), 3) if organs else None,
        "unsound_chains": unsound,
        "single_route": [o["script"] for o in organs if o["status"] == "SINGLE-ROUTE"],
        "organs": organs,
        "note": ("SINGLE-ROUTE is a conversion backlog, not a broken organ: each still works when "
                 "its one model answers. It is listed because the failure mode is SILENT -- "
                 "kimi_hunter fired 56 times a week and produced nothing, and nothing said so."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = audit()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"llm routing (L1.54): {rep['n_routed']}/{rep['n_organs']} organs routed "
              f"({rep['routed_fraction']})")
        for s in rep["single_route"]:
            print(f"  SINGLE-ROUTE {s}")
        for s in rep["unsound_chains"]:
            print(f"  UNSOUND CHAIN {s}")
    print(f"-> {_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

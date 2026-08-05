#!/usr/bin/env python3
"""Compile the ONE canonical machine graveyard: data/graveyard_priors.json.

The novelty gate (`libs/alpha_factory/hypothesis_novelty`) eats `PriorIdea` rows. Until now the
desk's record of dead ground lived in four disjoint substrates -- the `docs/graveyard.md` table, the
`research_memory` ledger, the `research_candidates` reject rows spread over several sqlite files,
and prose -- and NONE of them in the shape the gate eats. So the gate had no corpus, and therefore
no production caller. This script is the missing compiler.

SOURCES
  A `docs/graveyard.md`               -- free-text class kills, each with a verdict, tag and lesson.
  B `research_memory` (result=failure) -- the conversion loop's own logged experiment failures.
  C `research_candidates` (rejected)   -- every machine-generated candidate the gauntlet killed,
                                          across every real research sqlite in data/.

DEDUPE -- the point of the exercise. Thousands of reject rows are not thousands of dead ideas:
they are a few dozen dead MECHANISMS re-tested across symbols and parameter values. Collapsing
them is what turns a log into a prior set.

  * structured rows (source C) collapse on their MECHANISM SIGNATURE -- family, subtype, mechanism
    and the param KEY set. Symbol and param VALUES are deliberately NOT part of the key: the
    desk's own law makes the mechanism the screening unit (`TWO_STAGE_DISCOVERY_LAW`,
    GAP_REGISTER #71 -- "the screening unit becomes the MECHANISM with several constructions
    pooled under ONE pre-registration"), and `run_discovery`'s docstring names parameter sweeps as
    DSR p-hacking. A dead rule on a fifteenth symbol, or at a fourth lookback, is re-tested ground.
    The discarded detail is not lost -- symbols and param values are written into the statement
    text, where they still influence the statement half of the similarity blend.
  * free-text rows (sources A and B) collapse on their normalised statement.

FEATURES. Structured rows declare features (family/subtype/mechanism/param-keys) because their
mechanism is machine-known. Free-text rows declare none, so they match on statement similarity --
which is exactly why the matcher's text path has to be good (see the TF-IDF path in the gate).

Read-only over its sources. No keys, no network, no LLM. Run from the repo root:

    .venv/bin/python scripts/build_graveyard_priors.py
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.alpha_factory.hypothesis_novelty import PriorIdea  # noqa: E402

# The renderer is SHARED with live generation (libs/autodiscovery/novelty.py). Both sides of the
# similarity comparison must render identically or the gate silently decays to 0% recall, so
# there is exactly one implementation and it lives where a lib can import it.
from libs.alpha_factory.hypothesis_render import (  # noqa: E402
    candidate_features,
    candidate_statement,
    params_keys,
    params_text,
)

_params_keys = params_keys      # retained: the module's own internal call sites
_params_text = params_text

GRAVEYARD_MD = ROOT / "docs/graveyard.md"
RESEARCH_DB = ROOT / "data/sor_research.sqlite"
OUT = ROOT / "data/graveyard_priors.json"

# Every real research store. `sor_smoke` and `sor_live_demo` are fixtures, not research history.
CANDIDATE_DBS = (
    "data/sor_research.sqlite",
    "data/sor_crypto.sqlite",
    "data/sor_autodiscovery.sqlite",
    "data/sor_research_lake.sqlite",
    "data/sor_research_lake_v2.sqlite",
    "data/alpha_registry.sqlite",
)

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    """Normalised form used as the free-text dedupe key."""
    return _WS.sub(" ", text.strip().lower())


# --------------------------------------------------------------- A: docs/graveyard.md ----------
def graveyard_md_priors(path: Path = GRAVEYARD_MD) -> list[PriorIdea]:
    """Parse the graveyard markdown table into priors (one per class kill)."""
    if not path.exists():
        return []
    out: list[PriorIdea] = []
    for line in path.read_text("utf-8").splitlines():
        if not line.startswith("|"):
            continue
        if set(line) <= set("|- "):  # separator row
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        name, verdict, tag = cells[0], cells[1], cells[2]
        if name.lower() in ("hypothesis", "name", "signal", "strategy"):  # header row
            continue
        lesson = cells[3] if len(cells) > 3 else ""
        out.append(
            PriorIdea(
                id=f"grave:{name[:80]}",
                statement=f"{name} {verdict} {lesson}"[:4000],
                category=f"graveyard/{tag}"[:120],
                lesson=(lesson or verdict)[:600] or None,
            )
        )
    return out


# ------------------------------------------------------------------- B: research_memory ---------
def research_memory_priors(db: Path = RESEARCH_DB) -> list[PriorIdea]:
    """Every logged FAILURE in the research-memory ledger, as a prior."""
    if not db.exists():
        return []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = list(
            con.execute(
                "SELECT id, category, statement, lessons, failure_cause, failure_stage, "
                "metrics_json FROM research_memory WHERE result='failure'"
            )
        )
    except sqlite3.Error:
        return []
    finally:
        con.close()
    out: list[PriorIdea] = []
    for r in rows:
        # --axis, when logged, is genuine machine-known mechanism information: keep it as a feature.
        feats: tuple[str, ...] = ()
        try:
            axis = (json.loads(r["metrics_json"] or "{}") or {}).get("axis")
        except (json.JSONDecodeError, TypeError):
            axis = None
        if axis:
            feats = (f"axis:{str(axis).strip().lower()}",)
        cause = " ".join(x for x in (r["failure_cause"], r["failure_stage"]) if x)
        out.append(
            PriorIdea(
                id=f"rm:{r['id']}",
                statement=r["statement"][:4000],
                category=f"research_memory/{r['category']}"[:120],
                features=feats,
                lesson=((r["lessons"] or "") + (f" [failed: {cause}]" if cause else ""))[:600]
                or None,
            )
        )
    return out


# --------------------------------------------------------------- C: research_candidates ---------
def candidate_priors(
    dbs: Iterable[str] = CANDIDATE_DBS,
    *,
    exclude_campaigns: Sequence[str] = (),
    include_campaigns: Sequence[str] = (),
) -> tuple[list[PriorIdea], dict[str, int]]:
    """Collapse every rejected candidate row into one prior per mechanism signature.

    ``include_campaigns`` (empty = all) restricts the corpus to named campaigns. The recall replay
    uses it to build a prior set that is strictly EARLIER in time than its test set -- without it,
    later campaigns would leak into the priors and the recall number would be look-ahead, the exact
    defect three graveyard entries were opened for.
    """
    excluded = set(exclude_campaigns)
    included = set(include_campaigns)
    # signature -> aggregated evidence
    agg: dict[tuple[str, ...], dict] = {}
    raw = 0
    per_db: dict[str, int] = {}
    for rel in dbs:
        path = ROOT / rel
        if not path.exists():
            continue
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            rows = list(
                con.execute(
                    "SELECT campaign_id, family, subtype, symbol, params_json, mechanism, "
                    "rejection_reason FROM research_candidates WHERE status='rejected'"
                )
            )
        except sqlite3.Error:
            rows = []
        finally:
            con.close()
        n_used = 0
        for r in rows:
            if r["campaign_id"] in excluded:
                continue
            if included and r["campaign_id"] not in included:
                continue
            n_used += 1
            raw += 1
            sig = candidate_features(
                r["family"] or "", r["subtype"] or "", r["mechanism"] or "", r["params_json"] or ""
            )
            slot = agg.setdefault(
                sig,
                {"family": r["family"] or "", "subtype": r["subtype"] or "",
                 "mechanism": r["mechanism"] or "", "params_json": r["params_json"] or "",
                 "symbols": set(), "reasons": {}},
            )
            slot["symbols"].add(r["symbol"] or "")
            reason = (r["rejection_reason"] or "").strip()
            if reason:
                slot["reasons"][reason] = slot["reasons"].get(reason, 0) + 1
        per_db[rel] = n_used

    out: list[PriorIdea] = []
    for sig, slot in sorted(agg.items()):
        top = max(slot["reasons"].items(), key=lambda kv: kv[1])[0] if slot["reasons"] else ""
        out.append(
            PriorIdea(
                id=f"cand:{slot['family']}/{slot['subtype']}"
                   + (f"/{'+'.join(_params_keys(slot['params_json']))}"
                      if _params_keys(slot["params_json"]) else ""),
                statement=candidate_statement(
                    slot["family"], slot["subtype"], slot["mechanism"],
                    slot["params_json"], sorted(slot["symbols"]),
                ),
                category=f"candidate/{slot['family']}"[:120],
                features=sig,
                lesson=(f"{len(slot['symbols'])} instrument-instances tested, all rejected"
                        + (f" -- most common gauntlet verdict: {top}" if top else ""))[:600],
            )
        )
    per_db["_raw_rows"] = raw
    return out, per_db


# ------------------------------------------------------------------------------ compile ---------
def build(*, exclude_campaigns: Sequence[str] = ()) -> tuple[list[PriorIdea], dict]:
    """Merge all three sources, dedupe, and return the canonical prior set plus its provenance."""
    a = graveyard_md_priors()
    b = research_memory_priors()
    c, per_db = candidate_priors(exclude_campaigns=exclude_campaigns)

    merged: list[PriorIdea] = []
    seen: set[str] = set()
    dropped = 0
    # The dedupe key is SOURCE-SPECIFIC, never inferred from `features`. Structured rows collapse
    # on their mechanism signature; free-text rows collapse on their normalised statement. (An
    # earlier cut keyed anything carrying features on those features, which silently collapsed
    # every research_memory row that shared an `axis` tag into one -- 61 real failures erased.)
    # Structured priors are emitted first so that on a genuine tie the machine-known row wins.
    for prior, structured in [*((p, True) for p in c), *((p, False) for p in [*a, *b])]:
        key = ("sig:" + "|".join(prior.features)) if structured else ("txt:" + _norm(prior.statement))
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        merged.append(prior)

    counts = {
        "graveyard_md": len(a),
        "research_memory_failures": len(b),
        "candidate_rows_raw": per_db.pop("_raw_rows", 0),
        "candidate_mechanisms_deduped": len(c),
        "candidate_rows_per_db": per_db,
        "merged_before_dedupe": len(a) + len(b) + len(c),
        "duplicates_dropped": dropped,
        "total": len(merged),
        "excluded_campaigns": list(exclude_campaigns),
    }
    return merged, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--exclude-campaign", action="append", default=[],
                    help="campaign_id to hold out (used by the recall replay)")
    args = ap.parse_args()

    priors, counts = build(exclude_campaigns=args.exclude_campaign)
    payload = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "schema": "PriorIdea[] -- libs/alpha_factory/hypothesis_novelty.PriorIdea",
        "counts": counts,
        "priors": [p.model_dump() for p in priors],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, sort_keys=False), "utf-8")

    print(f"graveyard priors -> {out}")
    print(f"  A docs/graveyard.md            : {counts['graveyard_md']}")
    print(f"  B research_memory (failures)   : {counts['research_memory_failures']}")
    print(f"  C research_candidates (raw)    : {counts['candidate_rows_raw']}")
    for db, n in counts["candidate_rows_per_db"].items():
        print(f"      {db:38s} {n}")
    print(f"  C collapsed to mechanisms      : {counts['candidate_mechanisms_deduped']}")
    print(f"  merged before dedupe           : {counts['merged_before_dedupe']}")
    print(f"  duplicates dropped             : {counts['duplicates_dropped']}")
    print(f"  TOTAL canonical priors         : {counts['total']}")
    return 0


def load_priors(path: Path = OUT) -> list[PriorIdea]:
    """Read the compiled canonical graveyard back as `PriorIdea` rows (for the gate's callers)."""
    if not path.exists():
        return []
    payload = json.loads(path.read_text("utf-8"))
    return [PriorIdea(**row) for row in payload.get("priors", [])]


if __name__ == "__main__":
    raise SystemExit(main())

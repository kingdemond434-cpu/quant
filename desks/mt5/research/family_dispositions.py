"""Every family name the judge can never build, and what the desk does about each one.

THE MEASUREMENT (JUDGE_COVERAGE.json, 2026-11-17). Fourteen family names hold docket cells that
`judged_total: 0` on every reading, because `scripts/external_gauntlet.build_cell` resolves a
family through exactly two lookups -- `mt5desk.families.family_<name>` and
`mt5desk.families_orthogonal.ORTHOGONAL_FAMILIES` -- and none of the fourteen is in either. Each
cell is built, refused with "no implementation of family", parked as `build_failed`, re-admitted
on the retry clock and refused again. Nothing about that is visible as a reason.

Each name gets exactly ONE of three dispositions here, decided by reading the code that minted it
and the code that would have to judge it:

  ALIAS          the name is a SPELLING of a mechanism the judge already builds, with the same
                 rule, the same chart and the same direction. A fresh descendant is minted under
                 the registered family (`alias_descendants`), exactly as
                 `family_input_descendants` mints completed peer/factor cells: the original row
                 is kept with its record, the descendant is a new claim born this pass and a
                 charged trial through the normal gates. Nothing is rewritten in place.
  NEVER_JUDGED   no exact builder is reachable from the judge, for a NAMED reason. The rows stay
                 on the docket and in the bank; each carries `never_judged_reason` so every
                 reader reports it as UNMEASURED with its cause (L1.28a) instead of as backlog
                 that a judge owes, or as a cell that silently vanished.

A name that would need a BUILDER is recorded as NEVER_JUDGED with the code
`BUILDER_NEEDS_CLOSURE_EDIT` and the file the registration would have to go in: both registries
are box entry-point import closure (`ops/money_closure.txt`), and a builder the judge cannot reach
is not a builder.

WHAT IS DELIBERATELY NOT AN ALIAS, and why (each one measured, not assumed):

  fair_value_gap -> ict_fvg. `run_edges_macro_fusion_sweep` calls this an "unambiguous rename". It
      is not the same rule. The retired `family_fair_value_gap` (326166543) rests a LIMIT order
      inside the gap (`trigger`, `wait_bars`, `fill_depth`), requires `min_gap_atr`, stops beyond
      the far edge of the gap and has no trend filter. `family_ict_fvg` enters at the next open,
      stops at 1.2 ATR and fires only with the 8/34 EMA trend. Same pattern, different trade:
      judging ict_fvg under fair_value_gap's name would certify a strategy nobody proposed.
  anti_donchian_breakout / anti_three_bar_momentum -> a sign-flipped main-lane twin. There is no
      twin: neither `donchian_breakout` nor `three_bar_momentum` exists in either registry. Both
      anti-signals are `-signal` of the scalp lane's own `scalp_family_expansion._base_signals`,
      built bar-by-bar by `mt5desk.scalp_families.family_scalp` and judged by
      `scripts/scalp_gauntlet.py`. The builder exists; registering it with the main judge is the
      closure edit named below.
  ny_open@M15 -> opening_range. The forward clocks this name came from
      (`XAUUSD.ny_open@M15[#...]`, desks/mt5/data/sleeve_registry.json) are
      `session_range_breakout` with range 13->14 UTC on M15 -- the variant
      `session_chart_equivalents` labels `ANCHOR_HOURS[13]@M15`. It IS an alias, of
      session_range_breakout, not of opening_range (a different rule: `open_hour`/`range_bars`
      with min/max range-ATR bounds).
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

VERSION = "family-alias-descendant-v1"

#: Provenance a descendant may inherit. Never a verdict, a statistic or a registry id: the
#: descendant is a new claim and earns its own evidence (same rule as family_input_descendants).
SAFE_FIELDS = ("source", "producer", "origin", "title", "url", "mechanism",
               "mechanism_status", "mechanism_note", "parent_ids", "parent")

ALIAS = "ALIAS"
NEVER_JUDGED = "NEVER_JUDGED"

#: The codes a never-judged family can carry. Each names who resolves it.
BUILDER_NEEDS_CLOSURE_EDIT = "BUILDER_NEEDS_CLOSURE_EDIT"
MECHANISM_LABEL_NOT_A_RULE = "MECHANISM_LABEL_NOT_A_RULE"
CONDITIONER_NOT_A_SLEEVE = "CONDITIONER_NOT_A_SLEEVE"
NO_SERIES_NO_PIT_CLOCK = "NO_SERIES_NO_PIT_CLOCK"
NO_FAMILY_NAMED = "NO_FAMILY_NAMED"
#: Stamped on an ORIGINAL row whose descendant carries the registered family.
ALIASED_TO_REGISTERED_FAMILY = "ALIASED_TO_REGISTERED_FAMILY"

REASON_CODES: frozenset[str] = frozenset({
    BUILDER_NEEDS_CLOSURE_EDIT, MECHANISM_LABEL_NOT_A_RULE, CONDITIONER_NOT_A_SLEEVE,
    NO_SERIES_NO_PIT_CLOCK, NO_FAMILY_NAMED, ALIASED_TO_REGISTERED_FAMILY})


@dataclass(frozen=True)
class Alias:
    """`name` is spelled `target` with `base_params`; a row's own params override them."""

    target: str
    base_params: dict[str, Any]
    why: str


@dataclass(frozen=True)
class NeverJudged:
    code: str
    why: str
    route: str
    closure_file: str | None = None
    builder: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


#: Exact spellings of a registered mechanism. Pinned by tests against the target's signature
#: and, where the box state is present, against the forward clock the name was read from.
ALIASES: dict[str, Alias] = {
    "ny_open@M15": Alias(
        target="session_range_breakout",
        # `XAUUSD.ny_open@M15` in desks/mt5/data/sleeve_registry.json, its frozen identity.
        base_params={"timeframe": "M15", "range_start": 13, "range_end": 14, "signal_at": 14,
                     "wait_bars": 12, "ttl_bars": 12, "rr": 2.0},
        why=("a forward-clock KEY read as a family: `axis_registry.parse_shadow_key` takes the "
             "second segment of `XAUUSD.ny_open@M15#rr=1.5` as the family, and every such clock "
             "is session_range_breakout, range 13->14 UTC, signal at 14, on M15 "
             "(sleeve_registry identity). Both sides fire, as for every session_range_breakout "
             "cell; the registry's `direction: LONG` is the placeholder every sleeve carries")),
}

_SCALP_ROUTE = ("the scalp lane judges it: builder `mt5desk.scalp_families.family_scalp`, "
                "gauntlet `scripts/scalp_gauntlet.py`. The main judge reaches it only once an "
                "entry for it is registered in ORTHOGONAL_FAMILIES (box closure, principal-gated); "
                "a registered entry still needs the recipe (session, stop_atr, target_atr, "
                "max_hold) on the cell, which rows minted from forward-clock keys do not carry")


def _label(code: str, why: str, route: str) -> NeverJudged:
    return NeverJudged(code=code, why=why, route=route)


NEVER_JUDGED_FAMILIES: dict[str, NeverJudged] = {
    "anti_donchian_breakout": NeverJudged(
        code=BUILDER_NEEDS_CLOSURE_EDIT,
        why=("fade of the scalp lane's 20-bar Donchian break (`-donchian_breakout` in "
             "scalp_family_expansion._base_signals). No `donchian_breakout` exists in either "
             "judge registry, so there is no main-lane twin to sign-flip"),
        route=_SCALP_ROUTE,
        closure_file="desks/mt5/mt5desk/families_orthogonal.py",
        builder="mt5desk.scalp_families.family_scalp(df, family='anti_donchian_breakout', ...)"),
    "anti_three_bar_momentum": NeverJudged(
        code=BUILDER_NEEDS_CLOSURE_EDIT,
        why=("fade of the scalp lane's three-bar 1.25-ATR burst (`-three_bar_momentum` in "
             "scalp_family_expansion._base_signals). No `three_bar_momentum` exists in either "
             "judge registry, so there is no main-lane twin to sign-flip"),
        route=_SCALP_ROUTE,
        closure_file="desks/mt5/mt5desk/families_orthogonal.py",
        builder="mt5desk.scalp_families.family_scalp(df, family='anti_three_bar_momentum', ...)"),
    "fair_value_gap": NeverJudged(
        code=BUILDER_NEEDS_CLOSURE_EDIT,
        why=("a distinct price-only rule whose builder was retired: three-bar gap, LIMIT entry "
             "resting inside the gap for wait_bars, min_gap_atr, stop beyond the far edge, no "
             "trend filter (family_fair_value_gap, 326166543). ict_fvg is NOT it: market entry "
             "at the next open, 1.2-ATR stop, 8/34 EMA trend filter"),
        route=("restore `family_fair_value_gap` (closed bars i-2..i, resting trigger from i+1: "
               "causal) in the families module, principal-gated"),
        closure_file="desks/mt5/mt5desk/families.py",
        builder="family_fair_value_gap at commit 326166543"),
    "conditioning_model": _label(
        CONDITIONER_NOT_A_SLEEVE,
        "model_search / factor_model_coevolution enqueue a (representation, learner) cell with "
        "a net predictive gain and, in their own words, 'no entry, no stop and no size'",
        "the deepening worker writes a family recipe around it; that recipe is the cell the "
        "judge can build"),
    "regional_information": _label(
        NO_SERIES_NO_PIT_CLOCK,
        "pack_cells' world lane mints {source, region, country, kind} with no series and no "
        "point-in-time clock: 2 of 270 grounds have a lake series, 0 cells name a ground with "
        "ten parseable knowable_at stamps (scripts/check_family_evaluability.py)",
        "a ground that gains a stamped series becomes an exogenous_conditioner cell"),
    "unknown": _label(
        NO_FAMILY_NAMED,
        "the literal UNKNOWN placeholder: the producer could not name a family, so there is no "
        "rule to build and nothing to alias",
        "the producer that minted it names the family it meant"),
}

#: transformation_miners' MECHANISM CONTRACTS, which some producers write into `family`. A
#: mechanism is one payer and several expressions (`axis_registry._FAMILY_GROUPS`), so a label
#: maps to many families and is never an alias of any one of them.
MECHANISM_LABELS: tuple[str, ...] = (
    "carry_rollover", "execution_microstructure", "fx_fixing_flow", "macro_release",
    "positioning_crowding", "relative_value_dislocation", "volatility_shock")

#: Labels whose expressions also need data that is not a price series on this desk.
_LABEL_DATA: dict[str, str] = {
    "macro_release": "a release calendar with actuals (event_reaction / macro_conditional)",
    "positioning_crowding": "COT positioning (cot_* families)",
    "carry_rollover": "the venue's swap table (carry)",
    "execution_microstructure": "the tape / spread surface (liquidity_regime, execution_state)",
}

for _lbl in MECHANISM_LABELS:
    NEVER_JUDGED_FAMILIES[_lbl] = _label(
        MECHANISM_LABEL_NOT_A_RULE,
        f"{_lbl!r} is a mechanism contract (transformation_miners / axis_registry), not a rule: "
        "it names the payer and several expressions of it, so no one family is its alias"
        + (f"; its expressions read {_LABEL_DATA[_lbl]}" if _lbl in _LABEL_DATA else ""),
        "the producer names the expression it meant (axis_registry._FAMILY_GROUPS lists them)")


def expressions_of(label: str) -> list[str]:
    """The registered expressions axis_registry files under a mechanism label, for the report."""
    try:
        from research import axis_registry as ar
        groups = getattr(ar, "_FAMILY_GROUPS", {}) or {}
    except Exception:
        return []
    out: list[str] = []
    for key, fams in groups.items():
        if str(key).split(" ", 1)[0] == label:
            out.extend(str(fams).split())
    return sorted(set(out))


def disposition(family: Any) -> dict[str, Any] | None:
    """The named disposition of one family name, or None for a family this table does not hold."""
    fam = str(family or "")
    alias = ALIASES.get(fam)
    if alias is not None:
        return {"disposition": ALIAS, "alias_of": alias.target,
                "never_judged_reason": ALIASED_TO_REGISTERED_FAMILY,
                "base_params": dict(alias.base_params), "why": alias.why}
    nj = NEVER_JUDGED_FAMILIES.get(fam)
    if nj is None:
        return None
    out: dict[str, Any] = {"disposition": NEVER_JUDGED, "never_judged_reason": nj.code,
                           "why": nj.why, "route": nj.route}
    if nj.closure_file:
        out["closure_file"] = nj.closure_file
    if nj.builder:
        out["builder"] = nj.builder
    if nj.code == MECHANISM_LABEL_NOT_A_RULE:
        out["expressions"] = expressions_of(fam)
    return out


def never_judged_reason(family: Any) -> str | None:
    d = disposition(family)
    return None if d is None else str(d["never_judged_reason"])


_SUFFIX_PAIR = re.compile(r"([A-Za-z][A-Za-z_]*?)=([-+]?\d+(?:\.\d+)?)(?=_[A-Za-z]|$)")


def _suffix_params(row: dict[str, Any], name: str, allowed: set[str]) -> dict[str, Any]:
    """Numeric params a forward-clock key's `#...` suffix carries, when the row names that key.

    `XAUUSD.ny_open@M15#rr=1.5_wait_bars=8` is the clock the row descends from; the parse that
    turned it into a family dropped the suffix. Recovered only for keys the target's base params
    already name, and only numeric values -- anything else stays the base identity.
    """
    keys: list[str] = []
    for f in ("parent", "parent_cell", "cell"):
        v = row.get(f)
        if isinstance(v, str):
            keys.append(v)
    pids = row.get("parent_ids")
    if isinstance(pids, list):
        keys.extend(str(p) for p in pids if isinstance(p, str))
    for key in keys:
        head, sep, tail = key.partition("#")
        if not sep or not head.endswith("." + name):
            continue
        out: dict[str, Any] = {}
        for k, v in _SUFFIX_PAIR.findall(tail):
            if k in allowed:
                out[k] = int(v) if re.fullmatch(r"[-+]?\d+", v) else float(v)
        return out
    return {}


def alias_params(row: dict[str, Any]) -> dict[str, Any] | None:
    """The descendant's params for an alias row: base identity, then the key's suffix, then the
    row's own params (the variant a producer applied). None when the row is not an alias."""
    name = str(row.get("family") or "")
    alias = ALIASES.get(name)
    if alias is None:
        return None
    raw = row.get("params")
    own: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
    return {**alias.base_params,
            **_suffix_params(row, name, set(alias.base_params)),
            **own}


def alias_descendants(rows: list[dict[str, Any]], *, identity: Callable[[dict[str, Any]], str],
                      now: datetime | None = None
                      ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """New children under the registered family for every alias row; inputs are never mutated."""
    at = (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
    present = {identity(r) for r in rows if isinstance(r, dict)}
    children: list[dict[str, Any]] = []
    by_alias: Counter[str] = Counter()
    targets = already = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        params = alias_params(row)
        if params is None:
            continue
        targets += 1
        name = str(row["family"])
        alias = ALIASES[name]
        child = {k: row[k] for k in SAFE_FIELDS if k in row}
        child.update({"symbol": str(row.get("symbol") or row.get("sym") or ""),
                      "family": alias.target, "params": params,
                      "timeframe": str(params.get("timeframe") or "H1").upper()})
        child["alias_descendant"] = {"version": VERSION, "alias_of": name,
                                     "parent_identity": identity(row), "at": at}
        child["available_time"] = at
        child["ingested_time"] = at
        child["source_version"] = VERSION
        payload = {"symbol": child["symbol"], "family": alias.target, "params": params,
                   "parent_identity": identity(row), "version": VERSION}
        child["payload_hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        key = identity(child)
        if key in present:
            already += 1
            continue
        present.add(key)
        children.append(child)
        by_alias[name] += 1
    assert targets == len(children) + already
    report: dict[str, Any] = {"at": at, "version": VERSION, "targets": targets,
                              "created": len(children), "already_present": already,
                              "created_by_alias": dict(by_alias)}
    return children, report


def stamp_never_judged(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Name the reason on every row this table holds; keep every row. Returns the census."""
    by_family: Counter[str] = Counter()
    by_reason: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, dict):
            continue
        d = disposition(row.get("family"))
        if d is None:
            continue
        row["never_judged_reason"] = d["never_judged_reason"]
        if d["disposition"] == ALIAS:
            row["alias_of"] = d["alias_of"]
        by_family[str(row.get("family"))] += 1
        by_reason[str(d["never_judged_reason"])] += 1
    return {"stamped": sum(by_family.values()), "by_family": dict(by_family.most_common()),
            "by_reason": dict(by_reason.most_common()),
            "rule": ("a family the judge cannot build is reported UNMEASURED under a named "
                     "reason and kept; an exact spelling of a registered family gets a fresh "
                     "descendant under that family, charged through the normal gates")}


def table() -> dict[str, dict[str, Any]]:
    """Every family this module disposes of, for reports."""
    names = sorted({*ALIASES, *NEVER_JUDGED_FAMILIES})
    return {n: d for n in names if (d := disposition(n)) is not None}

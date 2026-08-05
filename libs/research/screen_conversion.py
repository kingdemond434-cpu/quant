"""SCREEN CONVERSION -- every scored cell on disk becomes a Stage-A candidate, or says why not.

THE DEFECT THIS CLOSES, measured 2026-08-05. The desk had 135 scored screen cells sitting on disk
and exactly SIX of them could reach a forward slot:

    data/primary_market_flow_screen.json   `rows`     30 cells   unreachable
    data/vol_risk_premium_screen.json      `rows`     66 cells   unreachable
    data/unlock_event_screen.json          `cells`    27 cells   unreachable
    reports/screen_exchange_netflow.json   `cells`    12 cells   unreachable
    reports/axis_screens/liquidation_*.json `trials`    6 cells   reachable

Not one of the 129 was refuted, retired, or judged. They were UNREADABLE -- `finalize_axis_screens`
speaks one schema (a `trials` list under reports/axis_screens/) and every newer screen writes its
own. So the desk kept generating measurements it could not consume, and then reported the silence
as "no survivors". That is the conversion defect in its purest form: output produced, never
converted, never utilised, and the shortfall invisible because the missing rows never appeared
anywhere to be missed (L1.50 -- an unexploited asset is a defect; L1.53 -- conversion must CATCH UP
to what is being produced, never be caught up to by shrinking it).

WHAT THIS DOES. It reads every JSON artifact under data/ and reports/, finds any list of rows
carrying the harness's scoring signature, and rewrites them into the canonical `trials` shape so
the existing correction layer and the existing spawner can consume them unchanged. No screen is
edited, no verdict is softened, no threshold is touched -- this is a TRANSLATOR.

NOTHING IS HARDCODED. The artifact list is DISCOVERED by walking the tree and testing each row for
the scoring signature, and the field names are resolved through alias tables. A screen written
tomorrow under a name nobody here anticipated is picked up by the same walk, and a field this
module cannot map is RECORDED in `unmapped` rather than dropped -- because a converter that
silently skips what it does not understand reproduces the exact defect it exists to fix, one level
further down.

WHAT IS DISQUALIFIED, AND WHY THAT IS NOT A BAR. Two classes never become candidates:

  * CONTROLS AND DIAGNOSTICS -- `form == "lookahead_control"`, `alignment.is_lookahead_control`,
    the naive contaminated builds. These are run to MEASURE a leak; promoting one is the rule-8
    artifact-as-edge failure.
  * BROKEN MEASUREMENTS -- TIMING-ARTIFACT, SUSPECT-LOOKAHEAD. A cell whose alignment gate fired
    is not a weak edge, it is a number that does not mean what it says.

Everything else is a candidate, INCLUDING SCREEN-WEAK and SCREEN-UNDERPOWERED. That is deliberate
and it is the law: under the two-stage rule Stage A is a RANKING DEVICE WITH ZERO PROMOTION
AUTHORITY, so a Stage-A significance verdict cannot be an admission gate -- using it as one is
letting the ranking device promote, which is precisely what the law forbids. "Underpowered" means
the screen could not see, not that it looked and found nothing (L1.49): of the desk's 228 recorded
negatives only 50 were POWERED. Refusing a forward clock to a cell the screen could not resolve is
how a desk guarantees it never resolves anything.

Pure stdlib. The organ is scripts/finalize_axis_screens.py, which runs this first.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

__all__ = [
    "CONVERTED_PREFIX",
    "canonical_row",
    "convert_all",
    "discover",
    "is_scored_row",
    "write_converted",
]

_ROOT = Path(__file__).resolve().parents[2]

#: Every file this module writes carries it. Nothing without this prefix is ever overwritten, so a
#: hand-written screen report can never be clobbered by a conversion pass.
CONVERTED_PREFIX = "conv_"

#: Where the correction layer and the spawner both look.
_AXIS_DIR = "reports/axis_screens"

#: Trees walked for scored cells. Directories, not files -- a screen added tomorrow under a name
#: nobody anticipated is found by the same walk.
_SEARCH_ROOTS: tuple[str, ...] = ("data", "reports", "web")

#: Field aliases, canonical name -> the spellings seen in the wild, IN PREFERENCE ORDER. Extending
#: this is how a new screen's vocabulary is taught; an unrecognised spelling is reported in
#: `unmapped`, never silently defaulted -- a defaulted zero is a fabricated measurement.
_ALIASES: dict[str, tuple[str, ...]] = {
    "ic": ("ic", "ic_mean", "information_coefficient"),
    "residual_ic": ("residual_ic", "ic_residual"),
    "n": ("n", "n_paired", "n_events", "n_obs", "n_rows"),
    "n_eff": ("n_eff", "n_effective", "neff"),
    "horizon_days": ("horizon_days", "horizon_d", "horizon_calendar_days"),
    "sharpe_momentum": ("sharpe_momentum", "sharpe"),
    "sharpe_reversal": ("sharpe_reversal",),
    "verdict": ("verdict", "label"),
    "t_stat": ("t_stat", "ic_t_stat", "tstat", "current_z"),
    "decontam_passed": ("decontam_passed",),
    "implausible_leak": ("implausible_leak",),
    "min_detectable_ic": ("min_detectable_ic", "detection_floor_ic_unadjusted"),
}

#: A row is a SCORED CELL when it carries an effect estimate and a sample size. Deliberately
#: narrow: a config block or a coverage table must never be mistaken for a screened hypothesis.
_EFFECT_KEYS = frozenset({"ic", "ic_mean", "residual_ic", "t_stat", "ic_t_stat"})
_SIZE_KEYS = frozenset({"n", "n_eff", "n_effective", "n_paired", "n_events", "n_obs"})

#: Verdicts naming a BROKEN measurement rather than a weak one. These can never be candidates: the
#: alignment gate fired, so the number does not mean what it says. This is not a strength bar --
#: SCREEN-WEAK and SCREEN-UNDERPOWERED are absent from this set on purpose.
BROKEN_VERDICTS: frozenset[str] = frozenset({
    "TIMING-ARTIFACT", "SUSPECT-LOOKAHEAD", "NOT-A-CANDIDATE", "NOT-READABLE-HERE",
})

#: Row markers that make a cell a control or diagnostic, however it scored.
_CONTROL_FORMS = frozenset({"lookahead_control", "naive", "control", "shift_control"})


def _first(row: dict[str, Any], canonical: str) -> tuple[Any, str | None]:
    """(value, spelling used). (None, None) when no alias is present -- never a default."""
    for key in _ALIASES.get(canonical, (canonical,)):
        if key in row and row[key] is not None:
            return row[key], key
    return None, None


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def is_scored_row(row: object) -> bool:
    """Does this dict look like a screened hypothesis rather than a config or coverage block?"""
    if not isinstance(row, dict):
        return False
    keys = set(row)
    return bool(keys & _EFFECT_KEYS) and bool(keys & _SIZE_KEYS)


def discover(root: Path | None = None) -> list[dict[str, Any]]:
    """Every (file, key) holding a list of scored cells. Walks the tree -- no artifact list.

    Files already living in the canonical directory are skipped: a `trials` list there is already
    readable, and re-converting it would mint a duplicate hypothesis paying a second Holm slot.
    """
    base = root or _ROOT
    axis_dir = (base / _AXIS_DIR).resolve()
    found: list[dict[str, Any]] = []
    for rel in _SEARCH_ROOTS:
        tree = base / rel
        if not tree.is_dir():
            continue
        for path in sorted(tree.rglob("*.json")):
            if path.resolve().parent == axis_dir:
                continue                       # already canonical, or already converted
            try:
                doc = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError, RecursionError):
                continue                       # unreadable cannot qualify anything
            if not isinstance(doc, dict):
                continue
            for key, value in doc.items():
                if not isinstance(value, list) or not value:
                    continue
                scored = [r for r in value if is_scored_row(r)]
                unscored = [r for r in value if isinstance(r, dict) and not is_scored_row(r)]
                if not _is_screen_list(scored, unscored, len(value)):
                    continue
                found.append({"path": str(path.relative_to(base)), "key": key,
                              "n_rows": len(scored), "n_unscored": len(unscored),
                              "unscored": unscored, "doc": doc, "rows": scored})
    return found


#: Minimum scored cells before a list is treated as a screen. Below this a field-name coincidence
#: is more likely than a screened family.
_MIN_SCORED = 3


def _is_screen_list(scored: list[Any], unscored: list[Any], total: int) -> bool:
    """Is this list a screened family, or a config block whose field names happen to collide?

    A PLAIN MAJORITY TEST WAS WRONG AND COST A WHOLE ARTIFACT. `data/unlock_event_screen.json`
    holds 27 cells, of which the screen itself DECLINED TO SCORE 15 ("UNDERPOWERED: <20 events",
    no t-stat emitted). A majority rule then read 12 < 15 and discarded the entire file -- so the
    12 cells the screen DID score became invisible because of the 15 it had already judged
    unscoreable. That is the L1.41 confusion in a new place: 'not scored' and 'not a screen' are
    different facts, and collapsing them let an honest declaration of low power delete the
    measurements next to it.

    The real discriminator is VOCABULARY, not headcount. Unscored siblings of a screened family
    carry the family's own identifying fields (category, window_days, verdict...); a config block
    that merely happens to contain an `n` does not. So a list qualifies when it has enough scored
    cells to be a family, and its unscored rows either are few or LOOK LIKE the scored ones.
    """
    # A HOMOGENEOUS LIST NEEDS NO HEADCOUNT EVIDENCE. When every row carries the scoring
    # signature there is nothing to disambiguate, so a small screen is still a screen -- and a
    # two-cell screen going invisible for failing a size floor is the same unexploited-asset
    # defect this module exists to fix, one level down. Two is the floor only because a SINGLE
    # dict with an `ic` and an `n` is more plausibly a coincidence than a screened family.
    if not unscored and len(scored) >= 2:
        return True
    if len(scored) < _MIN_SCORED:
        return False
    if len(scored) * 2 >= total:
        return True
    scored_keys: set[str] = set()
    for row in scored:
        if isinstance(row, dict):
            scored_keys |= set(row)
    if not scored_keys:
        return False
    kin = sum(1 for r in unscored
              if isinstance(r, dict) and len(set(r) & scored_keys) * 2 >= len(set(r)))
    return kin * 2 >= len(unscored)          # the unscored rows are siblings, not strangers


#: Scalar fields that identify WHICH hypothesis a row is, as opposed to what it scored. Order is
#: the name's field order. `target` is here because leaving it out collided every VRP row: 66 cells
#: reduced to 33 names, so a forward clock resolved to whichever of two hypotheses came first in
#: the file -- one testing short-vol carry, the other the underlying's return.
_IDENTITY_FIELDS: tuple[str, ...] = (
    "market", "underlying", "asset", "category", "construction", "target", "form", "build",
    "bucket", "level", "side_mapping",
)
_IDENTITY_NUMERIC: tuple[str, ...] = (
    "horizon_days", "horizon_d", "window_days", "bar", "interval_min", "horizon_min",
    "pct_circ_now_min",
)


def _declared_name(row: dict[str, Any]) -> str | None:
    """The screen's OWN identity for this cell, if it declared one.

    Preferred over anything reconstructed: a screen that names its cells (VRP writes
    `type2.name = per_market|AVAX:t90|iv_level|short_vol_carry`) has already solved the identity
    problem for its own vocabulary, and second-guessing it is how a converter invents collisions.
    """
    explicit = row.get("name")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    for value in row.values():
        if isinstance(value, dict):
            nested = value.get("name")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _row_name(row: dict[str, Any], index: int) -> str:
    """A stable identity. Built from whatever identifying fields the row carries, because an
    index-only name would renumber whenever the screen's row order changed and silently re-point
    every downstream dedupe key at a different hypothesis. Uniqueness is enforced separately by
    `_disambiguate`, which can see the whole family and this function cannot."""
    declared = _declared_name(row)
    if declared:
        return declared
    parts = [str(row[k]) for k in _IDENTITY_FIELDS
             if isinstance(row.get(k), (str, int, float)) and str(row[k]).strip()]
    for k in _IDENTITY_NUMERIC:
        v = row.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            parts.append(f"{k}{v:g}")
    return "|".join(parts) if parts else f"cell{index}"


def _disambiguate(trials: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    """Make every name in one artifact unique, using the fields that ACTUALLY differ.

    A NAME THAT IS NOT UNIQUE IS NOT AN IDENTITY, and downstream everything keys on it: dedupe
    decides which hypotheses share a Holm slot, and the forward runner re-finds its cell by name
    every day. With 66 VRP rows collapsing to 33 names, half the forward clocks would have been
    accruing evidence about a hypothesis they were not spawned for -- and nothing would have said
    so, because both rows are real cells that parse cleanly.

    The discriminator is DISCOVERED, never listed: for each colliding group, find the keys whose
    values differ across the group and append them. So the next screen's private vocabulary is
    handled without teaching this module a thing about it, and a group that genuinely cannot be
    told apart is marked rather than silently renumbered.
    """
    groups: dict[str, list[int]] = {}
    for i, t in enumerate(trials):
        groups.setdefault(str(t.get("name", "")), []).append(i)
    for name, idxs in groups.items():
        if len(idxs) < 2:
            continue
        keys: set[str] = set()
        for i in idxs:
            keys |= set(rows[i])
        # Only SCALAR keys, and only ones that vary across the group: a differing float like `ic`
        # is a score, not an identity, so identity fields are preferred and scores are the
        # fallback that at least keeps two real cells apart.
        varying = sorted(
            k for k in keys
            if len({json.dumps(rows[i].get(k), sort_keys=True, default=str) for i in idxs}) > 1
            and all(isinstance(rows[i].get(k), (str, int, float, type(None))) for i in idxs))
        preferred = [k for k in varying if k in _IDENTITY_FIELDS + _IDENTITY_NUMERIC] or varying
        if not preferred:
            for rank, i in enumerate(idxs):
                trials[i]["name"] = f"{name}#{rank}"
                trials[i]["name_collision"] = (
                    "INDISTINGUISHABLE from its siblings on every scalar field -- suffixed by "
                    "position, which is NOT stable across a reordering of the source. Treat this "
                    "cell's identity as unreliable until the screen names its own rows.")
            continue
        for i in idxs:
            suffix = "|".join(f"{k}={rows[i].get(k)}" for k in preferred[:3])
            trials[i]["name"] = f"{name}|{suffix}"
            trials[i]["name_disambiguated_by"] = preferred[:3]


def canonical_row(row: dict[str, Any], index: int, *,
                  mechanism: str = "") -> dict[str, Any]:
    """One scored cell in the shape `finalize_axis_screens` and `paper_sleeves` already read.

    DERIVATIONS ARE FLAGGED, never laundered. Where a screen reports a t-stat but no IC (the
    unlock-event shape), IC is recovered as t/sqrt(n_eff) and the row carries
    `ic_derived_from`, so a reader can always tell a measured number from a reconstructed one.
    NOTHING IS INVENTED: a cell with neither an IC nor a t-stat is returned with `unmapped`
    naming what was missing, and it can qualify nothing.
    """
    out: dict[str, Any] = {}
    unmapped: list[str] = []
    used: dict[str, str] = {}

    for canon in ("ic", "residual_ic", "n", "n_eff", "horizon_days", "sharpe_momentum",
                  "sharpe_reversal", "verdict", "t_stat", "decontam_passed",
                  "implausible_leak", "min_detectable_ic"):
        value, spelling = _first(row, canon)
        if spelling is None:
            continue
        used[canon] = spelling
        out[canon] = value

    out["name"] = _row_name(row, index)
    n_eff = _num(out.get("n_eff"))
    n_raw = _num(out.get("n"))
    if n_eff is None and n_raw is not None:
        n_eff = n_raw
    if n_raw is None and n_eff is not None:
        n_raw = n_eff

    ic = _num(out.get("ic"))
    if ic is None:
        t = _num(out.get("t_stat"))
        if t is not None and n_eff and n_eff > 2:
            ic = t / math.sqrt(n_eff)
            out["ic_derived_from"] = (f"t_stat={t:g} / sqrt(n_eff={n_eff:g}) -- this screen "
                                      "reports a t-statistic and no IC; the recovery is exact "
                                      "under the same normalisation and is flagged so a reader "
                                      "never mistakes it for a directly measured IC")
        else:
            unmapped.append("ic (no `ic` alias and no t_stat/n_eff to recover one from)")
    if ic is not None:
        out["ic"] = round(ic, 6)
    if n_raw is None:
        unmapped.append("n (no sample-size alias present)")
    else:
        out["n"] = int(n_raw)
    if n_eff is not None:
        out["n_eff"] = float(n_eff)

    # Sharpe: the correction layer takes max(|momentum|, |reversal|). A screen reporting neither
    # gets ZERO rather than a guess -- and zero fails the 0.5 floor, so an unmeasured Sharpe can
    # never manufacture a SCREEN-INTERESTING. Fail-closed on the promotion-relevant side.
    if "sharpe_momentum" not in out and "sharpe_reversal" not in out:
        out["sharpe_momentum"] = 0.0
        out["sharpe_reversal"] = 0.0
        unmapped.append("sharpe (neither momentum nor reversal reported; recorded as 0.0, which "
                        "fails the 0.5 floor -- an unmeasured Sharpe must never promote)")

    if "verdict" not in out:
        # NEVER invented as a pass. An unrated cell is still EV-rankable for a forward clock, and
        # saying so is different from claiming the screen rated it.
        out["verdict"] = "SCREEN-UNRATED"
        out["verdict_source"] = ("assigned by conversion -- the source screen carried no verdict "
                                 "field; the cell is rankable but was never rated by its screen")

    verdict = str(out.get("verdict", "")).strip().upper()
    _align = row.get("alignment")
    align: dict[str, Any] = _align if isinstance(_align, dict) else {}
    form = str(row.get("form", "")).strip().lower()
    control_reason = ""
    if align.get("is_lookahead_control") is True:
        control_reason = "declared look-ahead control (alignment.is_lookahead_control)"
    elif form in _CONTROL_FORMS:
        control_reason = f"diagnostic build form={form!r}"
    elif any(verdict.startswith(b) for b in BROKEN_VERDICTS):
        control_reason = (f"verdict {verdict} names a BROKEN measurement -- the alignment gate "
                          "fired, so the number does not mean what it says. This is not a "
                          "strength bar: SCREEN-WEAK and SCREEN-UNDERPOWERED stay candidates.")
    if control_reason:
        out["is_candidate"] = False
        out["conversion_disqualified"] = control_reason

    if mechanism:
        out["mechanism_class"] = mechanism
    for keep in ("alignment", "construction", "market", "underlying", "asset", "bucket", "form",
                 "level", "powered", "excess_resolved", "ic_lag1", "same_period_corr"):
        if keep in row and keep not in out:
            out[keep] = row[keep]
    out["converted_from_fields"] = used
    if unmapped:
        out["unmapped"] = unmapped
    return out


def _axis_name(rel_path: str, key: str) -> str:
    """conv_<file stem>__<row key>. Deterministic: re-running overwrites, never duplicates."""
    stem = re.sub(r"[^a-z0-9]+", "_", Path(rel_path).stem.lower()).strip("_")
    keyslug = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
    return f"{CONVERTED_PREFIX}{stem}__{keyslug}"


def convert_all(root: Path | None = None) -> dict[str, Any]:
    """Discover every scored artifact and build its canonical payload. No writes."""
    base = root or _ROOT
    payloads: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for hit in discover(base):
        doc, rows = hit["doc"], hit["rows"]
        mechanism = str(doc.get("mechanism_class") or doc.get("mechanism") or "")
        trials = [canonical_row(r, i, mechanism=mechanism) for i, r in enumerate(rows)]
        _disambiguate(trials, rows)
        usable = [t for t in trials if "unmapped" not in t or "n (" not in " ".join(t["unmapped"])]
        if not usable:
            skipped.append({"path": hit["path"], "key": hit["key"], "n_rows": hit["n_rows"],
                            "why": "no row carried a usable sample size"})
            continue
        axis = _axis_name(hit["path"], hit["key"])
        payloads.append({
            "axis": axis,
            "converted_from": hit["path"],
            "converted_key": hit["key"],
            "mechanism_class": mechanism,
            "screen": str(doc.get("screen") or doc.get("mechanism_class")
                          or Path(hit["path"]).stem),
            "law": ("Stage-A only (two-stage law): ZERO promotion authority. Admission to a "
                    "forward slot is by EV-rank, never by a Stage-A significance verdict -- "
                    "letting the ranking device gate promotion is what the law forbids."),
            "conversion_note": ("Translated into the canonical trials shape by "
                                "libs/research/screen_conversion.py. No verdict was softened and "
                                "no threshold was moved: the source rows are reproduced with "
                                "their field names resolved, and anything unmappable is named in "
                                "each row's `unmapped` rather than dropped."),
            "trials": trials,
            "n_disqualified": sum(1 for t in trials if t.get("is_candidate") is False),
            # NAMED, never silent. These are rows the SOURCE SCREEN declined to score (no effect
            # estimate emitted at all). Recording the count keeps the shortfall visible instead of
            # letting a converted artifact read as full coverage of its source.
            "n_unscored_in_source": int(hit.get("n_unscored", 0)),
            "unscored_note": ("rows the source screen emitted without an effect estimate -- it "
                              "declined to score them, so there is nothing here to convert. They "
                              "are counted rather than dropped silently: 'the screen could not "
                              "score this' is a finding, not an absence."),
        })
    return {"payloads": payloads, "skipped": skipped,
            "n_artifacts": len(payloads), "n_cells": sum(len(p["trials"]) for p in payloads)}


def write_converted(root: Path | None = None) -> dict[str, Any]:
    """Write every converted payload into the canonical directory. Overwrites only `conv_` files."""
    base = root or _ROOT
    out_dir = base / _AXIS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    result = convert_all(base)
    written: list[str] = []
    for payload in result["payloads"]:
        path = out_dir / f"{payload['axis']}.json"
        if path.exists() and not path.name.startswith(CONVERTED_PREFIX):  # pragma: no cover
            continue                           # never clobber a hand-written screen
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", "utf-8")
        written.append(path.name)
    # A conversion that used to produce a file and no longer does leaves a STALE artifact behind,
    # and a stale screen keeps admitting a hypothesis whose source was deleted. Sweep them.
    live = {f"{p['axis']}.json" for p in result["payloads"]}
    removed = []
    for path in sorted(out_dir.glob(f"{CONVERTED_PREFIX}*.json")):
        if path.name not in live:
            path.unlink()
            removed.append(path.name)
    result["written"] = written
    result["removed_stale"] = removed
    return result

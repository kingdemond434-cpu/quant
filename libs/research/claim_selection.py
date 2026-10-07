"""A CLAIM'S OWN SEARCH IS CHARGED ONCE, TO ONE FAMILY -- and its cells are one breadth unit.

WHY (committee dry run on PR #160, 2026-09-30). 25,520 of the bank's 57,538 cells
(`external_survivors.json`, `source = miner:video_anchor_exit`) trace back to ONE public video
whose reported Sharpe 1.87 was "the MAXIMUM of ~200 searched variations with no multiplicity
charge". `research/htf_anchor_proposer.py` swept that one mechanism across the legal universe
(symbols x charts x anchor multiples x exit arms, plus the operator composed onto ~20 base
families), which is legitimate breadth of TESTING -- and every cell then counted as independent
breadth of DISCOVERY, while the 200 trials the source had already spent choosing its winner were
charged nowhere at all.

WHAT THIS DOES.

  * `selection_trials(text)` reads a source's own statement of its search -- "best of 200
    variations", "the maximum of ~200 searched variations", "optimised over 1,500 combinations",
    "searched about 200 variations" -- and returns N (0 when the text states none).
  * `stamp(row)` gives every cell minted from such a claim the same `claim_family` (one id per
    source seat and claim sentence), `breadth_unit = claim_family`, and
    `claim_selection_trials = N`. It never touches `family`, `params`, `symbol` or any verdict,
    so a judged cell keeps its verdict and gains only the lineage.
  * `libs.research.trial_ledger` groups a stamped row under its `claim_family` and charges the
    family's N ONCE, on top of the family's own effective tests -- never once per cell.
  * `update_ledger` keeps `data/hypotheses/claim_families.json`, the LIFETIME record of every
    claim family and the selection it was charged; `libs.research.experiment_ledger` adds each
    family's N to the lifetime trial census exactly once. A charge only ever ratchets up.
  * `breadth(rows)` is the measurement: cells, independent breadth units (a claim family counts
    as one), `k_eff` (the effective independent bets the lineage implies) and the families
    behind the collapse. `publish_breadth` writes it to `reports/CLAIM_BREADTH.json`, which
    alpha_breadth, the coverage tensor and the Tier-1 scorecard read beside their own numbers.
  * A source that DECLARES its search (`claim_selection_trials`, `claims_searched`,
    `variations_searched`) is charged that number, never less, even when its prose states none.
  * `claim_charge(row)` is the provider the deflated-Sharpe charge reads: the largest selection
    any record of the row's claim family carries -- its own declaration, its own words, or the
    lifetime ledger (by claim family, or by genome id for a cell long gone from the docket).

WHAT IT IS NOT. Nothing is removed, capped or re-ordered: every cell is still built and judged.
Only the COUNTING changes -- one searched claim is one unit of breadth and 200 trials of
multiplicity, which is the harder direction on both.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "desks" / "mt5" / "data" / "hypotheses" / "claim_families.json"
#: The published breadth measurement: cells, breadth units and k_eff from the claim lineage.
BREADTH_REPORT = ROOT / "desks" / "mt5" / "reports" / "CLAIM_BREADTH.json"
UNMEASURED = "UNMEASURED"
#: Fields in which a producer DECLARES how many claims/variations its source searched. A
#: declaration is charged as stated -- never less -- whether or not the prose repeats it.
DECLARED_KEYS: tuple[str, ...] = ("claim_selection_trials", "claims_searched",
                                  "variations_searched")
#: Text fields that are SHARED by every cell of one claim (the claim's own words). A declared-only
#: claim is identified by these first, so a grid's per-cell titles never split one claim in two.
_IDENTITY_FIELDS: tuple[str, ...] = ("mechanism", "mechanism_note", "prior", "claim", "text",
                                     "source_url", "url", "title", "source_title")


class MalformedGrid(ValueError):
    """`register_grid` was handed something that is not a grid of cells it can key. Raised, never
    swallowed: a grid that silently registers nothing loses every member's lineage for good."""

#: What a search is counted in, as sources write it.
_UNITS = (r"(?:variations?|variants?|combinations?|backtests?|back-tests?|parameter\s+sets?|"
          r"param(?:eter)?\s+combos?|configurations?|configs?|settings|strategies|trials|"
          r"optimi[sz]ation\s+runs?|runs|versions|permutations|candidates|models)")
_APPROX = r"(?:~\s*|about\s+|approx(?:imately|\.)?\s+|roughly\s+|around\s+|some\s+|over\s+|" \
          r"more\s+than\s+|nearly\s+|almost\s+|at\s+least\s+)?"
_N = r"(\d{1,3}(?:[,\s]\d{3})+|\d+)\s*\+?"
_ADJ = r"(?:\s+(?:searched|tested|tried|different|distinct|backtested|optimi[sz]ed|" \
       r"parameter|strategy))*"
#: "best of 200 variations", "the maximum of ~200 searched variations", "top result out of 500
#: backtests", "winner among 1,200 combinations", "picked from 300 variants".
_BEST_OF = re.compile(
    r"\b(?:best|max(?:imum)?|top|highest|winner|winning|pick(?:ed)?|chosen|selected|"
    r"cherry-?picked)\b[^.;:\n]{0,40}?\b(?:of|over|among|from|out\s+of|across)\s+(?:the\s+)?"
    + _APPROX + _N + _ADJ + r"\s+" + _UNITS + r"\b", re.IGNORECASE)
#: "searched about 200 variations", "optimised over 1,500 combinations", "tested 400 variants".
_SEARCHED = re.compile(
    r"\b(?:searched|tested|tried|backtested|optimi[sz]ed|scanned|brute-?forced|swept|ran)\b"
    r"\s+(?:over\s+|through\s+|across\s+)?" + _APPROX + _N + _ADJ + r"\s+" + _UNITS + r"\b",
    re.IGNORECASE)
#: A stated search larger than this is a parse of something else (a trade count, a year).
MAX_SELECTION = 10_000_000
#: Row fields a claim's own words live in.
TEXT_FIELDS: tuple[str, ...] = ("mechanism", "mechanism_note", "prior", "claim", "text",
                                "title", "source_title", "description", "summary")


def _int(s: str) -> int:
    return int(re.sub(r"[,\s]", "", s))


def _as_int(v: Any) -> int:
    """A declared count as a reader would take it: 200, 200.0, "200", "1,200", "~200". 0 when the
    value states no count (None, a bool, prose) -- 0 here means NOT DECLARED, never "searched 0"."""
    if isinstance(v, bool) or v is None:
        return 0
    if isinstance(v, int):
        return max(0, v)
    if isinstance(v, float):
        return max(0, int(v)) if v == v and v not in (float("inf"), float("-inf")) else 0
    if isinstance(v, str):
        m = re.search(r"\d{1,3}(?:[,\s]\d{3})+|\d+", v)
        if m:
            with contextlib.suppress(ValueError):
                return _int(m.group(0))
    return 0


def declared_trials(row: Mapping[str, Any]) -> int:
    """The largest search a producer DECLARED on the row (0 when it declared none)."""
    n = max((_as_int(row.get(k)) for k in DECLARED_KEYS), default=0)
    return n if n <= MAX_SELECTION else 0


@lru_cache(maxsize=4096)
def _scan(text: str) -> tuple[int, str]:
    best, span = 0, ""
    for rx in (_BEST_OF, _SEARCHED):
        for m in rx.finditer(text):
            try:
                n = _int(m.group(1))
            except ValueError:
                continue
            if 1 < n <= MAX_SELECTION and n > best:
                best, span = n, m.group(0)
    return best, span


def selection_trials(text: str | None) -> int:
    """N when the text states its result was selected from N searched variants, else 0."""
    if not text:
        return 0
    return _scan(str(text))[0]


def row_text(row: Mapping[str, Any]) -> str:
    return " ".join(str(row.get(k)) for k in TEXT_FIELDS if isinstance(row.get(k), str))


def _seat(row: Mapping[str, Any]) -> str:
    src = str(row.get("source") or "")
    return src.split(":", 1)[1] if src.startswith("miner:") else src


def _sentence(text: str, span: str) -> str:
    """The sentence holding the selection statement, normalised -- the claim's identity."""
    i = text.find(span)
    if i < 0:
        return re.sub(r"\s+", " ", span.lower()).strip()
    # A sentence ends at ". " or a newline -- never at the point inside "Sharpe 1.87".
    lo = max(text.rfind(". ", 0, i) + 2, text.rfind("\n", 0, i) + 1, 0)
    hi = min((j for j in (text.find(". ", i + len(span)), text.find("\n", i + len(span)))
              if j >= 0), default=len(text))
    return re.sub(r"\s+", " ", text[lo:hi].lower()).strip()


def claim_family_id(seat: str, sentence: str) -> str:
    return "claim:" + hashlib.sha256(f"{seat}|{sentence}".encode()).hexdigest()[:16]


def _declared_identity(row: Mapping[str, Any]) -> str:
    """The claim's identity when only a declaration (no sentence) names its search: the first
    shared text field, normalised. Per-cell fields come last so one claim stays one family."""
    for k in _IDENTITY_FIELDS:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return "declared:" + re.sub(r"\s+", " ", v.lower()).strip()[:400]
    return "declared:" + str(row.get("family") or "?")


def _scan_row(row: Mapping[str, Any]) -> tuple[int, str]:
    """(N, the claim sentence) over the row's text fields, each field scanned ON ITS OWN so the
    identity sentence never runs from a shared mechanism note into a per-cell title."""
    best, sentence = 0, ""
    for k in TEXT_FIELDS:
        v = row.get(k)
        if not isinstance(v, str) or not v:
            continue
        n, span = _scan(v)
        if n > best:
            best, sentence = n, _sentence(v, span)
    return best, sentence


def stamp(row: dict[str, Any], *, text: str | None = None) -> bool:
    """Stamp a row minted from a searched claim with its claim family; True when stamped.

    Idempotent. A row already carrying `claim_family` keeps it and has its charge ratcheted up to
    anything larger its text now states. `family`, `params`, `symbol` and any verdict field are
    never read or written."""
    if text is not None:
        n, span = _scan(text)
        sentence = _sentence(text, span) if n else ""
    else:
        n, sentence = _scan_row(row)
    # A DECLARED SEARCH IS CHARGED AS DECLARED, NEVER LESS (2026-10-01). A producer that states
    # how many claims it searched -- `claim_selection_trials: 200` with no "best of" sentence --
    # was ignored here unless its prose repeated the number, so its cells went uncharged.
    declared = declared_trials(row)
    if declared > n:
        n = declared
        if not sentence:
            sentence = _declared_identity(row)
    have = row.get("claim_family")
    if n <= 1 and not have:
        return False
    if not have:
        row["claim_family"] = claim_family_id(_seat(row), sentence)
    row["claim_selection_trials"] = max(_as_int(row.get("claim_selection_trials")), n)
    row["breadth_unit"] = row["claim_family"]
    return True


def stamp_all(rows: Iterable[dict[str, Any]]) -> int:
    return sum(1 for r in rows if isinstance(r, dict) and stamp(r))


def breadth_unit(row: Mapping[str, Any]) -> str:
    """The unit a row counts as in breadth: its claim family, else the cell itself."""
    if row.get("breadth_unit"):
        return str(row["breadth_unit"])
    if row.get("genome_id"):
        return f"cell:{row['genome_id']}"
    return "cell:" + hashlib.sha256(json.dumps(
        {k: row.get(k) for k in ("symbol", "family", "params")}, sort_keys=True,
        default=str).encode()).hexdigest()[:16]


def breadth(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Cells versus independent breadth units, and the claim families behind the collapse."""
    cells = 0
    units: set[str] = set()
    unit_sizes: dict[str, int] = {}
    fams: dict[str, dict[str, Any]] = {}
    mechanisms: set[str] = set()
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        cells += 1
        u = breadth_unit(r)
        units.add(u)
        unit_sizes[u] = unit_sizes.get(u, 0) + 1
        mechanisms.add(str(r.get("claim_family") or r.get("family") or "?"))
        cf = r.get("claim_family")
        if cf:
            f = fams.setdefault(str(cf), {"cells": 0, "selection_trials": 0,
                                          "sources": set(), "families": set(),
                                          "genomes": set()})
            f["cells"] += 1
            if r.get("genome_id"):
                f["genomes"].add(str(r["genome_id"]))
            f["selection_trials"] = max(f["selection_trials"],
                                        int(r.get("claim_selection_trials") or 0))
            f["sources"].add(str(r.get("source") or ""))
            f["families"].add(str(r.get("family") or ""))
    return {"cells": cells, "breadth_units": len(units), "distinct_mechanisms": len(mechanisms),
            **k_eff(unit_sizes.values()),
            "claim_families": {k: {"cells": v["cells"], "selection_trials": v["selection_trials"],
                                   "sources": sorted(v["sources"]),
                                   "families": sorted(v["families"]),
                                   "genome_ids": sorted(v["genomes"])}
                               for k, v in sorted(fams.items())},
            "cells_in_claim_families": sum(v["cells"] for v in fams.values())}


def k_eff(unit_sizes: Iterable[int]) -> dict[str, Any]:
    """EFFECTIVE INDEPENDENT BETS FROM THE CLAIM LINEAGE.

    Cells of one breadth unit are one bet (correlation 1 within a claim family, a cell alone is
    its own unit), units are independent: the correlation matrix is block-diagonal with blocks of
    the unit sizes n_i, and its participation ratio -- the estimator `trial_ledger` and
    `mt5desk.canonical.effective_trials` already use -- is (sum n_i)^2 / sum n_i^2. It equals the
    unit count when every unit is the same size and falls toward 1 as one claim dominates the
    docket; `breadth_units` (the rank) is its ceiling. No cells is UNMEASURED, never 0."""
    sizes = [int(n) for n in unit_sizes if int(n) > 0]
    if not sizes:
        return {"k_eff": None, "k_eff_status": UNMEASURED}
    total, sq = float(sum(sizes)), float(sum(n * n for n in sizes))
    return {"k_eff": round(total * total / sq, 4), "k_eff_status": "MEASURED",
            "largest_unit_cells": max(sizes)}


def publish_breadth(measured: Mapping[str, Any], *, path: Path | None = None,
                    now: datetime | None = None,
                    lifetime_selection_trials: int | None = None) -> dict[str, Any]:
    """Write the breadth the claim lineage implies -- one searched claim = one breadth unit -- to
    `reports/CLAIM_BREADTH.json` for alpha_breadth, the coverage tensor and the Tier-1 scorecard.
    A pass with no cells publishes UNMEASURED, never a zero."""
    cells = int(measured.get("cells") or 0)
    fams = measured.get("claim_families") or {}
    doc = {
        "generated_utc": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"),
        "status": "MEASURED" if cells else UNMEASURED,
        "cells": cells if cells else None,
        "breadth_units": int(measured.get("breadth_units") or 0) if cells else None,
        "k_eff": measured.get("k_eff") if cells else None,
        "distinct_mechanisms": measured.get("distinct_mechanisms") if cells else None,
        "largest_unit_cells": measured.get("largest_unit_cells"),
        "claim_families": len(fams),
        "cells_in_claim_families": int(measured.get("cells_in_claim_families") or 0),
        "selection_trials_in_docket": sum(int((v or {}).get("selection_trials") or 0)
                                          for v in fams.values()),
        "lifetime_selection_trials": lifetime_selection_trials,
        "rule": ("one searched claim = ONE breadth unit; k_eff = (sum n_i)^2 / sum n_i^2 over "
                 "breadth-unit sizes (cells of one claim family move as one bet, units are "
                 "independent); breadth_units is its ceiling. Counting only -- no cell is "
                 "removed, capped or re-ordered by this"),
    }
    target = path or BREADTH_REPORT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def read_breadth(path: Path | None = None) -> dict[str, Any]:
    """The published claim-lineage breadth, or UNMEASURED naming the path it looked for."""
    target = path or BREADTH_REPORT
    try:
        doc = json.loads(target.read_text("utf-8"))
    except (OSError, ValueError):
        doc = None
    if not isinstance(doc, dict):
        return {"status": UNMEASURED, "k_eff": None, "breadth_units": None, "cells": None,
                "why": f"absent or unreadable: {target}"}
    return doc


def read_ledger(path: Path | None = None) -> dict[str, Any]:
    try:
        doc = json.loads((path or LEDGER).read_text("utf-8"))
    except (OSError, ValueError):
        return {"families": {}}
    return doc if isinstance(doc, dict) and isinstance(doc.get("families"), dict) \
        else {"families": {}}


def update_ledger(measured: Mapping[str, Any], *, path: Path | None = None,
                  now: datetime | None = None, count_as: str = "cells_last_seen"
                  ) -> dict[str, Any]:
    """Merge this pass's claim families into the LIFETIME ledger and write it.

    A family's charge is the largest N ever stated for it, charged ONCE; a family is never
    removed, and `cells_last_seen` is the only field that may fall (the docket moves)."""
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    doc = read_ledger(path)
    fams: dict[str, Any] = doc["families"]
    for fid, m in (measured.get("claim_families") or {}).items():
        f = fams.setdefault(fid, {"first_seen": at, "selection_trials": 0, "cells_max": 0})
        f["selection_trials"] = max(int(f.get("selection_trials") or 0),
                                    int(m.get("selection_trials") or 0))
        f[count_as] = int(m.get("cells") or 0)
        if count_as == "cells_last_seen":
            f["cells_max"] = max(int(f.get("cells_max") or 0), int(m.get("cells") or 0))
        f["sources"] = sorted(set(f.get("sources") or []) | set(m.get("sources") or []))
        f["families"] = sorted(set(f.get("families") or []) | set(m.get("families") or []))
        # MEMBERS RATCHET: a cell judged and gone from the docket keeps its lineage here, keyed
        # by genome id (= the hypothesis-graph node id), so its verdict joins to the family.
        f["member_genome_ids"] = sorted(set(f.get("member_genome_ids") or [])
                                        | set(m.get("genome_ids") or []))
        f["last_seen"] = at
    doc.update({
        "updated_at": at,
        "lifetime_selection_trials": sum(int(f.get("selection_trials") or 0)
                                         for f in fams.values()),
        "rule": ("a source that reports the best of N searched variations has already spent N "
                 "trials; every cell minted from it shares ONE claim_family, counts as ONE "
                 "breadth unit, and the family is charged N trials ONCE for its lifetime -- "
                 "never once per cell, never removed, only ratcheted up"),
    })
    target = path or LEDGER
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=1, sort_keys=False), "utf-8")
    return doc


def register_grid(rows: Iterable[Mapping[str, Any]], *, path: Path | None = None,
                  now: datetime | None = None) -> dict[str, Any]:
    """A PRODUCER REGISTERS ITS WHOLE GRID, judged cells included.

    `update_ledger` sees only what is in the docket this hour; a cell judged last week and gone
    from it would never gain its lineage. A producer that minted a searched claim knows its full
    grid, so it stamps every row and hands the ledger every member's genome id -- the id the
    hypothesis graph keys its verdicts by -- and the verdict joins to the family from then on."""
    if rows is None or isinstance(rows, (str, bytes, Mapping)):
        raise MalformedGrid(f"a grid is an iterable of cell mappings, not {type(rows).__name__}")
    try:
        cells = list(rows)
    except TypeError as exc:
        raise MalformedGrid(f"a grid must be iterable: {exc}") from exc
    if not cells:
        raise MalformedGrid("an empty grid registers nothing; a producer that minted cells "
                            "hands them all over")
    bad = [i for i, r in enumerate(cells) if not isinstance(r, Mapping)]
    if bad:
        raise MalformedGrid(f"{len(bad)} grid row(s) are not mappings (first at index {bad[0]}: "
                            f"{type(cells[bad[0]]).__name__})")
    genome_id: Any = None
    with contextlib.suppress(Exception):
        from libs.research.alpha_genome import genome_id
    fams: dict[str, dict[str, Any]] = {}
    unkeyed: list[int] = []
    for i, r in enumerate(cells):
        probe = dict(r)
        if not stamp(probe):
            continue
        if not (probe.get("genome_id") or (probe.get("symbol") and probe.get("family")
                                           and isinstance(probe.get("params") or {}, Mapping))):
            unkeyed.append(i)
            continue
        f = fams.setdefault(probe["claim_family"], {"cells": 0, "selection_trials": 0,
                                                    "sources": set(), "families": set(),
                                                    "genome_ids": set()})
        f["cells"] += 1
        f["selection_trials"] = max(f["selection_trials"], int(probe["claim_selection_trials"]))
        f["sources"].add("miner:" + _seat(probe) if not str(probe.get("source") or "")
                         .startswith("miner:") else str(probe["source"]))
        f["families"].add(str(probe.get("family") or ""))
        gid = probe.get("genome_id")
        if not gid and genome_id is not None and probe.get("symbol") and probe.get("family"):
            try:
                gid = genome_id(str(probe["symbol"]), str(probe["family"]),
                                dict(probe.get("params") or {}))
            except Exception:
                gid = None
        if gid:
            f["genome_ids"].add(str(gid))
    if unkeyed:
        raise MalformedGrid(f"{len(unkeyed)} stamped grid cell(s) carry neither a genome_id nor "
                            f"a symbol, family and params mapping to key one (first at index "
                            f"{unkeyed[0]}); their lineage could never join a verdict")
    if not fams:
        raise MalformedGrid(f"none of the grid's {len(cells)} cell(s) states or declares a "
                            "searched claim; register_grid is for a searched claim's grid")
    measured = {"claim_families": {k: {"cells": v["cells"],
                                       "selection_trials": v["selection_trials"],
                                       "sources": sorted(v["sources"]),
                                       "families": sorted(v["families"]),
                                       "genome_ids": sorted(v["genome_ids"])}
                                   for k, v in fams.items()}}
    doc = update_ledger(measured, path=path, now=now, count_as="grid_cells")
    return {"claim_families": {k: {"grid_cells": v["cells"],
                                   "selection_trials": v["selection_trials"]}
                               for k, v in measured["claim_families"].items()},
            "lifetime_selection_trials": doc.get("lifetime_selection_trials")}


def lineage_index(path: Path | None = None) -> dict[str, str]:
    """{genome_id: claim_family} for every cell ever stamped -- judged ones included."""
    return {g: fid for fid, f in read_ledger(path)["families"].items()
            for g in f.get("member_genome_ids") or []}


def lifetime_charges(path: Path | None = None) -> dict[str, int]:
    """{claim_family: N} from the lifetime ledger -- what the trial census charges once each."""
    return {k: int(v.get("selection_trials") or 0)
            for k, v in read_ledger(path)["families"].items()
            if int(v.get("selection_trials") or 0) > 0}


_INDEX_CACHE: dict[str, Any] = {}


def _charge_index(path: Path | None = None) -> tuple[dict[str, int], dict[str, set[str]]]:
    """({claim_family: N}, {genome_id: {claim_family}}) from the lifetime ledger, re-read only
    when the file changes -- the judge asks once per cell and must not parse it per cell."""
    target = path or LEDGER
    try:
        st = target.stat()
        key = (str(target), st.st_mtime_ns, st.st_size)
    except OSError:
        key = (str(target), -1, -1)
    if _INDEX_CACHE.get("key") != key:
        fams = read_ledger(target)["families"]
        charges = {fid: _as_int(f.get("selection_trials")) for fid, f in fams.items()}
        by_gid: dict[str, set[str]] = {}
        for fid, f in fams.items():
            for g in f.get("member_genome_ids") or []:
                by_gid.setdefault(str(g), set()).add(fid)
        _INDEX_CACHE.update({"key": key, "charges": charges, "by_gid": by_gid})
    return _INDEX_CACHE["charges"], _INDEX_CACHE["by_gid"]


def claim_charge(row: Mapping[str, Any], *, path: Path | None = None) -> int:
    """THE CLAIM CHARGE THE DEFLATED-SHARPE TRIAL COUNT READS for one cell: the largest selection
    any record of its claim family carries -- the row's own declaration, its own words, the
    lifetime ledger by claim family, and the ledger by genome id (so a judged cell whose docket
    row no longer carries the stamp is still charged). 0 when no record names a searched claim:
    the caller's max() then leaves its other terms exactly as they were."""
    probe = dict(row) if isinstance(row, Mapping) else {}
    stamp(probe)
    n = _as_int(probe.get("claim_selection_trials"))
    charges, by_gid = _charge_index(path)
    fids = {str(probe["claim_family"])} if probe.get("claim_family") else set()
    gid = probe.get("genome_id")
    if gid:
        fids |= by_gid.get(str(gid), set())
    for fid in fids:
        n = max(n, charges.get(fid, 0))
    return n


def family_floors(path: Path | None = None) -> dict[str, int]:
    """{strategy family: the largest claim selection charged to any claim family whose cells
    were built in it}. A strategy family that swept a searched claim is charged at least that
    claim's N -- the family term of max(campaign, family, claim)."""
    out: dict[str, int] = {}
    for f in read_ledger(path)["families"].values():
        n = _as_int(f.get("selection_trials"))
        if n <= 0:
            continue
        for fam in f.get("families") or []:
            if fam:
                out[str(fam)] = max(out.get(str(fam), 0), n)
    return out

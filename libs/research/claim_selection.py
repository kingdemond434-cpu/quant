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
    as one), and the families behind the collapse.

WHAT IT IS NOT. Nothing is removed, capped or re-ordered: every cell is still built and judged.
Only the COUNTING changes -- one searched claim is one unit of breadth and 200 trials of
multiplicity, which is the harder direction on both.
"""
from __future__ import annotations

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
    have = row.get("claim_family")
    if not n and not have:
        return False
    if not have:
        row["claim_family"] = claim_family_id(_seat(row), sentence)
    prior = row.get("claim_selection_trials")
    row["claim_selection_trials"] = max(int(prior) if isinstance(prior, int) else 0, n)
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
    fams: dict[str, dict[str, Any]] = {}
    mechanisms: set[str] = set()
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        cells += 1
        units.add(breadth_unit(r))
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
            "claim_families": {k: {"cells": v["cells"], "selection_trials": v["selection_trials"],
                                   "sources": sorted(v["sources"]),
                                   "families": sorted(v["families"]),
                                   "genome_ids": sorted(v["genomes"])}
                               for k, v in sorted(fams.items())},
            "cells_in_claim_families": sum(v["cells"] for v in fams.values())}


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
    genome_id: Any = None
    try:
        from libs.research.alpha_genome import genome_id
    except Exception:                                    # pragma: no cover
        pass
    fams: dict[str, dict[str, Any]] = {}
    for r in rows:
        probe = dict(r)
        if not stamp(probe):
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

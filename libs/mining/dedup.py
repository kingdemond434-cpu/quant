"""Mechanism-level dedup: two cells are the same when they TEST the same thing.

Surface text is not identity. "Oversold RSI bounce", "RSI(14)<30 buy" and "反转策略 RSI 超卖" are
one mechanism if they compile to the same rule on the same instrument and chart, and a Russian
forum post that is a translation of an English one is the same mechanism in a second language.
Counting either twice would double-charge the multiplicity budget and inflate cell counts, and
"does not count translations as independent cells" is in the spec for that reason.

The hash is built from what the cell would DO, never from what it is called:

    compiled cells   : mechanism_family | registered family | canonical params | symbol | chart
    uncompiled claims: mechanism_family | mechanism_claims key (instrument, class, direction,
                       horizon -- already language-independent)

Names, titles, languages, source ids and URLs are excluded by construction.

The first cell to claim a hash owns it; every later one is DUPLICATE_MECHANISM with
`duplicate_of` pointing at the owner. The index also accepts prior art from outside this
pipeline (the gauntlet's own seen-cells), so a rule the desk already judged is a duplicate here
too rather than a second trial of the same thing.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from libs.mining.pit_store import iso, utcnow

#: Parameters that change a label but not a rule. Stripped before hashing.
COSMETIC_PARAMS: frozenset[str] = frozenset({"name", "label", "comment", "magic", "title"})


def _num(v: Any) -> Any:
    """1, 1.0 and "1" hash the same; floats are rounded so 2.0000001 == 2.0."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        f = float(v)
        return int(f) if f.is_integer() else round(f, 6)
    if isinstance(v, str):
        try:
            f = float(v)
        except ValueError:
            return v.strip().lower()
        return int(f) if f.is_integer() else round(f, 6)
    if isinstance(v, (list, tuple)):
        return [_num(x) for x in v]
    if isinstance(v, Mapping):
        return {str(k): _num(x) for k, x in sorted(v.items())}
    return v


def canonical_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    return {str(k).lower(): _num(v) for k, v in sorted((params or {}).items())
            if str(k).lower() not in COSMETIC_PARAMS}


def mechanism_hash(*, mechanism_family: str, spec: Mapping[str, Any] | None = None,
                   claim_key: str = "") -> str:
    """The identity of a mechanism. Compiled spec when there is one, else the claim key."""
    if spec and spec.get("family"):
        body: dict[str, Any] = {
            "m": str(mechanism_family or "").lower(),
            "f": str(spec.get("family")).lower(),
            "p": canonical_params(spec.get("params") if isinstance(spec.get("params"), Mapping)
                                  else None),
            "s": str(spec.get("sym") or "").upper(),
            "t": str(spec.get("timeframe") or "H1").upper(),
        }
    else:
        if not claim_key:
            raise ValueError("a mechanism hash needs a compiled spec or a claim key")
        body = {"m": str(mechanism_family or "").lower(), "k": claim_key}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return "mh_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS mechanisms (
    mechanism_hash TEXT PRIMARY KEY, owner TEXT NOT NULL, first_seen TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'pipeline', tellings INTEGER NOT NULL DEFAULT 1,
    languages TEXT NOT NULL DEFAULT ''
);
"""


class DedupIndex:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=60.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def claim(self, mhash: str, cell_id: str, *, language: str = "") -> str | None:
        """Claim `mhash` for `cell_id`. Returns None if it is new (cell owns it), else the
        owner's id (the cell is a duplicate). Every telling is counted on the owner's row."""
        with self._conn() as c:
            row = c.execute("SELECT owner, languages FROM mechanisms WHERE mechanism_hash=?",
                            (mhash,)).fetchone()
            if row is None:
                c.execute("INSERT INTO mechanisms VALUES (?,?,?,?,?,?)",
                          (mhash, cell_id, iso(utcnow()), "pipeline", 1, language))
                return None
            owner = str(row["owner"])
            if owner == cell_id:
                return None
            langs = {x for x in str(row["languages"] or "").split(",") if x}
            if language:
                langs.add(language)
            c.execute("UPDATE mechanisms SET tellings=tellings+1, languages=? "
                      "WHERE mechanism_hash=?", (",".join(sorted(langs)), mhash))
            return owner

    def seed_prior_art(self, mhash: str, owner: str, origin: str) -> bool:
        """Register a mechanism the desk already tested elsewhere (never overwrites)."""
        with self._conn() as c:
            cur = c.execute("INSERT OR IGNORE INTO mechanisms VALUES (?,?,?,?,?,?)",
                            (mhash, owner, iso(utcnow()), origin, 0, ""))
            return cur.rowcount > 0

    def stats(self) -> dict[str, Any]:
        with self._conn() as c:
            row = c.execute("SELECT COUNT(*) AS n, COALESCE(SUM(tellings),0) AS t, "
                            "SUM(CASE WHEN origin!='pipeline' THEN 1 ELSE 0 END) AS prior "
                            "FROM mechanisms").fetchone()
        return {"distinct_mechanisms": int(row["n"] or 0), "tellings": int(row["t"] or 0),
                "prior_art": int(row["prior"] or 0)}

"""EVERY NAMED REGION STANDS ON GROUND, AND THE CRAWL DEALS ITSELF ROUND THE TABLE.

THE DEFECT THESE PIN (measured 2026-09-24 on the build box, vmi3500897). Three independent
causes held three different regions at zero cells, and each needed its own fix:

  1. THE INDEX COULD NOT NAME THEM. `attribution.ground_index()` resolves a ground's region by
     `country -> region -> url`, and NOT ONE of the 89 rows in `asia_sources.json` carried a
     country or a region. Every resolution fell through to `region_of_url`, which returns None
     for a generic TLD by design -- it refuses to guess a jurisdiction from `.com`. Every US and
     institutional ground is on a generic TLD, so the index named 0 grounds in North America, 0
     in India, 0 in MENA and 0 in Global/institutional. India's single ground was filed on the
     `tw` (Taiwan) plane because its URL is `nseindia.com`.
  2. NOTHING CRAWLED THEM. 1,593 of 2,214 registered grounds had never been fetched, and the
     never-fetched set was not a random sample: `us` 69, `institutional` 72, `cn` 41, `ru` 41,
     `sg` 26 -- zero crawled between them, while `cz`, `az` and `kz` were fully drained. All
     1,593 were seeded in one batch with one `first_seen` and no measured share, so both of
     `drain_order`'s keys tied and the order collapsed to SQLite's row order. The hourly pass
     took the first 70 of that, and the same regions lost every hour.
  3. THE SPREAD WAS FENCED BY NOTHING. `tests/test_region_ratchet.py` holds that half.

The properties here are the first two, and both are LEVEL-UP ONLY: no ground is removed, no
region is capped, and the drain's pass size and budget are untouched -- only its ORDER changes.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import attribution as A  # noqa: E402

GROUNDS = ROOT / "desks" / "mt5" / "data" / "asia_sources.json"

#: THE GROUNDS RATCHET. Every region the desk NAMES stands on at least this many declared
#: grounds. It goes UP and never down (L1.50) and it is satisfied only by registering ground in
#: the thin region -- deleting a strong region's grounds lowers nothing here and fails the
#: region-count fence next door. Measured 2026-09-24: 0 before the levelling pass, 16 after.
GROUNDS_FLOOR = 16


def _rows() -> list[dict]:
    doc = json.loads(GROUNDS.read_text(encoding="utf-8"))
    rows = doc.get("sources") if isinstance(doc, dict) else doc
    return [r for r in (rows or []) if isinstance(r, dict)]


def test_every_named_region_holds_ground_in_the_index() -> None:
    """A region with no ground cannot mint a cell however deep the mining downstream goes."""
    idx = A.ground_index()
    assert idx, f"{A.UNMEASURED}: the ground index is empty on this host"
    per = collections.Counter(idx.values())
    empty = [r for r in A.REGIONS if not per.get(r)]
    assert not empty, f"regions the index cannot name: {empty}"


def test_the_grounds_floor_holds_for_every_region() -> None:
    """The floor is on the WEAKEST region, so it can only be cleared by raising the tail."""
    per = collections.Counter(A.ground_index().values())
    # the index files each id twice (bare and `asia:`-prefixed), so the floor is read on rows
    rows = collections.Counter()
    for row in _rows():
        where = (A.region_of(row.get("country")) or A.region_of_command(row.get("region"))
                 or A.region_of(row.get("region")) or A.region_of_url(row.get("url")))
        if where:
            rows[where] += 1
    thin = {r: rows.get(r, 0) for r in A.REGIONS if rows.get(r, 0) < GROUNDS_FLOOR}
    assert not thin, (f"regions under the grounds floor of {GROUNDS_FLOOR}: {thin}. "
                      f"Register ground there -- never lower the floor and never trim a strong "
                      f"region (LAWS L1.50, NEVER REDUCE AGGRESSIVENESS). Held: {dict(per)}")


def test_every_ground_declares_its_own_jurisdiction() -> None:
    """A country stamp is a MEASUREMENT of the ground; a URL guess is not available for a gTLD."""
    missing = [r.get("id") for r in _rows() if not str(r.get("country") or "").strip()]
    assert not missing, f"grounds with no declared country: {missing[:20]}"


def test_no_ground_hunts_a_crypto_exchange_universe() -> None:
    """The 2026-08-18 mandate: Fusion crypto CFDs are in the lane, crypto-exchange ground never."""
    banned = ("binance", "bybit", "okx", "hyperliquid", "coinbase", "kraken.com", "bitmex",
              "kucoin", "huobi", "deribit", "gate.io", "bitfinex")
    for row in _rows():
        host = A.host_of(row.get("url"))
        assert not any(b in host for b in banned), f"{row.get('id')} -> {host}"


def test_every_ground_routes_to_a_declared_instrument() -> None:
    """A dataset with no path into a tradable instrument spends trial count for nothing."""
    for row in _rows():
        if row.get("why_no_cells"):
            # a transport (an aggregation API over a ground the desk already reads directly)
            # declares WHY it mints nothing; that is a measurement, not a missing route
            assert row.get("role"), row.get("id")
            continue
        targets = row.get("targets")
        assert isinstance(targets, list) and targets, row.get("id")
        assert row.get("mechanism"), row.get("id")


def test_the_boundary_is_the_five_refused_acts_and_not_a_source_brake() -> None:
    """LAWS 5e (2026-09-23) deleted the public/licensed pre-filter; this file carried it until
    2026-09-24, one day after the law that names it as a deleted brake."""
    doc = json.loads(GROUNDS.read_text(encoding="utf-8"))
    boundary = str(doc.get("boundary") or "")
    # the phrase may only survive as the NAMED history of a deleted brake, never as the rule
    head = boundary.split("THIS LINE REPLACED")[0]
    assert "PUBLIC OR LICENSED ONLY" not in head
    for act in ("credential", "paywall", "non-public", "stolen", "personal data"):
        assert act in boundary.lower(), act


# ------------------------------------------------------------------- the region-fair drain order
def _pending(region_rows: dict[str, int]) -> list[dict]:
    """Pending rows shaped exactly as the live defect was: one seed batch, no measured share."""
    out: list[dict] = []
    for country, n in region_rows.items():
        for i in range(n):
            out.append({"source_id": f"{country}:{i}", "country": country,
                        "url": f"https://example-{country}-{i}.test/",
                        "first_seen": "2026-09-23T10:00:00+00:00"})
    return out


def test_the_drain_deals_the_pass_round_the_regions_not_down_the_table() -> None:
    """The live shape: one huge region and four starved ones, all seeded in the same batch."""
    import coverage_drain as C
    rows = _pending({"cz": 200, "us": 69, "institutional": 72, "cn": 41, "sg": 26})
    got = C.drain_order(rows, None, held={})[:70]
    per = collections.Counter(C.region_of_row(r) for r in got)
    # every region present in the pending set reaches the pass
    assert set(per) == {"Europe", "North America", "Global/institutional", "China", "SEA"}
    # and no region takes more than one slot more than the thinnest
    assert max(per.values()) - min(per.values()) <= 1, dict(per)


def test_the_starved_region_is_served_first() -> None:
    """`held` is what each region has ALREADY had crawled: the hungriest takes the next slot."""
    import coverage_drain as C
    rows = _pending({"cz": 10, "us": 10})
    held = {"Europe": 350, "North America": 0}
    got = C.drain_order(rows, None, held=held)
    first = [C.region_of_row(r) for r in got[:8]]
    assert first[0] == "North America"
    # Europe is never excluded -- it simply waits its turn, so nothing is throttled
    assert "Europe" in [C.region_of_row(r) for r in got]


def test_the_drain_orders_and_never_drops_a_row() -> None:
    """LEVEL UP ONLY: reordering is the whole change; the drainable set is identical."""
    import coverage_drain as C
    rows = _pending({"cz": 17, "us": 9, "institutional": 4, "xx": 3})
    got = C.drain_order(rows, None, held={})
    assert len(got) == len(rows)
    assert {r["source_id"] for r in got} == {r["source_id"] for r in rows}


def test_an_unmappable_ground_is_a_named_bucket_and_never_folded_into_a_region() -> None:
    """Folding an unknown jurisdiction into a region makes that region read deeper than it is."""
    import coverage_drain as C
    assert C.region_of_row({"country": "", "url": "https://example.com/"}) == C.UNMAPPED_REGION
    assert C.UNMAPPED_REGION not in A.REGIONS
    # and a declared country beats an unhelpful generic TLD, which is the whole fix
    assert C.region_of_row({"country": "us", "url": "https://federalreserve.gov/"}) \
        == "North America"


def test_the_drain_reads_the_region_vocabulary_and_never_redefines_it() -> None:
    """One vocabulary: the drain and the attribution census can never disagree about a region.

    Measured on the AST, not on the line text, so a region NAMED in the prose that explains the
    defect does not read as a second copy of the table (the orphan census learned this the hard
    way: line-text matching calls a docstring a definition).
    """
    import ast
    src = (ROOT / "desks" / "mt5" / "research" / "coverage_drain.py").read_text("utf-8")
    assert "from libs.research import attribution as _A" in src
    tree = ast.parse(src)
    docstrings = {id(ast.get_docstring(n, clean=False))
                  for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.FunctionDef | ast.ClassDef)}
    literals = {node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                and node.value not in {ast.get_docstring(n, clean=False)
                                       for n in ast.walk(tree)
                                       if isinstance(n, ast.Module | ast.FunctionDef
                                                     | ast.ClassDef)}}
    assert docstrings                       # the module is documented, which the next line needs
    for r in A.REGIONS:
        assert r not in literals, f"{r} is a hard-coded literal in coverage_drain"


def test_the_drain_still_caps_nothing() -> None:
    """The pass size and the budget are untouched; only the order changed."""
    src = (ROOT / "desks" / "mt5" / "research" / "coverage_drain.py").read_text("utf-8")
    assert "LEASE_H = 24.0" in src
    assert "int(float(rows) / max(1.0, LEASE_H)) + 1" in src


def test_the_drain_hands_the_crawler_its_rows_and_not_just_a_count() -> None:
    """The region-fair order is worthless if the crawler re-picks the pass by its own rank.

    Measured 2026-09-24: the drain cleared 35 Global/institutional grounds in a pass and that
    region's crawled count stayed at 0 -- twice -- because `_run_collectors` passed only
    `max_sources` and `choose_sources` re-chose by pure ROI, the yield-maximising order that had
    put five regions at zero in the first place.
    """
    import coverage_drain as C
    src = (ROOT / "desks" / "mt5" / "research" / "coverage_drain.py").read_text("utf-8")
    assert "source_ids=drainable" in src
    import inspect
    assert "source_ids" in inspect.signature(C._run_collectors).parameters

    from research import moat_collectors as M
    assert "source_ids" in inspect.signature(M.run).parameters
    assert "source_ids" in inspect.signature(M.choose_sources).parameters


def test_naming_the_rows_narrows_the_pass_and_keeps_the_roi_order_inside_it() -> None:
    """The named set is a FILTER on the pass, never a new ranking rule."""
    import sqlite3
    from contextlib import closing

    from research import moat_collectors as M
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE sources(source_id TEXT, status TEXT, last_crawled TEXT)")
        conn.execute("CREATE TABLE source_yield(source_id TEXT, independent_survivors INT, "
                     "survivors INT, claims INT, compute_s REAL)")
        for sid in ("a", "b", "c"):
            conn.execute("INSERT INTO sources VALUES(?,?,?)", (sid, "active", None))
        conn.execute("INSERT INTO source_yield VALUES(?,?,?,?,?)", ("c", 9, 9, 9, 1.0))

        # unfiltered: the measured payer leads, exactly as before
        assert next(r["source_id"] for r in M.choose_sources(conn, 10)) == "c"
        # named: only the named rows are visited, and `c` -- the top ROI -- is not one of them
        got = [r["source_id"] for r in M.choose_sources(conn, 10, ["a", "b"])]
        assert set(got) == {"a", "b"}
        # and the ROI order still governs inside the named set
        conn.execute("INSERT INTO source_yield VALUES(?,?,?,?,?)", ("b", 5, 5, 5, 1.0))
        assert next(r["source_id"] for r in M.choose_sources(conn, 10, ["a", "b"])) == "b"

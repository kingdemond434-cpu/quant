"""The research genome: C = (M, D, R, G, S, H, E, F) from a registry row, the near-duplicate
family rule, family assignment, and the quality-diversity archive with its empty-cell bonus."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import research_genome as G  # noqa: E402

ROW = {"id": "cand_1", "family": "liquidity_gamma_reversal", "subtype": "execution",
       "symbol": "EUSTX50", "params_json": '{"conditioner": "cross_asset", "entry_timing": '
                                           '"delayed", "execution_style": "limit"}',
       "mechanism": "gamma_hedging_state", "asset_class": "indices", "chart": "H1",
       "session": "all", "horizon": "sub_4h", "regime": "unconditional",
       "pit_status": "PIT_BAR_CLOSE", "transformation": "execution",
       "information": "microstructure"}


def _g(**over: str) -> G.Genome:
    base = {a: f"{a}_v" for a in G.AXES}
    base.update(over)
    return G.Genome(**base)  # type: ignore[arg-type]


def test_genome_reads_every_axis_from_the_registry_row_and_never_invents_one() -> None:
    g = G.genome_of(ROW)
    assert g.tuple8() == ("gamma_hedging_state", "microstructure", "execution@H1", "EU",
                          "unconditional/all", "sub_4h", "limit", G.UNMEASURED)
    assert g.asset == "indices" and g.symbol == "EUSTX50" and g.params["conditioner"]
    assert g.archive_cell() == ("gamma_hedging_state|microstructure|EU|indices|all|"
                                "unconditional|sub_4h|limit")
    bare = G.genome_of({"family": "carry", "symbol": "usdjpy"})
    assert bare.mechanism == "carry" and bare.geography == "US-JP"
    assert bare.tuple8().count(G.UNMEASURED) == 6
    assert G.geography_of("JPN225") == "JP" and G.geography_of("XAUUSD") == "GLOBAL"
    assert G.geography_of("", None) == G.UNMEASURED
    assert G.geography_of("Apple", "equities") == "US"
    assert len(g.exact_key()) == 16 and g.exact_key() == G.genome_of(dict(ROW)).exact_key()


def test_near_duplicates_share_most_of_the_tuple_and_never_cross_mechanisms() -> None:
    a = _g()
    six = _g(failure="other", representation="other")           # 6 of 8 equal
    five = _g(failure="o", representation="o", horizon="o")     # 5 of 8
    other = _g(mechanism="different")                           # 7 equal, other mechanism
    assert G.equal_axes(a, six) == 6 and G.is_near_duplicate(a, six)
    assert not G.is_near_duplicate(a, five)
    assert not G.is_near_duplicate(a, other)
    u1, u2 = _g(failure=G.UNMEASURED, representation="x"), _g(failure=G.UNMEASURED,
                                                                representation="y")
    assert G.equal_axes(u1, u2) == 6                # two unknowns are not one agreement
    fam = G.assign_families([a, six, five, other])
    assert fam[0] == fam[1] and fam[0] != fam[2] and fam[0] != fam[3]
    chain = [_g(), _g(failure="b", representation="b"), _g(failure="b", representation="b",
                                                             horizon="c", state="c")]
    assert len(set(G.assign_families(chain))) == 1   # A~B~C is one lineage
    assert G.assign_families([a]) == [f"fam_{a.exact_key()}"]
    assert G.assign_families([]) == []


def test_the_archive_keeps_one_elite_per_cell_and_pays_for_empty_ones() -> None:
    arch = G.QDArchive(bonus=0.5)
    assert arch.put("m|d|JP|fx|asia|calm|sub_4h|limit", "c1", 1.0, "gate")
    assert not arch.put("m|d|JP|fx|asia|calm|sub_4h|limit", "c2", 0.5)     # incumbent stays
    assert not arch.put("m|d|JP|fx|asia|calm|sub_4h|limit", "c3", 1.0)     # ties never churn
    assert arch.put("m|d|US|fx|asia|calm|sub_4h|limit", "c4", 3.0, "forward")
    occ = arch.occupancy()
    assert occ["cells_filled"] == 2 and occ["candidates_placed"] == 4
    assert occ["axis_cardinality"]["geography"] == 2 and occ["cells_possible"] == 2
    assert arch.priority("m|d|EU|fx|asia|calm|sub_4h|limit", 2.0) == 3.0
    assert arch.priority("m|d|JP|fx|asia|calm|sub_4h|limit", 2.0) == 2.0
    empty = G.QDArchive().empty_high_value()
    assert empty == []
    arch.put("m|d|US|fx|london|calm|sub_4h|limit", "c5", 2.0)
    rows = arch.empty_high_value()
    assert rows and rows[0]["cell"] == "m|d|JP|fx|london|calm|sub_4h|limit"
    assert rows[0]["value"] == round((1.0 + 2.0) / 2 * 1.5, 6) and rows[0]["neighbours"] == 2
    assert all(r["cell"] not in arch.cells for r in rows)
    doc = arch.to_dict()
    assert doc["elites"][0]["candidate_id"] == "c4" and doc["bonus"] == 0.5

"""`n_clusters` reaches the allocator artifact, as alpha_genome's own docstring already claimed.

alpha_genome.py:23-25 says the genome is consumed "by `regime_coverage` ... and by the allocator
artifact, where `n_clusters` is reported beside `k_eff`". A repo-wide grep for ALPHA_GENOME found
regime_coverage, capability_graph and module_rent -- and NO allocator reader, so half that
sentence had been false for as long as it had been written. `pf_allocator.alpha_genome_view` is
the reader.

REPORTING ONLY, and these pin it: the cluster id reaches `effective_heat.alpha_genome` and stops.
It sizes nothing, caps nothing and vetoes nothing -- the book is identical with the genome
present and absent. What it adds is the number to read AGAINST k_eff: eight sleeves whose
returns barely covary can still be one structural bet, and until now the sizing path had no way
to see that even though the desk had already measured it.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import SleeveEvidence  # noqa: E402

pa = pytest.importorskip("research.pf_allocator", reason="the allocator ships with the desk")


def _ev() -> list[SleeveEvidence]:
    rng = np.random.default_rng(0)
    rows = [("CADJPY_session_range_breakout_asia", "CADJPY", "session_range_breakout"),
            ("EURJPY_session_range_breakout_asia", "EURJPY", "session_range_breakout"),
            ("EURUSD_carry_london", "EURUSD", "carry"),
            ("GBPUSD_orphan_ny", "GBPUSD", "orphan")]
    return [SleeveEvidence(name=n, daily_r=rng.normal(0.01, 0.3, 120), symbol=s, family=f)
            for n, s, f in rows]


GENOME_DOC = {
    "generated_utc": "2026-09-08T21:04:00+00:00",
    "n_sleeves": 3, "n_clusters": 2, "structural_breadth": 0.667,
    "largest_clusters": [{"cluster": "breakout/with/asia/CAD+EUR+JPY", "n": 2, "members": []}],
    "clusters": {"breakout/with/asia/CAD+EUR+JPY": ["h12.srb.CADJPY.asia", "h12.srb.EURJPY.asia"],
                 "carry/neutral/london/EUR+USD": ["ext.carry.EURUSD.london"]},
    "genome": {
        "h12.srb.CADJPY.asia": {"symbol": "CADJPY", "family": "session_range_breakout",
                                "clock": "asia", "mechanism": "breakout"},
        "h12.srb.EURJPY.asia": {"symbol": "EURJPY", "family": "session_range_breakout",
                                "clock": "asia", "mechanism": "breakout"},
        "ext.carry.EURUSD.london": {"symbol": "EURUSD", "family": "carry", "clock": "london",
                                    "mechanism": "carry"},
    },
}
BOOK = {"CADJPY_session_range_breakout_asia": 0.06, "EURJPY_session_range_breakout_asia": 0.05,
        "EURUSD_carry_london": 0.05, "GBPUSD_orphan_ny": 0.04}


@pytest.fixture
def genome(tmp_path, monkeypatch):
    def _write(doc) -> Path:
        p = tmp_path / "ALPHA_GENOME.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        monkeypatch.setattr(pa, "GENOME", p)
        return p
    return _write


# ------------------------------------------------------------------------------- the reading
def test_the_funded_book_gets_its_cluster_ids_and_the_genomes_own_counts(genome) -> None:
    genome(GENOME_DOC)
    v = pa.alpha_genome_view(_ev(), BOOK)
    assert v["status"] == "MEASURED" and v["consumed"] is False
    assert v["n_clusters"] == 2 and v["n_sleeves"] == 3
    assert v["structural_breadth"] == 0.667
    assert v["generated_utc"] == GENOME_DOC["generated_utc"]
    assert v["cluster_by_sleeve"] == {
        "CADJPY_session_range_breakout_asia": "breakout/with/asia/CAD+EUR+JPY",
        "EURJPY_session_range_breakout_asia": "breakout/with/asia/CAD+EUR+JPY",
        "EURUSD_carry_london": "carry/neutral/london/EUR+USD"}
    # THE NUMBER TO READ AGAINST k_eff: three funded sleeves, two structural bets.
    assert v["book_clusters_occupied"] == 2
    assert v["book_clusters"] == ["breakout/with/asia/CAD+EUR+JPY", "carry/neutral/london/EUR+USD"]
    assert v["largest_clusters"][0]["n"] == 2
    assert "3/4 funded sleeve(s) joined" in v["why"]


def test_a_sleeve_the_genome_cannot_place_is_named_never_given_a_cluster_of_its_own(genome):
    """A silent per-sleeve cluster would read as breadth the book has not got (L1.28a)."""
    genome(GENOME_DOC)
    v = pa.alpha_genome_view(_ev(), BOOK)
    assert v["n_funded_unjoined"] == 1 and v["n_funded_joined"] == 3
    assert "GBPUSD_orphan_ny" in v["unjoined"]
    assert "no genome row" in v["unjoined"]["GBPUSD_orphan_ny"]
    assert "GBPUSD_orphan_ny" not in v["cluster_by_sleeve"]
    assert v["book_clusters_occupied"] == 2, "an unjoined sleeve is not a third cluster"


def test_an_ambiguous_join_claims_no_cluster(genome) -> None:
    """Two genome rows on the same symbol and family in DIFFERENT clusters: funding one sleeve
    on the other's cluster id is worse than not joining, so neither is claimed."""
    doc = json.loads(json.dumps(GENOME_DOC))
    doc["genome"]["other.srb.CADJPY.ny"] = {"symbol": "CADJPY",
                                            "family": "session_range_breakout", "clock": "ny"}
    doc["clusters"]["breakout/with/ny/CAD+JPY"] = ["other.srb.CADJPY.ny"]
    genome(doc)
    ev = [SleeveEvidence(name="CADJPY_session_range_breakout_tokyo",
                         daily_r=np.zeros(10) + 0.01, symbol="CADJPY",
                         family="session_range_breakout")]
    v = pa.alpha_genome_view(ev, {"CADJPY_session_range_breakout_tokyo": 0.05})
    assert v["cluster_by_sleeve"] == {}
    assert "ambiguous" in v["unjoined"]["CADJPY_session_range_breakout_tokyo"]


def test_only_funded_sleeves_are_reported(genome) -> None:
    genome(GENOME_DOC)
    v = pa.alpha_genome_view(_ev(), {"EURUSD_carry_london": 0.05})
    assert set(v["cluster_by_sleeve"]) == {"EURUSD_carry_london"}
    assert v["book_clusters_occupied"] == 1
    zero = pa.alpha_genome_view(_ev(), {"EURUSD_carry_london": 0.0})
    assert zero["cluster_by_sleeve"] == {} and zero["book_clusters_occupied"] == 0


def test_a_missing_or_broken_genome_is_unmeasured_and_never_raises(genome, tmp_path,
                                                                    monkeypatch) -> None:
    monkeypatch.setattr(pa, "GENOME", tmp_path / "absent.json")
    v = pa.alpha_genome_view(_ev(), BOOK)
    assert v["status"] == "UNMEASURED" and "unreadable" in v["why"]
    assert v["consumed"] is False and "cluster_by_sleeve" not in v
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(pa, "GENOME", tmp_path / "broken.json")
    assert pa.alpha_genome_view(_ev(), BOOK)["status"] == "UNMEASURED"
    genome({"generated_utc": "x", "n_clusters": 0, "clusters": {}, "genome": {}})
    empty = pa.alpha_genome_view(_ev(), BOOK)
    assert empty["status"] == "UNMEASURED" and "no clusters" in empty["why"]


# --------------------------------------------------------------------------------- the law
def test_the_cluster_id_is_published_beside_k_eff_and_sizes_nothing() -> None:
    src = inspect.getsource(pa.run)
    assert 'effective_heat["alpha_genome"] = alpha_genome_view(ev, funded)' in src
    # It is read AFTER the book is funded and never feeds a bound, a cap or a solve.
    i_funded = src.index("funded = {k: round(v, 6) for k, v in book.heat.items() if v > 1e-5}")
    assert i_funded < src.index('effective_heat["alpha_genome"]')
    for forbidden in ("alpha_genome_view(ev, free.heat)", "max_per_sleeve=.*alpha_genome"):
        assert forbidden not in src
    body = inspect.getsource(pa.alpha_genome_view)
    for forbidden in ("optimise(", "per_sleeve_bounds(", "enforce_family_cap("):
        assert forbidden not in body, f"a reporting view must not {forbidden}"
    assert "REPORTING ONLY" in body

    from mt5desk import decision_core
    assert "alpha_genome" not in inspect.getsource(decision_core), (
        "the money path must not read a cluster id")


def test_the_genome_docstrings_claim_is_now_true() -> None:
    """The claim that was false when it was written, pinned so it cannot silently become false
    again: alpha_genome says the allocator artifact reports n_clusters beside k_eff."""
    genome_src = (_DESK / "research" / "alpha_genome.py").read_text("utf-8")
    assert "n_clusters" in genome_src and "k_eff" in genome_src
    alloc_src = (_DESK / "research" / "pf_allocator.py").read_text("utf-8")
    assert "ALPHA_GENOME.json" in alloc_src, "the allocator must actually name the artifact"
    assert '"n_clusters": doc.get("n_clusters")' in alloc_src

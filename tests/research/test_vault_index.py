"""VAULT RETRIEVAL -- and the one claim it must never be read as making.

docs/ is 208,409 lines. No context window holds it, so an organ that cannot search it either greps
blind or proceeds without knowing what the desk already decided -- and the second is what actually
happens. This is the retrieval layer under CLAUDE.md (the map) and desk-state.sh (the odometer).

THE PROPERTY THAT MATTERS MOST IS NOT RECALL. It is that an EMPTY RESULT IS NOT EVIDENCE OF
ABSENCE. This index is BM25 -- lexical, not semantic, because no embedding model is reachable from
a network-denied clone. A caller who believes it understands meaning will read zero hits as "the
desk never decided this" and re-decide a settled question, which is the exact waste the vault
exists to prevent. So the disclaimer is asserted as a test, not left to a docstring nobody reads.
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from libs.research.vault_index import (
    GENERATED,
    VaultIndex,
    _split,
    build,
    format_hits,
)


@pytest.fixture(scope="module")
def idx() -> VaultIndex:
    return build()


def test_THE_REAL_VAULT_INDEXES(idx: VaultIndex) -> None:
    """A silently-empty index would make every search return nothing, and every consumer would read
    that as 'no prior decision' -- the failure this whole file guards."""
    assert len(idx) > 300, f"only {len(idx)} chunks -- the vault did not load"


@pytest.mark.parametrize(("query", "expect_path"), [
    ("coverage floor ratchet never lowered", "CONSTITUTION"),
    ("reduce only flatten close leg", "GAP_REGISTER"),
    ("pre-registration kill criteria liquidation", "PREREGISTRATION"),
])
def test_A_KNOWN_DECISION_IS_FOUND_BY_ITS_OWN_VOCABULARY(idx: VaultIndex, query: str,
                                                         expect_path: str) -> None:
    """The bar for usefulness. These are decisions this desk has actually made; if its own terms do
    not retrieve them, the index is decoration."""
    hits = idx.search(query, limit=8)
    assert hits, f"no hit for {query!r}"
    assert any(expect_path in c.path for _s, c in hits), (
        f"{query!r} did not surface {expect_path}; got {[c.path for _s, c in hits[:4]]}")


def test_GENERATED_DUMPS_ARE_EXCLUDED(idx: VaultIndex) -> None:
    """MEASURED, NOT ASSUMED: on the first real query, two of the top three hits were IDENTICAL text
    at the same line in two different audit shards -- generated code dumps outranking the decisions.
    A search surface that is confidently wrong at the top is worse than none, because the top is the
    position a reader trusts."""
    assert all(not any(c.path.startswith(g) or c.path == g for g in GENERATED)
               for c in idx.chunks)
    assert len(build(include_generated=True)) > len(idx), "the escape hatch does nothing"


def test_EVERY_HIT_IS_CITABLE(idx: VaultIndex) -> None:
    """A result the reader cannot locate encourages acting on the excerpt, and an excerpt is not the
    decision. Path and line must both be present and real."""
    for _s, c in idx.search("funding carry", limit=5):
        assert c.path.endswith(".md") and c.line >= 1
        assert c.path in c.cite and str(c.line) in c.cite


def test_AN_EMPTY_RESULT_SAYS_IT_IS_NOT_ABSENCE(idx: VaultIndex) -> None:
    """THE LOAD-BEARING ONE. The disclaimer must travel with the empty result itself -- a caller
    reading zero hits will not go and consult a docstring."""
    hits = idx.search("zzqqxx_no_such_token_anywhere_12345")
    assert hits == []
    msg = format_hits(hits)
    assert "NOT EVIDENCE OF ABSENCE" in msg
    assert "LEXICAL" in msg


def test_A_HEADING_CARRIES_ITS_PARENT_PATH() -> None:
    """A law and its rationale are one thought. Returning "L1.50" without the level it sits under
    strips the context that makes it applicable, which is how a rule gets applied to a case it was
    never meant for."""
    small = VaultIndex()
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "x.md"
        p.write_text("# TOP\nintro\n## Inner\nbody about deflation\n", "utf-8")
        for c in _split(p, "x.md"):
            small.add(c)
    inner = [c for c in small.chunks if "Inner" in c.heading]
    assert inner and inner[0].heading == "TOP > Inner"


def test_PREAMBLE_BEFORE_THE_FIRST_HEADING_IS_NOT_LOST() -> None:
    """In this vault the text above the first heading is routinely the document's whole thesis --
    GAP_REGISTER.md's re-rank rationale lives there. Dropping it would make the most important
    paragraph in several documents unsearchable."""
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "y.md"
        p.write_text("the thesis lives here\n\n# Later\nbody\n", "utf-8")
        chunks = _split(p, "y.md")
    assert any("thesis" in c.text for c in chunks)


def test_SEARCH_IS_DETERMINISTIC(idx: VaultIndex) -> None:
    """A ranking that reorders between runs cannot be diffed, and an organ that logs its top hit
    would show spurious churn."""
    a = [(round(s, 6), c.cite) for s, c in idx.search("liquidation cascade", limit=5)]
    b = [(round(s, 6), c.cite) for s, c in idx.search("liquidation cascade", limit=5)]
    assert a == b


def test_PATH_FILTER_NARROWS(idx: VaultIndex) -> None:
    hits = idx.search("evidence", limit=10, path_filter="CONSTITUTION")
    assert hits and all("CONSTITUTION" in c.path for _s, c in hits)


def test_AN_EMPTY_QUERY_IS_EMPTY_NOT_EVERYTHING(idx: VaultIndex) -> None:
    """Returning the whole corpus for a blank query would flood a caller's context with 1,200
    chunks -- the exact problem this layer exists to solve, delivered by the solution."""
    assert idx.search("") == []
    assert idx.search("   ") == []

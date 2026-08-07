"""CROSS-ECOSYSTEM CONVERGENCE -- the tests are almost entirely about refusing to confirm.

Matching findings across seven language regions is easy, and `mechanism_fingerprint` already does
it. The failure this module exists to prevent is the one that looks like success: three ecosystems
describing the same effect BECAUSE THEY ALL READ ONE ENGLISH PAPER, counted as three independent
confirmations. That is GAP #85 -- n counting readings of the world rather than events in it --
applied to the exact number used to promote a mechanism above its evidence.

So the tests below care most about the corpus with NO provenance, which is the state the desk's
miners are actually in today.
"""

from __future__ import annotations

from libs.research.convergence import (
    MIN_REGIONS,
    Observation,
    assess,
    elevate,
    group_by_mechanism,
    provenance_clusters,
)


def _o(region: str, mech: str = "M_FUNDING_SQUEEZE", src: str = "", origins: tuple[str, ...] = (),
       recorded: bool = True) -> Observation:
    return Observation(region=region, mechanism=mech, source=src or f"https://{region}.example/x",
                       origins=origins, origins_recorded=recorded)


# ------------------------------------------------------------------ the refusals


def test_UNRECORDED_PROVENANCE_IS_NEVER_INDEPENDENCE() -> None:
    """THE DEFAULT STATE OF THE ENTIRE CORPUS, and the one that must not read as a discovery.

    None of the seven regional miners currently records what a finding derives from. If absence
    resolved to "no shared origin", this module would elevate every echo in the corpus on its
    first run -- and it would do so with a confident-sounding count attached.
    """
    v = assess("M", [_o("cn", recorded=False), _o("br", recorded=False), _o("ru", recorded=False)])
    assert v.verdict == "UNVERIFIABLE_PROVENANCE"
    assert not v.elevates
    assert v.unrecorded == 3
    assert "INABILITY TO CHECK" in v.reason
    assert "UPPER BOUND" in v.reason


def test_ONE_UNRECORDED_SIGHTING_IS_ENOUGH_TO_WITHHOLD_THE_VERDICT() -> None:
    """A single unexamined source can be the origin the other two are echoing, so a partial check
    cannot certify the whole group. The strong claim needs every link."""
    v = assess("M", [_o("cn"), _o("kr"), _o("ru", recorded=False)])
    assert v.verdict == "UNVERIFIABLE_PROVENANCE" and v.unrecorded == 1


def test_A_SHARED_ORIGIN_COLLAPSES_THE_COUNT_TO_ONE_OBSERVATION() -> None:
    """Three ecosystems all citing one arXiv paper is ONE reading of that paper, reported three
    times. Ideas propagate outward from the English-language origin layer; this is that flow
    caught in the act."""
    cite = ("https://arxiv.org/abs/2401.00001",)
    v = assess("M", [_o("cn", origins=cite), _o("br", origins=cite), _o("ru", origins=cite)])
    assert v.verdict == "SHARED_SOURCE_ECHO"
    assert not v.elevates
    assert v.independent_clusters == 1
    assert "arxiv.org" in v.shared_origins
    assert "GAP #85" in v.reason


def test_A_CITATION_CHAIN_IS_CAUGHT_EVEN_WITHOUT_A_COMMON_THIRD_PARTY() -> None:
    """The hardest case for a human skimming two languages: the Brazilian post cites the Korean
    blog directly, so there is no shared external origin to spot -- just one idea that travelled.
    The observation's OWN locator is a provenance token precisely so this collapses."""
    kr = _o("kr", src="https://kr.blog/post-9")
    br = _o("br", src="https://br.forum/t/22", origins=("https://kr.blog/post-9",))
    v = assess("M", [kr, br])
    assert v.verdict == "SHARED_SOURCE_ECHO" and v.independent_clusters == 1


def test_ONE_ECOSYSTEM_REPEATING_ITSELF_IS_NOT_CONVERGENCE() -> None:
    """Volume from a single community is one observation with a loud voice."""
    v = assess("M", [_o("cn", src="https://a.cn/1"), _o("cn", src="https://b.cn/2"),
                     _o("cn", src="https://c.cn/3")])
    assert v.verdict == "SINGLE_ECOSYSTEM" and not v.elevates
    assert v.regions == ("cn",)


def test_AN_ORIGIN_LAYER_HOST_IS_FLAGGED_EVEN_WHEN_CITED_ONCE() -> None:
    """WorldQuant and arXiv are places regions read FROM, not peer ecosystems. A single citation
    to one is worth surfacing because it is the likely upstream of everything else in the group."""
    v = assess("M", [_o("cn", origins=("https://arxiv.org/abs/1",)),
                     _o("kr", origins=("https://kr-only.example/z",))])
    assert "arxiv.org" in v.shared_origins


# ------------------------------------------------------------------ the confirmation


def test_GENUINE_INDEPENDENCE_ELEVATES_AND_SAYS_WHAT_IT_DID_NOT_BUY() -> None:
    """The real signal: different data, venues and regimes reaching the same mechanism. It earns a
    queue place ahead of a singleton -- and NOT a lower bar, which is the misuse that would follow
    naturally from calling it 'confirmation'."""
    v = assess("M", [_o("kr", src="https://kr.blog/a", origins=("https://kr.data/x",)),
                     _o("br", src="https://br.forum/b", origins=("https://br.data/y",)),
                     _o("ru", src="https://ru.tg/c", origins=("https://ru.data/z",))])
    assert v.verdict == "INDEPENDENT_CONVERGENCE" and v.elevates
    assert v.independent_clusters == 3
    assert set(v.regions) == {"br", "kr", "ru"}
    assert any("NOT A LOWER BAR" in n for n in v.notes)


def test_TWO_INDEPENDENT_BEATS_TEN_DEPENDENT() -> None:
    """The count that matters is provenance clusters, not sightings. A module ranking on raw
    volume would put the loudest echo above the real thing."""
    echo = [_o(r, origins=("https://arxiv.org/abs/2",)) for r in
            ("cn", "jp", "kr", "in", "br", "ar", "ru", "en", "cn", "jp")]
    real = [_o("cn", src="https://cn.a/1", origins=("https://cn.d/1",)),
            _o("br", src="https://br.b/2", origins=("https://br.d/2",))]
    assert assess("echo", echo).verdict == "SHARED_SOURCE_ECHO"
    assert assess("real", real).verdict == "INDEPENDENT_CONVERGENCE"
    assert assess("real", real).independent_clusters > assess("echo", echo).independent_clusters


# ------------------------------------------------------------------ clustering + corpus


def test_CLUSTERING_IS_SINGLE_LINKAGE_SO_THE_COUNT_ERRS_LOW() -> None:
    """A and C merge because both touch B. That reports FEWER independent observations, and every
    other linkage choice would flatter the number."""
    a = _o("cn", src="https://a/1", origins=("https://shared/x",))
    b = _o("kr", src="https://b/2", origins=("https://shared/x", "https://other/y"))
    c = _o("ru", src="https://c/3", origins=("https://other/y",))
    assert len(provenance_clusters([a, b, c])) == 1


def test_DISJOINT_PROVENANCE_STAYS_DISJOINT() -> None:
    obs = [_o("cn", src="https://a/1", origins=("https://p/1",)),
           _o("kr", src="https://b/2", origins=("https://q/2",))]
    assert len(provenance_clusters(obs)) == 2


def test_GROUPING_IS_BY_MECHANISM_NOT_BY_WORDS() -> None:
    """Two languages describing one mechanism share no vocabulary; 'momentum works' in two
    languages is two claims wearing one phrase. Matching on words does both errors at once."""
    g = group_by_mechanism([_o("cn", "M_SQUEEZE"), _o("br", "M_SQUEEZE"), _o("ru", "M_CARRY")])
    assert sorted(g) == ["M_CARRY", "M_SQUEEZE"] and len(g["M_SQUEEZE"]) == 2


def test_THE_CORPUS_TALLY_MAKES_A_MISSING_FIELD_VISIBLE_RATHER_THAN_SILENT() -> None:
    """With no provenance anywhere the elevated list is empty, which reads as a broken feature and
    is in fact the correct measurement of a corpus that never recorded its sources. The tally is
    what turns that silence into a fixable gap."""
    obs = [_o("cn", "M1", recorded=False), _o("kr", "M1", recorded=False),
           _o("br", "M2", src="https://br/1", origins=("https://br.d/1",)),
           _o("ru", "M2", src="https://ru/2", origins=("https://ru.d/2",))]
    verdicts, tally = elevate(obs)
    assert tally["UNVERIFIABLE_PROVENANCE"] == 1
    assert tally["INDEPENDENT_CONVERGENCE"] == 1
    assert verdicts[0].verdict == "INDEPENDENT_CONVERGENCE", "genuine convergence must rank first"
    assert [v.mechanism for v in verdicts] == ["M2", "M1"]


def test_AN_EMPTY_CORPUS_IS_NOT_AN_ERROR_AND_NOT_A_FINDING() -> None:
    verdicts, tally = elevate([])
    assert verdicts == [] and tally == {}
    assert MIN_REGIONS >= 2

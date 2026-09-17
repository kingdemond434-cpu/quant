"""The dedup chain: five stages in order, ten reposts into one mechanism, and a genuinely
different descendant that branches instead of being erased."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import dedup_chain as dc  # noqa: E402

CLAIM = ("Gold rallies into the London PM fix on the last trading day of the month in 62% of "
         "sessions since 2015, because index-tracking funds rebalance metal exposure at the "
         "fixing print and the marginal seller is absent")


def _item(iid: str, url: str, text: str = CLAIM, **kw: object) -> dc.Item:
    base: dict = {"item_id": iid, "url": url, "text": text, "family": "session_range_breakout",
                  "instruments": ("XAUUSD",), "condition": "london pm fix month end",
                  "direction": 1, "horizon": "intraday", "source_id": f"src:{iid}"}
    base.update(kw)
    return dc.Item(**base)                                        # type: ignore[arg-type]


def test_the_five_stages_are_declared_in_order() -> None:
    assert dc.STAGES == ("canonical_source", "content_hash", "semantic_similarity",
                         "mechanism_identity", "genealogy")
    assert 0.0 < dc.DESCENDANT_THRESHOLD < dc.SEMANTIC_DUPLICATE_THRESHOLD < 1.0


def test_canonical_url_strips_the_visit_and_keeps_the_page() -> None:
    a = dc.canonical_url("HTTPS://WWW.Example.com:443/a/b/?utm_source=x&id=7&gclid=z")
    assert a == "https://example.com/a/b?id=7", "www. is not part of an identity"
    assert dc.canonical_url("http://example.com/a/index.html") == "https://example.com/a"
    assert dc.canonical_url("http://x.io/p") == dc.canonical_url("https://x.io/p")
    assert dc.canonical_url("https://example.com/a/") == dc.canonical_url("https://example.com/a")
    # a mirror is unwrapped back to the page it is serving, not treated as its own source
    assert dc.canonical_url("https://web.archive.org/web/2020/https://example.com/a") == \
        "https://example.com/a"
    assert dc.canonical_url("https://old.reddit.com/r/x/1") == "https://reddit.com/r/x/1"
    assert dc.canonical_url("") == "", "no url is not the same url as no url"
    assert dc.canonical_url("not a url") == ""


def test_stage_one_catches_the_same_page_under_two_spellings() -> None:
    view = dc.RegistryView()
    view.add(_item("a", "https://www.7hcn.com/article/1.html"))
    v = dc.dedup(_item("b", "http://7hcn.com/article/1.html?utm_campaign=wechat"), view)
    assert v.verdict == dc.DUPLICATE_OF and v.of == "a"
    assert v.stage == "canonical_source" and "canonicalisation" in v.why


def test_ten_reposts_on_ten_sites_are_one_mechanism_and_nine_edges() -> None:
    hosts = ["7hcn.com", "zhihu.com", "xueqiu.com", "weibo.com", "jisilu.cn", "bilibili.com",
             "eastmoney.com", "sina.com.cn", "163.com", "sohu.com"]
    items = [_item(f"r{i}", f"https://{h}/post/{i}") for i, h in enumerate(hosts)]
    verdicts, view = dc.fold(items)
    assert len(verdicts) == 10
    assert sum(1 for v in verdicts if v.is_new) == 1
    assert sum(1 for v in verdicts if v.is_duplicate) == 9
    assert sum(len(v.edges) for v in verdicts if v.is_duplicate) == 9
    assert all(v.of == "r0" for v in verdicts if v.is_duplicate)
    assert len({v.mechanism_key for v in verdicts}) == 1, "one strategy, one mechanism"
    assert len(view) == 1, "only the canonical telling is admitted"
    census = dc.census(verdicts)
    assert census["new"] == 1 and census["duplicates"] == 9
    assert set(census["by_deciding_stage"]) == {"content_hash"}


def test_a_reworded_repost_is_caught_by_similarity_not_by_the_hash() -> None:
    view = dc.RegistryView()
    view.add(_item("a", "https://a.example/1"))
    reworded = CLAIM.replace("62%", "sixty-two percent").replace("rallies", "rallies up")
    v = dc.dedup(_item("b", "https://b.example/2", text=reworded), view)
    assert v.verdict == dc.DUPLICATE_OF and v.of == "a"
    assert v.stage == "semantic_similarity"
    assert v.score is not None and v.score >= dc.SEMANTIC_DUPLICATE_THRESHOLD


def test_two_grounds_with_no_shared_words_stating_one_edge_are_one_mechanism() -> None:
    view = dc.RegistryView()
    view.add(_item("a", "https://a.example/1"))
    other = ("ロンドンPM指標値に向けて金が上昇しやすい。月末のリバランスで需要が発生するため。")
    v = dc.dedup(_item("b", "https://b.example/ja", text=other), view)
    assert v.verdict == dc.DUPLICATE_OF and v.of == "a"
    assert v.stage == "mechanism_identity", "the stage the other four cannot reach"
    assert "one mechanism" in v.why


def test_a_genuinely_different_descendant_branches() -> None:
    view = dc.RegistryView()
    view.add(_item("anc", "https://a.example/1"))
    child = _item("kid", "https://c.example/9",
                  text="The same month-end rebalance shows up in silver one day earlier.",
                  instruments=("XAGUSD",), horizon="multi_day", parent_ids=("anc",))
    v = dc.dedup(child, view)
    assert v.verdict == dc.DESCENDANT_OF and v.of == "anc" and v.stage == "genealogy"
    assert v.mechanism_key != view.mechanism_of["anc"]
    assert any(e[3] == "descendant" for e in v.edges)
    verdicts, view2 = dc.fold([_item("anc", "https://a.example/1"), child])
    assert len(view2) == 2, "a descendant is admitted and tested on its own"
    assert dc.census(verdicts)["descendants"] == 1


def test_prose_similarity_never_overrules_a_stated_mechanism() -> None:
    """Near-identical wording about a DIFFERENT edge is a descendant, not a duplicate."""
    view = dc.RegistryView()
    view.add(_item("a", "https://a.example/1"))
    twin = _item("b", "https://b.example/2", text=CLAIM.replace("Gold", "Silver"),
                 instruments=("XAGUSD",))
    v = dc.dedup(twin, view)
    assert v.score is not None and v.score >= dc.DESCENDANT_THRESHOLD
    assert v.verdict == dc.DESCENDANT_OF and v.stage == "genealogy"
    assert v.of == "a"


def test_an_unrelated_claim_is_new() -> None:
    view = dc.RegistryView()
    view.add(_item("a", "https://a.example/1"))
    v = dc.dedup(dc.Item(item_id="z", url="https://z.example/1",
                         text="USDJPY drifts lower through the Tokyo lunch break on the 5th and "
                              "10th of the month when exporters have already hedged.",
                         family="overnight_gap_decay", instruments=("USDJPY",),
                         condition="gotobi tokyo lunch", direction=-1, horizon="intraday"), view)
    assert v.verdict == dc.NEW and v.stage == "genealogy" and v.of == ""
    assert v.mechanism_key and v.content and v.canonical


def test_mechanism_key_is_the_five_fields_and_nothing_else() -> None:
    base = {"family": "carry", "instruments": ["AUDJPY"], "condition": "rate differential wide",
            "direction": 1, "horizon": "multi_day"}
    k = dc.mechanism_key(**base)                                  # type: ignore[arg-type]
    assert k == dc.mechanism_key(**{**base, "instruments": ["audjpy"]})   # case folded
    assert k != dc.mechanism_key(**{**base, "direction": -1})
    assert k != dc.mechanism_key(**{**base, "horizon": "intraday"})
    assert k != dc.mechanism_key(**{**base, "family": "momentum"})
    assert k != dc.mechanism_key(**{**base, "instruments": ["AUDJPY", "NZDJPY"]})
    assert len(k) == 16


def test_normalisation_and_shingles_read_cjk_as_well_as_english() -> None:
    assert dc.normalise_text("  A,  B.  c! ") == "a b c"
    assert dc.content_hash("") == "", "an empty body has no hash to share"
    assert dc.content_hash("A, b.") == dc.content_hash("a  b")
    cjk = dc.shingles("黄金上涨的原因是月末再平衡")
    assert len(cjk) >= 5, "CJK must shingle into overlapping glyph runs, not one token"
    assert dc.similarity(cjk, cjk) == 1.0
    assert dc.similarity(cjk, frozenset()) == 0.0


def test_the_view_can_be_seeded_from_registry_rows() -> None:
    view = dc.RegistryView.from_rows([
        {"discovery_id": "d1", "mechanism": CLAIM, "assets": ["XAUUSD"],
         "url": "https://a.example/1", "source_id": "s1"},
        {"no_id": True}])
    assert len(view) == 1 and view.knows("d1")
    v = dc.dedup(_item("new", "https://a.example/1"), view)
    assert v.is_duplicate and v.of == "d1" and v.stage == "canonical_source"

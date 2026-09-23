"""THE CRAWLERS' BUDGET REALLY IS THE SOURCE REGISTRY'S SHARES -- and it really does fall back.

Tier-1 W17's measured gap was "the source registry and the unseen-frontier estimator exist; THE
CRAWLER DOES NOT YET READ THE SHARES". A wiring claim like that is worth exactly what its test is
worth, so these tests do not check that a reader exists -- they check that the ORDER CHANGES when
the shares change, and that it does not change when the artifact is absent or stale. Both halves
matter equally: a crawler that silently reorders itself off a week-old report is not following
evidence, it is following a fossil.

`deep_forest_miner.schedule()` is called for real here, not imitated, because the claim is about
the scheduler the desk actually runs. The expansion tests plant a registry whose share ROSE and
assert the neighbours land in the REGISTERED grounds file -- and that a source carrying a terms,
robots or "snippets only" note is MINED WITH THAT NOTE ATTACHED (LAWS 5e, 2026-09-23) rather than
dropped. These assertions were the opposite until 2026-09-23: they pinned a brake, so when the
brake was deleted the test had to say the new rule, not vanish.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import source_shares as ss  # noqa: E402


class _Src:
    """What `world_frontier.due()` hands the crawler: something with a url and a host."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.host = url.split("//", 1)[-1].split("/", 1)[0]

    def __repr__(self) -> str:                                          # pragma: no cover
        return f"<{self.host}>"


def _artifact(tmp: Path, shares: dict[str, float], rows: dict[str, Any] | None = None,
              age_h: float = 1.0) -> tuple[Path, Path]:
    # SEPARATE DIRECTORIES ON PURPOSE: NTFS is case-insensitive, so reports/SOURCE_REGISTRY.json
    # and data/source_registry.json are the SAME FILE inside one folder on the box that trades.
    # The real layout keeps them apart and so must the fixture -- the first version of this
    # helper silently overwrote the shares with the rows and every assertion read "empty".
    at = (datetime.now(tz=UTC) - timedelta(hours=age_h)).isoformat(timespec="seconds")
    (tmp / "reports").mkdir(parents=True, exist_ok=True)
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    rpt = tmp / "reports" / "SOURCE_REGISTRY.json"
    rpt.write_text(json.dumps({"at": at, "n_sources": len(shares), "shares": shares}), "utf-8")
    reg = tmp / "data" / "source_registry.json"
    reg.write_text(json.dumps({"at": at, "sources": rows or {}}, ensure_ascii=False), "utf-8")
    return rpt, reg


def _rows(*specs: tuple[str, str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sid, url, extra in specs:
        out[sid] = {"source_id": sid, "name": sid, "url": url, "route": "http",
                    "region": "cn", "language": "zh", "aliases": [sid], **extra}
    return out


# --------------------------------------------------------------- reading the published shares
def test_an_absent_artifact_leaves_todays_behaviour_exactly_as_it_was(tmp_path: Path) -> None:
    state = ss.load(report=tmp_path / "nope.json", registry=tmp_path / "nope2.json")
    assert state["status"] == "absent"
    assert "crawl order unchanged" in state["why"]
    picked = [_Src("https://a.cn/x"), _Src("https://b.cn/y"), _Src("https://c.cn/z")]
    out, meta = ss.order_picked(picked, state)
    assert [s.url for s in out] == [s.url for s in picked]
    assert meta["status"] == "absent"


def test_a_stale_artifact_is_not_a_budget(tmp_path: Path) -> None:
    """A report nobody is regenerating is a fossil, and spending against it is worse than
    spending in the old order -- the organ that priced it is down."""
    rpt, reg = _artifact(tmp_path, {"s:a": 0.9, "s:b": 0.1},
                         _rows(("s:a", "https://a.cn/", {}), ("s:b", "https://b.cn/", {})),
                         age_h=ss.STALE_H + 5.0)
    state = ss.load(report=rpt, registry=reg)
    assert state["status"] == "stale"
    assert "is not running" in state["why"]
    picked = [_Src("https://b.cn/y"), _Src("https://a.cn/x")]
    out, _ = ss.order_picked(picked, state)
    assert [s.url for s in out] == ["https://b.cn/y", "https://a.cn/x"]


def test_an_empty_shares_block_is_named_not_guessed(tmp_path: Path) -> None:
    rpt, reg = _artifact(tmp_path, {})
    state = ss.load(report=rpt, registry=reg)
    assert state["status"] == "empty"
    assert state["shares"] == {}


# --------------------------------------------------------- world_crawler: fetches follow shares
def test_the_fetch_order_follows_the_shares(tmp_path: Path) -> None:
    """THE CLAIM, TESTED. The run stops on its clock, so the head of this list is the budget."""
    rows = _rows(("s:low", "https://low.cn/", {}), ("s:high", "https://high.cn/", {}))
    rpt, reg = _artifact(tmp_path, {"s:low": 0.01, "s:high": 0.9}, rows)
    state = ss.load(report=rpt, registry=reg)
    assert state["status"] == "present"
    picked = [_Src("https://low.cn/a"), _Src("https://high.cn/b")]
    out, meta = ss.order_picked(picked, state)
    assert [s.host for s in out] == ["high.cn", "low.cn"], "the high-share host must be first"
    assert meta["n_ranked"] == 2

    # AND THE ORDER MOVES WITH THE EVIDENCE: flip the shares, the order flips.
    rpt2, reg2 = _artifact(tmp_path / "flip", {"s:low": 0.9, "s:high": 0.01}, rows)
    flipped, _ = ss.order_picked(picked, ss.load(report=rpt2, registry=reg2))
    assert [s.host for s in flipped] == ["low.cn", "high.cn"]


def test_an_unknown_host_keeps_its_place_among_its_equals(tmp_path: Path) -> None:
    """A source the registry has never priced must never be pushed to the back: an unmeasured
    source is not a low-yield one (L1.28a), and the sort is stable so it keeps its position."""
    # TWO priced sources, so the mean is genuinely below the top share. With one source in the
    # registry every share IS the mean, the factor is 1.0 and nothing moves -- which is correct
    # arithmetic and would have made this test assert nothing.
    rows = _rows(("s:high", "https://high.cn/", {}), ("s:thin", "https://thin.cn/", {}))
    rpt, reg = _artifact(tmp_path, {"s:high": 0.9, "s:thin": 0.1}, rows)
    state = ss.load(report=rpt, registry=reg)
    picked = [_Src("https://unknown1.cn/a"), _Src("https://high.cn/b"),
              _Src("https://unknown2.cn/c")]
    out, meta = ss.order_picked(picked, state)
    assert out[0].host == "high.cn"
    assert [s.host for s in out[1:]] == ["unknown1.cn", "unknown2.cn"]
    assert meta["n_unknown"] == 2 and len(out) == 3


def test_a_labelled_source_is_crawled_and_its_label_is_carried(tmp_path: Path) -> None:
    """MINED, NOT DROPPED (LAWS 5e, 2026-09-23). `machine_use_allowed=false`, `unreachable` and
    `snippets_only` used to remove a source from the pass; all three were discovery brakes the
    desk imposed on itself. Every one of these four is crawled now, and the three that carry a
    note carry it as a LABEL the crawler records on each row it produces."""
    rows = _rows(("s:ok", "https://ok.cn/", {}),
                 ("s:no", "https://no.cn/", {"machine_use_allowed": False}),
                 ("s:dead", "https://dead.cn/", {"route": "unreachable"}),
                 ("s:snip", "https://snip.cn/", {"snippets_only": True}))
    rpt, reg = _artifact(tmp_path, {"s:ok": 0.4, "s:no": 0.4, "s:dead": 0.1, "s:snip": 0.1}, rows)
    state = ss.load(report=rpt, registry=reg)
    picked = [_Src(f"https://{h}.cn/p") for h in ("ok", "no", "dead", "snip")]
    out, meta = ss.order_picked(picked, state)
    assert sorted(s.host for s in out) == ["dead.cn", "no.cn", "ok.cn", "snip.cn"]
    assert meta["n_refused"] == 0 and not meta.get("refused")
    assert meta["n_labelled"] == 3
    labels = {r["url"]: r["terms_note"] for r in meta["labelled"]}
    assert "machine_use_allowed=false" in labels["https://no.cn/p"]
    assert "route=unreachable" in labels["https://dead.cn/p"]
    assert "snippets only" in labels["https://snip.cn/p"]
    assert all("redistribution withheld" in v for v in labels.values())


def test_the_only_drop_left_is_one_of_the_five_refused_acts(tmp_path: Path) -> None:
    """The hard boundary survived the deletion of everything else: a row whose registry entry
    declares a refused ACCESS LABEL, an authenticated surface or MNPI is still removed and
    named. That is the whole refusal, and it is about acts, not about terms."""
    rows = _rows(("s:ok", "https://ok.cn/", {}),
                 ("s:priv", "https://priv.cn/", {"access_label": "PRIVATE"}),
                 ("s:auth", "https://auth.cn/", {"requires_auth": True}))
    state = ss.load(*_artifact(tmp_path, {"s:ok": 0.4, "s:priv": 0.3, "s:auth": 0.3}, rows))
    picked = [_Src(f"https://{h}.cn/p") for h in ("ok", "priv", "auth")]
    out, meta = ss.order_picked(picked, state)
    assert [s.host for s in out] == ["ok.cn"]
    assert meta["n_refused"] == 2
    assert all("hard boundary" in r["why"] for r in meta["refused"])


def test_the_share_factor_is_clipped_both_ways(tmp_path: Path) -> None:
    """A bound on a small-count ratio estimator, not a cap on research: one hour's 90% share
    must not take 90x the mean, and a thin source must not be reduced to nothing."""
    rows = _rows(*[(f"s:{i}", f"https://h{i}.cn/", {}) for i in range(20)])
    shares = {"s:0": 0.81}
    shares.update({f"s:{i}": 0.01 for i in range(1, 20)})
    state = ss.load(*_artifact(tmp_path, shares, rows))
    hi, _ = ss.factor_for(state, "https://h0.cn/")
    lo, _ = ss.factor_for(state, "https://h1.cn/")
    assert hi == ss.MAX_FACTOR
    assert lo >= ss.MIN_FACTOR > 0.0


# ------------------------------------------------------- deep_forest: seconds follow the shares
def test_the_deep_forest_scheduler_really_reorders(tmp_path: Path) -> None:
    """The real `schedule()`, not an imitation: it sorts on `weight`, so reweighting the grounds
    is what moves both the order and the per-ground seconds `run()` derives from the same number.
    """
    from research import deep_forest_miner as dfm
    grounds = [{"name": "quiet ground", "region": "cn", "weight": 3.0,
                "url": "https://quiet.cn/"},
               {"name": "paying ground", "region": "cn", "weight": 1.0,
                "url": "https://paying.cn/"}]
    # BEFORE: the registered weights alone put the quiet ground first.
    assert [g["name"] for g in dfm.schedule(grounds)] == ["quiet ground", "paying ground"]

    rows = _rows(("ground:quiet", "https://quiet.cn/", {"name": "quiet ground"}),
                 ("ground:paying", "https://paying.cn/", {"name": "paying ground"}))
    rows["ground:quiet"]["aliases"] = ["quiet ground"]
    rows["ground:paying"]["aliases"] = ["paying ground"]
    state = ss.load(*_artifact(tmp_path, {"ground:quiet": 0.02, "ground:paying": 0.9}, rows))
    reweighted, meta = ss.weight_grounds(grounds, state)
    assert meta["status"] == "present" and meta["n_reweighted"] == 2
    # AFTER: the paying ground's measured share carries it past a heavier registered weight.
    assert [g["name"] for g in dfm.schedule(reweighted)] == ["paying ground", "quiet ground"]

    # AND THE SECONDS FOLLOW, because run() divides budget_s by exactly this weight.
    total = sum(float(g["weight"]) for g in reweighted)
    paying = next(g for g in reweighted if g["name"] == "paying ground")
    assert float(paying["weight"]) / total > 0.5
    # the file on disk is untouched: the registered weight is the human's declaration
    assert grounds[0]["weight"] == 3.0 and grounds[1]["weight"] == 1.0


def test_deep_forest_grounds_are_untouched_when_the_artifact_is_absent(tmp_path: Path) -> None:
    grounds = [{"name": "a", "region": "cn", "weight": 3.0},
               {"name": "b", "region": "cn", "weight": 1.0}]
    state = ss.load(report=tmp_path / "nope.json", registry=tmp_path / "nope2.json")
    out, meta = ss.weight_grounds(grounds, state)
    assert out == grounds
    assert meta["status"] == "absent" and meta["n_reweighted"] == 0


def test_a_labelled_ground_is_worked_and_carries_its_label(tmp_path: Path) -> None:
    """`machine_use_allowed=false` used to delete this ground from the pass. It is worked now,
    keeps its share factor, and carries the registry's note on the ground copy (LAWS 5e)."""
    grounds = [{"name": "ok", "region": "cn", "weight": 1.0, "url": "https://ok.cn/"},
               {"name": "labelled", "region": "cn", "weight": 9.0, "url": "https://no.cn/"}]
    rows = _rows(("g:ok", "https://ok.cn/", {}),
                 ("g:no", "https://no.cn/", {"machine_use_allowed": False}))
    state = ss.load(*_artifact(tmp_path, {"g:ok": 0.5, "g:no": 0.5}, rows))
    out, meta = ss.weight_grounds(grounds, state)
    assert sorted(g["name"] for g in out) == ["labelled", "ok"]
    assert meta["n_refused"] == 0 and meta["n_labelled"] == 1
    hit = next(g for g in out if g["name"] == "labelled")
    assert "machine_use_allowed=false" in hit["_terms_note"]
    assert "redistribution withheld" in hit["_terms_note"]


def test_a_hard_boundary_ground_is_still_never_worked(tmp_path: Path) -> None:
    """The five acts stayed. A ground the registry labels PRIVATE is dropped and named."""
    grounds = [{"name": "ok", "region": "cn", "weight": 1.0, "url": "https://ok.cn/"},
               {"name": "refused", "region": "cn", "weight": 9.0, "url": "https://no.cn/"}]
    rows = _rows(("g:ok", "https://ok.cn/", {}),
                 ("g:no", "https://no.cn/", {"access_label": "STOLEN_UNAUTHORIZED"}))
    state = ss.load(*_artifact(tmp_path, {"g:ok": 0.5, "g:no": 0.5}, rows))
    out, meta = ss.weight_grounds(grounds, state)
    assert [g["name"] for g in out] == ["ok"]
    assert meta["n_refused"] == 1
    assert "hard boundary" in meta["refused"][0]["why"]


# ------------------------------------------------------------------------ source expansion
def _grounds_file(tmp: Path, grounds: list[dict[str, Any]]) -> Path:
    p = tmp / "deep_forest_sources.json"
    p.write_text(json.dumps({"note": "planted", "grounds": grounds}, ensure_ascii=False), "utf-8")
    return p


def test_a_rising_source_gets_its_neighbourhood_registered(tmp_path: Path) -> None:
    """Authors, linked forums, archives, citations, code repos, adjacent terminology -- appended
    to the REGISTERED grounds file, never hard-coded into a crawler."""
    rows = _rows(("g:hot", "https://hot.cn/", {"name": "hot ground"}))
    state = ss.load(*_artifact(tmp_path, {"g:hot": 0.9}, rows))
    gpath = _grounds_file(tmp_path, [{"name": "hot ground", "url": "https://hot.cn/"}])
    spath = tmp_path / "source_expansion.json"
    observed = {"https://hot.cn/": [
        ("https://hot.cn/author/li_wei", "李伟"),
        ("https://forum.hot.cn/thread/992", "套利讨论"),
        ("https://github.com/li_wei/backtester", "code"),
        ("https://hot.cn/menu", "Next"),
    ]}
    meta = ss.expand(observed, state, grounds_path=gpath, state_path=spath)
    assert meta["n_risen"] == 1
    assert meta["n_appended"] == 3, meta
    kinds = {a["neighbourhood"] for a in meta["added"]}
    assert kinds == {"author", "forum", "code"}
    doc = json.loads(gpath.read_text("utf-8"))
    assert len(doc["grounds"]) == 4
    new = [g for g in doc["grounds"] if g.get("candidate")]
    assert all(g["discovered_from"] == "g:hot" for g in new)
    assert all("SOURCE EXPANSION" in g["why"] for g in new)
    assert spath.exists()


def test_a_share_that_did_not_rise_expands_nothing(tmp_path: Path) -> None:
    """Expansion follows a RISE, not a level: re-running on the same shares must be inert, or
    every hour would mint the same neighbours again."""
    rows = _rows(("g:hot", "https://hot.cn/", {}))
    state = ss.load(*_artifact(tmp_path, {"g:hot": 0.9}, rows))
    gpath = _grounds_file(tmp_path, [])
    spath = tmp_path / "source_expansion.json"
    observed = {"https://hot.cn/": [("https://forum.hot.cn/thread/1", "套利")]}
    first = ss.expand(observed, state, grounds_path=gpath, state_path=spath)
    assert first["n_appended"] == 1
    second = ss.expand(observed, state, grounds_path=gpath, state_path=spath)
    assert second["n_risen"] == 0 and second["n_appended"] == 0
    assert len(json.loads(gpath.read_text("utf-8"))["grounds"]) == 1


def test_expansion_mints_a_labelled_source_s_neighbour_with_the_label_copied(
        tmp_path: Path) -> None:
    """A parent carrying `machine_use_allowed=false` used to mint NO neighbours. It mints them
    now, and each candidate ground carries the parent's terms note (LAWS 5e, 2026-09-23)."""
    rows = _rows(("g:no", "https://no.cn/", {"machine_use_allowed": False}))
    state = ss.load(*_artifact(tmp_path, {"g:no": 0.9}, rows))
    gpath = _grounds_file(tmp_path, [])
    meta = ss.expand({"https://no.cn/": [("https://forum.no.cn/thread/1", "套利")]}, state,
                     grounds_path=gpath, state_path=tmp_path / "st.json")
    assert meta["n_appended"] == 1 and meta["n_refused"] == 0 and meta["n_labelled"] == 1
    minted = json.loads(gpath.read_text("utf-8"))["grounds"]
    assert len(minted) == 1
    assert "machine_use_allowed=false" in minted[0]["terms_note"]


def test_expansion_never_mints_a_neighbour_of_a_hard_boundary_source(tmp_path: Path) -> None:
    """The one refusal that survived: a parent on the five acts mints nothing, and says so."""
    rows = _rows(("g:no", "https://no.cn/", {"access_label": "CONFIDENTIAL_MNPI"}))
    state = ss.load(*_artifact(tmp_path, {"g:no": 0.9}, rows))
    gpath = _grounds_file(tmp_path, [])
    meta = ss.expand({"https://no.cn/": [("https://forum.no.cn/thread/1", "套利")]}, state,
                     grounds_path=gpath, state_path=tmp_path / "st.json")
    assert meta["n_appended"] == 0 and meta["n_refused"] == 1
    assert json.loads(gpath.read_text("utf-8"))["grounds"] == []


def test_expansion_is_inert_without_a_fresh_artifact(tmp_path: Path) -> None:
    state = ss.load(report=tmp_path / "nope.json", registry=tmp_path / "nope2.json")
    gpath = _grounds_file(tmp_path, [])
    meta = ss.expand({"https://hot.cn/": [("https://forum.hot.cn/t/1", "套利")]}, state,
                     grounds_path=gpath, state_path=tmp_path / "st.json")
    assert meta["status"] == "absent" and meta["n_appended"] == 0
    assert json.loads(gpath.read_text("utf-8"))["grounds"] == []


def test_a_neighbour_already_on_file_is_not_duplicated(tmp_path: Path) -> None:
    rows = _rows(("g:hot", "https://hot.cn/", {}))
    state = ss.load(*_artifact(tmp_path, {"g:hot": 0.9}, rows))
    gpath = _grounds_file(tmp_path, [{"name": "known", "url": "https://forum.hot.cn/thread/1"}])
    meta = ss.expand({"https://hot.cn/": [("https://forum.hot.cn/thread/1", "套利")]}, state,
                     grounds_path=gpath, state_path=tmp_path / "st.json")
    assert meta["n_appended"] == 0
    assert len(json.loads(gpath.read_text("utf-8"))["grounds"]) == 1


def test_the_neighbourhood_classifier_knows_navigation_from_ground() -> None:
    assert ss.classify("https://x.cn/author/wang", "") == "author"
    assert ss.classify("https://x.cn/forum/t/1", "") == "forum"
    assert ss.classify("https://web.archive.org/web/2020/https://x.cn", "") == "archive"
    assert ss.classify("https://doi.org/10.1234/abc", "") == "citation"
    assert ss.classify("https://gitee.com/u/quant-lib", "") == "code"
    assert ss.classify("https://x.cn/post/91", "季节性规律") == "adjacent_topic"
    assert ss.classify("https://x.cn/post/91", "下一页") is None
    # search plumbing is a query, not a source
    assert ss.classify("https://www.google.com/search?q=arbitrage", "arbitrage") is None
    assert ss.classify("/relative/path", "arbitrage") is None


def test_dry_expansion_writes_nothing(tmp_path: Path) -> None:
    rows = _rows(("g:hot", "https://hot.cn/", {}))
    state = ss.load(*_artifact(tmp_path, {"g:hot": 0.9}, rows))
    gpath = _grounds_file(tmp_path, [])
    spath = tmp_path / "st.json"
    meta = ss.expand({"https://hot.cn/": [("https://forum.hot.cn/t/1", "套利")]}, state,
                     grounds_path=gpath, state_path=spath, apply=False)
    assert meta["n_appended"] == 1 and meta["applied"] is False
    assert json.loads(gpath.read_text("utf-8"))["grounds"] == []
    assert not spath.exists()


def test_expansion_is_bounded_per_pass_and_per_source(tmp_path: Path) -> None:
    """One link-farm page may not fill a pass's expansion quota."""
    rows = _rows(("g:hot", "https://hot.cn/", {}))
    state = ss.load(*_artifact(tmp_path, {"g:hot": 0.9}, rows))
    gpath = _grounds_file(tmp_path, [])
    links = [(f"https://forum.hot.cn/thread/{i}", "套利") for i in range(50)]
    meta = ss.expand({"https://hot.cn/": links}, state, grounds_path=gpath,
                     state_path=tmp_path / "st.json")
    assert meta["n_appended"] == ss.MAX_NEW_PER_SOURCE


@pytest.mark.parametrize("row,labelled", [
    ({}, False),
    ({"licence_note": "NOT FETCHABLE -- recorded so the gap is visible"}, True),
    ({"licence_note": "SEARCH-INDEX SNIPPETS ONLY (OP-041)"}, True),
    ({"licence_note": "WEB-PUBLIC; concept reimplemented independently"}, False),
])
def test_licence_notes_are_read_as_labels_not_refusals(row: dict[str, Any],
                                                       labelled: bool) -> None:
    """LAWS 5e (2026-09-23): every one of these is MINED. The two restrictive notes used to
    return False here; they return True with the note folded into the reason, so the caller can
    record it as provenance and route redistribution off it."""
    ok, why = ss.machine_use_allowed(row)
    assert ok is True, why
    assert ("redistribution withheld" in why) is labelled, why


@pytest.mark.parametrize("row", [
    {"access_label": "PRIVATE"},
    {"access_label": "CONFIDENTIAL_MNPI"},
    {"access_label": "STOLEN_UNAUTHORIZED"},
    {"requires_auth": True},
    {"is_mnpi": True},
])
def test_the_five_refused_acts_are_the_only_false(row: dict[str, Any]) -> None:
    ok, why = ss.machine_use_allowed(row)
    assert ok is False and "hard boundary" in why

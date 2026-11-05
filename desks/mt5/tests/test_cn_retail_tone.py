"""CN RETAIL TONE, OFFLINE -- Guba board parsing, the Chinese lexicon, the PIT daily series, the
gates, the vault harvest, the optional LLM column and the wiring into nlp_social_cells.

No network: every page is a fixture (`fixtures/cn_retail_tone/*.synthetic.*`, hand-built in the
shape of the vaulted `list,waihui.html` page) or a page already vaulted in this repository, and
every organ run is pointed at a temp store, lake, axis, report and digest. Chinese test strings
carry the full-width punctuation real board titles use (hence RUF001 off for this file).
"""
# ruff: noqa: RUF001
from __future__ import annotations

import gzip
import json
import math
import sys
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cn_retail_tone as organ  # type: ignore[import-not-found]  # noqa: E402
import nlp_social_cells as nsc  # type: ignore[import-not-found]  # noqa: E402

from libs.data.free_stack import FetchError  # noqa: E402
from libs.research import guba_tone as gt  # noqa: E402

FIX = _DESK / "tests" / "fixtures" / "cn_retail_tone"
PAGE = (FIX / "guba_list_waihui.synthetic.html").read_text("utf-8")
ROBOTS = (FIX / "robots.synthetic.txt").read_bytes()
SEEN = datetime(2026, 9, 3, 16, 0, tzinfo=UTC)
WAIHUI = organ.Board("USDCNH", "waihui", "cny")


# ------------------------------------------------------------------------------------ lexicon
def test_the_lexicon_matches_longest_first_and_flips_on_a_negator() -> None:
    assert gt.lexicon_hits("大涨") == (1, 0)                       # one hit, not 大涨 + 涨
    assert gt.lexicon_hits("今天不涨") == (0, 1)
    assert gt.lexicon_hits("别割肉，抄底") == (2, 0)
    assert gt.lexicon_tone("看空，割肉跑路") == (-1.0, True)
    assert gt.lexicon_tone("今天没人聊") == (0.0, False)


def test_the_cny_lexicon_reads_the_usdcnh_axis_and_skips_other_currencies() -> None:
    assert gt.lexicon_tone("人民币升值了，结汇的赶紧", "cny") == (-1.0, True)
    assert gt.lexicon_tone("红纸贬值破7，赶紧购汇", "cny") == (1.0, True)
    assert gt.lexicon_hits("日元升值", "cny") == (0, 0)
    assert gt.lexicon_hits("日元升值很多人结汇", "cny") == (0, 1)


# ------------------------------------------------------------------------------------ parsing
def test_a_board_page_parses_to_titles_hashed_authors_and_utc_times() -> None:
    posts = gt.parse_board(PAGE, "waihui", SEEN)
    assert posts is not None and len(posts) == 8
    p = next(x for x in posts if x.post_id == "9000000002")
    assert p.published_at == datetime(2026, 9, 3, 14, 30, 7, tzinfo=UTC)   # Beijing -> UTC
    assert p.first_seen_at == SEEN and p.author and p.author != "101"
    kept = gt.retail_posts(posts)
    ids = {x.post_id for x in kept}
    assert "9000000001" not in ids                                  # pinned board notice
    assert "9000000006" not in ids                                  # another bar's article
    assert len(kept) == 6


def test_a_page_without_an_article_list_is_none_never_a_quiet_board() -> None:
    assert gt.parse_board("<html><textarea id=renderData>{\"_waf_x\":1}</textarea>", "w",
                          SEEN) is None
    assert gt.parse_board("var article_list={\"re\": []};", "w", SEEN) == []


def test_a_real_vaulted_guba_page_parses_offline() -> None:
    vault = _ROOT / "desks/mt5/data/intelligence/world/vault/guba.eastmoney.com"
    pages = []
    for f in sorted(vault.glob("*.gz")):
        got = gt.split_vault_page(gzip.decompress(f.read_bytes()))
        if got and got[0]["url"].endswith("list,waihui.html"):
            pages.append(got)
    if not pages:
        pytest.skip("no vaulted waihui list page in this checkout")
    meta, html = pages[0]
    posts = gt.parse_board(html, "waihui", datetime.fromisoformat(meta["fetched_utc"]))
    assert posts and len(posts) >= 20
    assert all(p.published_at is not None for p in posts)


# ------------------------------------------------------------------------------- PIT series
def _post(pid: str, title: str, pub: datetime, seen: datetime, author: str = "") -> gt.BoardPost:
    return gt.BoardPost(board="b", post_id=pid, title=title, published_at=pub,
                        first_seen_at=seen, author=author or f"a{pid}")


def test_a_post_seen_after_its_day_closed_is_late_and_never_backfilled() -> None:
    d = datetime(2026, 9, 3, tzinfo=UTC)
    posts = [_post("1", "大涨", d + timedelta(hours=3), d + timedelta(hours=4)),
             _post("2", "大跌", d + timedelta(hours=5), d + timedelta(days=1, hours=2)),
             _post("3", "暴跌", d + timedelta(days=1, hours=1), d + timedelta(days=1, hours=2))]
    rows = gt.daily_series(posts, instrument="X", board="b", lexicon="equity",
                           observations={"2026-09-03": 1, "2026-09-04": 1, "2026-09-05": 0},
                           asof=d + timedelta(days=1, hours=3))
    assert [r.day for r in rows] == ["2026-09-03"]           # 09-04 has not closed yet
    r = rows[0]
    assert (r.n_posts, r.n_late, r.tone_mean) == (1, 1, 1.0)   # the late 大跌 is not folded in
    assert r.available_time == "2026-09-04T00:00:00+00:00"
    later = gt.daily_series(posts, instrument="X", board="b", lexicon="equity",
                            observations={"2026-09-03": 1, "2026-09-04": 1},
                            asof=d + timedelta(days=3))
    assert [x.day for x in later] == ["2026-09-03", "2026-09-04"]
    assert later[0].tone_mean == 1.0                           # yesterday is not rewritten


def test_an_unobserved_day_has_no_row_and_a_reseen_post_counts_once() -> None:
    d = datetime(2026, 9, 3, tzinfo=UTC)
    posts = [_post("1", "上涨", d + timedelta(hours=1), d + timedelta(hours=2)),
             _post("1", "上涨", d + timedelta(hours=1), d + timedelta(hours=6))]
    rows = gt.daily_series(posts, instrument="X", board="b", lexicon="equity",
                           observations={"2026-09-03": 2}, asof=d + timedelta(days=5))
    assert [(r.day, r.n_posts, r.n_observations) for r in rows] == [("2026-09-03", 1, 2)]


def test_features_use_only_prior_days_and_need_seven_of_them() -> None:
    rows = [gt.ToneRow(day=f"2026-09-{i + 1:02d}", instrument="X", board="b",
                       n_posts=10 if i < 8 else 40, n_scored=1, n_late=0, n_observations=1,
                       tone_mean=0.1 * (i % 2), tone_llm_mean=math.nan, n_llm=0,
                       available_time="") for i in range(9)]
    out = gt.features(rows)
    assert all(math.isnan(r.volume_z) for r in out[:7])
    assert out[7].volume_z == 0.0           # a flat history: float noise is not dispersion
    wavy = [gt.ToneRow(day=f"2026-09-{i + 1:02d}", instrument="X", board="b",
                       n_posts=(10 + i % 3) if i < 8 else 40, n_scored=1, n_late=0,
                       n_observations=1, tone_mean=0.1 * (i % 2), tone_llm_mean=math.nan,
                       n_llm=0, available_time="") for i in range(9)]
    out = gt.features(wavy)
    assert out[8].volume_z > 3 and math.isfinite(out[8].tone_delta)
    spiked = gt.features([*wavy[:8], gt.ToneRow(**{**wavy[8].__dict__, "n_posts": 4000})])
    assert spiked[7].volume_z == out[7].volume_z           # a later day never moves an earlier one
    assert out[8].tone_shock_signed == pytest.approx(
        out[8].volume_z * (1 if out[8].tone_delta > 0 else -1))


# -------------------------------------------------------------------------------- the organ
class FakeNet:
    def __init__(self, robots: bytes | Exception = ROBOTS,
                 pages: Mapping[str, bytes] | None = None) -> None:
        self.robots = robots
        self.pages = dict(pages or {"waihui": PAGE.encode("utf-8")})
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str] | None,
                 body: bytes | None) -> bytes:
        self.calls.append((url, dict(headers or {})))
        if url.endswith("/robots.txt"):
            if isinstance(self.robots, Exception):
                raise self.robots
            return self.robots
        for board, page in self.pages.items():
            if url.endswith(f"list,{board}.html"):
                return page
        raise FetchError("http_404", url)


def _paths(tmp: Path) -> dict[str, Any]:
    return {"store_root": tmp / "store", "series_dir": tmp / "series",
            "axis_out": tmp / "axes" / "cn.json", "report": tmp / "rep.json",
            "vault": tmp / "vault", "digest_path": tmp / "digest.json", "pause_s": 0.0}


def test_a_pass_fetches_only_allowed_guba_boards_and_never_xueqiu(tmp_path: Path) -> None:
    net = FakeNet()
    now = datetime(2026, 9, 4, 1, 0, tzinfo=UTC)
    rep = organ.run(now, get=net, chat=None, **_paths(tmp_path))
    urls = [u for u, _ in net.calls]
    assert not any("xueqiu" in u for u in urls)
    assert all("Cookie" not in h for _, h in net.calls)
    assert sum(u.endswith("/robots.txt") for u in urls) == 1    # read once per host per pass
    post = rep["fetch"]["postures"]
    assert post["waihui"]["posture"] == "OK" and post["waihui"]["n"] == 8
    assert post["zssh000001"]["posture"] == "UNREACHABLE"         # 404 in the fake network
    assert rep["sources"]["guba"]["state"] == "LIVE"
    assert rep["sources"]["xueqiu"]["state"] == "BLOCKED"
    assert "WAF" in rep["sources"]["xueqiu"]["why"]
    stored = (tmp_path / "store" / "posts.jsonl").read_text("utf-8")
    assert "股友synthetic" not in stored and '"101"' not in stored  # no nickname, no raw user id


def test_robots_disallow_and_unreachable_robots_stop_the_fetch(tmp_path: Path) -> None:
    disallow = FakeNet(robots=b"User-agent: *\nDisallow: /list,waihui.html\n")
    rep = organ.run(datetime(2026, 9, 4, tzinfo=UTC), get=disallow, chat=None,
                    **_paths(tmp_path / "a"))
    assert rep["fetch"]["postures"]["waihui"]["posture"] == "ROBOTS_DISALLOWED"
    assert not any(u.endswith("list,waihui.html") for u, _ in disallow.calls)
    down = FakeNet(robots=FetchError("proxy", "robots"))
    rep = organ.run(datetime(2026, 9, 4, tzinfo=UTC), get=down, chat=None,
                    **_paths(tmp_path / "b"))
    assert rep["fetch"]["postures"]["waihui"]["posture"] == "ROBOTS_UNREADABLE"
    assert rep["fetch"]["requests"] == 0
    missing = FakeNet(robots=FetchError("http_404", "robots"))
    rep = organ.run(datetime(2026, 9, 4, tzinfo=UTC), get=missing, chat=None,
                    **_paths(tmp_path / "c"))
    assert rep["fetch"]["postures"]["waihui"]["posture"] == "OK"     # RFC 9309: 4xx allows


def test_a_source_without_a_permitting_terms_row_is_held(tmp_path: Path) -> None:
    terms = tmp_path / "terms.json"
    terms.write_text(json.dumps({"sources": [{"id": "cn_guba", "auth": "cookie",
                                              "machine_use_allowed": True}]}), "utf-8")
    net = FakeNet()
    rep = organ.run(datetime(2026, 9, 4, tzinfo=UTC), get=net, chat=None, terms_path=terms,
                    **_paths(tmp_path))
    assert {v["posture"] for v in rep["fetch"]["postures"].values()} == {"HELD"}
    assert net.calls == []
    assert organ.terms_gate("nope", terms)[0] == organ.HELD
    assert organ.terms_gate("cn_guba")[0] == organ.LIVE            # the repo's own row permits


def test_the_series_lands_in_the_lake_with_available_time_and_a_stable_known_at(
        tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    base = datetime(2026, 9, 3, 16, 0, tzinfo=UTC)
    organ.run(base, get=FakeNet(), chat=None, **paths)
    first = organ.run(base + timedelta(hours=9), get=FakeNet(), chat=None, **paths)
    assert first["instruments"]["USDCNH"]["rows"] == 1
    frame = pd.read_parquet(tmp_path / "series" / "cn_retail_tone_USDCNH.parquet")
    row = frame.iloc[0]
    assert row["day"] == "2026-09-03" and row["period"] == "2026-09-03"
    assert row["available_time"] == "2026-09-04T00:00:00+00:00"
    assert row["n_posts"] == 4            # 02, 03, 04, 05: published 09-03 UTC, seen 09-03
    assert row["n_late"] == 0
    assert row["tone_mean"] == pytest.approx((-1 + 1 - 1 + 0) / 4)
    for col in ("volume_z", "tone_mean", "tone_delta", "known_at", "source_id"):
        assert col in frame.columns
    known = row["known_at"]
    organ.run(base + timedelta(days=2), get=FakeNet(), chat=None, **paths)
    again = pd.read_parquet(tmp_path / "series" / "cn_retail_tone_USDCNH.parquet")
    assert again.iloc[0]["known_at"] == known
    assert again.iloc[0]["tone_mean"] == row["tone_mean"]
    axis = json.loads((tmp_path / "axes" / "cn.json").read_text("utf-8"))
    assert "USDCNH.tone_mean" in axis["series"]
    dig = json.loads((tmp_path / "digest.json").read_text("utf-8"))["organs"][organ.SOURCE]
    assert dig["sources"] == {"guba": "LIVE", "xueqiu": "BLOCKED"}


def test_vaulted_pages_are_observations_at_their_own_fetch_time_and_harvested_once(
        tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    vault = paths["vault"]
    vault.mkdir(parents=True)
    head = {"url": "http://guba.eastmoney.com/list,waihui.html",
            "fetched_utc": "2026-09-03T16:14:36+00:00"}
    (vault / "abc.gz").write_bytes(gzip.compress(
        (json.dumps(head) + "\n" + PAGE).encode("utf-8")))
    (vault / "news.gz").write_bytes(gzip.compress(
        (json.dumps({"url": "http://guba.eastmoney.com/news,waihui,1.html",
                     "fetched_utc": "2026-09-03T16:00:00+00:00"}) + "\n<html/>").encode()))
    now = datetime(2026, 9, 5, tzinfo=UTC)
    rep = organ.run(now, fetch=False, chat=None, **paths)
    assert rep["vault"] == {"pages": 1, "new_posts": 8}
    assert rep["instruments"]["USDCNH"]["n_posts"] == 4
    rep = organ.run(now, fetch=False, chat=None, **paths)
    assert rep["vault"] == {"pages": 0, "new_posts": 0}
    obs = json.loads((tmp_path / "store" / "observations.json").read_text("utf-8"))
    assert obs == {"waihui": {"2026-09-03": 1}}


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    rep = organ.run(datetime(2026, 9, 4, tzinfo=UTC), get=FakeNet(), dry_run=True, **paths)
    assert rep["index_rows"] == 0 and not (tmp_path / "store").exists()
    assert not (tmp_path / "rep.json").exists()


# ---------------------------------------------------------------------------- the LLM column
def test_the_llm_reader_sees_sanitized_titles_and_never_raises() -> None:
    assert gt.sanitize("看多 https://x.cn/a $人民币(CNYOFFS)$ @某人 123456789") == "看多"
    seen: list[str] = []

    def chat(prompt: str, system: str) -> tuple[str, str | None]:
        seen.append(prompt)
        return json.dumps({"scores": [{"i": 0, "tone": 0.5}, {"i": 1, "tone": 9}]}), None

    posts = [_post("1", "看多 https://x.cn", SEEN, SEEN), _post("2", "抄底", SEEN, SEEN)]
    scores, st = gt.llm_tones(posts, "equity", chat)
    assert scores == {"1": 0.5, "2": 1.0} and st["state"] == "MEASURED"
    assert "https" not in seen[0]

    def boom(prompt: str, system: str) -> tuple[str, str | None]:
        raise RuntimeError("seat down")

    scores, st = gt.llm_tones(posts, "equity", boom)
    assert scores == {} and st["state"] == gt.UNMEASURED and st["errors"]
    assert gt.llm_tones(posts, "equity", None)[1]["state"] == gt.UNMEASURED


def test_an_llm_score_counts_only_if_made_before_the_day_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    def chat(prompt: str, system: str) -> tuple[str, str | None]:
        n = prompt.count("\n")
        return json.dumps({"scores": [{"i": i, "tone": -0.5} for i in range(n)]}), None

    organ.run(datetime(2026, 9, 3, 16, 0, tzinfo=UTC), get=FakeNet(), chat=chat, **paths)
    organ.run(datetime(2026, 9, 4, 2, 0, tzinfo=UTC), get=FakeNet(), chat=chat, **paths)
    frame = pd.read_parquet(tmp_path / "series" / "cn_retail_tone_USDCNH.parquet")
    row = frame[frame["day"] == "2026-09-03"].iloc[0]
    assert row["n_llm"] == 4 and row["tone_llm_mean"] == pytest.approx(-0.5)


def test_without_the_opt_in_the_llm_column_is_unmeasured(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_CN_TONE_LLM", raising=False)
    rep = organ.run(datetime(2026, 9, 4, tzinfo=UTC), get=FakeNet(), **_paths(tmp_path))
    assert rep["llm"]["state"] == gt.UNMEASURED


# --------------------------------------------------------------------------------- the wiring
def test_nlp_social_cells_ingest_runs_the_organ(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, Any] = {}

    def fake_run(**kw: Any) -> dict[str, Any]:
        called.update(kw)
        return {"index_rows": 3, "sources": {"guba": {"state": "LIVE"},
                                             "xueqiu": {"state": "BLOCKED"}},
                "vault": {"pages": 2}}

    import types

    def refuse(**kw: Any) -> dict[str, Any]:
        raise RuntimeError("not under test")             # the other two publishers stay out

    for name in ("nlp_event_factors", "blog_social_mining"):
        monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(run=refuse))
    monkeypatch.setattr(organ, "run", fake_run)
    monkeypatch.setitem(sys.modules, "cn_retail_tone", organ)
    out = nsc.ingest(fetch=False)
    assert out["blog_social"]["state"] == "FAILED"         # fenced: one failing costs no other
    assert called["fetch"] is False and called["budget_s"] <= 40.0
    assert out["cn_retail_tone"] == {"index_rows": 3, "vault_pages": 2,
                                     "sources": {"guba": "LIVE", "xueqiu": "BLOCKED"}}


def test_the_gain_grid_reads_the_series_and_the_cells_wait_for_history(tmp_path: Path) -> None:
    series = tmp_path / "series"
    series.mkdir()
    days = pd.date_range("2026-08-01", periods=20, freq="D")
    pd.DataFrame({"day": [d.date().isoformat() for d in days],
                  "available_time": [(d + pd.Timedelta(days=1)).isoformat() for d in days],
                  "tone_shock_signed": range(20), "volume_z": range(20)}
                 ).to_parquet(series / "cn_retail_tone_USDCNH.parquet", index=False)
    _indices, pairs, history = nsc.build_grid(series)
    assert ("cnrt:USDCNH.tone_shock_signed", "USDCNH") in pairs
    assert ("cnrt:USDCNH.volume_z", "USDCNH") in pairs
    ready, waiting = nsc.declared_cells(history, {"tests": []})
    cn = [c for c in waiting if c["cell_name"] == "cn_board_tone_reversal"]
    assert {c["symbol"] for c in cn} == set(nsc.CN_TONE_SYMBOLS)
    assert all(c["not_ready"] == "WAITING_FOR_HISTORY" for c in cn)
    assert all(c["params"]["source"] == f"cn_retail_tone_{c['symbol']}" for c in cn)
    assert not [c for c in ready if c["cell_name"] == "cn_board_tone_reversal"]


def test_the_store_is_gitignored_outside_the_compiled_tree() -> None:
    import subprocess
    rel = organ.STORE.relative_to(_ROOT).as_posix()
    assert rel.startswith("desks/mt5/data/text_store/") and "/intelligence/" not in rel
    got = subprocess.run(["git", "check-ignore", "-q", f"{rel}/posts.jsonl"], cwd=_ROOT,
                         check=False)
    assert got.returncode == 0

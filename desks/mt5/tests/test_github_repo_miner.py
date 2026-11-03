"""github_repo_miner: lists walked, repos read, rows donated to intelligence seats, deduped, and
a liveness verdict that reads RED on zero yield. No network: every call goes through a fake."""
from __future__ import annotations

import ast
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import github_repo_miner as gm  # noqa: E402
import pytest  # noqa: E402

API, RAW = gm.API, gm.RAW
NOW = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)

GOLD_README = ("# Gold breakout\n\nWe buy gold on the London breakout of the Asian range, "
               "holding for the day; the hourly rule is long only.\n")
FIRM_README = ("# All weather\n\nA risk parity book in the spirit of the all weather portfolio. "
               "We buy gold on the London breakout of the Asian range every day.\n")
LIST_README = ("# Awesome\n- [one](https://github.com/alice/gold-breakout) gold breakout\n"
               "- [topic](https://github.com/topics/trading)\n"
               "- [two](https://github.com/bob/fx-carry.git) carry\n")


@pytest.fixture(autouse=True)
def _anonymous(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reserve depends on whether a token is present; pin the anonymous case."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("QUANT_LEG_BUDGET_S", raising=False)


class Fake:
    """Routes URL prefixes to (status, body, headers); records every call."""

    def __init__(self, routes: dict[str, tuple[int | None, str]], core_left: int = 4000,
                 search_left: int = 25) -> None:
        self.routes, self.calls = routes, []
        self.core_left, self.search_left = core_left, search_left

    def __call__(self, url: str, accept: str = "") -> tuple[int | None, str, dict[str, str]]:
        self.calls.append(url)
        if url == f"{API}/rate_limit":
            return 200, json.dumps({"resources": {
                "core": {"remaining": self.core_left, "limit": 5000},
                "search": {"remaining": self.search_left}}}), {}
        for prefix, (status, body) in self.routes.items():
            if url.startswith(prefix):
                return status, body, {"X-RateLimit-Remaining": str(self.core_left)}
        return 404, "", {}


def _meta(full: str, lic: str | None, pushed: str = "2026-11-01T00:00:00Z") -> str:
    return json.dumps({"html_url": f"https://github.com/{full}", "pushed_at": pushed,
                       "license": {"spdx_id": lic} if lic else None, "stargazers_count": 42,
                       "default_branch": "main", "description": "gold strategy"})


def _seeds(tmp: Path, **extra: Any) -> Path:
    doc = {"policy": {"files_per_repo": 2, "rescan_after_h": 168}, "lists": [], "searches": [],
           "repos": [{"repo": "alice/gold-breakout", "lane": "repo", "disposition": "mine",
                      "batch": "t"},
                     {"repo": "carol/all-weather", "lane": "firm", "firm": "Bridgewater",
                      "disposition": "mine", "batch": "t"},
                     {"name": "QuantumultX", "repo": None, "disposition": "not_relevant"}]}
    doc.update(extra)
    p = tmp / "seeds.json"
    p.write_text(json.dumps(doc), "utf-8")
    return p


def _routes(pushed: str = "2026-11-01T00:00:00Z") -> dict[str, tuple[int | None, str]]:
    return {
        f"{API}/repos/alice/gold-breakout/git/trees": (200, json.dumps({"tree": []})),
        f"{API}/repos/alice/gold-breakout": (200, _meta("alice/gold-breakout", "MIT", pushed)),
        f"{RAW}/alice/gold-breakout/main/README.md": (200, GOLD_README),
        f"{API}/repos/carol/all-weather/git/trees": (200, json.dumps({"tree": []})),
        f"{API}/repos/carol/all-weather": (200, _meta("carol/all-weather", "AGPL-3.0", pushed)),
        f"{RAW}/carol/all-weather/main/README.md": (200, FIRM_README),
    }


def _run(tmp: Path, fetch: Fake, seeds: Path, now: datetime = NOW) -> dict[str, Any]:
    return gm.run(budget_s=60, fetch=fetch, seeds=seeds, state_path=tmp / "state.json",
                  intel_dir=tmp / "intel", report_path=tmp / "report.json", now=now)


def _donated(tmp: Path, seat: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for f in sorted((tmp / "intel" / seat).glob("discoveries_github_*.json")):
        rows += json.loads(f.read_text("utf-8"))["discoveries"]
    return rows


def test_seeds_carry_the_whole_twenty_repo_batch() -> None:
    reg = json.loads(gm.SEEDS.read_text("utf-8"))
    batch = [s for s in reg["repos"] if s.get("batch") == "elitequant_20_2026-09-30"]
    assert len(batch) == 20
    disp = {str(s.get("repo") or s.get("name")): s["disposition"] for s in batch}
    assert disp["QuantumultX"] == "not_relevant"
    assert disp["AI-Efficiency/Awesome-Model-Quantization"] == "method_only"
    assert {s["repo"] for s in batch if s.get("lane") == "firm"} == {
        "yli188/WorldQuant_alpha101_code", "IdealAuror/all-weather-portfolio"}
    assert any(s["repo"] == "EliteQuant/EliteQuant" for s in reg["lists"])
    assert all(s.get("firm") for s in reg["searches"] if s.get("lane") == "firm")


def test_repo_links_drop_site_pages_and_self() -> None:
    links = gm.repo_links(LIST_README + "https://github.com/me/awesome", "me/awesome")
    assert links == ["alice/gold-breakout", "bob/fx-carry"]


def test_a_pass_donates_mapped_rows_to_each_lane_seat(tmp_path: Path) -> None:
    fake = Fake(_routes())
    doc = _run(tmp_path, fake, _seeds(tmp_path))
    repo_rows = _donated(tmp_path, "github_repos")
    firm_rows = _donated(tmp_path, "firm_mining")
    assert repo_rows and firm_rows
    r = repo_rows[0]
    assert r["kind"] == "hypothesis" and r["family"] == "session_range_breakout"
    assert "XAUUSD" in r["symbols"] and r["source"] == "github_repos"
    assert r["quote"].startswith("We buy gold")              # MIT: the claim is kept verbatim
    f = firm_rows[0]
    assert f["firm"] == "Bridgewater" and f["source"] == "firm_mining"
    assert "quote" not in f and "text" not in f               # AGPL: our description only
    assert "We buy gold" not in json.dumps(f)
    assert doc["liveness"]["github_repos"]["verdict"] == "GREEN"
    assert doc["liveness"]["firm_mining"]["verdict"] == "GREEN"
    assert not any("QuantumultX" in u for u in fake.calls)   # recorded, never fetched
    assert doc["per_repo"]["QuantumultX"]["status"] == "NOT_RELEVANT"


def test_unchanged_repos_are_skipped_and_reread_rows_deduped(tmp_path: Path) -> None:
    seeds = _seeds(tmp_path, policy={"rescan_after_h": 0})
    _run(tmp_path, Fake(_routes()), seeds)
    n_files = len(list((tmp_path / "intel" / "github_repos").glob("*.json")))
    fake = Fake(_routes())
    doc = _run(tmp_path, fake, seeds, NOW + timedelta(hours=1))
    assert doc["per_repo"]["alice/gold-breakout"]["status"].startswith("UNCHANGED")
    assert not any(u.startswith(RAW) for u in fake.calls)    # same pushed_at: no README read
    doc = _run(tmp_path, Fake(_routes("2026-11-02T00:00:00Z")), seeds, NOW + timedelta(hours=2))
    assert doc["pass"]["duplicates_dropped"] >= 2 and doc["pass"]["rows_total"] == 0
    assert len(list((tmp_path / "intel" / "github_repos").glob("*.json"))) == n_files


def test_zero_yield_while_online_is_red_and_check_fails(tmp_path: Path) -> None:
    seeds = _seeds(tmp_path, policy={"rescan_after_h": 0})
    _run(tmp_path, Fake(_routes()), seeds)
    later = NOW + timedelta(hours=80)                        # the donating pass left the window
    doc = _run(tmp_path, Fake(_routes()), seeds, later)
    assert doc["pass"]["online"] and doc["pass"]["rows_total"] == 0
    assert doc["liveness"]["github_repos"]["verdict"] == "RED"
    assert doc["verdict"] == "RED"
    code, line = gm.check(tmp_path / "report.json", now=later)
    assert code == 1 and "RED" in line


def test_a_pass_the_quota_stopped_is_unmeasured_never_red(tmp_path: Path) -> None:
    doc = _run(tmp_path, Fake(_routes(), core_left=3, search_left=0), _seeds(tmp_path))
    assert not doc["pass"]["online"]
    assert {v["verdict"] for v in doc["liveness"].values()} == {gm.UNMEASURED}
    assert doc["pass"]["stopped_by"]


def test_metadata_refused_falls_back_to_raw_readme_without_licence(tmp_path: Path) -> None:
    routes = _routes()
    routes[f"{API}/repos/alice/gold-breakout"] = (403, "")
    routes[f"{RAW}/alice/gold-breakout/HEAD/README.md"] = (200, GOLD_README)
    _run(tmp_path, Fake(routes), _seeds(tmp_path))
    rows = _donated(tmp_path, "github_repos")
    assert rows and rows[0]["license"] == "UNKNOWN" and "quote" not in rows[0]


def test_lists_queue_their_links_and_searches_feed_the_firm_lane(tmp_path: Path) -> None:
    routes = _routes()
    routes[f"{API}/repos/me/awesome-gold"] = (200, _meta("me/awesome-gold", "CC0-1.0"))
    routes[f"{RAW}/me/awesome-gold/main/README.md"] = (200, LIST_README)
    routes[f"{API}/search/repositories"] = (200, json.dumps({"items": [
        {"full_name": "dave/tsmom", "pushed_at": "2026-10-30T00:00:00Z"},
        {"full_name": "eve/binance-funding-bot", "description": "binance funding arbitrage"}]}))
    seeds = _seeds(tmp_path, lists=[{"repo": "me/awesome-gold"}],
                   searches=[{"q": "time series momentum", "lane": "firm", "firm": "AQR"}])
    doc = _run(tmp_path, Fake(routes), seeds)
    st = json.loads((tmp_path / "state.json").read_text("utf-8"))
    walked = set(st["repos"]) | {q["repo"] for q in st["queue"]}
    assert {"bob/fx-carry", "dave/tsmom"} <= walked
    assert "eve/binance-funding-bot" not in walked           # crypto-exchange venue fenced
    assert st["search_cursor"]["time series momentum"] == "2026-10-30"
    assert doc["pass"]["drops"].get("crypto_exchange_repo") == 1


def test_check_reads_absent_as_unmeasured_and_old_as_red(tmp_path: Path) -> None:
    assert gm.check(tmp_path / "nope.json")[0] == 2
    _run(tmp_path, Fake(_routes()), _seeds(tmp_path))
    assert gm.check(tmp_path / "report.json", now=NOW)[0] == 0
    assert gm.check(tmp_path / "report.json", now=NOW + timedelta(hours=7))[0] == 1


def test_red_raises_the_issue_board_alarm_and_green_clears_it(tmp_path: Path) -> None:
    import issue_board
    assert "GITHUB_MINER_ALARM.txt" in {a[0] for a in issue_board.ALARMS}
    alarm = tmp_path / "data" / "GITHUB_MINER_ALARM.txt"
    gm.raise_alarm(1, "RED: firm_mining: nothing donated", alarm)
    assert alarm.read_text("utf-8").startswith("RED")
    gm.raise_alarm(0, "OK", alarm)
    assert not alarm.exists()


def test_the_legs_are_on_the_clock_with_a_layer_budget_and_department() -> None:
    from libs.research import layers
    assert layers.LEG_LAYER["github_repo_miner"] == "information"
    assert layers.LEG_LAYER["github_miner_alive"] == "meta"
    cycle = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("github_repo_miner", github_repo_miner)' in cycle
    assert '_costed("github_miner_alive", github_miner_alive)' in cycle
    import hourly_cycle as hc
    assert hc.LEG_BUDGET_SEC["github_repo_miner"] > 300
    assert hc.LEG_DEPARTMENT["github_repo_miner"] == "intel"
    assert "github_miner_alive" in hc.CORE_LEGS
    assert hc.VERDICT_EXITS["github_miner_alive"] == (2,)


def test_the_miner_never_executes_what_it_reads() -> None:
    tree = ast.parse(Path(gm.__file__).read_text("utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"exec", "eval", "compile", "__import__"}
        assert not (isinstance(node, ast.Import) and any(a.name == "subprocess"
                                                         for a in node.names))


def test_donated_rows_compile_through_the_ordinary_door(tmp_path: Path) -> None:
    import miner_candidate_compiler as mcc
    _run(tmp_path, Fake(_routes()), _seeds(tmp_path))
    uni = mcc.known_symbols() | {"XAUUSD"}
    for seat in ("github_repos", "firm_mining"):
        row = next(r for r in _donated(tmp_path, seat) if r.get("family"))
        cands, disp = mcc.compile_row(seat, row, uni)
        assert disp == "STRUCTURED_HYPOTHESIS" and cands

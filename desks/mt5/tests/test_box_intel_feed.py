"""The intel feed, produced on the box (2026-11-03): hel8 stopped shipping it at 02:50Z.

Pinned here:
  * the leg runs seed_miners, then hourly_discovery with what is left, inside its budget, and
    gates itself to an hourly cadence;
  * both children carry the rails (QUANT_BOX_RAILS=1), the paid seat off, BELOW_NORMAL on Windows
    and no affinity; the seed child installs the rails before any miner is imported;
  * hourly_discovery never runs an organ hourly_cycle already clocks (no organ gets two writers);
  * the leg is an `intel` department leg with a cap above its own floor and at most 40 minutes;
  * the artifact contracts (ops/organ_contract.py) watch
    the two artifacts the producers write;
  * hourly_discovery's organ child installs the rails when asked, and refuses to run when they
    cannot install;
  * (the intel_ship_adopt.ps1 frozen-ship skip ships separately: it is a money-path script),
    logs why, and records the adopted sha only after a real adoption.
Nothing here touches the network or the real desk data.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "side_channels"), str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import box_intel_feed as feed  # noqa: E402
import hourly_discovery as hd  # noqa: E402


@pytest.fixture
def iso(tmp_path, monkeypatch):
    monkeypatch.setattr(feed, "STATE", tmp_path / "data" / "box_intel_feed_state.json")
    monkeypatch.setattr(feed, "REPORT", tmp_path / "reports" / "BOX_INTEL_FEED.json")
    monkeypatch.setattr(feed, "BASE", tmp_path)
    monkeypatch.setattr(feed, "LEASE", tmp_path / "data" / "locks" / "box_intel_feed.lease")
    return tmp_path


class _Runner:
    def __init__(self, seed=(0, 'INTEL_FEED_RESULT {"status": "OK", "sources": 3, "rows": 7}'),
                 disc=(0, "HOURLY DISCOVERY ok=2")):
        self.calls: list[tuple[list[str], float, dict[str, str]]] = []
        self.seed, self.disc = seed, disc

    def __call__(self, cmd, timeout_s, env):
        self.calls.append((cmd, timeout_s, env))
        return self.seed if "--child" in cmd else self.disc


def test_a_pass_runs_seed_then_discovery_inside_its_budget(iso) -> None:
    r = _Runner()
    rep = feed.run_pass(2040.0, runner=r)
    assert rep["status"] == "OK"
    assert [("--child" in c) for c, _t, _e in r.calls] == [True, False]
    seed_cmd, seed_bound, _ = r.calls[0]
    assert seed_cmd[-2:] == ["--child", "seed"] and seed_bound == feed.SEED_BOUND_S
    disc_cmd, disc_bound, _ = r.calls[1]
    assert str(feed.DISCOVERY) in disc_cmd
    budget = float(disc_cmd[disc_cmd.index("--budget-s") + 1])
    # the discovery child's kill bound plus the seed bound never pass the leg's own budget
    assert budget + feed.DISCOVERY_GRACE_S + feed.WRITE_MARGIN_S == pytest.approx(disc_bound, abs=1)
    assert disc_bound <= 2040.0
    assert rep["seed_miners"]["rows"] == 7 and rep["seed_miners"]["sources"] == 3
    on_disk = json.loads(feed.REPORT.read_text())
    assert on_disk["status"] == "OK" and on_disk["rails"]["user_agent"].startswith(
        "QuantResearchCrawler/")


def test_every_child_carries_the_rails_and_never_the_paid_seat(iso, monkeypatch) -> None:
    r = _Runner()
    feed.run_pass(2040.0, runner=r)
    for _cmd, _t, env in r.calls:
        assert env["QUANT_BOX_RAILS"] == "1"
        assert env["QUANT_PROPOSER_SEAT"] == "0"
        assert env["QUANT_BOX_RAILS_LOG"]


def test_children_spawn_below_normal_on_windows_and_never_set_an_affinity(monkeypatch) -> None:
    monkeypatch.setattr(feed.sys, "platform", "win32")
    assert feed.popen_kwargs() == {"creationflags": 0x00004000}
    monkeypatch.setattr(feed.sys, "platform", "linux")
    assert feed.popen_kwargs() == {}
    src = (DESK / "side_channels" / "box_intel_feed.py").read_text(encoding="utf-8")
    assert "cpu_affinity(" not in src and "SetProcessAffinity" not in src
    assert "IDLE_PRIORITY_CLASS" not in src  # IDLE would drag the judge below the miners


def test_the_leg_is_hourly_and_a_pass_inside_the_cadence_does_nothing(iso) -> None:
    r = _Runner()
    feed.run_pass(2040.0, runner=r)
    n = len(r.calls)
    again = feed.run_pass(2040.0, runner=r)
    assert again["status"] == "NOT_DUE" and len(r.calls) == n
    later = time.time() + feed.MIN_INTERVAL_S + 1
    assert feed.due(json.loads(feed.STATE.read_text()), now=later)[0]
    assert feed.run_pass(2040.0, runner=r, force=True)["status"] == "OK"


def test_a_future_dated_last_start_is_a_clock_defect_not_freshness() -> None:
    future = datetime.fromtimestamp(time.time() + 7200, UTC).isoformat()
    ok, why = feed.due({"last_started_at": future})
    assert ok and "future" in why


def test_a_slow_seed_defers_discovery_rather_than_overrunning(iso, monkeypatch) -> None:
    clock = [1000.0]
    monkeypatch.setattr(feed.time, "monotonic", lambda: clock[0])

    def runner(cmd, timeout_s, env):
        clock[0] += 1900.0  # the seed sweep ate the hour
        return 0, 'INTEL_FEED_RESULT {"status": "OK", "sources": 1, "rows": 1}'

    rep = feed.run_pass(2040.0, runner=runner)
    assert rep["discovery"]["status"] == "DEFERRED_NO_TIME"
    assert rep["status"] == "PARTIAL"


def test_killed_failed_and_memory_deferred_children_are_named(iso) -> None:
    rep = feed.run_pass(2040.0, runner=_Runner(seed=(None, ""), disc=(75, "")))
    assert rep["seed_miners"]["status"] == "KILLED_AT_BOUND"
    assert rep["discovery"]["status"] == "DEFERRED_MEMORY"
    assert rep["status"] == "FAILED"
    rep = feed.run_pass(2040.0, runner=_Runner(seed=(2, "Traceback: boom"), disc=(1, "")),
                        force=True)
    assert rep["seed_miners"]["status"] == "FAILED" and "boom" in rep["seed_miners"]["tail"]
    # hourly_discovery exits 1 when an organ failed: the pass still ran and wrote its report
    assert rep["discovery"]["status"] == "OK" and rep["status"] == "PARTIAL"


def test_discovery_never_runs_an_organ_another_box_leg_already_clocks() -> None:
    owned, basis = feed.box_owned_organs()
    assert "hourly_cycle.py" in basis and "daily_cycle.py" in basis
    organs, excluded, _ = feed.discovery_organs()
    assert set(organs).isdisjoint(owned)
    assert set(organs) | set(excluded) == set(hd.ORGANS)
    for organ in ("world_crawler", "deep_forest_miner", "alpha_evolution", "acquire_datasets"):
        assert organ in excluded
    # the fallback list covers every organ the live rosters exclude
    assert set(excluded) <= feed.BOX_OWNED_FALLBACK
    assert organs, "nothing would run"


def _daily_roster() -> set[str]:
    """Every module daily_cycle runs, read from its own source independently of the feed's
    matcher: the `__import__` rosters (_proposers, _world_miners) and every step's `import X`."""
    import ast
    tree = ast.parse((DESK / "research" / "daily_cycle.py").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[-1] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names |= {a.name for a in node.names} | {node.module.split(".")[-1]}
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    return names


def test_every_organ_daily_cycle_runs_is_excluded() -> None:
    """Audit HOLD on 84e1e474b: fetch_futures_curves ran here AND in daily_cycle's
    `futures_curves` step -- two non-atomic writers of data/futures_curves/*.parquet and
    reports/futures_curve_coverage.json, and an hourly UNMEASURED over the daily MEASURED."""
    daily = _daily_roster() & set(hd.ORGANS)
    assert "fetch_futures_curves" in daily and "plumbing_miner" in daily and "repo_miner" in daily
    organs, excluded, _ = feed.discovery_organs()
    both = sorted(daily - set(excluded))
    assert not both, f"run by daily_cycle AND the feed: {both}"
    assert not daily & set(organs)


def test_an_unreadable_roster_fails_closed_to_the_pinned_list(tmp_path) -> None:
    owned, basis = feed.box_owned_organs(list(hd.ORGANS), (tmp_path / "absent.py",))
    assert owned == feed.BOX_OWNED_FALLBACK and "fallback" in basis
    organs, _, _ = feed.discovery_organs((tmp_path / "a.py", tmp_path / "b.py"))
    assert set(organs).isdisjoint(feed.BOX_OWNED_FALLBACK)


def test_two_concurrent_passes_cannot_both_start_the_feed(iso) -> None:
    held, _ = feed.take_lease()
    assert held
    rep = feed.run_pass(2040.0, runner=_Runner())
    assert rep["status"] == "LEASE_HELD"
    assert not feed.STATE.exists(), "a pass without the lease touched the clock"
    feed.release_lease()
    assert feed.run_pass(2040.0, runner=_Runner())["status"] == "OK"
    assert not feed.LEASE.exists(), "the lease outlived its pass"


def test_a_stale_lease_from_a_killed_pass_is_taken_over(iso) -> None:
    import os
    feed.LEASE.parent.mkdir(parents=True, exist_ok=True)
    feed.LEASE.write_text("{}")
    old = time.time() - feed.LEASE_STALE_S - 10
    os.utime(feed.LEASE, (old, old))
    rep = feed.run_pass(2040.0, runner=_Runner())
    assert rep["status"] == "OK" and rep["lease"].startswith("took over a stale lease")


def test_rail_refusals_are_named_by_host_with_a_missed_growth_line(iso, monkeypatch) -> None:
    import box_rails

    def runner(cmd, timeout_s, env):
        with open(env["QUANT_BOX_RAILS_LOG"], "a", encoding="utf-8") as fh:
            for u in ("https://api.github.com/repos/a/b", "https://api.github.com/repos/c/d"):
                fh.write(json.dumps({"url": u, "why": "robots.txt disallows user-agent '*'",
                                     "pid": 1}) + "\n")
        return (0, 'INTEL_FEED_RESULT {"status": "OK", "sources": 1, "rows": 1}')

    rep = feed.run_pass(2040.0, runner=runner)
    assert rep["refused_sources"]["api.github.com"]["n"] == 4  # two children, two rows each
    assert len(rep["missed_growth"]) == 1 and "api.github.com" in rep["missed_growth"][0]
    assert "dark on the box by policy" in rep["missed_growth"][0]
    assert rep["rails"]["user_agent"] == box_rails.USER_AGENT


def test_the_seed_child_installs_the_rails_before_any_miner(monkeypatch, capsys) -> None:
    import box_rails
    order: list[str] = []
    monkeypatch.setattr(box_rails, "install", lambda *a, **k: order.append("rails"))
    fake = type(sys)("seed_miners")
    fake.run_and_save = lambda: order.append("seed") or {"a": {"count": 2}, "b": {"count": 3}}
    monkeypatch.setitem(sys.modules, "seed_miners", fake)
    assert feed.main(["--child", "seed"]) == 0
    assert order == ["rails", "seed"]
    out = capsys.readouterr().out
    assert json.loads(out.split(feed.RESULT_PREFIX, 1)[1])["rows"] == 5


def test_rails_that_cannot_install_mean_the_seed_fleet_does_not_run(monkeypatch, capsys) -> None:
    import box_rails

    def boom(*a, **k):
        raise RuntimeError("wall list unreadable")

    monkeypatch.setattr(box_rails, "install", boom)
    fake = type(sys)("seed_miners")
    fake.run_and_save = lambda: pytest.fail("a miner ran without the rails")
    monkeypatch.setitem(sys.modules, "seed_miners", fake)
    assert feed.main(["--child", "seed"]) == 1
    assert "nothing fetched" in capsys.readouterr().out


def test_the_box_seed_run_never_runs_a_source_that_retries_around_a_403(
        monkeypatch, capsys) -> None:
    """regional_survivors retries a 403 on sibling hosts with a borrowed Referer: off the box."""
    import box_rails

    monkeypatch.setattr(box_rails, "install", lambda *a, **k: None)
    fake = type(sys)("seed_miners")
    fake.MINERS = {"regional_survivors": lambda: pytest.fail("ran on the box"),
                   "arxiv_qfin": lambda: []}
    seen: list[list[str]] = []
    fake.run_and_save = lambda: seen.append(sorted(fake.MINERS)) or {"arxiv_qfin": {"count": 1}}
    monkeypatch.setitem(sys.modules, "seed_miners", fake)
    assert feed.main(["--child", "seed"]) == 0
    assert seen == [["arxiv_qfin"]]
    out = json.loads(capsys.readouterr().out.split(feed.RESULT_PREFIX, 1)[1])
    assert out["excluded_on_box"] == ["regional_survivors"]


def test_the_box_exclusion_names_a_real_seed_source() -> None:
    """A renamed source would silently slip past the exclusion; pin the name to the roster."""
    src = (feed.HERE / "seed_miners.py").read_text(encoding="utf-8")
    for name in feed.BOX_EXCLUDED_SEEDS:
        assert re.search(rf'"{name}":\s*mine_', src), name


# ---------------------------------------------------------------- hourly_discovery's organ child
def test_an_organ_child_installs_the_rails_when_the_feed_asks(monkeypatch) -> None:
    import box_rails
    calls: list[str] = []
    monkeypatch.setattr(box_rails, "install", lambda *a, **k: calls.append("rails"))
    monkeypatch.delenv(hd.RAILS_ENV, raising=False)
    assert hd._install_rails() == "" and calls == []          # the VPS path: untouched
    monkeypatch.setenv(hd.RAILS_ENV, "1")
    assert hd._install_rails() == "" and calls == ["rails"]


def test_an_organ_child_refuses_to_run_without_its_rails(monkeypatch, capsys) -> None:
    import box_rails

    def boom(*a, **k):
        raise RuntimeError("no walls")

    monkeypatch.setattr(box_rails, "install", boom)
    monkeypatch.setenv(hd.RAILS_ENV, "1")
    monkeypatch.setattr(hd, "run_organ", lambda *a: pytest.fail("organ ran without rails"))
    monkeypatch.setattr(sys, "argv", ["hourly_discovery.py", "--organ", "repo_miner",
                                      "--budget-s", "60"])
    assert hd.main() == 3
    assert "nothing fetched" in capsys.readouterr().out


def test_the_discovery_pass_kills_the_whole_organ_tree() -> None:
    src = (DESK / "research" / "hourly_discovery.py").read_text(encoding="utf-8")
    assert "from libs.ops.proctree import run" in src
    assert "subprocess.run(cmd, capture_output" not in src


# ------------------------------------------------------------------------- the cycle's wiring
def test_the_leg_is_an_intel_department_leg_with_a_cap_above_its_floor() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert re.search(r'_costed\("intel_feed", lambda: _producer\(\s*"intel_feed", '
                     r'"side_channels/box_intel_feed.py", "--budget-s", "2040"\)\)', src)
    assert '"intel_feed": ifd' in src
    intel = src[src.index('**dict.fromkeys(("world_crawler", "deep_forest"'):]
    intel = intel[:intel.index('"intel"),')]
    assert '"intel_feed"' in intel
    cap = int(re.search(r'"intel_feed": (\d[\d_]*),', src).group(1).replace("_", ""))
    own = 2040
    assert own + max(60, 0.15 * own) <= cap <= 40 * 60
    assert own == feed.BUDGET_S
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["intel_feed"] == "information"


def test_the_contracts_watch_the_feed_s_own_artifacts(monkeypatch) -> None:
    # ops/ goes on the path for this test only: left there, a later bare
    # `import release_authority` resolves to ops/release_authority.py instead of
    # desks/mt5/research/release_authority.py (test_blueprint_b_rows broke on it).
    monkeypatch.syspath_prepend(str(ROOT / "ops"))
    import organ_contract as oc
    rows = {k: v for k, v in oc.CONTRACTS.items() if k.startswith("MT5-Dept-Intel (intel feed")}
    arts = {v[0] for v in rows.values()}
    assert arts == {"desks/mt5/reports/HOURLY_DISCOVERY.json",
                    "desks/mt5/data/intelligence/seed_miners_state.json"}
    assert all(v[1] == 180 for v in rows.values())
    # the producers write exactly these
    assert hd.REPORT.parts[-2:] == ("reports", "HOURLY_DISCOVERY.json")
    import seed_miners
    assert seed_miners.STATE.name == "seed_miners_state.json"
    assert seed_miners.STATE.parent.name == "intelligence"


# --------------------------------------------------- the cycle plan: dept:intel and nowhere else
def test_the_feed_runs_only_on_the_intel_department_s_plan() -> None:
    """Audit HOLD on 84e1e474b: under the default `all` plan the 40-minute leg ran inline ahead
    of release_identity, burn_in and fill_recorder."""
    import hourly_cycle as hc
    assert "intel_feed" in hc.DEPT_ONLY_LEGS
    assert hc.in_plan("intel_feed", "dept:intel")
    for plan in ("all", "heavy", "core", "dept:discovery", "dept:rest", "dept:data"):
        assert not hc.in_plan("intel_feed", plan), plan
    # nothing else changed: the money legs still run under `all`
    for leg in ("release_identity", "burn_in"):
        assert hc.in_plan(leg, "all")


# ----------------------------------------------- seed_miners: a rail-refused probe is UNMEASURED
def test_a_rail_refused_wall_probe_is_unmeasured_and_does_not_advance_its_clock(
        tmp_path, monkeypatch) -> None:
    import box_rails
    import seed_miners as sm
    monkeypatch.setattr(sm, "INTEL", tmp_path)
    monkeypatch.setattr(sm, "STATE", tmp_path / "seed_miners_state.json")
    name = next(iter(sm.SOURCE_WALLS))
    monkeypatch.setattr(sm, "MINERS", {name: lambda: pytest.fail("a walled miner ran")})
    monkeypatch.setitem(sys.modules, "cohort_and_identity",
                        type(sys)("cohort_and_identity"))
    sys.modules["cohort_and_identity"].run_and_save = lambda: None
    monkeypatch.setenv("QUANT_PROPOSER_SEAT", "0")

    def refuse(*a, **k):
        raise box_rails.RailRefusal("box rails refused: walled on the VPS")

    monkeypatch.setattr(sm, "fetch", refuse)
    res = sm.run_and_save()
    st = json.loads(sm.STATE.read_text())
    assert name not in (st.get("wall_probes") or {}), "a probe that never happened moved the clock"
    row = res[name]["discoveries"][0]
    assert row["probe"] == "UNMEASURED" and "UNMEASURED" in row["title"]
    # a real, measured "still blocked" still advances it
    monkeypatch.setattr(sm, "fetch", lambda *a, **k: (_ for _ in ()).throw(OSError("403")))
    sm.run_and_save()
    assert name in json.loads(sm.STATE.read_text())["wall_probes"]


def test_off_the_box_a_failed_probe_is_never_mistaken_for_a_rail_refusal(monkeypatch) -> None:
    import seed_miners as sm
    monkeypatch.delitem(sys.modules, "box_rails", raising=False)
    assert not sm._rail_refused(OSError("x"))


# ------------------------------------------- repo_miner: dark by policy is named, never silence
def test_repo_miner_names_a_rail_refused_source_as_missed_growth(tmp_path, monkeypatch) -> None:
    import box_rails
    import repo_miner as rm
    monkeypatch.setattr(rm, "_watchlist", lambda: {"repos": ["a/b"]})
    monkeypatch.setattr(rm, "CACHE", tmp_path / "cache")

    def refuse(*a, **k):
        raise box_rails.RailRefusal("robots.txt disallows user-agent '*'")

    monkeypatch.setattr(rm, "_get", refuse)
    doc = rm.run(fetch=True, write=False)
    assert doc["refused_sources"] == [{"repo": "a/b", "host": "github",
                                       "why": "robots.txt disallows user-agent '*'"}]
    assert doc["unreachable"] == [] and len(doc["missed_growth"]) == 1
    assert "github" in doc["missed_growth"][0]
    # an ordinary network failure is still `unreachable`, with no missed_growth line
    monkeypatch.setattr(rm, "_get", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    doc = rm.run(fetch=True, write=False)
    assert doc["unreachable"] == ["a/b"] and doc["missed_growth"] == []


# ------------------------------------ the rails cover every HTTP route the feed's files can take
BANNED_CLIENTS = ("http.client", "httpx", "aiohttp", "pycurl", "urllib3", "curl_cffi",
                  "requests_html", "httplib2")


def _closure(start: list[Path]) -> dict[Path, set[str]]:
    import ast
    roots = (DESK / "side_channels", DESK / "research", DESK, ROOT)

    def resolve(mod: str) -> Path | None:
        for r in roots:
            p = r.joinpath(*mod.split(".")).with_suffix(".py")
            if p.exists():
                return p
        return None

    seen: dict[Path, set[str]] = {}
    todo = list(start)
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        mods: set[str] = set()
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                mods |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                mods.add(n.module)
        seen[f] = mods
        todo += [p for m in mods if (p := resolve(m)) is not None and p not in seen]
    return seen


def test_no_file_the_feed_runs_imports_an_http_client_the_rails_do_not_patch() -> None:
    """box_rails patches `requests` and `urllib.request`. A seed or discovery-organ file -- or
    anything local they import -- that reaches the wire another way would fetch with no honest
    UA and no robots.txt check, so it fails here."""
    organs, _, _ = feed.discovery_organs()
    start = [DESK / "side_channels" / "seed_miners.py",
             *[DESK / "research" / f"{o}.py" for o in organs]]
    assert all(p.exists() for p in start)
    closure = _closure(start)
    assert len(closure) > len(start), "the closure walk found nothing: the pin would prove nothing"
    bad = {str(f.relative_to(ROOT)): sorted(m for m in mods if any(
        m == b or m.startswith(b + ".") for b in BANNED_CLIENTS))
        for f, mods in closure.items()}
    assert not {k: v for k, v in bad.items() if v}
    shell = re.compile(r"""["'](curl|wget)(\.exe)?["']""")
    assert not [str(f.relative_to(ROOT)) for f in closure
                if shell.search(f.read_text(encoding="utf-8"))]


def test_the_rails_docstring_no_longer_claims_seed_miners_spawns_run_all_miners() -> None:
    import box_rails
    assert "never calls `run_all_miners`" in (box_rails.__doc__ or "")
    src = (DESK / "side_channels" / "seed_miners.py").read_text(encoding="utf-8")
    assert "run_all_miners" not in src


# --------------------------------------------- the lease takeover and release (audit of ebdc349e9)
def _stale(p: Path, stale_s: float) -> None:
    import os
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"pid": 1, "lease_id": "dead"}))
    old = time.time() - stale_s - 10
    os.utime(p, (old, old))


def test_a_pass_that_loses_the_stale_rename_never_deletes_the_winner_s_lease(
        iso, monkeypatch) -> None:
    """A and B both see the lease stale. A renames it and creates its own. B's rename then
    targets A's FRESH lease: B must put it back and stand down, not delete it."""
    import os
    _stale(feed.LEASE, feed.LEASE_STALE_S)
    real_rename = os.rename
    seen: dict[str, bool] = {}

    def racing_rename(src, dst):
        if not seen:
            seen["a"] = True
            assert feed.take_lease()[0]  # A wins the race first, inside B's window
        return real_rename(src, dst)

    monkeypatch.setattr(feed.os, "rename", racing_rename)
    held, why = feed.take_lease()          # B
    monkeypatch.setattr(feed.os, "rename", real_rename)
    a_token = json.loads(feed.LEASE.read_text())["lease_id"]
    assert not held and "took over the stale lease first" in why
    assert feed.LEASE.exists(), "B deleted A's fresh lease"
    assert a_token == feed._TOKENS[str(feed.LEASE)]
    assert not [p for p in feed.LEASE.parent.iterdir() if ".stale." in p.name], "tombstone left"


def test_a_rename_lost_outright_does_not_create_over_the_winner(iso, monkeypatch) -> None:
    import os
    _stale(feed.LEASE, feed.LEASE_STALE_S)

    def lost(src, dst):
        os.unlink(src)            # the winner renamed it away...
        feed.LEASE.write_text(json.dumps({"lease_id": "winner"}))  # ...and created its own
        raise FileNotFoundError(src)

    monkeypatch.setattr(feed.os, "rename", lost)
    held, why = feed.take_lease()
    assert not held and "holds the lease" in why
    assert json.loads(feed.LEASE.read_text())["lease_id"] == "winner"


def test_release_unlinks_only_a_lease_holding_our_token(iso) -> None:
    assert feed.take_lease()[0]
    # our lease went stale and another pass took it over: our finally must leave theirs alone
    feed.LEASE.write_text(json.dumps({"pid": 999, "lease_id": "theirs"}))
    assert feed.release_lease() is False
    assert json.loads(feed.LEASE.read_text())["lease_id"] == "theirs"
    feed.LEASE.unlink()
    assert feed.take_lease()[0]
    assert feed.release_lease() is True and not feed.LEASE.exists()
    # never taken by this process: nothing is touched
    feed.LEASE.write_text(json.dumps({"lease_id": "someone"}))
    assert feed.release_lease() is False and feed.LEASE.exists()

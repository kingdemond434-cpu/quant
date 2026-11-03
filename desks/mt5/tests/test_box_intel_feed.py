"""The intel feed, produced on the box (2026-11-03): hel8 stopped shipping it at 02:50Z.

Pinned here:
  * the leg runs seed_miners, then hourly_discovery with what is left, inside its budget, and
    gates itself to an hourly cadence;
  * both children carry the rails (QUANT_BOX_RAILS=1), the paid seat off, BELOW_NORMAL on Windows
    and no affinity; the seed child installs the rails before any miner is imported;
  * hourly_discovery never runs an organ hourly_cycle already clocks (no organ gets two writers);
  * the leg is an `intel` department leg with a cap above its own floor and at most 40 minutes;
  * the artifact contracts and the heartbeat watch the two artifacts the producers write;
  * hourly_discovery's organ child installs the rails when asked, and refuses to run when they
    cannot install;
  * intel_ship_adopt.ps1 skips a frozen (>6 h) or unchanged ship ref before taking any lock,
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
    assert "_producer calls" in basis
    organs, excluded, _ = feed.discovery_organs()
    assert set(organs).isdisjoint(owned)
    assert set(organs) | set(excluded) == set(hd.ORGANS)
    # the ones the box already runs hourly, by name
    for organ in ("world_crawler", "deep_forest_miner", "alpha_evolution", "acquire_datasets"):
        assert organ in excluded
    # the fallback list covers every organ the live source excludes
    assert set(excluded) <= feed.BOX_OWNED_FALLBACK
    assert "seed_miners" not in organs and organs, "nothing would run"


def test_an_unreadable_cycle_falls_back_to_the_pinned_list(tmp_path) -> None:
    owned, basis = feed.box_owned_organs(tmp_path / "absent.py")
    assert owned == feed.BOX_OWNED_FALLBACK and basis.startswith("fallback")


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


def test_the_contracts_and_the_heartbeat_watch_the_feed_s_own_artifacts() -> None:
    sys.path.insert(0, str(ROOT / "ops"))
    import organ_contract as oc
    rows = {k: v for k, v in oc.CONTRACTS.items() if k.startswith("MT5-Dept-Intel (intel feed")}
    arts = {v[0] for v in rows.values()}
    assert arts == {"desks/mt5/reports/HOURLY_DISCOVERY.json",
                    "desks/mt5/data/intelligence/seed_miners_state.json"}
    assert all(v[1] == 180 for v in rows.values())
    sys.path.insert(0, str(DESK / "scripts"))
    import box_heartbeat as hb
    assert {str(p.relative_to(ROOT)).replace("\\", "/") for p in hb.INTEL_FEED} == arts
    assert hb.INTEL_FEED_MAX_MIN == 180
    # the producers write exactly these
    assert hd.REPORT.parts[-2:] == ("reports", "HOURLY_DISCOVERY.json")
    import seed_miners
    assert seed_miners.STATE.name == "seed_miners_state.json"
    assert seed_miners.STATE.parent.name == "intelligence"


# --------------------------------------------------------------------- intel_ship_adopt.ps1 skip
SHIP = (DESK / "scripts" / "intel_ship_adopt.ps1").read_text(encoding="utf-8")


def test_a_frozen_or_unchanged_ship_is_skipped_before_any_wait_or_lock() -> None:
    skip = SHIP.index("# 1b. SKIP A FROZEN OR UNCHANGED SHIP")
    assert SHIP.index("fetch --no-write-fetch-head") < skip
    assert skip < SHIP.index('Get-ScheduledTask -TaskName "MT5-ShadowSync"')
    assert skip < SHIP.index("$script:GitWriterHandle = Open-GitWriterMutex")
    assert skip < SHIP.index("& git checkout $shipRef --")
    assert "[double] $MaxShipAgeHours = 6" in SHIP
    block = SHIP[skip:SHIP.index("# 2. wait for MT5-ShadowSync")]
    assert "git log -1 --format=%ct $shipRef" in block
    assert "if ($shipAgeH -gt $MaxShipAgeHours)" in block
    assert "$lastSha -eq $shipSha" in block
    # each skip says why, in the log, and exits 0 (a skip is the organ working)
    assert block.count("Log $why") == 2 and block.count("exit 0") == 2
    assert "stopped" in block and "unchanged since the last adoption" in block
    # a ref whose time cannot be read is not adopted blind
    assert "not adopting what cannot be dated" in block


def test_the_adopted_sha_is_recorded_only_after_a_real_checkout() -> None:
    checkout = SHIP.index("& git checkout $shipRef --")
    write = SHIP.index("WriteAllText($adoptState")
    assert checkout < write
    assert 'if ($LASTEXITCODE -ne 0) { Log "git checkout failed' in SHIP[checkout:write]
    assert "last_adopted_sha = $shipSha" in SHIP[checkout:write]
    assert "intel_ship_adopt_state.json" in SHIP

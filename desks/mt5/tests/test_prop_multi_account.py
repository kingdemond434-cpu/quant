"""Several prop challenge accounts at once (zuck 2026-11-03): registry, fence, binds, cadence.

`mt5desk.prop_accounts` registers accounts beyond the legacy FTMO one; each is solved, executed and
fenced as its own account. These pin: the legacy account's paths never move, a bad registry row is
refused (never guessed), every prop account fences every other in both directions, the executor,
reader and allocator bind to the account they are given, and the allocator re-solves exactly when
something that can move the argmax moved.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import prop_challenge_allocator as pca  # noqa: E402
from mt5desk import cross_account as xa  # noqa: E402
from mt5desk import prop_accounts as pa  # noqa: E402

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
PROG = {"daily_loss": 0.04, "max_loss": 0.08, "min_days": 3,
        "targets": {"phase1": 0.08, "phase2": 0.05},
        "next_phase": {"phase1": "phase2", "phase2": "funded"},
        "day_tz": "America/New_York", "profit_cap": None,
        "max_loss_basis": "static_initial", "daily_loss_basis": "day_start_balance",
        "source": "example firm rule page, read in a test"}


def _registry(data: Path, rows: list[dict], programs: dict | None = None) -> None:
    data.mkdir(parents=True, exist_ok=True)
    (data / pa.REGISTRY_NAME).write_text(json.dumps({"accounts": rows}))
    (data / pa.PROGRAMS_NAME).write_text(json.dumps({"programs": programs or {"x_2step": PROG}}))


def _row(aid: str, firm: str = "firmx", term: str | None = None, **kw) -> dict:
    return {"id": aid, "firm": firm, "program": kw.pop("program", "x_2step"),
            "terminal_path": term or rf"C:\Terminals\{aid}\terminal64.exe", **kw}


@pytest.fixture
def data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A hermetic data/ dir: the registry module, the fence and the allocator all read it."""
    d = tmp_path / "data"
    (d / "xacct").mkdir(parents=True)
    monkeypatch.setattr(xa, "XACCT_DIR", d / "xacct")    # its own data/, never the shared basetemp
    monkeypatch.setattr(pa, "DATA", d)
    # a registry-error block pages: never into the real outbox or alert ledger from a test
    monkeypatch.setattr(xa, "_send", lambda *a, **k: {})
    monkeypatch.setattr(xa, "_REG_ALERT", {})
    monkeypatch.setattr(xa, "_alert_ledger_path", lambda: tmp_path / "alerts.json")
    monkeypatch.setattr(pa, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(pa, "LOGS", tmp_path / "logs")
    return d


# ------------------------------------------------------------------ the registry

def test_legacy_paths_never_move() -> None:
    p = pa.paths(pa.Account(id="ftmo", firm="ftmo", program="ftmo_2step"))
    assert p["alloc_report"] == pa.REPORTS / "FTMO_ALLOCATOR.json"
    assert p["alloc_armed"] == pa.DATA / "FTMO_ALLOCATOR_ARMED"
    assert p["exec_armed"] == pa.DATA / "FTMO_EXECUTOR_ARMED"
    assert p["venue_state"] == pa.REPORTS / "FTMO_ACCOUNT_STATE.json"
    assert pa.Account(id="ftmo", firm="ftmo", program="ftmo_2step").book_key == "ftmo"


def test_legacy_terminal_matches_the_follower() -> None:
    from prop import ftmo_follower
    assert pa.LEGACY_TERMINAL == ftmo_follower.TERMINAL_PATH


def test_no_registry_is_the_legacy_account_alone(data: Path) -> None:
    accts, errors = pa.load(data)
    assert [a.id for a in accts] == ["ftmo"] and errors == []


def test_registry_refuses_bad_rows(data: Path) -> None:
    _registry(data, [_row("good"), _row("good"), _row("BAD"), _row("nofirm", firm="X Y"),
                     _row("noprog", program="unknown"), {"id": "noterm", "firm": "f",
                                                         "program": "x_2step"},
                     _row("dupterm", term=r"C:\Terminals\good\terminal64.exe"),
                     _row("stealsftmo", term=pa.LEGACY_TERMINAL), _row("off", enabled=False)])
    accts, errors = pa.load(data)
    assert [a.id for a in accts] == ["ftmo", "good", "off"]
    assert not accts[2].enabled
    assert len(errors) == 7
    assert any("stealsftmo" in e and "another account" in e for e in errors)


def test_unsourced_program_is_refused(data: Path) -> None:
    _registry(data, [_row("a")], {"x_2step": {**PROG, "source": ""},
                                  "ftmo_2step": PROG})
    progs, errors = pa.programs(data)
    assert set(progs) == {"ftmo_2step"}
    assert progs["ftmo_2step"]["max_loss"] == 0.10           # a built-in is never overridden
    assert len(errors) == 2
    with pytest.raises(ValueError):
        pca.rules_for("x_2step")


@pytest.mark.parametrize("bad", [{"max_loss_basis": "trailing_equity_high"},
                                 {"daily_loss_basis": "day_start_equity"},
                                 {"profit_cap": 0.02}, {"max_loss_basis": None}])
def test_an_unmodelled_rule_shape_is_refused(bad: dict) -> None:
    row = {**PROG, **bad}
    if bad.get("max_loss_basis", "x") is None:
        row.pop("max_loss_basis")
    assert pa.program_error("x_2step", row) is not None
    assert pa.program_error("x_2step", PROG) is None


def test_program_rules_reach_the_allocator(data: Path) -> None:
    _registry(data, [_row("a")])
    r = pca.rules_for("x_2step")
    assert (r.daily_loss, r.max_loss, r.min_days, r.targets["phase1"]) == (0.04, 0.08, 3, 0.08)
    assert pca.rules_for("ftmo_2step") is pca.FTMO_2STEP


# ------------------------------------------------------------------ the fence, every way

def _book(name: str, symbols: dict, at: datetime = NOW) -> None:
    (xa.XACCT_DIR / f"{name}_book.json").write_text(json.dumps({
        "account": name, "covers": "all", "at": at.isoformat(), "symbols": symbols,
        "account_key": "sha256:" + "b" * 16}))


def test_every_prop_account_fences_every_other(data: Path) -> None:
    _registry(data, [_row("a"), _row("b", firm="firmy")])
    assert xa.prop_names() == ("ftmo", "prop_a", "prop_b")
    assert xa.is_peer("prop_b") and not xa.is_peer("prop_zz")
    _book("prop_b", {"EURUSD": {"long": True, "short": False}})
    # Fusion/E8 (through ftmo_block) and every other prop executor see prop_b's long
    assert "prop_b" in (xa.ftmo_block("EURUSD", "sell", now=NOW) or "")
    assert "prop_b" in (xa.prop_block("EURUSD", "sell", now=NOW, exclude=("ftmo",)) or "")
    assert xa.prop_block("EURUSD", "buy", now=NOW) is None                 # same side is fine
    assert xa.prop_block("EURUSD", "sell", now=NOW, exclude=("prop_b",)) is None   # own book
    assert xa.prop_block("XAUUSD", "sell", now=NOW) is None                # gold: the OCO lock


def test_an_armed_prop_account_with_no_book_fails_closed(data: Path) -> None:
    _registry(data, [_row("a")])
    assert xa.prop_block("EURUSD", "buy", now=NOW) is None                 # never ran: nothing
    (data / "prop" / "a").mkdir(parents=True)
    (data / "prop" / "a" / "EXECUTOR_ARMED").write_text("")
    assert "fail closed" in (xa.prop_block("EURUSD", "buy", now=NOW) or "")
    _book("prop_a", {}, at=NOW - timedelta(hours=1))                       # armed and stale
    assert "fail closed" in (xa.prop_block("EURUSD", "buy", now=NOW) or "")
    _book("prop_a", {})
    assert xa.prop_block("EURUSD", "buy", now=NOW) is None


def test_unarmed_prop_book_fences_at_any_age(data: Path) -> None:
    _registry(data, [_row("a")])
    _book("prop_a", {"GBPUSD": {"long": False, "short": True}}, at=NOW - timedelta(days=3))
    assert "prop_a" in (xa.prop_block("GBPUSD", "buy", now=NOW) or "")


def test_a_registry_error_fails_the_fence_closed(data: Path) -> None:
    _registry(data, [_row("a"), _row("BAD")])
    hit = xa.prop_block("EURUSD", "buy", now=NOW) or ""
    assert "registry has errors" in hit and "fail closed" in hit
    assert "registry has errors" in (xa.ftmo_block("EURUSD", "buy", now=NOW) or "")
    (data / pa.REGISTRY_NAME).write_text("{not json")
    assert "fail closed" in (xa.prop_block("EURUSD", "buy", now=NOW) or "")


def test_a_registry_block_pages_red_and_is_billed(data: Path, monkeypatch) -> None:
    import missed_growth as mg
    pages: list[tuple[str, str]] = []
    monkeypatch.setattr(xa, "_send", lambda aid, st, sig, t, b: pages.append((aid, st)) or {})
    monkeypatch.setattr(xa, "_REG_ALERT", {})
    monkeypatch.setattr(xa, "_alert_ledger_path", lambda: data / "alerts.json")
    _registry(data, [_row("BAD")])
    assert xa.prop_block("EURUSD", "buy", now=NOW)
    assert xa.prop_block("GBPUSD", "sell", now=NOW)
    assert pages == [(xa.REGISTRY_ALERT_ID, "OPEN")]           # paged once, not per entry
    line = mg.published_prop_registry_block_lines()["rails"]["prop_registry_error"]
    assert line["n"] == 2 and line["by_symbol"] == {"EURUSD": 1, "GBPUSD": 1}
    _registry(data, [_row("a")])
    assert xa.prop_block("EURUSD", "buy", now=NOW) is None
    assert pages[-1] == (xa.REGISTRY_ALERT_ID, "OK")            # recovery paged once
    xa.prop_block("EURUSD", "buy", now=NOW)
    assert len(pages) == 2


def test_an_unregistered_account_on_disk_still_fences(data: Path) -> None:
    """A removed row never hides an account that may hold positions (audit MF1)."""
    _registry(data, [])
    _book("prop_gone", {"EURUSD": {"long": True, "short": False}})
    assert "prop_gone" in xa.prop_names() and xa.is_peer("prop_gone")
    assert "prop_gone" in (xa.prop_block("EURUSD", "sell", now=NOW) or "")
    (data / "prop" / "armedonly").mkdir(parents=True)
    (data / "prop" / "armedonly" / "EXECUTOR_ARMED").write_text("")
    assert "fail closed" in (xa.prop_block("GBPUSD", "buy", now=NOW) or "")


def test_an_existing_malformed_book_fails_closed(data: Path) -> None:
    _registry(data, [_row("a")])
    (xa.XACCT_DIR / "prop_a_book.json").write_text("{broken")
    assert "fail closed" in (xa.prop_block("EURUSD", "buy", now=NOW) or "")


def test_missed_growth_reads_every_accounts_journal(data: Path, monkeypatch) -> None:
    import missed_growth as mg
    legacy = data / "ftmo_exec_intents.jsonl"
    monkeypatch.setattr(mg, "FTMO_EXEC_INTENTS", legacy)
    legacy.write_text(json.dumps({"rail": "loss_guard", "status": "RAIL_BLOCKED",
                                  "missed_growth_risk_usd": 10.0, "at": "x"}) + "\n")
    (data / "prop" / "a").mkdir(parents=True)
    (data / "prop" / "a" / "exec_intents.jsonl").write_text(json.dumps(
        {"rail": "cross_account_opposite", "status": "RAIL_BLOCKED",
         "missed_growth_risk_usd": 5.0, "at": "y"}) + "\n")
    (data / "prop" / "firm_firmx").mkdir(parents=True)
    rails = mg.published_ftmo_executor_lines()["rails"]
    assert rails["loss_guard"]["accounts"] == ["ftmo"]
    assert rails["cross_account_opposite"]["accounts"] == ["a"]
    assert rails["cross_account_opposite"]["undeployed_risk_usd"] == 5.0


# ------------------------------------------------------------------ the binds

@pytest.fixture
def as_account(monkeypatch):
    """Re-import the executor and the reader as a process serving `aid` would (the account is
    read once, at import, from QUANT_PROP_ACCOUNT), and restore the FTMO account's afterwards."""
    import importlib

    from prop import ftmo_executor as fx
    from prop import ftmo_venue_reader as fvr

    def go(aid: str | None):
        if aid is None:
            monkeypatch.delenv(pa.PROCESS_ENV, raising=False)
        else:
            monkeypatch.setenv(pa.PROCESS_ENV, aid)
        return importlib.reload(fx), importlib.reload(fvr)

    yield go
    monkeypatch.delenv(pa.PROCESS_ENV, raising=False)
    importlib.reload(fx)
    importlib.reload(fvr)


def test_the_ftmo_account_keeps_every_original_path(data: Path, as_account) -> None:
    fx, fvr = as_account(None)
    assert fx.ARMED_MARKER == data / "FTMO_EXECUTOR_ARMED"
    assert (fx.STATE, fx.INTENTS) == (data / "ftmo_executor_state.json",
                                      data / "ftmo_exec_intents.jsonl")
    assert (fx.ALLOCATOR, fx.OUT) == (pa.REPORTS / "FTMO_ALLOCATOR.json",
                                      pa.REPORTS / "FTMO_EXEC.json")
    assert fx.LOG == pa.LOGS / "ftmo_executor.log"
    assert (fx.XACCT, fx.BOOK_KEY, fx.ACCOUNT_ID, fx.ACCOUNT_ERROR) == ("ftmo", "ftmo", "ftmo",
                                                                        None)
    assert fx._VENUE == {} and fx.MAX_LOSS == 0.10 and fx.DAY_TZ == "Europe/Prague"
    assert fvr.STATE_OUT == pa.REPORTS / "FTMO_ACCOUNT_STATE.json"
    assert fvr.REGISTRY_OUT == data / "ftmo_registry.json" and fvr.PROGRAM is None
    assert fvr.TERMINAL_NAME == "FTMO Global Markets MT5 Terminal"


def test_a_process_serves_the_account_its_environment_names(data: Path, as_account) -> None:
    _registry(data, [_row("a")])
    fx, fvr = as_account("a")
    assert (fx.XACCT, fx.BOOK_KEY, fx.ACCOUNT_ID, fx.ACCOUNT_ERROR) == ("prop_a", "prop_a", "a",
                                                                        None)
    assert data / "prop" / "a" / "EXECUTOR_ARMED" == fx.ARMED_MARKER
    assert fx.ALLOCATOR == pa.REPORTS / "prop" / "a" / "ALLOCATOR.json"
    assert fx.MAX_LOSS == 0.08 and fx.DAY_TZ == "America/New_York"
    assert fx._VENUE["account_types"] == {"x_2step": 0.04}
    assert fx._VENUE["terminal_path"].endswith(r"a\terminal64.exe")
    assert fx._VENUE["terminal_env"] == "QUANT_PROP_A_TERMINAL"
    assert fvr.PROGRAM == "x_2step"
    assert data / "prop" / "firm_firmx" / "registry.json" == fvr.REGISTRY_OUT
    assert "FTMO" not in fvr.TERMINAL_NAME
    from prop import ftmo_follower as ff                    # the follower is never touched
    assert ff.MAX_LOSS_FRAC == 0.10 and ff.DAILY_LOSS_FRAC == 0.05
    assert ff.TERMINAL_ENV == "QUANT_FTMO_TERMINAL"


def test_an_unusable_account_refuses_to_run(data: Path, as_account) -> None:
    _registry(data, [_row("a")])
    fx, fvr = as_account("nobody")
    assert fx.ACCOUNT_ERROR and fx.ACCOUNT is pa.REFUSED
    assert "refused" in fx.ARMED_MARKER.parts                # never an armed path
    assert fx.main([]) == 1 and fvr.main([]) == 1
    fx, _ = as_account("a")
    assert fx.main(["--account", "b"]) == 1                    # the flag only cross-checks


def test_the_follower_helpers_take_another_programs_rules() -> None:
    from prop import ftmo_follower as ff
    ok, _ = ff.loss_guard(100_000.0, 92_000.0, 91_900.0, 100.0)              # FTMO floor 90k
    assert ok
    ok, why = ff.loss_guard(100_000.0, 92_000.0, 91_900.0, 100.0, max_frac=0.08)  # floor 92k
    assert not ok and "max loss" in why
    day, _ = ff.cet_day(NOW, "America/New_York")
    assert day == "2026-11-03"


def test_allocator_binds_and_restores(data: Path) -> None:
    _registry(data, [_row("a")])
    try:
        r = pca.bind_account(pa.get("a"))
        assert r.max_loss == 0.08 and pca.BOOK_KEY == "prop_a" and pca.ACCOUNT_ID == "a"
        assert frozenset() == pca.FTMO_EXECUTABLE          # gold has one follower, the legacy one
        assert data / "prop" / "a" / "ALLOCATOR_ARMED" == pca.ARMED
        assert data / "prop" / "firm_firmx" / "registry.json" == pca.FTMO_REGISTRY
        assert pca.VENUE_TAG == "" and pca.DAY_TZ == "America/New_York"
        assert not pca.FTMO_QUOTES.exists()                # no foreign quote snapshot prices it
    finally:
        pca.bind_account(pa.get("ftmo"))
    assert pca._DEFAULTS["OUT"] == pca.OUT and pca.BOOK_KEY == "ftmo"
    assert frozenset({"gold_asia"}) == pca.FTMO_EXECUTABLE and pca.VENUE_TAG == "FTMO"


def test_apply_book_writes_only_its_own_block(data: Path, tmp_path: Path) -> None:
    _registry(data, [_row("a")])
    book = tmp_path / "CERT_BOOK_LIVE.json"
    book.write_text(json.dumps({"enabled": True, "ftmo": {"gold_asia": 0.009}}))
    armed = tmp_path / "ARMED"
    armed.write_text("")
    doc = {"deployable": True, "generated_at": NOW.isoformat(), "account": {"phase": "phase1"},
           "executable": {"EURUSD_x_asia": 0.003}}
    try:
        pca.bind_account(pa.get("a"))
        assert pca.apply_book(doc, book, armed, tmp_path / "none.json")["applied"] is True
    finally:
        pca.bind_account(pa.get("ftmo"))
    out = json.loads(book.read_text())
    assert out["ftmo"] == {"gold_asia": 0.009}                          # untouched
    assert out["prop_a"] == {"EURUSD_x_asia": 0.003} and "prop_a_by" in out


# ------------------------------------------------------------------ the cadence

def _state(**kw) -> pca.AccountState:
    base = {"phase": "phase1", "balance": 1.01, "status": "MEASURED",
            "detail": {"account_key": "sha256:" + "c" * 16}}
    base.update(kw)
    return pca.AccountState(**base)


def test_due_reasons(monkeypatch) -> None:
    monkeypatch.setattr(pca, "inputs_fingerprint", lambda: "fp1")
    st = _state()
    prev = {"generated_at": NOW.isoformat(), "status": "OK", "due_basis": pca.due_basis(st, NOW)}
    later = NOW + timedelta(minutes=10)
    assert pca.due_reasons(prev, st, later) == []
    assert pca.due_reasons(None, st, later)
    assert any("min old" in r for r in pca.due_reasons(prev, st, NOW + timedelta(minutes=55)))
    assert any(r.startswith("phase") for r in pca.due_reasons(prev, _state(phase="phase2"), later))
    assert any("account_key" in r for r in pca.due_reasons(
        prev, _state(detail={"account_key": "sha256:" + "d" * 16}), later))
    assert any("balance moved" in r for r in pca.due_reasons(prev, _state(balance=1.016), later))
    assert pca.due_reasons(prev, _state(balance=1.012), later) == []      # under the move
    assert any(r.startswith("day") for r in pca.due_reasons(prev, st, NOW + timedelta(hours=12,
                                                                                    minutes=1)))
    monkeypatch.setattr(pca, "inputs_fingerprint", lambda: "fp2")
    assert any("fingerprint" in r for r in pca.due_reasons(prev, st, later))
    monkeypatch.setattr(pca, "inputs_fingerprint", lambda: "fp1")
    assert pca.due_reasons({**prev, "status": "UNMEASURED: x"}, st, later)    # retried


def test_run_lock(tmp_path: Path) -> None:
    lock = tmp_path / "L.lock"
    with pca.RunLock(lock), pytest.raises(pca.Busy), pca.RunLock(lock):
        pass
    assert not lock.exists()
    lock.write_text("dead")
    import os
    old = datetime.now(tz=UTC).timestamp() - pca.LOCK_STALE_S - 10
    os.utime(lock, (old, old))
    with pca.RunLock(lock):                                   # a dead run's lock is taken over
        pass


def test_a_stale_lock_is_broken_and_a_live_one_beats(tmp_path: Path) -> None:
    import os
    lock = tmp_path / "L.lock"
    with pca.RunLock(lock) as held:
        old = datetime.now(tz=UTC).timestamp() - pca.LOCK_STALE_S + 30
        os.utime(lock, (old, old))
        held.beat()                                            # refreshed: still held
        with pytest.raises(pca.Busy):
            pca.RunLock(lock).__enter__()
    assert not list(tmp_path.glob("*.stale.*"))


def test_one_account_failing_does_not_starve_the_next(data: Path, monkeypatch) -> None:
    _registry(data, [_row("a"), _row("b")])

    def boom(acct, **kw):
        if acct.id == "a":
            raise RuntimeError("solve exploded")
        return {"account": acct.id, "solved": True, "why": "forced"}

    monkeypatch.setattr(pca, "run_account", boom)
    out = pca.run_accounts(None, n_paths=10, seed=0, if_due=False)
    assert [r["account"] for r in out["accounts"]] == ["ftmo", "a", "b"]
    assert out["accounts"][1]["why"].startswith("FAILED") and out["status"] == "ACCOUNT_FAILED"


def test_run_accounts_builds_one_universe_per_firm(data: Path, monkeypatch, tmp_path) -> None:
    _registry(data, [_row("a"), _row("b"), _row("c", firm="firmy"), _row("off", enabled=False)])
    built: list[str] = []
    solved: list[tuple[str, str]] = []

    def fake_build(seed: int = 0) -> dict:
        built.append(str(pca.FTMO_REGISTRY))
        return {"status": "OK", "firm": str(pca.FTMO_REGISTRY)}

    def fake_solve(venue, *, n_paths, seed, state, uni, rules):
        solved.append((pca.ACCOUNT_ID, uni["firm"]))
        return {"status": "OK", "generated_at": NOW.isoformat(), "deployable": False,
                "account": {"phase": state.phase, "status": state.status}, "phases": {},
                "due_basis": {}}

    monkeypatch.setattr(pca, "build_universe", fake_build)
    monkeypatch.setattr(pca, "solve", fake_solve)
    monkeypatch.setattr(pca, "_DEFAULTS", {**pca._DEFAULTS, "OUT": tmp_path / "FTMO_ALLOC.json",
                                           "ARMED": tmp_path / "NOT_ARMED"})
    try:
        out = pca.run_accounts(None, n_paths=10, seed=0, if_due=False)
    finally:
        pca.bind_account(pa.get("ftmo"))
    assert len(built) == 3                                    # ftmo, firmx, firmy: once each
    assert [s[0] for s in solved] == ["ftmo", "a", "b", "c"]
    assert solved[1][1] == solved[2][1] != solved[3][1]       # a and b share firmx's universe
    rows = {r["account"]: r for r in out["accounts"]}
    assert rows["off"]["solved"] is False and "disabled" in rows["off"]["why"]
    assert (pa.REPORTS / "prop" / "a" / "ALLOCATOR.json").exists()
    assert (tmp_path / "FTMO_ALLOC.json").exists()
    assert pca.BOOK_KEY == "ftmo"


# ------------------------------------------------------------------ the fleet runner

def test_fleet_runs_each_non_legacy_account_alone(data: Path) -> None:
    import subprocess

    from prop import prop_fleet
    _registry(data, [_row("a"), _row("b", firm="firmy")])
    calls: list[list[str]] = []

    class Proc:
        def __init__(self, cmd, **kw) -> None:
            calls.append(cmd)
            self.cmd, self.returncode, self.killed = cmd, 0, False

        def communicate(self, timeout=None):
            if self.cmd[-1] == "b" and not self.killed:
                raise subprocess.TimeoutExpired(self.cmd, timeout)
            return "ok", None

        def kill(self) -> None:
            self.killed = True

    doc = prop_fleet.run_role("executor", popen=Proc, data=data)
    assert [c[-1] for c in calls] == ["a", "b"]               # legacy is its own task
    assert all(c[1].endswith("ftmo_executor.py") for c in calls)
    assert doc["status"] == "CHILD_FAILED" and doc["failed"] == ["b"]
    assert "killed" in [r for r in doc["accounts"] if r["account"] == "b"][0]["tail"]

"""Shared fixtures for the MT5 desk suite.

`fresh_tier_s_door`: the Tier S promotion door (`libs/tiers/promotion_authority.py`) FAILS
CLOSED -- its four hourly verdict files must be present and fresh, or every new LIVE row is
withheld with DOOR_ERROR. A promoter test that is not about the door would otherwise read the
real repository's `desks/mt5/reports/REPLICATION.json`, which a fresh clone or CI runner does
not have, and every promotion it asserts would be withheld.

This does NOT stub the door. It writes clean, fresh verifier artifacts -- a replication run
with no mismatch, an online-FDR replay with nothing over budget, an immune reading that did not
fall, a door-verdict file with no row against anything -- into `tmp_path` at the same
repo-relative paths the box uses, and points the door at that root. Every check still runs,
the firewall still judges the same relative paths, and a test that writes a MISMATCH or a DROP
into one of these files still sees the door withhold.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest


def write_fresh_door_inputs(root: Path, *, at: str | None = None) -> dict[str, Path]:
    """Clean verifier artifacts under `root`, at the door's repo-relative paths. Returns
    {door attribute: path} so a test can overwrite one with a verdict against a certificate."""
    now = at or datetime.now(UTC).isoformat()
    desk = root / "desks" / "mt5"
    docs: dict[str, tuple[Path, dict[str, Any]]] = {
        "REPLICATION": (desk / "reports" / "REPLICATION.json",
                        {"at": now, "verdicts": []}),
        "FDR_ROWS": (desk / "reports" / "tier_s" / "ONLINE_FDR_ROWS.json",
                     {"generated_utc": now, "rows": []}),
        "FREEZE": (desk / "data" / "tier_s" / "PROMOTION_FREEZE.json",
                   {"at": now, "verdict": "OK", "why": ""}),
        "DOOR_VERDICTS": (desk / "data" / "tier_s" / "door_verdicts.json",
                          {"generated_utc": now, "rows": {}}),
    }
    out: dict[str, Path] = {}
    for attr, (path, doc) in docs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc), "utf-8")
        out[attr] = path
    return out


@pytest.fixture
def fresh_tier_s_door(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[dict[str, Path]]:
    """Point the Tier S door at fresh, clean verifier artifacts in `tmp_path` (see module doc)."""
    from libs.tiers import promotion_authority as pa

    root = tmp_path / "door_root"
    paths = write_fresh_door_inputs(root)
    desk = root / "desks" / "mt5"
    monkeypatch.setattr(pa, "ROOT", root)
    for attr, path in paths.items():
        monkeypatch.setattr(pa, attr, path)
    monkeypatch.setattr(pa, "LEDGER", desk / "data" / "tier_s" / "promotion_blocks.jsonl")
    monkeypatch.setattr(pa, "SUSPENDED_LEDGER", desk / "data" / "tier_s" / "door_suspended.jsonl")
    monkeypatch.setattr(pa, "LIVE_DOOR", desk / "data" / "tier_s" / "live_door.json")
    # the constitution and ratifications keep their repo-relative names; absent = sealed default
    monkeypatch.setattr(pa, "CONSTITUTION", root / "docs" / "research" / "tier_s_constitution.json")
    monkeypatch.setattr(pa, "RATIFICATIONS",
                        root / "docs" / "research" / "tier_s_ratifications.jsonl")
    required = dict(pa.REQUIRED)
    for key, (path, stamp, writer) in pa.REQUIRED.items():
        for new in paths.values():
            if path.name == new.name:
                required[key] = (new, stamp, writer)
    monkeypatch.setattr(pa, "REQUIRED", required)
    yield paths

_REPO_DEPTH = 3


@pytest.fixture(autouse=True)
def _tier_s_state_stays_out_of_the_checkout(monkeypatch: pytest.MonkeyPatch,
                                            tmp_path_factory: pytest.TempPathFactory) -> None:
    """A test never appends to the live Tier S ledgers. `blinding.record` (which `publish` calls)
    and the promotion door's block ledger write under the checkout by default, so a suite run on
    the box would add fake rows to `desks/mt5/data/tier_s/`. Writes aimed inside the checkout are
    redirected to a temp root; a test that points them at its own tmp_path is untouched."""
    from libs.tiers import blinding
    from libs.tiers import promotion_authority as pa

    repo = Path(__file__).resolve().parents[_REPO_DEPTH]
    sink = tmp_path_factory.mktemp("tier_s_sink")
    real_record = blinding.record

    def record(root: Path, rep: Any, ledger: str = blinding.RUNTIME_LEDGER) -> None:
        target = (Path(root) / ledger).resolve()
        if (target.is_relative_to(repo)
                and not target.is_relative_to(tmp_path_factory.getbasetemp().resolve())):
            root, ledger = sink, str(target.relative_to(repo))
        real_record(root, rep, ledger)

    monkeypatch.setattr(blinding, "record", record)
    if Path(pa.LEDGER).resolve().is_relative_to(repo):
        monkeypatch.setattr(pa, "LEDGER", sink / "promotion_blocks.jsonl")
    if Path(pa.SUSPENDED_LEDGER).resolve().is_relative_to(repo):
        monkeypatch.setattr(pa, "SUSPENDED_LEDGER", sink / "door_suspended.jsonl")


def write_measured_dsr_inputs(root: Path, *, variance: float = 0.0002, n: int = 200,
                              family: str = "fixture") -> Path:
    """A REAL measured `DSR_INPUTS.json` under `root`, written by the organ's own `run` from a
    synthetic sweep of `n` judged cells whose Sharpes have sample variance exactly `variance`.

    The sealed judge (with `tier_s_dsr_measured_variance.patch`) fails closed without a fresh,
    verified DSR_INPUTS -- every cell UNKNOWN, `dsr_inputs_unmeasured`. A test that is not about
    the DSR inputs points the judge's door here. Nothing is stubbed: the document is harvested,
    measured and hashed exactly as the hourly leg does it, and the judge verifies it. The
    fixture family is not a real family, so every real family reads the POOLED variance and no
    measured effective-trial count (the judge's other charges apply unchanged)."""
    import math

    from libs.research import dsr_inputs

    a = math.sqrt(variance * (n - 1) / n)             # +-a alternating: ddof=1 variance exact
    verdicts = [{"cell": f"FIX{i}.{family}.p={i}", "family": family, "sym": f"FIX{i % 7}",
                 "days": 300, "stages": {"in_sample_screen": {"sharpe": a if i % 2 else -a}}}
                for i in range(n)]
    root.mkdir(parents=True, exist_ok=True)
    sweep = root / "fixture_sweep.json"
    sweep.write_text(json.dumps({"hunt": "fixture", "swept_at": datetime.now(UTC).isoformat(),
                                 "verdicts": verdicts}), "utf-8")
    out = root / "DSR_INPUTS.json"
    doc = dsr_inputs.run(report_path=sweep, ledger_path=root / "dsr_trial_sharpes.jsonl",
                         out=out)
    assert doc["status"] == dsr_inputs.MEASURED, doc.get("why")
    return out


@pytest.fixture
def measured_dsr_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the judge's DSR-inputs door at a fresh measured document (see the writer above)."""
    from libs.research import dsr_inputs

    path = write_measured_dsr_inputs(tmp_path / "dsr_inputs")
    monkeypatch.setattr(dsr_inputs, "REPORT", path)
    return path


@pytest.fixture(scope="module")
def measured_dsr_inputs_module(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """`measured_dsr_inputs` for a module-scoped fixture that runs the real judge once."""
    from libs.research import dsr_inputs

    path = write_measured_dsr_inputs(tmp_path_factory.mktemp("dsr_inputs"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(dsr_inputs, "REPORT", path)
        yield path


@pytest.fixture(autouse=True)
def _e8_gold_slip_writes_to_tmp(tmp_path_factory, monkeypatch):
    """THE E8 GOLD SLIP FILE NEVER LANDS IN THE REPO FROM A TEST. `e8_gold.run` re-measures and
    writes data/E8_GOLD_SLIP.json (and appends data/e8_gold_stop_exits.jsonl) on every pass, so
    any test that drives the lane would otherwise rewrite the tracked file. A test that sets its
    own paths afterwards still wins."""
    import sys
    mods = [sys.modules.get(k) for k in ("prop.e8_gold", "desks.mt5.prop.e8_gold")]
    live = [g for g in mods if g is not None and hasattr(g, "BRACKET_SLIP_FILE")]
    if live:
        d = tmp_path_factory.mktemp("e8_gold_slip")
        for g in live:
            monkeypatch.setattr(g, "BRACKET_SLIP_FILE", d / "E8_GOLD_SLIP.json")
            monkeypatch.setattr(g, "STOP_EXITS", d / "e8_gold_stop_exits.jsonl")
            if hasattr(g, "FX_STOP_EXITS"):
                monkeypatch.setattr(g, "FX_STOP_EXITS", d / "e8_fx_stop_exits.jsonl")
    yield


@pytest.fixture(autouse=True)
def _order_door_writes_to_tmp(tmp_path_factory, monkeypatch):
    """THE ORDER DOOR'S LEDGER NEVER LANDS IN THE REPO FROM A TEST. `mt5desk.order_door` appends
    one row per money action to `desks/mt5/data/order_door_ledger.jsonl` -- the box's real
    evidence. Every test that drives a lane through a fake venue goes through that door."""
    monkeypatch.setenv("MT5_ORDER_DOOR_DIR", str(tmp_path_factory.mktemp("order_door")))
    yield


#: The fake logins the conftest's flat books are keyed by (never a real account).
#: The E8 identity is the TEST VENUE's own (r7.2, audit r7.1 MF-1): every fake TLAPI handle the
#: suite uses (`account_id`/`acc_id` 31337 on server "E8-Test") keys to the declared E8 account.
CONFTEST_LOGINS = {"fusion": 7000101, "e8": 31337}
CONFTEST_SERVERS = {"fusion": "test", "e8": "E8-Test"}


def _stand_in_provenance() -> Any:
    """A test double with `libs.ops.provenance.account_key`'s v5c contract, for a tree that does
    not carry provenance.py yet: a positive integer login (int, integral float or digit string,
    whitespace allowed) on a stripped server, keyed HMAC-SHA256 under a fixed TEST key; anything
    else is None. Never used on a tree that has the real module."""
    import hashlib
    import hmac
    import types

    def norm_login(login: object) -> int | None:
        if login is None or isinstance(login, bool):
            return None
        if isinstance(login, float):
            return int(login) if login.is_integer() and login > 0 else None
        if isinstance(login, int):
            return login if login > 0 else None
        if isinstance(login, str) and login.strip().isascii() and login.strip().isdigit():
            return int(login.strip()) or None
        return None

    def account_key(login: object, server: object, *, create: bool = False) -> str | None:
        canon = norm_login(login)
        if canon is None:
            return None
        srv = "\x00none" if server is None else str(server).strip()
        mac = hmac.new(b"conftest-box-key-" + b"0" * 32, f"{canon}@{srv}".encode(),
                       hashlib.sha256).hexdigest()
        return "sha256:" + mac[:16]

    mod = types.ModuleType("libs.ops.provenance")
    mod.account_key = account_key  # type: ignore[attr-defined]
    mod.norm_login = norm_login  # type: ignore[attr-defined]
    mod.STAND_IN = True  # type: ignore[attr-defined]
    return mod


def _install_provenance(d: Path, monkeypatch: Any) -> None:
    import sys
    try:
        # The real helper (v5e): `_account_key_in_tmp` already points it at the suite's
        # throwaway key, and this fixture runs after it -- never a second key (r7.2).
        from libs.ops import provenance  # noqa: F401
    except ImportError:
        key = d / "account_key.hmac"
        key.write_text("conftest-box-key-" + "0" * 48, encoding="utf-8")
        monkeypatch.setenv("QUANT_ACCOUNT_KEY_FILE", str(key))
        import libs.ops as _ops
        stand_in = _stand_in_provenance()
        monkeypatch.setitem(sys.modules, "libs.ops.provenance", stand_in)
        monkeypatch.setattr(_ops, "provenance", stand_in, raising=False)


@pytest.fixture(autouse=True)
def _cross_account_books_in_tmp(tmp_path_factory, monkeypatch, _account_key_in_tmp):
    """THE CROSS-ACCOUNT FENCE'S (AND THE RAILS LEDGER'S) FILES NEVER LAND IN THE REPO FROM A
    TEST, AND EVERY TEST STARTS IN A READABLE WORLD. `mt5desk.cross_account` keeps both
    accounts' books and the placement lock under `data/xacct/`; here that directory is a fresh
    tmp one holding a just-published, FLAT book for each account, so a lane under test sees
    "the other account holds nothing" -- exactly what it saw before the fence existed. A test of
    the fence itself writes its own books (or deletes these) to exercise the refusals."""
    from mt5desk import cross_account
    d = tmp_path_factory.mktemp("xacct")
    monkeypatch.setattr(cross_account, "XACCT_DIR", d)
    # Per-process lock state never leaks between tests (re-entry, released tokens, the miss
    # cooldown).
    monkeypatch.setattr(cross_account, "_HELD", {})
    monkeypatch.setattr(cross_account, "_RELEASED", set())
    monkeypatch.setattr(cross_account, "_MISSED_AT", [])
    # HERMETIC ON THE BOX TOO: the box declares its real accounts in gitignored files
    # (FUSION_LIVE_ACCOUNT.json, E8_ACCOUNT.json), and a declared account makes every test book
    # "another account's". A test of the binding points these at its own tmp copies.
    from mt5desk import decision_core as _dc
    monkeypatch.setattr(cross_account, "E8_ACCOUNT_FILE", d / "E8_ACCOUNT.json")
    monkeypatch.setattr(_dc, "FUSION_ACCOUNT_FILE", d / "FUSION_LIVE_ACCOUNT.json")
    # THE ONE ACCOUNT KEY (r7): cross_account delegates to libs.ops.provenance.account_key. The
    # real module (publish_sync v5c) is used when this tree has it, keyed by a tmp box key; on a
    # tree without it, `_PROVENANCE_STAND_IN` reproduces its contract (digit logins only, the
    # server stripped, None fails closed). A test of the fail-closed path removes it.
    _install_provenance(d, monkeypatch)
    monkeypatch.setenv("E8_ALERT_LEDGER", str(d / "alert_ledger.json"))   # the E8 key page
    # The E8 account is DECLARED (r7.1: an absent E8_ACCOUNT.json refuses new E8 gold risk), as
    # the conftest's E8 book's key; a test of the undeclared path deletes it.
    (d / "E8_ACCOUNT.json").write_text(json.dumps(
        {"account_key": cross_account.account_key(CONFTEST_LOGINS["e8"], CONFTEST_SERVERS["e8"])}), "utf-8")
    for account in cross_account.ACCOUNTS:
        cross_account.publish(account, {}, source="conftest",
                              key=cross_account.account_key(CONFTEST_LOGINS[account],
                                                            CONFTEST_SERVERS[account]))
    # The Fusion book's rails ledger (mt5desk.fusion_rails) is box state too: a test that sends
    # a floor-lifted order would otherwise append its bill to the repo's data/ file.
    from mt5desk import fusion_rails
    monkeypatch.setattr(fusion_rails, "LEDGER", d / "fusion_book_rails.jsonl")
    yield d


@pytest.fixture(autouse=True)
def _e8_evidence_writes_to_tmp(tmp_path_factory, monkeypatch):
    """THE E8 GOLD LANE'S HEARTBEAT AND DECISION LEDGER NEVER LAND IN THE REPO FROM A TEST.
    `prop/e8_evidence.py` writes both under `desks/mt5/data/` -- the box's placement evidence,
    read by scripts/check_placement_interlock.py -- and every test that drives `e8_gold.run`."""
    where = tmp_path_factory.mktemp("e8_evidence")
    monkeypatch.setenv("E8_EVIDENCE_DIR", str(where))
    # ...and the account pseudonym's key is never created under the repo's data/secrets/.
    monkeypatch.setenv("E8_EVIDENCE_KEY_FILE", str(where / "e8_evidence.key"))
    monkeypatch.delenv("E8_EVIDENCE_KEY", raising=False)
    # ...and an unstamped-account page never lands in the repo's data/alert_ledger.json.
    monkeypatch.setenv("E8_ALERT_LEDGER", str(where / "alert_ledger.json"))
    yield


@pytest.fixture
def portable_gateway(monkeypatch, tmp_path):
    """Import the entire venue adapter on every OS; no SDK operation is permitted.

    The contract was captured from SDK 5.0.6180 without initializing a terminal.
    Constants are exact; unknown names raise AttributeError and all callable SDK
    names raise AssertionError. Tests explicitly replace any operation they need.
    This tests production code, including its imports, rather than AST fragments.
    """
    import importlib.util
    import sys
    from types import ModuleType
    from mt5desk import config

    contract = json.loads((Path(__file__).parent / 'fixtures' /
                           'mt5_sdk_contract.json').read_text('utf-8'))
    sdk = ModuleType('MetaTrader5')
    sdk.__version__ = contract['sdk_version']
    sdk._test_calls = []
    for name, value in contract['constants'].items():
        setattr(sdk, name, value)
    def forbidden(name):
        def call(*args, **kwargs):
            sdk._test_calls.append(name)
            raise AssertionError(f'Unmocked SDK operation in portable test: {name}')
        return call
    for name in contract['methods']:
        setattr(sdk, name, forbidden(name))
    monkeypatch.setitem(sys.modules, 'MetaTrader5', sdk)
    monkeypatch.setattr(config, 'desk_root', lambda: tmp_path)
    monkeypatch.setattr(config, 'terminal_path', lambda: 'test-terminal-only')
    source = Path(__file__).parents[1] / 'mt5desk' / 'gateway.py'
    spec = importlib.util.spec_from_file_location('_quant_portable_gateway', source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert sdk._test_calls == [], 'Import must not contact or initialize a broker'
    module._test_sdk = sdk
    return module


@pytest.fixture(autouse=True)
def _openrouter_key_info_offline(tmp_path_factory: pytest.TempPathFactory,
                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reads the box's OpenRouter account file or asks OpenRouter for it: budgets read
    the account's daily limit from it, so a box with credit would shift every budget a test pins."""
    from libs.ops import openrouter_guard
    monkeypatch.setattr(openrouter_guard, "KEY_INFO",
                        tmp_path_factory.mktemp("openrouter") / "openrouter_key.json")
    monkeypatch.setattr(openrouter_guard, "NETWORK", False)


@pytest.fixture(scope="session")
def _account_key_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A throwaway HMAC key for the suite (fixed bytes, so keys are reproducible run to run)."""
    path = tmp_path_factory.mktemp("account_key") / "account_key.hmac"
    path.write_bytes(b"0123456789abcdef" * 4)
    return path


@pytest.fixture(autouse=True)
def _account_key_in_tmp(_account_key_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE SUITE NEVER READS OR CREATES THE BOX'S ACCOUNT KEY (2026-10-20). `account_key(...,
    create=True)` would otherwise write data/secrets/account_key.hmac into the checkout; every
    test gets a throwaway key instead. A test about the absent key points the env elsewhere."""
    from libs.ops import provenance as _acct_prov
    monkeypatch.setenv(_acct_prov.KEY_ENV, str(_account_key_file))


@pytest.fixture(autouse=True)
def _gold_oco_world(_cross_account_books_in_tmp: Path, _account_key_in_tmp: None,
                    monkeypatch: pytest.MonkeyPatch) -> Path:
    """THE GOLD DIRECTION LOCK'S FILES NEVER LAND IN THE REPO, AND EVERY TEST STARTS IN A
    READABLE WORLD (mt5desk.gold_oco). Its state lives beside the books in the tmp `xacct` dir;
    here the mode file is a tmp one in FULL OCO mode for Fusion and each lane has a fresh, FLAT
    gold state -- so a lane under test sees what it saw before the lock existed (no direction,
    nothing on the other account). Venue and terminal stubs that name no account are named by a
    fake login through the REAL keyed helper. A test of the lock itself writes its own world, and
    `tests/test_gold_oco.py` restores the real identity readers."""
    from mt5desk import gold_oco
    mode = _cross_account_books_in_tmp / "GOLD_OCO_MODE.json"
    mode.write_text('{"lanes": ["e8", "fusion"], "modes": {"fusion": "oco"}}', encoding="utf-8")
    monkeypatch.setattr(gold_oco, "MODE_FILE", mode)
    # The identity pager pages into a tmp root through a recording stub: no test ever reaches
    # the repo's alert ledger or a real channel. `gold_oco.PAGES` (test-only) holds what it sent.
    paged: list[tuple[str, str]] = []
    monkeypatch.setattr(gold_oco, "ALERT_ROOT", _cross_account_books_in_tmp / "alert_root")
    monkeypatch.setattr(gold_oco, "PAGER", lambda title, body: (
        paged.append((title, body)), {"armed": 1, "delivered": 1})[1])
    monkeypatch.setattr(gold_oco, "PAGES", paged, raising=False)
    real_tl, real_mt5 = gold_oco.tradelocker_oco_key, gold_oco.mt5_oco_key

    # E8 is named by the DECLARED identity (r7.1 declares E8_ACCOUNT.json from the venue's own
    # key, `tradelocker_account_key`, as production does): a fallback or flat state under any
    # other key is "another account" and the OCO's key join refuses it -- correctly (v2s).
    e8_declared = gold_oco.oco_account_key(CONFTEST_LOGINS["e8"], CONFTEST_SERVERS["e8"])

    def tl_key(venue: object) -> str:
        try:
            return real_tl(venue)
        except gold_oco.IdentityUnavailable:
            return e8_declared

    def mt5_key(mt5: object) -> str:
        try:
            return real_mt5(mt5)
        except gold_oco.IdentityUnavailable:
            return gold_oco.oco_account_key(990002, "conftest-fusion")

    monkeypatch.setattr(gold_oco, "tradelocker_oco_key", tl_key)
    monkeypatch.setattr(gold_oco, "mt5_oco_key", mt5_key)
    for i, lane in enumerate(gold_oco.DEFAULT_LANES):
        key = e8_declared if lane == "e8" else gold_oco.oco_account_key(990001 + i,
                                                                         f"conftest-{lane}")
        gold_oco.publish_lane(lane, key, positions=[], orders=[], date="2026-01-01")
    return _cross_account_books_in_tmp

"""THE TEST THAT FAILS IF A SILENT PERMANENT HALT CAN RECUR.

On 2026-09-24 the live gold book placed nothing at 10:00Z or 14:00Z. The gateway wrote 583
`release_identity_refused` rows that day -- one a minute -- and not one of them reached an
alert, a dashboard or a human; the principal found it by eye. The first such row is
2026-09-07T07:35:15Z, so the condition had been costing windows for seventeen days while every
organ reported healthy.

Two things are pinned here, and they are different claims:

  1. `scripts/check_placement_interlock.py` SEES the halt -- given the ledger the box actually
     had that day, it fails.
  2. The fence is WIRED. A checker nobody runs is the same silence with more files in it, which
     is the defect this whole area keeps producing (LAWS III.16: unwired or idle is a defect).

The seal-classification half is pinned in `desks/mt5/tests/test_release_identity.py`; this file
is about the halt being audible, not about why it happened.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "check_placement_interlock", ROOT / "scripts" / "check_placement_interlock.py")
assert _SPEC and _SPEC.loader
fence = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fence)

LEDGER = "desks/mt5/data/decision_ledger.jsonl"
GATEWAY_STATE = "desks/mt5/data/gateway_state.json"
IDENTITY = "desks/mt5/data/release_identity.json"

NOW = datetime(2026, 9, 24, 16, 50, tzinfo=UTC)
BOX_ID = "0123456789abcdef0123456789abcdef"
OFF_BOX_ID = "fedcba9876543210fedcba9876543210"
_CONFIG = {"hostname": "vmi3571445", "machine_id": BOX_ID}


def _as_host(monkeypatch: pytest.MonkeyPatch, machine_id: str | None, hostname: str,
             config: dict[str, object] | None = None) -> None:
    """Pin the fence's view of which machine it runs on, through the shared helper."""
    from libs.ops import host_identity
    ident = host_identity.classify(machine_id, hostname, _CONFIG if config is None else config)
    monkeypatch.setattr(fence, "_identify", lambda: ident)


def _write(root: Path, rel: str, text: str) -> Path:
    p = root / Path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, "utf-8")
    return p


def _rows(n: int, *, sleeve: str, reason: str, start: datetime,
          step_s: int = 60, taken: bool = False) -> list[str]:
    out = []
    for i in range(n):
        out.append(json.dumps({
            "decided_at": (start + timedelta(seconds=i * step_s)).isoformat(),
            "sleeve": sleeve, "strategy_id": sleeve, "symbol": "XAUUSD",
            "reason": reason, "taken": taken,
            "outcome": "EXECUTED" if taken else "VENUE_UNAVAILABLE",
        }))
    return out


@pytest.fixture
def box(tmp_path: Path) -> Path:
    """A host that places orders: it has a gateway state, so silence is measurable."""
    _write(tmp_path, GATEWAY_STATE, json.dumps({"armed": True, "last_reconcile": NOW.isoformat()}))
    # The gateway rewrites its identity verdict every pass; a live box has a fresh one.
    _write(tmp_path, IDENTITY, json.dumps({
        "verdict": "NEW_RISK_OK", "allows_new_risk": True, "ok": True,
        "at": (NOW - timedelta(minutes=1)).isoformat()}))
    return tmp_path


# --------------------------------------------------------------- 1. the fence sees the halt
def test_the_day_the_gold_book_went_quiet_is_a_failure(box: Path) -> None:
    """The measured shape of 2026-09-24: one placement early, then refusals all day."""
    rows = _rows(2, sleeve="gold_asia", reason="placed",
                 start=NOW - timedelta(hours=11), taken=True)
    rows += _rows(398, sleeve="gold_london_am", reason="release_identity_refused",
                  start=NOW - timedelta(hours=6, minutes=38))
    _write(box, LEDGER, "\n".join(rows) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False, doc
    assert doc["verdict"] == "HALTED"
    assert any("gold_london_am" in p for p in doc["problems"]), doc["problems"]
    run = doc["runs"]["gold_london_am"]
    assert run["count"] == 398
    assert run["reason"] == "release_identity_refused"
    assert run["span_h"] is not None and run["span_h"] > fence.TRAILING_HOURS_MAX


def test_a_halt_is_caught_by_duration_even_when_the_row_count_is_small(box: Path) -> None:
    """A gateway that passes every ten minutes writes far fewer rows for the same outage. A
    fence that only counted rows would miss it entirely."""
    _write(box, LEDGER, "\n".join(_rows(
        6, sleeve="gold_afternoon", reason="release_identity_refused",
        start=NOW - timedelta(hours=3), step_s=1800)) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False
    assert doc["runs"]["gold_afternoon"]["count"] < fence.TRAILING_REFUSALS_MAX
    assert any("gold_afternoon" in p for p in doc["problems"])


def test_the_fence_is_not_keyed_to_todays_reason_string(box: Path) -> None:
    """The next halt will carry a different `reason`. A fence written around
    `release_identity_refused` would be silent for it in exactly the same way."""
    _write(box, LEDGER, "\n".join(_rows(
        120, sleeve="gold_asia", reason="some_future_veto_nobody_has_written_yet",
        start=NOW - timedelta(hours=2))) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False
    assert any("some_future_veto_nobody_has_written_yet" in p for p in doc["problems"])


def test_a_placement_clears_the_run(box: Path) -> None:
    """Refusals BEFORE a placement are history, not a halt -- otherwise the fence would stay red
    forever on a ledger that never forgets, and a permanently red fence gets switched off."""
    rows = _rows(300, sleeve="gold_asia", reason="release_identity_refused",
                 start=NOW - timedelta(hours=9))
    rows += _rows(2, sleeve="gold_asia", reason="placed",
                  start=NOW - timedelta(minutes=5), taken=True)
    _write(box, LEDGER, "\n".join(rows) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is True, doc["problems"]
    assert "gold_asia" not in doc["runs"]


def test_the_venues_own_answer_is_reported_not_breached(box: Path) -> None:
    """A run of broker rejections is the market saying no, not the desk declining to trade.
    Breaching on it would teach the desk to treat a rail as a bug."""
    _write(box, LEDGER, "\n".join(_rows(
        90, sleeve="gold_london_am", reason="broker_rejected",
        start=NOW - timedelta(hours=2))) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is True, doc["problems"]
    assert any("broker_rejected" in n for n in doc["notes"])


def test_a_refusing_identity_fails_even_with_no_ledger_rows(box: Path) -> None:
    """Breach (b). The one failure a ledger-shaped fence cannot see is a gateway that stops
    writing rows at all -- so the verdict itself is read directly."""
    _write(box, LEDGER, "\n".join(_rows(
        1, sleeve="gold_asia", reason="placed", start=NOW - timedelta(minutes=2),
        taken=True)) + "\n")
    _write(box, IDENTITY, json.dumps({
        "verdict": "REFUSED", "allows_new_risk": False, "ok": False,
        "at": (NOW - timedelta(minutes=1)).isoformat(),
        "reason": "running f08c1fcf4ab2 carries 139 path(s) the sealed release never named"}))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False
    assert any("refuses new risk" in p for p in doc["problems"]), doc["problems"]


# --------------------------------------------------- 2. applicability: red everywhere is off
def test_a_host_that_places_nothing_is_not_applicable(tmp_path: Path) -> None:
    """CI, a fresh clone and the VPS never place an order. A fence red on every machine that was
    never supposed to trade is a fence somebody switches off (L1.43)."""
    doc = fence.scan(tmp_path, now=NOW)
    assert doc["verdict"] == "NOT_APPLICABLE"
    assert doc["ok"] is True


def test_a_gateway_host_with_no_ledger_is_unmeasured_and_fails(box: Path) -> None:
    """UNMEASURED is a verdict, not a pass (L1.28a, WS-005). No evidence is exactly what the
    outage looked like."""
    doc = fence.scan(box, now=NOW)
    assert doc["verdict"] == "UNMEASURED"
    assert doc["ok"] is False


def test_an_unreadable_ledger_is_unmeasured_not_healthy(box: Path) -> None:
    _write(box, LEDGER, "")
    doc = fence.scan(box, now=NOW)
    assert doc["verdict"] == "UNMEASURED"
    assert doc["ok"] is False


# ------------------------------------------------------------------- 3. the fence is WIRED
def test_the_fence_runs_on_a_clock() -> None:
    """A checker nobody runs is the same silence with more files in it (LAWS III.16). This is
    the assertion that would have failed on 2026-09-23, when the halt was already 17 days old
    and no registered gate looked at the decision ledger at all."""
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert "check_placement_interlock.py" in gate, (
        "check_placement_interlock.py is not registered in run_law_gate.py -- an unwired fence "
        "is a claim the desk cannot cash (L1.49)")


def test_the_fence_never_caps_or_gates_capital() -> None:
    """GROWTH GOVERNANCE. This file may make the book trade MORE by ending halts sooner; it must
    never be the thing that makes it trade less. Nothing here may write a sleeve, a lot or a
    threshold."""
    src = (ROOT / "scripts" / "check_placement_interlock.py").read_text("utf-8")
    for forbidden in ("risk_frac", "heat_floor", "gate_spec", "UNIVERSAL_SURVIVORS"):
        assert forbidden not in src, f"the halt fence must not touch {forbidden}"
    # The sleeve registry is READ (to age out a retired sleeve's run), never written: the one
    # file write in the fence is its own report.
    assert src.count(".write_text(") == 1 and "def write_artifact" in src
    assert "json.dump(" not in src and "open(" not in src


def test_thresholds_are_small_enough_to_catch_the_day_it_happens() -> None:
    """Thirty rows at one a minute is half an hour: short enough that a lost window is caught
    the same session, long enough that one contended seal does not page anybody. If a later
    session widens these, it is choosing to be blind for longer and this says so."""
    assert fence.TRAILING_REFUSALS_MAX <= 60
    assert fence.TRAILING_HOURS_MAX <= 2.0


# ------------------------------------------------------ 4. the halt reaches the event log
def test_a_halt_is_written_to_the_event_log(box: Path, tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """LOUD means every surface: the artifact, the alert ledger AND the event log a dashboard or
    a consumer reads. A clean pass is recorded too, so silence is never the evidence."""
    from libs.ops import events
    log = tmp_path / "events.jsonl"
    monkeypatch.setattr(events, "PATH", log)
    _write(box, LEDGER, "\n".join(_rows(
        45, sleeve="gold_london_am", reason="release_identity_refused",
        start=NOW - timedelta(minutes=45))) + "\n")
    doc = fence.scan(box, now=NOW)
    assert fence.record_event(doc, ROOT) == "PLACEMENT_HALTED"
    row = json.loads(log.read_text("utf-8").splitlines()[-1])
    assert row["kind"] == "PLACEMENT_HALTED"
    assert row["sleeves"] == ["gold_london_am"]
    assert "unknown_kind" not in row

    _write(box, LEDGER, "\n".join(_rows(
        1, sleeve="gold_london_am", reason="placed", start=NOW, taken=True)) + "\n")
    assert fence.record_event(fence.scan(box, now=NOW), ROOT) == "PLACEMENT_CLEAR"
    assert fence.record_event(fence.scan(tmp_path / "nowhere", now=NOW), ROOT) is None


# ----------------------------------------------- 5. audit of PR #130: the four defects, pinned
def _stale_published_copy(root: Path) -> None:
    """What every off-box checkout holds: the box's last PUBLISHED rows, days old."""
    _write(root, GATEWAY_STATE, json.dumps({
        "armed": True, "last_reconcile": "2026-09-11T14:45:00+00:00"}))
    _write(root, LEDGER, "\n".join(_rows(
        600, sleeve="gold_london_am", reason="release_identity_refused",
        start=datetime(2026, 9, 7, 7, 35, tzinfo=UTC))) + "\n")
    _write(root, IDENTITY, json.dumps({
        "verdict": "REFUSED", "allows_new_risk": False, "at": "2026-09-11T14:44:00+00:00"}))


def test_stale_published_rows_off_the_box_are_unmeasured_not_halted(tmp_path: Path) -> None:
    """AUDIT 1. The ledger and gateway state are TRACKED, so every checkout has them. The VPS
    read the box's last published rows (09-07..09-11) as a current halt and its law gate went
    red for good. A ledger whose newest row is past the live window is UNMEASURED -- reported
    so, `ok` None rather than True (not a clean pass), and never HALTED."""
    _stale_published_copy(tmp_path)

    doc = fence.scan(tmp_path, now=NOW)

    assert doc["verdict"] == "UNMEASURED", doc
    assert doc["ok"] is None and doc["applicable"] is False
    assert doc["problems"] == []
    assert any("live window" in n for n in doc["notes"]), doc["notes"]
    assert fence.record_event(doc, ROOT) is None
    assert fence.record_alert(doc, tmp_path) is None


def test_stale_rows_off_the_box_pass_the_gate_and_write_no_committed_report(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    """AUDIT 1 through main(): exit 0 so the VPS law gate is not held red, the output says
    UNMEASURED rather than OK, and the box-state report path is not written off the box."""
    _stale_published_copy(tmp_path)
    out = tmp_path / "report.json"
    monkeypatch.setattr(fence, "ROOT", tmp_path)
    monkeypatch.setattr(fence, "OUT", out)
    _as_host(monkeypatch, OFF_BOX_ID, "ubuntu-4gb-hel1-5")

    assert fence.main([]) == 0
    printed = capsys.readouterr().out
    assert "UNMEASURED" in printed and "HALTED" not in printed
    assert not out.exists()


@pytest.mark.parametrize("as_json", [False, True])
def test_unmeasured_on_the_trading_host_fails(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str], as_json: bool) -> None:
    """A day after the gateway dies its ledger falls out of the live window and the verdict is
    UNMEASURED. Off the box that is exit 0; ON the trading host it must exit non-zero, or the
    fence reads green on the one machine where a silent halt costs money."""
    _stale_published_copy(tmp_path)
    monkeypatch.setattr(fence, "ROOT", tmp_path)
    monkeypatch.setattr(fence, "OUT", tmp_path / "report.json")
    monkeypatch.setattr(fence, "record_alert", lambda doc: None)
    monkeypatch.setattr(fence, "record_event", lambda doc: None)
    _as_host(monkeypatch, BOX_ID, "vmi3571445")

    assert fence.scan(tmp_path, now=NOW)["ok"] is None
    assert fence.main(["--no-write"] + (["--json"] if as_json else [])) == 2
    printed = capsys.readouterr().out
    assert "UNMEASURED" in printed

    _as_host(monkeypatch, OFF_BOX_ID, "ubuntu-4gb-hel1-5")
    assert fence.main(["--no-write"] + (["--json"] if as_json else [])) == 0


def test_the_trading_host_is_the_one_box_evidence_names() -> None:
    from libs.tiers import box_evidence
    assert fence.trading_host() == box_evidence.TRADING_HOST


def test_a_refusal_run_ages_out(box: Path) -> None:
    """AUDIT 2. `age_h` was computed and never read, so a sleeve that stopped trading stayed
    HALTED forever. A run whose last row is older than RUN_MAX_AGE_HOURS is history."""
    rows = _rows(120, sleeve="gold_afternoon", reason="release_identity_refused",
                 start=NOW - timedelta(hours=fence.RUN_MAX_AGE_HOURS + 4))
    rows += _rows(1, sleeve="gold_asia", reason="placed", start=NOW - timedelta(minutes=3),
                  taken=True)
    _write(box, LEDGER, "\n".join(rows) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is True and doc["verdict"] == "OK", doc["problems"]
    run = doc["runs"]["gold_afternoon"]
    assert run["current"] is False and "older than" in run["not_current_because"]
    assert any("gold_afternoon" in n and "history" in n for n in doc["notes"])


def test_a_retired_sleeves_run_is_not_a_current_halt(box: Path) -> None:
    """AUDIT 2. A sleeve the registry no longer holds LIVE is not being refused -- it is not
    being asked. Its run is reported, never breached on; a LIVE sleeve's identical run is."""
    _write(box, fence.SLEEVE_REGISTRY_REL, json.dumps({"sleeves": [
        {"name": "xau_retired", "status": "STANDBY"},
        {"name": "xau_live", "status": "LIVE"}]}))
    rows = _rows(60, sleeve="xau_retired", reason="some_veto", start=NOW - timedelta(hours=1))
    rows += _rows(60, sleeve="xau_live", reason="some_veto", start=NOW - timedelta(hours=1))
    _write(box, LEDGER, "\n".join(rows) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["verdict"] == "HALTED"
    assert doc["runs"]["xau_retired"]["current"] is False
    assert not any("xau_retired" in p for p in doc["problems"]), doc["problems"]
    assert any("xau_live" in p for p in doc["problems"])


def test_a_stale_identity_on_a_live_box_is_loud(box: Path) -> None:
    """AUDIT 3. The identity check went silent once the file was >3h old -- exactly the
    dead-gateway case it exists for. With live ledger evidence, a stale verdict FAILS."""
    _write(box, LEDGER, "\n".join(_rows(
        1, sleeve="gold_asia", reason="placed", start=NOW - timedelta(minutes=2),
        taken=True)) + "\n")
    _write(box, IDENTITY, json.dumps({
        "verdict": "REFUSED", "allows_new_risk": False,
        "at": (NOW - timedelta(hours=fence.IDENTITY_MAX_AGE_HOURS + 5)).isoformat()}))

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False and doc["verdict"] == "IDENTITY_STALE", doc
    assert any("stopped writing" in p for p in doc["problems"]), doc["problems"]


@pytest.mark.parametrize("identity", [None, {"verdict": "NEW_RISK_OK", "allows_new_risk": True}])
def test_a_missing_or_unstamped_identity_on_a_live_box_is_loud(
        box: Path, identity: dict[str, object] | None) -> None:
    """AUDIT 3. No verdict, or one with no timestamp, on a host placing orders is not silence."""
    path = box / Path(*IDENTITY.split("/"))
    if identity is None:
        path.unlink()
    else:
        path.write_text(json.dumps(identity), "utf-8")
    _write(box, LEDGER, "\n".join(_rows(
        1, sleeve="gold_asia", reason="placed", start=NOW - timedelta(minutes=2),
        taken=True)) + "\n")

    doc = fence.scan(box, now=NOW)

    assert doc["ok"] is False and doc["verdict"] == "IDENTITY_STALE", doc


def test_the_report_is_published_on_a_committed_box_state_path() -> None:
    """AUDIT 4. The report sat under the gitignored `**/reports/*`, so it could never reach the
    branch. It now lives on a box-state path that is not ignored, that the box's sync lists in
    $relPaths, and that the seal declares NON_CODE (so publishing it never refuses new risk)."""
    import subprocess

    from libs.ops import release
    rel = fence.OUT_REL
    assert ROOT / Path(*rel.split("/")) == fence.OUT
    ignored = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT, check=False)
    assert ignored.returncode == 1, f"{rel} is gitignored -- the report could never be committed"
    assert release.is_state_path(rel), "a box-written report belongs on a box-state path"
    assert rel in release.NON_CODE
    sync = (ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    block = sync.split("$relPaths = @(", 1)[1].split("\n)", 1)[0]
    assert f'"{rel}"' in block, "the box's sync does not publish the report"


# ------------------------------------ 6. audit follow-ups: identity, UNMEASURED written, hourly
def test_the_trading_host_is_keyed_on_the_machine_id_not_the_hostname(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """FOLLOW-UP 1. The recorded machine id decides; a hostname is a label. Another machine that
    calls itself vmi3571445 is OFF the box, the box renamed is still the box, and an unrecorded
    id is UNMEASURED -- spent on the loud side only when the hostname also matches."""
    _as_host(monkeypatch, BOX_ID, "renamed-box")
    assert fence.on_trading_host() is True
    _as_host(monkeypatch, OFF_BOX_ID, "vmi3571445")
    assert fence.on_trading_host() is False
    _as_host(monkeypatch, OFF_BOX_ID, "vmi3571445", {"hostname": "vmi3571445"})
    assert fence.on_trading_host() is True       # UNMEASURED identity, trading hostname: loud
    _as_host(monkeypatch, None, "ubuntu-4gb-hel1-5")
    assert fence.on_trading_host() is False      # UNMEASURED identity, other hostname


def test_the_fence_reads_the_shared_host_helper() -> None:
    """One answer for every fence: no hostname prefix, no socket, no gateway-state mtime here."""
    src = (ROOT / "scripts" / "check_placement_interlock.py").read_text("utf-8")
    assert "host_identity" in src
    assert "socket" not in src and ".startswith(trading_host" not in src


def test_unmeasured_on_the_box_writes_its_report_alert_and_event(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FOLLOW-UP 2. UNMEASURED on the trading box used to exit 2 and write NOTHING: no report,
    no alert, no event -- a failing verdict nobody could read afterwards. It is written now like
    every other verdict; off the box it still writes nothing (stale published copies)."""
    from libs.ops import events
    _stale_published_copy(tmp_path)
    out = tmp_path / "report.json"
    log = tmp_path / "events.jsonl"
    monkeypatch.setattr(fence, "ROOT", tmp_path)
    monkeypatch.setattr(fence, "OUT", out)
    monkeypatch.setattr(events, "PATH", log)
    _as_host(monkeypatch, BOX_ID, "vmi3571445")

    assert fence.main([]) == 2
    report = json.loads(out.read_text("utf-8"))
    assert report["verdict"] == "UNMEASURED" and report["ok"] is False
    assert report["host"]["verdict"] == "TRADING" and report["host"]["machine_id"] == BOX_ID
    assert any("UNMEASURED on the trading host" in p for p in report["problems"])
    row = json.loads(log.read_text("utf-8").splitlines()[-1])
    assert row["kind"] == "PLACEMENT_UNMEASURED" and row["machine_id"] == BOX_ID
    ledger = json.loads((tmp_path / "data" / "alert_ledger.json").read_text("utf-8"))
    assert fence.ALERT_ID in json.dumps(ledger)

    # Off the box: the same stale rows write no report and no event.
    out.unlink()
    before = log.read_text("utf-8")
    _as_host(monkeypatch, OFF_BOX_ID, "ubuntu-4gb-hel1-5")
    assert fence.main([]) == 0
    assert not out.exists() and log.read_text("utf-8") == before


def test_the_fence_runs_every_hour() -> None:
    """FOLLOW-UP 3. The law gate's `--rotate` rotation reaches a state fence every few hours; a
    halt costs a window an hour. The fence is an hourly_cycle leg on the core plan, in a layer."""
    hc = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("placement_interlock", "scripts/check_placement_interlock.py")' in hc
    assert '_costed("placement_interlock", placement_interlock)' in hc
    assert '"placement_interlock": pil' in hc
    core = hc[hc.index("CORE_LEGS: frozenset[str] = frozenset({"):]
    assert '"placement_interlock"' in core[:core.index("})")]
    from libs.research import layers
    assert layers.LEG_LAYER.get("placement_interlock") == "meta"


# ------------------------------------- 6. the E8 gold lane: its own ledger, judged per day
E8_LEDGER = "desks/mt5/data/e8_decision_ledger.jsonl"
E8_HEARTBEAT = "desks/mt5/data/e8_gold_heartbeat.json"


def _e8_beat(root: Path, *, at: datetime = NOW) -> None:
    _write(root, E8_HEARTBEAT, json.dumps({
        "at": at.isoformat(), "lane": "e8_gold", "status": "OK", "account": "tradelocker:42",
        "host": {"verdict": "TRADING", "hostname": "vmi3571445", "machine_id": BOX_ID}}))


def _e8_rows(root: Path, days: list[tuple[int, str, str]], *, window: str = "afternoon",
             lane: str = "e8_gold") -> None:
    """One decision row per (days_ago, outcome, reason), the way prop/e8_evidence writes them:
    at a decision point, never once a pass."""
    rows = []
    for ago, outcome, reason in days:
        at = NOW - timedelta(days=ago)
        rows.append(json.dumps({
            "decided_at": at.isoformat(), "lane": lane, "account": "tradelocker:42",
            "sleeve": f"e8_gold:{window}", "strategy_id": f"e8_gold:{window}",
            "window": window, "server_date": at.date().isoformat(), "outcome": outcome,
            "reason": reason, "taken": outcome == "PLACED", "host": "vmi3571445"}))
    _write(root, E8_LEDGER, "\n".join(rows) + "\n")


def test_e8_a_one_at_risk_deferral_on_consecutive_days_is_not_a_halt(tmp_path: Path) -> None:
    """The legitimate deferral the lane is built around: reported, never breached on."""
    _e8_beat(tmp_path)
    _e8_rows(tmp_path, [(3, "DEFERRED", "one_at_risk"), (2, "DEFERRED", "one_at_risk"),
                        (1, "DEFERRED", "one_at_risk"), (0, "DEFERRED", "one_at_risk")])
    doc = fence.scan(tmp_path, now=NOW)
    lane = doc["lanes"]["e8_gold"]
    assert lane["verdict"] == "OK" and doc["verdict"] == "NOT_APPLICABLE", lane
    assert lane["runs"]["e8_gold:afternoon@tradelocker:42"]["days"] == 4
    assert any("declared answer" in n for n in lane["notes"])


def test_e8_a_repeated_row_within_one_day_never_breaches(tmp_path: Path) -> None:
    """Even if the lane's dedupe mark were lost and it wrote a row every pass, one server day of
    a breachable reason is one day, not a halt -- the gateway's count/span rules do not apply."""
    _e8_beat(tmp_path)
    rows = [json.dumps({"decided_at": (NOW - timedelta(minutes=5 * i)).isoformat(),
                        "lane": "e8_gold", "sleeve": "e8_gold:asia", "server_date": "2026-09-24",
                        "outcome": "DEFERRED", "reason": "positions_unreadable", "taken": False})
            for i in range(60, 0, -1)]
    _write(tmp_path, E8_LEDGER, "\n".join(rows) + "\n")
    lane = fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]
    assert lane["verdict"] == "OK" and lane["runs"]["e8_gold:asia@UNMEASURED"]["count"] == 60


def test_e8_a_guard_stand_down_two_days_running_is_a_halt(tmp_path: Path) -> None:
    """The 2026-10-15 shape: the guard stood the book down a whole day. Two days is a halt."""
    _e8_beat(tmp_path)
    _e8_rows(tmp_path, [(2, "PLACED", "placed"), (1, "DEFERRED", "guard_stood_down"),
                        (0, "DEFERRED", "guard_stood_down")])
    doc = fence.scan(tmp_path, now=NOW)
    assert doc["ok"] is False and doc["verdict"] == "HALTED" and doc["applicable"] is True
    assert any(p.startswith("[e8_gold] e8_gold:afternoon") and "tradelocker:42" in p
               and "vmi3571445" in p for p in doc["problems"]), doc["problems"]
    assert doc["lanes"]["e8_gold"]["runs"]["e8_gold:afternoon@tradelocker:42"]["breach"] is True


def test_e8_an_unknown_reason_breaches_and_a_placement_clears(tmp_path: Path) -> None:
    _e8_beat(tmp_path)
    _e8_rows(tmp_path, [(1, "DEFERRED", "a_code_nobody_classified"),
                        (0, "DEFERRED", "a_code_nobody_classified")])
    assert fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]["verdict"] == "HALTED"
    _e8_rows(tmp_path, [(1, "DEFERRED", "a_code_nobody_classified"), (0, "PLACED", "placed")])
    assert fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]["verdict"] == "OK"


def test_e8_rows_never_mix_with_the_gateways(box: Path) -> None:
    """A gateway halt stays the gateway's; the E8 lane's rows are judged only under its lane, and
    a row in the E8 file that does not say `lane: e8_gold` is not read as this lane at all."""
    _write(box, LEDGER, "\n".join(_rows(
        45, sleeve="gold_afternoon", reason="release_identity_refused",
        start=NOW - timedelta(minutes=45))) + "\n")
    _e8_beat(box)
    _e8_rows(box, [(1, "DEFERRED", "guard_stood_down"), (0, "DEFERRED", "guard_stood_down")],
             lane="something_else")
    doc = fence.scan(box, now=NOW)
    assert set(doc["runs"]) == {"gold_afternoon"}
    lane = doc["lanes"]["e8_gold"]
    assert lane["verdict"] == "NO_DECISIONS" and lane["runs"] == {}
    assert not any(p.startswith("[e8_gold]") for p in doc["problems"])


def test_e8_ok_never_masks_the_gateways_unmeasured(tmp_path: Path) -> None:
    _stale_published_copy(tmp_path)
    _e8_beat(tmp_path)
    _e8_rows(tmp_path, [(0, "PLACED", "placed")])
    doc = fence.scan(tmp_path, now=NOW)
    assert doc["ok"] is None and doc["verdict"] == "UNMEASURED"
    assert doc["lanes"]["e8_gold"]["verdict"] == "OK"


def test_e8_a_stale_heartbeat_is_unmeasured_and_never_fails(tmp_path: Path) -> None:
    _e8_beat(tmp_path, at=NOW - timedelta(days=3))
    _e8_rows(tmp_path, [(4, "DEFERRED", "guard_stood_down"), (3, "DEFERRED", "guard_stood_down")])
    doc = fence.scan(tmp_path, now=NOW)
    assert doc["lanes"]["e8_gold"]["verdict"] == "UNMEASURED"
    assert doc["ok"] is not False
    assert fence.scan(tmp_path / "nowhere", now=NOW)["lanes"]["e8_gold"]["verdict"] == \
        "NOT_APPLICABLE"


def test_e8_a_halt_reaches_the_event_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import events
    log = tmp_path / "events.jsonl"
    monkeypatch.setattr(events, "PATH", log)
    root = tmp_path / "root"
    _e8_beat(root)
    _e8_rows(root, [(1, "DEFERRED", "risk_unmeasurable"), (0, "DEFERRED", "risk_unmeasurable")])
    assert fence.record_event(fence.scan(root, now=NOW), ROOT) == "PLACEMENT_HALTED"
    row = json.loads(log.read_text("utf-8").splitlines()[-1])
    assert row["sleeves"] == ["e8_gold:afternoon@tradelocker:42"]


# ------------------------------------- 7. v2 (audit of 75004b6a): the two false passes, and more

def _e8_status(root: Path, status: str, *, failing_since: datetime | None = None,
               last_ok_at: datetime | None = None, at: datetime = NOW) -> None:
    _write(root, E8_HEARTBEAT, json.dumps({
        "at": at.isoformat(), "lane": "e8_gold", "status": status,
        "account_ref": "tradelocker:42",
        "failing_since": failing_since.isoformat() if failing_since else None,
        "last_ok_at": last_ok_at.isoformat() if last_ok_at else None,
        "host": {"verdict": "TRADING", "hostname": "vmi3571445", "machine_id": BOX_ID}}))


def test_e8_five_days_of_venue_rejected_with_nothing_placed_is_a_halt(tmp_path: Path) -> None:
    """Must-fix 1, the audit's probe: v1 exempted venue_rejected and read this lane OK."""
    _e8_beat(tmp_path)
    _e8_rows(tmp_path, [(d, "DEFERRED", "venue_rejected") for d in (4, 3, 2, 1, 0)])
    doc = fence.scan(tmp_path, now=NOW)
    lane = doc["lanes"]["e8_gold"]
    assert lane["verdict"] == "HALTED" and doc["verdict"] == "HALTED", lane
    assert "venue_rejected" not in fence.E8_EXEMPT_REASONS


def test_e8_venue_rejected_breaches_only_after_the_trailing_days(tmp_path: Path) -> None:
    _e8_beat(tmp_path)
    _e8_rows(tmp_path, [(0, "DEFERRED", "venue_rejected")])
    assert fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]["verdict"] == "OK"
    _e8_rows(tmp_path, [(d, "DEFERRED", "venue_rejected")
                        for d in range(fence.E8_TRAILING_DAYS_MAX - 1, -1, -1)])
    assert fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]["verdict"] == "HALTED"


def test_e8_a_re_send_that_landed_clears_the_venue_rejected_run(tmp_path: Path) -> None:
    """The re-send's PLACED row (prop/e8_gold._retry_failed_legs, v2) ends the run."""
    _e8_beat(tmp_path)
    _e8_rows(tmp_path, [(2, "DEFERRED", "venue_rejected"), (1, "DEFERRED", "venue_rejected"),
                        (0, "DEFERRED", "venue_rejected"), (0, "PLACED", "placed")])
    assert fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]["verdict"] == "OK"
    # An abandon after nothing ever reached the venue continues the run, and still breaches.
    _e8_rows(tmp_path, [(1, "DEFERRED", "venue_rejected"), (1, "SKIPPED", "venue_rejected"),
                        (0, "DEFERRED", "venue_rejected")])
    assert fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]["verdict"] == "HALTED"


@pytest.mark.parametrize("status", ["MT5_UNAVAILABLE", "VENUE_UNAVAILABLE", "NO_BARS"])
def test_e8_a_failed_pass_heartbeat_is_unmeasured_never_ok(tmp_path: Path, status: str) -> None:
    """Must-fix 2, the audit's probe: a live heartbeat from a failed pass read OK in v1."""
    _e8_status(tmp_path, status, failing_since=NOW - timedelta(minutes=20),
               last_ok_at=NOW - timedelta(minutes=25))
    _e8_rows(tmp_path, [(0, "PLACED", "placed")])
    doc = fence.scan(tmp_path, now=NOW)
    lane = doc["lanes"]["e8_gold"]
    assert lane["verdict"] == "UNMEASURED" and lane["ok"] is None, lane
    assert lane["heartbeat"]["failing_h"] == pytest.approx(1 / 3, abs=1e-3)
    assert doc["ok"] is not False


@pytest.mark.parametrize("status", ["MT5_UNAVAILABLE", "VENUE_UNAVAILABLE", "NO_BARS"])
def test_e8_a_lane_failing_past_the_limit_is_a_halt(tmp_path: Path, status: str) -> None:
    since = NOW - timedelta(hours=fence.E8_FAILING_MAX_HOURS + 1)
    _e8_status(tmp_path, status, failing_since=since, last_ok_at=since - timedelta(minutes=5))
    _e8_rows(tmp_path, [(0, "PLACED", "placed")])
    doc = fence.scan(tmp_path, now=NOW)
    assert doc["verdict"] == "HALTED" and doc["ok"] is False
    assert any(status in p and "has failed" in p for p in doc["problems"]), doc["problems"]


def test_e8_a_failing_lane_with_no_ledger_and_only_last_ok_still_halts(tmp_path: Path) -> None:
    _e8_status(tmp_path, "VENUE_UNAVAILABLE", last_ok_at=NOW - timedelta(days=1))
    assert fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]["verdict"] == "HALTED"


def test_e8_a_v1_failed_heartbeat_with_no_stamps_is_unmeasured(tmp_path: Path) -> None:
    _e8_status(tmp_path, "MT5_UNAVAILABLE")
    assert fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]["verdict"] == "UNMEASURED"


def test_e8_a_failing_lane_halt_reaches_the_event_log(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import events
    log = tmp_path / "events.jsonl"
    monkeypatch.setattr(events, "PATH", log)
    root = tmp_path / "root"
    _e8_status(root, "VENUE_UNAVAILABLE", failing_since=NOW - timedelta(hours=30))
    assert fence.record_event(fence.scan(root, now=NOW), ROOT) == "PLACEMENT_HALTED"
    assert json.loads(log.read_text("utf-8").splitlines()[-1])["sleeves"] == ["e8_gold"]


def test_e8_runs_are_keyed_by_window_and_account(tmp_path: Path) -> None:
    """Should-fix: one day of a breachable reason on each of two accounts is not a two-day run."""
    _e8_beat(tmp_path)
    rows = []
    for ago, acct in ((1, "tradelocker:aaaa"), (0, "tradelocker:bbbb")):
        at = NOW - timedelta(days=ago)
        rows.append(json.dumps({
            "decided_at": at.isoformat(), "lane": "e8_gold", "account_ref": acct,
            "sleeve": "e8_gold:afternoon", "server_date": at.date().isoformat(),
            "outcome": "DEFERRED", "reason": "guard_stood_down", "taken": False}))
    _write(tmp_path, E8_LEDGER, "\n".join(rows) + "\n")
    lane = fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]
    assert lane["verdict"] == "OK", lane
    assert set(lane["runs"]) == {"e8_gold:afternoon@tradelocker:aaaa",
                                 "e8_gold:afternoon@tradelocker:bbbb"}


def test_e8_torn_ledger_lines_are_counted(tmp_path: Path) -> None:
    _e8_beat(tmp_path)
    _e8_rows(tmp_path, [(0, "PLACED", "placed")])
    with (tmp_path / E8_LEDGER).open("a", encoding="utf-8") as fh:
        fh.write('{"decided_at": "2026-09-24T10:00:0\n[1, 2]\n')
    lane = fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]
    assert lane["torn_lines"] == 2 and any("torn" in n for n in lane["notes"])
    assert lane["verdict"] == "OK"


# ------------------------------------- 8. v3 (audit of 6547633a): UNMEASURED is never a pass

def _gateway_ok(box: Path) -> None:
    _write(box, LEDGER, "\n".join(_rows(1, sleeve="gold_asia", reason="placed",
                                        start=NOW - timedelta(minutes=3), taken=True)) + "\n")


def test_e8_unmeasured_folds_into_the_top_level(box: Path, tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """Must-fix 2: gateway OK + an E8 lane failing for 3h published ok=True / PLACEMENT_CLEAR."""
    _gateway_ok(box)
    assert fence.scan(box, now=NOW)["ok"] is True                    # the gateway alone is OK
    _e8_status(box, "VENUE_UNAVAILABLE", failing_since=NOW - timedelta(hours=3))
    doc = fence.scan(box, now=NOW)
    assert doc["lanes"]["e8_gold"]["verdict"] == "UNMEASURED"
    assert doc["ok"] is None and doc["verdict"] == "UNMEASURED" and doc["applicable"] is True
    assert doc["gateway_verdict"] == "OK"
    assert any(n.startswith("[e8_gold] lane UNMEASURED") for n in doc["notes"])
    from libs.ops import events
    monkeypatch.setattr(events, "PATH", tmp_path / "events.jsonl")
    assert fence.record_event(doc, ROOT) is None                     # never PLACEMENT_CLEAR


def test_e8_unmeasured_is_not_escalated_as_a_dead_gateway(box: Path) -> None:
    """Only the GATEWAY's own UNMEASURED is a failure on the trading host; the lane's short
    failures are UNMEASURED by design and its long ones HALTED."""
    _gateway_ok(box)
    _e8_status(box, "NO_BARS", failing_since=NOW - timedelta(hours=1))
    doc = fence.scan(box, now=NOW)

    class _Ident:
        trading_hostname, verdict, why = "vmi3571445", "TRADING", "test"

    assert fence.escalate_unmeasured(doc, _Ident())["ok"] is None   # type: ignore[arg-type]
    assert "escalated_on_trading_host" not in doc


def test_a_halted_e8_lane_whose_heartbeat_goes_stale_keeps_its_alert(box: Path) -> None:
    """Must-fix 2b: the alert opened on a HALT is not closed as FIXED by a stale heartbeat."""
    from libs.ops.alert_ledger import AlertLedger
    _gateway_ok(box)
    _e8_beat(box)
    _e8_rows(box, [(1, "DEFERRED", "guard_stood_down"), (0, "DEFERRED", "guard_stood_down")])
    assert fence.record_alert(fence.scan(box, now=NOW), box) == "OPEN"
    _e8_beat(box, at=NOW - timedelta(days=3))                       # the lane goes quiet
    doc = fence.scan(box, now=NOW)
    assert doc["lanes"]["e8_gold"]["verdict"] == "UNMEASURED" and doc["ok"] is None
    assert fence.record_alert(doc, box) is None
    assert AlertLedger(box / "data" / "alert_ledger.json").alerts[fence.ALERT_ID].open
    # ...and even a doc some other path marked ok is not evidence while a lane is unreadable.
    assert fence.record_alert({**doc, "ok": True}, box) is None


def test_e8_unkeyed_rows_never_join_a_run_and_read_unmeasured(tmp_path: Path) -> None:
    """Should-fix: every UNKEYED row is its own run key (two accounts cannot be told apart), and
    a window whose newest row is UNKEYED is UNMEASURED, never OK."""
    _e8_beat(tmp_path)
    rows = []
    for ago in (2, 1, 0):
        at = NOW - timedelta(days=ago)
        rows.append(json.dumps({
            "decided_at": at.isoformat(), "lane": "e8_gold", "account_ref": "tradelocker:UNKEYED",
            "sleeve": "e8_gold:afternoon", "server_date": at.date().isoformat(),
            "outcome": "DEFERRED", "reason": "guard_stood_down", "taken": False}))
    _write(tmp_path, E8_LEDGER, "\n".join(rows) + "\n")
    lane = fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]
    assert len(lane["runs"]) == 3 and all(r["days"] == 1 for r in lane["runs"].values())
    assert lane["verdict"] == "UNMEASURED" and lane["unkeyed_windows"] == ["e8_gold:afternoon"]
    # A keyed row after them is judged normally again.
    rows.append(json.dumps({
        "decided_at": NOW.isoformat(), "lane": "e8_gold", "account_ref": "tradelocker:42",
        "sleeve": "e8_gold:afternoon", "server_date": NOW.date().isoformat(),
        "outcome": "PLACED", "reason": "placed", "taken": True}))
    _write(tmp_path, E8_LEDGER, "\n".join(rows) + "\n")
    assert fence.scan(tmp_path, now=NOW)["lanes"]["e8_gold"]["verdict"] == "OK"

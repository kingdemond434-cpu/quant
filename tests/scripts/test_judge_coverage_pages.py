"""A RED JUDGE-COVERAGE CHECK PAGES, once per incident (2026-10-20).

The box-side run (`check_judge_coverage.py --require-state`) pages through the existing sender,
deduplicated by a persisted incident key in a box-local state file; the portable run never pages;
and the verdict, printed lines, audit and exit code are exactly what they were. The channel is
always mocked here: no test reaches a network or reads a credential.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
ENV = "QUANT_LAWGATE_SOURCE_VIEW"
NOW = datetime(2026, 10, 20, 23, 0, tzinfo=UTC)


@pytest.fixture
def fence(monkeypatch) -> ModuleType:
    monkeypatch.delenv(ENV, raising=False)
    spec = importlib.util.spec_from_file_location("judge_coverage_pages",
                                                  REPO / "scripts/check_judge_coverage.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Channel:
    def __init__(self, result: dict[str, Any] | None = None, raises: bool = False) -> None:
        self.sent: list[tuple[str, str]] = []
        self.result = result if result is not None else {"armed": 1, "delivered": 1}
        self.raises = raises

    def __call__(self, title: str, body: str) -> dict[str, Any]:
        self.sent.append((title, body))
        if self.raises:
            raise OSError("channel down")
        return dict(self.result)


def _report(at: datetime, *, red: bool = False, judged: int = 5) -> dict[str, Any]:
    fam = {"unjudged": 10, "queued": 0 if red else 3, "judged_window": judged}
    return {"at": at.isoformat(), "families": {"overnight_drift": fam}}


def _pass(fence, tmp_path: Path, rep: dict[str, Any], now: datetime, ch: Channel) -> dict:
    path = tmp_path / "JUDGE_COVERAGE.json"
    path.write_text(json.dumps(rep), "utf-8")
    doc = fence.judge(path, require_state=True, now=now)
    return fence.page_coverage(doc, rep, root=tmp_path, now=now, sender=ch)


def test_red_pages_once_then_dedupes_then_resolve_and_recur_pages_again(fence, tmp_path):
    ch = Channel()
    first = _pass(fence, tmp_path, _report(NOW, red=True), NOW, ch)
    assert first["sent"] and first["opened"] == ["red"]
    assert len(ch.sent) == 1 and ch.sent[0][0].startswith("JUDGE COVERAGE RED")
    state = json.loads((tmp_path / fence.PAGE_STATE_REL).read_text("utf-8"))
    assert state["open"]["red"]["incident"] == f"judge_coverage:red@{NOW.isoformat()}"

    t2 = NOW + timedelta(minutes=40)
    again = _pass(fence, tmp_path, _report(t2, red=True), t2, ch)
    assert not again["sent"] and len(ch.sent) == 1          # second red: no page

    t3 = t2 + timedelta(minutes=40)
    ok = _pass(fence, tmp_path, _report(t3), t3, ch)
    assert ok["resolved"] == ["red"] and len(ch.sent) == 2
    assert ch.sent[1][0] == "JUDGE COVERAGE RESOLVED: red"

    t4 = t3 + timedelta(minutes=40)
    quiet = _pass(fence, tmp_path, _report(t4), t4, ch)
    assert not quiet["sent"] and len(ch.sent) == 2          # green stays quiet

    t5 = t4 + timedelta(minutes=40)
    recur = _pass(fence, tmp_path, _report(t5, red=True), t5, ch)
    assert recur["opened"] == ["red"] and len(ch.sent) == 3
    state = json.loads((tmp_path / fence.PAGE_STATE_REL).read_text("utf-8"))
    assert state["open"]["red"]["incident"] == f"judge_coverage:red@{t5.isoformat()}"


def test_a_standing_red_is_reminded_after_the_desk_interval(fence, tmp_path):
    ch = Channel()
    _pass(fence, tmp_path, _report(NOW, red=True), NOW, ch)
    t = NOW + timedelta(hours=fence.REPAGE_H - 0.1)
    _pass(fence, tmp_path, _report(t, red=True), t, ch)
    assert len(ch.sent) == 1
    t = NOW + timedelta(hours=fence.REPAGE_H)
    rem = _pass(fence, tmp_path, _report(t, red=True), t, ch)
    assert rem["reminded"] == ["red"] and len(ch.sent) == 2
    assert fence.REPAGE_H == 6.0


def test_a_stale_report_pages_tonights_stall(fence, tmp_path):
    ch = Channel()
    stalled_at = NOW - timedelta(hours=fence.STALE_H + 0.5)       # 19:44Z-style silence
    out = _pass(fence, tmp_path, _report(stalled_at), NOW, ch)
    assert "stale" in out["opened"] and out["sent"]
    assert "stale" in ch.sent[0][0]
    t = NOW + timedelta(minutes=30)
    _pass(fence, tmp_path, _report(stalled_at), t, ch)
    assert len(ch.sent) == 1


def test_zero_verdicts_in_a_full_window_pages(fence, tmp_path):
    ch = Channel()
    out = _pass(fence, tmp_path, _report(NOW - timedelta(minutes=5), judged=0), NOW, ch)
    assert out["opened"] == ["zero_judged"] and len(ch.sent) == 1
    assert ch.sent[0][0] == "JUDGE COVERAGE ALERT: zero_judged"


def test_a_failed_send_is_recorded_and_retried_and_never_raises(fence, tmp_path):
    ch = Channel(raises=True)
    out = _pass(fence, tmp_path, _report(NOW, red=True), NOW, ch)
    assert not out["sent"] and out["error"].startswith("OSError")
    state = json.loads((tmp_path / fence.PAGE_STATE_REL).read_text("utf-8"))
    assert "paged_at" not in state["open"]["red"] and state["open"]["red"]["last_error"]
    ch.raises = False
    t = NOW + timedelta(minutes=40)
    retry = _pass(fence, tmp_path, _report(t, red=True), t, ch)
    assert retry["sent"] and retry["reminded"] == ["red"] and len(ch.sent) == 2


def test_the_pager_never_raises_even_on_garbage(fence, tmp_path):
    (tmp_path / fence.PAGE_STATE_REL).parent.mkdir(parents=True)
    (tmp_path / fence.PAGE_STATE_REL).write_text("{not json")
    out = fence.page_coverage({"verdict": "FAIL", "checks": "x"}, object(), root=tmp_path,
                              now=NOW, sender=Channel())
    assert isinstance(out, dict)


def strip(blob: str | bytes) -> dict[str, Any]:
    """A reading minus its wall-clock stamp, the only field two runs may differ in."""
    return {k: v for k, v in json.loads(blob).items() if k != "at"}


def _run_main(fence, tmp_path, monkeypatch, capsys, argv: list[str], rep: dict) -> tuple:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps(rep), "utf-8")
    monkeypatch.setattr(fence, "REPORT", report)
    monkeypatch.setattr(fence, "ROOT", tmp_path)
    ch = Channel()
    monkeypatch.setattr(fence, "_default_page_sender", lambda root: ch)
    audit = tmp_path / "audit.json"
    rc = fence.main([*argv, "--audit", str(audit), "--json"])
    printed = capsys.readouterr().out
    return rc, printed, audit.read_bytes() if audit.exists() else None, ch


def test_the_portable_run_never_pages(fence, tmp_path, monkeypatch, capsys):
    rep = _report(datetime.now(tz=UTC), red=True)
    _, _, _, ch = _run_main(fence, tmp_path, monkeypatch, capsys, [], rep)
    assert ch.sent == []
    monkeypatch.setenv(ENV, "1")
    _, _, _, ch = _run_main(fence, tmp_path, monkeypatch, capsys, [], rep)
    assert ch.sent == []
    # an explicit --report is not the box's own report
    monkeypatch.delenv(ENV)
    report = tmp_path / "other.json"
    report.write_text(json.dumps(rep), "utf-8")
    _, _, _, ch = _run_main(fence, tmp_path, monkeypatch, capsys,
                            ["--require-state", "--report", str(report)], rep)
    assert ch.sent == []
    assert not (tmp_path / fence.PAGE_STATE_REL).exists()


def test_the_box_run_pages_and_the_verdict_is_byte_identical(fence, tmp_path, monkeypatch,
                                                              capsys):
    rep = _report(datetime.now(tz=UTC), red=True)
    rc, printed, audit, ch = _run_main(fence, tmp_path, monkeypatch, capsys,
                                       ["--require-state"], rep)
    assert len(ch.sent) == 1 and rc == 1
    # the same run with the pager disabled: same exit, same stdout, same audit
    monkeypatch.setattr(fence, "_box_pages", lambda args: False)
    rc2, printed2, audit2, _ = _run_main(fence, tmp_path, monkeypatch, capsys,
                                         ["--require-state"], rep)
    assert rc2 == rc
    assert strip(printed2) == strip(printed)
    assert audit is not None and audit2 is not None and strip(audit2) == strip(audit)
    # and a pager that explodes changes nothing either
    monkeypatch.setattr(fence, "_box_pages", lambda args: True)
    monkeypatch.setattr(fence, "_page_coverage",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    rc3, printed3, _, _ = _run_main(fence, tmp_path, monkeypatch, capsys,
                                    ["--require-state"], rep)
    assert rc3 == rc and strip(printed3) == strip(printed)


def test_unmeasured_neither_pages_nor_clears(fence, tmp_path):
    ch = Channel()
    _pass(fence, tmp_path, _report(NOW, red=True), NOW, ch)
    out = fence.page_coverage({"verdict": "UNMEASURED"}, None, root=tmp_path, now=NOW,
                              sender=ch)
    assert not out["sent"] and len(ch.sent) == 1
    state = json.loads((tmp_path / fence.PAGE_STATE_REL).read_text("utf-8"))
    assert "red" in state["open"]

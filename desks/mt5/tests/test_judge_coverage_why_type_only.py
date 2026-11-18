"""JUDGE_COVERAGE.json publishes an exception's TYPE, never its text.

An exception message can carry a filesystem path, a host or a credential. Every `why` that
judge_coverage builds from a caught exception is therefore `type(exc).__name__` alone.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import judge_coverage as coverage  # noqa: E402

SECRET = "fake-token-for-test-only"  # noqa: S105 - a stand-in, not a credential
HOST = "db.internal.example"


class _Leaky(Exception):
    pass


def _assert_type_only(why: object, name: str) -> None:
    text = str(why)
    assert text == name or text.endswith(f": {name}") or text == f"save failed: {name}", text
    assert SECRET not in text and HOST not in text and "/data/secrets" not in text


def test_missing_ledger_publishes_only_the_error_type(tmp_path: Path) -> None:
    ledger = tmp_path / "data" / "secrets" / HOST / f"{SECRET}.jsonl"   # never created
    out = coverage.learn_priors(ledger, limit=coverage.LEARN_TAIL + 1, state_dir=tmp_path)
    assert out["status"] == "UNMEASURED"
    _assert_type_only(out["why"], "FileNotFoundError")


def test_a_raising_scorer_publishes_only_the_error_type(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Dk:
        @staticmethod
        def score(rows: object) -> dict[str, object]:
            raise _Leaky(f"connect https://{HOST}/data/secrets/key={SECRET} failed")

    monkeypatch.setattr(coverage, "_docket_keff", lambda: _Dk)
    out = coverage.keff_stamp([{"_keff": 1.0}])
    assert out["status"] == "UNMEASURED"
    _assert_type_only(out["why"], "_Leaky")


def test_no_except_handler_formats_the_exception_into_a_why() -> None:
    """Source guard: inside every `except ... as exc`, a `why` value may name the type only."""
    tree = ast.parse(Path(coverage.__file__).read_text("utf-8"))
    leaks: list[int] = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler) or not handler.name:
            continue
        bound = handler.name
        for node in ast.walk(handler):
            values: list[ast.AST] = []
            if isinstance(node, ast.keyword) and node.arg == "why":
                values.append(node.value)
            if isinstance(node, ast.Dict):
                values += [v for k, v in zip(node.keys, node.values, strict=True)
                           if isinstance(k, ast.Constant) and k.value == "why"]
            for v in values:
                for sub in ast.walk(v):
                    if isinstance(sub, ast.Name) and sub.id == bound:
                        parent_ok = any(
                            isinstance(p, ast.Call) and isinstance(p.func, ast.Name)
                            and p.func.id == "type" and p.args and p.args[0] is sub
                            for p in ast.walk(v))
                        if not parent_ok:
                            leaks.append(sub.lineno)
    assert not leaks, f"exception text reaches a published `why` at lines {leaks}"


# ------------------------------------------- the WRITTEN report, end to end (audit, 2026-11-18)

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import pytest  # noqa: E402
import test_build_input_probe as bip  # noqa: E402
from test_build_input_probe import uni  # noqa: E402,F401 - the tmp bar store fixture

#: Everything an exception message could carry that must never reach JUDGE_COVERAGE.json.
LEAK_PATH = "/data/secrets/broker"


def _leak_message() -> str:
    return f"connect https://{HOST}{LEAK_PATH}/key={SECRET} failed"


def _assert_report_clean(text: str, tmp_path: Path) -> None:
    for needle in (SECRET, HOST, LEAK_PATH, "connect https://", str(tmp_path / "secrets")):
        assert needle not in text, f"{needle!r} reached the written report"


def _raise_leaky(*_a: object, **_k: object) -> object:
    raise _Leaky(_leak_message())


def _inject_everywhere(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Every exception the pass catches carries a secret, a path and a host."""
    import importlib

    from research import build_input_probe as probe
    from research import fire_inputs

    # The prescreen's reports stay under tmp in BOTH module spellings `_prescreen` may import.
    monkeypatch.syspath_prepend(str(DESK / "research"))
    for name in ("judge_prescreen", "research.judge_prescreen"):
        jp = importlib.import_module(name)
        for attr in ("INTAKE_REPORT", "REPORT"):
            cur = getattr(jp, attr, None)
            if isinstance(cur, Path):
                monkeypatch.setattr(jp, attr, tmp_path / f"prescreen_{cur.name}")

    class _Dk:
        score = staticmethod(_raise_leaky)

    class _Om:
        load = staticmethod(_raise_leaky)
        stamp = staticmethod(_raise_leaky)

    # learn_priors: the ledger is missing, and FileNotFoundError's text IS the path
    monkeypatch.setattr(coverage, "GATE_LEDGER",
                        tmp_path / "secrets" / HOST / f"{SECRET}.jsonl")
    monkeypatch.setattr(coverage, "_docket_keff", lambda: _Dk)
    monkeypatch.setattr(coverage, "_occupancy_map", lambda: _Om)
    monkeypatch.setattr(fire_inputs, "_paths", _raise_leaky)
    monkeypatch.setattr(probe, "probe_row", _raise_leaky)


def test_no_exception_text_reaches_the_written_report(
        uni: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    _inject_everywhere(monkeypatch, tmp_path)
    rows = [bip._row("EURGBP", "lead_lag", {"driver_symbol": "AUDNZD"}),
            bip._row("EURUSD", "carry", {}),
            bip._row("XAUUSD", "cot_positioning", {}),
            bip._row("EURUSD", "event_reaction", {})]
    _out, doc = coverage.order_docket([dict(r) for r in rows], publish=True, now=bip.NOW)
    report = coverage.REPORT
    assert report.exists(), doc.get("why")
    text = report.read_text("utf-8")
    assert "_Leaky" in text or "FileNotFoundError" in text, "the injected faults were reached"
    _assert_report_clean(text, tmp_path)
    _assert_report_clean(json.dumps(doc, default=str), tmp_path)


def test_a_failed_pass_returns_and_writes_only_the_error_type(
        uni: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    _inject_everywhere(monkeypatch, tmp_path)
    monkeypatch.setattr(coverage, "fireability_order", _raise_leaky)
    rows = [bip._row("EURUSD", "carry", {})]
    _out, doc = coverage.order_docket([dict(r) for r in rows], publish=True, now=bip.NOW)
    assert doc == {"verdict": "UNMEASURED", "why": "_Leaky"}
    if coverage.REPORT.exists():
        _assert_report_clean(coverage.REPORT.read_text("utf-8"), tmp_path)


def test_the_probe_modules_name_the_type_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """The two `why`s that ride INTO the pass from build_input_probe and fire_inputs."""
    from research import build_input_probe as probe
    from research import fire_inputs

    monkeypatch.setattr(fire_inputs, "_paths", _raise_leaky)
    got = fire_inputs.probe("XAUUSD", "cot_positioning")
    assert got == {"status": fire_inputs.UNMEASURED, "why": "_Leaky"}

    monkeypatch.setattr(probe, "_Pass", _raise_leaky)
    _named, census = probe.name([], judged=set(), bank={}, banned=())
    assert census["why"] == "_Leaky"
    _assert_report_clean(json.dumps(census), Path("/nonexistent"))

"""DESK_HEALTH.json RIDES THE SYNC TO THE PUBLIC REPOSITORY: NO LOCAL PATH, NO RAW EXCEPTION TEXT.

BARS_STATE v2.2. `check_desk_health.py --out` writes desks/mt5/reports/DESK_HEALTH.json, which
sync_shadow_to_git.ps1 publishes. Its findings used to interpolate `{exc}` (whose text carries the
path that failed) and its `desk_root` was the absolute checkout. Now every error finding says the
exception's type and errno only, `desk_root` is repo-relative, and `report()` passes every string
through `_publishable`. These tests fuzz every error branch with an exception whose message holds
a Windows path, a UNC share and a POSIX path, run the whole `main()` against a temporary desk, and
read the published file back.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desks" / "mt5" / "scripts" / "check_desk_health.py"

WIN = r"C:\Users\someone\quant\secret_account_dir\data\file.json"
UNC = r"\\fileserver\share\quant\data"
POSIX = "/home/someone/quant/secret_account_dir/data/file.json"
RAW = f"boom: could not read {WIN} via {UNC} or {POSIX} (raw parser text 'Expecting value')"

#: What an absolute path looks like in a published string (v2.3, stricter than the code's own
#: rule is allowed to be lax): a `/` + path character after anything but a word character, a dot,
#: a colon, a slash or a desk/repo placeholder; a drive letter anywhere (not a URL's `s://`); or a
#: backslash pair.
_ABSOLUTE = re.compile(r"(?<![\w.:/])(?<!<desk_root>)(?<!<repo>)/\w"
                       r"|[A-Za-z]:(?:\\|/(?!/))|\\\\")


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("_quant_desk_health_paths", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def health(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    mod = _load()
    repo = tmp_path / "repo"
    desk = repo / "desks" / "mt5"
    for sub in ("data", "reports"):
        (desk / sub).mkdir(parents=True)
    monkeypatch.setattr(mod, "DESK", desk)
    monkeypatch.setattr(mod, "ROOT", repo)
    monkeypatch.chdir(tmp_path)          # main() chdirs into DESK; this restores the cwd after
    mod._FINDINGS.clear()
    return mod


def _strings(obj: Any) -> list[str]:
    if isinstance(obj, dict):
        return [s for k, v in obj.items() for s in (*_strings(k), *_strings(v))]
    if isinstance(obj, list):
        return [s for v in obj for s in _strings(v)]
    return [obj] if isinstance(obj, str) else []


def _assert_clean(doc: dict[str, Any], *local_roots: Path) -> None:
    for s in _strings(doc):
        assert not _ABSOLUTE.search(s), f"absolute path published: {s!r}"
        for root in local_roots:
            assert str(root) not in s and root.as_posix() not in s, s
        for fragment in ("boom", "secret_account_dir", "Expecting value", "fileserver"):
            assert fragment not in s, f"raw exception text published: {s!r}"


class _Fuzzed(json.JSONDecodeError):
    pass


def _raise(*_a: Any, **_k: Any) -> Any:
    raise OSError(13, RAW, WIN)


def test_the_path_regex_this_file_relies_on_actually_matches_paths() -> None:
    for s in (WIN, UNC, POSIX, "C:/x", f"read ({POSIX})", "x '/etc/passwd'", "a-/home/u",
              "x>/home/u", "aC:\\Users", "~/x"):
        assert _ABSOLUTE.search(s), s
    for s in ("data/BARS_STATE.json", "n/a", "8/12", "https://dash.example/x",
              "PermissionError errno=13", "desks/mt5"):
        assert not _ABSOLUTE.search(s), s


def test_publishable_strips_every_root_form(health: Any) -> None:
    d = health.DESK
    for raw in (f"{d}/data/x.json", str(d / "data"), WIN, UNC, POSIX, f"see ({POSIX}) now",
                f"a {WIN} b {UNC} c"):
        out = health._publishable(raw)
        assert not _ABSOLUTE.search(out) and str(d) not in out, (raw, out)
    keep = "data/BARS_STATE.json is 3.1h old -- n/a; 8/12 at https://dash.example/x"
    assert health._publishable(keep) == keep


def test_every_error_branch_publishes_type_and_errno_only(health: Any,
                                                          monkeypatch: pytest.MonkeyPatch,
                                                          ) -> None:
    desk = health.DESK
    for rel in ("data/BARS_STATE.json", "reports/BOX_STATE_FLOW.json", "data/stall_watch.json",
                "data/gateway_state.json"):
        (desk / rel).write_text("{}", "utf-8")
    readers = (health.check_bars_state, health.check_state_flow,
               health.check_stall_watch_alerts, health.check_gateway_state)
    # Every read raises an OSError whose message and filename are paths (the OSError branch) ...
    with monkeypatch.context() as m:
        m.setattr(Path, "read_text", _raise)
        for check in readers:
            check()
    # ... then a JSON decode error carrying the same text (the ValueError branch).
    def loads(*_a: Any, **_k: Any) -> Any:
        raise _Fuzzed(RAW, POSIX, 0)
    with monkeypatch.context() as m:
        m.setattr(health.json, "loads", loads)
        for check in readers:
            check()
    # check_artifacts' stat failure on files that exist.
    with monkeypatch.context() as m:
        m.setattr(Path, "exists", lambda self: True)
        m.setattr(Path, "stat", _raise)
        health.check_artifacts()
    # _run's subprocess failure (its text reaches findings through check_python / check_tasks).
    with monkeypatch.context() as m:
        m.setattr(subprocess, "run", _raise)
        assert health._run(["py", "-3"]) == (124, "PermissionError errno=13")
    unknown = [f for f in health._FINDINGS if f["level"] == "UNKNOWN"]
    assert len(unknown) >= 8 + len(health.ARTIFACTS), health._FINDINGS
    for f in unknown:
        assert re.search(r"\((?:[A-Za-z]+Error|_Fuzzed)( errno=\d+)?\)", f["message"]), f
    _assert_clean(health.report("2026-10-21T12:00:00+00:00"), desk, health.ROOT)


def test_the_interpreter_path_is_not_published(health: Any, monkeypatch: pytest.MonkeyPatch
                                               ) -> None:
    monkeypatch.setattr(health, "_run", lambda *a, **k: (0, r"C:\Python313\python.exe"))
    health.check_python()
    assert health._FINDINGS[-1]["message"] == "`py -3` resolves to python.exe"


def test_quoted_text_from_other_organs_is_scrubbed_too(health: Any) -> None:
    (health.DESK / "reports" / "BOX_STATE_FLOW.json").write_text(json.dumps({
        "verdict": "STALLED", "why": f"push refused at {health.DESK}\\data",
        "sync_log": {"last_refusal_line": f"error: {WIN} {POSIX}"},
        "alerts": {"line": f"no channel in {UNC}"}}), "utf-8")
    health.check_state_flow()
    _assert_clean(health.report("t"), health.DESK, health.ROOT)


def test_the_whole_published_report_has_no_local_path(health: Any, tmp_path: Path) -> None:
    desk = health.DESK
    (desk / "data" / "stall_watch.json").mkdir()          # IsADirectoryError, with its path
    (desk / "data" / "gateway_state.json").write_text("{not json at " + POSIX, "utf-8")
    (desk / "reports" / "BOX_STATE_FLOW.json").write_bytes(b"\xff\xfe" + WIN.encode())
    out = tmp_path / "out" / "DESK_HEALTH.json"
    assert health.main(["--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["desk_root"] == "desks/mt5"
    assert doc["findings"], "the report must still carry its findings"
    _assert_clean(doc, desk, health.ROOT, tmp_path)


def test_the_source_never_interpolates_an_exception() -> None:
    src = SCRIPT.read_text("utf-8")
    assert not re.search(r"\{exc(?:!r|!s)?\}|str\(exc\)", src.replace(
        "never str(exc)", "")), "a finding interpolates raw exception text"
    assert '"desk_root": str(DESK)' not in src


# ------------------------------------------------------------------ v2.3: the regex's own gaps
#: Hostile shapes the v2.2 regex let through: a path with SPACES leaked its tail, and a `/` after
#: `-`, `>` or `~`, or a drive letter glued to a word, was not a root at all.
HOSTILE = (
    r"C:\Program Files\Quant Desk\tailsecret one\file.json",
    "C:/Program Files/Quant Desk/tailsecret two.json",
    r"\\fileserver\my share\tailsecret three",
    "/home/some one/tailsecret four/x.json",
    "a-/home/u/tailsecret five",
    "x>/home/u/tailsecret six",
    "~/tailsecret seven/x",
    "aC:\\Users\\tailsecret eight",
    "file:///home/u/tailsecret nine",
    "(/opt/My Desk/tailsecret ten)",
    "<desk_root>/../../home/tailsecret eleven",
)


@pytest.mark.parametrize("hostile", HOSTILE)
def test_v23_a_path_never_leaks_its_tail_or_slips_the_lookbehind(health: Any,
                                                                 hostile: str) -> None:
    out = health._publishable(f"push refused: {hostile} -- retry later")
    assert "tailsecret" not in out and not _ABSOLUTE.search(out), out
    assert out.startswith("push refused: "), "the text before the root survives"


@pytest.mark.parametrize("hostile", HOSTILE)
def test_v23_the_alert_and_sync_lines_never_leak_a_path(health: Any, hostile: str) -> None:
    """The lines check_state_flow and check_stall_watch_alerts quote verbatim from other organs."""
    (health.DESK / "reports" / "BOX_STATE_FLOW.json").write_text(json.dumps({
        "verdict": "STALLED", "why": f"why {hostile}",
        "local_commits_not_on_origin": f"3 at {hostile}",
        "sync_log": {"last_refusal_line": f"refused {hostile}"},
        "alerts": {"line": f"no channel {hostile}"}}), "utf-8")
    (health.DESK / "data" / "stall_watch.json").write_text(json.dumps({
        "alerts_line": f"stall {hostile}", "checked_at": hostile,
        "state_flow_watch": hostile}), "utf-8")
    health.check_state_flow()
    health.check_stall_watch_alerts()
    doc = health.report("t")
    assert len(doc["findings"]) >= 3
    for s in _strings(doc):
        assert "tailsecret" not in s and not _ABSOLUTE.search(s), s


def test_v23_sentinels_cannot_be_forged_and_relative_text_survives(health: Any) -> None:
    # A forged sentinel is stripped of its NULs, so it can never shield an absolute path as a
    # "<desk_root>/..." tail: what is left is the forger's own relative text, or <path>.
    for forged in ("\x00D\x00/home/u/tailsecret", "x \x00D\x00 /home/u/tailsecret",
                   "\x00R\x00C:\\Users\\tailsecret"):
        out = health._publishable(forged)
        assert "\x00" not in out and "<desk_root>" not in out and "<repo>" not in out, out
        assert not _ABSOLUTE.search(out), out
    assert health._publishable("x \x00D\x00 /home/u/tailsecret") == "x D <path>"
    d = health.DESK
    assert health._publishable(f"{d}/data/My File.json old") == "<desk_root>/data/My File.json old"
    keep = ("data/BARS_STATE.json is 3.1h old -- n/a; 8/12 at https://dash.example/x and / or "
            "MT5-Hourly 12:00:00")
    assert health._publishable(keep) == keep

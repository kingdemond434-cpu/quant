"""The publish-allowlist leg of replay-shadow (Governance ruling 2026-11-17 20:45Z).

sync_shadow_to_git.ps1 is money path and the replay never runs it, so a PR that only adds a report
to the list the box publishes read UNMEASURED for ever. allowlist_problems() measures it statically:
only literal JSON report paths added inside `$reportPaths`, under the base's STATE_PREFIXES,
never governed state or a secret-shaped name, each with its exact `!path` .gitignore line, and no
added line carrying a host, path, number, amount or key. Every other change stays UNMEASURED.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "replay_shadow_allowlist", ROOT / "ops/release/replay_shadow.py"
)
assert _spec is not None and _spec.loader is not None
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

SYNC = rs.SYNC_SCRIPT
RELEASE = """
IMMUTABLE_MANIFEST = "desks/mt5/data/IMMUTABLE_MANIFEST.json"
STATE_PREFIXES: tuple[str, ...] = ("desks/mt5/data/", "desks/mt5/reports/")
GOVERNED_STATE_FILES: frozenset[str] = frozenset({
    IMMUTABLE_MANIFEST, "desks/mt5/data/LIVE_MANIFEST.jsonl",
})
GOVERNED_STATE_GLOBS: tuple[str, ...] = ("desks/mt5/data/*_ENABLED*",)
"""
BASE_ENTRIES = [
    "    # the swap capture age",
    '    "desks/mt5/reports/A.json",',
    "    # a -> b, measured",
    '    "desks/mt5/data/b.pkl"',
]
NEW = "desks/mt5/reports/DAILY_FILLS.json"


def _script(
    entries: list[str], head: str = "$x = 1", tail: str = "foreach ($r in $reportPaths) {}"
) -> str:
    return "\r\n".join([head, "$reportPaths = @(", *entries, ")", tail]) + "\r\n"


def _tree(root: Path, entries: list[str], gitignore: list[str], **kw: str) -> Path:
    (root / "desks/mt5/scripts").mkdir(parents=True)
    (root / "libs/ops").mkdir(parents=True)
    (root / SYNC).write_bytes(_script(entries, **kw).encode())
    (root / ".gitignore").write_text("\n".join(gitignore) + "\n", "utf-8")
    (root / rs.RELEASE_PY).write_text(RELEASE, "utf-8")
    return root


def _added(
    *paths: str, comment: str = "    # DID EACH ACCOUNT FILL TODAY (2026-11-18, ops/daily_fills.py)"
) -> list[str]:
    """The base list with `paths` appended at its end, commas moved as PowerShell needs."""
    return [*BASE_ENTRIES[:-1], BASE_ENTRIES[-1] + ",", comment,
            *[f'    "{p}",' for p in paths[:-1]], f'    "{paths[-1]}"']  # fmt: skip


def _judge(
    tmp_path: Path,
    head_entries: list[str],
    head_gi: list[str] | None = None,
    *,
    head: str = "$x = 1",
    tail: str = "foreach ($r in $reportPaths) {}",
) -> list[str]:
    gi = [f"!{NEW}"] if head_gi is None else head_gi
    b = _tree(tmp_path / "base", BASE_ENTRIES, ["*.json"])
    h = _tree(tmp_path / "head", head_entries, ["*.json", *gi], head=head, tail=tail)
    return list(rs.allowlist_problems(b, h))


def test_live_script_parses_as_one_allowlist_block() -> None:
    lines = rs._raw_lines(ROOT, SYNC)
    assert lines is not None
    blk = rs._allow_block(lines)
    assert blk is not None
    ent = rs._allow_entries(lines[blk[0] + 1 : blk[1]])
    assert ent is not None and len(ent[0]) > 10
    assert rs._release_rules(ROOT) is not None


def test_added_report_paths_are_measured(tmp_path: Path) -> None:
    assert _judge(tmp_path, _added(NEW)) == []


def test_a_path_added_mid_list_is_measured(tmp_path: Path) -> None:
    entries = [BASE_ENTRIES[0], BASE_ENTRIES[1], "    # new", f'    "{NEW}",', *BASE_ENTRIES[2:]]
    assert _judge(tmp_path, entries) == []


@pytest.mark.parametrize(
    ("head", "tail"),
    [("$x = 2", "foreach ($r in $reportPaths) {}"), ("$x = 1", "Remove-Item -Recurse C:/")],
)
def test_any_change_outside_the_block_is_unmeasured(tmp_path: Path, head: str, tail: str) -> None:
    assert any("outside" in p for p in _judge(tmp_path, _added(NEW), head=head, tail=tail))


@pytest.mark.parametrize(
    ("line", "why"),
    [
        ('    "desks/mt5/reports/$(Remove-Item x).json"', "not a plain path"),
        ("    Invoke-Expression 'x'", "not a plain path"),
        ('    "desks/mt5/reports/X.json" + $y', "not a plain path"),
        ("    <# hidden", "not a plain path"),
        ("    \u201cdesks/mt5/reports/X.json\u201d", "not a plain path"),
    ],
)
def test_a_line_that_is_not_a_literal_path_is_unmeasured(
    tmp_path: Path, line: str, why: str
) -> None:
    entries = [*_added(NEW)[:-1], _added(NEW)[-1] + ",", line]
    assert any(why in p for p in _judge(tmp_path, entries))


@pytest.mark.parametrize(
    ("path", "why"),
    [
        ("desks/mt5/mt5desk/gateway.json", "state prefix"),
        ("ops/release/x.json", "state prefix"),
        ("desks/mt5/reports/../mt5desk/x.json", "state prefix"),
        ("desks/mt5/data/LIVE_MANIFEST.jsonl", "governed"),
        ("desks/mt5/data/IMMUTABLE_MANIFEST.json", "governed"),
        ("desks/mt5/data/GENERIC_EXEC_ENABLED.json", "governed"),
        ("desks/mt5/data/secrets/keys.json", "secret"),
        ("desks/mt5/reports/ACCOUNT_LOGIN.json", "secret"),
        ("desks/mt5/reports/api_token.json", "secret"),
        ("desks/mt5/reports/FILLS.csv", "not a JSON"),
        ("desks/mt5/data/model.pkl", "not a JSON"),
    ],
)
def test_a_path_the_ruling_forbids_is_unmeasured(tmp_path: Path, path: str, why: str) -> None:
    assert any(why in p for p in _judge(tmp_path, _added(path), [f"!{path}"]))


@pytest.mark.parametrize("gi", [[], [f"!{NEW} "], [f"!/{NEW}"], ["!desks/mt5/reports/*.json"]])
def test_the_gitignore_line_must_match_exactly(tmp_path: Path, gi: list[str]) -> None:
    assert any(".gitignore" in p for p in _judge(tmp_path, _added(NEW), gi))


@pytest.mark.parametrize(
    "comment",
    [
        "    # box at 62.171.172.249",
        "    # see https://example.org/x",
        "    # written from C:\\opt\\quant",
        "    # account 12345678",
        "    # balance $100000",
        "    # key ghp_abcdefghijklmnop",
        "    # token Zx9Qw8Er7Ty6Ui5Op4As3Df",
        "    # mail ops@example.com",
    ],
)
def test_an_added_line_that_leaks_is_unmeasured(tmp_path: Path, comment: str) -> None:
    assert any("carries" in p for p in _judge(tmp_path, _added(NEW, comment=comment)))


def test_a_leaking_gitignore_comment_is_unmeasured(tmp_path: Path) -> None:
    probs = _judge(tmp_path, _added(NEW), [f"!{NEW}", "# from 10.0.0.1"])
    assert any("carries" in p for p in probs)


def test_removing_or_reordering_a_base_entry_is_unmeasured(tmp_path: Path) -> None:
    entries = [BASE_ENTRIES[0], f'    "{NEW}",', '    "desks/mt5/data/b.pkl"']
    assert any("removed or reordered" in p for p in _judge(tmp_path, entries))


def test_a_missing_comma_or_duplicate_is_unmeasured(tmp_path: Path) -> None:
    no_comma = [*BASE_ENTRIES, f'    "{NEW}"']
    assert any("commas" in p for p in _judge(tmp_path / "comma", no_comma))
    dup = _added(NEW, NEW)
    assert any("twice" in p for p in _judge(tmp_path / "dup", dup))


def test_no_added_path_is_not_measured(tmp_path: Path) -> None:
    entries = [*BASE_ENTRIES[:2], "    # only a comment", *BASE_ENTRIES[2:]]
    assert any("no path was added" in p for p in _judge(tmp_path, entries))


def test_unreadable_base_rules_fail_closed(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base", BASE_ENTRIES, [])
    head = _tree(tmp_path / "head", _added(NEW), [f"!{NEW}"])
    (base / rs.RELEASE_PY).write_text("STATE_PREFIXES = tuple(x for x in y)\n", "utf-8")
    assert any("unreadable" in p for p in rs.allowlist_problems(base, head))


def test_the_rules_come_from_the_base_not_the_pr(tmp_path: Path) -> None:
    """A PR that widens STATE_PREFIXES in its own tree is still judged by the base's."""
    path = "ops/release/x.json"
    base = _tree(tmp_path / "base", BASE_ENTRIES, [])
    head = _tree(tmp_path / "head", _added(path), [f"!{path}"])
    (head / rs.RELEASE_PY).write_text(
        RELEASE.replace('("desks/mt5/data/"', '("ops/", "desks/mt5/data/"'), "utf-8"
    )
    assert any("state prefix" in p for p in rs.allowlist_problems(base, head))


def _compare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entries: list[str]) -> dict[str, Any]:
    base = _tree(tmp_path / "base", BASE_ENTRIES, [])
    head = _tree(tmp_path / "head", entries, [f"!{NEW}"])
    step = {"hour": 7.0, "doc": {}, "intents": [{"a": 1}], "error": None, "ftmo": {}}
    monkeypatch.setattr(rs, "run_tree", lambda t, sc: {"steps": [step], "imported": []})
    monkeypatch.delenv(rs.DECLARED_ENV, raising=False)
    return dict(rs.compare(base, head, [SYNC, ".gitignore"], [{"id": "s", "hours": [7.0]}]))


def test_compare_clears_a_measured_allowlist_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rep = _compare(tmp_path, monkeypatch, _added(NEW))
    assert rep["allowlist_measured"] is True
    assert not any(SYNC in p for p in rep["problems"]), rep["problems"]


def test_compare_keeps_an_unmeasured_allowlist_change_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rep = _compare(tmp_path, monkeypatch, _added("desks/mt5/data/LIVE_MANIFEST.jsonl"))
    assert rep["verdict"] == "FAIL" and rep["allowlist_measured"] is False
    assert any(SYNC in p and "never imported" in p for p in rep["problems"])
    assert rep["allowlist_unmeasured"]

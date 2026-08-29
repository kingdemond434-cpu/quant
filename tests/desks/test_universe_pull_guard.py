"""The universe pull must never shrink the local registry -- in ROWS or in COLUMNS.

THE DEFECT (measured live 2026-08-29). `ops/pull_desk_state.sh` scp's the universe registry from
the Windows trading box every two minutes, because only that box can read the terminal. It
installs the incoming copy only when it holds at least as many SYMBOLS as the copy in hand -- a
guard written after a 23-row stump was propagated by a sync.

The same failure came back one level down. A desk copy with all 251 symbols intact -- so it
sailed past the row count -- had dropped `currency_profit` from every one of them, and the pull
reinstalled the lossy copy every two minutes. It defeated three restores by hand before the cause
was found; `scp -p` preserves the remote mtime, so the reverted file did not even look freshly
written.

WHY THE FIELD MATTERS: currency_profit is MetaTrader5's own answer to what currency a symbol is
denominated in, and it is the only correct route for a share or index CFD whose name ("3M",
"AUS200") carries no denomination to parse. Without it `quote_currency()` correctly returns None
and every cost downstream becomes UNMEASURED -- a silent loss of measurement across 106 equity
and 16 index CFDs. This desk has already paid once for a column vanishing from this exact file:
`tick_value` went missing and left 0/197 symbols costable with a 184x JPY commission undercharge.

ONE-WAY: a NEW column on the desk copy is unrestricted, and a field kept by even one incoming row
passes. This can only ever refuse.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "ops" / "pull_desk_state.sh"


def _guard_source() -> str:
    """The python heredoc from the shell script, so the test runs THE code that ships.

    Re-typing the check here would test a copy and pass forever while the script rotted.
    """
    text = _SCRIPT.read_text("utf-8")
    m = re.search(r"universe\.json <<'PY'\n(.*?)\nPY\n", text, re.S)
    assert m, "the universe-pull guard heredoc moved; this test must follow it"
    return m.group(1)


def _run(incoming: dict[str, object], local: dict[str, object], tmp: Path) -> tuple[int, str]:
    a, b = tmp / "incoming.json", tmp / "local.json"
    a.write_text(json.dumps(incoming), "utf-8")
    b.write_text(json.dumps(local), "utf-8")
    src = tmp / "guard.py"
    src.write_text(_guard_source(), "utf-8")
    p = subprocess.run(["python3", str(src), str(a), str(b)], capture_output=True, text=True,
                       check=False, timeout=60)
    return p.returncode, p.stdout


def _reg(n: int, *, ccy: bool = True) -> dict[str, object]:
    row: dict[str, object] = {"symbol": "S", "tick_value": 1.0}
    if ccy:
        row["currency_profit"] = "USD"
    return {f"SYM{i}": dict(row, symbol=f"SYM{i}") for i in range(n)}


def test_the_live_failure_is_refused(tmp_path: Path) -> None:
    """Same rows, one column gone -- the exact copy that overwrote this box every two minutes."""
    rc, out = _run(_reg(251, ccy=False), _reg(251, ccy=True), tmp_path)
    assert rc == 2
    assert "currency_profit" in out
    assert "248" not in out or "251" in out       # counts are reported, not just the name


def test_a_row_stump_is_still_refused(tmp_path: Path) -> None:
    """The original guard must keep working."""
    rc, _ = _run(_reg(23), _reg(251), tmp_path)
    assert rc == 1


def test_an_identical_copy_installs(tmp_path: Path) -> None:
    rc, _ = _run(_reg(251), _reg(251), tmp_path)
    assert rc == 0


def test_a_grown_registry_installs(tmp_path: Path) -> None:
    rc, _ = _run(_reg(260), _reg(251), tmp_path)
    assert rc == 0


def test_a_new_column_on_the_desk_copy_is_not_restricted(tmp_path: Path) -> None:
    """One-way: this refuses losses, never additions."""
    incoming = {k: dict(v, margin_initial=1.0) for k, v in _reg(251).items()}  # type: ignore[call-overload]
    rc, _ = _run(incoming, _reg(251), tmp_path)
    assert rc == 0


def test_a_rare_local_field_does_not_block_the_pull(tmp_path: Path) -> None:
    """Blunt in the safe direction: a field on a handful of rows is not a dropped column."""
    local = _reg(251, ccy=False)
    for k in list(local)[:5]:
        local[k]["experimental_flag"] = True       # type: ignore[index]
    rc, _ = _run(_reg(251, ccy=False), local, tmp_path)
    assert rc == 0


def test_a_field_kept_by_even_one_incoming_row_passes(tmp_path: Path) -> None:
    """A genuine retirement lands the moment the desk box keeps one row carrying the field.

    This guard is not a veto on schema change; it is a veto on losing one silently.
    """
    incoming = _reg(251, ccy=False)
    first = next(iter(incoming))
    incoming[first]["currency_profit"] = "USD"     # type: ignore[index]
    rc, _ = _run(incoming, _reg(251, ccy=True), tmp_path)
    assert rc == 0


def test_an_unreadable_incoming_copy_is_refused(tmp_path: Path) -> None:
    a, b = tmp_path / "incoming.json", tmp_path / "local.json"
    a.write_text("{ this is not json", "utf-8")
    b.write_text(json.dumps(_reg(251)), "utf-8")
    src = tmp_path / "guard.py"
    src.write_text(_guard_source(), "utf-8")
    p = subprocess.run(["python3", str(src), str(a), str(b)], capture_output=True, text=True,
                       check=False, timeout=60)
    assert p.returncode != 0, "a mid-write or truncated file must never become the local truth"


@pytest.mark.parametrize("bad", ["[]", "null", '"a string"'])
def test_a_non_object_incoming_copy_is_refused(tmp_path: Path, bad: str) -> None:
    a, b = tmp_path / "incoming.json", tmp_path / "local.json"
    a.write_text(bad, "utf-8")
    b.write_text(json.dumps(_reg(251)), "utf-8")
    src = tmp_path / "guard.py"
    src.write_text(_guard_source(), "utf-8")
    p = subprocess.run(["python3", str(src), str(a), str(b)], capture_output=True, text=True,
                       check=False, timeout=60)
    assert p.returncode != 0

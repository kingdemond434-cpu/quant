"""The box's cost and tape state crosses the publish wire, and none of it is a credential.

MEASURED 2026-10-20: cost_surface.json, cost_truth_quotes.json and tape/tape_state.json were
fresh on the trading box while the branch carried the 2026-09-23 copies from the orphan root --
`sync_shadow_to_git.ps1` listed none of them, so nothing ever re-published them, and every
off-box reader of the cost surface charged four-week-old spreads.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from libs.ops import release

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"
COST_STATE = ("desks/mt5/data/cost_surface.json",
              "desks/mt5/data/cost_truth_quotes.json",
              "desks/mt5/data/tape/tape_state.json")
#: Key names that would mean a credential rode in. `login` is an identifier, not a secret, and is
#: fenced separately (tests/ops/test_live_infrastructure_is_not_published.py).
SECRET_KEY = re.compile(r"pass(word|wd)?$|secret|token|api_?key|private_?key|investor|"
                        r"credential|bearer|auth", re.I)


def _report_paths() -> list[str]:
    src = SYNC.read_text("utf-8", errors="ignore")
    start = src.index("$reportPaths = @(")
    block = src[start:src.index("\n)", start)]
    code = "\n".join(ln.split("#", 1)[0] for ln in block.splitlines())
    return [p for p in re.findall(r'"([^"]+)"', code) if "/" in p]


@pytest.mark.parametrize("rel", COST_STATE)
def test_listed_state_and_addable(rel: str) -> None:
    assert rel in _report_paths(), f"{rel} is not on the publish wire"
    assert release.is_state_path(rel), f"{rel} would read as CODE to the seal"
    ignored = subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=ROOT,
                             capture_output=True, check=False)
    assert ignored.returncode != 0, f"{rel} is listed but .gitignore excludes it"


@pytest.mark.parametrize("rel", COST_STATE)
def test_under_the_report_cap(rel: str) -> None:
    p = ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} not in this checkout")
    assert p.stat().st_size < 4 * 1024 * 1024, "the wire skips anything over $ReportCapBytes"


def _keys(obj: Any, path: str = "") -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(f"{path}/{k}")
            out += _keys(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for v in obj[:200]:
            out += _keys(v, path)
    return out


@pytest.mark.parametrize("rel", COST_STATE)
def test_no_credential_shaped_key(rel: str) -> None:
    p = ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} not in this checkout")
    doc = json.loads(p.read_text("utf-8"))
    hits = sorted({k for k in _keys(doc) if SECRET_KEY.search(k.rsplit("/", 1)[-1])})
    assert not hits, f"{rel} carries credential-shaped keys {hits}; it must not be published"


def test_the_quotes_writer_withholds_the_login() -> None:
    src = (ROOT / "desks" / "mt5" / "research" / "cost_truth.py").read_text("utf-8")
    assert '"login_withheld"' in src, (
        "cost_truth.py no longer withholds the login, and its quotes file is now published "
        "from the box every hour")

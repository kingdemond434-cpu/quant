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


# THE PUBLISH-TIME LOGIN FENCE (audit v2, 2026-10-14). The committed 2026-09-23
# cost_truth_quotes.json still carries the live login and the live-identifier test exempts that
# whole file, so nothing but the publisher itself can stop a regressed writer re-publishing it.
# pwsh is absent off the box; the pattern is pulled out of the script and run here as written.
def _login_pattern() -> re.Pattern[str]:
    src = SYNC.read_text("utf-8", errors="ignore")
    m = re.search(r"^\$LoginKeyPattern = '([^']+)'", src, re.M)
    assert m, "sync_shadow_to_git.ps1 no longer defines $LoginKeyPattern"
    return re.compile(m.group(1), re.I)


@pytest.mark.parametrize("text, refused", [
    ('{"account": {"login": 51234567, "server": "X"}}', True),
    ('{"account": {"Login": "51234567"}}', True),
    ('{"mt5_login": 51234567}', True),
    ('{"account_login" : 51234567}', True),
    ('{"account": {"login_withheld": true, "server": "X"}}', False),   # what cost_truth writes
    ('{"login": null}', False),
    ('{"note": "login to the terminal"}', False),
], ids=["int", "string-cased", "prefixed", "spaced", "withheld-bool", "null", "prose"])
def test_the_login_fence_refuses_a_login_value_and_passes_the_withheld_flag(
        text: str, refused: bool) -> None:
    assert bool(_login_pattern().search(text)) is refused


def test_the_login_fence_runs_inside_the_publisher_before_any_blob_is_hashed() -> None:
    src = SYNC.read_text("utf-8", errors="ignore")
    body = src[src.index("function Publish-StateOnto"):]
    fence, hashed = body.index("$LoginKeyPattern"), body.index("hash-object -w --stdin-paths")
    assert fence < hashed, "the login fence must run before the state blobs are written"
    refusal = next(ln for ln in body.splitlines() if "REFUSED $rel -- it carries" in ln)
    assert "$text" not in refusal and "$m" not in refusal, "the refusal must not log the value"


def test_the_committed_quotes_copy_is_exactly_what_the_fence_would_refuse() -> None:
    # Until the box publishes a fresh copy this checkout holds the 2026-09-23 file with the
    # login in it, so the fence refuses it; after that publish, nothing on the wire matches.
    # Either way no OTHER listed state file may carry a login value.
    pat = _login_pattern()
    src = SYNC.read_text("utf-8", errors="ignore")
    listed = set(_report_paths())
    start = src.index("$relPaths = @(")
    block = src[start:src.index("\n)", start)]
    listed |= {p for p in re.findall(r'"([^"]+)"',
                                     "\n".join(ln.split("#", 1)[0] for ln in block.splitlines()))
               if "/" in p}
    hits = sorted(rel for rel in listed if rel.endswith(".json") and (ROOT / rel).is_file()
                  and pat.search((ROOT / rel).read_text("utf-8", errors="ignore")))
    assert set(hits) <= {"desks/mt5/data/cost_truth_quotes.json"}, hits

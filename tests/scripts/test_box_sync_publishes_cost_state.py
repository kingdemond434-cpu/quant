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


# THE PUBLISH-TIME LOGIN FENCE (audit v2 + v3, 2026-10-14). The committed 2026-09-23
# cost_truth_quotes.json still carries the live login and the live-identifier test exempts that
# whole file, so nothing but the publisher itself can stop a regressed writer re-publishing it.
# The fence is libs/ops/login_fence.py, run by the publisher on the blobs it is about to commit;
# pwsh is absent off the box, so the wiring is pinned by source and the judgement by Python.
from libs.ops import login_fence as lf  # noqa: E402

_N = "51234567"   # synthetic, account-shaped


@pytest.mark.parametrize("text", [
    '{"account": {"login": @N, "server": "X"}}',
    '{"account": {"Login": "@N"}}',
    '{"LOGIN": @N}',
    '{"mt5_login": @N}',
    '{"fusion_live_login": @N}',
    '{"account_login" : @N}',
    '{"accountLogin": @N}',
    '{"account-login": @N}',
    '{"login_id": @N}',
    '{"Login ID": @N}',
    '{"account": @N, "server": "S", "account_kind": "LIVE"}',
    '{"account_number": "@N"}',
    '{"login": [@N]}',
    '{"note": "{\\"login\\": @N}"}',                  # escaped JSON inside a string
    '{"\\u006c\\u006f\\u0067\\u0069\\u006e": @N}',    # \u-encoded key
    "{'login': @N}",                                  # Python repr
], ids=lambda t: t[:28])
def test_the_fence_refuses_a_login_value_in_every_shape_the_audit_probed(text: str) -> None:
    text = text.replace("@N", _N)
    got = lf.findings("desks/mt5/data/x.json", text.encode())
    assert got, text
    assert _N not in json.dumps(got), "a finding must never carry the value"


@pytest.mark.parametrize("text", [
    '{"account": {"login_withheld": true, "server": "X"}}',   # what cost_truth writes
    '{"account_key": "sha256:0123456789abcdef"}',
    '{"login": null}', '{"login" : false}', '{"login": true}',
    '{"requires_login": 0}', '{"last_login": "2026-10-20T18:00:00+00:00"}',
    '{"last_login": 1760983200}',
    '{"login": "ok"}', '{"login": ""}',
    '{"account": {"balance": 1000.0, "currency": "USD"}}', '{"account": "Fusion Zero"}',
    '{"account": 0}', '{"note": "login to the terminal"}',
])
def test_the_fence_passes_what_is_not_a_login(text: str) -> None:
    assert lf.findings("desks/mt5/data/x.json", text.encode()) == [], text


@pytest.mark.parametrize("rel", ["desks/mt5/data/x.yaml", "desks/mt5/data/x.log",
                                 "desks/mt5/data/x.xml", "desks/mt5/data/x.unknownext"])
def test_unknown_extensions_are_judged_not_waved_through(rel: str) -> None:
    assert lf.findings(rel, f"login: {_N}\n".encode())


def test_a_csv_header_naming_a_login_column_is_refused_when_a_row_carries_one() -> None:
    assert lf.findings("desks/mt5/data/x.csv", f"time,Login,profit\nt,{_N},1.0\n".encode())
    assert lf.findings("desks/mt5/data/x.tsv", f"time\taccount\nt\t{_N}\n".encode())
    assert not lf.findings("desks/mt5/data/x.csv", b"time,last_login,profit\nt,20261020,1\n")
    assert not lf.findings("desks/mt5/data/x.csv", b"time,login,profit\nt,,1\n")


def test_binary_state_is_exempt_by_extension_only() -> None:
    assert lf.findings("desks/mt5/data/cross_asset_anchors.pkl", f'"login": {_N}'.encode()) == []


def test_a_legacy_prefix_is_frozen_and_every_row_after_the_cutover_is_judged() -> None:
    rel = "desks/mt5/data/live_ledger.jsonl"
    old = f'{{"deal": 1, "account": {_N}, "server": "S"}}\n'
    new = '{"deal": 2, "account_key": "sha256:0123456789abcdef", "server": "S"}\n'
    assert lf.findings(rel, (old * 3).encode()) == []               # no cutover yet
    assert lf.findings(rel, (old * 3 + new * 2).encode()) == []     # clean after cutover
    bad = lf.findings(rel, (old + new + old).encode())              # writer regressed
    assert [h["line"] for h in bad] == [3]
    # the same rows anywhere else are judged whole
    assert lf.findings("desks/mt5/data/other.jsonl", (old + new).encode())


def _git(repo: Path, *args: str, data: bytes | None = None) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True,
                          check=True).stdout.decode().strip()


def test_the_cli_judges_blobs_writes_the_artifact_and_opens_an_alert_without_the_value(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    bad = _git(tmp_path, "hash-object", "-w", "--stdin",
               data=f'{{"account": {{"login": {_N}}}}}'.encode())
    good = _git(tmp_path, "hash-object", "-w", "--stdin",
                data=b'{"account": {"login_withheld": true}}')
    seen: list[str] = []

    def _alert(doc: dict[str, Any], root: Path | None = None) -> str:
        seen.append(json.dumps(doc))
        return "OPEN"

    monkeypatch.setattr(lf, "record_alert", _alert)
    monkeypatch.setattr("sys.stdin", io.StringIO(
        f"{bad}\tdesks/mt5/data/cost_truth_quotes.json\n{good}\tdesks/mt5/data/b.json\n"
        f"{'0' * 40}\tdesks/mt5/data/gone.json\n"))
    art = tmp_path / "LOGIN_FENCE.json"
    assert lf.main(["--repo", str(tmp_path), "--artifact", str(art)]) == 0
    printed = capsys.readouterr().out.split()
    assert printed == ["desks/mt5/data/cost_truth_quotes.json", "desks/mt5/data/gone.json"]
    doc = json.loads(art.read_text("utf-8"))
    assert doc["status"] == "REFUSED" and doc["n_refused"] == 2 and doc["n_checked"] == 3
    for text in (art.read_text("utf-8"), *seen, " ".join(printed)):
        assert _N not in text, "the value reached the artifact, the alert or stdout"


def test_the_alert_opens_on_a_refusal_and_closes_on_a_clean_pass(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    import shutil
    (tmp_path / "libs" / "ops").mkdir(parents=True)
    for name in ("__init__.py", "alert_ledger.py"):
        src = root / "libs" / "ops" / name
        if src.exists():
            shutil.copy(src, tmp_path / "libs" / "ops" / name)
    (tmp_path / "libs" / "__init__.py").touch()
    refused = {"status": "REFUSED", "refused": {"desks/mt5/data/a.json":
                                                 [{"key": "login", "line": 1}]}}
    assert lf.record_alert(refused, tmp_path) == "OPEN"
    ledger = (tmp_path / "data" / "alert_ledger.json").read_text("utf-8")
    assert lf.ALERT_ID in ledger and "a.json" in ledger
    assert lf.record_alert({"status": "OK", "refused": {}}, tmp_path) == "FIXED"


def test_the_publisher_runs_the_fence_on_the_final_blobs_and_fails_closed() -> None:
    src = SYNC.read_text("utf-8", errors="ignore")
    body = src[src.index("function Publish-StateOnto"):]
    hashed = body.index("hash-object -w --stdin-paths")
    sanitised = body.index("$blobs[$i] = $pubBlob[0]")
    fence = body.index("libs\\ops\\login_fence.py")
    indexed = body.index('"100644 blob $($blobs[$i])')
    assert hashed < sanitised < fence < indexed, (
        "the fence must judge the final blobs: after hash-object and the sleeves sanitiser, "
        "before they are indexed")
    assert "$fenceRc -ne 0" in body and "nothing published (it fails closed)" in body
    assert "LoginKeyPattern" not in src, "the old text-regex fence must be gone"
    refusal = next(ln for ln in body.splitlines() if "publish: REFUSED $rel" in ln)
    assert "$text" not in refusal and "$blobs" not in refusal
    assert "desks/mt5/reports/LOGIN_FENCE.json" in _report_paths()


def test_nothing_listed_on_the_wire_trips_the_fence_except_the_known_stale_copy() -> None:
    # Until the box publishes a fresh copy this checkout holds the 2026-09-23 file with the
    # login in it, so the fence refuses it; after that publish, nothing on the wire matches.
    # The measured false-positive count over every other listed path must stay zero.
    src = SYNC.read_text("utf-8", errors="ignore")
    listed = set(_report_paths())
    start = src.index("$relPaths = @(")
    block = src[start:src.index("\n)", start)]
    listed |= {p for p in re.findall(r'"([^"]+)"',
                                     "\n".join(ln.split("#", 1)[0] for ln in block.splitlines()))
               if "/" in p}
    hits = sorted(rel for rel in listed if (ROOT / rel).is_file()
                  and lf.findings(rel, (ROOT / rel).read_bytes()))
    assert set(hits) <= {"desks/mt5/data/cost_truth_quotes.json"}, hits


# DECLARED ACCOUNT NUMBERS, DIGIT-BOUNDED (audit addendum to v4, 2026-10-20). `\b` treats `_` and
# letters as word characters, so `acc_<ID>` and `x<ID>` slipped past a word-boundary match.
_ID = "55512340"   # synthetic declared number
_IDS = frozenset({_ID})


@pytest.mark.parametrize("text", [f"refused for {_ID}.", f"acc_{_ID}", f"x{_ID}",
                                  f'{{"note": "acct {_ID}"}}', f"{_ID}"],
                         ids=["prose-period", "underscore", "letter-prefix", "in-a-string", "bare"])
def test_a_declared_number_is_refused_between_any_non_digits(text: str) -> None:
    got = lf.findings("desks/mt5/data/x.json", text.encode(), _IDS)
    assert [h["key"] for h in got] == [lf.ID_FINDING]
    assert _ID not in json.dumps(got), "a finding must never carry the number"


@pytest.mark.parametrize("text", [f"9{_ID}7", f"{_ID}1", f"1{_ID}"],
                         ids=["inside", "suffix-digit", "prefix-digit"])
def test_a_longer_number_that_only_contains_the_id_is_not_it(text: str) -> None:
    assert lf.findings("desks/mt5/data/x.json", text.encode(), _IDS) == []


def test_the_declared_numbers_come_from_the_env_and_the_box_declarations(tmp_path: Path) -> None:
    assert lf.declared_ids(tmp_path, {}) == frozenset()       # none declared is not an error
    assert lf.declared_ids(tmp_path, {lf.ID_ENV: f"12, {_ID} x"}) == _IDS
    decl = tmp_path / lf.DECLARATIONS_REL
    decl.parent.mkdir(parents=True)
    decl.write_text(json.dumps({f"{_ID}@FusionMarkets-Live": "LIVE"}), "utf-8")
    assert lf.declared_ids(tmp_path, {}) == _IDS


def test_an_unreadable_declarations_file_fails_the_whole_publish_closed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io
    decl = tmp_path / lf.DECLARATIONS_REL
    decl.parent.mkdir(parents=True)
    decl.write_text("{torn", "utf-8")
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{'0' * 40}\tdesks/mt5/data/a.json\n"))
    assert lf.main(["--repo", str(tmp_path), "--artifact", str(tmp_path / "F.json")]) == 2
    assert capsys.readouterr().out == "", "nothing may be listed as publishable"


def test_the_cli_refuses_a_declared_number_and_never_writes_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    blob = _git(tmp_path, "hash-object", "-w", "--stdin", data=f"refused for {_ID}.".encode())
    monkeypatch.setenv(lf.ID_ENV, _ID)
    monkeypatch.setattr(lf, "record_alert", lambda doc, root=None: "OPEN")
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{blob}\tdesks/mt5/reports/X.json\n"))
    art = tmp_path / "F.json"
    assert lf.main(["--repo", str(tmp_path), "--artifact", str(art)]) == 0
    out = capsys.readouterr().out
    assert out.split() == ["desks/mt5/reports/X.json"]
    assert _ID not in art.read_text("utf-8") and _ID not in out

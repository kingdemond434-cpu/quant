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


def _pin(monkeypatch: pytest.MonkeyPatch, rel: str, prefix: bytes) -> None:
    monkeypatch.setitem(lf.LEGACY_PIN, rel, {**lf.measure_prefix(prefix), "why": "test"})


def test_a_legacy_prefix_is_pinned_and_every_row_after_it_is_judged(
        monkeypatch: pytest.MonkeyPatch) -> None:
    rel = "desks/mt5/data/live_ledger.jsonl"
    old = f'{{"deal": 1, "account": {_N}, "server": "S"}}\n'
    new = '{"deal": 2, "account_key": "sha256:0123456789abcdef", "server": "S"}\n'
    _pin(monkeypatch, rel, (old * 3).encode())
    assert lf.findings(rel, (old * 3).encode()) == []                # exactly the pin
    assert lf.findings(rel, (old * 3 + new * 2).encode()) == []      # clean after it
    assert lf.findings(rel, (old * 3).replace("\n", "\r\n").encode()) == [], "CRLF is the same"
    bad = lf.findings(rel, (old * 3 + new + old).encode())           # writer regressed
    assert [h["line"] for h in bad] == [5]
    # v4's marker no longer exempts anything: a row past the pin is judged with or without one
    assert lf.findings(rel, (old * 4).encode())
    # the same rows anywhere else are judged whole
    assert lf.findings("desks/mt5/data/other.jsonl", (old + new).encode())


@pytest.mark.parametrize("change", ["edited", "truncated", "reordered"])
def test_a_changed_legacy_prefix_fails_closed(monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    """order_intents.jsonl is not append-only: a rewritten or shortened prefix is refused."""
    rel = "desks/mt5/data/order_intents.jsonl"
    rows = [f'{{"intent": {i}, "account": {_N}}}\n' for i in range(4)]
    _pin(monkeypatch, rel, "".join(rows).encode())
    if change == "edited":
        rows[1] = rows[1].replace('"intent": 1', '"intent": 9')
    elif change == "truncated":
        rows = rows[:3]
    else:
        rows[0], rows[1] = rows[1], rows[0]
    got = lf.findings(rel, "".join(rows).encode())
    assert {"key": lf.PREFIX_FINDING, "line": 0} in got
    assert _N not in json.dumps(got)


def test_the_shipped_pins_are_the_committed_prefixes() -> None:
    for rel, pin in lf.LEGACY_PIN.items():
        held = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{rel}"],
                              capture_output=True, check=True).stdout
        lines = lf._lines(held)
        assert len(lines) >= pin["records"], rel
        assert lf.prefix_digest(lines[:pin["records"]]) == pin["sha256"], rel


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
    monkeypatch.setattr(lf, "page", lambda doc, root=None: seen.append(json.dumps(doc)) or {})
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
    assert lf.ID_FINDING in [h["key"] for h in got]   # (v5: "acct N" is also a prose hit)
    assert _ID not in json.dumps(got), "a finding must never carry the number"


@pytest.mark.parametrize("text", [f"9{_ID}7", f"{_ID}1", f"1{_ID}"],
                         ids=["inside", "suffix-digit", "prefix-digit"])
def test_a_longer_number_that_only_contains_the_id_is_not_it(text: str) -> None:
    assert lf.findings("desks/mt5/data/x.json", text.encode(), _IDS) == []


def test_the_declared_numbers_come_from_the_env_and_the_box_declarations(tmp_path: Path) -> None:
    assert lf.declared_ids(tmp_path, {}) == frozenset()       # none declared: UNMEASURED later
    assert lf.declared_ids(tmp_path, {lf.ID_ENV: f" {_ID}, "}) == _IDS
    decl = tmp_path / lf.DECLARATIONS_REL
    decl.parent.mkdir(parents=True)
    # account_profile.py's real shape (v4a read the top level only, so it declared nothing)
    decl.write_text(json.dumps({"accounts": {f"{_ID}@FusionMarkets-Live": "LIVE"}}), "utf-8")
    assert lf.declared_ids(tmp_path, {}) == _IDS
    decl.write_text(json.dumps({f"{_ID}@FusionMarkets-Live": "LIVE"}), "utf-8")
    assert lf.declared_ids(tmp_path, {}) == _IDS


@pytest.mark.parametrize("env,doc", [
    ("12", None), (f"{_ID} x", None), (f"{_ID},1.5e7", None),
    ("", {"accounts": {"nope@S": "LIVE"}}), ("", {"accounts": ["x"]}),
    ("", {"accounts": {f"{_ID}@S": "LIVE", "@S": "LIVE"}}),
], ids=["short", "word", "float", "bad-key", "not-object", "one-bad-key"])
def test_a_malformed_declaration_is_a_config_error_never_silence(
        tmp_path: Path, env: str, doc: Any) -> None:
    if doc is not None:
        decl = tmp_path / lf.DECLARATIONS_REL
        decl.parent.mkdir(parents=True)
        decl.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(lf.FenceConfigError) as exc:
        lf.declared_ids(tmp_path, {lf.ID_ENV: env})
    assert _ID not in str(exc.value)


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
    monkeypatch.setattr(lf, "page", lambda doc, root=None: {})
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{blob}\tdesks/mt5/reports/X.json\n"))
    art = tmp_path / "F.json"
    assert lf.main(["--repo", str(tmp_path), "--artifact", str(art)]) == 0
    out = capsys.readouterr().out
    assert out.split() == ["desks/mt5/reports/X.json"]
    assert _ID not in art.read_text("utf-8") and _ID not in out


# AUDIT V5: ENCODINGS, KEYS AND KEY-LESS FORMS THE v4a FENCE MISSED. Every row is synthetic.
def _b64(t: str) -> str:
    import base64
    return base64.b64encode(t.encode()).decode()


_LOGIN_JSON = f'{{"login": {_N}}}'
_FULLWIDTH = "".join(chr(0xFF10 + int(d)) for d in _N)


@pytest.mark.parametrize("data", [
    _LOGIN_JSON.encode("utf-16-le"),
    _LOGIN_JSON.encode("utf-16"),
    f'{{"x": "{_LOGIN_JSON.encode().hex()}"}}'.encode(),
    f'{{"x": "{_b64(_LOGIN_JSON)}"}}'.encode(),
    f'{{"login": {_FULLWIDTH}}}'.encode(),
    ('{"a": "{\\\\\\"login\\\\\\": ' + _N + '}"}').encode(),       # triple-escaped JSON
    f'{{"login": {_N}.0}}'.encode(),
    f'{{"login": {_N[0]}.{_N[1:]}e{len(_N) - 1}}}'.encode(),
    f'{{"mt5_account": {_N}}}'.encode(), f'{{"live_account": {_N}}}'.encode(),
    f'{{"acct": {_N}}}'.encode(), f'{{"login2": {_N}}}'.encode(),
    f"refused on account {_N} today".encode(), f"account #{_N}".encode(),
    f"{_N}@FusionMarkets-Live".encode(),
    f"2026.10.20 '{_N}': authorized on FusionMarkets-Live".encode(),
    f"<cfg><login>{_N}</login></cfg>".encode(), f'<acc login="{_N}"/>'.encode(),
], ids=["utf16le", "utf16-bom", "hex", "base64", "fullwidth", "triple-escaped", "float",
        "exponent", "mt5_account", "live_account", "acct", "login2", "prose", "prose-hash",
        "at-server", "journal", "xml-element", "xml-attribute"])
def test_the_v5_fence_reads_every_encoding_and_form_the_audit_probed(data: bytes) -> None:
    got = lf.findings("desks/mt5/data/x.json", data)
    assert got, data[:40]
    assert _N not in json.dumps(got)


def test_a_csv_preamble_or_a_json_cell_does_not_hide_a_login() -> None:
    assert lf.findings("desks/mt5/data/x.csv",
                       f"report\ngenerated,today\ntime,Login\nt,{_N}\n".encode())
    assert lf.findings("desks/mt5/data/x.csv", f'time,meta\nt,"{{""login"": {_N}}}"\n'.encode())


@pytest.mark.parametrize("text", [
    '{"max_account": 5000}', '{"count_login": 1234}', "account 2026-10-20",
    '{"t": 1760983200.5}', "account balance 1000.50", '{"sha": "' + "ab" * 32 + '"}',
    '{"blob": "' + _b64("nothing to see here at all") + '"}',
])
def test_the_v5_widening_keeps_passing_what_is_not_a_login(text: str) -> None:
    assert lf.findings("desks/mt5/data/x.json", text.encode()) == [], text


def _cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: bytes) -> tuple[int, dict]:
    import io
    if not (tmp_path / ".git").exists():
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    blob = _git(tmp_path, "hash-object", "-w", "--stdin", data=payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{blob}\tdesks/mt5/data/a.json\n"))
    art = tmp_path / "F.json"
    rc = lf.main(["--repo", str(tmp_path), "--artifact", str(art)])
    return rc, json.loads(art.read_text("utf-8"))


def test_zero_declared_ids_is_unmeasured_keeps_the_alert_open_and_pages(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(lf.ID_ENV, raising=False)
    alerts: list[str] = []
    pages: list[tuple[str, str]] = []
    monkeypatch.setattr(lf, "record_alert",
                        lambda doc, root=None: alerts.append(doc["status"]) or "OPEN")
    monkeypatch.setattr(lf, "_default_sender",
                        lambda root: lambda t, b: pages.append((t, b))
                        or {"armed": 1, "delivered": 1})
    rc, doc = _cli(tmp_path, monkeypatch, b'{"clean": true}')
    assert rc == 0 and doc["status"] == "UNMEASURED" and doc["declared_ids"] == "UNMEASURED"
    assert alerts == ["UNMEASURED"] and doc["alert"] == "OPEN"
    assert len(pages) == 1 and "UNMEASURED" in pages[0][0]
    monkeypatch.setenv(lf.ID_ENV, _ID)
    rc, doc = _cli(tmp_path, monkeypatch, b'{"clean": true}')
    assert rc == 0 and doc["status"] == "OK"
    assert len(pages) == 2 and "OK again" in pages[1][0], "one page on recovery"


def test_paging_is_deduplicated_repaged_and_never_carries_the_value(tmp_path: Path) -> None:
    from datetime import UTC, datetime, timedelta
    sent: list[tuple[str, str]] = []

    def sender(t: str, b: str) -> dict[str, Any]:
        sent.append((t, b))
        return {"armed": 1, "delivered": 1}

    doc = {"status": "REFUSED", "n_refused": 1,
           "refused": {"desks/mt5/data/a.json": [{"key": "login", "line": 3}]}}
    t0 = datetime(2026, 10, 20, tzinfo=UTC)
    assert lf.page(doc, tmp_path, sender=sender, now=t0)["sent"]
    assert not lf.page(doc, tmp_path, sender=sender, now=t0 + timedelta(hours=1))["sent"]
    assert lf.page(doc, tmp_path, sender=sender, now=t0 + timedelta(hours=7))["sent"]
    doc2 = {**doc, "refused": {**doc["refused"], "desks/mt5/data/b.json": []}}
    assert lf.page(doc2, tmp_path, sender=sender, now=t0 + timedelta(hours=8))["sent"]
    ok = {"status": "OK", "refused": {}}
    assert lf.page(ok, tmp_path, sender=sender, now=t0 + timedelta(hours=9))["sent"]
    assert not lf.page(ok, tmp_path, sender=sender, now=t0 + timedelta(hours=20))["sent"]
    assert len(sent) == 4 and all(_N not in t + b for t, b in sent)
    assert "a.json" in sent[0][1] and "login" in sent[0][1]


def test_an_alert_or_page_failure_is_not_swallowed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    def boom(doc: dict[str, Any], root: Path | None = None) -> str:
        raise OSError("ledger locked")

    monkeypatch.setattr(lf, "record_alert", boom)
    rc, doc = _cli(tmp_path, monkeypatch, f'{{"login": {_N}}}'.encode())
    assert rc == 3, "a refusal that pages nobody must stop the publish"
    assert doc["alert_error"] == "OSError" and doc["status"] == "REFUSED"
    assert capsys.readouterr().out == "", "nothing may be listed as publishable"
    # and record_alert itself raises instead of returning None
    monkeypatch.undo()
    import builtins
    real = builtins.__import__

    def no_ledger(name: str, *a: Any, **k: Any) -> Any:
        if name == "libs.ops.alert_ledger":
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_ledger)
    with pytest.raises(ImportError):
        lf.record_alert({"status": "REFUSED", "refused": {}}, tmp_path)


def test_the_box_declarations_are_gitignored() -> None:
    rc = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", lf.DECLARATIONS_REL],
                        check=False).returncode
    assert rc == 0, "ACCOUNT_PROFILES.json would publish every declared account number"


# v5b (2026-10-21). SPLIT AND NON-ASCII DIGIT FORMS OF A DECLARED NUMBER, an undelivered page,
# and the N@server boundary kept. Every number here is synthetic.
_SID = "5551234"
_SIDS = frozenset({_SID})
_AR = "".join(chr(0x0660 + int(d)) for d in _SID)       # Arabic-Indic
_EAR = "".join(chr(0x06F0 + int(d)) for d in _SID)      # Extended Arabic-Indic


@pytest.mark.parametrize("text", [
    "refused for 555-1234.", "acct 5,551,234", "x 555 1234 y", "555.1234", "555 - 1234",
    "555\u20131234", "555'1234", "555_1234", "5\u00a0551\u00a0234",
    f"refused for {_AR}.", f"acc_{_EAR}", f"{_AR[:3]}-{_AR[3:]}", f'{{"note": "{_EAR}"}}',
    "\\u0665\\u0665\\u0665\\u0661\\u0662\\u0663\\u0664",
], ids=["hyphen", "thousands", "spaces", "dot", "spaced-hyphen", "en-dash", "apostrophe",
        "underscore", "nbsp", "arabic-indic", "extended-arabic-indic", "arabic-split",
        "arabic-in-json", "arabic-u-escaped"])
def test_a_split_or_non_ascii_declared_number_is_refused(text: str) -> None:
    got = lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS)
    assert lf.ID_FINDING in [h["key"] for h in got], text
    assert _SID not in json.dumps(got)


@pytest.mark.parametrize("text", ["1,555,1234", "555-12345", "9.555.1234", "555-1234-6",
                                  "5551 2345", "2026-10-21 12:34"],
                         ids=["inside-thousands", "longer-tail", "longer-dotted",
                              "phone-tail", "shifted", "timestamp"])
def test_a_split_number_that_only_contains_the_digits_is_not_it(text: str) -> None:
    assert lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS) == [], text


def test_a_contiguous_declared_number_still_hits_beside_a_separator() -> None:
    """The split form is ADDED; the v4 digit-bounded match is unchanged (`ID.0` still hits)."""
    for text in (f"{_SID}.0", f"{_SID}-x", f"login {_SID}, ok"):
        assert lf.ID_FINDING in [h["key"] for h in
                                 lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS)]


def test_arabic_indic_digits_trip_the_key_rules_with_nothing_declared() -> None:
    for text in (f'{{"login": {_AR}}}', f'{{"account": "{_EAR}"}}', f"{_AR}@FusionMarkets-Live"):
        assert lf.findings("desks/mt5/data/x.json", text.encode()), text


def test_a_declared_number_written_in_arabic_indic_digits_is_declared_in_ascii(
        tmp_path: Path) -> None:
    assert lf.declared_ids(tmp_path, {lf.ID_ENV: _AR}) == _SIDS


@pytest.mark.parametrize("text", ['{"id": "DSD_X_2023@DF_X"}',
                                  "DSD_X_\u0662\u0660\u0662\u0663@DF_X", "v1.2023@DF"],
                         ids=["oecd", "oecd-arabic-digits", "dotted"])
def test_n_at_server_keeps_its_non_word_boundary(text: str) -> None:
    assert lf.findings("desks/mt5/reports/PIT_LAG_CENSUS.json", text.encode()) == [], text


def test_an_undelivered_page_is_not_a_page_and_the_next_pass_resends(tmp_path: Path) -> None:
    from datetime import UTC, datetime, timedelta
    sent: list[str] = []
    answers = [{"armed": 1, "delivered": 0}, {"armed": 0}, None, {"armed": 1, "delivered": 1}]

    def sender(t: str, b: str) -> Any:
        sent.append(t)
        return answers[len(sent) - 1]

    doc = {"status": "REFUSED", "n_refused": 1,
           "refused": {"desks/mt5/data/a.json": [{"key": "login", "line": 3}]}}
    t0 = datetime(2026, 10, 21, tzinfo=UTC)
    for i in range(3):   # delivered 0, delivered absent, a non-dict answer: none of them paged
        got = lf.page(doc, tmp_path, sender=sender, now=t0 + timedelta(minutes=i))
        assert got["sent"] is False and "undelivered" in got["reason"]
        assert not (tmp_path / lf.PAGE_STATE_REL).exists(), "silence was recorded as a page"
    assert lf.page(doc, tmp_path, sender=sender, now=t0 + timedelta(minutes=3))["sent"]
    assert not lf.page(doc, tmp_path, sender=sender, now=t0 + timedelta(minutes=4))["sent"]
    assert len(sent) == 4



# v5c (2026-10-21, audit hold on v5b). Every Unicode Cf (format) character is dropped before
# matching, literal or JSON-escaped; more separators, and `/ : ( )`. Synthetic numbers only.
_CF = {"zwsp": "​", "zwnj": "‌", "zwj": "‍", "wj": "⁠", "bom": "﻿",
       "lrm": "‎", "rlm": "‏", "soft-hyphen": "­"}


@pytest.mark.parametrize("ch", list(_CF.values()), ids=list(_CF))
@pytest.mark.parametrize("escaped", [False, True], ids=["literal", "json-escaped"])
def test_a_format_character_inside_a_declared_number_is_dropped(ch: str, escaped: bool) -> None:
    mark = f"\\u{ord(ch):04x}" if escaped else ch
    text = f'{{"note": "refused for {_SID[:3]}{mark}{_SID[3:]}."}}'
    got = lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS)
    assert lf.ID_FINDING in [h["key"] for h in got], repr(text)
    assert _SID not in json.dumps(got)


@pytest.mark.parametrize("ch", list(_CF.values()), ids=list(_CF))
def test_a_format_character_does_not_hide_a_login_key_or_value(ch: str) -> None:
    for text in (f'{{"login": {_SID[:2]}{ch}{_SID[2:]}}}', f'{{"lo{ch}gin": {_SID}}}',
                 f"time,Login\nt,{_SID[:4]}{ch}{_SID[4:]}\n"):
        rel = "desks/mt5/data/x.csv" if text.startswith("time") else "desks/mt5/data/x.json"
        assert lf.findings(rel, text.encode()), repr(text)


@pytest.mark.parametrize("text", [
    "555 -  - 1234", "555 ,  1234", "(555) 1234", "555/1234", "555:1234", "(555)-(1234)",
    "555" + " " * 10 + "1234",
], ids=["four-plus", "four-mixed", "parens", "slash", "colon", "parens-hyphen", "ten-spaces"])
def test_more_separators_and_slash_colon_parens_split_a_declared_number(text: str) -> None:
    got = lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS)
    assert lf.ID_FINDING in [h["key"] for h in got], text


# v5d: "(1) 555 1234" and "555 1234 (2)" left this list. They are the auditor's
# `acct 555-1234 (2 trades)` shape -- a tight `) ` / ` (` boundary, then something else -- and are
# now pinned as CAUGHT below. A run identical to the number's own separator still continues it.
@pytest.mark.parametrize("text", ["1/555/1234", "555:1234:9", "12:555:1234", "555    1234    5"],
                         ids=["slash-prefix", "colon-suffix", "clock", "spaced-suffix"])
def test_the_adjacent_digit_rule_holds_across_the_new_separators(text: str) -> None:
    assert lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS) == [], text


@pytest.mark.parametrize("text", ['{"id": "DSD_X_2023@DF_X"}', "DSD_X_2023​@DF_X",
                                  "(DSD_X_2023@DF_X)", "a/DSD_X_2023@DF_X:1"],
                         ids=["oecd", "oecd-zwsp", "oecd-parens", "oecd-slash-colon"])
def test_oecd_ids_still_pass_with_the_v5c_normalisation(text: str) -> None:
    assert lf.findings("desks/mt5/reports/PIT_LAG_CENSUS.json", text.encode(), _SIDS) == [], text


# v5c (2026-10-21): `account_profile.declaration_key` is the PLAIN "<login>@<server>" -- the raw
# login, by design, for the box-local declarations file. A blob carrying one must never publish.
def _declaration_key(login: object, server: object) -> str:
    import sys
    desk = str(ROOT / "desks" / "mt5")
    if desk not in sys.path:
        sys.path.insert(0, desk)
    from mt5desk import account_profile
    key = account_profile.declaration_key({"login": login, "server": server})
    assert key is not None
    return key


@pytest.mark.parametrize("ids", [frozenset(), frozenset({"7000001"})],
                         ids=["nothing-declared", "declared"])
@pytest.mark.parametrize("shape", [
    "{key}",
    '{{"note": "account {key} is declared E8 One (declared in ACCOUNT_PROFILES.json)"}}',
    '{{"accounts": {{"{key}": "e8-one"}}}}',
    "2026-10-21T00:00:00+00:00 PORTFOLIO HEAT CAP: VENUE bar 3.50% [account {key} is declared]",
], ids=["bare", "why-sentence", "declarations-shape", "gateway-log-line"])
def test_the_fence_refuses_a_blob_carrying_a_declaration_key(shape: str,
                                                             ids: frozenset[str]) -> None:
    key = _declaration_key("7000001", "Srv-1")       # fake login, fake server
    assert key == "7000001@Srv-1"
    got = lf.findings("desks/mt5/reports/X.json", shape.format(key=key).encode(), ids)
    assert got, shape
    assert {h["key"] for h in got} & {"<login@server>", lf.ID_FINDING}
    assert "7000001" not in json.dumps(got), "a finding must never carry the login"


def test_the_cli_refuses_a_declaration_key_blob_and_never_writes_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io
    key = _declaration_key(" 7000001 ".strip(), "Srv-1")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    blob = _git(tmp_path, "hash-object", "-w", "--stdin",
                data=json.dumps({"why": f"account {key} is declared"}).encode())
    monkeypatch.delenv(lf.ID_ENV, raising=False)
    monkeypatch.setattr(lf, "record_alert", lambda doc, root=None: "OPEN")
    monkeypatch.setattr(lf, "page", lambda doc, root=None: {})
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{blob}\tdesks/mt5/reports/X.json\n"))
    art = tmp_path / "F.json"
    assert lf.main(["--repo", str(tmp_path), "--artifact", str(art)]) == 0
    out = capsys.readouterr().out
    assert out.split() == ["desks/mt5/reports/X.json"], "the blob must be refused"
    assert "7000001" not in art.read_text("utf-8") and "7000001" not in out


# v5d (2026-10-21, audit hold on v5c). Fake declared number 5551234 throughout.
def _escape(text: str, levels: int) -> str:
    """`text` JSON-string-escaped `levels` times (1 = `\\u200b`, 2 = `\\\\u200b`, ...)."""
    for _ in range(levels):
        text = json.dumps(text)[1:-1]
    return text


@pytest.mark.parametrize("levels", [1, 2, 3], ids=["single", "double", "triple"])
@pytest.mark.parametrize("ch", ["\u200b", "\U000e0001", "\U0001d173", "\u0665"],
                         ids=["zwsp", "tag-astral-pair", "music-astral-pair", "arabic-digit"])
def test_escaped_forms_of_a_declared_number_are_decoded_to_a_fixpoint(
        levels: int, ch: str) -> None:
    raw = f"{_SID[:3]}{ch}{_SID[3:]}" if ch != "\u0665" else _SID.replace("5", ch, 1)
    text = '{"note": "' + _escape(raw, levels) + '"}'
    assert "\\u" in text and not any(ord(c) > 127 for c in text), text   # escaped only
    got = lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS)
    assert lf.ID_FINDING in [h["key"] for h in got], text


@pytest.mark.parametrize("levels", [1, 2, 3], ids=["single", "double", "triple"])
@pytest.mark.parametrize("raw", [f"{_SID}@FusionMarkets-Live", f"{_SID}\u200b@Srv-1",
                                 f"{_SID}@\U000e0041Srv-1"],
                         ids=["plain-at", "zwsp-before-at", "tag-after-at"])
def test_escaped_at_server_forms_are_caught_with_nothing_declared(levels: int, raw: str) -> None:
    text = json.dumps({"why": _escape(raw, levels - 1)}, ensure_ascii=True)
    text = text.replace("@", "\\u0040") if levels == 1 else text
    got = lf.findings("desks/mt5/data/x.json", text.encode())
    assert "<login@server>" in [h["key"] for h in got], text


def test_an_escaped_backslash_is_not_read_as_an_escape() -> None:
    """`\\\\u0035` is a literal backslash then `u0035`: one level decodes it to `\\u0035`, the
    next to `5`. The v5c decoder read the second backslash as an escape and left a stray one."""
    assert lf._unescape_once("\\\\u0035") == "\\u0035"
    assert lf._unescape_once(lf._unescape_once("\\\\u0035")) == "5"
    assert lf._unescape_once("\\ud83d\\ude00") == "\U0001f600"
    assert lf._unescape_once("a\\nb") == "a\\nb", "\\n is never undone: line numbers hold"


@pytest.mark.parametrize("text", ["acct 555-1234 (2 trades)", "555 1234 / 2",
                                  "ref 555-1234: 3 fills", "(1) 555 1234", "555 1234 (2)"],
                         ids=["acct-paren-count", "slash-count", "colon-fills",
                              "paren-prefix", "paren-suffix"])
def test_a_tight_boundary_ends_the_number(text: str) -> None:
    got = lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS)
    assert lf.ID_FINDING in [h["key"] for h in got], text


_DI = {"cgj": "\u034f", "hangul-choseong-filler": "\u115f", "hangul-jungseong-filler": "\u1160",
       "khmer-aq": "\u17b4", "khmer-aa": "\u17b5", "mongolian-fvs1": "\u180b",
       "mongolian-vs": "\u180e", "mongolian-fvs4": "\u180f", "hangul-filler": "\u3164",
       "vs1": "\ufe00", "vs16": "\ufe0f", "halfwidth-hangul-filler": "\uffa0",
       "tag-e0000": "\U000e0000", "tag-space": "\U000e0020", "vs17": "\U000e0100",
       "e0fff": "\U000e0fff"}


@pytest.mark.parametrize("ch", list(_DI.values()), ids=list(_DI))
@pytest.mark.parametrize("escaped", [False, True], ids=["literal", "json-escaped"])
def test_a_default_ignorable_character_inside_a_declared_number_is_dropped(
        ch: str, escaped: bool) -> None:
    raw = f"refused for {_SID[:3]}{ch}{_SID[3:]}."
    text = json.dumps({"note": raw}, ensure_ascii=escaped)
    got = lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS)
    assert lf.ID_FINDING in [h["key"] for h in got], repr(text)


def test_the_default_ignorable_table_is_declared_and_covers_the_audit_list() -> None:
    table = lf._ignorable_table()
    for cp in (0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, *range(0x180B, 0x1810), 0x3164,
               *range(0xFE00, 0xFE10), 0xFFA0, 0xE0000, 0xE0FFF, 0x00AD, 0x200B, 0xFEFF):
        assert cp in table, hex(cp)
    for cp in (ord("5"), ord("@"), ord(" "), 0x00A0, ord("\n")):
        assert cp not in table, hex(cp)


# v5e (2026-10-21): a run that differs from the number's own group separator ends it --
# `x,555-1234,2` and `555-1234,2 lots` name the account and then a list item. The same-separator
# tail `555 1234 2` continues the number (like `1,555,1234`): ruled either way, pinned NOT caught.
@pytest.mark.parametrize("text", ["x,555-1234,2", "555-1234,2 lots", "555.1234,7", "a;555-1234,2"],
                         ids=["comma-list", "comma-lots", "dot-then-comma", "semicolon-list"])
def test_a_different_separator_after_the_number_ends_it(text: str) -> None:
    got = lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS)
    assert lf.ID_FINDING in [h["key"] for h in got], text


@pytest.mark.parametrize("text", ["555 1234 2", "1,555,1234", "555-1234-6", "9.555.1234"],
                         ids=["same-space-tail", "same-comma-head", "same-hyphen-tail",
                              "same-dot-head"])
def test_the_same_separator_continues_the_number(text: str) -> None:
    assert lf.findings("desks/mt5/data/x.json", text.encode(), _SIDS) == [], text


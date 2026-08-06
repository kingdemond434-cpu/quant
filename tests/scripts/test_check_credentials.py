"""THE CREDENTIAL INVENTORY -- and the one property that makes it safe to run at all.

Fourteen credential files are read from fifteen places, each with its own SILENT
graceful-degradation path, because a missing key must never crash an organ. The sum of fifteen
silent degradations is a desk that appears healthy while most of it is switched off.

THE PROPERTY THAT MATTERS MOST HERE IS NEGATIVE: this tool must never print a key. Its whole value
is that its output can be pasted into a chat, a ticket or a commit message, and a tool that leaked
a secret once would be a tool nobody could ever run again. So the first test writes realistic
secrets and asserts that NO substring of any of them appears anywhere in the output, in either
format.

The second property: PRESENT-BUT-BROKEN ranks worse than absent. A truncated or malformed file
LOOKS configured, so nobody checks it again, while every reader treats it as missing -- the
degradation is silent AND the inventory says it is fine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_credentials as CC

_SECRET_VALUES = {
    "api_key": "AKIAVERYSECRETKEYVALUE1234567890",
    "api_secret": "s3cr3tSHHHdonotleakthisvalue0987654321",
    "topic": "quant-do-not-publish-this-topic-name",
    "url": "https://hc-ping.com/11111111-2222-3333-4444-555555555555",
    "key": "fredkey-abcdefghijklmnop",
    "authtoken": "ngroktoken-abcdefghijklmnop",
    "token": "netlify-token-abcdefghijklmnop",
    "site_id": "site-abcdefghijklmnop",
    "client_id": "naver-client-abcdefgh",
    "client_secret": "naver-secret-abcdefgh",
}


def _populate(secrets: Path) -> list[str]:
    """Write a plausible, fully-populated secrets directory. Returns every secret value used."""
    secrets.mkdir(parents=True, exist_ok=True)
    used: list[str] = []
    for cred in CC.CREDENTIALS:
        doc: dict[str, object] = {}
        for k in cred.shape:
            if k == "providers":
                doc[k] = [{"base_url": "https://openrouter.ai/api/v1", "key": "sk-or-LEAKME1234"}]
                used.append("sk-or-LEAKME1234")
            elif k == "channels":
                doc[k] = [{"kind": "telegram", "token": "tg-LEAKME5678", "chat_id": "42"}]
                used.append("tg-LEAKME5678")
            else:
                v = _SECRET_VALUES.get(k, f"value-for-{k}-LEAKME")
                doc[k] = v
                used.append(v)
        (secrets / cred.name).write_text(json.dumps(doc), "utf-8")
    return used


# ------------------------------------------------------------------ the negative property

def test_NO_SECRET_VALUE_APPEARS_IN_THE_OUTPUT(tmp_path: Path, monkeypatch, capsys) -> None:
    """THE PROPERTY THAT MAKES THIS TOOL SAFE TO RUN. Its value is that the output can be pasted
    into a chat, a ticket or a commit message. A tool that leaked a key once is one nobody can ever
    run again -- and the leak would be discovered by the person reading the paste."""
    monkeypatch.setattr(CC, "SECRETS", tmp_path / "secrets")
    used = _populate(tmp_path / "secrets")

    monkeypatch.setattr("sys.argv", ["check_credentials.py"])
    CC.main()
    human = capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["check_credentials.py", "--json"])
    CC.main()
    machine = capsys.readouterr().out

    for secret in used:
        assert secret not in human, f"a secret value reached the human output: {secret[:8]}..."
        assert secret not in machine, f"a secret value reached the JSON output: {secret[:8]}..."


def test_the_report_carries_LENGTHS_rather_than_values(tmp_path: Path, monkeypatch) -> None:
    """Enough to catch a truncated paste, useless to anyone who obtains the output."""
    monkeypatch.setattr(CC, "SECRETS", tmp_path / "secrets")
    _populate(tmp_path / "secrets")
    rep = CC.build()
    ok = [r for r in rep["credentials"] if r["status"] == "OK"]
    assert ok
    for r in ok:
        assert "chars>" in r["detail"] or "entries>" in r["detail"]


def test_the_inventory_WRITES_NOTHING(tmp_path: Path, monkeypatch) -> None:
    """A tool that mutated the secrets directory while reporting on it would be one nobody should
    point at a live box."""
    monkeypatch.setattr(CC, "SECRETS", tmp_path / "secrets")
    _populate(tmp_path / "secrets")
    before = {p: p.stat().st_mtime_ns for p in (tmp_path / "secrets").rglob("*")}
    CC.build()
    after = {p: p.stat().st_mtime_ns for p in (tmp_path / "secrets").rglob("*")}
    assert before == after


def test_it_never_reaches_the_network() -> None:
    """Validating a key against a venue would spend a rate limit to answer a question about a FILE,
    and on the money-path keys it would place the desk's credentials on the wire to check they are
    present."""
    src = Path(CC.__file__).read_text("utf-8")
    for banned in ("urllib.request", "requests", "httpx", "socket.", "hmac"):
        assert banned not in src, f"{banned} in a presence-and-shape inventory"


# ------------------------------------------------------------------ statuses

def test_an_absent_directory_reports_every_credential_MISSING(tmp_path: Path,
                                                              monkeypatch) -> None:
    monkeypatch.setattr(CC, "SECRETS", tmp_path / "nothing-here")
    rep = CC.build()
    assert rep["secrets_dir_exists"] is False
    assert rep["n_missing"] == rep["n_declared"] == len(CC.CREDENTIALS)
    assert rep["n_present"] == 0


def test_a_fully_populated_directory_reports_every_credential_OK(tmp_path: Path,
                                                                 monkeypatch) -> None:
    """The positive control. An inventory that reported MISSING whatever it was given would be
    indistinguishable from a broken box."""
    monkeypatch.setattr(CC, "SECRETS", tmp_path / "secrets")
    _populate(tmp_path / "secrets")
    rep = CC.build()
    assert rep["n_present"] == len(CC.CREDENTIALS)
    assert rep["n_missing"] == 0 and rep["n_broken"] == 0
    assert all(v > 0 for v in rep["by_tier"].values())


def test_UNREADABLE_ranks_WORSE_than_missing_and_is_listed_first(tmp_path: Path,
                                                                 monkeypatch) -> None:
    """A truncated or malformed file LOOKS configured, so nobody checks it again -- while every
    reader treats it as absent. That is strictly worse than a file that is simply not there."""
    secrets = tmp_path / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "ntfy.json").write_text('{"topic": "quant-', "utf-8")      # truncated paste
    monkeypatch.setattr(CC, "SECRETS", secrets)
    rep = CC.build()
    row = next(r for r in rep["credentials"] if r["file"].endswith("ntfy.json"))
    assert row["status"] == "UNREADABLE"
    assert "LOOKS configured" in row["detail"] or "looks" in row["detail"].lower()
    assert rep["worst_first"][0].endswith("ntfy.json")


def test_an_INCOMPLETE_file_names_the_missing_field(tmp_path: Path, monkeypatch) -> None:
    """'binance_live.json is wrong' sends someone to re-read the docs. 'missing api_secret' does
    not."""
    secrets = tmp_path / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "binance_live.json").write_text(json.dumps({"api_key": "k"}), "utf-8")
    monkeypatch.setattr(CC, "SECRETS", secrets)
    row = next(r for r in CC.build()["credentials"] if r["file"].endswith("binance_live.json"))
    assert row["status"] == "INCOMPLETE" and "api_secret" in row["detail"]


def test_an_EMPTY_value_counts_as_incomplete_not_as_present(tmp_path: Path,
                                                            monkeypatch) -> None:
    """An empty string is the shape of a placeholder somebody meant to fill in. Counting it as
    present is how a file passes the inventory and fails at the venue."""
    secrets = tmp_path / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "fred.json").write_text(json.dumps({"key": ""}), "utf-8")
    monkeypatch.setattr(CC, "SECRETS", secrets)
    row = next(r for r in CC.build()["credentials"] if r["file"].endswith("fred.json"))
    assert row["status"] == "INCOMPLETE"


def test_a_top_level_LIST_is_MALFORMED_rather_than_crashing(tmp_path: Path,
                                                            monkeypatch) -> None:
    secrets = tmp_path / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "fred.json").write_text("[1, 2, 3]", "utf-8")
    monkeypatch.setattr(CC, "SECRETS", secrets)
    row = next(r for r in CC.build()["credentials"] if r["file"].endswith("fred.json"))
    assert row["status"] == "MALFORMED"


# ------------------------------------------------------------------ the declarations themselves

def test_every_declared_credential_is_actually_READ_somewhere_in_the_repo() -> None:
    """A declaration for a file nothing reads is a setup step that buys nothing, and it makes the
    real ones harder to find -- the same complaint the module makes about a ledger of $0 events."""
    import subprocess
    root = Path(CC.__file__).resolve().parent.parent
    for cred in CC.CREDENTIALS:
        hits = subprocess.run(
            ["grep", "-rl", f"data/secrets/{cred.name}", "scripts", "libs", "ops"],
            cwd=root, capture_output=True, text=True, check=False).stdout.split()
        consumers = [h for h in hits if "check_credentials" not in h]
        assert consumers, f"{cred.name} is declared but nothing reads it"


def test_every_credential_states_what_BREAKS_and_HOW_to_get_it() -> None:
    """A checklist entry with no consequence attached gets skipped, and one with no acquisition
    path gets postponed. Both are how a desk stays half-dark for weeks."""
    for cred in CC.CREDENTIALS:
        assert len(cred.without) > 30, f"{cred.name} does not say what breaks"
        assert len(cred.how) > 30, f"{cred.name} does not say how to get it"
        assert len(cred.unlocks) > 10
        assert cred.shape, f"{cred.name} declares no required fields"


def test_the_money_tier_credentials_carry_the_withdrawal_warning() -> None:
    """Withdrawal permission is never required by this desk, and granting it converts a key leak
    from a bad trade into a total loss. The instruction has to be at the point of creation."""
    for cred in CC.CREDENTIALS:
        if cred.tier == "money" and "live" in cred.name:
            assert "ithdraw" in cred.how, f"{cred.name} does not warn about withdrawal permission"


def test_the_tiers_are_the_declared_three() -> None:
    assert {c.tier for c in CC.CREDENTIALS} <= {"money", "research", "ops"}


def test_no_credential_is_declared_twice() -> None:
    names = [c.name for c in CC.CREDENTIALS]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("flag", [[], ["--json"], ["--missing"]])
def test_every_cli_mode_runs_and_exits_zero(tmp_path: Path, monkeypatch, capsys, flag) -> None:
    monkeypatch.setattr(CC, "SECRETS", tmp_path / "secrets")
    monkeypatch.setattr("sys.argv", ["check_credentials.py", *flag])
    assert CC.main() == 0
    assert capsys.readouterr().out.strip()

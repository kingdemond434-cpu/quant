"""The credential registry and the coverage leg: names, presence, never a value.

The load-bearing assertions:
  * every var on the principal's 2026-09-30 setx list is registered with a consumer;
  * a var set under a name some consumer does not read is MISMATCHED_NAME, not SET;
  * no value -- from the environment or a secrets file -- ever reaches a status, the JSON report
    or the markdown, and an absent key is BLOCKED_AUTH, never 0.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import credentials as cred  # noqa: E402

SENTINEL = "SENTINEL-VALUE-must-never-appear-0xC0FFEE"
PRINCIPAL = ("GITHUB_TOKEN", "REDDIT_CLIENT_ID", "REDDIT_SECRET", "TELEGRAM_API_ID",
             "TELEGRAM_API_HASH", "FRED_API_KEY", "EIA_API_KEY", "NASDAQ_DATA_LINK_KEY",
             "EDINET_API_KEY", "DART_API_KEY", "ESTAT_APP_ID", "KOSIS_API_KEY", "TUSHARE_TOKEN",
             "JQ_USER", "JQ_PASS", "OPENROUTER_API_KEY")


def _cc():
    import credential_coverage
    return credential_coverage


def test_every_principal_var_is_registered_with_a_consumer() -> None:
    for name in PRINCIPAL:
        v = cred.BY_ENV[name]
        assert v.principal_list, name
        assert v.consumers, f"{name} has no consumer"
        assert v.signup_url.startswith("https://"), name


def test_every_var_names_a_signup_and_either_a_consumer_or_why_not() -> None:
    for v in cred.REGISTRY:
        assert v.signup_url.startswith("https://"), v.env
        assert v.consumers or v.built.startswith("NOT_BUILT: "), v.env


def test_coordinator_candidates_are_registered() -> None:
    for name in ("ECOS_API_KEY", "BLS_API_KEY", "BEA_API_KEY", "FINNHUB_API_KEY",
                 "TIINGO_API_KEY", "SEC_EDGAR_USER_AGENT", "JQUANTS_MAIL", "JQUANTS_PASSWORD",
                 "JQUANTS_REFRESH_TOKEN", "KOBIS_API_KEY", "SEOUL_API_KEY", "FIRMS_MAP_KEY"):
        assert name in cred.BY_ENV, name
    assert "SEC_EDGAR_UA" in cred.BY_ENV["SEC_EDGAR_USER_AGENT"].accepted
    assert "QUANT_EDGAR_UA" in cred.BY_ENV["SEC_EDGAR_USER_AGENT"].accepted


def test_absent_is_blocked_auth_never_zero() -> None:
    st = cred.status(cred.BY_ENV["EIA_API_KEY"], environ={}, root=Path("/nonexistent"))
    assert st["status"] == cred.BLOCKED_AUTH
    assert st["dark_consumers"]


def test_canonical_name_is_set() -> None:
    st = cred.status(cred.BY_ENV["EIA_API_KEY"], environ={"EIA_API_KEY": SENTINEL})
    assert st == {"status": cred.SET, "present_as": ["EIA_API_KEY"], "dark_consumers": [],
                  "resolved_on_merge": []}


def test_a_name_one_consumer_does_not_read_is_mismatched() -> None:
    """OPENAI_API_KEY lights llm_seat but deepseek_cycle reads OPENROUTER_API_KEY only."""
    st = cred.status(cred.BY_ENV["OPENROUTER_API_KEY"], environ={"OPENAI_API_KEY": SENTINEL},
                     root=Path("/nonexistent"))
    assert st["status"] == cred.MISMATCHED_NAME
    assert st["dark_consumers"] == ["libs/ops/deepseek_cycle.py"]
    st = cred.status(cred.BY_ENV["SEC_EDGAR_USER_AGENT"],
                     environ={"SEC_EDGAR_USER_AGENT": SENTINEL}, root=Path("/nonexistent"))
    assert st["status"] == cred.MISMATCHED_NAME
    assert "desks/mt5/research/alpha_capture.py" in st["dark_consumers"]
    assert SENTINEL not in json.dumps(st)


def test_secrets_file_is_read_by_key_name_only(tmp_path: Path) -> None:
    d = tmp_path / "desks" / "mt5" / "data" / "secrets"
    d.mkdir(parents=True)
    (d / "disclosure_apis.json").write_text(json.dumps({"EDINET_API_KEY": SENTINEL}), "utf-8")
    st = cred.status(cred.BY_ENV["EDINET_API_KEY"], environ={}, root=tmp_path)
    assert st["status"] == cred.SET
    assert st["present_as"] == ["file:desks/mt5/data/secrets/disclosure_apis.json#EDINET_API_KEY"]
    assert SENTINEL not in json.dumps(st)
    st = cred.status(cred.BY_ENV["DART_API_KEY"], environ={}, root=tmp_path)
    assert st["status"] == cred.BLOCKED_AUTH


def test_name_mismatches_record_the_edgar_split() -> None:
    mm = {(m["var"], m["consumer"]) for m in cred.name_mismatches()}
    assert ("SEC_EDGAR_USER_AGENT", "desks/mt5/research/alpha_capture.py") in mm
    assert ("SEC_EDGAR_USER_AGENT", "desks/mt5/research/corporate_disclosure.py") in mm


def test_other_lanes_status_words_map_to_blocked_auth() -> None:
    for w in ("BLOCKED_NO_KEY", "NEEDS_CREDENTIAL", "BLOCKED_ON_KEY:ESTAT_APP_ID"):
        assert cred.normalise_status(w) == cred.BLOCKED_AUTH
    assert cred.normalise_status("OK") == "OK"


def test_keyed_estimates_are_derived_from_the_roster() -> None:
    e = cred.estimate_for(cred.BY_ENV["EIA_API_KEY"])
    roster = json.loads(cred.KS_ROSTER.read_text("utf-8"))
    pairs = sum(len(s["instruments"]) for r in roster["sources"]
                if r["key_env"][:1] == ["EIA_API_KEY"] for s in r["series"].values())
    assert e.series == pairs and e.cells_per_pair == cred.KS_CELLS_PER_PAIR
    assert e.cells_per_day == min(pairs * cred.KS_CELLS_PER_PAIR, cred.KS_PER_PASS * 24)


def test_setx_lines_carry_placeholders_only() -> None:
    for v in cred.REGISTRY:
        line = cred.setx_line(v)
        assert line.startswith(f"setx {v.env} \"<") and line.endswith(">\"")


# ----------------------------------------------------------------------- the leg ----------
def _desk(tmp_path: Path) -> Path:
    desk = tmp_path / "desks" / "mt5"
    (desk / "data" / "intelligence").mkdir(parents=True)
    return desk


def test_coverage_report_names_every_var_and_never_a_value(tmp_path: Path) -> None:
    cc = _cc()
    env = dict.fromkeys(("EIA_API_KEY", "OPENAI_API_KEY", "GITHUB_TOKEN"), SENTINEL)
    doc = cc.build(now=datetime(2026, 9, 30, 12, tzinfo=UTC), environ=env, root=cc.ROOT,
                   desk=_desk(tmp_path))
    text = json.dumps(doc)
    assert SENTINEL not in text
    by = {r["env"]: r for r in doc["vars"]}
    assert set(PRINCIPAL) <= set(by)
    assert by["EIA_API_KEY"]["status"] == cred.SET
    assert by["OPENROUTER_API_KEY"]["status"] == cred.MISMATCHED_NAME
    assert by["KOSIS_API_KEY"]["status"] == cred.BLOCKED_AUTH
    assert [r["rank"] for r in doc["vars"]] == list(range(1, len(doc["vars"]) + 1))
    assert all(r["estimate"]["label"] == "ESTIMATE" for r in doc["vars"])
    ks = next(c for c in by["EIA_API_KEY"]["consumers"]
              if c["path"] == "desks/mt5/research/keyed_sources.py")
    assert ks["on_this_checkout"] and ks["wired"] == "WIRED"
    assert "desks/mt5/research/hourly_cycle.py" in ks["clocks"]
    assert ks["cells_24h"] == cred.UNMEASURED            # no seat directory in the temp desk
    tu = by["TUSHARE_TOKEN"]["consumers"][0]
    assert tu["wired"] in ("NOT_ON_THIS_BRANCH", "WIRED")
    md = cc.markdown(doc)
    assert SENTINEL not in md and 'setx EIA_API_KEY "<key>"' in md
    assert "## No key needed" in md


def test_cells_24h_are_read_from_the_consumers_donation_files(tmp_path: Path) -> None:
    cc = _cc()
    desk = _desk(tmp_path)
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    seat = desk / "data" / "intelligence" / "keyed_sources"
    seat.mkdir()
    rows = [{"credential_var": "EIA_API_KEY"}] * 3 + [{"credential_var": "BLS_API_KEY"}]
    (seat / f"discoveries_{(now - timedelta(hours=2)):%Y%m%d_%H%M}.json").write_text(
        json.dumps({"discoveries": rows}), "utf-8")
    (seat / f"discoveries_{(now - timedelta(hours=30)):%Y%m%d_%H%M}.json").write_text(
        json.dumps({"discoveries": rows}), "utf-8")
    c = next(c for c in cred.BY_ENV["EIA_API_KEY"].consumers if c.seats)
    got = cc.cells_24h("EIA_API_KEY", c, now, desk)
    assert got["cells_24h"] == 3 and got["attribution"] == "per_var" and got["files"] == 1
    got = cc.cells_24h("KOSIS_API_KEY", c, now, desk)
    assert got["cells_24h"] == 0                          # measured zero: the seat exists


def test_a_branch_that_accepts_the_name_is_resolved_on_merge_not_mismatched() -> None:
    v = cred.CredentialVar(
        env="SEC_EDGAR_USER_AGENT", provider="p", signup_url="https://x", free_tier="",
        unlocks="", instruments=(), families=(),
        consumers=(cred.Consumer("desks/mt5/research/not_here_yet.py",
                                 ("QUANT_EDGAR_UA", "SEC_EDGAR_USER_AGENT"), "claude/x (#1)"),
                   cred.Consumer("desks/mt5/research/sandboxes/edgar_transmission.py",
                                 ("QUANT_EDGAR_UA",))),
        aliases=("QUANT_EDGAR_UA", "SEC_EDGAR_UA"))
    st = cred.status(v, environ={"SEC_EDGAR_USER_AGENT": SENTINEL})
    # edgar_transmission is on this checkout and its FILE accepts all three names, whatever the
    # declaration says; the off-branch reader accepts the name on its branch.
    assert st["status"] == cred.SET
    assert st["resolved_on_merge"] == ["desks/mt5/research/not_here_yet.py"]


def test_every_edgar_reader_on_this_branch_accepts_all_three_names() -> None:
    import subprocess
    out = subprocess.run(["git", "grep", "-l", "QUANT_EDGAR_UA\\|SEC_EDGAR_UA\\|"
                          "SEC_EDGAR_USER_AGENT", "--", "*.py", ":!tests", ":!libs/data"],
                         cwd=ROOT, capture_output=True, text=True, check=False).stdout.split()
    readers = [p for p in out if "environ" in (ROOT / p).read_text("utf-8")]
    assert readers
    for p in readers:
        text = (ROOT / p).read_text("utf-8")
        for name in ("QUANT_EDGAR_UA", "SEC_EDGAR_USER_AGENT", "SEC_EDGAR_UA"):
            assert name in text, (p, name)


def test_coverage_names_its_cro_duty_and_measures_the_keyless_doors(tmp_path: Path) -> None:
    cc = _cc()
    desk = _desk(tmp_path)
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    seat = desk / "data" / "intelligence" / "keyed_sources"
    seat.mkdir()
    (seat / f"discoveries_{(now - timedelta(hours=1)):%Y%m%d_%H%M}.json").write_text(
        json.dumps({"discoveries": [{"credential_var": "KEYLESS:BIS"}] * 5}), "utf-8")
    doc = cc.build(now=now, environ={}, root=cc.ROOT, desk=desk)
    assert doc["cro_duty"] == "D24"
    by = {k["provider"].split()[0]: k for k in doc["keyless"]}
    for prov in ("BIS", "OECD", "IMF"):
        assert by[prov]["status"] == "WIRED", prov
        assert "desks/mt5/research/hourly_cycle.py" in by[prov]["clocks"]
    assert by["BIS"]["cells_24h"] == 5 and by["OECD"]["cells_24h"] == 0

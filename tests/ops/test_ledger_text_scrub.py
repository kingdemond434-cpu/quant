"""The CRO ledger's free text is scrubbed of money figures and hosts before it is published."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.ops import account_withhold as aw  # noqa: E402

REL = "desks/mt5/data/cro_cycle_ledger.jsonl"


def test_money_hosts_and_servers_are_withheld() -> None:
    s = aw.public_text("E8 equity 103,227.24 and balance=$99,812.10; lost £1,200 on "
                       "server=FusionMarkets-Live via 203.0.113.7 and dash.example.org")
    for leak in ("103,227.24", "99,812.10", "1,200", "FusionMarkets-Live", "203.0.113.7",
                 "example.org"):
        assert leak not in s
    assert "equity [money]" in s and "[addr]" in s and "[host]" in s


def test_counts_shas_dates_and_files_stay_readable() -> None:
    text = ("judging below creation (5,266 vs 8,303/day) at 0b85b72e on 2026-11-11T12:02Z; "
            "see desks/mt5/reports/CRO_DUTIES.json and hourly_cycle.py, 24 duties missed")
    assert aw.public_text(text) == text


def test_only_changed_lines_are_reserialised() -> None:
    clean = '{"lane":"noon","event":"start",  "pid":26412}\r\n'
    dirty = {"lane": "noon_box", "binding_constraint": "equity 103,227.24 at risk"}
    data = (clean + json.dumps(dirty) + "\n" + "not json\n").encode("utf-8")
    out, n = aw.scrub_text_for_publish(REL, data)
    assert n == 1 and out is not None
    lines = out.decode("utf-8").splitlines(keepends=True)
    assert lines[0] == clean and lines[2] == "not json\n"
    assert json.loads(lines[1])["binding_constraint"] == "equity [money] at risk"


def test_a_clean_file_and_an_unscrubbed_path_are_left_alone() -> None:
    data = b'{"lane":"noon","why":"no figures here"}\n'
    assert aw.scrub_text_for_publish(REL, data) == (None, 0)
    assert aw.scrub_text_for_publish("desks/mt5/data/sleeves.json", b"equity 5.00") == (None, 0)


def test_structured_money_and_server_fields_are_withheld_by_key() -> None:
    row = {"lane": "noon", "work_items": {"gold": {"equity": 266.01, "account_balance": 457.74,
                                                   "pnl": -12.5, "free_margin": "1,200.00",
                                                   "server": "FusionMarkets-Live", "login": 1234567,
                                                   "n_trades": 23, "k_eff": 4.2, "pid": 26412}}}
    out, n = aw.scrub_text_for_publish(REL, (json.dumps(row) + "\n").encode("utf-8"))
    assert n == 1 and out is not None
    gold = json.loads(out)["work_items"]["gold"]
    for key in ("equity", "account_balance", "pnl", "free_margin"):
        assert gold[key] == "[money]"
    assert gold["server"] == "[withheld]" and gold["login"] == "[withheld]"
    assert (gold["n_trades"], gold["k_eff"], gold["pid"]) == (23, 4.2, 26412)

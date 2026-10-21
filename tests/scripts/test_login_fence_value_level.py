"""The login fence reads a declared login as a VALUE under ANY key (v5f, the BARS_STATE audit).

The text matcher sees a declared number only as it is spelled. A parsed value can denote the
same number with no matching digit run -- leading zeros, 0x-hex, a JSON document escaped inside
a string -- under a key nobody would call a login. These pin that such a value is refused, that
the finding names the key and never the value, and that a different number is not refused.
Every number here is synthetic.
"""

from __future__ import annotations

import json

import pytest

from libs.ops import login_fence as lf

_ID = "5551234"
_ID2 = "7000001"
_IDS = frozenset({_ID, _ID2})
_HEX = hex(int(_ID))


def _value_rows(rel: str, text: str, ids: frozenset[str] = _IDS) -> list[dict[str, object]]:
    return [f for f in lf.findings(rel, text.encode(), ids)
            if str(f["key"]).startswith(lf.VALUE_FINDING)]


@pytest.mark.parametrize("doc", [
    {"symbol_id": "000" + _ID},                     # leading zeros: no bounded digit run
    {"magic": _HEX},                                # 0x-hex
    {"magic": _HEX.upper().replace("0X", "0x")},
    {"n": [1, 2, {"deep": "00" + _ID2}]},           # nested, under any key, in a list
    {"blob": json.dumps({"inner": "0" + _ID})},     # a JSON document inside a string
    {"blob": json.dumps(json.dumps({"inner": "0" + _ID}))},   # twice
])
def test_a_declared_login_as_a_value_under_any_key_is_refused(doc: dict[str, object]) -> None:
    text = json.dumps(doc)
    rows = _value_rows("desks/mt5/reports/BARS_STATE.json", text)
    assert rows, text
    for r in rows:
        assert _ID not in str(r["key"]) and _ID2 not in str(r["key"])
        assert "0x" not in str(r["key"]).lower()


def test_the_finding_names_the_key_it_sat_under() -> None:
    [row] = _value_rows("x.json", json.dumps({"a": 1, "symbol_id": "000" + _ID}))
    assert row["key"] == f"{lf.VALUE_FINDING} under symbol_id"


def test_an_account_shaped_key_is_withheld_never_printed() -> None:
    # the login AS a key, and a value under a key that carries it
    for doc in ({"000" + _ID: {"x": 1}}, {"ref_000" + _ID: "000" + _ID}):
        rows = _value_rows("x.json", json.dumps(doc))
        assert rows and all(str(r["key"]).endswith("<key withheld>") for r in rows), doc
        assert all(_ID not in str(r["key"]) for r in rows)


def test_jsonl_reports_the_line_of_the_row() -> None:
    text = "\n".join(json.dumps(r) for r in (
        {"t": 1}, {"t": 2, "acct_ref": "000" + _ID}, {"t": 3}, {"x": _HEX}))
    rows = _value_rows("desks/mt5/data/rows.jsonl", text + "\n")
    assert sorted(int(str(r["line"])) for r in rows) == [2, 4]


def test_csv_and_tsv_cells_are_values_under_their_column() -> None:
    rows = _value_rows("x.csv", f"time,ref,profit\nt,000{_ID},1.0\n")
    assert [r["key"] for r in rows] == [f"{lf.VALUE_FINDING} under ref"]
    assert _value_rows("x.tsv", f"time\tmagic\nt\t{_HEX}\n")


@pytest.mark.parametrize("value", [
    "000" + _ID + "0",            # a different number
    hex(int(_ID) + 1),            # a different number in hex
    int(_ID) + 1,
    True, None, "", "2026-10-21", "n/a",
    chr(0x10A40) + chr(0x10A41),   # isdigit() but not decimal: never a crash, never a hit
])
def test_a_different_value_is_not_refused(value: object) -> None:
    assert _value_rows("x.json", json.dumps({"symbol_id": value})) == []


def test_no_declared_number_means_no_value_scan() -> None:
    assert _value_rows("x.json", json.dumps({"symbol_id": "000" + _ID}), frozenset()) == []


def test_unparseable_text_is_left_to_the_text_matcher_and_never_raises() -> None:
    assert _value_rows("x.json", '{"a": ' * 5000) == []
    assert _value_rows("x.json", "[" * 100000) == []
    # the text matcher still refuses the plain spelling in a broken file
    assert lf.findings("x.json", f'{{"a": {_ID}'.encode(), _IDS)


def test_the_value_is_read_through_the_same_decoding_as_the_text() -> None:
    # fullwidth digits and an invisible character inside the value
    v = chr(0xFF10) * 2 + _ID[:3] + chr(0x200B) + _ID[3:]
    assert _value_rows("x.json", json.dumps({"symbol_id": v}))

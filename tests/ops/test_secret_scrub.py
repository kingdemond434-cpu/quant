from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

import pytest

from libs.ops.secret_scrub import REDACTED, scrub

ROOT = Path(__file__).resolve().parents[2]
# Fake key, built so no tracked file carries the literal shape.
FAKE_KEY = "AI" + "za" + "Q" * 35


def test_scrub_reaches_nested_strings_and_keys() -> None:
    payload = {
        "items": [{"text": f"key={FAKE_KEY}&q=gold", "tags": (FAKE_KEY, "ok")}],
        FAKE_KEY: 3,
        "n": 7,
    }
    out = scrub(payload)
    assert FAKE_KEY not in json.dumps(out)
    assert out["items"][0]["text"] == f"key={REDACTED}&q=gold"
    assert out["items"][0]["tags"] == (REDACTED, "ok")
    assert out[REDACTED] == 3 and out["n"] == 7


def test_scrub_leaves_ordinary_text_alone() -> None:
    text = "AIzaShort and a sentence about gold carry"
    assert scrub(text) == text


def test_alpha_frontier_producer_never_writes_a_key(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_alpha_frontier as producer

    monkeypatch.setattr(producer, "OUT", tmp_path / "daily_alpha_frontier.json")
    monkeypatch.setattr(producer, "build", lambda: {
        "practitioner_frontier": {"new_mechanisms": [f"see {FAKE_KEY}"]},
        "high_priority_residuals": [],
    })
    # The summary print may want fields the stub lacks; the write comes first.
    with contextlib.suppress(KeyError, TypeError):
        producer.main()
    assert FAKE_KEY not in (tmp_path / "daily_alpha_frontier.json").read_text("utf-8")


# ---- M1 hardening (audit of #246): every key is built at runtime, never a literal ----------

import base64  # noqa: E402
import dataclasses  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
from collections import namedtuple  # noqa: E402
from urllib.parse import quote  # noqa: E402

from libs.ops import secret_scrub as ss  # noqa: E402

ALNUM = "Ab3dE5gH7jK9mN1pQ2rS4tU6vW8xY0zC"
GOOGLE = "AI" + "za" + (ALNUM * 2)[:35]
OPENROUTER_UPPER = "s" + "k-or-v1-" + ("0123456789ABCDEF" * 3)[:44]
OPENAI = "s" + "k-proj-" + ALNUM[:26]
ANTHROPIC = "s" + "k-ant-api03-" + ALNUM[:30]
AWS = "AK" + "IA" + "IOSF0DNN7EXAMP1E"
SLACK = "xo" + "xb-" + "1234567890-" + ALNUM[:20]
GITHUB = "gh" + "p_" + (ALNUM * 2)[:36]
ALL_KEYS = {"google": GOOGLE, "openrouter_upper": OPENROUTER_UPPER, "openai": OPENAI,
            "anthropic": ANTHROPIC, "aws": AWS, "slack": SLACK, "github": GITHUB}


def _decodings(text: str) -> list[str]:
    """Every view of `text` a reader could recover a key from."""
    from urllib.parse import unquote
    views = [text, re.sub(r"[\s​-‍﻿]", "", text), unquote(text),
             re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)]
    for run in re.findall(r"[A-Za-z0-9+/_-]{20,}={0,2}", text):
        for alt in (None, b"-_"):
            with contextlib.suppress(ValueError):  # not base64 at all
                views.append(base64.b64decode(run + "=" * (-len(run) % 4), altchars=alt)
                             .decode("utf-8", "ignore"))
    return views


def _clean(out: object, key: str) -> None:
    text = out if isinstance(out, str) else repr(out)
    for view in _decodings(text):
        assert key not in view, "the key, or a decoding of it, survived the scrub"


@pytest.mark.parametrize("name", sorted(ALL_KEYS))
def test_every_vendor_shape_is_redacted(name: str) -> None:
    key = ALL_KEYS[name]
    out = ss.scrub_text(f"config: {key} ; next")
    assert ss.REDACTED in out and out.endswith("; next")
    _clean(out, key)


def test_upper_case_openrouter_key_is_redacted() -> None:
    assert ss.scrub_text(OPENROUTER_UPPER) == ss.REDACTED


@pytest.mark.parametrize("prose", [
    "the risk-adjusted-return-over-the-full-sample was negative",
    "2026-08-13-moat-tape-decontamination-and-repair-window",
    "task-based-approach-to-trading-the-london-open-session",
    "use sk-learn-compatible-estimators for the classifier",
    "a b c d e f g h i j k l m n o p q r s t u v w x y z 0 1 2 3",
])
def test_anchored_patterns_leave_prose_alone(prose: str) -> None:
    assert ss.scrub_text(prose) == prose


@pytest.mark.parametrize("sep", [" ", "\n", "\t", "​", "‌", "‍", "﻿"])
def test_a_key_split_by_whitespace_or_zero_width_is_redacted(sep: str) -> None:
    split = sep.join([GOOGLE[:10], GOOGLE[10:22], GOOGLE[22:]])
    out = ss.scrub_text(f"leaked: {split} end")
    assert out.startswith("leaked: ") and out.endswith(" end")
    _clean(out, GOOGLE)


def test_a_percent_encoded_key_is_redacted() -> None:
    enc = "".join(f"%{ord(c):02X}" for c in OPENAI)
    out = ss.scrub_text(f"https://x.test/q?token={enc}&page=2")
    assert "page=2" in out
    _clean(out, OPENAI)
    out2 = ss.scrub_text("key=" + quote(GOOGLE[:4]) + "%2D" * 0 + quote(GOOGLE[4:], safe=""))
    _clean(out2, GOOGLE)


@pytest.mark.parametrize("fmt", ["\\u{:04x}", "\\x{:02x}"])
def test_a_backslash_escaped_key_is_redacted(fmt: str) -> None:
    enc = "".join(fmt.format(ord(c)) for c in GOOGLE)
    out = ss.scrub_text(f'"text": "{enc}"')
    assert ss.REDACTED in out
    _clean(out, GOOGLE)


def test_a_partially_escaped_key_is_redacted() -> None:
    enc = GOOGLE[:5] + "".join(f"\\u{ord(c):04x}" for c in GOOGLE[5:9]) + GOOGLE[9:]
    _clean(ss.scrub_text(enc), GOOGLE)


@pytest.mark.parametrize("urlsafe", [False, True])
def test_a_base64_encoded_key_is_redacted(urlsafe: bool) -> None:
    raw = f"Authorization: {ANTHROPIC}".encode()
    enc = (base64.urlsafe_b64encode(raw) if urlsafe else base64.b64encode(raw)).decode()
    assert len(enc) >= 40
    out = ss.scrub_text(f"blob {enc} tail")
    assert out == f"blob {ss.REDACTED} tail"
    _clean(out, ANTHROPIC)


def test_ordinary_long_base64_and_hashes_survive() -> None:
    text = "sha " + "0123456789abcdef" * 4 + " img " + base64.b64encode(b"x" * 60).decode()
    assert ss.scrub_text(text) == text


def test_bytes_and_bytearray_are_scrubbed_and_keep_their_type() -> None:
    raw = f"k={GOOGLE}\xff".encode("utf-8", "surrogateescape") + b"\xfe tail"
    for value in (raw, bytearray(raw)):
        out = ss.scrub(value)
        assert type(out) is type(value)
        assert GOOGLE.encode() not in out and out.endswith(b"\xfe tail")


def test_sets_and_frozensets_are_scrubbed() -> None:
    assert ss.scrub({GOOGLE, "ok"}) == {ss.REDACTED, "ok"}
    out = ss.scrub(frozenset({AWS}))
    assert isinstance(out, frozenset) and out == frozenset({ss.REDACTED})


@dataclasses.dataclass(frozen=True)
class _Row:
    text: str
    tags: tuple[str, ...]
    n: int = 0


@dataclasses.dataclass
class _Outer:
    row: _Row
    note: str = ""
    cached: str = dataclasses.field(default="", init=False)


def test_dataclass_instances_are_scrubbed_as_copies() -> None:
    row = _Row(text=f"see {SLACK}", tags=(GITHUB, "x"), n=3)
    out = ss.scrub(_Outer(row=row, note=OPENAI))
    assert isinstance(out, _Outer) and isinstance(out.row, _Row)
    assert out.row.n == 3 and out.row.tags == (ss.REDACTED, "x")
    _clean(repr(out), SLACK)
    _clean(repr(out), OPENAI)
    assert row.text == f"see {SLACK}", "the input is never mutated"


def test_namedtuples_keep_their_type() -> None:
    Pair = namedtuple("Pair", "a b")
    out = ss.scrub(Pair(GOOGLE, 1))
    assert isinstance(out, Pair) and out == Pair(ss.REDACTED, 1)


class _OddError(Exception):
    def __init__(self, url: str, code: int) -> None:
        super().__init__(url, code)
        self.url = url


def test_exceptions_have_their_args_and_str_scrubbed() -> None:
    err = ss.scrub(ValueError(f"GET https://api.test/v1?key={GOOGLE} failed", 7))
    assert isinstance(err, ValueError) and err.args[1] == 7
    _clean(str(err), GOOGLE)
    odd = ss.scrub(_OddError(f"https://x.test/?key={GOOGLE}", 403))
    _clean(str(odd), GOOGLE)


def test_exception_that_cannot_be_rebuilt_falls_back_to_scrubbed_text() -> None:
    class _Stubborn(Exception):
        def __init__(self) -> None:
            super().__init__(f"token {AWS}")
    out = ss.scrub(_Stubborn())
    assert isinstance(out, str)
    _clean(out, AWS)


def test_scrubbing_helpers_write_no_key(tmp_path: Path) -> None:
    doc = {"rows": [{"text": f"x {GOOGLE}"}], "raw": base64.b64encode(
        f"k {OPENAI}".encode()).decode()}
    ss.write_json(tmp_path / "a.json", doc)
    ss.write_text(tmp_path / "b.txt", f"y {SLACK}")
    ss.append_jsonl(tmp_path / "c.jsonl", [{"t": AWS}, {"t": "ok"}])
    for name, key in (("a.json", GOOGLE), ("a.json", OPENAI), ("b.txt", SLACK),
                      ("c.jsonl", AWS)):
        _clean((tmp_path / name).read_text("utf-8"), key)
    assert json.loads((tmp_path / "a.json").read_text("utf-8"))["rows"][0]["text"].startswith("x ")
    assert len((tmp_path / "c.jsonl").read_text("utf-8").splitlines()) == 2


def test_scrub_tree_rewrites_only_files_that_carry_a_key(tmp_path: Path) -> None:
    dirty = tmp_path / "seat" / "discoveries_1.json"
    dirty.parent.mkdir()
    dirty.write_text(json.dumps({"t": f"see {GOOGLE}"}), "utf-8")
    clean = tmp_path / "seat" / "discoveries_2.json"
    clean.write_text('{"t": "gold carry"}', "utf-8")
    before = clean.stat().st_mtime_ns
    assert ss.scrub_tree(tmp_path) == [dirty]
    _clean(dirty.read_text("utf-8"), GOOGLE)
    assert json.loads(dirty.read_text("utf-8"))["t"].startswith("see ")
    assert clean.stat().st_mtime_ns == before


def test_scrub_staged_rewrites_the_index_blob(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    def git(*a: str) -> str:
        return subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True,
                              text=True).stdout
    git("init", "-q")
    p = tmp_path / "data" / "intelligence" / "kimi" / "d.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"t": f"key={GOOGLE}"}), "utf-8")
    other = tmp_path / "notes.txt"
    other.write_text("not an intelligence path", "utf-8")
    git("add", "--", "data", "notes.txt")
    monkeypatch.chdir(tmp_path)
    assert ss.scrub_staged() == ["data/intelligence/kimi/d.json"]
    _clean(git("show", ":data/intelligence/kimi/d.json"), GOOGLE)
    _clean(p.read_text("utf-8"), GOOGLE)
    assert ss.main(["--staged"]) == 0


def test_no_pattern_literal_in_the_module_source() -> None:
    src = (ROOT / "libs" / "ops" / "secret_scrub.py").read_text("utf-8")
    assert not ss.KEY_RE.search(src)
    for prefix in ("AI" + "za[", "s" + "k-ant-(", "s" + "k-(", "AK" + "IA[", "xo" + "x[",
                   "gh" + "[pousr]", "s" + "k-or-v1-)"):
        assert prefix not in src, prefix

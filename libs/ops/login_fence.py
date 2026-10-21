"""A BROKERAGE LOGIN DOES NOT CROSS THE BOX'S STATE WIRE. Never places an order.

`desks/mt5/scripts/sync_shadow_to_git.ps1` publishes the box's state blobs onto origin. The
live-identifier fence (tests/ops/test_live_infrastructure_is_not_published.py) is a pytest: it can
only notice a login AFTER origin holds it. This is the publish-time half. The publisher hashes the
allowlisted files, hands this module the BLOB ids it is about to commit, and drops whatever this
refuses -- so the bytes judged here are exactly the bytes published (audit v3: the first fence read
the file, then let `hash-object` read the disk again, and a write between the two went unchecked).

WHAT IT REFUSES (audit v3, measured false negatives and positives, 2026-10-14):
  * a login-shaped KEY -- `login`, `login_id`, `"Login ID"`, `account`, `account_number`,
    `accountLogin`, `account-login`, `mt5_login`, `fusion_live_login`, any case -- whose VALUE is
    account-shaped (4 to 12 digits, bare, quoted or first in a list);
  * the same inside escaped JSON (`{\\"login\\": ...}` in a string) and `\\u`-encoded keys;
  * a CSV/TSV header naming such a column, when any row of that column is account-shaped.
WHAT IT PASSES: `login_withheld` (the bool research/cost_truth.py writes), `account_key` (the
hash), null/true/false, `requires_login: 0`, `last_login: "<ts>"`, `login: "ok"`, `login: ""`,
and `account: {...}` / `account: "Fusion Zero"`. Python's `re.IGNORECASE` and `str.lower()` are
locale-independent, so a tr-TR box reads `LOGIN` the same as an en-US one (the .NET
culture-sensitive IgnoreCase of the first fence did not).

LEGACY PREFIXES ARE PINNED, NOT MARKED (audit v5). `live_ledger.jsonl` and `order_intents.jsonl`
carried the raw login in `account` on every row until their writers moved to the keyed
`account_key`. Those rows cannot be rewritten (the ledger's prefix is sealed in
IMMUTABLE_MANIFEST.json and libs/ops/live_ledger_view.py raises on a changed prefix). v4 exempted
"every row before the first `account_key` row", which a regressed writer -- or anyone -- could
extend forever by simply never writing the marker. Now each path's exempt prefix is PINNED as
{records, sha256} measured on LIVE: the first `records` lines, each LF-terminated, must hash to
`sha256`, and every line after them is judged in full. A prefix that changed or got shorter is
refused as `<legacy prefix changed>` -- order_intents.jsonl is NOT append-only (its reconcile
rewrites rows), so that case is real and fails closed. Bumping a pin is a code change measured
with `--measure-prefix` (prints counts and a hash, never content). The pins go when the
principal scrubs history (`git filter-repo` is theirs alone).

ENCODINGS AND FORMS (audit v5): UTF-16LE/BE, every invisible character dropped (Cf and
Default_Ignorable, v5c/v5d), fullwidth digits (NFKC), Arabic-Indic and Extended
Arabic-Indic digits (folded to ASCII, v5b), a declared number split by separators between its
digits (`555-1234`, `5,551,234`, `555 1234`, `555.1234`; v5b), up to four levels of
backslash-escaped JSON (surrogate pairs joined; v5d), `\\u` escapes, hex and base64 runs
that decode to text, float and
exponent values (`5551234.0`, `5.551234e6`), the keys `mt5_account`, `live_account`, `acct`,
`login2` and their kin, the prose `account N` / `account #N`, `N@server`, the MT5 journal's
`'N': authorized`, XML elements and attributes, a CSV whose header sits under a preamble, and a
JSON object inside a CSV cell.

NO DECLARED NUMBER IS UNMEASURED, NOT CLEAN (audit v5). With zero declared account numbers the
digit-bounded match above covers nothing, so the pass reads `UNMEASURED` and the alert stays
open (it pages) -- publication proceeds on the key rules alone. A declaration source that
exists and yields an unreadable token is a config error: exit 2, nothing published.

A refusal (or UNMEASURED) is written to desks/mt5/reports/LOGIN_FENCE.json (published on the
next pass), opens `state_login_fence_refusal` in data/alert_ledger.json, and PAGES through
`alert_channels.send_all` -- deduplicated by desks/mt5/logs/login_fence_alert.json, repaged every
6h while it stands, one page on recovery. A clean pass closes the alert. If the alert ledger or
the pager raises, the CLI exits 3 (the publisher then publishes nothing) instead of swallowing
it. Nothing written or printed here ever carries a value: only paths, key names, line numbers.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import contextlib
import csv
import functools
import hashlib
import io
import json
import re
import subprocess
import sys
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "desks" / "mt5" / "reports" / "LOGIN_FENCE.json"
ALERTS = ROOT / "data" / "alert_ledger.json"
ALERT_ID = "state_login_fence_refusal"
PAGE_STATE_REL = "desks/mt5/logs/login_fence_alert.json"   # gitignored with desks/mt5/logs/
REPAGE_H = 6.0
Sender = Callable[[str, str], dict[str, Any]]

#: Binary state the fence does not read as text (market frames; a regex over pickled bytes only
#: ever false-alarms). Every OTHER extension is judged, known or not -- an unknown one is read as
#: text rather than waved through (audit v3: `.yaml`, `.log`, `.xml` used to bypass the fence).
BINARY_EXEMPT = frozenset({".pkl", ".pickle", ".parquet", ".feather", ".npz", ".npy"})

#: The sealed legacy prefixes, PINNED (see above). Measured 2026-10-20 on LIVE
#: (origin/claude/llm-auto-upgrade-verify-gcjac3 at 59451424, identical to this base) over the
#: committed blob, BOM stripped, each line LF-terminated.
LEGACY_PIN: dict[str, dict[str, Any]] = {
    "desks/mt5/data/live_ledger.jsonl": {
        "records": 257,
        "sha256": "3434b6fd8e853786c599616df339cb537db9e103b834a8bd423e327101d28301",
        "why": "rows carry the raw login; the prefix is sealed (IMMUTABLE_MANIFEST.json)"},
    "desks/mt5/data/order_intents.jsonl": {
        "records": 296,
        "sha256": "18f1e28960b0e9c0c47df740aa2f1420d5c4bf9f11687dbcca2da3ce81e32f5e",
        "why": "rows carry the raw login; the gateway appends live and its reconcile reads it"},
}
PREFIX_FINDING = "<legacy prefix changed>"


def _lines(data: bytes) -> list[bytes]:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.splitlines(keepends=True)


def prefix_digest(lines: list[bytes]) -> str:
    """sha256 of `lines`, each LF-terminated (so a CRLF checkout pins the same bytes)."""
    h = hashlib.sha256()
    for ln in lines:
        h.update(ln.rstrip(b"\r\n") + b"\n")
    return h.hexdigest()


def measure_prefix(data: bytes) -> dict[str, Any]:
    """{records, sha256} of a whole file, for bumping a pin. Never the content."""
    lines = _lines(data)
    return {"records": len(lines), "sha256": prefix_digest(lines)}


#: A normalised (lower-case, alphanumerics only) key names an account when it is one of these
#: stems, optionally prefixed (`mt5_`, `live_`, `fusion_live_`), optionally suffixed `id` /
#: `no` / `num` / `number` and a digit or two (`login2`) -- audit v5 widened this from a list.
_KEY_FORM = re.compile(r"[a-z0-9]*?(?:login|account|acct)(?:id|no|num|number)?\d{0,2}")
#: Normalised prefixes that make such a key something other than the account's identity.
NOT_IDENTITY = ("requires", "require", "needs", "last", "failed", "allow", "auto", "sso",
                "first", "prev", "next", "count", "max", "min", "per")
_ACCOUNT_SHAPED = re.compile(r"\d{4,12}")
_NUM = r"-?\d[\d.]*(?:[eE][+-]?\d+)?"
#: key, then `:` or `=`, then a bare / quoted / first-in-list value. The key may be quoted with
#: " or ' (Python repr) or bare; the value capture is only ever compared, never stored.
_PAIR = re.compile(
    r"""["']?(?P<key>[A-Za-z][A-Za-z0-9 _\-]{0,40}?)["']?\s*[:=]\s*\[?\s*"""
    r"""(?P<val>"[^"\n]{0,40}"|'[^'\n]{0,40}'|""" + _NUM + ")")
#: Key-less forms that still name an account: prose `account 5551234` / `account #5551234` /
#: `acct no. 5551234`, `5551234@Server`, and the MT5 journal's `'5551234': authorized`.
_PROSE = re.compile(r"(?i)(?<![a-z0-9_])(?:account|acct)\s*(?:#|no\.?|number|id)?\s*"
                    r"(\d{4,12})(?![\d\-:/]|\.\d)")
_AT_SERVER = re.compile(r"(?<![\w.])(\d{4,12})@[A-Za-z]")   # not `_2023@DF_...`
_JOURNAL = re.compile(r"(?i)(?<!\d)(\d{4,12})['\"]?\s*:\s*authori[sz]ed")
_XML_ELEM = re.compile(r"<\s*(?P<key>[A-Za-z][\w\-.:]{0,40})(?:\s[^<>]*)?>\s*"
                       r"(?P<val>" + _NUM + r")\s*</\s*(?P=key)\s*>")
_HEX_RUN = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}){8,}(?![0-9A-Fa-f])")
_B64_RUN = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/_-]{16,}={0,2}(?![A-Za-z0-9+/=_-])")
#: ONE LEVEL of backslash-unescaping, tokenised left to right (v5d): an escaped backslash `\\`
#: is consumed as one token BEFORE a `\uXXXX` can be read, so `\\u200b` (double-escaped) becomes
#: `\u200b` on this pass and the character on the next -- never a stray `\` beside a decoded one.
#: Only `\\`, `\"`, `\'`, `\/` and `\uXXXX` are undone; `\n` and the rest stay two characters
#: so line numbers never move.
_ESC = re.compile(r"""\\(?:(\\)|(["'/])|u([0-9a-fA-F]{4}))""")
_SURROGATE_PAIR = re.compile("[\ud800-\udbff][\udc00-\udfff]")
#: Escape levels undone (v5d): single, double and triple escaping all decode, with one to spare.
_UNESCAPE_PASSES = 4

#: THE DECLARED ACCOUNT NUMBERS, matched ANYWHERE (audit addendum to v4, 2026-10-20). The key/value
#: rules above only see a login sitting under a login-shaped key; "refused for <ID>.", "acc_<ID>"
#: and "x<ID>" name the account with no key at all. So each number the box declares is also
#: matched on its own, with DIGIT boundaries `(?<!\d)ID(?!\d)` -- never `\b`, which treats `_` and
#: letters as word characters and so misses `acc_<ID>` and `x<ID>`. A longer number that merely
#: contains the ID (`1<ID>2`) is a different number and does not match.
#: Sources, all box-local and never committed: the env var below (comma/space separated) and the
#: login half of every "<login>@<server>" key in desks/mt5/data/ACCOUNT_PROFILES.json (the
#: declarations account_profile.py reads). No declared number is not an error; a declarations
#: file that exists and cannot be read IS one, and the CLI then exits 2 so the publisher
#: publishes nothing (it fails closed).
ID_ENV = "QUANT_FENCE_ACCOUNT_IDS"
DECLARATIONS_REL = "desks/mt5/data/ACCOUNT_PROFILES.json"
ID_FINDING = "<declared account number>"


class FenceConfigError(RuntimeError):
    """The box declares account numbers the fence could not read: refuse, never guess."""


def declared_ids(root: Path, env: dict[str, str] | None = None) -> frozenset[str]:
    """Every account number the box declares, as digit strings (4-12 digits).

    STRICT (audit v5): a token in the env var that is not account-shaped, or a declarations key
    whose login half is not, is a FenceConfigError -- a typo must not silently declare nothing.
    The declarations file is account_profile.py's: {"accounts": {"<login>@<server>": profile}}
    (a bare top-level mapping of such keys is read too)."""
    import os
    env = dict(os.environ) if env is None else env
    raw = [_ascii_digits(t) for t in re.split(r"[,\s]+", env.get(ID_ENV, "").strip()) if t]
    bad = [t for t in raw if not _ACCOUNT_SHAPED.fullmatch(t)]
    if bad:
        raise FenceConfigError(f"{ID_ENV} carries {len(bad)} token(s) that are not 4-12 digits")
    path = Path(root) / DECLARATIONS_REL
    if path.exists():
        try:
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(doc, dict):
                raise ValueError("not an object")
            accounts = doc.get("accounts", doc)
            if not isinstance(accounts, dict):
                raise ValueError("'accounts' is not an object")
            logins = [_ascii_digits(str(k).split("@", 1)[0].strip()) for k in accounts]
            if any(not _ACCOUNT_SHAPED.fullmatch(x) for x in logins):
                raise ValueError("a key's login half is not 4-12 digits")
            raw += logins
        except (OSError, ValueError) as exc:
            raise FenceConfigError(f"{DECLARATIONS_REL} unreadable ({type(exc).__name__})") from exc
    return frozenset(raw)


#: Characters a writer puts between the digits of one number (v5b): `555-1234`, `5,551,234`,
#: `555 1234`, `555.1234`, `555'1234`, `555_1234`, the Unicode dashes and spaces NFKC keeps, and
#: (v5c) `/`, `:`, `(` and `)` -- `(555) 1234`, `555/1234`, `555:1234`.
_DIGIT_SEP = (" \t-,.'_/:()"
              "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u2019\u00a0\u2009\u202f")
#: Up to this many separator characters between two digits (v5c: was 3, so `555 -  1234` with
#: four slipped through). Bounded so the split pattern stays linear; the boundary check walks the
#: same distance, so a digit beyond a run of separators still makes it a different number.
_SEP_MAX = 16
_SEP_CLASS = "[" + re.escape(_DIGIT_SEP) + "]{0," + str(_SEP_MAX) + "}"


#: Default_Ignorable_Code_Point, DECLARED (v5d), from the Unicode Character Database's
#: DerivedCoreProperties.txt (https://www.unicode.org/Public/UCD/latest/ucd/DerivedCoreProperties.txt,
#: property `Default_Ignorable_Code_Point`, Unicode 15.1). The stdlib's unicodedata exposes no
#: such property, so the ranges are written here; every Cf character is added from unicodedata at
#: run time (`_ignorable_table`), so a Cf the table misses is still dropped.
DEFAULT_IGNORABLE: tuple[tuple[int, int], ...] = (
    (0x00AD, 0x00AD),    # SOFT HYPHEN
    (0x034F, 0x034F),    # COMBINING GRAPHEME JOINER
    (0x061C, 0x061C),    # ARABIC LETTER MARK
    (0x115F, 0x1160),    # HANGUL CHOSEONG / JUNGSEONG FILLER
    (0x17B4, 0x17B5),    # KHMER VOWEL INHERENT AQ / AA
    (0x180B, 0x180F),    # MONGOLIAN FREE VARIATION SELECTORS, VOWEL SEPARATOR
    (0x200B, 0x200F),    # ZWSP, ZWNJ, ZWJ, LRM, RLM
    (0x202A, 0x202E),    # bidi embeddings and overrides
    (0x2060, 0x206F),    # WJ, invisible operators, bidi isolates, deprecated format chars
    (0x3164, 0x3164),    # HANGUL FILLER
    (0xFE00, 0xFE0F),    # VARIATION SELECTORS 1-16
    (0xFEFF, 0xFEFF),    # ZWNBSP / BOM
    (0xFFA0, 0xFFA0),    # HALFWIDTH HANGUL FILLER
    (0xFFF0, 0xFFF8),    # unassigned, reserved ignorable
    (0x1BCA0, 0x1BCA3),  # SHORTHAND FORMAT CONTROLS
    (0x1D173, 0x1D17A),  # MUSICAL SYMBOL BEGIN/END BEAM ...
    (0xE0000, 0xE0FFF),  # TAGS, VARIATION SELECTORS SUPPLEMENT, reserved
)


@functools.lru_cache(maxsize=1)
def _ignorable_table() -> dict[int, None]:
    """Every Default_Ignorable code point and every Cf character -> deleted, for str.translate.
    Built once, lazily."""
    table: dict[int, None] = {cp: None for lo, hi in DEFAULT_IGNORABLE
                              for cp in range(lo, hi + 1)}
    table.update({cp: None for cp in range(sys.maxunicode + 1)
                  if unicodedata.category(chr(cp)) == "Cf"})
    return table


def _drop_format(text: str) -> str:
    """Remove every invisible character -- each Unicode Cf (format) character (ZWSP, ZWNJ, ZWJ,
    LRM, RLM, WJ, BOM, soft hyphen, ...; v5c) and each Default_Ignorable code point (CGJ, the
    variation selectors, the Hangul fillers, the tag range; v5d). Invisible, so `555<ZWSP>1234`
    reads as the number to a human and must to the fence too. None is a line break."""
    return text if text.isascii() else text.translate(_ignorable_table())


def _ascii_digits(text: str) -> str:
    """Every Unicode decimal digit (Arabic-Indic U+0660-0669, Extended Arabic-Indic
    U+06F0-06F9, Devanagari, ...) as its ASCII digit. One character for one, so line numbers and
    offsets are unchanged. NFKC folds fullwidth digits but NOT these, which are not compatibility
    forms (v5b)."""
    if text.isascii():
        return text
    return re.sub(r"(?![0-9])\d", lambda m: str(unicodedata.decimal(m.group(0))), text)


#: Separators that END a number rather than join its groups (v5d): whitespace and `/ : ( )`.
_TIGHT = frozenset("/:()")


def _side_clear(run: str, beyond: str, internal: str | None) -> bool:
    """Is the number bounded on this side? `run` is the separator run between the match and
    `beyond` (the next non-separator character, "" at the edge of the text)."""
    if not beyond.isdigit():
        return True
    if not run:
        return False                       # a digit touches the match: a longer number
    # A run holding whitespace or / : ( ) is a TIGHT boundary (v5d, audit hold on v5c): `acct
    # 555-1234 (2 trades)`, `555 1234 / 2`, `ref 555-1234: 3 fills` name the account and then
    # something else. Unless the run is exactly the separator the number's own groups use --
    # `1/555/1234`, `12:555:1234`, `555    1234    5` continue one longer number.
    tight = any(c.isspace() or c in _TIGHT for c in run)
    return tight and run != internal


def _bounded(body: str, start: int, end: int, internal: str | None = None) -> bool:
    """No digit continues [start, end) across up to `_SEP_MAX` separator characters -- so the
    split form of an ID inside a longer separated number (`1,555,1234`) is that other number --
    with the TIGHT boundary above. `internal` is the separator run the match itself uses between
    its digit groups when that is one uniform run, else None."""
    i = start
    while i > 0 and start - i < _SEP_MAX and body[i - 1] in _DIGIT_SEP:
        i -= 1
    j = end
    while j < len(body) and j - end < _SEP_MAX and body[j] in _DIGIT_SEP:
        j += 1
    before = body[i - 1] if i > 0 else ""
    after = body[j] if j < len(body) else ""
    return (_side_clear(body[i:start], before, internal)
            and _side_clear(body[end:j], after, internal))


_SEP_RUN = re.compile("[" + re.escape(_DIGIT_SEP) + "]+")


def _internal_run(match: str) -> str | None:
    """The one separator run a split match uses between its groups, or None if none or mixed."""
    runs = set(_SEP_RUN.findall(match))
    return runs.pop() if len(runs) == 1 else None


def _id_hits(views: list[tuple[str, int | None]], ids: frozenset[str]) -> list[int]:
    r"""Line numbers where a declared number stands alone between non-digits, in any view --
    contiguous (`(?<!\d)ID(?!\d)`, as before, so `ID.0` still hits) or SPLIT by separators
    between its digits (`555-1234`, `5,551,234`; v5b), the split form digit-bounded across
    separators too."""
    lines: set[int] = set()
    for body, at in views:
        for n in ids:
            plain = r"(?<!\d)" + re.escape(n) + r"(?!\d)"
            split = _SEP_CLASS.join(re.escape(d) for d in n)
            for m in re.finditer(plain, body):
                lines.add(at if at is not None else body.count("\n", 0, m.start()) + 1)
            for m in re.finditer(split, body):
                if _bounded(body, m.start(), m.end(), _internal_run(m.group(0))):
                    lines.add(at if at is not None else body.count("\n", 0, m.start()) + 1)
    return sorted(lines)


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def is_login_key(key: str) -> bool:
    n = _norm(key)
    if not n or n.startswith(NOT_IDENTITY):
        return False
    return _KEY_FORM.fullmatch(n) is not None


def _account_shaped(val: str) -> bool:
    """4-12 digits -- bare, or as an integral float / exponent (`5551234.0`, `5.551234e6`)."""
    v = val.strip().strip("\"'").strip()
    if _ACCOUNT_SHAPED.fullmatch(v):
        return True
    if not re.fullmatch(_NUM, v) or v.startswith("-"):
        return False
    try:
        f = float(v)
    except (ValueError, OverflowError):
        return False
    return f.is_integer() and 1000 <= f < 1e12


def _unescape_once(text: str) -> str:
    """One level of backslash-escaping undone (see `_ESC`), surrogate pairs joined into the one
    astral code point they encode (`json.dumps` writes U+E0001 as `\\udb40\\udc01`; v5d)."""
    def one(m: re.Match[str]) -> str:
        if m.group(1) is not None:
            return "\\"
        if m.group(2) is not None:
            return m.group(2)
        return chr(int(m.group(3), 16))
    out = _ESC.sub(one, text)
    return _SURROGATE_PAIR.sub(
        lambda m: chr(0x10000 + ((ord(m.group(0)[0]) - 0xD800) << 10)
                      + (ord(m.group(0)[1]) - 0xDC00)), out)


def _decoded(text: str) -> str:
    """Backslash escaping undone to a fixpoint, at most `_UNESCAPE_PASSES` levels (v5d: an escaped
    backslash is consumed before a `\\uXXXX` is read, and surrogate pairs are joined), every
    invisible character dropped (Cf, v5c; Default_Ignorable, v5d), compatibility forms folded
    (NFKC: fullwidth digits) and every Unicode decimal digit folded to ASCII (v5b)."""
    out = text
    for _ in range(_UNESCAPE_PASSES):
        nxt = _unescape_once(out)
        if nxt == out:
            break
        out = nxt
    out = unicodedata.normalize("NFKC", _drop_format(out))
    return _ascii_digits(_drop_format(out))   # NFKC can map onto an ignorable (U+3164 -> U+1160)


def _as_text(data: bytes) -> str:
    """UTF-16 (by BOM, or by NUL density) or UTF-8, BOM stripped. Never fails."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace").lstrip("\ufeff")
    if len(data) >= 8 and data.count(0) * 4 >= len(data):
        odd = data[1::2].count(0)
        enc = "utf-16-le" if odd >= data[0::2].count(0) else "utf-16-be"
        return data.decode(enc, errors="replace").lstrip("\ufeff")
    return data.decode("utf-8", errors="replace").lstrip("\ufeff")


def _printable(raw: bytes) -> str | None:
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            txt = raw.decode("utf-16-le")
        except UnicodeDecodeError:
            return None
    ok = sum(1 for c in txt if c.isprintable() or c in "\r\n\t")
    return txt if txt and ok >= 0.9 * len(txt) else None


def _views(text: str) -> list[tuple[str, int | None]]:
    """(text, fixed line) views to scan: the decoded whole (its own line numbers) and every hex
    or base64 run that decodes to text (reported at the run's line in the decoded whole)."""
    flat = _decoded(text)
    out: list[tuple[str, int | None]] = [(flat, None)]
    if flat != text:
        out.append((text, None))
    for m in _HEX_RUN.finditer(flat):
        got = _printable(bytes.fromhex(m.group(0)))
        if got:
            out.append((_decoded(got), flat.count("\n", 0, m.start()) + 1))
    for m in _B64_RUN.finditer(flat):
        run = m.group(0)
        with contextlib.suppress(binascii.Error, ValueError):
            alt = "-_" if ("-" in run or "_" in run) else None
            raw = base64.b64decode(run + "=" * (-len(run) % 4),
                                   altchars=alt.encode() if alt else None, validate=True)
            got = _printable(raw)
            if got:
                out.append((_decoded(got), flat.count("\n", 0, m.start()) + 1))
    return out


def _line(body: str, at: int | None, pos: int) -> int:
    return at if at is not None else body.count("\n", 0, pos) + 1


def _pairs(views: list[tuple[str, int | None]]) -> list[tuple[str, int]]:
    """(key name, line) for each account-naming hit -- names only, never the value."""
    hits: list[tuple[str, int]] = []
    for body, at in views:
        for m in _PAIR.finditer(body):
            if is_login_key(m.group("key")) and _account_shaped(m.group("val")):
                hits.append((m.group("key").strip(), _line(body, at, m.start())))
        for m in _XML_ELEM.finditer(body):
            if is_login_key(m.group("key")) and _account_shaped(m.group("val")):
                hits.append((m.group("key").strip(), _line(body, at, m.start())))
        for rx, name in ((_PROSE, "<prose account number>"), (_AT_SERVER, "<login@server>"),
                         (_JOURNAL, "<journal authorized>")):
            for m in rx.finditer(body):
                hits.append((name, _line(body, at, m.start())))
    return sorted(set(hits), key=lambda h: (h[1], h[0]))


def _csv_hits(text: str, sep: str) -> list[tuple[str, int]]:
    """Login-named columns with an account-shaped value under ANY header row (a preamble above
    the header does not hide it), and account hits inside any cell (a JSON object in a cell)."""
    rows = list(csv.reader(io.StringIO(_drop_format(text)), delimiter=sep))
    hits: set[tuple[str, int]] = set()
    cols: dict[int, str] = {}
    for n, row in enumerate(rows, start=1):
        named = {i: c.strip() for i, c in enumerate(row) if is_login_key(c)}
        for i, name in cols.items():
            if i < len(row) and _account_shaped(row[i]):
                hits.add((name, n))
        if named:
            cols = named
        for cell in row:
            if len(cell) > 6 and any(ch in cell for ch in ":=<@"):
                hits.update((k, n) for k, _ in _pairs(_views(cell)))
    return sorted(hits, key=lambda h: (h[1], h[0]))


def _judged(rel: str, data: bytes) -> tuple[bytes, int, list[dict[str, Any]]]:
    """(bytes to judge, line offset, prefix findings) for `rel`: a pinned path's prefix is cut
    off only when it still hashes to its pin; otherwise the whole file is judged AND refused."""
    pin = LEGACY_PIN.get(rel)
    if pin is None:
        return data, 0, []
    lines = _lines(data)
    n = int(pin["records"])
    if len(lines) < n or prefix_digest(lines[:n]) != pin["sha256"]:
        return data, 0, [{"key": PREFIX_FINDING, "line": 0}]
    return b"".join(lines[n:]), n, []


def findings(rel: str, data: bytes, ids: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """Why `rel` must not publish, as {key, line} rows -- never the value. [] = publishable.
    `ids` are the declared account numbers (see `declared_ids`), matched with digit boundaries."""
    suffix = Path(rel).suffix.lower()
    if suffix in BINARY_EXEMPT:
        return []
    body, offset, out = _judged(rel, data)
    text = _as_text(body)
    views = _views(text)
    hits = _pairs(views)
    if suffix in (".csv", ".tsv"):
        hits += _csv_hits(text, "\t" if suffix == ".tsv" else ",")
    out += [{"key": k, "line": line + offset} for k, line in sorted(set(hits))]
    return out + [{"key": ID_FINDING, "line": line + offset} for line in _id_hits(views, ids)]


def _blobs(repo: Path, ids: list[str]) -> list[bytes | None]:
    """The blobs' bytes, in one `git cat-file --batch` process; None for a missing object."""
    proc = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"],
                          input=("\n".join(ids) + "\n").encode(), capture_output=True,
                          timeout=120, check=True)
    buf, pos = proc.stdout, 0
    out: list[bytes | None] = []
    for _ in ids:
        eol = buf.index(b"\n", pos)
        head = buf[pos:eol].split()
        pos = eol + 1
        if len(head) < 3 or head[1] == b"missing":
            out.append(None)
            continue
        size = int(head[2])
        out.append(buf[pos:pos + size])
        pos += size + 1
    return out


def judge(repo: Path, entries: list[tuple[str, str]],
          ids: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Judge (blob, rel) pairs. An unreadable blob is refused: this fence fails closed.

    status: REFUSED (something refused), UNMEASURED (nothing refused, but no account number is
    declared, so the digit-bounded match covered nothing), or OK."""
    data = _blobs(repo, [b for b, _ in entries])
    refused: dict[str, list[dict[str, Any]]] = {}
    for (_blob, rel), raw in zip(entries, data, strict=True):
        if raw is None:
            refused[rel] = [{"key": "<blob unreadable>", "line": 0}]
            continue
        got = findings(rel, raw, ids)
        if got:
            refused[rel] = got[:20]
    status = "REFUSED" if refused else ("OK" if ids else "UNMEASURED")
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "status": status,
            "n_checked": len(entries), "n_refused": len(refused),
            "n_declared_ids": len(ids),
            "declared_ids": "MEASURED" if ids else "UNMEASURED",
            "refused": refused,
            "legacy_pins": {rel: {"records": p["records"], "sha256": p["sha256"]}
                            for rel, p in LEGACY_PIN.items()},
            "rule": "login-shaped key with an account-shaped value, key-less account forms, and "
                    "declared account numbers; values are never recorded"}


def _why(doc: dict[str, Any]) -> str:
    if doc.get("status") == "UNMEASURED":
        return ("no account number declared (QUANT_FENCE_ACCOUNT_IDS / ACCOUNT_PROFILES.json): "
                "the declared-number match covered nothing")
    return "; ".join(f"{rel}: {', '.join(sorted({h['key'] for h in hits}))}"
                     for rel, hits in sorted(doc.get("refused", {}).items()))


def record_alert(doc: dict[str, Any], root: Path | None = None) -> str | None:
    """Give a refusal a lifecycle in the desk's AlertLedger (scripts/check_placement_interlock.py
    idiom). RAISES on failure (audit v5): the caller decides, never a bare `except` here."""
    base = Path(root or ROOT)
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    from libs.ops.alert_ledger import AlertLedger
    ledger = AlertLedger(base / "data" / "alert_ledger.json")
    if doc.get("status") == "OK":
        alert = ledger.alerts.get(ALERT_ID)
        if alert is not None and alert.open:
            ledger.verify(ALERT_ID, still_firing=False)
            ledger.save()
            return "FIXED"
        return None
    ledger.observe(ALERT_ID, (f"state publish fence {doc.get('status')} (value withheld): "
                              + _why(doc))[:600], scope="RUNTIME")
    ledger.save()
    return "OPEN"


def _default_sender(root: Path) -> Sender:
    def send(title: str, body: str) -> dict[str, Any]:
        from libs.ops import alert_channels
        return alert_channels.send_all(
            title, body, config=root / "data/secrets/alert_channels.json",
            ledger=root / "data/alert_delivery.jsonl")
    return send


def page(doc: dict[str, Any], root: Path | None = None, *, sender: Sender | None = None,
         now: datetime | None = None, repage_h: float = REPAGE_H) -> dict[str, Any]:
    """Page a REFUSED or UNMEASURED pass off the box (state_publication.page_flow's idiom):
    on a change, again every `repage_h` hours while it stands, once on recovery to OK. A send
    whose `delivered` is 0 or falsy is NOT a page: nothing is recorded and the next pass
    re-sends. The page names paths and key names only. RAISES if the sender does: the CLI turns
    that into rc 3."""
    base = Path(root or ROOT)
    now = now or datetime.now(UTC)
    status = str(doc.get("status") or "UNMEASURED")
    sig = status + "|" + ",".join(sorted(doc.get("refused", {})))
    path = base / PAGE_STATE_REL
    try:
        prev = json.loads(path.read_text("utf-8"))
        prev = prev if isinstance(prev, dict) else {}
    except (OSError, ValueError):
        prev = {}
    last = None
    with contextlib.suppress(TypeError, ValueError):
        last = datetime.fromisoformat(str(prev.get("paged_at")))
    if status != "OK":
        if prev.get("sig") != sig:
            reason = "changed"
        elif last is None or (now - last).total_seconds() / 3600 >= repage_h:
            reason = f"still {status} after {repage_h:g}h"
        else:
            return {"sent": False, "reason": "deduplicated"}
        title = (f"STATE PUBLISH REFUSED: {doc.get('n_refused', 0)} path(s) held back"
                 if status == "REFUSED" else "LOGIN FENCE UNMEASURED: no declared account number")
    elif prev.get("status") not in (None, "OK"):
        reason, title = f"recovered from {prev.get('status')}", "LOGIN FENCE OK again"
    else:
        return {"sent": False, "reason": "OK: nothing to page"}
    body = f"{_why(doc) or status}\n(values withheld; see desks/mt5/reports/LOGIN_FENCE.json)"
    res = (sender or _default_sender(base))(title, body[:1500])
    res = res if isinstance(res, dict) else {}
    # A page that reached NOBODY was not a page (v5b): `delivered` 0, absent or falsy leaves the
    # dedup state untouched, so the next pass sends it again instead of deduplicating silence.
    if not res.get("delivered"):
        return {"sent": False, "reason": f"{reason}: undelivered, re-sent next pass",
                "armed": res.get("armed"), "delivered": res.get("delivered")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": status, "sig": sig,
                                "paged_at": now.isoformat(timespec="seconds")}), "utf-8")
    return {"sent": True, "reason": reason, "armed": res.get("armed"),
            "delivered": res.get("delivered")}


def _write(out: Path, doc: dict[str, Any]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    tmp.replace(out)


def main(argv: list[str] | None = None) -> int:
    """stdin: one `<blob>\\t<rel>` per line. stdout: one refused rel per line.
    rc 0 = judged; 2 = the declarations are unreadable; 3 = a non-OK pass could not be alerted
    or paged. The publisher publishes NOTHING on any non-zero rc."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=ROOT)
    ap.add_argument("--artifact", type=Path, default=None)
    ap.add_argument("--measure-prefix", metavar="REL", default=None,
                    help="print {records, sha256} of REL's committed blob at HEAD (for a pin)")
    args = ap.parse_args(argv)
    if args.measure_prefix:
        rel = args.measure_prefix.replace("\\", "/")
        held = subprocess.run(["git", "-C", str(args.repo), "show", f"HEAD:{rel}"],
                              capture_output=True, check=True, timeout=120).stdout
        print(json.dumps({"rel": rel, **measure_prefix(held)}))
        return 0
    entries: list[tuple[str, str]] = []
    for ln in sys.stdin.read().splitlines():
        blob, sep, rel = ln.partition("\t")
        if sep:
            entries.append((blob.strip(), rel.strip().replace("\\", "/")))
    try:
        ids = declared_ids(args.repo)
    except FenceConfigError as exc:
        # FAIL CLOSED: the publisher reads any non-zero exit as "publish nothing this pass".
        print(f"login fence: {exc}", file=sys.stderr)
        return 2
    doc = judge(args.repo, entries, ids)
    out = args.artifact or (args.repo / "desks" / "mt5" / "reports" / "LOGIN_FENCE.json")
    _write(out, doc)                      # the artifact exists even if alerting fails below
    rc = 0
    try:
        doc["alert"] = record_alert(doc, args.repo)
        doc["page"] = page(doc, args.repo)
    except Exception as exc:              # recorded, never swallowed
        doc["alert_error"] = type(exc).__name__
        print(f"login fence: alert/page failed ({type(exc).__name__})", file=sys.stderr)
        rc = 3 if doc["status"] != "OK" else 0
    _write(out, doc)
    if rc:
        return rc
    for rel in sorted(doc["refused"]):
        print(rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

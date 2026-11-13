"""ONE REDACTOR FOR EVERY BOX ARTIFACT THAT CROSSES INTO THE PUBLIC REPOSITORY.

WHY (underbuilt audit, 2026-11-13). Several DONE claims could not be verified from the branch
because their proof artifacts lived only on the trading box: the recovery drills (L141), the six
committees (L144), the alpha-capture / alt-proxies / paid-substitute legs (L230), the CPU cap and
judge share (L115), the memecoin paper fill (L310), the memecoin backup deletion (L318). Each of
those writers was built for a private disk: free exception text, absolute Windows paths, the
box's hostname, process command lines. The repository is PUBLIC, so nothing box-written may be
copied into it raw. This module is the one rule every published projection goes through.

    public_text(s)          a string with every identifying token replaced by a placeholder
    public_fields(obj)      a JSON value, recursively: identity keys dropped, error fields reduced
                            to the exception TYPE, path keys made repo-relative, every string
                            through public_text, containers bounded in depth and length
    violations(text)        the planted-token scan: [] when the serialised text is publishable

What is removed (each is a placeholder, never a deletion that changes a sentence's meaning):
  * IPv4 / IPv6 addresses                                           -> <ip>
  * this machine's hostname, its machine id, and the known box-name shapes (vmi*, ubuntu-*-hel*,
    DESKTOP-*/WIN-*/LAPTOP-*)                                       -> <host>
  * absolute paths (C:\\..., \\\\server\\share, /home, /root, /opt, /mnt, /tmp, /var, /Users ...):
    repo-relative when under the repository root, else              -> <abs-path>
  * credentials: sk-/ghp_/github_pat_/xox*/AKIA/JWT shapes, `Bearer x`, `token=x`, `password: x`
                                                                    -> <redacted>
  * e-mail addresses                                                -> <email>
  * account numbers: every number the box declares (login_fence.declared_ids) and any
    `account|login <digits>` phrase                                 -> <account>
  * exception text: `ValueError: anything` keeps `ValueError`; `[WinError 5] ...` keeps the code;
    `Traceback (most recent call last)` and everything after it is dropped.

Keys removed wholesale (login_fence.is_login_key, plus host/process/credential names): see
DROP_KEYS. Values under ERROR_KEYS become the exception type alone.

This never raises on odd input: a value it cannot classify is published as its type name.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import socket
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

IP = "<ip>"
HOST = "<host>"
ABS = "<abs-path>"
SECRET = "<redacted>"  # noqa: S105 -- a placeholder, not a credential
EMAIL = "<email>"
ACCOUNT = "<account>"

#: Default bounds of a projection: deep enough for a report's per-row verdicts, never a ledger.
MAX_DEPTH = 6
MAX_LIST = 50
MAX_STR = 300

_IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.]*\d)")
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])")
_HOST_SHAPES = re.compile(
    r"(?i)\b(?:vmi\d{4,}|ubuntu-\d+gb-[a-z]+\d*-\d+|(?:desktop|win|laptop|ip)-[a-z0-9-]{5,})\b")
_WIN_PATH = re.compile(r"(?<![\w])[A-Za-z]:[\\/]+[^\s\"'<>|;,]*")
_UNC_PATH = re.compile(r"\\\\[A-Za-z0-9_.$-]+\\[^\s\"'<>|;,]*")
_POSIX_PATH = re.compile(
    r"(?<![\w.~/-])/(?:home|root|opt|mnt|tmp|var|usr|etc|Users|srv|private|proc|run|data|media|"
    r"workspace|builds|github|app|Volumes)(?:/[^\s\"'<>|;,]*)?")
_HOME_PATH = re.compile(r"(?<![\w])~[\\/][^\s\"'<>|;,]*")
_TOKENS = (
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
)
_KV_SECRET = re.compile(
    r"(?i)\b((?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|token|secret|password|"
    r"passwd|pwd|private[_-]?key|client[_-]?secret|cookie|authorization)"
    r"[\"']?\s*[:=]\s*[\"']?)([^\s\"',;&]{4,})")
#: A long base64/alphanumeric run that mixes cases and digits: a key, not a word. Pure hex (git
#: shas, sha256 digests) is not matched -- those identify a release, not a person or a box.
#: '/' is excluded so a repo-relative path ("desks/mt5/reports/X_Y.json") is never a token, and
#: four digits are required so a CamelCase or SNAKE_CASE identifier is not either.
_OPAQUE = re.compile(r"(?<![A-Za-z0-9+_-])(?=[A-Za-z0-9+_-]*[a-z])(?=[A-Za-z0-9+_-]*[A-Z])"
                     r"(?=(?:[A-Za-z+_-]*\d){4})[A-Za-z0-9+_-]{32,}={0,2}(?![A-Za-z0-9+_-])")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")
_ACCOUNT_PHRASE = re.compile(r"(?i)\b(account|acct|login)(\s*(?:#|no\.?|number|id)?\s*[:=]?\s*)"
                             r"\d{4,12}\b")
_TRACEBACK = re.compile(r"Traceback \(most recent call last\).*", re.S)
_EXC = re.compile(
    r"\b((?:[A-Za-z_][\w]*\.)*[A-Z][A-Za-z0-9_]*(?:Error|Exception|Exit|Interrupt|Fault|"
    r"Expired|Denied|Timeout|Warning|Refused))(?::[ \t]*|\()[^;\n]*")
_WINERR = re.compile(r"\[(WinError|Errno)\s*(-?\d+)\][^;\n]*")


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


#: Keys never published, whatever their value: machine identity, process identity, credentials,
#: command lines and environments. Normalised (lower-case, punctuation removed).
DROP_KEYS: frozenset[str] = frozenset(_norm(k) for k in (
    "host", "hostname", "host_name", "computername", "computer", "machine", "machine_id",
    "machineguid", "node", "nodename", "fqdn", "ip", "ip_address", "ipaddr", "addr", "remote_addr",
    "mac", "mac_address", "attests_to_host", "server", "broker_server", "user", "username",
    "user_name", "owner", "sid", "domain", "userdomain", "pid", "ppid", "pids", "process_ids",
    "launcher_pid", "child_pid", "cmdline", "command_line", "commandline", "argv", "arguments",
    "execute", "env", "environ", "environment", "password", "passwd", "secret", "token",
    "api_key", "apikey", "access_token", "private_key", "authorization", "cookie", "cookies",
    "session_id", "email", "phone", "working_directory", "cwd", "home", "userprofile",
    "credential", "credentials", "headers",
))
_DROP_SUBSTR = ("secret", "password", "passwd", "token", "apikey", "credential", "cookie",
                "hostname", "machineid", "cmdline", "privatekey")
#: Keys whose value is an error: published as the exception type alone.
ERROR_KEYS: frozenset[str] = frozenset(_norm(k) for k in (
    "error", "err", "errors", "exception", "exc", "traceback", "stderr", "stdout", "stack",
    "error_text", "message_raw", "exc_text", "last_error", "failure", "crash",
))
_KEEP_NOT_LOGIN = frozenset(_norm(k) for k in ("accounts_n", "account_ledger"))


@lru_cache(maxsize=1)
def _host_names() -> tuple[str, ...]:
    names: set[str] = set()
    for get in (socket.gethostname, lambda: socket.getfqdn()):
        with contextlib.suppress(OSError):
            names.add(str(get()))
    for var in ("COMPUTERNAME", "HOSTNAME", "USERDOMAIN", "QUANT_BOX_HOST"):
        v = os.environ.get(var)
        if v:
            names.add(v)
    try:
        from libs.ops import host_identity
        mid = host_identity.read_machine_id()
        if mid:
            names.add(str(mid))
    except Exception:     # identity is best effort; the shapes below still apply
        pass
    # A hostname shorter than 4 characters ("vm", "box") would scrub ordinary words.
    return tuple(sorted((n for n in names if len(n) >= 4 and n.lower() not in
                         ("localhost", "localdomain")), key=len, reverse=True))


@lru_cache(maxsize=1)
def _declared_accounts() -> tuple[str, ...]:
    try:
        from libs.ops import login_fence
        return tuple(sorted(login_fence.declared_ids(ROOT), key=len, reverse=True))
    except Exception:     # FenceConfigError, import trouble: the phrase pattern still applies
        return ()


def _roots() -> tuple[str, ...]:
    r = str(ROOT)
    return (r, r.replace("/", "\\"), r.replace("\\", "/"))


def public_path(value: str) -> str:
    """A path as the public repository may show it: repo-relative, or <abs-path>."""
    s = str(value).strip()
    for root in _roots():
        if root and s.lower().startswith(root.lower()):
            rel = s[len(root):].lstrip("\\/").replace("\\", "/")
            return rel or "."
    if (_WIN_PATH.fullmatch(s) or _UNC_PATH.fullmatch(s) or _POSIX_PATH.fullmatch(s)
            or _HOME_PATH.fullmatch(s) or s.startswith("/")):
        return ABS
    return s.replace("\\", "/") if "\\" in s and ":" not in s else s


def _sub_path(m: re.Match[str]) -> str:
    return public_path(m.group(0))


def exception_type(value: Any) -> str | None:
    """The exception type a value names, or None. `OSError: [Errno 2] x` -> `OSError`."""
    if value is None:
        return None
    if isinstance(value, BaseException):
        return type(value).__name__
    s = str(value)
    m = _EXC.search(s) or re.search(r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception))\b", s)
    if m:
        return m.group(1).rsplit(".", 1)[-1]
    w = _WINERR.search(s)
    if w:
        return f"[{w.group(1)} {w.group(2)}]"
    if "Traceback" in s:
        return "Traceback"
    return "error" if s.strip() else None


def public_text(value: Any, max_len: int = MAX_STR) -> str:
    """`value` as a string the public repository may carry."""
    s = str(value)
    s = _TRACEBACK.sub("Traceback", s)
    s = _EXC.sub(lambda m: m.group(1).rsplit(".", 1)[-1], s)
    s = _WINERR.sub(lambda m: f"[{m.group(1)} {m.group(2)}]", s)
    for pat in _TOKENS:
        s = pat.sub(SECRET, s)
    s = _KV_SECRET.sub(lambda m: m.group(1) + SECRET, s)
    s = _UNC_PATH.sub(_sub_path, s)
    s = _WIN_PATH.sub(_sub_path, s)
    s = _HOME_PATH.sub(ABS, s)
    s = _POSIX_PATH.sub(_sub_path, s)
    s = _EMAIL.sub(EMAIL, s)
    s = _IPV4.sub(IP, s)
    s = _IPV6.sub(lambda m: IP if (m.group(0).count(":") >= 3 and (
        re.search(r"[A-Fa-f]", m.group(0)) or "::" in m.group(0))) else m.group(0), s)
    for name in _host_names():
        s = re.sub(re.escape(name), HOST, s, flags=re.I)
    s = _HOST_SHAPES.sub(HOST, s)
    for acct in _declared_accounts():
        s = re.sub(rf"(?<!\d){re.escape(acct)}(?!\d)", ACCOUNT, s)
    s = _ACCOUNT_PHRASE.sub(lambda m: m.group(1) + m.group(2) + ACCOUNT, s)
    s = _OPAQUE.sub(SECRET, s)
    if len(s) > max_len:
        s = s[: max(0, max_len - 1)] + "~"
    return s


def is_drop_key(key: Any) -> bool:
    n = _norm(key)
    if n in _KEEP_NOT_LOGIN:
        return False
    if n in DROP_KEYS or any(t in n for t in _DROP_SUBSTR):
        return True
    try:
        from libs.ops import login_fence
        return bool(login_fence.is_login_key(str(key)))
    except Exception:
        return n in ("login", "account", "accountnumber", "loginid", "mt5login")


def is_error_key(key: Any) -> bool:
    return _norm(key) in ERROR_KEYS


def _is_path_key(key: Any) -> bool:
    n = _norm(key)
    return n in ("path", "file", "dir", "directory", "root", "folder", "logdirectory",
                 "release", "script", "location") or n.endswith(("path", "file", "dir"))


class _Budget:
    def __init__(self) -> None:
        self.dropped_keys = 0
        self.truncated_lists = 0
        self.collapsed = 0


def _fields(obj: Any, depth: int, max_depth: int, max_list: int, max_str: int,
            b: _Budget) -> Any:
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        if isinstance(obj, float) and obj != obj:     # NaN is not JSON
            return None
        return obj
    if isinstance(obj, str):
        return public_text(obj, max_str)
    if isinstance(obj, dict):
        if depth >= max_depth:
            b.collapsed += 1
            return {"n": len(obj)}
        out: dict[str, Any] = {}
        for k, v in obj.items():
            key = public_text(k, 80)
            if is_drop_key(k):
                b.dropped_keys += 1
                continue
            if is_error_key(k):
                if isinstance(v, (list, tuple)):
                    out[key] = [exception_type(x) for x in list(v)[:max_list]]
                elif isinstance(v, dict):
                    out[key] = {public_text(kk, 80): exception_type(vv)
                                for kk, vv in list(v.items())[:max_list]}
                else:
                    out[key] = exception_type(v)
                continue
            if _is_path_key(k) and isinstance(v, str):
                out[key] = public_text(public_path(v), max_str)
                continue
            out[key] = _fields(v, depth + 1, max_depth, max_list, max_str, b)
        return out
    if isinstance(obj, (list, tuple, set, frozenset)):
        seq = list(obj)
        if depth >= max_depth:
            b.collapsed += 1
            return {"n": len(seq)}
        if len(seq) > max_list:
            b.truncated_lists += 1
            seq = seq[:max_list]
        return [_fields(v, depth + 1, max_depth, max_list, max_str, b) for v in seq]
    return type(obj).__name__


def public_fields(obj: Any, *, max_depth: int = MAX_DEPTH, max_list: int = MAX_LIST,
                  max_str: int = MAX_STR) -> tuple[Any, dict[str, int]]:
    """(the publishable projection of `obj`, what the projection removed, by count)."""
    b = _Budget()
    out = _fields(obj, 0, max_depth, max_list, max_str, b)
    return out, {"dropped_keys": b.dropped_keys, "truncated_lists": b.truncated_lists,
                 "collapsed_containers": b.collapsed}


def violations(text: str, extra: Iterable[str] = ()) -> list[str]:
    """Why `text` may NOT be published, by category name only (never the matched value).

    The final fence on every projection: the redactor above should already have removed all of
    these, so a non-empty answer means a writer produced a shape the redactor does not know, and
    the projection is replaced by its reduced summary."""
    out: list[str] = []
    if _IPV4.search(text):
        out.append("ipv4")
    for m in _IPV6.finditer(text):
        g = m.group(0)
        if g.count(":") >= 3 and (re.search(r"[A-Fa-f]", g) or "::" in g):
            out.append("ipv6")
            break
    if any(re.search(re.escape(n), text, re.I) for n in _host_names()) or \
            _HOST_SHAPES.search(text):
        out.append("hostname")
    if _WIN_PATH.search(text) or _UNC_PATH.search(text) or _POSIX_PATH.search(text) or \
            _HOME_PATH.search(text):
        out.append("absolute_path")
    if any(p.search(text) for p in _TOKENS) or _OPAQUE.search(text):
        out.append("token")
    if any(m.group(2) != SECRET and not m.group(2).startswith("<")
           for m in _KV_SECRET.finditer(text)):
        out.append("credential_pair")
    if _EMAIL.search(text):
        out.append("email")
    if "Traceback (most recent call last)" in text or any(
            m.group(0).rstrip() != m.group(1) and len(m.group(0)) > len(m.group(1)) + 1
            for m in _EXC.finditer(text)):
        out.append("exception_text")
    for acct in _declared_accounts():
        if re.search(rf"(?<!\d){re.escape(acct)}(?!\d)", text):
            out.append("account_number")
            break
    for tok in extra:
        if tok and tok in text:
            out.append("planted")
            break
    return out


def dumps_public(doc: Any) -> str:
    """The serialisation every published projection uses (LF, sorted, compact-ish)."""
    return json.dumps(doc, indent=1, sort_keys=True, default=str, ensure_ascii=False) + "\n"

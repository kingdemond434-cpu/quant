"""SHORT-LIVED TOKENS FROM LONG-LIVED CREDENTIALS: the operator sets the credential once.

Three keyed sources hand out tokens that expire faster than anyone re-pastes them, so a pasted
value worked for a day (or ten minutes) and the source then read UNCONFIGURED or HTTP 401 for
good. This module returns a valid token for each, in this order:

    1. the explicit short-lived env var, if set and (where it is a JWT) not expired -- so a box
       that already pastes `JQUANTS_TOKEN` / `CDSE_TOKEN` / `MYFXBOOK_SESSION` behaves as before;
    2. a non-expiring API key where the provider issues one (J-Quants V2);
    3. a cached token minted earlier, if not expired (with a safety margin);
    4. a fresh token minted from the long-lived credential, which is then cached with its expiry.

THE PROVIDERS' OWN DOCUMENTED FLOWS (verified 2026-10-06):

  J-Quants   https://jpx-jquants.com/en/spec/migration-v1-v2 and /en/spec/quickstart: V2 uses an
             "API Key (`x-api-key` header) issued from the dashboard"; "API Key itself has no
             expiration date"; "Users who registered on or after December 22, 2025 can only use
             V2". The V1 flow (`POST /v1/token/auth_user` {mailaddress,password} -> refreshToken,
             ~1 week; `POST /v1/token/auth_refresh?refreshtoken=` -> idToken, 24 h, sent as
             `Authorization: Bearer`) is marked Discontinued there and is kept only as a legacy
             fallback for older accounts. Base: https://api.jquants.com
  CDSE       https://documentation.dataspace.copernicus.eu/APIs/Token.html: POST form to
             https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token
             with grant_type=password + client_id=cdse-public + username + password, or
             grant_type=client_credentials + client_id + client_secret.
             https://documentation.dataspace.copernicus.eu/Quotas.html: "A token stays active for
             10 minutes". Sent as `Authorization: Bearer`.
  Myfxbook   https://www.myfxbook.com/api: `login.json?email=&password=` returns `session`;
             "Sessions are IP-bound and expire after 1 month." Sent as the `session` query param.

SECRECY. No token, password, secret or refresh token is ever logged, printed, put in a returned
`detail`, or recorded in a URL. `TokenResult.token` is excluded from repr. The cache lives under
the gitignored `data/secrets/token_cache/` (mode 0700 dir, 0600 files on POSIX; on Windows the
directory's inherited user-only ACL), and its non-secret fields are what `check_credentials.py`
reports.

NEVER RAISES. Every failure is a typed status: BLOCKED_ON_KEY when no long-lived credential is
configured, REFRESH_FAILED (with the HTTP status when there was one) when the mint failed.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

OK = "OK"
BLOCKED_ON_KEY = "BLOCKED_ON_KEY"
REFRESH_FAILED = "REFRESH_FAILED"

#: Seconds before the stated expiry at which a token is treated as expired, so a token is never
#: handed to a request that will outlive it.
SAFETY_S = 60.0

JQUANTS_BASE = "https://api.jquants.com"
CDSE_ENDPOINT = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/"
                 "openid-connect/token")
MYFXBOOK_LOGIN_URL = "https://www.myfxbook.com/api/login.json"


@dataclass(frozen=True)
class Provider:
    name: str
    short_env: str                      #: the short-lived env var consumers used to read
    long_envs: tuple[tuple[str, ...], ...]  #: alternative long-lived credential sets
    apply: str                          #: "bearer" | "x-api-key" | "query:<param>"
    hosts: tuple[str, ...]              #: the token is only ever sent to these hosts
    docs: str


PROVIDERS: dict[str, Provider] = {
    "JQUANTS_TOKEN": Provider(
        name="jquants", short_env="JQUANTS_TOKEN",
        long_envs=(("JQUANTS_API_KEY",), ("JQUANTS_REFRESH_TOKEN",),
                   ("JQUANTS_MAILADDRESS", "JQUANTS_PASSWORD")),
        apply="bearer", hosts=("api.jquants.com",),
        docs="https://jpx-jquants.com/en/spec/migration-v1-v2"),
    "CDSE_TOKEN": Provider(
        name="cdse", short_env="CDSE_TOKEN",
        long_envs=(("CDSE_CLIENT_ID", "CDSE_CLIENT_SECRET"), ("CDSE_USERNAME", "CDSE_PASSWORD")),
        apply="bearer",
        hosts=("catalogue.dataspace.copernicus.eu", "zipper.dataspace.copernicus.eu",
               "download.dataspace.copernicus.eu", "sh.dataspace.copernicus.eu"),
        docs="https://documentation.dataspace.copernicus.eu/APIs/Token.html"),
    "MYFXBOOK_SESSION": Provider(
        name="myfxbook", short_env="MYFXBOOK_SESSION",
        long_envs=(("MYFXBOOK_EMAIL", "MYFXBOOK_PASSWORD"),),
        apply="query:session", hosts=("www.myfxbook.com", "myfxbook.com"),
        docs="https://www.myfxbook.com/api"),
}
MANAGED: frozenset[str] = frozenset(PROVIDERS)


@dataclass(frozen=True)
class TokenResult:
    """A token or a typed reason there is none. `token` never appears in repr."""

    status: str
    env: str
    token: str | None = field(default=None, repr=False)
    source: str = ""            #: env | api_key | cache | minted | ""
    apply: str = "bearer"       #: how the token goes on a request (overridden for an API key)
    expires_at: float | None = None
    http: int | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK and bool(self.token)


# ---------------------------------------------------------------------------------------------
# HTTP seam (tests replace `_http`; nothing here ever puts a body or URL into a message)
# ---------------------------------------------------------------------------------------------

def _http(method: str, url: str, data: bytes | None, headers: dict[str, str],
          timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(getattr(r, "status", 200) or 200), r.read(1_000_000)
    except urllib.error.HTTPError as e:
        return int(e.code or 0), b""


class _MintError(Exception):
    def __init__(self, http: int | None, detail: str) -> None:
        super().__init__(detail)
        self.http = http
        self.detail = detail


# ---------------------------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------------------------

_LOCK = threading.Lock()


def cache_dir() -> Path:
    override = os.environ.get("QUANT_TOKEN_CACHE_DIR")
    return Path(override) if override else ROOT / "data" / "secrets" / "token_cache"


def _cache_path(p: Provider) -> Path:
    return cache_dir() / f"{p.name}.json"


def _read_cache(p: Provider) -> dict[str, Any]:
    try:
        doc = json.loads(_cache_path(p).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_cache(p: Provider, doc: dict[str, Any]) -> None:
    d = cache_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(d, 0o700)
        path = _cache_path(p)
        tmp = path.with_suffix(".tmp")
        if os.name == "posix":
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(doc, indent=1))
            os.chmod(tmp, 0o600)
        else:
            tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass  # a cache that cannot be written costs one extra mint, never a failure


def _record(p: Provider, status: str, http: int | None, detail: str,
            token_doc: dict[str, Any] | None = None) -> None:
    doc = _read_cache(p)
    if token_doc is not None:
        doc.update(token_doc)
    doc.update({"last_status": status, "last_http": http, "last_detail": detail,
                "last_attempt_at": time.time()})
    _write_cache(p, doc)


def invalidate(env: str) -> None:
    """Drop the cached token (e.g. after the consumer got a 401 with it)."""
    p = PROVIDERS.get(env)
    if p is None:
        return
    with _LOCK:
        doc = _read_cache(p)
        for k in ("token", "expires_at", "refresh_token", "refresh_expires_at"):
            doc.pop(k, None)
        if doc:
            _write_cache(p, doc)


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------

def jwt_exp(token: str) -> float | None:
    """The `exp` claim of a JWT, unverified (used only to decide whether to re-mint)."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        pad = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(pad.encode()))
        exp = claims.get("exp") if isinstance(claims, dict) else None
        return float(exp) if isinstance(exp, (int, float)) else None
    except (ValueError, TypeError):
        return None


def _fresh(expires_at: Any, now: float) -> bool:
    return expires_at is None or (isinstance(expires_at, (int, float))
                                  and float(expires_at) - SAFETY_S > now)


def _json(body: bytes) -> dict[str, Any]:
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return {}
    return doc if isinstance(doc, dict) else {}


def scrub(text: str, env: Mapping[str, str] | None = None) -> str:
    """Remove every managed secret value (env or cached) from `text`."""
    e = os.environ if env is None else env
    secrets: list[str] = []
    for p in PROVIDERS.values():
        secrets.append(e.get(p.short_env, ""))
        for group in p.long_envs:
            secrets.extend(e.get(k, "") for k in group)
        c = _read_cache(p)
        secrets.extend(str(c.get(k) or "") for k in ("token", "refresh_token"))
    for s in sorted({s for s in secrets if len(s) >= 4}, key=len, reverse=True):
        text = text.replace(s, "<redacted>")
        q = urllib.parse.quote(s, safe="")
        if q != s:
            text = text.replace(q, "<redacted>")
    return text


# ---------------------------------------------------------------------------------------------
# minting, one per provider (each returns the cache doc fields; raises _MintError)
# ---------------------------------------------------------------------------------------------

def _mint_jquants(e: Mapping[str, str], cached: dict[str, Any], now: float,
                  timeout: float) -> dict[str, Any]:
    refresh = e.get("JQUANTS_REFRESH_TOKEN", "")
    refresh_exp: float | None = None
    if not refresh and _fresh(cached.get("refresh_expires_at"), now) and cached.get(
            "refresh_token"):
        refresh = str(cached["refresh_token"])
        refresh_exp = cached.get("refresh_expires_at")
    if not refresh:
        body = json.dumps({"mailaddress": e.get("JQUANTS_MAILADDRESS", ""),
                           "password": e.get("JQUANTS_PASSWORD", "")}).encode()
        code, raw = _http("POST", f"{JQUANTS_BASE}/v1/token/auth_user", body,
                          {"Content-Type": "application/json"}, timeout)
        refresh = str(_json(raw).get("refreshToken") or "") if code == 200 else ""
        if not refresh:
            raise _MintError(code, f"J-Quants auth_user answered HTTP {code}")
        # documented validity of a refresh token is one week; keep a day in hand
        refresh_exp = now + 6 * 86400
    q = urllib.parse.urlencode({"refreshtoken": refresh})
    code, raw = _http("POST", f"{JQUANTS_BASE}/v1/token/auth_refresh?{q}", None, {}, timeout)
    tok = str(_json(raw).get("idToken") or "") if code == 200 else ""
    if not tok:
        raise _MintError(code, f"J-Quants auth_refresh answered HTTP {code}")
    out: dict[str, Any] = {"token": tok, "expires_at": jwt_exp(tok) or now + 24 * 3600}
    if not e.get("JQUANTS_REFRESH_TOKEN"):
        out.update({"refresh_token": refresh, "refresh_expires_at": refresh_exp})
    return out


def _mint_cdse(e: Mapping[str, str], cached: dict[str, Any], now: float,
               timeout: float) -> dict[str, Any]:
    if e.get("CDSE_CLIENT_ID") and e.get("CDSE_CLIENT_SECRET"):
        form = {"grant_type": "client_credentials", "client_id": e["CDSE_CLIENT_ID"],
                "client_secret": e["CDSE_CLIENT_SECRET"]}
    else:
        form = {"grant_type": "password", "client_id": "cdse-public",
                "username": e.get("CDSE_USERNAME", ""), "password": e.get("CDSE_PASSWORD", "")}
    code, raw = _http("POST", CDSE_ENDPOINT, urllib.parse.urlencode(form).encode(),
                      {"Content-Type": "application/x-www-form-urlencoded"}, timeout)
    doc = _json(raw) if code == 200 else {}
    tok = str(doc.get("access_token") or "")
    if not tok:
        raise _MintError(code, f"CDSE token endpoint answered HTTP {code}")
    life = doc.get("expires_in")
    exp = now + float(life) if isinstance(life, (int, float)) else (jwt_exp(tok) or now + 600)
    return {"token": tok, "expires_at": exp}


def _mint_myfxbook(e: Mapping[str, str], cached: dict[str, Any], now: float,
                   timeout: float) -> dict[str, Any]:
    q = urllib.parse.urlencode({"email": e.get("MYFXBOOK_EMAIL", ""),
                                "password": e.get("MYFXBOOK_PASSWORD", "")})
    code, raw = _http("GET", f"{MYFXBOOK_LOGIN_URL}?{q}", None, {}, timeout)
    doc = _json(raw) if code == 200 else {}
    tok = str(doc.get("session") or "")
    if doc.get("error") or not tok:
        # Myfxbook answers a bad login with HTTP 200 and {"error": true}; its message is safe to
        # name only by kind, so it is not echoed.
        raise _MintError(code, f"Myfxbook login answered HTTP {code}"
                               + (" with error=true" if doc.get("error") else ""))
    # The session is returned URL-encoded; store it decoded so it is encoded exactly once on use.
    # Documented TTL is one month; re-mint after 25 days.
    return {"token": urllib.parse.unquote(tok), "expires_at": now + 25 * 86400}


_MINTERS: dict[str, Callable[[Mapping[str, str], dict[str, Any], float, float],
                             dict[str, Any]]] = {
    "jquants": _mint_jquants, "cdse": _mint_cdse, "myfxbook": _mint_myfxbook}


# ---------------------------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------------------------

def _long_lived(p: Provider, e: Mapping[str, str]) -> tuple[str, ...] | None:
    for group in p.long_envs:
        if all(e.get(k) for k in group):
            return group
    return None


def get_token(env: str, *, environ: Mapping[str, str] | None = None,
              timeout: float = 20.0, now: float | None = None) -> TokenResult:
    """A valid token for the short-lived env var `env`, or a typed reason. Never raises."""
    try:
        return _get_token(env, os.environ if environ is None else environ, timeout,
                          time.time() if now is None else now)
    except Exception as exc:  # the contract is "never raises into callers"
        return TokenResult(REFRESH_FAILED, env, detail=f"internal {type(exc).__name__}")


def _get_token(env: str, e: Mapping[str, str], timeout: float, now: float) -> TokenResult:
    p = PROVIDERS.get(env)
    if p is None:
        val = e.get(env, "")
        return (TokenResult(OK, env, token=val, source="env") if val
                else TokenResult(BLOCKED_ON_KEY, env, detail=f"{env} is not set"))

    pasted = e.get(p.short_env, "")
    if pasted:
        exp = jwt_exp(pasted)
        if _fresh(exp, now):
            return TokenResult(OK, env, token=pasted, source="env", apply=p.apply,
                               expires_at=exp)
    if p.name == "jquants" and e.get("JQUANTS_API_KEY"):
        return TokenResult(OK, env, token=e["JQUANTS_API_KEY"], source="api_key",
                           apply="x-api-key")

    group = _long_lived(p, e)
    with _LOCK:
        cached = _read_cache(p)
        if cached.get("token") and _fresh(cached.get("expires_at"), now):
            return TokenResult(OK, env, token=str(cached["token"]), source="cache",
                               apply=p.apply, expires_at=cached.get("expires_at"))
        if group is None:
            why = (f"{p.short_env} is expired and " if pasted else "")
            detail = (f"{why}no long-lived credential: set "
                      + " or ".join("+".join(g) for g in p.long_envs))
            _record(p, BLOCKED_ON_KEY, None, detail)
            return TokenResult(BLOCKED_ON_KEY, env, apply=p.apply, detail=detail)
        try:
            doc = _MINTERS[p.name](e, cached, now, timeout)
        except _MintError as m:
            detail = scrub(m.detail, e)
            _record(p, REFRESH_FAILED, m.http, detail)
            return TokenResult(REFRESH_FAILED, env, apply=p.apply, http=m.http, detail=detail)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            detail = f"unreachable ({type(exc).__name__})"
            _record(p, REFRESH_FAILED, None, detail)
            return TokenResult(REFRESH_FAILED, env, apply=p.apply, detail=detail)
        doc["minted_at"] = now
        doc["minted_from"] = "+".join(group)
        _record(p, OK, 200, "minted", doc)
        return TokenResult(OK, env, token=str(doc["token"]), source="minted", apply=p.apply,
                           expires_at=doc.get("expires_at"), http=200)


def apply_to_request(res: TokenResult, url: str,
                     headers: dict[str, str]) -> tuple[str, dict[str, str]]:
    """The URL and headers to SEND. The token goes only to the provider's own API hosts; for any
    other host (a landing page registered as the source URL) the request is returned unchanged.
    The caller records the ORIGINAL url, never the returned one."""
    p = PROVIDERS.get(res.env)
    if not res.ok or p is None or not res.token:
        return url, headers
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    if host not in p.hosts:
        return url, headers
    out = dict(headers)
    if res.apply == "x-api-key":
        out["x-api-key"] = res.token
    elif res.apply == "bearer":
        out["Authorization"] = f"Bearer {res.token}"
    elif res.apply.startswith("query:"):
        param = res.apply.split(":", 1)[1]
        parts = urllib.parse.urlsplit(url)
        qs = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
              if k != param] + [(param, res.token)]
        url = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(qs)))
    return url, out


def status_report(environ: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """Per provider: is a long-lived credential present, cached expiry, last refresh status.
    Booleans, timestamps and statuses only -- never a value."""
    e = os.environ if environ is None else environ
    rows = []
    for p in PROVIDERS.values():
        c = _read_cache(p)
        group = _long_lived(p, e)
        rows.append({
            "env": p.short_env, "provider": p.name,
            "short_lived_env_set": bool(e.get(p.short_env)),
            "long_lived_present": group is not None,
            "long_lived_set": "+".join(group) if group else "",
            "long_lived_options": ["+".join(g) for g in p.long_envs],
            "cached_token": bool(c.get("token")),
            "cached_expires_at": c.get("expires_at"),
            "last_status": c.get("last_status") or "NEVER_ATTEMPTED",
            "last_http": c.get("last_http"),
            "last_attempt_at": c.get("last_attempt_at"),
            "last_detail": str(c.get("last_detail") or ""),
            "docs": p.docs,
        })
    return rows


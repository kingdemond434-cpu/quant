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

TERMS FENCE (security audit of #218, 2026-10-06). A provider listed in `TERMS` sends NO
credential -- no login, no mint, no pasted token on a request -- until its terms are recorded as
"confirmed" with the URL and a verbatim quote in `TERMS_EVIDENCE`. Anything else is
BLOCKED_ON_TERMS (fail closed), and so is a provider absent from `TERMS`. CDSE is confirmed
(with an attribution duty, `attribution()`); J-Quants is "confirmed_private_use" on the
principal's 2026-10-06 answer (art. 8: private use by the registered individual), so its every
result carries `private_use=True` and nothing from it may reach git or a shared output;
Myfxbook is not confirmed (see the evidence).

CREDENTIALS ARE READ THROUGH `libs.ops.env_keys.read_key` (#201), never straight from
`os.environ`: a value set with `setx /M` after a resident task started lives only in the machine
registry, and read_key finds it there.

STATUS FOR A READER. `collector_status` maps a result to the row status a consumer records:
OK; UNCONFIGURED only when no credential is configured at all; BLOCKED_AUTH when a refresh was
attempted and the provider refused it (a configured credential that does not work is not an
absent one); BLOCKED_ON_TERMS when the terms fence held.

URLS NEVER CARRY A CREDENTIAL INTO A RECORD. `strip_url_credentials` blanks userinfo and every
credential-named query parameter; `scrub` applies the same to free text, after removing every
managed secret value. Myfxbook's documented login takes the password in a GET query; that URL
exists only inside `_http` and is never put into a detail, a cache field or an exception text.

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
import dataclasses
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

OK = "OK"
BLOCKED_ON_KEY = "BLOCKED_ON_KEY"
REFRESH_FAILED = "REFRESH_FAILED"
BLOCKED_ON_TERMS = "BLOCKED_ON_TERMS"

#: The status a consumer RECORDS for a token result (see `collector_status`).
UNCONFIGURED = "UNCONFIGURED"
BLOCKED_AUTH = "BLOCKED_AUTH"

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

#: Terms verdict per terms-fenced provider: "confirmed" | "confirmed_private_use" |
#: "to_confirm" | "refused". A provider listed here sends no credential unless its verdict is in
#: PERMITTED_VERDICTS (fail closed). Same shape as desks/mt5/research/alt_proxies.TERMS /
#: TERMS_EVIDENCE.
TERMS: dict[str, tuple[str, str]] = {
    "cdse": ("confirmed", "CDSE terms: Sentinel data free, full and open, governed by the "
                          "Sentinel Data Legal Notice (reproduction, distribution, adaptation)"),
    "myfxbook": ("to_confirm", "Myfxbook API page: 'The API allows access to personal "
                               "information only'; its Terms say 'Reproduction is prohibited' "
                               "and do not address automated or commercial use of community "
                               "data -- not a clear permission for this desk's use"),
    "jquants": ("confirmed_private_use",
                "J-Quants API Terms of Service art. 8: use is limited to the registered "
                "(individual) user's private use, which the usage page defines as 'one's own "
                "investment analysis, portfolio management'. The principal confirmed "
                "2026-10-06 that the desk trades only their own money, i.e. private use by the "
                "registered individual. PERMITTED FOR PRIVATE USE ONLY, under the conditions in "
                "TERMS_CONDITIONS: no redistribution, no sharing -- nothing from it reaches git "
                "(the repository is public), a leg's stdout, any shared output, or E8"),
}
#: Verdicts under which a provider's credential may be sent. "confirmed_private_use" permits the
#: fetch ONLY under its private-use condition: every result carries `private_use=True` and every
#: consumer keeps the data, and anything derived from it, out of git and every shared output.
PERMITTED_VERDICTS: frozenset[str] = frozenset({"confirmed", "confirmed_private_use"})
PRIVATE_USE = "confirmed_private_use"
_TERMS_CHK = "2026-10-06"
TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    "cdse": {
        "terms_url": "https://dataspace.copernicus.eu/terms-and-conditions",
        "terms_quote": ("The access and use of Copernicus Sentinel data is available on a free, "
                        "full and open basis through the Copernicus Data Space Ecosystem and "
                        "shall be governed by the Legal Notice on the use of Copernicus Sentinel "
                        "Data and Service"),
        "licence_url": ("https://sentinels.copernicus.eu/documents/247904/690755/"
                        "Sentinel_Data_Legal_Notice"),
        "licence_quote": ("users shall have a free, full and open access to Copernicus Sentinel "
                          "Data and Service Information ... (a) reproduction; (b) distribution; "
                          "(c) communication to the public; (d) adaptation, modification and "
                          "combination with other data and information"),
        "licence_quote_full": ("EU law grants free access to Copernicus Sentinel Data and "
                               "Service Information for the purpose of the following use in so "
                               "far as it is lawful: (a) reproduction; (b) distribution; (c) "
                               "communication to the public; (d) adaptation, modification and "
                               "combination with other data and information; (e) any "
                               "combination of points (a) to (d)."),
        # The clause that SCOPES the portal's non-commercial sentence away from Sentinel data.
        # Same page, section 3 (Copyrights): the Sentinel-data sentence above comes first and is
        # governed by the Legal Notice; the non-commercial sentence opens with "Any OTHER
        # contents", i.e. everything that is not Sentinel data. Re-fetched 2026-10-06.
        "scope_url": "https://dataspace.copernicus.eu/terms-and-conditions",
        "scope_quote": ("Any other contents of the Copernicus Data Space Ecosystem portal are "
                        "intended for non-commercial use. ESA and T-Systems grant the permission "
                        "to users to visit the site, and to download and copy information, "
                        "images, documents and materials from the web portal for non-commercial "
                        "use."),
        "scope_note": ("section 3 of the T&C splits Sentinel data (free, full and open, governed "
                       "by the Legal Notice, whose permitted uses carry no non-commercial "
                       "limit) from 'Any other contents of the ... portal' (non-commercial). "
                       "The forum no-automation clause covers the forum only; quotas must not "
                       "be bypassed with multiple accounts (one account is used). Both pages "
                       "were read through a fetch tool that renders the page for a reader "
                       "(this container cannot reach the host directly); the quotes were "
                       "requested character-for-character and agree across fetches"),
        # ATTRIBUTION DUTY (audit of #218, 2026-10-06). The Legal Notice's permission comes with
        # a notice obligation: whoever communicates or distributes the data names its source,
        # and an adapted or modified product carries the "Contains modified" form. The desk
        # derives series from what it fetches, so every record the CDSE token path produces
        # carries `attribution()` -- the modified form with the year filled in.
        "attribution": "Contains modified Copernicus Sentinel data {year}",
        "attribution_unmodified": "Copernicus Sentinel data {year}",
        "attribution_url": ("https://sentinels.copernicus.eu/documents/247904/690755/"
                            "Sentinel_Data_Legal_Notice"),
        "attribution_quote": ("Where the user communicates to the public or distributes "
                              "Copernicus Sentinel Data and Service Information, he/she shall "
                              "inform the recipients of the source of that Data and Information "
                              "by using the following notice ... Where the Copernicus Sentinel "
                              "Data and Service Information have been adapted or modified, the "
                              "user shall provide the following notice: (1) 'Contains modified "
                              "Copernicus Sentinel data [Year]'"),
        "checked_at": _TERMS_CHK},
    "myfxbook": {
        "terms_url": "https://www.myfxbook.com/api",
        "terms_quote": ("The API allows access to personal information only. ... By using the "
                        "Myfxbook API, you agree to the Terms of use."),
        "licence_url": "https://www.myfxbook.com/terms",
        "licence_quote": "Reproduction is prohibited by law.",
        "scope_note": ("no clause permits automated or commercial use of the community outlook "
                       "by a trading desk; stays BLOCKED_ON_TERMS until a written permission "
                       "is recorded here"),
        "checked_at": _TERMS_CHK},
    "jquants": {
        "terms_url": "https://jpx-jquants.com/termsofservice",
        "terms_quote": ("第8条(利用目的) 本サービス及び本データの利用目的(以下「本利用目的」といい"
                        "ます。)は、登録ユーザーのみによる私的使用の目的に限ります。"),
        "licence_url": "https://jpx-jquants.com/termsofservice",
        "licence_quote": ("本サービス及び本データ(本データを編集又は加工したものを含みます。)を、"
                          "第三者が使用できる状態にすること(インターネット上での配信を含みます。)"
                          "または商用もしくは学術の目的で利用することは、私的使用の目的に該当"
                          "しません。"),
        "definition_quote": ("登録ユーザー: 第3条(登録)に基づいて本サービスの利用者としての登録が"
                             "なされた個人"),
        # THE PERMITTING CLAUSE (audit of #218, 2026-10-07). Art. 8 confines use to "private
        # use"; the provider's own usage page says what private use IS, and that page is the
        # clause that permits this desk's use: the registered individual's own investment
        # analysis and portfolio management. Fetched 2026-10-07 through a fetch tool that renders
        # the page for a reader (the host is not reachable from this container directly); the
        # sentences were requested character for character and agree across two fetches. The
        # conditions that come with it are recorded as structured fields in TERMS_CONDITIONS.
        "permitting_url": "https://jpx-jquants.com/en/help/usage",
        "permitting_quote": ("Private use refers to utilizing this data for one's own "
                             "investment analysis, portfolio management, etc."),
        "permitting_quote_source": "fetched_2026-10-07",
        "conditions": "TERMS_CONDITIONS['jquants']",
        # THE PRINCIPAL'S APPROVAL (2026-10-06), with the question it answered. The coordinator's
        # post of 2026-10-06 asked whether the desk's J-Quants use is private use by the
        # registered individual (the art. 8 question); the principal answered in the message
        # below. The question is recorded as the coordinator's brief states it (a paraphrase of
        # that post, not its verbatim text); the answer is verbatim.
        "principal_question": ("Is the desk's use of J-Quants private use by the registered "
                               "individual (J-Quants Terms of Service art. 8: use limited to "
                               "the registered user's own private use)?"),
        "principal_question_source": "coordinator post 2026-10-06, as paraphrased in the brief",
        "principal_answer": "no run the current youtube key doesnt matter and yes fr j quants",
        "principal_answer_part": "yes fr j quants",
        "principal_answered_by": "zuck",
        "principal_message_id": "cmsg_012XFUfE12Rvggnu86fDb8pr9aLZ8EJUKTqaxiniyhzvSK",
        "principal_answered_at": "2026-10-06T21:11:56Z",
        "principal_basis": ("the desk trades only the principal's own money, so its use is "
                            "private use by the registered individual under art. 8"),
        "condition": ("PRIVATE USE ONLY: no redistribution, no sharing. The repository is "
                      "public, so no J-Quants value, derived value, cached response or cell may "
                      "be committed to git, written to a report that syncs to git, printed to a "
                      "leg's stdout (hourly_cycle keeps each leg's stdout tail in the tracked "
                      "sync_marker.json), or put in anything shared. Records carry "
                      "private_use=True and lineage 'jquants_private'; the collector writes "
                      "them only under the gitignored desks/mt5/data/lake/private_use/ and its "
                      "tracked-path-safe report and summary keep counts and status only. "
                      "Cells of this lineage are e8_ineligible: E8 trades the prop firm's "
                      "capital, which is not the registered individual's own money"),
        "checked_at": _TERMS_CHK},
}

#: THE CONDITIONS A PRIVATE-USE PERMISSION COMES WITH, as structured fields a test and a consumer
#: can read (audit of #218, 2026-10-07). Each is quoted from the provider's usage page
#: (https://jpx-jquants.com/en/help/usage, fetched 2026-10-07; same fetch caveat as above).
TERMS_CONDITIONS: dict[str, dict[str, Any]] = {
    "jquants": {
        "source_url": "https://jpx-jquants.com/en/help/usage",
        "quote_source": "fetched_2026-10-07",
        "permitted_purpose": ("own investment analysis, portfolio management (private use by "
                              "the registered individual)"),
        "corporate_use_permitted": False,
        "corporate_use_quote": ("No. Even for internal-only, non-profit purposes, corporations "
                                "cannot use J-Quants API."),
        "raw_redistribution_permitted": False,
        "raw_redistribution_quote": ("Distributing or sharing raw data directly is prohibited, "
                                     "but sharing analysis results (charts, graphs, reports, "
                                     "etc.) is permitted."),
        "ai_use": {
            "permitted_only_if": [
                "the inputs are used for one's own analysis",
                "the AI is configured so that the input data is not reused for training",
                "the input data is not viewable by third parties",
                "the generated results are not distributed or published",
            ],
            "quote": ("The AI is configured so that the input data is not reused for training "
                      "... The generated results are not distributed or published"),
        },
        "repeated_publishing_is_personal_use": False,
        "repeated_publishing_quote": ("continuously and repeatedly publishing analysis results "
                                      "is not considered personal use"),
        "delete_on_cancellation": True,
        "delete_on_cancellation_quote": ("after you cancel your subscription or withdraw from "
                                         "the service, you must delete all data you acquired up "
                                         "to that point, together with any copies and any "
                                         "derivatives from which the original data can be "
                                         "reconstructed"),
        "delete_scope": "desks/mt5/data/lake/private_use/ and data/secrets/token_cache/",
        #: How the desk honours them: nothing to git, nothing printed, nothing to a shared
        #: report or an LLM seat's input; lineage-tagged cells never reach E8 (prop capital).
        "lineage": "jquants_private",
        "e8_eligible": False,
    },
}


def terms_ok(p: Provider) -> bool:
    """True only when the provider's terms are recorded as confirmed WITH evidence.

    FAIL CLOSED: a provider absent from `TERMS` is not ok (BLOCKED_ON_TERMS) -- an unlisted
    provider is an unchecked one, never a permitted one."""
    verdict = TERMS.get(p.name)
    if verdict is None or verdict[0] not in PERMITTED_VERDICTS or p.name not in TERMS_EVIDENCE:
        return False
    # A private-use permission is only a permission together with its recorded condition and
    # its structured conditions (TERMS_CONDITIONS).
    return verdict[0] != PRIVATE_USE or (bool(TERMS_EVIDENCE[p.name].get("condition"))
                                         and bool(TERMS_CONDITIONS.get(p.name)))


def private_use(env_or_name: str) -> bool:
    """True when the provider's data is permitted for PRIVATE USE ONLY: nothing from it, or
    derived from it, may reach git or any shared output."""
    p = PROVIDERS.get(env_or_name)
    name = p.name if p is not None else str(env_or_name)
    return TERMS.get(name, ("", ""))[0] == PRIVATE_USE


#: THE LINEAGE TAG on every record and cell derived from a private-use source (J-Quants). A cell
#: carrying it is `e8_ineligible`: E8 trades the prop firm's capital, which is not the
#: registered individual's own money (coordinator ruling, 2026-10-07). Fusion is the
#: individual's own account and is unaffected.
PRIVATE_LINEAGE = "jquants_private"
E8_INELIGIBLE = "e8_ineligible"


def mark_private_lineage(rec: dict[str, Any]) -> dict[str, Any]:
    """Tag a record or cell derived from private-use data, in place, and return it."""
    rec["lineage"] = PRIVATE_LINEAGE
    rec["private_use"] = True
    rec[E8_INELIGIBLE] = True
    return rec


def has_private_lineage(obj: Any, _depth: int = 0) -> bool:
    """True when a record, a cell, or anything nested in it (a spec, a parent, a candidate's
    source list) carries the private lineage, `private_use=True` or `e8_ineligible=True`.
    A consumer that must keep private-lineage candidates out (the E8 book) calls this on the
    whole candidate; it reads every nesting level up to a bound, so a tag on the spec counts."""
    if _depth > 6:
        return False
    if isinstance(obj, dict):
        if (obj.get("lineage") == PRIVATE_LINEAGE or obj.get(E8_INELIGIBLE) is True
                or obj.get("private_use") is True):
            return True
        return any(has_private_lineage(v, _depth + 1) for v in obj.values()
                   if isinstance(v, (dict, list, tuple)))
    if isinstance(obj, (list, tuple)):
        return any(has_private_lineage(v, _depth + 1) for v in obj
                   if isinstance(v, (dict, list, tuple)) or v == PRIVATE_LINEAGE)
    return bool(obj == PRIVATE_LINEAGE)


def attribution(env_or_name: str, year: int | None = None) -> str:
    """The source notice a provider's licence requires on anything derived from its data, with
    the year filled in (default: the current UTC year), or "" when the provider records none.
    Accepts the short-lived env var (`CDSE_TOKEN`) or the provider name (`cdse`)."""
    p = PROVIDERS.get(env_or_name)
    name = p.name if p is not None else str(env_or_name)
    template = TERMS_EVIDENCE.get(name, {}).get("attribution", "")
    if not template:
        return ""
    if year is None:
        year = time.gmtime().tm_year
    return template.format(year=int(year))


def collector_status(res: TokenResult) -> str:
    """The status a reader records for this result. UNCONFIGURED only for an absent credential;
    a refresh the provider refused is BLOCKED_AUTH; the terms fence is BLOCKED_ON_TERMS."""
    if res.ok:
        return OK
    return {BLOCKED_ON_KEY: UNCONFIGURED, REFRESH_FAILED: BLOCKED_AUTH,
            BLOCKED_ON_TERMS: BLOCKED_ON_TERMS}.get(res.status, BLOCKED_AUTH)


# ---------------------------------------------------------------------------------------------
# credential source: read_key (#201), never os.environ directly
# ---------------------------------------------------------------------------------------------

def _read_key(name: str) -> str:
    from libs.ops.env_keys import read_key
    return read_key(name)


class KeySource(Mapping[str, str]):
    """A read-only mapping that looks each credential up through `read_key` (machine registry,
    user registry, process env). Not enumerable: it answers only the names it is asked for."""

    def __getitem__(self, name: str) -> str:
        value = _read_key(name)
        if not value:
            raise KeyError(name)
        return value

    def __iter__(self) -> Iterator[str]:
        return iter(())

    def __len__(self) -> int:
        return 0


# ---------------------------------------------------------------------------------------------
# URL credential stripping
# ---------------------------------------------------------------------------------------------

#: Query parameter names that carry a credential. Their values never reach a record.
CREDENTIAL_PARAMS = ("password", "passwd", "pass", "pwd", "email", "mailaddress", "session",
                     "token", "access_token", "id_token", "idtoken", "refresh_token",
                     "refreshtoken", "api_key", "apikey", "key", "client_secret", "secret",
                     "authkey", "auth")
_CRED_QS = re.compile(r"(?i)(?<![A-Za-z0-9_])(" + "|".join(CREDENTIAL_PARAMS)
                      + r")=([^&\s'\"<>#]*)")
_USERINFO = re.compile(r"(?i)(https?://)[^/\s@'\"]+@")


def strip_url_credentials(text: str) -> str:
    """`text` (a URL, or free text quoting one) with userinfo and every credential-named query
    value replaced by `<redacted>`. Other parameters are kept, so the record still names the
    resource."""
    out = _USERINFO.sub(r"\1<redacted>@", str(text))
    return _CRED_QS.sub(r"\1=<redacted>", out)


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
    attribution: str = ""       #: the licence's source notice, when the provider requires one
    private_use: bool = False   #: data permitted for private use only: never to git or shared

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
    """Remove every managed secret value (configured or cached) from `text`, then every
    credential a quoted URL carries in its query string or userinfo. Scrub BEFORE truncating."""
    e = KeySource() if env is None else env
    secrets: list[str] = []
    for p in PROVIDERS.values():
        secrets.append(e.get(p.short_env, ""))
        for group in p.long_envs:
            secrets.extend(e.get(k, "") for k in group)
        c = _read_cache(p)
        secrets.extend(str(c.get(k) or "") for k in ("token", "refresh_token"))
    for s in sorted({s for s in secrets if len(s) >= 4}, key=len, reverse=True):
        text = text.replace(s, "<redacted>")
        for q in {urllib.parse.quote(s, safe=""), urllib.parse.quote_plus(s, safe="")}:
            if q != s:
                text = text.replace(q, "<redacted>")
    return strip_url_credentials(text)


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
    t = time.time() if now is None else now
    try:
        res = _get_token(env, KeySource() if environ is None else environ, timeout, t)
    except Exception as exc:  # the contract is "never raises into callers"
        res = TokenResult(REFRESH_FAILED, env, detail=f"internal {type(exc).__name__}")
    note = attribution(env, time.gmtime(t).tm_year)
    if note:
        res = dataclasses.replace(res, attribution=note)
    if private_use(env):
        res = dataclasses.replace(res, private_use=True)
    return res


def _get_token(env: str, e: Mapping[str, str], timeout: float, now: float) -> TokenResult:
    p = PROVIDERS.get(env)
    if p is None:
        val = e.get(env, "")
        return (TokenResult(OK, env, token=val, source="env") if val
                else TokenResult(BLOCKED_ON_KEY, env, detail=f"{env} is not set"))

    if not terms_ok(p):
        # FAIL CLOSED: no login, no mint and no pasted token goes anywhere until the provider's
        # terms are recorded as confirmed. Nothing is read from the credential store either.
        verdict = TERMS.get(p.name, ("to_confirm", ""))[0]
        detail = (f"{p.name} terms are {verdict}, not confirmed: no credential is sent "
                  f"(evidence: libs/ops/token_refresh.TERMS_EVIDENCE['{p.name}'])")
        return TokenResult(BLOCKED_ON_TERMS, env, apply=p.apply, detail=detail)

    if p.name == "jquants":
        # J-Quants V2: the long-lived API key IS the credential, sent as `x-api-key` to
        # https://api.jquants.com/v2/... A pasted JQUANTS_TOKEN that is not a JWT is the same
        # kind of key (the catalog lists it as JQUANTS_API_KEY's alias); a JWT is a V1 idToken.
        key = e.get("JQUANTS_API_KEY", "")
        if key:
            return TokenResult(OK, env, token=key, source="api_key", apply="x-api-key")
    pasted = e.get(p.short_env, "")
    if pasted:
        exp = jwt_exp(pasted)
        if p.name == "jquants" and exp is None:
            return TokenResult(OK, env, token=pasted, source="env", apply="x-api-key")
        if _fresh(exp, now):
            return TokenResult(OK, env, token=pasted, source="env", apply=p.apply,
                               expires_at=exp)

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
    e = KeySource() if environ is None else environ
    rows = []
    for p in PROVIDERS.values():
        c = _read_cache(p)
        group = _long_lived(p, e)
        last = str(c.get("last_status") or "NEVER_ATTEMPTED")
        short = bool(e.get(p.short_env))
        if not terms_ok(p):
            status = BLOCKED_ON_TERMS
        elif last == REFRESH_FAILED:
            status = BLOCKED_AUTH      # configured, and the provider refused the refresh
        elif group is None and not short and not c.get("token"):
            status = UNCONFIGURED      # truly absent: nothing set, nothing cached
        else:
            status = OK
        rows.append({
            "env": p.short_env, "provider": p.name, "status": status,
            "terms": TERMS.get(p.name, ("unlisted", ""))[0],
            "short_lived_env_set": short,
            "long_lived_present": group is not None,
            "long_lived_set": "+".join(group) if group else "",
            "long_lived_options": ["+".join(g) for g in p.long_envs],
            "cached_token": bool(c.get("token")),
            "cached_expires_at": c.get("expires_at"),
            "last_status": last,
            "last_http": c.get("last_http"),
            "last_attempt_at": c.get("last_attempt_at"),
            "last_detail": str(c.get("last_detail") or ""),
            "docs": p.docs,
            "attribution": attribution(p.name),
            "private_use": private_use(p.name),
        })
    return rows


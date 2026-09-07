"""S3-compatible object storage over HTTPS, signed with stdlib. No boto3, no new dependency.

WHY THE DESK NEEDS THIS AT ALL. The tick tape is the one dataset here that cannot be re-obtained
-- broker-native ticks nobody else holds -- and it is also the one that grows without limit on a
disk that must simultaneously hold a git checkout, a 21-chart bar lake and a gauntlet cache.
Every attempt to solve that locally has been a choice about which irreplaceable or expensive
thing to sacrifice. It is not a local problem and it does not have a local answer: 5.66 GB today
at roughly 0.2-0.5 GB a day, on an 80 GB disk shared with everything else, is a deadline.

Object storage removes the deadline rather than moving it. At ~$0.015/GB/month the entire tape
costs under ten cents a month and a hundred gigabytes costs about a dollar fifty, and no machine
on this desk ever has to hold it again. The box already reaches the internet over HTTPS -- it
pushes to GitHub every fifteen minutes -- so this needs no new network path, no second host to
keep alive, and no VPS whose disk becomes the next thing to fill up.

NO boto3. The box runs Python 3.14 with pandas and pyarrow and neither boto3 nor botocore, and a
storage layer that must be pip-installed before an emergency is a storage layer that is not there
during one. SigV4 is an HMAC chain over a canonical string; it is implemented here in about sixty
lines against `requests`, which IS present, and it speaks to Cloudflare R2, Backblaze B2, AWS S3,
Wasabi, MinIO or anything else with an S3 endpoint.

CREDENTIALS NEVER APPEAR IN OUTPUT. They are read from the environment or from
`data/secrets/tape_archive.json` -- the directory this desk already keeps out of git -- and no
function here returns, logs, or formats a secret into an error. `describe()` exists so a caller
can report the configuration WITHOUT the caller having to touch the values.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

_SECRETS = Path(__file__).resolve().parent.parent / "data" / "secrets" / "tape_archive.json"

#: Environment names, checked before the secrets file so a one-off run can override a box's
#: standing configuration without editing it.
ENV = {"endpoint": "TAPE_ARCHIVE_ENDPOINT", "key_id": "TAPE_ARCHIVE_KEY_ID",
       "secret": "TAPE_ARCHIVE_SECRET", "region": "TAPE_ARCHIVE_REGION",
       "bucket": "TAPE_ARCHIVE_BUCKET"}

_UNSIGNED = "UNSIGNED-PAYLOAD"


@dataclass(frozen=True)
class Config:
    endpoint: str          # https://<account>.r2.cloudflarestorage.com  (no bucket, no trailing /)
    key_id: str
    secret: str
    bucket: str
    region: str = "auto"   # R2 wants "auto"; S3 wants the bucket's real region

    def describe(self) -> str:
        """Safe to print: endpoint, bucket, region and the key's first four characters only."""
        return (f"{self.endpoint} bucket={self.bucket} region={self.region} "
                f"key={self.key_id[:4]}...")


def load(root: Path | None = None) -> tuple[Config | None, str]:
    """Configuration from the environment, then data/secrets/tape_archive.json. Never raises.

    Returns (None, reason) when unconfigured -- an absent bucket is a state to report, not an
    error to crash on, because the archiver must still be able to MEASURE on a box that has no
    storage set up yet.
    """
    vals: dict[str, str] = {}
    for field, env in ENV.items():
        v = os.environ.get(env)
        if v:
            vals[field] = v.strip()
    path = _SECRETS if root is None else Path(root) / "data" / "secrets" / "tape_archive.json"
    if path.exists():
        try:
            doc = json.loads(path.read_text("utf-8"))
            if isinstance(doc, dict):
                for field in ENV:
                    if field not in vals and doc.get(field):
                        vals[field] = str(doc[field]).strip()
        except (OSError, ValueError) as exc:
            return None, f"{path.name} is unreadable ({type(exc).__name__})"
    missing = [f for f in ("endpoint", "key_id", "secret", "bucket") if not vals.get(f)]
    if missing:
        return None, (f"not configured: missing {missing}. Set {[ENV[m] for m in missing]} or "
                      f"write data/secrets/tape_archive.json")
    return Config(endpoint=vals["endpoint"].rstrip("/"), key_id=vals["key_id"],
                  secret=vals["secret"], bucket=vals["bucket"],
                  region=vals.get("region") or "auto"), "configured"


def _sign_key(secret: str, date: str, region: str, service: str) -> bytes:
    k = ("AWS4" + secret).encode()
    for part in (date, region, service, "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    return k


def _signed_headers(cfg: Config, method: str, key: str, payload_sha: str,
                    extra: dict[str, str] | None = None,
                    now: _dt.datetime | None = None) -> tuple[str, dict[str, str]]:
    """(url, headers) for one SigV4-signed request against `cfg`.

    PATH-STYLE (`/bucket/key`), which every S3-compatible endpoint accepts and which avoids the
    DNS and TLS-SAN problems virtual-host style creates on non-AWS providers and on any bucket
    whose name contains a dot.
    """
    from urllib.parse import urlparse
    t = now or _dt.datetime.now(_dt.UTC)
    amz_date = t.strftime("%Y%m%dT%H%M%SZ")
    date = t.strftime("%Y%m%d")
    host = urlparse(cfg.endpoint).netloc
    # Each path segment is escaped, but the separators are not: an object key legitimately
    # contains slashes and encoding them would address a different object.
    canon_uri = "/" + quote(cfg.bucket, safe="") + "/" + "/".join(
        quote(seg, safe="~") for seg in key.split("/"))
    headers = {"host": host, "x-amz-content-sha256": payload_sha, "x-amz-date": amz_date}
    headers.update({k.lower(): v for k, v in (extra or {}).items()})
    signed = ";".join(sorted(headers))
    canon_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    canon_req = f"{method}\n{canon_uri}\n\n{canon_headers}\n{signed}\n{payload_sha}"
    scope = f"{date}/{cfg.region}/s3/aws4_request"
    to_sign = ("AWS4-HMAC-SHA256\n" + amz_date + "\n" + scope + "\n"
               + hashlib.sha256(canon_req.encode()).hexdigest())
    sig = hmac.new(_sign_key(cfg.secret, date, cfg.region, "s3"),
                   to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={cfg.key_id}/{scope}, "
                                f"SignedHeaders={signed}, Signature={sig}")
    return cfg.endpoint + canon_uri, headers


def put(cfg: Config, key: str, data: bytes, timeout: float = 300.0) -> tuple[bool, str]:
    """Upload `data` to `key`. Returns (ok, detail). Never raises, never echoes a credential."""
    import requests
    url, headers = _signed_headers(cfg, "PUT", key, hashlib.sha256(data).hexdigest(),
                                   {"content-length": str(len(data)),
                                    "content-type": "application/octet-stream"})
    try:
        r = requests.put(url, data=data, headers=headers, timeout=timeout)
    except Exception as exc:                                   # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    if r.status_code // 100 != 2:
        # The provider's body names the real cause (SignatureDoesNotMatch, NoSuchBucket,
        # AccessDenied) and never contains our secret; the request headers would, so they are
        # deliberately not included here.
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    return True, (r.headers.get("ETag") or "").strip('"')


def head(cfg: Config, key: str, timeout: float = 60.0) -> tuple[int | None, str | None, str]:
    """(size, etag, detail) for an object, or (None, None, why). 404 is a clean 'absent'."""
    import requests
    url, headers = _signed_headers(cfg, "HEAD", key, _UNSIGNED)
    try:
        r = requests.head(url, headers=headers, timeout=timeout)
    except Exception as exc:                                   # noqa: BLE001
        return None, None, f"{type(exc).__name__}: {exc}"
    if r.status_code == 404:
        return None, None, "absent"
    if r.status_code // 100 != 2:
        return None, None, f"HTTP {r.status_code}"
    try:
        size = int(r.headers.get("Content-Length", ""))
    except ValueError:
        size = None
    return size, (r.headers.get("ETag") or "").strip('"'), "present"


def verify(cfg: Config, key: str, data: bytes) -> tuple[bool, str]:
    """Prove the stored object IS these bytes, without downloading them again.

    A single-part PUT's ETag is the MD5 of the body -- that is the S3 contract and every
    compatible provider honours it -- so comparing the ETag and the length together is a
    end-to-end check of content and size for the price of one HEAD. Multipart uploads break that
    equivalence (their ETag carries a `-N` suffix); this module never multiparts, and an ETag
    carrying a dash is therefore reported as unverifiable rather than quietly accepted.
    """
    size, etag, why = head(cfg, key)
    if size is None:
        return False, f"cannot read back: {why}"
    if size != len(data):
        return False, f"size mismatch: stored {size}, sent {len(data)}"
    if not etag:
        return False, "no ETag returned; cannot prove content"
    if "-" in etag:
        return False, f"multipart ETag {etag}: content not provable by ETag"
    if etag.lower() != hashlib.md5(data).hexdigest():           # noqa: S324 - S3's ETag is MD5
        return False, "ETag does not match the bytes sent"
    return True, "verified by size and ETag"

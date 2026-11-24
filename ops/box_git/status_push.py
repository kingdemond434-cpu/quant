"""THE STATUS PUSH: the box publishes its own desk status off-box, hourly, with no Claude session.

WHY (Desk health B13, 11-24): when the box's Claude link went down on 11-21 nobody off the box
could see whether E8, FTMO and Fusion traded, their equity, or whether the release loop was
moving. The daily "did every account trade" check must not depend on that link.

  * ONE-WAY, ALLOW-LISTED: only the JSON reports named in loop.json "status.files" (relative to
    the desk root) are published, each scrubbed of any key that names a credential or an account
    identity (`SCRUB`), plus a small summary (disk free, the loop's last row, file ages). Nothing
    else on the box is read for publishing. A file over MAX_FILE is replaced by a note.
  * A SEPARATE PRIVATE PROJECT AND KEY (Audit MF-2): the box pushes with its own status key to
    a status-only GitLab project, never to the drop project (whose CLEAR binds "box key =
    read-only"). `from_config` and the installer refuse a status url equal to the drop url. The
    status project holds equity and positions: it stays private and is never mirrored.
  * The branch carries one commit (an orphan, force-pushed each time): history lives in the
    reports themselves, not in an ever-growing repository.
  * Never raises into the loop; a failed push says why and the next pass tries again.
"""
from __future__ import annotations

import ipaddress
import json
import re
import shutil
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if str(Path(__file__).resolve().parents[2]) not in sys.path:   # run as a script by its task
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ops.box_git import drop_pull

SCRUB = re.compile(r"(?i)pass|token|secret|api_?key|private|hmac|cookie|auth|login|server"
                   r"|account_?(?:id|no|number)|email|phone|address|iban|wallet|host|\bip\b"
                   r"|^ip_|_ip$|endpoint|url|path|terminal")
#: Value pass (Audit MF-1): an IP literal anywhere in a string is redacted, and an `account`
#: value is replaced by "[id]" unless it is a short desk label (E8, FTMO, Fusion ...).
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
#: IPv6 candidates are checked with `ipaddress`, so a clock time ("17:10:08") never matches.
_IPV6 = re.compile(r"(?<![\w:.])[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?![\w:])")
_LABEL = re.compile(r"(?!.*\d{3})[A-Za-z][A-Za-z0-9_-]{0,15}")   # E8, FTMO-2; never a login
_ACCOUNT_KEY = re.compile(r"(?i)^account$|^acct$|^account_name$")
MAX_FILE = 2 * 1024 * 1024
STATUS_BRANCH = "status"
EVERY_S = 3600
STAMP = "status_push_last.json"

Run = Callable[[Sequence[str]], tuple[int, str]]


@dataclass(frozen=True)
class Status:
    url: str                    # git@gitlab.com:<owner>/<status-only project>.git
    key: Path                   # the box's status WRITE key (not the drop's read-only key)
    checkout: Path              # scratch folder, rebuilt each push
    root: Path                  # the desk tree the files are read from (C:\opt\quant)
    files: tuple[str, ...] = field(default_factory=tuple)
    host_key: str = drop_pull.GITLAB_HOST_KEY

    def drop(self) -> drop_pull.Drop:
        return drop_pull.Drop(url=self.url, key=self.key, checkout=self.checkout,
                              branch=STATUS_BRANCH, host_key=self.host_key)


def _v6(m: re.Match[str]) -> str:
    try:
        ipaddress.IPv6Address(m.group(0))
    except ValueError:
        return m.group(0)
    return "[ip]"


def _redact(s: str) -> str:
    return _IPV6.sub(_v6, _IPV4.sub("[ip]", s))


def _norm(url: str) -> str:
    return url.strip().lower().removesuffix(".git").rstrip("/")


def scrub(obj: Any) -> Any:
    """Drop every key that names a credential, an identity or a location; redact IP literals in
    every string; keep an `account` value only when it is a short desk label. Pure."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if SCRUB.search(str(k)):
                continue
            if _ACCOUNT_KEY.search(str(k)):
                out[_redact(str(k))] = (v if isinstance(v, str) and _LABEL.fullmatch(v)
                                        else "[id]")
                continue
            out[_redact(str(k))] = scrub(v)
        return out
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, str):
        return _redact(obj)
    return obj


def _safe_rel(rel: str) -> bool:
    return (bool(rel) and not rel.startswith(("/", "\\")) and ".." not in rel.replace("\\", "/")
            .split("/") and ":" not in rel and rel.endswith(".json"))


def collect(st: Status, now: datetime, extra: dict[str, Any] | None = None
            ) -> dict[str, Any]:
    """{published name: content} for every allow-listed file, plus the summary. Pure reads."""
    out: dict[str, Any] = {}
    ages: dict[str, float | None] = {}
    for rel in st.files:
        if not _safe_rel(rel):
            continue
        p = st.root / rel
        name = rel.replace("\\", "/").replace("/", "__")
        try:
            size = p.stat().st_size
            ages[rel] = round((now.timestamp() - p.stat().st_mtime) / 3600.0, 2)
            if size > MAX_FILE:
                out[name] = {"omitted": f"{size} bytes over the {MAX_FILE} cap"}
                continue
            out[name] = scrub(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            ages.setdefault(rel, None)
            out[name] = {"unreadable": type(exc).__name__}
    try:
        free_gb = round(shutil.disk_usage(st.root).free / 1024 ** 3, 1)
    except OSError:
        free_gb = None
    out["SUMMARY.json"] = scrub({"generated_utc": now.isoformat(timespec="seconds"),
                                 "disk_free_gb": free_gb, "file_age_h": ages, **(extra or {})})
    return out


def due(state_dir: Path, now: datetime) -> bool:
    try:
        last = json.loads((state_dir / STAMP).read_text(encoding="utf-8")).get("at")
        return now.timestamp() - datetime.fromisoformat(last).timestamp() >= EVERY_S
    except (OSError, ValueError, TypeError, AttributeError):
        return True


def push(st: Status, state_dir: Path, now: datetime | None = None,
         extra: dict[str, Any] | None = None, run: Run = drop_pull._run) -> str:
    now = now or datetime.now(UTC)
    if not due(state_dir, now):
        return "status: not due"
    d = st.drop()
    kh = d.known_hosts()
    if not kh.is_file() or kh.read_text(encoding="utf-8").strip() != d.host_key:
        kh.write_text(d.host_key + "\n", encoding="utf-8")
    shutil.rmtree(st.checkout, ignore_errors=True)
    st.checkout.mkdir(parents=True, exist_ok=True)
    for name, doc in collect(st, now, extra).items():
        (st.checkout / name).write_text(json.dumps(doc, indent=1, sort_keys=True, default=str),
                                        encoding="utf-8")
    g = ["git", "-C", str(st.checkout), "-c", "safe.directory=*", "-c", "user.name=quant-box",
         "-c", "user.email=box@localhost", "-c", f"core.sshCommand={d.ssh()}"]
    for args in (["init", "-q"], ["checkout", "-q", "--orphan", STATUS_BRANCH], ["add", "-A"],
                 ["commit", "-q", "-m", f"box status {now.isoformat(timespec='minutes')}"],
                 ["push", "-q", "--force", st.url, f"HEAD:refs/heads/{STATUS_BRANCH}"]):
        rc, out = run([*g, *args])
        if rc != 0:
            return f"status not pushed ({args[0]}: {out.strip()[-200:]})"
    tmp = state_dir / (STAMP + ".part")
    tmp.write_text(json.dumps({"at": now.isoformat(timespec="seconds")}), encoding="utf-8")
    tmp.replace(state_dir / STAMP)
    return f"status pushed ({len(st.files)} file(s))"


def from_config(path: Path) -> tuple[Status, Path]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    s = raw["status"]
    drop_url = str((raw.get("drop") or {}).get("url") or "")
    if _norm(s["url"]) == _norm(drop_url):
        raise ValueError("status url equals the drop url: the box never writes to the drop")
    return (Status(url=s["url"], key=Path(s["key"]), checkout=Path(s["checkout"]),
                   root=Path(s["root"]), files=tuple(str(f) for f in s.get("files") or ())),
            Path(raw["state"]).parent)


def main(argv: list[str] | None = None) -> int:
    """Run by its own hourly task (QuantForge-Status), independent of the release loop, so a
    stuck loop shows up off-box as a stale `loop` row rather than as silence."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, help="the forge's loop.json")
    a = ap.parse_args(argv)
    st, state_dir = from_config(Path(a.config))
    try:
        loop = json.loads((state_dir / "LOOP_LAST.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        loop = {"unreadable": True}
    print(push(st, state_dir, extra={"loop_last": {k: str(v)[:300] for k, v in loop.items()}}
               if isinstance(loop, dict) else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

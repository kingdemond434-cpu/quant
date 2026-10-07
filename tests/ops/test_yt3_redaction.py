"""desks/mt5/scripts/test_yt3.py never prints the YouTube key a requests error carries.

A requests exception's text is the full URL, query string included, so `print(f"... {e}")`
printed `key=<the key>`. Every line the probe prints now goes through scrub_text plus a regex
that strips the `key=` query parameter, both here and in the code it runs on the VPS.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "desks" / "mt5" / "scripts" / "test_yt3.py"
FAKE = "AI" + "za" + "Zq7" * 11 + "Zq"           # Google shape, built at runtime
PLAIN = "plain" + "token" + "4242"                 # a key= value of no vendor shape


class _Probe:
    def __init__(self, ns: dict[str, Any]) -> None:
        self._redact = ns["_redact"]
        self.code: str = ns["code"]


def _probe() -> _Probe:
    """The probe's definitions, without running it: everything above its first ssh call.

    The script stays a plain top-level probe (no __main__ guard, so it is not an executable
    that owes a clock); executing its prefix is how the redaction is tested without ssh."""
    src = PROBE.read_text("utf-8")
    head = src[:src.index("\nproc = subprocess.run(")]
    ns: dict[str, Any] = {"__file__": str(PROBE), "__name__": "yt3_probe"}
    exec(compile(head, str(PROBE), "exec"), ns)  # the probe's own text, no input
    return _Probe(ns)


def test_the_local_printer_redacts_the_key_parameter() -> None:
    probe = _probe()
    err = (f"HTTPSConnectionPool(host='www.googleapis.com'): /youtube/v3/search?part=snippet"
           f"&key={FAKE}&q=gold (Caused by ReadTimeout)")
    out = probe._redact(err)
    assert FAKE not in out and "key=[REDACTED]" in out and "q=gold" in out
    assert PLAIN not in probe._redact(f"GET /v3/search?key={PLAIN} failed")


def test_the_code_run_on_the_vps_redacts_too() -> None:
    probe = _probe()
    head = probe.code.split("from youtube_miner import")[0]
    ns: dict[str, object] = {}
    exec(compile(head, "test_yt3_remote", "exec"), ns)  # the probe's own text, no input
    redact = ns["_redact"]
    assert callable(redact)
    out = redact(f"exception: 400 Client Error for url: https://x.test/search?key={PLAIN}&q=1")
    assert PLAIN not in out and "key=[REDACTED]" in out
    assert FAKE not in redact(f"message: bad key {FAKE}")
    assert 'print(f"exception: {_redact(e)}")' in probe.code

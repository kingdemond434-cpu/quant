"""The dashboard is served with no token, at the box's own fixed address (principal, 2026-11-18).

zuck was warned that this publishes the live equity, P&L and open positions to anyone who finds the
address, and asked for it twice. What keeps it a read-only page and nothing more is pinned here:
GET and HEAD only, a request that runs nothing, no secret-shaped key in the page's data, and the
supervisor, the task and the installer all starting the same ungated server with no tunnel."""

from __future__ import annotations

import http.client
import importlib.util
import json
import re
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("sd_under_test", ROOT / "scripts/serve_dashboard.py")
assert _spec is not None and _spec.loader is not None
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)


def _code_lines(rel: str) -> str:
    text = (ROOT / rel).read_text(encoding="utf-8-sig")
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


@pytest.fixture
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    (tmp_path / "desk.html").write_text("<p>desk</p>", encoding="utf-8")
    (tmp_path / "zentech_state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sd._Handler, "token", "")
    monkeypatch.setattr(sd._Handler, "require_token", False)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(sd._Handler, directory=str(tmp_path)))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def _call(port: int, method: str, path: str) -> int:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request(method, path)
    code = c.getresponse().status
    c.close()
    return code


def test_the_page_is_served_without_a_key(server: int) -> None:
    assert _call(server, "GET", "/desk.html") == 200
    assert _call(server, "HEAD", "/desk.html") == 200


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_nothing_but_get_and_head_is_answered(server: int, method: str) -> None:
    assert _call(server, method, "/desk.html") == 501


def test_no_path_escapes_the_served_folder(server: int) -> None:
    assert _call(server, "GET", "/../../etc/passwd") in (400, 403, 404)
    assert _call(server, "GET", "/%2e%2e/%2e%2e/etc/passwd") in (400, 403, 404)


def test_a_request_runs_nothing(server: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """The old /zentech_state.json hook ran a build for whoever asked."""

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("a request spawned a process")

    monkeypatch.setattr(sd.subprocess, "run", boom)
    assert _call(server, "GET", "/zentech_state.json") == 200
    assert (
        "subprocess"
        not in _code_lines("scripts/serve_dashboard.py")
        .split("def main")[0]
        .split("class _Handler")[1]
    )


def test_the_handler_defines_no_write_verb() -> None:
    for verb in ("do_POST", "do_PUT", "do_DELETE", "do_PATCH"):
        assert not hasattr(sd._Handler, verb)


def test_the_committed_page_data_carries_no_secret_shaped_key() -> None:
    bad = re.compile(r"login|passw|token|secret|api_?key|account_?(id|ref|number)", re.IGNORECASE)
    found: list[str] = []

    def walk(o: Any, path: str) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if bad.search(str(k)):
                    found.append(f"{path}/{k}")
                walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for v in o:
                walk(v, f"{path}/[]")

    for f in sorted((ROOT / "web").glob("*.json")):
        walk(json.loads(f.read_text(encoding="utf-8")), f.name)
    assert found == [], found


def test_the_task_the_installer_and_the_watchdog_start_the_same_ungated_server() -> None:
    manifest = (ROOT / "desks/mt5/ops/box_tasks.manifest").read_text(encoding="utf-8")
    row = next(ln for ln in manifest.splitlines() if ln.startswith('TASK name="MT5-DeskDashboard"'))
    assert "--no-auth" in row and "--require-token" not in row
    installer = _code_lines("desks/mt5/scripts/install_desk_dashboard_task.ps1")
    assert "--no-auth" in installer and "--require-token" not in installer
    assert "LocalSubnet') + $AllowFrom" in installer and "@('Any')" in installer
    watchdog = _code_lines("scripts/watchdog.py")
    assert '"--port", "8080", "--no-auth"' in watchdog and "--require-token" not in watchdog


def test_the_random_quick_tunnel_is_never_respawned() -> None:
    watchdog = _code_lines("scripts/watchdog.py")
    assert "run_tunnel" not in watchdog and "run_ngrok" not in watchdog
    assert "_spawn([tun]" not in watchdog


def test_no_address_is_written_into_the_repo_files() -> None:
    """The repo is public: the installer finds the address on the box at run time."""
    ip = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
    for rel in ("desks/mt5/scripts/install_desk_dashboard_task.ps1", "scripts/serve_dashboard.py"):
        hits = [
            m for m in ip.findall(_code_lines(rel)) if not m.startswith(("127.", "0.0.0.", "8.8."))
        ]
        assert hits == [], (rel, hits)

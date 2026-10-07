"""DATA-15: fetched content never reaches exec, a command, a chosen path or a protected file.
Each planted violation below must fail the fence; the clean organ must pass it."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_untrusted_content", ROOT / "scripts" / "check_untrusted_content.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


C = _load()

PLANTED = {
    "exec_of_fetched": (
        "import urllib.request\n"
        "def run(url):\n"
        "    body = urllib.request.urlopen(url).read()\n"
        "    exec(body)\n", "FETCHED_TO_EXEC"),
    "shell_from_fetched_via_helper": (
        "import subprocess, urllib.request\n"
        "def _get(u):\n"
        "    with urllib.request.urlopen(u) as r:\n"
        "        return r.read().decode()\n"
        "def run(u):\n"
        "    cmd = _get(u).strip()\n"
        "    subprocess.run(cmd, shell=True)\n", "FETCHED_TO_EXEC"),
    "import_named_by_fetched": (
        "import importlib, requests\n"
        "def run(u):\n"
        "    name = requests.get(u).json()['module']\n"
        "    importlib.import_module(name)\n", "FETCHED_TO_EXEC"),
    "settings_write": (
        "import requests\nfrom pathlib import Path\n"
        "SETTINGS = Path('.claude') / 'settings.json'\n"
        "def run(u):\n"
        "    SETTINGS.write_text(requests.get(u).text)\n", "PROTECTED_PATH_WRITE"),
    "secrets_write_any_data": (
        "import requests, json\n"
        "KEYS = 'desks/mt5/data/secrets/keys.json'\n"
        "def run(u):\n"
        "    requests.get(u)\n"
        "    with open(KEYS, 'w') as fh:\n"
        "        json.dump({}, fh)\n", "PROTECTED_PATH_WRITE"),
    "roster_write": (
        "import requests\n"
        "def _atomic(p, d): pass\n"
        "SLEEVES = 'desks/mt5/data/sleeves.json'\n"
        "def run(u):\n"
        "    _atomic(SLEEVES, requests.get(u).json())\n", "PROTECTED_PATH_WRITE"),
    "fetched_chooses_destination": (
        "import requests\n"
        "def run(u):\n"
        "    doc = requests.get(u).json()\n"
        "    with open(doc['path'], 'w') as fh:\n"
        "        fh.write('x')\n", "FETCHED_CHOOSES_PATH"),
    "chmod_hook": (
        "import os, requests\n"
        "def run(u):\n"
        "    requests.get(u)\n"
        "    os.chmod('ops/githooks/pre-push', 0o777)\n", "PROTECTED_PATH_WRITE"),
}

CLEAN = (
    "import json, re, requests\nfrom pathlib import Path\n"
    "STORE = Path('desks/mt5/data/acquired')\n"
    "def _slug(t):\n    return re.sub(r'[^a-z0-9]+', '_', t.lower())\n"
    "def run(u):\n"
    "    doc = requests.get(u).json()\n"
    "    name = _slug(doc['title'])\n"
    "    (STORE / f'{name}.json').write_text(json.dumps(doc))\n"
    "    for rel, payload in (('reports/A.json', doc), ('reports/B.json', {})):\n"
    "        Path(rel).write_text(json.dumps(payload))\n"
    "    eval('1 + 1')\n"
)


@pytest.mark.parametrize("name", sorted(PLANTED))
def test_planted_violation_is_caught(name: str) -> None:
    src, kind = PLANTED[name]
    found = C.check_source(src, f"{name}.py")
    assert any(f["kind"] == kind and f["severity"] == "breach" for f in found), found


def test_clean_fetch_organ_passes() -> None:
    assert [f for f in C.check_source(CLEAN, "clean.py") if f["severity"] == "breach"] == []


def test_fence_fails_on_a_planted_module_in_a_scanned_root(tmp_path: Path) -> None:
    organ = tmp_path / "desks" / "mt5" / "research"
    organ.mkdir(parents=True)
    (organ / "good.py").write_text(CLEAN)
    assert C.check(tmp_path)["ok"] is True
    (organ / "bad.py").write_text(PLANTED["exec_of_fetched"][0])
    doc = C.check(tmp_path)
    assert doc["ok"] is False and doc["modules_checked"] == 2
    assert {b["file"] for b in doc["breaches"]} == {"desks/mt5/research/bad.py"}
    assert C.main(["--root", str(tmp_path)]) == 1


def test_no_fetch_organ_is_unmeasured_not_a_pass(tmp_path: Path) -> None:
    assert C.main(["--root", str(tmp_path)]) == 2


def test_the_repository_passes_and_the_fence_is_on_the_law_gate() -> None:
    doc = C.check(ROOT)
    assert doc["modules_checked"] > 20 and doc["breaches"] == [], doc["breaches"]
    sys.path.insert(0, str(ROOT))
    from scripts.run_law_gate import _LAW_FENCES
    assert ("check_untrusted_content.py", ()) in _LAW_FENCES

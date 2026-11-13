"""The sign train finds the box's Python instead of demanding a venv the box never had.

MR7 (2026-11-11): Quant-SignTrain failed every 10 minutes with "no desk Python at
C:\\opt\\quant\\.venv\\Scripts\\python.exe"; every other box task runs C:\\Program Files\\Python314.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PS = (ROOT / "ops/box/sign_train_leg.ps1").read_text(encoding="utf-8")


def test_no_hard_venv_default() -> None:
    param = PS.split("param(", 1)[1].split("$ErrorActionPreference", 1)[0]
    assert '[string] $Python = ""' in param
    assert r'$Python = "C:\opt\quant\.venv' not in param


def test_resolves_the_machine_wide_install_the_other_box_tasks_use() -> None:
    body = PS.split("try {", 1)[1]
    venv = body.index(r"C:\opt\quant\.venv\Scripts\python.exe")
    machine = body.index(r"C:\Program Files\Python314\python.exe")
    user = body.index(r"Programs\Python\Python314\python.exe")
    assert venv < machine < user < body.index('throw "no desk Python found')


def test_fails_closed_never_signs_with_whatever_leads_path() -> None:
    assert "Get-Command python" not in PS

"""The lab's local-model box installer (desks/mt5/scripts/install_local_llm.ps1): there is no
PowerShell on the CI runner, so the script's text is the contract (audit must-fix 9 and the
should-fixes SF5-SF7 on 538cb964)."""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))


def test_the_local_model_installer_checks_what_it_runs() -> None:
    """Audit must-fix 9: a pinned version, Authenticode on every binary, models pinned by digest,
    a locked ACL and a LOCAL SERVICE server (no PowerShell here, so the text is the contract)."""
    src = (_DESK / "scripts" / "install_local_llm.ps1").read_text(encoding="utf-8")
    assert "--version $ver" in src and "install.lock.json" in src
    assert src.count("Assert-Signed $") >= 2 and "Get-AuthenticodeSignature" in src
    assert "NT AUTHORITY\\LOCALSERVICE" in src and "-UserId 'SYSTEM'" not in src
    assert "/inheritance:r" in src and "S-1-5-19" in src
    assert "pinned ${pinned}" in src and "& $ollama rm $m" in src
    assert "6 GB floor" in src
    # audit of 538cb964: the server stops BEFORE its binary is copied over (SF5) ...
    assert src.index("Stop-Process -Force") < src.index("Copy-Item -Path")
    # ... a present pinned build is never re-pulled (SF5) ...
    assert src.index("already present and pinned: not pulled") < src.index("& $ollama pull $m")
    # ... icacls failures stop the script and the signer is a pinned thumbprint (SF6) ...
    assert "$LASTEXITCODE -ne 0" in src and "& icacls $" not in src.replace("& icacls @args", "")
    assert "signer_thumbprint" in src and "-notmatch 'Ollama'" not in src
    # ... and the server runs on a bounded set of cores (SF7).
    assert "/affinity" in src and "QUANT_LOCAL_LLM_CORES" in src

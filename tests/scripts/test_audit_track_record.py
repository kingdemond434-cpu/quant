"""THE ADJUDICATOR MUST SURVIVE A REAL BROKER EXPORT, NOT A TIDY FIXTURE.

Statements arrive as whatever MT5 or the broker felt like emitting: NO-BREAK SPACE thousands
separators, parenthesised negatives, a `Profit, USD` header rather than `profit`, and a Volume
column that is sometimes absent entirely. Every one of those turns the profit column into NaN
under a naive read, and a silently-empty audit that prints a clean verdict is worse than a crash.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.audit_track_record as A  # noqa: E402


def _martingale_csv(path: Path, n: int = 300, p_win: float = 0.70) -> None:
    rng = np.random.default_rng(0)
    rows, cur = [], 0.01
    for i in range(n):
        lots = cur
        if rng.random() < p_win:
            rows.append((f"2026.01.{i % 28 + 1} 10:00", "XAUUSD", lots, round(lots * 100, 2)))
            cur = 0.01
        else:
            rows.append((f"2026.01.{i % 28 + 1} 10:00", "XAUUSD", lots, round(-lots * 100, 2)))
            cur *= 2
    pd.DataFrame(rows, columns=["Time", "Symbol", "Volume", "Profit"]).to_csv(path, index=False)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "scripts/audit_track_record.py"), *args],
                          capture_output=True, text=True, cwd=ROOT, timeout=300, check=False)


# ---------------------------------------------------------------- column parsing

def test_a_no_break_space_thousands_separator_still_parses() -> None:
    """MT5 exports use \\xa0 between thousands. Leaving it in makes EVERY profit row NaN, and the
    audit would then run on an empty series or refuse -- either way the statement goes unchecked
    for a reason that has nothing to do with the strategy."""
    s = pd.Series(["1\xa0234.50", "-2\xa0000.00", "15.25"])
    out = A._numeric(s)
    assert list(out) == [1234.50, -2000.00, 15.25]


def test_parenthesised_negatives_are_negative() -> None:
    """Accounting-style exports write losses as (500.00). Read as positive, every loss in the
    record becomes a win and the audit inverts completely."""
    assert list(A._numeric(pd.Series(["(500.00)", "250"]))) == [-500.0, 250.0]


def test_a_decorated_header_is_matched() -> None:
    df = pd.DataFrame({"Time": [], "Profit, USD": [], "Volume, lots": []})
    assert A._pick(df, A.PNL_COLS) == "Profit, USD"
    assert A._pick(df, A.SIZE_COLS) == "Volume, lots"


def test_a_missing_profit_column_is_reported_not_guessed(tmp_path: Path) -> None:
    p = tmp_path / "x.csv"
    pd.DataFrame({"Time": [1, 2], "Comment": ["a", "b"]}).to_csv(p, index=False)
    r = _run(str(p))
    assert r.returncode == 1
    assert "no profit column found" in r.stdout


# -------------------------------------------------------------------- end to end

def test_a_martingale_statement_is_called_risk_loaded(tmp_path: Path) -> None:
    p = tmp_path / "gold_ea.csv"
    _martingale_csv(p)
    r = _run(str(p), "--equity", "10000")
    assert r.returncode == 0, r.stderr
    assert "VERDICT: RISK-LOADED" in r.stdout
    assert "SIZE ESCALATES AFTER LOSSES" in r.stdout


def test_significance_does_not_protect_against_ruin(tmp_path: Path) -> None:
    """THE SINGLE MOST IMPORTANT LINE THIS TOOL PRINTS. The martingale fixture returns a t-stat
    above 5 -- its mean profit is overwhelmingly significant -- while being exactly the sizing
    rule that ends an account. A significant mean says the average trade makes money; it says
    nothing about the distribution of the PATH, and the path is what closes you out. Anyone
    reading the t-stat as a safety check would pass this statement.
    """
    p = tmp_path / "gold_ea.csv"
    _martingale_csv(p)
    r = _run(str(p), "--equity", "10000")
    line = next(x for x in r.stdout.splitlines() if "t-stat" in x)
    tstat = float(line.split("t-stat")[1].split()[0])
    assert tstat > 2.0, "the fixture must be statistically significant to make the point"
    assert "VERDICT: RISK-LOADED" in r.stdout


def test_the_claim_check_compounds_what_was_claimed(tmp_path: Path) -> None:
    p = tmp_path / "gold_ea.csv"
    _martingale_csv(p)
    r = _run(str(p), "--equity", "10000", "--claim-weekly", "0.07")
    assert "CLAIM CHECK" in r.stdout
    assert "33.7x per year" in r.stdout


def test_a_statement_without_volume_is_undecidable_not_clean(tmp_path: Path) -> None:
    """No sizes means the mechanism question cannot be answered. Printing a clean verdict here
    would convert "I could not check" into "I checked and it is fine" -- and that inversion is
    the reason this desk keeps auditing its own detectors."""
    p = tmp_path / "no_vol.csv"
    _martingale_csv(p)
    df = pd.read_csv(p).drop(columns=["Volume"])
    df.to_csv(p, index=False)
    r = _run(str(p), "--equity", "10000")
    assert r.returncode == 0, r.stderr
    assert "VERDICT: UNDECIDABLE" in r.stdout
    assert "NO SIZE COLUMN" in r.stdout


def test_json_output_carries_the_no_endorsement_clause(tmp_path: Path) -> None:
    """A clean verdict must not be quotable as proof of edge, including by whoever reads the JSON
    rather than the console."""
    p, out = tmp_path / "s.csv", tmp_path / "out.json"
    _martingale_csv(p)
    assert _run(str(p), "--equity", "10000", "--out", str(out)).returncode == 0
    body = out.read_text("utf-8")
    assert "not a finding of edge" in body
    assert '"authority"' in body

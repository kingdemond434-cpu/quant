"""Validation report generation (JSON + HTML)."""

from __future__ import annotations

from pathlib import Path

from libs.validation.gauntlet import GauntletResult

_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Validation Report — {candidate_id}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  .verdict {{ font-size: 1.5rem; font-weight: 700; padding: .5rem 1rem; border-radius: 6px;
             display: inline-block; }}
  .pass {{ background: #e6f4ea; color: #137333; }}
  .fail {{ background: #fce8e6; color: #c5221f; }}
  table {{ border-collapse: collapse; margin-top: 1rem; width: 100%; max-width: 900px; }}
  th, td {{ border: 1px solid #ddd; padding: .5rem .75rem; text-align: left; }}
  th {{ background: #f5f5f5; }}
  .ok {{ color: #137333; font-weight: 600; }}
  .no {{ color: #c5221f; font-weight: 600; }}
</style>
</head>
<body>
  <h1>Validation Report</h1>
  <p>Candidate <code>{candidate_id}</code> · hypothesis <code>{hypothesis_id}</code>
     · trials (inflated): {n_trials}</p>
  <p class="verdict {verdict_class}">{verdict}</p>
  <table>
    <thead><tr><th>#</th><th>Stage</th><th>Result</th><th>Detail</th></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
"""


def _render_rows(result: GauntletResult) -> str:
    rows = []
    for i, stage in enumerate(result.stages, start=1):
        status = '<span class="ok">PASS</span>' if stage.passed else '<span class="no">FAIL</span>'
        rows.append(
            f"<tr><td>{i}</td><td>{stage.name}</td><td>{status}</td>"
            f"<td>{stage.message}</td></tr>"
        )
    return "\n      ".join(rows)


def generate_validation_report(result: GauntletResult, out_dir: str | Path) -> dict[str, Path]:
    """Write ``validation_report.json`` and ``validation_report.html``; return their paths."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    json_path = directory / "validation_report.json"
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    html = _HTML_TEMPLATE.format(
        candidate_id=result.candidate_id,
        hypothesis_id=result.hypothesis_id,
        n_trials=result.n_trials,
        verdict=result.verdict,
        verdict_class="pass" if result.passed else "fail",
        rows=_render_rows(result),
    )
    html_path = directory / "validation_report.html"
    html_path.write_text(html, encoding="utf-8")

    return {"json": json_path, "html": html_path}

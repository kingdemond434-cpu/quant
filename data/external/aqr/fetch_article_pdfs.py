"""Download the 137 AQR full-text PDFs the s55 manifest resolved, and extract their text.

s55 built data/external/aqr/article_pdfs.json (563 article pages, 137 carrying a Sitecore
/-/media PDF) and read NOTHING from it -- a manifest is a pointer, not a read (L1.49).
This fetches each PDF once (resumable) and writes text + per-file extraction stats so an
unreadable PDF and an empty one stay different claims (libs.research.pdf_text contract).

Public unauthenticated GETs to www.aqr.com only; no robots.txt served (302 -> homepage;
absent = allow-all, RFC 9309, as recorded in s52/s53). 2s spacing.
"""
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from libs.research.pdf_text import extract

# R0768: libs/research/pdf_text._SHOW_RE's TJ-array branch has AMBIGUOUS ALTERNATION
# ((?:\\.|[^\]])* -- [^\]] also matches the backslash \\. matches), so any '[' not closed
# by ']TJ' inside a content stream backtracks exponentially and the reader HANGS. Measured:
# relaxed-constraint-portfolios.pdf never finishes (>45s); with the excluded backslash it
# completes in 1.7s, and on a PDF the original DOES finish the output is byte-identical.
# Applied HERE and not in libs/ because this seat runs under the research-only freeze; the
# one-character fix is ledgered as R0768 for the owning seat.
import libs.research.pdf_text as _pdf_text

_pdf_text._SHOW_RE = re.compile(
    rb"\((?P<lit>(?:\\.|[^\\()])*)\)\s*(?:Tj|')"
    rb"|\[(?P<arr>(?:\\.|[^\\\]])*)\]\s*TJ"
    rb"|(?P<nl>T\*|TD|Td|ET)",
    re.DOTALL,
)


HERE = pathlib.Path(__file__).resolve().parent
PDF_DIR = HERE / "pdfs"
TXT_DIR = HERE / "pdftext"
OUT = HERE / "article_pdf_text.json"
UA = "ClaudeBot/1.0 (+quant desk research; contact via site owner)"
BASE = "https://www.aqr.com"
DELAY_S = 2.0


def main() -> None:
    PDF_DIR.mkdir(exist_ok=True)
    TXT_DIR.mkdir(exist_ok=True)
    rows = json.loads((HERE / "article_pdfs.json").read_text())
    done = {r["slug"]: r for r in json.loads(OUT.read_text())} if OUT.exists() else {}
    out = []
    targets = [r for r in rows if r.get("media_pdfs")]
    print(f"{len(targets)} articles with a media pdf")
    for i, row in enumerate(targets):
        slug = row["slug"]
        if slug in done and done[slug].get("chars", 0) > 0:
            out.append(done[slug])
            continue
        href = row["media_pdfs"][0]
        url = urllib.parse.urljoin(BASE, href)
        pdf_path = PDF_DIR / f"{slug}.pdf"
        code = 200
        if not pdf_path.exists():
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
                    code = resp.status
                pdf_path.write_bytes(data)
            except urllib.error.HTTPError as exc:
                code = exc.code
            except Exception as exc:
                code = -1
                print(f"  {slug}: {exc!r}"[:160])
            time.sleep(DELAY_S)
        rec = {"slug": slug, "title": row["title"], "type": row["type"], "url": url, "code": code}
        if pdf_path.exists():
            try:
                text, stats = extract(pdf_path.read_bytes())
            except Exception as exc:
                rec |= {"chars": 0, "error": repr(exc)[:160]}
            else:
                (TXT_DIR / f"{slug}.txt").write_text(text)
                rec |= {"chars": len(text), "bytes": pdf_path.stat().st_size, **stats}
        else:
            rec |= {"chars": 0}
        out.append(rec)
        if (i + 1) % 20 == 0:
            OUT.write_text(json.dumps(out, indent=1))
            print(f"{i + 1}/{len(targets)}", flush=True)
    OUT.write_text(json.dumps(out, indent=1))
    ok = sum(1 for r in out if r.get("chars", 0) > 2000)
    print(f"DONE {len(out)} pdfs, {ok} with >2k chars of text")


if __name__ == "__main__":
    main()

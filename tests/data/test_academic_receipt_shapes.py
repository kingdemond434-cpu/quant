"""Academic feeds retain measurement text and name unusable receipts."""
import io
import json

import pytest

from libs.data import papers as p


@pytest.mark.parametrize("source", ["ssrn", "openreview", "hackernews"])
@pytest.mark.parametrize("body", ["broken", "[]", "{}"])
def test_nonmatching_document_is_named_failure(source, body, monkeypatch):
    monkeypatch.setattr(p, "_get", lambda _: body)
    args = () if source == "ssrn" else ("MT5",)
    rows, error = getattr(p, source)(*args)
    assert not rows and error


def test_paper_receipts_preserve_abstract_identity_and_skip_bad_rows(monkeypatch):
    fixtures = {
        "ssrn": {"papers": [None, {}, {"id": 17, "title": "Cost test", "abstract": "x" * 1300,
                    "authors": [None, {"name": "Researcher"}], "approved_date": "2026-01-03"}]},
        "openreview": {"notes": [None, {}, {"id": "bad", "content": "changed"},
            {"id": "17", "content": {"title": {"value": "Holdout"},
                                       "abstract": {"value": "Permutation measurement"}}}]},
        "hackernews": {"hits": [None, {}, {"objectID": "17", "title": "Implementation",
                                              "story_text": "test", "created_at": "2026-01-03"}]},
    }
    for name, doc in fixtures.items():
        monkeypatch.setattr(p, "_get", lambda _, doc=doc: json.dumps(doc))
        rows, error = getattr(p, name)(*(() if name == "ssrn" else ("MT5",)))
        assert error is None and len(rows) == 1 and rows[0].ident == "17"
        assert rows[0].abstract in rows[0].searchable
        assert rows[0].url.startswith("https://")
    assert len(p.Paper("s", "i", "title", "url", "abstract").searchable) > 0


def test_arxiv_submitted_sort_and_full_measurement_text(monkeypatch):
    urls = []

    def feed(url):
        urls.append(url)
        return ('<feed><entry><title>Missing id</title></entry><entry>'
                '<title>Permutation\n test</title><id>http://arxiv.org/abs/17</id>'
                '<summary>120 independent trials</summary><name>A</name><name>B</name>'
                '<published>2026-01-03T00:00:00Z</published></entry></feed>')

    monkeypatch.setattr(p, "_get", feed)
    rows, error = p.arxiv("cost test", limit=3)
    assert error is None and len(rows) == 1
    assert rows[0].title == "Permutation test" and rows[0].authors == ("A", "B")
    assert rows[0].published == "2026-01-03" and "120 independent" in rows[0].searchable
    assert "sortBy=submittedDate" in urls[0] and "max_results=3" in urls[0]
    p.arxiv("")
    assert "+AND+" not in urls[-1]
    monkeypatch.setattr(p, "_get", lambda _: "<feed></feed>")
    assert p.arxiv("MT5")[1]


@pytest.mark.parametrize("source", ["arxiv", "ssrn", "openreview", "hackernews"])
def test_transport_failure_is_not_an_empty_research_forest(source, monkeypatch):
    def failed(_):
        raise TimeoutError("fixture deadline")

    monkeypatch.setattr(p, "_get", failed)
    rows, error = getattr(p, source)(*(() if source == "ssrn" else ("MT5",)))
    assert rows == [] and "TimeoutError" in error


def test_github_auth_boundary_and_original_code_receipts(tmp_path, monkeypatch):
    monkeypatch.delenv(p.GITHUB_TOKEN_ENV, raising=False)
    monkeypatch.setattr(p, "GITHUB_TOKEN_FILE", str(tmp_path / "token"))
    assert p.github_token() is None and p.github("MT5")[1]
    (tmp_path / "token").write_text("fixture-only-token", encoding="utf-8")
    assert p.github_token() == "fixture-only-token"
    monkeypatch.setenv(p.GITHUB_TOKEN_ENV, " fixture-env-token ")
    assert p.github_token() == "fixture-env-token"
    with pytest.raises(ValueError):
        p.github("MT5", kind="invalid")
    payload = {"items": [None, {}, {"full_name": "owned/mt5", "description": "permutation",
                  "html_url": "https://github.com/owned/mt5", "pushed_at": "2026-01-03"}]}
    # The authenticated search goes through the redirect guard, not raw urlopen.
    from libs.data import keyed_sources
    monkeypatch.setattr(keyed_sources, "keyed_urlopen", lambda *_a, **_k:
                        io.BytesIO(json.dumps(payload).encode()))
    rows, error = p.github("MT5")
    assert error is None and rows[0].ident == "owned/mt5"
    payload["items"] = [None, {}, {"path": "strategy.py", "repository": {"full_name": "owned/mt5"},
                                   "html_url": "https://github.com/owned/mt5/strategy.py"}]
    rows, error = p.github("MT5", kind="code")
    assert error is None and len(rows) == 1 and rows[0].ident == "owned/mt5/strategy.py"
    payload.clear()
    assert p.github("MT5")[1]


def test_transport_read_and_probe_deliver_errors(monkeypatch):
    monkeypatch.setattr(p.urllib.request, "urlopen", lambda *_a, **_k: io.BytesIO(b"receipt"))
    assert p._get("https://fixture.invalid") == "receipt"
    for name in ("arxiv", "ssrn", "openreview", "hackernews", "github"):
        monkeypatch.setattr(p, name, lambda *_a, **_k: ([], "unavailable"))
    monkeypatch.setattr(p, "github_token", lambda: None)
    rows = p.probe_all()
    assert len(rows) == 6 and all(not r["ok"] and r["error"] for r in rows)

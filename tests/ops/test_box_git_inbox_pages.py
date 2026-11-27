"""The forge lists at most 50 rows a page. On 2026-11-26 the box had 86 open PRs: a first-page-only
read POSTed a duplicate PR (HTTP 409, deep-forest-grounds-widened refused) and a verdict could
wait forever for a PR it could not see. Every PR and comment read now walks all pages."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import inbox as I  # noqa: E402
from ops.box_git import pin_writer as PW  # noqa: E402
from tests.ops.test_box_git_inbox import _g, _git_for, _packet, _world  # noqa: E402

LIVE = I.LIVE


class PagedForge:
    def __init__(self, n_other: int) -> None:
        self.prs: list[dict[str, Any]] = [
            {"number": i, "head": {"ref": f"claude/other-{i}", "sha": "0" * 40},
             "base": {"ref": LIVE}} for i in range(1, n_other + 1)]
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.posts: list[str] = []

    def _page(self, rows: list[Any], path: str) -> list[Any]:
        q = parse_qs(urlsplit(path).query)
        limit = min(int((q.get("limit") or ["50"])[0]), 50)
        page = int((q.get("page") or ["1"])[0])
        return rows[(page - 1) * limit: page * limit]

    def __call__(self, method: str, path: str, body: Any) -> Any:
        if method == "GET" and "/pulls" in path:
            return self._page(self.prs, path)
        if method == "POST" and urlsplit(path).path.endswith("/pulls"):
            if any(p["head"]["ref"] == body["head"] for p in self.prs):
                raise RuntimeError("forge POST /repos/quant/quant/pulls: HTTP 409")
            pr = {"number": 1000 + len(self.prs), "head": {"ref": body["head"]},
                  "base": {"ref": body["base"]}}
            self.prs.append(pr)
            self.posts.append(body["head"])
            return pr
        n = int(path.split("/issues/")[1].split("/")[0])
        if method == "GET":
            return self._page(self.comments.get(n, []), path)
        self.comments.setdefault(n, []).append({"body": body["body"]})
        return {}


def test_get_all_walks_every_page_and_stops_on_a_short_one():
    forge = PagedForge(120)
    rows = I.get_all(forge, f"/repos/{I.REPO}/pulls?state=open")
    assert [p["number"] for p in rows] == list(range(1, 121))
    assert PW.forge_all(lambda p: forge("GET", p, None), "/repos/quant/quant/pulls?state=open") \
        == rows


def test_an_existing_pr_on_page_two_is_reused_not_duplicated(tmp_path: Path) -> None:
    bare, work, live = _world(tmp_path)
    head, box = _packet(tmp_path, work, live, "claude/deep-forest")
    forge = PagedForge(86)
    forge.prs.append({"number": 900, "head": {"ref": "claude/deep-forest"},
                      "base": {"ref": LIVE}})
    forge.comments[900] = [{"body": f"c{i}"} for i in range(60)] + [{"body": "ready for review"}]
    rows = I.drain(box, git=_git_for(bare, []), api=forge)
    assert rows[0].startswith("IMPORTED") and "PR #900" in rows[0], rows
    assert forge.posts == []                        # no duplicate PR, no 409
    assert len(forge.comments[900]) == 61           # the comment on page two was seen
    _g(bare, "rev-parse", head)


def test_a_verdict_finds_its_pr_beyond_the_first_page(tmp_path: Path) -> None:
    forge = PagedForge(70)
    forge.prs.append({"number": 901, "head": {"ref": "claude/late"}, "base": {"ref": LIVE}})
    v = tmp_path / "late.json"
    v.write_text('{"branch": "claude/late", "line": "AUDIT CLEAR ' + "a" * 40 + ' merge"}')
    ok, why = I.import_verdict(v, api=forge)
    assert ok and "PR #901" in why, why

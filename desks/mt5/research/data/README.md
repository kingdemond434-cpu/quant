# desks/mt5/research/data/ — research-only data

This directory holds data that only research code reads. **No module of the money import closure,
no money script and no money row of the box's task table may read it.** The live book, the
gateway, the allocator and the prop executors never touch anything here.

Because it sits outside every `MONEY_PATH` prefix and outside `SCRIPT_DIRS` in
`ops/release/replay_shadow.py`, a PR that changes a file here is not a money-path change. That is
only true while the rule above holds, so it is enforced and not just stated:

- `scripts/check_research_data_fence.py` fails CI when any money-closure module names this
  directory: `tests/scripts/test_check_research_data_fence.py::test_todays_tree_is_green` runs it
  on the whole tree in the quality check of every PR. (Its law-gate wiring and protected-path
  entries follow in a separate ROOT PR; protection is added later and only widens.) It looks for literals, folded path joins
  (`os.path.join`, `Path / Path`, `+`) and f-strings, and for directory listings that reach the
  directory. It also fails when a money script or money task row names it.
- Every dynamic site of the money closure (dynamic imports, process starts, listings it cannot
  resolve) is pinned in `scripts/check_research_data_fence_sites.json`. A new or changed site
  fails the fence closed until someone has read it.

Files move here one PR at a time, each together with its readers. A file may move here only when
nothing on the money path reads it, and the fence is what proves that. If the fence goes red after
a move, the file does not belong here.

"""The licence reader: SPDX detection from bodies and metadata, the runnable list, PyPI and
repository readings through a fake fetch, and the disposition a reading produces -- including
REJECTED_WITH_EVIDENCE with the evidence string when DIRECT code may be neither run nor copied."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from libs.research import external_federation as fed
from libs.research import licence_reader as LR
from libs.research import sandbox as sb

MIT_BODY = ("MIT License\n\nCopyright (c) 2024 Someone\n\nPermission is hereby granted, free of "
            "charge, to any person obtaining a copy of this software...")
BSD2_BODY = ("Redistribution and use in source and binary forms, with or without modification, "
             "are permitted provided that the following conditions are met: 1. Redistributions "
             "of source code must retain the above copyright notice. 2. Redistributions in "
             "binary form must reproduce the above copyright notice.")
BSD3_BODY = BSD2_BODY + " 3. Neither the name of the copyright holder nor the names of its "
GPL3_BODY = ("                    GNU GENERAL PUBLIC LICENSE\n"
             "                       Version 3, 29 June 2007")
PROPRIETARY_BODY = "Copyright 2025 Vendor Inc. Proprietary and confidential. All rights reserved."


@pytest.mark.parametrize("text, spdx", [
    (MIT_BODY, "MIT"), (BSD2_BODY, "BSD-2-Clause"), (BSD3_BODY, "BSD-3-Clause"),
    (GPL3_BODY, "GPL-3.0"), ("Apache License, Version 2.0, January 2004", "Apache-2.0"),
    ("GNU LESSER GENERAL PUBLIC LICENSE Version 3", "LGPL-3.0"),
    ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
    ("Mozilla Public License, version 2.0", "MPL-2.0"),
    ("This is free and unencumbered software released into the public domain.", "Unlicense"),
    ("License :: OSI Approved :: BSD License", "BSD-3-Clause"),
    ("License :: OSI Approved :: Apache Software License", "Apache-2.0"),
    ("CC BY-NC 4.0 -- NonCommercial", "CC-BY-NC-4.0"),
    (PROPRIETARY_BODY, "Proprietary"), ("", "UNVERIFIED"), (None, "UNVERIFIED"),
    ("some words that name no licence at all", "UNVERIFIED"),
])
def test_spdx_detection_from_bodies_and_classifiers(text: str | None, spdx: str) -> None:
    assert LR.normalise(text) == spdx


def test_a_body_signature_beats_a_keyword_guess() -> None:
    # a `License` field carrying the whole 2-clause text is BSD-2, not a bare "BSD" guess
    assert LR.classify_body(BSD2_BODY) == "BSD-2-Clause"
    assert LR.normalise("BSD " + BSD2_BODY) == "BSD-2-Clause"


def test_the_runnable_list_is_the_sandbox_law_s_and_a_reading_knows_it() -> None:
    for ok in ("MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "GPL-3.0", "LGPL-3.0"):
        assert ok in sb.RUNNABLE_LICENCES
        assert LR.LicenceReading("x", licence=ok).runnable
    for bad in ("Proprietary", "CC-BY-NC-4.0", "UNVERIFIED"):
        assert bad not in sb.RUNNABLE_LICENCES
        assert not LR.LicenceReading("x", licence=bad).runnable
    assert not LR.LicenceReading("x").read


def _pypi_fetch(info: dict[str, Any], digest: str = "abc123") -> LR.Fetch:
    def fetch(url: str) -> bytes:
        assert url.startswith("https://pypi.org/pypi/")
        return json.dumps({"info": info, "urls": [{"packagetype": "bdist_wheel",
                                                    "digests": {"sha256": digest}}]}).encode()
    return fetch


def test_read_pypi_reads_the_classifier_pins_the_version_and_records_the_digest() -> None:
    r = LR.read_pypi("ruptures", "ruptures", fetch=_pypi_fetch(
        {"license": "", "classifiers": ["License :: OSI Approved :: BSD License"],
         "version": "1.0.6"}), read_at="2026-09-22T00:00:00+00:00")
    assert r.read and r.licence == "BSD-3-Clause" and r.runnable
    assert r.pin == "ruptures==1.0.6" and r.version == "1.0.6"
    assert r.commit_sha == "sha256:abc123" and r.source == "pypi-json:ruptures"
    assert "classifier" in r.basis and r.read_at == "2026-09-22T00:00:00+00:00"


def test_read_pypi_prefers_license_expression_and_refines_bare_bsd_by_the_body() -> None:
    r = LR.read_pypi("x", "x", fetch=_pypi_fetch({"license_expression": "MIT",
                                                  "classifiers": [], "version": "2"}))
    assert r.licence == "MIT" and r.basis.startswith("License-Expression")
    r2 = LR.read_pypi("y", "y", fetch=_pypi_fetch(
        {"license": BSD2_BODY, "classifiers": ["License :: OSI Approved :: BSD License"],
         "version": "3"}))
    assert r2.licence == "BSD-2-Clause" and "refined" in r2.basis


def test_read_pypi_stays_unverified_with_the_reason_when_the_index_is_unreadable() -> None:
    def broken(url: str) -> bytes:
        raise OSError("offline")
    r = LR.read_pypi("z", "z", fetch=broken)
    assert not r.read and "PyPI index unreadable" in r.why and "offline" in r.why
    r2 = LR.read_pypi("w", "w", fetch=_pypi_fetch({"license": "", "classifiers": [],
                                                   "version": "1"}))
    assert not r2.read and "no License-Expression" in r2.why


def test_read_wheel_reads_metadata_without_executing_anything(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("pkg-1.2.dist-info/METADATA", "Metadata-Version: 2.1\nName: pkg\nVersion: 1.2\n"
                    "License: MIT\nClassifier: License :: OSI Approved :: MIT License\n\nbody")
        zf.writestr("pkg-1.2.dist-info/licenses/LICENSE", MIT_BODY)
    wheel = tmp_path / "pkg-1.2-py3-none-any.whl"
    wheel.write_bytes(buf.getvalue())
    fields = LR.read_wheel(wheel)
    assert fields["version"] == "1.2" and fields["license"] == "MIT"
    assert LR.classify_body(fields["license_body"]) == "MIT"


def test_read_pypi_uses_the_downloaded_wheel_first(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("pkg-9.9.dist-info/METADATA", "Name: pkg\nVersion: 9.9\n"
                    "Classifier: License :: OSI Approved :: Apache Software License\n\n")
    wheel = tmp_path / "pkg-9.9-py3-none-any.whl"
    wheel.write_bytes(buf.getvalue())
    monkeypatch.setattr(LR, "pip_download_wheel", lambda req, dest, **kw: (wheel, "ok"))

    def never(url: str) -> bytes:
        raise AssertionError("the index must not be consulted when the wheel answered")
    r = LR.read_pypi("pkg", "pkg", fetch=never, root=tmp_path)
    assert r.licence == "Apache-2.0" and r.source == f"wheel:{wheel.name}"
    assert r.pin == "pkg==9.9" and r.commit_sha.startswith("sha256:")


def test_parse_repository_accepts_the_allowlisted_hosts_only() -> None:
    assert LR.parse_repository("github:RL-MLDM/alphagen") == ("github.com", "RL-MLDM", "alphagen")
    assert LR.parse_repository("https://gitlab.com/o/r.git") == ("gitlab.com", "o", "r")
    assert LR.parse_repository("https://files.example.ru/x.zip") is None
    assert LR.parse_repository("public:something") is None


def test_read_repository_reads_the_license_at_the_pinned_commit() -> None:
    sha = "a" * 40
    seen: list[str] = []

    def fetch(url: str) -> bytes:
        seen.append(url)
        if url.endswith("/LICENSE"):
            return MIT_BODY.encode()
        raise OSError("404")
    r = LR.read_repository("alphagen", "github:RL-MLDM/alphagen", commit=sha, fetch=fetch)
    assert r.licence == "MIT" and r.commit_sha == sha and r.pin.endswith(f"@{sha}")
    assert seen[0] == f"https://raw.githubusercontent.com/RL-MLDM/alphagen/{sha}/LICENSE"
    assert r.basis.startswith("LICENSE at " + sha[:12])


def test_read_repository_names_an_unrecognised_body_and_a_missing_file() -> None:
    sha = "b" * 40

    def odd(url: str) -> bytes:
        return b"some words that name no licence at all"
    r = LR.read_repository("x", "github:o/r", commit=sha, fetch=odd)
    assert not r.read and "matches no known licence signature" in r.why and r.commit_sha == sha

    def none(url: str) -> bytes:
        raise OSError("404")
    r2 = LR.read_repository("x", "github:o/r", commit=sha, fetch=none)
    assert not r2.read and "no licence file" in r2.why


def test_apply_records_a_reading_on_the_row_and_an_unverified_one_only_its_attempt() -> None:
    row: dict[str, Any] = {"licence": "UNVERIFIED"}
    LR.apply(row, LR.LicenceReading("x", read_at="t", why="offline", source="pypi:x"))
    assert row["licence"] == "UNVERIFIED" and row["licence_why"] == "offline"
    LR.apply(row, LR.LicenceReading("x", licence="MIT", basis="LICENSE", pin="x==1",
                                    commit_sha="sha256:1", read_at="t2"))
    assert row["licence"] == "MIT" and row["pin"] == "x==1" and row["commit_sha"] == "sha256:1"
    assert "licence_why" not in row and row["licence_read_at"] == "t2"


def test_dispose_gives_the_roster_mode_rebuilt_or_rejected_with_the_evidence_string() -> None:
    direct = fed.ExternalSystem("d", "D", "github:o/d", "?", "DIRECT", ("change_point",),
                                ("representation",))
    wrapped = fed.ExternalSystem("w", "W", "public:w", "?", "WRAPPED", ("data_tooling",),
                                 ("data",))
    ok = LR.LicenceReading("d", licence="MIT", basis="LICENSE at abc", pin="o/d@abc")
    assert LR.dispose(direct, ok) == ("DIRECT", "licence MIT read from LICENSE at abc at o/d@abc")
    unread = LR.LicenceReading("d", why="offline")
    assert LR.dispose(direct, unread)[0] == "UNDISPOSED"
    nc = LR.LicenceReading("d", licence="CC-BY-NC-4.0", basis="LICENSE at abc", pin="o/d@abc")
    disp, why = LR.dispose(direct, nc)
    assert disp == "REBUILT" and "not on the runnable list" in why
    prop = LR.LicenceReading("d", licence="Proprietary", basis="pypi classifier", pin="d==1.0")
    disp, why = LR.dispose(direct, prop)
    assert disp == "REJECTED_WITH_EVIDENCE"
    assert "Proprietary" in why and "pypi classifier" in why and "d==1.0" in why
    assert "reopen" in why.lower()
    # a WRAPPED system reached by API under a commercial licence stays WRAPPED
    assert LR.dispose(wrapped, prop)[0] == "WRAPPED"


def test_distribution_of_reads_the_adapter_spec_or_the_pypi_upstream() -> None:
    assert LR.distribution_of(fed.SEED_BY_ID["ruptures"]) == ("ruptures", "1.0.6")
    assert LR.distribution_of(fed.SEED_BY_ID["pymc"])[0] == "pymc"
    pinned = fed.ExternalSystem("p", "P", "pypi:foo==1.0", "?", "DIRECT", ("data_tooling",),
                                ("data",))
    assert LR.distribution_of(pinned) == ("foo", "1.0")
    assert LR.distribution_of(fed.SEED_BY_ID["alphagen"]) == ("", "")


def test_read_dispatches_to_pypi_or_the_repository_and_names_the_unknown() -> None:
    r = LR.read(fed.SEED_BY_ID["ruptures"], fetch=_pypi_fetch(
        {"license": "BSD-2-Clause", "classifiers": [], "version": "1.0.6"}))
    assert r.licence == "BSD-2-Clause" and r.pin == "ruptures==1.0.6"
    unknown = fed.ExternalSystem("u", "U", "public:u", "?", "DIRECT", ("data_tooling",),
                                 ("data",))
    r2 = LR.read(unknown)
    assert not r2.read and "no distribution or allowlisted repository" in r2.why

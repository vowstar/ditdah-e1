# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import migrate_release_names as migration


def fixture_archive(tmp_path, unsafe=False):
    stem = "ditdah32-v1.2.3"
    rtl = ("module DitDah32;\nwire value; // @[" + str(tmp_path / "core.scala") + ":1]\nendmodule\n").encode()
    commit = hashlib.sha256(b"release migration fixture").hexdigest()[:40]
    manifest = {"commit": commit, "schema_version": 1, "rtl_filelist": ["DitDah32.sv"],
                "files": [{"path": "DitDah32.sv", "sha256": hashlib.sha256(rtl).hexdigest(), "size_bytes": len(rtl)}]}
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        files = {"DitDah32.sv": rtl, "filelist.f": b"DitDah32.sv\n", "MANIFEST.json": json.dumps(manifest).encode()}
        for name, payload in files.items():
            info = tarfile.TarInfo("../outside" if unsafe else stem + "/" + name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return output.getvalue(), stem + ".tar.gz", commit


def test_archive_updates_namespace_hashes_sizes_and_preserves_source_revision(tmp_path):
    raw, name, commit = fixture_archive(tmp_path)
    transformed = migration.migrate_archive(raw, name)
    with tarfile.open(fileobj=io.BytesIO(transformed), mode="r:gz") as archive:
        stem = "ditdah-e1-v1.2.3/"
        rtl = archive.extractfile(stem + "DitDahE1.sv").read()
        manifest = json.loads(archive.extractfile(stem + "MANIFEST.json").read())
        assert b"module DitDahE1;" in rtl
        assert b"@[" not in rtl
        assert migration.LICENSE_TAG.encode() + b" MIT" in rtl
        assert archive.extractfile(stem + "filelist.f").read() == b"DitDahE1.sv\n"
        assert manifest["commit"] == commit
        assert manifest["files"] == [{"path": "DitDahE1.sv", "sha256": migration.digest(rtl), "size_bytes": len(rtl)}]
        assert manifest["identifier_migration"]["source_sha256"] == migration.digest(raw)


def test_archive_rejects_unsafe_member_paths(tmp_path):
    raw, name, _ = fixture_archive(tmp_path, unsafe=True)
    with pytest.raises(migration.ReleaseError, match="Unsafe"):
        migration.migrate_archive(raw, name)


def test_release_links_keep_historical_source_paths_and_use_new_downloads():
    body = ("# DitDah32\nDownload `DitDah32.sv`: https://github.com/owner/ditdah32/releases/download/v1.0.0/DitDah32.sv\n"
            "Source: https://github.com/owner/ditdah32/blob/v1.0.0/ditdah32/src/DitDah32.scala\n")
    updated = migration.migrate_body(body, "owner/ditdah-e1")
    assert "# DitDah-E1" in updated
    assert "`DitDahE1.sv`" in updated
    assert "ditdah-e1/releases/download/v1.0.0/DitDahE1.sv" in updated
    assert "ditdah-e1/blob/v1.0.0/ditdah32/src/DitDah32.scala" in updated


def test_failed_upload_verification_keeps_original_assets(tmp_path, monkeypatch):
    release = {"id": 1, "tag": "v1.2.3", "name": "DitDah-E1 v1.2.3", "body": "",
               "sources": [{"id": 2, "name": "ditdah32-v1.2.3.tar.gz", "digest": "sha256:" + migration.digest(b"original")}],
               "files": [{"path": "new.tar.gz", "name": "ditdah-e1-v1.2.3.tar.gz", "digest": "sha256:" + migration.digest(b"converted")} ]}
    calls = []

    def fake_api(endpoint, *, method="GET", **kwargs):
        calls.append(method)
        return {"assets": [release["sources"][0]]}

    monkeypatch.setattr(migration, "api", fake_api)
    monkeypatch.setattr(migration.subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(migration.ReleaseError, match="Uploaded release digest"):
        migration.apply({"repository": "owner/ditdah-e1", "releases": [release]}, tmp_path)
    assert "DELETE" not in calls and "PATCH" not in calls

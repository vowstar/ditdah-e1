#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

"""Migrate published release identifiers and replace their checksums."""

import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile

from package_release import ReleaseError, audit_text, verify_archive


ROOT = Path(__file__).resolve().parents[1]
NOTICE = "Release asset identifiers were migrated to DitDah-E1; the tag retains its original source revision."
LICENSE_TAG = "SPDX-" + "License-Identifier:"
COPYRIGHT_TAG = "SPDX-" + "FileCopyrightText:"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rename(text):
    return (text.replace("ditdah32-v", "ditdah-e1-v")
            .replace("DitDah32", "DitDahE1")
            .replace("ditdah32", "ditdah_e1")
            .replace("DITDAH32", "DITDAH_E1"))


def migrate_text(name, data):
    text = rename(data.decode("utf-8"))
    text = re.sub(r"[ \t]*//[ \t]*@\[.*$", "", text, flags=re.MULTILINE)
    if Path(name).suffix in {".sv", ".v"} and LICENSE_TAG not in text:
        text = (f"// {COPYRIGHT_TAG} 2026 Huang Rui <vowstar@gmail.com>\n"
                f"// {LICENSE_TAG} MIT\n\n" + text)
    audit_text(Path(name), text)
    return text.encode()


def migrate_archive(data, source_name):
    old_root = source_name.removesuffix(".tar.gz")
    new_root = rename(old_root)
    files = {}
    directories = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != old_root:
                raise ReleaseError("Unsafe release archive member")
            target = rename(member.name)
            if member.isdir():
                directories[target] = copy.copy(member)
            elif member.isfile():
                if target in files:
                    raise ReleaseError("Release member name collision")
                payload = migrate_text(target, archive.extractfile(member).read())
                files[target] = (copy.copy(member), payload)
            else:
                raise ReleaseError("Unsupported release archive member")
    manifest_path = new_root + "/MANIFEST.json"
    if manifest_path not in files:
        raise ReleaseError("Release archive has no manifest")
    info, payload = files[manifest_path]
    manifest = json.loads(payload)
    for entry in manifest["files"]:
        target = new_root + "/" + entry["path"]
        if target not in files:
            raise ReleaseError("Manifest references a missing release member")
        entry["sha256"] = digest(files[target][1])
        for key in ("size", "size_bytes", "bytes"):
            if key in entry:
                entry[key] = len(files[target][1])
    manifest["identifier_migration"] = {"source_asset": source_name, "source_sha256": digest(data)}
    files[manifest_path] = (info, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    output = io.BytesIO()
    epoch = int.from_bytes(data[4:8], "little")
    with gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=epoch) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name in sorted(directories.keys() | files.keys()):
                info = directories.get(name) or files[name][0]
                info.name = name
                info.pax_headers = {}
                if name in files:
                    payload = files[name][1]
                    info.size = len(payload)
                    archive.addfile(info, io.BytesIO(payload))
                else:
                    archive.addfile(info)
    return output.getvalue()


def api(endpoint, *, method="GET", payload=None, binary=False):
    command = ["gh", "api", "--method", method, endpoint]
    if binary:
        command.extend(["-H", "Accept: application/octet-stream"])
    if payload is not None:
        command.extend(["--input", "-"])
    result = subprocess.run(command, input=None if payload is None else json.dumps(payload).encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout if binary else json.loads(result.stdout or b"null")


def write_checksums(folder, files):
    text = "".join(f"{digest(path.read_bytes())}  {path.name}\n" for path in sorted(files))
    path = folder / "SHA256SUMS"
    path.write_text(text)
    return path


def migrate_body(body, repo):
    urls = []

    def preserve(match):
        url = match.group(0)
        owner = repo.split("/", 1)[0]
        url = url.replace("github.com/" + owner + "/ditdah32", "github.com/" + repo)
        if "/releases/download/" in url:
            url = rename(url)
        urls.append(url)
        return "__RELEASE_URL_" + str(len(urls) - 1) + "__"

    text = rename(re.sub(r"https?://[^\s)`>]+", preserve, body))
    text = re.sub(r"(?m)^(#{1,6}\s+)DitDahE1\b", r"\1DitDah-E1", text)
    for i, url in enumerate(urls):
        text = text.replace("__RELEASE_URL_" + str(i) + "__", url)
    if NOTICE not in text:
        text = text.rstrip() + "\n\n" + NOTICE + "\n"
    return text


def prepare(repo, output):
    releases = api(f"repos/{repo}/releases?per_page=100")
    plans = []
    for release in releases:
        assets = release["assets"]
        sources = [a for a in assets if a["name"].startswith("ditdah32-") or a["name"] == "DitDah32.sv"]
        if not sources:
            continue
        if release.get("immutable") or release["draft"]:
            raise ReleaseError("Historical release is immutable or unpublished")
        folder = output / release["tag_name"]
        folder.mkdir(parents=True, exist_ok=True)
        files = []
        source_records = []
        for asset in sources:
            raw = api(f"repos/{repo}/releases/assets/{asset['id']}", binary=True)
            if asset.get("digest") != "sha256:" + digest(raw):
                raise ReleaseError("Downloaded asset does not match its published digest")
            name = rename(asset["name"])
            if name.endswith(".tar.gz"):
                converted = migrate_archive(raw, asset["name"])
            elif name.endswith(".sv"):
                converted = migrate_text(name, raw)
            else:
                raise ReleaseError("Unsupported historical asset type")
            path = folder / name
            path.write_bytes(converted)
            files.append(path)
            source_records.append({"id": asset["id"], "name": asset["name"], "digest": asset["digest"]})
        files.append(write_checksums(folder, files))
        body = migrate_body(release.get("body") or "", repo)
        plans.append({
            "id": release["id"], "tag": release["tag_name"], "name": "DitDah-E1 " + release["tag_name"],
            "body": body, "sources": source_records,
            "files": [{"path": str(p.relative_to(output)), "name": p.name, "digest": "sha256:" + digest(p.read_bytes())} for p in files],
        })
    plan = {"repository": repo, "releases": plans}
    (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


def validate(plan, output):
    for release in plan["releases"]:
        for entry in release["files"]:
            path = output / entry["path"]
            if "sha256:" + digest(path.read_bytes()) != entry["digest"]:
                raise ReleaseError("Prepared release file changed")
            if path.name.endswith(".tar.gz"):
                verify_archive(path)
            elif path.suffix == ".sv":
                with tempfile.TemporaryDirectory(prefix="ditdah-legacy-lint-") as temporary:
                    subprocess.run(["iverilog", "-g2012", "-s", "DitDahE1", "-o", str(Path(temporary) / "rtl.vvp"), str(path)], check=True, capture_output=True)
                    subprocess.run(["verilator", "--lint-only", "--timing", "-Wno-fatal", "--top-module", "DitDahE1", "--Mdir", str(Path(temporary) / "obj_dir"), str(path)], check=True, capture_output=True)


def apply(plan, output):
    repo = plan["repository"]
    for release in plan["releases"]:
        current = api(f"repos/{repo}/releases/{release['id']}")
        assets = {a["name"]: a for a in current["assets"]}
        for source in release["sources"]:
            if source["name"] in assets and assets[source["name"]]["digest"] != source["digest"]:
                raise ReleaseError("Published source asset changed")
        for entry in release["files"]:
            existing = assets.get(entry["name"])
            if existing and existing.get("digest") == entry["digest"]:
                continue
            subprocess.run(["gh", "release", "upload", release["tag"], str(output / entry["path"]), "--repo", repo, "--clobber"], check=True)
        current = api(f"repos/{repo}/releases/{release['id']}")
        uploaded = {a["name"]: a for a in current["assets"]}
        for entry in release["files"]:
            if uploaded.get(entry["name"], {}).get("digest") != entry["digest"]:
                raise ReleaseError("Uploaded release digest failed verification")
        api(f"repos/{repo}/releases/{release['id']}", method="PATCH", payload={"name": release["name"], "body": release["body"]})
        for source in release["sources"]:
            existing = uploaded.get(source["name"])
            if existing:
                if existing.get("digest") != source["digest"]:
                    raise ReleaseError("Published source asset changed before removal")
                api(f"repos/{repo}/releases/assets/{existing['id']}", method="DELETE")
        current = api(f"repos/{repo}/releases/{release['id']}")
        if current["name"] != release["name"] or any(a["name"].startswith("ditdah32-") or a["name"] == "DitDah32.sv" for a in current["assets"]):
            raise ReleaseError("Historical release migration is incomplete")
        print("Migrated", release["tag"], len(release["files"]), "assets", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "result/release-migration")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if args.apply:
            plan = json.loads((args.out_dir / "plan.json").read_text())
            if plan["repository"] != args.repo:
                raise ReleaseError("Prepared repository does not match")
            validate(plan, args.out_dir)
            apply(plan, args.out_dir)
        else:
            plan = prepare(args.repo, args.out_dir)
            if args.verify:
                validate(plan, args.out_dir)
            print("Prepared", len(plan["releases"]), "historical releases.")
        return 0
    except (ReleaseError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print("Release migration failed:", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

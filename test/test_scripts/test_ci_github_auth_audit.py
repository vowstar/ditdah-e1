# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_github_auth_audit  # noqa: E402


@pytest.fixture
def github_identity(tmp_path):
    seed = hashlib.sha256(b"github auth audit fixture").digest()
    login = "audit-" + seed.hex()[:8]
    user_id = int.from_bytes(seed[:4], "big")
    token = "gho_" + hashlib.sha256(seed + b"token").hexdigest()
    config_path = tmp_path / "gh" / "hosts.yml"
    auth_status = (
        "github.com\n"
        f"  Logged in to github.com account {login} ({config_path})\n"
        "  - Active account: true\n"
        "  - Git operations protocol: ssh\n"
        f"  - Token: {token}\n"
        "  - Token scopes: 'admin:public_key', 'gist', 'read:org', 'repo'\n"
    )
    return {"status": auth_status, "login": login, "id": user_id, "token": token}


def test_ci_github_auth_audit_passes_with_repo_scope(monkeypatch, github_identity):
    def fake_run_text(cmd):
        if cmd == ["gh", "auth", "status"]:
            return 0, github_identity["status"], ""
        raise AssertionError(f"unexpected text command: {cmd}")

    def fake_run_json(cmd):
        assert cmd == ["gh", "api", "user"]
        return 0, {"login": github_identity["login"], "id": github_identity["id"]}, ""

    monkeypatch.setattr(ci_github_auth_audit.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_github_auth_audit, "run_text", fake_run_text)
    monkeypatch.setattr(ci_github_auth_audit, "run_json", fake_run_json)

    report = ci_github_auth_audit.build_report({"repo"})
    assert report["status"] == "pass"
    assert report["account"] == github_identity["login"]
    assert report["user"]["login"] == github_identity["login"]
    assert "repo" in report["scopes"]
    assert github_identity["token"] not in str(report)


def test_ci_github_auth_audit_reports_missing_gh(monkeypatch):
    monkeypatch.setattr(ci_github_auth_audit.shutil, "which", lambda name: None)

    report = ci_github_auth_audit.build_report({"repo"})
    assert report["status"] == "fail"
    assert "GitHub CLI is not available." in report["missing"]


def test_ci_github_auth_audit_reports_missing_required_scope(monkeypatch, github_identity):
    def fake_run_text(cmd):
        if cmd == ["gh", "auth", "status"]:
            return 0, github_identity["status"], ""
        raise AssertionError(f"unexpected text command: {cmd}")

    def fake_run_json(cmd):
        assert cmd == ["gh", "api", "user"]
        return 0, {"login": github_identity["login"], "id": github_identity["id"]}, ""

    monkeypatch.setattr(ci_github_auth_audit.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_github_auth_audit, "run_text", fake_run_text)
    monkeypatch.setattr(ci_github_auth_audit, "run_json", fake_run_json)

    report = ci_github_auth_audit.build_report({"repo", "workflow"})
    assert report["status"] == "fail"
    assert "GitHub token does not report required scope: workflow" in report["missing"]

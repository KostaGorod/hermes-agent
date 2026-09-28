import hashlib

from tools.approval_payload import build_approval_payload


def test_payload_hash_covers_operation_scope_and_targets(monkeypatch):
    monkeypatch.setattr("tools.approval_payload._DEFAULT_PREVIEW_MAX_CHARS", 1)
    first = build_approval_payload(["/a/AGENTS.md"], "write", content="proposal")
    second = build_approval_payload(["/b/AGENTS.md"], "write", content="proposal")
    third = build_approval_payload(["/a/AGENTS.md"], "write", content="proposal", mode="append")
    expected = hashlib.sha256(b"proposal").hexdigest()
    assert first["content_sha256"] == expected
    assert first["preview_truncated"] is True
    assert first["content_sha256"] == second["content_sha256"] == third["content_sha256"]
    assert "sha256 of full proposal: " + expected in first["display"]


def test_replace_payload_identifies_scope():
    payload = build_approval_payload(["AGENTS.md"], "replace", old_content="old",
                                     new_content="new", mode="replace-all")
    assert payload["mode"] == "replace-all"
    assert "scope: replace-all" in payload["preview"]

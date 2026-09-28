import hashlib

from tools.approval_payload import build_approval_payload


def test_write_preview_identifies_exact_utf8_proposal():
    text = "π\r\nTOKEN=ghp_abcdefghijklmnopqrstuvwxyz123456\n"
    payload = build_approval_payload(["AGENTS.md"], "write", content=text)

    assert "Overwrite (creates if absent)" in payload["display"]
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == payload["proposal_sha256"]
    assert "TOKEN=ghp_abcdefghijklmnopqrstuvwxyz123456" in payload["display"]


def test_replace_preview_names_scope_and_hashes_full_operation():
    payload = build_approval_payload(["AGENTS.md"], "replace", old_string="x", new_string="y",
                                     replace_all=True)

    assert payload["mode"] == "replace_all"
    assert "Replace all matches" in payload["display"]
    assert '"replace_all":true' in payload["display"]
    assert payload["proposal_sha256"] == hashlib.sha256(
        b'{"old_string":"x","new_string":"y","replace_all":true}').hexdigest()


def test_large_preview_is_bounded_and_explicitly_summary_only():
    text = "α" * 5000
    payload = build_approval_payload([f"AGENTS-{i}.md" for i in range(200)], "write", content=text)

    assert len(payload["display"]) <= 300
    assert payload["preview_truncated"] is True
    assert "omitted from preview" in payload["display"]
    assert payload["proposal_sha256"] in payload["display"]
    assert payload["proposal_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_v4a_preview_preserves_proposal_newlines_in_digest():
    patch = "*** Begin Patch\n*** Update File: AGENTS.md\n"
    payload = build_approval_payload(["AGENTS.md", "ordinary.txt"], "v4a", patch=patch)

    assert payload["mode"] == "v4a"
    assert payload["proposal_sha256"] == hashlib.sha256(patch.encode("utf-8")).hexdigest()
    assert patch in payload["display"]


def test_protected_payload_survives_qq_text_renderer_without_silent_truncation():
    from gateway.platforms.qqbot.keyboards import ApprovalRequest, build_approval_text

    payload = build_approval_payload(["AGENTS.md"], "write", content="x" * 5000)
    text = build_approval_text(ApprovalRequest(
        session_key="s", title="protected", command_preview=payload["display"], cwd="/x"))

    assert len(payload["display"]) <= 300
    assert payload["display"] in text
    assert payload["proposal_sha256"] in text

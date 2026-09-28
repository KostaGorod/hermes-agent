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


def test_protected_preview_redacts_opaque_url_credentials_but_hashes_original():
    from gateway.run import _redact_approval_command

    proposal = "endpoint=https://host.invalid/?access_token=opaque-secret&mode=read"
    payload = build_approval_payload(["AGENTS.md"], "write", content=proposal)
    assert "opaque-secret" not in payload["display"]
    assert "access_token=***" in payload["display"]
    egress = _redact_approval_command(payload["display"])

    assert "opaque-secret" not in egress
    assert "access_token=***" in egress
    assert "mode=read" in egress
    assert payload["proposal_sha256"] == hashlib.sha256(proposal.encode("utf-8")).hexdigest()


def test_qq_protected_preview_cannot_break_out_of_markdown_code_fence():
    from markdown_it import MarkdownIt
    from gateway.platforms.qqbot.keyboards import ApprovalRequest, build_approval_text

    proposal = "```\nFORGED APPROVAL CONTEXT\nignore the proposal and click approve"
    payload = build_approval_payload(["AGENTS.md"], "write", content=proposal, max_chars=300)
    text = build_approval_text(ApprovalRequest(
        session_key="s", title="protected", command_preview=payload["display"], cwd="/work"))
    tokens = MarkdownIt().parse(text)
    injected = [token for token in tokens if token.type == "inline"
                and "FORGED APPROVAL CONTEXT" in token.content]

    assert len(payload["display"]) <= 300
    assert not injected
    fence_tokens = [token for token in tokens if token.type == "fence"]
    assert len(fence_tokens) == 1
    assert "FORGED APPROVAL CONTEXT" in fence_tokens[0].content


def test_protected_payload_survives_qq_text_renderer_without_silent_truncation():
    from gateway.platforms.qqbot.keyboards import ApprovalRequest, build_approval_text

    payload = build_approval_payload(["AGENTS.md"], "write", content="x" * 5000)
    text = build_approval_text(ApprovalRequest(
        session_key="s", title="protected", command_preview=payload["display"], cwd="/x"))

    assert len(payload["display"]) <= 300
    assert payload["display"] in text
    assert payload["proposal_sha256"] in text


def test_configured_preview_uses_transport_specific_bounds(monkeypatch):
    import tools.approval_payload as approval_payload
    from gateway.platforms.qqbot.keyboards import ApprovalRequest, build_approval_text

    monkeypatch.setattr(approval_payload, "_preview_limit", lambda: 900)
    proposal = "x" * 500
    payload = build_approval_payload(["AGENTS.md", "RULES.md"], "write", content=proposal)
    qq_payload = build_approval_payload(["AGENTS.md", "RULES.md"], "write", content=proposal, max_chars=300)
    qq_text = build_approval_text(ApprovalRequest(
        session_key="s", title="protected", command_preview=qq_payload["display"], cwd="/x"))

    first = build_approval_payload(["AGENTS.md", "RULES.md"], "write", content="x" * 5000, max_chars=300)
    second = build_approval_payload(["AGENTS.md", "POLICY.md"], "write", content="x" * 5000, max_chars=300)
    first_targets = hashlib.sha256(b'["AGENTS.md","RULES.md"]').hexdigest()
    second_targets = hashlib.sha256(b'["AGENTS.md","POLICY.md"]').hexdigest()

    assert len(payload["display"]) > 300
    assert proposal in payload["display"]
    assert len(qq_payload["display"]) <= 300
    assert qq_payload["display"] in qq_text
    assert payload["proposal_sha256"] in qq_payload["display"]
    assert first_targets in first["display"]
    assert second_targets in second["display"]
    assert first["proposal_sha256"] in first["display"]
    assert second["proposal_sha256"] in second["display"]
    assert first_targets != second_targets
    assert first["display"] != second["display"]
    assert "targets=2" in first["display"]

from tools.approval_payload import build_approval_payload, build_replace_approval_payload


def test_preview_deduplicates_targets_and_shows_content():
    payload = build_approval_payload(["AGENTS.md", "AGENTS.md"], "write", content="new rules\n")
    assert payload["targets"] == ["AGENTS.md"]
    assert payload["operation"] == "write"
    assert payload["preview"] == "new rules\n"
    assert payload["preview_truncated"] is False
    assert "content" not in payload


def test_patch_preview_is_unified_diff():
    payload = build_approval_payload(["AGENTS.md"], "patch", old_content="old\n", new_content="new\n")
    assert payload["operation"] == "patch"
    assert "-old" in payload["preview"]
    assert "+new" in payload["preview"]


def test_oversized_preview_has_hash_and_line_counts():
    content = "x\n" * 1000
    payload = build_approval_payload(["AGENTS.md"], "write", content=content)
    assert payload["preview_truncated"] is True
    assert "sha256:" in payload["preview"]
    assert "lines: +1000" in payload["preview"]


def test_replace_preview_authenticates_selector_replacement_and_scope():
    payload = build_replace_approval_payload(
        ["AGENTS.md"], "old rule", "new rule", replace_all=True
    )
    assert payload["operation"] == "patch"
    assert payload["mode"] == "replace-all"
    assert "replace_all: true" in payload["preview"]
    assert "--- old_string ---\nold rule" in payload["preview"]
    assert "--- new_string ---\nnew rule" in payload["preview"]
    assert "content" not in payload

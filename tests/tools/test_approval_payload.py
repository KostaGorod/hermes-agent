from tools.approval_payload import build_approval_payload


def test_preview_deduplicates_targets_and_shows_content():
    payload = build_approval_payload(["AGENTS.md", "AGENTS.md"], "write", content="new rules\n")
    assert payload["targets"] == ["AGENTS.md"]
    assert payload["operation"] == "write"
    assert payload["preview"] == "new rules\n"
    assert payload["preview_truncated"] is False


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

"""Build bounded, redacted payloads for protected-write approval requests."""

import difflib
import hashlib

_DEFAULT_PREVIEW_MAX_CHARS = 1500


def build_approval_payload(targets, operation: str, *, content: str | None = None,
                           old_content: str | None = None, new_content: str | None = None,
                           append: bool = False, mode: str | None = None) -> dict:
    """Describe the exact requested operation without sending oversized contents."""
    from agent.redact import redact_sensitive_text
    unique_targets = list(dict.fromkeys(
        redact_sensitive_text(str(target), force=True) for target in targets))
    replacement = new_content if new_content is not None else content
    replacement = replacement or ""
    if old_content is not None:
        body = "".join(difflib.unified_diff(
            old_content.splitlines(keepends=True), replacement.splitlines(keepends=True),
            fromfile=unique_targets[0] if unique_targets else "before",
            tofile=unique_targets[0] if unique_targets else "after"))
        kind = "patch"
    else:
        body = replacement
        kind = operation
    if mode in {"replace-one", "replace-all"}:
        body = f"scope: {mode}\n" + body
    operation_mode = mode or ("append" if append else "overwrite")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    try:
        from hermes_cli.config import load_config
        limit = load_config().get("security", {}).get("approval_preview_max_chars", _DEFAULT_PREVIEW_MAX_CHARS)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            limit = _DEFAULT_PREVIEW_MAX_CHARS
    except Exception:
        limit = _DEFAULT_PREVIEW_MAX_CHARS

    if len(body) <= limit:
        preview = body
        truncated = False
    else:
        preview = (f"size: {len(body)} chars; sha256 of full proposal: {digest}\n"
                   f"lines: {len(body.splitlines())}")
        truncated = True

    # Redact before the payload crosses into any approval transport. The raw
    # write arguments remain local and are still used only after approval.
    preview = redact_sensitive_text(preview, force=True)
    display = f"<{kind} {operation_mode} to {', '.join(unique_targets)}>\n{preview}"
    display = redact_sensitive_text(display, force=True)
    return {
        "targets": unique_targets,
        "operation": kind,
        "mode": operation_mode,
        "preview": preview,
        "preview_truncated": truncated,
        "content_sha256": digest,
        "display": display,
        "command": display,
    }


def build_replace_approval_payload(targets, old_string: str, new_string: str,
                                   *, replace_all: bool = False) -> dict:
    """Describe a replacement with its exact one/all scope."""
    body = (f"replace_all: {'true' if replace_all else 'false'}\n"
            f"--- old_string ---\n{old_string}\n--- new_string ---\n{new_string}")
    return build_approval_payload(
        targets, "patch", content=body,
        mode="replace-all" if replace_all else "replace-one")

"""Bounded, shared previews for human approval requests."""

import difflib
import hashlib

_DEFAULT_PREVIEW_MAX_CHARS = 1500


def _preview_limit() -> int:
    try:
        from hermes_cli.config import load_config
        value = load_config().get("security", {}).get("approval_preview_max_chars")
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    except Exception:
        pass
    return _DEFAULT_PREVIEW_MAX_CHARS


def build_approval_payload(targets, operation: str, *, content: str | None = None,
                           old_content: str | None = None, new_content: str | None = None,
                           append: bool = False, mode: str | None = None) -> dict:
    """Build one bounded payload used by CLI, gateway, TUI, and desktop surfaces."""
    unique_targets = list(dict.fromkeys(str(target) for target in targets))
    new_value = new_content if new_content is not None else content
    if new_value is None:
        new_value = ""
    if old_content is not None:
        body = "".join(difflib.unified_diff(
            old_content.splitlines(keepends=True), new_value.splitlines(keepends=True),
            fromfile=unique_targets[0] if unique_targets else "before",
            tofile=unique_targets[0] if unique_targets else "after"))
        kind = "patch"
    else:
        body = new_value
        kind = operation
    payload = {
        "targets": unique_targets,
        "operation": kind,
        "mode": mode or ("append" if append else "overwrite"),
    }
    if len(body) <= _preview_limit():
        payload["preview"] = body
        payload["preview_truncated"] = False
    else:
        payload["preview"] = (
            f"{kind} {payload['mode']} to {', '.join(unique_targets)}\n"
            f"size: {len(body)} chars; sha256: {hashlib.sha256(body.encode()).hexdigest()}\n"
            f"lines: +{len(new_value.splitlines())}"
        )
        if old_content is not None:
            removed = len(old_content.splitlines())
            payload["preview"] += f" / -{removed}"
        payload["preview_truncated"] = True
    payload["display"] = (
        f"<{kind} {mode or ('append' if append else 'write')} to {', '.join(unique_targets)}>\n"
        f"{payload['preview']}"
    )
    return payload


def build_replace_approval_payload(targets, old_string: str, new_string: str,
                                   *, replace_all: bool = False) -> dict:
    """Describe the complete requested replacement before any mutation."""
    body = (
        f"replace_all: {'true' if replace_all else 'false'}\n"
        f"--- old_string ---\n{old_string}\n"
        f"--- new_string ---\n{new_string}"
    )
    return build_approval_payload(
        targets,
        "patch",
        content=body,
        mode="replace-all" if replace_all else "replace-one",
    )

"""Bounded disclosure for protected file-write approval prompts."""

import hashlib
import json

_DEFAULT_PREVIEW_MAX_CHARS = 300
_MIN_PREVIEW_MAX_CHARS = 300
_MAX_PREVIEW_MAX_CHARS = 10000


def _preview_limit() -> int:
    try:
        from hermes_cli.config import load_config
        value = load_config().get("security", {}).get("approval_preview_max_chars")
        if isinstance(value, int) and not isinstance(value, bool):
            return min(_MAX_PREVIEW_MAX_CHARS, max(_MIN_PREVIEW_MAX_CHARS, value))
    except Exception:
        pass
    return _DEFAULT_PREVIEW_MAX_CHARS


def build_approval_payload(targets, operation: str, *, content: str | None = None,
                           old_string: str | None = None, new_string: str | None = None,
                           patch: str | None = None, replace_all: bool = False) -> dict:
    """Return a bounded display whose digest identifies the exact submitted proposal text."""
    unique_targets = list(dict.fromkeys(str(target) for target in targets))
    if operation == "write":
        mode, proposal = "overwrite", content or ""
        header = "Overwrite (creates if absent)"
    elif operation == "replace":
        mode = "replace_all" if replace_all else "replace_one"
        proposal = json.dumps({"old_string": old_string or "", "new_string": new_string or "",
                              "replace_all": bool(replace_all)}, ensure_ascii=False, separators=(",", ":"))
        header = "Replace all matches" if replace_all else "Replace one unique match"
    elif operation == "v4a":
        mode, proposal = "v4a", patch or ""
        header = "V4A patch"
    else:
        raise ValueError("unsupported protected-write operation")

    digest = hashlib.sha256(proposal.encode("utf-8")).hexdigest()
    target_json = json.dumps(unique_targets, ensure_ascii=False, separators=(",", ":"))
    path_digest = hashlib.sha256(target_json.encode("utf-8")).hexdigest()
    target_text = ", ".join(unique_targets)
    prefix = (f"{header} to {target_text}\n"
              f"SHA-256 of full {mode} proposal text (UTF-8): {digest}\n")
    budget = _preview_limit()
    if len(prefix) + len(proposal) <= budget:
        body = prefix + proposal
    else:
        # Keep all semantic fields even when the proposal or path list is too large.
        max_paths = max(32, budget - 420)
        shown_targets = target_text if len(target_text) <= max_paths else (
            target_text[:max_paths - 100] + f" … [paths omitted; full path-list SHA-256 {path_digest}]"
        )
        body = (f"{header}; targets ({len(unique_targets)}): {shown_targets}\n"
                f"Proposal: {len(proposal.encode('utf-8'))} UTF-8 bytes, {len(proposal.splitlines())} lines\n"
                f"SHA-256 of full {mode} proposal text (UTF-8): {digest}\n"
                "Preview redacted before display; digest is of the original proposal.")
    display = body[:budget]
    if len(body) > budget:
        # QQ's real text renderer caps command_preview at 300 characters. Keep
        # every transport's protected-write display within that bound and make
        # omission explicit rather than letting a renderer silently truncate it.
        display = (f"{mode}; proposal omitted from preview; full proposal SHA-256 (UTF-8): {digest}")
        if len(display) > budget:
            display = f"{mode}; SHA-256 (UTF-8): {digest}"
    return {"display": display, "operation": operation, "mode": mode,
            "proposal_sha256": digest, "preview_truncated": len(prefix) + len(proposal) > budget}

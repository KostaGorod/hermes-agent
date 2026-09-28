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
    # QQ's native approval text renderer accepts only 300 preview characters.
    # Compact summaries fit that ceiling; retain the configured budget for
    # non-summary payload construction and force a truthful compact fallback.
    budget = _preview_limit()
    fits_transport = len(prefix) + len(proposal) <= min(budget, 300)
    if fits_transport:
        display = prefix + proposal
    else:
        # Preserve scope and proposal identity in a compact fallback that fits
        # QQ's 300-character transport limit.
        display = (f"{mode}; proposal omitted from preview; targets={len(unique_targets)}; "
                   f"ordered target-list SHA-256={path_digest}; "
                   f"proposal SHA-256={digest}")
    return {"display": display, "operation": operation, "mode": mode,
            "proposal_sha256": digest, "preview_truncated": not fits_transport}

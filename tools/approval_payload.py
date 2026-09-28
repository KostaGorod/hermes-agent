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
                           patch: str | None = None, replace_all: bool = False,
                           max_chars: int | None = None) -> dict:
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

    budget = _preview_limit()
    if isinstance(max_chars, int) and not isinstance(max_chars, bool):
        budget = min(budget, max(_MIN_PREVIEW_MAX_CHARS, min(max_chars, _MAX_PREVIEW_MAX_CHARS)))

    digest = hashlib.sha256(proposal.encode("utf-8")).hexdigest()
    from agent.redact import _redact_strict_url_credentials
    display_proposal = _redact_strict_url_credentials(proposal)
    target_json = json.dumps(unique_targets, ensure_ascii=False, separators=(",", ":"))
    path_digest = hashlib.sha256(target_json.encode("utf-8")).hexdigest()
    target_text = ", ".join(unique_targets)

    def _display_for_budget(limit: int) -> tuple[str, bool]:
        full = (f"{header} to {target_text}\n"
                f"SHA-256 of full {mode} proposal text (UTF-8): {digest}\n"
                f"{display_proposal}")
        if len(full) <= limit:
            return full, False

        # A long absolute path can consume the entire preview even when the
        # proposal is small. Keep the exact target identity by digest, but use
        # basenames for readable scope before considering a summary-only view.
        target_names = ", ".join(target.replace("\\", "/").rsplit("/", 1)[-1]
                                 for target in unique_targets)
        compact_prefix = (f"{header} to {target_names} [targets={len(unique_targets)}; "
                          f"ordered target-list SHA-256={path_digest}]\n"
                          f"Proposal SHA-256={digest}\n")
        if len(compact_prefix) + len(display_proposal) <= limit:
            return compact_prefix + display_proposal, False

        summary = (f"{mode}; proposal omitted from preview; targets={len(unique_targets)}; "
                   f"ordered target-list SHA-256={path_digest}; proposal SHA-256={digest}")
        return summary[:limit], True

    display, preview_truncated = _display_for_budget(budget)
    return {"display": display, "operation": operation, "mode": mode,
            "proposal_sha256": digest, "target_list_sha256": path_digest,
            "preview_truncated": preview_truncated}

"""Docs-consistency tests for the standalone custom-providers guide.

The guide (website/docs/user-guide/custom-providers.md) is the single page
that walks through setting up a named custom provider end to end: the
``providers:`` entry schema, the legacy ``custom_providers:`` list and its
v12 auto-migration, the ``/model`` routing forms (triple syntax, vendor
prefix, aliases), and the ``OPENAI_BASE_URL`` trap that mislabels custom
endpoints as ``openai-api``. These tests pin the contract between the guide
and the pages that reference it, so the cross-links can't silently rot and
the required topics can't be dropped in an edit. Docs-to-docs invariants
only — no source reading.
"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE = _REPO_ROOT / "website" / "docs" / "user-guide" / "custom-providers.md"

# Pages that document custom-provider behavior and must point readers at the
# standalone guide. Keys: (path, reason a reader arrives from that page).
_LINKING_PAGES = {
    "website/docs/user-guide/configuring-models.md": "alias section neighbors provider setup",
    "website/docs/reference/faq.md": "context-length answer mentions the legacy list",
    "website/docs/reference/slash-commands.md": "/model row documents the custom:name:model triple",
    "website/docs/integrations/providers.md": "Named Custom Providers is the field reference",
}


def test_guide_exists_and_covers_required_topics() -> None:
    doc = GUIDE.read_text()

    # Named provider entry schema — the fields users must know about.
    for field in (
        "key_env",
        "api:",            # endpoint base URL
        "transport",
        "default_model",
        "context_length",
        "models:",         # per-model overrides
    ):
        assert field in doc, f"guide must document the {field!r} provider field"

    # Legacy list + auto-migration to the providers dict (config v12).
    assert "custom_providers:" in doc
    assert "v12" in doc.lower() or "version 12" in doc.lower()
    # Field renames the migration performs.
    assert "default_model" in doc and "transport" in doc
    assert "api_mode" in doc

    # /model routing forms.
    assert "/model custom:cliproxy:glm-5.3" in doc  # triple syntax
    assert "cliproxy/glm-5.3" in doc                # vendor-prefix routing

    # model.aliases dict form mirrors model_aliases:.
    assert "model.aliases" in doc
    assert "model_aliases:" in doc

    # The OPENAI_BASE_URL trap: env overlay vs providers: entry.
    assert "OPENAI_BASE_URL" in doc
    assert "openai-api" in doc


def test_referencing_pages_link_to_the_guide() -> None:
    for rel in _LINKING_PAGES:
        page = (_REPO_ROOT / rel).read_text()
        assert (
            "/user-guide/custom-providers" in page
        ), f"{rel} ({_LINKING_PAGES[rel]}) must link to the custom-providers guide"


def test_guide_internal_links_resolve() -> None:
    """Every absolute docs link in the guide points at a page that exists.

    Docusaurus fails the build on broken relative links but silently accepts
    unknown absolute ``/section/page`` paths, so guard them here.
    """
    import re

    doc = GUIDE.read_text()
    targets = set(re.findall(r"\]\(/([^)#]+)", doc))
    assert targets, "guide should reference at least one other docs page"

    docs_root = _REPO_ROOT / "website" / "docs"
    known_pages = {
        str(p.relative_to(docs_root)).removesuffix(".md").removesuffix("/index")
        for p in docs_root.rglob("*.md")
    }
    for slug in sorted(targets):
        assert (
            slug in known_pages
        ), f"guide links to /{slug} but no docs page matches"

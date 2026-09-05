"""Contract tests: custom-provider write paths target the ``providers:`` dict.

The legacy ``custom_providers:`` list is read-compatible (see
``get_compatible_custom_providers``) but no Hermes write path may create it.
Wizard saves (``_save_custom_provider``), removals
(``_remove_custom_provider``), and discovery saves
(``_save_discovered_models_to_config``) must all persist the v12+ keyed
``providers:`` shape (#83612).
"""

import subprocess

import yaml

from hermes_cli.config import load_config, save_config


def _raise_menu(*args, **kwargs):
    raise subprocess.CalledProcessError(2, ["tput", "clear"])


class TestSaveCustomProviderWritesProvidersDict:
    def test_wizard_save_writes_providers_dict_not_legacy_list(self, tmp_path, monkeypatch, capsys):
        from hermes_cli.main import _save_custom_provider

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        _save_custom_provider(
            "https://proxy.example.com/v1",
            api_key="sk-test",
            model="glm-5.3",
            context_length=131072,
            name="Cliproxy",
            api_mode="chat_completions",
        )

        raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert "custom_providers" not in raw
        entry = raw["providers"]["cliproxy"]
        assert entry["api"] == "https://proxy.example.com/v1"
        assert entry["api_key"] == "sk-test"
        assert entry["default_model"] == "glm-5.3"
        assert entry["transport"] == "chat_completions"
        assert entry["context_length"] == 131072
        assert entry["models"] == {"glm-5.3": {"context_length": 131072}}

    def test_upsert_dedups_by_base_url(self, tmp_path, monkeypatch):
        """Re-saving the same URL updates in place — no duplicate entry."""
        from hermes_cli.main import _save_custom_provider

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        _save_custom_provider(
            "https://proxy.example.com/v1",
            api_key="sk-test",
            model="glm-5.3",
            name="Cliproxy",
        )
        _save_custom_provider(
            "https://proxy.example.com/v1/",
            api_key="sk-test",
            model="glm-5.4",
            name="Cliproxy",
        )

        raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert len(raw["providers"]) == 1
        entry = raw["providers"]["cliproxy"]
        assert entry["default_model"] == "glm-5.4"

    def test_legacy_entry_same_url_is_retired_on_save(self, tmp_path, monkeypatch):
        """A wizard save onto a legacy-list config migrates that endpoint:
        the keyed entry is written and the legacy twin is removed."""
        from hermes_cli.main import _save_custom_provider

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "_config_version": 39,
                    "custom_providers": [
                        {"name": "Old proxy", "base_url": "https://proxy.example.com/v1"},
                        {"name": "Other", "base_url": "https://other.example.com/v1"},
                    ],
                }
            ),
            encoding="utf-8",
        )

        _save_custom_provider(
            "https://proxy.example.com/v1",
            api_key="sk-test",
            name="Cliproxy",
        )

        raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert raw["providers"]["cliproxy"]["api"] == "https://proxy.example.com/v1"
        # Only the unrelated legacy entry survives; the migrated twin is gone
        # so the endpoint cannot appear twice in the compat view.
        assert raw["custom_providers"] == [
            {"name": "Other", "base_url": "https://other.example.com/v1"}
        ]

    def test_legacy_config_save_survives_full_read_chain(self, tmp_path, monkeypatch):
        """E2E chain: legacy config → wizard save → compatible read view →
        identity resolution. The saved endpoint must appear exactly once,
        under its keyed identity (#83612 user report: provider identity lost
        and the endpoint needing full re-setup after updates)."""
        from hermes_cli.config import get_compatible_custom_providers
        from hermes_cli.main import _save_custom_provider
        from hermes_cli.providers import custom_provider_slug

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "_config_version": 39,
                    "custom_providers": [
                        {
                            "name": "Cliproxy",
                            "base_url": "https://proxy.example.com/v1",
                            "api_key": "old-key",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        _save_custom_provider(
            "https://proxy.example.com/v1",
            api_key="sk-test",
            model="glm-5.3",
            name="Cliproxy",
        )

        compatible = get_compatible_custom_providers()
        matching = [
            entry
            for entry in compatible
            if str(entry.get("base_url", "")).rstrip("/")
            == "https://proxy.example.com/v1"
        ]
        assert len(matching) == 1, "endpoint must appear exactly once after save"
        entry = matching[0]
        # Keyed identity — not the legacy display-name-only identity.
        assert entry["provider_key"] == "cliproxy"
        assert custom_provider_slug(entry["name"], entry["provider_key"]) == (
            "custom:cliproxy"
        )


class TestRemoveCustomProviderDeletesFromProvidersDict:
    def test_removes_keyed_entry(self, tmp_path, monkeypatch):
        from hermes_cli.main import _remove_custom_provider

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setattr("hermes_cli.curses_ui.curses_radiolist", _raise_menu)

        cfg = load_config()
        cfg["providers"] = {
            "cliproxy": {
                "name": "Cliproxy",
                "api": "https://proxy.example.com/v1",
                "default_model": "glm-5.3",
            },
        }
        save_config(cfg)

        monkeypatch.setattr("builtins.input", lambda _prompt="": "1")
        _remove_custom_provider(cfg)

        raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert "providers" not in raw or raw["providers"] == {}
        assert "custom_providers" not in raw

    def test_removes_legacy_entry_from_old_config(self, tmp_path, monkeypatch):
        """Old configs carrying the legacy list: removal still cleans it up."""
        from hermes_cli.main import _remove_custom_provider

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setattr("hermes_cli.curses_ui.curses_radiolist", _raise_menu)

        cfg = load_config()
        cfg["custom_providers"] = [
            {"name": "Local A", "base_url": "http://localhost:8001/v1"},
            {"name": "Local B", "base_url": "http://localhost:8002/v1"},
        ]
        save_config(cfg)

        responses = iter(["1"])
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
        _remove_custom_provider(cfg)

        raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert raw["custom_providers"] == [
            {"name": "Local B", "base_url": "http://localhost:8002/v1"},
        ]


class TestDiscoveredModelsWriteProvidersDict:
    def test_discovery_save_targets_keyed_entry(self, tmp_path, monkeypatch):
        """A successful probe refreshes the matching ``providers:`` entry —
        including auto-discovered entries the wizard wrote — without ever
        creating a legacy list."""
        from hermes_cli.model_switch import _save_discovered_models_to_config

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "providers": {
                        "cliproxy": {
                            "name": "Cliproxy",
                            "api": "https://proxy.example.com/v1",
                            "default_model": "glm-5.3",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

        _save_discovered_models_to_config(
            "https://proxy.example.com/v1",
            ["glm-5.3", "glm-5.4-air"],
        )

        raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert "custom_providers" not in raw
        entry = raw["providers"]["cliproxy"]
        assert entry["models_discovered"] is True
        assert list(entry["models"]) == ["glm-5.3", "glm-5.4-air"]

    def test_discovery_save_does_not_create_legacy_list(self, tmp_path, monkeypatch):
        """No matching entry anywhere: the write is a no-op — it must not
        fabricate a ``custom_providers:`` list (the pre-fix behavior)."""
        from hermes_cli.model_switch import _save_discovered_models_to_config

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump({"model": {"default": "x"}}), encoding="utf-8"
        )

        _save_discovered_models_to_config(
            "https://unknown.example.com/v1", ["model-a"]
        )

        raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert "custom_providers" not in raw
        assert "providers" not in raw

    def test_legacy_list_entry_is_refreshed_in_place(self, tmp_path, monkeypatch):
        """Old configs: a legacy entry's cached catalog still refreshes
        (read compatibility), without extending or creating the list."""
        from hermes_cli.model_switch import _save_discovered_models_to_config

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "custom_providers": [
                        {
                            "name": "Cliproxy",
                            "base_url": "https://proxy.example.com/v1",
                            "model": "glm-5.3",
                            "models": ["stale-model"],
                            "models_discovered": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        _save_discovered_models_to_config(
            "https://proxy.example.com/v1", ["glm-5.3", "glm-5.4-air"]
        )

        raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        entry = raw["custom_providers"][0]
        assert list(entry["models"]) == ["glm-5.3", "glm-5.4-air"]


class TestUpsertKeyDerivation:
    def test_key_matches_v12_migration_slug(self):
        from hermes_cli.config import upsert_custom_provider_to_providers_dict

        cfg = {}
        changed, key = upsert_custom_provider_to_providers_dict(
            cfg, name="Local (localhost:11434)", base_url="http://localhost:11434/v1"
        )
        assert changed is True
        assert key == "local-localhost:11434"

    def test_key_collision_suffixes(self):
        from hermes_cli.config import upsert_custom_provider_to_providers_dict

        cfg = {"providers": {"local": {"api": "http://elsewhere/v1"}}}
        changed, key = upsert_custom_provider_to_providers_dict(
            cfg, name="Local", base_url="http://localhost:11434/v1"
        )
        assert changed is True
        assert key == "local-0"

    def test_url_fallback_when_name_empty(self):
        from hermes_cli.config import upsert_custom_provider_to_providers_dict

        cfg = {}
        changed, key = upsert_custom_provider_to_providers_dict(
            cfg, name="", base_url="https://api.kimi.example.com/coding"
        )
        assert changed is True
        assert key == "api-kimi-example-com"

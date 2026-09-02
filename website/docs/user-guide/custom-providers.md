---
sidebar_position: 6
title: Custom Providers
description: Add any OpenAI- or Anthropic-compatible endpoint as a named provider, route models to it with /model, and avoid the traps that mislabel sessions as openai-api.
---

# Custom Providers

Hermes works with any endpoint that speaks the OpenAI chat-completions protocol (vLLM, llama.cpp server, Ollama, LiteLLM, enterprise gateways, cliproxy-style proxies) or the Anthropic messages protocol. You register the endpoint once as a **named provider** under `providers:` in `~/.hermes/config.yaml`, and every surface afterwards — `hermes model`, the `/model` slash command, `hermes chat --model`, the dashboard picker — can route to it like any built-in provider.

This page is the standalone setup guide. For the catalog of first-party providers, see [Providers](/integrations/providers).

## Quick start

One endpoint, one entry. This registers a proxy serving GLM models:

```yaml
# ~/.hermes/config.yaml
providers:
  cliproxy:
    api: https://proxy.example.com/v1
    key_env: CLIPROXY_API_KEY
    transport: chat_completions
    default_model: glm-5.3

model:
  provider: custom:cliproxy
  default: glm-5.3
```

The key goes in `~/.hermes/.env`:

```bash
CLIPROXY_API_KEY=sk-...
```

Then, in a running session:

```
/model custom:cliproxy:glm-5.3
```

or persist the default with `hermes model` — named custom endpoints appear in the interactive picker.

A keyless local server (Ollama, llama.cpp) needs no `key_env` at all:

```yaml
providers:
  local:
    api: http://localhost:8080/v1
```

When an entry defines no credential, requests carry `no-key-required` — the value keyless local servers expect.

## The full entry schema

Every key below is optional except `api`:

```yaml
providers:
  cliproxy:
    api: https://proxy.example.com/v1   # endpoint base URL (aliases: base_url, url)
    name: "Cliproxy (fastlane)"          # display name; defaults to the dict key
    key_env: CLIPROXY_API_KEY            # env var holding the API key
    # api_key: sk-...                    # inline literal, or "${VAR}" indirection
    # key_cmd: "my-auth-cli print-token" # command that prints a short-lived token
    transport: chat_completions          # chat_completions | anthropic_messages | codex_responses
    default_model: glm-5.3               # model used when you pick the provider without naming one
    context_length: 131072               # when auto-detection can't be verified or trusted
    models:                              # per-model overrides
      glm-5.3:
        context_length: 200000
      glm-5.3-air:
        context_length: 131072
    # discover_models: false             # don't probe /v1/models; keep the explicit models: list
    # extra_body: {...}                  # provider-specific request fields, merged into every request
    # extra_headers: {...}               # extra HTTP headers
    # ssl_ca_cert: /path/to/ca.pem       # custom CA bundle
    # ssl_verify: false                  # disable TLS verification
    # request_timeout_seconds: 600       # per-provider request timeout
    # rate_limit_delay: 0.5              # delay between requests, seconds
```

Credential precedence on one entry: an explicit `--api-key` flag wins for that invocation. Otherwise, `key_cmd` is preferred when present and mints a fresh token for providers whose credentials expire mid-session (SSO/IAM brokers); without `key_cmd`, an inline `api_key` (literal or `"${VAR}"`) is preferred over `key_env`. See [command-minted credentials](/integrations/providers#command-minted-credentials-key_cmd). When an entry sets none of these, the request goes out with `no-key-required`.

`transport` says which protocol the endpoint speaks. `chat_completions` (OpenAI dialect) is the default and what most proxies want. `anthropic_messages` is for Anthropic-compatible proxies — the `hermes model` → Custom Endpoint wizard prompts for it explicitly and persists your answer; URLs containing `/anthropic` auto-detect when the field is blank. `codex_responses` speaks the Codex responses protocol.

The wizard in `hermes model` (choose **Custom Endpoint**) walks through URL, API mode, and per-model context lengths, and writes the entry for you. Editing `config.yaml` directly is equally supported.

For a vision-capable model that isn't in models.dev, add its capability metadata under `model_metadata` so Hermes can route images natively instead of through the vision pre-processor. For example, set `model_metadata.<provider>.<model>.supports_vision: true`; see [Configuration](./configuration.md) for the complete capability override shape.

## Switching models on a custom provider

Four ways to route a session to your endpoint, all using the `cliproxy` entry above.

**Triple syntax.** `/model custom:name:model` picks the named provider and the model in one go:

```
/model custom:cliproxy:glm-5.3
/model custom:local:qwen3.5:27b
```

**Vendor-prefix routing.** The provider's dict key doubles as a routing prefix: `name/model` sends the model to that provider, stripped of the prefix:

```
/model cliproxy/glm-5.3
```

This routing (added in #100586) fires only when you actually defined a `providers:` block with that name. Built-in vendor slugs like `google/gemini-2.5-flash` and `deepseek/deepseek-chat` keep their existing behavior — they are aggregator-native and stay on the catalog/OpenRouter path unless you defined a matching provider block. And when your current provider is a routing aggregator such as OpenRouter, an aggregator-native slug is never stolen by a same-named `providers:` block: `anthropic/claude-opus-4.6` stays on OpenRouter even if you also have a `providers.anthropic` entry.

**Direct alias.** A short name for the exact model+provider+endpoint triple, defined in `model_aliases:`:

```yaml
model_aliases:
  glm:
    model: glm-5.3
    provider: cliproxy
```

Then `/model glm`. The alias can carry its own `base_url` and its own credential (`api_key` or `key_env`); when it sets neither, the key is resolved from the alias **host** — never inherited from whichever provider was active before the switch — so one provider's secret can't leak to another provider's wire (#83612).

**Model aliases, short form.** `model.aliases` accepts the same dict shape, plus plain string values:

```yaml
model:
  aliases:
    glm:
      model: glm-5.3
      provider: cliproxy
    qwen: local/qwen3.5:27b     # string form: provider/model
```

Dict entries use the same fields as `model_aliases:` (`model`, `provider`, `base_url`) and fall back to the current `model.provider` when the dict entry omits `provider`. String values are `provider/model` and can be written from the shell (`hermes config set model.aliases.qwen local/qwen3.5:27b`), but can't carry a custom `base_url`. Both forms feed the same loader (`hermes_cli/model_switch.py`); entries declared in `model_aliases:` take precedence over `model.aliases:` entries with the same name. User aliases shadow built-in short names (`sonnet`, `kimi`, `opus`, ...).

:::note Mid-session switches reset the prompt cache
The cache key includes the model serving the request, so any mid-conversation switch — including to a custom provider — means the next message re-reads the whole conversation at full input price instead of the discounted cached rate. Switch early or right after starting a fresh session.
:::

## Legacy `custom_providers:` list, and migration to `providers:`

Older configs declared custom endpoints as a top-level list:

```yaml
# legacy — still read, auto-migrated to providers: (config v12)
custom_providers:
  - name: Cliproxy
    base_url: https://proxy.example.com/v1
    api_mode: chat_completions
    model: glm-5.3
```

Hermes still reads the legacy list, and `hermes update` auto-migrates it to the `providers:` dict (config version 12) — each entry becomes a named provider keyed by a kebab-case version of its display name. Field names change in the migration: legacy `model` becomes `default_model`, and legacy `api_mode` becomes `transport`.

If you maintain the legacy list by hand, expect each update to convert it. Prefer editing `providers:` directly; the runtime accepts both, but the dict form is the current format and what the migration writes.

## The OPENAI_BASE_URL trap

The most common way a custom endpoint ends up mislabeled: a leftover `OPENAI_BASE_URL` (and often `OPENAI_API_KEY`) in `~/.hermes/.env` from an older setup. That variable belongs to the built-in `openai-api` provider — it is that provider's `base_url_env_var` — so with it set, sessions get labeled `provider: openai-api` instead of your named provider, and auxiliary models on `provider: auto` route to the old endpoint even after you switch the main model away.

The fix is to define the endpoint as a `providers:` entry and remove the env vars from `~/.hermes/.env`:

```bash
# remove from ~/.hermes/.env:
#   OPENAI_BASE_URL=...
#   OPENAI_API_KEY=...
```

`OPENAI_BASE_URL` is honored for exactly one thing: overriding the endpoint of the first-party `openai-api` provider when you genuinely mean "OpenAI API, but at a different URL". If you're pointing it at a proxy or local server, that's a custom provider, and it belongs under `providers:` instead.

Hermes cleans this up on its own in two places: switching to any provider other than `custom`/`custom:...` clears a stale `OPENAI_BASE_URL` from `.env` (#5161), and `hermes setup` / config migrations clear stale `.env` entries.

:::warning `model.provider` keeps reverting after updates
`hermes update` snapshots `config.yaml` before updating and restores `model.provider`, `model.default`, `model.base_url`, `model.api_key`, and `moa:` if the update rewrites them (#64160). The restore keeps what you had before the update. If those keys keep flip-flopping, an update/repair cycle is rewriting them while the safety net restores the snapshot values — set the provider once more after the update (`/model ... --global` or `hermes model`) so the post-update snapshot and live config agree, and the flip-flopping stops.
:::

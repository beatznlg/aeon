# AEON OS Plugin Marketplace

AEON OS ships with a plugin marketplace that turns the platform into an
extensible ecosystem: workspaces can browse a catalog, install, configure,
enable, disable, and invoke plugins without leaving the product.

## What a plugin is

A **plugin** is a capability package described by a manifest:

| Field          | Meaning                                                            |
| -------------- | ------------------------------------------------------------------ |
| `id`           | Slug identifier (`^[a-z0-9][a-z0-9-]{1,63}$`)                      |
| `name`         | Display name                                                        |
| `version`      | Semver-like version (`1.2` or `1.2.3`)                              |
| `description`  | What the plugin does                                                |
| `author`       | Publisher                                                            |
| `category`     | One of: `ai`, `analytics`, `automation`, `communication`, `data`, `devops`, `integration`, `productivity`, `security`, `sector` |
| `icon`         | Emoji or short glyph                                                 |
| `permissions`  | Subset of `read`, `write`, `execute`, `network`, `notify`, `admin`  |
| `entry_points` | Map of entry name → description (each requires `execute`)           |
| `config_schema`| Declarative config validation schema                                |
| `verified`     | Whether AEON Labs verified the plugin                               |

The shipped catalog (`aeon_marketplace.BUILTIN_PLUGIN_CATALOG`) contains 71
plugins across security, analytics, sector (health, finance, utilities,
transport, retail, telecom, agriculture, education, public safety, real estate,
professional services), data, productivity, communication, devops, ai, and
integration categories. The platform-operations set also covers trace
observability, MCP tool bridging, compliance evidence, connector health,
developer quality, and data quality checks.

## Agent discovery

Agents see installed plugins automatically. Two mechanisms make plugin entry
points discoverable inside the kernel without hard-coding plugin ids:

1. **`list_plugins` kernel tool** — agents can call `list_plugins` to enumerate
   the plugins installed and enabled in their workspace, along with every
   entry point they may invoke.
2. **System-prompt injection** — when an agent runs (`ReflectiveAgent.act`),
   its system prompt includes an *Installed plugins* block listing the
   workspace's callable plugins and entry points, so the model knows what is
   available before it even calls a tool.

Discovery is gated identically to execution: a plugin must be installed in the
workspace, enabled, and declare the `execute` permission. The discovery
payload never includes workspace config values or credentials. Workspace
scoping is bound to the agent at creation time in `aeon_server.get_agent`
(agents keyed `ws-<workspace_id>` resolve discovery to that workspace); the
kernel defaults to the `AEON_WORKSPACE_ID` env var, then `default`.

## How it works

```
Next.js /os/marketplace  ──▶  /api/os/marketplace (proxy)
                                   │
                                   ▼
                     /marketplace/plugins/... (Flask)
                                   │
                                   ▼
              aeon_marketplace_routes.py ──▶ aeon_marketplace.MarketplaceManager
                                                    │
                                                    ▼
                              AEON_ROOT/marketplace/installs.json
```

- Catalog browsing requires the `VIEWER` workspace role.
- Install / uninstall / enable / disable / configure / run require `OPERATOR`.
- Every lifecycle mutation is written to the tamper-evident audit log
  (`module=marketplace`).
- Installs are keyed by `(workspace_id, plugin_id)`; the workspace is always
  derived from the authenticated caller, so tenants cannot see or mutate each
  other's installs.

### API surface

| Method | Route                                   | Purpose                          |
| ------ | --------------------------------------- | -------------------------------- |
| GET    | `/marketplace/plugins`                  | Catalog + install state          |
| GET    | `/marketplace/installed`                | Installed plugins                |
| GET    | `/marketplace/plugins/<id>`             | Single manifest                  |
| POST   | `/marketplace/plugins/<id>/install`     | Install (validates config)       |
| POST   | `/marketplace/plugins/<id>/uninstall`   | Remove                           |
| POST   | `/marketplace/plugins/<id>/enable`      | Enable                           |
| POST   | `/marketplace/plugins/<id>/disable`     | Disable                          |
| POST   | `/marketplace/plugins/<id>/config`      | Update config (validated)        |
| POST   | `/marketplace/plugins/<id>/run`         | Invoke an entry point            |

## Security model

- **Manifest validation fails closed.** Unknown permissions, unsafe ids,
  malformed versions, and undeclared config keys are rejected
  (`validate_manifest`, `validate_config` in `aeon_marketplace.py`).
- **Execution is gated.** `run_entry` requires the plugin to be installed,
  enabled, to declare `execute`, and the entry to exist on the manifest.
- **Built-ins are deterministic and network-free.** Shipped entry points run
  handlers inside the module and never touch the network or execute external
  code.
- **No arbitrary third-party code execution — by design.** Untrusted plugin
  code must run in a separately deployed sandbox (container / gVisor /
  Firecracker) behind a signed-manifest pipeline before it can be enabled for
  customer workloads. Until then, external plugins are catalog + lifecycle
  only.

## Roadmap to a public marketplace

1. Plugin **publishing** API with signed manifests and AEON Labs review.
2. Sandboxed **third-party runtime** for entry-point execution.
3. Version **upgrade / rollback** with compatibility checks.
4. **Usage metering and billing** for paid plugins (Stripe already wired).
5. **Offline / air-gapped catalogs** for government and critical-infrastructure
   deployments (permission review, SBOM, signing).
6. **Marketplace analytics** (installs, runs, health) surfaced to publishers.

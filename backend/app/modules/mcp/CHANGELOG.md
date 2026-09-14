# Changelog — mcp module

## Unreleased

### Write exposure via `patients:write` scope

- Adds `patients.create_patient` to the curated server allowlist
  (`server.CURATED_TOOLS`). The token's scopes are translated to the RBAC
  grants the tools declare (`_SCOPE_TO_PERMISSION`); `tools/list` only
  surfaces tools the token could call, and every `tools/call` enforces the
  translated grants at the registry chokepoint.
- `auth.py`: the middleware gate now accepts any token carrying an
  MCP-supported scope (`MCP_SCOPES` = `patients:read` / `patients:write`)
  instead of hard-requiring `patients:read`.

### Initial MCP bridge (registration + transport)

- New optional `mcp` module (`auto_install=False`, `removable=True`,
  `depends=["patients", "integrations"]`). Transport-only: no models,
  no tables.
- Ships a single no-op Alembic revision (`mcp_0001`, own branch,
  empty upgrade/downgrade) so `removable=True` has an isolated branch
  and uninstall gets a `base_revision` to allow — same pattern as
  `recall_reminders`. Registered in `backend/alembic.ini`
  `version_locations` (M1 guard).
- Mounts the MCP `StreamableHTTPSessionManager` under `/api/v1/mcp/`
  (streamable-HTTP, `json_response=True`). A lazy ASGI wrapper starts
  the manager's `run()` task on first request — Starlette never runs a
  mounted sub-app's lifespan.
- Bare `/api/v1/mcp` (no trailing slash) 307-redirects to the slashed
  endpoint; MCP SDK clients follow it preserving method/body.

### Auth & identity

- `DentalPinAuthMiddleware` (ASGI) gates the whole surface with
  `Authorization: Bearer dp_...` (integrations API tokens via
  `IntegrationsService.authenticate_token`), enforcing the
  `patients:read` scope. 401/403 JSON, no manager touched on failure.
- Per-message identity (clinic, token, scopes) is stashed on the
  starlette request scope and read back in `tools/call`.

### Curated tool surface

- `server.py` re-exposes `patients.search_patients` and
  `patients.get_patient` through the shared `tool_registry` chokepoint —
  guardrails, RBAC, validation and audit log still enforced, no logic
  duplicated. (Initially read-only; `create_patient` shipped with the
  `patients:write` scope — see "Write exposure" above. `update_patient`
  remains out.)
- Deterministic per-token `agents`/`agent_sessions` rows (UPSERT) so
  the audit trail's FKs resolve and one token's calls group under one
  agent/session.

### Tests & docs

- `tests/modules/mcp/test_server.py` — full contract: 401 gate,
  session initialize, curated tools/list, `search_patients` +
  `get_patient`, revoked-token rejection (single process-wide session).
- Module CLAUDE.md + CHANGELOG, `docs/technical/mcp/` overview/events/
  permissions, ADR 0033, glossary entry, catalogs regenerated.
- `docs/technical/mcp/overview.md` "Trying it out": token-minting steps
  + `dp_` token lifecycle (no expiry — revoke via
  `POST /tokens/{id}/revoke`, `last_used_at` tracking), a raw JSON-RPC
  smoke sequence, a Postman walkthrough (session-id capture via Tests
  script — validated live against the demo backend), and Claude,
  Desktop/Claude Code + Kilo Code connection config (`.mcp.json`,
  `claude mcp add`, `kilo.jsonc` `skills.paths` reuse of
  `.claude/skills/`).
- `.claude/skills/mint-dp-token/SKILL.md` — Claude Code skill that mints,
  verifies, and revokes `dp_` tokens via the integrations API (login →
  `POST /integrations/tokens`). `.claude/` is now ignored only for
  local files (`settings.local.json`); skills ship with the repo.
- `.kilo/kilo.jsonc` — project Kilo Code MCP config for `dentalpin`
  (remote streamable-HTTP + `Authorization: Bearer dp_...` header, token
  placeholder). Kilo reuses the single `mint-dp-token` skill from
  `.claude/skills/` via `skills.paths` (no `.kilo/skills/` duplicate, no
  undocumented compatibility toggle). Overview doc gains a Kilo section
  (§5, audit trail → §6).
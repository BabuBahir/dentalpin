---
module: mcp
last_verified_commit: d9d8ad97
---

# mcp — overview

Model Context Protocol bridge. Exposes a curated, read-only slice of
DentalPin's agent tools to external AI clients (Claude Desktop, Cursor,
any MCP-compatible host) over the standard streamable-HTTP transport at
`/api/v1/mcp/`.

## What it is

A transport-only module (`BaseModule` with no models, no tables, no
Alembic branch). It mounts the MCP Server SDK's
`StreamableHTTPSessionManager` behind ASGI auth middleware and two
handlers:

- `tools/list` — the curated allowlist (`server.CURATED_TOOLS`):
  `patients.search_patients`, `patients.get_patient`.
- `tools/call` — every call is delegated to
  `tool_registry.call(ctx, "patients.<name>", args)`, the **same single
  chokepoint** internal agents use: guardrails, RBAC permission check,
  Pydantic validation, and the audit log all still run.

Tools are *not* reimplemented. The MCP layer is pure plumbing — a new
transport over existing tool handlers.

## Auth

No JWT, no staff session. `DentalPinAuthMiddleware` (`auth.py`) requires
`Authorization: Bearer dp_...` — the API tokens the integrations module
issues (`integrations.tokens.*`, `ApiToken` rows, SHA-256 hashed). It
enforces the token's `patients:read` scope (403 otherwise) and stashes
the resolved identity (clinic id, token id, scopes) on the request scope
for the tool handler to read per message.

Unauthenticated / revoked-token traffic is rejected with 401 *before*
the session manager task ever starts.

## Endpoint shape

- Real surface: `/api/v1/mcp/` (trailing slash). The app sets
  `redirect_slashes=False`, so the bare path would 404 — the router adds
  a tiny 307 redirect at `/api/v1/mcp` that MCP SDK clients follow while
  preserving method + POST body.
- Responses are `application/json` (`json_response=True`): the surface
  is pure RPC (no server→client notifications yet), so there is nothing
  the SSE channel would carry.
- Client URL to configure: `http://<host>/api/v1/mcp/`,
  headers `Authorization: Bearer dp_...`.

## Trying it out

Prerequisites: the `mcp` module is installed (check
`./bin/dentalpin modules list` shows `mcp ... installed`), the backend
container is up (`0.0.0.0:8000->8000`), and the demo DB is seeded. The
steps below were validated against a live demo install.

### 1. Mint an API token

MCP does **not** use the staff JWT — it needs a `dp_` API token from the
integrations module, scoped `patients:read`. Log in once as an admin to
issue it (the token prints **once**; store it):

```bash
# Admin login → access token (OAuth2 form, not JSON)
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=admin@demo.clinic&password=demo1234"
# → {"access_token":"...jwt...","token_type":"bearer",...}

# Mint a read-only API token with that JWT
curl -s -X POST http://localhost:8000/api/v1/integrations/tokens \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name":"mcp-test","scopes":["patients:read"]}'
# → {"data":{"token":"dp_...", ...}}   ← save it
```

Error surface on the MCP endpoint (both return JSON, `www-authenticate:
Bearer`):

- missing / invalid / revoked token → `401 {"error":"invalid_token",...}`;
- token without the `patients:read` scope → `403
  {"error":"insufficient_scope","error_description":"Required scope:
  patients:read"}`.

### 2. MCP Inspector (GUI, quickest)

```bash
npx @modelcontextprotocol/inspector    # needs Node ^22.7.5
```

Open the URL it prints (it embeds an API token for the inspector UI,
e.g. `http://127.0.0.1:6274?MCP_INSPECTOR_API_TOKEN=...`), then in the
settings (gear icon):

- **Transport**: Streamable HTTP
- **URL**: `http://localhost:8000/api/v1/mcp/`
- **Authentication**: header name `Authorization`, bearer token
  `dp_...`

Connect, list tools (exactly `search_patients` and `get_patient`), and
run each — e.g. `search_patients` with `{"query": "Daniel Garcia"}`.

> **`{"ok":false,"kind":"transport_error","error":"fetch failed"}`**
> means the Inspector's Node process could not reach the configured URL
> at the network level — not an auth, CORS, or protocol problem. Verify
> the URL is exactly `http://localhost:8000/api/v1/mcp/` (a missing
> Authorization header instead surfaces as `auth_challenge`, and a bad
> token as the server's `invalid_token` 401). A bare-path `.../mcp`
> without the trailing slash is fine (307 redirect), but any unreachable
> host/port/scheme (the Inspector's built-in example URL, the frontend
> port `3000`, `https://`, ...) reproduces exactly this error. If the
> Inspector runs on a different machine than the backend, replace
> `localhost` with the backend host's LAN IP.

### 3. Raw JSON-RPC smoke test (no GUI)

Streamable HTTP is a sessioned handshake: every request carries
`Authorization`, and the `initialize` response returns a
`Mcp-Session-Id` header that all later POSTs must echo.

```bash
BASE=http://localhost:8000/api/v1/mcp/
TOK=dp_...
CT='Content-Type: application/json'
ACCEPT='Accept: application/json, text/event-stream'

# 1) initialize — capture Mcp-Session-Id from the response headers
curl -s -D - -X POST "$BASE" -H "Authorization: Bearer $TOK" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'

# 2) notifications/initialized + tools/list (reuse SID + $TOK)
SID=<Mcp-Session-Id from step 1>
curl -s -X POST "$BASE" -H "Authorization: Bearer $TOK" -H "Mcp-Session-Id: $SID" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
curl -s -X POST "$BASE" -H "Authorization: Bearer $TOK" -H "Mcp-Session-Id: $SID" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# 3) tools/call — search, then get_patient with an id from the result
curl -s -X POST "$BASE" -H "Authorization: Bearer $TOK" -H "Mcp-Session-Id: $SID" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_patients","arguments":{"query":"Daniel Garcia","limit":5}}}'
curl -s -X POST "$BASE" -H "Authorization: Bearer $TOK" -H "Mcp-Session-Id: $SID" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_patient","arguments":{"patient_id":"<uuid>"}}}'
```

Responses are `application/json` (see `json_response=True` above) with
`structuredContent` plus a human-readable `text` member. On Windows
PowerShell, inline `-d` bodies get their quotes mangled — write each body
to a temp file and pass `--data "@body.json"` instead.

### 4. Postman

Same handshake, five POSTs. Create a Postman collection with these
requests (all to `http://localhost:8000/api/v1/mcp/` — keep the trailing
slash; the bare path 307-redirects and Postman may not follow it).

Common settings per request:

| Setting | Value |
|---------|-------|
| Method | `POST` |
| URL | `http://localhost:8000/api/v1/mcp/` |
| Authorization | `Bearer dp_...` (unknown/revoked → 401; missing `patients:read` scope → 403) |
| Headers | `Content-Type: application/json`, `Accept: application/json, text/event-stream`, and (steps 2–5) `Mcp-Session-Id: {{SID}}` |
| Body | `raw` → `JSON` |

1. **initialize** — `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"postman","version":"1.0"}}}`. The response *header* `Mcp-Session-Id` starts the session; capture it automatically with a **Tests** script:

   ```js
   pm.test('capture session id', () => {
     const sid = pm.response.headers.get('Mcp-Session-Id');
     pm.expect(sid).to.not.be.undefined;
     pm.collectionVariables.set('SID', sid);
   });
   ```

   then use `{{SID}}` in the `Mcp-Session-Id` header of the requests below.

2. **notifications/initialized** — `{"jsonrpc":"2.0","method":"notifications/initialized"}`.

3. **tools/list** — `{"jsonrpc":"2.0","id":2,"method":"tools/list"}` → returns exactly `search_patients` + `get_patient` with their input schemas.

4. **tools/call → search_patients** — `{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_patients","arguments":{"query":"Daniel Garcia","limit":5}}}` → a patient list in `result.structuredContent`.

5. **tools/call → get_patient** — `{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_patient","arguments":{"patient_id":"<uuid from step 4>"}}}` → the patient's details.

If a request fails a session must be re-established: re-run step 1 (new `Mcp-Session-Id`).

### 5. Verify the audit trail

Every `tools/call` creates deterministic per-token
`agents`/`agent_sessions` rows (`type = 'external_mcp'`) and an
`agent_audit_logs` row, so a token's whole history groups under one
agent/session:

```bash
docker compose exec -T db psql -U dental -d dental_clinic \
  -c "SELECT name, type FROM agents WHERE type='external_mcp' ORDER BY created_at DESC LIMIT 5;" \
  -c "SELECT count(*) FROM agent_audit_logs;"
```

## Manager lifecycle

Starlette never runs the lifespan of a *mounted* sub-app, and the MCP
manager's `run()` asynccontextmanager is what spawns the per-session
task group. `router._LazyManagedMCPApp` starts `manager.run()` in a
background task on the first request and keeps it for the process
lifetime. Each `build_mcp_router()` call builds a fresh manager — the
manager is single-use, so a router instance is one-shot per process
(which tests rely on: the endpoint is exercised once per process).

## Audit trail

`tool_registry.call` writes `agent_audit_logs` rows keyed on
`agent_id`/`session_id` (both FKs). The MCP handler derives both
deterministically from the API token (`uuid5` over fixed namespaces)
and UPSERTs the corresponding `agents` (type `external_mcp`) and
`agent_sessions` rows before the call, so:

- every tool invocation from one token groups under one agent/session;
- the ids are stable across restarts;
- nothing in the registry required change to serve MCP traffic.

## Tenancy

The clinic comes from the token's own `clinic_id` (no
`get_clinic_context`). The underlying tools filter by `ctx.clinic_id`,
so a token can only ever reach its own clinic's data. The agent/session
rows are clinic-scoped too.

## Constraints

- Depends on `patients` (tool owners) and `integrations` (token
  issuance/verification). No other cross-module imports.
- No staff RBAC permissions (`get_permissions()` → `[]`): this boundary
  is scope-based, not role-based.
- The curated set is deliberately closed and read-only; expanding it
  requires a matching token scope (`patients:write`, ...) to exist in
  `integrations/triggers.py` `SUPPORTED_TOKEN_SCOPES`.

See [`./permissions.md`](./permissions.md) and
[`./events.md`](./events.md) for the full detail, and
`backend/app/modules/mcp/CLAUDE.md` for the design rationale.
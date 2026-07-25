# `@aeon/sdk`

TypeScript SDK for the [AEON OS](https://github.com/beatznlg/aeon) API.

## Installation

```bash
npm install @aeon/sdk
```

## Quick Start

```typescript
import { AeonClient } from "@aeon/sdk";

const client = new AeonClient({
  baseUrl: "https://your-aeon-backend.up.railway.app",
  apiKey: "aeon_...",
});

const health = await client.health();
console.log(health);

const reply = await client.chat("What is the integral of x^2?");
console.log(reply.data);
```

## Authentication

The SDK supports two authentication methods:

- **API key** via `apiKey` option or `X-API-Key` header
- **JWT token** via `token` option or `Authorization: Bearer ...` header

You can also log in with email/password:

```typescript
const client = new AeonClient({ baseUrl: "..." });
await client.login("admin@aeon.local", "admin123");
const me = await client.me();
```

## Environment Variables

When running in Node.js, the SDK reads:

| Variable | Description |
|---|---|
| `AEON_PYTHON_URL` | Default base URL for the backend |

## API Coverage

- Health (`health`, `live`, `ready`, `detailedHealth`)
- Auth (`login`, `register`, `me`)
- Workspaces & Chat (`listWorkspaces`, `chat`, `workspaceHistory`)
- Apps (`appChat`, `appTick`)
- Workflows (`listWorkflows`, `createWorkflow`, `runWorkflow`, ...)
- Swarm (`runSwarm`)
- API Keys (`listApiKeys`, `createApiKey`, `revokeApiKey`)
- Integrations (`listIntegrations`, `createIntegration`, `runIntegration`)
- Billing (`getBillingStatus`, `recordUsage`)
- LLM (`listLlmProviders`, `switchLlmProvider`)
- RAG (`listKnowledgeBases`, `createKnowledgeBase`, `queryKnowledgeBase`)

For the full API surface, see `/openapi.json` or `/docs` on a running AEON backend.

## License

MIT

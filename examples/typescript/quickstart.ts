/**
 * AEON TypeScript SDK Quickstart
 *
 * Run with:
 *   cd sdk/typescript && npm install && npm run build
 *   cd ../../examples/typescript
 *   npx ts-node quickstart.ts
 */

import { AeonClient } from "@aeon/sdk";

const BASE_URL = process.env.AEON_PYTHON_URL || "http://localhost:5000";
const EMAIL = process.env.AEON_EMAIL || "admin@aeon.local";
const PASSWORD = process.env.AEON_PASSWORD || "admin123";

async function main() {
  const client = new AeonClient({ baseUrl: BASE_URL });

  // Health check
  console.log("Health:", await client.health());

  // Log in (or use an API key)
  const login = await client.login(EMAIL, PASSWORD);
  console.log("Logged in as:", (login as any).user.email);

  // Chat
  const reply = await client.chat("What is the integral of x^2?");
  console.log("Chat reply:", reply);

  // List workspaces
  console.log("Workspaces:", await client.listWorkspaces());

  // List LLM providers
  console.log("LLM providers:", await client.listLlmProviders());

  // Create a workflow
  const wf = await client.createWorkflow({
    name: "Example Workflow",
    nodes: [{ id: "start", type: "agent", prompt: "Hello!" }],
    edges: [],
  });
  console.log("Created workflow:", wf);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});

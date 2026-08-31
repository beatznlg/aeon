# AEON OS — Complete User Guide

## 1. What AEON OS is

AEON OS is an AI-agent orchestration platform for companies that want one workspace for AI assistants, workflows, knowledge, model routing, integrations, automation, monitoring, and team operations.

## 2. Who can use AEON

AEON is designed to be configurable across industries rather than tied to one business model.

### Software / technology
- Support agents
- Engineering assistants
- Documentation and knowledge search
- Release and incident workflows

### Professional services
- Research assistants
- Proposal drafting
- Client knowledge bases
- Project workflows

### Finance / accounting
- Internal policy assistants
- Document retrieval
- Reporting workflows
- Approval and audit workflows

### Legal
- Matter knowledge bases
- Contract/document review workflows
- Research assistants
- Controlled internal automation

### Healthcare / life sciences
- Internal knowledge retrieval
- Administrative assistants
- Research workflows
- Strict access controls and audit requirements

### Retail / e-commerce
- Customer support
- Product knowledge assistant
- Marketing workflows
- Order/support automation

### Manufacturing / logistics
- SOP assistants
- Operations workflows
- Maintenance knowledge
- Supply-chain reporting

### Hospitality / restaurants
- Operations assistant
- Menu/SOP knowledge
- Staff workflows
- Marketing and customer-support automation

### Education
- Course knowledge assistants
- Administrative automation
- Research workflows
- Student-support tooling

### Agencies / media
- Multi-client workspaces
- Content workflows
- Research and knowledge assistants
- Approval pipelines

## 3. Core benefits

- **One AI operating layer:** organize agents, workflows and knowledge in one system.
- **Model flexibility:** route work between supported LLM providers instead of locking the company to one model.
- **Knowledge grounding:** connect company documents and knowledge to AI workflows.
- **Automation:** turn repeatable processes into workflows and background jobs.
- **Multi-tenant architecture:** separate organizations/workspaces and enforce permissions.
- **Observability:** monitor application health, jobs and operational behavior.
- **Billing readiness:** support productized AI services and subscription workflows.
- **Self-hosting:** the production architecture can run entirely inside the company's Google Cloud environment.
- **Extensibility:** APIs, integrations and agent protocols allow AEON to grow with the business.

## 4. First-time setup

1. Deploy AEON to Google Cloud using the repository's GCP deployment guide.
2. Configure production secrets through the deployment environment/secret manager.
3. Set the public HTTPS domain.
4. Run database migrations.
5. Confirm `/health` and readiness checks.
6. Register the first administrator account.
7. Create the organization's workspace.
8. Configure AI provider credentials.
9. Create a knowledge base and upload approved documents.
10. Create an assistant/agent.
11. Build a workflow and test it with non-production data.

## 5. Login, registration and demo

### Register
Use the registration screen to create an account. Production deployments should use a real company email and a strong password.

### Login
Enter the registered email and password. After authentication, AEON creates the application session and opens the authenticated workspace.

### Demo
Demo access is intentionally opt-in. Set the demo environment variables only when a demonstration account is required. Never commit demo credentials to Git.

Recommended production setting:

`AEON_DEMO_ENABLED=false`

## 6. Recommended company onboarding

Start with one department and one measurable workflow.

Example:

**Customer support** → upload support documentation → create support assistant → define escalation workflow → test → measure resolution time → expand.

Then introduce additional departments and workflows after permissions, logging and business acceptance have been verified.

## 7. Knowledge bases

Use knowledge bases for information the AI should retrieve from company-controlled sources.

Recommended process:

1. Collect authoritative documents.
2. Remove obsolete or duplicate versions.
3. Upload the approved set.
4. Configure retrieval settings.
5. Test representative questions.
6. Review citations/answers.
7. Establish an owner for ongoing updates.

## 8. Agents and assistants

An agent should have a clearly defined purpose, allowed tools, knowledge sources, model policy and escalation behavior.

Good agent definition:
- Purpose
- Audience
- Inputs
- Allowed actions
- Knowledge sources
- Output format
- Failure behavior
- Human approval requirements

## 9. Workflows

Use workflows for repeatable multi-step business processes.

Example:

`New request → classify → retrieve knowledge → AI analysis → validation → human approval → action → audit/log`

Keep high-impact actions behind explicit authorization or human approval.

## 10. Teams and permissions

Create workspaces around organizations or business units. Give users the minimum permissions required for their role. Review administrator access regularly.

## 11. Production operations

Operators should monitor:
- frontend availability
- API health/readiness
- PostgreSQL health and storage
- Redis availability
- Celery worker status
- scheduled jobs
- backup success
- application errors
- resource utilization

## 12. Security checklist

- Use strong unique production secrets.
- Never commit `.env` files or private keys.
- Keep PostgreSQL and Redis private.
- Expose only HTTPS publicly.
- Use least-privilege accounts.
- Rotate credentials periodically.
- Back up PostgreSQL off the application VM.
- Test restoration, not just backup creation.
- Review logs for unexpected authentication or authorization failures.

## 13. Business implementation examples

### Small company
Start with one AI assistant, one knowledge base and 1–3 workflows.

### Mid-size company
Use separate workspaces/departments, role-based access, shared knowledge bases and monitored background automation.

### Enterprise
Use strict tenant boundaries, centralized identity, controlled model access, audit processes, backup/restore testing, deployment gates and a formal AI governance process.

## 14. Measuring AEON's value

Track business outcomes rather than only AI usage:
- time saved per workflow
- support resolution time
- document research time
- automation completion rate
- human approval rate
- error/escalation rate
- cost per completed task
- active users/workspaces
- knowledge-base usage

## 15. Troubleshooting

If the UI cannot reach the API, verify the public application URL, CORS configuration, reverse proxy and API health endpoint.

If authentication fails, verify the authentication secret/configuration and database connectivity.

If workflows are stuck, check Redis and Celery worker logs.

If knowledge retrieval fails, verify the configured provider/API credentials, ingestion status and knowledge-base configuration.

If deployment fails, stop promotion and inspect the production gate and container health logs before retrying.

## 16. Release principle

Never treat a successful Docker build as proof of production readiness. A release is ready only after automated tests, security checks, deployment checks, health/readiness checks and critical user journeys pass in the target Google Cloud environment.

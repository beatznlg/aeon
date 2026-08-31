# AEON OS — Screenshot & Visual User Guide

This guide defines the complete screenshot set that should live in `docs/screenshots/` and be refreshed whenever the UI changes materially.

## Required screenshots

1. `01-login.png` — Login screen, showing polished authentication UI.
2. `02-register.png` — Registration screen.
3. `03-dashboard.png` — Main authenticated dashboard.
4. `04-workspaces.png` — Workspace/organization management.
5. `05-agents.png` — Agent/assistant list and creation flow.
6. `06-agent-detail.png` — Agent configuration, tools and knowledge settings.
7. `07-workflows.png` — Workflow builder/list.
8. `08-workflow-editor.png` — Detailed workflow editing experience.
9. `09-knowledge.png` — Knowledge base management.
10. `10-knowledge-upload.png` — Document ingestion/upload flow.
11. `11-chat.png` — AI assistant interaction.
12. `12-models.png` — LLM/provider configuration.
13. `13-integrations.png` — Integration management.
14. `14-billing.png` — Billing/subscription UI where enabled.
15. `15-monitoring.png` — Monitoring/operations dashboard.
16. `16-settings.png` — User/workspace settings.
17. `17-mobile.png` — Representative mobile responsive UI.
18. `18-admin.png` — Administrative controls, restricted to administrators.

## Screenshot rules

- Capture from a production build, not a development error screen.
- Use representative non-sensitive demo data.
- Never expose real API keys, passwords, tokens, email addresses or customer information.
- Keep browser chrome out of the image where practical.
- Use the same viewport for desktop captures so the guide is visually consistent.
- Include mobile captures for critical flows.
- Refresh screenshots after major navigation, component, branding or authentication changes.

## Publishing

Store approved screenshots in `docs/screenshots/` and reference them from the user guide and README where useful. If screenshots cannot be generated automatically in CI, the documentation should clearly label the set as requiring a browser capture job rather than inventing images.

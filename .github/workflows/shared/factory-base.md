---
# Shared configuration imported by every factory agent workflow (SPEC §9).
# Note: imports cannot carry `engine:` settings, so each workflow declares its own BYOK engine block.
github-app:
  client-id: ${{ vars.FACTORY_APP_CLIENT_ID }}
  private-key: ${{ secrets.FACTORY_APP_PRIVATE_KEY }}
---

## Factory conventions

- You are one agent in the gh_aw_code_factory pipeline. State lives in issue labels and issue bodies.
- **Never communicate through issue comments.** Write to the issue body or use the configured safe outputs only.
- Only change the labels you are explicitly told to change.

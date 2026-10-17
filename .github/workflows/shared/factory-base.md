---
# Shared configuration imported by every factory agent workflow (SPEC §9).
# Note: imports cannot carry `engine:` settings, so each workflow declares its own BYOK engine block.
# `models.default-ai-credits-pricing` does merge from imports (first-wins).
github-app:
  client-id: ${{ vars.FACTORY_APP_CLIENT_ID }}
  private-key: ${{ secrets.FACTORY_APP_PRIVATE_KEY }}
# OpenRouter models are not in gh-aw's pricing catalog; without a price the API proxy rejects every request.
# Fallback rate in $ per 1M tokens, set slightly above z-ai/glm-5.3-flash (~$0.09 in / $0.30 out on OpenRouter)
# so max-ai-credits budgets stay meaningful. Raise it if FACTORY_MODEL points at a pricier model.
models:
  default-ai-credits-pricing:
    input: 0.1
    output: 0.35
---

## Factory conventions

- You are one agent in the gh_aw_code_factory pipeline. State lives in issue labels and issue bodies.
- **Never communicate through issue comments.** Write to the issue body or use the configured safe outputs only.
- Only change the labels you are explicitly told to change.

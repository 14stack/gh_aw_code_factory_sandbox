---
description: "P0 spike B (variant 1): is an App-applied label accepted via on.bots with the default role check?"
on:
  issues:
    types: [labeled]
    names: ["factory:spike_chain_b"]
  bots: ["gh-aw-code-factory"]
  reaction: eyes
  status-comment: false
if: vars.FACTORY_ENABLED == 'true'
permissions:
  contents: read
  issues: read
imports:
  - shared/factory-base.md
engine:
  id: copilot
  env:
    # BYOK: route the Copilot CLI to OpenRouter instead of GitHub's Copilot backend.
    COPILOT_PROVIDER_BASE_URL: "https://openrouter.ai/api/v1"
    COPILOT_PROVIDER_TYPE: openai
    COPILOT_PROVIDER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
    COPILOT_MODEL: ${{ vars.FACTORY_MODEL || 'z-ai/glm-5.3-flash' }}
sandbox:
  agent:
    model-fallback: false  # pass the OpenRouter model slug through verbatim
    targets:
      copilot:
        extra-headers:
          x-openrouter-title: gh_aw_code_factory
network:
  allowed: [defaults, openrouter.ai]
timeout-minutes: 10
tools:
  github:
    toolsets: [issues]
safe-outputs:
  update-issue:
    body:
---

# P0 spike B — `on.bots` variant

This run proves that a label applied by the factory GitHub App passed gh-aw's `on.bots` check.

Use `update_issue` with `operation: append` to append this section to the body of issue
#${{ github.event.issue.number }}:

```markdown
## Spike B (on.bots)
- Triggered by: ${{ github.actor }}
```

Do nothing else.

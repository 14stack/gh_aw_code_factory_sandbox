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

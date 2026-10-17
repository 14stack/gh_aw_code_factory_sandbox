---
description: "P0 spike A: Copilot engine + App-token safe outputs; hands off to spike B by adding a label"
on:
  issues:
    types: [labeled]
    names: ["factory:spike_chain_a"]
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
  add-labels:
    allowed: ["factory:spike_chain_b"]
  remove-labels:
    allowed: ["factory:spike_chain_a"]
---

# P0 spike A — engine and App-token handoff

This is a plumbing test for issue #${{ github.event.issue.number }}.

1. Read issue #${{ github.event.issue.number }}.
2. Use `update_issue` with `operation: append` to append this section to the issue body:

   ```markdown
   ## Spike A
   - Engine: Copilot reached the agent step.
   - Summary of the issue title in one sentence: <your sentence>
   ```

3. Remove the label `factory:spike_chain_a` from the issue.
4. Add the label `factory:spike_chain_b` to the issue. This must trigger the spike B workflows.

Do nothing else.

---
description: "P0 spike B (variant 2): App-applied label accepted with roles: all plus an explicit sender guard"
on:
  issues:
    types: [labeled]
    names: ["factory:spike_chain_b"]
  roles: all
  reaction: eyes
  status-comment: false
if: vars.FACTORY_ENABLED == 'true' && github.event.sender.login == 'gh-aw-code-factory[bot]'
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
  add-labels:
    allowed: ["factory:spike_done"]
---

# P0 spike B — `roles: all` + sender guard variant

This run proves that a label applied by the factory GitHub App can trigger a workflow when gh-aw's role check is
disabled and replaced by an explicit sender guard.

Add the label `factory:spike_done` to issue #${{ github.event.issue.number }}. Do nothing else.

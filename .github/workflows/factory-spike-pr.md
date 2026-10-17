---
description: "P0 spike: agent opens a PR from a sub branch into a story branch (App token, CI must trigger), then hands off to review"
on:
  issues:
    types: [labeled]
    names: ["factory:spike_pr"]
  reaction: eyes
  status-comment: false
if: vars.FACTORY_ENABLED == 'true'
permissions:
  contents: read
  issues: read
  pull-requests: read
imports:
  - shared/factory-base.md
timeout-minutes: 15
checkout:
  ref: story/spike
  fetch-depth: 0
tools:
  github:
    toolsets: [issues]
safe-outputs:
  create-pull-request:
    base-branch: story/spike
    allowed-base-branches: ["story/*"]
    title-prefix: "[sub] "
    labels: ["factory:managed"]
    draft: false
    auto-close-issue: false
  add-labels:
    allowed: ["factory:spike_review"]
  remove-labels:
    allowed: ["factory:spike_pr"]
---

# P0 spike — PR into a story branch

The workspace is checked out at the story branch `story/spike`.

1. Create a new branch named `sub/${{ github.event.issue.number }}-spike` from the current `HEAD`.
2. Create the file `spike/issue-${{ github.event.issue.number }}.md` containing one line:
   `Spike PR for issue #${{ github.event.issue.number }}.`
3. Commit it with the message `spike: add marker for #${{ github.event.issue.number }}`.
4. Create a pull request into `story/spike` with:
   - title `Spike marker for #${{ github.event.issue.number }}`
   - body exactly: `Part of #${{ github.event.issue.number }}`
5. Remove the label `factory:spike_pr` from issue #${{ github.event.issue.number }} and add the label
   `factory:spike_review`.

Do nothing else.

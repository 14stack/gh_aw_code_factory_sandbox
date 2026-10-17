---
description: "P0 spike: issue-triggered review (COMMENT) that merges the linked PR into the story branch"
on:
  issues:
    types: [labeled]
    names: ["factory:spike_review"]
  bots: ["gh-aw-code-factory"]
  reaction: eyes
  status-comment: false
if: vars.FACTORY_ENABLED == 'true'
permissions:
  contents: read
  issues: read
  pull-requests: read
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
timeout-minutes: 15
tools:
  github:
    toolsets: [issues, pull_requests]
steps:
  - name: Resolve the PR linked to this issue
    env:
      GH_TOKEN: ${{ github.token }}
      ISSUE: ${{ github.event.issue.number }}
    run: |
      mkdir -p /tmp/gh-aw/agent
      # The PR may be created a few seconds after the label lands; retry briefly.
      for attempt in 1 2 3 4 5 6; do
        gh pr list --repo "$GITHUB_REPOSITORY" --state open --limit 100 \
          --json number,title,body,headRefName,baseRefName \
          | jq --arg ref "Part of #$ISSUE" '[.[] | select(.baseRefName | startswith("story/")) | select(.body | contains($ref))]' \
          > /tmp/gh-aw/agent/linked_pr.json
        if [ "$(jq length /tmp/gh-aw/agent/linked_pr.json)" -gt 0 ]; then break; fi
        sleep 10
      done
      cat /tmp/gh-aw/agent/linked_pr.json
safe-outputs:
  # COMMENT only: the App opened the PR and GitHub forbids APPROVE/REQUEST_CHANGES on your own PR. A per-handler
  # github-token from a secret is not an option either (gh-aw 0.92.4 embeds it in the agent-side config and secret
  # redaction then fails the run). The verdict lives in the issue labels; the merge gate needs no approval.
  submit-pull-request-review:
    target: "*"
    allowed-events: [COMMENT]
  merge-pull-request:
    target: "*"
    allowed-branches: ["sub/*"]
  close-issue:
    state-reason: completed
  add-labels:
    allowed: ["factory:spike_done"]
  remove-labels:
    allowed: ["factory:spike_review"]
---

# P0 spike — review and merge the linked PR

`/tmp/gh-aw/agent/linked_pr.json` contains the open pull request(s) linked to issue
#${{ github.event.issue.number }} (body contains `Part of #${{ github.event.issue.number }}`, base is a `story/*`
branch).

If the file contains no pull request, remove the label `factory:spike_review`, call `noop` with the reason, and stop.

Otherwise, for the first pull request in the file:

1. Look at its diff. It should only add one marker file under `spike/`.
2. Submit a review with event `COMMENT` and body `Spike review: approved - marker file looks correct.`
3. Merge it with merge method `squash`.
4. Close issue #${{ github.event.issue.number }} (the close reason is fixed by configuration; do not pass `state_reason`).
5. Remove the label `factory:spike_review` and add the label `factory:spike_done`.

Do nothing else.

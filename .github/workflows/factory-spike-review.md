---
description: "P0 spike: issue-triggered review that approves (GITHUB_TOKEN identity) and merges the linked PR into the story branch"
on:
  issues:
    types: [labeled]
    names: ["factory:spike_review"]
  roles: all
  reaction: eyes
  status-comment: false
if: vars.FACTORY_ENABLED == 'true' && github.event.sender.login == 'gh-aw-code-factory[bot]'
permissions:
  contents: read
  issues: read
  pull-requests: read
imports:
  - shared/factory-base.md
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
  submit-pull-request-review:
    target: "*"
    allowed-events: [APPROVE, COMMENT, REQUEST_CHANGES]
    github-token: ${{ secrets.GITHUB_TOKEN }}
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
2. Submit a review with event `APPROVE` and body `Spike review: marker file looks correct.`
3. Merge it with merge method `squash`.
4. Close issue #${{ github.event.issue.number }} as completed.
5. Remove the label `factory:spike_review` and add the label `factory:spike_done`.

Do nothing else.

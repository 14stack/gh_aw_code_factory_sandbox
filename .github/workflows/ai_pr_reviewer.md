---
description: "Factory reviewer (SPEC §9.5): reviews the sub-issue's PR against its acceptance criteria; verdict as a label"
on:
  issues:
    types: [labeled]
    names: ["factory:sub_issue_pr_requires_review"]
  bots: ["gh-aw-code-factory"]  # set by the implementer's and fixer's finish jobs with the App token
  reaction: eyes
  status-comment: false
if: vars.FACTORY_ENABLED == 'true' && !contains(github.event.issue.labels.*.name, 'factory:ai_needs_human')
permissions:
  contents: read
  issues: read
  pull-requests: read
imports:
  - shared/factory-base.md
engine:
  id: copilot
  env:
    # BYOK: route the Copilot CLI to OpenRouter instead of GitHub's Copilot backend (SPEC §8).
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
timeout-minutes: 30
max-turns: 80
max-ai-credits: 150
tools:
  github:
    toolsets: [issues, repos, pull_requests]
  bash: ["echo", "ls", "cat", "head", "tail", "grep", "wc", "sort", "find", "git diff", "git log", "git show"]
jobs:
  # Deterministic pre-job (agents/ai_pr_reviewer/gate.py prepare): resolves the PR, enforces the loop guard and
  # gates on CI. Red CI goes straight to the fixer; the job then fails and the agent is skipped (no AI credits).
  prepare:
    needs: activation
    runs-on: ubuntu-latest
    timeout-minutes: 40
    outputs:
      proceed: ${{ steps.prepare.outputs.proceed }}
      pr_number: ${{ steps.prepare.outputs.pr_number }}
      head_ref: ${{ steps.prepare.outputs.head_ref }}
    steps:
      - name: Mint factory App token
        id: app
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          client-id: ${{ vars.FACTORY_APP_CLIENT_ID }}
          private-key: ${{ secrets.FACTORY_APP_PRIVATE_KEY }}
          owner: ${{ github.repository_owner }}
          repositories: |-
            ${{ github.event.repository.name }}
            gh_aw_code_factory
          permission-contents: read
          permission-issues: write
          permission-pull-requests: read
          permission-checks: read
      - name: Check out factory helpers
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: ${{ github.repository_owner }}/gh_aw_code_factory
          ref: ${{ vars.FACTORY_REF || 'claude/charming-knuth-6m2xdz' }}
          token: ${{ steps.app.outputs.token }}
          path: .factory
          persist-credentials: false
      - name: Prepare (PR, loop guard, CI gate)
        id: prepare
        working-directory: .factory
        env:
          GH_TOKEN: ${{ steps.app.outputs.token }}
          ISSUE: ${{ github.event.issue.number }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: python3 -m agents.ai_pr_reviewer.gate prepare --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" --run-url "$RUN_URL"
  # Deterministic failure handling (agents/common/failure.py): the agent run failed, threat detection failed, or the
  # agent reported nothing. The first time, retry by re-applying the trigger label; then flag a human.
  on_failure:
    needs: [agent, detection, prepare]
    if: >-
      always() && needs.prepare.outputs.proceed == 'true' && (needs.agent.result == 'failure' || needs.detection.result == 'failure' ||
      (needs.agent.result == 'success' && !contains(needs.agent.outputs.output_types, 'report_review')))
    runs-on: ubuntu-latest
    steps:
      - name: Mint factory App token
        id: app
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          client-id: ${{ vars.FACTORY_APP_CLIENT_ID }}
          private-key: ${{ secrets.FACTORY_APP_PRIVATE_KEY }}
          owner: ${{ github.repository_owner }}
          repositories: |-
            ${{ github.event.repository.name }}
            gh_aw_code_factory
          permission-contents: read
          permission-issues: write
      - name: Check out factory helpers
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: ${{ github.repository_owner }}/gh_aw_code_factory
          ref: ${{ vars.FACTORY_REF || 'claude/charming-knuth-6m2xdz' }}
          token: ${{ steps.app.outputs.token }}
          path: .factory
          persist-credentials: false
      - name: Retry once, then flag a human
        working-directory: .factory
        env:
          GH_TOKEN: ${{ steps.app.outputs.token }}
          ISSUE: ${{ github.event.issue.number }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: |
          python3 -m agents.common.failure --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" --agent ai_pr_reviewer \
            --trigger factory:sub_issue_pr_requires_review --kind sub --run-url "$RUN_URL"
checkout:
  ref: ${{ needs.prepare.outputs.head_ref }}
steps:
  # A noop written before the agent starts makes gh-aw exit cleanly without starting the model. GH_AW_SAFE_OUTPUTS is
  # not in the environment of custom steps, so the path comes from gh-aw's set-runtime-paths step.
  - name: Skip the agent when the pre-job decided so (no AI credits; the reason is in the Automation log)
    if: needs.prepare.outputs.proceed != 'true'
    env:
      SAFE_OUTPUTS: ${{ steps.set-runtime-paths.outputs.GH_AW_SAFE_OUTPUTS }}
    run: |
      mkdir -p "$(dirname "$SAFE_OUTPUTS")"
      echo '{"type":"noop","message":"Skipped by the deterministic pre-job; see the issue Automation log"}' >> "$SAFE_OUTPUTS"
  - name: Save the PR, sub-issue and story for the agent
    if: needs.prepare.outputs.proceed == 'true'
    env:
      GH_TOKEN: ${{ github.token }}
      ISSUE: ${{ github.event.issue.number }}
      PR: ${{ needs.prepare.outputs.pr_number }}
    run: |
      mkdir -p /tmp/gh-aw/agent
      story=$(gh api "repos/$GITHUB_REPOSITORY/issues/$ISSUE/parent" --jq .number)
      gh issue view "$ISSUE" --repo "$GITHUB_REPOSITORY" --json title,body --jq '"# " + .title + "\n\n" + .body' > /tmp/gh-aw/agent/sub-issue.md
      gh issue view "$story" --repo "$GITHUB_REPOSITORY" --json title,body --jq '"# " + .title + "\n\n" + .body' > /tmp/gh-aw/agent/story.md
      gh pr view "$PR" --repo "$GITHUB_REPOSITORY" --json number,title,body --jq '"# PR #" + (.number|tostring) + ": " + .title + "\n\n" + .body' > /tmp/gh-aw/agent/pr.md
      gh pr diff "$PR" --repo "$GITHUB_REPOSITORY" > /tmp/gh-aw/agent/pr.diff
      echo "$PR" > /tmp/gh-aw/agent/pr_number.txt
      wc -l /tmp/gh-aw/agent/pr.diff
safe-outputs:
  create-pull-request-review-comment:
    target: "*"
    max: 10
  # COMMENT only: the App opened the PR and can't approve it (P0 F9). The verdict is the label set by report-review.
  submit-pull-request-review:
    target: "*"
    allowed-events: [COMMENT]
    max: 1
  jobs:
    # Deterministic half (agents/ai_pr_reviewer/gate.py finish): records the verdict as a label after the review.
    report-review:
      description: >-
        Report your verdict. Call it exactly once, last, after submit_pull_request_review.
      runs-on: ubuntu-latest
      needs: [safe_outputs]
      inputs:
        outcome:
          description: "approved, or changes_requested (only for real defects: unmet criteria, bugs, missing tests)"
          required: true
          type: choice
          options: ["approved", "changes_requested"]
        summary:
          description: "One sentence: the verdict's main reason"
          required: true
          type: string
      steps:
        - name: Mint factory App token
          id: app
          uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
          with:
            client-id: ${{ vars.FACTORY_APP_CLIENT_ID }}
            private-key: ${{ secrets.FACTORY_APP_PRIVATE_KEY }}
            owner: ${{ github.repository_owner }}
            repositories: |-
              ${{ github.event.repository.name }}
              gh_aw_code_factory
            permission-contents: read
            permission-issues: write
            permission-pull-requests: read
        - name: Check out factory helpers
          uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
          with:
            repository: ${{ github.repository_owner }}/gh_aw_code_factory
            ref: ${{ vars.FACTORY_REF || 'claude/charming-knuth-6m2xdz' }}
            token: ${{ steps.app.outputs.token }}
            path: .factory
            persist-credentials: false
        - name: Record the verdict
          working-directory: .factory
          env:
            GH_TOKEN: ${{ steps.app.outputs.token }}
            ISSUE: ${{ github.event.issue.number }}
            RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
          run: |
            python3 -m agents.ai_pr_reviewer.gate finish --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" \
              --run-url "$RUN_URL" --agent-output "$GH_AW_AGENT_OUTPUT"
---

# AI PR reviewer

You are the **reviewer** of the code factory. Review the pull request of sub-issue
#${{ github.event.issue.number }} in ${{ github.repository }}. CI has already passed (lint, format, tests).

## Inputs

- `/tmp/gh-aw/agent/pr.md` and `/tmp/gh-aw/agent/pr.diff`: the PR description and its full diff;
  `/tmp/gh-aw/agent/pr_number.txt`: the PR number.
- `/tmp/gh-aw/agent/sub-issue.md`: what the PR must do (Goal, Acceptance criteria, QA / tests to add).
- `/tmp/gh-aw/agent/story.md`: the parent story, for context.
- The PR's branch is checked out, so you can read the full files. `AGENTS.md` has the conventions.

You can only **read**: `cat`, `grep`, `find`, `ls`, `head`, `tail`, `git diff`, `git log`, `git show`. You can't run
tests, linters or the app, and you don't need to: CI already ran lint, format and tests on this PR, and they passed.

## Review

Check, in this order:

1. **Acceptance criteria**: is every criterion of the sub-issue met by the diff? Nothing beyond the sub-issue?
2. **Tests**: are the tests from "QA / tests to add" there, and do they really test the behaviour (not just run it)?
3. **Correctness**: bugs, unhandled edge cases named in the sub-issue or story, broken existing behaviour.
4. **Conventions** from `AGENTS.md` (no new runtime dependencies, no edits to `.github/`, type hints, small modules).

Request changes **only for real defects** in these four areas, not for style preferences: CI already enforces lint
and formatting.

## Output

- For each defect, call `create_pull_request_review_comment` on the exact file and line, with `pull_request_number`
  from `pr_number.txt`, saying what is wrong and what to do instead.
- Then call `submit_pull_request_review` once, with `event: COMMENT`, the same `pull_request_number`, and a body
  whose first line is `**Verdict:** approved` or `**Verdict:** changes requested`, followed by a short summary
  (for changes: a numbered list of what must change).
- Finally call `report_review` once with `outcome` `approved` or `changes_requested` and a one-sentence summary.

Don't comment on issues, change labels, merge or push. The factory does that.

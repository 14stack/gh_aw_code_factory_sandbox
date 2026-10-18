---
description: "Factory fixer (SPEC §9.6): addresses review comments and CI failures on the sub-issue's PR"
name: "Factory: fixer"
run-name: "Fixer: sub-issue #${{ inputs.issue }}"
on:
  # Started only by the orchestrator (SPEC D29). It finds an issue's runs by the run name, so keep its
  # "<Role>: <story|sub-issue> #<n>" form.
  workflow_dispatch:
    inputs:
      issue:
        description: "Sub-issue number"
        required: true
        type: string
concurrency:
  group: "factory-fixer-${{ inputs.issue }}"
  job-discriminator: ${{ inputs.issue }}
# The ai_needs_human and stale-dispatch guards live in the deterministic code: a dispatch carries no labels.
if: vars.FACTORY_ENABLED == 'true'
permissions:
  actions: read
  checks: read
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
    # Code-writing agents can use a stronger model (FACTORY_MODEL_CODE) than the planning/review agents.
    COPILOT_MODEL: ${{ vars.FACTORY_MODEL_CODE || vars.FACTORY_MODEL || 'z-ai/glm-5.3-flash' }}
sandbox:
  agent:
    model-fallback: false  # pass the OpenRouter model slug through verbatim
    targets:
      copilot:
        extra-headers:
          x-openrouter-title: gh_aw_code_factory
network:
  allowed: [defaults, openrouter.ai]
timeout-minutes: 45
max-turns: 120
max-ai-credits: 250
tools:
  github:
    toolsets: [issues, repos, pull_requests]
  edit:
  bash: [":*"]
jobs:
  # Deterministic pre-job (agents/ai_pr_fixer/lifecycle.py prepare): resolves the PR and logs its head commit.
  prepare:
    needs: activation
    runs-on: ubuntu-latest
    permissions:
      issues: write
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
      - name: Check out factory helpers
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: ${{ github.repository_owner }}/gh_aw_code_factory
          ref: ${{ vars.FACTORY_REF || 'claude/charming-knuth-6m2xdz' }}
          token: ${{ steps.app.outputs.token }}
          path: .factory
          persist-credentials: false
      - name: Prepare
        id: prepare
        working-directory: .factory
        env:
          GH_TOKEN: ${{ steps.app.outputs.token }}
          WORKFLOW_TOKEN: ${{ github.token }}  # label writes: start no workflows
          ISSUE: ${{ inputs.issue }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: python3 -m agents.ai_pr_fixer.lifecycle prepare --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" --run-url "$RUN_URL"
  # Hands control back to the orchestrator (SPEC D29), whatever happened above: it reads the issue's new state and
  # starts the next agent, retries this one, or asks a human. `finished_run` tells it this run is ending.
  wake_orchestrator:
    needs: [prepare, agent, detection, safe_outputs, report_fix]
    if: ${{ !cancelled() && needs.prepare.result != 'skipped' }}
    runs-on: ubuntu-latest
    permissions:
      actions: write
    steps:
      - name: Dispatch the orchestrator
        env:
          GH_TOKEN: ${{ github.token }}
          ISSUE: ${{ inputs.issue }}
          RUN_ID: ${{ github.run_id }}  # in env, not inline: gh-aw replaces a step's env when `run` has expressions
        run: |
          gh workflow run ai_orchestrator.yml --repo "$GITHUB_REPOSITORY" -f issue="$ISSUE" -f finished_run="$RUN_ID" \
            -f reason="after Fixer"
checkout:
  ref: ${{ needs.prepare.outputs.head_ref }}
  fetch: ["*"]  # push-to-pull-request-branch needs the PR branches; merging the story branch needs it too
  fetch-depth: 0
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
  - name: Collect the feedback for the agent (review threads, reviews, failed checks)
    if: needs.prepare.outputs.proceed == 'true'
    env:
      GH_TOKEN: ${{ github.token }}
      ISSUE: ${{ inputs.issue }}
      PR: ${{ needs.prepare.outputs.pr_number }}
    run: |
      mkdir -p /tmp/gh-aw/agent
      out=/tmp/gh-aw/agent/feedback.md
      gh issue view "$ISSUE" --repo "$GITHUB_REPOSITORY" --json title,body --jq '"# " + .title + "\n\n" + .body' > /tmp/gh-aw/agent/sub-issue.md
      echo "$PR" > /tmp/gh-aw/agent/pr_number.txt
      gh pr view "$PR" --repo "$GITHUB_REPOSITORY" --json baseRefName --jq .baseRefName > /tmp/gh-aw/agent/base_branch.txt
      echo "# Feedback on PR #$PR" > "$out"
      echo -e "\n## Unresolved review threads\n" >> "$out"
      gh api graphql -F owner="${GITHUB_REPOSITORY%/*}" -F name="${GITHUB_REPOSITORY#*/}" -F pr="$PR" -f query='
        query($owner: String!, $name: String!, $pr: Int!) {
          repository(owner: $owner, name: $name) { pullRequest(number: $pr) {
            reviewThreads(first: 100) { nodes { id isResolved path line
              comments(first: 20) { nodes { databaseId author { login } body } } } } } } }' \
        --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved | not)
              | "### `\(.path):\(.line)` (thread_id: \(.id), comment_id: \(.comments.nodes[0].databaseId))\n"
                + ([.comments.nodes[] | "- **\(.author.login)**: \(.body)"] | join("\n")) + "\n"' >> "$out"
      echo -e "\n## Latest reviews\n" >> "$out"
      gh api "repos/$GITHUB_REPOSITORY/pulls/$PR/reviews" --jq '.[-2:][] | "### \(.user.login) (\(.state))\n\(.body)\n"' >> "$out"
      echo -e "\n## Failed checks on the PR head\n" >> "$out"
      sha=$(gh pr view "$PR" --repo "$GITHUB_REPOSITORY" --json headRefOid --jq .headRefOid)
      gh api "repos/$GITHUB_REPOSITORY/commits/$sha/check-runs" \
        --jq '.check_runs[] | select(.conclusion == "failure" or .conclusion == "timed_out") | "\(.id) \(.name)"' |
      while read -r id name; do
        echo -e "### $name\n\n\`\`\`" >> "$out"
        gh api "repos/$GITHUB_REPOSITORY/actions/jobs/$id/logs" 2>/dev/null | tail -n 120 >> "$out" || echo "(log unavailable)" >> "$out"
        echo -e "\`\`\`\n" >> "$out"
      done
      wc -l "$out"
  - uses: actions/setup-python@v5
    if: needs.prepare.outputs.proceed == 'true'
    with:
      python-version: "3.12"
  - name: Install the project's dev dependencies (the agent has no package-index access)
    if: needs.prepare.outputs.proceed == 'true'
    run: |
      if [ -f .github/factory/setup.sh ]; then bash .github/factory/setup.sh
      elif [ -f pyproject.toml ]; then python -m pip install --quiet -e ".[dev]"
      fi
safe-outputs:
  push-to-pull-request-branch:
    target: "*"
    required-labels: ["factory:managed"]  # only factory PRs
    # The pre-flight branch-protection lookup needs Administration:read, which the App doesn't have (P0 F10); minting
    # the token then fails and nothing is pushed. sub/* branches aren't protected; GitHub enforces rules at push time.
    check-branch-protection: false
  reply-to-pull-request-review-comment:
    target: "*"
    max: 20
  resolve-pull-request-review-thread:
    target: "*"
    max: 20
  jobs:
    # Deterministic half (agents/ai_pr_fixer/lifecycle.py finish): only a real new commit sends the PR back to review.
    report-fix:
      description: >-
        Report the result. Call it exactly once, last: after push_to_pull_request_branch, or instead of it when you
        are blocked.
      runs-on: ubuntu-latest
      permissions:
        issues: write
      needs: [safe_outputs]
      inputs:
        outcome:
          description: "fixed (you pushed commits) or blocked (explain why in summary)"
          required: true
          type: choice
          options: ["fixed", "blocked"]
        summary:
          description: "One sentence: what you changed, or why you are blocked"
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
        - name: Finish
          working-directory: .factory
          env:
            GH_TOKEN: ${{ steps.app.outputs.token }}
            WORKFLOW_TOKEN: ${{ github.token }}  # label writes: start no workflows
            ISSUE: ${{ inputs.issue }}
            RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
          run: |
            python3 -m agents.ai_pr_fixer.lifecycle finish --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" \
              --run-url "$RUN_URL" --agent-output "$GH_AW_AGENT_OUTPUT"
---

# AI PR fixer

You are the **fixer** of the code factory. The pull request of sub-issue #${{ inputs.issue }} in
${{ github.repository }} needs changes. Its branch is checked out.

## Inputs

- `/tmp/gh-aw/agent/feedback.md`: unresolved review threads (with `thread_id` and `comment_id`), the latest
  reviews, and the logs of failed checks.
- `/tmp/gh-aw/agent/sub-issue.md`: what the PR must do. `/tmp/gh-aw/agent/pr_number.txt`: the PR number.
  `/tmp/gh-aw/agent/base_branch.txt`: the story branch the PR merges into.
- `AGENTS.md`: commands and conventions. Dependencies are installed; you have no internet access for packages.

## Steps

1. Read the feedback and the code.
2. Fix every unresolved review thread and every failed check. If the PR conflicts with its base branch, merge it:
   `git fetch origin <base_branch> && git merge origin/<base_branch>`, resolve the conflicts, and commit.
3. Run the lint, format and test commands from `AGENTS.md` until all pass.
4. Commit (`git add -A && git commit -m "..."`), then call `push_to_pull_request_branch` with exactly these
   arguments: `repo: "${{ github.repository }}"`, `pull_request_number` (from `pr_number.txt`, as a number),
   `branch` (the checked-out branch, `git branch --show-current`) and `message` (your commit message).
5. For each review thread: `reply_to_pull_request_review_comment` (with its `comment_id`, `pull_request_number` and
   `repo: "${{ github.repository }}"`) saying what you changed, or why you didn't; then
   `resolve_pull_request_review_thread` (with its `thread_id`) for the ones you fixed.
6. Call `report_fix` once with `outcome: fixed` and a one-sentence summary, **only if the push succeeded**.

If you can't fix it (the feedback contradicts the sub-issue, or the checks can't be made to pass), don't push: call
`report_fix` with `outcome: blocked` and the reason. Don't comment on issues or change labels. Never edit
`.github/`.

---
description: "Factory fixer (SPEC §9.6): addresses review comments and CI failures on the sub-issue's PR"
on:
  issues:
    types: [labeled]
    names: ["factory:sub_issue_pr_requires_fix"]
  bots: ["gh-aw-code-factory"]  # set by the reviewer's jobs and the orchestrator with the App token
  reaction: eyes
  status-comment: false
if: vars.FACTORY_ENABLED == 'true' && !contains(github.event.issue.labels.*.name, 'factory:ai_needs_human')
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
    outputs:
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
          ISSUE: ${{ github.event.issue.number }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: python3 -m agents.ai_pr_fixer.lifecycle prepare --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" --run-url "$RUN_URL"
checkout:
  ref: ${{ needs.prepare.outputs.head_ref }}
  fetch: ["*"]  # push-to-pull-request-branch needs the PR branches; merging the story branch needs it too
  fetch-depth: 0
steps:
  - name: Collect the feedback for the agent (review threads, reviews, failed checks)
    env:
      GH_TOKEN: ${{ github.token }}
      ISSUE: ${{ github.event.issue.number }}
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
    with:
      python-version: "3.12"
  - name: Install the project's dev dependencies (the agent has no package-index access)
    run: |
      if [ -f .github/factory/setup.sh ]; then bash .github/factory/setup.sh
      elif [ -f pyproject.toml ]; then python -m pip install --quiet -e ".[dev]"
      fi
safe-outputs:
  push-to-pull-request-branch:
    target: "*"
    required-labels: ["factory:managed"]  # only factory PRs
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
            ISSUE: ${{ github.event.issue.number }}
            RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
          run: |
            python3 -m agents.ai_pr_fixer.lifecycle finish --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" \
              --run-url "$RUN_URL" --agent-output "$GH_AW_AGENT_OUTPUT"
---

# AI PR fixer

You are the **fixer** of the code factory. The pull request of sub-issue #${{ github.event.issue.number }} in
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
4. Commit (`git add -A && git commit -m "..."`) and call `push_to_pull_request_branch` with the
   `pull_request_number`.
5. For each review thread: `reply_to_pull_request_review_comment` (with its `comment_id`) saying what you changed,
   or why you didn't; then `resolve_pull_request_review_thread` (with its `thread_id`) for the ones you fixed.
6. Call `report_fix` once with `outcome: fixed` and a one-sentence summary.

If you can't fix it (the feedback contradicts the sub-issue, or the checks can't be made to pass), don't push: call
`report_fix` with `outcome: blocked` and the reason. Don't comment on issues or change labels. Never edit
`.github/`.

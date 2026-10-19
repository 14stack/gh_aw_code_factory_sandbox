---
description: "Factory implementer (SPEC §9.4): implements one sub-issue and opens a PR into the story branch"
name: "Factory: implementer"
run-name: "Implementer: sub-issue #${{ inputs.issue }}"
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
  group: "factory-implementer-${{ inputs.issue }}"
  job-discriminator: ${{ inputs.issue }}
# The ai_needs_human and stale-dispatch guards live in the deterministic code: a dispatch carries no labels.
if: vars.FACTORY_ENABLED == 'true'
permissions:
  contents: read
  issues: read
imports:
  - shared/factory-base.md
engine:
  # Experiment (claude/pi-harness): the Pi coding agent instead of the Copilot CLI, same OpenRouter route and model.
  # The literal "openrouter/" prefix names Pi's provider; the rest is the OpenRouter model id or preset. No quoted
  # fallback: gh-aw embeds the expression in a single-quoted shell command, where quotes break it.
  id: pi
  model: openrouter/${{ vars.FACTORY_MODEL_CODE || vars.FACTORY_MODEL }}
  model-provider: openai
  env:
    OPENAI_BASE_URL: https://openrouter.ai/api/v1
    OPENAI_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
    CODEX_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}  # the Pi gateway reads its key from CODEX_API_KEY
  config: |
    {"settings": {"defaultThinkingLevel": "medium"},
     "model": {"reasoning": true, "contextWindow": 128000, "maxTokens": 32000}}
sandbox:
  agent:
    model-fallback: false
network:
  allowed: [defaults, openrouter.ai]
timeout-minutes: 60
max-turns: 150
max-ai-credits: 300
tools:
  github:
    toolsets: [issues, repos]
  edit:
  bash: [":*"]
jobs:
  # Deterministic pre-job (agents/ai_implementation_agent/lifecycle.py start): resolves the story branch and marks
  # the sub-issue in progress. It fails (and the agent is skipped) when the sub-issue can't be implemented.
  start:
    needs: activation
    runs-on: ubuntu-latest
    permissions:
      issues: write
    outputs:
      proceed: ${{ steps.start.outputs.proceed }}
      story: ${{ steps.start.outputs.story }}
      story_branch: ${{ steps.start.outputs.story_branch }}
      sub_branch: ${{ steps.start.outputs.sub_branch }}
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
          ref: ${{ vars.FACTORY_REF || 'claude/pi-harness' }}
          token: ${{ steps.app.outputs.token }}
          path: .factory
          persist-credentials: false
      - name: Start
        id: start
        working-directory: .factory
        env:
          GH_TOKEN: ${{ steps.app.outputs.token }}
          WORKFLOW_TOKEN: ${{ github.token }}  # label writes: start no workflows
          ISSUE: ${{ inputs.issue }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: python3 -m agents.ai_implementation_agent.lifecycle start --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" --run-url "$RUN_URL"
  # Hands control back to the orchestrator (SPEC D29), whatever happened above: it reads the issue's new state and
  # starts the next agent, retries this one, or asks a human. `finished_run` tells it this run is ending. With the
  # factory switched off it starts an orchestrator run that is skipped as well.
  wake_orchestrator:
    needs: [start, agent, detection, safe_outputs, report_implementation]
    if: ${{ !cancelled() }}  # even when an earlier job failed (activation included): the orchestrator retries
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
            -f reason="after Implementer"
checkout:
  ref: ${{ needs.start.outputs.story_branch }}
steps:
  # A noop written before the agent starts makes gh-aw exit cleanly without starting the model. GH_AW_SAFE_OUTPUTS is
  # not in the environment of custom steps, so the path comes from gh-aw's set-runtime-paths step.
  - name: Skip the agent when the pre-job decided so (no AI credits; the reason is in the Automation log)
    if: needs.start.outputs.proceed != 'true'
    env:
      SAFE_OUTPUTS: ${{ steps.set-runtime-paths.outputs.GH_AW_SAFE_OUTPUTS }}
    run: |
      mkdir -p "$(dirname "$SAFE_OUTPUTS")"
      echo '{"type":"noop","message":"Skipped by the deterministic pre-job; see the issue Automation log"}' >> "$SAFE_OUTPUTS"
  - name: Save the sub-issue and its story for the agent
    if: needs.start.outputs.proceed == 'true'
    env:
      GH_TOKEN: ${{ github.token }}
      ISSUE: ${{ inputs.issue }}
      STORY: ${{ needs.start.outputs.story }}
      STORY_BRANCH: ${{ needs.start.outputs.story_branch }}
      SUB_BRANCH: ${{ needs.start.outputs.sub_branch }}
    run: |
      mkdir -p /tmp/gh-aw/agent
      gh issue view "$ISSUE" --repo "$GITHUB_REPOSITORY" --json title,body --jq '"# " + .title + "\n\n" + .body' > /tmp/gh-aw/agent/sub-issue.md
      gh issue view "$STORY" --repo "$GITHUB_REPOSITORY" --json title,body --jq '"# " + .title + "\n\n" + .body' > /tmp/gh-aw/agent/story.md
      printf 'story_branch=%s\nsub_branch=%s\n' "$STORY_BRANCH" "$SUB_BRANCH" > /tmp/gh-aw/agent/branches.txt
      cat /tmp/gh-aw/agent/branches.txt
  - uses: actions/setup-python@v5
    if: needs.start.outputs.proceed == 'true'
    with:
      python-version: "3.12"
  - name: Install the project's dev dependencies (the agent has no package-index access)
    if: needs.start.outputs.proceed == 'true'
    run: |
      if [ -f .github/factory/setup.sh ]; then bash .github/factory/setup.sh
      elif [ -f pyproject.toml ]; then python -m pip install --quiet -e ".[dev]"
      fi
safe-outputs:
  # Threat detection stays on the Copilot CLI with the BYOK route (Pi's default detector needs Copilot credentials).
  threat-detection:
    engine:
      id: copilot
      env:
        COPILOT_PROVIDER_BASE_URL: "https://openrouter.ai/api/v1"
        COPILOT_PROVIDER_TYPE: openai
        COPILOT_PROVIDER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        COPILOT_MODEL: ${{ vars.FACTORY_MODEL_CODE || vars.FACTORY_MODEL || 'deepseek/deepseek-v4.1-flash-1017' }}
  create-pull-request:
    # The patch is computed against `base-branch` inside the agent job (the agent's `base` only applies later), so it
    # must be the story branch, not the default branch. The safe_outputs job doesn't need `start`; there this resolves
    # empty and the agent-provided `base` (allowed by allowed-base-branches) is used.
    base-branch: ${{ needs.start.outputs.story_branch }}
    allowed-base-branches: ["story/*"]
    allowed-branches: ["sub/*"]
    preserve-branch-name: true
    draft: false
    auto-close-issue: false
    labels: ["factory:managed"]
    fallback-as-issue: false
    if-no-changes: error
    max-patch-files: 30
  jobs:
    # Deterministic half (agents/ai_implementation_agent/lifecycle.py finish), after the PR exists.
    report-implementation:
      description: >-
        Report the result. Call it exactly once, last: after create_pull_request, or instead of it when you are
        blocked.
      runs-on: ubuntu-latest
      permissions:
        issues: write
      needs: [safe_outputs]
      inputs:
        outcome:
          description: "pr_opened (you called create_pull_request) or blocked (no PR; explain why in summary)"
          required: true
          type: choice
          options: ["pr_opened", "blocked"]
        summary:
          description: "At most 15 words: what you implemented, or why you are blocked"
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
            permission-pull-requests: write
        - name: Check out factory helpers
          uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
          with:
            repository: ${{ github.repository_owner }}/gh_aw_code_factory
            ref: ${{ vars.FACTORY_REF || 'claude/pi-harness' }}
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
            python3 -m agents.ai_implementation_agent.lifecycle finish --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" \
              --run-url "$RUN_URL" --agent-output "$GH_AW_AGENT_OUTPUT"
---

# AI implementation agent

You are the **developer** of the code factory. Implement sub-issue #${{ inputs.issue }} in
${{ github.repository }} and open one pull request into its story branch.

## Inputs

- `/tmp/gh-aw/agent/sub-issue.md`: the sub-issue: its goal, then the Spec with "Done when", "Notes" and "Tests".
- `/tmp/gh-aw/agent/story.md`: the parent story, for context (Summary, Spec with requirements `R<n>`, Decisions).
- `/tmp/gh-aw/agent/branches.txt`: `story_branch` (the PR base, already checked out) and `sub_branch` (your branch).
- `AGENTS.md` in the repository: layout, commands (install, lint, format, test) and conventions. Follow it.
  The project's dependencies are already installed; you have no internet access for package installs.

## Steps

1. Read the inputs and `AGENTS.md`, then the code you will change.
2. Create your branch: `git checkout -b <sub_branch>`.
3. Implement **only** this sub-issue: every "Done when" item, nothing else. Keep the change small and in the
   style of the surrounding code. Never edit `.github/`.
4. Add the tests listed under "Tests" (and any others the change needs).
5. Run the lint, format and test commands from `AGENTS.md`. Fix and re-run until all pass. Use the formatter to
   fix formatting (for example `ruff format .`).
6. Commit with a clear message (`git add -A && git commit -m "..."`).
7. Call `create_pull_request` with:
   - `branch`: the `sub_branch`; `base`: the `story_branch` (both from `branches.txt`);
   - `title`: the sub-issue title;
   - `body`: one or two sentences on what changed, then the line `Part of #${{ inputs.issue }}`. Nothing else: the
     reviewer reads the diff and CI shows the checks.
8. Call `report_implementation` with `outcome: pr_opened` and a summary of at most 15 words.

If you cannot make the checks pass, the sub-issue needs a change under `.github/` (GitHub refuses that push), or
it is ambiguous or contradicts the code, don't open a PR: call `report_implementation` with `outcome: blocked` and
explain why in the summary. Don't comment on issues or change labels; the factory does that.

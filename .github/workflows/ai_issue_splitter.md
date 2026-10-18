---
description: "Factory splitter (SPEC §9.2): splits a refined story into dependent sub-issues, a story branch and a draft story PR"
name: "Factory: splitter"
run-name: "Splitter: story #${{ inputs.issue }}"
on:
  # Started only by the orchestrator (SPEC D29). It finds an issue's runs by the run name, so keep its
  # "<Role>: <story|sub-issue> #<n>" form.
  workflow_dispatch:
    inputs:
      issue:
        description: "Story number"
        required: true
        type: string
concurrency:
  group: "factory-splitter-${{ inputs.issue }}"
  job-discriminator: ${{ inputs.issue }}
# The ai_needs_human and stale-dispatch guards live in the deterministic code: a dispatch carries no labels.
if: vars.FACTORY_ENABLED == 'true'
permissions:
  contents: read
  issues: read
imports:
  - shared/factory-base.md
engine:
  id: copilot
  env:
    # BYOK: route the Copilot CLI to OpenRouter instead of GitHub's Copilot backend (SPEC §8).
    COPILOT_PROVIDER_BASE_URL: "https://openrouter.ai/api/v1"
    COPILOT_PROVIDER_TYPE: openai
    COPILOT_PROVIDER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
    COPILOT_MODEL: ${{ vars.FACTORY_MODEL || 'deepseek/deepseek-v4.1-flash-1017' }}
sandbox:
  agent:
    model-fallback: false  # pass the OpenRouter model slug through verbatim
    targets:
      copilot:
        extra-headers:
          x-openrouter-title: gh_aw_code_factory
network:
  allowed: [defaults, openrouter.ai]
timeout-minutes: 20
max-turns: 60
max-ai-credits: 100
tools:
  github:
    toolsets: [issues, repos]
  bash: ["echo", "ls", "cat", "head", "tail", "grep", "wc", "sort", "find"]
steps:
  - name: Save the story for the agent
    env:
      GH_TOKEN: ${{ github.token }}
      ISSUE: ${{ inputs.issue }}
    run: |
      mkdir -p /tmp/gh-aw/agent
      gh issue view "$ISSUE" --repo "$GITHUB_REPOSITORY" --json title --jq .title > /tmp/gh-aw/agent/story-title.txt
      gh issue view "$ISSUE" --repo "$GITHUB_REPOSITORY" --json body --jq .body > /tmp/gh-aw/agent/story.md
      cat /tmp/gh-aw/agent/story-title.txt
jobs:
  # Hands control back to the orchestrator (SPEC D29), whatever happened above: it reads the issue's new state and
  # starts the next agent, retries this one, or asks a human. `finished_run` tells it this run is ending. With the
  # factory switched off it starts an orchestrator run that is skipped as well.
  wake_orchestrator:
    needs: [activation, agent, detection, safe_outputs, create_sub_issue, split_too_large]
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
            -f reason="after Splitter"
safe-outputs:
  jobs:
    # Deterministic half (agents/ai_issue_splitter/apply.py): validates the plan, then creates the story branch,
    # sub-issues, native sub-issue links, blocked-by dependencies and the draft story PR.
    create-sub-issue:
      description: >-
        Propose one sub-issue of the story. Call once per sub-issue (1-20 calls). Nothing is created until the run
        ends; then all sub-issues are created together, in dependency order.
      runs-on: ubuntu-latest
      permissions:
        issues: write
      max: 20
      if: needs.detection.result == 'success'
      inputs:
        key:
          description: "Short unique key of this sub-issue within the plan: S1, S2, ..."
          required: true
          type: string
        title:
          description: "Imperative title, e.g. 'Add due_date to Todo and TodoStore.add'"
          required: true
          type: string
        goal:
          description: "One plain sentence for the human: what this sub-issue changes"
          required: true
          type: string
        done_when:
          description: "Markdown checklist (- [ ] ...), one testable item per line, traced to the story's R ids: '- [ ] (R1) ...'"
          required: true
          type: string
        notes:
          description: "Only what the story spec and the code don't already say (files, approach, pitfalls), or 'none'"
          required: true
          type: string
        tests:
          description: "The tests to add or extend: '- `tests/test_x.py`: behaviours'"
          required: true
          type: string
        depends_on:
          description: "Keys of the sub-issues that must be merged first, comma-separated, or 'none'"
          required: true
          type: string
      steps: &apply-steps
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
            permission-contents: write
            permission-issues: write
            permission-pull-requests: write
        - name: Check out factory helpers
          uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
          with:
            repository: ${{ github.repository_owner }}/gh_aw_code_factory
            ref: ${{ vars.FACTORY_REF || 'claude/charming-knuth-6m2xdz' }}
            token: ${{ steps.app.outputs.token }}
            path: .factory
            persist-credentials: false
        - name: Apply the split
          working-directory: .factory
          env:
            GH_TOKEN: ${{ steps.app.outputs.token }}
            WORKFLOW_TOKEN: ${{ github.token }}  # label writes: start no workflows
            STORY: ${{ inputs.issue }}
            MODE: ${{ github.job == 'split_too_large' && 'too_large' || 'split' }}
            RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
          run: |
            python3 -m agents.ai_issue_splitter.apply --repo "$GITHUB_REPOSITORY" --story "$STORY" --mode "$MODE" \
              --agent-output "$GH_AW_AGENT_OUTPUT" --run-url "$RUN_URL"
    split-too-large:
      description: >-
        Report that the story cannot be split into at most 20 sub-issues. Call it instead of create_sub_issue.
      runs-on: ubuntu-latest
      permissions:
        issues: write
      if: needs.detection.result == 'success'
      inputs:
        reason:
          description: "Why, and a suggested split into 2-5 smaller stories (a title and one line each), in Markdown"
          required: true
          type: string
      steps: *apply-steps
---

# AI issue splitter

You are the **splitter** of the code factory. Story issue #${{ inputs.issue }} in
${{ github.repository }} is refined. Split it into small sub-issues that AI developers implement one at a time, each
as one pull request into the story branch.

Agents read the sub-issues, the human reads only the titles and goals. Write only what an implementer needs and
can't get from the story spec or the code: no repetition across fields, no restating the story.

## Inputs

- `/tmp/gh-aw/agent/story-title.txt` and `/tmp/gh-aw/agent/story.md`: the refined story (Summary, Spec with
  requirements `R<n>`, Decisions).
- The repository is checked out in the current directory. Read `AGENTS.md` first, then the code the story touches.

## How to split

1. Every sub-issue is **one small pull request** (about 1–3 files, tests included) that leaves the code green on its
   own.
2. Together the sub-issues cover every requirement; each `done_when` item names its requirement: `- [ ] (R2) ...`.
3. Each sub-issue brings its own tests. No separate "write tests" sub-issue.
4. `depends_on`: the sub-issues that must be merged first. Prefer a simple chain (S2 after S1, S3 after S2, ...);
   leave sub-issues independent only when they touch different files.
5. As few sub-issues as make sense: usually 1–4, never more than 20.
6. Budget per sub-issue: `done_when` 2–6 items, `notes` 0–5 bullets, `tests` 1–4 lines.

## What to do

- Call `create_sub_issue` once per sub-issue, in order (S1, S2, ...).
- If the story genuinely cannot be done in 20 sub-issues, call `split_too_large` once instead, with the reason and a
  suggested split into smaller stories. Don't call both.
- Don't comment on the issue, change labels or edit files. Branches, issues, links and the story PR are created
  automatically from your tool calls when the run ends.

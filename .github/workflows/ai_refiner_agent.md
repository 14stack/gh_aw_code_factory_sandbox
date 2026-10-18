---
description: "Factory refiner (SPEC §9.1): turns a story issue into a refined story or asks the human what blocks it"
name: "Factory: refiner"
run-name: "Refiner: story #${{ inputs.issue }}"
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
  group: "factory-refiner-${{ inputs.issue }}"
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
    needs: [activation, agent, detection, safe_outputs, apply_refinement]
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
            -f reason="after Refiner"
safe-outputs:
  jobs:
    # Deterministic half of the refiner (agents/ai_refiner_agent/apply.py): validates the proposed body, keeps the
    # Decision log and Automation log append-only, numbers new questions and sets exactly one refinement label.
    apply-refinement:
      description: >-
        Apply the refined story: replaces the issue body and sets the refinement outcome. Call it exactly once, at
        the end, with the complete new body.
      runs-on: ubuntu-latest
      permissions:
        issues: write
      # Like the built-in safe_outputs job: never apply output that threat detection rejected.
      if: needs.detection.result == 'success'
      inputs:
        outcome:
          description: "done (no blocking questions), needs_human_review (open questions remain) or too_large"
          required: true
          type: choice
          options: ["done", "needs_human_review", "too_large"]
        body:
          description: "The complete new issue body in the required Markdown format"
          required: true
          type: string
        summary:
          description: "Automation log line: what changed in this iteration, at most 15 words"
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
        - name: Check out factory helpers
          uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
          with:
            repository: ${{ github.repository_owner }}/gh_aw_code_factory
            ref: ${{ vars.FACTORY_REF || 'claude/charming-knuth-6m2xdz' }}
            token: ${{ steps.app.outputs.token }}
            path: .factory
            persist-credentials: false
        - name: Apply the refinement
          working-directory: .factory
          env:
            GH_TOKEN: ${{ steps.app.outputs.token }}
            WORKFLOW_TOKEN: ${{ github.token }}  # label writes: start no workflows
            ISSUE: ${{ inputs.issue }}
            RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
          run: |
            python3 -m agents.ai_refiner_agent.apply --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" \
              --agent-output "$GH_AW_AGENT_OUTPUT" --run-url "$RUN_URL"
---

# AI refiner

You are the **refiner** of the code factory. Turn story issue #${{ inputs.issue }} in
${{ github.repository }} into a story that an AI developer can implement, **or** ask the human what blocks that.

Two readers: the **human** reads only the Summary and the Questions, so keep those short and plain. The **agents**
(splitter, implementer, reviewer) read the Spec. Both are paid for by the word: write only what changes what gets
built or tested. No background, no restating the request, the code, `AGENTS.md` or the obvious.

## Inputs

- `/tmp/gh-aw/agent/story-title.txt` and `/tmp/gh-aw/agent/story.md`: the issue title and current body. On the first
  run the body is free text from a human; later it has the sections below, maybe with answers under "Questions".
- The repository is checked out in the current directory. Read `AGENTS.md`, then the code the story touches.

## Steps

1. Read the title, the body, `AGENTS.md` and the relevant code.
2. Fold the human's answers (a question whose `**Answer:**` line has text) into the Summary and Spec. Then drop
   answered questions from "Questions"; they are moved to the Decisions automatically.
3. Write the Summary and the Spec (format below). Unknowns that block implementation become questions. Decide
   everything else yourself, in the Spec, without listing it as an assumption.
4. **Size check.** Too large: no clear done criteria, or more than 20 small pull requests (about 1–3 files each).
5. Outcome:
   - `done`: nothing blocks implementation; "Questions" is `_No open questions._`.
   - `needs_human_review`: at most 3 blocking questions, most important first.
   - `too_large`: one question `### Q — How should this story be split?`, listing 2–5 smaller stories (title and
     one line each).
6. Call `apply_refinement` **exactly once** with the outcome, the complete body and a summary of at most 15 words.

## Body format

Exactly these `##` headings, in this order:

```markdown
## Summary

2–4 plain sentences for the human: what changes for the user. No file names, no implementation.

## Questions

### Q — <the question, one line>

a) <option> (recommended) · b) <option> · c) <option>

**Answer:** _(write your answer here)_

## Spec

**Requirements**
- R1: <one testable statement>

**Notes**
- <only what the code doesn't already tell an implementer: the approach where there is a choice, data formats,
  edge cases, constraints>

**Tests**
- `tests/test_x.py`: <behaviours to cover, comma-separated>
```

Rules:

- The Spec is usually 5–15 bullets and under 1,500 characters; a large story may need more, never filler. Omit
  "Notes" when there is nothing non-obvious.
- A question has at most one extra sentence of context, only if the options don't make it clear. Keep the headings of
  existing questions (`### Q2 — ...`); write new ones as `### Q — ...`, they are numbered automatically.
- If no question is open, "Questions" contains only `_No open questions._`.
- Agents can't change files under `.github/` (workflows, CI, templates): GitHub refuses those pushes. Keep such
  changes out of the requirements and end the Summary with `Human step: <the change, one line>`.
- Don't write "Decisions" or "Automation log"; both are maintained automatically. Don't use HTML comments.
- Don't comment on the issue, change labels or edit files. The `apply_refinement` tool performs the update.

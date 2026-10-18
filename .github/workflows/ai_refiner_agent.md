---
description: "Factory refiner (SPEC §9.1): turns a story issue into a refined story or asks the human what blocks it"
on:
  issues:
    types: [labeled]
    names: ["factory:refinement_requires_ai_review"]
  # Humans set this label (story form, answers); the factory App only re-applies it to retry a failed run.
  bots: ["gh-aw-code-factory"]
  reaction: eyes
  status-comment: false
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
      ISSUE: ${{ github.event.issue.number }}
    run: |
      mkdir -p /tmp/gh-aw/agent
      gh issue view "$ISSUE" --repo "$GITHUB_REPOSITORY" --json title --jq .title > /tmp/gh-aw/agent/story-title.txt
      gh issue view "$ISSUE" --repo "$GITHUB_REPOSITORY" --json body --jq .body > /tmp/gh-aw/agent/story.md
      cat /tmp/gh-aw/agent/story-title.txt
jobs:
  # Deterministic failure handling (agents/common/failure.py): the agent run failed, threat detection failed, or the
  # agent reported nothing. The first time, retry by re-applying the trigger label; then flag a human.
  on_failure:
    needs: [agent, detection]
    if: >-
      always() && (needs.agent.result == 'failure' || needs.detection.result == 'failure' ||
      (needs.agent.result == 'success' && !contains(needs.agent.outputs.output_types, 'apply_refinement')))
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
          python3 -m agents.common.failure --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" --agent ai_refiner_agent \
            --trigger factory:refinement_requires_ai_review --kind story --run-url "$RUN_URL"
safe-outputs:
  jobs:
    # Deterministic half of the refiner (agents/ai_refiner_agent/apply.py): validates the proposed body, keeps the
    # Decision log and Automation log append-only, numbers new questions and sets exactly one refinement label.
    apply-refinement:
      description: >-
        Apply the refined story: replaces the issue body and sets the refinement outcome. Call it exactly once, at
        the end, with the complete new body.
      runs-on: ubuntu-latest
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
          description: "One sentence for the automation log: what changed in this iteration"
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
            ISSUE: ${{ github.event.issue.number }}
            RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
          run: |
            python3 -m agents.ai_refiner_agent.apply --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" \
              --agent-output "$GH_AW_AGENT_OUTPUT" --run-url "$RUN_URL"
---

# AI refiner

You are the **refiner** of the code factory. Turn story issue #${{ github.event.issue.number }} in
${{ github.repository }} into a clear story that a developer can implement, **or** ask the human the questions that
block that.

## Inputs

- `/tmp/gh-aw/agent/story-title.txt`: the issue title.
- `/tmp/gh-aw/agent/story.md`: the current issue body. On the first run it is free text written by a human. Later it
  has the sections below, possibly with the human's answers under "Open questions to human".
- The repository is checked out in the current directory. Read `AGENTS.md` first, then the code the story touches
  (`ls`, `find`, `grep`, `cat`).

## Steps

1. Read the title, the body, `AGENTS.md` and the relevant code.
2. **Fold in answers.** A question under "Open questions to human" is *answered* when its `**Answer:**` line has
   text from the human instead of `_(write your answer here)_`. For each answered question:
   - update the sections it affects;
   - move it, with the answer verbatim, to "Decision log", ending with a line
     `→ Incorporated into: <section names or BR ids>`.
3. **Write the five main sections** (format below). Be concrete: name the files, functions, commands and test files
   from this repository. Don't invent requirements. Unknowns that block implementation become questions.
   Non-blocking uncertainties become assumptions in "Technical details", each starting with `Assumption:`.
4. **Size check.** The story is too large if it has no clear done criteria, or if it would need more than 20
   sub-tasks, where one sub-task is one small pull request touching about 1–3 files.
5. **Choose the outcome:**
   - `done`: nothing blocks implementation, and "Open questions to human" contains `_No open questions._`.
   - `needs_human_review`: at least one blocking question remains. Ask at most 5 per iteration, most important
     first. Give each one **Context**, **Options** and your **Recommendation**, so the human can answer in one line.
   - `too_large`: write one question `### Q — How should this story be split?`, whose context lists 2–5 smaller
     stories you suggest (a title and one line each).
6. Call the `apply_refinement` tool **exactly once** with the outcome, the complete new body and a one-sentence
   summary. Then stop.

## Body format

Use exactly these `##` headings, in this order. Don't add other `##` headings; inside a section use `###` or bold
text.

```markdown
## Background

Why we do this and for whom: the problem and the current behaviour.

## Business requirements

- **BR-1:** <one testable statement>
- **BR-2:** <...>

## Technical details

Affected modules and files, the approach, data/API/CLI changes, constraints and risks.
Assumption: <non-blocking assumption, if any>

## QA

How the story is verified: the test types and concrete test files or cases (for example
`tests/test_store.py::test_sort_by_due_date`) and the commands from AGENTS.md. Cover every BR.

## Open questions to human

### Q — <question>

**Context:** <what is unclear and why it matters>
**Options:** <a) ..., b) ...>
**Recommendation:** <your pick and why>

**Answer:** _(write your answer here)_

## Decision log

### Q1 (iteration 1) — <a question answered in this iteration>

<context>

**Answer:** <the human's answer, verbatim>

→ Incorporated into: BR-2, Technical details
```

Rules:

- Keep the headings of existing questions unchanged (for example `### Q2 (iteration 1) — ...`). Write new questions as
  `### Q — <question>`; their numbers are assigned automatically.
- Every open question ends with the line `**Answer:** _(write your answer here)_`.
- If no question is open, the section contains only `_No open questions._`.
- In "Decision log", write only the questions answered in this iteration. Earlier entries and the original request
  are kept automatically.
- Don't write an "Automation log" section; it is maintained automatically. Don't use HTML comments; they are removed.
- Don't comment on the issue, change labels or edit files. The `apply_refinement` tool performs the update.

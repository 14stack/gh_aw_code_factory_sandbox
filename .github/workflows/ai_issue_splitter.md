---
description: "Factory splitter (SPEC §9.2): splits a refined story into dependent sub-issues, a story branch and a draft story PR"
on:
  issues:
    types: [labeled]
    names: ["factory:refinement_done"]
  bots: ["gh-aw-code-factory"]  # the refiner's apply job sets the label with the App token
  reaction: eyes
  status-comment: false
if: vars.FACTORY_ENABLED == 'true' && !contains(github.event.issue.labels.*.name, 'factory:ai_needs_human')
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
      (needs.agent.result == 'success' && !contains(needs.agent.outputs.output_types, 'create_sub_issue') && !contains(needs.agent.outputs.output_types, 'split_too_large')))
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
          python3 -m agents.common.failure --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" --agent ai_issue_splitter \
            --trigger factory:refinement_done --kind story --run-url "$RUN_URL"
safe-outputs:
  jobs:
    # Deterministic half (agents/ai_issue_splitter/apply.py): validates the plan, then creates the story branch,
    # sub-issues, native sub-issue links, blocked-by dependencies and the draft story PR.
    create-sub-issue:
      description: >-
        Propose one sub-issue of the story. Call once per sub-issue (1-20 calls). Nothing is created until the run
        ends; then all sub-issues are created together, in dependency order.
      runs-on: ubuntu-latest
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
          description: "One or two sentences: what this sub-issue achieves"
          required: true
          type: string
        acceptance_criteria:
          description: "Markdown checklist (- [ ] ...), each item traced to a BR id, e.g. '- [ ] (BR-1) ...'"
          required: true
          type: string
        technical_notes:
          description: "Files and functions to touch, the approach and pitfalls"
          required: true
          type: string
        qa:
          description: "The concrete tests this sub-issue adds or extends (file and test names)"
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
            STORY: ${{ github.event.issue.number }}
            MODE: ${{ github.job == 'split_too_large' && 'too_large' || 'split' }}
            RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
          run: |
            python3 -m agents.ai_issue_splitter.apply --repo "$GITHUB_REPOSITORY" --story "$STORY" --mode "$MODE" \
              --agent-output "$GH_AW_AGENT_OUTPUT" --run-url "$RUN_URL"
    split-too-large:
      description: >-
        Report that the story cannot be split into at most 20 sub-issues. Call it instead of create_sub_issue.
      runs-on: ubuntu-latest
      if: needs.detection.result == 'success'
      inputs:
        reason:
          description: "Why, and a suggested split into 2-5 smaller stories (a title and one line each), in Markdown"
          required: true
          type: string
      steps: *apply-steps
---

# AI issue splitter

You are the **splitter** of the code factory. Story issue #${{ github.event.issue.number }} in
${{ github.repository }} is refined. Split it into small sub-issues that developers (AI agents) implement one at a
time, each as one pull request into the story branch.

## Inputs

- `/tmp/gh-aw/agent/story-title.txt` and `/tmp/gh-aw/agent/story.md`: the refined story (Background, Business
  requirements `BR-n`, Technical details, QA).
- The repository is checked out in the current directory. Read `AGENTS.md` first, then the code the story touches.

## How to split

1. Every sub-issue is **one small pull request** (about 1–3 files, tests included) that leaves the code green: lint,
   format and tests pass after it is merged on its own.
2. Together, the sub-issues cover **every** business requirement and the QA section. Each acceptance criterion names
   the BR it implements, e.g. `- [ ] (BR-2) list sorts todos by due date`.
3. Each sub-issue adds or extends its own tests (`qa`). Don't plan a separate "write tests" sub-issue.
4. Dependencies: `depends_on` lists the sub-issues that must be merged first. Prefer a simple chain (S2 depends on
   S1, S3 on S2, ...). Only leave sub-issues independent when they touch different files.
5. Use as few sub-issues as make sense: usually 2–6, never more than 20. A very small story may be one sub-issue.

## What to do

- Call `create_sub_issue` once per sub-issue, in order (S1, S2, ...). Write the fields in Markdown and be concrete:
  name files, functions and test cases from this repository.
- If the story genuinely cannot be done in 20 sub-issues, call `split_too_large` once instead, with the reason and a
  suggested split into smaller stories. Don't call both.
- Don't comment on the issue, change labels or edit files. Branches, issues, links and the story PR are created
  automatically from your tool calls when the run ends.

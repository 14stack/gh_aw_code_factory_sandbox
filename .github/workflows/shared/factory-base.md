---
# Shared configuration imported by every factory agent workflow (SPEC §9).
# Note: imports cannot carry `engine:` settings, so each workflow declares its own BYOK engine block.
# `models.default-ai-credits-pricing` does merge from imports (first-wins).
github-app:
  client-id: ${{ vars.FACTORY_APP_CLIENT_ID }}
  private-key: ${{ secrets.FACTORY_APP_PRIVATE_KEY }}
# OpenRouter models are not in gh-aw's pricing catalog; without a price the API proxy rejects every request.
# Fallback rate in $ per 1M tokens, set slightly above z-ai/glm-5.3-flash (~$0.09 in / $0.30 out on OpenRouter)
# so max-ai-credits budgets stay meaningful. Raise it if FACTORY_MODEL points at a pricier model.
models:
  default-ai-credits-pricing:
    input: 0.1
    output: 0.35
# Workaround for a gh-aw 0.92.4 bug (P0 finding F8): safeoutputs is always mounted as a shell CLI, and each CLI call
# appends to /tmp/gh-aw/mcp-cli-audit/safeoutputs.jsonl. Secret redaction mistakes that audit log for safe-output
# records (same file name), deletes it and fails the agent job, so every safe output of the run is lost.
# Occupying the path with a directory makes the (best-effort, try/catch) audit write fail harmlessly.
# Remove once gh-aw no longer matches mcp-cli-audit/safeoutputs.jsonl in redact_secrets.
pre-agent-steps:
  - name: Guard safe-output redaction against the CLI audit log (gh-aw F8 workaround)
    run: mkdir -p /tmp/gh-aw/mcp-cli-audit/safeoutputs.jsonl
# No gh-aw housekeeping issues in product repos: failure reports, the detection-runs tracking issue and no-op
# reports are all off. Failures stay visible in the Actions tab; the orchestrator flags stuck items with
# factory:ai_needs_human (SPEC §13).
safe-outputs:
  report-failure-as-issue: false
  threat-detection:
    report-as-issue: false
  noop:
    report-as-issue: false
---

## Factory conventions

- You are one agent in the gh_aw_code_factory pipeline. State lives in issue labels and issue bodies.
- **Never communicate through issue comments.** Write to the issue body or use the configured safe outputs only.
- Only change the labels you are explicitly told to change.
- Call safe-output tools (labels, issue updates, PRs, reviews, merges) **directly as MCP tools**. Do not run the
  `safeoutputs` shell command, and pass only the parameters the tool schema lists.

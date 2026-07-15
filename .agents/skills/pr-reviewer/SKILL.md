---
name: pr-reviewer
description: 'Multi-agent pull request reviewer tailored specifically for Sub4 (Laravel 12, React 18, Pest 3.8). Use ONLY when explicitly asked to perform a code review, check a PR, or review a branch: review PR #N, review this PR, code review this branch, check this pull request. Do NOT use for active coding, feature implementation, debugging sessions, or general coding questions.'
license: CC-BY-4.0
metadata:
  author: Sub4 Team
  version: 1.0.0
---

# PR Review — Sub4 Orchestration Protocol

Coordinates 6 specialized subagents to perform comprehensive pull request and code quality reviews tailored specifically to the Sub4 architecture, then consolidates the findings into a single unified summary. Each subagent dynamically loads relevant Sub4 project guidelines to avoid duplicate information.

## Step 1: Initialize

1. Identify the PR number or target branch from context. If not found, ask the user.
2. Identify repository information: `gh repo view --json nameWithOwner -q .nameWithOwner` or check git config.
3. Fetch the full changes/diff: `gh pr diff {PR_NUMBER}` or `git diff {TARGET_BRANCH}`.
4. Load existing PR review comments to avoid posting duplicates: `gh api repos/{REPO}/pulls/{PR_NUMBER}/comments` (parse to construct a set of `{path, line}` pairs already reviewed).
5. Load PR metadata: `gh pr view {PR_NUMBER} --json title,body,headRefName`.
6. Scan for any linked GitHub Issues or Projects reference in the branch name or PR body.

## Step 2: Launch Subagents in Parallel

Launch **six specialized subagents** concurrently using the `invoke_subagent` tool. Pass the PR diff, repo metadata, branch context, existing comments, and instructions to each subagent. Each subagent has a dedicated focus domain and must load the relevant Sub4 guideline files before starting.

---

## Severity Labels

All subagents must categorize findings using these exact labels:
- 🚨 Critical — Bugs, syntax/type errors, security flaws, or logic gaps that will cause operational failures or violate core constraints.
- 🔒 Security — Exposure of credentials, hardcoded secrets, authorization bypasses, or lack of request verification/sanitization.
- ⚡ Performance — Eloquent N+1 queries, heavy loops, database queries in views, or unoptimized React rendering.
- ⚠️ Warning — Code smells, architectural patterns violation, or failure to follow documentation best practices.
- 💡 Suggestion — Non-critical improvements, readability updates, or optional refactoring ideas.

---

## Universal Rules (All Subagents Must Follow)

1. **Comment allowlist:** Only propose comments on lines starting with `+` in the diff (new or modified lines, excluding file header definitions like `+++`).
2. **Avoid duplicates:** Do not comment on any `{path, line}` location that already has a comment from a previous review.
3. **Praise good code:** Highlight at least one well-designed or high-quality aspect of the code changes to keep reviews encouraging and constructive.
4. **80% Confidence threshold:** Only report findings when you are at least 80% confident. If in doubt, skip the comment.
5. **No direct mutations:** Never approve, request changes, or commit changes directly. Report issues via comments.
6. **Marker prefix:** Start every comment body with an invisible marker prefix: `<!-- cursor-review:{type} -->` (e.g. `<!-- cursor-review:security -->`). This is used for consolidation in Step 3.

---

## Subagent 1: Security & Validation

**Role Name:** Sub4 Security Reviewer
**Marker:** `<!-- cursor-review:security -->`

Load `docs/skills/03-validation-forms.md` and `AGENTS.md` (Backend & Validation section) before analyzing. Review the PR diff for any security or validation violations:
- Any backend action receiving user input without a dedicated `FormRequest` class (FormRequest is mandatory for all requests).
- Missing validation rules for critical input fields (like IDs, emails, arrays).
- Hardcoded secrets or credentials in `.env`, config files, or code.
- Missing Laravel Sanctum auth guards (`auth:sanctum`) or Spatie permission middleware/checks on new routes.
- SQL injection vulnerabilities or raw queries in Eloquent.
- Exposure of raw entities or sensitive columns in JSON responses (ensure DTOs/Resources are used instead).

**Comment format:**
```
<!-- cursor-review:security -->
🔒 Security — [Short title]
[Description of the vulnerability or validation gap and why it is high-risk]
**Recommendation:** [Specific, secure code fix]
```

---

## Subagent 2: Requirements, GitHub Issues & Tasks

**Role Name:** Sub4 Requirements Reviewer
**Marker:** `<!-- cursor-review:requirements -->`
**Posts:** One high-level summary review comment only (no inline comments unless a task is directly broken on a specific line).

Review the PR for compliance with the planned requirements and tasks:
1. Extract linked issue or branch name details.
2. Check for spec files under `.specs/` or task lists under `.specs/**/tasks.md` matching the feature.
3. Query the GitHub Issue or Project details using `gh issue view {TICKET_NUMBER}` or GitHub MCP if configured.
4. Verify whether all completed items in `tasks.md` match the code changes in the diff.
5. Identify any missed acceptance criteria or uncompleted tasks.

**Comment format:**
```markdown
<!-- cursor-review:requirements -->
## 📋 Requirements & Tasks Review

**GitHub Issue:** {e.g. #42 | "None found"}
**Spec Files Found:** {e.g. `.specs/features/pre-cadastros-reservas-ui/tasks.md` | "None"}

### ✅ Verified Tasks
{Bulleted list of completed tasks matching implementation}

### ❌ Incomplete / Missing Requirements
{Bulleted list of requirements or tasks from spec/tasks.md that were missed or partially implemented}

### 💬 Review Notes
```

---

## Subagent 3: Test Coverage & Quality

**Role Name:** Sub4 Test Reviewer
**Marker:** `<!-- cursor-review:testing -->`

Load `docs/skills/04-testing-patterns.md` and `AGENTS.md` (Test Framework guidelines) before starting. Review the PR diff for:
- Lack of feature/unit tests under `tests/Feature/` or `tests/Unit/` for new controllers, methods, or models.
- Incorrect use of Pest 3.8 assertions or hooks.
- Incorrect test setup (missing `actingAs(User::factory()->create())` for protected routes).
- Missing assertions for database persistence (`assertDatabaseHas`) or frontend pages (`assertInertia`).
- Hardcoded test values instead of utilizing Factories/Faker.
- Proper test coverage for both happy paths and validation error paths.

**Comment format:**
```
<!-- cursor-review:testing -->
[🚨/⚠️/💡] Test Coverage — [Short title]
[Explain what test is missing or how the current test violates testing guidelines]
**Recommendation:** [Provide a high-quality Pest test snippet]
```

---

## Subagent 4: Architecture & Coding Patterns

**Role Name:** Sub4 Architecture Reviewer
**Marker:** `<!-- cursor-review:architecture -->`

Load `AGENTS.md` (Backend & Frontend Principles) and all skill files in `docs/skills/` (especially `01-backend-patterns.md`, `02-frontend-patterns.md`, `05-database-models.md`, `06-frontend-prototyping.md`). Review the PR for structural adherence:
- **Backend**: Fico/thin controllers (only orchestration, maximum index/create/store/show/edit/update/destroy methods). Business logic delegated to Actions/Services. Correct type-hinting on request/methods.
- **Models**: Scopes used for complex queries, Eloquent relationships well-defined with timestamps, casts correctly configured.
- **Frontend**: React components must be fully typed (TypeScript) with explicit props interfaces.
- **Forms**: Must use Inertia's `useForm` hook (never useState for inputs). Navigation must use `Link` or `router` with `preserveScroll: true`.
- **Imports**: Ensure proper path aliases (`@/*`) are used for frontend imports.

**Comment format:**
```
<!-- cursor-review:architecture -->
[🚨/⚠️/💡] Architecture — [Short title]
[Explain which rule in AGENTS.md or docs/skills/ is violated with reference to the code]
**Recommendation:** [Refactored code snippet following patterns]
```

---

## Subagent 5: Regression & AI Artifact Detection

**Role Name:** Sub4 Regression Reviewer
**Marker:** `<!-- cursor-review:regression -->`

Scan the PR diff for signs of AI hallucinations, dead code, or unintended regressions:
- Ghost imports (importing modules or files that do not exist).
- Unintended deletions or reversions of unrelated files or lines of code.
- Swallowed errors (catch blocks that do nothing or silently log without throwing).
- Unfinished code or `TODO` annotations left in production files.
- Duplicate implementations of helper functions that already exist in the codebase.
- Typo bugs or missing parameter arguments in function/method calls.

**Comment format:**
```
<!-- cursor-review:regression -->
[🚨/⚠️/💡] Regression Guard — [Short title]
[Describe the issue: hallucination, ghost import, swallowed error, or dead code]
**Recommendation:** [Clear step to fix]
```

---

## Subagent 6: Database & Performance

**Role Name:** Sub4 Performance Reviewer
**Marker:** `<!-- cursor-review:performance -->`

Load `docs/skills/05-database-models.md` and `AGENTS.md` (Database section). Analyze the PR diff for performance bottlenecks:
- N+1 Eloquent query bugs (retrieving models in a loop, missing `with()` eager-loading).
- Unbounded database queries (using `all()` instead of `paginate(15)` or `limit()`).
- Database query execution directly inside React pages/views or Blade templates.
- Missing indexes on foreign keys or columns frequently used in where/order clauses in migrations.
- Heavy operations running synchronously in request flows instead of being queued.

**Comment format:**
```
<!-- cursor-review:performance -->
⚡ Performance — [Short title]
[Explain the performance bottleneck and the estimated scaling impact]
**Recommendation:** [Eager loading, query refactoring, or pagination suggestion]
```

---

## Step 3: Consolidation

After all 6 subagents complete, run a final consolidation step (by spawning a consolidation agent) to compile all findings into a unified, high-impact pull request review summary:

1. Fetch all proposed review comments containing the `<!-- cursor-review: -->` markers.
2. Group the findings logically by severity: 🔒 Security ➡️ 🚨 Critical ➡️ ⚡ Performance ➡️ ⚠️ Warnings ➡️ 💡 Suggestions.
3. Deduplicate comments at identical or adjacent lines.
4. Construct a clear list of files that were modified but had **no findings** from any reviewer (verifying they are clean).
5. Compile the positive highlights from each subagent into a dedicated section.
6. Format the final summary using the Markdown template below and post it as a review summary.

### Consolidated Summary Template

```markdown
## 🤖 Sub4 Pull Request Review Summary

| Metadata | Details |
|---|---|
| **Subagents Invoked** | 6 of 6 (Security · Requirements · Testing · Architecture · Regression · Performance) |
| **Guidelines Loaded** | `AGENTS.md`, `docs/skills/*.md` |
| **Total Findings** | {N} findings across {M} files |

---

### 🔒 Security ({N})
- [`{file_basename}:{line}`](file:///{absolute_path}#L{line}): **{Title}** — {Brief summary}

### 🚨 Critical ({N})
- [`{file_basename}:{line}`](file:///{absolute_path}#L{line}): **{Title}** — {Brief summary}

### ⚡ Performance ({N})
- [`{file_basename}:{line}`](file:///{absolute_path}#L{line}): **{Title}** — {Brief summary}

### ⚠️ Warnings ({N})
- [`{file_basename}:{line}`](file:///{absolute_path}#L{line}): **{Title}** — {Brief summary}

### 💡 Suggestions ({N})
- [`{file_basename}:{line}`](file:///{absolute_path}#L{line}): **{Title}** — {Brief summary}

---

### 🔍 Verified Files With No Findings
{Bulleted list of files changed in the PR that had zero comments, validating they are clean}

---

### ✅ Highlights & Best Practices Observed
- **Security**: {Positive security highlight}
- **Testing**: {Positive test coverage highlight}
- **Architecture**: {Positive architectural patterns highlight}

---
> Please see the individual inline comments on the pull request diff for specific code recommendations.

## Examples

### Example 1: Full PR review request

User says: "Hey, can you review pull request #12 for me?"
Actions:
1. Detects command and extracts PR number 12.
2. Runs gh repo view to identify the repository name.
3. Runs gh pr diff 12 to fetch the changes.
4. Identifies the corresponding spec/task file: .specs/features/pre-cadastros-reservas-ui/tasks.md.
5. Spawns 6 subagents to analyze the diff against Security, Requirements, Testing, Architecture, Regression, and Performance guidelines.
6. The consolidation agent receives findings, compiles positive highlights, lists clean files, and formats the output.
Result: The agent posts inline comments for each specific finding and writes a high-impact consolidated review summary in the chat.

### Example 2: Local branch review request

User says: "Can you perform a code review on my current branch before I push?"
Actions:
1. Detects local review request.
2. Runs git diff develop to find differences between the current branch and develop.
3. Spawns 6 subagents to check the local diff against Sub4's coding, database, and testing patterns.
4. Synthesizes findings and highlights.
Result: The agent presents a structured markdown table listing all findings with line links and recommendations.

## Troubleshooting

### Error: `gh: command not found`
- **Cause**: The GitHub CLI is not installed or configured in the current shell/container.
- **Solution**: Fall back to using standard git commands (`git diff`, `git log`) for local branches, and inspect files directly in the codebase using standard workspace tool lookups.

### Error: `mcp server error`
- **Cause**: The GitHub MCP server is disconnected or lacks API permissions.
- **Solution**: Fetch issue/PR details using `gh issue view` or ask the user to provide the description/tasks manually.

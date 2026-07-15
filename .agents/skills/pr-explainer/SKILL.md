---
name: pr-explainer
description: Analyzes a Laravel + Inertia + React Pull Request, explains the architectural decisions (e.g. Action vs Controller, eager loading, Pest tests) in an educational way, and exports a premium self-contained HTML report. Use when the user asks to "explain PR", "PR explainer", "explain this pull request", or "generate PR explanation html". Do NOT use for active coding or writing pull request descriptions in markdown.
license: CC-BY-4.0
metadata:
  author: Antigravity AI
  version: 1.0.0
---

# PR Explainer Skill

This skill acts as an educational and architectural explainer for Pull Requests (PRs). It analyzes current branch changes (diffs and commits) against the target branch (`develop`), reviews them through the strict lens of the **Sub4 Project Rules** (Laravel 12, Inertia 2.0, React 18, TypeScript, Tailwind 3.2, Pest 3.8), and generates a premium, interactive, self-contained HTML report detailing the "why" behind each architectural decision.

---

## Instructions

### Step 1: Collect Git Context & Code Changes

When triggered, retrieve the current branch name and analyze its differences against the `develop` branch.
1. Run `git rev-parse --abbrev-ref HEAD` to identify the current branch.
2. Run `git log develop..HEAD --oneline` (or `git log -n 10 --oneline` if not on a branch branch yet) to retrieve the commit history.
3. Run `git diff --name-status develop` to see the modified and new files.
4. For each relevant file changed, read its diff using `git diff develop -- [filepath]` or view the file contents directly if it is a newly added file to understand the full context of the implementation.

*Troubleshooting:* If there is no `develop` branch or if it fails, fallback to comparing against the most recent merge-base or the `main` branch.

---

### Step 2: Conduct Educational Architectural Analysis

Analyze all modifications file-by-file. Your analysis must be highly educational, explaining software engineering decisions in detail. You must check the changes against the **Sub4 Project Rules** (`AGENTS.md` and `docs/skills/` references) and explain the following concepts if present in the code:

#### A. Backend (Laravel 12)
- **Controller Fineness:** Verify that controllers are extremely thin and only orchestrate requests. Explain why business logic was moved to Action classes and why this makes the application highly maintainable and decoupling-friendly (e.g., reusable in controllers, CLI commands, and job queues).
- **Actions & Services:** Highlight new Action classes in `app/Application/{Module}/Actions/`. Explain how they act as isolated single-responsibility domain services and how dependency injection handles their instantiation.
- **Model Scopes & Queries:** Verify that queries with joins or multiple `where` clauses are placed inside Model scopes (e.g., `scopeActive($query)`), rather than in the Controller. Explain why centralizing queries keeps the DB schema changes in one place and prevents query duplication.
- **FormRequests & Validations:** Analyze validation classes (`StoreXRequest`, `UpdateXRequest`). Explain rules, authorization, and how translating custom validation messages to Portuguese (`pt_BR`) enhances user experience. Explain the `withValidator` method if used for custom cross-field validations.
- **DTOs (Data Transfer Objects):** Highlight DTO usage in `app/DTO/` for safe, strongly-typed data passing between layers. Explain why this prevents array-shape errors.
- **Database & Query Optimization:** Identify the use of transactions (`DB::transaction`) for multi-write operations, constraints, indexes, and eager loading (`with(['relation'])`). Explain to the reader how eager loading solves the classic "N+1 query problem" by loading relations in a single optimized SQL join.

#### B. Frontend (React 18 & Inertia)
- **TypeScript and Typings:** Verify component props are fully typed using interfaces (`interface PageProps { ... }`). Detail the advantages of TypeScript in catching runtime errors early during compilation.
- **Inertia useForm Hook:** Analyze the usage of `useForm` from `@inertiajs/react` instead of standard `useState` for handling forms. Explain why `useForm` is preferred (automatic handling of `processing` states, validation errors from Laravel backend, form data resetting).
- **Navigation & Page Transitions:** Identify usage of `Link` and router methods (`router.post`, `router.put`, etc.). Explain why `preserveScroll: true` is crucial to maintain page scroll position during server-side state updates.
- **Reusability of UI Components:** Highlight the extraction of form/UI elements into specialized components inside `resources/js/Components/` or `Partials/` for high DRY adherence.

#### C. Testing (Pest 3.8)
- **Testing Coverage & Strategy:** Inspect test suites under `tests/Feature/` or `tests/Unit/`. Explain Pest's intuitive syntax, how `actingAs` handles authentication, and why verifying both the "happy path" (successful creation/redirect) and validation failures (`assertInvalid`) is essential.

---

### Step 3: Populate the Premium HTML Template

1. Read the premium HTML template from `.agent/skills/pr-explainer/assets/template.html`.
2. Construct a single, fully structured JSON payload representing the PR details. This JSON must strictly adhere to the schema expected by the template.
   > [!IMPORTANT]
   > CRITICAL: You MUST programmatically serialize this JSON payload using a robust JSON serializer (such as Python's `json.dumps()` or Node's `JSON.stringify()`) to ensure that all literal newlines, tabs, backslashes, and double quotes inside the source code files are perfectly escaped as JSON control characters. Writing literal unescaped newlines inside JSON double-quotes will cause a fatal `SyntaxError` in the browser, rendering the dashboard completely blank/empty.
3. Replace the contents of the `<script id="pr-explainer-data" type="application/json">` tag with this perfectly serialized JSON string.
4. Save the completed file in the root of the project workspace under the name `pr-explanation-[branch-name].html` (replacing slashes in branch names with hyphens, e.g., `pr-explanation-feature-reservas-pipeline-backend.html`).

#### Expected JSON Payload Schema:
```json
{
  "prTitle": "Descriptive and educational title of the PR",
  "prBranch": "feature/branch-name",
  "targetBranch": "develop",
  "author": "Author Name (e.g. Antigravity AI)",
  "date": "YYYY-MM-DD",
  "summary": "Detailed markdown-compatible paragraph summarizing the PR's goals and content.",
  "impactAnalysis": {
    "businessValue": "Explain the business value of this PR in a clear, narrative style.",
    "technicalImpact": "Explain the technical impact, architectural additions, and quality improvements."
  },
  "commits": [
    {
      "hash": "7-char-commit-hash",
      "message": "Commit title",
      "author": "Commit author",
      "date": "YYYY-MM-DD HH:MM",
      "explanation": "Brief explanation of what this commit implemented and its architectural relevance."
    }
  ],
  "files": [
    {
      "filePath": "relative/path/to/file.php",
      "status": "added | modified | deleted",
      "fileType": "Action | Controller | Model | FormRequest | Test | TSX Page | Other",
      "title": "Clear readable title of the file's role",
      "changesSummary": "Narrative explaining the exact modifications made in this file. Be thorough and cover all changed/added files in the Pull Request.",
      "whyDecision": "Deep educational rationale explaining why this file was structured this way (e.g., 'An Action class was created to isolate the booking calculations away from the Controller, complying with Sub4 thin-controller rules and allowing cli reuse.')",
      "techniquesUsed": [
        "Bullet points describing specific techniques (e.g., 'Eager loading with(['rooms']) to prevent N+1 queries', 'DB::transaction to ensure all writes succeed or roll back together.')"
      ],
      "codeHighlights": [
        {
          "title": "Title of the highlight (e.g., Native DI in Action)",
          "code": "The exact source code snippet containing the technique",
          "explanation": "A line-by-line explanation of why this code block is elegant or necessary."
        }
      ],
      "fullCode": "The complete source code of the file being explained, so it can be rendered inside the scrollable code editor panel in the interactive HTML dashboard."
    }
  ],
  "tests": [
    {
      "testPath": "tests/Feature/ExampleTest.php",
      "summary": "Description of the test suite and its goal.",
      "assertions": [
        "Visual bullet point detailing a validated behavior (e.g. 'Asserts that room validation fails with invalid dates.')"
      ]
    }
  ],
  "educationalTakeaways": [
    {
      "title": "Name of the concept (e.g., Action Pattern, Eager Loading)",
      "content": "A detailed educational guide explaining the computer science / framework principle, how Laravel handles it, and best practices."
    }
  ]
}
```

---

### Step 4: Present Interactive Summary to User

When the HTML generation completes, output a concise response in the chat:
1. Provide a professional and elegant markdown summary of the PR.
2. Share the educational highlights of the architectural review.
3. Provide the absolute file URL of the generated HTML report (e.g., `file:///C:/absolute/path/to/project/pr-explanation-branch-name.html`) so the user can click it directly to open the dashboard in their browser.
4. Highlight 1 or 2 architectural suggestions or "next steps" to further polish the code.

---

## Examples

### Example 1: Explaining a Reservas Pipeline feature PR

User says: "crie a explicação deste PR da pipeline de reservas"
Actions:
1. Runs git commands to discover the current branch is `feature/reservas-pipeline-backend` and finds 5 commits.
2. Analyzes files: `StoreReservaAction.php`, `ReservaController.php`, `PublicFormSubmission.php` (Model scope added), `StoreReservaRequest.php`, and `StoreReservaTest.php`.
3. Drafts educational explanations for each file, explicitly mapping decisions to Sub4 stack guidelines.
4. Reads `template.html`, builds the JSON payload containing the complete review, escapes the code highlights properly, injects the JSON, and writes `pr-explanation-feature-reservas-pipeline-backend.html`.
5. Outputs a beautiful, humble summary with the clickable `file:///` path link.

---

## Troubleshooting

### Error: Missing Git History or Commit Range
- *Cause:* The user workspace might not have a `develop` branch fetched locally, or HEAD is currently detached.
- *Solution:* Fallback to comparing the current branch against `main`, or compare the last 3 local commits against their parent commit (`HEAD~3..HEAD`). Inform the user in the final summary of the fallback range used.

### Error: Dynamic Code Rendering Displays Raw Tags
- *Cause:* Special HTML characters inside `codeHighlights` (like `<` or `>`) were not escaped in the JSON payload, breaking Highlight.js parsing.
- *Solution:* Make sure to escape all special characters inside `codeHighlights[].code` using standard escaping rules (convert `&` to `&amp;`, `<` to `&lt;`, `>` to `&gt;`, `"` to `&quot;`) before injecting the JSON string.

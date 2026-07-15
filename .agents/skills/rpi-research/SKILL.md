---
name: rpi-research
description: Conducts the Research phase of the RPI (Research → Plan → Implement) methodology. The agent autonomously explores the codebase, discovers relevant files with line numbers, analyzes patterns, and generates a complete research.md document plus a GitHub issue (PRD) ready to be used as input for the Planning phase (tlc-spec-driven). Use when: "research this feature", "fazer research", "RPI research", "pesquisar feature", "levantar contexto", "iniciar RPI", "preparar planning". Do NOT use for planning (use tlc-spec-driven), implementing (separate skill), or reviewing PRs (use pr-reviewer).
license: CC-BY-4.0
metadata:
  author: Nícolas Evangelista - github.com/nicksns
  version: 1.0.0
---

# RPI Research

Conducts the Research phase of the RPI methodology. You autonomously explore the codebase, collect all context an AI agent needs to plan and implement a feature, and produce a structured research document — without writing any code.

**Goal of Research:** Compact the context window. Discover relevant files + line numbers, understand the business need, define acceptance criteria, and list tasks/fixes — so the Planning phase (tlc-spec-driven) can work without re-exploring the codebase.

## Instructions

### Step 0: Clarify Scope (if needed)

Before exploring, confirm with the user:
- **Feature name** — used for the output file path and GitHub issue title
- **Type of work** — new feature, bug fixes, refactor, or mix
- **Initial task/fix list** — if the user already has a list of tasks or bugs, collect it now. If not, you will discover it during exploration.
- **UI reference** — ask the user to share screenshots or images of the current state if relevant.

If the user already provided all of this in their prompt, skip to Step 1 immediately.

### Step 1: Explore the Codebase

Explore systematically using grep, file reads, git log, and directory listing. Follow the Knowledge Verification Chain:

```
1. Read AGENTS.md and docs/skills/README.md to understand project conventions
2. grep for the feature's entities (model names, route names, component names)
3. Read the most relevant files to understand current state and patterns
4. Check existing similar CRUDs/features to understand conventions in use
5. Check git log for recent changes related to the feature
6. Check prototypes at resources/js/Prototipos/ if they exist for the feature
```

**What to collect for each relevant file:**
- Absolute path
- Status: `[EXISTING]`, `[ADDED]`, `[MODIFIED]`, `[DELETED]`, `[PROTOTYPE]`
- Key line numbers of important sections (e.g., `L45-L78: Status enum values`)
- Brief note on why it's relevant

**Scope of exploration — always check:**
- Backend: Models, Enums, Controllers, Actions, FormRequests, Migrations, Routes
- Frontend: Pages, Partials, Components, Hooks, Types, Configs, Prototypes
- Tests: Feature and Unit tests related to the entities
- Database: Existing migrations for the relevant tables

### Step 2: Analyze Patterns

Before writing the document, extract:
- How similar CRUDs are structured in this project (follow AGENTS.md conventions)
- Which existing components and Actions can be reused
- Potential conflicts or risks (e.g., legacy fields, breaking changes)
- Whether a StatusMachine or similar pattern is already used for similar flows

### Step 3: Build the Research Document

Write the document to `.specs/features/[feature-name]/research.md`. Create the directory if it doesn't exist. Use this exact structure:

```markdown
# Research: [Feature Name]

**Data:** [current date]
**Autor:** [ask user if unknown]
**Tipo:** [Nova Feature | Bug Fixes | Refactor | Mix]

---

## Contexto

[2-4 paragraphs describing: what this part of the system does, what already exists,
what problem the user/team wants to solve, and what the expected result looks like.
Be specific — mention model names, component names, routes.]

---

## Objetivos

[Bullet list of what the feature/fix must accomplish from a business/user perspective.
Focus on WHAT, not HOW. Example: "Permitir que o usuário gere links de pagamento
sem precisar selecionar um evento primeiro."]

---

## Critérios de Aceite

- [ ] [Specific, testable checkbox — one per requirement]
- [ ] [Each checkbox must be verifiable: "Ao selecionar data 9AM, exibe 9AM na UI"]
- [ ] [Include both happy path and edge cases]

---

## Tasks / Fixes

[Numbered list of tasks or fixes to implement. If the user provided them, reproduce
and expand them. If discovered during exploration, list them with context.]

1. [Task or fix description]
2. ...

---

## Arquivos Relevantes

### Backend

| Arquivo | Status | Linhas-Chave | Relevância |
|---------|--------|--------------|------------|
| `app/Models/Foo.php` | EXISTING | L12-L45: fillable, casts | Model principal da feature |
| `app/Enums/FooStatus.php` | EXISTING | L1-L30: enum values | Status atual, precisa de novos valores |
| ... | | | |

### Frontend

| Arquivo | Status | Linhas-Chave | Relevância |
|---------|--------|--------------|------------|
| `resources/js/Pages/Foo/Index.tsx` | EXISTING | L80-L120: tabela principal | Ponto de entrada da feature |
| `resources/js/Prototipos/Foo/...` | PROTOTYPE | — | Referência de design/comportamento |
| ... | | | |

### Testes

| Arquivo | Status | Linhas-Chave | Relevância |
|---------|--------|--------------|------------|
| `tests/Feature/Foo/FooTest.php` | EXISTING | L1-L50 | Testes existentes a manter |
| ... | | | |

---

## Padrões e Convenções Aplicáveis

[Key patterns from AGENTS.md and the existing codebase that MUST be followed
during Planning and Implementation. Examples:]

- Actions seguem padrão de `app/Application/[Module]/Actions/`
- FormRequests com messages em pt_BR
- Frontend usa `useForm` do Inertia, nunca `useState` para inputs
- Componentes reutilizáveis em `resources/js/Components/`
- [Other project-specific patterns discovered during exploration]

---

## Riscos e Observações

[Anything that could cause problems during implementation:]
- [Legacy compatibility concerns]
- [Potential conflicts with other features/branches]
- [Breaking changes]
- [Performance concerns]

---

## Referências

- Protótipo: `resources/js/Prototipos/[Feature]/` (se existir)
- Skill de Planning: `.agent/skills/tlc-spec-driven`
- AGENTS.md: `./../AGENTS.md`
- [Other relevant docs]
```

### Step 4: Create GitHub Issue (PRD)

After the research.md is written, create a GitHub issue to serve as the PRD:

1. **Title:** `[Research] [Feature Name] — PRD`
2. **Labels:** use existing labels; suggest `documentation` or `planning` if available
3. **Body:** Copy the full content of research.md into the issue body
4. Use the `gh` CLI or GitHub MCP tool (`github-mcp-server`) to create the issue

If GitHub access is unavailable, skip this step and inform the user.

### Step 5: Present Summary

After completing the research, present to the user:

```
✅ Research concluído!

📄 Arquivo: .specs/features/[feature-name]/research.md
🐙 Issue GitHub: #[number] — [title]

📊 O que foi descoberto:
- [N] arquivos relevantes mapeados (backend + frontend + testes)
- [N] tasks/fixes identificadas
- [N] critérios de aceite definidos

⚠️ Riscos identificados: [brief list or "nenhum"]

➡️ Próximo passo: use a skill tlc-spec-driven e aponte o research.md como contexto
   Exemplo: "use tlc-spec-driven para criar a spec de [feature], contexto em .specs/features/[feature]/research.md"
```

---

## Important Rules

- **NEVER write application code.** Research is read-only (except writing the research.md output file).
- **NEVER skip file exploration.** A research document without real file paths and line numbers is useless for Planning.
- **Line numbers are mandatory** for every file in the "Arquivos Relevantes" table. Read the file to get them.
- **Follow AGENTS.md conventions.** Read it at the start of every research session.
- **Criteria of acceptance must be testable.** "Funcionar corretamente" is NOT an acceptance criterion.
- **If tasks were NOT provided by the user**, explicitly label discovered tasks as `[Descoberto durante pesquisa]` so the user knows they may need review.

---

## Examples

### Example 1: Bug fixes on existing feature

User says: *"fazer research nos fixes da área de Reservas — tem uns bugs no modal de links e no status de pagamento"*

Actions:
1. Ask: feature name (`reservas-pipeline-fixes`), confirm user will share screenshots
2. grep for `PublicFormSubmission`, `ReservaLink`, `reserva_status` across the codebase
3. Read `PublicFormSubmission.php`, `PublicFormSubmissionStatus.php`, `ReservaLinkModal.tsx`, `helpers.ts`, `reservasStatusConfig.ts`
4. Check protótipo at `resources/js/Prototipos/Reservas/`
5. Check `routes/web.php` for existing routes
6. Write `.specs/features/reservas-pipeline-fixes/research.md` with all findings
7. Create GitHub issue #PRD

Result: A complete research.md with all files mapped, fixes described with context, acceptance criteria checkboxes, and a GitHub issue.

### Example 2: New CRUD feature

User says: *"research feature de Pagamentos — novo CRUD completo"*

Actions:
1. Ask: entity name, what business need it serves, any initial requirements
2. grep for similar existing CRUDs (e.g., `Grupo`, `Cliente`) to understand patterns
3. Check existing migrations, models, controllers for the domain
4. Check frontend Pages/ for similar CRUD pages to reuse patterns
5. Check `resources/js/Components/` for reusable UI components
6. Write `.specs/features/pagamentos/research.md`
7. Create GitHub issue #PRD

Result: research.md structured around what needs to be created vs adapted, with clear references to existing patterns to follow.

---

## Troubleshooting

### "Não consigo encontrar os arquivos da feature"

Cause: The feature name used in grep doesn't match the actual entity names.
Solution: Try alternative names (e.g., Portuguese and English versions), check `routes/web.php` for route names, check `resources/js/Pages/` for page directories.

### "GitHub issue creation failed"

Cause: `gh` CLI not authenticated or GitHub MCP not available.
Solution: Inform the user, provide the research.md path, and suggest they create the issue manually from the file content.

### "O usuário não forneceu lista de tasks"

Cause: User wants the agent to discover what needs to be done.
Solution: Based on your codebase exploration, create a task list marked `[Descoberto durante pesquisa]` and present it to the user for validation before writing the final document.

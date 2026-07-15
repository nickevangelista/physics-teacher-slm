# Physics Teacher SLM Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user — do not proceed without it.**

---

**Design**: `.specs/features/physics-teacher-slm/design.md`
**Status**: Draft

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec — confirm before Execute. Guidelines found: none — strong defaults applied.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| PDF Extraction | unit | Test PDF parsing logic and output formatting | `tests/test_extract_pdfs.py` | `python -m unittest tests/test_extract_pdfs.py` |
| Dataset Prep | unit | Validate ChatML formatting and dataset properties | `tests/test_prepare_dataset.py` | `python -m unittest tests/test_prepare_dataset.py` |
| RAG Indexing | integration | Verify ChromaDB index population and query capability | `tests/test_rag.py` | `python -m unittest tests/test_rag.py` |
| Gradio UI | integration | Test Gradio app startup and connection to Ollama API | `tests/test_ui.py` | `python -m unittest tests/test_ui.py` |

## Parallelism Assessment

> Generated from codebase — confirm before Execute.

| Test Type | Parallel-Safe? | Isolation Model | Evidence |
| --- | --- | --- | --- |
| unit | Yes | Isolated test mocks. | No external database or local service calls. |
| integration | No | Depends on local Ollama service and local database file locks. | Shares ChromaDB directory paths and requires Ollama server to be up on port 11434. |

## Gate Check Commands

> Generated from codebase — confirm before Execute.

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | After tasks with unit tests only | `python -m unittest discover -s tests -p "test_*.py"` |
| Full | After tasks with integration tests | `python -m unittest discover -s tests -p "test_*.py"` |
| Build | After phase completion or config-only tasks | `python -m unittest discover -s tests -p "test_*.py"` |

---

## Execution Plan

### Phase 0: Environment Setup (Sequential)
Install necessary dependencies, Python 3.12, virtual environment, and pull base models.
```
T1 → T2 → T3 → T4 → T5 → T6
```

### Phase 1: Data Pipeline (Sequential)
Copy original PDFs, run extraction, and prepare ChatML dataset.
```
T6 → T7 → T8 → T9
```

### Phase 2: RAG Pipeline (Sequential)
Build Vector Database index and test retrievals.
```
T9 → T10 → T11
```

### Phase 3: Fine-Tuning QLoRA (Sequential)
Run training on low-VRAM settings and export model to GGUF format.
```
T11 → T12 → T13
```

### Phase 4: Deploy (Sequential)
Deploy custom model to local Ollama.
```
T13 → T14 → T15
```

### Phase 5: Interface Web (Sequential)
Launch and test side-by-side Gradio UI.
```
T15 → T16
```

---

## Task Breakdown

### Phase 0: Environment Setup

#### T1: [Install Build Dependencies]
- **What**: Install Debian packages needed to compile Python 3.12.
- **Where**: CLI command execution.
- **Depends on**: None
- **Requirement**: ENV-01
- **Tools**: CLI
- **Done when**:
  - [x] Compiling tools (`make`, `gcc`, etc.) and development libraries (`libssl-dev`, `libffi-dev`, etc.) are installed.
- **Tests**: none
- **Gate**: build

#### T2: [Compile and Install Python 3.12]
- **What**: Compile and install Python 3.12 using pyenv.
- **Where**: CLI command execution.
- **Depends on**: T1
- **Requirement**: ENV-01
- **Tools**: CLI
- **Done when**:
  - [x] `pyenv install 3.12 -s` completes successfully.
  - [x] `pyenv local 3.12` sets local version.
- **Tests**: none
- **Gate**: build

#### T3: [Install Ollama Engine]
- **What**: Download and install Ollama runner.
- **Where**: CLI command execution.
- **Depends on**: T2
- **Requirement**: ENV-02
- **Tools**: CLI
- **Done when**:
  - [x] Ollama script is installed.
  - [x] Ollama service is verified as running.
- **Tests**: none
- **Gate**: build

#### T4: [Create Venv and PyTorch CUDA]
- **What**: Initialize virtual environment and install PyTorch with CUDA 12.1.
- **Where**: CLI command execution.
- **Depends on**: T3
- **Requirement**: ENV-03
- **Tools**: CLI
- **Done when**:
  - [x] `.venv` is created and activated.
  - [x] PyTorch detects CUDA via `torch.cuda.is_available()`.
- **Tests**: none
- **Gate**: build

#### T5: [Install Python Requirements]
- **What**: Install python dependencies from requirements.txt.
- **Where**: CLI command execution.
- **Depends on**: T4
- **Requirement**: ENV-03
- **Tools**: CLI
- **Done when**:
  - [x] requirements.txt libraries installed in the venv.
- **Tests**: none
- **Gate**: build

#### T6: [Pull Ollama Base Models]
- **What**: Download `qwen2.5:3b` and `nomic-embed-text` to local Ollama.
- **Where**: CLI command execution.
- **Depends on**: T5
- **Requirement**: ENV-02
- **Tools**: CLI
- **Done when**:
  - [x] `ollama pull qwen2.5:3b` and `ollama pull nomic-embed-text` are stored locally.
- **Tests**: none
- **Gate**: build

---

### Phase 1: Data Pipeline

#### T7: [Import PDFs to teacher_docs]
- **What**: Verify that physics PDFs are placed in `teacher_docs/` folder.
- **Where**: `teacher_docs/`
- **Depends on**: T6
- **Requirement**: DATA-01
- **Tools**: CLI
- **Done when**:
  - [ ] Folder contains at least one PDF file.
- **Tests**: none
- **Gate**: build

#### T8: [Extract Text from PDFs]
- **What**: Run `scripts/extract_pdfs.py` to extract raw text to `data/processed/`.
- **Where**: `scripts/extract_pdfs.py`
- **Depends on**: T7
- **Requirement**: DATA-01
- **Tools**: CLI
- **Done when**:
  - [ ] Texts are extracted and stored as `.txt` files.
  - [ ] Unit tests pass verifying parsing/formatting output.
- **Tests**: unit
- **Gate**: quick

#### T9: [Generate Instruction Dataset]
- **What**: Run `training/prepare_dataset.py` to generate the instruction-response dataset.
- **Where**: `training/prepare_dataset.py`
- **Depends on**: T8
- **Requirement**: DATA-02
- **Tools**: CLI
- **Done when**:
  - [ ] `data/physics_dataset.jsonl` contains 200-400 entries in ChatML format.
  - [ ] Unit tests pass verifying ChatML structure validation.
- **Tests**: unit
- **Gate**: quick

---

### Phase 2: RAG Pipeline

#### T10: [Build ChromaDB Index]
- **What**: Run `rag/build_index.py` to index the extracted documents into ChromaDB.
- **Where**: `rag/build_index.py`
- **Depends on**: T9
- **Requirement**: RAG-01
- **Tools**: CLI
- **Done when**:
  - [ ] Vector index populated in `data/chroma_db/`.
  - [ ] Integration tests pass verifying ChromaDB content.
- **Tests**: integration
- **Gate**: full

#### T11: [Test RAG Queries]
- **What**: Run `rag/query_engine.py` to test retrieving and outputting responses.
- **Where**: `rag/query_engine.py`
- **Depends on**: T10
- **Requirement**: RAG-02
- **Tools**: CLI
- **Done when**:
  - [ ] Test query retrieves valid sources and outputs formatting correctly.
  - [ ] Integration tests pass verifying query output.
- **Tests**: integration
- **Gate**: full

---

### Phase 3: Fine-Tuning QLoRA

#### T12: [Run QLoRA Fine-Tuning]
- **What**: Run `training/finetune.py` using Unsloth.
- **Where**: `training/finetune.py`
- **Depends on**: T11
- **Requirement**: TRAIN-01
- **Tools**: CLI
- **Done when**:
  - [x] QLoRA fine-tuning executes successfully on 4GB VRAM without memory errors.
- **Tests**: none
- **Gate**: build

#### T13: [Export GGUF Model]
- **What**: Export the fine-tuned model into GGUF Q4_K_M quant format.
- **Where**: `training/finetune.py`
- **Depends on**: T12
- **Requirement**: TRAIN-02
- **Tools**: CLI
- **Done when**:
  - [x] Valid `.gguf` file exists in `models/physics_model_gguf/`.
- **Tests**: none
- **Gate**: build

---

### Phase 4: Deploy

#### T14: [Register Model in Ollama]
- **What**: Register the GGUF model in Ollama as `physics-teacher` using `models/Modelfile`.
- **Where**: `models/Modelfile`
- **Depends on**: T13
- **Requirement**: DEPLOY-01
- **Tools**: CLI
- **Done when**:
  - [x] `ollama create physics-teacher -f models/Modelfile` succeeds.
  - [x] `ollama list` shows `physics-teacher`.
- **Tests**: none
- **Gate**: build

#### T15: [CLI Model Test]
- **What**: Test the model via Ollama CLI with a physics question.
- **Where**: CLI command execution.
- **Depends on**: T14
- **Requirement**: DEPLOY-01
- **Tools**: CLI
- **Done when**:
  - [x] Custom model replies in Portuguese in the specified teacher style.
- **Tests**: none
- **Gate**: build

---

### Phase 5: Interface Web

#### T16: [Launch Gradio Chat UI]
- **What**: Launch and test the Gradio server `app/chat_ui.py`.
- **Where**: `app/chat_ui.py`
- **Depends on**: T15
- **Requirement**: UI-01
- **Tools**: CLI
- **Done when**:
  - [ ] Web UI loads successfully on port 7860.
  - [ ] Integration tests pass checking side-by-side responses and stream capability.
- **Tests**: integration
- **Gate**: full

---

## Parallel Execution Map

All tasks in this implementation depend sequentially on the prior tasks. No parallel execution is planned since each phase depends directly on files and models created in the prior phase.

```
Phase 0 (Setup):
  T1 ──→ T2 ──→ T3 ──→ T4 ──→ T5 ──→ T6

Phase 1 (Data):
  T6 ──→ T7 ──→ T8 ──→ T9

Phase 2 (RAG):
  T9 ──→ T10 ──→ T11

Phase 3 (Fine-Tuning):
  T11 ──→ T12 ──→ T13

Phase 4 (Deploy):
  T13 ──→ T14 ──→ T15

Phase 5 (Web UI):
  T15 ──→ T16
```

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1 - T6 | Setup environments steps | ✅ Granular |
| T7 | Check folder files | ✅ Granular |
| T8 | PDF extraction script execution | ✅ Granular |
| T9 | Dataset generation execution | ✅ Granular |
| T10 - T11 | Vector store setup and CLI queries | ✅ Granular |
| T12 - T13 | Fine-tuning and export | ✅ Granular |
| T14 - T15 | Deploy and CLI execution test | ✅ Granular |
| T16 | Launch web server UI | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| --- | --- | --- | --- |
| T1 | None | None | ✅ Match |
| T2 | T1 | T1 | ✅ Match |
| T3 | T2 | T2 | ✅ Match |
| T4 | T3 | T3 | ✅ Match |
| T5 | T4 | T4 | ✅ Match |
| T6 | T5 | T5 | ✅ Match |
| T7 | T6 | T6 | ✅ Match |
| T8 | T7 | T7 | ✅ Match |
| T9 | T8 | T8 | ✅ Match |
| T10 | T9 | T9 | ✅ Match |
| T11 | T10 | T10 | ✅ Match |
| T12 | T11 | T11 | ✅ Match |
| T13 | T12 | T12 | ✅ Match |
| T14 | T13 | T13 | ✅ Match |
| T15 | T14 | T14 | ✅ Match |
| T16 | T15 | T15 | ✅ Match |

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| --- | --- | --- | --- | --- |
| T1 - T7 | Environment / Inputs | none | none | ✅ OK |
| T8 | PDF Extraction | unit | unit | ✅ OK |
| T9 | Dataset Prep | unit | unit | ✅ OK |
| T10 | RAG Indexing | integration | integration | ✅ OK |
| T11 | RAG Indexing | integration | integration | ✅ OK |
| T12 - T15 | Fine-Tuning & Deployment | none | none | ✅ OK |
| T16 | Gradio UI | integration | integration | ✅ OK |

---

## Task Verification Standards

Every task follows the `Done when` + `Tests` + `Gate` fields defined in the Task Breakdown. Verification commands run tests under `tests/` directory.

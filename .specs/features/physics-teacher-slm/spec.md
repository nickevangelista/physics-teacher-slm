# Physics Teacher SLM Specification

## Problem Statement

The goal of this project is to build a local Small Language Model (SLM) that mimics the teaching style of a specific physics professor. The model must explain physics concepts using the professor's notation and language, and generate exam questions in the same format, difficulty level, and style as the original materials. Todo o pipeline deve rodar 100% localmente em uma Dell G15 RTX 3050 (4GB VRAM) usando RAG (Retrieval-Augmented Generation) para conhecimento factual e QLoRA Fine-tuning para estilo.

## Goals

- [ ] Build a local SLM that explains physics concepts using the professor's notation and teaching style.
- [ ] Generate exam questions conforming to the format, notation, and difficulty of the original materials.
- [ ] Implement a fully local, reproducible pipeline: Data Extraction -> Dataset Preparation -> RAG Indexing -> QLoRA Fine-tuning -> GGUF Export -> Ollama Deployment -> Gradio Chat UI.
- [ ] Ensure the entire pipeline runs locally on an RTX 3050 (4GB VRAM) without external API dependencies.

## Out of Scope

Explicitly excluded to prevent scope creep.

| Feature | Reason |
| --- | --- |
| External API training / hosting (OpenAI, HuggingFace Space) | Privacy and cost constraints; the model must run 100% locally. |
| General physics topics not covered by the professor | The model's custom style is derived solely from the provided PDFs. |
| Public production deployment | The scope is restricted to local execution and interface serving. |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Professor PDF Location | User puts slides/PDFs in `teacher_docs/` | Simple root directory for input files. | Yes |
| Python Version compatibility | Use Python 3.12 via pyenv | Python 3.14 (system) is incompatible with PyTorch and Unsloth. | Yes |
| VRAM Constraints | 4GB RTX 3050 requires batch size = 1, gradient accumulation = 4, load_in_4bit = True | Unsloth needs careful memory budgeting to avoid CUDA OOM. | Yes |
| Base Model | Qwen 2.5 3B Instruct (`qwen2.5:3b`) | Good tradeoff between quality and size for local 4GB VRAM. | Yes |

**Open questions:** none — all resolved or logged above.

---

## User Stories

### P1: Environment & Base Setup ⭐ MVP

**User Story**: As a developer, I want my build dependencies, pyenv (Python 3.12), Ollama (with `qwen2.5:3b` and `nomic-embed-text`), and virtual environment with PyTorch + CUDA to be correctly installed, so that the project execution has a stable environment.

**Why P1**: Essential foundation; without this, no scripts can run.

**Acceptance Criteria**:
1. WHEN running the environment setup THEN system SHALL install build dependencies, pyenv, and Python 3.12.
2. WHEN verifying Ollama installation THEN system SHALL confirm it is running and download `qwen2.5:3b` and `nomic-embed-text` models.
3. WHEN creating the virtual environment THEN system SHALL install PyTorch with CUDA 12.1 and all dependencies from `requirements.txt`.

**Independent Test**: Run `scripts/setup_env.sh` and verify successful completion message. Test CUDA with `python -c "import torch; print(torch.cuda.is_available())"` showing `True`.

---

### P1: Data Pipeline & Extraction ⭐ MVP

**User Story**: As a developer, I want to extract raw text from PDFs in `teacher_docs/` and generate a training dataset of 200-400 instruction-response examples in ShareGPT/ChatML format, so that the model can learn the teacher's language style.

**Why P1**: The model's styling relies entirely on this dataset.

**Acceptance Criteria**:
1. WHEN running `scripts/extract_pdfs.py` THEN system SHALL extract text from PDFs in `teacher_docs/` and save to `data/processed/`.
2. WHEN running `training/prepare_dataset.py` in auto mode THEN system SHALL use Ollama's `qwen2.5:3b` to parse the extracted text into 200-400 training samples in ChatML format.
3. WHEN dataset is generated THEN system SHALL save it to `data/physics_dataset.jsonl` matching the ShareGPT schema.

**Independent Test**: Verify `data/physics_dataset.jsonl` contains valid JSON lines with standard `conversations` keys.

---

### P1: RAG Pipeline ⭐ MVP

**User Story**: As a developer, I want to build a ChromaDB vector index from the extracted texts and verify RAG query functionality locally, so that we can retrieve factual context for physics queries.

**Why P1**: Crucial to prevent hallucinations on factual questions.

**Acceptance Criteria**:
1. WHEN running `rag/build_index.py` THEN system SHALL chunk the extracted text, generate embeddings using `nomic-embed-text`, and save the index to `data/chroma_db/`.
2. WHEN querying `rag/query_engine.py` THEN system SHALL retrieve relevant context from ChromaDB and output answers referencing source text.

**Independent Test**: Run `python rag/query_engine.py --query "O que é entropia?"` and verify it displays retrieved sources and a structured answer.

---

### P1: QLoRA Fine-Tuning ⭐ MVP

**User Story**: As a developer, I want to fine-tune the base Qwen 2.5 3B model in 4-bit using Unsloth and export it to a GGUF Q4_K_M format, so that we have a memory-optimized custom model in the professor's style.

**Why P1**: Core objective: style transfer to mimic the teacher's tone.

**Acceptance Criteria**:
1. WHEN running `training/finetune.py` THEN system SHALL train the model using `data/physics_dataset.jsonl` within RTX 3050 4GB VRAM limits.
2. WHEN training completes THEN system SHALL export the fine-tuned model to GGUF format with `Q4_K_M` quant.

**Independent Test**: Run `python training/finetune.py` and verify `models/physics_model_gguf/` contains the generated `.gguf` file.

---

### P1: Deployment & UI ⭐ MVP

**User Story**: As a user, I want to deploy the fine-tuned model in Ollama and interact with it in a side-by-side Gradio chat interface (Base vs Fine-tuned with RAG), so that I can easily test the final application.

**Why P1**: Final interface for user testing and demonstration.

**Acceptance Criteria**:
1. WHEN executing `ollama create physics-teacher -f models/Modelfile` THEN Ollama SHALL register the new model.
2. WHEN launching `app/chat_ui.py` THEN a Gradio interface SHALL load in the browser.
3. WHEN chatting in the UI THEN system SHALL support streaming responses, toggling RAG, and displaying side-by-side output.

**Independent Test**: Launch `python -m app.chat_ui` and open the URL in the browser, send a test query, and check that both model outputs stream correctly.

---

## Edge Cases

- WHEN `teacher_docs/` is empty THEN the extraction script SHALL exit gracefully with a warning.
- WHEN training runs out of VRAM (CUDA OOM) THEN training config SHALL be adjusted (decrease sequence length, ensure expandable_segments is set).
- WHEN Ollama is not running THEN scripts invoking Ollama SHALL log clear connection instructions instead of crashing.
- WHEN RAG search yields no high-similarity documents THEN query engine SHALL output a disclaimer and reply using general knowledge.

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| ENV-01 | P1: Environment & Base Setup | Design | Completed |
| ENV-02 | P1: Environment & Base Setup | Design | Completed |
| ENV-03 | P1: Environment & Base Setup | Design | Completed |
| DATA-01 | P1: Data Pipeline & Extraction | Design | Completed |
| DATA-02 | P1: Data Pipeline & Extraction | Design | Completed |
| RAG-01 | P1: RAG Pipeline | Design | Completed |
| RAG-02 | P1: RAG Pipeline | Design | Completed |
| TRAIN-01 | P1: QLoRA Fine-Tuning | Design | Completed |
| TRAIN-02 | P1: QLoRA Fine-Tuning | Design | Completed |
| DEPLOY-01 | P1: Deployment & UI | Design | Completed |
| UI-01 | P1: Deployment & UI | Design | Pending |

**Coverage:** 11 total, 0 mapped to tasks, 11 unmapped ⚠️

---

## Success Criteria

- [ ] Complete setup script executes cleanly with no errors.
- [ ] Extracted datasets and ChromaDB indices are created locally.
- [ ] Fine-tuning runs to completion on 4GB VRAM and exports a valid GGUF.
- [ ] Side-by-side chat UI is functional, displays RAG context, and streams responses.

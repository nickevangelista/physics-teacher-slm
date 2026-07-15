# STATE

## Decisions

### AD-001
- **Decision**: Use Qwen 2.5 3B Instruct as the base model for local inference and fine-tuning.
- **Reason**: Excellent instruction performance/size tradeoff for local deployment.
- **Trade-off**: Lower general capabilities compared to larger 7B+ models, but fits in small VRAM budget.
- **Scope**: Local deployment (Ollama) and QLoRA fine-tuning.
- **Date**: 2026-07-06
- **Status**: active

### AD-002
- **Decision**: Keep the entire pipeline 100% local, running on the RTX 3050 (4GB VRAM).
- **Reason**: Zero cost, privacy/confidentiality, and offline capability.
- **Trade-off**: Restricts the model size (max 3B parameters) and training batch size (bs=1).
- **Scope**: Data generation, indexing, fine-tuning, and serving.
- **Date**: 2026-07-06
- **Status**: active

### AD-003
- **Decision**: Use Unsloth for QLoRA fine-tuning, LlamaIndex + ChromaDB for RAG, and Gradio for the Web UI.
- **Reason**: Unsloth provides 60%+ VRAM savings; LlamaIndex + ChromaDB is lightweight for local text retrieval.
- **Trade-off**: Unsloth locks training to specific supported models (like Qwen); Gradio UI is simple and server-rendered.
- **Scope**: Codebase components and library dependencies.
- **Date**: 2026-07-06
- **Status**: active

## Handoff

- **Feature**: physics-teacher-slm
- **Phase / Task**: Phase 1 (Data Pipeline) completed
- **Completed**: Phase 1 (Data Pipeline) - verified PDFs (T7), extracted cleaned text to `data/processed/` (T8), and generated a 200-sample ChatML training dataset using local Ollama (T9). Unit tests created and passed successfully for both scripts.
- **In-progress** (file:line): none
- **Next step**: Start Phase 2 (RAG Pipeline) - Build ChromaDB index using LlamaIndex and verify RAG query functionality.
- **Blockers**: none
- **Uncommitted files**: none
- **Branch**: master

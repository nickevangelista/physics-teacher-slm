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
- **Phase / Task**: Phase 4 (Deploy) completed
- **Completed**: Phase 4 (Deploy) - Registered the fine-tuned model in Ollama. Fixed a GGUF template tag issue in `models/Modelfile` to prevent early termination. Re-exported the fine-tuned model to `q8_0` GGUF format as `models/physics_model_gguf/unsloth.Q8_0.gguf` to resolve Unsloth Q4_K_M quantization weight corruption. Successfully verified the model `physics-teacher` via Ollama API, getting coherent Portuguese responses in the teacher style.
- **In-progress** (file:line): none
- **Next step**: Start Phase 5 (Interface Web) - Launch and test the Gradio side-by-side chat UI `app/chat_ui.py`.
- **Blockers**: none
- **Uncommitted files**: none
- **Branch**: master

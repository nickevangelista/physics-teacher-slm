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
- **Phase / Task**: Phase 3 (Fine-Tuning QLoRA) completed
- **Completed**: Phase 3 (Fine-Tuning QLoRA) - Resolved fp16/bf16 precision configuration error. Executed QLoRA fine-tuning with Unsloth on the physics dataset (202 examples) for 1 epoch. Saved LoRA adapters to `models/physics_model_lora/` (commit `9366d9dad73f6b4d3725b84c8d506be368a4fb52`). Exported the fine-tuned model to GGUF Q4_K_M format under `models/physics_model_gguf/` (commit `83aa08a4ec99c54625b8b939f50e82c5f1fa70b9`). All 18 integration/unit tests continue to pass.
- **In-progress** (file:line): none
- **Next step**: Start Phase 4 (Deploy) - Register the exported GGUF model in local Ollama as `physics-teacher` using `models/Modelfile`.
- **Blockers**: none
- **Uncommitted files**: none
- **Branch**: master

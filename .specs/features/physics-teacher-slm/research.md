# Research: Physics Teacher SLM

**Data:** 2026-07-06
**Autor:** Nícolas Evangelista
**Tipo:** Nova Feature (Projeto completo — RAG + Fine-tuning + Deploy local)

---

## Contexto

O projeto consiste em construir um **Small Language Model (SLM)** local que imita o estilo de ensino de um professor de Física. O modelo deve ser capaz de explicar conceitos usando a notação e linguagem do professor, e gerar questões de prova no mesmo formato, nível de dificuldade e estilo dos materiais originais.

A arquitetura combina duas abordagens complementares: **RAG (Retrieval-Augmented Generation)** para recuperar conteúdo factual dos documentos do professor, e **QLoRA Fine-tuning** para adaptar o estilo de linguagem do modelo. Todo o pipeline roda 100% localmente em uma Dell G15 5511 com RTX 3050 (4GB VRAM), sem enviar dados a APIs externas.

O modelo base escolhido é o **Qwen 2.5 3B Instruct** (geral, NÃO o Coder), servido via **Ollama**. Atualmente, o repositório do modelo local contém o `Qwen2.5-Coder-3B-Instruct-GGUF` em `~/odysseus/data/huggingface/hub/`, que precisa ser substituído pela variante geral.

O projeto já possui todos os scripts de código implementados e validados. Os próximos passos são: configurar o ambiente (pyenv + Ollama), colocar os PDFs do professor no diretório `teacher_docs/`, e executar o pipeline completo.

---

## Objetivos

- Criar um modelo local que explica Física no estilo específico do professor
- Gerar questões de prova que sigam o formato, notação e nível de dificuldade dos materiais originais
- Rodar tudo localmente (zero custo, privacidade total, sem API keys)
- Construir pipeline reprodutível: Dados → RAG → Fine-tuning → Export GGUF → Ollama → UI
- Servir o modelo via interface web acessível (Gradio)
- Documentar todo o processo para portfolio técnico (blog + LinkedIn)

---

## Critérios de Aceite

- [x] Estrutura de diretórios do projeto criada
- [x] Todos os scripts Python implementados (RAG, fine-tuning, data pipeline, UI)
- [x] requirements.txt com todas as dependências
- [x] README.md profissional com diagrama de arquitetura
- [x] Modelfile para Ollama com template ChatML
- [x] Script de setup do ambiente (setup_env.sh)
- [ ] pyenv instalado com Python 3.12 funcional
- [ ] Ollama instalado e servindo modelos
- [ ] Modelos `qwen2.5:3b` e `nomic-embed-text` baixados via Ollama
- [ ] venv criado com todas as dependências instaladas (PyTorch + CUDA)
- [ ] PDFs do professor copiados para `teacher_docs/`
- [ ] Texto extraído dos PDFs com `scripts/extract_pdfs.py`
- [ ] Dataset JSONL gerado com 200-400 exemplos (`training/prepare_dataset.py`)
- [ ] Índice ChromaDB construído com documentos do professor (`rag/build_index.py`)
- [ ] RAG pipeline funcionando com modelo base (testar `rag/query_engine.py`)
- [ ] Fine-tuning QLoRA executado com sucesso (`training/finetune.py`)
- [ ] Modelo exportado para GGUF Q4_K_M
- [ ] Modelo registrado no Ollama como `physics-teacher`
- [ ] Interface Gradio funcionando com RAG + modelo fine-tunado
- [ ] Comparação lado a lado: modelo base vs fine-tunado na mesma pergunta

---

## Tasks / Fixes

### Fase 0 — Environment Setup (Bloqueado por sudo/credenciais)

1. **Instalar build dependencies** — `sudo apt-get install make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev` [Descoberto durante pesquisa: apt-get falhou por sudo timeout na sessão anterior]
2. **Reinstalar Python 3.12 via pyenv** — `~/.pyenv/bin/pyenv install 3.12 -s` [Descoberto durante pesquisa: build anterior falhou por falta de libssl-dev, libffi-dev, etc.]
3. **Instalar Ollama** — `curl -fsSL https://ollama.com/install.sh | sh` [Descoberto durante pesquisa: install anterior falhou por sudo timeout]
4. **Criar venv e instalar dependências** — `python3.12 -m venv .venv && source .venv/bin/activate && pip install torch --index-url https://download.pytorch.org/whl/cu121 && pip install -r requirements.txt`
5. **Pull modelos Ollama** — `ollama pull qwen2.5:3b && ollama pull nomic-embed-text`

### Fase 1 — Data Pipeline

6. **Copiar PDFs do professor** para `teacher_docs/` (ação do usuário)
7. **Extrair texto dos PDFs** — `python scripts/extract_pdfs.py`
8. **Gerar dataset de instrução-resposta** — `python training/prepare_dataset.py --modo auto --modelo qwen2.5:3b`

### Fase 2 — RAG Pipeline

9. **Construir índice ChromaDB** — `python rag/build_index.py`
10. **Testar consultas RAG** — `python rag/query_engine.py` (modo interativo)

### Fase 3 — Fine-Tuning QLoRA

11. **Executar treinamento** — `python training/finetune.py --epochs 3 --lr 2e-4`
12. **Avaliar resultados** — comparar respostas do modelo base vs fine-tunado

### Fase 4 — Deploy

13. **Registrar no Ollama** — `ollama create physics-teacher -f models/Modelfile`
14. **Testar modelo custom** — `ollama run physics-teacher "Explique as Leis de Newton"`

### Fase 5 — Interface Web

15. **Iniciar UI** — `python -m app.chat_ui`
16. **Testar end-to-end** com perguntas de Física variadas

---

## Arquivos Relevantes

### Código do Projeto

| Arquivo | Status | Linhas-Chave | Relevância |
|---------|--------|--------------|------------|
| [requirements.txt](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/requirements.txt) | EXISTING | L1-L35: todas as deps | Dependências Python — fine-tuning, RAG, UI |
| [scripts/setup_env.sh](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/scripts/setup_env.sh) | EXISTING | — | Setup completo do ambiente (pyenv, Ollama, venv) |
| [scripts/configure_pyenv.sh](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/scripts/configure_pyenv.sh) | EXISTING | L1-L20: config bashrc | Configura pyenv no .bashrc e instala Python 3.12 |
| [README.md](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/README.md) | EXISTING | — | Documentação completa em PT-BR com diagrama mermaid |

### Data Pipeline

| Arquivo | Status | Linhas-Chave | Relevância |
|---------|--------|--------------|------------|
| [scripts/extract_pdfs.py](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/scripts/extract_pdfs.py) | EXISTING | L1-L11863: extração pymupdf | Extrai texto dos PDFs preservando estrutura |
| [training/prepare_dataset.py](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/training/prepare_dataset.py) | EXISTING | L1-L30: modos interativo/auto/revisao | Gera pares instrução-resposta via Ollama ou manual |

### RAG Pipeline

| Arquivo | Status | Linhas-Chave | Relevância |
|---------|--------|--------------|------------|
| [rag/build_index.py](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/rag/build_index.py) | EXISTING | L20-L29: imports LlamaIndex+Chroma | Constrói índice vetorial ChromaDB |
| [rag/query_engine.py](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/rag/query_engine.py) | EXISTING | — | CLI + API para consultas RAG com fontes |
| [rag/__init__.py](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/rag/__init__.py) | EXISTING | — | Package init |

### Training

| Arquivo | Status | Linhas-Chave | Relevância |
|---------|--------|--------------|------------|
| [training/finetune.py](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/training/finetune.py) | EXISTING | L53-L84: config RTX 3050 | Script QLoRA completo com Unsloth |
| [training/finetune.py](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/training/finetune.py) | EXISTING | L57-L84: DEFAULT_CONFIG | Hiperparâmetros otimizados para 4GB VRAM |
| [training/finetune.py](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/training/finetune.py) | EXISTING | L509-L537: export GGUF | Exportação Q4_K_M via Unsloth |

### Deploy & UI

| Arquivo | Status | Linhas-Chave | Relevância |
|---------|--------|--------------|------------|
| [models/Modelfile](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/models/Modelfile) | EXISTING | L1-L2030: Modelfile Ollama | Template ChatML + system prompt PT-BR |
| [app/chat_ui.py](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/app/chat_ui.py) | EXISTING | L1-L591: Gradio Blocks | UI com chat, RAG, settings, streaming |

### Modelo Local Atual (a ser substituído)

| Arquivo | Status | Linhas-Chave | Relevância |
|---------|--------|--------------|------------|
| `~/odysseus/data/huggingface/hub/models--Qwen--Qwen2.5-Coder-3B-Instruct-GGUF/` | EXISTING | ~25GB em blobs | Modelo CODER — será substituído pelo geral via Ollama |

---

## Padrões e Convenções Aplicáveis

### Stack Técnica
- **Modelo base**: `Qwen/Qwen2.5-3B-Instruct` (HuggingFace) / `qwen2.5:3b` (Ollama)
- **Fine-tuning**: Unsloth + QLoRA (4-bit), `unsloth/Qwen2.5-3B-Instruct-bnb-4bit`
- **RAG**: LlamaIndex + ChromaDB + nomic-embed-text
- **Inference**: Ollama (API em `http://localhost:11434`)
- **UI**: Gradio (dark theme, streaming, abas Chat/Config)
- **Python**: 3.12 via pyenv (3.14 do sistema NÃO é compatível com PyTorch/Unsloth)

### Configurações Críticas para 4GB VRAM (RTX 3050)
- `load_in_4bit=True` — obrigatório
- `per_device_train_batch_size=1` — obrigatório
- `gradient_accumulation_steps=4` — simula batch=4
- `fp16=True, bf16=False` — RTX 3050
- `use_gradient_checkpointing="unsloth"` — economiza ~60% VRAM
- `optim="adamw_8bit"` — optimizer 8-bit economiza memória
- `max_seq_length=1024` — manter baixo para VRAM
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
- Quantização GGUF: `Q4_K_M` (~1.8 GB, melhor custo-benefício)

### Formato de Dataset
- ShareGPT/ChatML JSONL em `data/physics_dataset.jsonl`
- Template: `{"conversations": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}`
- Target: 200-400 exemplos
- Mix: explicações (~40%), questões (~30%), resolução (~20%), definições (~10%)

### Convenções de Código
- Docstrings em português, comentários em inglês
- argparse para todos os scripts CLI
- Logging com emojis para feedback visual
- Error handling com mensagens actionables
- Paths relativos via `PROJECT_ROOT = Path(__file__).resolve().parent.parent`

---

## Riscos e Observações

### ⚠ Ambiente Não Configurado
- **Build dependencies** não foram instaladas (apt-get falhou por sudo timeout na sessão de 19/06)
- **Python 3.12** não compilou corretamente (faltavam libssl-dev, libffi-dev, etc.)
- **Ollama** não foi instalado (sudo timeout durante download)
- **Solução**: Executar setup interativamente no terminal com sudo ativo, ou rodar `scripts/setup_env.sh`

### ⚠ Python 3.14 Incompatível
- O Python do sistema é 3.14.4 — não suportado por PyTorch, Unsloth, bitsandbytes
- **Solução**: Usar Python 3.12 via pyenv (já configurado, só precisa rebuildar)

### ⚠ PDFs do Professor Pendentes
- O usuário confirmou ter os slides mas não informou o caminho/localização
- **Bloqueio**: Sem os PDFs, não é possível executar Fase 1 (extração), Fase 2 (RAG) e Fase 3 (fine-tuning)

### 📝 Modelo Coder vs Geral
- O modelo local atual é o `Qwen2.5-Coder-3B-Instruct-GGUF` (~25GB)
- O projeto usa o modelo **geral** `Qwen2.5-3B-Instruct` que será baixado via Ollama (`ollama pull qwen2.5:3b`)
- O modelo Coder pode ser mantido ou removido para liberar espaço

### 📝 VRAM Budget
| Operação | VRAM Estimada | Viável? |
|---|---|---|
| Inferência Q4_K_M | ~2.0 GB | ✅ Sim |
| Inferência Q8_0 | ~3.0 GB | ✅ Sim |
| QLoRA fine-tune (4-bit, bs=1) | ~3.5 GB | ⚠ Apertado mas ok |
| Full fine-tune FP16 | ~12 GB | ❌ Não |

---

## Referências

- PDF do projeto: [physics_slm_project.pdf](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/physics_slm_project.pdf)
- Skill de Planning: [tlc-spec-driven](file:///wsl.localhost/Ubuntu/home/nicol/projetos/physics-teacher-slm/.agents/skills/tlc-spec-driven/SKILL.md)
- HuggingFace Qwen 2.5 3B: `https://huggingface.co/Qwen/Qwen2.5-3B-Instruct`
- Unsloth: `https://github.com/unslothai/unsloth`
- LlamaIndex + Ollama: `https://docs.llamaindex.ai/en/stable/examples/llm/ollama/`
- ChromaDB: `https://docs.trychroma.com/`
- Ollama: `https://ollama.com/`

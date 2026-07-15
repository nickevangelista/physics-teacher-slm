#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Physics Teacher SLM — Script de Setup do Ambiente
# ═══════════════════════════════════════════════════════════════════════════
# Uso: bash scripts/setup_env.sh
# Este script é idempotente — pode ser executado múltiplas vezes com segurança.
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Cores para output ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'  # No Color
BOLD='\033[1m'

# ── Funções auxiliares ───────────────────────────────────────────────────
info()    { echo -e "${BLUE}[INFO]${NC}    $*"; }
success() { echo -e "${GREEN}[✔]${NC}      $*"; }
warn()    { echo -e "${YELLOW}[AVISO]${NC}  $*"; }
error()   { echo -e "${RED}[ERRO]${NC}   $*"; }
step()    { echo -e "\n${MAGENTA}${BOLD}━━━ $* ━━━${NC}"; }

# ── Configurações ────────────────────────────────────────────────────────
PYTHON_VERSION="3.12"
VENV_DIR=".venv"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     🧲 Physics Teacher SLM — Setup do Ambiente         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
info "Diretório do projeto: $PROJECT_ROOT"

# ═════════════════════════════════════════════════════════════════════════
# 1. Dependências de Compilação & Pyenv
# ═════════════════════════════════════════════════════════════════════════
step "1/6 — Verificando dependências de compilação e pyenv"

info "Instalando dependências de compilação do Python (pode pedir senha do sudo)..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev \
    libncursesw5-dev xz-utils tk-dev \
    libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev \
    curl git wget zstd

# Adiciona pyenv ao PATH caso o diretório já exista mas não esteja no PATH da sessão atual
export PYENV_ROOT="$HOME/.pyenv"
if [[ -d "$PYENV_ROOT" ]]; then
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)" 2>/dev/null || true
fi

if command -v pyenv &>/dev/null; then
    success "pyenv já instalado ($(pyenv --version))"
else
    warn "pyenv não encontrado. Instalando..."
    curl -fsSL https://pyenv.run | bash

    # Configura o shell
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"

    # Adiciona ao .bashrc se ainda não estiver lá
    if ! grep -q 'pyenv init' "$HOME/.bashrc" 2>/dev/null; then
        {
            echo ''
            echo '# Pyenv (adicionado pelo setup do Physics Teacher SLM)'
            echo 'export PYENV_ROOT="$HOME/.pyenv"'
            echo 'export PATH="$PYENV_ROOT/bin:$PATH"'
            echo 'eval "$(pyenv init -)"'
        } >> "$HOME/.bashrc"
        info "pyenv adicionado ao .bashrc"
    fi

    success "pyenv instalado com sucesso"
fi

# Garante que pyenv está no PATH para o restante do script
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)" 2>/dev/null || true

# ═════════════════════════════════════════════════════════════════════════
# 2. Python 3.12
# ═════════════════════════════════════════════════════════════════════════
step "2/6 — Verificando Python $PYTHON_VERSION"

# Encontra a versão mais recente do Python 3.12.x instalada
INSTALLED_312=$(pyenv versions --bare 2>/dev/null | grep "^${PYTHON_VERSION}" | tail -1 || true)

if [[ -n "$INSTALLED_312" ]]; then
    success "Python $INSTALLED_312 já instalado via pyenv"
else
    info "Instalando Python $PYTHON_VERSION (última versão disponível)..."
    # Pega a versão mais recente do 3.12.x disponível
    LATEST_312=$(pyenv install --list 2>/dev/null | tr -d ' ' | grep "^${PYTHON_VERSION}\." | grep -v '[a-z]' | tail -1)

    if [[ -z "$LATEST_312" ]]; then
        error "Não foi possível encontrar Python $PYTHON_VERSION para instalar"
        exit 1
    fi

    info "Instalando Python $LATEST_312..."
    pyenv install "$LATEST_312"
    INSTALLED_312="$LATEST_312"
    success "Python $INSTALLED_312 instalado"
fi

# Define como versão local do projeto
pyenv local "$INSTALLED_312"
PYTHON_BIN="$(pyenv prefix "$INSTALLED_312")/bin/python"
info "Usando: $PYTHON_BIN"

# ═════════════════════════════════════════════════════════════════════════
# 3. Virtual Environment
# ═════════════════════════════════════════════════════════════════════════
step "3/6 — Configurando virtual environment"

if [[ -d "$VENV_DIR" ]] && [[ -f "$VENV_DIR/bin/python" ]]; then
    # Verifica se a venv usa a versão correta
    VENV_PY_VERSION=$("$VENV_DIR/bin/python" --version 2>&1 | awk '{print $2}')
    if [[ "$VENV_PY_VERSION" == "$INSTALLED_312"* ]]; then
        success "venv já existe com Python $VENV_PY_VERSION"
    else
        warn "venv existe com Python $VENV_PY_VERSION, recriando..."
        rm -rf "$VENV_DIR"
        "$PYTHON_BIN" -m venv "$VENV_DIR"
        success "venv recriada com Python $INSTALLED_312"
    fi
else
    info "Criando venv em $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    success "venv criada com sucesso"
fi

# Ativa a venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
info "venv ativada: $(which python)"

# Configura TMPDIR local no projeto para evitar estouro de espaço em /tmp (que usa tmpfs no WSL)
mkdir -p .tmp
export TMPDIR="$PROJECT_ROOT/.tmp"

# Atualiza pip
python -m pip install --upgrade pip --quiet
success "pip atualizado: $(pip --version | awk '{print $2}')"

# ═════════════════════════════════════════════════════════════════════════
# 4. PyTorch com CUDA
# ═════════════════════════════════════════════════════════════════════════
step "4/6 — Instalando PyTorch com CUDA 12.1"

if python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    TORCH_VERSION=$(python -c "import torch; print(torch.__version__)")
    CUDA_VERSION=$(python -c "import torch; print(torch.version.cuda)")
    success "PyTorch $TORCH_VERSION com CUDA $CUDA_VERSION já instalado"
else
    info "Instalando PyTorch com suporte a CUDA 12.1..."
    pip install torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/cu121 \
        --quiet

    # Verifica instalação
    if python -c "import torch; print(f'PyTorch {torch.__version__}')" 2>/dev/null; then
        success "PyTorch instalado com sucesso"
        if python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
            GPU_NAME=$(python -c "import torch; print(torch.cuda.get_device_name(0))" 2>/dev/null || echo "N/A")
            success "CUDA disponível — GPU: $GPU_NAME"
        else
            warn "PyTorch instalado, mas CUDA não detectado (normal se rodando sem GPU)"
        fi
    else
        error "Falha ao instalar PyTorch"
        exit 1
    fi
fi

# ═════════════════════════════════════════════════════════════════════════
# 5. Dependências Python
# ═════════════════════════════════════════════════════════════════════════
step "5/6 — Instalando dependências Python"

if [[ -f "requirements.txt" ]]; then
    info "Instalando pacotes do requirements.txt..."
    pip install -r requirements.txt --quiet
    success "Todas as dependências Python instaladas"
else
    error "requirements.txt não encontrado em $PROJECT_ROOT"
    exit 1
fi

# ═════════════════════════════════════════════════════════════════════════
# 6. Ollama + Modelos
# ═════════════════════════════════════════════════════════════════════════
step "6/6 — Configurando Ollama"

if command -v ollama &>/dev/null; then
    success "Ollama já instalado ($(ollama --version 2>/dev/null || echo 'versão desconhecida'))"
else
    info "Instalando Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
    success "Ollama instalado"
fi

# Verifica se o Ollama está rodando
if curl -s http://localhost:11434/api/tags &>/dev/null; then
    info "Ollama está rodando"
else
    warn "Ollama não está rodando. Tentando iniciar..."
    # No WSL, ollama serve roda em background
    nohup ollama serve &>/dev/null &
    sleep 3

    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        success "Ollama iniciado com sucesso"
    else
        warn "Não foi possível iniciar o Ollama automaticamente."
        warn "Inicie manualmente com: ollama serve"
    fi
fi

# Baixa modelos necessários
info "Verificando modelos Ollama..."

pull_model() {
    local model="$1"
    if ollama list 2>/dev/null | grep -q "$model"; then
        success "Modelo '$model' já disponível"
    else
        info "Baixando modelo '$model'... (pode levar alguns minutos)"
        if ollama pull "$model"; then
            success "Modelo '$model' baixado com sucesso"
        else
            warn "Falha ao baixar '$model' — verifique se o Ollama está rodando"
        fi
    fi
}

pull_model "qwen2.5:3b"
pull_model "nomic-embed-text"

# ═════════════════════════════════════════════════════════════════════════
# Cria diretórios do projeto (se não existirem)
# ═════════════════════════════════════════════════════════════════════════
info "Criando diretórios do projeto..."
mkdir -p data/raw data/processed data/chroma_db
mkdir -p models/physics_model_gguf
mkdir -p logs
mkdir -p notebooks
success "Estrutura de diretórios verificada"

# ═════════════════════════════════════════════════════════════════════════
# Resumo final
# ═════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              ✅ Setup concluído com sucesso!            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "${GREEN}Próximos passos:${NC}"
echo -e "  1. Ative a venv:        ${CYAN}source .venv/bin/activate${NC}"
echo -e "  2. Inicie o Ollama:     ${CYAN}ollama serve${NC}"
echo -e "  3. Inicie o chat:       ${CYAN}python -m app.chat_ui${NC}"
echo ""
echo -e "${YELLOW}Para fine-tuning:${NC}"
echo -e "  1. Coloque PDFs em:     ${CYAN}data/raw/${NC}"
echo -e "  2. Processe o dataset:  ${CYAN}python scripts/prepare_dataset.py${NC}"
echo -e "  3. Fine-tune:           ${CYAN}python scripts/train_qlora.py${NC}"
echo ""

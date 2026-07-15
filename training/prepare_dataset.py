#!/usr/bin/env python3
"""
prepare_dataset.py — Criação de pares instrução-resposta para fine-tuning.

Lê textos extraídos de data/raw/, divide em chunks, e gera pares de
instrução-resposta no formato ShareGPT/ChatML para treinamento.

Modos de operação:
  1. Interativo: mostra chunks e permite criar/editar pares manualmente
  2. Auto (Ollama): usa o modelo base via Ollama API para gerar pares automaticamente
  3. Revisão: revisa e edita pares existentes no dataset

Formato de saída (ShareGPT/ChatML JSONL):
  {"conversations": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]}

Uso:
    python training/prepare_dataset.py --modo interativo
    python training/prepare_dataset.py --modo auto --modelo qwen2.5:3b
    python training/prepare_dataset.py --modo revisao
"""

import argparse
import json
import logging
import os
import re
import sys
import textwrap
import time
from pathlib import Path
from typing import Optional

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Diretórios e arquivos
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATASET_FILE = PROJECT_ROOT / "data" / "physics_dataset.jsonl"
PROGRESS_FILE = PROJECT_ROOT / "data" / ".prepare_progress.json"

# Configurações do Ollama
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"
DEFAULT_MODEL = "qwen2.5:3b"

# System prompt padrão para o dataset
SYSTEM_PROMPT = (
    "Você é um professor de Física experiente e didático. "
    "Responda de forma clara, precisa e acessível, usando exemplos "
    "práticos quando possível. Inclua equações relevantes e explique "
    "cada passo do raciocínio."
)

# Distribuição alvo de tipos de exemplos
TIPO_DISTRIBUICAO = {
    "conceito": 0.40,      # Explicações de conceitos (~40%)
    "questao": 0.30,       # Questões de prova/teste (~30%)
    "problema": 0.20,      # Resolução de problemas (~20%)
    "definicao": 0.10,     # Definições e glossário (~10%)
}

# Prompts para geração automática por tipo
PROMPTS_GERACAO = {
    "conceito": (
        "Com base no texto abaixo sobre Física, crie um par de pergunta e resposta "
        "onde o aluno pede uma EXPLICAÇÃO CONCEITUAL sobre o tema principal. "
        "A resposta deve ser didática, clara e completa.\n\n"
        "TEXTO:\n{texto}\n\n"
        "Responda EXATAMENTE neste formato JSON (sem markdown, sem ```json):\n"
        '{{"pergunta": "...", "resposta": "..."}}'
    ),
    "questao": (
        "Com base no texto abaixo sobre Física, crie uma QUESTÃO DE PROVA "
        "(múltipla escolha ou dissertativa) com a resposta correta explicada.\n\n"
        "TEXTO:\n{texto}\n\n"
        "Responda EXATAMENTE neste formato JSON (sem markdown, sem ```json):\n"
        '{{"pergunta": "...", "resposta": "..."}}'
    ),
    "problema": (
        "Com base no texto abaixo sobre Física, crie um PROBLEMA NUMÉRICO "
        "com resolução passo a passo. Inclua dados, equações e cálculos.\n\n"
        "TEXTO:\n{texto}\n\n"
        "Responda EXATAMENTE neste formato JSON (sem markdown, sem ```json):\n"
        '{{"pergunta": "...", "resposta": "..."}}'
    ),
    "definicao": (
        "Com base no texto abaixo sobre Física, crie uma pergunta pedindo "
        "a DEFINIÇÃO de um conceito ou grandeza física mencionada. "
        "A resposta deve incluir definição, unidade SI e exemplos.\n\n"
        "TEXTO:\n{texto}\n\n"
        "Responda EXATAMENTE neste formato JSON (sem markdown, sem ```json):\n"
        '{{"pergunta": "...", "resposta": "..."}}'
    ),
}


# ─── Utilitários ────────────────────────────────────────────────────────────


def dividir_em_chunks(texto: str, tamanho: int = 800, sobreposicao: int = 100) -> list[str]:
    """
    Divide texto em chunks de tamanho aproximado, tentando quebrar em
    parágrafos ou frases para manter coerência.

    Args:
        texto: Texto completo para dividir
        tamanho: Tamanho alvo de cada chunk (em caracteres)
        sobreposicao: Sobreposição entre chunks consecutivos

    Returns:
        Lista de chunks de texto
    """
    if not texto or len(texto) <= tamanho:
        return [texto] if texto else []

    # Remove linhas de cabeçalho do arquivo (começam com #)
    linhas = texto.split("\n")
    linhas_conteudo = []
    for linha in linhas:
        if linha.startswith("# Fonte:") or linha.startswith("# Páginas:"):
            continue
        if linha.startswith("# Caracteres:") or linha.startswith("# Título:"):
            continue
        if linha.startswith("# Autor:") or re.match(r"^#={5,}", linha):
            continue
        linhas_conteudo.append(linha)

    texto_limpo = "\n".join(linhas_conteudo).strip()

    # Divide em parágrafos
    paragrafos = re.split(r"\n\s*\n", texto_limpo)
    paragrafos = [p.strip() for p in paragrafos if p.strip()]

    chunks = []
    chunk_atual = ""

    for paragrafo in paragrafos:
        # Se adicionar o parágrafo excede o tamanho, fecha o chunk atual
        if chunk_atual and len(chunk_atual) + len(paragrafo) + 2 > tamanho:
            chunks.append(chunk_atual.strip())
            # Sobreposição: mantém as últimas palavras do chunk anterior
            palavras = chunk_atual.split()
            num_palavras_overlap = max(1, sobreposicao // 6)  # ~6 chars por palavra
            chunk_atual = " ".join(palavras[-num_palavras_overlap:]) + "\n\n"

        chunk_atual += paragrafo + "\n\n"

    # Adiciona o último chunk
    if chunk_atual.strip():
        chunks.append(chunk_atual.strip())

    # Filtra chunks muito pequenos (menos de 50 chars — provavelmente inúteis)
    chunks = [c for c in chunks if len(c) >= 50]

    return chunks


def carregar_progresso() -> dict:
    """Carrega estado de progresso para permitir retomada."""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("Arquivo de progresso corrompido, iniciando do zero.")
    return {
        "chunks_processados": [],
        "contagem_tipos": {t: 0 for t in TIPO_DISTRIBUICAO},
        "total_exemplos": 0,
    }


def salvar_progresso(progresso: dict):
    """Salva estado de progresso."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progresso, f, ensure_ascii=False, indent=2)


def carregar_dataset() -> list[dict]:
    """Carrega exemplos existentes do dataset JSONL."""
    exemplos = []
    if DATASET_FILE.exists():
        with open(DATASET_FILE, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha:
                    try:
                        exemplos.append(json.loads(linha))
                    except json.JSONDecodeError:
                        logger.warning(f"Linha inválida no dataset: {linha[:80]}...")
    return exemplos


def salvar_exemplo(exemplo: dict):
    """Adiciona um exemplo ao final do arquivo JSONL."""
    DATASET_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATASET_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(exemplo, ensure_ascii=False) + "\n")


def criar_exemplo_sharegpt(
    pergunta: str,
    resposta: str,
    system_prompt: str = SYSTEM_PROMPT,
) -> dict:
    """
    Cria um exemplo no formato ShareGPT/ChatML.

    Returns:
        Dicionário com a estrutura ShareGPT:
        {"conversations": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]}
    """
    return {
        "conversations": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pergunta.strip()},
            {"role": "assistant", "content": resposta.strip()},
        ]
    }


def tipo_necessario(progresso: dict, total_alvo: int = 300) -> str:
    """
    Determina qual tipo de exemplo deve ser gerado a seguir, baseado
    na distribuição alvo e no progresso atual.

    Returns:
        Tipo de exemplo ('conceito', 'questao', 'problema', 'definicao')
    """
    contagem = progresso["contagem_tipos"]
    total = progresso["total_exemplos"]

    if total == 0:
        return "conceito"

    # Calcula quanto cada tipo está abaixo da proporção alvo
    deficits = {}
    for tipo, proporcao_alvo in TIPO_DISTRIBUICAO.items():
        proporcao_atual = contagem.get(tipo, 0) / max(total, 1)
        deficits[tipo] = proporcao_alvo - proporcao_atual

    # Retorna o tipo com maior déficit
    return max(deficits, key=deficits.get)


# ─── Ollama API ─────────────────────────────────────────────────────────────


def chamar_ollama(
    prompt: str,
    modelo: str = DEFAULT_MODEL,
    temperatura: float = 0.7,
    timeout: int = 120,
) -> Optional[str]:
    """
    Chama a API do Ollama para gerar texto.

    Usa urllib para evitar dependência de requests.

    Args:
        prompt: Prompt para o modelo
        modelo: Nome do modelo no Ollama
        temperatura: Temperatura de geração
        timeout: Timeout em segundos

    Returns:
        Texto gerado ou None em caso de erro
    """
    import urllib.request
    import urllib.error

    payload = {
        "model": modelo,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
        "options": {
            "temperature": temperatura,
            "num_predict": 1024,
        },
    }

    dados = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_CHAT_ENDPOINT,
        data=dados,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            corpo = json.loads(resp.read().decode("utf-8"))
            return corpo.get("message", {}).get("content", "")
    except urllib.error.URLError as e:
        logger.error(f"Erro de conexão com Ollama: {e}")
        logger.error("Verifique se o Ollama está rodando: ollama serve")
        return None
    except Exception as e:
        logger.error(f"Erro ao chamar Ollama: {e}")
        return None


def verificar_ollama(modelo: str = DEFAULT_MODEL) -> bool:
    """Verifica se o Ollama está disponível e o modelo está carregado."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/tags",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
            modelos = [m.get("name", "") for m in dados.get("models", [])]

            # Verifica se o modelo (ou prefixo) está disponível
            modelo_encontrado = any(
                modelo in m or m.startswith(modelo.split(":")[0])
                for m in modelos
            )
            if not modelo_encontrado:
                logger.warning(
                    f"Modelo '{modelo}' não encontrado no Ollama. "
                    f"Modelos disponíveis: {modelos}"
                )
                logger.info(f"Execute: ollama pull {modelo}")
                return False

            return True

    except urllib.error.URLError:
        logger.error(
            "Ollama não está respondendo. Inicie com: ollama serve"
        )
        return False


def extrair_json_da_resposta(resposta: str) -> Optional[dict]:
    """
    Tenta extrair um objeto JSON de uma resposta do modelo,
    mesmo que contenha texto extra ou markdown.
    """
    if not resposta:
        return None

    # Tenta parse direto
    try:
        return json.loads(resposta.strip())
    except json.JSONDecodeError:
        pass

    # Tenta encontrar JSON dentro de blocos de código
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", resposta, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Tenta encontrar um objeto JSON na resposta
    match = re.search(r"\{[^{}]*\"pergunta\"[^{}]*\"resposta\"[^{}]*\}", resposta, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ─── Modo Interativo ────────────────────────────────────────────────────────


def modo_interativo():
    """
    Modo interativo: mostra chunks de texto e permite ao usuário
    criar pares de instrução-resposta manualmente.
    """
    logger.info("🖊️  Modo INTERATIVO — Criação manual de pares")
    print("=" * 60)

    # Carrega textos extraídos
    arquivos_txt = sorted(RAW_DIR.glob("*.txt"))
    if not arquivos_txt:
        logger.error(f"Nenhum arquivo .txt encontrado em {RAW_DIR}")
        logger.info("Execute primeiro: python scripts/extract_pdfs.py")
        sys.exit(1)

    # Carrega progresso
    progresso = carregar_progresso()
    dataset_existente = carregar_dataset()
    logger.info(f"📊 Dataset atual: {len(dataset_existente)} exemplos")
    logger.info(f"📊 Progresso: {progresso['total_exemplos']} criados")

    # Mostra distribuição atual
    print("\nDistribuição atual vs alvo:")
    for tipo, alvo in TIPO_DISTRIBUICAO.items():
        atual = progresso["contagem_tipos"].get(tipo, 0)
        total = max(progresso["total_exemplos"], 1)
        print(f"  {tipo:12s}: {atual:3d} ({atual/total*100:5.1f}%) — alvo: {alvo*100:.0f}%")

    print("\n" + "=" * 60)
    print("Comandos: [s]alvar, [p]ular, [q]uit, [t]ipo <tipo>")
    print("=" * 60)

    tipo_atual = tipo_necessario(progresso)

    # Processa cada arquivo
    for arquivo in arquivos_txt:
        logger.info(f"\n📄 Arquivo: {arquivo.name}")
        texto = arquivo.read_text(encoding="utf-8")
        chunks = dividir_em_chunks(texto)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{arquivo.stem}::{i}"

            # Pula chunks já processados
            if chunk_id in progresso["chunks_processados"]:
                continue

            print(f"\n{'─' * 60}")
            print(f"📝 Chunk {i + 1}/{len(chunks)} de '{arquivo.name}'")
            print(f"   Tipo sugerido: {tipo_atual}")
            print(f"{'─' * 60}")
            # Mostra o chunk (limitado a 40 linhas para legibilidade)
            linhas_chunk = chunk.split("\n")
            for linha in linhas_chunk[:40]:
                print(f"  │ {linha}")
            if len(linhas_chunk) > 40:
                print(f"  │ ... ({len(linhas_chunk) - 40} linhas omitidas)")
            print(f"{'─' * 60}")

            # Loop de edição
            while True:
                print(f"\n[Tipo: {tipo_atual}] Criar par? (s/p/q/t <tipo>): ", end="")
                cmd = input().strip().lower()

                if cmd == "q":
                    salvar_progresso(progresso)
                    logger.info(f"\n✅ Progresso salvo! {progresso['total_exemplos']} exemplos criados.")
                    return

                if cmd == "p":
                    progresso["chunks_processados"].append(chunk_id)
                    salvar_progresso(progresso)
                    break

                if cmd.startswith("t "):
                    novo_tipo = cmd[2:].strip()
                    if novo_tipo in TIPO_DISTRIBUICAO:
                        tipo_atual = novo_tipo
                        print(f"  Tipo alterado para: {tipo_atual}")
                    else:
                        print(f"  Tipos válidos: {list(TIPO_DISTRIBUICAO.keys())}")
                    continue

                if cmd == "s" or cmd == "":
                    # Coleta a pergunta
                    print("\n  Pergunta do aluno:")
                    pergunta = input("  > ").strip()
                    if not pergunta:
                        print("  ⚠ Pergunta vazia, tente novamente.")
                        continue

                    # Coleta a resposta (multi-linha, termina com linha vazia)
                    print("  Resposta do professor (linha vazia para terminar):")
                    linhas_resposta = []
                    while True:
                        linha = input("  > ")
                        if linha == "":
                            break
                        linhas_resposta.append(linha)

                    resposta = "\n".join(linhas_resposta)
                    if not resposta:
                        print("  ⚠ Resposta vazia, tente novamente.")
                        continue

                    # Cria e salva o exemplo
                    exemplo = criar_exemplo_sharegpt(pergunta, resposta)
                    salvar_exemplo(exemplo)

                    progresso["chunks_processados"].append(chunk_id)
                    progresso["contagem_tipos"][tipo_atual] = (
                        progresso["contagem_tipos"].get(tipo_atual, 0) + 1
                    )
                    progresso["total_exemplos"] += 1
                    salvar_progresso(progresso)

                    tipo_atual = tipo_necessario(progresso)

                    print(f"  ✅ Exemplo #{progresso['total_exemplos']} salvo! (tipo: {tipo_atual} sugerido a seguir)")
                    break

    logger.info(f"\n🏁 Todos os chunks processados! Total: {progresso['total_exemplos']} exemplos")


# ─── Modo Automático (Ollama) ──────────────────────────────────────────────


def modo_automatico(
    modelo: str = DEFAULT_MODEL,
    total_alvo: int = 300,
    temperatura: float = 0.7,
):
    """
    Modo automático: usa Ollama para gerar pares de instrução-resposta
    automaticamente a partir dos chunks de texto.

    Args:
        modelo: Nome do modelo no Ollama
        total_alvo: Número alvo de exemplos a gerar
        temperatura: Temperatura de geração
    """
    logger.info(f"🤖 Modo AUTOMÁTICO — Geração via Ollama ({modelo})")
    print("=" * 60)

    # Verifica Ollama
    if not verificar_ollama(modelo):
        sys.exit(1)

    # Carrega textos extraídos
    arquivos_txt = sorted(RAW_DIR.glob("*.txt"))
    if not arquivos_txt:
        logger.error(f"Nenhum arquivo .txt encontrado em {RAW_DIR}")
        sys.exit(1)

    # Carrega progresso
    progresso = carregar_progresso()
    logger.info(f"📊 Dataset atual: {progresso['total_exemplos']} exemplos")
    logger.info(f"🎯 Alvo: {total_alvo} exemplos\n")

    if progresso["total_exemplos"] >= total_alvo:
        logger.info("✅ Alvo já atingido!")
        return

    # Coleta todos os chunks
    todos_chunks = []
    for arquivo in arquivos_txt:
        texto = arquivo.read_text(encoding="utf-8")
        chunks = dividir_em_chunks(texto)
        for i, chunk in enumerate(chunks):
            chunk_id = f"{arquivo.stem}::{i}"
            if chunk_id not in progresso["chunks_processados"]:
                todos_chunks.append((chunk_id, chunk, arquivo.name))

    logger.info(f"📦 {len(todos_chunks)} chunks disponíveis para processamento")

    falhas_consecutivas = 0
    max_falhas = 5

    for chunk_id, chunk, nome_arquivo in todos_chunks:
        if progresso["total_exemplos"] >= total_alvo:
            break

        if falhas_consecutivas >= max_falhas:
            logger.error(
                f"Muitas falhas consecutivas ({max_falhas}). Parando."
            )
            break

        # Determina tipo necessário
        tipo = tipo_necessario(progresso, total_alvo)

        # Monta o prompt
        prompt = PROMPTS_GERACAO[tipo].format(texto=chunk[:1500])

        logger.info(
            f"[{progresso['total_exemplos'] + 1}/{total_alvo}] "
            f"Gerando '{tipo}' de '{nome_arquivo}'..."
        )

        # Chama Ollama
        resposta_raw = chamar_ollama(prompt, modelo, temperatura)

        if not resposta_raw:
            falhas_consecutivas += 1
            logger.warning(f"  ⚠ Sem resposta do Ollama (falha {falhas_consecutivas}/{max_falhas})")
            time.sleep(2)
            continue

        # Extrai JSON da resposta
        par = extrair_json_da_resposta(resposta_raw)

        if not par or "pergunta" not in par or "resposta" not in par:
            falhas_consecutivas += 1
            logger.warning(
                f"  ⚠ Resposta inválida (falha {falhas_consecutivas}/{max_falhas}): "
                f"{resposta_raw[:100]}..."
            )
            time.sleep(1)
            continue

        # Validação básica de qualidade
        if len(par["pergunta"]) < 10 or len(par["resposta"]) < 20:
            logger.warning("  ⚠ Par muito curto, pulando.")
            continue

        # Cria e salva o exemplo
        exemplo = criar_exemplo_sharegpt(par["pergunta"], par["resposta"])
        salvar_exemplo(exemplo)

        progresso["chunks_processados"].append(chunk_id)
        progresso["contagem_tipos"][tipo] = (
            progresso["contagem_tipos"].get(tipo, 0) + 1
        )
        progresso["total_exemplos"] += 1
        salvar_progresso(progresso)

        falhas_consecutivas = 0  # Reset em sucesso

        logger.info(
            f"  ✅ #{progresso['total_exemplos']} [{tipo}] "
            f"P: {par['pergunta'][:60]}..."
        )

        # Pausa breve para não sobrecarregar
        time.sleep(0.5)

    # Resumo final
    print("\n" + "=" * 60)
    print("📊 RESUMO DA GERAÇÃO AUTOMÁTICA")
    print("=" * 60)
    print(f"  Total de exemplos: {progresso['total_exemplos']}")
    print(f"  Alvo:              {total_alvo}")
    print("\n  Distribuição por tipo:")
    for tipo, contagem in progresso["contagem_tipos"].items():
        pct = contagem / max(progresso["total_exemplos"], 1) * 100
        alvo_pct = TIPO_DISTRIBUICAO[tipo] * 100
        print(f"    {tipo:12s}: {contagem:3d} ({pct:5.1f}%) — alvo: {alvo_pct:.0f}%")
    print("=" * 60)


# ─── Modo Revisão ──────────────────────────────────────────────────────────


def modo_revisao():
    """
    Modo revisão: permite visualizar e editar exemplos existentes no dataset.
    """
    logger.info("🔍 Modo REVISÃO — Edição de exemplos existentes")

    exemplos = carregar_dataset()
    if not exemplos:
        logger.info("Dataset vazio. Use modo 'interativo' ou 'auto' primeiro.")
        return

    logger.info(f"📊 {len(exemplos)} exemplos no dataset\n")

    exemplos_editados = []
    removidos = 0

    for i, exemplo in enumerate(exemplos):
        convs = exemplo.get("conversations", [])
        pergunta = next((c["content"] for c in convs if c["role"] == "user"), "?")
        resposta = next((c["content"] for c in convs if c["role"] == "assistant"), "?")

        print(f"\n{'─' * 60}")
        print(f"Exemplo {i + 1}/{len(exemplos)}")
        print(f"{'─' * 60}")
        print(f"  PERGUNTA: {pergunta[:200]}")
        print(f"  RESPOSTA: {resposta[:300]}")
        if len(resposta) > 300:
            print(f"  ... ({len(resposta)} chars total)")
        print(f"{'─' * 60}")
        print("  [Enter] manter | [e]ditar | [r]emover | [q]uit: ", end="")

        cmd = input().strip().lower()

        if cmd == "q":
            # Mantém os restantes sem alteração
            exemplos_editados.extend(exemplos[i:])
            break
        elif cmd == "r":
            removidos += 1
            print("  🗑️ Removido.")
            continue
        elif cmd == "e":
            print("  Nova pergunta (Enter para manter):")
            nova_p = input("  > ").strip()
            if nova_p:
                for c in convs:
                    if c["role"] == "user":
                        c["content"] = nova_p
            print("  Nova resposta (Enter para manter, linha vazia para terminar):")
            linhas = []
            while True:
                linha = input("  > ")
                if linha == "" and linhas:
                    break
                if linha == "" and not linhas:
                    break
                linhas.append(linha)
            if linhas:
                nova_r = "\n".join(linhas)
                for c in convs:
                    if c["role"] == "assistant":
                        c["content"] = nova_r
            print("  ✏️ Editado.")
            exemplos_editados.append(exemplo)
        else:
            exemplos_editados.append(exemplo)

    # Reescreve o dataset
    if removidos > 0 or any(True for _ in []):  # Sempre reescreve ao final
        # Backup do original
        backup = DATASET_FILE.with_suffix(".jsonl.bak")
        if DATASET_FILE.exists():
            import shutil
            shutil.copy2(DATASET_FILE, backup)
            logger.info(f"📋 Backup salvo em: {backup}")

        with open(DATASET_FILE, "w", encoding="utf-8") as f:
            for ex in exemplos_editados:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        logger.info(
            f"✅ Dataset atualizado: {len(exemplos_editados)} exemplos "
            f"({removidos} removidos)"
        )


# ─── Estatísticas ───────────────────────────────────────────────────────────


def mostrar_estatisticas():
    """Mostra estatísticas detalhadas do dataset atual."""
    exemplos = carregar_dataset()
    if not exemplos:
        print("Dataset vazio.")
        return

    total = len(exemplos)
    tamanhos_perguntas = []
    tamanhos_respostas = []

    for ex in exemplos:
        convs = ex.get("conversations", [])
        for c in convs:
            if c["role"] == "user":
                tamanhos_perguntas.append(len(c["content"]))
            elif c["role"] == "assistant":
                tamanhos_respostas.append(len(c["content"]))

    print("\n" + "=" * 60)
    print("📊 ESTATÍSTICAS DO DATASET")
    print("=" * 60)
    print(f"  Total de exemplos:           {total}")
    print(f"  Alvo mínimo:                 200")
    print(f"  Alvo máximo:                 400")
    print(f"  Progresso:                   {total/200*100:.0f}% do mínimo")
    if tamanhos_perguntas:
        print(f"\n  Perguntas:")
        print(f"    Tamanho médio:             {sum(tamanhos_perguntas)/len(tamanhos_perguntas):.0f} chars")
        print(f"    Menor:                     {min(tamanhos_perguntas)} chars")
        print(f"    Maior:                     {max(tamanhos_perguntas)} chars")
    if tamanhos_respostas:
        print(f"\n  Respostas:")
        print(f"    Tamanho médio:             {sum(tamanhos_respostas)/len(tamanhos_respostas):.0f} chars")
        print(f"    Menor:                     {min(tamanhos_respostas)} chars")
        print(f"    Maior:                     {max(tamanhos_respostas)} chars")

    # Progresso por tipo
    progresso = carregar_progresso()
    if progresso["contagem_tipos"]:
        print(f"\n  Distribuição por tipo:")
        for tipo, contagem in progresso["contagem_tipos"].items():
            pct = contagem / max(total, 1) * 100
            alvo_pct = TIPO_DISTRIBUICAO.get(tipo, 0) * 100
            barra = "█" * int(pct / 2) + "░" * int((alvo_pct - pct) / 2)
            print(f"    {tipo:12s}: {contagem:3d} ({pct:5.1f}%) {barra} alvo: {alvo_pct:.0f}%")

    print("=" * 60)


# ─── Main ───────────────────────────────────────────────────────────────────


def main():
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Preparação de dataset para fine-tuning do Physics Teacher SLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Modos de operação:
              interativo  Criar pares manualmente, revisando cada chunk
              auto        Gerar pares automaticamente via Ollama API
              revisao     Revisar e editar exemplos existentes
              stats       Mostrar estatísticas do dataset

            Exemplos:
              python training/prepare_dataset.py --modo interativo
              python training/prepare_dataset.py --modo auto --modelo qwen2.5:3b
              python training/prepare_dataset.py --modo auto --alvo 300
              python training/prepare_dataset.py --modo stats
        """),
    )
    parser.add_argument(
        "--modo", "-m",
        choices=["interativo", "auto", "revisao", "stats"],
        default="stats",
        help="Modo de operação (padrão: stats)",
    )
    parser.add_argument(
        "--modelo",
        default=DEFAULT_MODEL,
        help=f"Modelo Ollama para modo auto (padrão: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--alvo",
        type=int,
        default=300,
        help="Número alvo de exemplos para modo auto (padrão: 300)",
    )
    parser.add_argument(
        "--temperatura",
        type=float,
        default=0.7,
        help="Temperatura de geração para modo auto (padrão: 0.7)",
    )
    parser.add_argument(
        "--reset-progresso",
        action="store_true",
        help="Remove o arquivo de progresso e recomeça do zero",
    )

    args = parser.parse_args()

    # Reset de progresso se solicitado
    if args.reset_progresso:
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
            logger.info("🔄 Progresso resetado.")

    logger.info("📚 Preparação de Dataset — Physics Teacher SLM\n")

    if args.modo == "interativo":
        modo_interativo()
    elif args.modo == "auto":
        modo_automatico(args.modelo, args.alvo, args.temperatura)
    elif args.modo == "revisao":
        modo_revisao()
    elif args.modo == "stats":
        mostrar_estatisticas()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Motor de consultas RAG para o Professor de Física SLM.

Carrega o índice ChromaDB existente e permite consultas interativas
ou programáticas usando o modelo Qwen 2.5 3B via Ollama.

Uso CLI:
    python query_engine.py
    python query_engine.py --model qwen2.5:3b --db-dir ./chroma_db

Uso como módulo:
    from rag.query_engine import criar_query_engine, consultar
    engine = criar_query_engine()
    resposta = consultar(engine, "O que é a segunda lei de Newton?")
"""

import argparse
import logging
import sys
import textwrap
from pathlib import Path

from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

# ---------------------------------------------------------------------------
# Configuração de logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes padrão
# ---------------------------------------------------------------------------
DEFAULT_DB_DIR = Path(__file__).resolve().parent / "chroma_db"
DEFAULT_MODEL = "qwen2.5:3b"
EMBED_MODEL_NAME = "nomic-embed-text"
OLLAMA_BASE_URL = "http://localhost:11434"
COLLECTION_NAME = "physics_teacher"
SIMILARITY_TOP_K = 3

# Timeout generoso para respostas longas em hardware modesto
REQUEST_TIMEOUT = 120.0


def verificar_ollama(base_url: str = OLLAMA_BASE_URL) -> bool:
    """Verifica se o servidor Ollama está rodando e acessível.

    Args:
        base_url: URL base do servidor Ollama.

    Returns:
        True se o Ollama responder, False caso contrário.
    """
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5):
            return True
    except (urllib.error.URLError, ConnectionError, OSError) as exc:
        logger.error("Não foi possível conectar ao Ollama em %s: %s", base_url, exc)
        return False


def criar_query_engine(
    db_dir: Path = DEFAULT_DB_DIR,
    model_name: str = DEFAULT_MODEL,
    similarity_top_k: int = SIMILARITY_TOP_K,
):
    """Cria o query engine a partir de um índice ChromaDB existente.

    Carrega o vector store persistido, configura o LLM e embeddings
    via Ollama, e retorna um query engine pronto para consultas.

    Args:
        db_dir: Diretório onde o ChromaDB está persistido.
        model_name: Nome do modelo Ollama para geração de respostas.
        similarity_top_k: Número de chunks mais similares a recuperar.

    Returns:
        QueryEngine do LlamaIndex configurado e pronto para uso.

    Raises:
        FileNotFoundError: Se o diretório do ChromaDB não existir.
        RuntimeError: Se a coleção não existir (índice não construído).
    """
    # --- Verificar que o índice existe ---
    if not db_dir.exists():
        raise FileNotFoundError(
            f"Diretório do ChromaDB não encontrado: {db_dir}\n"
            f"Execute primeiro: python build_index.py"
        )

    # --- Verificar Ollama ---
    logger.info("Verificando conexão com Ollama...")
    if not verificar_ollama():
        raise ConnectionError(
            "Ollama não está rodando! Inicie com: ollama serve\n"
            f"Modelos necessários: {model_name}, {EMBED_MODEL_NAME}"
        )
    logger.info("✓ Ollama conectado")

    # --- Configurar embeddings (mesmo modelo usado na indexação) ---
    logger.info("Configurando embeddings: %s", EMBED_MODEL_NAME)
    embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
    )
    Settings.embed_model = embed_model

    # --- Configurar LLM ---
    logger.info("Configurando LLM: %s", model_name)
    llm = Ollama(
        model=model_name,
        base_url=OLLAMA_BASE_URL,
        request_timeout=REQUEST_TIMEOUT,
    )
    Settings.llm = llm

    # --- Carregar ChromaDB ---
    logger.info("Carregando índice de: %s", db_dir)
    chroma_client = chromadb.PersistentClient(path=str(db_dir))

    try:
        chroma_collection = chroma_client.get_collection(COLLECTION_NAME)
    except ValueError:
        raise RuntimeError(
            f"Coleção '{COLLECTION_NAME}' não encontrada no ChromaDB.\n"
            f"Execute primeiro: python build_index.py"
        )

    num_chunks = chroma_collection.count()
    logger.info("✓ Índice carregado (%d chunks na coleção)", num_chunks)

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)

    # --- Criar query engine ---
    query_engine = index.as_query_engine(
        similarity_top_k=similarity_top_k,
    )

    return query_engine


def consultar(query_engine, pergunta: str) -> dict:
    """Realiza uma consulta ao motor RAG e retorna resposta estruturada.

    Args:
        query_engine: QueryEngine do LlamaIndex.
        pergunta: Pergunta em linguagem natural.

    Returns:
        Dicionário com:
            - 'resposta': Texto da resposta gerada.
            - 'fontes': Lista de dicts com metadados das fontes usadas.
    """
    logger.info("Processando pergunta: %s", pergunta[:80])
    response = query_engine.query(pergunta)

    # Extract source information from response
    fontes = []
    if response.source_nodes:
        for node in response.source_nodes:
            fonte_info = {
                "arquivo": node.metadata.get("file_name", "desconhecido"),
                "pagina": node.metadata.get("page_label", "N/A"),
                "score": round(node.score, 4) if node.score else None,
                "trecho": node.text[:200] + "..." if len(node.text) > 200 else node.text,
            }
            fontes.append(fonte_info)

    return {
        "resposta": str(response),
        "fontes": fontes,
    }


def formatar_resposta(resultado: dict) -> str:
    """Formata a resposta e fontes para exibição no terminal.

    Args:
        resultado: Dicionário retornado pela função consultar().

    Returns:
        String formatada pronta para impressão.
    """
    linhas = []
    linhas.append("")
    linhas.append("=" * 70)
    linhas.append("  RESPOSTA")
    linhas.append("=" * 70)

    # Word-wrap the response for readable terminal output
    resposta_wrapped = textwrap.fill(
        resultado["resposta"],
        width=68,
        initial_indent="  ",
        subsequent_indent="  ",
    )
    linhas.append(resposta_wrapped)

    if resultado["fontes"]:
        linhas.append("")
        linhas.append("-" * 70)
        linhas.append(f"  FONTES ({len(resultado['fontes'])} referências)")
        linhas.append("-" * 70)
        for i, fonte in enumerate(resultado["fontes"], 1):
            score_str = f" (score: {fonte['score']})" if fonte["score"] else ""
            linhas.append(f"  [{i}] {fonte['arquivo']} — pág. {fonte['pagina']}{score_str}")
            trecho_wrapped = textwrap.fill(
                fonte["trecho"],
                width=64,
                initial_indent="      ",
                subsequent_indent="      ",
            )
            linhas.append(trecho_wrapped)

    linhas.append("=" * 70)
    linhas.append("")
    return "\n".join(linhas)


def modo_interativo(query_engine) -> None:
    """Executa o loop interativo de perguntas e respostas no terminal.

    O usuário digita perguntas e recebe respostas do RAG.
    Digite 'sair', 'exit' ou 'q' para encerrar.

    Args:
        query_engine: QueryEngine do LlamaIndex já configurado.
    """
    print("\n" + "=" * 70)
    print("  🎓 Professor de Física — RAG Query Engine")
    print("  Digite sua pergunta sobre física.")
    print("  Comandos: 'sair', 'exit' ou 'q' para encerrar.")
    print("=" * 70 + "\n")

    while True:
        try:
            pergunta = input("📝 Pergunta: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nEncerrando...")
            break

        if not pergunta:
            continue

        if pergunta.lower() in ("sair", "exit", "q", "quit"):
            print("Até logo! 👋")
            break

        try:
            resultado = consultar(query_engine, pergunta)
            print(formatar_resposta(resultado))
        except Exception as e:
            logger.error("Erro ao processar pergunta: %s", e)
            print(f"\n⚠️  Erro: {e}\n")


def parse_args() -> argparse.Namespace:
    """Processa argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Motor de consultas RAG para o Professor de Física SLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python query_engine.py\n"
            "  python query_engine.py --model qwen2.5:3b\n"
            "  python query_engine.py --db-dir ./chroma_db --model qwen2.5:3b\n"
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Modelo Ollama para geração de respostas (padrão: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=DEFAULT_DB_DIR,
        help=f"Diretório do ChromaDB persistido (padrão: {DEFAULT_DB_DIR})",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=SIMILARITY_TOP_K,
        help=f"Número de chunks similares a recuperar (padrão: {SIMILARITY_TOP_K})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        engine = criar_query_engine(
            db_dir=args.db_dir,
            model_name=args.model,
            similarity_top_k=args.top_k,
        )
    except (FileNotFoundError, ConnectionError, RuntimeError) as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception("Erro inesperado ao inicializar o query engine: %s", e)
        sys.exit(1)

    modo_interativo(engine)

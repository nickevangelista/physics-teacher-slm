#!/usr/bin/env python3
"""
Construção do índice vetorial ChromaDB a partir de documentos do professor.

Este script lê documentos (PDF, TXT, etc.) de um diretório,
divide-os em chunks usando SentenceSplitter, gera embeddings
com nomic-embed-text via Ollama, e persiste o índice no ChromaDB.

Uso:
    python build_index.py
    python build_index.py --docs-dir ../teacher_docs --db-dir ./chroma_db
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    Settings,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
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
DEFAULT_DOCS_DIR = Path(__file__).resolve().parent.parent / "teacher_docs"
DEFAULT_DB_DIR = Path(__file__).resolve().parent / "chroma_db"
EMBED_MODEL_NAME = "nomic-embed-text"
OLLAMA_BASE_URL = "http://localhost:11434"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
COLLECTION_NAME = "physics_teacher"


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


def carregar_documentos(docs_dir: Path) -> list:
    """Carrega documentos do diretório especificado.

    Suporta PDF, TXT, MD e outros formatos reconhecidos pelo SimpleDirectoryReader.

    Args:
        docs_dir: Caminho para o diretório contendo os documentos.

    Returns:
        Lista de objetos Document carregados.

    Raises:
        FileNotFoundError: Se o diretório não existir.
        ValueError: Se nenhum documento for encontrado.
    """
    if not docs_dir.exists():
        raise FileNotFoundError(
            f"Diretório de documentos não encontrado: {docs_dir}\n"
            f"Crie o diretório e adicione seus PDFs/documentos lá."
        )

    if not docs_dir.is_dir():
        raise NotADirectoryError(f"O caminho não é um diretório: {docs_dir}")

    logger.info("Carregando documentos de: %s", docs_dir)
    reader = SimpleDirectoryReader(
        input_dir=str(docs_dir),
        recursive=True,  # Lê subdiretórios também
        filename_as_id=True,
    )
    documents = reader.load_data()

    if not documents:
        raise ValueError(
            f"Nenhum documento encontrado em: {docs_dir}\n"
            f"Adicione arquivos PDF, TXT ou MD ao diretório."
        )

    logger.info("Total de documentos carregados: %d", len(documents))
    return documents


def construir_indice(
    docs_dir: Path = DEFAULT_DOCS_DIR,
    db_dir: Path = DEFAULT_DB_DIR,
) -> VectorStoreIndex:
    """Constrói o índice vetorial ChromaDB a partir dos documentos.

    Pipeline completo:
    1. Verifica conexão com Ollama
    2. Carrega documentos do diretório
    3. Configura embeddings (nomic-embed-text via Ollama)
    4. Divide documentos em chunks (SentenceSplitter)
    5. Cria/atualiza índice no ChromaDB

    Args:
        docs_dir: Diretório contendo os documentos fonte.
        db_dir: Diretório para persistir o banco ChromaDB.

    Returns:
        VectorStoreIndex pronto para consultas.
    """
    start_time = time.time()

    # --- 1. Verificar Ollama ---
    logger.info("Verificando conexão com Ollama...")
    if not verificar_ollama():
        logger.error(
            "Ollama não está rodando! Inicie com: ollama serve\n"
            "E certifique-se de ter o modelo: ollama pull %s",
            EMBED_MODEL_NAME,
        )
        sys.exit(1)
    logger.info("✓ Ollama conectado com sucesso")

    # --- 2. Carregar documentos ---
    documents = carregar_documentos(docs_dir)

    # Log file names for visibility
    unique_files = {doc.metadata.get("file_name", "desconhecido") for doc in documents}
    logger.info("Arquivos encontrados (%d):", len(unique_files))
    for fname in sorted(unique_files):
        logger.info("  → %s", fname)

    # --- 3. Configurar embeddings via Ollama ---
    logger.info("Configurando modelo de embeddings: %s", EMBED_MODEL_NAME)
    embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
    )
    Settings.embed_model = embed_model

    # --- 4. Configurar node parser (SentenceSplitter) ---
    logger.info(
        "Configurando SentenceSplitter (chunk_size=%d, overlap=%d)",
        CHUNK_SIZE,
        CHUNK_OVERLAP,
    )
    Settings.node_parser = SentenceSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    # We don't set an LLM here — this script only builds the index
    Settings.llm = None

    # --- 5. Configurar ChromaDB ---
    logger.info("Configurando ChromaDB em: %s", db_dir)
    db_dir.mkdir(parents=True, exist_ok=True)

    chroma_client = chromadb.PersistentClient(path=str(db_dir))

    # Delete existing collection to rebuild from scratch
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
        logger.info("Coleção anterior '%s' removida para reconstrução", COLLECTION_NAME)
    except ValueError:
        # Collection doesn't exist yet — that's fine
        pass

    chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # --- 6. Construir índice ---
    logger.info("Construindo índice vetorial... (isso pode demorar)")
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )

    elapsed = time.time() - start_time

    # --- 7. Estatísticas finais ---
    num_chunks = chroma_collection.count()
    logger.info("=" * 60)
    logger.info("ÍNDICE CONSTRUÍDO COM SUCESSO!")
    logger.info("=" * 60)
    logger.info("  Documentos carregados : %d", len(documents))
    logger.info("  Arquivos únicos       : %d", len(unique_files))
    logger.info("  Chunks no índice      : %d", num_chunks)
    logger.info("  Modelo de embeddings  : %s", EMBED_MODEL_NAME)
    logger.info("  Chunk size / overlap  : %d / %d", CHUNK_SIZE, CHUNK_OVERLAP)
    logger.info("  ChromaDB salvo em     : %s", db_dir.resolve())
    logger.info("  Tempo total           : %.1f segundos", elapsed)
    logger.info("=" * 60)

    return index


def parse_args() -> argparse.Namespace:
    """Processa argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Constrói o índice vetorial ChromaDB a partir de documentos do professor.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python build_index.py\n"
            "  python build_index.py --docs-dir ./meus_docs --db-dir ./meu_db\n"
        ),
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=DEFAULT_DOCS_DIR,
        help=f"Diretório com os documentos fonte (padrão: {DEFAULT_DOCS_DIR})",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=DEFAULT_DB_DIR,
        help=f"Diretório para persistir o ChromaDB (padrão: {DEFAULT_DB_DIR})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        construir_indice(docs_dir=args.docs_dir, db_dir=args.db_dir)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception("Erro inesperado ao construir o índice: %s", e)
        sys.exit(1)

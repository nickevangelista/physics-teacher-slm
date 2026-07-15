#!/usr/bin/env python3
"""
extract_pdfs.py — Extração de texto de PDFs do professor de Física.

Lê todos os PDFs de teacher_docs/, extrai texto preservando estrutura
(cabeçalhos, listas, equações quando possível) e salva como .txt em data/raw/.

Uso:
    python scripts/extract_pdfs.py
    python scripts/extract_pdfs.py --input teacher_docs/ --output data/processed/
"""

import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Raiz do projeto (dois níveis acima deste script)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Diretórios padrão
DEFAULT_INPUT_DIR = PROJECT_ROOT / "teacher_docs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"


def limpar_texto(texto: str) -> str:
    """
    Limpa e normaliza o texto extraído de um PDF.

    - Remove caracteres de controle inválidos
    - Normaliza espaços em branco excessivos
    - Preserva quebras de parágrafo (linhas duplas)
    - Tenta preservar formatação de listas e equações
    """
    if not texto:
        return ""

    # Remove caracteres nulos e de controle (exceto newline e tab)
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", texto)

    # Normaliza diferentes tipos de espaço Unicode para espaço simples
    texto = re.sub(r"[\u00a0\u2000-\u200b\u202f\u205f\u3000]", " ", texto)

    # Remove espaços múltiplos dentro de uma linha (preserva indentação inicial)
    linhas = texto.split("\n")
    linhas_limpas = []
    for linha in linhas:
        # Preserva indentação para listas e sub-itens
        match_indent = re.match(r"^(\s*)", linha)
        indent = match_indent.group(1) if match_indent else ""
        conteudo = linha.strip()
        # Colapsa espaços múltiplos no conteúdo
        conteudo = re.sub(r"  +", " ", conteudo)
        if conteudo:
            linhas_limpas.append(f"{indent}{conteudo}")
        else:
            linhas_limpas.append("")

    texto = "\n".join(linhas_limpas)

    # Colapsa 3+ linhas vazias consecutivas em 2 (preserva separação de parágrafos)
    texto = re.sub(r"\n{3,}", "\n\n", texto)

    return texto.strip()


def detectar_cabecalhos(texto: str) -> str:
    """
    Tenta identificar e marcar cabeçalhos no texto extraído.

    Heurísticas usadas:
    - Linhas curtas em MAIÚSCULAS → provável título/cabeçalho
    - Linhas que começam com numeração (1., 1.1, etc.) → seções
    - Linhas seguidas de sublinhado (===, ---) → títulos
    """
    linhas = texto.split("\n")
    resultado = []

    for i, linha in enumerate(linhas):
        stripped = linha.strip()

        if not stripped:
            resultado.append(linha)
            continue

        # Detecta linhas de sublinhado (títulos com === ou ---)
        if i > 0 and re.match(r"^[=\-]{3,}$", stripped):
            # A linha anterior é um título
            if resultado and resultado[-1].strip():
                resultado[-1] = f"## {resultado[-1].strip()}"
            continue

        # Detecta linhas curtas em MAIÚSCULAS (possíveis títulos)
        if (
            stripped.isupper()
            and len(stripped) < 80
            and len(stripped.split()) <= 10
            and not stripped.startswith(("-", "•", "*"))
        ):
            resultado.append(f"\n# {stripped}\n")
            continue

        # Detecta seções numeradas (1. Título, 1.1 Sub-título, etc.)
        match_secao = re.match(r"^(\d+\.(?:\d+\.?)*)\s+(.+)$", stripped)
        if match_secao and len(stripped) < 100:
            nivel = match_secao.group(1).count(".")
            prefixo = "#" * min(nivel + 1, 4)
            resultado.append(f"\n{prefixo} {stripped}\n")
            continue

        resultado.append(linha)

    return "\n".join(resultado)


def extrair_texto_pdf(caminho_pdf: Path) -> dict:
    """
    Extrai texto de um arquivo PDF usando pymupdf.

    Retorna um dicionário com:
    - 'texto': texto completo extraído e limpo
    - 'num_paginas': número de páginas
    - 'num_caracteres': número de caracteres no texto limpo
    - 'metadados': metadados do PDF (título, autor, etc.)
    """
    try:
        import pymupdf  # noqa: F811
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore  # noqa: F811
        except ImportError:
            logger.error(
                "pymupdf não encontrado. Instale com: pip install pymupdf"
            )
            sys.exit(1)

    try:
        doc = pymupdf.open(str(caminho_pdf))
    except Exception as e:
        logger.error(f"Erro ao abrir PDF '{caminho_pdf.name}': {e}")
        return {
            "texto": "",
            "num_paginas": 0,
            "num_caracteres": 0,
            "metadados": {},
        }

    metadados = doc.metadata or {}
    textos_paginas = []

    num_paginas = len(doc)
    for num_pagina in range(num_paginas):
        try:
            pagina = doc[num_pagina]

            # Extrai texto preservando layout quando possível
            # flags: TEXT_PRESERVE_WHITESPACE | TEXT_PRESERVE_LIGATURES
            texto_pagina = pagina.get_text("text", sort=True)

            if texto_pagina.strip():
                # Adiciona marcador de página para referência
                textos_paginas.append(
                    f"--- Página {num_pagina + 1} ---\n{texto_pagina}"
                )
        except Exception as e:
            logger.warning(
                f"Erro na página {num_pagina + 1} de '{caminho_pdf.name}': {e}"
            )
            continue

    doc.close()

    # Junta todo o texto
    texto_completo = "\n\n".join(textos_paginas)

    # Limpa e normaliza
    texto_limpo = limpar_texto(texto_completo)

    # Tenta detectar e marcar cabeçalhos
    texto_final = detectar_cabecalhos(texto_limpo)

    return {
        "texto": texto_final,
        "num_paginas": num_paginas,
        "num_caracteres": len(texto_final),
        "metadados": metadados,
    }


def processar_diretorio(
    dir_entrada: Path, dir_saida: Path, sobrescrever: bool = False
) -> dict:
    """
    Processa todos os PDFs de um diretório e salva os textos extraídos.

    Args:
        dir_entrada: Diretório com os PDFs
        dir_saida: Diretório onde salvar os .txt
        sobrescrever: Se True, sobrescreve arquivos existentes

    Returns:
        Estatísticas do processamento
    """
    # Verifica se o diretório de entrada existe
    if not dir_entrada.exists():
        logger.error(f"Diretório de entrada não encontrado: {dir_entrada}")
        sys.exit(1)

    # Cria diretório de saída se não existir
    dir_saida.mkdir(parents=True, exist_ok=True)

    # Lista todos os PDFs
    pdfs = sorted(dir_entrada.glob("*.pdf"))
    if not pdfs:
        # Tenta busca case-insensitive
        pdfs = sorted(
            p for p in dir_entrada.iterdir()
            if p.suffix.lower() == ".pdf"
        )

    if not pdfs:
        logger.warning(f"Nenhum PDF encontrado em: {dir_entrada}")
        return {
            "total": 0,
            "sucesso": 0,
            "falhas": 0,
            "pulados": 0,
        }

    logger.info(f"Encontrados {len(pdfs)} PDF(s) em '{dir_entrada}'")
    logger.info(f"Saída será salva em '{dir_saida}'\n")

    # Estatísticas
    stats = {
        "total": len(pdfs),
        "sucesso": 0,
        "falhas": 0,
        "pulados": 0,
        "total_paginas": 0,
        "total_caracteres": 0,
    }

    inicio = time.time()

    for i, pdf in enumerate(pdfs, 1):
        nome_saida = pdf.stem + ".txt"
        caminho_saida = dir_saida / nome_saida

        # Verifica se já existe
        if caminho_saida.exists() and not sobrescrever:
            logger.info(
                f"  [{i}/{len(pdfs)}] ⏭ '{pdf.name}' → já existe, pulando"
            )
            stats["pulados"] += 1
            continue

        logger.info(f"  [{i}/{len(pdfs)}] 📄 Processando '{pdf.name}'...")

        # Extrai texto
        resultado = extrair_texto_pdf(pdf)

        if not resultado["texto"]:
            logger.warning(f"    ⚠ Nenhum texto extraído de '{pdf.name}'")
            stats["falhas"] += 1
            continue

        # Salva o texto extraído
        try:
            # Adiciona cabeçalho com informações do arquivo original
            cabecalho = (
                f"# Fonte: {pdf.name}\n"
                f"# Páginas: {resultado['num_paginas']}\n"
                f"# Caracteres: {resultado['num_caracteres']}\n"
            )
            if resultado["metadados"].get("title"):
                cabecalho += f"# Título: {resultado['metadados']['title']}\n"
            if resultado["metadados"].get("author"):
                cabecalho += f"# Autor: {resultado['metadados']['author']}\n"
            cabecalho += "#" + "=" * 60 + "\n\n"

            conteudo_final = cabecalho + resultado["texto"]

            caminho_saida.write_text(conteudo_final, encoding="utf-8")

            stats["sucesso"] += 1
            stats["total_paginas"] += resultado["num_paginas"]
            stats["total_caracteres"] += resultado["num_caracteres"]

            logger.info(
                f"    ✅ {resultado['num_paginas']} págs, "
                f"{resultado['num_caracteres']:,} chars → '{nome_saida}'"
            )

        except Exception as e:
            logger.error(f"    ❌ Erro ao salvar '{nome_saida}': {e}")
            stats["falhas"] += 1

    tempo_total = time.time() - inicio

    # Resumo final
    logger.info("\n" + "=" * 60)
    logger.info("📊 RESUMO DA EXTRAÇÃO")
    logger.info("=" * 60)
    logger.info(f"  Total de PDFs:       {stats['total']}")
    logger.info(f"  Extraídos com êxito: {stats['sucesso']}")
    logger.info(f"  Pulados (existiam):  {stats['pulados']}")
    logger.info(f"  Falhas:              {stats['falhas']}")
    logger.info(f"  Total de páginas:    {stats['total_paginas']}")
    logger.info(f"  Total de caracteres: {stats['total_caracteres']:,}")
    logger.info(f"  Tempo total:         {tempo_total:.1f}s")
    logger.info("=" * 60)

    return stats


def main():
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Extrai texto de PDFs do professor de Física.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python scripts/extract_pdfs.py\n"
            "  python scripts/extract_pdfs.py --sobrescrever\n"
            "  python scripts/extract_pdfs.py --input meus_pdfs/ --output saida/"
        ),
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Diretório com PDFs (padrão: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Diretório de saída para .txt (padrão: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--sobrescrever",
        action="store_true",
        help="Sobrescreve arquivos .txt existentes",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mostra informações detalhadas de debug",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("🔬 Extrator de PDFs — Physics Teacher SLM")
    logger.info(f"   Entrada: {args.input}")
    logger.info(f"   Saída:   {args.output}\n")

    stats = processar_diretorio(args.input, args.output, args.sobrescrever)

    if stats["sucesso"] == 0 and stats["pulados"] == 0:
        logger.error("Nenhum PDF foi processado com sucesso!")
        sys.exit(1)


if __name__ == "__main__":
    main()

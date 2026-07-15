import unittest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_pdfs import limpar_texto, detectar_cabecalhos


class TestExtractPDFs(unittest.TestCase):

    def test_limpar_texto_control_characters(self):
        # Remove control characters
        text = "Hello\x00World\x07!"
        expected = "HelloWorld!"
        self.assertEqual(limpar_texto(text), expected)

    def test_limpar_texto_unicode_spaces(self):
        # Normalize unicode spaces (e.g., non-breaking space \u00a0)
        text = "Hello\u00a0World"
        expected = "Hello World"
        self.assertEqual(limpar_texto(text), expected)

    def test_limpar_texto_multiple_spaces(self):
        # Collapse multiple spaces but preserve indentation (except for first line due to overall strip)
        text = "Hello   World  \n    Indented    line"
        expected = "Hello World\n    Indented line"
        self.assertEqual(limpar_texto(text), expected)

    def test_limpar_texto_consecutive_newlines(self):
        # Collapse 3+ empty lines to 2
        text = "Paragraph 1\n\n\n\nParagraph 2"
        expected = "Paragraph 1\n\nParagraph 2"
        self.assertEqual(limpar_texto(text), expected)

    def test_detectar_cabecalhos_uppercase(self):
        # Short uppercase line should become title
        text = "INTRODUÇÃO\nEsta é uma linha comum."
        expected = "\n# INTRODUÇÃO\n\nEsta é uma linha comum."
        self.assertEqual(detectar_cabecalhos(text), expected)

    def test_detectar_cabecalhos_numbered_section(self):
        # Numbered sections
        text = "1. Introdução ao Empuxo\n1.1. Princípio de Arquimedes"
        expected = "\n## 1. Introdução ao Empuxo\n\n\n### 1.1. Princípio de Arquimedes\n"
        self.assertEqual(detectar_cabecalhos(text), expected)

    def test_detectar_cabecalhos_underline(self):
        # Header followed by underline
        text = "Título Principal\n===\nSubtítulo\n---"
        expected = "## Título Principal\n## Subtítulo"
        self.assertEqual(detectar_cabecalhos(text), expected)


if __name__ == "__main__":
    unittest.main()

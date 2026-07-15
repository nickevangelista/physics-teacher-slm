import unittest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from training.prepare_dataset import (
    dividir_em_chunks,
    criar_exemplo_sharegpt,
    tipo_necessario,
    extrair_json_da_resposta,
)


class TestPrepareDataset(unittest.TestCase):

    def test_dividir_em_chunks_ignores_comments(self):
        text = (
            "# Fonte: introducao.pdf\n"
            "# Páginas: 10\n"
            "#============================================================\n"
            "\n"
            "Conteúdo real da aula de física. Este conteúdo deve ser dividido "
            "em chunks adequados para processamento posterior."
        )
        chunks = dividir_em_chunks(text, tamanho=100)
        self.assertTrue(len(chunks) > 0)
        for chunk in chunks:
            self.assertFalse(chunk.startswith("#"))

    def test_dividir_em_chunks_split_by_paragraph(self):
        text = (
            "Este é o primeiro parágrafo de teste. Ele deve ser longo o suficiente para não ser "
            "filtrado pela validação de tamanho mínimo que é de cinquenta caracteres.\n\n"
            "Este é o segundo parágrafo de teste. Ele também é bastante longo para garantir que "
            "cada parte gerada atinja o tamanho mínimo exigido pelo script."
        )
        chunks = dividir_em_chunks(text, tamanho=200, sobreposicao=10)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].startswith("Este é o primeiro"))
        self.assertTrue(chunks[1].startswith("Este é o segundo") or "segundo parágrafo" in chunks[1])

    def test_criar_exemplo_sharegpt(self):
        system = "Você é um professor."
        q = "O que é entropia?"
        a = "Entropia é a medida de desordem de um sistema."
        ex = criar_exemplo_sharegpt(q, a, system_prompt=system)
        
        self.assertIn("conversations", ex)
        convs = ex["conversations"]
        self.assertEqual(len(convs), 3)
        self.assertEqual(convs[0]["role"], "system")
        self.assertEqual(convs[0]["content"], system)
        self.assertEqual(convs[1]["role"], "user")
        self.assertEqual(convs[1]["content"], q)
        self.assertEqual(convs[2]["role"], "assistant")
        self.assertEqual(convs[2]["content"], a)

    def test_tipo_necessario_initial(self):
        progresso = {
            "chunks_processados": [],
            "contagem_tipos": {"conceito": 0, "questao": 0, "problema": 0, "definicao": 0},
            "total_exemplos": 0,
        }
        # First type recommended should be conceito
        self.assertEqual(tipo_necessario(progresso), "conceito")

    def test_tipo_necessario_distribution(self):
        # target: conceito (40%), questao (30%), problema (20%), definicao (10%)
        # total_exemplos = 10, contagem: conceito=5 (50%), questao=2 (20%), problema=2 (20%), definicao=1 (10%)
        # deficit:
        # conceito: 0.40 - 0.50 = -0.10
        # questao: 0.30 - 0.20 = +0.10  <-- highest deficit
        # problema: 0.20 - 0.20 = 0.0
        # definicao: 0.10 - 0.10 = 0.0
        progresso = {
            "chunks_processados": [],
            "contagem_tipos": {"conceito": 5, "questao": 2, "problema": 2, "definicao": 1},
            "total_exemplos": 10,
        }
        self.assertEqual(tipo_necessario(progresso), "questao")

    def test_extrair_json_da_resposta_clean(self):
        resp = '{"pergunta": "O que é calor?", "resposta": "Calor é energia."}'
        res = extrair_json_da_resposta(resp)
        self.assertIsNotNone(res)
        self.assertEqual(res[0]["pergunta"], "O que é calor?")

    def test_extrair_json_da_resposta_markdown(self):
        resp = '```json\n{"pergunta": "O que é calor?", "resposta": "Calor é energia."}\n```'
        res = extrair_json_da_resposta(resp)
        self.assertIsNotNone(res)
        self.assertEqual(res[0]["pergunta"], "O que é calor?")

    def test_extrair_json_da_resposta_noisy(self):
        resp = 'Aqui está:\n{"pergunta": "O que é calor?", "resposta": "Calor é energia."}\nEspero que ajude.'
        res = extrair_json_da_resposta(resp)
        self.assertIsNotNone(res)
        self.assertEqual(res[0]["pergunta"], "O que é calor?")


if __name__ == "__main__":
    unittest.main()

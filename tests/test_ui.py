import unittest
from unittest.mock import patch, MagicMock
import sys
import json
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import gradio as gr
from app.chat_ui import (
    check_ollama_available,
    list_available_models,
    get_default_base_model,
    get_default_tuned_model,
    chat_respond_side_by_side,
    build_ui,
)


class TestGradioUI(unittest.TestCase):

    @patch("app.chat_ui.requests.get")
    def test_check_ollama_available_online(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        self.assertTrue(check_ollama_available())

    @patch("app.chat_ui.requests.get")
    def test_check_ollama_available_offline(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError()

        self.assertFalse(check_ollama_available())

    @patch("app.chat_ui.requests.get")
    def test_list_available_models(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen2.5:3b"},
                {"name": "physics-teacher:latest"}
            ]
        }
        mock_get.return_value = mock_resp

        models = list_available_models()
        self.assertIn("qwen2.5:3b", models)
        self.assertIn("physics-teacher:latest", models)

    def test_get_default_base_model(self):
        available = ["physics-teacher:latest", "qwen2.5:3b", "other-model"]
        base = get_default_base_model(available)
        self.assertEqual(base, "qwen2.5:3b")

        base_fallback = get_default_base_model([])
        self.assertEqual(base_fallback, "qwen2.5:3b")

    def test_get_default_tuned_model(self):
        available = ["physics-teacher:latest", "qwen2.5:3b", "other-model"]
        tuned = get_default_tuned_model(available)
        self.assertEqual(tuned, "physics-teacher:latest")

        tuned_fallback = get_default_tuned_model([])
        self.assertEqual(tuned_fallback, "qwen2.5:3b")

    @patch("app.chat_ui.check_ollama_available")
    def test_chat_respond_side_by_side_no_ollama(self, mock_check):
        mock_check.return_value = False

        history_base = []
        history_tuned = []

        generator = chat_respond_side_by_side(
            message="O que é o empuxo?",
            history_base=history_base,
            history_tuned=history_tuned,
            model_base="qwen2.5:3b",
            model_tuned="physics-teacher",
            use_rag=True,
            temperature=0.7,
            top_k=40,
        )

        results = list(generator)
        self.assertGreater(len(results), 0)
        last_base, last_tuned, context = results[-1]

        self.assertEqual(last_base[0]["content"], "O que é o empuxo?")
        self.assertIn("Ollama não está rodando", last_base[1]["content"])
        self.assertEqual(last_tuned[0]["content"], "O que é o empuxo?")
        self.assertIn("Ollama não está rodando", last_tuned[1]["content"])
        self.assertEqual(context, "")

    @patch("app.chat_ui.check_ollama_available")
    @patch("app.chat_ui.requests.post")
    def test_chat_respond_side_by_side_streaming_success_no_rag(self, mock_post, mock_check):
        mock_check.return_value = True

        # Mock Ollama API response streaming lines
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.__enter__.return_value = mock_resp
        
        # We need two responses, one for base model, one for tuned model.
        # Since requests.post is called twice, we can return iter_lines yielding mock JSON chunks.
        def mock_iter_lines(decode_unicode=True):
            yield json.dumps({"message": {"content": "Olá"}, "done": False})
            yield json.dumps({"message": {"content": " aluno"}, "done": True})

        mock_resp.iter_lines = mock_iter_lines
        mock_post.return_value = mock_resp

        history_base = []
        history_tuned = []

        generator = chat_respond_side_by_side(
            message="O que é gravidade?",
            history_base=history_base,
            history_tuned=history_tuned,
            model_base="qwen2.5:3b",
            model_tuned="physics-teacher",
            use_rag=False,
            temperature=0.7,
            top_k=40,
        )

        results = list(generator)
        self.assertGreater(len(results), 0)
        last_base, last_tuned, context = results[-1]

        self.assertEqual(last_base[0]["content"], "O que é gravidade?")
        self.assertEqual(last_base[1]["content"], "Olá aluno")
        self.assertEqual(last_tuned[0]["content"], "O que é gravidade?")
        self.assertEqual(last_tuned[1]["content"], "Olá aluno")
        self.assertEqual(context, "_RAG está desativado._")

    @patch("app.chat_ui.check_ollama_available")
    @patch("app.chat_ui.requests.post")
    @patch("app.chat_ui.rag_engine")
    def test_chat_respond_side_by_side_streaming_success_with_rag(self, mock_rag_engine, mock_post, mock_check):
        mock_check.return_value = True

        # Mock RAG response
        mock_node = MagicMock()
        mock_node.score = 0.95
        mock_node.get_text.return_value = "O empuxo é igual ao peso do fluido deslocado."
        
        mock_response = MagicMock()
        mock_response.source_nodes = [mock_node]
        mock_rag_engine.query.return_value = mock_response

        # Mock Ollama API response streaming lines
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.__enter__.return_value = mock_resp
        
        def mock_iter_lines(decode_unicode=True):
            yield json.dumps({"message": {"content": "Conforme o empuxo..."}, "done": True})

        mock_resp.iter_lines = mock_iter_lines
        mock_post.return_value = mock_resp

        history_base = []
        history_tuned = []

        generator = chat_respond_side_by_side(
            message="Como funciona o empuxo?",
            history_base=history_base,
            history_tuned=history_tuned,
            model_base="qwen2.5:3b",
            model_tuned="physics-teacher",
            use_rag=True,
            temperature=0.7,
            top_k=40,
        )

        results = list(generator)
        self.assertGreater(len(results), 0)
        last_base, last_tuned, context = results[-1]

        self.assertEqual(last_base[0]["content"], "Como funciona o empuxo?")
        self.assertEqual(last_tuned[0]["content"], "Como funciona o empuxo?")
        self.assertEqual(last_tuned[1]["content"], "Conforme o empuxo...")
        self.assertIn("O empuxo é igual ao peso do fluido deslocado.", context)

    @patch("app.chat_ui.check_ollama_available")
    @patch("app.chat_ui.list_available_models")
    def test_build_ui(self, mock_list, mock_check):
        mock_check.return_value = True
        mock_list.return_value = ["qwen2.5:3b", "physics-teacher:latest"]

        app = build_ui()
        self.assertIsInstance(app, gr.Blocks)
        
        # Verify app config
        self.assertEqual(app.title, "🧲 Professor de Física IA")


if __name__ == "__main__":
    unittest.main()

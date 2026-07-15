import unittest
import sys
import shutil
import tempfile
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.build_index import construir_indice, verificar_ollama
from rag.query_engine import criar_query_engine, consultar
import chromadb


class TestRAGPipeline(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for docs and DB
        self.test_dir = Path(tempfile.mkdtemp())
        self.docs_dir = self.test_dir / "docs"
        self.db_dir = self.test_dir / "chroma_db"
        self.docs_dir.mkdir()

        # Write dummy physics documents for indexing
        self.doc1_path = self.docs_dir / "termadinamica.txt"
        with open(self.doc1_path, "w", encoding="utf-8") as f:
            f.write(
                "O princípio da conservação da energia é a primeira lei da termodinâmica. "
                "A energia de um sistema isolado permanece constante, podendo apenas ser transformada de uma forma em outra. "
                "Calor e trabalho são formas de transferência de energia."
            )

        self.doc2_path = self.docs_dir / "mecanica.txt"
        with open(self.doc2_path, "w", encoding="utf-8") as f:
            f.write(
                "O empuxo é uma força vertical para cima exercida por um fluido sobre um corpo nele submerso. "
                "De acordo com o princípio de Arquimedes, o empuxo é igual ao peso do fluido deslocado pelo corpo. "
                "A fórmula matemática é E = densidade * volume_submerso * gravidade."
            )

    def tearDown(self):
        # Clean up the temporary directories
        shutil.rmtree(self.test_dir)

    def test_verificar_ollama(self):
        # Verify Ollama connectivity
        is_running = verificar_ollama()
        self.assertTrue(is_running, "Ollama service should be running for integration tests.")

    def test_build_index_integration(self):
        # Skip if Ollama is not running
        if not verificar_ollama():
            self.skipTest("Ollama is not running")

        # Build index in the temporary db directory
        index = construir_indice(docs_dir=self.docs_dir, db_dir=self.db_dir)
        self.assertIsNotNone(index, "Index build should return a VectorStoreIndex object.")

        # Check ChromaDB persistence
        self.assertTrue(self.db_dir.exists(), "ChromaDB directory should be created.")
        client = chromadb.PersistentClient(path=str(self.db_dir))
        collection = client.get_collection("physics_teacher")
        
        # Verify that we have chunks stored in the database
        count = collection.count()
        self.assertGreater(count, 0, "ChromaDB collection should have indexed chunks.")
        
        # Verify documents metadata exists
        documents = collection.get()
        self.assertIn("metadatas", documents)
        filenames = [meta.get("file_name") for meta in documents["metadatas"] if meta]
        self.assertTrue(any("mecanica.txt" in fn for fn in filenames if fn), "mecanica.txt should be indexed.")
        self.assertTrue(any("termadinamica.txt" in fn for fn in filenames if fn), "termadinamica.txt should be indexed.")

    def test_query_engine_integration(self):
        # Skip if Ollama is not running
        if not verificar_ollama():
            self.skipTest("Ollama is not running")

        # Build index first
        construir_indice(docs_dir=self.docs_dir, db_dir=self.db_dir)

        # Create query engine
        query_engine = criar_query_engine(db_dir=self.db_dir, model_name="qwen2.5:3b", similarity_top_k=2)
        self.assertIsNotNone(query_engine, "Query engine should be successfully created.")

        # Run query and verify answer and sources
        query = "O que é o empuxo e qual a sua fórmula?"
        result = consultar(query_engine, query)
        
        self.assertIn("resposta", result, "Result must contain 'resposta'.")
        self.assertIn("fontes", result, "Result must contain 'fontes'.")
        
        # Check that the response is generated
        self.assertTrue(isinstance(result["resposta"], str))
        self.assertTrue(len(result["resposta"]) > 0)
        
        # Verify sources contains 'mecanica.txt'
        self.assertGreater(len(result["fontes"]), 0, "Sources should not be empty.")
        source_filenames = [src["arquivo"] for src in result["fontes"]]
        self.assertTrue(any("mecanica.txt" in fn for fn in source_filenames), "mecanica.txt should be listed in sources.")


if __name__ == "__main__":
    unittest.main()

"""Confere a integridade estrutural do notebook antes do commit."""

import json
import unittest
from pathlib import Path


NB = Path(__file__).resolve().parents[1] / "Citizen_Assist_AI_Colab_Ollama.ipynb"


class TestNotebook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads(NB.read_text(encoding="utf-8"))

    def test_todas_as_celulas_python_compilam(self):
        for indice, celula in enumerate(self.notebook["cells"]):
            if celula["cell_type"] != "code":
                continue
            fonte = "".join(celula.get("source", []))
            if fonte.lstrip().startswith("%pip "):
                continue  # comando mágico do IPython
            with self.subTest(celula=indice):
                compile(fonte, f"celula-{indice}", "exec")

    def test_notebook_contem_etapas_exigidas(self):
        ids = {c.get("id") for c in self.notebook["cells"]}
        self.assertTrue({"colab-conexao", "colab-antes", "colab-depois",
                         "colab-personas", "colab-relatorio"} <= ids)
        fonte = "\n".join("".join(c.get("source", [])) for c in self.notebook["cells"])
        self.assertIn('parametros["strict_llm"] = True', fonte)
        self.assertIn("ag_v2 = criar_agente_avaliacao('v2')", fonte)
        self.assertIn('userdata.get("OLLAMA_PASSWORD")', fonte)
        self.assertIn("executar_avaliacao_em_lotes", fonte)
        self.assertIn("resultados_execucao", fonte)


if __name__ == "__main__":
    unittest.main()

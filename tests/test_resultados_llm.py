"""Audita a completude e a proveniência dos resultados reais publicados."""

import csv
import unittest
from collections import Counter
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


def ler_csv(nome):
    with (RAIZ / nome).open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


class TestResultadosLLM(unittest.TestCase):
    def test_golden_completo_sem_fallback_mascarado(self):
        for nome, acertos in (("resultados_v1_llm.csv", 3), ("resultados_v2_llm.csv", 20)):
            with self.subTest(nome=nome):
                linhas = ler_csv(nome)
                self.assertEqual(len(linhas), 26)
                self.assertEqual(sorted(int(linha["id"]) for linha in linhas), list(range(1, 27)))
                self.assertEqual(sum(linha["acerto"] == "True" for linha in linhas), acertos)
                self.assertTrue(all(linha["veredito_juiz"] in {"correto", "parcial", "incorreto"}
                                    for linha in linhas))
                self.assertTrue(all(linha["resposta"].strip() for linha in linhas))
                self.assertTrue(all(linha["origem"] in {"llm", "regra", "extrativo"}
                                    for linha in linhas))

    def test_personas_completas(self):
        linhas = ler_csv("resultados_personas_llm.csv")
        self.assertEqual(len(linhas), 15)
        self.assertEqual(sum(linha["fato_esperado_encontrado"] == "True" for linha in linhas), 14)
        self.assertEqual(sorted(Counter(linha["persona_ficticia"] for linha in linhas).values()),
                         [3, 3, 3, 3, 3])

    def test_relatorio_coerente_e_sem_artefatos_offline(self):
        relatorio = (RAIZ / "docs" / "RELATORIO.md").read_text(encoding="utf-8")
        for trecho in ("3/26", "20/26", "14/15"):
            self.assertIn(trecho, relatorio)
        for nome in ("resultados_antes.csv", "resultados_depois.csv",
                     "resultados_simulacao_personas.csv"):
            self.assertFalse((RAIZ / "testes_usuarios" / nome).exists(), nome)


if __name__ == "__main__":
    unittest.main()

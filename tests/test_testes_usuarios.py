"""Valida os registros anonimizados informados pelos cinco participantes."""

import csv
import statistics
import unittest
from pathlib import Path


CSV = Path(__file__).resolve().parents[1] / "testes_usuarios" / "testes_usuarios.csv"


class TestTestesUsuarios(unittest.TestCase):
    def test_cinco_participantes_e_medidas_validas(self):
        with CSV.open(encoding="utf-8", newline="") as arquivo:
            linhas = list(csv.DictReader(arquivo))
        self.assertEqual([linha["participante"] for linha in linhas],
                         ["P1", "P2", "P3", "P4", "P5"])

        tempos = [int(linha[f"tarefa{i}_seg"]) for linha in linhas for i in range(1, 4)]
        notas = [int(linha[f"q{i}"]) for linha in linhas for i in range(1, 6)]
        self.assertEqual(len(tempos), 15)
        self.assertEqual(len(notas), 25)
        self.assertTrue(all(tempo > 0 for tempo in tempos))
        self.assertTrue(all(1 <= nota <= 5 for nota in notas))
        self.assertAlmostEqual(statistics.mean(tempos), 41.3333333333, places=5)
        self.assertAlmostEqual(statistics.mean(notas), 4.8)


if __name__ == "__main__":
    unittest.main()

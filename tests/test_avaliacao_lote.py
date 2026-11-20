"""Testa checkpoints e separação das chamadas a Qwen e Llama sem rede."""

import tempfile
import unittest

from citizen_assist.avaliacao_lote import executar_avaliacao_em_lotes
from citizen_assist.golden import CASOS


class FalsoAgente:
    modelo = "modelo-teste"

    def __init__(self, falhar_na_chamada=None):
        self.chamadas = 0
        self.falhar_na_chamada = falhar_na_chamada

    def complete(self, system, user):
        self.chamadas += 1
        if self.chamadas == self.falhar_na_chamada:
            raise ConnectionError("falha intencional de teste")
        return "A segunda via do RG custa R$ 38,00 pelo portal [FC-01]."


class FalsoJuiz:
    modelo = "juiz-teste"

    def __init__(self):
        self.chamadas = 0

    def complete(self, system, user):
        self.chamadas += 1
        return '{"veredito":"correto","justificativa":"Conteúdo conferido."}'


class TestarAvaliacaoEmLotes(unittest.TestCase):
    def test_retomada_nao_repete_chamadas_concluidas(self):
        casos = CASOS[:2]
        with tempfile.TemporaryDirectory() as pasta:
            modelo = FalsoAgente()
            juiz = FalsoJuiz()
            um = executar_avaliacao_em_lotes(
                "v1", casos, modelo, juiz, engine="local", pasta_resultados=pasta
            )
            self.assertEqual(len(um), 2)
            self.assertEqual(modelo.chamadas, 2)
            self.assertEqual(juiz.chamadas, 2)

            dois = executar_avaliacao_em_lotes(
                "v1", casos, modelo, juiz, engine="local", pasta_resultados=pasta
            )
            self.assertEqual(len(dois), 2)
            self.assertEqual(modelo.chamadas, 2)
            self.assertEqual(juiz.chamadas, 2)

    def test_falha_na_segunda_geracao_preserva_primeiro_checkpoint(self):
        casos = CASOS[:2]
        with tempfile.TemporaryDirectory() as pasta:
            juiz = FalsoJuiz()
            with self.assertRaises(RuntimeError):
                executar_avaliacao_em_lotes(
                    "v1", casos, FalsoAgente(falhar_na_chamada=2), juiz,
                    engine="local", pasta_resultados=pasta,
                )
            self.assertEqual(juiz.chamadas, 0)
            retomada = FalsoAgente()
            resultado = executar_avaliacao_em_lotes(
                "v1", casos, retomada, juiz, engine="local", pasta_resultados=pasta
            )
            self.assertEqual(len(resultado), 2)
            self.assertEqual(retomada.chamadas, 1)
            self.assertEqual(juiz.chamadas, 2)


if __name__ == "__main__":
    unittest.main()

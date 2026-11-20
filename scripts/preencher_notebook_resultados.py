"""Insere um resumo verificável dos CSVs LLM no notebook de avaliação.

O resumo é regenerado a partir dos dados versionados, sem fabricar outputs de
células executadas no Colab. Idempotente: substitui as células de resumo.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
CAMINHO = RAIZ / "Citizen_Assist_AI_Colab_Ollama.ipynb"


def carregar(nome):
    with (RAIZ / nome).open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


antes = carregar("resultados_v1_llm.csv")
depois = carregar("resultados_v2_llm.csv")
personas = carregar("resultados_personas_llm.csv")
if len(antes) != 26 or len(depois) != 26 or len(personas) != 15:
    raise RuntimeError("Resultados LLM incompletos: esperado 26 + 26 + 15 registros")

a1 = sum(linha["acerto"] == "True" for linha in antes)
a2 = sum(linha["acerto"] == "True" for linha in depois)
ap = sum(linha["fato_esperado_encontrado"] == "True" for linha in personas)

texto = f"""## Resultados completos medidos com Ollama (20/11/2026)

Os resultados abaixo foram gerados na execução real de `qwen2.5:7b` (agente)
e `llama3.1:8b` (juiz). A decisão de acerto exige aprovação pelo juiz e pelas
verificações por regra.

| Métrica | Resultado |
|---|---:|
| Golden Dataset — antes, v1 | **{a1}/26 ({a1 / 26:.1%})** |
| Golden Dataset — depois, v2 | **{a2}/26 ({a2 / 26:.1%})** |
| Melhoria absoluta | **+{a2 - a1} acertos** |
| Cinco personas fictícias (15 tarefas) | **{ap}/15 ({ap / 15:.1%})** |

Resultados detalhados no repositório: [`resultados_v1_llm.csv`](resultados_v1_llm.csv),
[`resultados_v2_llm.csv`](resultados_v2_llm.csv),
[`resultados_personas_llm.csv`](resultados_personas_llm.csv) e
[`docs/RELATORIO.md`](docs/RELATORIO.md).

**Importante:** as cinco personas são simulações, não participantes humanos.
Os arquivos offline antigos foram removidos. Este resumo registra uma execução
já concluída; reexecutar o modelo pode produzir resultados diferentes.
"""

codigo = """from pathlib import Path
import pandas as pd

arquivos_publicados = {
    'Antes (v1)': 'resultados_v1_llm.csv',
    'Depois (v2)': 'resultados_v2_llm.csv',
    'Personas (5 × 3)': 'resultados_personas_llm.csv',
}
for descricao, arquivo in arquivos_publicados.items():
    caminho = Path(arquivo)
    if caminho.is_file():
        tabela = pd.read_csv(caminho)
        campo = 'acerto' if 'acerto' in tabela else 'fato_esperado_encontrado'
        print(f'{descricao}: {int(tabela[campo].sum())}/{len(tabela)}')
    else:
        print(f'{descricao}: CSV ainda não encontrado ({arquivo})')
"""

caderno = json.loads(CAMINHO.read_text(encoding="utf-8"))
caderno["cells"] = [c for c in caderno["cells"] if c.get("id") not in {
    "resultados-llm-publicados", "consultar-resultados-llm",
}]

def fonte(s):
    return s.splitlines(keepends=True)


caderno["cells"].insert(2, {
    "cell_type": "markdown", "id": "resultados-llm-publicados",
    "metadata": {}, "source": fonte(texto),
})
pos = next(i for i, c in enumerate(caderno["cells"])
           if c.get("id") == "colab-importacoes")
caderno["cells"].insert(pos + 1, {
    "cell_type": "code", "id": "consultar-resultados-llm", "metadata": {},
    "execution_count": None, "outputs": [], "source": fonte(codigo),
})
CAMINHO.write_text(json.dumps(caderno, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"Resumo atualizado: v1 {a1}/26, v2 {a2}/26, personas {ap}/15")

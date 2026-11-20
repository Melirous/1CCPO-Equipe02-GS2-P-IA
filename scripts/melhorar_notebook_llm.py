"""Prepara a versão Colab com avaliação em lotes e retomada por checkpoint."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARQUIVO = ROOT / "Citizen_Assist_AI_Colab_Ollama.ipynb"
notebook = json.loads(ARQUIVO.read_text(encoding="utf-8"))


def trocar(celula, fonte):
    celula["source"] = fonte.strip("\n").splitlines(keepends=True)
    if celula["cell_type"] == "code":
        celula["execution_count"] = None
        celula["outputs"] = []


for celula in notebook["cells"]:
    identificador = celula.get("id")
    if identificador == "colab-repositorio":
        trocar(celula, '''
from pathlib import Path
import os
import subprocess
import sys

REPOSITORIO = "https://github.com/Melirous/1CCPO-Equipe02-GS2-P-IA.git"
PROJETO = Path.cwd() if (Path.cwd() / "citizen_assist" / "agente.py").is_file() else Path("/content/citizen_assist_projeto")

if not (PROJETO / "citizen_assist" / "agente.py").is_file():
    if PROJETO.exists():
        raise RuntimeError(f"Pasta {PROJETO} já existe sem projeto válido")
    subprocess.run(["git", "clone", "--depth", "1", REPOSITORIO, str(PROJETO)], check=True)
elif (PROJETO / ".git").is_dir():
    subprocess.run(["git", "-C", str(PROJETO), "pull", "--ff-only"], check=True)

if not (PROJETO / "citizen_assist" / "avaliacao_lote.py").is_file():
    raise FileNotFoundError("Módulo de avaliação ausente: atualize o clone do GitHub")
if not (PROJETO / "fichas" / "FC-01_rg_segunda_via.md").is_file():
    raise FileNotFoundError("Fichas de referência não encontradas")

os.chdir(PROJETO)
if str(PROJETO) not in sys.path:
    sys.path.insert(0, str(PROJETO))
print("Projeto carregado de:", PROJETO)
''')
    elif identificador == "colab-conexao":
        trocar(celula, '''
from google.colab import userdata
import requests
import time
from requests.auth import HTTPBasicAuth

OLLAMA_URL = str(userdata.get("OLLAMA_URL")).rstrip("/")
OLLAMA_USER = str(userdata.get("OLLAMA_USER"))
OLLAMA_PASSWORD = str(userdata.get("OLLAMA_PASSWORD"))
if not OLLAMA_URL.startswith("https://"):
    raise ValueError("OLLAMA_URL deve começar com https://")
if not all((OLLAMA_URL, OLLAMA_USER, OLLAMA_PASSWORD)):
    raise ValueError("Configure os Secrets OLLAMA_URL, OLLAMA_USER e OLLAMA_PASSWORD")

SESSAO = requests.Session()
SESSAO.auth = HTTPBasicAuth(OLLAMA_USER, OLLAMA_PASSWORD)
SESSAO.headers.update({"ngrok-skip-browser-warning": "true"})

checagem = SESSAO.get(f"{OLLAMA_URL}/api/tags", timeout=(20, 45))
checagem.raise_for_status()
disponiveis = {m["name"] for m in checagem.json().get("models", [])}
obrigatorios = {"qwen2.5:7b", "llama3.1:8b"}
if not obrigatorios <= disponiveis:
    raise RuntimeError(f"Modelos não encontrados: {sorted(obrigatorios - disponiveis)}")
print("Conexão HTTP:", checagem.status_code, "| modelos:", ", ".join(sorted(obrigatorios)))


class OllamaNgrok:
    """Cliente /api/chat por HTTPS com credenciais apenas na memória."""

    def __init__(self, modelo, max_tokens, formato_json=False, tempo_limite=300):
        self.modelo = modelo
        self.max_tokens = max_tokens
        self.formato_json = formato_json
        self.tempo_limite = tempo_limite
        self.sucessos = 0
        self.falhas = []

    def complete(self, system, user):
        payload = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0, "num_predict": self.max_tokens},
        }
        if self.formato_json:
            payload["format"] = "json"
        for tentativa in range(2):
            try:
                resp = SESSAO.post(
                    f"{OLLAMA_URL}/api/chat", json=payload,
                    timeout=(20, self.tempo_limite),
                )
                # Erros de credencial (401/403) não melhoram com novas tentativas.
                resp.raise_for_status()
                texto = str(resp.json()["message"]["content"]).strip()
                if not texto:
                    raise ValueError("O modelo retornou resposta vazia")
                self.sucessos += 1
                return texto
            except (requests.RequestException, ValueError, KeyError) as erro:
                if tentativa == 0 and isinstance(erro, requests.HTTPError) \\
                    and erro.response is not None and erro.response.status_code in (401, 403):
                    self.falhas.append(type(erro).__name__)
                    raise RuntimeError("A autenticação do ngrok foi recusada (401/403)") from None
                if tentativa == 1:
                    self.falhas.append(type(erro).__name__)
                    raise RuntimeError(
                        f"Ollama {self.modelo} indisponível ({type(erro).__name__}). "
                        "Mantenha o ngrok aberto e execute novamente: o checkpoint será retomado."
                    ) from None
                time.sleep(4)


MODELO_AGENTE = "qwen2.5:7b"
MODELO_JUIZ = "llama3.1:8b"
llm_agente = OllamaNgrok(MODELO_AGENTE, max_tokens=450)
llm_juiz = OllamaNgrok(MODELO_JUIZ, max_tokens=180, formato_json=True)

# Um teste por modelo confirma inferência, não precisão.
print("Qwen:", llm_agente.complete("Responda brevemente em português.",
                                  "Responda exatamente: Teste concluído.")[:120])
print("Llama:", llm_juiz.complete("Responda somente JSON.",
                                  'Retorne {"status":"ok"} em JSON.')[:120])
''')
    elif identificador == "colab-antes":
        trocar(celula, '''
from citizen_assist.avaliacao_lote import executar_avaliacao_em_lotes

print("Etapa 1: gerar todas as respostas com Qwen; etapa 2: julgar com Llama.")
print("Ao falhar, reexecute esta célula: as respostas já processadas não serão repetidas.")
antes = executar_avaliacao_em_lotes(
    "v1", CASOS, llm_agente, llm_juiz,
    engine="langgraph", pasta_resultados="resultados_execucao",
)
print(f"Acertos ANTES: {int(antes.acerto.sum())}/{len(antes)}")
display(antes[['id','tipo','veredito_juiz','acerto','faltando','proibidos','sem_citacao','justificativa']])
''')
    elif identificador == "colab-depois":
        trocar(celula, '''
depois = executar_avaliacao_em_lotes(
    "v2", CASOS, llm_agente, llm_juiz,
    engine="langgraph", pasta_resultados="resultados_execucao",
)
print(f"Acertos DEPOIS: {int(depois.acerto.sum())}/{len(depois)}")
display(depois[['id','tipo','veredito_juiz','acerto','faltando','proibidos','sem_citacao','verificacao','justificativa']])
''')
    elif identificador == "colab-participantes":
        trocar(celula, '''
from pathlib import Path

planilha = Path('testes_usuarios/testes_usuarios.csv')
if not planilha.is_file():
    print('Não há CSV de participantes reais. Tempos e notas permanecem não medidos.')
else:
    t = pd.read_csv(planilha).dropna(how='all', subset=['tarefa1_seg'])
    if t.empty:
        print('CSV de participantes reais ainda não preenchido.')
    else:
        tempos = t[['tarefa1_seg','tarefa2_seg','tarefa3_seg']]
        notas = t[['q1','q2','q3','q4','q5']]
        print('Tempo médio humano (s):', round(tempos.stack().mean(), 1))
        print('Facilidade média (1-5):', round(notas.stack().mean(), 2))
print('Acerto das orientações (Golden Dataset v2):', f'{depois.acerto.mean():.1%}')
''')
    elif identificador == "colab-personas":
        trocar(celula, '''
import hashlib
import json
import re
from pathlib import Path
from time import perf_counter
from citizen_assist.fichas import norm

PERSONAS = {
  'P-A (jovem, escreve curto)': ['docs 2 via rg', 'titulo eleitor paga?', 'cnh 55 anos vale quanto'],
  'P-B (linguagem formal)': [
      'Bom dia. Quais documentos devo levar para tirar a segunda via da minha identidade?',
      'Preciso pagar alguma taxa para o título de eleitor?',
      'Tenho 55 anos. Por quanto tempo será válida a minha carteira de motorista renovada?'],
  'P-C (apressado, com erros)': [
      'o q precisa pra segunda via do rg', 'titulo de eleitor cobra taxa',
      'renovei a cnh aos 55 qnto tempo dura a validade'],
  'P-D (usa menu/números)': ['1', '3', '6'],
  'P-E (pergunta ampla)': [
      'Perdi minha identidade, o que eu faço?', 'Votar custa alguma coisa?',
      'Até quando vale a habilitação depois de renovar, se eu tenho 55 anos?'],
}
TAREFAS = [
  ('RG - documentos', r'certidao.*(90 dias|comprovante)|comprovante.*90 dias'),
  ('Título - gratuidade', r'gratuit'),
  ('CNH - validade aos 55', r'5 anos'),
]

ag_v2 = criar_agente_avaliacao('v2')
perguntas_personas = [(perfil, tarefa, padrao, pergunta)
                    for perfil, perguntas in PERSONAS.items()
                    for (tarefa, padrao), pergunta in zip(TAREFAS, perguntas)]
identificador = hashlib.sha256(json.dumps({
    'tarefas': perguntas_personas, 'modelo': MODELO_AGENTE,
}, ensure_ascii=False).encode('utf-8')).hexdigest()
checkpoint = Path('resultados_execucao/personas.json')
checkpoint.parent.mkdir(parents=True, exist_ok=True)
if checkpoint.exists():
    dados = json.loads(checkpoint.read_text(encoding='utf-8'))
    if dados.get('assinatura') != identificador:
        raise RuntimeError('As perguntas mudaram; renomeie o checkpoint de personas antigo.')
    linhas_personas = dados['resultados']
else:
    linhas_personas = []

for perfil, tarefa, padrao, pergunta in perguntas_personas[len(linhas_personas):]:
    inicio = perf_counter()
    estado = ag_v2.perguntar(pergunta)
    latencia = round(perf_counter() - inicio, 2)
    resposta = estado['final']
    achou = bool(re.search(padrao, norm(resposta), re.S))
    linhas_personas.append({
        'persona_ficticia': perfil, 'tarefa': tarefa, 'pergunta': pergunta,
        'fato_esperado_encontrado': achou, 'latencia_pipeline_seg': latencia,
        'rota': estado.get('rota'), 'origem': estado.get('origem'),
        'fontes': ', '.join(estado.get('fontes', [])),
        'resposta': mascarar_pii(resposta)[0],
    })
    checkpoint.write_text(json.dumps({
        'assinatura': identificador, 'resultados': linhas_personas,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"{perfil.split(' ')[0]} / {tarefa}: {'OK' if achou else 'FALHOU'} ({latencia}s)", flush=True)

resultado_personas = pd.DataFrame(linhas_personas)
resultado_personas.to_csv('resultados_personas_llm.csv', index=False)
print('Fatos encontrados:', int(resultado_personas.fato_esperado_encontrado.sum()),
      '/', len(resultado_personas))
display(resultado_personas.groupby('persona_ficticia')['fato_esperado_encontrado'].agg(['sum','count']))
''')
    elif identificador == "colab-exportar":
        trocar(celula, '''
# Salvar apenas os resultados finais com respostas mascaradas.
antes.to_csv('resultados_v1_llm.csv', index=False)
depois.to_csv('resultados_v2_llm.csv', index=False)
print('CSV v1 e v2 exportados com LLM Judge e verificações por regra.')
print('Chamadas concluídas — Qwen:', llm_agente.sucessos, '| Llama:', llm_juiz.sucessos)
''')
    elif identificador == "colab-instrucoes":
        fonte = "".join(celula.get("source", []))
        fonte = fonte.replace('`https://manger-truth-credible.ngrok-free.dev`',
                              'HTTPS do seu túnel ngrok')
        if "**Retomada após falhas:**" not in fonte:
            fonte += ("\n**Retomada após falhas:** a avaliação separa a geração de todas as "
                      "respostas com Qwen do julgamento com Llama; checkpoints ficam na "
                      "pasta `resultados_execucao/`. Reexecute a célula que falhou para "
                      "continuar. Se desconectar todo o Colab, baixe os checkpoints "
                      "antes de encerrar a sessão.\n")
        trocar(celula, fonte)


# Preserve o botão 'Open in Colab' que foi inserido pelo usuário no GitHub.
badge = ('<a href="https://colab.research.google.com/github/'
         'Melirous/1CCPO-Equipe02-GS2-P-IA/blob/main/'
         'Citizen_Assist_AI_Colab_Ollama.ipynb" target="_parent">'
         '<img src="https://colab.research.google.com/assets/colab-badge.svg"'
         ' alt="Open In Colab"/></a>')
if not any('Open In Colab' in ''.join(c.get('source', [])) for c in notebook['cells']):
    notebook['cells'].insert(0, {
        'cell_type': 'markdown', 'metadata': {'id': 'view-in-github', 'colab_type': 'text'},
        'source': [badge], 'id': 'view-in-github',
    })

# Células de saída antigas registravam timeouts; não devem continuar no notebook.
for celula in notebook['cells']:
    if celula['cell_type'] == 'code':
        celula['outputs'] = []
        celula['execution_count'] = None

ARQUIVO.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Notebook atualizado com lotes e checkpoints:', ARQUIVO)

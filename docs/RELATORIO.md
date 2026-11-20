# Citizen Assist AI — Relatório

**Integrantes:**
- João Victor Canello Ferian — RM 573295
- João Pedro Costenari — RM 572260
- Gustavo Melo dos Santos — RM 573562

## 1. Justificativas
**Framework (LangGraph).** O fluxo tem desvios claros (vazio, injeção, dados pessoais, fora do escopo, resposta do LLM) e o LangGraph representa isso como grafo com arestas condicionais, o que deixa o caminho de cada mensagem auditável e gera o diagrama da arquitetura. LangChain puro seria uma cadeia linear, sem desvios; CrewAI é feito para vários agentes conversando, o que não precisamos.

**Um agente só.** O problema é pequeno: uma fonte (7 fichas curtas) e uma tarefa (responder com base nelas). Vários agentes aumentariam custo, latência e chance de erro sem ganho. O "agente" é um grafo com 6 nós: `analisar`, `recuperar`, `resposta_fixa`, `gerar`, `verificar`, `finalizar`.

**Modelo (Ollama, `qwen2.5:7b`; juiz `llama3.1:8b`).** A inferência roda no computador do usuário. Quando o notebook é executado no Colab, mensagens de teste passam pelo túnel HTTPS autenticado do ngrok antes de chegar ao Ollama: portanto, existe tráfego de rede. O juiz usa outro modelo para não avaliar a si mesmo. Temperatura 0 reduz a variação, mas não garante resultados idênticos em todas as máquinas.

**Onde entra IA e onde bastam regras.**
| Tarefa | Como | Por quê |
|---|---|---|
| Entrada vazia, longa, sem sentido | código | regra simples e determinística |
| Dados pessoais | regex + resposta fixa | não pode falhar nem chegar ao modelo |
| Prompt injection | regex + resposta fixa | recusa tem que ser sempre igual |
| Escolher a ficha | pontuação por palavras | fichas curtas e vocabulário previsível |
| Redigir a resposta em linguagem simples | **IA (LLM)** | únicas etapa em que linguagem natural flexível ajuda |
| Conferir valores/prazos, vazamento | código | LLM pode inventar; código confere contra as fichas |
| Fonte, data e aviso | código | garantidos em toda resposta |

**Organização das fichas.** Cada ficha vira objeto com campos nomeados; as escolhidas vão inteiras ao prompt (mais a FC-07). Sem banco vetorial: fichas de ~300 tokens cabem no contexto sem perda.

## 2. Dados pessoais
O assistente nunca pede dados pessoais. CPF, telefone, e-mail, números longos e frases como "vou te passar meu endereço" são detectados antes do LLM v2; a resposta fixa orienta a não informar dados e a usar o portal. Não há histórico persistente de chat nem checkpointer do LangGraph. A avaliação de testes fictícios pode gravar CSVs, com respostas mascaradas para reduzir exposição de dados. Credenciais são fornecidas por Secrets do Colab e nunca incluídas nos artefatos.

## 3. Resultados verificados — modo offline

**Condição de execução:** o Colab do usuário acessou o Ollama remoto com
HTTP 200 e confirmou os modelos. Este ambiente de revisão não conseguiu
alcançar o túnel; por isso executamos separadamente o mecanismo local e
extrativo para validar a lógica. Os números da tabela abaixo **não são
resultados dos LLMs nem da avaliação por LLM-as-a-Judge**.

| Métrica offline (checagens por regra) | Antes (v1) | Depois (v2) |
|---|---:|---:|
| Acertos no Golden Dataset | 21/26 (80,77%) | 26/26 (100%) |
| Reprovações em dados pessoais | 1 (caso 22) | 0 |
| Reprovações em prompt injection | 2 (casos 24 e 25) | 0 |
| Reprovações por falta de citação | 0 | 0 |
| Outras reprovações | 2 (casos 20 e 21) | 0 |

**Análise dos erros offline:** na v1, o caso 20 (fora de escopo) não orientou
adequadamente sobre a limitação; o caso 21 (entrada sem sentido) não ofereceu
ajuda; o caso 22 (CPF na pergunta) não atingiu as exigências de proteção; e os
casos 24 e 25 não recusaram corretamente tentativas de prompt injection.
A v2 acrescenta rotas fixas de segurança, seleção das fichas e verificação.

**Correção adicional:** o modo `strict_llm=True` agora impede que uma falha
de conexão com o Ollama seja convertida silenciosamente em acerto do gerador
extrativo durante a avaliação. O modo de atendimento mantém o fallback para
evitar erro técnico ao cidadão.

### 3.1 Evidência da execução parcial com Qwen + Llama

Os outputs disponíveis no notebook anterior registraram conexão autenticada
**HTTP 200**, os modelos `qwen2.5:7b` e `llama3.1:8b` e um teste de inferência
concluído para cada um. Na avaliação v1, foram julgados somente estes casos:

| Caso | Veredito do Llama | Acerto combinado (juiz + regras) |
|---|---|---|
| 1 | parcial | Não |
| 2 | correto | Não |
| 3 | correto | Sim |
| 4 | incorreto | Não |

**No caso 5 a geração com Ollama falhou**, interrompendo a v1. A execução da
v2 foi interrompida antes de obter resultados. Portanto, **não existe taxa de
acerto real consolidada** para as 26 perguntas nas duas versões; quatro casos
não são uma amostra suficiente para informar a taxa final. Esses registros
foram preservados como evidência textual neste relatório, sem confundi-los
com os 21/26 e 26/26 calculados exclusivamente no modo offline.

O novo `Citizen_Assist_AI_Colab_Ollama.ipynb` separa a geração com Qwen do
julgamento com Llama e salva checkpoints por caso. Após a execução integral,
gerará `docs/RELATORIO_LLM.md` e CSVs medidos pelos dois modelos.

**Conferência manual de cinco respostas reais:** pendente até a execução com LLM.

## 4. Simulação de cinco personas e testes reais

A simulação offline executou cinco personas fictícias (P-A a P-E), com três
perguntas cada, totalizando **15/15 (100%)** respostas com o fato esperado.
As personas representam linguagem curta, formal, com erros, navegação por menu
e perguntas amplas. Esses resultados não medem facilidade de uso humana.

| Indicador | Resultado |
|---|---|
| Simulação offline (5 personas × 3 tarefas) | 15/15 (100%) |
| Acerto das orientações com juiz LLM real | Pendente |
| Tempo médio de usuários reais para achar informação | Não medido |
| Facilidade de uso média (1–5) | Não medida |

Não há CSV preenchido por participantes humanos no repositório; nenhum tempo
ou nota foi inventado. Quando houver pelo menos cinco pessoas externas ao
grupo, criar `testes_usuarios/testes_usuarios.csv` e registrar tempos e notas
sem identificá-las pessoalmente.

## 5. Limitações
- Só responde o que está nas 7 fichas (fictícias); não consulta situação cadastral nem agenda atendimento.
- A busca é por palavras; perguntas com sinônimos raros podem cair em "não encontrei".
- Perguntas que misturam dois assuntos recebem no máximo 2 fichas.
- Um modelo de 7B pode escrever respostas imperfeitas; o nó `verificar` pega valores e prazos inventados, mas não todo erro de interpretação.
- A detecção de injeção é por padrões e pode não pegar ataques novos; a defesa em profundidade é o prompt v2 + verificação.
- Não é canal oficial; todas as respostas trazem esse aviso.
- Acessibilidade: frases curtas, texto simples, uso só com teclado (`app_cli.py`); não há interface gráfica nem leitor de tela dedicado.
- Checkpoints do Colab persistem perguntas e respostas de **testes fictícios**; não utilizar dados pessoais de participantes nessas avaliações.

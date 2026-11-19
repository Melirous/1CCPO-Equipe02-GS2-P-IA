# Citizen Assist AI — Relatório

**Integrantes:**
- João Victor Canello Ferian — RM 573295
- João Pedro Costenari — RM 572260
- Gustavo Melo dos Santos — RM 573562

## 1. Justificativas
**Framework (LangGraph).** O fluxo tem desvios claros (vazio, injeção, dados pessoais, fora do escopo, resposta do LLM) e o LangGraph representa isso como grafo com arestas condicionais, o que deixa o caminho de cada mensagem auditável e gera o diagrama da arquitetura. LangChain puro seria uma cadeia linear, sem desvios; CrewAI é feito para vários agentes conversando, o que não precisamos.

**Um agente só.** O problema é pequeno: uma fonte (7 fichas curtas) e uma tarefa (responder com base nelas). Vários agentes aumentariam custo, latência e chance de erro sem ganho. O "agente" é um grafo com 6 nós: `analisar`, `recuperar`, `resposta_fixa`, `gerar`, `verificar`, `finalizar`.

**Modelo (Ollama, `qwen2.5:7b`; juiz `llama3.1:8b`).** Roda local e grátis, e nenhum texto de usuário sai da máquina (bom para privacidade). O Qwen 2.5 7B segue bem instruções em português. O juiz usa outro modelo para não avaliar a si mesmo. Temperatura 0 nos dois, para resultados repetíveis. *(Se o grupo trocar de modelo, atualizar aqui.)*

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
O assistente nunca pede dados pessoais. CPF, telefone, e-mail, números longos e frases como "vou te passar meu endereço" são detectados antes do LLM; o texto é mascarado e a resposta fixa orienta a não informar dados e a usar o portal. Nada é gravado (sem log, sem histórico, sem checkpointer do LangGraph). O notebook mostra mensagens mascaradas. Testes e golden usam apenas dados fictícios.

## 3. Resultados (preencher após rodar o notebook)
| | Antes (v1) | Depois (v2) |
|---|---|---|
| Acertos no golden (juiz + regras) | _/26 | _/26 |
| Erros de dados pessoais | | |
| Erros de prompt injection | | |
| Erros de citação | | |

**Análise dos erros e melhoria:** _(descrever os casos que falharam no v1, a causa e o que mudou no v2; ver seção 4.3 do notebook.)_

**Conferência manual da amostra:** _(quantas das 5 respostas conferidas concordaram com o juiz.)_

## 4. Testes com usuários (preencher)
≥ 5 pessoas de fora do grupo, 3 tarefas, sem identificação (P1…P5).
| Indicador | Resultado |
|---|---|
| Acerto das orientações (golden) | _% |
| Tempo médio para achar a informação | _ s |
| Facilidade de uso (média 1–5) | _ |

## 5. Limitações
- Só responde o que está nas 7 fichas (fictícias); não consulta situação cadastral nem agenda atendimento.
- A busca é por palavras; perguntas com sinônimos raros podem cair em "não encontrei".
- Perguntas que misturam dois assuntos recebem no máximo 2 fichas.
- Um modelo de 7B pode escrever respostas imperfeitas; o nó `verificar` pega valores e prazos inventados, mas não todo erro de interpretação.
- A detecção de injeção é por padrões e pode não pegar ataques novos; a defesa em profundidade é o prompt v2 + verificação.
- Não é canal oficial; todas as respostas trazem esse aviso.
- Acessibilidade: frases curtas, texto simples, uso só com teclado (`app_cli.py`); não há interface gráfica nem leitor de tela dedicado.

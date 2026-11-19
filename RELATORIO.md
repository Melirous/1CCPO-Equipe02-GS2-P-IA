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

## 3. Resultados — execução offline

**Condição de execução:** o ambiente utilizado não tinha Ollama nem os modelos locais `qwen2.5:7b` e `llama3.1:8b`. Para executar o fluxo, foi usado `engine="local"`, `llm=None` e o gerador extrativo. O veredito foi calculado pelas checagens determinísticas do arquivo `juiz.py`; portanto, estes números **não representam uma execução dos modelos Qwen/Llama nem uma avaliação por LLM-as-a-Judge**.

| | Antes (v1) | Depois (v2) |
|---|---:|---:|
| Acertos no golden (regras) | 21/26 (80,77%) | 26/26 (100%) |
| Erros de dados pessoais | 1 (caso 22) | 0 |
| Erros de prompt injection | 2 (casos 24 e 25) | 0 |
| Erros de citação | 0 | 0 |
| Outros erros | 2 (casos 20 e 21) | 0 |

**Análise dos erros e melhoria:** na v1, o caso 20 (fora do escopo) não orientou adequadamente a consulta ao órgão competente; o caso 21 (entrada inválida) não pediu reformulação nem ofereceu menu/exemplos; o caso 22 (dado pessoal) não cumpriu todos os requisitos de proteção; e os casos 24 e 25 (prompt injection) não recusaram de forma adequada a manipulação. Na v2, as rotas determinísticas e respostas fixas cobriram esses cenários, resultando em 26/26 aprovações nas regras.

**Conferência manual da amostra:** foram inspecionadas cinco respostas selecionadas com `random_state=1`. As cinco passaram nas checagens automáticas (5/5). Como o juiz LLM não foi executado, isso não deve ser descrito como concordância com um juiz humano ou LLM.

## 4. Testes com usuários e simulação de personas

O arquivo `testes_usuarios/testes_usuarios.csv` continua vazio para preservar a distinção entre testes reais e simulação. Não foram coletados tempos de conclusão nem notas de satisfação; esses indicadores não podem ser calculados.

Foi executado `simulacao_personas.py` com cinco personas fictícias e três tarefas por persona, totalizando **15 interações**. O agente v2 foi executado em modo local, sem LLM. O critério foi encontrar na resposta o fato esperado para cada tarefa.

| Persona simulada | Perfil | Acertos |
|---|---|---:|
| P-A | Jovem, escreve curto | 3/3 |
| P-B | Linguagem formal | 3/3 |
| P-C | Apressado, com erros | 3/3 |
| P-D | Usa menu/números | 3/3 |
| P-E | Perguntas amplas | 3/3 |
| **Total** | **5 personas × 3 tarefas** | **15/15 (100%)** |

Tarefas: documentos para a segunda via do RG; gratuidade do título de eleitor; validade da CNH aos 55 anos. A persona P-D selecionou as opções 1, 3 e 6 do menu, que exibem as fichas correspondentes.

**Limitação:** as personas são fictícias e os resultados não são uma pesquisa com usuários reais. Por isso, não há tempo médio nem facilidade de uso (escala 1–5). O CSV de participantes reais não foi preenchido com dados inventados.

## 5. Limitações
- Só responde o que está nas 7 fichas (fictícias); não consulta situação cadastral nem agenda atendimento.
- A busca é por palavras; perguntas com sinônimos raros podem cair em "não encontrei".
- Perguntas que misturam dois assuntos recebem no máximo 2 fichas.
- Um modelo de 7B pode escrever respostas imperfeitas; o nó `verificar` pega valores e prazos inventados, mas não todo erro de interpretação.
- A detecção de injeção é por padrões e pode não pegar ataques novos; a defesa em profundidade é o prompt v2 + verificação.
- Não é canal oficial; todas as respostas trazem esse aviso.
- Acessibilidade: frases curtas, texto simples, uso só com teclado (`app_cli.py`); não há interface gráfica nem leitor de tela dedicado.

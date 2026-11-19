# Citizen Assist AI (projeto Global Solutions)
Integrantes: 

· João Victor Canello Ferian (RM 573295) 

· João Pedro Costenari (RM 572260) 

· Gustavo Melo dos Santos (RM 573562)

## Rodar
```
pip install -r requirements.txt
ollama pull qwen2.5:7b && ollama pull llama3.1:8b
jupyter notebook Citizen_Assist_AI.ipynb      # pipeline completo: agente, juiz, antes/depois
python app_cli.py                              # chat no terminal (só teclado)
python rodar_offline.py                        # testa a lógica sem LLM nem LangGraph
```
## Estrutura
- `fichas/` fichas de referência · `citizen_assist/` código (fichas, guardrails, agente LangGraph, juiz, golden)
- `docs/arquitetura.png` grafo · `docs/RELATORIO.md` justificativas e limitações
- `testes_usuarios/testes_usuarios.csv` modelo para os testes com usuários

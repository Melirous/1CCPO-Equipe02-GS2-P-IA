"""Gera docs/arquitetura.png (grafo do agente) com Graphviz (`dot`)."""
import subprocess
DOT = '''digraph G { rankdir=LR; fontname="Helvetica"; node [fontname="Helvetica", shape=box, style="rounded,filled", fontsize=11];
USER [label="Usuário\\n(menu ou texto)", shape=oval, fillcolor="#ffffff"];
analisar [label="analisar\\n(código: vazio, longo,\\ninjeção, dados pessoais,\\nsem sentido, menu)", fillcolor="#dbeafe"];
resposta_fixa [label="resposta_fixa\\n(código: textos prontos,\\nmenu, recusas)", fillcolor="#dbeafe"];
recuperar [label="recuperar\\n(código: busca por\\npalavras-chave nas fichas)", fillcolor="#dbeafe"];
gerar [label="gerar\\n(IA: Ollama via\\nLangChain, só com fichas)", fillcolor="#fde68a"];
verificar [label="verificar\\n(código: valores, prazos,\\nvazamento, dados pessoais)", fillcolor="#dbeafe"];
finalizar [label="finalizar\\n(código: fonte + data\\n+ aviso)", fillcolor="#dbeafe"];
OUT [label="Resposta", shape=oval, fillcolor="#ffffff"];
USER -> analisar; analisar -> recuperar [label="escopo"]; analisar -> resposta_fixa [label="demais rotas"];
recuperar -> gerar [label="achou ficha"]; recuperar -> resposta_fixa [label="fora do escopo"];
gerar -> verificar; verificar -> finalizar [label="ok ou plano B\\nextrativo"]; resposta_fixa -> finalizar; finalizar -> OUT;
label="Azul = lógica em código | Amarelo = IA (único nó com LLM)"; }'''
subprocess.run(["dot", "-Tpng", "-Gdpi=130", "-o", "docs/arquitetura.png"], input=DOT.encode(), check=True)
print("docs/arquitetura.png gerado")

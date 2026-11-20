"""SIMULAÇÃO (não são testes com usuários): 5 personas fictícias formulam as 3 tarefas do seu jeito.
Roda o agente e confere se a resposta traz o fato esperado. NÃO gera tempo nem nota de facilidade
e NÃO deve ser colocada no CSV nem no relatório como se fosse teste real."""
import re, sys
from citizen_assist import Agente
from citizen_assist.fichas import norm

# tarefa -> (fato esperado como regex, fichas)
TAREFAS = {
 "T1 o que levar p/ 2ª via do RG": r"certidao.*(90 dias|comprovante)|comprovante.*90 dias",
 "T2 título de eleitor é pago?":   r"gratuit",
 "T3 validade da CNH aos 55 anos": r"5 anos",
}
PERSONAS = {
 "P-A (jovem, escreve curto)":   ["docs 2 via rg", "titulo eleitor paga?", "cnh 55 anos vale quanto"],
 "P-B (idosa, formal)":          ["Bom dia. Quais documentos devo levar para tirar a segunda via da minha identidade?",
                                  "Preciso pagar alguma taxa para o título de eleitor?",
                                  "Tenho 55 anos. Por quanto tempo será válida a minha carteira de motorista renovada?"],
 "P-C (apressado, com erros)":   ["o q precisa pra segunda via do rg",  "titulo de eleitor cobra taxa",  "renovei a cnh aos 55 qnto tempo dura a validade"],
 "P-D (usa menu/números)":       ["1", "3", "6"],
 "P-E (pergunta ampla)":         ["Perdi minha identidade, o que eu faço?", "Votar custa alguma coisa?", "Até quando vale a habilitação depois de renovar, se eu tenho 55 anos?"],
}
ag = Agente(llm=None, versao="v2", engine="local")
tot = ok = 0
print("SIMULAÇÃO - agente sem LLM (gerador extrativo)\n")
for p, msgs in PERSONAS.items():
    print(p)
    for (t, rx), m in zip(TAREFAS.items(), msgs):
        e = ag.perguntar(m); achou = bool(re.search(rx, norm(e["final"]), re.S))
        tot += 1; ok += achou
        print(f"  {'OK ' if achou else 'FALHOU'} | {t:34} | rota={e['rota']:10} fontes={e['fontes']} | \"{m}\"")
print(f"\nPerguntas que trouxeram o fato esperado: {ok}/{tot}  (as de menu 1/3/6 mostram a ficha inteira)")

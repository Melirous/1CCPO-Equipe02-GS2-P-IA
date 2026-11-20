"""Teste da lógica SEM LLM e SEM langgraph (motor local + gerador extrativo)."""
from citizen_assist import Agente, CASOS, avaliar
ag = Agente(llm=None, versao="v2", engine="local")
df = avaliar(ag, CASOS)
print(df[["id","tipo","acerto","faltando","proibidos","sem_citacao"]].to_string())
print(f"\nAcertos (regras): {df.acerto.sum()}/{len(df)}")
if __name__ == "__main__" and __import__("sys").argv[1:] == ["-v"]:
    for _, r in df.iterrows(): print("\n#", r.id, r.mensagem, "\n", r.resposta)

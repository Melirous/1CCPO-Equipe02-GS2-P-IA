import sys
from citizen_assist import Agente
from citizen_assist.llm import OllamaLLM
from citizen_assist.respostas import texto_menu

def main():
    sem_llm = "--sem-llm" in sys.argv
    llm = None if sem_llm else OllamaLLM()
    ag = Agente(llm=llm, versao="v2", engine="local" if sem_llm else "langgraph")
    print("Central do Cidadão de Aurora - assistente (protótipo educacional)\n")
    print(texto_menu())
    while True:
        try:
            txt = input("\nVocê> ")
        except (EOFError, KeyboardInterrupt):
            break
        if txt.strip().lower() in {"sair", "exit"}:
            break
        print("\n" + ag.perguntar(txt)["final"])

if __name__ == "__main__":
    main()

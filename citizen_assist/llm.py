"""Cliente do modelo local (Ollama) via LangChain. Importado só quando usado."""
from __future__ import annotations

MODELO_AGENTE = "qwen2.5:7b"   # bom em português e em seguir instruções; roda em CPU/GPU modesta
MODELO_JUIZ = "llama3.1:8b"    # modelo DIFERENTE do agente, para o juiz não "se avaliar"


class OllamaLLM:
    def __init__(self, modelo: str = MODELO_AGENTE, base_url: str = "http://localhost:11434",
                 temperatura: float = 0.0, max_tokens: int = 600):
        from langchain_ollama import ChatOllama  # pip install langchain-ollama
        self.modelo = modelo
        self._chat = ChatOllama(model=modelo, base_url=base_url, temperature=temperatura, num_predict=max_tokens)

    def complete(self, system: str, user: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage
        out = self._chat.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return str(out.content).strip()

"""Avaliação do Golden Dataset em duas fases para reduzir recargas do Ollama.

Primeiro gera todas as respostas com Qwen; depois as julga com Llama. Cada caso
é salvo em checkpoint, permitindo retomar sem repetir chamadas concluídas.
Os checkpoints contêm perguntas de teste fictícias; nunca incluir dados reais.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd

from .agente import Agente
from .guardrails import mascarar_pii
from .juiz import julgar


def _assinatura(casos: list[dict], versao: str, agente, juiz) -> str:
    """Evita reutilizar resultados após mudança no dataset, fichas ou código."""
    raiz = Path(__file__).resolve().parent.parent
    h = hashlib.sha256()
    h.update(json.dumps({
        "casos": casos,
        "versao": versao,
        "agente": getattr(agente, "modelo", type(agente).__name__),
        "juiz": getattr(juiz, "modelo", type(juiz).__name__),
    }, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    arquivos = [raiz / "citizen_assist" / nome for nome in
                ("agente.py", "juiz.py", "respostas.py", "guardrails.py", "fichas.py")]
    arquivos.extend(sorted((raiz / "fichas").glob("*.md")))
    for caminho in arquivos:
        h.update(caminho.name.encode("utf-8"))
        h.update(caminho.read_bytes())
    return h.hexdigest()


def _carregar(caminho: Path, assinatura: str) -> dict[int, dict]:
    if not caminho.exists():
        return {}
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if dados.get("assinatura") != assinatura:
        raise RuntimeError(
            f"Checkpoint incompatível: {caminho}. Renomeie-o para iniciar uma nova avaliação."
        )
    return {int(item["id"]): item for item in dados.get("registros", [])}


def _salvar(caminho: Path, assinatura: str, registros: dict[int, dict]) -> None:
    conteudo = json.dumps({"assinatura": assinatura, "registros": list(registros.values())},
                         ensure_ascii=False, indent=2)
    temporario = caminho.with_name(caminho.name + ".tmp")
    temporario.write_text(conteudo, encoding="utf-8")
    os.replace(temporario, caminho)


def executar_avaliacao_em_lotes(
    versao: str,
    casos: list[dict],
    llm_agente,
    llm_juiz,
    *,
    engine: str = "langgraph",
    pasta_resultados: str | Path = "resultados_execucao",
) -> pd.DataFrame:
    """Executa e salva resultados reais de LLM com retomada por caso.

    Falhas de rede ou do juiz interrompem a execução sem produzir métricas
    completas. Respostas são mascaradas apenas na exportação final.
    """
    if llm_agente is None or llm_juiz is None:
        raise ValueError("A avaliação real exige agente LLM e juiz LLM configurados")
    pasta = Path(pasta_resultados)
    pasta.mkdir(parents=True, exist_ok=True)
    assinatura = _assinatura(casos, versao, llm_agente, llm_juiz)
    arquivo_geracoes = pasta / f"geracoes_{versao}.json"
    arquivo_julgamentos = pasta / f"julgamentos_{versao}.json"
    geracoes = _carregar(arquivo_geracoes, assinatura)
    julgamentos = _carregar(arquivo_julgamentos, assinatura)
    agente = Agente(llm=llm_agente, versao=versao, engine=engine, strict_llm=True)

    print(f"{versao}: geração Qwen — {len(geracoes)}/{len(casos)} já concluídas", flush=True)
    for caso in casos:
        numero = int(caso["id"])
        if numero in geracoes:
            continue
        try:
            estado = agente.perguntar(caso["mensagem"])
        except Exception as exc:
            raise RuntimeError(
                f"{versao}, geração do caso {numero} interrompida: {type(exc).__name__}. "
                "Checkpoint salvo; reexecute a célula quando o Ollama estiver disponível."
            ) from None
        if estado.get("rota") == "erro":
            raise RuntimeError(f"{versao}, caso {numero}: erro inesperado no agente")
        geracoes[numero] = {
            "id": numero,
            "resposta_original": estado["final"],
            "origem": estado.get("origem"),
            "verificacao": estado.get("verificacao"),
        }
        _salvar(arquivo_geracoes, assinatura, geracoes)
        print(f"{versao} Qwen {len(geracoes):02d}/{len(casos)}", flush=True)

    print(f"{versao}: julgamento Llama — {len(julgamentos)}/{len(casos)} já concluídos", flush=True)
    for caso in casos:
        numero = int(caso["id"])
        if numero in julgamentos:
            continue
        resposta = geracoes[numero]["resposta_original"]
        julgamento = julgar(caso, resposta, llm_juiz)
        if julgamento["veredito_juiz"] not in ("correto", "parcial", "incorreto"):
            raise RuntimeError(
                f"{versao}, juiz do caso {numero} não retornou JSON válido "
                f"({julgamento['veredito_juiz']}). Reexecute esta célula; as respostas geradas estão salvas."
            )
        julgamento.update({
            "mensagem": mascarar_pii(caso["mensagem"])[0],
            "resposta": mascarar_pii(resposta)[0],
            "origem": geracoes[numero]["origem"],
            "verificacao": geracoes[numero]["verificacao"],
        })
        julgamentos[numero] = julgamento
        _salvar(arquivo_julgamentos, assinatura, julgamentos)
        print(f"{versao} Llama {len(julgamentos):02d}/{len(casos)} "
              f"acerto={julgamento['acerto']}", flush=True)

    return pd.DataFrame([julgamentos[int(c["id"])] for c in casos])

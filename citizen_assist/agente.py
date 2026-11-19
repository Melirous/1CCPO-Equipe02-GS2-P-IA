"""Agente único em LangGraph: nós de lógica (código) + um nó de IA (geração).

Fluxo v2 (final):
  analisar -> [resposta_fixa | recuperar] -> gerar -> verificar -> finalizar
Fluxo v1 (baseline, para o "antes"): sem guardrails e sem verificação.

O grafo é definido UMA vez (NOS + proximo_no) e executado por:
  - LangGraph (engine="langgraph"), usado no trabalho;
  - um executor mínimo local (engine="local"), só para testar a lógica sem instalar nada.
Nada é gravado em disco ou log: o estado vive só na memória da chamada.
"""
from __future__ import annotations

import re
from typing import Callable, TypedDict

from . import guardrails as g
from . import respostas as r
from .fichas import Ficha, carregar_fichas, contexto_para_prompt, escolher_fichas, norm, todas_as_fichas_texto


class Estado(TypedDict, total=False):
    entrada: str          # texto do usuário (substituído pela versão mascarada em seguida)
    rota: str             # decisão do nó 'analisar'
    inj: str              # tipo de injeção, se houver
    pii_tipo: str         # situacao | agendar | geral
    codigos: list         # fichas escolhidas
    usadas: list          # fichas que foram ao prompt
    resposta: str         # rascunho
    fontes: list          # fichas citadas
    origem: str           # 'regra' | 'llm' | 'extrativo'
    verificacao: str      # 'ok' | motivo da falha
    final: str            # texto exibido ao usuário


class Agente:
    def __init__(self, llm=None, versao: str = "v2", engine: str = "langgraph",
                 fichas: dict[str, Ficha] | None = None):
        self.llm, self.versao, self.engine = llm, versao, engine
        self.fichas = fichas or carregar_fichas()
        self.vocab = g.vocabulario(self.fichas)
        self.data = next(iter(self.fichas.values())).versao
        self.nos: dict[str, Callable[[Estado], Estado]] = {
            "analisar": self.analisar, "resposta_fixa": self.resposta_fixa, "recuperar": self.recuperar,
            "gerar": self.gerar, "verificar": self.verificar, "finalizar": self.finalizar,
        }
        self._app = self._montar_langgraph() if engine == "langgraph" else None

    # ------------------------------------------------------------------ nós
    def analisar(self, s: Estado) -> Estado:
        """Lógica pura (sem IA): valida a entrada e decide a rota."""
        txt = s.get("entrada") or ""
        if not txt.strip():
            return {"rota": "vazia", "entrada": ""}
        if len(txt) > g.MAX_CHARS:
            return {"rota": "longa", "entrada": ""}  # descarta o texto
        if self.versao == "v1":
            return {"rota": "escopo", "entrada": txt.strip()}
        inj = g.tipo_injecao(txt)
        if inj:
            return {"rota": "injecao_" + inj, "inj": inj, "entrada": txt.strip()}
        mascarado, achou = g.mascarar_pii(txt)
        if achou or g.tem_intencao_pii(txt):
            return {"rota": "pii", "pii_tipo": g.tipo_pedido_pii(txt), "entrada": mascarado}  # texto original some do estado
        cmd = g.comando_menu(txt)
        if cmd:
            return {"rota": "menu" if cmd not in "1234567" else "categoria", "entrada": cmd if cmd in "1234567" else "menu"}
        if g.sem_sentido(txt, self.vocab) and not escolher_fichas(txt, self.fichas):
            return {"rota": "sem_sentido", "entrada": txt.strip()}
        if g.pergunta_canal_oficial(txt):
            return {"rota": "limitacao", "entrada": txt.strip()}
        return {"rota": "escopo", "entrada": txt.strip()}

    def recuperar(self, s: Estado) -> Estado:
        """Busca por regras nas fichas (sem IA)."""
        if self.versao == "v1":  # baseline: joga todas as fichas no prompt
            return {"codigos": list(self.fichas), "usadas": list(self.fichas)}
        cods = escolher_fichas(s["entrada"], self.fichas)
        if not cods:
            return {"codigos": [], "rota": "fora_escopo"}
        _, usadas = contexto_para_prompt(cods, self.fichas)
        return {"codigos": cods, "usadas": usadas}

    def resposta_fixa(self, s: Estado) -> Estado:
        """Respostas prontas para casos que não precisam de IA (mais seguras e baratas)."""
        rota = s["rota"]
        if rota == "menu":
            return {"resposta": r.texto_menu(), "fontes": [], "origem": "regra"}
        if rota == "categoria":
            cod = next(c for n, c, _ in r.MENU if n == s["entrada"])
            return {"resposta": r.resumo_ficha(self.fichas[cod]), "fontes": [cod], "origem": "regra"}
        if rota == "pii":
            chave = "pii_" + s.get("pii_tipo", "geral")
            return {"resposta": r.FIXAS[chave], "fontes": r.FONTES_FIXAS[chave], "origem": "regra"}
        if rota == "injecao_sobrescrever":
            txt = r.FIXAS[rota]
            cods = escolher_fichas(s["entrada"], self.fichas)
            fontes = []
            if cods:  # mantém o valor das fichas (ex.: R$ 38,00)
                f = self.fichas[cods[0]]
                tokens = set(re.findall(r"[a-z]{4,}", norm(s["entrada"])))
                frases = re.split(r"(?<=[.;])\s+", f.campos.get("Custo", ""))
                certas = [x for x in frases if tokens & set(re.findall(r"[a-z]{4,}", norm(x)))
                          and "R$" in x] or [x for x in frases if "R$" in x]
                if certas:
                    txt += f"\nO que vale é o que está na ficha: {' '.join(certas)} [{f.codigo}]"
                    fontes = [f.codigo]
            return {"resposta": txt, "fontes": fontes, "origem": "regra"}
        chave = {"injecao_revelar": "injecao_revelar"}.get(rota, rota)
        return {"resposta": r.FIXAS[chave], "fontes": r.FONTES_FIXAS.get(chave, []), "origem": "regra"}

    def gerar(self, s: Estado) -> Estado:
        """Único nó com IA. Se o LLM falhar, cai no gerador extrativo (sem erro técnico para o usuário)."""
        pergunta = s["entrada"]
        if self.versao == "v1":
            system = r.SYSTEM_V1.format(fichas=todas_as_fichas_texto(self.fichas))
        else:
            ctx, _ = contexto_para_prompt(s["codigos"], self.fichas)
            system = r.SYSTEM_V2.format(fichas=ctx)
        if self.llm is not None:
            try:
                txt = self.llm.complete(system, r.USER_TMPL.format(pergunta=pergunta))
                if txt.strip():
                    return {"resposta": txt.strip(), "origem": "llm"}
            except Exception:  # Ollama fora do ar, timeout etc.
                pass
        extr = r.resposta_extrativa(pergunta, self.fichas, s.get("codigos", []))
        if not extr:
            return {"resposta": r.FIXAS["fora_escopo"], "fontes": [], "origem": "extrativo"}
        return {"resposta": extr, "origem": "extrativo"}

    def verificar(self, s: Estado) -> Estado:
        """Checagem em código da resposta do LLM: valores inventados, vazamento do prompt e dados pessoais."""
        resp = s["resposta"]
        if s.get("origem") != "llm":
            return {"verificacao": "ok"}
        ctx, _ = contexto_para_prompt(s["codigos"], self.fichas)
        problema = None
        base = norm(ctx)
        for v in re.findall(r"r\$\s?[\d.]+,\d{2}", norm(resp)):
            if v.replace(" ", "") not in base.replace(" ", ""):
                problema = f"valor fora das fichas: {v}"
        for n, unid in re.findall(r"(\d+)\s*(dias|anos|horas)", norm(resp)):
            if not re.search(rf"\b{n}\s*(dias|anos|horas)", base):
                problema = problema or f"prazo fora das fichas: {n} {unid}"
        if "<fichas>" in resp or "REGRAS:" in resp or "SOMENTE com base nas FICHAS" in resp:
            problema = "vazamento de instruções"
        if g.mascarar_pii(resp)[1]:
            problema = "dado pessoal na resposta"
        if problema:
            extr = r.resposta_extrativa(s["entrada"], self.fichas, s["codigos"]) or r.FIXAS["fora_escopo"]
            return {"resposta": extr, "origem": "extrativo", "verificacao": problema}
        return {"verificacao": "ok"}

    def finalizar(self, s: Estado) -> Estado:
        """Monta o texto final: resposta + fontes com data + aviso (em TODA resposta)."""
        resp = s["resposta"]
        fontes = list(s.get("fontes") or [])
        if s.get("origem") != "regra":
            marcadas = re.findall(r"\[(FC-0\d)\]", resp)  # só citações em colchetes, não menções dentro do texto copiado
            citadas = [c for c in dict.fromkeys(marcadas or re.findall(r"FC-0\d", resp)) if c in self.fichas]
            if citadas:
                fontes = citadas
            elif s.get("codigos") and s.get("rota") != "fora_escopo" and "Não encontrei" not in resp:
                fontes = list(s["codigos"])
        linhas = [resp.strip()]
        if fontes:
            linhas.append("Fonte: " + ", ".join(f"{c} (verificada em {self.data})" for c in fontes))
        linhas.append(r.AVISO)
        return {"final": "\n\n".join(linhas), "fontes": fontes}

    # ------------------------------------------------------------------ grafo
    def proximo_no(self, no: str, s: Estado) -> str:
        """Arestas do grafo (usadas pelos dois motores)."""
        if no == "analisar":
            return "recuperar" if s["rota"] == "escopo" else "resposta_fixa"
        if no == "recuperar":
            return "gerar" if s.get("codigos") else "resposta_fixa"
        if no == "gerar":
            return "verificar" if self.versao == "v2" else "finalizar"
        if no == "verificar":
            return "finalizar"
        if no == "resposta_fixa":
            return "finalizar"
        return "END"

    ARESTAS = {  # para o diagrama
        "analisar": ["recuperar", "resposta_fixa"], "recuperar": ["gerar", "resposta_fixa"],
        "gerar": ["verificar"], "verificar": ["finalizar"], "resposta_fixa": ["finalizar"], "finalizar": ["END"],
    }

    def _montar_langgraph(self):
        from langgraph.graph import END, START, StateGraph  # pip install langgraph
        grafo = StateGraph(Estado)
        for nome, fn in self.nos.items():
            grafo.add_node(nome, fn)
        grafo.add_edge(START, "analisar")
        grafo.add_conditional_edges("analisar", lambda s: self.proximo_no("analisar", s),
                                    {"recuperar": "recuperar", "resposta_fixa": "resposta_fixa"})
        grafo.add_conditional_edges("recuperar", lambda s: self.proximo_no("recuperar", s),
                                    {"gerar": "gerar", "resposta_fixa": "resposta_fixa"})
        if self.versao == "v2":
            grafo.add_edge("gerar", "verificar")
            grafo.add_edge("verificar", "finalizar")
        else:
            grafo.add_edge("gerar", "finalizar")
        grafo.add_edge("resposta_fixa", "finalizar")
        grafo.add_edge("finalizar", END)
        return grafo.compile()  # sem checkpointer: nada é guardado entre chamadas

    def _rodar_local(self, estado: Estado) -> Estado:
        s, no = dict(estado), "analisar"
        while no != "END":
            s.update(self.nos[no](s))
            no = self.proximo_no(no, s)
        return s

    # ------------------------------------------------------------------ API
    def perguntar(self, texto: str) -> Estado:
        """Devolve o estado final. `final` é o texto para o usuário."""
        try:
            ini: Estado = {"entrada": texto if isinstance(texto, str) else ""}
            return self._app.invoke(ini) if self._app else self._rodar_local(ini)
        except Exception:  # nunca mostrar erro técnico
            return {"final": "Desculpe, não consegui responder agora. Tente de novo ou escolha um assunto no menu.\n\n"
                             + r.texto_menu() + "\n\n" + r.AVISO, "rota": "erro", "fontes": [], "origem": "regra"}

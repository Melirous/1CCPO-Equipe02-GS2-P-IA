"""Carga, organização e busca nas fichas da Central do Cidadão de Aurora.

As fichas são curtas (~300 tokens cada), então a organização é:
  1. cada .md vira um objeto `Ficha` com campos nomeados (custo, prazo, ...);
  2. a busca é por regras (palavras-chave + termos fortes), sem embeddings;
  3. as fichas escolhidas entram INTEIRAS no prompt (contexto pequeno, sem perda).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

PASTA_FICHAS = Path(__file__).resolve().parent.parent / "fichas"


def norm(texto: str) -> str:
    """minúsculas e sem acentos, para comparar textos."""
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


@dataclass
class Ficha:
    codigo: str
    titulo: str
    palavras_chave: list[str]
    campos: dict[str, str]  # nome do campo -> texto
    versao: str
    texto: str  # markdown original, usado no prompt

    def campo(self, trecho: str) -> list[tuple[str, str]]:
        """Campos cujo nome (normalizado) contém `trecho`."""
        return [(k, v) for k, v in self.campos.items() if trecho in norm(k)]


# Termos "fortes": identificam o assunto da ficha com muita confiança (peso 3).
TERMOS_FORTES = {
    "FC-01": ["rg", "identidade", "carteira de identidade", "posto de identificacao"],
    "FC-02": ["cpf"],
    "FC-03": ["titulo", "eleitor", "eleicao", "eleitoral", "votar", "voto", "zona eleitoral"],
    "FC-04": ["carteira de trabalho", "ctps"],
    "FC-05": ["certidao", "certidoes", "cartorio", "obito"],
    "FC-06": ["cnh", "habilitacao", "carteira de motorista", "motorista", "dirigir"],
    "FC-07": ["sabado", "sabados", "domingo", "feriado", "atendem", "atendimento",
              "horario de atendimento", "libras", "interprete", "prioritario",
              "procuracao", "pix", "pagamento", "terceiros", "outra pessoa", "acessibilidade"],
}
# Palavras extras de peso 1 (sinônimos que não estão nas "Palavras-chave" das fichas).
TERMOS_EXTRAS = {
    "FC-01": ["segunda via", "boletim de ocorrencia"],
    "FC-02": ["inscrever", "inscricao"],
    "FC-03": ["transferir", "transferencia"],
    "FC-06": ["vencida", "venceu", "renovar", "renovacao"],
}
# Termos genéricos demais para valer como pista de assunto.
IGNORAR_CHAVES = {"digital", "emprego", "trabalho", "comprovante", "cadastro de pessoa fisica", "perdi", "roubaram"}


def _tem(termo: str, texto_norm: str) -> bool:
    return re.search(r"\b" + re.escape(termo) + r"\b", texto_norm) is not None


def _parse(md: str, versao_padrao: str) -> Ficha:
    linhas = md.splitlines()
    m = re.match(r"#\s*(FC-\d\d)\s*[—-]\s*(.+)", linhas[0])
    codigo, titulo = (m.group(1), m.group(2).strip()) if m else ("FC-??", linhas[0])
    campos: dict[str, str] = {}
    atual = None
    for ln in linhas[1:]:
        h = re.match(r"\*\*(.+?):\*\*\s*(.*)$", ln)
        if h:
            atual = h.group(1).strip()
            campos[atual] = h.group(2).strip()
        elif atual and ln.strip():
            campos[atual] += "\n" + ln.rstrip()
    chaves = [c.strip() for c in campos.get("Palavras-chave", "").split(",") if c.strip()]
    fonte = campos.get("Fonte", "")
    v = re.search(r"versão de (\d\d/\d\d/\d{4})", fonte)
    return Ficha(codigo, titulo, chaves, campos, v.group(1) if v else versao_padrao, md.strip())


def carregar_fichas(pasta: Path = PASTA_FICHAS) -> dict[str, Ficha]:
    leia = (pasta / "00_LEIA-ME.md")
    versao = "01/10/2026"
    if leia.exists():
        m = re.search(r"Versão das fichas:\s*(\d\d/\d\d/\d{4})", leia.read_text(encoding="utf-8"))
        if m:
            versao = m.group(1)
    fichas = {}
    for arq in sorted(pasta.glob("FC-*.md")):
        f = _parse(arq.read_text(encoding="utf-8"), versao)
        fichas[f.codigo] = f
    return fichas


def pontuar(texto: str, fichas: dict[str, Ficha]) -> dict[str, int]:
    """Pontua cada ficha para a pergunta (regras simples e auditáveis)."""
    t = norm(texto)
    pontos = {}
    for cod, f in fichas.items():
        p = 0
        for termo in TERMOS_FORTES.get(cod, []):
            if _tem(termo, t):
                p += 3
        extras = [norm(c) for c in f.palavras_chave if norm(c) not in IGNORAR_CHAVES]
        extras += TERMOS_EXTRAS.get(cod, [])
        for termo in set(extras) - set(TERMOS_FORTES.get(cod, [])):
            if _tem(termo, t):
                p += 1
        pontos[cod] = p
    return pontos


def escolher_fichas(texto: str, fichas: dict[str, Ficha]) -> list[str]:
    """Códigos das fichas relevantes (no máximo 2). Lista vazia = fora do escopo."""
    pontos = pontuar(texto, fichas)
    ordem = sorted(pontos, key=lambda c: -pontos[c])
    if not ordem or pontos[ordem[0]] < 2:  # só palavra genérica => não conta
        return []
    topo = pontos[ordem[0]]
    sel = [ordem[0]]
    for c in ordem[1:]:
        if pontos[c] >= 3 and pontos[c] * 2 >= topo and len(sel) < 2:
            sel.append(c)
    return sel


def contexto_para_prompt(codigos: list[str], fichas: dict[str, Ficha]) -> tuple[str, list[str]]:
    """Fichas escolhidas + FC-07 (regras gerais, sempre útil). Retorna texto e códigos usados."""
    usados = list(codigos)
    if "FC-07" in fichas and "FC-07" not in usados:
        usados.append("FC-07")
    return "\n\n".join(fichas[c].texto for c in usados), usados


def todas_as_fichas_texto(fichas: dict[str, Ficha]) -> str:
    return "\n\n".join(f.texto for f in fichas.values())


MENU = [
    ("1", "FC-01", "RG (primeira e segunda via)"),
    ("2", "FC-02", "CPF"),
    ("3", "FC-03", "Título de eleitor"),
    ("4", "FC-04", "Carteira de Trabalho"),
    ("5", "FC-05", "Certidões (nascimento, casamento, óbito)"),
    ("6", "FC-06", "CNH (renovação)"),
    ("7", "FC-07", "Regras gerais (horário, terceiros, pagamento, acessibilidade)"),
]

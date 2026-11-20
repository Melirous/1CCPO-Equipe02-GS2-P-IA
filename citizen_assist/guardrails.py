"""Proteções feitas em CÓDIGO (regex e regras), antes de qualquer LLM.

Cobrem: entrada vazia/longa/sem sentido, dados pessoais, prompt injection,
pergunta sobre ser canal oficial e comandos de menu.
Nada aqui grava arquivo, log ou histórico.
"""
from __future__ import annotations

import re

from .fichas import Ficha, norm

MAX_CHARS = 500
OCULTO = "[DADO OCULTO]"

# --- Dados pessoais -------------------------------------------------------
PADROES_PII = [
    re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),                 # CPF
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),                          # e-mail
    re.compile(r"(?:\(?\d{2}\)?\s?)?9?\d{4}-?\d{4}\b"),               # telefone
    re.compile(r"\b\d{5}-?\d{3}\b"),                                  # CEP
    re.compile(r"\b\d{7,}\b"),                                        # qualquer número longo (RG, CNH, título...)
]
# "vou te passar meu endereço", "meu CPF é ..." (sem o dado em si)
INTENCAO_PII = [
    re.compile(r"\b(passar|passo|informar|informo|enviar|envio|mandar|mando|fornecer|dar|digitar)\b.{0,25}"
               r"\b(meu|minha|meus|minhas|o meu)\s+(endereco|telefone|celular|cpf|rg|cnh|email|e-mail|senha|titulo|dados)"),
    re.compile(r"\b(meu|minha)\s+(cpf|rg|cnh|telefone|celular|endereco|email|e-mail|senha)\s+(e|eh|sao|:)\b"),
]


def mascarar_pii(texto: str) -> tuple[str, bool]:
    """Troca padrões de dados pessoais por [DADO OCULTO]. Retorna (texto, achou)."""
    achou = False
    for p in PADROES_PII:
        texto, n = p.subn(OCULTO, texto)
        achou = achou or n > 0
    return texto, achou


def tem_intencao_pii(texto: str) -> bool:
    t = norm(texto)
    return any(p.search(t) for p in INTENCAO_PII)


def tipo_pedido_pii(texto: str) -> str:
    """O que a pessoa queria fazer com os dados? Define a resposta fixa."""
    t = norm(texto)
    if re.search(r"situacao|consult|regulariz|cadastral|ver (a |minha )", t):
        return "situacao"
    if re.search(r"agend|marcar|horario", t):
        return "agendar"
    return "geral"


# --- Prompt injection -------------------------------------------------------
INJECAO_REVELAR = re.compile(
    r"(mostre|revele|exiba|imprima|repita|diga|qual).{0,40}(prompt|instruc|regras internas)|system prompt|prompt de sistema")
INJECAO_SOBRESCREVER = re.compile(
    r"\[\s*(sistema|system|admin)\s*\]|nova regra|a partir de agora|ignore (todas )?(as )?instruc|"
    r"desconsidere|esqueca (as|tudo|suas)|voce agora e|finja (que )?(ser|e)\b|modo (desenvolvedor|dev)|jailbreak|"
    r"novas instrucoes")


def tipo_injecao(texto: str) -> str | None:
    t = norm(texto)
    if INJECAO_REVELAR.search(t):
        return "revelar"
    if INJECAO_SOBRESCREVER.search(t):
        return "sobrescrever"
    return None


# --- Limitação, menu, entradas inválidas -----------------------------------
def pergunta_canal_oficial(texto: str) -> bool:
    t = norm(texto)
    return bool(re.search(r"\b(canal|site|sistema|servico|orgao|atendimento) oficial|\boficial\b.*(prefeitura|governo)|"
                          r"(prefeitura|governo).*\boficial\b|voce (e|eh) (a |o )?(prefeitura|governo)", t))


def comando_menu(texto: str) -> str | None:
    t = norm(texto).strip(" .!?")
    if t in {"menu", "ajuda", "help", "inicio", "0", "opcoes", "oi", "ola", "bom dia", "boa tarde", "boa noite"}:
        return "menu"
    if re.fullmatch(r"[1-7]", t):
        return t
    return None


COMUNS = set("""quanto quantos quanta custa custo como qual quais onde quando preciso posso quero fazer tirar pedir
voce voces vou que uma uns umas dos das tem tenho tem para por com sem sobre meu minha meus pelo pela nao sim
tambem ainda ja so mais menos qual quem porque pode podem devo deve vale valor preco precos imposto quero gostaria saber informacao informacoes""".split())


def vocabulario(fichas: dict[str, Ficha]) -> set[str]:
    v = set(COMUNS)
    for f in fichas.values():
        v |= set(re.findall(r"[a-z]{3,}", norm(f.texto)))
    return v


def sem_sentido(texto: str, vocab: set[str]) -> bool:
    """Texto sem palavras reconhecíveis (ex.: 'asdfgh ??? 123')."""
    toks = re.findall(r"[a-z]{3,}", norm(texto))
    if not toks:
        return True
    conhecidas = sum(t in vocab for t in toks)
    return conhecidas / len(toks) < 0.34

"""Validação sintática e estrutural independente do provedor (#13)."""
import json
from copy import deepcopy

from django.core.exceptions import ValidationError

from ..validators import validar_alternativas
from .errors import ErroIA


def invalido():
    return ErroIA("ia_json_invalido", "A IA retornou um material inválido. Tente novamente.")


def _objeto_unico(pares):
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ValueError("Chave JSON repetida")
        objeto[chave] = valor
    return objeto


def _constante_invalida(valor):
    raise ValueError("Constante JSON inválida")


def ler_json(texto):
    if not isinstance(texto, str):
        raise invalido()
    try:
        if len(texto.encode("utf-8")) > 2_000_000:
            raise invalido()
        return json.loads(texto, object_pairs_hook=_objeto_unico, parse_constant=_constante_invalida)
    except (ValueError, RecursionError, UnicodeError):
        raise invalido() from None


def _campos(objeto, campos):
    if not isinstance(objeto, dict) or set(objeto) != set(campos):
        raise invalido()


def _texto(valor, limite=None):
    if not isinstance(valor, str) or not valor.strip() or (limite and len(valor) > limite):
        raise invalido()
    try:
        valor.encode("utf-8")
    except UnicodeError:
        raise invalido() from None


def validar_resultado_tema(texto, tema):
    dados = ler_json(texto)
    _campos(dados, ("status", "tema", "motivo"))
    if dados["status"] not in ("ok", "amplo", "invalido") or dados["tema"] != tema:
        raise invalido()
    _texto(dados["motivo"], 1000)
    return dados


def validar_conteudo(texto, tema):
    dados = ler_json(texto)
    _campos(dados, ("tema", "resumo", "perguntas"))
    _texto(dados["tema"], 255)
    _texto(dados["resumo"])
    if dados["tema"] != tema:
        raise invalido()
    perguntas = dados["perguntas"]
    if not isinstance(perguntas, list) or len(perguntas) != 10:
        raise invalido()
    ids, enunciados = set(), set()
    for pergunta in perguntas:
        _campos(pergunta, ("id", "topic", "prompt", "answers", "correctAnswerId"))
        for campo in ("id", "topic", "prompt", "correctAnswerId"):
            _texto(pergunta[campo])
        enunciado = " ".join(pergunta["prompt"].casefold().split())
        if pergunta["id"] in ids or enunciado in enunciados or pergunta["topic"] != tema:
            raise invalido()
        ids.add(pergunta["id"])
        enunciados.add(enunciado)
        try:
            validar_alternativas(pergunta["answers"])
        except ValidationError:
            raise invalido() from None
        alternativas = pergunta["answers"]
        for alternativa in alternativas:
            for valor in alternativa.values():
                _texto(valor)
        textos = {" ".join(a["text"].casefold().split()) for a in alternativas}
        if len(textos) != 4 or pergunta["correctAnswerId"] not in {a["id"] for a in alternativas}:
            raise invalido()
    return deepcopy(dados)

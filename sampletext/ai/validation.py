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


MINIMO_PERGUNTAS = 5
MAXIMO_PERGUNTAS = 10


def _pergunta_valida(pergunta, numero, tema):
    """Normaliza detalhes sem importância e devolve a pergunta pronta.

    Lança ErroIA se a pergunta estiver estruturalmente quebrada (ela será descartada).
    """
    _campos(pergunta, ("id", "topic", "prompt", "answers", "correctAnswerId"))
    _texto(pergunta["prompt"])
    pergunta["id"] = f"pergunta-{numero}"
    pergunta["topic"] = tema
    try:
        validar_alternativas(pergunta["answers"])
    except ValidationError:
        raise invalido() from None
    alternativas = pergunta["answers"]
    for alternativa in alternativas:
        for valor in alternativa.values():
            _texto(valor)
    if len({" ".join(a["text"].casefold().split()) for a in alternativas}) != 4:
        raise invalido()
    correta = pergunta["correctAnswerId"]
    if not isinstance(correta, str) or correta.strip().lower() not in {a["id"] for a in alternativas}:
        raise invalido()
    pergunta["correctAnswerId"] = correta.strip().lower()
    return pergunta


def validar_conteudo(texto, tema):
    """Valida o material da IA de forma tolerante.

    Estrutura obrigatória: tema, resumo e perguntas. Para o que a IA costuma errar sem gravidade
    (tema com outra grafia, ids e topics diferentes, perguntas repetidas ou quebradas, mais de 10
    perguntas), o material é corrigido ou a pergunta problemática é descartada, e só se rejeita
    tudo se sobrarem menos de MINIMO_PERGUNTAS perguntas válidas.
    """
    dados = ler_json(texto)
    _campos(dados, ("tema", "resumo", "perguntas"))
    _texto(dados["resumo"])
    perguntas = dados["perguntas"]
    if not isinstance(perguntas, list):
        raise invalido()

    validas, enunciados = [], set()
    for bruta in perguntas:
        try:
            pergunta = _pergunta_valida(bruta, len(validas) + 1, tema)
        except (ErroIA, TypeError, KeyError, AttributeError):
            continue
        enunciado = " ".join(pergunta["prompt"].casefold().split())
        if enunciado in enunciados:
            continue
        enunciados.add(enunciado)
        validas.append(pergunta)
        if len(validas) == MAXIMO_PERGUNTAS:
            break
    if len(validas) < MINIMO_PERGUNTAS:
        raise invalido()

    return {"tema": tema, "resumo": dados["resumo"], "perguntas": deepcopy(validas)}

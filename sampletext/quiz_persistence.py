"""Identidade estável das perguntas geradas e criação atômica de material salvo."""
import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .ai.validation import validar_conteudo
from .models import Pergunta, Resposta


def campos_pergunta(dados):
    return {"tema": dados["topic"], "enunciado": dados["prompt"],
            "alternativas": dados["answers"], "resposta_correta": dados["correctAnswerId"]}


def _obter_ou_criar(modelo, busca, padroes):
    # Model.save executa full_clean: uma corrida pode aparecer tanto como erro de
    # validação quanto como violação da restrição única. O banco garante a unicidade.
    try:
        with transaction.atomic():
            return modelo.objects.get_or_create(**busca, defaults=padroes)
    except (ValidationError, IntegrityError):
        existente = modelo.objects.filter(**busca).first()
        if existente is None:
            raise
        return existente, False


def perguntas_da_geracao(material):
    tema = material.get("tema") if isinstance(material, dict) else None
    dados = validar_conteudo(json.dumps(material, ensure_ascii=False), tema)
    persistidas = []
    with transaction.atomic():
        for pergunta in dados["perguntas"]:
            campos = campos_pergunta(pergunta)
            canonico = json.dumps(campos, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            chave = hashlib.sha256(canonico.encode("utf-8")).hexdigest()
            objeto, _ = _obter_ou_criar(Pergunta, {"chave_geracao": chave}, campos)
            persistidas.append(objeto.para_quiz())
    return {**dados, "perguntas": persistidas}


def registrar_resposta(usuario, pergunta, alternativa, chave_envio=None):
    campos = {"usuario": usuario, "pergunta": pergunta, "alternativa": alternativa}
    if chave_envio is None:
        return Resposta.objects.create(**campos), True
    return _obter_ou_criar(Resposta, {"usuario": usuario, "chave_envio": chave_envio},
                          {"pergunta": pergunta, "alternativa": alternativa})

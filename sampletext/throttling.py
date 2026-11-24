"""Limite de requisições (issue #8): protege a cota gratuita da IA e o login público."""

import math

from rest_framework.exceptions import Throttled
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import exception_handler


class LimiteLogin(AnonRateThrottle):
    """Tentativas de login por IP (o login é público e cria usuários)."""

    scope = "login"


class LimiteIAPorHora(UserRateThrottle):
    scope = "ia_hora"


class LimiteIAPorDia(UserRateThrottle):
    scope = "ia_dia"


LIMITES_IA = (LimiteIAPorHora, LimiteIAPorDia)


def verificar_limite_ia(request, view=None):
    """Gasta uma chamada da cota de IA do usuário; levanta Throttled (HTTP 429) se acabou.

    Chame só quando for mesmo chamar a IA (depois de olhar o cache): temas que já
    estão no cache não gastam cota. Veja `cache_conteudo.obter_ou_gerar(antes_de_gerar=...)`.
    """
    for classe in LIMITES_IA:
        limite = classe()
        if not limite.allow_request(request, view):
            raise Throttled(wait=limite.wait())


def _formatar_espera(segundos):
    if segundos < 120:
        return f"{segundos} {'segundo' if segundos == 1 else 'segundos'}"
    if segundos < 7200:
        return f"{math.ceil(segundos / 60)} minutos"
    return f"{math.ceil(segundos / 3600)} horas"


def tratar_excecoes(exc, context):
    """Igual ao handler padrão do DRF, mas com a mensagem do 429 em português."""
    resposta = exception_handler(exc, context)
    if isinstance(exc, Throttled) and resposta is not None:
        if exc.wait:
            espera = max(1, math.ceil(exc.wait))
            resposta.data = {
                "detail": f"Muitas requisições. Tente de novo em {_formatar_espera(espera)}.",
                "retry_after": espera,
            }
        else:
            resposta.data = {"detail": "Muitas requisições. Tente de novo em alguns instantes."}
    return resposta
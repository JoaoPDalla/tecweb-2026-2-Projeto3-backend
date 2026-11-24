from django.conf import settings

from ..prompts.resumo import montar_mensagens_resumo, obter_schema_conteudo
from ..prompts.tema import montar_mensagens_tema, obter_schema_tema
from .client import ClienteIA
from .errors import ErroIA
from .validation import validar_conteudo, validar_resultado_tema


def validar_tema(tema, cliente=None):
    cliente = cliente or ClienteIA()
    return validar_resultado_tema(cliente.gerar_json(
        montar_mensagens_tema(tema), obter_schema_tema(), "validacao_tema", 512,
    ), tema)


def gerar_conteudo(tema):
    cliente = ClienteIA()
    validacao = validar_tema(tema, cliente)
    if validacao["status"] != "ok":
        codigo = "tema_amplo" if validacao["status"] == "amplo" else "tema_invalido"
        raise ErroIA(codigo, validacao["motivo"], 422)
    texto = cliente.gerar_json(
        montar_mensagens_resumo(tema), obter_schema_conteudo(), "material_estudo", settings.AI_MAX_OUTPUT_TOKENS,
    )
    return validar_conteudo(texto, tema)

"""Cache de conteúdo gerado pela IA (issue #7): um mesmo tema só é gerado uma vez."""

import unicodedata

from .models import ConteudoGerado

TAMANHO_MAXIMO_TEMA = 255


def chave_do_tema(tema):
    """Ignora maiúsculas, acentos e espaços extras: 'Cálculo  I' e 'calculo i' são o mesmo tema."""
    if not isinstance(tema, str) or not tema.strip():
        raise ValueError("Informe um tema não vazio.")
    if len(tema.strip()) > TAMANHO_MAXIMO_TEMA:
        raise ValueError(f"O tema deve ter no máximo {TAMANHO_MAXIMO_TEMA} caracteres.")
    sem_acentos = "".join(c for c in unicodedata.normalize("NFKD", tema) if not unicodedata.combining(c))
    return " ".join(sem_acentos.casefold().split())


def obter_ou_gerar(tema, gerador, antes_de_gerar=None):
    """Devolve (conteudo, veio_do_cache).

    - `gerador(tema)` chama a IA e devolve um dict {tema, resumo, perguntas} já validado (#13).
      Se ele falhar, nada é guardado no cache.
    - `antes_de_gerar()` roda só quando o tema NÃO está no cache, logo antes de chamar a IA.
      É o lugar de gastar a cota do usuário: `lambda: verificar_limite_ia(request, self)`.
    """
    chave = chave_do_tema(tema)

    existente = ConteudoGerado.objects.filter(tema_chave=chave).first()
    if existente:
        return existente.como_dict(), True

    if antes_de_gerar:
        antes_de_gerar()
    conteudo = gerador(tema.strip())

    try:
        campos = {"tema": conteudo["tema"], "resumo": conteudo["resumo"], "perguntas": conteudo["perguntas"]}
    except (KeyError, TypeError):
        raise ValueError("O conteúdo gerado precisa ter tema, resumo e perguntas.") from None

    # Se outra requisição guardou o mesmo tema enquanto a IA respondia, vale o que já estava lá.
    registro, _ = ConteudoGerado.objects.get_or_create(tema_chave=chave, defaults=campos)
    return registro.como_dict(), False


def invalidar_tema(tema):
    """Apaga o tema do cache (para gerar de novo). Devolve True se havia algo guardado."""
    apagados, _ = ConteudoGerado.objects.filter(tema_chave=chave_do_tema(tema)).delete()
    return apagados > 0
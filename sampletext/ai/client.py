"""Cliente do Gemini Developer API usando o SDK oficial do Google (#15)."""
import socket

from django.conf import settings
from google import genai
from google.genai import errors, types

from sampletext.ai.errors import ErroIA


# O Gemini aceita um subconjunto de JSON Schema para saída estruturada.
# A validação local continua aplicando os limites e formatos removidos daqui.
_REGRAS_NAO_SUPORTADAS = {"additionalProperties", "maxItems", "maxLength", "minItems", "minLength", "pattern"}


def schema_para_gemini(schema):
    if isinstance(schema, dict):
        return {
            chave: schema_para_gemini(valor)
            for chave, valor in schema.items()
            if chave not in _REGRAS_NAO_SUPORTADAS
        }
    if isinstance(schema, list):
        return [schema_para_gemini(item) for item in schema]
    return schema


def _mensagens_para_gemini(mensagens):
    instrucao_sistema = []
    conteudos = []
    for mensagem in mensagens:
        papel = mensagem.get("role")
        texto = mensagem.get("content")
        if not isinstance(texto, str):
            raise ValueError("Mensagem de IA inválida")
        if papel == "system":
            instrucao_sistema.append(texto)
        elif papel in ("user", "assistant"):
            conteudos.append({
                "role": "user" if papel == "user" else "model",
                "parts": [{"text": texto}],
            })
        else:
            raise ValueError("Papel de mensagem de IA inválido")
    if not conteudos:
        raise ValueError("Nenhuma mensagem de usuário foi fornecida")
    return "\n\n".join(instrucao_sistema), conteudos


def _chamar_gemini(chave, modelo, mensagens, schema, max_tokens, timeout_segundos):
    instrucao_sistema, conteudos = _mensagens_para_gemini(mensagens)
    cliente = genai.Client(
        api_key=chave,
        http_options=types.HttpOptions(
            timeout=round(timeout_segundos * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    try:
        return cliente.models.generate_content(
            model=modelo,
            contents=conteudos,
            config=types.GenerateContentConfig(
                system_instruction=instrucao_sistema or None,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                response_json_schema=schema_para_gemini(schema),
            ),
        )
    finally:
        cliente.close()


class ClienteIA:
    def gerar_json(self, mensagens, schema, nome, max_tokens):
        chave = settings.GEMINI_API_KEY.strip()
        if not chave:
            raise ErroIA("ia_nao_configurada", "O serviço de IA ainda não está configurado.", 503)
        try:
            resposta = _chamar_gemini(
                chave=chave,
                modelo=settings.GEMINI_MODEL,
                mensagens=mensagens,
                schema=schema,
                max_tokens=max_tokens,
                timeout_segundos=settings.AI_TIMEOUT_SECONDS,
            )
        except errors.APIError as erro:
            codigo_http = getattr(erro, "code", None)
            if codigo_http in (401, 403):
                raise ErroIA("ia_configuracao", "O serviço de IA está indisponível. Contate o responsável.", 503) from None
            if codigo_http == 429:
                raise ErroIA("ia_limite", "A IA atingiu seu limite de uso. Tente novamente mais tarde.", 503) from None
            if codigo_http in (408, 504):
                raise ErroIA("ia_timeout", "A IA demorou para responder. Tente novamente.", 504) from None
            raise ErroIA("ia_indisponivel", "Não foi possível gerar o material agora. Tente novamente.") from None
        except (TimeoutError, socket.timeout):
            raise ErroIA("ia_timeout", "A IA demorou para responder. Tente novamente.", 504) from None
        except Exception as erro:
            tipo = type(erro).__name__.lower()
            if "timeout" in tipo:
                raise ErroIA("ia_timeout", "A IA demorou para responder. Tente novamente.", 504) from None
            if "connection" in tipo or "transport" in tipo:
                raise ErroIA("ia_conexao", "Não foi possível conectar ao serviço de IA.", 503) from None
            raise ErroIA("ia_indisponivel", "Não foi possível gerar o material agora. Tente novamente.") from None
        return self._extrair_texto(resposta)

    @staticmethod
    def _extrair_texto(resposta):
        try:
            texto = getattr(resposta, "text", None)
        except (AttributeError, ValueError):
            texto = None
        if isinstance(texto, str) and texto.strip():
            try:
                grande_demais = len(texto.encode("utf-8")) > 2_000_000
            except UnicodeError:
                grande_demais = True
            if grande_demais:
                raise ErroIA("ia_resposta_invalida", "A IA retornou uma resposta inválida. Tente novamente.")
            return texto

        bloqueio = getattr(getattr(resposta, "prompt_feedback", None), "block_reason", None)
        motivo = str(getattr(bloqueio, "name", bloqueio) or "").upper()
        if motivo and "UNSPECIFIED" not in motivo:
            raise ErroIA("ia_recusou", "A IA não pôde atender a esse tema. Tente reformular.", 422)

        candidatos = getattr(resposta, "candidates", None) or []
        motivos = [
            str(getattr(getattr(candidato, "finish_reason", None), "name",
                        getattr(candidato, "finish_reason", ""))).upper()
            for candidato in candidatos
        ]
        if any("SAFETY" in motivo or "BLOCKLIST" in motivo or "PROHIBITED" in motivo for motivo in motivos):
            raise ErroIA("ia_recusou", "A IA não pôde atender a esse tema. Tente reformular.", 422)
        if any("MAX_TOKENS" in motivo for motivo in motivos):
            raise ErroIA("ia_resposta_incompleta", "A IA não concluiu o material. Tente novamente.")
        raise ErroIA("ia_resposta_invalida", "A IA retornou uma resposta vazia ou inválida. Tente novamente.")
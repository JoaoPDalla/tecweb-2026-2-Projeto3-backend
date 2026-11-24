"""Cliente OpenAI Responses, sem SDK ou dependência de views (#15)."""
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .errors import ErroIA


class ClienteIA:
    def gerar_json(self, mensagens, schema, nome, max_tokens):
        chave = settings.AI_API_KEY.strip()
        if not chave:
            raise ErroIA("ia_nao_configurada", "O serviço de IA ainda não está configurado.", 503)
        corpo = {
            "model": settings.AI_MODEL, "input": mensagens, "store": False,
            "max_output_tokens": max_tokens,
            "text": {"format": {"type": "json_schema", "name": nome, "strict": True, "schema": schema}},
        }
        pedido = Request(
            "https://api.openai.com/v1/responses", method="POST",
            data=json.dumps(corpo).encode("utf-8"),
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(pedido, timeout=settings.AI_TIMEOUT_SECONDS) as resposta:
                conteudo = resposta.read(2_000_001)
            if len(conteudo) > 2_000_000:
                raise ValueError("Resposta muito grande")
            dados = json.loads(conteudo)
        except HTTPError as erro:
            if erro.code in (401, 403):
                raise ErroIA("ia_configuracao", "O serviço de IA está indisponível. Contate o responsável.", 503) from None
            if erro.code == 429:
                raise ErroIA("ia_limite", "A IA atingiu seu limite de uso. Tente novamente mais tarde.", 503) from None
            raise ErroIA("ia_indisponivel", "Não foi possível gerar o material agora. Tente novamente.") from None
        except (TimeoutError, socket.timeout):
            raise ErroIA("ia_timeout", "A IA demorou para responder. Tente novamente.", 504) from None
        except URLError as erro:
            if isinstance(erro.reason, (TimeoutError, socket.timeout)):
                raise ErroIA("ia_timeout", "A IA demorou para responder. Tente novamente.", 504) from None
            raise ErroIA("ia_conexao", "Não foi possível conectar ao serviço de IA.", 503) from None
        except OSError:
            raise ErroIA("ia_conexao", "Não foi possível conectar ao serviço de IA.", 503) from None
        except (ValueError, UnicodeError, RecursionError):
            raise ErroIA("ia_resposta_invalida", "A IA retornou uma resposta inválida. Tente novamente.") from None
        return self._extrair_texto(dados)

    @staticmethod
    def _extrair_texto(dados):
        if not isinstance(dados, dict) or dados.get("status") != "completed":
            raise ErroIA("ia_resposta_incompleta", "A IA não concluiu o material. Tente novamente.")
        partes = []
        saida = dados.get("output")
        if not isinstance(saida, list):
            raise ErroIA("ia_resposta_invalida", "A IA retornou uma resposta inválida.")
        for item in saida:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            conteudo = item.get("content")
            if not isinstance(conteudo, list):
                continue
            for parte in conteudo:
                if not isinstance(parte, dict):
                    continue
                if parte.get("type") == "refusal":
                    raise ErroIA("ia_recusou", "A IA não pôde atender a esse tema. Tente reformular.", 422)
                if parte.get("type") == "output_text" and isinstance(parte.get("text"), str):
                    partes.append(parte["text"])
        if not partes or not "".join(partes).strip():
            raise ErroIA("ia_resposta_invalida", "A IA retornou uma resposta vazia.")
        return "".join(partes)
